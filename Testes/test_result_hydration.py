import unittest
import zlib

import core
from labs.bitlab import BitlabConnector
from labs.nexio import NexioConnector
from web import app as web_app
from web.state import state


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

        self.assertEqual(rows[0]["valor"], "44")
        self.assertEqual(rows[0]["referencia"], "35 a 75")

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

        self.assertEqual(rows[0]["valor"], "61")
        self.assertEqual(rows[0]["referencia"], "60 a 77")

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


if __name__ == "__main__":
    unittest.main()
