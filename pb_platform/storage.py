from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .security import hash_password, token_hash, verify_password
from .settings import settings

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
TELEGRAM_USERS_FILE = ROOT / "telegram_users.json"

# ── Permissões por role/categoria ─────────────────────────────────────────────
#
# Roles internos:  admin, operator, viewer
# Categorias externas (auto-cadastro): veterinario, auxiliar, colaborador
#
# Permissões disponíveis:
#   platform_access   – acessa a home e módulos internos
#   labmonitor_access – acessa /labmonitor (leitura)
#   manage_labmonitor – gerencia lab monitor
#   ops_tools         – acessa ops-map e sandboxes
#   manage_users      – administra usuários
#   plantao_access    – acessa /plantao (plantonistas)
#   manage_plantao    – gerencia escalas e aprova cadastros (gestores)

ALL_PERMISSIONS = [
    "platform_access",
    "labmonitor_access",
    "manage_labmonitor",
    "ops_tools",
    "manage_users",
    "plantao_access",
    "manage_plantao",
]

DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "admin": {
        "platform_access": True,
        "labmonitor_access": True,
        "manage_labmonitor": True,
        "ops_tools": True,
        "manage_users": True,
        "plantao_access": True,
        "manage_plantao": True,
    },
    "operator": {
        "platform_access": True,
        "labmonitor_access": True,
        "manage_labmonitor": True,
        "ops_tools": True,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": True,
    },
    "viewer": {
        "platform_access": True,
        "labmonitor_access": True,
        "manage_labmonitor": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": False,
        "manage_plantao": False,
    },
    # Categorias externas
    "veterinario": {
        "platform_access": True,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": False,
    },
    "auxiliar": {
        "platform_access": True,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": True,
        "manage_plantao": False,
    },
    "colaborador": {
        "platform_access": True,
        "labmonitor_access": False,
        "manage_labmonitor": False,
        "ops_tools": False,
        "manage_users": False,
        "plantao_access": False,
        "manage_plantao": False,
    },
}

# Roles que são categorias de auto-cadastro (externas)
EXTERNAL_ROLES = {"veterinario", "auxiliar", "colaborador"}
# Roles internos (criados por admin)
INTERNAL_ROLES = {"admin", "operator", "viewer"}

# Labels amigáveis para exibição
ROLE_LABELS: dict[str, str] = {
    "admin": "Administrador",
    "operator": "Operador",
    "viewer": "Visualizador",
    "veterinario": "Veterinário Plantonista",
    "auxiliar": "Auxiliar Veterinário",
    "colaborador": "Colaborador",
}

# Rate limiting
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

DEFAULT_GLOBAL_THRESHOLDS: dict[str, float] = {
    "warning_multiplier": 1.0,
    "critical_multiplier": 1.2,
}


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


def _slugify_exam(text: str) -> str:
    import re
    import unicodedata

    normalized = "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    ).lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or "exam"


class PlatformStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._db_path = settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
        self.bootstrap_legacy_runtime()
        self.ensure_master_user()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS app_kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            is_active INTEGER NOT NULL DEFAULT 1,
            force_password_change INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            nome TEXT NOT NULL DEFAULT '',
            telefone TEXT NOT NULL DEFAULT '',
            crmv TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'ativo',
            tentativas_login INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate TEXT
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS telegram_subscriptions (
            chat_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            subscribed_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS lab_snapshots (
            lab_id TEXT PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            last_check TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_event_log (
            signature TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exam_thresholds (
            exam_slug TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            warning_multiplier REAL NOT NULL,
            critical_multiplier REAL NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT ''
        );
        """
        with self._connect() as conn:
            conn.executescript(schema)
            # Colunas adicionadas incrementalmente — idempotentes
            for alter in [
                "ALTER TABLE users ADD COLUMN nome TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN telefone TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN crmv TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'ativo'",
                "ALTER TABLE users ADD COLUMN tentativas_login INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN bloqueado_ate TEXT",
                # Mantida por compatibilidade legada — não é mais usada para auth
                "ALTER TABLE users ADD COLUMN gestor_plantao INTEGER NOT NULL DEFAULT 0",
            ]:
                try:
                    conn.execute(alter)
                    conn.commit()
                except Exception:
                    pass  # coluna já existe

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

    # ── Config / KV ──────────────────────────────────────────────────────────

    def load_json_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_kv WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return _json_loads(row["value"], default)

    def save_json_setting(self, key: str, value: Any) -> None:
        payload = _json_dumps(value)
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_kv(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, payload, now),
            )
            conn.commit()

    def load_runtime_config(self) -> dict | None:
        return self.load_json_setting("lab_monitor.runtime_config")

    def save_runtime_config(self, config: dict) -> None:
        self.save_json_setting("lab_monitor.runtime_config", config)

    # ── Permissões ────────────────────────────────────────────────────────────

    def list_roles(self) -> list[str]:
        return list(DEFAULT_ROLE_PERMISSIONS.keys())

    def get_role_permissions(self) -> dict[str, dict[str, bool]]:
        current = self.load_json_setting("platform.role_permissions", {}) or {}
        result: dict[str, dict[str, bool]] = {}
        for role, defaults in DEFAULT_ROLE_PERMISSIONS.items():
            persisted = current.get(role) if isinstance(current, dict) else {}
            result[role] = {
                key: bool((persisted or {}).get(key, default))
                for key, default in defaults.items()
            }
        return result

    def save_role_permissions(self, role: str, permissions: dict[str, bool]) -> None:
        role = role.strip().lower()
        if role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"role desconhecido: {role}")
        matrix = self.get_role_permissions()
        matrix[role] = {
            key: bool(permissions.get(key, False))
            for key in ALL_PERMISSIONS
        }
        if role == "admin":
            matrix[role] = {key: True for key in ALL_PERMISSIONS}
        self.save_json_setting("platform.role_permissions", matrix)

    def get_user_permissions(self, user: dict | None) -> dict[str, bool]:
        """Retorna o conjunto de permissões efetivas de um usuário."""
        if not user:
            return {k: False for k in ALL_PERMISSIONS}
        matrix = self.get_role_permissions()
        role = (user.get("role") or "viewer").strip().lower()
        role_permissions = matrix.get(role) or {}
        return {key: bool(role_permissions.get(key, False)) for key in ALL_PERMISSIONS}

    # ── Thresholds ────────────────────────────────────────────────────────────

    def get_global_thresholds(self) -> dict[str, float]:
        current = self.load_json_setting("lab_monitor.global_thresholds", {}) or {}
        try:
            warning = float(current.get("warning_multiplier", DEFAULT_GLOBAL_THRESHOLDS["warning_multiplier"]))
        except Exception:
            warning = DEFAULT_GLOBAL_THRESHOLDS["warning_multiplier"]
        try:
            critical = float(current.get("critical_multiplier", DEFAULT_GLOBAL_THRESHOLDS["critical_multiplier"]))
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

    # ── Lab snapshots ─────────────────────────────────────────────────────────

    def get_lab_sync_state(self, lab_id: str) -> dict:
        return self.load_json_setting(f"lab_monitor.sync_state.{lab_id}", {}) or {}

    def save_lab_sync_state(self, lab_id: str, payload: dict) -> None:
        self.save_json_setting(f"lab_monitor.sync_state.{lab_id}", payload or {})

    def load_lab_runtime(self) -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
        snapshots: dict[str, dict] = {}
        last_check: dict[str, str] = {}
        last_error: dict[str, str] = {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT lab_id, snapshot_json, last_check, last_error FROM lab_snapshots"
            ).fetchall()
        for row in rows:
            snapshots[row["lab_id"]] = _json_loads(row["snapshot_json"], {})
            if row["last_check"]:
                last_check[row["lab_id"]] = row["last_check"]
            if row["last_error"]:
                last_error[row["lab_id"]] = row["last_error"]
        return snapshots, last_check, last_error

    def save_lab_snapshot(self, lab_id: str, snapshot: dict, *, last_check: str = "", last_error: str = "") -> None:
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lab_snapshots(lab_id, snapshot_json, last_check, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(lab_id) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json,
                    last_check=excluded.last_check,
                    last_error=excluded.last_error,
                    updated_at=excluded.updated_at
                """,
                (lab_id, _json_dumps(snapshot), last_check, last_error, now),
            )
            conn.commit()

    # ── Notificações de eventos ───────────────────────────────────────────────

    def remember_notification_event(self, signature: str, kind: str, ttl_hours: int = 72) -> bool:
        cutoff = (datetime.utcnow() - timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM notification_event_log WHERE created_at < ?", (cutoff,))
            exists = conn.execute(
                "SELECT 1 FROM notification_event_log WHERE signature = ?", (signature,)
            ).fetchone()
            if exists:
                conn.commit()
                return False
            conn.execute(
                "INSERT INTO notification_event_log(signature, kind, created_at) VALUES (?, ?, ?)",
                (signature, kind, now),
            )
            conn.commit()
        return True

    def clear_notification_events(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM notification_event_log")
            conn.commit()

    # ── Usuários ──────────────────────────────────────────────────────────────

    def ensure_master_user(self) -> None:
        email = settings.master_email.strip().lower()
        existing = self.get_user_by_email(email)
        if existing:
            # Garante que o master sempre está ativo e com role admin
            if existing.get("status") != "ativo" or existing.get("role") != "admin":
                now = _utcnow()
                with self._lock, self._connect() as conn:
                    conn.execute(
                        "UPDATE users SET status='ativo', role='admin', updated_at=? WHERE email=?",
                        (now, email),
                    )
                    conn.commit()
            return
        self.create_user(
            email=email,
            password=settings.master_password,
            role="admin",
            force_password_change=settings.master_force_change,
            status="ativo",
        )

    def _normalize_user(self, row: sqlite3.Row | None) -> dict | None:
        if not row:
            return None
        keys = list(row.keys()) if hasattr(row, "keys") else []
        return {
            "id": row["id"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "force_password_change": bool(row["force_password_change"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "nome": row["nome"] if "nome" in keys else "",
            "telefone": row["telefone"] if "telefone" in keys else "",
            "crmv": row["crmv"] if "crmv" in keys else "",
            "status": row["status"] if "status" in keys else "ativo",
            "tentativas_login": row["tentativas_login"] if "tentativas_login" in keys else 0,
            "bloqueado_ate": row["bloqueado_ate"] if "bloqueado_ate" in keys else None,
            # Aliases de compatibilidade com o módulo Plantão (que usava plantao_perfis.tipo)
            "tipo": row["role"],
            # campo legado — mantido para não quebrar código existente
            "gestor_plantao": bool(row["gestor_plantao"]) if "gestor_plantao" in keys else False,
        }

    def list_users(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY nome ASC, email ASC"
            ).fetchall()
        return [self._normalize_user(row) for row in rows]

    def list_pending_users(self) -> list[dict]:
        """Retorna usuários com status='pendente' aguardando aprovação."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users WHERE status = 'pendente' ORDER BY created_at ASC"
            ).fetchall()
        return [self._normalize_user(row) for row in rows]

    def get_user_by_email(self, email: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        return self._normalize_user(row)

    def get_user_by_id(self, user_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._normalize_user(row)

    def authenticate_user(self, email: str, password: str) -> tuple[dict | None, str]:
        """
        Autentica com rate limiting.

        Returns (user, 'ok') ou (None, código_erro).
        Códigos: 'invalid', 'locked', 'pending', 'rejected', 'inactive'
        """
        now = _utcnow()
        email = email.strip().lower()

        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                return None, "invalid"

            perfil = {k: row[k] for k in row.keys()}

            # Verifica bloqueio
            if perfil.get("bloqueado_ate") and perfil["bloqueado_ate"] > now:
                return None, "locked"
            if perfil.get("bloqueado_ate") and perfil["bloqueado_ate"] <= now:
                conn.execute(
                    "UPDATE users SET tentativas_login=0, bloqueado_ate=NULL WHERE id=?",
                    (perfil["id"],),
                )
                conn.commit()
                perfil["tentativas_login"] = 0
                perfil["bloqueado_ate"] = None

            # Verifica senha
            if not verify_password(password, perfil["password_hash"]):
                tentativas = (perfil.get("tentativas_login") or 0) + 1
                bloqueado_ate = None
                if tentativas >= MAX_LOGIN_ATTEMPTS:
                    bloqueado_ate = (
                        datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                    ).isoformat(timespec="seconds")
                conn.execute(
                    "UPDATE users SET tentativas_login=?, bloqueado_ate=?, updated_at=? WHERE id=?",
                    (tentativas, bloqueado_ate, now, perfil["id"]),
                )
                conn.commit()
                return None, "invalid"

            # Senha OK — zera tentativas
            conn.execute(
                "UPDATE users SET tentativas_login=0, bloqueado_ate=NULL, updated_at=? WHERE id=?",
                (now, perfil["id"]),
            )
            conn.commit()

        if not perfil.get("is_active"):
            return None, "inactive"
        status = perfil.get("status", "ativo")
        if status == "pendente":
            return None, "pending"
        if status == "rejeitado":
            return None, "rejected"
        if status != "ativo":
            return None, "inactive"

        user = self.get_user_by_email(email)
        return user, "ok"

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
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users(email, password_hash, role, is_active, force_password_change,
                                  created_at, updated_at, nome, telefone, crmv, status)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email,
                    hash_password(password),
                    role,
                    1 if force_password_change else 0,
                    now,
                    now,
                    nome.strip(),
                    telefone.strip(),
                    crmv.strip(),
                    status,
                ),
            )
            conn.commit()
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
        """
        Cria um usuário via auto-cadastro público com status='pendente'.
        Levanta ValueError se o e-mail já estiver cadastrado.
        """
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
        """Aprova um cadastro pendente, ativando o usuário."""
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET status='ativo', is_active=1, updated_at=? WHERE id=? AND status='pendente'",
                (now, user_id),
            )
            conn.commit()

    def reject_user(self, user_id: int, motivo: str = "") -> None:
        """Rejeita um cadastro pendente."""
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET status='rejeitado', is_active=0, updated_at=? WHERE id=?",
                (now, user_id),
            )
            conn.commit()

    def set_user_password(self, user_id: int, password: str, *, force_password_change: bool = False) -> None:
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash=?, force_password_change=?, updated_at=? WHERE id=?",
                (hash_password(password), 1 if force_password_change else 0, now, user_id),
            )
            conn.commit()

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET is_active=?, updated_at=? WHERE id=?",
                (1 if is_active else 0, now, user_id),
            )
            conn.commit()

    def set_user_role(self, user_id: int, role: str) -> None:
        role = role.strip().lower()
        if role not in DEFAULT_ROLE_PERMISSIONS:
            raise ValueError(f"role desconhecido: {role}")
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE users SET role=?, updated_at=? WHERE id=?",
                (role, now, user_id),
            )
            conn.commit()

    # ── Sessões ───────────────────────────────────────────────────────────────

    def create_session(self, user_id: int) -> str:
        raw = secrets.token_urlsafe(32)
        hashed = token_hash(raw)
        now = datetime.utcnow()
        expires = now + timedelta(days=settings.session_ttl_days)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO user_sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (
                    hashed,
                    user_id,
                    now.isoformat(timespec="seconds"),
                    expires.isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
        return raw

    def get_user_for_session(self, raw_token: str | None) -> dict | None:
        if not raw_token:
            return None
        now = datetime.utcnow().isoformat(timespec="seconds")
        hashed = token_hash(raw_token)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now,))
            row = conn.execute(
                """
                SELECT u.*
                  FROM user_sessions s
                  JOIN users u ON u.id = s.user_id
                 WHERE s.token_hash = ?
                """,
                (hashed,),
            ).fetchone()
            conn.commit()
        user = self._normalize_user(row)
        if not user:
            return None
        # Só permite sessão para usuários ativos e aprovados
        if not user["is_active"] or user.get("status") != "ativo":
            return None
        return user

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash(raw_token),))
            conn.commit()

    def revoke_all_sessions(self, user_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            conn.commit()

    # ── Telegram ──────────────────────────────────────────────────────────────

    def list_telegram_users(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT chat_id, name, username, subscribed_at FROM telegram_subscriptions ORDER BY subscribed_at DESC, chat_id"
            ).fetchall()
        return [
            {"chat_id": row["chat_id"], "name": row["name"], "username": row["username"], "subscribed_at": row["subscribed_at"]}
            for row in rows
        ]

    def add_telegram_user(self, chat_id: str, *, name: str = "", username: str = "", subscribed_at: str = "") -> bool:
        existing = any(u["chat_id"] == str(chat_id) for u in self.list_telegram_users())
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telegram_subscriptions(chat_id, name, username, subscribed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name=excluded.name,
                    username=excluded.username,
                    subscribed_at=CASE
                        WHEN telegram_subscriptions.subscribed_at = '' THEN excluded.subscribed_at
                        ELSE telegram_subscriptions.subscribed_at
                    END
                """,
                (str(chat_id), name, username, subscribed_at or datetime.now().strftime("%d/%m/%Y %H:%M")),
            )
            conn.commit()
        return not existing

    def remove_telegram_user(self, chat_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM telegram_subscriptions WHERE chat_id = ?", (str(chat_id),))
            conn.commit()
        return cur.rowcount > 0

    # ── Exam thresholds ───────────────────────────────────────────────────────

    def list_exam_thresholds(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT exam_slug, display_name, warning_multiplier, critical_multiplier, updated_at, updated_by FROM exam_thresholds ORDER BY display_name"
            ).fetchall()
        return [
            {
                "exam_slug": row["exam_slug"],
                "display_name": row["display_name"],
                "warning_multiplier": row["warning_multiplier"],
                "critical_multiplier": row["critical_multiplier"],
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
            }
            for row in rows
        ]

    def get_exam_threshold(self, exam_name: str) -> dict:
        slug = _slugify_exam(exam_name)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM exam_thresholds WHERE exam_slug = ?", (slug,)
            ).fetchone()
        defaults = self.get_global_thresholds()
        if not row:
            return {
                "exam_slug": slug, "display_name": exam_name,
                "warning_multiplier": defaults["warning_multiplier"],
                "critical_multiplier": defaults["critical_multiplier"],
                "updated_at": "", "updated_by": "",
            }
        return {
            "exam_slug": row["exam_slug"], "display_name": row["display_name"],
            "warning_multiplier": row["warning_multiplier"],
            "critical_multiplier": row["critical_multiplier"],
            "updated_at": row["updated_at"], "updated_by": row["updated_by"],
        }

    def upsert_exam_threshold(self, exam_name: str, *, warning_multiplier: float, critical_multiplier: float, updated_by: str = "") -> None:
        slug = _slugify_exam(exam_name)
        now = _utcnow()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exam_thresholds(exam_slug, display_name, warning_multiplier, critical_multiplier, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(exam_slug) DO UPDATE SET
                    display_name=excluded.display_name,
                    warning_multiplier=excluded.warning_multiplier,
                    critical_multiplier=excluded.critical_multiplier,
                    updated_at=excluded.updated_at,
                    updated_by=excluded.updated_by
                """,
                (slug, exam_name, warning_multiplier, critical_multiplier, now, updated_by),
            )
            conn.commit()

    def delete_exam_threshold(self, exam_slug: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM exam_thresholds WHERE exam_slug = ?", (exam_slug,))
            conn.commit()


store = PlatformStore()
