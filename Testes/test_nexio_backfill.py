import unittest

import core
from modules.lab_monitor.labs.nexio import NexioConnector


class NexioBackfillTests(unittest.TestCase):
    def test_snapshot_between_merges_reception_and_release_ranges(self):
        connector = NexioConnector()
        connector._login = lambda: object()

        calls = []

        def fake_busca(session, *, data_recepcao="", data_liberacao=""):
            calls.append((data_recepcao, data_liberacao))
            if data_recepcao:
                return [
                    {
                        "numero": "AP000184/26",
                        "paciente": "LINDA",
                        "proprietario": "ANELISE",
                        "data_prometida": "27/03/26",
                        "data_liberacao": "26/03/26",
                        "status": "Arquivo morto",
                        "exame_id": "1",
                    }
                ]
            return [
                {
                    "numero": "AP000184/26",
                    "paciente": "LINDA",
                    "proprietario": "ANELISE",
                    "data_prometida": "27/03/26",
                    "data_liberacao": "26/03/26",
                    "status": "Arquivo morto",
                    "exame_id": "1",
                },
                {
                    "numero": "AP000140/26",
                    "paciente": "MOCO",
                    "proprietario": "TUTOR",
                    "data_prometida": "11/03/26",
                    "data_liberacao": "13/03/26",
                    "status": "Arquivo morto",
                    "exame_id": "2",
                },
            ]

        connector._buscar_exames = fake_busca

        snapshot = connector.snapshot_between("2026-03-01", "2026-03-31")

        self.assertEqual(
            calls,
            [
                ("01/03/2026 - 31/03/2026", ""),
                ("", "01/03/2026 - 31/03/2026"),
            ],
        )
        self.assertEqual(set(snapshot.keys()), {"AP000184/26", "AP000140/26"})
        self.assertEqual(snapshot["AP000184/26"]["portal_id"], "1")

    def test_historical_backfill_primes_empty_snapshot_before_windows(self):
        class FakeLab:
            lab_id = "fake"
            lab_name = "Fake"

            def snapshot(self):
                return {
                    "REQ-1": {
                        "label": "Bidu - Tutor",
                        "data": "2026-03-20",
                        "itens": {"I1": {"nome": "Hemograma", "status": "Pronto"}},
                    }
                }

            def snapshot_between(self, start_date, end_date):
                return {
                    "REQ-0": {
                        "label": "Bidu - Tutor",
                        "data": "2026-02-10",
                        "itens": {"I0": {"nome": "Hemograma", "status": "Pronto"}},
                    }
                }

        class FakeState:
            def __init__(self):
                self.config = {"labs": [{"id": "fake", "connector": "fake", "enabled": True}]}
                self.snapshots = {}
                self.saved = 0

            def save_lab_runtime(self, lab_id):
                self.saved += 1

        state = FakeState()
        original = core.CONNECTORS.get("fake")
        original_sync = core.store.get_lab_sync_state("fake")
        try:
            core.CONNECTORS["fake"] = FakeLab
            core.store.save_lab_sync_state("fake", {})
            summary = core.run_historical_backfill(state, max_windows_per_lab=1)
        finally:
            if original is None:
                core.CONNECTORS.pop("fake", None)
            else:
                core.CONNECTORS["fake"] = original
            core.store.save_lab_sync_state("fake", original_sync)

        self.assertIn("fake", summary)
        self.assertEqual(summary["fake"]["windows"], 1)
        self.assertGreaterEqual(state.saved, 1)
        self.assertEqual(set(state.snapshots["fake"].keys()), {"REQ-1", "REQ-0"})
