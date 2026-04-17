from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Float, Integer, MetaData, Table, Text, create_engine, event, inspect, text
from sqlalchemy.pool import NullPool

from .security import hash_password, token_hash, verify_password
from .settings import settings

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
TELEGRAM_USERS_FILE = ROOT / "telegram_users.json"

ALL_PERMISSIONS = [
    "platform_access",
    "labmonitor_access",
    "manage_labmonitor",
    # Sub-permissões granulares do Lab Monitor (implicadas por manage_labmonitor)
    "manage_labmonitor_labs",
    "manage_labmonitor_settings",
    "ops_tools",
    "manage_users",
    "plantao_access",
    "manage_plantao",
    # Sub-permissões granulares do Plantão (implicadas por manage_plantao)
    "plantao_gerir_escalas",
    "plantao_aprovar_candidaturas",
    "plantao_aprovar_cadastros",
    "plantao_ver_relatorios",
]

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {permission: True for permission in ALL_PERMISSIONS},
    "operator": {
        "platform_access": True,
        "labmonitor_access": True,
        "manage_labmonitor": True,
        "manage_labmonitor_labs": True,
        "manage_labmonitor_settings": True,
        "ops_tools": True,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": True,
        "plantao_gerir_escalas": True,
        "plantao_aprovar_candidaturas": True,
        "plantao_aprovar_cadastros": True,
        "plantao_ver_relatorios": True,
    },
    "viewer": {
        "platform_access": True,
        "labmonitor_access": True,
        "manage_labmonitor": False,
        "manage_labmonitor_labs": False,
        "manage_labmonitor_settings": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": False,
        "manage_plantao": False,
        "plantao_gerir_escalas": False,
        "plantao_aprovar_candidaturas": False,
        "plantao_aprovar_cadastros": False,
        "plantao_ver_relatorios": False,
    },
    "veterinario": {
        "platform_access": False,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "manage_labmonitor_labs": False,
        "manage_labmonitor_settings": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": False,
        "plantao_gerir_escalas": False,
        "plantao_aprovar_candidaturas": False,
        "plantao_aprovar_cadastros": False,
        "plantao_ver_relatorios": False,
    },
    "auxiliar": {
        "platform_access": False,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "manage_labmonitor_labs": False,
        "manage_labmonitor_settings": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": False,
        "plantao_gerir_escalas": False,
        "plantao_aprovar_candidaturas": False,
        "plantao_aprovar_cadastros": False,
        "plantao_ver_relatorios": False,
    },
    "colaborador": {
        "platform_access": False,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "manage_labmonitor_labs": False,
        "manage_labmonitor_settings": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": False,
        "manage_plantao": False,
        "plantao_gerir_escalas": False,
        "plantao_aprovar_candidaturas": False,
        "plantao_aprovar_cadastros": False,
        "plantao_ver_relatorios": False,
    },
}

EXTERNAL_ROLES = {"veterinario", "auxiliar", "colaborador"}
INTERNAL_ROLES = {"admin", "operator", "viewer"}

ROLE_LABELS: dict[str, str] = {
    "admin": "Administrador",
    "operator": "Operador",
    "viewer": "Visualizador",
    "veterinario": "Veterinário Plantonista",
    "auxiliar": "Auxiliar Veterinário",
    "colaborador": "Colaborador",
}

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

DEFAULT_GLOBAL_THRESHOLDS: dict[str, float] = {
    "warning_multiplier": 1.0,
    "critical_multiplier": 1.2,
}

metadata = MetaData()

_t_app_kv = Table(
    "app_kv",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

_t_users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("role", Text, nullable=False, server_default="viewer"),
    Column("is_active", Integer, nullable=False, server_default="1"),
    Column("force_password_change", Integer, nullable=False, server_default="0"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("nome", Text, nullable=False, server_default=""),
    Column("telefone", Text, nullable=False, server_default=""),
    Column("crmv", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False, server_default="ativo"),
    Column("tentativas_login", Integer, nullable=False, server_default="0"),
    Column("bloqueado_ate", Text, nullable=True),
    Column("profile_id", Integer, nullable=True),
)

_t_user_sessions = Table(
    "user_sessions",
    metadata,
    Column("token_hash", Text, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
)

_t_telegram_subscriptions = Table(
    "telegram_subscriptions",
    metadata,
    Column("chat_id", Text, primary_key=True),
    Column("name", Text, nullable=False, server_default=""),
    Column("username", Text, nullable=False, server_default=""),
    Column("subscribed_at", Text, nullable=False, server_default=""),
)

_t_lab_snapshots = Table(
    "lab_snapshots",
    metadata,
    Column("lab_id", Text, primary_key=True),
    Column("snapshot_json", Text, nullable=False),
    Column("last_check", Text, nullable=False, server_default=""),
    Column("last_error", Text, nullable=False, server_default=""),
    Column("updated_at", Text, nullable=False),
)

_t_notification_event_log = Table(
    "notification_event_log",
    metadata,
    Column("signature", Text, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

_t_exam_thresholds = Table(
    "exam_thresholds",
    metadata,
    Column("exam_slug", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("warning_multiplier", Float, nullable=False),
    Column("critical_multiplier", Float, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("updated_by", Text, nullable=False, server_default=""),
)

_t_sync_runs = Table(
    "sync_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lab_id", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("finished_at", Text, nullable=True),
    Column("success", Integer, nullable=True),
    Column("error", Text, nullable=True),
)

_t_module_logs = Table(
    "module_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module", Text, nullable=False),
    Column("level", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("payload_json", Text, nullable=True),
    Column("created_at", Text, nullable=False),
)

_t_platform_profiles = Table(
    "platform_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nome", Text, nullable=False),
    Column("descricao", Text, nullable=False, server_default=""),
    Column("base_role", Text, nullable=False),
    Column("permissions_json", Text, nullable=False, server_default="{}"),
    Column("is_system", Integer, nullable=False, server_default="0"),
    Column("criado_em", Text, nullable=False),
    Column("alterado_em", Text, nullable=False),
)


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _slugify_exam(text_: str) -> str:
    import re
    import unicodedata

    normalized = "".join(
        c for c in unicodedata.normalize("NFD", text_ or "") if unicodedata.category(c) != "Mn"
    ).lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "exam"


class PlatformStore:
    def __init__(self):
        self._lock = threading.RLock()
        db_url = settings.database_url
        is_sqlite = db_url.startswith("sqlite")
        connect_args: dict[str, Any] = {}
        if is_sqlite:
            connect_args["check_same_thread"] = False
            self._engine = create_engine(db_url, connect_args=connect_args, poolclass=NullPool)
        else:
            self._engine = create_engine(db_url, pool_pre_ping=True)

        if is_sqlite:

            @event.listens_for(self._engine, "connect")
            def _set_sqlite_pragmas(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

        self.init_db()
        self.bootstrap_legacy_runtime()
        self.ensure_master_user()

    @property
    def engine(self):
        return self._engine

    def init_db(self) -> None:
        metadata.create_all(self._engine)
        self._ensure_schema_compatibility()

    def _ensure_schema_compatibility(self) -> None:
        inspector = inspect(self._engine)
        if "users" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("users")}
        missing = {
            "nome": "TEXT NOT NULL DEFAULT ''",
            "telefone": "TEXT NOT NULL DEFAULT ''",
            "crmv": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'ativo'",
            "tentativas_login": "INTEGER NOT NULL DEFAULT 0",
            "bloqueado_ate": "TEXT",
            "profile_id": "INTEGER",
        }
        with self._engine.begin() as conn:
            for column_name, ddl in missing.items():
                if column_name in columns:
                    continue
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {ddl}"))
        self._seed_system_profiles()

    def bootstrap_legacy_runtime(self) -> None:
        if self.load_runtime_config() is None and CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = None
            if isinstance(data, dict):
                self.save_runtime_config(data)

        if self.list_telegram_users():
            return
        if TELEGRAM_USERS_FILE.exists():
            try:
                payload = json.loads(TELEGRAM_USERS_FILE.read_text(encoding="utf-8"))
            except Exception:
                payload = []
            for entry in payload:
                if isinstance(entry, str):
                    self.add_telegram_user(entry)
                elif isinstance(entry, dict) and entry.get("chat_id"):
                    self.add_telegram_user(
                        str(entry["chat_id"]),
                        name=entry.get("name", ""),
                        username=entry.get("username", ""),
                        subscribed_at=entry.get("subscribed_at", ""),
                    )

    def load_json_setting(self, key: str, default: Any = None) -> Any:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM app_kv WHERE key = :key"),
                {"key": key},
            ).mappings().first()
        if not row:
            return default
        return _json_loads(row["value"], default)

    def save_json_setting(self, key: str, value: Any) -> None:
        payload = _json_dumps(value)
        now = _utcnow()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO app_kv(key, value, updated_at) VALUES (:key, :value, :updated_at) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
                ),
                {"key": key, "value": payload, "updated_at": now},
            )

    def load_runtime_config(self) -> dict | None:
        return self.load_json_setting("lab_monitor.runtime_config")

    def save_runtime_config(self, config: dict) -> None:
        self.save_json_setting("lab_monitor.runtime_config", config)

    def list_roles(self) -> list[str]:
        return list(DEFAULT_ROLE_PERMISSIONS.keys())

    def get_role_permissions(self) -> dict[str, dict[str, bool]]:
        current = self.load_json_setting("platform.role_permissions", {}) or {}
        result: dict[str, dict[str, bool]] = {}
        for role, defaults in DEFAULT_ROLE_PERMISSIONS.items():
            persisted = current.get(role) if isinstance(current, dict) else {}
            result[role] = {
                permission: bool((persisted or {}).get(permission, default))
                for permission, default in defaults.items()
            }
        return result

    def save_role_permissions(self, role: str, permissions: dict[str, bool]) -> None:
        role = role.strip().lower()
        if role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"role desconhecido: {role}")
        matrix = self.get_role_permissions()
        matrix[role] = {permission: bool(permissions.get(permission, False)) for permission in ALL_PERMISSIONS}
        if role == "admin":
            matrix[role] = {permission: True for permission in ALL_PERMISSIONS}
        self.save_json_setting("platform.role_permissions", matrix)

    def get_user_permissions(self, user: dict | None) -> dict[str, bool]:
        """Resolve permissões com cascata: role-default → perfil → permissões individuais."""
        if not user:
            return {permission: False for permission in ALL_PERMISSIONS}
        role = (user.get("role") or "viewer").strip().lower()
        # 1. Base: permissões do role padrão
        matrix = self.get_role_permissions()
        resolved = dict(matrix.get(role) or {})
        # 2. Sobrescreve com permissões do perfil customizado (se houver)
        profile_id = user.get("profile_id")
        if profile_id:
            profile = self.get_profile(profile_id)
            if profile and not profile["is_system"]:
                for perm, val in profile["permissions"].items():
                    resolved[perm] = bool(val)
        result = {permission: bool(resolved.get(permission, False)) for permission in ALL_PERMISSIONS}
        # manage_plantao implica plantao_access e todas as sub-permissões granulares do módulo Plantão
        if result.get("manage_plantao"):
            result["plantao_access"] = True
            for sub in ("plantao_gerir_escalas", "plantao_aprovar_candidaturas", "plantao_aprovar_cadastros", "plantao_ver_relatorios"):
                result[sub] = True
        return result

    def get_global_thresholds(self) -> dict[str, float]:
        current = self.load_json_setting("lab_monitor.global_thresholds", {}) or {}
        try:
            warning = float(
                current.get("warning_multiplier", DEFAULT_GLOBAL_THRESHOLDS["warning_multiplier"])
            )
        except Exception:
            warning = DEFAULT_GLOBAL_THRESHOLDS["warning_multiplier"]
        try:
            critical = float(
                current.get("critical_multiplier", DEFAULT_GLOBAL_THRESHOLDS["critical_multiplier"])
            )
        except Exception:
            critical = DEFAULT_GLOBAL_THRESHOLDS["critical_multiplier"]
        critical = max(critical, warning)
        return {"warning_multiplier": warning, "critical_multiplier": critical}

    def save_global_thresholds(self, *, warning_multiplier: float, critical_multiplier: float) -> None:
        self.save_json_setting(
            "lab_monitor.global_thresholds",
            {
                "warning_multiplier": float(warning_multiplier),
                "critical_multiplier": float(max(critical_multiplier, warning_multiplier)),
            },
        )

    def get_lab_sync_state(self, lab_id: str) -> dict:
        return self.load_json_setting(f"lab_monitor.sync_state.{lab_id}", {}) or {}

    def save_lab_sync_state(self, lab_id: str, payload: dict) -> None:
        self.save_json_setting(f"lab_monitor.sync_state.{lab_id}", payload or {})

    def load_lab_runtime(self) -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
        snapshots: dict[str, dict] = {}
        last_check: dict[str, str] = {}
        last_error: dict[str, str] = {}
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT lab_id, snapshot_json, last_check, last_error FROM lab_snapshots")
            ).mappings().all()
        for row in rows:
            snapshots[row["lab_id"]] = _json_loads(row["snapshot_json"], {})
            if row["last_check"]:
                last_check[row["lab_id"]] = row["last_check"]
            if row["last_error"]:
                last_error[row["lab_id"]] = row["last_error"]
        return snapshots, last_check, last_error

    def save_lab_snapshot(self, lab_id: str, snapshot: dict, *, last_check: str = "", last_error: str = "") -> None:
        now = _utcnow()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO lab_snapshots(lab_id, snapshot_json, last_check, last_error, updated_at) "
                    "VALUES (:lab_id, :snapshot_json, :last_check, :last_error, :updated_at) "
                    "ON CONFLICT(lab_id) DO UPDATE SET "
                    "snapshot_json=excluded.snapshot_json, "
                    "last_check=excluded.last_check, "
                    "last_error=excluded.last_error, "
                    "updated_at=excluded.updated_at"
                ),
                {
                    "lab_id": lab_id,
                    "snapshot_json": _json_dumps(snapshot),
                    "last_check": last_check,
                    "last_error": last_error,
                    "updated_at": now,
                },
            )

    def remember_notification_event(self, signature: str, kind: str, ttl_hours: int = 72) -> bool:
        cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        now = _utcnow()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM notification_event_log WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            exists = conn.execute(
                text("SELECT 1 FROM notification_event_log WHERE signature = :signature"),
                {"signature": signature},
            ).first()
            if exists:
                return False
            conn.execute(
                text(
                    "INSERT INTO notification_event_log(signature, kind, created_at) "
                    "VALUES (:signature, :kind, :created_at)"
                ),
                {"signature": signature, "kind": kind, "created_at": now},
            )
        return True

    def clear_notification_events(self) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(text("DELETE FROM notification_event_log"))

    def ensure_master_user(self) -> None:
        if not settings.has_bootstrap_master:
            return
        email = settings.master_email
        existing = self.get_user_by_email(email)
        if existing:
            if existing.get("role") != "admin" or existing.get("status") != "ativo" or not existing.get("is_active"):
                with self._lock, self._engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE users "
                            "SET role='admin', is_active=1, status='ativo', updated_at=:updated_at "
                            "WHERE email=:email"
                        ),
                        {"updated_at": _utcnow(), "email": email},
                    )
            return
        self.create_user(
            email=email,
            password=settings.master_password,
            role="admin",
            force_password_change=settings.master_force_change,
            status="ativo",
        )

    def _normalize_user(self, row: Any) -> dict | None:
        if not row:
            return None
        status = row.get("status")
        if not status:
            status = "ativo" if bool(row.get("is_active")) else "inativo"
        role = row["role"]
        return {
            "id": row["id"],
            "email": row["email"],
            "role": role,
            "is_active": bool(row["is_active"]),
            "force_password_change": bool(row["force_password_change"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "nome": row.get("nome", "") or "",
            "telefone": row.get("telefone", "") or "",
            "crmv": row.get("crmv", "") or "",
            "status": status,
            "tentativas_login": int(row.get("tentativas_login") or 0),
            "bloqueado_ate": row.get("bloqueado_ate"),
            "profile_id": row.get("profile_id"),
            "tipo": role,
            "gestor_plantao": role in {"admin", "operator"},
        }

    def list_users(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM users ORDER BY nome ASC, email ASC")).mappings().all()
        return [self._normalize_user(row) for row in rows]

    def list_pending_users(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM users WHERE status = 'pendente' ORDER BY created_at ASC")
            ).mappings().all()
        return [self._normalize_user(row) for row in rows]

    def get_user_by_email(self, email: str) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE email = :email"),
                {"email": email.strip().lower()},
            ).mappings().first()
        return self._normalize_user(row)

    def get_user_by_id(self, user_id: int) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
        return self._normalize_user(row)

    def authenticate_user(self, email: str, password: str) -> tuple[dict | None, str]:
        now = _utcnow()
        email = email.strip().lower()
        with self._lock, self._engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE email = :email"),
                {"email": email},
            ).mappings().first()
            if not row:
                return None, "invalid"
            row = dict(row)

            if row.get("bloqueado_ate") and row["bloqueado_ate"] > now:
                return None, "locked"
            if row.get("bloqueado_ate") and row["bloqueado_ate"] <= now:
                conn.execute(
                    text(
                        "UPDATE users "
                        "SET tentativas_login=0, bloqueado_ate=NULL, updated_at=:updated_at "
                        "WHERE id=:user_id"
                    ),
                    {"updated_at": now, "user_id": row["id"]},
                )
                row["tentativas_login"] = 0
                row["bloqueado_ate"] = None

            if not verify_password(password, row["password_hash"]):
                tentativas = int(row.get("tentativas_login") or 0) + 1
                bloqueado_ate = None
                if tentativas >= MAX_LOGIN_ATTEMPTS:
                    bloqueado_ate = (
                        datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                    ).isoformat(timespec="seconds")
                conn.execute(
                    text(
                        "UPDATE users "
                        "SET tentativas_login=:tentativas_login, bloqueado_ate=:bloqueado_ate, updated_at=:updated_at "
                        "WHERE id=:user_id"
                    ),
                    {
                        "tentativas_login": tentativas,
                        "bloqueado_ate": bloqueado_ate,
                        "updated_at": now,
                        "user_id": row["id"],
                    },
                )
                return None, "invalid"

            conn.execute(
                text(
                    "UPDATE users "
                    "SET tentativas_login=0, bloqueado_ate=NULL, updated_at=:updated_at "
                    "WHERE id=:user_id"
                ),
                {"updated_at": now, "user_id": row["id"]},
            )

        if not row.get("is_active"):
            return None, "inactive"
        status = row.get("status") or "ativo"
        if status == "pendente":
            return None, "pending"
        if status == "rejeitado":
            return None, "rejected"
        if status != "ativo":
            return None, "inactive"
        return self.get_user_by_email(email), "ok"

    def create_user(
        self,
        *,
        email: str,
        password: str,
        role: str = "viewer",
        force_password_change: bool = False,
        nome: str = "",
        telefone: str = "",
        crmv: str = "",
        status: str = "ativo",
    ) -> dict:
        now = _utcnow()
        email = email.strip().lower()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users("
                    "email, password_hash, role, is_active, force_password_change, created_at, updated_at, "
                    "nome, telefone, crmv, status, tentativas_login, bloqueado_ate"
                    ") VALUES ("
                    ":email, :password_hash, :role, :is_active, :force_password_change, :created_at, :updated_at, "
                    ":nome, :telefone, :crmv, :status, 0, NULL)"
                ),
                {
                    "email": email,
                    "password_hash": hash_password(password),
                    "role": role,
                    "is_active": 1 if status == "ativo" else 0,
                    "force_password_change": 1 if force_password_change else 0,
                    "created_at": now,
                    "updated_at": now,
                    "nome": nome.strip(),
                    "telefone": telefone.strip(),
                    "crmv": crmv.strip(),
                    "status": status,
                },
            )
        return self.get_user_by_email(email) or {}

    def create_user_request(
        self,
        *,
        email: str,
        password: str,
        role: str,
        nome: str,
        telefone: str = "",
        crmv: str = "",
    ) -> dict:
        email = email.strip().lower()
        existing = self.get_user_by_email(email)
        if existing:
            raise ValueError("E-mail já cadastrado. Tente fazer login ou recuperar sua senha.")
        if role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"Categoria inválida: {role}")
        return self.create_user(
            email=email,
            password=password,
            role=role,
            nome=nome,
            telefone=telefone,
            crmv=crmv,
            status="pendente",
        )

    def approve_user(self, user_id: int, approved_by_id: int | None = None) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE users "
                    "SET status='ativo', is_active=1, updated_at=:updated_at "
                    "WHERE id=:user_id AND status='pendente'"
                ),
                {"updated_at": _utcnow(), "user_id": user_id},
            )

    def reject_user(self, user_id: int, motivo: str = "") -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE users "
                    "SET status='rejeitado', is_active=0, updated_at=:updated_at "
                    "WHERE id=:user_id"
                ),
                {"updated_at": _utcnow(), "user_id": user_id},
            )

    def set_user_password(self, user_id: int, password: str, *, force_password_change: bool = False) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE users "
                    "SET password_hash=:password_hash, force_password_change=:force_password_change, updated_at=:updated_at "
                    "WHERE id=:user_id"
                ),
                {
                    "password_hash": hash_password(password),
                    "force_password_change": 1 if force_password_change else 0,
                    "updated_at": _utcnow(),
                    "user_id": user_id,
                },
            )

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        current = self.get_user_by_id(user_id)
        if not current:
            return
        new_status = current.get("status") or "ativo"
        if is_active and new_status in {"inativo", "rejeitado"}:
            new_status = "ativo"
        if not is_active and new_status == "ativo":
            new_status = "inativo"
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE users "
                    "SET is_active=:is_active, status=:status, updated_at=:updated_at "
                    "WHERE id=:user_id"
                ),
                {
                    "is_active": 1 if is_active else 0,
                    "status": new_status,
                    "updated_at": _utcnow(),
                    "user_id": user_id,
                },
            )

    def set_user_role(self, user_id: int, role: str) -> None:
        role = role.strip().lower()
        if role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"role desconhecido: {role}")
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET role=:role, updated_at=:updated_at WHERE id=:user_id"),
                {"role": role, "updated_at": _utcnow(), "user_id": user_id},
            )

    # ── Perfis customizáveis ─────────────────────────────────────────────────

    def _seed_system_profiles(self) -> None:
        """Garante que os perfis padrão existam como is_system=1."""
        now = _utcnow()
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            label = ROLE_LABELS.get(role, role.capitalize())
            with self._lock, self._engine.begin() as conn:
                exists = conn.execute(
                    text("SELECT id FROM platform_profiles WHERE base_role=:role AND is_system=1"),
                    {"role": role},
                ).first()
                if not exists:
                    conn.execute(
                        text(
                            "INSERT INTO platform_profiles(nome, descricao, base_role, permissions_json, is_system, criado_em, alterado_em) "
                            "VALUES (:nome, :descricao, :base_role, :permissions_json, 1, :criado_em, :alterado_em)"
                        ),
                        {
                            "nome": label,
                            "descricao": f"Perfil padrão de sistema: {label}",
                            "base_role": role,
                            "permissions_json": _json_dumps(perms),
                            "criado_em": now,
                            "alterado_em": now,
                        },
                    )

    def list_profiles(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM platform_profiles ORDER BY is_system DESC, nome ASC")
            ).mappings().all()
        return [self._normalize_profile(r) for r in rows]

    def get_profile(self, profile_id: int) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM platform_profiles WHERE id=:id"),
                {"id": profile_id},
            ).mappings().first()
        return self._normalize_profile(row) if row else None

    def _normalize_profile(self, row: Any) -> dict:
        return {
            "id": row["id"],
            "nome": row["nome"],
            "descricao": row.get("descricao", "") or "",
            "base_role": row["base_role"],
            "permissions": _json_loads(row.get("permissions_json"), {}),
            "is_system": bool(row["is_system"]),
            "criado_em": row.get("criado_em", ""),
            "alterado_em": row.get("alterado_em", ""),
        }

    def create_profile(self, *, nome: str, descricao: str, base_role: str, permissions: dict) -> dict:
        if base_role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"base_role inválido: {base_role}")
        now = _utcnow()
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO platform_profiles(nome, descricao, base_role, permissions_json, is_system, criado_em, alterado_em) "
                    "VALUES (:nome, :descricao, :base_role, :permissions_json, 0, :now, :now)"
                ),
                {
                    "nome": nome.strip(),
                    "descricao": descricao.strip(),
                    "base_role": base_role,
                    "permissions_json": _json_dumps(permissions),
                    "now": now,
                },
            )
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM platform_profiles WHERE nome=:nome AND is_system=0 ORDER BY id DESC LIMIT 1"),
                {"nome": nome.strip()},
            ).mappings().first()
        return self._normalize_profile(row)

    def update_profile(self, profile_id: int, *, nome: str, descricao: str, permissions: dict) -> None:
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError("Perfil não encontrado.")
        if profile["is_system"]:
            raise ValueError("Perfis de sistema não podem ser editados.")
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE platform_profiles SET nome=:nome, descricao=:descricao, "
                    "permissions_json=:permissions_json, alterado_em=:now WHERE id=:id"
                ),
                {
                    "nome": nome.strip(),
                    "descricao": descricao.strip(),
                    "permissions_json": _json_dumps(permissions),
                    "now": _utcnow(),
                    "id": profile_id,
                },
            )

    def delete_profile(self, profile_id: int) -> None:
        profile = self.get_profile(profile_id)
        if not profile:
            return
        if profile["is_system"]:
            raise ValueError("Perfis de sistema não podem ser excluídos.")
        with self._lock, self._engine.begin() as conn:
            # Desvincula usuários deste perfil antes de deletar
            conn.execute(
                text("UPDATE users SET profile_id=NULL WHERE profile_id=:id"),
                {"id": profile_id},
            )
            conn.execute(
                text("DELETE FROM platform_profiles WHERE id=:id"),
                {"id": profile_id},
            )

    def assign_user_profile(self, user_id: int, profile_id: int | None) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET profile_id=:profile_id, updated_at=:now WHERE id=:user_id"),
                {"profile_id": profile_id, "now": _utcnow(), "user_id": user_id},
            )

    def create_session(self, user_id: int) -> str:
        raw = secrets.token_urlsafe(32)
        hashed = token_hash(raw)
        now = datetime.utcnow()
        expires = now + timedelta(days=settings.session_ttl_days)
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO user_sessions(token_hash, user_id, created_at, expires_at) "
                    "VALUES (:token_hash, :user_id, :created_at, :expires_at)"
                ),
                {
                    "token_hash": hashed,
                    "user_id": user_id,
                    "created_at": now.isoformat(timespec="seconds"),
                    "expires_at": expires.isoformat(timespec="seconds"),
                },
            )
        return raw

    def get_user_for_session(self, raw_token: str | None) -> dict | None:
        if not raw_token:
            return None
        now = datetime.utcnow().isoformat(timespec="seconds")
        hashed = token_hash(raw_token)
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM user_sessions WHERE expires_at < :now"),
                {"now": now},
            )
            row = conn.execute(
                text(
                    "SELECT u.* "
                    "FROM user_sessions s "
                    "JOIN users u ON u.id = s.user_id "
                    "WHERE s.token_hash = :token_hash"
                ),
                {"token_hash": hashed},
            ).mappings().first()
        user = self._normalize_user(row)
        if not user:
            return None
        if not user["is_active"] or user.get("status") != "ativo":
            return None
        return user

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM user_sessions WHERE token_hash = :token_hash"),
                {"token_hash": token_hash(raw_token)},
            )

    def revoke_all_sessions(self, user_id: int) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM user_sessions WHERE user_id = :user_id"),
                {"user_id": user_id},
            )

    def cleanup_expired_sessions(self) -> int:
        now = datetime.utcnow().isoformat()
        with self._lock, self._engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM user_sessions WHERE expires_at < :now"),
                {"now": now},
            )
            return result.rowcount

    def list_telegram_users(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT chat_id, name, username, subscribed_at "
                    "FROM telegram_subscriptions "
                    "ORDER BY subscribed_at DESC, chat_id"
                )
            ).mappings().all()
        return [
            {
                "chat_id": row["chat_id"],
                "name": row["name"],
                "username": row["username"],
                "subscribed_at": row["subscribed_at"],
            }
            for row in rows
        ]

    def add_telegram_user(self, chat_id: str, *, name: str = "", username: str = "", subscribed_at: str = "") -> bool:
        existing = any(user["chat_id"] == str(chat_id) for user in self.list_telegram_users())
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO telegram_subscriptions(chat_id, name, username, subscribed_at) "
                    "VALUES (:chat_id, :name, :username, :subscribed_at) "
                    "ON CONFLICT(chat_id) DO UPDATE SET "
                    "name=excluded.name, "
                    "username=excluded.username, "
                    "subscribed_at=CASE "
                    "WHEN telegram_subscriptions.subscribed_at = '' THEN excluded.subscribed_at "
                    "ELSE telegram_subscriptions.subscribed_at END"
                ),
                {
                    "chat_id": str(chat_id),
                    "name": name,
                    "username": username,
                    "subscribed_at": subscribed_at or datetime.now().strftime("%d/%m/%Y %H:%M"),
                },
            )
        return not existing

    def remove_telegram_user(self, chat_id: str) -> bool:
        with self._lock, self._engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM telegram_subscriptions WHERE chat_id = :chat_id"),
                {"chat_id": str(chat_id)},
            )
        return result.rowcount > 0

    def list_exam_thresholds(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT exam_slug, display_name, warning_multiplier, critical_multiplier, updated_at, updated_by "
                    "FROM exam_thresholds ORDER BY display_name"
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    def get_exam_threshold(self, exam_name: str) -> dict:
        slug = _slugify_exam(exam_name)
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM exam_thresholds WHERE exam_slug = :exam_slug"),
                {"exam_slug": slug},
            ).mappings().first()
        defaults = self.get_global_thresholds()
        if not row:
            return {
                "exam_slug": slug,
                "display_name": exam_name,
                "warning_multiplier": defaults["warning_multiplier"],
                "critical_multiplier": defaults["critical_multiplier"],
                "updated_at": "",
                "updated_by": "",
            }
        return dict(row)

    def upsert_exam_threshold(
        self,
        exam_name: str,
        *,
        warning_multiplier: float,
        critical_multiplier: float,
        updated_by: str = "",
    ) -> None:
        slug = _slugify_exam(exam_name)
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO exam_thresholds("
                    "exam_slug, display_name, warning_multiplier, critical_multiplier, updated_at, updated_by"
                    ") VALUES ("
                    ":exam_slug, :display_name, :warning_multiplier, :critical_multiplier, :updated_at, :updated_by"
                    ") ON CONFLICT(exam_slug) DO UPDATE SET "
                    "display_name=excluded.display_name, "
                    "warning_multiplier=excluded.warning_multiplier, "
                    "critical_multiplier=excluded.critical_multiplier, "
                    "updated_at=excluded.updated_at, "
                    "updated_by=excluded.updated_by"
                ),
                {
                    "exam_slug": slug,
                    "display_name": exam_name,
                    "warning_multiplier": warning_multiplier,
                    "critical_multiplier": critical_multiplier,
                    "updated_at": _utcnow(),
                    "updated_by": updated_by,
                },
            )

    def delete_exam_threshold(self, exam_slug: str) -> None:
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM exam_thresholds WHERE exam_slug = :exam_slug"),
                {"exam_slug": exam_slug},
            )


store = PlatformStore()
