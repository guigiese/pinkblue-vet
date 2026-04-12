"""
Módulo Plantão — definições de schema e inicialização do banco.

Todas as tabelas usam o mesmo engine da plataforma (banco compartilhado).
Timestamps armazenados como TEXT (ISO 8601) para compatibilidade SQLite/PostgreSQL,
seguindo o padrão de pb_platform/storage.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any

from sqlalchemy import MetaData, Table, Column, Integer, Text, Float as Real, text

log = logging.getLogger(__name__)

metadata = MetaData()

# ── Locais ────────────────────────────────────────────────────────────────────

t_plantao_locais = Table(
    "plantao_locais", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nome", Text, nullable=False),
    Column("endereco", Text, nullable=False, server_default=""),
    Column("cidade", Text, nullable=False, server_default=""),
    Column("uf", Text, nullable=False, server_default=""),
    Column("telefone", Text, nullable=False, server_default=""),
    Column("ativo", Integer, nullable=False, server_default="1"),
    Column("criado_em", Text, nullable=False),
    Column("alterado_em", Text, nullable=False),
)

# ── Perfis de plantonistas ────────────────────────────────────────────────────

t_plantao_perfis = Table(
    "plantao_perfis", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nome", Text, nullable=False),
    Column("email", Text, nullable=False, unique=True),
    Column("senha_hash", Text, nullable=False),
    # tipo: 'veterinario' | 'auxiliar'
    Column("tipo", Text, nullable=False),
    Column("crmv", Text, nullable=True),
    Column("especialidade", Text, nullable=False, server_default=""),
    Column("telefone", Text, nullable=False, server_default=""),
    # status: 'pendente' | 'ativo' | 'inativo' | 'rejeitado'
    Column("status", Text, nullable=False, server_default="pendente"),
    Column("motivo_rejeicao", Text, nullable=True),
    Column("tentativas_login", Integer, nullable=False, server_default="0"),
    Column("bloqueado_ate", Text, nullable=True),
    Column("reset_token", Text, nullable=True, unique=True),
    Column("reset_token_expira", Text, nullable=True),
    Column("criado_em", Text, nullable=False),
    Column("alterado_em", Text, nullable=False),
    Column("aprovado_em", Text, nullable=True),
    Column("aprovado_por", Integer, nullable=True),  # users.id
)

# ── Sessões dos plantonistas ──────────────────────────────────────────────────

t_plantao_sessoes = Table(
    "plantao_sessoes", metadata,
    Column("id", Text, primary_key=True),           # secrets.token_hex(32)
    Column("perfil_id", Integer, nullable=False),
    Column("criada_em", Text, nullable=False),
    Column("expira_em", Text, nullable=False),
    Column("ultimo_acesso", Text, nullable=False),
    Column("ip", Text, nullable=False, server_default=""),
    Column("user_agent", Text, nullable=False, server_default=""),
)

# ── Tarifas ───────────────────────────────────────────────────────────────────

t_plantao_tarifas = Table(
    "plantao_tarifas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # tipo_perfil: 'veterinario' | 'auxiliar'
    Column("tipo_perfil", Text, nullable=False),
    # dia_semana: 0=seg…6=dom, 7=feriado, NULL=qualquer (auxiliar)
    Column("dia_semana", Integer, nullable=True),
    # subtipo_turno: 'regular'|'substituicao'|'feriado'|NULL=qualquer
    Column("subtipo_turno", Text, nullable=True),
    Column("valor_hora", Real, nullable=False),
    Column("vigente_de", Text, nullable=False, server_default="2000-01-01"),
    Column("vigente_ate", Text, nullable=True),
    Column("criado_em", Text, nullable=False),
    Column("criado_por", Integer, nullable=True),  # users.id
)

# ── Feriados ─────────────────────────────────────────────────────────────────

t_plantao_feriados = Table(
    "plantao_feriados", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("data", Text, nullable=False),            # YYYY-MM-DD
    Column("nome", Text, nullable=False),
    # tipo: 'nacional' | 'estadual' | 'municipal'
    Column("tipo", Text, nullable=False, server_default="nacional"),
    # local_id: NULL=todos os locais; ID=específico de um local
    Column("local_id", Integer, nullable=True),
)

# ── Datas de plantão ──────────────────────────────────────────────────────────

t_plantao_datas = Table(
    "plantao_datas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("local_id", Integer, nullable=False),
    # tipo: 'presencial' | 'sobreaviso'
    Column("tipo", Text, nullable=False, server_default="presencial"),
    # subtipo: 'regular' | 'substituicao' | 'feriado' | 'sobreaviso_emergencia'
    Column("subtipo", Text, nullable=False, server_default="regular"),
    Column("data", Text, nullable=False),            # YYYY-MM-DD
    Column("hora_inicio", Text, nullable=False),     # HH:MM
    Column("hora_fim", Text, nullable=False),        # HH:MM (pode ser < hora_inicio = overnight)
    Column("observacoes", Text, nullable=False, server_default=""),
    # status: 'rascunho' | 'publicado' | 'cancelado' | 'encerrado'
    Column("status", Text, nullable=False, server_default="rascunho"),
    Column("publicado_em", Text, nullable=True),
    Column("publicado_por", Integer, nullable=True),  # users.id
    Column("criado_em", Text, nullable=False),
    Column("alterado_em", Text, nullable=False),
    Column("criado_por", Integer, nullable=False),   # users.id
)

# ── Posições (vagas) por data ─────────────────────────────────────────────────

t_plantao_posicoes = Table(
    "plantao_posicoes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("data_id", Integer, nullable=False),
    # tipo: 'veterinario' | 'auxiliar'
    Column("tipo", Text, nullable=False),
    Column("vagas", Integer, nullable=False, server_default="1"),
)

# ── Candidaturas ─────────────────────────────────────────────────────────────

t_plantao_candidaturas = Table(
    "plantao_candidaturas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("posicao_id", Integer, nullable=False),
    Column("perfil_id", Integer, nullable=False),
    # status: 'provisorio' | 'confirmado' | 'cancelado' | 'recusado' | 'lista_espera'
    Column("status", Text, nullable=False, server_default="provisorio"),
    Column("ordem_espera", Integer, nullable=True),
    Column("motivo_recusa", Text, nullable=True),
    # cancelado_dentro_prazo: 1=sim, 0=não, NULL=não cancelado
    Column("cancelado_dentro_prazo", Integer, nullable=True),
    Column("criado_em", Text, nullable=False),
    Column("alterado_em", Text, nullable=False),
    Column("confirmado_em", Text, nullable=True),
    Column("confirmado_por", Integer, nullable=True),  # users.id
    # campos de remuneração — preenchidos somente ao confirmar
    Column("valor_hora_snapshot", Real, nullable=True),
    Column("valor_base_calculado", Real, nullable=True),
    Column("horas_turno", Real, nullable=True),
)

# ── Trocas e substituições ────────────────────────────────────────────────────

t_plantao_trocas = Table(
    "plantao_trocas", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # tipo: 'troca_direta' | 'substituicao'
    Column("tipo", Text, nullable=False),
    Column("candidatura_a_id", Integer, nullable=False),
    Column("candidatura_b_id", Integer, nullable=True),   # NULL para substituição aberta
    # status: 'solicitado' | 'aceito' | 'recusado' | 'cancelado' | 'expirado'
    Column("status", Text, nullable=False, server_default="solicitado"),
    Column("mensagem", Text, nullable=False, server_default=""),
    Column("respondido_em", Text, nullable=True),
    Column("criado_em", Text, nullable=False),
    Column("expira_em", Text, nullable=False),
)

# ── Sobreaviso (adesões à escala de disponibilidade) ─────────────────────────

t_plantao_sobreaviso = Table(
    "plantao_sobreaviso", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("data_id", Integer, nullable=False),
    Column("perfil_id", Integer, nullable=False),
    Column("prioridade", Integer, nullable=False),
    # status: 'ativo' | 'cancelado'
    Column("status", Text, nullable=False, server_default="ativo"),
    Column("criado_em", Text, nullable=False),
    Column("cancelado_em", Text, nullable=True),
)

# ── Notificações ─────────────────────────────────────────────────────────────

t_plantao_notificacoes = Table(
    "plantao_notificacoes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("perfil_id", Integer, nullable=False),
    Column("tipo", Text, nullable=False),
    Column("titulo", Text, nullable=False),
    Column("corpo", Text, nullable=False, server_default=""),
    Column("lida", Integer, nullable=False, server_default="0"),
    Column("entidade", Text, nullable=True),
    Column("entidade_id", Integer, nullable=True),
    Column("criado_em", Text, nullable=False),
    Column("lida_em", Text, nullable=True),
)

# ── Audit log (imutável) ──────────────────────────────────────────────────────

t_plantao_audit = Table(
    "plantao_audit_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("acao", Text, nullable=False),
    Column("entidade", Text, nullable=False),
    Column("entidade_id", Integer, nullable=True),
    # ator_tipo: 'perfil' | 'gestor' | 'sistema'
    Column("ator_tipo", Text, nullable=False),
    Column("ator_id", Integer, nullable=True),
    Column("dados", Text, nullable=True),   # JSON serializado
    Column("ip", Text, nullable=False, server_default=""),
    Column("criado_em", Text, nullable=False),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ── Inicialização ─────────────────────────────────────────────────────────────

_DDL_PG = """
CREATE TABLE IF NOT EXISTS app_kv (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plantao_locais (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL,
    endereco    TEXT NOT NULL DEFAULT '',
    cidade      TEXT NOT NULL DEFAULT '',
    uf          TEXT NOT NULL DEFAULT '',
    telefone    TEXT NOT NULL DEFAULT '',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT NOT NULL,
    alterado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plantao_locais_ativo ON plantao_locais(ativo);

CREATE TABLE IF NOT EXISTS plantao_tarifas (
    id              SERIAL PRIMARY KEY,
    tipo_perfil     TEXT NOT NULL,
    dia_semana      INTEGER,
    subtipo_turno   TEXT,
    valor_hora      REAL NOT NULL,
    vigente_de      TEXT NOT NULL DEFAULT '2000-01-01',
    vigente_ate     TEXT,
    criado_em       TEXT NOT NULL,
    criado_por      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_plantao_tarifas_lookup ON plantao_tarifas(tipo_perfil, dia_semana, vigente_de);

CREATE TABLE IF NOT EXISTS plantao_feriados (
    id       SERIAL PRIMARY KEY,
    data     TEXT NOT NULL,
    nome     TEXT NOT NULL,
    tipo     TEXT NOT NULL DEFAULT 'nacional',
    local_id INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_feriados_uniq ON plantao_feriados(data, tipo, COALESCE(local_id::TEXT, 'null'));
CREATE INDEX IF NOT EXISTS idx_plantao_feriados_data ON plantao_feriados(data);

CREATE TABLE IF NOT EXISTS plantao_datas (
    id           SERIAL PRIMARY KEY,
    local_id     INTEGER NOT NULL,
    tipo         TEXT NOT NULL DEFAULT 'presencial',
    subtipo      TEXT NOT NULL DEFAULT 'regular',
    data         TEXT NOT NULL,
    hora_inicio  TEXT NOT NULL,
    hora_fim     TEXT NOT NULL,
    observacoes  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'rascunho',
    publicado_em TEXT,
    publicado_por INTEGER,
    criado_em    TEXT NOT NULL,
    alterado_em  TEXT NOT NULL,
    criado_por   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plantao_datas_local_data ON plantao_datas(local_id, data);
CREATE INDEX IF NOT EXISTS idx_plantao_datas_status ON plantao_datas(status);

CREATE TABLE IF NOT EXISTS plantao_posicoes (
    id       SERIAL PRIMARY KEY,
    data_id  INTEGER NOT NULL,
    tipo     TEXT NOT NULL,
    vagas    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_plantao_posicoes_data ON plantao_posicoes(data_id);

CREATE TABLE IF NOT EXISTS plantao_candidaturas (
    id                      SERIAL PRIMARY KEY,
    posicao_id              INTEGER NOT NULL,
    perfil_id               INTEGER NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'provisorio',
    ordem_espera            INTEGER,
    motivo_recusa           TEXT,
    cancelado_dentro_prazo  INTEGER,
    criado_em               TEXT NOT NULL,
    alterado_em             TEXT NOT NULL,
    confirmado_em           TEXT,
    confirmado_por          INTEGER,
    valor_hora_snapshot     REAL,
    valor_base_calculado    REAL,
    horas_turno             REAL
);
CREATE INDEX IF NOT EXISTS idx_plantao_cand_posicao_status ON plantao_candidaturas(posicao_id, status);
CREATE INDEX IF NOT EXISTS idx_plantao_cand_perfil_status ON plantao_candidaturas(perfil_id, status);

CREATE TABLE IF NOT EXISTS plantao_trocas (
    id                 SERIAL PRIMARY KEY,
    tipo               TEXT NOT NULL,
    candidatura_a_id   INTEGER NOT NULL,
    candidatura_b_id   INTEGER,
    status             TEXT NOT NULL DEFAULT 'solicitado',
    mensagem           TEXT NOT NULL DEFAULT '',
    respondido_em      TEXT,
    criado_em          TEXT NOT NULL,
    expira_em          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plantao_trocas_status ON plantao_trocas(status);

CREATE TABLE IF NOT EXISTS plantao_sobreaviso (
    id           SERIAL PRIMARY KEY,
    data_id      INTEGER NOT NULL,
    perfil_id    INTEGER NOT NULL,
    prioridade   INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'ativo',
    criado_em    TEXT NOT NULL,
    cancelado_em TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_sobreaviso_ativo ON plantao_sobreaviso(data_id, perfil_id) WHERE status = 'ativo';
CREATE UNIQUE INDEX IF NOT EXISTS idx_plantao_sobreaviso_prio ON plantao_sobreaviso(data_id, prioridade) WHERE status = 'ativo';

CREATE TABLE IF NOT EXISTS plantao_notificacoes (
    id          SERIAL PRIMARY KEY,
    perfil_id   INTEGER NOT NULL,
    tipo        TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    corpo       TEXT NOT NULL DEFAULT '',
    lida        INTEGER NOT NULL DEFAULT 0,
    entidade    TEXT,
    entidade_id INTEGER,
    criado_em   TEXT NOT NULL,
    lida_em     TEXT
);
CREATE INDEX IF NOT EXISTS idx_plantao_notif_perfil_lida ON plantao_notificacoes(perfil_id, lida);

CREATE TABLE IF NOT EXISTS plantao_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    acao        TEXT NOT NULL,
    entidade    TEXT NOT NULL,
    entidade_id INTEGER,
    ator_tipo   TEXT NOT NULL,
    ator_id     INTEGER,
    dados       TEXT,
    ip          TEXT NOT NULL DEFAULT '',
    criado_em   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plantao_audit_acao ON plantao_audit_log(acao);
CREATE INDEX IF NOT EXISTS idx_plantao_audit_entidade ON plantao_audit_log(entidade, entidade_id);
CREATE INDEX IF NOT EXISTS idx_plantao_audit_criado ON plantao_audit_log(criado_em);

ALTER TABLE users ADD COLUMN IF NOT EXISTS gestor_plantao INTEGER NOT NULL DEFAULT 0;
"""

# SQLite-compatible DDL (sem SERIAL, sem BIGSERIAL, sem partial indexes, sem ALTER ADD IF NOT EXISTS)
_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS app_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plantao_locais (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
    endereco TEXT NOT NULL DEFAULT '', cidade TEXT NOT NULL DEFAULT '',
    uf TEXT NOT NULL DEFAULT '', telefone TEXT NOT NULL DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1, criado_em TEXT NOT NULL, alterado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plantao_tarifas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tipo_perfil TEXT NOT NULL, dia_semana INTEGER,
    subtipo_turno TEXT, valor_hora REAL NOT NULL, vigente_de TEXT NOT NULL DEFAULT '2000-01-01',
    vigente_ate TEXT, criado_em TEXT NOT NULL, criado_por INTEGER
);
CREATE TABLE IF NOT EXISTS plantao_feriados (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'nacional', local_id INTEGER
);
CREATE TABLE IF NOT EXISTS plantao_datas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, local_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'presencial', subtipo TEXT NOT NULL DEFAULT 'regular',
    data TEXT NOT NULL, hora_inicio TEXT NOT NULL, hora_fim TEXT NOT NULL,
    observacoes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'rascunho',
    publicado_em TEXT, publicado_por INTEGER, criado_em TEXT NOT NULL,
    alterado_em TEXT NOT NULL, criado_por INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS plantao_posicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data_id INTEGER NOT NULL,
    tipo TEXT NOT NULL, vagas INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS plantao_candidaturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, posicao_id INTEGER NOT NULL,
    perfil_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'provisorio',
    ordem_espera INTEGER, motivo_recusa TEXT, cancelado_dentro_prazo INTEGER,
    criado_em TEXT NOT NULL, alterado_em TEXT NOT NULL, confirmado_em TEXT, confirmado_por INTEGER,
    valor_hora_snapshot REAL, valor_base_calculado REAL, horas_turno REAL
);
CREATE TABLE IF NOT EXISTS plantao_trocas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL,
    candidatura_a_id INTEGER NOT NULL, candidatura_b_id INTEGER,
    status TEXT NOT NULL DEFAULT 'solicitado', mensagem TEXT NOT NULL DEFAULT '',
    respondido_em TEXT, criado_em TEXT NOT NULL, expira_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plantao_sobreaviso (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data_id INTEGER NOT NULL,
    perfil_id INTEGER NOT NULL, prioridade INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ativo', criado_em TEXT NOT NULL, cancelado_em TEXT
);
CREATE TABLE IF NOT EXISTS plantao_notificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, perfil_id INTEGER NOT NULL, tipo TEXT NOT NULL,
    titulo TEXT NOT NULL, corpo TEXT NOT NULL DEFAULT '', lida INTEGER NOT NULL DEFAULT 0,
    entidade TEXT, entidade_id INTEGER, criado_em TEXT NOT NULL, lida_em TEXT
);
CREATE TABLE IF NOT EXISTS plantao_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, entidade TEXT NOT NULL,
    entidade_id INTEGER, ator_tipo TEXT NOT NULL, ator_id INTEGER,
    dados TEXT, ip TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL
);
"""

_FERIADOS_NACIONAIS_2026 = [
    ("2026-01-01", "Confraternização Universal", "nacional"),
    ("2026-02-16", "Carnaval (segunda)", "nacional"),
    ("2026-02-17", "Carnaval (terça)", "nacional"),
    ("2026-02-18", "Quarta de Cinzas (ponto facultativo)", "nacional"),
    ("2026-04-03", "Sexta-feira Santa", "nacional"),
    ("2026-04-21", "Tiradentes", "nacional"),
    ("2026-05-01", "Dia do Trabalhador", "nacional"),
    ("2026-06-04", "Corpus Christi", "nacional"),
    ("2026-09-07", "Independência do Brasil", "nacional"),
    ("2026-10-12", "Nossa Senhora Aparecida", "nacional"),
    ("2026-11-02", "Finados", "nacional"),
    ("2026-11-15", "Proclamação da República", "nacional"),
    ("2026-11-20", "Consciência Negra", "nacional"),
    ("2026-12-25", "Natal", "nacional"),
]

_FERIADOS_NACIONAIS_2027 = [
    ("2027-01-01", "Confraternização Universal", "nacional"),
    ("2027-03-01", "Carnaval (segunda)", "nacional"),
    ("2027-03-02", "Carnaval (terça)", "nacional"),
    ("2027-03-03", "Quarta de Cinzas (ponto facultativo)", "nacional"),
    ("2027-04-02", "Sexta-feira Santa", "nacional"),
    ("2027-04-21", "Tiradentes", "nacional"),
    ("2027-05-01", "Dia do Trabalhador", "nacional"),
    ("2027-06-24", "Corpus Christi", "nacional"),
    ("2027-09-07", "Independência do Brasil", "nacional"),
    ("2027-10-12", "Nossa Senhora Aparecida", "nacional"),
    ("2027-11-02", "Finados", "nacional"),
    ("2027-11-15", "Proclamação da República", "nacional"),
    ("2027-11-20", "Consciência Negra", "nacional"),
    ("2027-12-25", "Natal", "nacional"),
]

# Feriados municipais de Passo de Torres/SC (local_id=1 = Pink Blue Passo de Torres)
_FERIADOS_MUNICIPAIS_PASSO_TORRES = [
    ("2026-03-12", "Aniversário de Passo de Torres", "municipal"),
    ("2027-03-12", "Aniversário de Passo de Torres", "municipal"),
]

# Feriados estaduais de SC
_FERIADOS_ESTADUAIS_SC = [
    ("2026-08-11", "Dia de Santa Catarina", "estadual"),
    ("2027-08-11", "Dia de Santa Catarina", "estadual"),
]


_VIEW_PLANTAO_PERFIS_SQLITE = """
CREATE VIEW IF NOT EXISTS plantao_perfis AS
SELECT
    id,
    nome,
    email,
    password_hash AS senha_hash,
    role          AS tipo,
    crmv,
    ''            AS especialidade,
    telefone,
    status,
    NULL          AS motivo_rejeicao,
    tentativas_login,
    bloqueado_ate,
    NULL          AS reset_token,
    NULL          AS reset_token_expira,
    created_at    AS criado_em,
    updated_at    AS alterado_em,
    NULL          AS aprovado_em,
    NULL          AS aprovado_por
FROM users
WHERE role IN ('veterinario', 'auxiliar')
"""


def _migrate_remove_old_plantao_auth(conn) -> None:
    """
    Remove tabelas isoladas de auth do plantão (plantao_perfis e plantao_sessoes)
    caso ainda existam como tabelas — elas são substituídas pela VIEW sobre users
    e pela tabela user_sessions da plataforma.
    """
    for table in ("plantao_perfis", "plantao_sessoes"):
        row = conn.execute(
            text("SELECT type FROM sqlite_master WHERE name = :n"),
            {"n": table},
        ).fetchone()
        if row and row[0] == "table":
            conn.execute(text(f"DROP TABLE {table}"))
            log.info("Migração: tabela isolada '%s' removida (substituída por auth unificada).", table)


def init_schema(engine) -> None:
    """
    Cria todas as tabelas do módulo Plantão se não existirem.
    Seguro para chamar múltiplas vezes (idempotente).
    Deve ser chamado no startup da aplicação, após a store da plataforma ser inicializada.
    """
    is_pg = engine.dialect.name == "postgresql"
    ddl = _DDL_PG if is_pg else _DDL_SQLITE

    with engine.begin() as conn:
        # SQLite: migra tabelas antigas → VIEW sobre users
        if not is_pg:
            _migrate_remove_old_plantao_auth(conn)

        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    # Ignorar erros de "já existe" — outros erros relançar
                    msg = str(e).lower()
                    if "already exists" in msg or "duplicate column" in msg:
                        log.debug("Schema já existia (ok): %s", str(e)[:80])
                    else:
                        log.error("Erro ao criar schema plantão: %s\n%s", stmt[:80], e)
                        raise

        # Cria a VIEW plantao_perfis (SQLite) após as tabelas do DDL
        if not is_pg:
            try:
                conn.execute(text(_VIEW_PLANTAO_PERFIS_SQLITE))
            except Exception as e:
                msg = str(e).lower()
                if "already exists" not in msg:
                    log.error("Erro ao criar VIEW plantao_perfis: %s", e)
                    raise

    _seed_defaults(engine, is_pg)
    log.info("Módulo Plantão: schema inicializado.")


def _seed_defaults(engine, is_pg: bool) -> None:
    """Insere dados padrão se ainda não existirem."""
    now = _now()

    with engine.begin() as conn:
        # Local padrão
        existing = conn.execute(
            text("SELECT id FROM plantao_locais WHERE nome = :n"),
            {"n": "Pink Blue Passo de Torres"}
        ).fetchone()
        if not existing:
            conn.execute(text(
                "INSERT INTO plantao_locais (nome, cidade, uf, ativo, criado_em, alterado_em)"
                " VALUES (:n, :c, :uf, 1, :t, :t)"
            ), {"n": "Pink Blue Passo de Torres", "c": "Passo de Torres", "uf": "SC", "t": now})
            log.info("Seed: local padrão inserido.")

        # Feriados
        todos_feriados = (
            [(d, n, t, None) for d, n, t in _FERIADOS_NACIONAIS_2026] +
            [(d, n, t, None) for d, n, t in _FERIADOS_NACIONAIS_2027] +
            [(d, n, t, None) for d, n, t in _FERIADOS_ESTADUAIS_SC]
        )
        # Municipais de Passo de Torres — associar ao local_id=1 (já inserido acima)
        local_row = conn.execute(
            text("SELECT id FROM plantao_locais WHERE nome = :n"),
            {"n": "Pink Blue Passo de Torres"}
        ).fetchone()
        local_id = local_row[0] if local_row else 1

        for d, n, t in _FERIADOS_MUNICIPAIS_PASSO_TORRES:
            todos_feriados.append((d, n, t, local_id))

        for data, nome, tipo, lid in todos_feriados:
            exists = conn.execute(
                text("SELECT id FROM plantao_feriados WHERE data = :d AND tipo = :t AND (:lid IS NULL AND local_id IS NULL OR local_id = :lid)"),
                {"d": data, "t": tipo, "lid": lid}
            ).fetchone()
            if not exists:
                conn.execute(text(
                    "INSERT INTO plantao_feriados (data, nome, tipo, local_id) VALUES (:d, :n, :t, :lid)"
                ), {"d": data, "n": nome, "t": tipo, "lid": lid})

        # Tarifa padrão para auxiliar (valor configurável — R$15/h como default)
        aux_exists = conn.execute(
            text("SELECT id FROM plantao_tarifas WHERE tipo_perfil = 'auxiliar' AND dia_semana IS NULL"),
        ).fetchone()
        if not aux_exists:
            conn.execute(text(
                "INSERT INTO plantao_tarifas (tipo_perfil, dia_semana, subtipo_turno, valor_hora, vigente_de, criado_em)"
                " VALUES ('auxiliar', NULL, NULL, 15.0, '2026-01-01', :t)"
            ), {"t": now})
            log.info("Seed: tarifa padrão auxiliar inserida (R$15/h).")
