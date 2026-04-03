from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

CARD_SANDBOX_DIR = Path(__file__).parent.parent / "poc" / "lab-card-variants"
DEFAULT_CARD_SANDBOX_VARIANT = "v1-reference"

CARD_SANDBOX_VARIANTS = [
    {
        "id": "v1-reference",
        "name": "V1 · Funcional",
        "note": "Base funcional aprovada até aqui: sinais à direita, trilho vívido, alertas em triângulo, tabela compacta e trilho orgânico forte.",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "neutral-lower",
        "meta_layout": "inline",
        "card_density": "standard",
    },
    {
        "id": "v2-species-badges",
        "name": "V2 · Badge espécie/sexo",
        "note": "Mantém a V1, mas colore o badge por sexo, capitaliza o texto e adiciona um ícone da espécie à esquerda.",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "inline",
        "card_density": "standard",
    },
    {
        "id": "v3-third-line",
        "name": "V3 · 3ª linha arejada",
        "note": "Leva data e protocolo para uma terceira linha menor, mantendo o respiro interno mais aberto sem crescer o card.",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "neutral-lower",
        "meta_layout": "third-line-compact",
        "card_density": "compact-3row-s3",
    },
    {
        "id": "v4-badges-third-line",
        "name": "V4 · Badge + 3ª linha arejada",
        "note": "Replica a V3 com badge de espécie/sexo colorido, capitalizado e com ícone da espécie.",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "third-line-compact",
        "card_density": "compact-3row-s3",
    }
    ,
    {
        "id": "v5-badges-third-line-mobile-locked",
        "name": "V5 · Badge + 3ª linha com status fixo no mobile",
        "note": "Parte da V4, mas preserva o bloco de status na direita também no celular, sem deixá-lo cair para baixo.",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "third-line-compact",
        "card_density": "compact-3row-s3",
    }
]

_VARIANTS_BY_ID = {variant["id"]: variant for variant in CARD_SANDBOX_VARIANTS}

# Sandbox layout overrides for the current fast-iteration round.
DEFAULT_CARD_SANDBOX_VARIANT = "v0-reference-current"

CARD_SANDBOX_VARIANTS = [
    {
        "id": "v0-reference-current",
        "name": "V0 - Consolidada final",
        "note": "Consolida protocolo apenas no expandido, simbolo inline antes do nome e textos condicionais centralizados em relacao ao badge.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "expanded-only",
        "species_mode": "icon-inline",
    },
    {
        "id": "v1-two-row-aligned",
        "name": "V1 - Base alinhada 2 linhas",
        "note": "2 linhas, data antes do laboratorio, protocolo clicavel e contagem apenas em Parcial.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "badge",
    },
    {
        "id": "v2-protocol-expanded",
        "name": "V2 - Protocolo so no expandido",
        "note": "Parte da V1, mas move o protocolo clicavel para dentro do agrupador expandido.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "expanded-only",
        "species_mode": "badge",
    },
    {
        "id": "v3-species-inline-icon",
        "name": "V3 - Simbolo inline antes do nome",
        "note": "Troca o badge de especie/sexo por um simbolo minimalista ao lado esquerdo do nome.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "icon-inline",
    },
    {
        "id": "v4-species-side-icon",
        "name": "V4 - Simbolo lateral entre trilho e texto",
        "note": "Mantem a V1, mas usa um simbolo de especie maior entre o trilho de criticidade e o conteudo.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "icon-side",
    },
    {
        "id": "v5-airy-two-row",
        "name": "V5 - Base com mais respiro",
        "note": "Mantem a V1, mas relaxa espacos internos e aceita um pouco mais de altura para aliviar a leitura.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-airy",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "badge",
    },
    {
        "id": "v6-days-only-when-stale",
        "name": "V6 - Dias so quando pesa",
        "note": "Mantem a V1, mas so mostra dias em aberto quando houver atraso relevante.",
        "family": "aligned-2row",
        "signals_align": "right",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "stale-only-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "badge",
    },
    {
        "id": "v7-centered-conditionals",
        "name": "V7 - Textos condicionais centralizados",
        "note": "Mantem a V1, mas centraliza a pilha de sinais para testar os textos condicionais alinhados ao badge de status.",
        "family": "aligned-2row",
        "signals_align": "center",
        "date_mode": "inline-meta",
        "rail_palette": "vivid",
        "item_alert_style": "triangle-alert-only",
        "result_table_width": "compact",
        "rail_shape": "organic-strong",
        "species_badge_mode": "sex-colored",
        "meta_layout": "two-row-clean",
        "card_density": "two-row-compact",
        "status_label_mode": "short",
        "ratio_mode": "partial-only",
        "days_mode": "non-ready-except-partial",
        "protocol_mode": "closed-link",
        "species_mode": "badge",
    },
]

_VARIANTS_BY_ID = {variant["id"]: variant for variant in CARD_SANDBOX_VARIANTS}

_PREVIEW_PROTOCOLS = [
    {
        "sampleReason": "critical-ready",
        "labId": "bitlab",
        "labName": "Bioanálises",
        "protocol": "08-00000001",
        "patientName": "Lua",
        "tutorName": "Patricia S.",
        "speciesSex": "cadela",
        "status": "Pronto",
        "criticality": "red",
        "dateRaw": "2026-03-31",
        "summaryAtIso": "2026-03-31T10:42:00",
        "releaseAtIso": "2026-03-31T10:42:00",
        "daysOpen": None,
        "portalUrl": "https://bitlabenterprise.com.br/bioanalises/resultados",
        "items": [
            {
                "name": "Creatinina veterinaria",
                "status": "Pronto",
                "alert": "yellow",
                "itemId": "fake-1",
                "releaseAtIso": "2026-03-31T10:42:00",
                "results": [
                    {
                        "nome": "Creatinina veterinaria",
                        "valor": "1,1 mg/dL",
                        "referencia": "Canino: 0,0 a 1,4 mg/dL",
                        "alerta": "yellow",
                    }
                ],
            },
            {
                "name": "Fosfatase alcalina",
                "status": "Pronto",
                "alert": None,
                "itemId": "fake-2",
                "releaseAtIso": "2026-03-31T10:42:00",
                "results": [
                    {
                        "nome": "Fosfatase alcalina",
                        "valor": "68 U/L",
                        "referencia": "Canino: 20 a 156 U/L",
                        "alerta": None,
                    }
                ],
            },
            {"name": "Gama-GT", "status": "Pronto", "alert": None, "itemId": "fake-3", "releaseAtIso": "2026-03-31T10:42:00", "results": []},
            {
                "name": "Hemograma",
                "status": "Pronto",
                "alert": "red",
                "itemId": "fake-4",
                "releaseAtIso": "2026-03-31T10:42:00",
                "results": [
                    {
                        "nome": "Hematócrito",
                        "valor": "22 %",
                        "referencia": "Canino: 37 a 55 %",
                        "alerta": "red",
                    },
                    {
                        "nome": "Leucócitos",
                        "valor": "14,8 mil/uL",
                        "referencia": "Canino: 6 a 17 mil/uL",
                        "alerta": None,
                    }
                ],
            },
            {"name": "TGP", "status": "Pronto", "alert": None, "itemId": "fake-5", "releaseAtIso": "2026-03-31T10:42:00", "results": []},
            {"name": "Ureia", "status": "Pronto", "alert": None, "itemId": "fake-6", "releaseAtIso": "2026-03-31T10:42:00", "results": []},
        ],
    },
    {
        "sampleReason": "partial-warning",
        "labId": "bitlab",
        "labName": "Bioanálises",
        "protocol": "08-00000002",
        "patientName": "Aurora",
        "tutorName": "Marilene C.",
        "speciesSex": "gata",
        "status": "Parcial",
        "criticality": "yellow",
        "dateRaw": "2026-03-31",
        "summaryAtIso": "2026-03-31T09:12:00",
        "releaseAtIso": None,
        "daysOpen": 2,
        "portalUrl": "https://bitlabenterprise.com.br/bioanalises/resultados",
        "items": [
            {"name": "Alergia a picada de pulga", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {"name": "Citologia", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {
                "name": "Creatinina",
                "status": "Pronto",
                "alert": None,
                "itemId": "fake-7",
                "releaseAtIso": "2026-03-31T09:12:00",
                "results": [
                    {
                        "nome": "Creatinina",
                        "valor": "0,9 mg/dL",
                        "referencia": "Felino: 0,8 a 1,8 mg/dL",
                        "alerta": None,
                    }
                ],
            },
            {"name": "Fosfatase alcalina", "status": "Pronto", "alert": None, "itemId": "fake-8", "releaseAtIso": "2026-03-31T09:12:00", "results": []},
            {"name": "Glicose", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {
                "name": "Hemograma",
                "status": "Pronto",
                "alert": "yellow",
                "itemId": "fake-9",
                "releaseAtIso": "2026-03-31T09:12:00",
                "results": [
                    {
                        "nome": "Neutrófilos",
                        "valor": "13,2 mil/uL",
                        "referencia": "Felino: 2,5 a 12,5 mil/uL",
                        "alerta": "yellow",
                    }
                ],
            },
            {"name": "Proteina total", "status": "Pronto", "alert": None, "itemId": "fake-10", "releaseAtIso": "2026-03-31T09:12:00", "results": []},
            {"name": "TGP", "status": "Pronto", "alert": None, "itemId": "fake-11", "releaseAtIso": "2026-03-31T09:12:00", "results": []},
            {"name": "Triglicerideos", "status": "Pronto", "alert": None, "itemId": "fake-12", "releaseAtIso": "2026-03-31T09:12:00", "results": []},
            {"name": "Ureia", "status": "Pronto", "alert": None, "itemId": "fake-13", "releaseAtIso": "2026-03-31T09:12:00", "results": []},
        ],
    },
    {
        "sampleReason": "long-open",
        "labId": "bitlab",
        "labName": "Bioanálises",
        "protocol": "08-00000003",
        "patientName": "Bento",
        "tutorName": "Daniel F.",
        "speciesSex": "cão",
        "status": "Em Andamento",
        "criticality": "red",
        "dateRaw": "2026-03-21",
        "summaryAtIso": "2026-03-21T07:55:00",
        "releaseAtIso": None,
        "daysOpen": 11,
        "portalUrl": "https://bitlabenterprise.com.br/bioanalises/resultados",
        "items": [
            {"name": "ALT", "status": "Em Andamento", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {"name": "AST", "status": "Recebido", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {"name": "Hemograma", "status": "Analisando", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
            {"name": "Ureia", "status": "Recebido", "alert": None, "itemId": None, "releaseAtIso": None, "results": []},
        ],
    },
    {
        "sampleReason": "nexio-single",
        "labId": "nexio",
        "labName": "Nexio Patologia",
        "protocol": "AP000044/26",
        "patientName": "Thor",
        "tutorName": "Márcia",
        "speciesSex": "gato",
        "status": "Pronto",
        "criticality": None,
        "dateRaw": "2026-03-04",
        "summaryAtIso": "2026-03-28T14:18:00",
        "releaseAtIso": "2026-03-28T14:18:00",
        "daysOpen": None,
        "portalUrl": "https://www.pathoweb.com.br",
        "items": [
            {
                "name": "Patologia AP000044/26",
                "status": "Pronto",
                "alert": None,
                "itemId": None,
                "releaseAtIso": "2026-03-28T14:18:00",
                "results": [
                    {
                        "nome": "Diagnóstico",
                        "valor": "Dermatite eosinofílica",
                        "referencia": "Laudo final",
                        "alerta": None,
                    }
                ],
            },
        ],
    },
]


def get_card_sandbox_variant(variant_id: str | None) -> dict:
    if not variant_id:
        return _VARIANTS_BY_ID[DEFAULT_CARD_SANDBOX_VARIANT]
    return _VARIANTS_BY_ID.get(variant_id, _VARIANTS_BY_ID[DEFAULT_CARD_SANDBOX_VARIANT])


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _format_date(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except Exception:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return raw


def _format_time(raw: str | None) -> str:
    parsed = _parse_iso(raw)
    if not parsed:
        return ""
    return parsed.strftime("%H:%M")


def _status_counts(items: list[dict]) -> dict[str, int]:
    order = ["Pronto", "Em Andamento", "Analisando", "Recebido", "Cancelado"]
    counter = Counter(item["status"] for item in items)
    return {status: counter[status] for status in order if counter[status]}


def _ready_ratio_text(counts: dict[str, int], total: int) -> str:
    return f"{counts.get('Pronto', 0)}/{total} prontos"


def _legacy_count_parts(counts: dict[str, int]) -> list[dict]:
    parts = [{"label": f"{sum(counts.values())} exames", "tone": "neutral"}]
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


def _build_item_view(index: int, item: dict) -> dict:
    return {
        "id": item.get("itemId") or f"preview-{index}",
        "name": item["name"],
        "status": item["status"],
        "alert": item.get("alert"),
        "item_id": item.get("itemId"),
        "release_at": item.get("releaseAtIso"),
        "release_at_display": _format_date(item.get("releaseAtIso")) if item.get("releaseAtIso") else None,
        "results": item.get("results") or [],
    }


def _days_payload(days_open: int | None) -> tuple[str | None, bool]:
    if days_open is None:
        return None, False
    return f"{days_open}d em aberto", days_open > 7


def _matches_query(group: dict, lab: str, status: str, q: str) -> bool:
    if lab and group["lab_id"] != lab:
        return False
    if status and group["status_geral"] != status:
        return False
    if not q:
        return True
    haystack = " ".join(
        [
            group["patient_name"],
            group["tutor_name"],
            group["protocol"],
            group["lab"],
        ]
    ).lower()
    return q.lower() in haystack


def _build_preview_group(protocol: dict) -> dict:
    items_view = [_build_item_view(index, item) for index, item in enumerate(protocol["items"], start=1)]
    counts = _status_counts(items_view)
    days_label, days_stale = _days_payload(protocol.get("daysOpen"))
    date_display = _format_date(protocol["dateRaw"])
    time_display = _format_time(protocol.get("summaryAtIso"))

    return {
        "sample_reason": protocol["sampleReason"],
        "lab_id": protocol["labId"],
        "lab": protocol["labName"],
        "record_id": protocol["protocol"],
        "paciente": f"{protocol['patientName']} - {protocol['tutorName']}",
        "patient_name": protocol["patientName"],
        "tutor_name": protocol["tutorName"],
        "species_sex": protocol.get("speciesSex"),
        "protocol": protocol["protocol"],
        "data": date_display,
        "data_raw": protocol["dateRaw"],
        "date_display": date_display,
        "time_display": time_display,
        "status_geral": protocol["status"],
        "dias_em_aberto": protocol.get("daysOpen"),
        "days_label": days_label,
        "days_stale": days_stale,
        "liberado_em": _format_time(protocol.get("releaseAtIso")) if protocol.get("releaseAtIso") else None,
        "release_at_display": _format_date(protocol.get("releaseAtIso")) if protocol.get("releaseAtIso") else None,
        "portal_url": protocol.get("portalUrl"),
        "portal_id": protocol["protocol"],
        "criticality": protocol.get("criticality"),
        "alerta_geral": protocol.get("criticality"),
        "items_total": len(items_view),
        "ready_ratio_text": _ready_ratio_text(counts, len(items_view)),
        "status_counts": counts,
        "status_count_parts": _legacy_count_parts(counts),
        "items_view": items_view,
        "itens": [
            {
                "nome": item["name"],
                "status": item["status"],
                "item_id": item.get("itemId"),
                "alerta": item.get("alert"),
                "resultado": item.get("results") or [],
            }
            for item in protocol["items"]
        ],
    }


def get_card_sandbox_groups(lab: str = "", status: str = "", q: str = "") -> list[dict]:
    groups = [_build_preview_group(protocol) for protocol in _PREVIEW_PROTOCOLS]
    return [group for group in groups if _matches_query(group, lab, status, q)]


def get_card_sandbox_runtime() -> dict:
    return {
        "generatedAt": datetime.now().isoformat(),
        "source": "preview-fixture",
        "notes": [
            "Sandbox espelhado com protocolos fixos para iteração visual rápida.",
            "Inclui combinações estáveis de criticidade, atraso, espécie/sexo e resultados prontos.",
            "Não depende do estado vivo do Lab Monitor para facilitar comparações entre versões.",
        ],
        "protocols": _PREVIEW_PROTOCOLS,
    }
