import unittest

import core
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


if __name__ == "__main__":
    unittest.main()
