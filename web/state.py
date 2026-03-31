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
    "arquivo morto":      "Arquivado",
    "arquivado":          "Arquivado",
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


# Exames a excluir (ruído operacional dos labs)
EXCLUDE_EXAMES: set[str] = {
    "OBS BIOQUIMICA",
    "OBS BIOQUÍMICA",
}

# Statuses considered "done" — no dias_em_aberto tracking
_STATUS_DONE: set[str] = {"Pronto", "Arquivado", "Cancelado"}

# Statuses considered "fully ready" for group completion
_STATUS_PRONTO: set[str] = {"Pronto"}

# Ordered priority for overall group status (when no items are Pronto)
_STATUS_PRIORITY: list[str] = [
    "Analisando", "Em Andamento", "Recebido", "Arquivado", "Cancelado"
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
        Each group: lab, record_id, paciente, data, status_geral, itens, liberado_em, portal_url.
        status_geral: Pronto | Parcial | Em Andamento | Analisando | Recebido | Arquivado | Cancelado
        dias_em_aberto: None for done statuses (Pronto, Arquivado, Cancelado).
        Search: multi-word, accent-insensitive, case-insensitive, sequential.
        Sorted by date descending.
        """
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
                        "nome":       item["nome"],
                        "status":     normalize_status(item["status"]),
                        "liberado_em": item.get("liberado_em"),
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

                if not _search_match(q, paciente):
                    continue

                portal_id  = record.get("portal_id", "")
                pattern    = PORTAL_URL_PATTERN.get(lab_id, "")
                portal_url = (
                    pattern.format(portal_id=portal_id)
                    if portal_id and pattern
                    else PORTAL_URLS.get(lab_id, "")
                )

                # Strip liberado_em from itens before storing (it's on the group already)
                itens_clean = [{"nome": i["nome"], "status": i["status"]} for i in itens]

                groups.append({
                    "lab_id":         lab_id,
                    "lab":            lab_name,
                    "record_id":      record_id,
                    "paciente":       paciente,
                    "data":           data_fmt,
                    "data_raw":       record["data"],
                    "status_geral":   status_geral,
                    "dias_em_aberto": dias_em_aberto,
                    "liberado_em":    liberado_em,
                    "itens":          sorted(itens_clean, key=lambda x: x["nome"]),
                    "portal_url":     portal_url,
                    "portal_id":      record_id,  # requisition number for display
                })

        return sorted(groups, key=lambda x: x["data_raw"], reverse=True)

    def get_lab_counts(self) -> dict:
        """
        Returns counts per lab measured by GROUPS (protocols), not individual items.
        status_geral per group: Pronto | Parcial | Em Andamento | Analisando | Recebido | Arquivado | Cancelado
        """
        result = {}
        for lab_cfg in self.config["labs"]:
            lid  = lab_cfg["id"]
            snap = self.snapshots.get(lid, {})

            pronto = parcial = andamento = arquivado = total = 0

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
                elif any(s in {"Arquivado", "Cancelado"} for s in itens):
                    arquivado += 1
                else:
                    andamento += 1

            result[lid] = {
                "name":      lab_cfg["name"],
                "enabled":   lab_cfg.get("enabled", True),
                "pronto":    pronto,
                "parcial":   parcial,
                "andamento": andamento,
                "arquivado": arquivado,
                "total":     total,
                "last_check": self.last_check.get(lid, "—"),
                "error":      self.last_error.get(lid, ""),
                "checking":   self.is_checking.get(lid, False),
            }
        return result


state = AppState()
