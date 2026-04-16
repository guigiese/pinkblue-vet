import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import run_historical_backfill_until_complete, run_monitor_loop
from labs import CONNECTORS
from labs.bitlab import BitlabConnector
from modules.plantao.schema import init_schema
from modules.plantao.router import make_router as make_plantao_router
from modules.plantao.jobs import run_plantao_jobs
from notifiers import NOTIFIERS
from notifiers.telegram import get_users, remove_user
from notifiers.telegram_polling import WEBHOOK_SECRET_PATH, handle_update, register_webhook
from notification_settings import NOTIFICATION_TEMPLATE_VARIABLES
from pb_platform.auth import (
    attach_user_to_request,
    auth_bypassed,
    can_access_target,
    default_redirect_for_user,
    forbidden_response,
    gerar_csrf_token,
    has_permission,
    no_access_response,
    path_requires_auth,
    preferred_redirect_for_user,
    required_permission,
    redirect_to_login,
    user_permissions,
)
from pb_platform.settings import settings
from pb_platform.storage import store
from web.card_sandbox import (
    CARD_SANDBOX_DIR,
    CARD_SANDBOX_VARIANTS,
    DEFAULT_CARD_SANDBOX_VARIANT,
    get_card_sandbox_groups,
    get_card_sandbox_runtime,
    get_card_sandbox_variant,
)
from web.ops_map import OPS_MAP_DIR, get_ops_map_runtime
from web.state import state
from web.text_reports import build_report_sections

# ── Módulo Plantão — engine compartilhado com a plataforma ───────────────────
plantao_engine = store.engine

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_URL = os.environ.get("APP_URL", "https://pinkblue-vet-production.up.railway.app")
STANDARD_STATUSES = ["Pronto", "Parcial", "Em Andamento", "Analisando", "Recebido", "Cancelado"]
EXAMES_PAGE_SIZE = 20


def _default_module_name(path: str) -> str:
    if path.startswith("/labmonitor"):
        return "Lab Monitor"
    if path.startswith("/plantao"):
        return "Plantão"
    return "Plataforma"


@asynccontextmanager
async def lifespan(app):
    # Plataforma principal
    monitor_thread = threading.Thread(target=run_monitor_loop, args=(state,), daemon=True)
    monitor_thread.start()
    register_webhook(APP_URL)
    # Módulo Plantão
    init_schema(plantao_engine)
    plantao_jobs_thread = threading.Thread(
        target=run_plantao_jobs, args=(plantao_engine,), daemon=True
    )
    plantao_jobs_thread.start()
    yield


app = FastAPI(lifespan=lifespan, title="PinkBlue Vet")
router = APIRouter(prefix="/labmonitor")
app.mount("/ops-map-static", StaticFiles(directory=str(OPS_MAP_DIR)), name="ops_map_static")
app.mount("/sandboxes/cards-static", StaticFiles(directory=str(CARD_SANDBOX_DIR)), name="cards_sandbox_static")

# ── Módulo Plantão ────────────────────────────────────────────────────────────
# Rotas /plantao/* usam a mesma autenticação e o mesmo banco da plataforma.
app.include_router(make_plantao_router(plantao_engine))


@app.middleware("http")
async def platform_auth_middleware(request: Request, call_next):
    if auth_bypassed(request):
        request.state.user = {"email": "tests@pinkbluevet.local", "role": "admin",
                               "nome": "Teste", "status": "ativo"}
        return await call_next(request)

    user = attach_user_to_request(request)

    # Gera token CSRF vinculado à sessão e disponibiliza para templates
    session_token = request.cookies.get(settings.session_cookie_name, "")
    request.state.csrf_token = gerar_csrf_token(session_token)

    if path_requires_auth(request.url.path) and not user:
        return redirect_to_login(request)
    if user and request.url.path == "/login":
        return RedirectResponse(url=default_redirect_for_user(user), status_code=303)
    if user and request.url.path == "/cadastro":
        return RedirectResponse(url=default_redirect_for_user(user), status_code=303)
    permission = required_permission(request.url.path, request.method)
    if permission and user and not has_permission(request, permission):
        return forbidden_response(request)
    return await call_next(request)


def _render(request: Request, template: str, **ctx):
    platform_user = getattr(request.state, "user", None)
    module_name = ctx.pop("module_name", _default_module_name(request.url.path))
    return templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "platform_name": settings.app_name,
            "module_name": module_name,
            "platform_user": platform_user,
            "platform_permissions": user_permissions(platform_user) if platform_user else {},
            "is_dev": settings.is_dev,
            **ctx,
        },
    )


@app.post(f"/telegram/webhook/{WEBHOOK_SECRET_PATH}")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        handle_update(update)
    except Exception as e:
        print(f"[Webhook] Erro ao processar update: {e}")
    return JSONResponse({"ok": True})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/", error: str = ""):
    return _render(request, "login.html", next=next, error=error)


@app.post("/login")
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


@app.get("/logout")
async def logout(request: Request):
    store.revoke_session(request.cookies.get(settings.session_cookie_name))
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


# ── Cadastro público (auto-registro com aprovação) ────────────────────────────

@app.get("/cadastro", response_class=HTMLResponse)
async def cadastro_page(request: Request, erro: str = ""):
    return _render(request, "cadastro.html", erro=erro)


@app.post("/cadastro")
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
    # Notificar gestores sobre novo cadastro pendente
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
        pass  # Notificação é best-effort
    return RedirectResponse("/cadastro/aguardando", status_code=303)


@app.get("/cadastro/aguardando", response_class=HTMLResponse)
async def cadastro_aguardando(request: Request):
    return _render(request, "cadastro_aguardando.html")


# ── Aprovação de cadastros pendentes ─────────────────────────────────────────

@app.post("/admin/usuarios/{user_id}/aprovar")
async def aprovar_usuario(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.approve_user(user_id, approved_by_id=(getattr(request.state, "user", None) or {}).get("id"))
    return RedirectResponse(url="/admin/usuarios?saved=aprovado", status_code=303)


@app.post("/admin/usuarios/{user_id}/rejeitar")
async def rejeitar_usuario(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.reject_user(user_id)
    return RedirectResponse(url="/admin/usuarios?saved=rejeitado", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    platform_user = getattr(request.state, "user", None)
    if platform_user:
        perms = user_permissions(platform_user)
        has_labmonitor = perms.get("labmonitor_access") or perms.get("manage_labmonitor")
        has_plantao = perms.get("plantao_access") or perms.get("manage_plantao")
        modules_count = sum([bool(has_labmonitor), bool(has_plantao)])
        if modules_count == 1:
            if has_plantao:
                return RedirectResponse(url="/plantao/", status_code=302)
            if has_labmonitor:
                return RedirectResponse(url="/labmonitor", status_code=302)
    return _render(request, "index.html", users=store.list_users())


@app.get("/admin/usuarios", response_class=HTMLResponse)
async def users_admin(request: Request, saved: str = ""):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ROLE_LABELS
    _PERM_LABELS = {
        "platform_access": "Home da plataforma",
        "labmonitor_access": "Lab Monitor",
        "manage_labmonitor": "Gerenciar Lab Monitor",
        "ops_tools": "Ops-map e sandboxes",
        "manage_users": "Administrar acessos",
        "plantao_access": "Módulo Plantão",
        "manage_plantao": "Gerenciar Plantão",
    }
    return _render(
        request,
        "admin_users.html",
        users=store.list_users(),
        pending_users=store.list_pending_users(),
        roles=store.list_roles(),
        permissions=store.get_role_permissions(),
        all_permissions=_PERM_LABELS,
        role_labels=ROLE_LABELS,
        profiles=store.list_profiles(),
        save_state=saved,
    )


@app.post("/admin/usuarios")
async def create_platform_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("viewer"),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.create_user(email=email, password=password, role=role)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/usuarios/{user_id}/role")
async def update_platform_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.set_user_role(user_id, role)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/usuarios/{user_id}/senha")
async def update_platform_user_password(
    request: Request,
    user_id: int,
    password: str = Form(...),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.set_user_password(user_id, password, force_password_change=False)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/usuarios/{user_id}/toggle")
async def toggle_platform_user(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    user = store.get_user_by_id(user_id)
    if user:
        store.set_user_active(user_id, not user["is_active"])
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/permissoes")
async def update_role_permissions(
    request: Request,
    role: str = Form(...),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ALL_PERMISSIONS
    form = await request.form()
    permissions = {p: form.get(p) == "on" for p in ALL_PERMISSIONS}
    store.save_role_permissions(role, permissions)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


# ── Perfis customizáveis ─────────────────────────────────────────────────────

_PERM_LABELS_GLOBAL = {
    "platform_access": "Home da plataforma",
    "labmonitor_access": "Lab Monitor",
    "manage_labmonitor": "Gerenciar Lab Monitor",
    "ops_tools": "Ops-map e sandboxes",
    "manage_users": "Administrar acessos",
    "plantao_access": "Módulo Plantão",
    "manage_plantao": "Gerenciar Plantão",
}


@app.get("/admin/perfis", response_class=HTMLResponse)
async def profiles_page(request: Request, saved: str = "", erro: str = ""):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ROLE_LABELS
    return _render(
        request,
        "admin_profiles.html",
        profiles=store.list_profiles(),
        all_permissions=_PERM_LABELS_GLOBAL,
        role_labels=ROLE_LABELS,
        save_state=saved,
        erro=erro,
    )


@app.post("/admin/perfis")
async def create_profile(
    request: Request,
    nome: str = Form(...),
    descricao: str = Form(""),
    base_role: str = Form("viewer"),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ALL_PERMISSIONS
    form = await request.form()
    permissions = {p: form.get(f"perm_{p}") == "on" for p in ALL_PERMISSIONS}
    try:
        store.create_profile(nome=nome, descricao=descricao, base_role=base_role, permissions=permissions)
    except ValueError as exc:
        return RedirectResponse(url=f"/admin/perfis?erro={exc}", status_code=303)
    return RedirectResponse(url="/admin/perfis?saved=criado", status_code=303)


@app.post("/admin/perfis/{profile_id}")
async def update_profile(
    request: Request,
    profile_id: int,
    nome: str = Form(...),
    descricao: str = Form(""),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ALL_PERMISSIONS
    form = await request.form()
    permissions = {p: form.get(f"perm_{p}") == "on" for p in ALL_PERMISSIONS}
    try:
        store.update_profile(profile_id, nome=nome, descricao=descricao, permissions=permissions)
    except ValueError as exc:
        return RedirectResponse(url=f"/admin/perfis?erro={exc}", status_code=303)
    return RedirectResponse(url="/admin/perfis?saved=atualizado", status_code=303)


@app.post("/admin/perfis/{profile_id}/delete")
async def delete_profile(request: Request, profile_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    try:
        store.delete_profile(profile_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/admin/perfis?erro={exc}", status_code=303)
    return RedirectResponse(url="/admin/perfis?saved=excluido", status_code=303)


@app.post("/admin/usuarios/{user_id}/perfil")
async def assign_user_profile(
    request: Request,
    user_id: int,
    profile_id: str = Form(""),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    pid = int(profile_id) if profile_id and profile_id.isdigit() else None
    store.assign_user_profile(user_id, pid)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


# ── Dev user switcher (apenas em ambiente de desenvolvimento) ─────────────────

if settings.is_dev:
    @app.get("/dev/switch-user", response_class=JSONResponse)
    async def dev_list_users(request: Request):
        users = [
            {"id": u["id"], "email": u["email"], "role": u["role"], "nome": u["nome"]}
            for u in store.list_users()
            if u.get("status") == "ativo"
        ]
        return JSONResponse(users)

    @app.post("/dev/switch-user")
    async def dev_switch_user(request: Request, user_id: int = Form(...)):
        user = store.get_user_by_id(user_id)
        if not user or user.get("status") != "ativo":
            return RedirectResponse(url="/", status_code=303)
        token = store.create_session(user["id"])
        destination = default_redirect_for_user(user)
        response = RedirectResponse(url=destination, status_code=303)
        response.set_cookie(
            settings.session_cookie_name,
            token,
            httponly=True,
            samesite="lax",
            max_age=settings.session_ttl_days * 24 * 60 * 60,
        )
        return response


@app.get("/ops-map", response_class=HTMLResponse)
async def ops_map_redirect():
    return RedirectResponse(url="/ops-map/", status_code=307)


@app.get("/ops-map/", response_class=HTMLResponse)
async def ops_map_page(request: Request):
    return _render(request, "ops_map.html")


@app.get("/ops-map/data/runtime.json", response_class=JSONResponse)
async def ops_map_runtime():
    return JSONResponse(get_ops_map_runtime())


@app.get("/sandboxes/cards", response_class=HTMLResponse)
async def cards_sandbox_redirect():
    return RedirectResponse(url="/sandboxes/cards/", status_code=307)


@app.get("/sandboxes/cards/", response_class=HTMLResponse)
async def cards_sandbox_page(
    request: Request,
    lab: str = "",
    status: str = "",
    q: str = "",
    variant: str = DEFAULT_CARD_SANDBOX_VARIANT,
):
    variant_cfg = get_card_sandbox_variant(variant)
    return _render(
        request,
        "cards_sandbox_mirror.html",
        groups=get_card_sandbox_groups(lab, status, q),
        labs_cfg=state.config["labs"],
        statuses=STANDARD_STATUSES,
        lab_filter=lab,
        status_filter=status,
        q=q,
        variants=CARD_SANDBOX_VARIANTS,
        variant_filter=variant_cfg["id"],
        variant_cfg=variant_cfg,
        default_variant_id=DEFAULT_CARD_SANDBOX_VARIANT,
    )


@app.get("/sandboxes/cards/data/runtime.json", response_class=JSONResponse)
async def cards_sandbox_runtime():
    return JSONResponse(get_card_sandbox_runtime())


@app.get("/sandboxes/cards/partials/exames", response_class=HTMLResponse)
async def cards_sandbox_partial_exames(
    request: Request,
    lab: str = "",
    status: str = "",
    q: str = "",
    variant: str = DEFAULT_CARD_SANDBOX_VARIANT,
):
    variant_cfg = get_card_sandbox_variant(variant)
    return _render(
        request,
        "partials/cards_sandbox_table.html",
        groups=get_card_sandbox_groups(lab, status, q),
        variant_cfg=variant_cfg,
    )


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(
        request,
        "dashboard.html",
        lab_counts=state.get_lab_counts(),
        groups=state.get_ultimos_liberados(),
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard_slash(request: Request):
    return await dashboard(request)


@router.get("/exames", response_class=HTMLResponse)
async def exames(request: Request, lab: str = "", status: str = "", q: str = ""):
    variant_cfg = get_card_sandbox_variant("v0-reference-current")
    page = state.get_exames_page(lab, status, q, offset=0, limit=EXAMES_PAGE_SIZE)
    return _render(
        request,
        "exames.html",
        page=page,
        groups=page["groups"],
        variant_cfg=variant_cfg,
        result_fetch_prefix="/labmonitor/partials/resultado",
        result_text_fetch_prefix="/labmonitor/partials/resultado-texto",
        labs_cfg=state.config["labs"],
        statuses=STANDARD_STATUSES,
        lab_filter=lab,
        status_filter=status,
        q=q,
    )


@router.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    return _render(
        request,
        "labs.html",
        labs=state.config["labs"],
        last_check=state.last_check,
        last_error=state.last_error,
        sync_state={lab["id"]: state.get_lab_sync_state(lab["id"]) for lab in state.config["labs"]},
    )


@router.get("/canais", response_class=HTMLResponse)
async def canais_page(request: Request):
    return _render(
        request,
        "canais.html",
        notifiers=state.config["notifiers"],
        telegram_users=get_users(),
    )


@router.get("/notificacoes", response_class=HTMLResponse)
async def notificacoes_page(request: Request, saved: str = "", reset: str = ""):
    return _render(
        request,
        "notificacoes.html",
        notification_settings=state.get_notification_settings(),
        preview_messages=state.get_notification_previews(),
        notification_variables=NOTIFICATION_TEMPLATE_VARIABLES,
        save_state="saved" if saved else "reset" if reset else "",
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _render(request, "settings.html", config=state.config)


@router.get("/tolerancias", response_class=HTMLResponse)
async def thresholds_page(request: Request, saved: str = ""):
    defaults = store.get_global_thresholds()
    thresholds = []
    for item in state.list_exam_thresholds():
        thresholds.append(
            {
                **item,
                "warning_percent": round(float(item["warning_multiplier"]) * 100, 2),
                "critical_percent": round(float(item["critical_multiplier"]) * 100, 2),
            }
        )
    return _render(
        request,
        "thresholds.html",
        thresholds=thresholds,
        save_state=saved,
        default_warning_percent=round(float(defaults["warning_multiplier"]) * 100, 2),
        default_critical_percent=round(float(defaults["critical_multiplier"]) * 100, 2),
    )


@router.get("/partials/notifications", response_class=HTMLResponse)
async def partial_notifications(request: Request):
    return _render(request, "partials/notifications.html", notifications=state.notifications)


@router.get("/partials/lab_counts", response_class=HTMLResponse)
async def partial_lab_counts(request: Request):
    return _render(request, "partials/lab_counts.html", lab_counts=state.get_lab_counts())


@router.get("/partials/exames", response_class=HTMLResponse)
async def partial_exames(
    request: Request,
    lab: str = "",
    status: str = "",
    q: str = "",
    offset: int = 0,
):
    variant_cfg = get_card_sandbox_variant("v0-reference-current")
    page = state.get_exames_page(lab, status, q, offset=offset, limit=EXAMES_PAGE_SIZE)
    return _render(
        request,
        "partials/exames_table.html",
        page=page,
        groups=page["groups"],
        variant_cfg=variant_cfg,
        result_fetch_prefix="/labmonitor/partials/resultado",
        result_text_fetch_prefix="/labmonitor/partials/resultado-texto",
        lab_filter=lab,
        status_filter=status,
        q=q,
    )


@router.get("/partials/telegram-users", response_class=HTMLResponse)
async def partial_telegram_users(request: Request):
    return _render(request, "partials/telegram_users.html", telegram_users=get_users())


@router.post("/labs/{lab_id}/toggle", response_class=HTMLResponse)
async def toggle_lab(request: Request, lab_id: str):
    state.toggle_lab(lab_id)
    lab = next(l for l in state.config["labs"] if l["id"] == lab_id)
    return HTMLResponse(_toggle_html("labs", lab_id, lab.get("enabled", True), lab["name"]))


@router.post("/canais/{notifier_id}/toggle", response_class=HTMLResponse)
async def toggle_notifier(request: Request, notifier_id: str):
    state.toggle_notifier(notifier_id)
    notifier = next(x for x in state.config["notifiers"] if x["id"] == notifier_id)
    return HTMLResponse(
        _toggle_html("canais", notifier_id, notifier.get("enabled", True), notifier["id"].capitalize())
    )


@router.post("/labs/{lab_id}/test", response_class=HTMLResponse)
async def test_lab(lab_id: str):
    lab_cfg = next((l for l in state.config["labs"] if l["id"] == lab_id), None)
    if not lab_cfg or lab_cfg["connector"] not in CONNECTORS:
        return HTMLResponse('<span class="text-red-600 text-sm">Lab nÃ£o encontrado</span>')
    try:
        connector = CONNECTORS[lab_cfg["connector"]]()
        connector.sync_hints = state.sync_context(lab_id)
        if hasattr(connector, "test_connection"):
            message = await asyncio.to_thread(connector.test_connection)
        else:
            snap = await asyncio.to_thread(connector.snapshot)
            message = f"Conexao OK - {len(snap)} registros"
        return HTMLResponse(f'<span class="text-green-600 text-sm">{message}</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">âœ• Erro: {e}</span>')


@router.post("/canais/{notifier_id}/test", response_class=HTMLResponse)
async def test_notifier(notifier_id: str):
    n_cfg = next((n for n in state.config["notifiers"] if n["id"] == notifier_id), None)
    if not n_cfg or n_cfg["type"] not in NOTIFIERS:
        return HTMLResponse('<span class="text-red-600 text-sm">Canal nÃ£o encontrado</span>')
    try:
        notifier = NOTIFIERS[n_cfg["type"]]()
        message = "Teste - Lab Monitor\nCanal funcionando!"
        if hasattr(notifier, "send_test"):
            await asyncio.to_thread(notifier.send_test, message)
        else:
            await asyncio.to_thread(notifier.enviar, message)
        return HTMLResponse('<span class="text-green-600 text-sm">âœ“ Mensagem enviada</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">âœ• Erro: {e}</span>')



@router.post("/canais/telegram/users/{chat_id}/remove", response_class=HTMLResponse)
async def remove_telegram_user(request: Request, chat_id: str):
    remove_user(chat_id)
    return _render(request, "partials/telegram_users.html", telegram_users=get_users())


@router.post("/notificacoes/salvar")
async def save_notificacoes(
    received_enabled: str | None = Form(None),
    completed_enabled: str | None = Form(None),
    status_update_enabled: str | None = Form(None),
    received_template: str = Form(...),
    completed_template: str = Form(...),
    status_update_template: str = Form(...),
):
    state.update_notification_settings(
        received_enabled=received_enabled == "on",
        completed_enabled=completed_enabled == "on",
        status_update_enabled=status_update_enabled == "on",
        received_template=received_template,
        completed_template=completed_template,
        status_update_template=status_update_template,
    )
    return RedirectResponse("/labmonitor/notificacoes?saved=1", status_code=303)


@router.post("/notificacoes/resetar")
async def reset_notificacoes():
    state.reset_notification_settings()
    return RedirectResponse("/labmonitor/notificacoes?reset=1", status_code=303)


@router.post("/settings/interval", response_class=HTMLResponse)
async def save_interval(minutes: int = Form(...)):
    state.set_interval(max(1, minutes))
    return HTMLResponse(f'<span class="text-green-600 text-sm">âœ“ Intervalo atualizado para {minutes} min</span>')


@router.post("/tolerancias/salvar")
async def save_threshold(
    request: Request,
    exam_name: str = Form(...),
    warning_percent: float = Form(...),
    critical_percent: float = Form(...),
):
    updated_by = (getattr(request.state, "user", None) or {}).get("email", "")
    state.save_exam_threshold(
        exam_name.strip(),
        warning_multiplier=max(warning_percent, 0) / 100.0,
        critical_multiplier=max(critical_percent, 0) / 100.0,
        updated_by=updated_by,
    )
    return RedirectResponse("/labmonitor/tolerancias?saved=1", status_code=303)


@router.post("/tolerancias/geral")
async def save_global_thresholds(
    warning_percent: float = Form(...),
    critical_percent: float = Form(...),
):
    store.save_global_thresholds(
        warning_multiplier=max(warning_percent, 0) / 100.0,
        critical_multiplier=max(critical_percent, 0) / 100.0,
    )
    return RedirectResponse("/labmonitor/tolerancias?saved=1", status_code=303)


@router.post("/tolerancias/{exam_slug}/remover")
async def delete_threshold(exam_slug: str):
    state.delete_exam_threshold(exam_slug)
    return RedirectResponse("/labmonitor/tolerancias?saved=1", status_code=303)


@router.post("/sync/historico", response_class=HTMLResponse)
async def trigger_history_sync():
    thread = threading.Thread(
        target=run_historical_backfill_until_complete,
        args=(state,),
        kwargs={"max_windows_per_lab": 3},
        daemon=True,
    )
    thread.start()
    return HTMLResponse('<span class="text-green-600 text-sm">Backfill historico iniciado em segundo plano.</span>')


def _toggle_html(route: str, id: str, enabled: bool, label: str) -> str:
    checked = "checked" if enabled else ""
    status_text = "Habilitado" if enabled else "Desabilitado"
    status_color = "text-green-600" if enabled else "text-gray-400"
    return f"""
    <div id="toggle-{id}" class="flex items-center gap-3">
      <label class="toggle-switch" title="{status_text}">
        <input type="checkbox" {checked}
               hx-post="/labmonitor/{route}/{id}/toggle"
               hx-target="#toggle-{id}"
               hx-swap="outerHTML"
               hx-trigger="change">
        <span class="toggle-track"></span>
        <span class="toggle-thumb"></span>
      </label>
      <span class="text-sm font-medium {status_color}">{status_text}</span>
    </div>"""


@router.get("/partials/resultado/{item_id:path}", response_class=HTMLResponse)
async def partial_resultado(request: Request, item_id: str):
    try:
        rows, report_text, diagnosis_text, _record = _load_resultado_payload(item_id)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-500 text-xs p-3">Erro ao carregar resultado: {e}</p>')

    return _render(
        request,
        "partials/resultado_bitlab.html",
        rows=rows or [],
        report_text=report_text or "",
        diagnosis_text=diagnosis_text or "",
    )


@router.get("/partials/resultado-texto/{item_id:path}", response_class=HTMLResponse)
async def partial_text_report(request: Request, item_id: str):
    try:
        rows, report_text, diagnosis_text, record = _load_resultado_payload(item_id)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-500 text-xs p-3">Erro ao carregar laudo: {e}</p>')

    if rows and not report_text:
        return HTMLResponse('<p class="text-gray-500 text-sm p-4">Esse exame possui resultado numerico inline.</p>')

    sections = build_report_sections(report_text or "", diagnosis_text or "")
    item = _find_result_item(item_id)
    return _render(
        request,
        "partials/report_text_modal.html",
        item=item or {},
        record=record or {},
        sections=sections,
    )


@router.get("/partials/historico-paciente", response_class=HTMLResponse)
async def partial_patient_history(
    request: Request,
    patient_name: str = "",
    tutor_name: str = "",
):
    history = state.get_patient_history(patient_name, tutor_name)
    return _render(request, "partials/patient_history.html", history=history)


def _find_cached_resultado(item_id: str) -> tuple[list[dict] | None, str, str]:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    if "resultado" in item or item.get("report_text"):
                        return (
                            item.get("resultado"),
                            item.get("report_text") or "",
                            item.get("diagnosis_text") or "",
                        )
    return None, "", ""


def _find_result_record(item_id: str) -> tuple[str, dict] | tuple[None, None]:
    for lab_id, snap in state.snapshots.items():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    return lab_id, record
    return None, None


def _find_result_item(item_id: str) -> dict | None:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    return item
    return None


def _load_resultado_payload(item_id: str) -> tuple[list[dict], str, str, dict | None]:
    rows, report_text, diagnosis_text = _find_cached_resultado(item_id)
    lab_id, record = _find_result_record(item_id)
    if rows is not None or report_text:
        return rows or [], report_text or "", diagnosis_text or "", record

    if lab_id != "bitlab":
        return [], report_text or "", diagnosis_text or "", record

    connector = BitlabConnector()
    token = connector._login()
    raw = connector.buscar_resultado_payload(token, item_id)
    rows = connector.parse_resultado(raw, record)
    report_text = ""
    diagnosis_text = ""
    if not rows:
        report_text = connector.parse_resultado_text(raw)
    _cache_resultado(
        item_id,
        rows or [],
        report_text=report_text,
        diagnosis_text=diagnosis_text,
    )
    return rows or [], report_text or "", diagnosis_text or "", record


def _cache_resultado(
    item_id: str,
    rows: list[dict],
    *,
    report_text: str = "",
    diagnosis_text: str = "",
) -> None:
    alert_rank = {None: 0, "yellow": 1, "red": 2}
    worst = max((row.get("alerta") for row in rows), key=lambda level: alert_rank.get(level, 0), default=None)

    for lab_id, snap in state.snapshots.items():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    item["resultado"] = rows
                    item["alerta"] = worst
                    if report_text:
                        item["report_text"] = report_text
                    if diagnosis_text:
                        item["diagnosis_text"] = diagnosis_text
                    state.save_lab_runtime(lab_id)
                    return


@router.get("/partials/ultimos_liberados", response_class=HTMLResponse)
async def partial_ultimos_liberados(request: Request):
    return _render(request, "partials/ultimos_liberados.html", groups=state.get_ultimos_liberados())


app.include_router(router)

