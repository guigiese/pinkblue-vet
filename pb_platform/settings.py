from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("postgresql+psycopg2://") or url.startswith("sqlite:///"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    return url


_load_dotenv(ROOT / ".env")


@dataclass(slots=True)
class PlatformSettings:
    app_name: str = "PinkBlue Vet"
    data_dir: Path = Path(
        os.environ.get("PB_DATA_DIR")
        or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        or (ROOT / "runtime-data")
    )
    legacy_db_filename: str = os.environ.get("PB_DB_FILENAME", "pinkbluevet.sqlite3")
    auth_enabled: bool = _bool_env("PB_AUTH_ENABLED", True)
    session_cookie_name: str = os.environ.get("PB_SESSION_COOKIE", "pbv_session")
    session_ttl_days: int = int(os.environ.get("PB_SESSION_TTL_DAYS", "14"))
    csrf_secret: str = os.environ.get("PB_CSRF_SECRET", "")
    master_email: str = os.environ.get("PB_MASTER_EMAIL", "").strip().lower()
    master_password: str = os.environ.get("PB_MASTER_PASSWORD", "")
    master_force_change: bool = _bool_env("PB_MASTER_FORCE_CHANGE", False)
    local_dev_database_url: str = os.environ.get("PB_DEV_DATABASE_URL", "")

    @property
    def legacy_db_path(self) -> Path:
        return self.data_dir / self.legacy_db_filename

    @property
    def database_url(self) -> str:
        explicit = _normalize_database_url(
            os.environ.get("DATABASE_URL") or os.environ.get("PB_DATABASE_URL") or ""
        )
        db_url = explicit or _normalize_database_url(self.local_dev_database_url)
        if db_url:
            if self.app_env == "production" and db_url.startswith("sqlite"):
                raise RuntimeError(
                    "SQLite nao e permitido no runtime oficial de producao. "
                    "Configure PostgreSQL em DATABASE_URL/PB_DATABASE_URL."
                )
            return db_url
        raise RuntimeError(
            "DATABASE_URL/PB_DATABASE_URL ou PB_DEV_DATABASE_URL nao configurados. "
            "O runtime oficial da plataforma agora exige PostgreSQL; SQLite deve ser usado "
            "apenas via URL explicita em testes ou CI efemero."
        )

    @property
    def has_bootstrap_master(self) -> bool:
        return bool(self.master_email and self.master_password)

    @property
    def app_env(self) -> str:
        """Retorna 'development' em dev local, 'production' em prod."""
        return os.environ.get("APP_ENV", os.environ.get("PB_ENV", "development")).lower()

    @property
    def is_dev(self) -> bool:
        return self.app_env != "production"


settings = PlatformSettings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
