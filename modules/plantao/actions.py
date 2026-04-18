"""
Modulo Plantao - acoes de escrita (mutations).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from pb_platform.security import hash_password, verify_password
from pb_platform.storage import store

from .audit import audit
from .business import (
    calcular_horas_turno,
    calcular_valor_base,
    pode_cancelar,
)
from .notifications import notificar, notificar_gestores
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
    listar_disponibilidade_por_data,
    listar_tarifas_vigentes,
)


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _to_dt(data_ref: str, hora_ref: str) -> datetime:
    return datetime.fromisoformat(f"{data_ref}T{hora_ref}:00")


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
        horas=horas,
        tarifas=tarifas,
        tipo_data=data_turno.get("tipo", "presencial"),
    )
    return valor_hora, valor_base, horas


def aprovar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    """Aprova um cadastro pendente via store da plataforma."""
    # Verifica via users table (auth unificada)
    usuario = store.get_user_by_id(perfil_id)
    if not usuario:
        raise ValueError("Usuário nao encontrado.")
    if usuario.get("status") != "pendente":
        raise ValueError("Apenas cadastros pendentes podem ser aprovados.")

    store.approve_user(perfil_id, approved_by_id=gestor_id)

    audit(
        engine,
        "perfil.aprovado",
        gestor_id=gestor_id,
        entidade="users",
        entidade_id=perfil_id,
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "cadastro_aprovado",
        "Cadastro aprovado",
        "Seu cadastro foi aprovado. Voce ja pode fazer login.",
        entidade="users",
        entidade_id=perfil_id,
    )


def rejeitar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    motivo: str = "",
    ip: str = "",
) -> None:
    """Rejeita um cadastro pendente via store da plataforma."""
    # Verifica via users table (auth unificada)
    usuario = store.get_user_by_id(perfil_id)
    if not usuario:
        raise ValueError("Usuário nao encontrado.")
    if usuario.get("status") != "pendente":
        raise ValueError("Apenas cadastros pendentes podem ser rejeitados.")

    store.reject_user(perfil_id, motivo=motivo.strip())

    audit(
        engine,
        "perfil.rejeitado",
        gestor_id=gestor_id,
        entidade="users",
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
        entidade="users",
        entidade_id=perfil_id,
    )


def desativar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    """Desativa conta de plantonista via store da plataforma."""
    usuario = store.get_user_by_id(perfil_id)
    if not usuario:
        raise ValueError("Usuário nao encontrado.")
    if usuario.get("status") != "ativo":
        raise ValueError("Somente plantonista ativo pode ser desativado.")

    store.set_user_active(perfil_id, False)
    store.revoke_all_sessions(perfil_id)

    audit(
        engine,
        "perfil.desativado",
        gestor_id=gestor_id,
        entidade="users",
        entidade_id=perfil_id,
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "perfil_desativado",
        "Conta desativada",
        "Seu acesso foi desativado por um gestor.",
        entidade="users",
        entidade_id=perfil_id,
    )


def reativar_plantonista(
    engine: Any,
    perfil_id: int,
    gestor_id: int,
    ip: str = "",
) -> None:
    """Reativa conta de plantonista inativo ou rejeitado."""
    usuario = store.get_user_by_id(perfil_id)
    if not usuario:
        raise ValueError("Usuário não encontrado.")
    if usuario.get("status") == "ativo":
        raise ValueError("Plantonista já está ativo.")

    store.set_user_active(perfil_id, True)

    audit(
        engine,
        "perfil.reativado",
        gestor_id=gestor_id,
        entidade="users",
        entidade_id=perfil_id,
        ip=ip,
    )
    notificar(
        engine,
        perfil_id,
        "perfil_reativado",
        "Conta reativada",
        "Seu acesso foi reativado por um gestor.",
        entidade="users",
        entidade_id=perfil_id,
    )


def atualizar_perfil(
    engine: Any,
    perfil_id: int,
    dados: dict,
    ip: str = "",
) -> None:
    """Atualiza nome e telefone do plantonista na tabela users."""
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")

    campos = {}
    for k in ("nome", "telefone"):
        if k in dados:
            campos[k] = (dados[k] or "").strip()
    if not campos:
        return

    campos["updated_at"] = _utcnow()
    sets = ", ".join(f"{k} = :{k}" for k in campos.keys())
    params = {**campos, "id": perfil_id}

    with engine.begin() as conn:
        conn.execute(text(f"UPDATE users SET {sets} WHERE id = :id"), params)

    audit(
        engine,
        "perfil.atualizado",
        perfil_id=perfil_id,
        entidade="users",
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
    """Altera senha do plantonista via store da plataforma."""
    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil:
        raise ValueError("Plantonista nao encontrado.")
    if not verify_password(senha_atual, perfil["senha_hash"]):
        raise ValueError("Senha atual incorreta.")
    if len(senha_nova) < 8:
        raise ValueError("A senha nova deve ter no minimo 8 caracteres.")

    store.set_user_password(perfil_id, senha_nova)

    audit(
        engine,
        "perfil.senha_alterada",
        perfil_id=perfil_id,
        entidade="users",
        entidade_id=perfil_id,
        ip=ip,
    )




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
    feriado: int | None = None,
    vigente_de: str = "2000-01-01",
    vigente_ate: str | None = None,
) -> int:
    if tipo_perfil not in ("veterinario", "auxiliar"):
        raise ValueError("Tipo de perfil invalido.")
    if valor_hora <= 0:
        raise ValueError("Valor/hora deve ser maior que zero.")
    if dia_semana is not None and dia_semana not in range(0, 7):
        raise ValueError("Dia da semana invalido. Use 0..6.")
    if feriado is not None and feriado not in (0, 1):
        raise ValueError("Flag feriado invalido. Use 0 ou 1.")

    with engine.begin() as conn:
        tarifa_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_tarifas
                (tipo_perfil, dia_semana, feriado, valor_hora, vigente_de, vigente_ate, criado_em, criado_por)
            VALUES
                (:tipo_perfil, :dia_semana, :feriado, :valor_hora, :vigente_de, :vigente_ate, :agora, :criado_por)
            """,
            {
                "tipo_perfil": tipo_perfil,
                "dia_semana": dia_semana,
                "feriado": feriado,
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


def editar_tarifa(
    engine: Any,
    tarifa_id: int,
    gestor_id: int,
    tipo_perfil: str | None = None,
    dia_semana: int | None = ...,  # type: ignore[assignment]
    feriado: int | None = ...,  # type: ignore[assignment]
    valor_hora: float | None = None,
    vigente_de: str | None = None,
    vigente_ate: str | None = ...,  # type: ignore[assignment]
) -> None:
    campos: dict[str, Any] = {}
    if tipo_perfil is not None:
        if tipo_perfil not in ("veterinario", "auxiliar"):
            raise ValueError("Tipo de perfil invalido.")
        campos["tipo_perfil"] = tipo_perfil
    if dia_semana is not ...:
        if dia_semana is not None and dia_semana not in range(0, 7):
            raise ValueError("Dia da semana invalido. Use 0..6.")
        campos["dia_semana"] = dia_semana
    if feriado is not ...:
        if feriado is not None and feriado not in (0, 1):
            raise ValueError("Flag feriado invalido. Use 0 ou 1.")
        campos["feriado"] = feriado
    if valor_hora is not None:
        if valor_hora <= 0:
            raise ValueError("Valor/hora deve ser maior que zero.")
        campos["valor_hora"] = float(valor_hora)
    if vigente_de is not None:
        campos["vigente_de"] = vigente_de
    if vigente_ate is not ...:
        campos["vigente_ate"] = vigente_ate

    if not campos:
        return

    sets = ", ".join(f"{k} = :{k}" for k in campos)
    params = {**campos, "id": tarifa_id}
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM plantao_tarifas WHERE id = :id"),
            {"id": tarifa_id},
        ).mappings().first()
        if not row:
            raise ValueError("Tarifa nao encontrada.")
        conn.execute(text(f"UPDATE plantao_tarifas SET {sets} WHERE id = :id"), params)

    audit(
        engine,
        "tarifa.editada",
        gestor_id=gestor_id,
        entidade="plantao_tarifas",
        entidade_id=tarifa_id,
        detalhes=json.dumps(campos, ensure_ascii=False),
    )


def excluir_tarifa(engine: Any, tarifa_id: int, gestor_id: int, ip: str = "") -> None:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM plantao_tarifas WHERE id = :id"),
            {"id": tarifa_id},
        ).mappings().first()
        if not row:
            raise ValueError("Tarifa nao encontrada.")
        conn.execute(text("DELETE FROM plantao_tarifas WHERE id = :id"), {"id": tarifa_id})

    audit(
        engine,
        "tarifa.excluida",
        gestor_id=gestor_id,
        entidade="plantao_tarifas",
        entidade_id=tarifa_id,
        ip=ip,
    )


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
    data: str,
    hora_inicio: str,
    hora_fim: str,
    posicoes: list[dict],
    gestor_id: int,
    observacoes: str = "",
    ip: str = "",
    auto_approve: bool = False,
) -> int:
    if tipo not in ("presencial", "disponibilidade"):
        raise ValueError("Tipo de plantao invalido.")
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
                (local_id, tipo, data, hora_inicio, hora_fim, observacoes, status, auto_approve, criado_em, alterado_em, criado_por)
            VALUES
                (:local_id, :tipo, :data, :hora_inicio, :hora_fim, :observacoes, 'rascunho', :auto_approve, :agora, :agora, :gestor_id)
            """,
            {
                "local_id": local_id,
                "tipo": tipo,
                "data": data,
                "hora_inicio": hora_inicio,
                "hora_fim": hora_fim,
                "observacoes": observacoes.strip(),
                "auto_approve": auto_approve,
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


def criar_lote_plantao(
    engine: Any,
    local_id: int,
    tipo: str,
    data_inicio: str,
    data_fim: str,
    dias_semana: list[int],
    hora_inicio: str,
    hora_fim: str,
    vagas_veterinario: int,
    vagas_auxiliar: int,
    gestor_id: int,
    auto_approve: bool = False,
    observacoes: str = "",
    ip: str = "",
) -> dict:
    """
    Cria múltiplas datas de plantão para um período e dias da semana.

    dias_semana: lista de inteiros 0-6 (0=seg ... 6=dom, convenção Python weekday)
    Retorna: {"criadas": [data_id,...], "ignoradas": [date_str,...], "total": int}
    """
    from datetime import date as _date, timedelta

    inicio = _date.fromisoformat(data_inicio)
    fim = _date.fromisoformat(data_fim)
    if fim < inicio:
        raise ValueError("data_fim deve ser >= data_inicio.")
    if not dias_semana:
        raise ValueError("Selecione pelo menos um dia da semana.")

    dias_set = set(dias_semana)
    criadas: list[int] = []
    ignoradas: list[str] = []

    d = inicio
    while d <= fim:
        if d.weekday() in dias_set:
            posicoes = []
            if vagas_veterinario > 0:
                posicoes.append({"tipo": "veterinario", "vagas": vagas_veterinario})
            if vagas_auxiliar > 0:
                posicoes.append({"tipo": "auxiliar", "vagas": vagas_auxiliar})
            if not posicoes:
                ignoradas.append(d.isoformat())
            else:
                try:
                    data_id = criar_data_plantao(
                        engine,
                        local_id=local_id,
                        tipo=tipo,
                        data=d.isoformat(),
                        hora_inicio=hora_inicio,
                        hora_fim=hora_fim,
                        posicoes=posicoes,
                        gestor_id=gestor_id,
                        observacoes=observacoes,
                        ip=ip,
                        auto_approve=auto_approve,
                    )
                    criadas.append(data_id)
                except ValueError:
                    ignoradas.append(d.isoformat())
        d += timedelta(days=1)

    return {"criadas": criadas, "ignoradas": ignoradas, "total": len(criadas)}


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
    hora_inicio_disponibilidade: str = "20:00",
    hora_fim_disponibilidade: str = "08:00",
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
                data_id = _insert_and_get_id(
                    conn,
                    """
                    INSERT INTO plantao_datas
                        (local_id, tipo, data, hora_inicio, hora_fim, observacoes, status, criado_em, alterado_em, criado_por)
                    VALUES
                        (:local_id, 'presencial', :data, :hora_inicio, :hora_fim, '', 'rascunho', :agora, :agora, :gestor_id)
                    """,
                    {
                        "local_id": local_id,
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

            existe_disponibilidade = conn.execute(
                text(
                    "SELECT id FROM plantao_datas "
                    "WHERE local_id=:local_id AND data=:data AND tipo='disponibilidade' AND status IN ('rascunho','publicado')"
                ),
                {"local_id": local_id, "data": data_str},
            ).mappings().first()
            if not existe_disponibilidade:
                data_id_s = _insert_and_get_id(
                    conn,
                    """
                    INSERT INTO plantao_datas
                        (local_id, tipo, data, hora_inicio, hora_fim, observacoes, status, criado_em, alterado_em, criado_por)
                    VALUES
                        (:local_id, 'disponibilidade', :data, :hora_inicio, :hora_fim, '', 'rascunho', :agora, :agora, :gestor_id)
                    """,
                    {
                        "local_id": local_id,
                        "data": data_str,
                        "hora_inicio": hora_inicio_disponibilidade,
                        "hora_fim": hora_fim_disponibilidade,
                        "agora": _utcnow(),
                        "gestor_id": gestor_id,
                    },
                    "SELECT id FROM plantao_datas WHERE local_id=:local_id AND data=:data AND tipo='disponibilidade' ORDER BY id DESC LIMIT 1",
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
    else:
        # provisorio — notifica gestores para que possam confirmar
        notificar_gestores(
            engine,
            "nova_candidatura",
            f"Nova candidatura: {posicao['data']} {posicao['hora_inicio']}–{posicao['hora_fim']}",
            f"{perfil['tipo']} · {perfil.get('nome') or perfil.get('email', '')}",
            entidade="plantao_candidaturas",
            entidade_id=candidatura_id,
            permissao="plantao_aprovar_candidaturas",
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
            "tipo": cand.get("data_tipo", "presencial"),
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
    notificar_gestores(
        engine,
        "candidatura_cancelada",
        f"Candidatura cancelada: {cand['data']} {cand['hora_inicio']}–{cand['hora_fim']}",
        f"{cand.get('perfil_nome') or cand.get('perfil_email', '')} cancelou a candidatura.",
        entidade="plantao_candidaturas",
        entidade_id=candidatura_id,
        permissao="plantao_aprovar_candidaturas",
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
                    "tipo": cand_a.get("data_tipo", "presencial"),
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
                    "tipo": cand_b.get("data_tipo", "presencial"),
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
                    "tipo": cand_a.get("data_tipo", "presencial"),
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


def aderir_disponibilidade(
    engine: Any,
    data_id: int,
    perfil_id: int,
    ip: str = "",
) -> int:
    data_row = get_data_plantao(engine, data_id)
    if not data_row:
        raise ValueError("Data de disponibilidade nao encontrada.")
    if data_row["tipo"] != "disponibilidade" or data_row["status"] != "publicado":
        raise ValueError("A adesao e permitida apenas para disponibilidade publicada.")

    perfil = get_perfil_por_id(engine, perfil_id)
    if not perfil or perfil["status"] != "ativo" or perfil["tipo"] != "veterinario":
        raise ValueError("Somente veterinarios ativos podem aderir a disponibilidade.")

    with engine.begin() as conn:
        existe = conn.execute(
            text(
                "SELECT id FROM plantao_disponibilidade "
                "WHERE data_id=:data_id AND perfil_id=:perfil_id AND status='ativo'"
            ),
            {"data_id": data_id, "perfil_id": perfil_id},
        ).mappings().first()
        if existe:
            raise ValueError("Voce ja aderiu a disponibilidade desta data.")

        row = conn.execute(
            text(
                "SELECT COALESCE(MAX(prioridade), 0) AS max_prio "
                "FROM plantao_disponibilidade WHERE data_id=:data_id AND status='ativo'"
            ),
            {"data_id": data_id},
        ).mappings().first()
        prioridade = (int(row["max_prio"]) if row else 0) + 1
        adesao_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO plantao_disponibilidade (data_id, perfil_id, prioridade, status, criado_em)
            VALUES (:data_id, :perfil_id, :prioridade, 'ativo', :agora)
            """,
            {"data_id": data_id, "perfil_id": perfil_id, "prioridade": prioridade, "agora": _utcnow()},
            "SELECT id FROM plantao_disponibilidade WHERE data_id=:data_id AND perfil_id=:perfil_id AND status='ativo' ORDER BY id DESC LIMIT 1",
            {"data_id": data_id, "perfil_id": perfil_id},
        )

    audit(
        engine,
        "disponibilidade.adesao",
        perfil_id=perfil_id,
        entidade="plantao_disponibilidade",
        entidade_id=adesao_id,
        ip=ip,
    )
    return adesao_id


def cancelar_disponibilidade(
    engine: Any,
    adesao_id: int,
    perfil_id: int,
    ip: str = "",
) -> None:
    with engine.begin() as conn:
        adesao = conn.execute(
            text("SELECT * FROM plantao_disponibilidade WHERE id=:id"),
            {"id": adesao_id},
        ).mappings().first()
        if not adesao or adesao["status"] != "ativo":
            raise ValueError("Adesao nao encontrada ou ja cancelada.")
        if int(adesao["perfil_id"]) != int(perfil_id):
            raise ValueError("Voce nao pode cancelar adesao de outro plantonista.")

        data_id = int(adesao["data_id"])
        conn.execute(
            text(
                "UPDATE plantao_disponibilidade SET status='cancelado', cancelado_em=:agora WHERE id=:id"
            ),
            {"agora": _utcnow(), "id": adesao_id},
        )

        ativos = conn.execute(
            text(
                "SELECT id FROM plantao_disponibilidade "
                "WHERE data_id=:data_id AND status='ativo' "
                "ORDER BY prioridade ASC, id ASC"
            ),
            {"data_id": data_id},
        ).mappings().all()
        for ordem, row in enumerate(ativos, start=1):
            conn.execute(
                text("UPDATE plantao_disponibilidade SET prioridade=:ordem WHERE id=:id"),
                {"ordem": ordem, "id": int(row["id"])},
            )

    audit(
        engine,
        "disponibilidade.cancelado",
        perfil_id=perfil_id,
        entidade="plantao_disponibilidade",
        entidade_id=adesao_id,
        ip=ip,
    )


def reordenar_disponibilidade(
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
                "SELECT id FROM plantao_disponibilidade "
                "WHERE data_id=:data_id AND status='ativo' ORDER BY prioridade ASC, id ASC"
            ),
            {"data_id": data_id},
        ).mappings().all()
        ativos_ids = [int(r["id"]) for r in ativos]
        if sorted(ativos_ids) != sorted([int(x) for x in nova_ordem]):
            raise ValueError("Nova ordem invalida para a disponibilidade.")

        for ordem, adesao_id in enumerate(nova_ordem, start=1):
            conn.execute(
                text("UPDATE plantao_disponibilidade SET prioridade=:ordem WHERE id=:id"),
                {"ordem": ordem, "id": int(adesao_id)},
            )

    audit(
        engine,
        "disponibilidade.reordenado",
        gestor_id=gestor_id,
        entidade="plantao_disponibilidade",
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
        "plantao_notif_disponibilidade_dias_antecedencia",
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
