"""
Monitor de exames - BitLab Enterprise (Telegram)
Versão paralela para testes — notifica via Telegram.
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

# ============================================================
# CONFIGURAÇÃO
# ============================================================
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN",  "8704375512:AAFs8ICnxKAphbFscOK9NKNbpzWwyYTB4tA")
TELEGRAM_CHATID = os.environ.get("TELEGRAM_CHATID", "8658992577")

API_BASE    = "https://bitlabenterprise.com.br/bioanalises/api/v1"
USUARIO     = os.environ.get("BITLAB_USUARIO",  "11702")
SENHA       = os.environ.get("BITLAB_SENHA",    "melanie")
CD_CONVENIO = int(os.environ.get("CD_CONVENIO", "1170"))
CD_POSTO    = int(os.environ.get("CD_POSTO",    "8"))

INTERVALO_MINUTOS = int(os.environ.get("INTERVALO_MINUTOS", "5"))
DIAS_ATRAS        = int(os.environ.get("DIAS_ATRAS",        "30"))

ESTADO_ARQUIVO = Path("/tmp/estado_exames_telegram.json")
# ============================================================


def login() -> str:
    r = requests.post(f"{API_BASE}/SignIn", json={"userName": USUARIO, "password": SENHA}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def buscar_requisicoes(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    hoje   = datetime.now().strftime("%Y-%m-%d")
    inicio = (datetime.now() - timedelta(days=DIAS_ATRAS)).strftime("%Y-%m-%d")
    r = requests.post(
        f"{API_BASE}/Requisicao?pageNumber=1&pageSize=100",
        headers=headers,
        json={"dataInicial": inicio, "dataFinal": hoje},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("data", r.json())


def buscar_exames(token: str, cd_requisicao: int) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{API_BASE}/ItemRequisicao",
        headers=headers,
        json={"cdPosto": CD_POSTO, "cdRequisicao": cd_requisicao, "cdConvenio": CD_CONVENIO},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def montar_snapshot(token: str) -> dict:
    requisicoes = buscar_requisicoes(token)
    snapshot = {}
    for req in requisicoes:
        num        = req["requisicao"]
        exames_raw = buscar_exames(token, req["cdRequisicao"])
        exames     = {e["cdExame"]: {"status": e["deStatusWeb"], "nome": e["deExame"]} for e in exames_raw}
        snapshot[num] = {
            "paciente": req["nmPaciente"],
            "data":     req["dtRequisicao"][:10],
            "exames":   exames,
        }
        time.sleep(0.2)
    return snapshot


def detectar_novidades(anterior: dict, atual: dict) -> list[str]:
    msgs = []
    for num, req in atual.items():
        if num not in anterior:
            nomes = ", ".join(e["nome"] for e in req["exames"].values())
            msgs.append(
                f"🆕 <b>Nova requisição!</b>\n"
                f"👤 {req['paciente']}\n"
                f"📋 Nº {num} | {req['data']}\n"
                f"🔬 {nomes}"
            )
        else:
            exames_ant = anterior[num].get("exames", {})
            for cod, exame in req["exames"].items():
                status_novo = exame["status"]
                status_ant  = exames_ant.get(cod, {}).get("status", "")
                if status_ant and status_novo != status_ant:
                    msgs.append(
                        f"✅ <b>Resultado disponível!</b>\n"
                        f"👤 {req['paciente']}\n"
                        f"🔬 {exame['nome']}\n"
                        f"📊 {status_ant} → {status_novo}"
                    )
    return msgs


def enviar_telegram(mensagem: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHATID, "text": mensagem, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        print(f"[Telegram] Erro: {e}")


def carregar_estado() -> dict:
    if ESTADO_ARQUIVO.exists():
        return json.loads(ESTADO_ARQUIVO.read_text(encoding="utf-8"))
    return {}


def salvar_estado(snapshot: dict):
    ESTADO_ARQUIVO.write_text(
        json.dumps({"snapshot": snapshot, "atualizado_em": datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def monitorar():
    print(f"[{datetime.now():%H:%M:%S}] Monitor Telegram iniciado (intervalo: {INTERVALO_MINUTOS} min)")

    while True:
        try:
            print(f"[{datetime.now():%H:%M:%S}] Verificando...")
            token    = login()
            atual    = montar_snapshot(token)
            estado   = carregar_estado()
            anterior = estado.get("snapshot", {})

            if not anterior:
                print(f"[{datetime.now():%H:%M:%S}] Primeira execução — estado salvo, sem notificações.")
            else:
                novidades = detectar_novidades(anterior, atual)
                if novidades:
                    for msg in novidades:
                        print(f"  -> {msg[:80]}")
                        enviar_telegram(msg)
                else:
                    print(f"[{datetime.now():%H:%M:%S}] Sem novidades.")

            salvar_estado(atual)

        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] Erro: {e}")

        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    monitorar()
