import asyncio
import threading

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from core import run_historical_backfill_until_complete
from modules.lab_monitor.labs import CONNECTORS
from modules.lab_monitor.labs.bitlab import BitlabConnector
from modules.lab_monitor.notifiers import NOTIFIERS
from modules.lab_monitor.notifiers.telegram import get_users, remove_user
from modules.lab_monitor.settings import NOTIFICATION_TEMPLATE_VARIABLES
from pb_platform.storage import store
from web.card_sandbox import get_card_sandbox_variant
from web.shared import EXAMES_PAGE_SIZE, STANDARD_STATUSES, _render
from web.state import state
from web.text_reports import build_report_sections

router = APIRouter(prefix="/labmonitor")


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
        return HTMLResponse('<span class="text-red-600 text-sm">Lab não encontrado</span>')
    try:
        connector = CONNECTORS[lab_cfg["connector"]]()
        connector.sync_hints = state.sync_context(lab_id)
        if hasattr(connector, "test_connection"):
            message = await asyncio.to_thread(connector.test_connection)
        else:
            snap = await asyncio.to_thread(connector.snapshot)
            message = f"Conexão OK - {len(snap)} registros"
        return HTMLResponse(f'<span class="text-green-600 text-sm">{message}</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">✗ Erro: {e}</span>')


@router.post("/canais/{notifier_id}/test", response_class=HTMLResponse)
async def test_notifier(notifier_id: str):
    n_cfg = next((n for n in state.config["notifiers"] if n["id"] == notifier_id), None)
    if not n_cfg or n_cfg["type"] not in NOTIFIERS:
        return HTMLResponse('<span class="text-red-600 text-sm">Canal não encontrado</span>')
    try:
        notifier = NOTIFIERS[n_cfg["type"]]()
        message = "Teste - Lab Monitor\nCanal funcionando!"
        if hasattr(notifier, "send_test"):
            await asyncio.to_thread(notifier.send_test, message)
        else:
            await asyncio.to_thread(notifier.enviar, message)
        return HTMLResponse('<span class="text-green-600 text-sm">✓ Mensagem enviada</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-600 text-sm">✗ Erro: {e}</span>')


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
    return HTMLResponse(f'<span class="text-green-600 text-sm">✓ Intervalo atualizado para {minutes} min</span>')


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
    return HTMLResponse('<span class="text-green-600 text-sm">Backfill histórico iniciado em segundo plano.</span>')


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
        return HTMLResponse('<p class="text-gray-500 text-sm p-4">Esse exame possui resultado numérico inline.</p>')
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


@router.get("/partials/ultimos_liberados", response_class=HTMLResponse)
async def partial_ultimos_liberados(request: Request):
    return _render(request, "partials/ultimos_liberados.html", groups=state.get_ultimos_liberados())


def _find_cached_resultado(item_id: str) -> tuple[list[dict] | None, str, str]:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record.get("itens", {}).values():
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
            for item in record.get("itens", {}).values():
                if item.get("item_id") == item_id:
                    return lab_id, record
    return None, None


def _find_result_item(item_id: str) -> dict | None:
    for snap in state.snapshots.values():
        for record in snap.values():
            for item in record.get("itens", {}).values():
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
    _cache_resultado(item_id, rows or [], report_text=report_text, diagnosis_text=diagnosis_text)
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
            for item in record.get("itens", {}).values():
                if item.get("item_id") == item_id:
                    item["resultado"] = rows
                    item["alerta"] = worst
                    if report_text:
                        item["report_text"] = report_text
                    if diagnosis_text:
                        item["diagnosis_text"] = diagnosis_text
                    state.save_lab_runtime(lab_id)
                    return
