import json
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from notification_settings import (
    DEFAULT_NOTIFICATION_SETTINGS,
    apply_notification_settings,
    build_notification_preview_context,
    render_notification_template,
)

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

STATUS_SHORT_LABELS: dict[str, str] = {
    "Pronto": "PRONTO",
    "Parcial": "PARCIAL",
    "Em Andamento": "EM CURSO",
    "Analisando": "ANALISE",
    "Recebido": "RECEBIDO",
    "Cancelado": "CANCELADO",
}

# Fallback portal URLs (when no portal_id is available)
PORTAL_URLS: dict[str, str] = {
    "bitlab": "https://bitlabenterprise.com.br/bioanalises/resultados",
    "nexio":  "https://www.pathoweb.com.br",
}

# Deep link patterns per lab — {portal_id} placeholder
# BitLab: SPA route /laudos/{id} — requires active browser session (JWT in localStorage)
# Nexio: visualizarLaudoAjax — requires active session cookie
PORTAL_URL_PATTERN: dict[str, str] = {
    "bitlab": "https://bitlabenterprise.com.br/bioanalises/laudos/{portal_id}",
    "nexio":  "https://www.pathoweb.com.br/moduloProcedencia/visualizarLaudoAjax?id={portal_id}",
}

# ── Status normalization ──────────────────────────────────────────────────────
# Maps raw lab status strings → standardized display values.
# Lookup is case-insensitive (keys stored lowercase below via _STATUS_MAP_LOWER).
STATUS_MAP: dict[str, str] = {
    # Standard
    "pronto":             "Pronto",
    "em andamento":       "Em Andamento",
    "recebido":           "Recebido",
    "analisando":         "Analisando",
    "cancelado":          "Cancelado",
    # Aliases
    "entrega":            "Pronto",
    "entregue":           "Pronto",
    "liberado":           "Pronto",
    "resultado liberado": "Pronto",
    "disponível":         "Pronto",
    "disponivel":         "Pronto",
    "concluído":          "Pronto",
    "concluido":          "Pronto",
    "arquivo morto":      "Pronto",
    "arquivado":          "Pronto",
    "em análise":         "Analisando",
    "em analise":         "Analisando",
    "análise":            "Analisando",
    "analise":            "Analisando",
    "aguardando":         "Recebido",
    "aguardando análise": "Recebido",
    "aguardando analise": "Recebido",
    "coletado":           "Recebido",
}


def normalize_status(raw: str) -> str:
    """Map raw lab status to standardized value. Case-insensitive. Unknown values pass through."""
    return STATUS_MAP.get(raw.strip().lower(), raw)


def _strip_accents(text: str) -> str:
    """Remove diacritics from text for accent-insensitive comparison."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _search_match(q: str, text: str) -> bool:
    """
    Multi-word sequential search:
    - Case-insensitive
    - Accent-insensitive
    - Each word must appear in the text in order (with any chars between them)
    - Words are split by whitespace in the query
    """
    if not q:
        return True
    q_norm   = _strip_accents(q.lower())
    txt_norm = _strip_accents(text.lower())
    words = q_norm.split()
    pos = 0
    for word in words:
        idx = txt_norm.find(word, pos)
        if idx == -1:
            return False
        pos = idx + len(word)
    return True


def _split_patient_label(label: str) -> tuple[str, str]:
    """
    Best-effort split of the existing label into patient and tutor.
    Current labels usually follow: "Paciente - Tutor".
    """
    if " - " not in label:
        return label.strip(), ""
    patient, tutor = label.split(" - ", 1)
    tutor = tutor.strip()
    tutor_upper = tutor.upper()
    if "PROP:" in tutor_upper:
        tutor = tutor[tutor_upper.rfind("PROP:") + len("PROP:"):].strip()
    return patient.strip(), tutor


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
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw).strftime("%H:%M")
    except Exception:
        return ""


def _format_release_display(raw: str | None) -> str | None:
    dt = _parse_datetime(raw)
    if not dt:
        return None
    if "T" not in (raw or "") and " " not in (raw or ""):
        return dt.strftime("%d/%m/%Y")
    return dt.strftime("%d/%m %H:%M")


def _parse_datetime(raw: str | None) -> datetime | None:
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


def _format_patient_age(raw: str | None) -> str:
    text = " ".join((raw or "").strip().split())
    if not text:
        return "n/d"
    norm = _strip_accents(text.lower())
    if norm in {"n/e", "ne", "n/d", "nd", "nao informado", "nao especificado"}:
        return "n/d"
    return text.lower()


def _iso_sort_key(raw: str | None) -> str:
    dt = _parse_datetime(raw)
    return dt.isoformat() if dt else (raw or "")


def status_card_title(status: str) -> str:
    label = STATUS_SHORT_LABELS.get(status, status.upper())
    return label.capitalize()


def _build_days_payload(days_open: int | None) -> tuple[str | None, bool]:
    if days_open is None:
        return None, False
    return f"{days_open}d em aberto", days_open > 7


# Exames a excluir (ruído operacional dos labs)
EXCLUDE_EXAMES: set[str] = {
    "OBS BIOQUIMICA",
    "OBS BIOQUÍMICA",
}

# Statuses considered "done" — no dias_em_aberto tracking
_STATUS_DONE: set[str] = {"Pronto", "Cancelado"}

# Statuses considered "fully ready" for group completion
_STATUS_PRONTO: set[str] = {"Pronto"}

# Ordered priority for overall group status (when no items are Pronto)
_STATUS_PRIORITY: list[str] = [
    "Analisando", "Em Andamento", "Recebido", "Cancelado"
]


class AppState:
    def __init__(self):
        self.snapshots:   dict[str, dict] = {}
        self.last_check:  dict[str, str]  = {}
        self.last_error:  dict[str, str]  = {}
        self.is_checking: dict[str, bool] = {}
        self.notifications: list[dict]    = []
        self._config: dict | None         = None

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            apply_notification_settings(self._config)
        return self._config

    def save_config(self):
        CONFIG_FILE.write_text(
            json.dumps(self._config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def toggle_lab(self, lab_id: str):
        for lab in self.config["labs"]:
            if lab["id"] == lab_id:
                lab["enabled"] = not lab.get("enabled", True)
                break
        self.save_config()

    def toggle_notifier(self, notifier_id: str):
        for n in self.config["notifiers"]:
            if n["id"] == notifier_id:
                n["enabled"] = not n.get("enabled", True)
                break
        self.save_config()

    def set_interval(self, minutes: int):
        self.config["interval_minutes"] = minutes
        self.save_config()

    def get_notification_settings(self) -> dict:
        return apply_notification_settings(self.config)

    def update_notification_settings(
        self,
        *,
        received_enabled: bool,
        completed_enabled: bool,
        received_template: str,
        completed_template: str,
    ) -> None:
        settings = self.get_notification_settings()
        settings["events"]["received"]["enabled"] = received_enabled
        settings["events"]["completed"]["enabled"] = completed_enabled
        settings["events"]["received"]["template"] = (
            received_template.strip()
            or DEFAULT_NOTIFICATION_SETTINGS["events"]["received"]["template"]
        )
        settings["events"]["completed"]["template"] = (
            completed_template.strip()
            or DEFAULT_NOTIFICATION_SETTINGS["events"]["completed"]["template"]
        )
        self.save_config()

    def reset_notification_settings(self) -> None:
        self.config["notification_settings"] = json.loads(
            json.dumps(DEFAULT_NOTIFICATION_SETTINGS, ensure_ascii=False)
        )
        self.save_config()

    def get_notification_previews(self) -> dict[str, str]:
        settings = self.get_notification_settings()
        context = build_notification_preview_context()
        return {
            event_key: render_notification_template(event_cfg["template"], context)
            for event_key, event_cfg in settings["events"].items()
        }

    def add_notification(self, lab_name: str, msg: str):
        now = datetime.now()
        self.notifications.insert(0, {
            "datetime": now,
            "time":     now.strftime("%d/%m %H:%M"),
            "lab":      lab_name,
            "msg":      msg,
        })
        cutoff = datetime.now() - timedelta(days=3)
        self.notifications = [n for n in self.notifications if n["datetime"] >= cutoff]

    def get_exames(self, lab_filter: str = "", status_filter: str = "", q: str = "") -> list[dict]:
        """
        Returns exames grouped by record_id (one entry per request/patient).
        Each group: lab, record_id, paciente, data, status_geral, itens, liberado_em, portal_url,
                    alerta_geral (None | "yellow" | "red").
        Sorted by date descending.
        """
        _alert_rank = {None: 0, "yellow": 1, "red": 2}
        groups = []
        for lab_id, snapshot in self.snapshots.items():
            lab_cfg  = next((l for l in self.config["labs"] if l["id"] == lab_id), {})
            lab_name = lab_cfg.get("name", lab_id)
            if lab_filter and lab_id != lab_filter:
                continue

            for record_id, record in snapshot.items():
                itens = []
                for item in record["itens"].values():
                    if item["nome"] in EXCLUDE_EXAMES:
                        continue
                    itens.append({
                        "nome":        item["nome"],
                        "status":      normalize_status(item["status"]),
                        "liberado_em": item.get("liberado_em"),
                        "item_id":     item.get("item_id"),
                        "alerta":      item.get("alerta"),
                        "resultado":   item.get("resultado") or [],
                        "report_text": item.get("report_text") or item.get("resultado_texto") or "",
                        "diagnosis_text": item.get("diagnosis_text") or "",
                    })

                if not itens:
                    continue

                release_candidates = [
                    i["liberado_em"]
                    for i in itens
                    if i.get("liberado_em") and i["status"] in _STATUS_PRONTO
                ]
                liberado_em_raw = None
                if release_candidates:
                    liberado_em_raw = max(
                        release_candidates,
                        key=lambda raw: _parse_datetime(raw) or datetime.min,
                    )
                liberado_em = _format_release_display(liberado_em_raw)

                # Compute group overall status
                n_pronto = sum(1 for i in itens if i["status"] in _STATUS_PRONTO)
                if n_pronto == len(itens):
                    status_geral = "Pronto"
                elif n_pronto > 0:
                    status_geral = "Parcial"
                else:
                    statuses_presentes = {i["status"] for i in itens}
                    status_geral = next(
                        (s for s in _STATUS_PRIORITY if s in statuses_presentes),
                        itens[0]["status"]
                    )

                if status_filter and status_geral != status_filter:
                    continue

                received_at_raw = record.get("received_at") or record.get("collected_at") or record["data"]
                received_at_dt = _parse_datetime(received_at_raw) or _parse_datetime(record["data"])

                # Date formatting + dias_em_aberto (None for done statuses)
                if received_at_dt:
                    data_fmt = received_at_dt.strftime("%d/%m/%Y")
                    dias_em_aberto = (
                        (datetime.now() - received_at_dt).days
                        if status_geral not in _STATUS_DONE else None
                    )
                else:
                    data_fmt = record["data"]
                    dias_em_aberto = None

                paciente = record["label"]
                patient_name, tutor_name = _split_patient_label(paciente)
                breed = record.get("breed") or record.get("raca") or ""
                species_sex = (
                    record.get("species_sex")
                    or record.get("especie_sexo")
                    or record.get("speciesSex")
                )
                patient_age = record.get("patient_age") or record.get("idade") or ""
                patient_age_display = _format_patient_age(patient_age)

                search_blob = " ".join(
                    part for part in [paciente, patient_name, tutor_name, species_sex, breed, patient_age_display] if part
                )
                if not _search_match(q, search_blob):
                    continue

                portal_id  = record.get("portal_id", "")
                pattern    = PORTAL_URL_PATTERN.get(lab_id, "")
                portal_url = (
                    pattern.format(portal_id=portal_id)
                    if portal_id and pattern
                    else PORTAL_URLS.get(lab_id, "")
                )

                # Worst alert across all Pronto items
                alerta_geral = max(
                    (i["alerta"] for i in itens if i["alerta"] in _alert_rank),
                    key=lambda a: _alert_rank[a],
                    default=None,
                )

                itens_clean = [
                    {
                        "nome":    i["nome"],
                        "status":  i["status"],
                        "item_id": i["item_id"],
                        "alerta":  i["alerta"],
                        "resultado": i["resultado"],
                        "report_text": i.get("report_text") or i.get("resultado_texto") or "",
                        "diagnosis_text": i.get("diagnosis_text") or "",
                    }
                    for i in itens
                ]

                days_label, days_stale = _build_days_payload(dias_em_aberto)
                time_display = _format_time(received_at_raw)
                ready_ratio_text = f"{n_pronto}/{len(itens_clean)} prontos"
                itens_view = [
                    {
                        "id": item["item_id"] or f"{record_id}-{idx}",
                        "name": item["nome"],
                        "status": item["status"],
                        "alert": item["alerta"],
                        "item_id": item["item_id"],
                        "release_at": liberado_em_raw if item["status"] in _STATUS_PRONTO else None,
                        "release_at_display": liberado_em if item["status"] in _STATUS_PRONTO else None,
                        "results": item["resultado"],
                        "report_text": item.get("report_text") or item.get("resultado_texto") or "",
                        "diagnosis_text": item.get("diagnosis_text") or "",
                    }
                    for idx, item in enumerate(itens_clean, start=1)
                ]

                groups.append({
                    "lab_id":          lab_id,
                    "lab":             lab_name,
                    "record_id":       record_id,
                    "paciente":        paciente,
                    "patient_name":    patient_name,
                    "tutor_name":      tutor_name,
                    "species_sex":     species_sex,
                    "breed":           breed,
                    "patient_age":     patient_age,
                    "patient_age_display": patient_age_display,
                    "data":            data_fmt,
                    "data_raw":        _iso_sort_key(received_at_raw) or record["data"],
                    "date_display":    _format_date(received_at_raw or record["data"]),
                    "time_display":    time_display,
                    "status_geral":    status_geral,
                    "dias_em_aberto":  dias_em_aberto,
                    "days_label":      days_label,
                    "days_stale":      days_stale,
                    "liberado_em":     liberado_em,
                    "liberado_em_iso": liberado_em_raw,
                    "last_release_display": liberado_em,
                    "last_release_iso": liberado_em_raw,
                    "last_release_date_display": _format_date(liberado_em_raw),
                    "last_release_time_display": _format_time(liberado_em_raw),
                    "itens":           sorted(itens_clean, key=lambda x: x["nome"]),
                    "items_view":      sorted(itens_view, key=lambda x: x["name"]),
                    "items_total":     len(itens_clean),
                    "items_ready":     n_pronto,
                    "ready_ratio_text": ready_ratio_text,
                    "portal_url":      portal_url,
                    "portal_id":       portal_id,
                    "alerta_geral":    alerta_geral,
                    "criticality":     alerta_geral,
                    "protocol":        record_id,
                })

        return sorted(groups, key=lambda x: x["data_raw"], reverse=True)

    def get_ultimos_liberados(self, n: int = 12) -> list[dict]:
        """Returns the n most recently liberated (Pronto/Parcial) exam groups."""
        groups = [
            g for g in self.get_exames()
            if g["status_geral"] in {"Pronto", "Parcial"}
        ]
        groups.sort(
            key=lambda g: g["liberado_em_iso"] or g["data_raw"],
            reverse=True,
        )
        return groups[:n]

    def get_lab_counts(self) -> dict:
        """
        Returns counts per lab measured by GROUPS (protocols), not individual items.
        status_geral per group: Pronto | Parcial | Em Andamento | Analisando | Recebido | Arquivado | Cancelado
        """
        result = {}
        now = datetime.now()
        recent_cutoff = now - timedelta(hours=24)
        for lab_cfg in self.config["labs"]:
            lid  = lab_cfg["id"]
            snap = self.snapshots.get(lid, {})

            pronto = parcial = andamento = total = 0
            pending = overdue = released_last_24h = 0
            oldest_pending_days = 0

            for record in snap.values():
                itens = [
                    {
                        "status": normalize_status(item["status"]),
                        "liberado_em": item.get("liberado_em"),
                    }
                    for item in record["itens"].values()
                    if item["nome"] not in EXCLUDE_EXAMES
                ]
                if not itens:
                    continue
                total += 1
                n_p = sum(1 for item in itens if item["status"] in _STATUS_PRONTO)
                if n_p == len(itens):
                    pronto += 1
                elif n_p > 0:
                    parcial += 1
                    pending += 1
                else:
                    andamento += 1
                    pending += 1

                received_at_raw = record.get("received_at") or record.get("collected_at") or record.get("data")
                received_at_dt = _parse_datetime(received_at_raw)
                if received_at_dt and n_p != len(itens):
                    days_open = (now - received_at_dt).days
                    oldest_pending_days = max(oldest_pending_days, days_open)
                    if days_open > 7:
                        overdue += 1

                ready_releases = [
                    _parse_datetime(item["liberado_em"])
                    for item in itens
                    if item["status"] in _STATUS_PRONTO and item.get("liberado_em")
                ]
                ready_releases = [dt for dt in ready_releases if dt]
                if ready_releases and max(ready_releases) >= recent_cutoff:
                    released_last_24h += 1

            result[lid] = {
                "name":      lab_cfg["name"],
                "enabled":   lab_cfg.get("enabled", True),
                "pronto":    pronto,
                "parcial":   parcial,
                "andamento": andamento,
                "total":     total,
                "pending":   pending,
                "overdue":   overdue,
                "oldest_pending_days": oldest_pending_days,
                "released_last_24h": released_last_24h,
                "last_check": self.last_check.get(lid, "—"),
                "error":      self.last_error.get(lid, ""),
                "checking":   self.is_checking.get(lid, False),
            }
        return result


state = AppState()
