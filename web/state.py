import json
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

PORTAL_URLS: dict[str, str] = {
    "bitlab": "https://bitlabenterprise.com.br/bioanalises/resultados",
    "nexio":  "https://www.pathoweb.com.br",
}

# ── Status normalization ──────────────────────────────────────────────────────
# Maps raw lab status strings → standardized display values.
# Add new mappings here as new status strings are discovered.
STATUS_MAP: dict[str, str] = {
    # Already standard
    "Pronto":          "Pronto",
    "Em Andamento":    "Em Andamento",
    "Recebido":        "Recebido",
    "Analisando":      "Analisando",
    "Arquivo morto": "Arquivado",
    "Arquivado":     "Arquivado",
    "Cancelado":       "Cancelado",
    # Variations / lab-specific aliases
    "Entrega":         "Pronto",
    "Entregue":        "Pronto",
    "Liberado":        "Pronto",
    "Resultado Liberado": "Pronto",
    "resultado liberado": "Pronto",
    "Disponível":      "Pronto",
    "Concluído":       "Pronto",
    "em andamento":    "Em Andamento",
    "Em Análise":      "Analisando",
    "em análise":      "Analisando",
    "Análise":         "Analisando",
    "Em analise":      "Analisando",
    "Aguardando":      "Recebido",
    "Aguardando análise": "Recebido",
    "Coletado":        "Recebido",
}

# Exames a excluir (ruído operacional dos labs)
EXCLUDE_EXAMES: set[str] = {
    "OBS BIOQUIMICA",
    "OBS BIOQUÍMICA",
}

# Statuses considered "done" for group status computation
_STATUS_PRONTO: set[str] = {"Pronto"}

# Ordered priority for overall group status (when no items are done)
_STATUS_PRIORITY: list[str] = [
    "Analisando", "Em Andamento", "Recebido", "Arquivado", "Cancelado"
]


def normalize_status(raw: str) -> str:
    """Map raw lab status to standardized value. Unknown values pass through."""
    return STATUS_MAP.get(raw, raw)


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
        # Keep only notifications from the last 3 days
        cutoff = datetime.now() - timedelta(days=3)
        self.notifications = [n for n in self.notifications if n["datetime"] >= cutoff]

    def get_exames(self, lab_filter: str = "", status_filter: str = "", q: str = "") -> list[dict]:
        """
        Returns exames grouped by record_id (one entry per request/patient).
        Each group has: lab, record_id, paciente, data (dd/mm/aaaa), status_geral, itens.
        status_geral: Pronto | Parcial | Em Andamento | Analisando | Recebido | ...
        Excludes items in EXCLUDE_EXAMES. Normalizes statuses via STATUS_MAP.
        Sorted by date descending.
        """
        groups = []
        for lab_id, snapshot in self.snapshots.items():
            lab_cfg = next((l for l in self.config["labs"] if l["id"] == lab_id), {})
            lab_name = lab_cfg.get("name", lab_id)
            if lab_filter and lab_id != lab_filter:
                continue

            for record_id, record in snapshot.items():
                # Build filtered + normalized item list
                itens = []
                for item in record["itens"].values():
                    if item["nome"] in EXCLUDE_EXAMES:
                        continue
                    itens.append({
                        "nome":   item["nome"],
                        "status": normalize_status(item["status"]),
                    })

                if not itens:
                    continue

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

                # Format date for display + compute days in progress
                try:
                    data_dt  = datetime.strptime(record["data"], "%Y-%m-%d")
                    data_fmt = data_dt.strftime("%d/%m/%Y")
                    dias_em_aberto = (datetime.now() - data_dt).days if status_geral != "Pronto" else None
                except Exception:
                    data_fmt       = record["data"]
                    dias_em_aberto = None

                paciente = record["label"]

                # Name search filter (case-insensitive, strips accents-agnostic)
                if q and q.lower() not in paciente.lower():
                    continue

                groups.append({
                    "lab_id":         lab_id,
                    "lab":            lab_name,
                    "record_id":      record_id,
                    "paciente":       paciente,
                    "data":           data_fmt,
                    "data_raw":       record["data"],
                    "status_geral":   status_geral,
                    "dias_em_aberto": dias_em_aberto,
                    "itens":          sorted(itens, key=lambda x: x["nome"]),
                    "portal_url":     PORTAL_URLS.get(lab_id, ""),
                })

        return sorted(groups, key=lambda x: x["data_raw"], reverse=True)

    def get_lab_counts(self) -> dict:
        result = {}
        for lab_cfg in self.config["labs"]:
            lid  = lab_cfg["id"]
            snap = self.snapshots.get(lid, {})
            itens = [
                item
                for rec in snap.values()
                for item in rec["itens"].values()
                if item["nome"] not in EXCLUDE_EXAMES
            ]
            normalized = [normalize_status(i["status"]) for i in itens]
            result[lid] = {
                "name":       lab_cfg["name"],
                "enabled":    lab_cfg.get("enabled", True),
                "pronto":     sum(1 for s in normalized if s in _STATUS_PRONTO),
                "andamento":  sum(1 for s in normalized if s in {"Em Andamento", "Analisando", "Recebido"}),
                "total":      len(normalized),
                "last_check": self.last_check.get(lid, "—"),
                "error":      self.last_error.get(lid, ""),
                "checking":   self.is_checking.get(lid, False),
            }
        return result


state = AppState()
