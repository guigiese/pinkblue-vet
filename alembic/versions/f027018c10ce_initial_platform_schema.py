"""initial_platform_schema

Revision ID: f027018c10ce
Revises:
Create Date: 2026-04-12
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "f027018c10ce"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    id_col = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app_kv (
            key TEXT NOT NULL PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_col},
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
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            token_hash TEXT NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_subscriptions (
            chat_id TEXT NOT NULL PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            subscribed_at TEXT NOT NULL DEFAULT ''
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_snapshots (
            lab_id TEXT NOT NULL PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            last_check TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_event_log (
            signature TEXT NOT NULL PRIMARY KEY,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS exam_thresholds (
            exam_slug TEXT NOT NULL PRIMARY KEY,
            display_name TEXT NOT NULL,
            warning_multiplier FLOAT NOT NULL,
            critical_multiplier FLOAT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS sync_runs (
            id {id_col},
            lab_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            success INTEGER,
            error TEXT
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS module_logs (
            id {id_col},
            module TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            payload_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    for table in (
        "module_logs",
        "sync_runs",
        "exam_thresholds",
        "notification_event_log",
        "lab_snapshots",
        "telegram_subscriptions",
        "user_sessions",
        "users",
        "app_kv",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
