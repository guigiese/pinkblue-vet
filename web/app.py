import asyncio
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core import run_monitor_loop
from labs import CONNECTORS
from labs.bitlab import BitlabConnector
from notifiers import NOTIFIERS
from notifiers.telegram import get_users, remove_user
from notifiers.telegram_polling import WEBHOOK_SECRET_PATH, handle_update, register_webhook
from notification_settings import NOTIFICATION_TEMPLATE_VARIABLES
from pb_platform.auth import (
    attach_user_to_request,
    auth_bypassed,
    is_admin,
    path_requires_auth,
    redirect_to_login,
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

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_URL = os.environ.get("APP_URL", "https://pinkblue-vet-production.up.railway.app")
STANDARD_STATUSES = ["Pronto", "Parcial", "Em Andamento", "Analisando", "Recebido", "Cancelado"]


@asynccontextmanager
async def lifespan(app):
    monitor_thread = threading.Thread(target=run_monitor_loop, args=(state,), daemon=True)
    monitor_thread.start()
    register_webhook(APP_URL)
    yield


app = FastAPI(lifespan=lifespan, title="PinkBlue Vet")
router = APIRouter(prefix="/labmonitor")
app.mount("/ops-map-static", StaticFiles(directory=str(OPS_MAP_DIR)), name="ops_map_static")
app.mount("/sandboxes/cards-static", StaticFiles(directory=str(CARD_SANDBOX_DIR)), name="cards_sandbox_static")


@app.middleware("http")
async def platform_auth_middleware(request: Request, call_next):
    if auth_bypassed(request):
        request.state.user = {"email": "tests@pinkbluevet.local", "role": "admin"}
        return await call_next(request)
    user = attach_user_to_request(request)
    if path_requires_auth(request.url.path) and not user:
        return redirect_to_login(request)
    if user and request.url.path == "/login":
        return RedirectResponse(url="/", status_code=303)
    return await call_next(request)


def _render(request: Request, template: str, **ctx):
    return templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "platform_name": settings.app_name,
            "module_name": settings.module_name,
            "platform_user": getattr(request.state, "user", None),
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
    user = store.authenticate_user(email, password)
    if not user:
        return _render(request, "login.html", next=next or "/", error="Email ou senha invÃ¡lidos.")

    token = store.create_session(user["id"])
    response = RedirectResponse(url=next or "/", status_code=303)
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


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _render(request, "index.html", users=store.list_users())


@app.get("/admin/usuarios", response_class=HTMLResponse)
async def users_admin(request: Request, saved: str = ""):
    if not is_admin(request):
        return RedirectResponse(url="/", status_code=303)
    return _render(request, "admin_users.html", users=store.list_users(), save_state=saved)


@app.post("/admin/usuarios")
async def create_platform_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("viewer"),
):
    if not is_admin(request):
        return RedirectResponse(url="/", status_code=303)
    store.create_user(email=email, password=password, role=role)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/usuarios/{user_id}/senha")
async def update_platform_user_password(
    request: Request,
    user_id: int,
    password: str = Form(...),
):
    if not is_admin(request):
        return RedirectResponse(url="/", status_code=303)
    store.set_user_password(user_id, password, force_password_change=False)
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


@app.post("/admin/usuarios/{user_id}/toggle")
async def toggle_platform_user(request: Request, user_id: int):
    if not is_admin(request):
        return RedirectResponse(url="/", status_code=303)
    user = store.get_user_by_id(user_id)
    if user:
        store.set_user_active(user_id, not user["is_active"])
    return RedirectResponse(url="/admin/usuarios?saved=1", status_code=303)


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
    return _render(
        request,
        "exames.html",
        groups=state.get_exames(lab, status, q),
        variant_cfg=variant_cfg,
        result_fetch_prefix="/labmonitor/partials/resultado",
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
    return _render(
        request,
        "thresholds.html",
        thresholds=state.list_exam_thresholds(),
        save_state=saved,
        default_warning=1.0,
        default_critical=1.2,
    )


@router.get("/partials/notifications", response_class=HTMLResponse)
async def partial_notifications(request: Request):
    return _render(request, "partials/notifications.html", notifications=state.notifications)


@router.get("/partials/lab_counts", response_class=HTMLResponse)
async def partial_lab_counts(request: Request):
    return _render(request, "partials/lab_counts.html", lab_counts=state.get_lab_counts())


@router.get("/partials/exames", response_class=HTMLResponse)
async def partial_exames(request: Request, lab: str = "", status: str = "", q: str = ""):
    variant_cfg = get_card_sandbox_variant("v0-reference-current")
    return _render(
        request,
        "partials/exames_table.html",
        groups=state.get_exames(lab, status, q),
        variant_cfg=variant_cfg,
        result_fetch_prefix="/labmonitor/partials/resultado",
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
    warning_multiplier: float = Form(...),
    critical_multiplier: float = Form(...),
):
    updated_by = (getattr(request.state, "user", None) or {}).get("email", "")
    state.save_exam_threshold(
        exam_name.strip(),
        warning_multiplier=warning_multiplier,
        critical_multiplier=critical_multiplier,
        updated_by=updated_by,
    )
    return RedirectResponse("/labmonitor/tolerancias?saved=1", status_code=303)


@router.post("/tolerancias/{exam_slug}/remover")
async def delete_threshold(exam_slug: str):
    state.delete_exam_threshold(exam_slug)
    return RedirectResponse("/labmonitor/tolerancias?saved=1", status_code=303)


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
    connector = BitlabConnector()
    rows, report_text, diagnosis_text = _find_cached_resultado(item_id)
    record = _find_result_record(item_id)

    if rows is None and not report_text:
        try:
            token = connector._login()
            raw = connector.buscar_resultado_html(token, item_id)
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
        except Exception as e:
            return HTMLResponse(f'<p class="text-red-500 text-xs p-3">Erro ao carregar resultado: {e}</p>')

    return _render(
        request,
        "partials/resultado_bitlab.html",
        rows=rows or [],
        report_text=report_text or "",
        diagnosis_text=diagnosis_text or "",
    )


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


def _find_result_record(item_id: str) -> dict | None:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    return record
    return None


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

