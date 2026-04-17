import unittest
import zlib

import core
from fastapi.testclient import TestClient
from labs.bitlab import BitlabConnector
from labs.nexio import NexioConnector, _build_exam_display_name
from web import app as web_app
from web.state import state


def _fake_bitlab_pdf_payload(*lines: tuple[float, float, str]) -> bytes:
    chunks = [b"%PDF-1.2\n"]
    for x_pos, y_pos, text in lines:
        safe_text = (
            text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        chunks.append(f"{x_pos} {y_pos} Td ({safe_text}) Tj\n".encode("latin-1"))
    chunks.append(b"%%EOF")
    return b"".join(chunks)


class SnapshotHydrationTests(unittest.TestCase):
    def test_first_cycle_hydrates_ready_items(self):
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {
                        "nome": "Hemograma",
                        "status": "Pronto",
                        "item_id": "item-1",
                    }
                },
            }
        }

        class FakeLab:
            def __init__(self):
                self.called = 0

            def enrich_resultados(self, anterior, snapshot):
                self.called += 1
                snapshot["REQ-1"]["itens"]["I1"]["alerta"] = "yellow"
                snapshot["REQ-1"]["itens"]["I1"]["resultado"] = [
                    {"nome": "ALT", "valor": "12", "referencia": "10 a 20", "alerta": "yellow"}
                ]

        lab = FakeLab()

        core._hydrate_snapshot_details(lab, {}, atual, "2026-04-01T10:00:00")

        self.assertEqual(lab.called, 1)
        self.assertEqual(atual["REQ-1"]["itens"]["I1"]["alerta"], "yellow")
        self.assertEqual(len(atual["REQ-1"]["itens"]["I1"]["resultado"]), 1)

    def test_first_cycle_preserves_ready_items_with_fallback_release_hint(self):
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "received_at": "2026-03-31T16:55:17",
                "itens": {
                    "I1": {
                        "nome": "Hemograma",
                        "status": "Pronto",
                        "item_id": "item-1",
                        "dtColeta": "2026-03-31T17:10:00",
                    }
                },
            }
        }

        class FakeLab:
            pass

        core._hydrate_snapshot_details(FakeLab(), {}, atual, "2026-04-02T10:00:00")

        self.assertEqual(atual["REQ-1"]["itens"]["I1"]["liberado_em"], "2026-03-31T17:10:00")

    def test_operational_rules_mark_ready_without_payload_as_inconsistent(self):
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {
                        "nome": "Hemograma",
                        "status": "Pronto",
                        "lab_status": "Pronto",
                        "resultado": [],
                        "report_text": "",
                    }
                },
            }
        }

        core._apply_operational_status_rules(atual)

        self.assertEqual(atual["REQ-1"]["itens"]["I1"]["status"], "Inconsistente")
        self.assertEqual(atual["REQ-1"]["itens"]["I1"]["result_issue"], "ready-without-result")

    def test_operational_rules_preserve_ready_when_textual_result_exists(self):
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {
                        "nome": "Patologia",
                        "status": "Pronto",
                        "lab_status": "Pronto",
                        "resultado": [],
                        "report_text": "Diagnostico conclusivo",
                    }
                },
            }
        }

        core._apply_operational_status_rules(atual)

        self.assertEqual(atual["REQ-1"]["itens"]["I1"]["status"], "Pronto")

    def test_group_status_rollup_keeps_inconsistent_only_at_item_level(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {
                                "nome": "Hemograma",
                                "status": "Inconsistente",
                                "lab_status": "Pronto",
                                "item_id": "item-1",
                            }
                        },
                    }
                }
            }

            groups = state.get_exames()
            counts = state.get_lab_counts()

            self.assertEqual(groups[0]["status_geral"], "Em Andamento")
            self.assertEqual(groups[0]["items_view"][0]["status"], "Inconsistente")
            self.assertEqual(counts["bitlab"]["andamento"], 1)
            self.assertEqual(counts["bitlab"]["pronto"], 0)
        finally:
            state.snapshots = original_snapshots
            state._config = original_config


class ResultCacheTests(unittest.TestCase):
    def test_manual_result_fetch_rehydrates_snapshot_item(self):
        original_snapshots = state.snapshots
        try:
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {
                                "nome": "Hemograma",
                                "status": "Pronto",
                                "item_id": "item-1",
                            }
                        },
                    }
                }
            }

            rows = [
                {"nome": "ALT", "valor": "12", "referencia": "10 a 20", "alerta": "yellow"},
                {"nome": "AST", "valor": "50", "referencia": "10 a 20", "alerta": "red"},
            ]

            web_app._cache_resultado("item-1", rows)

            item = state.snapshots["bitlab"]["REQ-1"]["itens"]["I1"]
            self.assertEqual(item["resultado"], rows)
            self.assertEqual(item["alerta"], "red")
        finally:
            state.snapshots = original_snapshots

    def test_get_exames_exposes_cached_result_rows(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "BitLab"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "portal_id": "portal-1",
                        "itens": {
                            "I1": {
                                "nome": "Hemograma",
                                "status": "Pronto",
                                "item_id": "item-1",
                                "alerta": "yellow",
                                "resultado": [{"nome": "Hemacias", "valor": "3,2", "referencia": "5,5 a 8,5", "alerta": "red"}],
                            }
                        },
                    }
                }
            }

            groups = state.get_exames()

            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["itens"][0]["resultado"][0]["nome"], "Hemacias")
            self.assertEqual(groups[0]["patient_name"], "Bidu")
            self.assertEqual(groups[0]["tutor_name"], "Tutor")
            self.assertEqual(groups[0]["protocol"], "REQ-1")
            self.assertEqual(groups[0]["ready_ratio_text"], "1/1 prontos")
            self.assertEqual(groups[0]["items_view"][0]["name"], "Hemograma")
            self.assertEqual(groups[0]["criticality"], "yellow")
        finally:
            state.snapshots = original_snapshots
            state._config = original_config

    def test_sync_context_uses_short_discovery_window_and_tracks_open_records(self):
        original_snapshots = state.snapshots
        try:
            state.snapshots = {
                "bitlab": {
                    "REQ-OPEN": {
                        "label": "Bidu - Tutor",
                        "data": "2026-03-01",
                        "received_at": "2026-03-01T10:00:00",
                        "portal_id": "portal-1",
                        "request_key": "123",
                        "itens": {
                            "I1": {"nome": "Hemograma", "status": "Em Andamento"},
                        },
                    },
                    "REQ-DONE": {
                        "label": "Bidu - Tutor",
                        "data": "2026-03-02",
                        "received_at": "2026-03-02T10:00:00",
                        "portal_id": "portal-2",
                        "request_key": "456",
                        "itens": {
                            "I2": {"nome": "ALT", "status": "Pronto"},
                        },
                    },
                }
            }

            ctx = state.sync_context("bitlab")

            self.assertEqual(ctx["discovery_days"], 3)
            self.assertEqual(len(ctx["open_records"]), 1)
            self.assertEqual(ctx["open_records"][0]["record_id"], "REQ-OPEN")
            self.assertEqual(ctx["open_records"][0]["request_key"], "123")
        finally:
            state.snapshots = original_snapshots

    def test_get_exames_exposes_breed_and_report_text(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "nexio", "name": "Nexio"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "nexio": {
                    "AP000184/26": {
                        "label": "Linda - Anelise Vogt",
                        "data": "2026-03-26",
                        "portal_id": "22032821",
                        "species_sex": "gata",
                        "breed": "SRD",
                        "itens": {
                            "AP000184/26": {
                                "nome": "Patologia AP000184/26",
                                "status": "Arquivo morto",
                                "report_text": "DIAGNÓSTICO\nHemangiossarcoma cutâneo.",
                                "diagnosis_text": "Hemangiossarcoma cutâneo.",
                            }
                        },
                    }
                }
            }

            groups = state.get_exames()

            self.assertEqual(groups[0]["species_sex"], "gata")
            self.assertEqual(groups[0]["breed"], "SRD")
            self.assertIn("Hemangiossarcoma", groups[0]["items_view"][0]["report_text"])
            self.assertIn("Hemangiossarcoma", groups[0]["items_view"][0]["diagnosis_text"])
        finally:
            state.snapshots = original_snapshots
            state._config = original_config

    def test_get_exames_strips_prop_prefix_from_tutor_label(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "BitLab"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-2": {
                        "label": "PIDA - JINGWEI DU PROP: JINGWEI DU",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {
                                "nome": "Hemograma",
                                "status": "Pronto",
                            }
                        },
                    }
                }
            }

            groups = state.get_exames()

            self.assertEqual(groups[0]["patient_name"], "PIDA")
            self.assertEqual(groups[0]["tutor_name"], "JINGWEI DU")
        finally:
            state.snapshots = original_snapshots
            state._config = original_config


class ConnectorMetadataParsingTests(unittest.TestCase):
    def test_bitlab_parse_requisicao_metadata(self):
        raw_pdf = (
            "q 0 0 0 rg BT /F2 8 Tf 12 678 Td (Proprietário....:) Tj ET Q "
            "q 0 0 0 rg BT /F2 8 Tf 12 666 Td (Espécie.........:) Tj ET Q "
            "q 0 0 0 rg BT /F2 8 Tf 349.5 678 Td (Raça............:) Tj ET Q "
            "q 0 0 0 rg 101.25 710.25 249.75 12 re W n BT /F1 11 Tf 104.25 712.5 Td (PIDA - JINGWEI DU) Tj ET Q "
            "q 0 0 0 rg 502.5 686.25 25.5 12 re W n BT /F2 8 Tf 504.75 690 Td (F) Tj ET Q "
            "q 0 0 0 rg 441.75 686.25 59.25 12 re W n BT /F2 8 Tf 444 690 Td (7 Meses) Tj ET Q "
            "q 0 0 0 rg 441.75 698.25 99.75 12 re W n BT /F2 8 Tf 444 702 Td (31/03/26 16:55) Tj ET Q "
            "q 0 0 0 rg 462.75 710.25 79.5 12 re W n BT /F2 8 Tf 465 714 Td (00030473) Tj ET Q "
            "q 0 0 0 rg 437.25 710.25 18.75 12 re W n BT /F2 8 Tf 440.25 714 Td (08) Tj ET Q "
            "q 0 0 0 rg 104.25 674.25 207.75 12 re W n BT /F2 8 Tf 106.5 678 Td (JINGWEI DU) Tj ET Q "
            "q 0 0 0 rg 104.25 662.25 72.75 12 re W n BT /F2 8 Tf 106.5 666 Td (FELINA) Tj ET Q "
            "q 0 0 0 rg 441.75 674.25 72.75 12 re W n BT /F2 8 Tf 444 678 Td (S.R.D..) Tj ET Q "
        ).encode("latin-1")

        metadata = BitlabConnector.parse_requisicao_metadata(raw_pdf)

        self.assertEqual(metadata["owner_name"], "JINGWEI DU")
        self.assertEqual(metadata["species_raw"], "FELINA")
        self.assertEqual(metadata["species_sex"], "gata")
        self.assertEqual(metadata["breed"], "SRD")
        self.assertEqual(metadata["protocol_number"], "08-00030473")

    def test_nexio_parse_report_text(self):
        report_text = """
        14/03/2026
        DADOS DO PACIENTE:
        Espécie: FELINA
        Idade:
        FSexo:
        Responsável: ANELISE VOGT
        Convênio: PINK E BLUE VETERINÁRIA
        DIAGNÓSTICO
        Características histológicas favorecem hemangiossarcoma cutâneo.
        DESCRIÇÃO MACROSCOPICA
        Material: Um fragmento.
        """

        metadata = NexioConnector.parse_report_text(report_text)

        self.assertEqual(metadata["species_raw"], "Felina")
        self.assertEqual(metadata["species_sex"], "gata")
        self.assertEqual(metadata["sex_raw"], "F")
        self.assertEqual(metadata["owner_name"], "Anelise Vogt")
        self.assertEqual(metadata["received_at"], "2026-03-14")
        self.assertIn("hemangiossarcoma", metadata["diagnosis_text"].lower())

    def test_nexio_parse_report_text_handles_late_diagnosis_section(self):
        report_text = """
        DESCRIÇÃO MACROSCOPICA
        Material: Nódulo cutâneo.
        HISTÓRICO
        Crescimento rápido.
        DIAGNÓSTICO
        Paniculite e dermatite profunda, piogranulomatosa, associada a fibrose.
        NOTA
        Recomenda-se correlação clínica.
        """

        metadata = NexioConnector.parse_report_text(report_text)

        self.assertIn("Paniculite e dermatite profunda", metadata["diagnosis_text"])

    def test_nexio_enrich_snapshot_metadata_reuses_cached_report_text_to_replace_raw_name(self):
        connector = NexioConnector()
        connector._login = lambda: (_ for _ in ()).throw(AssertionError("should not fetch remote metadata"))

        anterior = {
            "AP000802/25": {
                "label": "Manjericão - Graziela Barth",
                "species_sex": "cão",
                "itens": {
                    "AP000802/25": {
                        "nome": "Patologia AP000802/25",
                        "status": "Pronto",
                        "report_text": (
                            "DESCRIÇÃO MACROSCOPICA\nMaterial: Nódulo.\n"
                            "DIAGNÓSTICO\nPaniculite e dermatite profunda, piogranulomatosa.\n"
                            "NOTA\nCorrelação clínica.\n"
                        ),
                    }
                },
            }
        }
        atual = {
            "AP000802/25": {
                "label": "Manjericão - Graziela Barth",
                "species_sex": "cão",
                "itens": {
                    "AP000802/25": {
                        "nome": "Patologia AP000802/25",
                        "status": "Pronto",
                        "report_text": (
                            "DESCRIÇÃO MACROSCOPICA\nMaterial: Nódulo.\n"
                            "DIAGNÓSTICO\nPaniculite e dermatite profunda, piogranulomatosa.\n"
                            "NOTA\nCorrelação clínica.\n"
                        ),
                    }
                },
            }
        }

        connector.enrich_snapshot_metadata(anterior, atual)

        item = atual["AP000802/25"]["itens"]["AP000802/25"]
        self.assertEqual(item["diagnosis_text"], "Paniculite e dermatite profunda, piogranulomatosa.")
        self.assertEqual(item["nome"], "Paniculite e dermatite profunda, piogranulomatosa")

    def test_nexio_builds_readable_display_name_from_diagnosis(self):
        readable = _build_exam_display_name(
            "AP000184/26",
            "Características histológicas favorecem hemangiossarcoma cutâneo.",
        )

        self.assertEqual(readable, "Hemangiossarcoma cutâneo")


class BitlabReferenceSelectionTests(unittest.TestCase):
    def test_bitlab_selects_reference_for_patient_species(self):
        html = """
        <html><body>
          <div style="left:20px;top:10px">TGP</div>
          <div style="left:320px;top:10px"><b>50</b></div>
          <div style="left:380px;top:10px">U/L</div>
          <div style="left:320px;top:40px">Canino: 10 a 80 U/L</div>
          <div style="left:320px;top:60px">Felino: 5 a 35 U/L</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Felina", "sex_raw": "F", "species_sex": "gata"},
        )

        self.assertEqual(rows[0]["referencia"], "Felino: 5 a 35 U/L")
        self.assertEqual(rows[0]["alerta"], "red")

    def test_bitlab_falls_back_to_species_group_when_sex_unknown(self):
        html = """
        <html><body>
          <div style="left:20px;top:10px">Creatinina</div>
          <div style="left:320px;top:10px"><b>1,3</b></div>
          <div style="left:380px;top:10px">mg/dL</div>
          <div style="left:320px;top:40px">Canino macho: 0,8 a 1,6 mg/dL</div>
          <div style="left:320px;top:60px">Canino femea: 0,7 a 1,4 mg/dL</div>
          <div style="left:320px;top:80px">Felino: 0,8 a 1,8 mg/dL</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Canina"},
        )

        self.assertEqual(
            rows[0]["referencia"],
            "Canino macho: 0,8 a 1,6 mg/dL; Canino femea: 0,7 a 1,4 mg/dL",
        )
        self.assertIsNone(rows[0]["alerta"])

    def test_bitlab_enrich_resultados_uses_record_context(self):
        html = """
        <html><body>
          <div style="left:20px;top:10px">TGP</div>
          <div style="left:320px;top:10px"><b>50</b></div>
          <div style="left:380px;top:10px">U/L</div>
          <div style="left:320px;top:40px">Canino: 10 a 80 U/L</div>
          <div style="left:320px;top:60px">Felino: 5 a 35 U/L</div>
        </body></html>
        """.encode("latin-1")

        connector = BitlabConnector()
        connector._login = lambda: "token"
        connector.buscar_resultado_html = lambda token, item_id: zlib.compress(html)

        atual = {
            "REQ-1": {
                "label": "Mia - Tutor",
                "data": "2026-04-01",
                "species_raw": "Felina",
                "sex_raw": "F",
                "species_sex": "gata",
                "itens": {
                    "I1": {"nome": "TGP", "status": "Pronto", "item_id": "item-1"},
                },
            }
        }

        connector.enrich_resultados({}, atual)

        item = atual["REQ-1"]["itens"]["I1"]
        self.assertEqual(item["resultado"][0]["referencia"], "Felino: 5 a 35 U/L")
        self.assertEqual(item["alerta"], "red")

    def test_bitlab_parse_resultado_text_reads_pdf_operator_payload(self):
        raw_pdf = _fake_bitlab_pdf_payload(
            (16.5, 615.75, "CREATININA VETERINARIA.......:"),
            (237.0, 615.75, "2,3"),
            (262.5, 615.75, "mg/dL"),
            (327.0, 584.25, "Felino:   0,8 a 1,8 mg/dL"),
            (375.0, 170.25, "Data da liberação:"),
            (459.75, 170.25, "15/04/26 17:15"),
        )

        report_text = BitlabConnector.parse_resultado_text(raw_pdf)

        self.assertIn("CREATININA VETERINARIA.......: 2,3 mg/dL", report_text)
        self.assertIn("Felino: 0,8 a 1,8 mg/dL", report_text)
        self.assertIn("Data da liberação: 15/04/26 17:15", report_text)

    def test_bitlab_enrich_resultados_falls_back_to_pdf_text_when_html_is_empty(self):
        raw_pdf = _fake_bitlab_pdf_payload(
            (16.5, 615.75, "CREATININA VETERINARIA.......:"),
            (237.0, 615.75, "2,3"),
            (262.5, 615.75, "mg/dL"),
            (327.0, 584.25, "Felino:   0,8 a 1,8 mg/dL"),
        )

        connector = BitlabConnector()
        connector._login = lambda: "token"
        connector.buscar_resultado_html = lambda token, item_id: b"\x00"
        connector.buscar_resultado_pdf = lambda token, item_id: raw_pdf

        atual = {
            "REQ-1": {
                "label": "Layla - Tutor",
                "data": "2026-04-15",
                "species_raw": "Felina",
                "sex_raw": "F",
                "species_sex": "gata",
                "itens": {
                    "I1": {"nome": "Creatinina", "status": "Pronto", "lab_status": "Pronto", "item_id": "item-1"},
                },
            }
        }

        connector.enrich_resultados({}, atual)
        core._apply_operational_status_rules(atual)

        item = atual["REQ-1"]["itens"]["I1"]
        self.assertEqual(item["resultado"], [])
        self.assertIn("CREATININA VETERINARIA.......: 2,3 mg/dL", item["report_text"])
        self.assertEqual(item["status"], "Pronto")

    def test_bitlab_hemograma_prefers_species_specific_range_from_combined_cell(self):
        html = """
        <html><body>
          <div style="left:22px;top:208px"><b>LEUCOGRAMA</b></div>
          <div style="left:472px;top:224px">Caninos</div>
          <div style="left:638px;top:224px">Felinos</div>
          <div style="left:22px;top:272px">Segmentados................:</div>
          <div style="left:324px;top:272px"><b>44</b></div>
          <div style="left:387px;top:272px"><b>3608</b></div>
          <div style="left:466px;top:272px">60 a 77                    35 a 75</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Felina", "sex_raw": "F", "species_sex": "gata", "patient_age": "7 Meses"},
        )

        self.assertEqual(rows[0]["valor"], "44%")
        self.assertEqual(rows[0]["referencia"], "35 a 75")
        self.assertEqual(rows[0]["components"][0]["valor"], "44%")
        self.assertEqual(rows[0]["components"][0]["referencia"], "35 a 75")
        self.assertEqual(rows[0]["components"][1]["valor"], "3608/mm3")
        self.assertEqual(rows[0]["components"][1]["referencia"], "n/d")
    def test_bitlab_hemograma_keeps_species_context_for_later_compound_rows(self):
        html = """
        <html><body>
          <div style="left:22px;top:208px"><b>LEUCOGRAMA</b></div>
          <div style="left:472px;top:224px">Caninos</div>
          <div style="left:638px;top:224px">Felinos</div>
          <div style="left:22px;top:240px">Linfocitos................:</div>
          <div style="left:324px;top:240px"><b>44</b></div>
          <div style="left:405px;top:240px"><b>3608</b></div>
          <div style="left:466px;top:240px">20 a 55                    20 a 55</div>
          <div style="left:22px;top:256px">Monocitos.................:</div>
          <div style="left:324px;top:256px"><b>0</b></div>
          <div style="left:405px;top:256px"><b>0</b></div>
          <div style="left:466px;top:256px">0 a 3                      0 a 3</div>
          <div style="left:22px;top:272px">Segmentados................:</div>
          <div style="left:324px;top:272px"><b>44</b></div>
          <div style="left:387px;top:272px"><b>3608</b></div>
          <div style="left:466px;top:272px">60 a 77                    35 a 75</div>
          <div style="left:22px;top:288px">Eosinofilos................:</div>
          <div style="left:324px;top:288px"><b>12</b></div>
          <div style="left:405px;top:288px"><b>984</b></div>
          <div style="left:466px;top:288px">2 a 10                     2 a 12</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Felina", "sex_raw": "F", "species_sex": "gata", "patient_age": "7 Meses"},
        )

        eos = next(row for row in rows if "Eosino" in row["nome"])
        self.assertEqual(eos["valor"], "12%")
        self.assertEqual(eos["referencia"], "2 a 12")
        self.assertEqual(eos["components"][0]["referencia"], "2 a 12")
        self.assertEqual(eos["components"][1]["referencia"], "n/d")

    def test_bitlab_hemograma_prefers_first_range_when_row_has_percent_and_absolute_values(self):
        html = """
        <html><body>
          <div style="left:22px;top:208px"><b>LEUCOGRAMA</b></div>
          <div style="left:484px;top:224px">Adultos</div>
          <div style="left:610px;top:224px">Filhotes</div>
          <div style="left:22px;top:272px">Segmentados................:</div>
          <div style="left:324px;top:272px"><b>61</b></div>
          <div style="left:378px;top:272px"><b>12261</b></div>
          <div style="left:466px;top:272px">60 a 77        3.000 a 11.500</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Canina", "sex_raw": "F", "species_sex": "cadela", "patient_age": "5 Anos"},
        )

        self.assertEqual(rows[0]["valor"], "61%")
        self.assertEqual(rows[0]["referencia"], "60 a 77")
        self.assertEqual(rows[0]["components"][1]["valor"], "12261/mm3")
        self.assertEqual(rows[0]["components"][1]["referencia"], "3.000 a 11.500")
        self.assertEqual(rows[0]["alerta"], "yellow")

    def test_bitlab_hemograma_selects_age_range_when_single_value_has_adult_and_puppy_columns(self):
        html = """
        <html><body>
          <div style="left:22px;top:208px"><b>LEUCOGRAMA</b></div>
          <div style="left:484px;top:224px">Adultos</div>
          <div style="left:610px;top:224px">Filhotes</div>
          <div style="left:22px;top:240px">Leucócitos por mm3.........:</div>
          <div style="left:283px;top:240px"><b>20.100</b></div>
          <div style="left:466px;top:240px">6.000 a 17.000</div>
          <div style="left:565px;top:240px">mm3</div>
          <div style="left:601px;top:240px">8.500 a 16.000mm3</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Canina", "sex_raw": "F", "species_sex": "cadela", "patient_age": "7 Meses"},
        )

        self.assertEqual(rows[0]["referencia"], "8.500 a 16.000mm3")

    def test_bitlab_hemograma_defaults_missing_age_to_adult_range(self):
        html = """
        <html><body>
          <div style="left:22px;top:208px"><b>LEUCOGRAMA</b></div>
          <div style="left:484px;top:224px">Adultos</div>
          <div style="left:610px;top:224px">Filhotes</div>
          <div style="left:22px;top:240px">Leucocitos por mm3.........:</div>
          <div style="left:283px;top:240px"><b>20.100</b></div>
          <div style="left:466px;top:240px">6.000 a 17.000</div>
          <div style="left:565px;top:240px">mm3</div>
          <div style="left:601px;top:240px">8.500 a 16.000mm3</div>
        </body></html>
        """.encode("latin-1")

        rows = BitlabConnector.parse_resultado(
            zlib.compress(html),
            {"species_raw": "Canina", "sex_raw": "F", "species_sex": "cadela", "patient_age": "n/d"},
        )

        self.assertEqual(rows[0]["referencia"], "6.000 a 17.000")


class StatePresentationTests(unittest.TestCase):
    def test_get_exames_uses_received_at_for_card_date_and_latest_release_for_group(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "received_at": "2026-03-31T16:55:17",
                        "itens": {
                            "I1": {"nome": "Hemograma", "status": "Pronto", "liberado_em": "2026-04-01T10:00:00"},
                            "I2": {"nome": "ALT", "status": "Pronto", "liberado_em": "2026-04-01T12:30:00"},
                        },
                    }
                }
            }

            groups = state.get_exames()

            self.assertEqual(groups[0]["date_display"], "31/03/2026")
            self.assertEqual(groups[0]["time_display"], "16:55")
            self.assertEqual(groups[0]["last_release_display"], "01/04 12:30")
            self.assertEqual(groups[0]["liberado_em_iso"], "2026-04-01T12:30:00")
        finally:
            state.snapshots = original_snapshots
            state._config = original_config

    def test_get_exames_exposes_patient_age_or_nd(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises"}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "patient_age": "7 Meses",
                        "itens": {
                            "I1": {"nome": "Hemograma", "status": "Pronto"},
                        },
                    },
                    "REQ-2": {
                        "label": "Mia - Tutor",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {"nome": "TGP", "status": "Pronto"},
                        },
                    },
                }
            }

            groups = state.get_exames()
            mapped = {group["record_id"]: group for group in groups}

            self.assertEqual(mapped["REQ-1"]["patient_age_display"], "7 meses")
            self.assertEqual(mapped["REQ-2"]["patient_age_display"], "n/d")
        finally:
            state.snapshots = original_snapshots
            state._config = original_config


class ResultTemplateRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        web_app.app.state.disable_auth = True
        cls.client = TestClient(web_app.app)

    @classmethod
    def tearDownClass(cls):
        web_app.app.state.disable_auth = False

    def test_partial_resultado_renders_compound_rows(self):
        original_snapshots = state.snapshots
        try:
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {
                                "nome": "Hemograma",
                                "status": "Pronto",
                                "item_id": "item-1",
                                "resultado": [
                                    {
                                        "nome": "Segmentados",
                                        "valor": "44%",
                                        "referencia": "35 a 75",
                                        "alerta": "yellow",
                                        "components": [
                                            {"valor": "44%", "referencia": "35 a 75", "alerta": None},
                                            {"valor": "3608/mm3", "referencia": "n/d", "alerta": "yellow"},
                                        ],
                                    }
                                ],
                            }
                        },
                    }
                }
            }

            response = self.client.get("/labmonitor/partials/resultado/item-1")

            self.assertEqual(response.status_code, 200)
            body = response.text
            self.assertIn("44%", body)
            self.assertIn("3608/mm", body)
            self.assertIn("35 a 75", body)
            self.assertIn("n/d", body)
        finally:
            state.snapshots = original_snapshots

    def test_exames_partial_renders_patient_age_meta(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises", "enabled": True}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "patient_age": "",
                        "itens": {
                            "I1": {"nome": "Hemograma", "status": "Pronto", "item_id": "item-1"},
                        },
                    }
                }
            }

            response = self.client.get("/labmonitor/partials/exames")

            self.assertEqual(response.status_code, 200)
            body = response.text
            self.assertIn("IDADE", body)
            self.assertIn("n/d", body)
        finally:
            state.snapshots = original_snapshots
            state._config = original_config

    def test_textual_result_modal_renders_sections(self):
        original_snapshots = state.snapshots
        try:
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {
                                "nome": "PCR Qualitativo",
                                "status": "Pronto",
                                "item_id": "item-text-1",
                                "report_text": "DADOS DO PACIENTE\nNome: Bidu\nDIAGNOSTICO\nNao detectado.\nMETODOLOGIA\nPCR em tempo real.",
                                "diagnosis_text": "Não detectado.",
                            }
                        },
                    }
                }
            }

            response = self.client.get("/labmonitor/partials/resultado-texto/item-text-1")

            self.assertEqual(response.status_code, 200)
            body = response.text
            self.assertIn("Laudo textual", body)
            self.assertIn("Diagnóstico", body)
            self.assertIn("<strong><u>", body)
            self.assertNotIn("DADOS DO PACIENTE", body)
        finally:
            state.snapshots = original_snapshots

    def test_partial_exames_supports_pagination_sentinel(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises", "enabled": True}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    f"REQ-{idx:02d}": {
                        "label": f"Paciente {idx} - Tutor {idx}",
                        "data": "2026-04-01",
                        "itens": {
                            "I1": {"nome": "Hemograma", "status": "Pronto", "item_id": f"item-{idx}"},
                        },
                    }
                    for idx in range(1, 25)
                }
            }

            response = self.client.get("/labmonitor/partials/exames")

            self.assertEqual(response.status_code, 200)
            body = response.text
            self.assertIn("Carregando mais exames", body)
            self.assertIn("offset=20", body)
        finally:
            state.snapshots = original_snapshots
            state._config = original_config

    def test_patient_history_partial_renders_series(self):
        original_snapshots = state.snapshots
        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises", "enabled": True}],
                "notifiers": [],
                "interval_minutes": 5,
            }
            state.snapshots = {
                "bitlab": {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-01",
                        "received_at": "2026-04-01T10:00:00",
                        "itens": {
                            "I1": {
                                "nome": "TGP",
                                "status": "Pronto",
                                "item_id": "item-1",
                                "resultado": [
                                    {"nome": "TGP", "valor": "40", "referencia": "10 a 80", "alerta": None}
                                ],
                            }
                        },
                    },
                    "REQ-2": {
                        "label": "Bidu - Tutor",
                        "data": "2026-04-02",
                        "received_at": "2026-04-02T10:00:00",
                        "itens": {
                            "I1": {
                                "nome": "TGP",
                                "status": "Pronto",
                                "item_id": "item-2",
                                "resultado": [
                                    {"nome": "TGP", "valor": "95", "referencia": "10 a 80", "alerta": "yellow"}
                                ],
                            }
                        },
                    },
                }
            }

            response = self.client.get("/labmonitor/partials/historico-paciente?patient_name=Bidu&tutor_name=Tutor")

            self.assertEqual(response.status_code, 200)
            body = response.text
            self.assertIn("Evolução histórica", body)
            self.assertIn("TGP", body)
            self.assertIn("95", body)
            self.assertIn("Atenção", body)
        finally:
            state.snapshots = original_snapshots
            state._config = original_config


if __name__ == "__main__":
    unittest.main()
