import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pb_platform import storage as storage_module


class PlatformStoreTests(unittest.TestCase):
    def test_store_supports_users_sessions_thresholds_and_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            temp_db_url = f"sqlite:///{temp_path / 'pbv-test.sqlite3'}"
            missing_json = temp_path / "missing.json"

            with patch.dict(os.environ, {"DATABASE_URL": temp_db_url}, clear=False), patch.object(
                storage_module.settings, "master_email", "admin@test.local"
            ), patch.object(
                storage_module.settings, "master_password", "SenhaTemporaria123"
            ), patch.object(
                storage_module.settings, "master_force_change", False
            ), patch.object(
                storage_module, "CONFIG_FILE", missing_json
            ), patch.object(
                storage_module, "TELEGRAM_USERS_FILE", missing_json
            ):
                store = storage_module.PlatformStore()

                master = store.get_user_by_email("admin@test.local")
                self.assertIsNotNone(master)

                created = store.create_user(
                    email="tester@pinkbluevet.local",
                    password="SenhaTemporaria123",
                    role="operator",
                )
                self.assertEqual(created["role"], "operator")

                auth_user, code = store.authenticate_user("tester@pinkbluevet.local", "SenhaTemporaria123")
                self.assertEqual(code, "ok")
                self.assertIsNotNone(auth_user)

                token = store.create_session(auth_user["id"])
                session_user = store.get_user_for_session(token)
                self.assertEqual(session_user["email"], "tester@pinkbluevet.local")

                store.save_runtime_config({"interval_minutes": 7, "notification_settings": {"events": {}}})
                self.assertEqual(store.load_runtime_config()["interval_minutes"], 7)

                store.save_global_thresholds(warning_multiplier=1.05, critical_multiplier=1.3)
                defaults = store.get_global_thresholds()
                self.assertEqual(defaults["warning_multiplier"], 1.05)
                self.assertEqual(defaults["critical_multiplier"], 1.3)

                store.upsert_exam_threshold(
                    "Hemograma Veterinario",
                    warning_multiplier=1.1,
                    critical_multiplier=1.35,
                    updated_by="tester@pinkbluevet.local",
                )
                threshold = store.get_exam_threshold("Hemograma Veterinario")
                self.assertEqual(threshold["warning_multiplier"], 1.1)
                self.assertEqual(threshold["critical_multiplier"], 1.35)

                perms = store.get_role_permissions()
                self.assertTrue(perms["admin"]["manage_users"])
                store.save_role_permissions(
                    "viewer",
                    {
                        "platform_access": True,
                        "labmonitor_access": True,
                        "manage_labmonitor": False,
                        "ops_tools": True,
                        "manage_users": False,
                        "plantao_access": False,
                        "manage_plantao": False,
                    },
                )
                perms = store.get_role_permissions()
                self.assertTrue(perms["viewer"]["ops_tools"])

                store.save_lab_sync_state("bitlab", {"history_complete": False, "next_backfill_end": "2026-03-01"})
                sync_state = store.get_lab_sync_state("bitlab")
                self.assertEqual(sync_state["next_backfill_end"], "2026-03-01")

                self.assertTrue(store.remember_notification_event("sig-1", "external"))
                self.assertFalse(store.remember_notification_event("sig-1", "external"))


if __name__ == "__main__":
    unittest.main()
