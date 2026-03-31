"""
Conector para BioAnálises BitLab.
API REST com autenticação JWT.
"""

import os
import re
import zlib
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from .base import LabConnector

_REF_PAT    = re.compile(r"[\d.,]+\s+a\s+[\d.,]+")
_ALERT_RANK = {None: 0, "yellow": 1, "red": 2}


def _try_float(text: str) -> float | None:
    try:
        return float(text.strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _parse_num(text: str) -> float:
    return float(text.strip().replace(".", "").replace(",", "."))


def _calc_alert_single(value_str: str, ref_str: str) -> str | None:
    """Alert for Layout A: single numeric range on same row."""
    try:
        numeric = _parse_num(value_str)
        ref_m = _REF_PAT.search(ref_str)
        if ref_m:
            parts = ref_m.group().split(" a ")
            rmin = _parse_num(parts[0])
            rmax = _parse_num(parts[1])
            if numeric < rmin or numeric > rmax:
                boundary = rmin if numeric < rmin else rmax
                dev = abs(numeric - boundary) / boundary if boundary else 1.0
                return "red" if dev > 0.20 else "yellow"
    except (ValueError, ZeroDivisionError):
        pass
    return None


class BitlabConnector(LabConnector):

    BASE = "https://bitlabenterprise.com.br/bioanalises/api/v1"

    def __init__(self):
        self._usuario     = os.environ.get("BITLAB_USUARIO",   "11702")
        self._senha       = os.environ.get("BITLAB_SENHA",     "melanie")
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
            f"{self.BASE}/Requisicao?pageNumber=1&pageSize=500",
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

    def buscar_resultado_html(self, token: str, item_id: str) -> bytes:
        """Returns raw (zlib-compressed) HTML for a single exam result."""
        r = requests.get(
            f"{self.BASE}/ItemRequisicao/{item_id}?type=Html",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.content

    @staticmethod
    def parse_resultado(raw_bytes: bytes) -> list[dict]:
        """
        Parse BitLab zlib-compressed HTML result into structured rows.
        Handles two layouts:
          Layout A (hemograma): name + bold value + reference all on same row.
          Layout B (biochemistry): name + value on top row; species refs on subsequent rows.
        Returns list of {nome, valor, referencia, alerta} dicts.
        alerta: None | "yellow" (<=20% out of range) | "red" (>20% out of range)
        """
        try:
            html = zlib.decompress(raw_bytes).decode("latin-1")
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        rows_by_top: dict[int, list[dict]] = {}

        for div in soup.find_all("div", style=True):
            style = div.get("style", "")
            lm = re.search(r"left:(\d+)px", style)
            tm = re.search(r"top:(\d+)px", style)
            if not lm or not tm or div.find("img"):
                continue
            left = int(lm.group(1))
            top  = int(tm.group(1))
            text = div.get_text().strip()
            if text:
                rows_by_top.setdefault(top, []).append(
                    {"left": left, "text": text, "bold": bool(div.find("b"))}
                )

        sorted_tops = sorted(rows_by_top)
        skip_tops: set[int] = set()
        results = []

        for i, top in enumerate(sorted_tops):
            if top in skip_tops:
                continue

            cols = sorted(rows_by_top[top], key=lambda c: c["left"])

            # Name: one or more leftmost columns (left < 250)
            name_parts = [c["text"] for c in cols if c["left"] < 250]
            if not name_parts:
                continue

            raw_name = " ".join(name_parts)
            name = re.sub(r"\.{3,}:?\s*$", "", raw_name).rstrip(":").strip()
            if len(name) < 3:
                continue

            # Layout A: same-row reference "X a Y"
            ref_col = next(
                (c for c in sorted(cols, key=lambda c: -c["left"])
                 if _REF_PAT.search(c["text"])),
                None,
            )

            if ref_col:
                # Layout A — value + reference on same row
                val_candidates = [c for c in cols if c["left"] >= 250 and c is not ref_col]
                val_col = (
                    next((c for c in val_candidates if c["bold"]), None)
                    or next((c for c in val_candidates), None)
                )
                if not val_col:
                    continue
                value_str = val_col["text"].strip()
                ref_str   = ref_col["text"].strip()
                results.append({
                    "nome":       name,
                    "valor":      value_str,
                    "referencia": ref_str,
                    "alerta":     _calc_alert_single(value_str, ref_str),
                })

            else:
                # Layout B — value on current row, species refs on look-ahead rows
                non_name_cols = [c for c in cols if c["left"] >= 250]
                value_str: str | None = None
                unit_str:  str | None = None
                for c in non_name_cols:
                    txt = c["text"].strip()
                    if value_str is None and _try_float(txt) is not None:
                        value_str = txt
                    elif value_str is not None and unit_str is None and not _REF_PAT.search(txt):
                        unit_str = txt

                if value_str is None:
                    continue  # no numeric value → not a parameter row

                # Look ahead for species reference rows
                species_refs: list[tuple[float, float]] = []
                ref_texts: list[str] = []

                for j in range(i + 1, len(sorted_tops)):
                    next_top = sorted_tops[j]
                    next_cols = sorted(rows_by_top[next_top], key=lambda c: c["left"])

                    # Stop if this row is a new parameter (name on left + numeric on right)
                    next_name_cols  = [c for c in next_cols if c["left"] < 250]
                    next_right_cols = [c for c in next_cols if c["left"] >= 250]
                    if next_name_cols and next_right_cols:
                        if any(_try_float(c["text"]) is not None for c in next_right_cols):
                            break

                    # Stop on section headers
                    all_text = " ".join(c["text"] for c in next_cols)
                    if "Resultados Anteriores" in all_text:
                        break

                    # Collect species refs from right-side columns
                    for c in next_cols:
                        if c["left"] < 300:
                            continue
                        ref_m = _REF_PAT.search(c["text"])
                        if ref_m:
                            skip_tops.add(next_top)
                            ref_texts.append(c["text"].strip())
                            parts = ref_m.group().split(" a ")
                            try:
                                species_refs.append(
                                    (_parse_num(parts[0]), _parse_num(parts[1]))
                                )
                            except Exception:
                                pass

                valor_display = value_str + (f" {unit_str}" if unit_str else "")

                if not species_refs:
                    results.append({
                        "nome":       name,
                        "valor":      valor_display,
                        "referencia": "—",
                        "alerta":     None,
                    })
                    continue

                # Alert: outside ALL ranges → red/yellow; outside SOME → yellow; none → None
                alert: str | None = None
                numeric = _try_float(value_str)
                if numeric is not None:
                    outside_count = sum(
                        1 for rmin, rmax in species_refs
                        if numeric < rmin or numeric > rmax
                    )
                    if outside_count == len(species_refs) and outside_count > 0:
                        max_dev = 0.0
                        for rmin, rmax in species_refs:
                            if numeric < rmin:
                                dev = abs(numeric - rmin) / rmin if rmin else 1.0
                            else:
                                dev = abs(numeric - rmax) / rmax if rmax else 1.0
                            max_dev = max(max_dev, dev)
                        alert = "red" if max_dev > 0.20 else "yellow"
                    elif outside_count > 0:
                        alert = "yellow"

                results.append({
                    "nome":       name,
                    "valor":      valor_display,
                    "referencia": "; ".join(ref_texts),
                    "alerta":     alert,
                })

        return results

    def enrich_resultados(self, anterior: dict, atual: dict) -> None:
        """
        Fetch and cache result alert levels for newly-Pronto items. Mutates atual in-place.
        - If item was already Pronto with a cached alerta → carries it forward (no HTTP call).
        - If item is newly Pronto → fetches result HTML and stores alerta + resultado rows.
        """
        from web.state import normalize_status

        to_fetch: list[tuple[str, str, str]] = []  # (rid, iid, item_id)

        for rid, rec in atual.items():
            ant_rec = anterior.get(rid, {})
            for iid, item in rec["itens"].items():
                if normalize_status(item["status"]) != "Pronto":
                    continue
                ant_item = ant_rec.get("itens", {}).get(iid, {})
                if "alerta" in ant_item:
                    # Carry forward cached result
                    item["alerta"]    = ant_item["alerta"]
                    item["resultado"] = ant_item.get("resultado", [])
                elif item.get("item_id"):
                    to_fetch.append((rid, iid, item["item_id"]))

        if not to_fetch:
            return

        try:
            token = self._login()
        except Exception as e:
            print(f"  [BitLab resultados] login failed: {e}")
            return

        for rid, iid, item_id in to_fetch:
            try:
                raw = self.buscar_resultado_html(token, item_id)
                rows = self.parse_resultado(raw)
                worst = max(
                    (r["alerta"] for r in rows),
                    key=lambda a: _ALERT_RANK.get(a, 0),
                    default=None,
                )
                atual[rid]["itens"][iid]["alerta"]    = worst
                atual[rid]["itens"][iid]["resultado"] = rows
                print(f"  [BitLab resultados] {iid} → alerta={worst}")
            except Exception as e:
                print(f"  [BitLab resultados] {iid}: {e}")
            time.sleep(0.1)

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
                    "item_id":  e.get("id", ""),
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
