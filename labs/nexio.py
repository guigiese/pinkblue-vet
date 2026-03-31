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
            radio = row.find("input", {"name": "exameId"})
            exames.append({
                "numero":         cols[1],
                "paciente":       cols[3],
                "proprietario":   cols[4],
                "data_prometida": cols[6],
                "data_liberacao": cols[7],
                "status":         cols[8],
                "exame_id":       radio["value"] if radio else "",
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
            # Normaliza data para YYYY-MM-DD.
            # Usa D.Liberação se preenchida, senão D.Prometido.
            # Pathoweb pode retornar DD/MM/YY (2 dígitos) ou DD/MM/YYYY (4 dígitos).
            from datetime import datetime
            raw_date = exame["data_liberacao"] or exame["data_prometida"]
            data_iso = raw_date
            for fmt in ("%d/%m/%Y", "%d/%m/%y"):
                try:
                    data_iso = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            resultado[num] = {
                "label":     label,
                "data":      data_iso,
                "portal_id": exame["exame_id"],
                "itens": {
                    num: {"nome": f"Patologia {num}", "status": exame["status"]}
                },
            }

        return resultado
