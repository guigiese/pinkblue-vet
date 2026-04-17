"""
Módulo Plantão — utilitário de calendário.

Gera a estrutura de semanas/dias para o calendário mensal de escalas,
enriquecida com todos os estados necessários para o visual multi-estado.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Any


_MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def build_month_calendar(
    year: int,
    month: int,
    datas_mes: list[dict],
    vagas_abertas: list[dict] | None = None,
    candidaturas_usuario: list[dict] | None = None,
    *,
    eventos_por_data: dict[str, list[dict]] | None = None,
    feriados: dict[str, str] | None = None,
) -> dict:
    """
    Retorna a estrutura do calendário mensal.

    Parâmetros:
        year                 — ano
        month                — mês (1-12)
        datas_mes            — resultado de listar_datas_por_mes
        vagas_abertas        — escalas com vagas em aberto (compat legado)
        candidaturas_usuario — candidaturas do usuário no mês (compat legado)
        eventos_por_data     — dict {date_iso: [evento_dict]} com status rico por evento
        feriados             — dict {date_iso: nome_do_feriado}

    Cada célula de semana contém:
        day, date, out_of_month, is_today, is_past
        is_sunday, is_holiday, holiday_name
        escalas          — lista de datas_mes para o dia (compat)
        eventos          — lista de eventos ricos do dia
        has_open         — algum evento com status "livre"
        has_confirmed    — algum evento com status "meu_turno"
        has_pending      — algum evento com status "pendente" (aguardando aprovação)
        has_cedido       — algum evento com status "cedido"
        has_disponibilidade — algum evento com status "disponibilidade_aberta" ou "minha_disponibilidade"
        has_draft        — algum evento com status "rascunho" (admin)
        candidatada      — compat legado
    """
    vagas_abertas = vagas_abertas or []
    candidaturas_usuario = candidaturas_usuario or []
    eventos_por_data = eventos_por_data or {}
    feriados = feriados or {}

    hoje = date.today()

    # Índice legado de escalas por data
    escalas_por_data: dict[str, list[dict]] = {}
    for e in datas_mes:
        escalas_por_data.setdefault(e["data"], []).append(e)

    datas_com_vaga: set[str] = {v["data"] for v in vagas_abertas}
    datas_candidatadas: set[str] = {c["data"] for c in candidaturas_usuario}

    # Navegação prev/next
    if month == 1:
        prev = {"year": year - 1, "month": 12}
    else:
        prev = {"year": year, "month": month - 1}
    if month == 12:
        next_ = {"year": year + 1, "month": 1}
    else:
        next_ = {"year": year, "month": month + 1}

    cal = calendar.monthcalendar(year, month)

    weeks = []
    for raw_week in cal:
        week = []
        for day in raw_week:
            if day == 0:
                week.append({"out_of_month": True})
                continue
            d = date(year, month, day)
            iso = d.isoformat()
            is_sunday = d.weekday() == 6  # Python: Mon=0, Sun=6

            eventos = eventos_por_data.get(iso, [])
            statuses = {ev.get("status", "") for ev in eventos}

            week.append({
                "day": day,
                "date": iso,
                "out_of_month": False,
                "is_today": d == hoje,
                "is_past": d < hoje,
                "is_sunday": is_sunday,
                "is_holiday": iso in feriados,
                "holiday_name": feriados.get(iso),
                # eventos ricos
                "eventos": eventos,
                "has_open": "livre" in statuses,
                "has_confirmed": "meu_turno" in statuses,
                "has_pending": "pendente" in statuses,
                "has_cedido": "cedido" in statuses,
                "has_disponibilidade": bool(statuses & {"disponibilidade_aberta", "minha_disponibilidade"}),
                "has_draft": "rascunho" in statuses,
                # compat legado
                "escalas": escalas_por_data.get(iso, []),
                "candidatada": iso in datas_candidatadas,
            })
        weeks.append(week)

    return {
        "year": year,
        "month": month,
        "month_name": _MONTHS_PT.get(month, str(month)),
        "prev": prev,
        "next": next_,
        "weeks": weeks,
        "weekday_labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
    }
