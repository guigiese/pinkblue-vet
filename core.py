"""
Logica central de monitoramento.
Pode rodar standalone (monitor.py) ou embutido na web (web/app.py).
"""

import hashlib
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta

from pb_platform.storage import store
from labs import CONNECTORS
from notifiers import NOTIFIERS
from notification_settings import ensure_notification_settings, render_notification_template
from web.state import normalize_status

_EXTERNAL_EVENT_CACHE: dict[str, float] = {}
_EXTERNAL_EVENT_TTL_SECONDS = 60 * 60 * 72
_SYNC_LOCK = threading.RLock()


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


def _merge_snapshots(previous: dict, fresh: dict) -> dict:
    merged = deepcopy(previous or {})
    for record_id, record in (fresh or {}).items():
        current = merged.setdefault(record_id, {})
        for key, value in record.items():
            if key == "itens":
                current_items = current.setdefault("itens", {})
                for item_id, item_payload in value.items():
                    current_items[item_id] = {
                        **current_items.get(item_id, {}),
                        **item_payload,
                    }
            elif value not in ("", None, [], {}):
                current[key] = value
    return merged


def _history_anchor_date(snapshot: dict) -> datetime | None:
    candidates: list[datetime] = []
    for record in snapshot.values():
        raw = record.get("received_at") or record.get("collected_at") or record.get("data")
        parsed = _parse_iso_like(raw)
        if parsed:
            candidates.append(parsed)
    return min(candidates) if candidates else None


def _history_window_for_lab(lab_id: str, snapshot: dict) -> tuple[datetime, datetime] | None:
    sync_state = store.get_lab_sync_state(lab_id)
    if sync_state.get("history_complete"):
        return None

    next_end_raw = sync_state.get("next_backfill_end")
    if next_end_raw:
        next_end = _parse_iso_like(next_end_raw)
    else:
        anchor = _history_anchor_date(snapshot)
        next_end = (anchor - timedelta(days=1)) if anchor else None

    if not next_end:
        return None
    if next_end.year < 2010:
        sync_state["history_complete"] = True
        store.save_lab_sync_state(lab_id, sync_state)
        return None

    window_start = next_end - timedelta(days=59)
    return window_start, next_end


def _update_history_sync_state(lab_id: str, window_start: datetime, window_end: datetime, batch: dict) -> None:
    sync_state = store.get_lab_sync_state(lab_id)
    empty_windows = int(sync_state.get("empty_windows") or 0)
    if batch:
        oldest = _history_anchor_date(batch)
        next_end = (oldest - timedelta(days=1)) if oldest else (window_start - timedelta(days=1))
        sync_state.update({
            "history_complete": False,
            "empty_windows": 0,
            "last_window_start": window_start.date().isoformat(),
            "last_window_end": window_end.date().isoformat(),
            "last_window_records": len(batch),
            "next_backfill_end": next_end.date().isoformat(),
        })
    else:
        empty_windows += 1
        next_end = window_start - timedelta(days=1)
        sync_state.update({
            "history_complete": empty_windows >= 2,
            "empty_windows": empty_windows,
            "last_window_start": window_start.date().isoformat(),
            "last_window_end": window_end.date().isoformat(),
            "last_window_records": 0,
            "next_backfill_end": next_end.date().isoformat(),
        })
    store.save_lab_sync_state(lab_id, sync_state)


def run_historical_backfill(state, max_windows_per_lab: int = 1) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    labs = [
        CONNECTORS[l["connector"]]()
        for l in state.config["labs"]
        if l.get("enabled") and l["connector"] in CONNECTORS
    ]

    with _SYNC_LOCK:
        for lab in labs:
            current = state.snapshots.get(lab.lab_id, {})
            if not current:
                try:
                    current = lab.snapshot()
                    if current:
                        _hydrate_snapshot_metadata(lab, {}, current, datetime.now().isoformat())
                        state.snapshots[lab.lab_id] = current
                        state.save_lab_runtime(lab.lab_id)
                except Exception as e:
                    print(f"[backfill:{lab.lab_id}] falha ao primar snapshot atual - {e}")
            processed = 0
            added_records = 0
            while processed < max_windows_per_lab:
                window = _history_window_for_lab(lab.lab_id, current)
                if not window or not hasattr(lab, "snapshot_between"):
                    if not window:
                        sync_state = store.get_lab_sync_state(lab.lab_id)
                        if current and "history_complete" not in sync_state:
                            sync_state["history_complete"] = True
                            store.save_lab_sync_state(lab.lab_id, sync_state)
                    break
                start_dt, end_dt = window
                previous = deepcopy(current)
                batch = lab.snapshot_between(start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
                before_count = len(current)
                current = _merge_snapshots(current, batch)
                if batch:
                    # Historical backfill should preserve list-level metadata without
                    # triggering a mass download of every old result payload at once.
                    # Numeric/textual details remain available on-demand.
                    _hydrate_snapshot_metadata(lab, previous, current, datetime.now().isoformat())
                added_records += max(0, len(current) - before_count)
                _update_history_sync_state(lab.lab_id, start_dt, end_dt, batch)
                processed += 1
                time.sleep(0.2)

            if processed:
                state.snapshots[lab.lab_id] = current
                state.save_lab_runtime(lab.lab_id)
            summary[lab.lab_id] = {
                "windows": processed,
                "records": len(current),
                "added_records": added_records,
                "sync_state": store.get_lab_sync_state(lab.lab_id),
            }
    return summary


def run_historical_backfill_until_complete(
    state,
    *,
    max_windows_per_lab: int = 2,
    pause_seconds: float = 2.0,
) -> None:
    while True:
        summary = run_historical_backfill(state, max_windows_per_lab=max_windows_per_lab)
        if not summary:
            return

        incomplete = [
            lab_id
            for lab_id, payload in summary.items()
            if not (payload.get("sync_state") or {}).get("history_complete")
        ]
        if not incomplete:
            return
        time.sleep(pause_seconds)


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


def _item_has_usable_result(item: dict) -> bool:
    if item.get("resultado"):
        return True
    if (item.get("report_text") or "").strip():
        return True
    if (item.get("diagnosis_text") or "").strip():
        return True
    return False


def _apply_operational_status_rules(atual: dict) -> None:
    """
    Applies platform-wide operational rules after connector enrichment.
    Connectors provide lab-facing state; the Lab Monitor derives the
    user-facing operational state from that payload.
    """
    for record in atual.values():
        for item in record.get("itens", {}).values():
            raw_status = item.get("lab_status") or item.get("status") or ""
            normalized = normalize_status(raw_status)
            item["lab_status"] = raw_status
            if normalized == "Pronto" and not _item_has_usable_result(item):
                item["status"] = "Inconsistente"
                item["result_issue"] = "ready-without-result"
            else:
                item["status"] = normalized
                item.pop("result_issue", None)


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
            with _SYNC_LOCK:
                if state:
                    state.is_checking[lab.lab_id] = True
                    hints = state.sync_context(lab.lab_id)
                    setattr(lab, "sync_hints", hints)
                try:
                    print(f"[{datetime.now():%H:%M:%S}] Verificando {lab.lab_name}...")
                    fresh = lab.snapshot()
                    anterior = state.snapshots.get(lab.lab_id, {}) if state else {}
                    atual = _merge_snapshots(anterior, fresh) if state else fresh
                    ts_now = datetime.now().isoformat()
                    if state:
                        state.snapshots[lab.lab_id] = atual

                    if not anterior:
                        _hydrate_snapshot_metadata(lab, anterior, atual, ts_now)
                        _hydrate_snapshot_results(lab, anterior, atual)
                        _apply_operational_status_rules(atual)
                        print("  Primeira execucao - estado salvo.")
                    else:
                        _hydrate_snapshot_metadata(lab, anterior, atual, ts_now)
                        _hydrate_snapshot_results(lab, anterior, atual)
                        _apply_operational_status_rules(atual)
                        internal_messages, external_events = build_notification_plan(
                            lab.lab_id,
                            lab.lab_name,
                            anterior,
                            atual,
                            notification_settings,
                        )

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
