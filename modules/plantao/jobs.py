"""
Módulo Plantão — jobs de background.

Todos os jobs são funções síncronas simples, chamadas por um daemon thread
que itera em loop com sleep() entre execuções.

Padrão idêntico ao core.py da plataforma: rodam a cada intervalo, com
logging de erros mas sem re-raise para não matar o thread.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Jobs individuais ──────────────────────────────────────────────────────────

def encerrar_escalas_passadas(engine: Any) -> int:
    """Encerra automaticamente datas de plantão cujo fim já passou.

    Muda status de 'publicado' para 'encerrado' para plantões onde
    data+hora_fim < agora. Retorna o número de linhas afetadas.
    """
    agora = _utcnow()
    # Comparação de texto ISO 8601 funciona corretamente para datas/horas
    # no formato YYYY-MM-DD + HH:MM
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE plantao_datas SET status='encerrado', alterado_em=:agora"
                    " WHERE status='publicado'"
                    "   AND (data || 'T' || hora_fim) < :agora"
                    "   AND tipo='presencial'"
                ),
                {"agora": agora},
            )
            affected = result.rowcount or 0
        if affected:
            log.info("[plantao.jobs] %d escala(s) encerrada(s) automaticamente.", affected)
        return affected
    except Exception:
        log.exception("[plantao.jobs] Erro em encerrar_escalas_passadas")
        return 0


def expirar_trocas(engine: Any) -> int:
    """Expira solicitações de troca que passaram do prazo sem resposta.

    Retorna o número de linhas afetadas.
    """
    agora = _utcnow()
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE plantao_trocas SET status='expirado'"
                    " WHERE status='solicitado' AND expira_em < :agora"
                ),
                {"agora": agora},
            )
            affected = result.rowcount or 0
        if affected:
            log.info("[plantao.jobs] %d troca(s) expirada(s).", affected)
        return affected
    except Exception:
        log.exception("[plantao.jobs] Erro em expirar_trocas")
        return 0


def alertar_sobreaviso_vazio(engine: Any, dias_antecedencia: int = 3) -> list[str]:
    """Detecta datas de sobreaviso sem participantes nos próximos N dias.

    Retorna lista de datas (YYYY-MM-DD) sem cobertura de sobreaviso.
    O alerta em si é apenas log — a exibição de alertas no dashboard
    é responsabilidade de queries.py.
    """
    hoje = _hoje()
    try:
        with engine.connect() as conn:
            # datas de sobreaviso publicadas nos próximos N dias
            rows = conn.execute(
                text(
                    "SELECT pd.id, pd.data FROM plantao_datas pd"
                    " WHERE pd.tipo='sobreaviso' AND pd.status='publicado'"
                    "   AND pd.data >= :hoje"
                    "   AND pd.data <= date(:hoje, '+' || :dias || ' days')"
                    "   AND NOT EXISTS ("
                    "       SELECT 1 FROM plantao_sobreaviso ps"
                    "       WHERE ps.data_id = pd.id AND ps.status = 'ativo'"
                    "   )"
                ),
                {"hoje": hoje, "dias": dias_antecedencia},
            ).mappings().all()
        datas_vazias = [r["data"] for r in rows]
        if datas_vazias:
            log.warning(
                "[plantao.jobs] Sobreaviso sem participantes em: %s",
                ", ".join(datas_vazias),
            )
        return datas_vazias
    except Exception:
        log.exception("[plantao.jobs] Erro em alertar_sobreaviso_vazio")
        return []


def limpar_sessoes_expiradas(engine: Any) -> int:
    """Sessões agora gerenciadas pela plataforma (pb_platform). Stub mantido por compatibilidade."""
    return 0


def limpar_notificacoes_antigas(engine: Any, dias: int = 30) -> int:
    """Remove notificações lidas com mais de N dias."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM plantao_notificacoes"
                    " WHERE lida = 1"
                    "   AND criado_em < date(:hoje, '-' || :dias || ' days')"
                ),
                {"hoje": _hoje(), "dias": dias},
            )
            affected = result.rowcount or 0
        if affected:
            log.debug("[plantao.jobs] %d notificação(ões) antiga(s) removida(s).", affected)
        return affected
    except Exception:
        log.exception("[plantao.jobs] Erro em limpar_notificacoes_antigas")
        return 0


# ── Loop de background ────────────────────────────────────────────────────────

def run_plantao_jobs(engine: Any, interval_seconds: int = 300) -> None:
    """Loop principal de jobs do módulo Plantão.

    Deve ser iniciado como daemon thread em web/app.py:

        thread = threading.Thread(
            target=run_plantao_jobs,
            args=(plantao_engine,),
            daemon=True,
        )
        thread.start()

    Executa a cada interval_seconds (padrão: 5 min).
    """
    log.info("[plantao.jobs] Loop iniciado (intervalo: %ds).", interval_seconds)
    while True:
        try:
            encerrar_escalas_passadas(engine)
            expirar_trocas(engine)
            alertar_sobreaviso_vazio(engine)
            limpar_sessoes_expiradas(engine)
            limpar_notificacoes_antigas(engine)
        except Exception:
            log.exception("[plantao.jobs] Erro inesperado no loop principal.")
        time.sleep(interval_seconds)
