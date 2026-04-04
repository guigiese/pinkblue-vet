from __future__ import annotations

import html
import re
import unicodedata


KEYWORDS_TO_EMPHASIZE = (
    "positivo",
    "negativo",
    "detectado",
    "nao detectado",
    "não detectado",
)

SKIP_SECTION_TOKENS = (
    "paciente",
    "proprietario",
    "proprietário",
    "tutor",
    "veterinario",
    "veterinário",
    "medico veterinario",
    "médico veterinário",
    "idade",
    "sexo",
    "raca",
    "raça",
    "especie",
    "espécie",
    "material",
    "solicitante",
    "requisicao",
    "requisição",
    "protocolo",
)

KNOWN_SECTION_TITLES = {
    "diagnostico": "Diagnóstico",
    "diagnóstico": "Diagnóstico",
    "resultado": "Resultado",
    "metodologia": "Metodologia",
    "macroscopia": "Macroscopia",
    "microscopia": "Microscopia",
    "conclusao": "Conclusão",
    "conclusão": "Conclusão",
    "comentarios": "Comentários",
    "comentários": "Comentários",
    "observacoes": "Observações",
    "observações": "Observações",
}


def _normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.strip().lower())
        if unicodedata.category(c) != "Mn"
    )


def _is_heading(line: str) -> bool:
    clean = line.strip().rstrip(":")
    normalized = _normalize(clean)
    if normalized in KNOWN_SECTION_TITLES:
        return True
    if len(clean) > 72:
        return False
    if clean.endswith(":"):
        return True
    return clean.isupper() and len(clean.split()) <= 5


def _display_heading(line: str) -> str:
    normalized = _normalize(line.strip().rstrip(":"))
    return KNOWN_SECTION_TITLES.get(normalized, line.strip().rstrip(":").capitalize())


def _should_skip_line(line: str) -> bool:
    normalized = _normalize(line)
    return any(normalized.startswith(token) for token in SKIP_SECTION_TOKENS)


def _highlight_keywords(text: str) -> str:
    escaped = html.escape(text)
    for keyword in sorted(KEYWORDS_TO_EMPHASIZE, key=len, reverse=True):
        pattern = re.compile(re.escape(html.escape(keyword)), re.IGNORECASE)
        escaped = pattern.sub(lambda m: f"<strong><u>{m.group(0)}</u></strong>", escaped)
    return escaped


def _render_section_body(lines: list[str]) -> str:
    paragraphs = []
    for raw in lines:
        cleaned = raw.strip()
        if not cleaned or _should_skip_line(cleaned):
            continue
        paragraphs.append(f"<p>{_highlight_keywords(cleaned)}</p>")
    return "".join(paragraphs)


def build_report_sections(report_text: str, diagnosis_text: str = "") -> list[dict[str, str]]:
    lines = [line.strip() for line in (report_text or "").splitlines()]
    lines = [line for line in lines if line]

    sections: list[dict[str, str]] = []
    current_title = "Laudo"
    current_lines: list[str] = []

    def flush():
        nonlocal current_lines, current_title
        body = _render_section_body(current_lines)
        if body:
            sections.append({"title": current_title, "html": body})
        current_lines = []

    for line in lines:
        if _should_skip_line(line):
            continue
        if _is_heading(line):
            flush()
            current_title = _display_heading(line)
            continue
        current_lines.append(line)
    flush()

    diagnosis = (diagnosis_text or "").strip()
    if diagnosis:
        diagnosis_section = {
            "title": "Diagnóstico",
            "html": _render_section_body([diagnosis]),
        }
        sections = [
            section for section in sections
            if _normalize(section["title"]) != "diagnostico"
        ]
        sections.insert(0, diagnosis_section)

    if not sections and report_text:
        sections = [{"title": "Laudo", "html": _render_section_body([report_text])}]

    return sections
