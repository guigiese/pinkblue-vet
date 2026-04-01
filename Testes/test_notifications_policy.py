import unittest

import core


class NotificationPolicyTests(unittest.TestCase):
    def setUp(self):
        core._EXTERNAL_EVENT_CACHE.clear()

    def test_new_record_generates_one_received_event(self):
        anterior = {}
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {"nome": "Hemograma", "status": "Recebido"},
                    "I2": {"nome": "ALT", "status": "Recebido"},
                },
            }
        }

        internal, external = core.build_notification_plan("bitlab", "BitLab", anterior, atual)

        self.assertEqual(len(internal), 1)
        self.assertEqual(len(external), 1)
        self.assertEqual(external[0]["kind"], "received")
        self.assertIn("Exame recebido no laboratorio", external[0]["message"])

    def test_ready_items_are_grouped_by_record(self):
        anterior = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {"nome": "Hemograma", "status": "Recebido"},
                    "I2": {"nome": "ALT", "status": "Em Andamento"},
                    "I3": {"nome": "Ureia", "status": "Analisando"},
                },
            }
        }
        atual = {
            "REQ-1": {
                "label": "Bidu - Tutor",
                "data": "2026-04-01",
                "itens": {
                    "I1": {"nome": "Hemograma", "status": "Pronto"},
                    "I2": {"nome": "ALT", "status": "Pronto"},
                    "I3": {"nome": "Ureia", "status": "Pronto"},
                },
            }
        }

        internal, external = core.build_notification_plan("bitlab", "BitLab", anterior, atual)

        self.assertEqual(len(internal), 3)
        self.assertEqual(len(external), 1)
        self.assertEqual(external[0]["kind"], "completed")
        self.assertIn("Hemograma", external[0]["message"])
        self.assertIn("ALT", external[0]["message"])
        self.assertIn("Ureia", external[0]["message"])

    def test_external_signature_deduplicates_repeated_dispatch(self):
        signature = "abc123"

        self.assertTrue(core._should_send_external_event(signature))
        self.assertFalse(core._should_send_external_event(signature))


if __name__ == "__main__":
    unittest.main()
