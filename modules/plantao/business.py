"""
Módulo Plantão — lógica de negócio pura.

Todas as funções aqui são puras (sem I/O, sem banco): recebem dados já
carregados e devolvem resultados. Isso as torna 100% testáveis em isolamento.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


# ── Horas do turno ─────────────────────────────────────────────────────────────

def calcular_horas_turno(hora_inicio: str, hora_fim: str) -> float:
    """Duração do turno em horas, suportando virada de meia-noite (overnight).

    Args:
        hora_inicio: "HH:MM"
        hora_fim:    "HH:MM" — pode ser menor que hora_inicio (overnight)

    Returns:
        Duração em horas (float), sempre > 0.

    Example:
        >>> calcular_horas_turno("08:00", "20:00")
        12.0
        >>> calcular_horas_turno("20:00", "08:00")  # overnight
        12.0
    """
    h_i, m_i = map(int, hora_inicio.split(":"))
    h_f, m_f = map(int, hora_fim.split(":"))
    minutos_inicio = h_i * 60 + m_i
    minutos_fim = h_f * 60 + m_f
    if minutos_fim <= minutos_inicio:
        # overnight: turno passa da meia-noite
        minutos_duracao = (24 * 60 - minutos_inicio) + minutos_fim
    else:
        minutos_duracao = minutos_fim - minutos_inicio
    return round(minutos_duracao / 60, 4)


# ── Horas úteis ───────────────────────────────────────────────────────────────

_HORA_INICIO_UTIL = 8   # 08:00
_HORA_FIM_UTIL = 18     # 18:00


def _minutos_uteis_no_dia(dia: date, hora_referencia: datetime | None = None) -> int:
    """Minutos úteis disponíveis em um dado dia (seg–sex, 8h–18h, sem feriados).

    Se hora_referencia for fornecida e for do mesmo dia, conta a partir dela.
    """
    # Feriados: tratados externamente — este método não conhece o calendário.
    # Fim de semana = 0 minutos úteis.
    if dia.weekday() >= 5:  # sábado=5, domingo=6
        return 0
    inicio = _HORA_INICIO_UTIL * 60
    fim = _HORA_FIM_UTIL * 60
    if hora_referencia and hora_referencia.date() == dia:
        agora_minutos = hora_referencia.hour * 60 + hora_referencia.minute
        inicio = max(inicio, agora_minutos)
    return max(0, fim - inicio)


def calcular_horas_uteis_restantes(
    agora: datetime,
    inicio_turno: datetime,
    feriados: set[date],
) -> float:
    """Horas úteis restantes entre agora e o início do turno.

    Horas úteis: seg–sex, 08h–18h, excluindo feriados.
    Se início_turno <= agora, retorna 0.0.

    Args:
        agora:         momento atual (timezone-naive, UTC).
        inicio_turno:  início do turno (timezone-naive, UTC).
        feriados:      conjunto de datas que são feriados (sem expediente útil).

    Returns:
        Horas úteis como float.
    """
    if inicio_turno <= agora:
        return 0.0

    total_minutos = 0
    cursor = agora

    while cursor.date() < inicio_turno.date():
        dia = cursor.date()
        if dia not in feriados:
            minutos = _minutos_uteis_no_dia(dia, hora_referencia=cursor if cursor.date() == agora.date() else None)
            total_minutos += minutos
        # avança para meia-noite do próximo dia
        cursor = datetime(cursor.year, cursor.month, cursor.day) + timedelta(days=1)

    # último fragmento: mesmo dia que o início do turno
    if cursor.date() == inicio_turno.date() and cursor.date() not in feriados:
        inicio_minutos = _HORA_INICIO_UTIL * 60
        fim_minutos = min(_HORA_FIM_UTIL * 60, inicio_turno.hour * 60 + inicio_turno.minute)
        cursor_minutos = cursor.hour * 60 + cursor.minute
        # se cursor ainda é meia-noite (avançamos um dia inteiro), usa início do expediente
        inicio_contagem = max(inicio_minutos, cursor_minutos)
        total_minutos += max(0, fim_minutos - inicio_contagem)

    return round(total_minutos / 60, 4)


# ── Cancelamento ──────────────────────────────────────────────────────────────

def pode_cancelar(
    status: str,
    inicio_turno: datetime,
    agora: datetime,
    prazo_horas_uteis: int,
    feriados: set[date],
) -> tuple[bool, str]:
    """Verifica se uma candidatura pode ser cancelada.

    Regras:
    - Status deve ser 'provisorio' ou 'confirmado'
    - Turno não pode ter começado (início_turno > agora)
    - Deve haver pelo menos prazo_horas_uteis de horas úteis antes do turno

    Returns:
        (pode_cancelar: bool, motivo: str)
        motivo é vazio string se pode cancelar.
    """
    if status not in ("provisorio", "confirmado"):
        return False, f"Status '{status}' não permite cancelamento."

    if agora >= inicio_turno:
        return False, "O turno já começou. Cancelamento não é permitido após o início."

    horas_uteis = calcular_horas_uteis_restantes(agora, inicio_turno, feriados)
    if horas_uteis < prazo_horas_uteis:
        return False, (
            f"Prazo mínimo de {prazo_horas_uteis}h úteis não cumprido. "
            f"Restam apenas {horas_uteis:.1f}h úteis."
        )

    return True, ""


# ── Cálculo de valor base ──────────────────────────────────────────────────────

def calcular_valor_base(
    tipo_perfil: str,
    dia_semana: int,
    is_feriado: bool,
    horas: float,
    tarifas: list[dict[str, Any]],
    tipo_data: str = "presencial",
) -> tuple[float | None, float | None]:
    """Calcula valor_hora_snapshot e valor_base_calculado para uma candidatura.

    Para sobreaviso retorna (None, None) — não é remunerado.

    Lógica de scoring (maior score = mais específico = preferido):
      +2  match exato de dia_semana
       0  dia_semana NULL (wildcard)
      -∞  dia_semana diferente (descarta)
      +1  match exato de feriado flag
       0  feriado NULL (wildcard)
      -∞  feriado diferente (descarta)

    Empate → tarifa com maior id (criado mais recentemente) vence.

    Args:
        tipo_perfil: 'veterinario' | 'auxiliar'
        dia_semana:  0-6 (weekday Python)
        is_feriado:  True se a data do turno é feriado
        horas:       duração do turno em horas
        tarifas:     lista de dicts com campos da tabela plantao_tarifas,
                     já filtrada por vigência (vigente_de <= hoje <= vigente_ate or NULL).
        tipo_data:   tipo da escala ('presencial' | 'sobreaviso'); sobreaviso não remunera.

    Returns:
        (valor_hora_snapshot, valor_base_calculado) — ambos float ou ambos None.
    """
    if tipo_data == "sobreaviso":
        return None, None

    feriado_int = 1 if is_feriado else 0

    # filtra tarifas pelo tipo_perfil
    candidatas = [t for t in tarifas if t["tipo_perfil"] == tipo_perfil]

    def _score(t: dict) -> int:
        """Maior score = mais específico = preferido. -1 = descarta."""
        score = 0
        t_dia = t.get("dia_semana")
        if t_dia == dia_semana:
            score += 2
        elif t_dia is None:
            score += 0
        else:
            return -1  # dia não corresponde

        t_fer = t.get("feriado")
        if t_fer == feriado_int:
            score += 1
        elif t_fer is None:
            score += 0
        else:
            return -1  # flag feriado não corresponde

        return score

    scored = [(t, _score(t)) for t in candidatas]
    validas = [(t, s) for t, s in scored if s >= 0]
    if not validas:
        return None, None

    # Empate: maior id (mais recente) vence
    melhor, _ = max(validas, key=lambda x: (x[1], x[0].get("id", 0)))
    valor_hora = float(melhor["valor_hora"])
    valor_base = round(valor_hora * horas, 2)
    return valor_hora, valor_base


# ── Remuneração final (para módulo financeiro) ────────────────────────────────

def calcular_pagamento_veterinario(
    valor_base_calculado: float | None,
    comissao_dia_inteiro: float | None,
) -> float | None:
    """Remuneração final do veterinário: MAX(piso, comissão do dia inteiro).

    A comissão é do dia INTEIRO no SimplesVet — sem filtro de horário.
    Se o veterinário trabalhou além do turno, toda a comissão do dia conta.

    Args:
        valor_base_calculado: piso mínimo calculado no momento da confirmação.
        comissao_dia_inteiro: comissão total apurada no SimplesVet para o dia.

    Returns:
        Valor a pagar (float) ou None se dados insuficientes.
    """
    if valor_base_calculado is None and comissao_dia_inteiro is None:
        return None
    piso = valor_base_calculado or 0.0
    comissao = comissao_dia_inteiro or 0.0
    return round(max(piso, comissao), 2)


def calcular_pagamento_auxiliar(
    valor_base_calculado: float | None,
) -> float | None:
    """Remuneração final do auxiliar: valor_base_calculado (sem comissão).

    Args:
        valor_base_calculado: valor calculado no momento da confirmação.

    Returns:
        Valor a pagar (float) ou None.
    """
    if valor_base_calculado is None:
        return None
    return round(valor_base_calculado, 2)
