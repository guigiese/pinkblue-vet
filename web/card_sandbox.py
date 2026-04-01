from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from web.state import normalize_status, state

CARD_SANDBOX_DIR = Path(__file__).parent.parent / "poc" / "lab-card-variants"

_FALLBACK_PROTOCOLS = [
    {
        "sampleReason": "critical-ready",
        "labId": "bitlab",
        "labName": "BioAnálises (BitLab)",
        "protocol": "08-00000001",
        "patientName": "Lua",
        "tutorName": "Patrícia S.",
        "speciesSex": None,
        "status": "Pronto",
        "criticality": "red",
        "date": "31/03/2026",
        "dateRaw": "2026-03-31",
        "releaseAt": "31/03/2026 10:42",
        "daysOpen": None,
        "portalUrl": "https://bitlabenterprise.com.br/bioanalises/resultados",
        "statusCounts": {"Pronto": 6},
        "items": [
            {
                "name": "Creatinina veterinária",
                "status": "Pronto",
                "alert": "yellow",
                "itemId": "fake-1",
                "releaseAt": "2026-03-31T10:42:00",
                "results": [
                    {
                        "nome": "Creatinina veterinária",
                        "valor": "1,1 mg/dL",
                        "referencia": "Canino: 0,0 a 1,4 mg/dL",
                        "alerta": "yellow",
                    }
                ],
            },
            {"name": "Fosfatase alcalina", "status": "Pronto", "alert": None, "itemId": "fake-2", "releaseAt": "2026-03-31T10:42:00", "results": []},
            {"name": "Gama-GT", "status": "Pronto", "alert": None, "itemId": "fake-3", "releaseAt": "2026-03-31T10:42:00", "results": []},
            {"name": "Hemograma", "status": "Pronto", "alert": "red", "itemId": "fake-4", "releaseAt": "2026-03-31T10:42:00", "results": []},
            {"name": "TGP", "status": "Pronto", "alert": None, "itemId": "fake-5", "releaseAt": "2026-03-31T10:42:00", "results": []},
            {"name": "Ureia", "status": "Pronto", "alert": None, "itemId": "fake-6", "releaseAt": "2026-03-31T10:42:00", "results": []},
        ],
    },
    {
        "sampleReason": "partial-warning",
        "labId": "bitlab",
        "labName": "BioAnálises (BitLab)",
        "protocol": "08-00000002",
        "patientName": "Aurora",
        "tutorName": "Marilene C.",
        "speciesSex": None,
        "status": "Parcial",
        "criticality": "yellow",
        "date": "31/03/2026",
        "dateRaw": "2026-03-31",
        "releaseAt": None,
        "daysOpen": 1,
        "portalUrl": "https://bitlabenterprise.com.br/bioanalises/resultados",
        "statusCounts": {"Pronto": 7, "Em Andamento": 3},
        "items": [
            {"name": "Alergia a picada de pulga", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAt": None, "results": []},
            {"name": "Citologia", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAt": None, "results": []},
            {"name": "Creatinina", "status": "Pronto", "alert": None, "itemId": "fake-7", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "Fosfatase alcalina", "status": "Pronto", "alert": None, "itemId": "fake-8", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "Glicose", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAt": None, "results": []},
            {"name": "Hemograma", "status": "Pronto", "alert": "yellow", "itemId": "fake-9", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "Proteína total", "status": "Pronto", "alert": None, "itemId": "fake-10", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "TGP", "status": "Pronto", "alert": None, "itemId": "fake-11", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "Triglicerídeos", "status": "Pronto", "alert": None, "itemId": "fake-12", "releaseAt": "2026-03-31T09:12:00", "results": []},
            {"name": "Ureia", "status": "Pronto", "alert": None, "itemId": "fake-13", "releaseAt": "2026-03-31T09:12:00", "results": []},
        ],
    },
    {
        "sampleReason": "nexio-single",
        "labId": "nexio",
        "labName": "Nexio Patologia",
        "protocol": "AP000044/26",
        "patientName": "Thor",
        "tutorName": "Márcia",
        "speciesSex": None,
        "status": "Pronto",
        "criticality": None,
        "date": "04/03/2026",
        "dateRaw": "2026-03-04",
        "releaseAt": None,
        "daysOpen": None,
        "portalUrl": "https://www.pathoweb.com.br",
        "statusCounts": {"Pronto": 1},
        "items": [
            {"name": "Patologia AP000044/26", "status": "Pronto", "alert": None, "itemId": None, "releaseAt": None, "results": []},
        ],
    },
]

_ALERT_RANK = {None: 0, "yellow": 1, "red": 2}


def _parse_label(label: str) -> tuple[str, str]:
    raw = " ".join((label or "").split())
    if not raw:
        return "Paciente não identificado", ""

    tutor = ""
    main = raw

    if " PROP:" in raw:
        main, tutor = raw.split(" PROP:", 1)
        tutor = tutor.strip(" -")

    if " - " in main:
        patient, fallback_tutor = main.split(" - ", 1)
        if not tutor:
            tutor = fallback_tutor.strip()
        return patient.strip(), tutor.strip()

    return main.strip(), tutor.strip()


def _format_release(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return raw


def _status_counts(items: list[dict]) -> dict[str, int]:
    order = ["Pronto", "Em Andamento", "Analisando", "Recebido", "Cancelado"]
    counter = Counter(item["status"] for item in items)
    return {status: counter[status] for status in order if counter[status]}


def _snapshot_lookup(lab_id: str, record_id: str) -> dict | None:
    return state.snapshots.get(lab_id, {}).get(record_id)


def _record_alert(record: dict | None) -> str | None:
    if not record:
        return None

    worst = None
    for item in record.get("itens", {}).values():
        item_alert = item.get("alerta")
        if _ALERT_RANK.get(item_alert, 0) > _ALERT_RANK.get(worst, 0):
            worst = item_alert
        for row in item.get("resultado") or []:
            row_alert = row.get("alerta")
            if _ALERT_RANK.get(row_alert, 0) > _ALERT_RANK.get(worst, 0):
                worst = row_alert
    return worst


def _build_protocol(group: dict, reason: str) -> dict:
    snapshot_record = _snapshot_lookup(group["lab_id"], group["record_id"]) or {}
    patient_name, tutor_name = _parse_label(snapshot_record.get("label") or group["paciente"])
    items_source = snapshot_record.get("itens", {})

    items = []
    for key, item in sorted(items_source.items(), key=lambda pair: pair[1].get("nome", "")):
        items.append(
            {
                "id": key,
                "name": item.get("nome", ""),
                "status": normalize_status(item.get("status", "")),
                "alert": item.get("alerta"),
                "itemId": item.get("item_id"),
                "releaseAt": item.get("liberado_em"),
                "releaseAtDisplay": _format_release(item.get("liberado_em")),
                "results": item.get("resultado") or [],
            }
        )

    if not items:
        items = [
            {
                "id": str(index),
                "name": item.get("nome", ""),
                "status": normalize_status(item.get("status", "")),
                "alert": item.get("alerta"),
                "itemId": item.get("item_id"),
                "releaseAt": item.get("liberado_em"),
                "releaseAtDisplay": _format_release(item.get("liberado_em")),
                "results": item.get("resultado") or [],
            }
            for index, item in enumerate(group["itens"], start=1)
        ]

    return {
        "sourceKind": "live",
        "sampleReason": reason,
        "labId": group["lab_id"],
        "labName": group["lab"],
        "protocol": group["record_id"],
        "patientName": patient_name,
        "tutorName": tutor_name,
        "speciesSex": None,
        "status": group["status_geral"],
        "criticality": group["alerta_geral"] or _record_alert(snapshot_record),
        "date": group["data"],
        "dateRaw": group["data_raw"],
        "releaseAt": _format_release(group.get("liberado_em_iso")),
        "daysOpen": group["dias_em_aberto"],
        "portalUrl": group["portal_url"],
        "statusCounts": _status_counts(items),
        "items": items,
    }


def _pick_sample_groups(groups: list[dict]) -> tuple[list[dict], list[dict]]:
    if not groups:
        return [], []

    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def take(predicate, reason: str):
        for group in groups:
            key = (group["lab_id"], group["record_id"])
            if key in seen:
                continue
            if predicate(group):
                selected.append(_build_protocol(group, reason))
                seen.add(key)
                return

    take(lambda g: g["status_geral"] == "Parcial", "partial-warning")
    take(lambda g: (_record_alert(_snapshot_lookup(g["lab_id"], g["record_id"])) or g["alerta_geral"]) == "red", "critical-ready")
    take(lambda g: g["lab_id"] == "nexio", "nexio-single")
    take(lambda g: len(g["itens"]) >= 8, "large-protocol")
    take(lambda g: (_record_alert(_snapshot_lookup(g["lab_id"], g["record_id"])) or g["alerta_geral"]) == "yellow", "warning-ready")
    take(lambda g: True, "fallback")

    remaining = [
        _build_protocol(group, "live-extra")
        for group in groups
        if (group["lab_id"], group["record_id"]) not in seen
    ]

    return selected[:3], remaining


def _missing_dimensions(protocols: list[dict]) -> set[str]:
    missing: set[str] = set()
    if len({protocol["status"] for protocol in protocols}) < 2:
        missing.add("status")
    if len({protocol["labId"] for protocol in protocols}) < 2:
        missing.add("lab")
    if not any(protocol["criticality"] for protocol in protocols):
        missing.add("criticality")
    if not any(len(protocol["items"]) > 1 for protocol in protocols):
        missing.add("multi-item")
    return missing


def _candidate_score(candidate: dict, protocols: list[dict], missing: set[str]) -> int:
    score = 0
    statuses = {protocol["status"] for protocol in protocols}
    labs = {protocol["labId"] for protocol in protocols}

    if "status" in missing and candidate["status"] not in statuses:
        score += 2
    if "lab" in missing and candidate["labId"] not in labs:
        score += 2
    if "criticality" in missing and candidate["criticality"]:
        score += 3
    if "multi-item" in missing and len(candidate["items"]) > 1:
        score += 2

    score += max(0, len(candidate["items"]) - 1)
    return score


def _with_fallback_source(protocol: dict) -> dict:
    return {**protocol, "sourceKind": "fallback"}


def get_card_sandbox_runtime() -> dict:
    groups = state.get_exames()
    live_protocols, live_remaining = _pick_sample_groups(groups)

    if live_protocols:
        protocols = list(live_protocols)
        live_pool = list(live_remaining)
        fallback_pool = [_with_fallback_source(protocol) for protocol in _FALLBACK_PROTOCOLS]

        while len(protocols) < 3 and live_pool:
            protocols.append(live_pool.pop(0))

        while len(protocols) < 3 and fallback_pool:
            protocols.append(fallback_pool.pop(0))

        missing = _missing_dimensions(protocols)
        if missing:
            candidate_pool = live_pool + fallback_pool
            used = {(protocol["sourceKind"], protocol["protocol"], protocol["patientName"]) for protocol in protocols}
            while candidate_pool and missing:
                candidate = max(candidate_pool, key=lambda item: _candidate_score(item, protocols, missing))
                candidate_pool.remove(candidate)
                key = (candidate["sourceKind"], candidate["protocol"], candidate["patientName"])
                if key in used:
                    continue
                if _candidate_score(candidate, protocols, missing) <= 0:
                    break
                if len(protocols) < 3:
                    protocols.append(candidate)
                else:
                    protocols[-1] = candidate
                used.add(key)
                missing = _missing_dimensions(protocols)

        return {
            "generatedAt": datetime.now().isoformat(),
            "source": "live-state",
            "speciesSexMapped": False,
            "notes": [
                "Amostras reais selecionadas do estado atual do Lab Monitor.",
                "Espécie/sexo ainda não aparecem no payload atual do módulo.",
                "O card inteiro abre os detalhes; não há CTA textual fixo.",
                "Se o estado vivo não trouxer variedade suficiente, o sandbox complementa com amostras de contraste claramente marcadas.",
            ],
            "protocols": protocols[:3],
        }

    return {
        "generatedAt": datetime.now().isoformat(),
        "source": "fallback-synthetic",
        "speciesSexMapped": False,
        "notes": [
            "Fallback sem dados sensíveis versionados no repositório.",
            "Ao publicar no Railway, o sandbox passa a usar protocolos reais do estado vivo.",
            "Espécie/sexo seguem fora do payload atual.",
        ],
        "protocols": [_with_fallback_source(protocol) for protocol in _FALLBACK_PROTOCOLS],
    }
