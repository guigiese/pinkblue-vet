from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class PlatformSettings:
    app_name: str = "PinkBlue Vet"
    module_name: str = "Lab Monitor"
    data_dir: Path = Path(
        os.environ.get("PB_DATA_DIR")
        or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        or (Path(__file__).resolve().parent.parent / "runtime-data")
    )
    db_filename: str = os.environ.get("PB_DB_FILENAME", "pinkbluevet.sqlite3")
    auth_enabled: bool = _bool_env("PB_AUTH_ENABLED", True)
    session_cookie_name: str = os.environ.get("PB_SESSION_COOKIE", "pbv_session")
    session_ttl_days: int = int(os.environ.get("PB_SESSION_TTL_DAYS", "14"))
    master_email: str = os.environ.get("PB_MASTER_EMAIL", "guigiese@gmail.com")
    master_password: str = os.environ.get("PB_MASTER_PASSWORD", "PinkBlueVet@2026")
    master_force_change: bool = _bool_env("PB_MASTER_FORCE_CHANGE", True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename


settings = PlatformSettings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
