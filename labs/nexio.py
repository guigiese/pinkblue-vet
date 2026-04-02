"""
Conector para Nexio Patologia (Pathoweb).
Autenticação via sessão (Spring Security form login).
"""

import os
import io
import re
import time
import unicodedata
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .base import LabConnector


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def _compose_species_sex(species_raw: str, sex_raw: str) -> str:
    species_norm = _strip_accents((species_raw or "").strip().lower())
    sex_norm = (sex_raw or "").strip().upper()

    if species_norm.startswith("canin"):
        return "cadela" if sex_norm == "F" else "cão" if sex_norm == "M" else "cão"
    if species_norm.startswith("felin"):
        return "gata" if sex_norm == "F" else "gato" if sex_norm == "M" else "gato"
    if not species_raw:
        return ""
    if sex_norm:
        return f"{species_raw.title()} {sex_norm}"
    return species_raw.title()


def _clean_report_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    cleaned: list[str] = []
    prev_blank = True
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
            continue
        cleaned.append(line)
        prev_blank = False
    return "\n".join(cleaned).strip()


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

    def _fetch_report_pdf(self, session: requests.Session, exame_id: str) -> bytes:
        viewer = session.get(
            f"{self.BASE}/moduloProcedencia/visualizarLaudoAjax?id={exame_id}",
            timeout=20,
        )
        viewer.raise_for_status()
        soup = BeautifulSoup(viewer.text, "html.parser")
        frame = soup.find(src=re.compile(r"/imagem/renderReport\?path="))
        if not frame or not frame.get("src"):
            raise ValueError("Nao foi possivel localizar o PDF do laudo no viewer do Nexio.")
        report = session.get(f"{self.BASE}{frame['src']}", timeout=20)
        report.raise_for_status()
        return report.content

    @staticmethod
    def parse_report_metadata(raw_pdf: bytes) -> dict:
        raw_text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(raw_pdf)).pages
        )
        return NexioConnector.parse_report_text(raw_text)

    @staticmethod
    def parse_report_text(raw_text: str) -> dict:
        report_text = _clean_report_text(raw_text)
        plain_text = _strip_accents(report_text)

        species_match = re.search(r"ESPECIE:\s*([A-Z]+)", plain_text, re.I)
        breed_match = re.search(r"RACA:\s*(.*?)\s*DATA DE RECEBIMENTO:", plain_text, re.I | re.S)
        owner_match = re.search(r"RESPONSAVEL:\s*([^\n]+)", plain_text, re.I)
        sex_match = re.search(r"([MF])SEXO:", plain_text, re.I)
        diagnosis_match = re.search(
            r"DIAGNOSTICO\s*(.*?)\s*DESCRICAO MACROSCOPICA",
            plain_text,
            re.I | re.S,
        )

        species_raw = (species_match.group(1).strip().title() if species_match else "")
        breed = (breed_match.group(1).strip().title() if breed_match and breed_match.group(1).strip() else "")
        owner_name = (owner_match.group(1).strip().title() if owner_match else "")
        sex_raw = (sex_match.group(1).strip().upper() if sex_match else "")
        diagnosis = (diagnosis_match.group(1).strip() if diagnosis_match else "")

        return {
            "owner_name": owner_name,
            "species_raw": species_raw,
            "sex_raw": sex_raw,
            "species_sex": _compose_species_sex(species_raw, sex_raw),
            "breed": breed,
            "report_text": report_text,
            "diagnosis_text": diagnosis,
        }

    def enrich_snapshot_metadata(self, anterior: dict, atual: dict) -> None:
        carry_fields = ("owner_name", "species_raw", "sex_raw", "species_sex", "breed")
        to_fetch: list[tuple[str, str]] = []

        for rid, record in atual.items():
            ant_rec = anterior.get(rid, {})
            for field in carry_fields:
                if ant_rec.get(field) and not record.get(field):
                    record[field] = ant_rec[field]

            current_item = next(iter(record.get("itens", {}).values()), None)
            ant_item = next(iter(ant_rec.get("itens", {}).values()), None)
            if current_item is not None and ant_item:
                if ant_item.get("report_text") and not current_item.get("report_text"):
                    current_item["report_text"] = ant_item["report_text"]
                if ant_item.get("diagnosis_text") and not current_item.get("diagnosis_text"):
                    current_item["diagnosis_text"] = ant_item["diagnosis_text"]

            if record.get("species_sex") and current_item and current_item.get("report_text"):
                continue

            portal_id = record.get("portal_id")
            if portal_id:
                to_fetch.append((rid, portal_id))

        if not to_fetch:
            return

        try:
            session = self._login()
        except Exception as e:
            print(f"  [Nexio metadata] login failed: {e}")
            return

        for rid, portal_id in to_fetch:
            try:
                raw_pdf = self._fetch_report_pdf(session, portal_id)
                metadata = self.parse_report_metadata(raw_pdf)
                if metadata:
                    atual[rid].update({k: v for k, v in metadata.items() if k not in {"report_text", "diagnosis_text"} and v})
                    current_item = next(iter(atual[rid]["itens"].values()), None)
                    if current_item is not None:
                        if metadata.get("report_text"):
                            current_item["report_text"] = metadata["report_text"]
                        if metadata.get("diagnosis_text"):
                            current_item["diagnosis_text"] = metadata["diagnosis_text"]
                    print(
                        f"  [Nexio metadata] {rid} -> "
                        f"species={atual[rid].get('species_sex') or '-'} "
                        f"breed={atual[rid].get('breed') or '-'}"
                    )
            except Exception as e:
                print(f"  [Nexio metadata] {rid}: {e}")
            time.sleep(0.05)

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
