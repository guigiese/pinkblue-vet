import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.app import app
from web.state import state


class DashboardRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.state.disable_auth = True
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.state.disable_auth = False

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
        self.assertIn("pb-signals pb-signals--right", body)
        self.assertNotIn("pb-species-badge", body)

    def test_ultimos_liberados_links_with_clean_patient_query_and_without_footer_noise(self):
        fake_groups = [
            {
                "paciente": "PIDA - JINGWEI DU PROP: JINGWEI DU",
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
        self.assertIn('/labmonitor/exames?q=PIDA"', body)
        self.assertNotIn("PROP%3A", body)
        self.assertNotIn("pb-rail-palette--vivid", body)
        self.assertNotIn("crit-red", body)
        self.assertNotIn("min-w-[7.4rem]", body)

    def test_lab_counts_cards_link_to_filtered_exams(self):
        fake_counts = {
            "bitlab": {
                "name": "Bioanálises",
                "pronto": 5,
                "parcial": 2,
                "andamento": 3,
                "total": 10,
                "pending": 5,
                "overdue": 1,
                "oldest_pending_days": 9,
                "released_last_24h": 4,
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
        self.assertNotIn("Saude operacional", body)
        self.assertNotIn("Liberados 24h", body)
        self.assertNotIn("progress-wrap", body)
        self.assertIn("grid grid-cols-2 gap-2 xl:grid-cols-4 sm:gap-3", body)
        self.assertIn("min-w-0 bg-white rounded-xl", body)

    def test_exames_partial_keeps_right_aligned_signals_and_chevron(self):
        fake_groups = [
            {
                "patient_name": "PIDA",
                "tutor_name": "Jingwei Du",
                "species_sex": "gata",
                "lab": "Bioanálises",
                "date_display": "03/04/2026",
                "time_display": "10:45",
                "status_geral": "Parcial",
                "ready_ratio_text": "2/4 prontos",
                "days_label": None,
                "days_stale": False,
                "criticality": "yellow",
                "alerta_geral": "yellow",
                "protocol": "08-00000001",
                "portal_url": "https://example.com",
                "last_release_display": None,
                "patient_age_display": "n/d",
                "breed": "",
                "items_view": [],
            }
        ]

        with patch.object(state, "get_exames", return_value=fake_groups):
            response = self.client.get("/labmonitor/partials/exames")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("pb-chevron", body)
        self.assertIn("pb-signals--right", body)

    def test_exames_page_uses_mobile_safe_filter_layout(self):
        response = self.client.get("/labmonitor/exames")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('class="grid gap-2 mb-5 sm:flex sm:flex-wrap"', body)
        self.assertIn('name="lab" class="w-full min-w-0 border rounded-lg px-3 py-2 text-sm bg-white sm:w-auto"', body)
        self.assertIn('name="status" class="w-full min-w-0 border rounded-lg px-3 py-2 text-sm bg-white sm:w-auto"', body)

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

    def test_notificacoes_page_renders_event_templates_and_preview(self):
        response = self.client.get("/labmonitor/notificacoes")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("Template da mensagem", body)
        self.assertIn("Recebimento", body)
        self.assertIn("Conclusão em lote", body)
        self.assertIn("{lab_name}", body)
        self.assertIn("Salvar ajustes", body)
        self.assertIn("overflow-wrap:anywhere", body)
        self.assertIn("break-words", body)

    def test_telegram_users_partial_stacks_action_on_mobile(self):
        fake_users = [
            {
                "name": "Guilherme",
                "username": "guigiese",
                "chat_id": "123456",
                "subscribed_at": "03/04/2026 00:52",
            }
        ]

        with patch("web.app.get_users", return_value=fake_users):
            response = self.client.get("/labmonitor/partials/telegram-users")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("sm:flex-row", body)
        self.assertIn("w-full sm:w-auto", body)

    def test_test_lab_prefers_light_connection_check(self):
        class FakeConnector:
            def test_connection(self):
                return "✓ Conexão OK — teste leve"

            def snapshot(self):
                raise AssertionError("snapshot should not be called")

        original_config = state._config
        try:
            state._config = {
                "labs": [{"id": "bitlab", "name": "Bioanálises", "connector": "bitlab", "enabled": True}],
                "notifiers": [],
            }
            with patch.dict("web.app.CONNECTORS", {"bitlab": FakeConnector}, clear=False):
                response = self.client.post("/labmonitor/labs/bitlab/test")
        finally:
            state._config = original_config

        self.assertEqual(response.status_code, 200)
        self.assertIn("teste leve", response.text)

    def test_test_notifier_prefers_light_send_test(self):
        class FakeNotifier:
            def send_test(self, message: str):
                self.message = message

            def enviar(self, message: str):
                raise AssertionError("enviar should not be called")

        original_config = state._config
        try:
            state._config = {
                "labs": [],
                "notifiers": [{"id": "telegram", "type": "telegram", "enabled": True}],
            }
            with patch.dict("web.app.NOTIFIERS", {"telegram": FakeNotifier}, clear=False):
                response = self.client.post("/labmonitor/canais/telegram/test")
        finally:
            state._config = original_config

        self.assertEqual(response.status_code, 200)
        self.assertIn("Mensagem enviada", response.text)


if __name__ == "__main__":
    unittest.main()
