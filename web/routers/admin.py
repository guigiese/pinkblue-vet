from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pb_platform.auth import has_permission, user_permissions
from pb_platform.settings import settings
from pb_platform.storage import store
from web.shared import _render, _default_module_name

router = APIRouter()

_PERM_LABELS_GLOBAL = {
    # Plataforma
    "platform_access": "Home da plataforma",
    "manage_users": "Administrar acessos (usuários e perfis)",
    "ops_tools": "Ops-map e sandboxes",
    # Lab Monitor
    "labmonitor_access": "Lab Monitor — visualizar",
    "manage_labmonitor": "Lab Monitor — gerenciar",
    "manage_labmonitor_labs": "Lab Monitor — configurar laboratórios",
    "manage_labmonitor_settings": "Lab Monitor — configurações",
    # Plantão
    "plantao_access": "Plantão — acesso (plantonista)",
    "manage_plantao": "Plantão — gerenciar (todos os sub-itens)",
    "plantao_gerir_escalas": "Plantão — criar e editar escalas",
    "plantao_aprovar_candidaturas": "Plantão — aprovar/recusar candidaturas",
    "plantao_aprovar_cadastros": "Plantão — aprovar cadastros de plantonistas",
    "plantao_ver_relatorios": "Plantão — relatórios e audit log",
}


@router.post("/admin/usuarios/{user_id}/aprovar")
async def aprovar_usuario(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.approve_user(user_id, approved_by_id=(getattr(request.state, "user", None) or {}).get("id"))
    return RedirectResponse(url="/admin/usuarios?saved=aprovado", status_code=303)


@router.post("/admin/usuarios/{user_id}/rejeitar")
async def rejeitar_usuario(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.reject_user(user_id)
    return RedirectResponse(url="/admin/usuarios?saved=rejeitado", status_code=303)


@router.get("/admin/usuarios")
async def users_admin(request: Request, saved: str = ""):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    from pb_platform.storage import ROLE_LABELS
    return _render(
        request,
        "admin_users.html",
        users=store.list_users(),
        pending_users=store.list_pending_users(),
        roles=store.list_roles(),
        permissions=store.get_role_permissions(),
        all_permissions=_PERM_LABELS_GLOBAL,
        role_labels=ROLE_LABELS,
        profiles=store.list_profiles(),
        save_state=saved,
    )


@router.post("/admin/usuarios")
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


@router.post("/admin/usuarios/{user_id}/role")
async def update_platform_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.set_user_role(user_id, role)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@router.post("/admin/usuarios/{user_id}/senha")
async def update_platform_user_password(
    request: Request,
    user_id: int,
    password: str = Form(...),
):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    store.set_user_password(user_id, password, force_password_change=False)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@router.post("/admin/usuarios/{user_id}/toggle")
async def toggle_platform_user(request: Request, user_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    user = store.get_user_by_id(user_id)
    if user:
        store.set_user_active(user_id, not user["is_active"])
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@router.post("/admin/permissoes")
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


@router.get("/admin/perfis")
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


@router.post("/admin/perfis")
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


@router.post("/admin/perfis/{profile_id}")
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


@router.post("/admin/perfis/{profile_id}/delete")
async def delete_profile(request: Request, profile_id: int):
    if not has_permission(request, "manage_users"):
        return RedirectResponse(url="/", status_code=303)
    try:
        store.delete_profile(profile_id)
    except ValueError as exc:
        return RedirectResponse(url=f"/admin/perfis?erro={exc}", status_code=303)
    return RedirectResponse(url="/admin/perfis?saved=excluido", status_code=303)


@router.post("/admin/usuarios/{user_id}/perfil")
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
