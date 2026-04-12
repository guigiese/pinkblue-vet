"""
Módulo Plantão — notificações in-app.

As notificações são armazenadas em plantao_notificacoes e exibidas
para o plantonista em todas as páginas (badge + lista).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def notificar(
    engine: Any,
    perfil_id: int,
    tipo: str,
    titulo: str,
    corpo: str = "",
    entidade: str | None = None,
    entidade_id: int | None = None,
) -> None:
    """Cria uma notificação para o plantonista.

    Args:
        engine:      SQLAlchemy engine.
        perfil_id:   destinatário.
        tipo:        categoria, ex: 'candidatura_aprovada', 'troca_solicitada', 'alerta'.
        titulo:      título curto exibido no badge/lista.
        corpo:       texto completo da notificação (opcional).
        entidade:    tabela relacionada (para link rápido), ex: 'plantao_trocas'.
        entidade_id: ID da linha relacionada.
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO plantao_notificacoes"
                    " (perfil_id, tipo, titulo, corpo, lida, entidade, entidade_id, criado_em)"
                    " VALUES (:pid, :tipo, :titulo, :corpo, 0, :ent, :eid, :ts)"
                ),
                {
                    "pid": perfil_id,
                    "tipo": tipo,
                    "titulo": titulo,
                    "corpo": corpo,
                    "ent": entidade,
                    "eid": entidade_id,
                    "ts": _utcnow(),
                },
            )
    except Exception:
        log.exception("Falha ao criar notificação: perfil_id=%s tipo=%s", perfil_id, tipo)


def contar_nao_lidas(engine: Any, perfil_id: int) -> int:
    """Retorna o número de notificações não lidas."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM plantao_notificacoes"
                " WHERE perfil_id = :pid AND lida = 0"
            ),
            {"pid": perfil_id},
        ).mappings().first()
    return int(row["cnt"]) if row else 0


def listar_notificacoes(engine: Any, perfil_id: int, limit: int = 20) -> list[dict]:
    """Lista as últimas notificações do plantonista, mais recentes primeiro."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT * FROM plantao_notificacoes"
                " WHERE perfil_id = :pid"
                " ORDER BY criado_em DESC LIMIT :lim"
            ),
            {"pid": perfil_id, "lim": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


def marcar_lida(engine: Any, notif_id: int, perfil_id: int) -> None:
    """Marca uma notificação como lida (valida que pertence ao perfil)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_notificacoes SET lida = 1"
                " WHERE id = :id AND perfil_id = :pid"
            ),
            {"id": notif_id, "pid": perfil_id},
        )


def marcar_todas_lidas(engine: Any, perfil_id: int) -> None:
    """Marca todas as notificações do plantonista como lidas."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_notificacoes SET lida = 1 WHERE perfil_id = :pid"
            ),
            {"pid": perfil_id},
        )
