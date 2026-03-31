import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web.state import state
from core import run_monitor_loop
from labs import CONNECTORS
from notifiers import NOTIFIERS
from notifiers.telegram import get_users, remove_user
from notifiers.telegram_polling import (
    handle_update,
    register_webhook,
    WEBHOOK_SECRET_PATH,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_URL = os.environ.get("APP_URL", "https://pinkblue-vet-production.up.railway.app")
STANDARD_STATUSES = ["Pronto", "Parcial", "Em Andamento", "Analisando", "Recebido", "Arquivado", "Cancelado"]


@asynccontextmanager
async def lifespan(app):
    # Monitor loop
    monitor_thread = threading.Thread(target=run_monitor_loop, args=(state,), daemon=True)
    monitor_thread.start()

    # Register Telegram webhook (replaces polling — no thread needed)
    register_webhook(APP_URL)

    yield


app = FastAPI(lifespan=lifespan, title="PinkBlue Vet")
router = APIRouter(prefix="/labmonitor")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _render(request, template, **ctx):
    return templates.TemplateResponse(template, {"request": request, **ctx})


# ── Telegram Webhook ─────────────────────────────────────────────────────────

@app.post(f"/telegram/webhook/{WEBHOOK_SECRET_PATH}")
async def telegram_webhook(request: Request):
    """Receives Telegram updates via webhook. One update = one response, no polling race."""
    try:
        update = await request.json()
        handle_update(update)
    except Exception as e:
        print(f"[Webhook] Erro ao processar update: {e}")
    return JSONResponse({"ok": True})


# ── Landing page ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _render(request, "index.html")


# ── Lab Monitor Pages ─────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(request, "dashboard.html",
                   lab_counts=state.get_lab_counts(),
                   notifications=state.notifications)


@router.get("/", response_class=HTMLResponse)
async def dashboard_slash(request: Request):
    return _render(request, "dashboard.html",
                   lab_counts=state.get_lab_counts(),
                   notifications=state.notifications)


@router.get("/exames", response_class=HTMLResponse)
async def exames(request: Request, lab: str = "", status: str = "", q: str = ""):
    return _render(request, "exames.html",
                   groups=state.get_exames(lab, status, q),
                   labs_cfg=state.config["labs"],
                   statuses=STANDARD_STATUSES,
                   lab_filter=lab,
                   status_filter=status,
                   q=q)


@router.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    return _render(request, "labs.html",
                   labs=state.config["labs"],
                   last_check=state.last_check,
                   last_error=state.last_error)


@router.get("/canais", response_class=HTMLResponse)
async def canais_page(request: Request):
    return _render(request, "canais.html",
                   notifiers=state.config["notifiers"],
                   telegram_users=get_users())


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _render(request, "settings.html",
                   config=state.config)


# ── HTMX Partials ─────────────────────────────────────────────────────────────

@router.get("/partials/notifications", response_class=HTMLResponse)
async def partial_notifications(request: Request):
    return _render(request, "partials/notifications.html",
                   notifications=state.notifications)


@router.get("/partials/lab_counts", response_class=HTMLResponse)
async def partial_lab_counts(request: Request):
    return _render(request, "partials/lab_counts.html",
                   lab_counts=state.get_lab_counts())


@router.get("/partials/exames", response_class=HTMLResponse)
async def partial_exames(request: Request, lab: str = "", status: str = "", q: str = ""):
    return _render(request, "partials/exames_table.html",
                   groups=state.get_exames(lab, status, q))


@router.get("/partials/telegram-users", response_class=HTMLResponse)
async def partial_telegram_users(request: Request):
    return _render(request, "partials/telegram_users.html",
                   telegram_users=get_users())


# ── Actions ───────────────────────────────────────────────────────────────────

@router.post("/labs/{lab_id}/toggle", response_class=HTMLResponse)
async def toggle_lab(request: Request, lab_id: str):
    state.toggle_lab(lab_id)
    lab = next(l for l in state.config["labs"] if l["id"] == lab_id)
    return HTMLResponse(_toggle_html("labs", lab_id, lab.get("enabled", True), lab["name"]))


@router.post("/canais/{notifier_id}/toggle", response_class=HTMLResponse)
async def toggle_notifier(request: Request, notifier_id: str):
    state.toggle_notifier(notifier_id)
    n = next(x for x in state.config["notifiers"] if x["id"] == notifier_id)
    return HTMLResponse(_toggle_html("canais", notifier_id, n.get("enabled", True), n["id"].capitalize()))


@router.post("/labs/{lab_id}/test", response_class=HTMLResponse)
async def test_lab(lab_id: str):
    lab_cfg = next((l for l in state.config["labs"] if l["id"] == lab_id), None)
    if not lab_cfg or lab_cfg["connector"] not in CONNECTORS:
        return HTMLResponse('<span class="text-red-600 text-sm">Lab não encontrado</span>')
    try:
        connector = CONNECTORS[lab_cfg["connector"]]()
        snap = connector.snapshot()
        return HTMLResponse(f'<span class="text-green-600 text-sm">✓ Conexão OK — {len(snap)} registros</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">✗ Erro: {e}</span>')


@router.post("/canais/{notifier_id}/test", response_class=HTMLResponse)
async def test_notifier(notifier_id: str):
    n_cfg = next((n for n in state.config["notifiers"] if n["id"] == notifier_id), None)
    if not n_cfg or n_cfg["type"] not in NOTIFIERS:
        return HTMLResponse('<span class="text-red-600 text-sm">Canal não encontrado</span>')
    try:
        notifier = NOTIFIERS[n_cfg["type"]]()
        notifier.enviar("🔔 <b>Teste — Lab Monitor</b>\nCanal funcionando!")
        return HTMLResponse('<span class="text-green-600 text-sm">✓ Mensagem enviada</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">✗ Erro: {e}</span>')


@router.post("/canais/telegram/users/{chat_id}/remove", response_class=HTMLResponse)
async def remove_telegram_user(request: Request, chat_id: str):
    remove_user(chat_id)
    return _render(request, "partials/telegram_users.html",
                   telegram_users=get_users())


@router.post("/settings/interval", response_class=HTMLResponse)
async def save_interval(minutes: int = Form(...)):
    state.set_interval(max(1, minutes))
    return HTMLResponse(f'<span class="text-green-600 text-sm">✓ Intervalo atualizado para {minutes} min</span>')


# ── Helper ────────────────────────────────────────────────────────────────────

def _toggle_html(route: str, id: str, enabled: bool, label: str) -> str:
    checked = "checked" if enabled else ""
    status_text  = "Habilitado" if enabled else "Desabilitado"
    status_color = "text-green-600" if enabled else "text-gray-400"
    return f'''
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
    </div>'''


app.include_router(router)
