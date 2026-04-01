from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from web.state import normalize_status, state

CARD_SANDBOX_DIR = Path(__file__).parent.parent / "poc" / "lab-card-variants"
DEFAULT_CARD_SANDBOX_VARIANT = "rail-clean"

CARD_SANDBOX_VARIANTS = [
    {
        "id": "rail-clean",
        "name": "V1 · Rail clean",
        "note": "Linha-base compacta com barra lateral, clusters enxutos e foco em leitura horizontal.",
        "frame": "rail",
        "density": "compact",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "none",
        "meta_density": "compact",
    },
    {
        "id": "rail-clean-ratio",
        "name": "V2 · Rail + ratio",
        "note": "Derivada direta da V1 com a leitura 'x/y prontos' logo abaixo do status.",
        "frame": "rail",
        "density": "compact",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "ready-ratio",
        "meta_density": "compact",
    },
    {
        "id": "rail-clean-tight",
        "name": "V3 · Rail tighter",
        "note": "Versao mais comprimida da V1, com paddings e tipografia ligeiramente menores.",
        "frame": "rail",
        "density": "tight",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "none",
        "meta_density": "tight",
    },
    {
        "id": "rail-clean-tight-ratio",
        "name": "V4 · Tight + ratio",
        "note": "Combina a compactacao da V3 com o texto pequeno 'x/y prontos' sob o status.",
        "frame": "rail",
        "density": "tight",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "ready-ratio",
        "meta_density": "tight",
    },
    {
        "id": "rail-soft-date",
        "name": "V5 · Rail soft date",
        "note": "Mantem a base da V1, mas suaviza a ancora da data e os clusters da ultima linha.",
        "frame": "rail",
        "density": "compact",
        "date_style": "soft",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "badges",
        "timeline_style": "inline",
        "status_detail": "none",
        "meta_density": "compact",
    },
    {
        "id": "rail-inline-triangle",
        "name": "V6 · Rail + triangle",
        "note": "Testa a barra lateral junto com um triangulo pequeno ao lado do status.",
        "frame": "hybrid",
        "density": "compact",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "inline",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "none",
        "meta_density": "compact",
    },
    {
        "id": "rail-minimal-border",
        "name": "V7 · Rail border",
        "note": "Mantem a leitura da V1, mas testa a criticidade na borda inteira para comparar limpeza.",
        "frame": "border",
        "density": "compact",
        "date_style": "plain",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "inline",
        "timeline_style": "inline",
        "status_detail": "none",
        "meta_density": "compact",
    },
    {
        "id": "rail-chip-date-ratio",
        "name": "V8 · Date chip + ratio",
        "note": "Explora a data em chip e a contagem de prontos sob o status, sem sair da linguagem da V1.",
        "frame": "rail",
        "density": "compact",
        "date_style": "chip",
        "status_style": "solid",
        "critical_style": "hidden",
        "meta_style": "badges",
        "timeline_style": "inline",
        "status_detail": "ready-ratio",
        "meta_density": "compact",
    },
]

_VARIANTS_BY_ID = {variant["id"]: variant for variant in CARD_SANDBOX_VARIANTS}

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
_SPECIES_PREVIEW = ["cadela", "gato", "cão", "gata"]
_SANDBOX_PREVIEW_OVERLAYS = [
    {"days_open": 2, "species_sex": "cadela"},
    {"days_open": 9, "species_sex": "gato"},
    {"days_open": 5, "species_sex": "cão"},
    {"days_open": 11, "species_sex": "gata"},
]


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


def _format_date_only(raw: str | None, fallback: str | None = None) -> str:
    if not raw:
        return fallback or ""
    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except Exception:
        return fallback or raw


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


def get_card_sandbox_variant(variant_id: str | None) -> dict:
    if not variant_id:
        return _VARIANTS_BY_ID[DEFAULT_CARD_SANDBOX_VARIANT]
    return _VARIANTS_BY_ID.get(variant_id, _VARIANTS_BY_ID[DEFAULT_CARD_SANDBOX_VARIANT])


def _build_group_items(group: dict, snapshot_record: dict | None) -> list[dict]:
    items_source = (snapshot_record or {}).get("itens", {})
    items: list[dict] = []

    if items_source:
        for key, item in sorted(items_source.items(), key=lambda pair: pair[1].get("nome", "")):
            items.append(
                {
                    "id": key,
                    "name": item.get("nome", ""),
                    "status": normalize_status(item.get("status", "")),
                    "alert": item.get("alerta"),
                    "item_id": item.get("item_id"),
                    "release_at": item.get("liberado_em"),
                    "release_at_display": _format_release(item.get("liberado_em")),
                    "results": item.get("resultado") or [],
                }
            )
        return items

    for index, item in enumerate(group["itens"], start=1):
        items.append(
            {
                "id": str(index),
                "name": item.get("nome", ""),
                "status": normalize_status(item.get("status", "")),
                "alert": item.get("alerta"),
                "item_id": item.get("item_id"),
                "release_at": item.get("liberado_em"),
                "release_at_display": _format_release(item.get("liberado_em")),
                "results": item.get("resultado") or [],
            }
        )

    return items


def _humanize_status_counts(counts: dict[str, int]) -> list[dict]:
    parts = [{"label": f"{sum(counts.values())} exame{'s' if sum(counts.values()) != 1 else ''}", "tone": "neutral"}]
    labels = {
        "Pronto": "pronto",
        "Em Andamento": "and.",
        "Analisando": "anal.",
        "Recebido": "receb.",
        "Cancelado": "cancel.",
    }
    tones = {
        "Pronto": "ready",
        "Em Andamento": "progress",
        "Analisando": "analysis",
        "Recebido": "received",
        "Cancelado": "neutral",
    }
    for status, count in counts.items():
        if not count:
            continue
        parts.append({"label": f"{count} {labels.get(status, status.lower())}", "tone": tones.get(status, "neutral")})
    return parts


def _ready_ratio_text(counts: dict[str, int], total: int) -> str:
    return f"{counts.get('Pronto', 0)}/{total} prontos"


def _timeline_parts(days_open: int | None, release_at_iso: str | None) -> list[dict]:
    if days_open is not None:
        return [{"label": f"{days_open}d em aberto", "stale": days_open > 7}]
    if release_at_iso:
        return [{"label": f"Lib. {_format_release(release_at_iso)}", "stale": False}]
    return []


def _inject_sandbox_preview(group_view: dict, index: int) -> dict:
    overlay = _SANDBOX_PREVIEW_OVERLAYS[index % len(_SANDBOX_PREVIEW_OVERLAYS)]
    group_view["species_sex"] = overlay["species_sex"]

    if group_view.get("days_em_aberto") is None:
        group_view["days_em_aberto_preview"] = overlay["days_open"]
        group_view["timeline_parts"] = _timeline_parts(overlay["days_open"], None)
    else:
        group_view["days_em_aberto_preview"] = group_view["days_em_aberto"]

    return group_view


def _filter_group_view(group: dict, lab: str, status: str, q: str) -> bool:
    if lab and group["lab_id"] != lab:
        return False
    if status and group["status_geral"] != status:
        return False
    if q:
        haystack = " ".join(
            value
            for value in [
                group.get("patient_name"),
                group.get("tutor_name"),
                group.get("paciente"),
                group.get("protocol"),
                group.get("record_id"),
            ]
            if value
        )
        if q.lower() not in haystack.lower():
            return False
    return True


def _fallback_group_view(protocol: dict) -> dict:
    items = [
        {
            "nome": item["name"],
            "status": item["status"],
            "item_id": item["itemId"],
            "alerta": item["alert"],
            "resultado": item["results"],
        }
        for item in protocol["items"]
    ]
    counts = _status_counts(
        [
            {
                "status": item["status"],
            }
            for item in protocol["items"]
        ]
    )
    return {
        "lab_id": protocol["labId"],
        "lab": protocol["labName"],
        "record_id": protocol["protocol"],
        "paciente": f"{protocol['patientName']} - {protocol['tutorName']}" if protocol.get("tutorName") else protocol["patientName"],
        "patient_name": protocol["patientName"],
        "tutor_name": protocol.get("tutorName") or "",
        "species_sex": protocol.get("speciesSex"),
        "protocol": protocol["protocol"],
        "data": protocol["date"],
        "date_display": protocol["date"],
        "data_raw": protocol["dateRaw"],
        "status_geral": protocol["status"],
        "dias_em_aberto": protocol.get("daysOpen"),
        "days_em_aberto_preview": protocol.get("daysOpen"),
        "liberado_em": protocol.get("releaseAt"),
        "liberado_em_iso": None,
        "release_at_display": protocol.get("releaseAt"),
        "portal_url": protocol.get("portalUrl"),
        "portal_id": protocol["protocol"],
        "criticality": protocol.get("criticality"),
        "alerta_geral": protocol.get("criticality"),
        "items_total": len(items),
        "ready_ratio_text": _ready_ratio_text(counts, len(items)),
        "status_counts": counts,
        "status_count_parts": _humanize_status_counts(counts),
        "timeline_parts": _timeline_parts(protocol.get("daysOpen"), None),
        "items_view": [
            {
                "id": item["id"],
                "name": item["name"],
                "status": item["status"],
                "alert": item["alert"],
                "item_id": item["itemId"],
                "release_at": item.get("releaseAt"),
                "release_at_display": item.get("releaseAtDisplay"),
                "results": item["results"],
            }
            for item in protocol["items"]
        ],
        "itens": items,
    }


def _build_group_view(group: dict) -> dict:
    snapshot_record = _snapshot_lookup(group["lab_id"], group["record_id"]) or {}
    patient_name, tutor_name = _parse_label(snapshot_record.get("label") or group["paciente"])
    items = _build_group_items(group, snapshot_record)
    counts = _status_counts(items)

    return {
        **group,
        "patient_name": patient_name,
        "tutor_name": tutor_name,
        "species_sex": None,
        "protocol": group["record_id"],
        "date_display": _format_date_only(group.get("data_raw"), group.get("data")),
        "release_at_display": _format_release(group.get("liberado_em_iso")),
        "criticality": group.get("alerta_geral") or _record_alert(snapshot_record),
        "items_total": len(items),
        "ready_ratio_text": _ready_ratio_text(counts, len(items)),
        "status_counts": counts,
        "status_count_parts": _humanize_status_counts(counts),
        "timeline_parts": _timeline_parts(group.get("dias_em_aberto"), group.get("liberado_em_iso")),
        "items_view": items,
    }


def get_card_sandbox_groups(lab: str = "", status: str = "", q: str = "") -> list[dict]:
    groups = [_build_group_view(group) for group in state.get_exames(lab, status, q)]
    if groups:
        return [_inject_sandbox_preview(group, index) for index, group in enumerate(groups)]

    fallback_groups = [_fallback_group_view(protocol) for protocol in _FALLBACK_PROTOCOLS]
    fallback_groups = [group for group in fallback_groups if _filter_group_view(group, lab, status, q)]
    return [_inject_sandbox_preview(group, index) for index, group in enumerate(fallback_groups)]


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
    patients = {protocol["patientName"] for protocol in protocols}
    reasons = {protocol["sampleReason"] for protocol in protocols}

    if "status" in missing and candidate["status"] not in statuses:
        score += 2
    if "lab" in missing and candidate["labId"] not in labs:
        score += 2
    if "criticality" in missing and candidate["criticality"]:
        score += 3
        if candidate["criticality"] == "red":
            score += 2
    if "multi-item" in missing and len(candidate["items"]) > 1:
        score += 2

    if candidate["patientName"] in patients:
        score -= 5
    if candidate["sampleReason"] in reasons:
        score -= 2
    if candidate["status"] in statuses and "status" not in missing:
        score -= 1

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
