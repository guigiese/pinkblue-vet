"""
Monitor de exames - Multi-lab, Multi-canal
Carrega configuração de config.json e monitora todos os labs habilitados.
"""

import json
import time
from pathlib import Path
from datetime import datetime

from labs import CONNECTORS
from notifiers import NOTIFIERS

CONFIG_FILE = Path(__file__).parent / "config.json"
STATE_DIR   = Path("/tmp")


def carregar_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def estado_path(lab_id: str) -> Path:
    return STATE_DIR / f"estado_{lab_id}.json"


def carregar_estado(lab_id: str) -> dict:
    p = estado_path(lab_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("snapshot", {})
    return {}


def salvar_estado(lab_id: str, snapshot: dict):
    estado_path(lab_id).write_text(
        json.dumps({"snapshot": snapshot, "atualizado_em": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def detectar_novidades(lab_name: str, anterior: dict, atual: dict) -> list[str]:
    msgs = []

    for record_id, record in atual.items():
        if record_id not in anterior:
            nomes = ", ".join(i["nome"] for i in record["itens"].values())
            msgs.append(
                f"🆕 <b>Nova entrada — {lab_name}</b>\n"
                f"👤 {record['label']}\n"
                f"📋 {record_id} | {record['data']}\n"
                f"🔬 {nomes}"
            )
        else:
            itens_ant = anterior[record_id].get("itens", {})
            for item_id, item in record["itens"].items():
                status_novo = item["status"]
                status_ant  = itens_ant.get(item_id, {}).get("status", "")
                if status_ant and status_novo != status_ant:
                    msgs.append(
                        f"✅ <b>Resultado disponível — {lab_name}</b>\n"
                        f"👤 {record['label']}\n"
                        f"🔬 {item['nome']}\n"
                        f"📊 {status_ant} → {status_novo}"
                    )

    return msgs


def monitorar():
    config = carregar_config()
    intervalo = config.get("interval_minutes", 5) * 60

    # Instancia labs e notifiers habilitados
    labs = [
        CONNECTORS[lab["connector"]]()
        for lab in config["labs"]
        if lab.get("enabled") and lab["connector"] in CONNECTORS
    ]
    notifiers = [
        NOTIFIERS[n["type"]]()
        for n in config["notifiers"]
        if n.get("enabled") and n["type"] in NOTIFIERS
    ]

    lab_names = ", ".join(l.lab_name for l in labs)
    notif_names = ", ".join(type(n).__name__ for n in notifiers)
    print(f"[{datetime.now():%H:%M:%S}] Monitor iniciado | Labs: {lab_names} | Notifiers: {notif_names}")

    while True:
        for lab in labs:
            try:
                print(f"[{datetime.now():%H:%M:%S}] Verificando {lab.lab_name}...")
                atual    = lab.snapshot()
                anterior = carregar_estado(lab.lab_id)

                if not anterior:
                    print(f"  Primeira execução — estado salvo.")
                else:
                    novidades = detectar_novidades(lab.lab_name, anterior, atual)
                    if novidades:
                        for msg in novidades:
                            print(f"  -> {msg[:100]}")
                            for notifier in notifiers:
                                notifier.enviar(msg)
                    else:
                        print(f"  Sem novidades.")

                salvar_estado(lab.lab_id, atual)

            except Exception as e:
                print(f"[{datetime.now():%H:%M:%S}] Erro em {lab.lab_name}: {e}")

        time.sleep(intervalo)


if __name__ == "__main__":
    monitorar()
