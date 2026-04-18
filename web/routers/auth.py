from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from modules.lab_monitor.notifiers.telegram_polling import WEBHOOK_SECRET_PATH, handle_update
from pb_platform.auth import (
    can_access_target,
    default_redirect_for_user,
    no_access_response,
    preferred_redirect_for_user,
)
from pb_platform.settings import settings
from pb_platform.storage import store
from web.shared import _render

router = APIRouter()


@router.post(f"/telegram/webhook/{WEBHOOK_SECRET_PATH}")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        handle_update(update)
    except Exception as e:
        print(f"[Webhook] Erro ao processar update: {e}")
    return JSONResponse({"ok": True})


@router.get("/login")
async def login_page(request: Request, next: str = "/", error: str = ""):
    from fastapi.responses import HTMLResponse
    return _render(request, "login.html", next=next, error=error)


@router.post("/login")
async def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    _ERROR_MAP = {
        "invalid": "E-mail ou senha inválidos.",
        "locked": "Conta bloqueada temporariamente. Tente novamente em alguns minutos.",
        "pending": "Seu cadastro ainda está aguardando aprovação.",
        "rejected": "Seu cadastro foi rejeitado. Entre em contato com a clínica.",
        "inactive": "Conta desativada. Entre em contato com a clínica.",
    }
    user, code = store.authenticate_user(email, password)
    if not user:
        return _render(request, "login.html", next=next or "/", error=_ERROR_MAP.get(code, "Erro ao entrar."))

    token = store.create_session(user["id"])
    destination = next or default_redirect_for_user(user)
    if destination and not can_access_target(user, destination):
        destination = preferred_redirect_for_user(user)
    if not destination:
        response = no_access_response(user)
        response.set_cookie(
            settings.session_cookie_name,
            token,
            httponly=True,
            samesite="lax",
            max_age=settings.session_ttl_days * 24 * 60 * 60,
        )
        return response
    response = RedirectResponse(url=destination, status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    store.revoke_session(request.cookies.get(settings.session_cookie_name))
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


@router.get("/cadastro")
async def cadastro_page(request: Request, erro: str = ""):
    from fastapi.responses import HTMLResponse
    return _render(request, "cadastro.html", erro=erro)


@router.post("/cadastro")
async def cadastro_action(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    role: str = Form(...),
    telefone: str = Form(""),
    crmv: str = Form(""),
):
    from pb_platform.storage import EXTERNAL_ROLES
    erros = []
    if password != password_confirm:
        erros.append("As senhas não coincidem.")
    if len(password) < 8:
        erros.append("A senha deve ter no mínimo 8 caracteres.")
    if role not in EXTERNAL_ROLES:
        erros.append("Categoria inválida.")
    if role == "veterinario" and not crmv.strip():
        erros.append("CRMV é obrigatório para veterinários.")
    if erros:
        return _render(request, "cadastro.html", erro=" ".join(erros), dados={
            "nome": nome, "email": email, "role": role, "telefone": telefone,
        })
    try:
        novo_usuario = store.create_user_request(
            email=email.strip().lower(),
            password=password,
            role=role,
            nome=nome.strip(),
            telefone=telefone.strip(),
            crmv=crmv.strip(),
        )
    except ValueError as exc:
        return _render(request, "cadastro.html", erro=str(exc))
    try:
        from modules.plantao.notifications import notificar_gestores
        from modules.plantao.router import _engine as _plantao_engine
        role_label = {"veterinario": "Veterinário", "auxiliar": "Auxiliar", "colaborador": "Colaborador"}.get(role, role)
        nome_display = nome.strip() or email.strip().lower()
        notificar_gestores(
            _plantao_engine,
            "novo_cadastro",
            f"Novo cadastro pendente: {nome_display}",
            f"{role_label} · {email.strip().lower()}",
            entidade="users",
            entidade_id=novo_usuario.get("id"),
            permissao="plantao_aprovar_cadastros",
        )
    except Exception:
        pass
    return RedirectResponse("/cadastro/aguardando", status_code=303)


@router.get("/cadastro/aguardando")
async def cadastro_aguardando(request: Request):
    from fastapi.responses import HTMLResponse
    return _render(request, "cadastro_aguardando.html")
