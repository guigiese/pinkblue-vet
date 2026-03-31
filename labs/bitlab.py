"""
Conector para BioAnálises BitLab.
API REST com autenticação JWT.
"""

import os
import time
import requests
from datetime import datetime, timedelta
from .base import LabConnector


class BitlabConnector(LabConnector):

    BASE = "https://bitlabenterprise.com.br/bioanalises/api/v1"

    def __init__(self):
        self._usuario    = os.environ.get("BITLAB_USUARIO",   "11702")
        self._senha      = os.environ.get("BITLAB_SENHA",     "melanie")
        self._cd_convenio = int(os.environ.get("BITLAB_CD_CONVENIO", "1170"))
        self._cd_posto    = int(os.environ.get("BITLAB_CD_POSTO",    "8"))
        self._dias_atras  = int(os.environ.get("DIAS_ATRAS",         "30"))

    @property
    def lab_id(self):
        return "bitlab"

    @property
    def lab_name(self):
        return "BioAnálises (BitLab)"

    def _login(self) -> str:
        r = requests.post(f"{self.BASE}/SignIn",
                          json={"userName": self._usuario, "password": self._senha},
                          timeout=15)
        r.raise_for_status()
        return r.json()["token"]

    def _buscar_requisicoes(self, token: str) -> list[dict]:
        hoje   = datetime.now().strftime("%Y-%m-%d")
        inicio = (datetime.now() - timedelta(days=self._dias_atras)).strftime("%Y-%m-%d")
        r = requests.post(
            f"{self.BASE}/Requisicao?pageNumber=1&pageSize=200",
            headers={"Authorization": f"Bearer {token}"},
            json={"dataInicial": inicio, "dataFinal": hoje},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data

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
                }
                for e in itens_raw
            }
            resultado[req["requisicao"]] = {
                "label":     req["nmPaciente"],
                "data":      req["dtRequisicao"][:10],
                "portal_id": req["id"],
                "itens":     itens,
            }
            time.sleep(0.2)

        return resultado
