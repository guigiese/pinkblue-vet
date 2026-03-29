"""
Conector para Nexio Patologia (Pathoweb).
Autenticação via sessão (Spring Security form login).
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from .base import LabConnector


class NexioConnector(LabConnector):

    BASE  = "https://www.pathoweb.com.br"
    LOGIN = f"{BASE}/j_spring_security_check"
    LISTA = f"{BASE}/moduloProcedencia/consultaExameFiltroAjax"

    def __init__(self):
        self._usuario = os.environ.get("NEXIO_USUARIO", "pinkblue.vet@gmail.com")
        self._senha   = os.environ.get("NEXIO_SENHA",   "123")

    @property
    def lab_id(self):
        return "nexio"

    @property
    def lab_name(self):
        return "Nexio Patologia"

    def _login(self) -> requests.Session:
        session = requests.Session()
        session.post(self.LOGIN, data={
            "j_username": self._usuario,
            "j_password": self._senha,
            "_spring_security_remember_me": "on",
        }, allow_redirects=True, timeout=15)
        return session

    def _buscar_exames(self, session: requests.Session) -> list[dict]:
        ts = int(time.time() * 1000)
        r = session.post(f"{self.LISTA}?timeReq={ts}", data={
            "campo": "", "cpf": "", "rg": "", "dataNascimento": "",
            "convenioId": "", "medicoRequisitanteId": "", "patologistaDesignadoId": "",
            "tipoExameId": "", "dataRecepcao": "", "dataLiberacao": "",
            "numeroInicial": "", "numeroFinal": "", "prontuario": "",
            "positivoMalignidade": "", "etapa": "", "numeroGuiaConvenio": "",
            "ordenarPor": "", "sortiar": "", "atipia": "", "casoCritico": "",
            "nomeProprietario": "",
        }, timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        exames = []
        rows = soup.find_all("tr")

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 9:
                continue
            # Colunas: [0]checkbox | [1]Exame | [2]Senha | [3]Nome | [4]Proprietário
            #          [5]Prontuário | [6]D.Prometido | [7]D.Liberação | [8]Situação
            exames.append({
                "numero":        cols[1],
                "paciente":      cols[3],
                "proprietario":  cols[4],
                "data_prometida": cols[6],
                "status":        cols[8],
            })

        return exames

    def snapshot(self) -> dict[str, dict]:
        session = self._login()
        resultado = {}

        for exame in self._buscar_exames(session):
            num = exame["numero"]
            if not num:
                continue
            label = f"{exame['paciente']} - {exame['proprietario']}".strip(" -")
            resultado[num] = {
                "label": label,
                "data":  exame["data_prometida"],
                "itens": {
                    num: {"nome": f"Exame {num}", "status": exame["status"]}
                },
            }

        return resultado
