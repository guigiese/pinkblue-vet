"""
Modulo Plantao - camada de leitura do banco (queries).
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text


def _hoje() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _agora() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _rows(engine: Any, sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    return [dict(r) for r in rows]


def _row(engine: Any, sql: str, params: dict | None = None) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def listar_locais(engine: Any, apenas_ativos: bool = True) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT *
          FROM plantao_locais
         WHERE (:apenas_ativos = 0 OR ativo = 1)
         ORDER BY nome ASC
        """,
        {"apenas_ativos": 1 if apenas_ativos else 0},
    )


def get_local(engine: Any, local_id: int) -> dict | None:
    return _row(engine, "SELECT * FROM plantao_locais WHERE id = :id", {"id": local_id})


def get_perfil_por_email(engine: Any, email: str) -> dict | None:
    return _row(
        engine,
        "SELECT * FROM plantao_perfis WHERE LOWER(email) = LOWER(:email)",
        {"email": email.strip()},
    )


def get_perfil_por_id(engine: Any, perfil_id: int) -> dict | None:
    return _row(engine, "SELECT * FROM plantao_perfis WHERE id = :id", {"id": perfil_id})


def listar_perfis(
    engine: Any,
    status: str | None = None,
    tipo: str | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT *
          FROM plantao_perfis
         WHERE (:status IS NULL OR status = :status)
           AND (:tipo IS NULL OR tipo = :tipo)
         ORDER BY nome ASC
        """,
        {"status": status, "tipo": tipo},
    )


def listar_tarifas_vigentes(engine: Any, data_ref: str) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT *
          FROM plantao_tarifas
         WHERE vigente_de <= :data_ref
           AND (vigente_ate IS NULL OR vigente_ate >= :data_ref)
         ORDER BY tipo_perfil ASC,
                  CASE WHEN dia_semana IS NULL THEN 1 ELSE 0 END ASC,
                  dia_semana ASC,
                  CASE WHEN feriado IS NULL THEN 1 ELSE 0 END ASC,
                  feriado ASC,
                  id ASC
        """,
        {"data_ref": data_ref},
    )


def listar_feriados_por_periodo(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    local_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT *
          FROM plantao_feriados
         WHERE data >= :inicio
           AND data <= :fim
           AND (
                local_id IS NULL
                OR (:local_id IS NOT NULL AND local_id = :local_id)
           )
         ORDER BY data ASC, nome ASC
        """,
        {"inicio": data_inicio, "fim": data_fim, "local_id": local_id},
    )


def get_set_feriados(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    local_id: int | None = None,
) -> set:
    rows = listar_feriados_por_periodo(engine, data_inicio, data_fim, local_id)
    return {date.fromisoformat(r["data"]) for r in rows}


def listar_datas_por_mes(
    engine: Any,
    ano: int,
    mes: int,
    local_id: int | None = None,
    tipo: str | None = None,
    status: str | None = None,
) -> list[dict]:
    _, ultimo_dia = calendar.monthrange(ano, mes)
    inicio = f"{ano:04d}-{mes:02d}-01"
    fim = f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}"
    return _rows(
        engine,
        """
        SELECT d.*,
               l.nome AS local_nome,
               COALESCE((
                 SELECT SUM(p.vagas)
                   FROM plantao_posicoes p
                  WHERE p.data_id = d.id
               ), 0) AS vagas_total,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                   JOIN plantao_posicoes p2 ON p2.id = c.posicao_id
                  WHERE p2.data_id = d.id
                    AND c.status = 'confirmado'
               ), 0) AS confirmados_total,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                   JOIN plantao_posicoes p3 ON p3.id = c.posicao_id
                  WHERE p3.data_id = d.id
                    AND c.status = 'provisorio'
               ), 0) AS provisorios_total,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_sobreaviso s
                  WHERE s.data_id = d.id
                    AND s.status = 'ativo'
               ), 0) AS sobreaviso_ativos
          FROM plantao_datas d
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.data >= :inicio
           AND d.data <= :fim
           AND (:local_id IS NULL OR d.local_id = :local_id)
           AND (:tipo IS NULL OR d.tipo = :tipo)
           AND (:status IS NULL OR d.status = :status)
         ORDER BY d.data ASC, d.hora_inicio ASC, d.id ASC
        """,
        {
            "inicio": inicio,
            "fim": fim,
            "local_id": local_id,
            "tipo": tipo,
            "status": status,
        },
    )


def get_data_plantao(engine: Any, data_id: int) -> dict | None:
    data_row = _row(
        engine,
        """
        SELECT d.*, l.nome AS local_nome, l.cidade AS local_cidade, l.uf AS local_uf
          FROM plantao_datas d
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.id = :id
        """,
        {"id": data_id},
    )
    if not data_row:
        return None
    data_row["posicoes"] = listar_posicoes_por_data(engine, data_id)
    data_row["candidaturas"] = listar_candidaturas_por_data(engine, data_id)
    data_row["sobreaviso"] = listar_sobreaviso_por_data(engine, data_id)
    return data_row


def listar_datas_com_vagas_abertas(
    engine: Any,
    local_id: int | None = None,
    tipo_perfil: str | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT d.id AS data_id,
               d.local_id,
               d.tipo AS data_tipo,
               d.subtipo AS data_subtipo,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.status,
               l.nome AS local_nome,
               p.id AS posicao_id,
               p.tipo AS tipo_perfil,
               p.vagas,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id
                    AND c.status = 'confirmado'
               ), 0) AS confirmados,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id
                    AND c.status = 'provisorio'
               ), 0) AS provisorios
          FROM plantao_datas d
          JOIN plantao_posicoes p ON p.data_id = d.id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.status = 'publicado'
           AND d.tipo = 'presencial'
           AND d.data >= :hoje
           AND (:local_id IS NULL OR d.local_id = :local_id)
           AND (:tipo_perfil IS NULL OR p.tipo = :tipo_perfil)
           AND p.vagas > COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id
                    AND c.status = 'confirmado'
               ), 0)
         ORDER BY d.data ASC, d.hora_inicio ASC, p.tipo ASC, p.id ASC
        """,
        {"hoje": _hoje(), "local_id": local_id, "tipo_perfil": tipo_perfil},
    )


def listar_posicoes_por_data(engine: Any, data_id: int) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT p.*,
               COALESCE((
                 SELECT COUNT(*) FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id AND c.status = 'confirmado'
               ), 0) AS confirmados,
               COALESCE((
                 SELECT COUNT(*) FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id AND c.status = 'provisorio'
               ), 0) AS provisorios,
               COALESCE((
                 SELECT COUNT(*) FROM plantao_candidaturas c
                  WHERE c.posicao_id = p.id AND c.status = 'lista_espera'
               ), 0) AS em_espera
          FROM plantao_posicoes p
         WHERE p.data_id = :data_id
         ORDER BY p.tipo ASC, p.id ASC
        """,
        {"data_id": data_id},
    )


def get_posicao(engine: Any, posicao_id: int) -> dict | None:
    return _row(
        engine,
        """
        SELECT p.*,
               d.local_id,
               d.tipo AS data_tipo,
               d.subtipo AS data_subtipo,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.status AS data_status
          FROM plantao_posicoes p
          JOIN plantao_datas d ON d.id = p.data_id
         WHERE p.id = :id
        """,
        {"id": posicao_id},
    )


def listar_candidaturas_por_data(
    engine: Any,
    data_id: int,
    status: str | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT c.*,
               p.tipo AS posicao_tipo,
               p.vagas AS posicao_vagas,
               d.id AS data_id,
               d.local_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.tipo AS data_tipo,
               d.subtipo AS data_subtipo,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.tipo AS perfil_tipo,
               pf.telefone AS perfil_telefone
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE p.data_id = :data_id
           AND (:status IS NULL OR c.status = :status)
         ORDER BY c.posicao_id ASC, c.status ASC, c.criado_em ASC, c.id ASC
        """,
        {"data_id": data_id, "status": status},
    )


def listar_candidaturas_pendentes(
    engine: Any,
    apenas_futuras: bool = True,
) -> list[dict]:
    """Lista candidaturas provisórias aguardando confirmação gestor, por data do turno."""
    hoje = _hoje()
    return _rows(
        engine,
        """
        SELECT c.*,
               p.tipo AS posicao_tipo,
               p.vagas AS posicao_vagas,
               d.id AS data_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               l.nome AS local_nome,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.tipo AS perfil_tipo
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE c.status = 'provisorio'
           AND (:apenas_futuras = 0 OR d.data >= :hoje)
         ORDER BY d.data ASC, d.hora_inicio ASC, c.criado_em ASC
        """,
        {"apenas_futuras": 1 if apenas_futuras else 0, "hoje": hoje},
    )


def contar_candidaturas_pendentes(engine: Any) -> int:
    hoje = _hoje()
    rows = _rows(
        engine,
        """
        SELECT COUNT(*) AS total
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
         WHERE c.status = 'provisorio'
           AND d.data >= :hoje
        """,
        {"hoje": hoje},
    )
    return int((rows[0]["total"] if rows else 0) or 0)


def listar_candidaturas_por_perfil(
    engine: Any,
    perfil_id: int,
    apenas_futuras: bool = False,
    status: str | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT c.*,
               p.tipo AS posicao_tipo,
               p.vagas AS posicao_vagas,
               d.id AS data_id,
               d.local_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.tipo AS data_tipo,
               d.subtipo AS data_subtipo,
               d.status AS data_status,
               l.nome AS local_nome
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE c.perfil_id = :perfil_id
           AND (:status IS NULL OR c.status = :status)
           AND (:apenas_futuras = 0 OR d.data >= :hoje)
         ORDER BY d.data DESC, d.hora_inicio DESC, c.id DESC
        """,
        {
            "perfil_id": perfil_id,
            "status": status,
            "apenas_futuras": 1 if apenas_futuras else 0,
            "hoje": _hoje(),
        },
    )


def get_candidatura(engine: Any, candidatura_id: int) -> dict | None:
    return _row(
        engine,
        """
        SELECT c.*,
               p.data_id,
               p.tipo AS posicao_tipo,
               p.vagas AS posicao_vagas,
               d.local_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.tipo AS data_tipo,
               d.subtipo AS data_subtipo,
               d.status AS data_status,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.tipo AS perfil_tipo
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE c.id = :id
        """,
        {"id": candidatura_id},
    )


def candidatura_existe(engine: Any, perfil_id: int, data_id: int) -> bool:
    row = _row(
        engine,
        """
        SELECT 1 AS existe
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
         WHERE c.perfil_id = :perfil_id
           AND p.data_id = :data_id
           AND c.status NOT IN ('cancelado', 'recusado')
         LIMIT 1
        """,
        {"perfil_id": perfil_id, "data_id": data_id},
    )
    return bool(row)


def contar_confirmados_por_posicao(engine: Any, posicao_id: int) -> int:
    row = _row(
        engine,
        """
        SELECT COUNT(*) AS total
          FROM plantao_candidaturas
         WHERE posicao_id = :posicao_id
           AND status = 'confirmado'
        """,
        {"posicao_id": posicao_id},
    )
    return int(row["total"]) if row else 0


def listar_trocas_por_perfil(
    engine: Any,
    perfil_id: int,
    status: str | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT t.*,
               ca.perfil_id AS perfil_a_id,
               pa.nome AS perfil_a_nome,
               pa.email AS perfil_a_email,
               pca.tipo AS posicao_a_tipo,
               da.id AS data_a_id,
               da.data AS data_a,
               da.hora_inicio AS hora_inicio_a,
               da.hora_fim AS hora_fim_a,
               cb.perfil_id AS perfil_b_id,
               pb.nome AS perfil_b_nome,
               pb.email AS perfil_b_email,
               pcb.tipo AS posicao_b_tipo,
               db.id AS data_b_id,
               db.data AS data_b,
               db.hora_inicio AS hora_inicio_b,
               db.hora_fim AS hora_fim_b
          FROM plantao_trocas t
          JOIN plantao_candidaturas ca ON ca.id = t.candidatura_a_id
          JOIN plantao_posicoes pca ON pca.id = ca.posicao_id
          JOIN plantao_datas da ON da.id = pca.data_id
          JOIN plantao_perfis pa ON pa.id = ca.perfil_id
          LEFT JOIN plantao_candidaturas cb ON cb.id = t.candidatura_b_id
          LEFT JOIN plantao_posicoes pcb ON pcb.id = cb.posicao_id
          LEFT JOIN plantao_datas db ON db.id = pcb.data_id
          LEFT JOIN plantao_perfis pb ON pb.id = cb.perfil_id
         WHERE (:status IS NULL OR t.status = :status)
           AND (
                ca.perfil_id = :perfil_id
                OR cb.perfil_id = :perfil_id
           )
         ORDER BY t.criado_em DESC, t.id DESC
        """,
        {"perfil_id": perfil_id, "status": status},
    )


def get_troca(engine: Any, troca_id: int) -> dict | None:
    return _row(
        engine,
        """
        SELECT t.*,
               ca.perfil_id AS perfil_a_id,
               pa.nome AS perfil_a_nome,
               pca.tipo AS posicao_a_tipo,
               da.id AS data_a_id,
               da.data AS data_a,
               da.hora_inicio AS hora_inicio_a,
               da.hora_fim AS hora_fim_a,
               cb.perfil_id AS perfil_b_id,
               pb.nome AS perfil_b_nome,
               pcb.tipo AS posicao_b_tipo,
               db.id AS data_b_id,
               db.data AS data_b,
               db.hora_inicio AS hora_inicio_b,
               db.hora_fim AS hora_fim_b
          FROM plantao_trocas t
          JOIN plantao_candidaturas ca ON ca.id = t.candidatura_a_id
          JOIN plantao_posicoes pca ON pca.id = ca.posicao_id
          JOIN plantao_datas da ON da.id = pca.data_id
          JOIN plantao_perfis pa ON pa.id = ca.perfil_id
          LEFT JOIN plantao_candidaturas cb ON cb.id = t.candidatura_b_id
          LEFT JOIN plantao_posicoes pcb ON pcb.id = cb.posicao_id
          LEFT JOIN plantao_datas db ON db.id = pcb.data_id
          LEFT JOIN plantao_perfis pb ON pb.id = cb.perfil_id
         WHERE t.id = :id
        """,
        {"id": troca_id},
    )


def listar_substituicoes_abertas(
    engine: Any,
    tipo_perfil: str,
    local_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT t.*,
               ca.perfil_id AS solicitante_id,
               pa.nome AS solicitante_nome,
               pa.email AS solicitante_email,
               d.id AS data_id,
               d.local_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.subtipo,
               p.tipo AS tipo_posicao,
               l.nome AS local_nome
          FROM plantao_trocas t
          JOIN plantao_candidaturas ca ON ca.id = t.candidatura_a_id
          JOIN plantao_posicoes p ON p.id = ca.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pa ON pa.id = ca.perfil_id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE t.tipo = 'substituicao'
           AND t.status = 'solicitado'
           AND t.candidatura_b_id IS NULL
           AND t.expira_em >= :agora
           AND p.tipo = :tipo_perfil
           AND d.status = 'publicado'
           AND d.data >= :hoje
           AND (:local_id IS NULL OR d.local_id = :local_id)
         ORDER BY d.data ASC, d.hora_inicio ASC, t.criado_em DESC
        """,
        {
            "agora": _agora(),
            "hoje": _hoje(),
            "tipo_perfil": tipo_perfil,
            "local_id": local_id,
        },
    )


def listar_sobreaviso_por_data(engine: Any, data_id: int) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT s.*,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.telefone AS perfil_telefone,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.local_id
          FROM plantao_sobreaviso s
          JOIN plantao_perfis pf ON pf.id = s.perfil_id
          JOIN plantao_datas d ON d.id = s.data_id
         WHERE s.data_id = :data_id
           AND s.status = 'ativo'
         ORDER BY s.prioridade ASC, s.id ASC
        """,
        {"data_id": data_id},
    )


def listar_sobreaviso_por_perfil(engine: Any, perfil_id: int) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT s.*,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.status AS data_status,
               d.local_id,
               l.nome AS local_nome
          FROM plantao_sobreaviso s
          JOIN plantao_datas d ON d.id = s.data_id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE s.perfil_id = :perfil_id
           AND s.status = 'ativo'
         ORDER BY d.data ASC, s.prioridade ASC
        """,
        {"perfil_id": perfil_id},
    )


def get_sobreaviso_ativo(
    engine: Any,
    data: str,
    hora: str,
    local_id: int | None = None,
) -> list[dict]:
    data_ref = date.fromisoformat(data)
    data_prev = (data_ref - timedelta(days=1)).isoformat()
    candidatos = _rows(
        engine,
        """
        SELECT d.id AS data_id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               s.prioridade,
               pf.nome,
               pf.telefone,
               pf.email
          FROM plantao_datas d
          JOIN plantao_sobreaviso s ON s.data_id = d.id AND s.status = 'ativo'
          JOIN plantao_perfis pf ON pf.id = s.perfil_id
         WHERE d.tipo = 'sobreaviso'
           AND d.status = 'publicado'
           AND d.data IN (:data, :data_prev)
           AND (:local_id IS NULL OR d.local_id = :local_id)
         ORDER BY s.prioridade ASC, s.id ASC
        """,
        {"data": data, "data_prev": data_prev, "local_id": local_id},
    )

    def _ativo(row: dict) -> bool:
        hi = row["hora_inicio"]
        hf = row["hora_fim"]
        if row["data"] == data:
            if hi < hf:
                return hi <= hora < hf
            return hora >= hi
        if row["data"] == data_prev and hi >= hf:
            return hora < hf
        return False

    return [
        {
            "nome": r["nome"],
            "telefone": r["telefone"],
            "prioridade": r["prioridade"],
            "email": r["email"],
        }
        for r in candidatos
        if _ativo(r)
    ]


def get_alertas_dashboard(engine: Any, dias: int = 7) -> dict:
    hoje = date.today()
    fim = (hoje + timedelta(days=max(dias, 0))).isoformat()
    hoje_iso = hoje.isoformat()

    datas_sem_vagas = _rows(
        engine,
        """
        SELECT d.id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.local_id,
               l.nome AS local_nome,
               COALESCE((
                 SELECT SUM(p.vagas) FROM plantao_posicoes p WHERE p.data_id = d.id
               ), 0) AS vagas_total,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                   JOIN plantao_posicoes p2 ON p2.id = c.posicao_id
                  WHERE p2.data_id = d.id
                    AND c.status = 'confirmado'
               ), 0) AS confirmados_total
          FROM plantao_datas d
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.status = 'publicado'
           AND d.tipo = 'presencial'
           AND d.data >= :hoje
           AND d.data <= :fim
           AND COALESCE((
                 SELECT COUNT(*) FROM plantao_posicoes p3 WHERE p3.data_id = d.id
               ), 0) > 0
           AND COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c2
                   JOIN plantao_posicoes p4 ON p4.id = c2.posicao_id
                  WHERE p4.data_id = d.id
                    AND c2.status = 'confirmado'
               ), 0) < COALESCE((
                 SELECT SUM(p5.vagas)
                   FROM plantao_posicoes p5
                  WHERE p5.data_id = d.id
               ), 0)
         ORDER BY d.data ASC, d.hora_inicio ASC
        """,
        {"hoje": hoje_iso, "fim": fim},
    )

    sobreaviso_vazio = _rows(
        engine,
        """
        SELECT d.id,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.local_id,
               l.nome AS local_nome
          FROM plantao_datas d
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.status = 'publicado'
           AND d.tipo = 'sobreaviso'
           AND d.data >= :hoje
           AND d.data <= :fim
           AND NOT EXISTS (
               SELECT 1
                 FROM plantao_sobreaviso s
                WHERE s.data_id = d.id
                  AND s.status = 'ativo'
           )
         ORDER BY d.data ASC, d.hora_inicio ASC
        """,
        {"hoje": hoje_iso, "fim": fim},
    )

    row = _row(
        engine,
        """
        SELECT COUNT(*) AS total
          FROM users
         WHERE status = 'pendente'
        """,
    )
    cadastros_pendentes = int(row["total"]) if row else 0

    return {
        "datas_sem_vagas": datas_sem_vagas,
        "sobreaviso_vazio": sobreaviso_vazio,
        "cadastros_pendentes": cadastros_pendentes,
    }


def relatorio_escalas_por_periodo(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    local_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT d.id,
               d.local_id,
               l.nome AS local_nome,
               d.tipo,
               d.subtipo,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.status,
               COALESCE((
                 SELECT SUM(p.vagas) FROM plantao_posicoes p WHERE p.data_id = d.id
               ), 0) AS vagas_total,
               COALESCE((
                 SELECT COUNT(*)
                   FROM plantao_candidaturas c
                   JOIN plantao_posicoes p2 ON p2.id = c.posicao_id
                  WHERE p2.data_id = d.id
                    AND c.status = 'confirmado'
               ), 0) AS confirmados_total
          FROM plantao_datas d
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE d.data >= :inicio
           AND d.data <= :fim
           AND (:local_id IS NULL OR d.local_id = :local_id)
         ORDER BY d.data ASC, d.hora_inicio ASC, d.id ASC
        """,
        {"inicio": data_inicio, "fim": data_fim, "local_id": local_id},
    )


def relatorio_participacao_por_plantonista(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    perfil_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT pf.id AS perfil_id,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.tipo AS perfil_tipo,
               COUNT(*) AS turnos_confirmados
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE c.status = 'confirmado'
           AND d.tipo = 'presencial'
           AND d.data >= :inicio
           AND d.data <= :fim
           AND (:perfil_id IS NULL OR pf.id = :perfil_id)
         GROUP BY pf.id, pf.nome, pf.email, pf.tipo
         ORDER BY turnos_confirmados DESC, pf.nome ASC
        """,
        {"inicio": data_inicio, "fim": data_fim, "perfil_id": perfil_id},
    )


def relatorio_cancelamentos_trocas(
    engine: Any,
    data_inicio: str,
    data_fim: str,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT 'cancelamento' AS evento_tipo,
               c.alterado_em AS evento_em,
               c.id AS referencia_id,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               c.status AS status_evento,
               c.motivo_recusa AS detalhe
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE c.status = 'cancelado'
           AND c.alterado_em >= :inicio_dt
           AND c.alterado_em <= :fim_dt
        UNION ALL
        SELECT CASE WHEN t.tipo = 'substituicao' THEN 'substituicao' ELSE 'troca' END AS evento_tipo,
               COALESCE(t.respondido_em, t.criado_em) AS evento_em,
               t.id AS referencia_id,
               pfa.nome AS perfil_nome,
               pfa.email AS perfil_email,
               da.data,
               da.hora_inicio,
               da.hora_fim,
               t.status AS status_evento,
               t.mensagem AS detalhe
          FROM plantao_trocas t
          JOIN plantao_candidaturas ca ON ca.id = t.candidatura_a_id
          JOIN plantao_posicoes pa ON pa.id = ca.posicao_id
          JOIN plantao_datas da ON da.id = pa.data_id
          JOIN plantao_perfis pfa ON pfa.id = ca.perfil_id
         WHERE COALESCE(t.respondido_em, t.criado_em) >= :inicio_dt
           AND COALESCE(t.respondido_em, t.criado_em) <= :fim_dt
         ORDER BY evento_em DESC
        """,
        {
            "inicio_dt": f"{data_inicio}T00:00:00",
            "fim_dt": f"{data_fim}T23:59:59",
        },
    )


def relatorio_pre_fechamento(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    local_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT c.id AS candidatura_id,
               pf.id AS perfil_id,
               pf.nome AS perfil_nome,
               pf.email AS perfil_email,
               pf.tipo AS tipo_perfil,
               d.id AS data_id,
               d.local_id,
               l.nome AS local_nome,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               d.subtipo,
               c.horas_turno,
               c.valor_hora_snapshot,
               c.valor_base_calculado
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
          LEFT JOIN plantao_locais l ON l.id = d.local_id
         WHERE c.status = 'confirmado'
           AND d.tipo = 'presencial'
           AND d.data >= :inicio
           AND d.data <= :fim
           AND (:local_id IS NULL OR d.local_id = :local_id)
         ORDER BY d.data ASC, pf.nome ASC, c.id ASC
        """,
        {"inicio": data_inicio, "fim": data_fim, "local_id": local_id},
    )


def get_fechamento_api(
    engine: Any,
    data_inicio: str,
    data_fim: str,
    local_id: int | None = None,
) -> list[dict]:
    return _rows(
        engine,
        """
        SELECT pf.email,
               pf.nome,
               d.data,
               d.hora_inicio,
               d.hora_fim,
               pf.tipo AS tipo_perfil,
               d.subtipo,
               c.horas_turno,
               c.valor_hora_snapshot,
               c.valor_base_calculado
          FROM plantao_candidaturas c
          JOIN plantao_posicoes p ON p.id = c.posicao_id
          JOIN plantao_datas d ON d.id = p.data_id
          JOIN plantao_perfis pf ON pf.id = c.perfil_id
         WHERE c.status = 'confirmado'
           AND d.tipo = 'presencial'
           AND d.data >= :inicio
           AND d.data <= :fim
           AND (:local_id IS NULL OR d.local_id = :local_id)
         ORDER BY d.data ASC, pf.nome ASC, c.id ASC
        """,
        {"inicio": data_inicio, "fim": data_fim, "local_id": local_id},
    )
