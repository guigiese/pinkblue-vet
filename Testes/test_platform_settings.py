import os
import unittest
from unittest.mock import patch

from pb_platform.settings import PlatformSettings


class PlatformSettingsTests(unittest.TestCase):
    def test_production_runtime_rejects_sqlite_database_url(self):
        settings = PlatformSettings()
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite:///tmp/pbv-test.sqlite3",
                "PB_DATABASE_URL": "",
            },
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                _ = settings.database_url


if __name__ == "__main__":
    unittest.main()
