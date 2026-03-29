"""
Monitor de exames - BitLab Enterprise
Detecta novas requisições e mudanças de status, notifica via WhatsApp (Callmebot).
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

# ============================================================
# CONFIGURAÇÃO — lida de variáveis de ambiente
# ============================================================
import os

WHATSAPP_PHONE   = os.environ.get("WHATSAPP_PHONE",   "555197529191")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "4137541")

API_BASE    = "https://bitlabenterprise.com.br/bioanalises/api/v1"
USUARIO     = os.environ.get("BITLAB_USUARIO",  "11702")
SENHA       = os.environ.get("BITLAB_SENHA",    "melanie")
CD_CONVENIO = int(os.environ.get("CD_CONVENIO", "1170"))
CD_POSTO    = int(os.environ.get("CD_POSTO",    "8"))

INTERVALO_MINUTOS = int(os.environ.get("INTERVALO_MINUTOS", "5"))
DIAS_ATRAS        = int(os.environ.get("DIAS_ATRAS",        "30"))

ESTADO_ARQUIVO = Path("/tmp/estado_exames.json")
# ============================================================


def login() -> str:
    r = requests.post(f"{API_BASE}/SignIn", json={"userName": USUARIO, "password": SENHA}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def buscar_requisicoes(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    hoje = datetime.now().strftime("%Y-%m-%d")
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
    """Retorna dict {numero_req: {info, exames: {codigo: status}}}"""
    requisicoes = buscar_requisicoes(token)
    snapshot = {}
    for req in requisicoes:
        num = req["requisicao"]
        exames_raw = buscar_exames(token, req["cdRequisicao"])
        exames = {e["cdExame"]: {"status": e["deStatusWeb"], "nome": e["deExame"]} for e in exames_raw}
        snapshot[num] = {
            "paciente":  req["nmPaciente"],
            "data":      req["dtRequisicao"][:10],
            "exames":    exames,
        }
        time.sleep(0.2)  # gentileza com a API
    return snapshot


def detectar_novidades(anterior: dict, atual: dict) -> list[str]:
    msgs = []

    for num, req in atual.items():
        if num not in anterior:
            nomes = ", ".join(e["nome"] for e in req["exames"].values())
            msgs.append(
                f"Nova requisicao!\n"
                f"Paciente: {req['paciente']}\n"
                f"N: {num} | Data: {req['data']}\n"
                f"Exames: {nomes}"
            )
        else:
            exames_ant = anterior[num].get("exames", {})
            for cod, exame in req["exames"].items():
                status_novo = exame["status"]
                status_ant  = exames_ant.get(cod, {}).get("status", "")
                if status_ant and status_novo != status_ant:
                    msgs.append(
                        f"Resultado disponivel!\n"
                        f"Paciente: {req['paciente']}\n"
                        f"Exame: {exame['nome']}\n"
                        f"Status: {status_ant} -> {status_novo}"
                    )

    return msgs


def enviar_whatsapp(mensagem: str):
    try:
        requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": WHATSAPP_PHONE, "text": mensagem, "apikey": CALLMEBOT_APIKEY},
            timeout=15,
        )
    except Exception as e:
        print(f"[WhatsApp] Erro: {e}")


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
    print(f"[{datetime.now():%H:%M:%S}] Monitor iniciado (intervalo: {INTERVALO_MINUTOS} min)")

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
                        enviar_whatsapp(msg)
                else:
                    print(f"[{datetime.now():%H:%M:%S}] Sem novidades.")

            salvar_estado(atual)

        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] Erro: {e}")

        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    monitorar()
