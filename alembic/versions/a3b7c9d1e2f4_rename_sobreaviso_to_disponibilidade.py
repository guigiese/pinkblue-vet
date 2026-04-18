"""rename plantao_sobreaviso to plantao_disponibilidade

Revision ID: a3b7c9d1e2f4
Revises: f027018c10ce
Create Date: 2026-04-17
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "a3b7c9d1e2f4"
down_revision: str | None = "f027018c10ce"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Rename table
    op.rename_table("plantao_sobreaviso", "plantao_disponibilidade")

    # Update tipo column values in plantao_datas
    op.execute("UPDATE plantao_datas SET tipo='disponibilidade' WHERE tipo='sobreaviso'")

    # Recreate indexes with new name (SQLite doesn't support ALTER INDEX)
    if dialect == "sqlite":
        op.execute("DROP INDEX IF EXISTS idx_plantao_sobreaviso_ativo")
        op.execute("DROP INDEX IF EXISTS idx_plantao_sobreaviso_prio")
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_disponibilidade_ativo "
            "ON plantao_disponibilidade(data_id, perfil_id) WHERE status = 'ativo'"
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_disponibilidade_prio "
            "ON plantao_disponibilidade(data_id, prioridade) WHERE status = 'ativo'"
        )
    else:
        # PostgreSQL
        op.execute("ALTER INDEX IF EXISTS idx_plantao_sobreaviso_ativo RENAME TO idx_plantao_disponibilidade_ativo")
        op.execute("ALTER INDEX IF EXISTS idx_plantao_sobreaviso_prio RENAME TO idx_plantao_disponibilidade_prio")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.execute("UPDATE plantao_datas SET tipo='sobreaviso' WHERE tipo='disponibilidade'")
    op.rename_table("plantao_disponibilidade", "plantao_sobreaviso")

    if dialect == "sqlite":
        op.execute("DROP INDEX IF EXISTS idx_plantao_disponibilidade_ativo")
        op.execute("DROP INDEX IF EXISTS idx_plantao_disponibilidade_prio")
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_sobreaviso_ativo "
            "ON plantao_sobreaviso(data_id, perfil_id) WHERE status = 'ativo'"
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_sobreaviso_prio "
            "ON plantao_sobreaviso(data_id, prioridade) WHERE status = 'ativo'"
        )
    else:
        op.execute("ALTER INDEX IF EXISTS idx_plantao_disponibilidade_ativo RENAME TO idx_plantao_sobreaviso_ativo")
        op.execute("ALTER INDEX IF EXISTS idx_plantao_disponibilidade_prio RENAME TO idx_plantao_sobreaviso_prio")
