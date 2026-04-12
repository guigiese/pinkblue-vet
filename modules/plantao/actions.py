"""
Modulo Plantao - acoes de escrita (mutations).
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from pb_platform.security import hash_password, verify_password

from .audit import audit
from .auth import revogar_todas_sessoes
from .business import (
    calcular_horas_turno,
    calcular_valor_base,
    inferir_subtipo,
    pode_cancelar,
)
from .notifications import notificar
from .queries import (
    candidatura_existe,
    contar_confirmados_por_posicao,
    get_candidatura,
    get_data_plantao,
    get_perfil_por_email,
    get_perfil_por_id,
    get_posicao,
    get_set_feriados,
    get_troca,
    listar_candidaturas_por_data,
    listar_sobreaviso_por_data,
    listar_tarifas_vigentes,
)


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _to_dt(data_ref: str, hora_ref: str) -> datetime:
    return datetime.fromisoformat(f"{data_ref}T{hora_ref}:00")


def _hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _insert_and_get_id(conn: Any, sql: str, params: dict, lookup_sql: str, lookup_params: dict) -> int:
    result = conn.execute(text(sql), params)
    row_id = getattr(result, "lastrowid", None)
    if row_id:
        return int(row_id)
    row = conn.execute(text(lookup_sql), lookup_params).mappings().first()
    if not row:
        raise ValueError("Falha ao obter ID da linha criada.")
    return int(row["id"])


def _app_kv_get(conn: Any, chave: str) -> str | None:
    try:
        row = conn.execute(
            text("SELECT value FROM app_kv WHERE key = :k"),
            {"k": chave},
        ).mappings().first()
        return row["value"] if row else None
    except Exception:
        row = conn.execute(
            text("SELECT valor FROM app_kv WHERE chave = :k"),
            {"k": chave},
        ).mappings().first()
        return row["valor"] if row else None


def _app_kv_set(conn: Any, chave: str, valor: str) -> None:
    agora = _utcnow()
    try:
        conn.execute(
            text(
                "INSERT INTO app_kv (key, value, updated_at) VALUES (:k, :v, :ts) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
            ),
            {"k": chave, "v": valor, "ts": agora},
        )
    except Exception:
        conn.execute(
            text(
                "INSERT INTO app_kv (chave, valor, alterado_em) VALUES (:k, :v, :ts) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, alterado_em=excluded.alterado_em"
            ),
            {"k": chave, "v": valor, "ts": agora},
        )


def _prazo_cancelamento_horas_uteis(conn: Any) -> int:
    raw = _app_kv_get(conn, "plantao_prazo_cancelamento_horas_uteis")
    if not raw:
        return 24
    try:
        return max(1, int(raw))
    except Exception:
        return 24


def _calcular_snapshot_remuneracao(
    engine: Any,
    perfil_tipo: str,
    data_turno: dict,
) -> tuple[float | None, float | None, float]:
    horas = calcular_horas_turno(data_turno["hora_inicio"], data_turno["hora_fim"])
    feriados = get_set_feriados(
        engine,
        data_turno["data"],
        data_turno["data"],
        data_turno.get("local_id"),
    )
    dia = date.fromisoformat(data_turno["data"])
    is_feriado = dia in feriados
    tarifas = listar_tarifas_vigentes(engine, data_turno["data"])
    valor_hora, valor_base = calcular_valor_base(
        tipo_perfil=perfil_tipo,
        dia_semana=dia.weekday(),
        is_feriado=is_feriado,
        subtipo=data_turno["subtipo"],
        horas=horas,
        tarifas=tarifas,
    )
    return valor_hora, valor_base, horas


def cadastrar_plantonista(
    engine: Any,
    nome: str,
    email: str,
    senha: str,
    tipo: str,
    crmv: str | None = None,
    especialidade: str = "",
    telefone: str = "",
) -> int:
    email_n = email.strip().lower()
    if get_perfil_por_email(engine, email_n):
        raise ValueError("Ja existe cadastro com este e-mail.")
    if tipo not in ("veterinario", "auxiliar"):
        raise ValueError("Tipo invalido.")
    if tipo == "veterinario" and not (crmv or "").strip():
        raise ValueError("CRMV e obrigatorio para veterinarios.")
    if len(senha) < 8:
        raise ValueError("A senha deve ter no minimo 8 caracteres.")

    agora = _utcnow()
    senha_hash = hash_password(senha)
    with engine.begin() as conn:
        perfil_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_perfis
                (nome, email, senha_hash, tipo, crmv, especialidade, telefone, status, criado_em, alterado_em)
            VALUES
                (:nome, :email, :senha_hash, :tipo, :crmv, :especialidade, :telefone, 'pendente', :agora, :agora)
            """,
            {
                "nome": nome.strip(),
                "email": email_n,
                "senha_hash": senha_hash,
                "tipo": tipo,
                "crmv": (crmv or "").strip() or None,
                "especialidade": especialidade.strip(),
                "telefone": telefone.strip(),
                "agora": agora,
            },
            "SELECT id FROM plantao_perfis WHERE email = :email",
            {"email": email_n},
        )

    audit(
        engine,
        "perfil.cadastrado",
        perfil_id=perfil_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )
    return perfil_id


def aprovar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")
    if perfil["status"] != "pendente":
        raise ValueError("Apenas cadastros pendentes podem ser aprovados.")

    agora = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_perfis "
                "SET status='ativo', aprovado_em=:agora, aprovado_por=:gestor_id, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"agora": agora, "gestor_id": gestor_id, "id": perfil_id},
        )

    audit(
        engine,
        "perfil.aprovado",
        gestor_id=gestor_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "cadastro_aprovado",
        "Cadastro aprovado",
        "Seu cadastro foi aprovado. Voce ja pode fazer login no modulo de Plantao.",
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )


def rejeitar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    motivo: str = "",
    ip: str = "",
) -> None:
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")
    if perfil["status"] != "pendente":
        raise ValueError("Apenas cadastros pendentes podem ser rejeitados.")

    agora = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_perfis "
                "SET status='rejeitado', motivo_rejeicao=:motivo, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"motivo": motivo.strip(), "agora": agora, "id": perfil_id},
        )

    audit(
        engine,
        "perfil.rejeitado",
        gestor_id=gestor_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
        detalhes=motivo.strip(),
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "cadastro_rejeitado",
        "Cadastro rejeitado",
        motivo.strip() or "Seu cadastro foi rejeitado. Entre em contato com a clinica.",
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )


def desativar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")
    if perfil["status"] != "ativo":
        raise ValueError("Somente plantonista ativo pode ser desativado.")

    agora = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE plantao_perfis SET status='inativo', alterado_em=:agora WHERE id=:id"),
            {"agora": agora, "id": perfil_id},
        )

    revogar_todas_sessoes(engine, perfil_id)
    audit(
        engine,
        "perfil.desativado",
        gestor_id=gestor_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "perfil_desativado",
        "Conta desativada",
        "Seu acesso ao modulo de Plantao foi desativado por um gestor.",
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )


def atualizar_perfil(
    engine: Any,
    perfil_id: int,
    dados: dict,
    ip: str = "",
) -> None:
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")

    campos = {}
    for k in ("nome", "telefone", "especialidade"):
        if k in dados:
            campos[k] = (dados[k] or "").strip()
    if not campos:
        return

    campos["alterado_em"] = _utcnow()
    sets = ", ".join(f"{k} = :{k}" for k in campos.keys())
    params = {**campos, "id": perfil_id}

    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE plantao_perfis SET {sets} WHERE id = :id"),
            params,
        )

    audit(
        engine,
        "perfil.atualizado",
        perfil_id=perfil_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
        detalhes=json.dumps(campos, ensure_ascii=False),
        ip=ip,
    )


def alterar_senha(
    engine: Any,
    perfil_id: int,
    senha_atual: str,
    senha_nova: str,
    ip: str = "",
) -> None:
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")
    if not verify_password(senha_atual, perfil["senha_hash"]):
        raise ValueError("Senha atual incorreta.")
    if len(senha_nova) < 8:
        raise ValueError("A senha nova deve ter no minimo 8 caracteres.")

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE plantao_perfis SET senha_hash=:h, alterado_em=:agora WHERE id=:id"),
            {"h": hash_password(senha_nova), "agora": _utcnow(), "id": perfil_id},
        )

    audit(
        engine,
        "perfil.senha_alterada",
        perfil_id=perfil_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
        ip=ip,
    )


def iniciar_reset_senha(engine: Any, email: str) -> str | None:
    perfil = get_perfil_por_email(engine, email.strip().lower())
    if not perfil:
        return None

    token_raw = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(token_raw)
    expira = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_perfis "
                "SET reset_token=:tok, reset_token_expira=:expira, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"tok": token_hash, "expira": expira, "agora": _utcnow(), "id": perfil["id"]},
        )

    audit(
        engine,
        "perfil.reset_senha_solicitado",
        perfil_id=perfil["id"],
        entidade="plantao_perfis",
        entidade_id=perfil["id"],
    )
    return token_raw


def confirmar_reset_senha(engine: Any, token_raw: str, nova_senha: str) -> bool:
    if len(nova_senha) < 8:
        return False
    token_hash = _hash_reset_token(token_raw)
    agora = _utcnow()
    with engine.begin() as conn:
        perfil = conn.execute(
            text(
                "SELECT id FROM plantao_perfis "
                "WHERE reset_token=:tok AND reset_token_expira IS NOT NULL AND reset_token_expira >= :agora"
            ),
            {"tok": token_hash, "agora": agora},
        ).mappings().first()
        if not perfil:
            return False
        perfil_id = int(perfil["id"])
        conn.execute(
            text(
                "UPDATE plantao_perfis SET senha_hash=:h, reset_token=NULL, reset_token_expira=NULL, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"h": hash_password(nova_senha), "agora": agora, "id": perfil_id},
        )

    revogar_todas_sessoes(engine, perfil_id)
    audit(
        engine,
        "perfil.senha_redefinida",
        perfil_id=perfil_id,
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )
    notificar(
        engine,
        perfil_id,
        "senha_redefinida",
        "Senha redefinida",
        "Sua senha foi redefinida com sucesso.",
        entidade="plantao_perfis",
        entidade_id=perfil_id,
    )
    return True


def criar_local(
    engine: Any,
    nome: str,
    endereco: str,
    cidade: str,
    uf: str,
    telefone: str,
    gestor_id: int,
) -> int:
    if not nome.strip():
        raise ValueError("Nome do local e obrigatorio.")
    agora = _utcnow()
    with engine.begin() as conn:
        local_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_locais (nome, endereco, cidade, uf, telefone, ativo, criado_em, alterado_em)
            VALUES (:nome, :endereco, :cidade, :uf, :telefone, 1, :agora, :agora)
            """,
            {
                "nome": nome.strip(),
                "endereco": endereco.strip(),
                "cidade": cidade.strip(),
                "uf": uf.strip().upper(),
                "telefone": telefone.strip(),
                "agora": agora,
            },
            "SELECT id FROM plantao_locais WHERE nome = :nome ORDER BY id DESC LIMIT 1",
            {"nome": nome.strip()},
        )

    audit(
        engine,
        "local.criado",
        gestor_id=gestor_id,
        entidade="plantao_locais",
        entidade_id=local_id,
    )
    return local_id


def atualizar_local(engine: Any, local_id: int, dados: dict, gestor_id: int) -> None:
    allowed = ("nome", "endereco", "cidade", "uf", "telefone", "ativo")
    campos = {}
    for k in allowed:
        if k in dados:
            v = dados[k]
            campos[k] = v.strip() if isinstance(v, str) else v
    if not campos:
        return

    campos["alterado_em"] = _utcnow()
    params = {**campos, "id": local_id}
    sets = ", ".join(f"{k} = :{k}" for k in campos.keys())
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM plantao_locais WHERE id = :id"),
            {"id": local_id},
        ).mappings().first()
        if not row:
            raise ValueError("Local nao encontrado.")
        conn.execute(text(f"UPDATE plantao_locais SET {sets} WHERE id = :id"), params)

    audit(
        engine,
        "local.atualizado",
        gestor_id=gestor_id,
        entidade="plantao_locais",
        entidade_id=local_id,
        detalhes=json.dumps(campos, ensure_ascii=False),
    )


def desativar_local(engine: Any, local_id: int, gestor_id: int) -> None:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM plantao_locais WHERE id = :id"),
            {"id": local_id},
        ).mappings().first()
        if not row:
            raise ValueError("Local nao encontrado.")
        conn.execute(
            text("UPDATE plantao_locais SET ativo = 0, alterado_em = :agora WHERE id = :id"),
            {"agora": _utcnow(), "id": local_id},
        )

    audit(
        engine,
        "local.desativado",
        gestor_id=gestor_id,
        entidade="plantao_locais",
        entidade_id=local_id,
    )


def criar_tarifa(
    engine: Any,
    tipo_perfil: str,
    valor_hora: float,
    gestor_id: int,
    dia_semana: int | None = None,
    subtipo_turno: str | None = None,
    vigente_de: str = "2000-01-01",
    vigente_ate: str | None = None,
) -> int:
    if tipo_perfil not in ("veterinario", "auxiliar"):
        raise ValueError("Tipo de perfil invalido.")
    if valor_hora <= 0:
        raise ValueError("Valor/hora deve ser maior que zero.")
    if dia_semana is not None and dia_semana not in range(0, 8):
        raise ValueError("Dia da semana invalido. Use 0..7.")
    if subtipo_turno is not None and subtipo_turno not in ("regular", "substituicao", "feriado"):
        raise ValueError("Subtipo de turno invalido.")

    with engine.begin() as conn:
        tarifa_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_tarifas
                (tipo_perfil, dia_semana, subtipo_turno, valor_hora, vigente_de, vigente_ate, criado_em, criado_por)
            VALUES
                (:tipo_perfil, :dia_semana, :subtipo_turno, :valor_hora, :vigente_de, :vigente_ate, :agora, :criado_por)
            """,
            {
                "tipo_perfil": tipo_perfil,
                "dia_semana": dia_semana,
                "subtipo_turno": subtipo_turno,
                "valor_hora": float(valor_hora),
                "vigente_de": vigente_de,
                "vigente_ate": vigente_ate,
                "agora": _utcnow(),
                "criado_por": gestor_id,
            },
            "SELECT id FROM plantao_tarifas ORDER BY id DESC LIMIT 1",
            {},
        )

    audit(
        engine,
        "tarifa.criada",
        gestor_id=gestor_id,
        entidade="plantao_tarifas",
        entidade_id=tarifa_id,
    )
    return tarifa_id


def criar_feriado(
    engine: Any,
    data: str,
    nome: str,
    tipo: str,
    local_id: int | None,
    gestor_id: int,
) -> int:
    if tipo not in ("nacional", "estadual", "municipal"):
        raise ValueError("Tipo de feriado invalido.")
    if not nome.strip():
        raise ValueError("Nome do feriado e obrigatorio.")

    with engine.begin() as conn:
        feriado_id = _insert_and_get_id(
            conn,
            "INSERT INTO plantao_feriados (data, nome, tipo, local_id) VALUES (:data, :nome, :tipo, :local_id)",
            {
                "data": data,
                "nome": nome.strip(),
                "tipo": tipo,
                "local_id": local_id,
            },
            "SELECT id FROM plantao_feriados WHERE data=:data AND nome=:nome ORDER BY id DESC LIMIT 1",
            {"data": data, "nome": nome.strip()},
        )

    audit(
        engine,
        "feriado.criado",
        gestor_id=gestor_id,
        entidade="plantao_feriados",
        entidade_id=feriado_id,
    )
    return feriado_id


def criar_data_plantao(
    engine: Any,
    local_id: int,
    tipo: str,
    subtipo: str,
    data: str,
    hora_inicio: str,
    hora_fim: str,
    posicoes: list[dict],
    gestor_id: int,
    observacoes: str = "",
    ip: str = "",
) -> int:
    if tipo not in ("presencial", "sobreaviso"):
        raise ValueError("Tipo de plantao invalido.")
    if subtipo not in ("regular", "substituicao", "feriado", "sobreaviso_emergencia"):
        raise ValueError("Subtipo de plantao invalido.")
    if tipo == "presencial" and not posicoes:
        raise ValueError("Plantoes presenciais exigem ao menos uma posicao.")

    agora = _utcnow()
    with engine.begin() as conn:
        local = conn.execute(
            text("SELECT id FROM plantao_locais WHERE id = :id AND ativo = 1"),
            {"id": local_id},
        ).mappings().first()
        if not local:
            raise ValueError("Local invalido ou inativo.")

        data_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_datas
                (local_id, tipo, subtipo, data, hora_inicio, hora_fim, observacoes, status, criado_em, alterado_em, criado_por)
            VALUES
                (:local_id, :tipo, :subtipo, :data, :hora_inicio, :hora_fim, :observacoes, 'rascunho', :agora, :agora, :gestor_id)
            """,
            {
                "local_id": local_id,
                "tipo": tipo,
                "subtipo": subtipo,
                "data": data,
                "hora_inicio": hora_inicio,
                "hora_fim": hora_fim,
                "observacoes": observacoes.strip(),
                "agora": agora,
                "gestor_id": gestor_id,
            },
            "SELECT id FROM plantao_datas WHERE local_id=:local_id AND data=:data AND hora_inicio=:hora_inicio ORDER BY id DESC LIMIT 1",
            {"local_id": local_id, "data": data, "hora_inicio": hora_inicio},
        )

        for pos in posicoes:
            tipo_pos = (pos.get("tipo") or "").strip()
            vagas = int(pos.get("vagas") or 0)
            if tipo_pos not in ("veterinario", "auxiliar"):
                raise ValueError("Tipo de posicao invalido.")
            if vagas <= 0:
                raise ValueError("Quantidade de vagas deve ser maior que zero.")
            conn.execute(
                text(
                    "INSERT INTO plantao_posicoes (data_id, tipo, vagas) VALUES (:data_id, :tipo, :vagas)"
                ),
                {"data_id": data_id, "tipo": tipo_pos, "vagas": vagas},
            )

    audit(
        engine,
        "data.criada",
        gestor_id=gestor_id,
        entidade="plantao_datas",
        entidade_id=data_id,
        ip=ip,
    )
    return data_id


def publicar_data_plantao(
    engine: Any,
    data_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    data_row = get_data_plantao(engine, data_id)
    if not data_row:
        raise ValueError("Data de plantao nao encontrada.")
    if data_row["status"] != "rascunho":
        raise ValueError("Somente datas em rascunho podem ser publicadas.")

    agora = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_datas "
                "SET status='publicado', publicado_em=:agora, publicado_por=:gestor_id, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"agora": agora, "gestor_id": gestor_id, "id": data_id},
        )

    audit(
        engine,
        "data.publicada",
        gestor_id=gestor_id,
        entidade="plantao_datas",
        entidade_id=data_id,
        ip=ip,
    )


def cancelar_data_plantao(
    engine: Any,
    data_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    data_row = get_data_plantao(engine, data_id)
    if not data_row:
        raise ValueError("Data de plantao nao encontrada.")
    if data_row["status"] == "cancelado":
        return

    confirmados = [c for c in listar_candidaturas_por_data(engine, data_id) if c["status"] == "confirmado"]

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE plantao_datas SET status='cancelado', alterado_em=:agora WHERE id=:id"),
            {"agora": _utcnow(), "id": data_id},
        )
        conn.execute(
            text(
                "UPDATE plantao_candidaturas "
                "SET status='cancelado', alterado_em=:agora "
                "WHERE posicao_id IN (SELECT id FROM plantao_posicoes WHERE data_id=:data_id) "
                "AND status IN ('provisorio', 'confirmado', 'lista_espera')"
            ),
            {"agora": _utcnow(), "data_id": data_id},
        )

    audit(
        engine,
        "data.cancelada",
        gestor_id=gestor_id,
        entidade="plantao_datas",
        entidade_id=data_id,
        ip=ip,
    )
    for c in confirmados:
        notificar(
            engine,
            int(c["perfil_id"]),
            "data_cancelada",
            "Plantao cancelado",
            f"O plantao de {c['data']} ({c['hora_inicio']} - {c['hora_fim']}) foi cancelado.",
            entidade="plantao_datas",
            entidade_id=data_id,
        )


def gerar_escala_mensal(
    engine: Any,
    local_id: int,
    ano: int,
    mes: int,
    gestor_id: int,
    hora_inicio: str = "08:00",
    hora_fim: str = "20:00",
    hora_inicio_sobreaviso: str = "20:00",
    hora_fim_sobreaviso: str = "08:00",
) -> list[int]:
    primeiro = date(ano, mes, 1)
    prox = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    ultimo = prox - timedelta(days=1)
    feriados = get_set_feriados(engine, primeiro.isoformat(), ultimo.isoformat(), local_id)

    alvos: list[date] = []
    cursor = primeiro
    while cursor <= ultimo:
        if cursor.weekday() >= 5 or cursor in feriados:
            alvos.append(cursor)
        cursor += timedelta(days=1)

    criados: list[int] = []
    with engine.begin() as conn:
        for d in alvos:
            data_str = d.isoformat()
            existe_presencial = conn.execute(
                text(
                    "SELECT id FROM plantao_datas "
                    "WHERE local_id=:local_id AND data=:data AND tipo='presencial' AND status IN ('rascunho','publicado')"
                ),
                {"local_id": local_id, "data": data_str},
            ).mappings().first()
            if not existe_presencial:
                subtipo = inferir_subtipo(d, feriados)
                data_id = _insert_and_get_id(
                    conn,
                    """
                    INSERT INTO plantao_datas
                        (local_id, tipo, subtipo, data, hora_inicio, hora_fim, observacoes, status, criado_em, alterado_em, criado_por)
                    VALUES
                        (:local_id, 'presencial', :subtipo, :data, :hora_inicio, :hora_fim, '', 'rascunho', :agora, :agora, :gestor_id)
                    """,
                    {
                        "local_id": local_id,
                        "subtipo": subtipo,
                        "data": data_str,
                        "hora_inicio": hora_inicio,
                        "hora_fim": hora_fim,
                        "agora": _utcnow(),
                        "gestor_id": gestor_id,
                    },
                    "SELECT id FROM plantao_datas WHERE local_id=:local_id AND data=:data AND tipo='presencial' ORDER BY id DESC LIMIT 1",
                    {"local_id": local_id, "data": data_str},
                )
                conn.execute(
                    text("INSERT INTO plantao_posicoes (data_id, tipo, vagas) VALUES (:id, 'veterinario', 1)"),
                    {"id": data_id},
                )
                conn.execute(
                    text("INSERT INTO plantao_posicoes (data_id, tipo, vagas) VALUES (:id, 'auxiliar', 1)"),
                    {"id": data_id},
                )
                criados.append(data_id)

            existe_sobreaviso = conn.execute(
                text(
                    "SELECT id FROM plantao_datas "
                    "WHERE local_id=:local_id AND data=:data AND tipo='sobreaviso' AND status IN ('rascunho','publicado')"
                ),
                {"local_id": local_id, "data": data_str},
            ).mappings().first()
            if not existe_sobreaviso:
                data_id_s = _insert_and_get_id(
                    conn,
                    """
                    INSERT INTO plantao_datas
                        (local_id, tipo, subtipo, data, hora_inicio, hora_fim, observacoes, status, criado_em, alterado_em, criado_por)
                    VALUES
                        (:local_id, 'sobreaviso', 'sobreaviso_emergencia', :data, :hora_inicio, :hora_fim, '', 'rascunho', :agora, :agora, :gestor_id)
                    """,
                    {
                        "local_id": local_id,
                        "data": data_str,
                        "hora_inicio": hora_inicio_sobreaviso,
                        "hora_fim": hora_fim_sobreaviso,
                        "agora": _utcnow(),
                        "gestor_id": gestor_id,
                    },
                    "SELECT id FROM plantao_datas WHERE local_id=:local_id AND data=:data AND tipo='sobreaviso' ORDER BY id DESC LIMIT 1",
                    {"local_id": local_id, "data": data_str},
                )
                criados.append(data_id_s)

    audit(
        engine,
        "escala.gerada_automaticamente",
        gestor_id=gestor_id,
        entidade="plantao_datas",
        detalhes=json.dumps({"ano": ano, "mes": mes, "criados": criados}, ensure_ascii=False),
    )
    return criados


def candidatar(
    engine: Any,
    posicao_id: int,
    perfil_id: int,
    ip: str = "",
) -> int:
    posicao = get_posicao(engine, posicao_id)
    if not posicao:
        raise ValueError("Posicao nao encontrada.")
    if posicao["data_status"] != "publicado":
        raise ValueError("A data do plantao ainda nao esta publicada.")

    inicio_turno = _to_dt(posicao["data"], posicao["hora_inicio"])
    if inicio_turno <= datetime.utcnow():
        raise ValueError("Nao e possivel se candidatar para turno ja iniciado.")

    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil or perfil["status"] != "ativo":
        raise ValueError("Perfil invalido ou inativo.")
    if perfil["tipo"] != posicao["tipo"]:
        raise ValueError("Tipo de perfil nao compativel com a vaga.")

    if candidatura_existe(engine, perfil_id, posicao["data_id"]):
        raise ValueError("Voce ja possui candidatura ativa para esta data.")

    confirmados = contar_confirmados_por_posicao(engine, posicao_id)
    status = "provisorio"
    ordem_espera = None
    if confirmados >= int(posicao["vagas"]):
        status = "lista_espera"
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(MAX(ordem_espera), 0) AS max_ordem "
                    "FROM plantao_candidaturas WHERE posicao_id=:pid AND status='lista_espera'"
                ),
                {"pid": posicao_id},
            ).mappings().first()
            ordem_espera = int(row["max_ordem"]) + 1 if row else 1

    agora = _utcnow()
    with engine.begin() as conn:
        candidatura_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_candidaturas
                (posicao_id, perfil_id, status, ordem_espera, criado_em, alterado_em)
            VALUES
                (:posicao_id, :perfil_id, :status, :ordem_espera, :agora, :agora)
            """,
            {
                "posicao_id": posicao_id,
                "perfil_id": perfil_id,
                "status": status,
                "ordem_espera": ordem_espera,
                "agora": agora,
            },
            "SELECT id FROM plantao_candidaturas WHERE posicao_id=:pid AND perfil_id=:perfil_id ORDER BY id DESC LIMIT 1",
            {"pid": posicao_id, "perfil_id": perfil_id},
        )

    audit(
        engine,
        "candidatura.criada",
        perfil_id=perfil_id,
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
        ip=ip,
    )
    if status == "lista_espera":
        notificar(
            engine,
            perfil_id,
            "candidatura_lista_espera",
            "Voce entrou na lista de espera",
            "No momento as vagas confirmadas estao completas para este turno.",
            entidade="plantao_candidaturas",
            entidade_id=candidatura_id,
        )
    return candidatura_id


def confirmar_candidatura(
    engine: Any,
    candidatura_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    cand = get_candidatura(engine, candidatura_id)
    if not cand:
        raise ValueError("Candidatura nao encontrada.")
    if cand["status"] != "provisorio":
        raise ValueError("Apenas candidaturas provisorias podem ser confirmadas.")
    if contar_confirmados_por_posicao(engine, cand["posicao_id"]) >= int(cand["posicao_vagas"]):
        raise ValueError("Nao ha vagas disponiveis para confirmar esta candidatura.")

    valor_hora, valor_base, horas = _calcular_snapshot_remuneracao(
        engine,
        cand["perfil_tipo"],
        {
            "data": cand["data"],
            "hora_inicio": cand["hora_inicio"],
            "hora_fim": cand["hora_fim"],
            "subtipo": cand["data_subtipo"],
            "local_id": cand["local_id"],
        },
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE plantao_candidaturas
                   SET status='confirmado',
                       confirmado_em=:agora,
                       confirmado_por=:gestor_id,
                       valor_hora_snapshot=:valor_hora,
                       valor_base_calculado=:valor_base,
                       horas_turno=:horas,
                       alterado_em=:agora
                 WHERE id=:id
                """
            ),
            {
                "agora": _utcnow(),
                "gestor_id": gestor_id,
                "valor_hora": valor_hora,
                "valor_base": valor_base,
                "horas": horas,
                "id": candidatura_id,
            },
        )

    audit(
        engine,
        "candidatura.confirmada",
        gestor_id=gestor_id,
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
        ip=ip,
    )
    notificar(
        engine,
        int(cand["perfil_id"]),
        "candidatura_confirmada",
        "Candidatura confirmada",
        f"Sua candidatura para {cand['data']} foi confirmada.",
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
    )


def recusar_candidatura(
    engine: Any,
    candidatura_id: int,
    gestor_id: int,
    motivo: str = "",
    ip: str = "",
) -> None:
    cand = get_candidatura(engine, candidatura_id)
    if not cand:
        raise ValueError("Candidatura nao encontrada.")
    if cand["status"] not in ("provisorio", "lista_espera"):
        raise ValueError("Somente candidaturas provisorias/lista de espera podem ser recusadas.")

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_candidaturas "
                "SET status='recusado', motivo_recusa=:motivo, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"motivo": motivo.strip(), "agora": _utcnow(), "id": candidatura_id},
        )

    audit(
        engine,
        "candidatura.recusada",
        gestor_id=gestor_id,
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
        detalhes=motivo.strip(),
        ip=ip,
    )
    notificar(
        engine,
        int(cand["perfil_id"]),
        "candidatura_recusada",
        "Candidatura recusada",
        motivo.strip() or "Sua candidatura foi recusada pela gestao.",
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
    )


def cancelar_candidatura(
    engine: Any,
    candidatura_id: int,
    perfil_id: int,
    prazo_horas_uteis: int,
    ip: str = "",
) -> None:
    cand = get_candidatura(engine, candidatura_id)
    if not cand:
        raise ValueError("Candidatura nao encontrada.")
    if int(cand["perfil_id"]) != int(perfil_id):
        raise ValueError("Voce nao pode cancelar candidatura de outro plantonista.")

    inicio_turno = _to_dt(cand["data"], cand["hora_inicio"])
    feriados = get_set_feriados(
        engine,
        cand["data"],
        cand["data"],
        cand.get("local_id"),
    )
    pode, motivo = pode_cancelar(
        status=cand["status"],
        inicio_turno=inicio_turno,
        agora=datetime.utcnow(),
        prazo_horas_uteis=prazo_horas_uteis,
        feriados=feriados,
    )
    if not pode:
        raise ValueError(motivo)

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE plantao_candidaturas "
                "SET status='cancelado', cancelado_dentro_prazo=1, ordem_espera=NULL, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"agora": _utcnow(), "id": candidatura_id},
        )

    if cand["status"] in ("confirmado", "provisorio"):
        _promover_lista_espera(engine, int(cand["posicao_id"]))

    audit(
        engine,
        "candidatura.cancelada",
        perfil_id=perfil_id,
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
        ip=ip,
    )


def _promover_lista_espera(engine: Any, posicao_id: int) -> None:
    promovida_id: int | None = None
    promovida_perfil: int | None = None
    with engine.begin() as conn:
        prox = conn.execute(
            text(
                """
                SELECT id, perfil_id
                  FROM plantao_candidaturas
                 WHERE posicao_id=:pid AND status='lista_espera'
                 ORDER BY ordem_espera ASC, id ASC
                 LIMIT 1
                """
            ),
            {"pid": posicao_id},
        ).mappings().first()
        if not prox:
            return
        promovida_id = int(prox["id"])
        promovida_perfil = int(prox["perfil_id"])
        conn.execute(
            text(
                "UPDATE plantao_candidaturas "
                "SET status='provisorio', ordem_espera=NULL, alterado_em=:agora "
                "WHERE id=:id"
            ),
            {"agora": _utcnow(), "id": promovida_id},
        )

        restantes = conn.execute(
            text(
                """
                SELECT id
                  FROM plantao_candidaturas
                 WHERE posicao_id=:pid AND status='lista_espera'
                 ORDER BY ordem_espera ASC, id ASC
                """
            ),
            {"pid": posicao_id},
        ).mappings().all()
        for ordem, r in enumerate(restantes, start=1):
            conn.execute(
                text("UPDATE plantao_candidaturas SET ordem_espera=:ordem WHERE id=:id"),
                {"ordem": ordem, "id": int(r["id"])},
            )

    if promovida_id and promovida_perfil:
        notificar(
            engine,
            promovida_perfil,
            "lista_espera_promovida",
            "Voce saiu da lista de espera",
            "Uma vaga foi liberada e sua candidatura voltou para status provisorio.",
            entidade="plantao_candidaturas",
            entidade_id=promovida_id,
        )


def solicitar_troca_direta(
    engine: Any,
    candidatura_a_id: int,
    candidatura_b_id: int,
    perfil_id: int,
    mensagem: str = "",
    ip: str = "",
) -> int:
    cand_a = get_candidatura(engine, candidatura_a_id)
    cand_b = get_candidatura(engine, candidatura_b_id)
    if not cand_a or not cand_b:
        raise ValueError("Candidatura invalida para troca.")
    if int(cand_a["perfil_id"]) != int(perfil_id):
        raise ValueError("Voce so pode solicitar troca da sua propria candidatura.")
    if int(cand_b["perfil_id"]) == int(perfil_id):
        raise ValueError("A candidatura alvo deve ser de outro plantonista.")
    if cand_a["status"] != "confirmado" or cand_b["status"] != "confirmado":
        raise ValueError("Troca direta exige duas candidaturas confirmadas.")

    agora = datetime.utcnow()
    with engine.begin() as conn:
        prazo_horas = _prazo_cancelamento_horas_uteis(conn)
    for cand in (cand_a, cand_b):
        inicio = _to_dt(cand["data"], cand["hora_inicio"])
        feriados = get_set_feriados(engine, cand["data"], cand["data"], cand.get("local_id"))
        ok, motivo = pode_cancelar(cand["status"], inicio, agora, prazo_horas, feriados)
        if not ok:
            raise ValueError(f"Troca fora da janela permitida: {motivo}")

    expira = (datetime.utcnow() + timedelta(hours=48)).isoformat(timespec="seconds")
    with engine.begin() as conn:
        troca_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_trocas
                (tipo, candidatura_a_id, candidatura_b_id, status, mensagem, criado_em, expira_em)
            VALUES
                ('troca_direta', :a, :b, 'solicitado', :mensagem, :agora, :expira)
            """,
            {"a": candidatura_a_id, "b": candidatura_b_id, "mensagem": mensagem.strip(), "agora": _utcnow(), "expira": expira},
            "SELECT id FROM plantao_trocas WHERE candidatura_a_id=:a AND candidatura_b_id=:b ORDER BY id DESC LIMIT 1",
            {"a": candidatura_a_id, "b": candidatura_b_id},
        )

    audit(
        engine,
        "troca.solicitada",
        perfil_id=perfil_id,
        entidade="plantao_trocas",
        entidade_id=troca_id,
        ip=ip,
    )
    notificar(
        engine,
        int(cand_b["perfil_id"]),
        "troca_solicitada",
        "Nova solicitacao de troca",
        "Um colega solicitou troca direta de plantao.",
        entidade="plantao_trocas",
        entidade_id=troca_id,
    )
    return troca_id


def abrir_substituicao(
    engine: Any,
    candidatura_a_id: int,
    perfil_id: int,
    mensagem: str = "",
    ip: str = "",
) -> int:
    cand_a = get_candidatura(engine, candidatura_a_id)
    if not cand_a:
        raise ValueError("Candidatura nao encontrada.")
    if int(cand_a["perfil_id"]) != int(perfil_id):
        raise ValueError("Voce so pode abrir substituicao para seu proprio turno.")
    if cand_a["status"] != "confirmado":
        raise ValueError("Substituicao so pode ser aberta para candidatura confirmada.")

    expira = (datetime.utcnow() + timedelta(hours=72)).isoformat(timespec="seconds")
    with engine.begin() as conn:
        troca_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_trocas
                (tipo, candidatura_a_id, candidatura_b_id, status, mensagem, criado_em, expira_em)
            VALUES
                ('substituicao', :a, NULL, 'solicitado', :mensagem, :agora, :expira)
            """,
            {"a": candidatura_a_id, "mensagem": mensagem.strip(), "agora": _utcnow(), "expira": expira},
            "SELECT id FROM plantao_trocas WHERE candidatura_a_id=:a AND tipo='substituicao' ORDER BY id DESC LIMIT 1",
            {"a": candidatura_a_id},
        )

        perfis = conn.execute(
            text(
                "SELECT id FROM plantao_perfis "
                "WHERE status='ativo' AND tipo=:tipo AND id<>:perfil_id"
            ),
            {"tipo": cand_a["perfil_tipo"], "perfil_id": perfil_id},
        ).mappings().all()

    audit(
        engine,
        "substituicao.aberta",
        perfil_id=perfil_id,
        entidade="plantao_trocas",
        entidade_id=troca_id,
        ip=ip,
    )
    for p in perfis:
        notificar(
            engine,
            int(p["id"]),
            "substituicao_aberta",
            "Turno disponivel para substituicao",
            "Ha um turno confirmado disponivel para substituicao aberta.",
            entidade="plantao_trocas",
            entidade_id=troca_id,
        )
    return troca_id


def aceitar_troca(
    engine: Any,
    troca_id: int,
    perfil_id: int,
    ip: str = "",
) -> None:
    troca = get_troca(engine, troca_id)
    if not troca:
        raise ValueError("Troca nao encontrada.")
    if troca["status"] != "solicitado":
        raise ValueError("A troca nao esta mais disponivel.")
    if troca["expira_em"] < _utcnow():
        raise ValueError("A troca expirou.")

    cand_a = get_candidatura(engine, int(troca["candidatura_a_id"]))
    cand_b = get_candidatura(engine, int(troca["candidatura_b_id"])) if troca.get("candidatura_b_id") else None
    if not cand_a:
        raise ValueError("Candidatura principal da troca nao encontrada.")

    now = _utcnow()
    with engine.begin() as conn:
        prazo_horas = _prazo_cancelamento_horas_uteis(conn)

        if troca["tipo"] == "troca_direta":
            if not cand_b:
                raise ValueError("Troca direta invalida.")
            if int(cand_b["perfil_id"]) != int(perfil_id):
                raise ValueError("Apenas o destinatario pode aceitar esta troca.")
            perfil_a = get_perfil_por_id(engine, int(cand_a["perfil_id"]))
            perfil_b = get_perfil_por_id(engine, int(cand_b["perfil_id"]))
            if not perfil_a or not perfil_b:
                raise ValueError("Perfis da troca nao encontrados.")
            if perfil_b["tipo"] != cand_a["posicao_tipo"] or perfil_a["tipo"] != cand_b["posicao_tipo"]:
                raise ValueError("Tipos de perfil nao compativeis com as vagas da troca.")

            for cand in (cand_a, cand_b):
                inicio = _to_dt(cand["data"], cand["hora_inicio"])
                feriados = get_set_feriados(engine, cand["data"], cand["data"], cand.get("local_id"))
                ok, motivo = pode_cancelar(cand["status"], inicio, datetime.utcnow(), prazo_horas, feriados)
                if not ok:
                    raise ValueError(f"Troca fora da janela permitida: {motivo}")

            vha, vba, ha = _calcular_snapshot_remuneracao(
                engine,
                perfil_b["tipo"],
                {
                    "data": cand_a["data"],
                    "hora_inicio": cand_a["hora_inicio"],
                    "hora_fim": cand_a["hora_fim"],
                    "subtipo": cand_a["data_subtipo"],
                    "local_id": cand_a["local_id"],
                },
            )
            vhb, vbb, hb = _calcular_snapshot_remuneracao(
                engine,
                perfil_a["tipo"],
                {
                    "data": cand_b["data"],
                    "hora_inicio": cand_b["hora_inicio"],
                    "hora_fim": cand_b["hora_fim"],
                    "subtipo": cand_b["data_subtipo"],
                    "local_id": cand_b["local_id"],
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE plantao_candidaturas
                       SET perfil_id=:novo_perfil,
                           valor_hora_snapshot=:vh,
                           valor_base_calculado=:vb,
                           horas_turno=:h,
                           alterado_em=:agora
                     WHERE id=:id
                    """
                ),
                {"novo_perfil": cand_b["perfil_id"], "vh": vha, "vb": vba, "h": ha, "agora": now, "id": cand_a["id"]},
            )
            conn.execute(
                text(
                    """
                    UPDATE plantao_candidaturas
                       SET perfil_id=:novo_perfil,
                           valor_hora_snapshot=:vh,
                           valor_base_calculado=:vb,
                           horas_turno=:h,
                           alterado_em=:agora
                     WHERE id=:id
                    """
                ),
                {"novo_perfil": cand_a["perfil_id"], "vh": vhb, "vb": vbb, "h": hb, "agora": now, "id": cand_b["id"]},
            )
        else:
            perfil_novo = get_perfil_por_id(engine, perfil_id)
            if not perfil_novo or perfil_novo["status"] != "ativo":
                raise ValueError("Perfil do substituto invalido.")
            if int(cand_a["perfil_id"]) == int(perfil_id):
                raise ValueError("Voce nao pode aceitar sua propria substituicao.")
            if perfil_novo["tipo"] != cand_a["posicao_tipo"]:
                raise ValueError("Tipo de perfil nao compativel com a vaga.")
            if candidatura_existe(engine, perfil_id, cand_a["data_id"]):
                raise ValueError("Voce ja possui candidatura ativa para esta data.")

            inicio = _to_dt(cand_a["data"], cand_a["hora_inicio"])
            feriados = get_set_feriados(engine, cand_a["data"], cand_a["data"], cand_a.get("local_id"))
            ok, motivo = pode_cancelar(cand_a["status"], inicio, datetime.utcnow(), prazo_horas, feriados)
            if not ok:
                raise ValueError(f"Substituicao fora da janela permitida: {motivo}")

            vh, vb, h = _calcular_snapshot_remuneracao(
                engine,
                perfil_novo["tipo"],
                {
                    "data": cand_a["data"],
                    "hora_inicio": cand_a["hora_inicio"],
                    "hora_fim": cand_a["hora_fim"],
                    "subtipo": cand_a["data_subtipo"],
                    "local_id": cand_a["local_id"],
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE plantao_candidaturas
                       SET perfil_id=:novo_perfil,
                           valor_hora_snapshot=:vh,
                           valor_base_calculado=:vb,
                           horas_turno=:h,
                           alterado_em=:agora
                     WHERE id=:id
                    """
                ),
                {"novo_perfil": perfil_id, "vh": vh, "vb": vb, "h": h, "agora": now, "id": cand_a["id"]},
            )

        conn.execute(
            text("UPDATE plantao_trocas SET status='aceito', respondido_em=:agora WHERE id=:id"),
            {"agora": now, "id": troca_id},
        )

    audit(
        engine,
        "troca.executada",
        perfil_id=perfil_id,
        entidade="plantao_trocas",
        entidade_id=troca_id,
        ip=ip,
    )
    notificar(
        engine,
        int(cand_a["perfil_id"]),
        "troca_aceita",
        "Troca executada",
        "A troca/substituicao foi concluida com sucesso.",
        entidade="plantao_trocas",
        entidade_id=troca_id,
    )
    if cand_b:
        notificar(
            engine,
            int(cand_b["perfil_id"]),
            "troca_aceita",
            "Troca executada",
            "A troca/substituicao foi concluida com sucesso.",
            entidade="plantao_trocas",
            entidade_id=troca_id,
        )


def recusar_troca(
    engine: Any,
    troca_id: int,
    perfil_id: int,
    ip: str = "",
) -> None:
    troca = get_troca(engine, troca_id)
    if not troca:
        raise ValueError("Troca nao encontrada.")
    if troca["status"] != "solicitado":
        raise ValueError("Troca nao pode mais ser recusada.")

    cand_a = get_candidatura(engine, int(troca["candidatura_a_id"]))
    cand_b = get_candidatura(engine, int(troca["candidatura_b_id"])) if troca.get("candidatura_b_id") else None
    if not cand_a:
        raise ValueError("Troca invalida.")

    if troca["tipo"] == "troca_direta":
        if not cand_b or int(cand_b["perfil_id"]) != int(perfil_id):
            raise ValueError("Apenas o destinatario pode recusar a troca.")
    else:
        if int(cand_a["perfil_id"]) == int(perfil_id):
            raise ValueError("Use cancelamento da candidatura para desistir da substituicao.")

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE plantao_trocas SET status='recusado', respondido_em=:agora WHERE id=:id"),
            {"agora": _utcnow(), "id": troca_id},
        )

    audit(
        engine,
        "troca.recusada",
        perfil_id=perfil_id,
        entidade="plantao_trocas",
        entidade_id=troca_id,
        ip=ip,
    )
    notificar(
        engine,
        int(cand_a["perfil_id"]),
        "troca_recusada",
        "Troca recusada",
        "Sua solicitacao de troca/substituicao foi recusada.",
        entidade="plantao_trocas",
        entidade_id=troca_id,
    )


def aderir_sobreaviso(
    engine: Any,
    data_id: int,
    perfil_id: int,
    ip: str = "",
) -> int:
    data_row = get_data_plantao(engine, data_id)
    if not data_row:
        raise ValueError("Data de sobreaviso nao encontrada.")
    if data_row["tipo"] != "sobreaviso" or data_row["status"] != "publicado":
        raise ValueError("A adesao e permitida apenas para sobreaviso publicado.")

    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil or perfil["status"] != "ativo" or perfil["tipo"] != "veterinario":
        raise ValueError("Somente veterinarios ativos podem aderir ao sobreaviso.")

    with engine.begin() as conn:
        existe = conn.execute(
            text(
                "SELECT id FROM plantao_sobreaviso "
                "WHERE data_id=:data_id AND perfil_id=:perfil_id AND status='ativo'"
            ),
            {"data_id": data_id, "perfil_id": perfil_id},
        ).mappings().first()
        if existe:
            raise ValueError("Voce ja aderiu ao sobreaviso desta data.")

        row = conn.execute(
            text(
                "SELECT COALESCE(MAX(prioridade), 0) AS max_prio "
                "FROM plantao_sobreaviso WHERE data_id=:data_id AND status='ativo'"
            ),
            {"data_id": data_id},
        ).mappings().first()
        prioridade = (int(row["max_prio"]) if row else 0) + 1
        adesao_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_sobreaviso (data_id, perfil_id, prioridade, status, criado_em)
            VALUES (:data_id, :perfil_id, :prioridade, 'ativo', :agora)
            """,
            {"data_id": data_id, "perfil_id": perfil_id, "prioridade": prioridade, "agora": _utcnow()},
            "SELECT id FROM plantao_sobreaviso WHERE data_id=:data_id AND perfil_id=:perfil_id AND status='ativo' ORDER BY id DESC LIMIT 1",
            {"data_id": data_id, "perfil_id": perfil_id},
        )

    audit(
        engine,
        "sobreaviso.adesao",
        perfil_id=perfil_id,
        entidade="plantao_sobreaviso",
        entidade_id=adesao_id,
        ip=ip,
    )
    return adesao_id


def cancelar_sobreaviso(
    engine: Any,
    adesao_id: int,
    perfil_id: int,
    ip: str = "",
) -> None:
    with engine.begin() as conn:
        adesao = conn.execute(
            text("SELECT * FROM plantao_sobreaviso WHERE id=:id"),
            {"id": adesao_id},
        ).mappings().first()
        if not adesao or adesao["status"] != "ativo":
            raise ValueError("Adesao nao encontrada ou ja cancelada.")
        if int(adesao["perfil_id"]) != int(perfil_id):
            raise ValueError("Voce nao pode cancelar adesao de outro plantonista.")

        data_id = int(adesao["data_id"])
        conn.execute(
            text(
                "UPDATE plantao_sobreaviso SET status='cancelado', cancelado_em=:agora WHERE id=:id"
            ),
            {"agora": _utcnow(), "id": adesao_id},
        )

        ativos = conn.execute(
            text(
                "SELECT id FROM plantao_sobreaviso "
                "WHERE data_id=:data_id AND status='ativo' "
                "ORDER BY prioridade ASC, id ASC"
            ),
            {"data_id": data_id},
        ).mappings().all()
        for ordem, row in enumerate(ativos, start=1):
            conn.execute(
                text("UPDATE plantao_sobreaviso SET prioridade=:ordem WHERE id=:id"),
                {"ordem": ordem, "id": int(row["id"])},
            )

    audit(
        engine,
        "sobreaviso.cancelado",
        perfil_id=perfil_id,
        entidade="plantao_sobreaviso",
        entidade_id=adesao_id,
        ip=ip,
    )


def reordenar_sobreaviso(
    engine: Any,
    data_id: int,
    nova_ordem: list[int],
    gestor_id: int,
    ip: str = "",
) -> None:
    if not nova_ordem:
        return
    with engine.begin() as conn:
        ativos = conn.execute(
            text(
                "SELECT id FROM plantao_sobreaviso "
                "WHERE data_id=:data_id AND status='ativo' ORDER BY prioridade ASC, id ASC"
            ),
            {"data_id": data_id},
        ).mappings().all()
        ativos_ids = [int(r["id"]) for r in ativos]
        if sorted(ativos_ids) != sorted([int(x) for x in nova_ordem]):
            raise ValueError("Nova ordem invalida para o sobreaviso.")

        for ordem, adesao_id in enumerate(nova_ordem, start=1):
            conn.execute(
                text("UPDATE plantao_sobreaviso SET prioridade=:ordem WHERE id=:id"),
                {"ordem": ordem, "id": int(adesao_id)},
            )

    audit(
        engine,
        "sobreaviso.reordenado",
        gestor_id=gestor_id,
        entidade="plantao_sobreaviso",
        entidade_id=data_id,
        detalhes=json.dumps({"nova_ordem": [int(x) for x in nova_ordem]}, ensure_ascii=False),
        ip=ip,
    )


def salvar_configuracao(
    engine: Any,
    chave: str,
    valor: str,
    gestor_id: int,
) -> None:
    validas = {
        "plantao_prazo_cancelamento_horas_uteis",
        "plantao_max_candidaturas_provisorias_por_vaga",
        "plantao_notif_sobreaviso_dias_antecedencia",
        "plantao_permitir_troca_sem_aprovacao_gestor",
        "plantao_api_key",
    }
    if chave not in validas:
        raise ValueError("Chave de configuracao invalida.")

    with engine.begin() as conn:
        _app_kv_set(conn, chave, valor.strip())

    audit(
        engine,
        "configuracao.salva",
        gestor_id=gestor_id,
        entidade="app_kv",
        entidade_id=None,
        detalhes=json.dumps({"chave": chave}, ensure_ascii=False),
    )


def get_configuracao(engine: Any, chave: str, default: str = "") -> str:
    with engine.connect() as conn:
        valor = _app_kv_get(conn, chave)
    return valor if valor is not None else default
