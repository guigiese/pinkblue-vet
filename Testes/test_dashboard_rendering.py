import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.app import app
from web.state import state


class DashboardRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_ultimos_liberados_uses_exam_card_language(self):
        fake_groups = [
            {
                "paciente": "PIDA",
                "patient_name": "PIDA",
                "tutor_name": "Jingwei Du",
                "species_sex": "gata",
                "alerta_geral": "red",
                "status_geral": "Parcial",
                "items_ready": 2,
                "items_total": 4,
                "ready_ratio_text": "2/4 prontos",
                "last_release_date_display": "02/04/2026",
                "last_release_time_display": "17:42",
                "date_display": "01/04/2026",
                "data": "01/04/2026",
                "lab": "Bioanálises",
                "record_id": "08-00000001",
            }
        ]

        with patch.object(state, "get_ultimos_liberados", return_value=fake_groups):
            response = self.client.get("/labmonitor/partials/ultimos_liberados")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("pb-group", body)
        self.assertIn("02/04/2026", body)
        self.assertIn("17:42", body)
        self.assertIn("Bioanálises", body)
        self.assertIn("2/4 prontos", body)
        self.assertIn("PARCIAL", body)
        self.assertIn("pb-species-symbol is-inline", body)
        self.assertNotIn("pb-species-badge", body)

    def test_ultimos_liberados_links_with_clean_patient_query(self):
        fake_groups = [
            {
                "paciente": "PIDA - JINGWEI DU PROP: JINGWEI DU",
                "patient_name": "PIDA",
                "tutor_name": "Jingwei Du",
                "species_sex": "gata",
                "alerta_geral": "red",
                "status_geral": "Pronto",
                "items_ready": 6,
                "items_total": 6,
                "ready_ratio_text": "6/6 prontos",
                "last_release_date_display": "02/04/2026",
                "last_release_time_display": "17:42",
                "date_display": "01/04/2026",
                "data": "01/04/2026",
                "lab": "Bioanálises",
                "record_id": "08-00000001",
            }
        ]

        with patch.object(state, "get_ultimos_liberados", return_value=fake_groups):
            response = self.client.get("/labmonitor/partials/ultimos_liberados")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('/labmonitor/exames?q=PIDA"', body)
        self.assertNotIn("PROP%3A", body)
        self.assertNotIn("crit-red", body)
        self.assertNotIn("pb-rail-palette--vivid", body)

    def test_lab_counts_cards_link_to_filtered_exams(self):
        fake_counts = {
            "bitlab": {
                "name": "Bioanálises",
                "pronto": 5,
                "parcial": 2,
                "andamento": 3,
                "total": 10,
                "last_check": "02/04/2026 18:00",
                "checking": False,
                "error": "",
                "enabled": True,
            }
        }

        with patch.object(state, "get_lab_counts", return_value=fake_counts):
            response = self.client.get("/labmonitor/partials/lab_counts")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('id="card-pronto"', body)
        self.assertIn('data-status="Pronto"', body)
        self.assertIn("Abrir lista filtrada", body)
        self.assertIn("EM CURSO", body)
        self.assertIn("updateCardLinks", body)

    def test_labs_page_omits_connector_prefix(self):
        original_config = state._config
        original_last_check = state.last_check
        original_last_error = state.last_error
        try:
            state._config = {
                "labs": [
                    {
                        "id": "bitlab",
                        "name": "Bioanálises",
                        "connector": "bitlab",
                        "enabled": True,
                    }
                ],
                "notifiers": [],
            }
            state.last_check = {}
            state.last_error = {}

            response = self.client.get("/labmonitor/labs")
        finally:
            state._config = original_config
            state.last_check = original_last_check
            state.last_error = original_last_error

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("Bioanálises", body)
        self.assertIn(">bitlab<", body)
        self.assertNotIn("conector bitlab", body)


if __name__ == "__main__":
    unittest.main()
