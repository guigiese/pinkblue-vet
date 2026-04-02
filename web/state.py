import json
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

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
    return patient.strip(), tutor.strip()


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
                    })

                if not itens:
                    continue

                # Liberation timestamp: first item with liberado_em that is Pronto
                liberado_em_raw = next(
                    (
                        i["liberado_em"]
                        for i in itens
                        if i.get("liberado_em") and i["status"] in _STATUS_PRONTO
                    ),
                    None,
                )
                try:
                    liberado_em = (
                        datetime.fromisoformat(liberado_em_raw).strftime("%d/%m %H:%M")
                        if liberado_em_raw else None
                    )
                except Exception:
                    liberado_em = None

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

                # Date formatting + dias_em_aberto (None for done statuses)
                try:
                    data_dt  = datetime.strptime(record["data"], "%Y-%m-%d")
                    data_fmt = data_dt.strftime("%d/%m/%Y")
                    dias_em_aberto = (
                        (datetime.now() - data_dt).days
                        if status_geral not in _STATUS_DONE else None
                    )
                except Exception:
                    data_fmt       = record["data"]
                    dias_em_aberto = None

                paciente = record["label"]
                patient_name, tutor_name = _split_patient_label(paciente)

                if not _search_match(q, paciente):
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
                    }
                    for i in itens
                ]

                species_sex = (
                    record.get("species_sex")
                    or record.get("especie_sexo")
                    or record.get("speciesSex")
                )
                days_label, days_stale = _build_days_payload(dias_em_aberto)
                time_display = _format_time(liberado_em_raw)
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
                    "data":            data_fmt,
                    "data_raw":        record["data"],
                    "date_display":    _format_date(record["data"]),
                    "time_display":    time_display,
                    "status_geral":    status_geral,
                    "dias_em_aberto":  dias_em_aberto,
                    "days_label":      days_label,
                    "days_stale":      days_stale,
                    "liberado_em":     liberado_em,
                    "liberado_em_iso": liberado_em_raw,
                    "itens":           sorted(itens_clean, key=lambda x: x["nome"]),
                    "items_view":      sorted(itens_view, key=lambda x: x["name"]),
                    "items_total":     len(itens_clean),
                    "ready_ratio_text": ready_ratio_text,
                    "portal_url":      portal_url,
                    "portal_id":       record_id,
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
        for lab_cfg in self.config["labs"]:
            lid  = lab_cfg["id"]
            snap = self.snapshots.get(lid, {})

            pronto = parcial = andamento = total = 0

            for record in snap.values():
                itens = [
                    normalize_status(item["status"])
                    for item in record["itens"].values()
                    if item["nome"] not in EXCLUDE_EXAMES
                ]
                if not itens:
                    continue
                total += 1
                n_p = sum(1 for s in itens if s in _STATUS_PRONTO)
                if n_p == len(itens):
                    pronto += 1
                elif n_p > 0:
                    parcial += 1
                else:
                    andamento += 1

            result[lid] = {
                "name":      lab_cfg["name"],
                "enabled":   lab_cfg.get("enabled", True),
                "pronto":    pronto,
                "parcial":   parcial,
                "andamento": andamento,
                "total":     total,
                "last_check": self.last_check.get(lid, "—"),
                "error":      self.last_error.get(lid, ""),
                "checking":   self.is_checking.get(lid, False),
            }
        return result


state = AppState()
