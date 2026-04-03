from __future__ import annotations

from copy import deepcopy


DEFAULT_NOTIFICATION_SETTINGS: dict = {
    "events": {
        "received": {
            "enabled": True,
            "template": (
                "🧪 <b>Exame recebido no laboratório - {lab_name}</b>\n"
                "👤 {record_label}\n"
                "📋 {record_id} | {record_date}\n"
                "🔬 Exames\n"
                "{item_lines}"
            ),
        },
        "completed": {
            "enabled": True,
            "template": (
                "✅ <b>Exames concluídos - {lab_name}</b>\n"
                "👤 {record_label}\n"
                "📋 {record_id} | {record_date}\n"
                "🔬 Liberados neste lote\n"
                "{item_lines}"
            ),
        },
        "status_update": {
            "enabled": False,
            "template": (
                "🔄 <b>Status atualizado - {lab_name}</b>\n"
                "👤 {record_label}\n"
                "📋 {record_id} | {record_date}\n"
                "📍 {status_summary}\n"
                "{item_lines}"
            ),
        },
    }
}

NOTIFICATION_TEMPLATE_VARIABLES: tuple[dict[str, str], ...] = (
    {
        "name": "lab_name",
        "description": "Nome exibido do laboratório de origem.",
        "example": "Bioanálises",
    },
    {
        "name": "record_label",
        "description": "Identificação resumida do protocolo, normalmente paciente e tutor.",
        "example": "PIDA - Jingwei Du",
    },
    {
        "name": "record_id",
        "description": "Número do protocolo/requisição usado para rastrear o bloco.",
        "example": "08-00030473",
    },
    {
        "name": "record_date",
        "description": "Data operacional exibida no agrupador do protocolo.",
        "example": "31/03/2026 16:55",
    },
    {
        "name": "item_lines",
        "description": "Lista formatada dos exames envolvidos naquele envio.",
        "example": "• Hemograma\\n• TGP\\n• Creatinina",
    },
    {
        "name": "items_total",
        "description": "Quantidade total de exames incluídos no bloco da notificação.",
        "example": "3",
    },
    {
        "name": "status_summary",
        "description": "Resumo agregado das mudanças de status quando o template de atualização estiver ativo.",
        "example": "2 exame(s) passaram para EM CURSO",
    },
)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def ensure_notification_settings(config: dict | None) -> dict:
    base = deepcopy(DEFAULT_NOTIFICATION_SETTINGS)
    source = (config or {}).get("notification_settings") or {}
    source_events = source.get("events") or {}
    for event_key, event_defaults in base["events"].items():
        current = source_events.get(event_key) or {}
        template = current.get("template")
        enabled = current.get("enabled")
        if isinstance(template, str) and template.strip():
            event_defaults["template"] = template
        if isinstance(enabled, bool):
            event_defaults["enabled"] = enabled
    return base


def apply_notification_settings(config: dict) -> dict:
    settings = ensure_notification_settings(config)
    config["notification_settings"] = settings
    return settings


def render_notification_template(template: str, context: dict) -> str:
    return template.format_map(_SafeFormatDict(context))


def build_notification_preview_context() -> dict:
    return {
        "lab_name": "Bioanálises",
        "record_label": "PIDA - Jingwei Du",
        "record_id": "08-00030473",
        "record_date": "31/03/2026 16:55",
        "item_lines": "• Hemograma\n• TGP\n• Creatinina",
        "items_total": 3,
        "status_summary": "2 exame(s) passaram para EM CURSO",
    }
