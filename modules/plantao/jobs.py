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
    from datetime import timedelta, date as _date
    hoje = _hoje()
    limite = (_date.today() + timedelta(days=dias_antecedencia)).isoformat()
    try:
        with engine.connect() as conn:
            # datas de sobreaviso publicadas nos próximos N dias
            rows = conn.execute(
                text(
                    "SELECT pd.id, pd.data FROM plantao_datas pd"
                    " WHERE pd.tipo='sobreaviso' AND pd.status='publicado'"
                    "   AND pd.data >= :hoje"
                    "   AND pd.data <= :limite"
                    "   AND NOT EXISTS ("
                    "       SELECT 1 FROM plantao_sobreaviso ps"
                    "       WHERE ps.data_id = pd.id AND ps.status = 'ativo'"
                    "   )"
                ),
                {"hoje": hoje, "limite": limite},
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


def enviar_lembretes_turno(engine: Any) -> int:
    """Envia lembretes D-1 e D-0 para plantonistas com turnos confirmados.

    Evita duplicatas verificando se a notificação já foi enviada para cada
    candidatura+tipo de lembrete.
    Retorna total de notificações enviadas.
    """
    from datetime import timedelta, date as _date
    from .notifications import notificar

    hoje = _date.today()
    amanha = (hoje + timedelta(days=1)).isoformat()
    hoje_str = hoje.isoformat()

    lembretes = [
        (amanha, "lembrete_d1", "Lembrete: plantão amanhã"),
        (hoje_str, "lembrete_d0", "Lembrete: plantão hoje"),
    ]
    enviados = 0

    try:
        for data_alvo, tipo_notif, titulo in lembretes:
            with engine.connect() as conn:
                candidaturas = conn.execute(
                    text(
                        """
                        SELECT c.id AS candidatura_id,
                               c.perfil_id,
                               d.data,
                               d.hora_inicio,
                               d.hora_fim
                          FROM plantao_candidaturas c
                          JOIN plantao_posicoes p ON p.id = c.posicao_id
                          JOIN plantao_datas d ON d.id = p.data_id
                         WHERE c.status = 'confirmado'
                           AND d.data = :data_alvo
                        """
                    ),
                    {"data_alvo": data_alvo},
                ).mappings().all()

                # IDs que já têm lembrete deste tipo
                ja_enviados: set[int] = set()
                if candidaturas:
                    ids = [int(r["candidatura_id"]) for r in candidaturas]
                    placeholders = ",".join(str(i) for i in ids)
                    enviados_rows = conn.execute(
                        text(
                            f"SELECT entidade_id FROM plantao_notificacoes"
                            f" WHERE tipo = :tipo AND entidade = 'plantao_candidaturas'"
                            f"   AND entidade_id IN ({placeholders})"
                        ),
                        {"tipo": tipo_notif},
                    ).mappings().all()
                    ja_enviados = {int(r["entidade_id"]) for r in enviados_rows}

            for row in candidaturas:
                cand_id = int(row["candidatura_id"])
                if cand_id in ja_enviados:
                    continue
                corpo = (
                    f"Voce tem um turno confirmado em "
                    f"{row['data']} das {row['hora_inicio']} às {row['hora_fim']}."
                )
                notificar(
                    engine,
                    int(row["perfil_id"]),
                    tipo_notif,
                    titulo,
                    corpo,
                    entidade="plantao_candidaturas",
                    entidade_id=cand_id,
                )
                enviados += 1

        if enviados:
            log.info("[plantao.jobs] %d lembrete(s) de turno enviado(s).", enviados)
    except Exception:
        log.exception("[plantao.jobs] Erro em enviar_lembretes_turno")
    return enviados


def limpar_notificacoes_antigas(engine: Any, dias: int = 30) -> int:
    """Remove notificações lidas com mais de N dias."""
    from datetime import timedelta, date as _date
    cutoff = (_date.today() - timedelta(days=dias)).isoformat()
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM plantao_notificacoes"
                    " WHERE lida = 1"
                    "   AND criado_em < :cutoff"
                ),
                {"cutoff": cutoff},
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
            enviar_lembretes_turno(engine)
            limpar_sessoes_expiradas(engine)
            limpar_notificacoes_antigas(engine)
        except Exception:
            log.exception("[plantao.jobs] Erro inesperado no loop principal.")
        time.sleep(interval_seconds)
