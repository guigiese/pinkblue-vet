import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.state import state
from core import run_monitor_loop
from labs import CONNECTORS
from notifiers import NOTIFIERS
from notifiers.telegram import get_users, remove_user
from notifiers.telegram_polling import run_bot_polling

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app):
    # Monitor loop
    monitor_thread = threading.Thread(target=run_monitor_loop, args=(state,), daemon=True)
    monitor_thread.start()

    # Telegram bot polling
    token = os.environ.get("TELEGRAM_TOKEN", "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")
    bot_thread = threading.Thread(target=run_bot_polling, args=(token,), daemon=True)
    bot_thread.start()

    yield


app = FastAPI(lifespan=lifespan, title="Lab Monitor")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _render(request, template, **ctx):
    return templates.TemplateResponse(template, {"request": request, **ctx})


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(request, "dashboard.html",
                   lab_counts=state.get_lab_counts(),
                   notifications=state.notifications)


@app.get("/exames", response_class=HTMLResponse)
async def exames(request: Request, lab: str = "", status: str = ""):
    labs_cfg = state.config["labs"]
    statuses = sorted({i["status"]
                       for snap in state.snapshots.values()
                       for rec in snap.values()
                       for i in rec["itens"].values()})
    return _render(request, "exames.html",
                   rows=state.get_exames(lab, status),
                   labs_cfg=labs_cfg,
                   statuses=statuses,
                   lab_filter=lab,
                   status_filter=status)


@app.get("/labs", response_class=HTMLResponse)
async def labs_page(request: Request):
    return _render(request, "labs.html",
                   labs=state.config["labs"],
                   last_check=state.last_check,
                   last_error=state.last_error)


@app.get("/canais", response_class=HTMLResponse)
async def canais_page(request: Request):
    return _render(request, "canais.html",
                   notifiers=state.config["notifiers"],
                   telegram_users=get_users())


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _render(request, "settings.html",
                   config=state.config)


# ── HTMX Partials ─────────────────────────────────────────────────────────────

@app.get("/partials/notifications", response_class=HTMLResponse)
async def partial_notifications(request: Request):
    return _render(request, "partials/notifications.html",
                   notifications=state.notifications)


@app.get("/partials/lab_counts", response_class=HTMLResponse)
async def partial_lab_counts(request: Request):
    return _render(request, "partials/lab_counts.html",
                   lab_counts=state.get_lab_counts())


@app.get("/partials/exames", response_class=HTMLResponse)
async def partial_exames(request: Request, lab: str = "", status: str = ""):
    return _render(request, "partials/exames_table.html",
                   rows=state.get_exames(lab, status))


@app.get("/partials/telegram-users", response_class=HTMLResponse)
async def partial_telegram_users(request: Request):
    return _render(request, "partials/telegram_users.html",
                   telegram_users=get_users())


# ── Actions ───────────────────────────────────────────────────────────────────

@app.post("/labs/{lab_id}/toggle", response_class=HTMLResponse)
async def toggle_lab(request: Request, lab_id: str):
    state.toggle_lab(lab_id)
    lab = next(l for l in state.config["labs"] if l["id"] == lab_id)
    return HTMLResponse(_toggle_html("lab", lab_id, lab.get("enabled", True), lab["name"]))


@app.post("/canais/{notifier_id}/toggle", response_class=HTMLResponse)
async def toggle_notifier(request: Request, notifier_id: str):
    state.toggle_notifier(notifier_id)
    n = next(x for x in state.config["notifiers"] if x["id"] == notifier_id)
    return HTMLResponse(_toggle_html("canais", notifier_id, n.get("enabled", True), n["id"].capitalize()))


@app.post("/labs/{lab_id}/test", response_class=HTMLResponse)
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


@app.post("/canais/{notifier_id}/test", response_class=HTMLResponse)
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


@app.post("/canais/telegram/users/{chat_id}/remove", response_class=HTMLResponse)
async def remove_telegram_user(request: Request, chat_id: str):
    remove_user(chat_id)
    return _render(request, "partials/telegram_users.html",
                   telegram_users=get_users())


@app.post("/settings/interval", response_class=HTMLResponse)
async def save_interval(minutes: int = Form(...)):
    state.set_interval(max(1, minutes))
    return HTMLResponse(f'<span class="text-green-600 text-sm">✓ Intervalo atualizado para {minutes} min</span>')


# ── Helper ────────────────────────────────────────────────────────────────────

def _toggle_html(route: str, id: str, enabled: bool, label: str) -> str:
    color = "bg-green-100 text-green-800" if enabled else "bg-gray-100 text-gray-500"
    text  = "Habilitado" if enabled else "Desabilitado"
    return f'''
    <div id="toggle-{id}" class="flex items-center gap-3">
      <span class="text-sm px-2 py-1 rounded-full {color}">{text}</span>
      <button hx-post="/{route}/{id}/toggle" hx-target="#toggle-{id}" hx-swap="outerHTML"
              class="text-sm px-3 py-1 rounded border border-gray-300 hover:bg-gray-50">
        {"Desabilitar" if enabled else "Habilitar"}
      </button>
    </div>'''
