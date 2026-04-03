"""
Logica central de monitoramento.
Pode rodar standalone (monitor.py) ou embutido na web (web/app.py).
"""

import hashlib
import time
from datetime import datetime

from pb_platform.storage import store
from labs import CONNECTORS
from notifiers import NOTIFIERS
from notification_settings import ensure_notification_settings, render_notification_template
from web.state import normalize_status

_EXTERNAL_EVENT_CACHE: dict[str, float] = {}
_EXTERNAL_EVENT_TTL_SECONDS = 60 * 60 * 72


def _parse_iso_like(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    return None


def _derive_liberado_fallback(record: dict, item: dict, ts: str) -> str:
    candidates = (
        item.get("released_at_hint"),
        record.get("released_at_hint"),
        item.get("dtEntrega"),
        item.get("dtColeta"),
        record.get("received_at"),
        record.get("data"),
        ts,
    )
    for raw in candidates:
        parsed = _parse_iso_like(raw)
        if parsed:
            return parsed.isoformat()
    return ts


def _cleanup_external_event_cache(now_ts: float) -> None:
    cutoff = now_ts - _EXTERNAL_EVENT_TTL_SECONDS
    expired = [sig for sig, ts in _EXTERNAL_EVENT_CACHE.items() if ts < cutoff]
    for sig in expired:
        _EXTERNAL_EVENT_CACHE.pop(sig, None)


def _should_send_external_event(signature: str) -> bool:
    now_ts = time.time()
    _cleanup_external_event_cache(now_ts)
    if signature in _EXTERNAL_EVENT_CACHE:
        return False
    if not store.remember_notification_event(signature, "external"):
        return False
    _EXTERNAL_EVENT_CACHE[signature] = now_ts
    return True


def _event_signature(lab_id: str, kind: str, record_id: str, item_ids: list[str]) -> str:
    base = "|".join([lab_id, kind, record_id, *sorted(item_ids)])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _format_item_lines(items: list[dict]) -> str:
    seen: set[str] = set()
    names: list[str] = []
    for item in items:
        name = item.get("nome", "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return "\n".join(f"• {name}" for name in names)


def _notification_context(lab_name: str, record_id: str, record: dict, items: list[dict]) -> dict:
    return {
        "lab_name": lab_name,
        "record_label": record["label"],
        "record_id": record_id,
        "record_date": record["data"],
        "item_lines": _format_item_lines(items),
        "items_total": len(items),
    }


def _build_external_message(
    event_kind: str,
    lab_name: str,
    record_id: str,
    record: dict,
    items: list[dict],
    notification_settings: dict,
) -> str | None:
    settings = ensure_notification_settings({"notification_settings": notification_settings})
    event_cfg = settings["events"].get(event_kind) or {}
    if not event_cfg.get("enabled", True):
        return None
    template = event_cfg.get("template") or ""
    return render_notification_template(
        template,
        _notification_context(lab_name, record_id, record, items),
    )


def _stamp_liberados(anterior: dict, atual: dict, ts: str) -> None:
    """
    Stamps 'liberado_em' ISO timestamp on items that just transitioned to Pronto.
    Preserves existing timestamps for items already Pronto in the previous snapshot.
    Mutates 'atual' in place.
    """
    for rid, rec in atual.items():
        ant_rec = anterior.get(rid, {})
        for iid, item in rec["itens"].items():
            s_new = normalize_status(item["status"])
            ant_item = ant_rec.get("itens", {}).get(iid, {})
            s_old = normalize_status(ant_item.get("status", ""))

            if s_new == "Pronto":
                if ant_item.get("liberado_em"):
                    item["liberado_em"] = ant_item["liberado_em"]
                elif s_old and s_old != "Pronto":
                    item["liberado_em"] = ts
                elif not item.get("liberado_em"):
                    item["liberado_em"] = _derive_liberado_fallback(rec, item, ts)


def _hydrate_snapshot_details(lab, anterior: dict, atual: dict, ts: str) -> None:
    """
    Enriches the current snapshot with derived metadata that the UI depends on.
    This must happen on every cycle, including the first one after a restart,
    otherwise alert/resultado data disappear until a later refresh.
    """
    _hydrate_snapshot_metadata(lab, anterior, atual, ts)
    _hydrate_snapshot_results(lab, anterior, atual)


def _hydrate_snapshot_metadata(lab, anterior: dict, atual: dict, ts: str) -> None:
    _stamp_liberados(anterior, atual, ts)
    if hasattr(lab, "enrich_snapshot_metadata"):
        lab.enrich_snapshot_metadata(anterior, atual)


def _hydrate_snapshot_results(lab, anterior: dict, atual: dict) -> None:
    if hasattr(lab, "enrich_resultados"):
        lab.enrich_resultados(anterior, atual)


def build_notification_plan(
    lab_id: str,
    lab_name: str,
    anterior: dict,
    atual: dict,
    notification_settings: dict | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Returns two streams:
    - internal_messages: fine-grained feed for the app state
    - external_events: Telegram/WhatsApp-safe notifications following the current policy

    External policy:
    - notify when a new record first appears in the lab
    - notify when items in a record transition to Pronto, grouped by record in the same cycle
    - optional status_update template can emit grouped non-terminal transitions when enabled
    """
    internal_messages: list[str] = []
    external_events: list[dict] = []
    effective_settings = ensure_notification_settings({"notification_settings": notification_settings or {}})

    for rid, rec in atual.items():
        itens = rec.get("itens", {})

        if rid not in anterior:
            nomes = ", ".join(item["nome"] for item in itens.values())
            internal_messages.append(
                f"🆕 <b>Nova entrada - {lab_name}</b>\n"
                f"👤 {rec['label']}\n"
                f"📋 {rid} | {rec['data']}\n"
                f"🔬 {nomes}"
            )

            statuses = {normalize_status(item.get('status', '')) for item in itens.values()}
            item_ids = list(itens.keys())
            if itens and statuses == {"Pronto"}:
                message = _build_external_message(
                    "completed",
                    lab_name,
                    rid,
                    rec,
                    list(itens.values()),
                    effective_settings,
                )
                if not message:
                    continue
                external_events.append({
                    "kind": "completed",
                    "signature": _event_signature(lab_id, "completed", rid, item_ids),
                    "message": message,
                })
            else:
                message = _build_external_message(
                    "received",
                    lab_name,
                    rid,
                    rec,
                    list(itens.values()),
                    effective_settings,
                )
                if not message:
                    continue
                external_events.append({
                    "kind": "received",
                    "signature": _event_signature(lab_id, "received", rid, item_ids),
                    "message": message,
                })
            continue

        completed_items: list[tuple[str, dict]] = []
        updated_items: list[tuple[str, dict]] = []

        for iid, item in itens.items():
            s_new = normalize_status(item["status"])
            s_old = normalize_status(anterior[rid]["itens"].get(iid, {}).get("status", ""))
            if s_old and s_new != s_old:
                internal_messages.append(
                    f"✅ <b>Resultado disponivel - {lab_name}</b>\n"
                    f"👤 {rec['label']}\n"
                    f"🔬 {item['nome']}\n"
                    f"📊 {s_old} → {s_new}"
                )
                if s_new == "Pronto" and s_old != "Pronto":
                    completed_items.append((iid, item))
                elif s_new not in {"Pronto", "Cancelado"}:
                    updated_items.append((iid, item))

        if completed_items:
            completed_payload = [item for _, item in completed_items]
            message = _build_external_message(
                "completed",
                lab_name,
                rid,
                rec,
                completed_payload,
                effective_settings,
            )
            if not message:
                continue
            external_events.append({
                "kind": "completed",
                "signature": _event_signature(
                    lab_id,
                    "completed",
                    rid,
                    [iid for iid, _ in completed_items],
                ),
                "message": message,
            })
        elif updated_items:
            message = _build_external_message(
                "status_update",
                lab_name,
                rid,
                rec,
                [item for _, item in updated_items],
                effective_settings,
            )
            if message:
                external_events.append({
                    "kind": "status_update",
                    "signature": _event_signature(
                        lab_id,
                        "status_update",
                        rid,
                        [iid for iid, _ in updated_items],
                    ),
                    "message": message,
                })

    return internal_messages, external_events


def run_monitor_loop(state=None):
    """
    Loop principal de monitoramento.
    Se `state` for fornecido (AppState), atualiza o estado da interface web.
    Se nao, roda standalone sem persistencia em memoria.
    """
    print(f"[{datetime.now():%H:%M:%S}] Monitor iniciado")

    while True:
        config = state.config if state else _load_config_file()
        interval = config.get("interval_minutes", 5) * 60
        notification_settings = ensure_notification_settings(config)

        labs = [
            CONNECTORS[l["connector"]]()
            for l in config["labs"]
            if l.get("enabled") and l["connector"] in CONNECTORS
        ]
        notifiers = [
            NOTIFIERS[n["type"]]()
            for n in config["notifiers"]
            if n.get("enabled") and n["type"] in NOTIFIERS
        ]

        for lab in labs:
            if state:
                state.is_checking[lab.lab_id] = True
                hints = state.sync_context(lab.lab_id)
                setattr(lab, "sync_hints", hints)
            try:
                print(f"[{datetime.now():%H:%M:%S}] Verificando {lab.lab_name}...")
                atual = lab.snapshot()
                anterior = state.snapshots.get(lab.lab_id, {}) if state else {}
                ts_now = datetime.now().isoformat()
                if state:
                    # Publish the fresh snapshot immediately so the panel stops
                    # rendering empty while metadata/results continue to hydrate.
                    state.snapshots[lab.lab_id] = atual

                if not anterior:
                    _hydrate_snapshot_metadata(lab, anterior, atual, ts_now)
                    _hydrate_snapshot_results(lab, anterior, atual)
                    print("  Primeira execucao - estado salvo.")
                else:
                    internal_messages, external_events = build_notification_plan(
                        lab.lab_id,
                        lab.lab_name,
                        anterior,
                        atual,
                        notification_settings,
                    )
                    _hydrate_snapshot_metadata(lab, anterior, atual, ts_now)
                    _hydrate_snapshot_results(lab, anterior, atual)

                    for msg in internal_messages:
                        print(f"  -> {msg[:80]}")
                        if state:
                            state.add_notification(lab.lab_name, msg)

                    for event in external_events:
                        if not _should_send_external_event(event["signature"]):
                            print(f"  -> evento externo duplicado suprimido ({event['kind']})")
                            continue
                        print(f"  -> envio externo {event['kind']}")
                        for notifier in notifiers:
                            notifier.enviar(event["message"])

                if state:
                    state.snapshots[lab.lab_id] = atual
                    state.last_check[lab.lab_id] = datetime.now().strftime("%H:%M:%S")
                    state.last_error.pop(lab.lab_id, None)
                    state.save_lab_runtime(lab.lab_id)

                print(f"  {lab.lab_name}: {len(atual)} registros")

            except Exception as e:
                print(f"  {lab.lab_name}: erro - {e}")
                if state:
                    state.last_error[lab.lab_id] = str(e)
                    state.save_lab_runtime(lab.lab_id)
            finally:
                if state:
                    state.is_checking[lab.lab_id] = False

        time.sleep(interval)


def _load_config_file() -> dict:
    from pathlib import Path
    import json
    return json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
