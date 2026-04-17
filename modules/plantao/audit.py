"""
Módulo Plantão — auditoria.

Todo evento relevante do módulo deve ser registrado via audit().
O log é imutável — nunca fazer UPDATE ou DELETE em plantao_audit_log.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def audit(
    engine: Any,
    acao: str,
    *,
    perfil_id: int | None = None,
    gestor_id: int | None = None,
    entidade: str | None = None,
    entidade_id: int | None = None,
    detalhes: str = "",
    ip: str = "",
) -> None:
    """Registra uma ação no log de auditoria.

    Args:
        engine:      SQLAlchemy engine.
        acao:        código da ação, ex: 'candidatura.confirmada', 'troca.executada'.
        perfil_id:   plantonista responsável (se aplicável).
        gestor_id:   usuário da plataforma responsável (se aplicável).
        entidade:    nome da tabela afetada, ex: 'plantao_candidaturas'.
        entidade_id: PK da linha afetada.
        detalhes:    texto livre com contexto adicional (JSON ou prose).
        ip:          IP do requisitante.
    """
    # Determina ator_tipo e ator_id a partir dos argumentos
    if gestor_id is not None:
        ator_tipo = "gestor"
        ator_id = gestor_id
    elif perfil_id is not None:
        ator_tipo = "perfil"
        ator_id = perfil_id
    else:
        ator_tipo = "sistema"
        ator_id = None

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO plantao_audit_log"
                    " (acao, entidade, entidade_id, ator_tipo, ator_id, dados, ip, criado_em)"
                    " VALUES (:acao, :ent, :eid, :ator_tipo, :ator_id, :dados, :ip, :ts)"
                ),
                {
                    "acao": acao,
                    "ent": entidade or "",
                    "eid": entidade_id,
                    "ator_tipo": ator_tipo,
                    "ator_id": ator_id,
                    "dados": detalhes or None,
                    "ip": ip,
                    "ts": _utcnow(),
                },
            )
    except Exception:
        log.exception("Falha ao registrar auditoria: acao=%s", acao)
