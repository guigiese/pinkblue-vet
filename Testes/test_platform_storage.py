import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pb_platform import storage as storage_module


class PlatformStoreTests(unittest.TestCase):
    def test_store_supports_users_sessions_thresholds_and_runtime_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            temp_db = "pbv-test.sqlite3"
            missing_json = temp_path / "missing.json"

            with patch.object(storage_module.settings, "data_dir", temp_path), patch.object(
                storage_module.settings,
                "db_filename",
                temp_db,
            ), patch.object(storage_module, "CONFIG_FILE", missing_json), patch.object(
                storage_module,
                "TELEGRAM_USERS_FILE",
                missing_json,
            ):
                store = storage_module.PlatformStore()

                master = store.get_user_by_email(storage_module.settings.master_email)
                self.assertIsNotNone(master)

                created = store.create_user(
                    email="tester@pinkbluevet.local",
                    password="SenhaTemporaria123",
                    role="operator",
                )
                self.assertEqual(created["role"], "operator")

                auth_user = store.authenticate_user("tester@pinkbluevet.local", "SenhaTemporaria123")
                self.assertIsNotNone(auth_user)

                token = store.create_session(auth_user["id"])
                session_user = store.get_user_for_session(token)
                self.assertEqual(session_user["email"], "tester@pinkbluevet.local")

                store.save_runtime_config({"interval_minutes": 7, "notification_settings": {"events": {}}})
                self.assertEqual(store.load_runtime_config()["interval_minutes"], 7)

                store.upsert_exam_threshold(
                    "Hemograma Veterinário",
                    warning_multiplier=1.1,
                    critical_multiplier=1.35,
                    updated_by="tester@pinkbluevet.local",
                )
                threshold = store.get_exam_threshold("Hemograma Veterinário")
                self.assertEqual(threshold["warning_multiplier"], 1.1)
                self.assertEqual(threshold["critical_multiplier"], 1.35)

                self.assertTrue(store.remember_notification_event("sig-1", "external"))
                self.assertFalse(store.remember_notification_event("sig-1", "external"))


if __name__ == "__main__":
    unittest.main()
