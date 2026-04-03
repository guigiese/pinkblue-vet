import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
from web.card_sandbox import (
    CARD_SANDBOX_DIR,
    CARD_SANDBOX_VARIANTS,
    DEFAULT_CARD_SANDBOX_VARIANT,
    get_card_sandbox_groups,
    get_card_sandbox_runtime,
    get_card_sandbox_variant,
)
from web.ops_map import OPS_MAP_DIR, get_ops_map_runtime

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

APP_URL = os.environ.get("APP_URL", "https://pinkblue-vet-production.up.railway.app")
STANDARD_STATUSES = ["Pronto", "Parcial", "Em Andamento", "Analisando", "Recebido", "Cancelado"]


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
app.mount("/ops-map-static", StaticFiles(directory=str(OPS_MAP_DIR)), name="ops_map_static")
app.mount("/sandboxes/cards-static", StaticFiles(directory=str(CARD_SANDBOX_DIR)), name="cards_sandbox_static")


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


# ── Lab Monitor Pages ─────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(request, "dashboard.html",
                   lab_counts=state.get_lab_counts(),
                   groups=state.get_ultimos_liberados())


@router.get("/", response_class=HTMLResponse)
async def dashboard_slash(request: Request):
    return _render(request, "dashboard.html",
                   lab_counts=state.get_lab_counts(),
                   groups=state.get_ultimos_liberados())


@router.get("/exames", response_class=HTMLResponse)
async def exames(request: Request, lab: str = "", status: str = "", q: str = ""):
    variant_cfg = get_card_sandbox_variant("v0-reference-current")
    return _render(request, "exames.html",
                   groups=state.get_exames(lab, status, q),
                   variant_cfg=variant_cfg,
                   result_fetch_prefix="/labmonitor/partials/resultado",
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


@router.get("/notificacoes", response_class=HTMLResponse)
async def notificacoes_page(request: Request, saved: str = "", reset: str = ""):
    return _render(
        request,
        "notificacoes.html",
        notification_settings=state.get_notification_settings(),
        preview_messages=state.get_notification_previews(),
        notification_variables=(
            "lab_name",
            "record_label",
            "record_id",
            "record_date",
            "item_lines",
            "items_total",
        ),
        save_state="saved" if saved else "reset" if reset else "",
    )


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
    variant_cfg = get_card_sandbox_variant("v0-reference-current")
    return _render(request, "partials/exames_table.html",
                   groups=state.get_exames(lab, status, q),
                   variant_cfg=variant_cfg,
                   result_fetch_prefix="/labmonitor/partials/resultado")


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


@router.post("/notificacoes/salvar")
async def save_notificacoes(
    received_enabled: str | None = Form(None),
    completed_enabled: str | None = Form(None),
    received_template: str = Form(...),
    completed_template: str = Form(...),
):
    state.update_notification_settings(
        received_enabled=received_enabled == "on",
        completed_enabled=completed_enabled == "on",
        received_template=received_template,
        completed_template=completed_template,
    )
    return RedirectResponse("/labmonitor/notificacoes?saved=1", status_code=303)


@router.post("/notificacoes/resetar")
async def reset_notificacoes():
    state.reset_notification_settings()
    return RedirectResponse("/labmonitor/notificacoes?reset=1", status_code=303)


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


@router.get("/partials/resultado/{item_id:path}", response_class=HTMLResponse)
async def partial_resultado(request: Request, item_id: str):
    """Fetches and renders a BitLab exam result for inline display."""
    from labs.bitlab import BitlabConnector
    connector = BitlabConnector()

    # Check if result is already cached in the snapshot
    rows = _find_cached_resultado(item_id)
    record = _find_result_record(item_id)

    if rows is None:
        # Not cached — fetch fresh from BitLab
        try:
            token = connector._login()
            raw   = connector.buscar_resultado_html(token, item_id)
            rows  = connector.parse_resultado(raw, record)
            _cache_resultado(item_id, rows)
        except Exception as e:
            return HTMLResponse(
                f'<p class="text-red-500 text-xs p-3">Erro ao carregar resultado: {e}</p>'
            )

    return _render(request, "partials/resultado_bitlab.html", rows=rows)


def _find_cached_resultado(item_id: str) -> list[dict] | None:
    """Look up cached resultado rows from the current snapshot, if available."""
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id and "resultado" in item:
                    return item["resultado"]
    return None


def _find_result_record(item_id: str) -> dict | None:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    return record
    return None


def _cache_resultado(item_id: str, rows: list[dict]) -> None:
    """Persists freshly fetched result rows back into the in-memory snapshot."""
    alert_rank = {None: 0, "yellow": 1, "red": 2}
    worst = max((row.get("alerta") for row in rows), key=lambda level: alert_rank.get(level, 0), default=None)

    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record["itens"].values():
                if item.get("item_id") == item_id:
                    item["resultado"] = rows
                    item["alerta"] = worst
                    return


@router.get("/partials/ultimos_liberados", response_class=HTMLResponse)
async def partial_ultimos_liberados(request: Request):
    return _render(request, "partials/ultimos_liberados.html",
                   groups=state.get_ultimos_liberados())


app.include_router(router)
