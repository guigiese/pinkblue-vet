"""
Conector para BioAnálises BitLab.
API REST com autenticação JWT.
"""

import os
import re
import zlib
import time
import unicodedata
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pb_platform.storage import store
from .base import LabConnector

_REF_PAT    = re.compile(r"[\d.,]+\s+a\s+[\d.,]+")
_ALERT_RANK = {None: 0, "yellow": 1, "red": 2}
_PDF_TEXT_PAT = re.compile(
    r"(?P<x>\d+(?:\.\d+)?)\s+(?P<y>\d+(?:\.\d+)?)\s+Td\s+\((?P<text>(?:\\.|[^()])*)\)\s+Tj"
)


def _try_float(text: str) -> float | None:
    try:
        return float(text.strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _parse_num(text: str) -> float:
    return float(text.strip().replace(".", "").replace(",", "."))


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _clean_breed(text: str) -> str:
    clean = re.sub(r"\.+", ".", (text or "").strip()).strip(" .")
    if not clean:
        return ""
    if clean.upper().replace(".", "") == "SRD":
        return "SRD"
    return clean.title()


def _pdf_unescape(text: str) -> str:
    return (
        text.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .strip()
    )


def _clean_report_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    cleaned: list[str] = []
    prev_blank = True
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
            continue
        cleaned.append(line)
        prev_blank = False
    return "\n".join(cleaned).strip()


def _compose_species_sex(species_raw: str, sex_raw: str) -> str:
    species_norm = _strip_accents((species_raw or "").strip().lower())
    sex_norm = (sex_raw or "").strip().upper()

    if species_norm.startswith("canin"):
        return "cadela" if sex_norm == "F" else "cão" if sex_norm == "M" else "cão"
    if species_norm.startswith("felin"):
        return "gata" if sex_norm == "F" else "gato" if sex_norm == "M" else "gato"
    if not species_raw:
        return ""
    if sex_norm:
        return f"{species_raw.title()} {sex_norm}"
    return species_raw.title()


def _normalize_species_key(*values: str) -> str:
    for value in values:
        norm = _strip_accents((value or "").strip().lower())
        if not norm:
            continue
        if any(token in norm for token in ("canin", "cao", "cadela", "cachorr")):
            return "canine"
        if any(token in norm for token in ("felin", "gato", "gata")):
            return "feline"
    return ""


def _normalize_sex_key(*values: str) -> str:
    for value in values:
        norm = _strip_accents((value or "").strip().lower())
        if not norm:
            continue
        if norm in {"f", "femea", "female"} or "femea" in norm:
            return "F"
        if norm in {"m", "macho", "male"} or "macho" in norm:
            return "M"
        if any(token in norm for token in ("cadela", "gata")):
            return "F"
        if any(token in norm for token in ("cao", "cão", "gato")):
            return "M"
    return ""


def _parse_reference_entry(text: str) -> dict | None:
    ref_m = _REF_PAT.search(text or "")
    if not ref_m:
        return None
    parts = ref_m.group().split(" a ")
    try:
        range_min = _parse_num(parts[0])
        range_max = _parse_num(parts[1])
    except Exception:
        return None
    label = re.sub(r"[:\-\s]+$", "", (text or "")[:ref_m.start()].strip())
    species_key = _normalize_species_key(label)
    sex_key = _normalize_sex_key(label)
    return {
        "text": (text or "").strip(),
        "range": (range_min, range_max),
        "species_key": species_key,
        "sex_key": sex_key,
        "specificity": int(bool(species_key)) + int(bool(sex_key)),
    }


def _select_reference_entries(entries: list[dict], patient_context: dict | None) -> list[dict]:
    if not entries:
        return []

    patient_context = patient_context or {}
    patient_species = _normalize_species_key(
        patient_context.get("species_sex", ""),
        patient_context.get("species_raw", ""),
    )
    patient_sex = _normalize_sex_key(
        patient_context.get("sex_raw", ""),
        patient_context.get("species_sex", ""),
    )

    selected: list[dict] = []
    best_score: int | None = None

    for entry in entries:
        entry_species = entry.get("species_key", "")
        entry_sex = entry.get("sex_key", "")
        if entry_species and patient_species and entry_species != patient_species:
            continue
        if entry_sex and patient_sex and entry_sex != patient_sex:
            continue

        score = 0
        if patient_species and entry_species == patient_species:
            score += 1
        if patient_sex and entry_sex == patient_sex:
            score += 1

        if best_score is None or score > best_score:
            best_score = score
            selected = [entry]
        elif score == best_score:
            selected.append(entry)

    if not selected:
        return entries
    if best_score and best_score > 0:
        return selected

    generic = [entry for entry in selected if entry.get("specificity", 0) == 0]
    return generic or selected


def _normalize_age_bucket(*values: str) -> str:
    for value in values:
        norm = _strip_accents((value or "").strip().lower())
        if not norm:
            continue
        if norm in {"n/e", "ne", "n/d", "nd", "nao informado", "nao especificado"}:
            return "adult"
        months = re.search(r"(\d+)\s*(mes|meses)", norm)
        if months:
            return "juvenile" if int(months.group(1)) < 12 else "adult"
        years = re.search(r"(\d+)\s*(ano|anos)", norm)
        if years:
            return "juvenile" if int(years.group(1)) < 1 else "adult"
        if "filhote" in norm:
            return "juvenile"
        if "adult" in norm:
            return "adult"
    return ""


def _recent_layout_headers(
    sorted_tops: list[int],
    rows_by_top: dict[int, list[dict]],
    current_index: int,
    window: int | None = None,
) -> list[str]:
    headers: list[str] = []
    start = 0 if window is None else max(0, current_index - window)
    for idx in range(start, current_index):
        top = sorted_tops[idx]
        text = " ".join(
            c["text"] for c in sorted(rows_by_top[top], key=lambda col: col["left"])
        )
        norm = _strip_accents(text).lower()
        if norm:
            headers.append(norm)
    return headers


def _extract_layout_a_reference_options(ref_candidates: list[dict]) -> list[str]:
    options: list[str] = []
    for col in sorted(ref_candidates, key=lambda entry: entry["left"]):
        text = (col.get("text") or "").strip()
        matches = [m.group().strip() for m in _REF_PAT.finditer(text)]
        if len(matches) > 1:
            options.extend(re.sub(r"\s+", " ", match).strip() for match in matches)
        elif matches:
            options.append(re.sub(r"\s+", " ", text).strip())
    return options


def _layout_a_context(
    sorted_tops: list[int],
    rows_by_top: dict[int, list[dict]],
    current_index: int,
    patient_context: dict | None,
) -> dict:
    patient_context = patient_context or {}
    patient_species = _normalize_species_key(
        patient_context.get("species_sex", ""),
        patient_context.get("species_raw", ""),
    )
    patient_age_bucket = _normalize_age_bucket(
        patient_context.get("patient_age", ""),
        patient_context.get("idade", ""),
    ) or "adult"
    headers = _recent_layout_headers(sorted_tops, rows_by_top, current_index)
    has_species_headers = any("caninos" in h and "felinos" in h for h in headers)
    has_age_headers = any("adultos" in h and "filhotes" in h for h in headers)
    return {
        "patient_species": patient_species,
        "patient_age_bucket": patient_age_bucket,
        "has_species_headers": has_species_headers,
        "has_age_headers": has_age_headers,
    }


def _select_layout_a_reference(
    ref_candidates: list[dict],
    numeric_candidates: list[dict],
    sorted_tops: list[int],
    rows_by_top: dict[int, list[dict]],
    current_index: int,
    patient_context: dict | None,
) -> str:
    options = _extract_layout_a_reference_options(ref_candidates)
    if not options:
        return ""

    ctx = _layout_a_context(sorted_tops, rows_by_top, current_index, patient_context)
    patient_species = ctx["patient_species"]
    patient_age_bucket = ctx["patient_age_bucket"]
    has_species_headers = ctx["has_species_headers"]
    has_age_headers = ctx["has_age_headers"]

    if len(options) > 1 and has_species_headers and patient_species in {"canine", "feline"}:
        species_idx = 0 if patient_species == "canine" else 1
        if species_idx < len(options):
            return options[species_idx]

    if len(options) > 1 and len(numeric_candidates) > 1:
        return options[0]

    if len(options) > 1 and has_age_headers and patient_age_bucket:
        age_idx = 1 if patient_age_bucket == "juvenile" else 0
        if age_idx < len(options):
            return options[age_idx]

    return options[0]


def _format_layout_a_component_value(value_str: str, component_kind: str) -> str:
    value = (value_str or "").strip()
    if not value:
        return ""
    if component_kind == "percent":
        return value if "%" in value else f"{value}%"
    if component_kind == "absolute":
        return value if "/mm" in value.lower() else f"{value}/mm3"
    return value


def _layout_a_component_kind(idx: int) -> str:
    if idx == 0:
        return "percent"
    if idx == 1:
        return "absolute"
    return "value"


def _build_layout_a_components(
    ref_candidates: list[dict],
    numeric_candidates: list[dict],
    sorted_tops: list[int],
    rows_by_top: dict[int, list[dict]],
    current_index: int,
    patient_context: dict | None,
    exam_name: str,
) -> list[dict]:
    numbers = [c["text"].strip() for c in sorted(numeric_candidates, key=lambda entry: entry["left"])]
    options = _extract_layout_a_reference_options(ref_candidates)
    ctx = _layout_a_context(sorted_tops, rows_by_top, current_index, patient_context)

    refs: list[str] = []
    if ctx["has_species_headers"] and len(options) > 1:
        refs.append(
            _select_layout_a_reference(
                ref_candidates,
                numeric_candidates,
                sorted_tops,
                rows_by_top,
                current_index,
                patient_context,
            )
        )
        refs.extend("" for _ in range(max(0, len(numbers) - 1)))
    elif len(options) >= len(numbers):
        refs = options[:len(numbers)]
    elif len(options) == 1:
        refs = [options[0]]
        refs.extend("" for _ in range(max(0, len(numbers) - 1)))
    else:
        refs = options[:]
        refs.extend("" for _ in range(max(0, len(numbers) - len(refs))))

    components: list[dict] = []
    for idx, value_str in enumerate(numbers):
        component_kind = _layout_a_component_kind(idx)
        ref_str = refs[idx] if idx < len(refs) else ""
        components.append({
            "kind": component_kind,
            "valor": _format_layout_a_component_value(value_str, component_kind),
            "referencia": ref_str or "n/d",
            "alerta": _calc_alert_single(value_str, ref_str, exam_name),
        })
    return components


def _get_threshold_cutoffs(exam_name: str) -> tuple[float, float]:
    threshold = store.get_exam_threshold(exam_name)
    warning_cutoff = max(0.0, float(threshold["warning_multiplier"]) - 1.0)
    critical_cutoff = max(warning_cutoff, float(threshold["critical_multiplier"]) - 1.0)
    return warning_cutoff, critical_cutoff


def _alert_from_range(numeric: float, rmin: float, rmax: float, exam_name: str) -> str | None:
    if rmin <= numeric <= rmax:
        return None
    boundary = rmin if numeric < rmin else rmax
    dev = abs(numeric - boundary) / boundary if boundary else 1.0
    warning_cutoff, critical_cutoff = _get_threshold_cutoffs(exam_name)
    if dev > critical_cutoff:
        return "red"
    if dev >= warning_cutoff:
        return "yellow"
    return None


def _calc_alert_single(value_str: str, ref_str: str, exam_name: str) -> str | None:
    """Alert for a single numeric range, using persisted per-exam thresholds when available."""
    try:
        numeric = _parse_num(value_str)
        ref_m = _REF_PAT.search(ref_str)
        if ref_m:
            parts = ref_m.group().split(" a ")
            rmin = _parse_num(parts[0])
            rmax = _parse_num(parts[1])
            return _alert_from_range(numeric, rmin, rmax, exam_name)
    except (ValueError, ZeroDivisionError):
        pass
    return None


class BitlabConnector(LabConnector):

    BASE = "https://bitlabenterprise.com.br/bioanalises/api/v1"

    def __init__(self):
        self._usuario     = os.environ.get("BITLAB_USUARIO",   "11702")
        self._senha       = os.environ.get("BITLAB_SENHA",     "melanie")
        self._cd_convenio = int(os.environ.get("BITLAB_CD_CONVENIO", "1170"))
        self._cd_posto    = int(os.environ.get("BITLAB_CD_POSTO",    "8"))
        self._dias_atras  = int(os.environ.get("DIAS_ATRAS",         "60"))

    @property
    def lab_id(self):
        return "bitlab"

    @property
    def lab_name(self):
        return "Bioanálises"

    def _login(self) -> str:
        r = requests.post(f"{self.BASE}/SignIn",
                          json={"userName": self._usuario, "password": self._senha},
                          timeout=15)
        r.raise_for_status()
        return r.json()["token"]

    def _buscar_requisicoes(self, token: str, page_size: int = 500) -> list[dict]:
        hoje   = datetime.now().strftime("%Y-%m-%d")
        sync_hints = getattr(self, "sync_hints", {}) or {}
        days_back = int(sync_hints.get("days_back") or self._dias_atras)
        days_back = max(7, min(days_back, self._dias_atras))
        inicio = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        r = requests.post(
            f"{self.BASE}/Requisicao?pageNumber=1&pageSize={page_size}",
            headers={"Authorization": f"Bearer {token}"},
            json={"dataInicial": inicio, "dataFinal": hoje},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data

    def test_connection(self) -> str:
        token = self._login()
        self._buscar_requisicoes(token, page_size=1)
        return "✓ Conexão OK — API acessível"

    def _buscar_itens(self, token: str, cd_requisicao: int) -> list[dict]:
        r = requests.post(
            f"{self.BASE}/ItemRequisicao",
            headers={"Authorization": f"Bearer {token}"},
            json={"cdPosto": self._cd_posto, "cdRequisicao": cd_requisicao,
                  "cdConvenio": self._cd_convenio},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def buscar_resultado_html(self, token: str, item_id: str) -> bytes:
        """Returns raw (zlib-compressed) HTML for a single exam result."""
        r = requests.get(
            f"{self.BASE}/ItemRequisicao/{item_id}?type=Html",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.content

    def buscar_requisicao_pdf(self, token: str, requisicao_portal_id: str) -> bytes:
        r = requests.get(
            f"{self.BASE}/Requisicao/{requisicao_portal_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        r.raise_for_status()
        return r.content

    @staticmethod
    def parse_requisicao_metadata(raw_pdf: bytes) -> dict:
        try:
            text = raw_pdf.decode("latin-1", errors="ignore")
        except Exception:
            return {}

        entries: list[tuple[float, float, str]] = [
            (float(match.group("x")), float(match.group("y")), _pdf_unescape(match.group("text")))
            for match in _PDF_TEXT_PAT.finditer(text)
        ]

        if not entries:
            return {}

        def pick(x_min: float, x_max: float, y_target: float, tolerance: float = 2.0) -> str:
            for x_pos, y_pos, value in entries:
                if x_min <= x_pos <= x_max and abs(y_pos - y_target) <= tolerance and value:
                    return value
            return ""

        patient_display = pick(100, 130, 712.5)
        owner_name = pick(100, 130, 678.0)
        species_raw = pick(100, 130, 666.0)
        breed = _clean_breed(pick(430, 460, 678.0))
        sex_raw = pick(490, 520, 690.0)
        age = pick(430, 460, 690.0)
        collected_at = pick(430, 460, 702.0)
        posto = pick(430, 445, 714.0)
        requisicao_num = pick(460, 470, 714.0)
        species_sex = _compose_species_sex(species_raw, sex_raw)

        return {
            "patient_display": patient_display,
            "owner_name": owner_name,
            "species_raw": species_raw,
            "sex_raw": sex_raw,
            "species_sex": species_sex,
            "breed": breed,
            "patient_age": age,
            "collected_at": collected_at,
            "protocol_number": f"{posto}-{requisicao_num}" if posto and requisicao_num else requisicao_num,
        }

    @staticmethod
    def parse_resultado(raw_bytes: bytes, patient_context: dict | None = None) -> list[dict]:
        """
        Parse BitLab zlib-compressed HTML result into structured rows.
        Handles two layouts:
          Layout A (hemograma): name + bold value + reference all on same row.
          Layout B (biochemistry): name + value on top row; species refs on subsequent rows.
        Returns list of {nome, valor, referencia, alerta} dicts.
        alerta: None | "yellow" (<=20% out of range) | "red" (>20% out of range)
        """
        try:
            html = zlib.decompress(raw_bytes).decode("latin-1")
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        rows_by_top: dict[int, list[dict]] = {}

        for div in soup.find_all("div", style=True):
            style = div.get("style", "")
            lm = re.search(r"left:(\d+)px", style)
            tm = re.search(r"top:(\d+)px", style)
            if not lm or not tm or div.find("img"):
                continue
            left = int(lm.group(1))
            top  = int(tm.group(1))
            text = div.get_text().strip()
            if text:
                rows_by_top.setdefault(top, []).append(
                    {"left": left, "text": text, "bold": bool(div.find("b"))}
                )

        sorted_tops = sorted(rows_by_top)
        skip_tops: set[int] = set()
        results = []

        for i, top in enumerate(sorted_tops):
            if top in skip_tops:
                continue

            cols = sorted(rows_by_top[top], key=lambda c: c["left"])

            # Name: one or more leftmost columns (left < 250)
            name_parts = [c["text"] for c in cols if c["left"] < 250]
            if not name_parts:
                continue

            raw_name = " ".join(name_parts)
            name = re.sub(r"\.{3,}:?\s*$", "", raw_name).rstrip(":").strip()
            if len(name) < 3:
                continue

            # Layout A: same-row reference "X a Y"
            ref_candidates = [
                c for c in cols
                if c["left"] >= 250 and _REF_PAT.search(c["text"])
            ]

            if ref_candidates:
                # Layout A — value + reference on same row
                val_candidates = [
                    c for c in cols
                    if c["left"] >= 250 and c not in ref_candidates
                ]
                numeric_candidates = [
                    c for c in val_candidates if _try_float(c["text"]) is not None
                ]
                val_col = (
                    next((c for c in numeric_candidates if c["bold"]), None)
                    or next((c for c in numeric_candidates), None)
                )
                if not val_col:
                    continue
                if len(numeric_candidates) > 1:
                    components = _build_layout_a_components(
                        ref_candidates,
                        numeric_candidates,
                        sorted_tops,
                        rows_by_top,
                        i,
                        patient_context,
                        name,
                    )
                    worst = max(
                        (component["alerta"] for component in components),
                        key=lambda level: _ALERT_RANK.get(level, 0),
                        default=None,
                    )
                    primary = components[0] if components else {"valor": "", "referencia": "n/d"}
                    results.append({
                        "nome": name,
                        "valor": primary["valor"],
                        "referencia": primary["referencia"],
                        "alerta": worst,
                        "components": components,
                    })
                else:
                    value_str = val_col["text"].strip()
                    ref_str = _select_layout_a_reference(
                        ref_candidates,
                        numeric_candidates,
                        sorted_tops,
                        rows_by_top,
                        i,
                        patient_context,
                    )
                    results.append({
                        "nome":       name,
                        "valor":      value_str,
                        "referencia": ref_str,
                        "alerta":     _calc_alert_single(value_str, ref_str, name),
                    })

            else:
                # Layout B — value on current row, species refs on look-ahead rows
                non_name_cols = [c for c in cols if c["left"] >= 250]
                value_str: str | None = None
                unit_str:  str | None = None
                for c in non_name_cols:
                    txt = c["text"].strip()
                    if value_str is None and _try_float(txt) is not None:
                        value_str = txt
                    elif value_str is not None and unit_str is None and not _REF_PAT.search(txt):
                        unit_str = txt

                if value_str is None:
                    continue  # no numeric value → not a parameter row

                # Look ahead for species reference rows
                ref_entries: list[dict] = []

                for j in range(i + 1, len(sorted_tops)):
                    next_top = sorted_tops[j]
                    next_cols = sorted(rows_by_top[next_top], key=lambda c: c["left"])

                    # Stop if this row is a new parameter (name on left + numeric on right)
                    next_name_cols  = [c for c in next_cols if c["left"] < 250]
                    next_right_cols = [c for c in next_cols if c["left"] >= 250]
                    if next_name_cols and next_right_cols:
                        if any(_try_float(c["text"]) is not None for c in next_right_cols):
                            break

                    # Stop on section headers
                    all_text = " ".join(c["text"] for c in next_cols)
                    if "Resultados Anteriores" in all_text:
                        break

                    # Collect species refs from right-side columns
                    for c in next_cols:
                        if c["left"] < 300:
                            continue
                        ref_m = _REF_PAT.search(c["text"])
                        if ref_m:
                            skip_tops.add(next_top)
                            entry = _parse_reference_entry(c["text"])
                            if entry:
                                ref_entries.append(entry)

                valor_display = value_str + (f" {unit_str}" if unit_str else "")
                selected_refs = _select_reference_entries(ref_entries, patient_context)

                if not selected_refs:
                    results.append({
                        "nome":       name,
                        "valor":      valor_display,
                        "referencia": "—",
                        "alerta":     None,
                    })
                    continue

                # Alert: outside ALL ranges → red/yellow; outside SOME → yellow; none → None
                alert: str | None = None
                numeric = _try_float(value_str)
                if numeric is not None:
                    alerts = [
                        _alert_from_range(numeric, rmin, rmax, name)
                        for rmin, rmax in (entry["range"] for entry in selected_refs)
                    ]
                    alert = max(
                        (level for level in alerts),
                        key=lambda level: _ALERT_RANK.get(level, 0),
                        default=None,
                    )

                results.append({
                    "nome":       name,
                    "valor":      valor_display,
                    "referencia": "; ".join(entry["text"] for entry in selected_refs),
                    "alerta":     alert,
                })

        return results

    @staticmethod
    def parse_resultado_text(raw_bytes: bytes) -> str:
        try:
            html = zlib.decompress(raw_bytes).decode("latin-1")
        except Exception:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        return _clean_report_text(text)

    def enrich_resultados(self, anterior: dict, atual: dict) -> None:
        """
        Fetch and cache result alert levels for newly-Pronto items. Mutates atual in-place.
        - If item was already Pronto with a cached alerta → carries it forward (no HTTP call).
        - If item is newly Pronto → fetches result HTML and stores alerta + resultado rows.
        """
        from web.state import normalize_status

        to_fetch: list[tuple[str, str, str]] = []  # (rid, iid, item_id)

        for rid, rec in atual.items():
            ant_rec = anterior.get(rid, {})
            for iid, item in rec["itens"].items():
                if normalize_status(item["status"]) != "Pronto":
                    continue
                ant_item = ant_rec.get("itens", {}).get(iid, {})
                # Only carry forward if we actually have parsed rows (non-empty resultado).
                # alerta=None + resultado=[] means old parse failed → re-fetch.
                if "alerta" in ant_item and ant_item.get("resultado"):
                    item["alerta"]    = ant_item["alerta"]
                    item["resultado"] = ant_item["resultado"]
                elif item.get("item_id"):
                    to_fetch.append((rid, iid, item["item_id"]))

        if not to_fetch:
            return

        try:
            token = self._login()
        except Exception as e:
            print(f"  [BitLab resultados] login failed: {e}")
            return

        for rid, iid, item_id in to_fetch:
            try:
                raw = self.buscar_resultado_html(token, item_id)
                rows = self.parse_resultado(raw, atual[rid])
                report_text = ""
                if not rows:
                    report_text = self.parse_resultado_text(raw)
                worst = max(
                    (r["alerta"] for r in rows),
                    key=lambda a: _ALERT_RANK.get(a, 0),
                    default=None,
                )
                atual[rid]["itens"][iid]["alerta"]    = worst
                atual[rid]["itens"][iid]["resultado"] = rows
                if report_text:
                    atual[rid]["itens"][iid]["report_text"] = report_text
                print(f"  [BitLab resultados] {iid} -> alerta={worst}")
            except Exception as e:
                print(f"  [BitLab resultados] {iid}: {e}")
            time.sleep(0.1)

    def enrich_snapshot_metadata(self, anterior: dict, atual: dict) -> None:
        carry_fields = (
            "owner_name",
            "species_raw",
            "sex_raw",
            "species_sex",
            "breed",
            "patient_age",
            "collected_at",
            "protocol_number",
        )
        to_fetch: list[tuple[str, str]] = []

        for rid, record in atual.items():
            ant_rec = anterior.get(rid, {})
            for field in carry_fields:
                if ant_rec.get(field) and not record.get(field):
                    record[field] = ant_rec[field]

            if record.get("species_sex") and record.get("breed") and record.get("patient_age"):
                continue

            portal_id = record.get("portal_id")
            if portal_id:
                to_fetch.append((rid, portal_id))

        if not to_fetch:
            return

        try:
            token = self._login()
        except Exception as e:
            print(f"  [BitLab metadata] login failed: {e}")
            return

        for rid, portal_id in to_fetch:
            try:
                raw_pdf = self.buscar_requisicao_pdf(token, portal_id)
                metadata = self.parse_requisicao_metadata(raw_pdf)
                if metadata:
                    atual[rid].update({k: v for k, v in metadata.items() if v})
                    print(
                        f"  [BitLab metadata] {rid} -> "
                        f"species={atual[rid].get('species_sex') or '-'} "
                        f"breed={atual[rid].get('breed') or '-'}"
                    )
            except Exception as e:
                print(f"  [BitLab metadata] {rid}: {e}")
            time.sleep(0.05)

    def snapshot(self) -> dict[str, dict]:
        token = self._login()
        resultado = {}

        for req in self._buscar_requisicoes(token):
            itens_raw = self._buscar_itens(token, req["cdRequisicao"])
            itens = {
                e["cdExame"]: {
                    "nome":     e["deExame"],
                    "status":   e["deStatusWeb"],
                    "dtColeta": e.get("dtColeta", ""),
                    "released_at_hint": e.get("dtEntrega", ""),
                    "item_id":  e.get("id", ""),
                }
                for e in itens_raw
            }
            resultado[req["requisicao"]] = {
                "label":     req["nmPaciente"],
                "data":      req["dtRequisicao"][:10],
                "received_at": req.get("dtRequisicao", "") or req["dtRequisicao"][:10],
                "portal_id": req["id"],
                "itens":     itens,
            }
            time.sleep(0.2)

        return resultado
