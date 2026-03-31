"""
Lógica central de monitoramento.
Pode rodar standalone (monitor.py) ou embutido na web (web/app.py).
"""

import time
from datetime import datetime
from labs import CONNECTORS
from notifiers import NOTIFIERS
from web.state import normalize_status


def detectar_novidades(lab_name: str, anterior: dict, atual: dict) -> list[str]:
    msgs = []
    for rid, rec in atual.items():
        if rid not in anterior:
            nomes = ", ".join(i["nome"] for i in rec["itens"].values())
            msgs.append(
                f"🆕 <b>Nova entrada — {lab_name}</b>\n"
                f"👤 {rec['label']}\n"
                f"📋 {rid} | {rec['data']}\n"
                f"🔬 {nomes}"
            )
        else:
            for iid, item in rec["itens"].items():
                s_new = normalize_status(item["status"])
                s_old = normalize_status(anterior[rid]["itens"].get(iid, {}).get("status", ""))
                if s_old and s_new != s_old:
                    msgs.append(
                        f"✅ <b>Resultado disponível — {lab_name}</b>\n"
                        f"👤 {rec['label']}\n"
                        f"🔬 {item['nome']}\n"
                        f"📊 {s_old} → {s_new}"
                    )
    return msgs


def run_monitor_loop(state=None):
    """
    Loop principal de monitoramento.
    Se `state` for fornecido (AppState), atualiza o estado da interface web.
    Se não, roda standalone sem persistência em memória.
    """
    print(f"[{datetime.now():%H:%M:%S}] Monitor iniciado")

    while True:
        config = state.config if state else _load_config_file()
        interval = config.get("interval_minutes", 5) * 60

        labs = [
            CONNECTORS[l["connector"]]()
            for l in config["labs"]
            if l.get("enabled") and l["connector"] in CONNECTORS
        ]
        notifiers = [
            NOTIFIERS[n["type"]]()
            for n in config["notifiers"]
            if n.get("enabled") and n["type"] in NOTIFIERS
        ]

        for lab in labs:
            if state:
                state.is_checking[lab.lab_id] = True
            try:
                print(f"[{datetime.now():%H:%M:%S}] Verificando {lab.lab_name}...")
                atual    = lab.snapshot()
                anterior = state.snapshots.get(lab.lab_id, {}) if state else {}

                if not anterior:
                    print(f"  Primeira execução — estado salvo.")
                else:
                    novidades = detectar_novidades(lab.lab_name, anterior, atual)
                    if novidades:
                        for msg in novidades:
                            print(f"  -> {msg[:80]}")
                            if state:
                                state.add_notification(lab.lab_name, msg)
                        # Um único envio por lab por ciclo — evita spam de notificações
                        batch_msg = "\n\n".join(novidades)
                        for n in notifiers:
                            n.enviar(batch_msg)

                if state:
                    state.snapshots[lab.lab_id]  = atual
                    state.last_check[lab.lab_id] = datetime.now().strftime("%H:%M:%S")
                    state.last_error.pop(lab.lab_id, None)

                print(f"  {lab.lab_name}: {len(atual)} registros")

            except Exception as e:
                print(f"  {lab.lab_name}: erro — {e}")
                if state:
                    state.last_error[lab.lab_id] = str(e)
            finally:
                if state:
                    state.is_checking[lab.lab_id] = False

        time.sleep(interval)


def _load_config_file() -> dict:
    from pathlib import Path
    import json
    return json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
