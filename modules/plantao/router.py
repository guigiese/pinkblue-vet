"""
Modulo Plantao - router FastAPI.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import ChoiceLoader, FileSystemLoader
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from pb_platform.auth import (
    attach_user_to_request,
    gerar_csrf_token,
    has_permission,
    validar_csrf,
)
from pb_platform.settings import settings
from pb_platform.storage import store
from .notifications import (
    contar_nao_lidas,
    listar_notificacoes,
    marcar_lida,
    marcar_todas_lidas,
)

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
PLATFORM_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"
_templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
_templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader(str(TEMPLATES_DIR)),
        FileSystemLoader(str(PLATFORM_TEMPLATES_DIR)),
    ]
)

# Filtro tojson para serialização segura em templates
import json as _json

def _tojson_filter(value, indent=None):
    return _json.dumps(value, ensure_ascii=False, default=str, indent=indent)

_templates.env.filters["tojson"] = _tojson_filter
_engine: Any = None


def _redir_erro(path: str, msg: str) -> RedirectResponse:
    return RedirectResponse(f"{path}?erro={quote_plus(msg)}", status_code=303)


def make_router(engine: Any) -> APIRouter:
    global _engine
    _engine = engine

    router = APIRouter(prefix="/plantao")

    # ── Guards de auth unificada ──────────────────────────────────────────────

    def _exige_plantonista(request: Request):
        """
        Valida que há um usuário da plataforma logado com permissão plantao_access.
        Popula request.state.plantonista (alias de request.state.user).
        Retorna o user dict ou uma RedirectResponse.
        """
        user = attach_user_to_request(request)
        if not user:
            return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
        if not has_permission(request, "plantao_access") and not has_permission(request, "manage_plantao"):
            return RedirectResponse("/login?erro=sem_permissao", status_code=303)
        # Popula state para compatibilidade com templates que usam 'perfil'
        request.state.plantonista = user
        raw_token = request.cookies.get(settings.session_cookie_name, "")
        request.state.csrf_token = gerar_csrf_token(raw_token)
        return user

    # Sub-permissões que concedem acesso a alguma área admin
    _PLANTAO_ADMIN_PERMS = (
        "manage_plantao",
        "plantao_gerir_escalas",
        "plantao_aprovar_candidaturas",
        "plantao_aprovar_cadastros",
        "plantao_ver_relatorios",
    )

    def _exige_gestor(request: Request, permissao: str = "manage_plantao"):
        """
        Valida que o usuário está logado e possui a permissão indicada
        (ou manage_plantao, que cascateia todas as sub-permissões).
        Popula request.state.gestor / request.state.user.
        Retorna o user dict ou uma Response de erro.
        """
        user = attach_user_to_request(request)
        if not user:
            return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
        # Aceita manage_plantao (hierarquia) OU a permissão específica da rota
        if not has_permission(request, permissao) and not has_permission(request, "manage_plantao"):
            return HTMLResponse("<h1>403 — Sem permissão para esta área.</h1>", status_code=403)
        request.state.gestor = user
        request.state.user = user
        raw_token = request.cookies.get(settings.session_cookie_name, "")
        request.state.csrf_token = gerar_csrf_token(raw_token)
        return user

    # ── Redirects de compatibilidade (rotas de auth antigas) ─────────────────

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    async def landing(request: Request):
        """Página de entrada unificada do módulo Plantão.

        Renderiza uma visão comum (próximas escalas, alertas, links rápidos)
        com seções distintas por role. Gestores veem alertas e métricas;
        plantonistas veem seus turnos e as escalas abertas.
        """
        from .queries import (
            get_alertas_dashboard,
            listar_datas_por_mes,
            listar_candidaturas_por_perfil,
            listar_locais,
        )
        from datetime import date, timedelta

        user = attach_user_to_request(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        if not has_permission(request, "plantao_access") and not has_permission(request, "manage_plantao"):
            return RedirectResponse("/login?erro=sem_permissao", status_code=303)

        raw_token = request.cookies.get(settings.session_cookie_name, "")
        request.state.csrf_token = gerar_csrf_token(raw_token)

        hoje = date.today()
        is_gestor = has_permission(request, "manage_plantao")

        # Próximas escalas publicadas (7 dias)
        fim_semana = (hoje + timedelta(days=7)).isoformat()
        proximas_escalas = listar_datas_por_mes(engine, hoje.year, hoje.month, None, status="publicado")
        proximas_escalas = [e for e in proximas_escalas if e["data"] >= hoje.isoformat() and e["data"] <= fim_semana]

        # Dados específicos por role
        alertas = get_alertas_dashboard(engine) if is_gestor else None
        meus_turnos = (
            listar_candidaturas_por_perfil(engine, user["id"], apenas_futuras=True, status="confirmado")[:5]
            if not is_gestor
            else []
        )

        return _render(
            request,
            "plantao_landing.html",
            perfil=user,
            is_gestor=is_gestor,
            proximas_escalas=proximas_escalas,
            alertas=alertas,
            meus_turnos=meus_turnos,
            hoje=hoje.isoformat(),
        )

    @router.get("/login")
    async def login_compat():
        return RedirectResponse("/login", status_code=301)

    @router.get("/logout")
    async def logout_compat():
        return RedirectResponse("/logout", status_code=301)

    @router.get("/cadastro")
    async def cadastro_compat():
        return RedirectResponse("/cadastro", status_code=301)

    @router.get("/cadastro/aguardando")
    async def cadastro_aguardando_compat():
        return RedirectResponse("/cadastro/aguardando", status_code=301)

    @router.get("/senha/recuperar")
    async def recuperar_senha_compat():
        return RedirectResponse("/login", status_code=301)

    # ── Agenda legada → redireciona para /escalas ─────────────────────────────

    @router.get("/agenda", response_class=HTMLResponse)
    async def agenda_redirect(request: Request, mes: int = 0, ano: int = 0):
        parts = []
        if ano:
            parts.append(f"ano={ano}")
        if mes:
            parts.append(f"mes={mes}")
        qs = "?" + "&".join(parts) if parts else ""
        return RedirectResponse(f"/plantao/escalas{qs}", status_code=301)

    # Redirecionamentos das rotas antigas do plantonista → escalas unificadas
    @router.get("/meus-turnos", response_class=HTMLResponse)
    async def meus_turnos_redirect(request: Request):
        return RedirectResponse("/plantao/escalas", status_code=302)

    @router.get("/trocas", response_class=HTMLResponse)
    async def trocas_redirect(request: Request):
        return RedirectResponse("/plantao/escalas", status_code=302)

    @router.get("/sobreaviso", response_class=HTMLResponse)
    async def sobreaviso_redirect(request: Request):
        qs = request.url.query
        target = "/plantao/disponibilidade" + (f"?{qs}" if qs else "")
        return RedirectResponse(target, status_code=302)

    @router.get("/disponibilidade", response_class=HTMLResponse)
    async def disponibilidade_page(request: Request):
        from .queries import listar_disponibilidade_por_perfil, listar_datas_por_mes
        from datetime import date as dt_date

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil

        hoje = dt_date.today()
        ano, mes = hoje.year, hoje.month
        disponibilidades_abertas = listar_datas_por_mes(engine, ano, mes, None, tipo="disponibilidade", status="publicado")
        minhas_adesoes = listar_disponibilidade_por_perfil(engine, perfil["id"])
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_disponibilidade.html",
            csrf_token=csrf,
            perfil=perfil,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
            disponibilidades_abertas=disponibilidades_abertas,
            minhas_adesoes=minhas_adesoes,
        )

    @router.get("/escalas", response_class=HTMLResponse)
    async def escalas_page(
        request: Request,
        mes: int = 0,
        ano: int = 0,
        local_id: int = 0,
    ):
        """
        Tela unificada de escalas. Adapta por permissão:
        - Plantonistas: veem escalas publicadas, suas candidaturas, disponibilidades
        - Gestores: veem tudo (inclusive rascunhos), podem criar/publicar escalas
        """
        from .queries import (
            listar_datas_por_mes,
            listar_datas_com_vagas_abertas,
            listar_candidaturas_por_perfil,
            listar_substituicoes_abertas,
            listar_disponibilidade_por_perfil,
            listar_feriados_por_periodo,
            listar_locais,
        )
        from .calendar_utils import build_month_calendar
        from datetime import date as _date
        from collections import defaultdict
        import calendar as _cal

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil

        is_gestor = bool(
            has_permission(request, "plantao_gerir_escalas")
            or has_permission(request, "manage_plantao")
        )

        hoje = _date.today()
        ano = ano or hoje.year
        mes = mes or hoje.month

        # ── Dados compartilhados ─────────────────────────────────────────────
        locais = listar_locais(engine)
        local_sel = local_id or None
        # Auto-selecionar quando há apenas 1 local
        if not local_sel and len(locais) == 1:
            local_sel = locais[0]["id"]
            local_id = local_sel

        _ultimo_dia = _cal.monthrange(ano, mes)[1]
        inicio_mes = f"{ano:04d}-{mes:02d}-01"
        fim_mes = f"{ano:04d}-{mes:02d}-{_ultimo_dia:02d}"
        feriados_rows = listar_feriados_por_periodo(engine, inicio_mes, fim_mes)
        feriados_dict = {r["data"]: r["nome"] for r in feriados_rows}

        # ── Camada admin (gestores): todas as escalas incluindo rascunhos ─────
        datas_mes_admin: list[dict] = []
        if is_gestor:
            datas_mes_admin = listar_datas_por_mes(engine, ano, mes, local_sel)

        # ── Camada plantonista: dados enriquecidos com status por usuário ─────
        escalas_mes_pub = listar_datas_por_mes(engine, ano, mes, local_sel, status="publicado")
        vagas_abertas = listar_datas_com_vagas_abertas(engine, local_sel)
        minhas_candidaturas = listar_candidaturas_por_perfil(engine, perfil["id"])
        substituicoes = listar_substituicoes_abertas(engine, perfil.get("tipo", ""))
        disponibilidades_abertas = listar_datas_por_mes(
            engine, ano, mes, local_sel, tipo="disponibilidade", status="publicado"
        )
        minhas_adesoes = listar_disponibilidade_por_perfil(engine, perfil["id"])
        minhas_adesoes_ids = {a["data_id"]: a for a in minhas_adesoes}

        # ── Montar eventos_por_data ──────────────────────────────────────────
        eventos_por_data: dict[str, list[dict]] = defaultdict(list)

        # Índices para lookup eficiente
        vagas_por_data: dict[int, list[dict]] = defaultdict(list)
        for _v in vagas_abertas:
            vagas_por_data[_v["data_id"]].append(_v)

        cands_conf_por_data: dict[int, list[dict]] = defaultdict(list)
        for _c in minhas_candidaturas:
            if _c["status"] in ("confirmado", "provisorio"):
                cands_conf_por_data[_c["data_id"]].append(_c)

        # Escalas presenciais publicadas
        for e in escalas_mes_pub:
            data = e["data"]
            data_id = e["id"]
            _base = {
                "hora_inicio": e.get("hora_inicio", ""),
                "hora_fim": e.get("hora_fim", ""),
                "local_nome": e.get("local_nome", ""),
                "posicao_id": None,
                "candidatura_id": None,
                "substituicao_id": None,
                "data_id": data_id,
                "adesao_id": None,
                "escala_id": data_id,
                "admin_only": False,
                "vagas_total": e.get("vagas_total", 0),
                "confirmados_total": e.get("confirmados_total", 0),
            }

            # Agrupa vagas abertas por tipo para esta data
            vagas_desta: dict[str, dict] = {}
            for _v in vagas_por_data.get(data_id, []):
                tp = _v.get("tipo_perfil", "")
                tipo_ev = "plantao_aux" if "aux" in tp.lower() else "plantao_vet"
                if tipo_ev not in vagas_desta:
                    vagas_desta[tipo_ev] = _v

            # Agrupa candidaturas confirmadas por tipo para esta data
            cands_desta: dict[str, dict] = {}
            for _c in cands_conf_por_data.get(data_id, []):
                tp = _c.get("posicao_tipo", "")
                tipo_ev = "plantao_aux" if "aux" in tp.lower() else "plantao_vet"
                cands_desta[tipo_ev] = _c

            todos_tipos = set(vagas_desta.keys()) | set(cands_desta.keys())

            if not todos_tipos:
                # Sem vagas abertas e sem candidaturas → preenchido (fallback)
                eventos_por_data[data].append({**_base, "tipo": "plantao_vet", "status": "preenchido"})
                continue

            for tipo in todos_tipos:
                ev = {**_base, "tipo": tipo}
                if tipo in cands_desta:
                    ev["status"] = "meu_turno"
                    ev["candidatura_id"] = cands_desta[tipo]["id"]
                else:
                    vaga = vagas_desta[tipo]
                    ev["status"] = "livre"
                    ev["posicao_id"] = vaga["posicao_id"]
                eventos_por_data[data].append(ev)

        # Substituições abertas (cedido)
        for s in substituicoes:
            data = s["data"]
            tp = s.get("tipo_posicao") or ""
            tipo = "plantao_aux" if "aux" in tp.lower() else "plantao_vet"
            eventos_por_data[data].append({
                "tipo": tipo, "status": "cedido",
                "hora_inicio": s.get("hora_inicio", ""),
                "hora_fim": s.get("hora_fim", ""),
                "local_nome": s.get("local_nome", ""),
                "posicao_id": None, "candidatura_id": None,
                "substituicao_id": s["id"], "data_id": None, "adesao_id": None,
                "escala_id": None, "admin_only": False,
                "vagas_total": 0, "confirmados_total": 0,
            })

        # Disponibilidades do mês
        for d in disponibilidades_abertas:
            data = d["data"]
            if d["id"] in minhas_adesoes_ids:
                adesao = minhas_adesoes_ids[d["id"]]
                st = "minha_disponibilidade"
                adesao_id = adesao["id"]
            else:
                st = "disponibilidade_aberta"
                adesao_id = None
            eventos_por_data[data].append({
                "tipo": "disponibilidade", "status": st,
                "hora_inicio": d.get("hora_inicio", ""),
                "hora_fim": d.get("hora_fim", ""),
                "local_nome": d.get("local_nome", ""),
                "posicao_id": None, "candidatura_id": None,
                "substituicao_id": None, "data_id": d["id"], "adesao_id": adesao_id,
                "escala_id": d["id"], "admin_only": False,
                "vagas_total": 0, "confirmados_total": 0,
            })

        # Gestor: injetar rascunhos e outros status não visíveis ao plantonista
        if is_gestor:
            pub_ids = {e["id"] for e in escalas_mes_pub}
            for e in datas_mes_admin:
                if e["id"] not in pub_ids:
                    data = e["data"]
                    tipo = "plantao_vet"  # rascunho: sem info de vagas; fallback
                    eventos_por_data[data].append({
                        "tipo": tipo, "status": e.get("status", "rascunho"),
                        "hora_inicio": e.get("hora_inicio", ""),
                        "hora_fim": e.get("hora_fim", ""),
                        "local_nome": e.get("local_nome", ""),
                        "posicao_id": None, "candidatura_id": None,
                        "substituicao_id": None, "data_id": e["id"], "adesao_id": None,
                        "escala_id": e["id"], "admin_only": True,
                        "vagas_total": e.get("vagas_total", 0),
                        "confirmados_total": e.get("confirmados_total", 0),
                    })

        datas_ordenadas = sorted(eventos_por_data.keys())

        # ── Calendário enriquecido ────────────────────────────────────────────
        datas_para_cal = datas_mes_admin if is_gestor else escalas_mes_pub
        calendario = build_month_calendar(
            ano, mes, datas_para_cal, vagas_abertas, minhas_candidaturas,
            eventos_por_data=dict(eventos_por_data),
            feriados=feriados_dict,
        )

        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_escalas.html",
            perfil=perfil,
            ano=ano,
            mes=mes,
            hoje=hoje.isoformat(),
            calendario=calendario,
            eventos_por_data=dict(eventos_por_data),
            datas_ordenadas=datas_ordenadas,
            locais=locais,
            local_id=local_id,
            feriados_dict=feriados_dict,
            is_gestor=is_gestor,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/escalas/{posicao_id}/candidatar")
    async def candidatar_action(request: Request, posicao_id: int):
        from .actions import candidatar

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            candidatar(engine, posicao_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse("/plantao/escalas?ok=1", status_code=303)

    @router.post("/candidaturas/{candidatura_id}/cancelar")
    async def cancelar_candidatura_action(request: Request, candidatura_id: int):
        from .actions import cancelar_candidatura, get_configuracao

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            prazo = int(get_configuracao(engine, "plantao_prazo_cancelamento_horas_uteis", "24"))
        except Exception:
            prazo = 24
        try:
            cancelar_candidatura(
                engine,
                candidatura_id,
                perfil["id"],
                prazo_horas_uteis=prazo,
                ip=request.client.host if request.client else "",
            )
        except ValueError as exc:
            return _redir_erro("/plantao/meus-turnos", str(exc))
        return RedirectResponse("/plantao/meus-turnos?ok=1", status_code=303)

    @router.post("/trocas/solicitar")
    async def solicitar_troca_action(
        request: Request,
        candidatura_a_id: int = Form(...),
        candidatura_b_id: int = Form(...),
        mensagem: str = Form(""),
    ):
        from .actions import solicitar_troca_direta

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            solicitar_troca_direta(
                engine,
                candidatura_a_id,
                candidatura_b_id,
                perfil["id"],
                mensagem=mensagem,
                ip=request.client.host if request.client else "",
            )
        except ValueError as exc:
            return _redir_erro("/plantao/trocas", str(exc))
        return RedirectResponse("/plantao/trocas?ok=1", status_code=303)

    @router.post("/trocas/substituicao")
    async def abrir_substituicao_action(
        request: Request,
        candidatura_a_id: int = Form(...),
        mensagem: str = Form(""),
    ):
        from .actions import abrir_substituicao

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            abrir_substituicao(
                engine,
                candidatura_a_id,
                perfil["id"],
                mensagem=mensagem,
                ip=request.client.host if request.client else "",
            )
        except ValueError as exc:
            return _redir_erro("/plantao/trocas", str(exc))
        return RedirectResponse("/plantao/trocas?ok=1", status_code=303)

    @router.post("/trocas/{troca_id}/aceitar")
    async def aceitar_troca_action(request: Request, troca_id: int):
        from .actions import aceitar_troca

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            aceitar_troca(engine, troca_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/trocas", str(exc))
        return RedirectResponse("/plantao/trocas?ok=1", status_code=303)

    @router.post("/trocas/{troca_id}/recusar")
    async def recusar_troca_action(request: Request, troca_id: int):
        from .actions import recusar_troca

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            recusar_troca(engine, troca_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/trocas", str(exc))
        return RedirectResponse("/plantao/trocas?ok=1", status_code=303)

    @router.post("/disponibilidade/{data_id}/aderir")
    async def aderir_disponibilidade_action(request: Request, data_id: int):
        from .actions import aderir_disponibilidade

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            aderir_disponibilidade(engine, data_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/disponibilidade", str(exc))
        return RedirectResponse("/plantao/disponibilidade?ok=1", status_code=303)

    @router.post("/disponibilidade/{adesao_id}/cancelar")
    async def cancelar_disponibilidade_action(request: Request, adesao_id: int):
        from .actions import cancelar_disponibilidade

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            cancelar_disponibilidade(engine, adesao_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/disponibilidade", str(exc))
        return RedirectResponse("/plantao/disponibilidade?ok=1", status_code=303)

    @router.get("/notificacoes", response_class=HTMLResponse)
    async def notificacoes_page(request: Request):
        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        notifs = listar_notificacoes(engine, perfil["id"])
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "plantao_notificacoes.html", notificacoes=notifs, csrf_token=csrf)

    @router.post("/notificacoes/{notif_id}/lida", response_class=HTMLResponse)
    async def marcar_notificacao_lida(request: Request, notif_id: int):
        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        marcar_lida(engine, notif_id, perfil["id"])
        return HTMLResponse("", status_code=200)

    @router.post("/notificacoes/todas-lidas")
    async def marcar_todas_lidas_action(request: Request):
        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        marcar_todas_lidas(engine, perfil["id"])
        return RedirectResponse("/plantao/notificacoes", status_code=303)

    @router.get("/partials/badge-notificacoes", response_class=HTMLResponse)
    async def badge_notificacoes(request: Request):
        perfil = attach_user_to_request(request)
        if not perfil or not has_permission(request, "plantao_access"):
            return HTMLResponse("")
        n = contar_nao_lidas(engine, perfil["id"])
        if n == 0:
            return HTMLResponse("")
        return HTMLResponse(
            f'<span class="inline-flex items-center justify-center px-1.5 py-0.5 text-xs'
            f' font-bold leading-none text-white bg-red-600 rounded-full">{n}</span>'
        )

    @router.get("/perfil", response_class=HTMLResponse)
    async def perfil_page(request: Request, salvo: str = ""):
        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "plantao_perfil.html", perfil=perfil, csrf_token=csrf, salvo=salvo)

    @router.post("/perfil/atualizar")
    async def atualizar_perfil_action(
        request: Request,
        nome: str = Form(...),
        telefone: str = Form(""),
        especialidade: str = Form(""),
    ):
        from .actions import atualizar_perfil

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        atualizar_perfil(
            engine,
            perfil["id"],
            {"nome": nome.strip(), "telefone": telefone.strip(), "especialidade": especialidade.strip()},
            ip=request.client.host if request.client else "",
        )
        return RedirectResponse("/plantao/perfil?salvo=1", status_code=303)

    @router.post("/perfil/senha")
    async def alterar_senha_action(
        request: Request,
        senha_atual: str = Form(...),
        nova_senha: str = Form(...),
        nova_senha_confirma: str = Form(...),
    ):
        from .actions import alterar_senha

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        csrf = getattr(request.state, "csrf_token", "")
        if nova_senha != nova_senha_confirma:
            return _render(request, "plantao_perfil.html", perfil=perfil, csrf_token=csrf, erro_senha="As senhas nao coincidem.")
        try:
            alterar_senha(engine, perfil["id"], senha_atual, nova_senha)
        except ValueError as exc:
            return _render(request, "plantao_perfil.html", perfil=perfil, csrf_token=csrf, erro_senha=str(exc))
        return RedirectResponse("/plantao/perfil?salvo=1", status_code=303)

    @router.get("/admin", response_class=HTMLResponse)
    @router.get("/admin/", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        from .queries import get_alertas_dashboard

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        alertas = get_alertas_dashboard(engine)
        return _render(request, "admin/dashboard.html", alertas=alertas)

    @router.get("/admin/cadastros", response_class=HTMLResponse)
    async def admin_cadastros(request: Request):
        gestor = _exige_gestor(request, "plantao_aprovar_cadastros")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        # Usar platform users (auth unificada) filtrados por role de plantonista
        from pb_platform.storage import EXTERNAL_ROLES
        all_users = store.list_users()
        externos = [u for u in all_users if u.get("role") in EXTERNAL_ROLES]
        pendentes = [u for u in externos if u.get("status") == "pendente"]
        ativos = [u for u in externos if u.get("status") == "ativo"]
        inativos_rejeitados = [u for u in externos if u.get("status") in ("inativo", "rejeitado")]
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "admin/cadastros.html",
            pendentes=pendentes,
            ativos=ativos,
            inativos_rejeitados=inativos_rejeitados,
            csrf_token=csrf,
        )

    @router.post("/admin/cadastros/{perfil_id}/aprovar")
    async def admin_aprovar_cadastro(request: Request, perfil_id: int):
        from .actions import aprovar_plantonista

        gestor = _exige_gestor(request, "plantao_aprovar_cadastros")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            aprovar_plantonista(engine, perfil_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.post("/admin/cadastros/{perfil_id}/rejeitar")
    async def admin_rejeitar_cadastro(request: Request, perfil_id: int, motivo: str = Form("")):
        from .actions import rejeitar_plantonista

        gestor = _exige_gestor(request, "plantao_aprovar_cadastros")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            rejeitar_plantonista(
                engine, perfil_id, gestor["id"], motivo=motivo, ip=request.client.host if request.client else ""
            )
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.post("/admin/cadastros/{perfil_id}/desativar")
    async def admin_desativar(request: Request, perfil_id: int):
        from .actions import desativar_plantonista

        gestor = _exige_gestor(request, "plantao_aprovar_cadastros")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            desativar_plantonista(engine, perfil_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.post("/admin/cadastros/{perfil_id}/reativar")
    async def admin_reativar(request: Request, perfil_id: int):
        from .actions import reativar_plantonista

        gestor = _exige_gestor(request, "plantao_aprovar_cadastros")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            reativar_plantonista(engine, perfil_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.get("/admin/escalas", response_class=HTMLResponse)
    async def admin_escalas_redirect(request: Request, mes: int = 0, ano: int = 0, local_id: int = 0):
        parts = []
        if ano:
            parts.append(f"ano={ano}")
        if mes:
            parts.append(f"mes={mes}")
        if local_id:
            parts.append(f"local_id={local_id}")
        qs = "?" + "&".join(parts) if parts else ""
        return RedirectResponse(f"/plantao/escalas{qs}", status_code=301)

    @router.post("/admin/escalas/criar")
    async def admin_criar_data(request: Request):
        from .actions import criar_data_plantao

        gestor = _exige_gestor(request, "plantao_gerir_escalas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)

        form = await request.form()
        try:
            local_id = int(form.get("local_id", 0))
            tipo = str(form.get("tipo", "presencial"))
            data_ref = str(form.get("data", ""))
            hora_inicio = str(form.get("hora_inicio", "08:00"))
            hora_fim = str(form.get("hora_fim", "20:00"))
            observacoes = str(form.get("observacoes", ""))
            vet_vagas = int(form.get("vagas_veterinario", 1) or 0)
            aux_vagas = int(form.get("vagas_auxiliar", 1) or 0)
            posicoes: list[dict] = []
            if tipo == "presencial":
                if vet_vagas > 0:
                    posicoes.append({"tipo": "veterinario", "vagas": vet_vagas})
                if aux_vagas > 0:
                    posicoes.append({"tipo": "auxiliar", "vagas": aux_vagas})
            auto_approve = form.get("auto_approve") in ("1", "on", "true")
            criar_data_plantao(
                engine,
                local_id=local_id,
                tipo=tipo,
                data=data_ref,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                posicoes=posicoes,
                gestor_id=gestor["id"],
                observacoes=observacoes,
                ip=request.client.host if request.client else "",
                auto_approve=auto_approve,
            )
        except Exception as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/criar-lote")
    async def admin_criar_lote(request: Request):
        from .actions import criar_lote_plantao

        gestor = _exige_gestor(request, "plantao_gerir_escalas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)

        form = await request.form()
        try:
            local_id = int(form.get("local_id", 0))
            tipo = str(form.get("tipo", "presencial"))
            data_inicio = str(form.get("data_inicio", ""))
            data_fim = str(form.get("data_fim", ""))
            hora_inicio = str(form.get("hora_inicio", "08:00"))
            hora_fim = str(form.get("hora_fim", "20:00"))
            vet_vagas = int(form.get("vagas_veterinario", 1) or 0)
            aux_vagas = int(form.get("vagas_auxiliar", 0) or 0)
            observacoes = str(form.get("observacoes", ""))
            auto_approve = form.get("auto_approve") in ("1", "on", "true")
            # dias_semana: "0" a "6" (0=seg, 6=dom)
            dias_semana = [int(d) for d in form.getlist("dias_semana") if d.isdigit()]
            resultado = criar_lote_plantao(
                engine,
                local_id=local_id,
                tipo=tipo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                dias_semana=dias_semana,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                vagas_veterinario=vet_vagas,
                vagas_auxiliar=aux_vagas,
                gestor_id=gestor["id"],
                auto_approve=auto_approve,
                observacoes=observacoes,
                ip=request.client.host if request.client else "",
            )
            total = resultado["total"]
        except Exception as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse(f"/plantao/admin/escalas?ok={total}_criadas", status_code=303)

    @router.post("/admin/escalas/{data_id}/publicar")
    async def admin_publicar_data(request: Request, data_id: int):
        from .actions import publicar_data_plantao

        gestor = _exige_gestor(request, "plantao_gerir_escalas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            publicar_data_plantao(engine, data_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/{data_id}/cancelar")
    async def admin_cancelar_data(request: Request, data_id: int):
        from .actions import cancelar_data_plantao

        gestor = _exige_gestor(request, "plantao_gerir_escalas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            cancelar_data_plantao(engine, data_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/gerar-mensal")
    async def admin_gerar_mensal(
        request: Request,
        local_id: int = Form(...),
        ano: int = Form(...),
        mes: int = Form(...),
    ):
        from .actions import gerar_escala_mensal

        gestor = _exige_gestor(request, "plantao_gerir_escalas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            gerar_escala_mensal(engine, local_id, ano, mes, gestor["id"])
        except ValueError as exc:
            return _redir_erro("/plantao/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    # ── Fila unificada de aprovações ──────────────────────────────────────────

    @router.get("/admin/aprovacoes", response_class=HTMLResponse)
    async def admin_aprovacoes(request: Request, historico: str = ""):
        from .queries import listar_candidaturas_pendentes, listar_candidaturas_por_data

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        pendentes = listar_candidaturas_pendentes(engine, apenas_futuras=True)
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "admin/aprovacoes.html",
            pendentes=pendentes,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/aprovacoes/lote")
    async def admin_aprovacoes_lote(request: Request):
        from .actions import confirmar_candidatura, recusar_candidatura

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        form = await request.form()
        ids_raw = form.getlist("candidatura_id")
        acao = str(form.get("acao", "confirmar"))
        motivo = str(form.get("motivo", ""))
        confirmadas = 0
        ip = request.client.host if request.client else ""
        for id_str in ids_raw:
            try:
                cid = int(id_str)
                if acao == "recusar":
                    recusar_candidatura(engine, cid, gestor["id"], motivo=motivo, ip=ip)
                else:
                    confirmar_candidatura(engine, cid, gestor["id"], ip=ip)
                confirmadas += 1
            except Exception:
                pass
        return RedirectResponse(f"/plantao/admin/aprovacoes?ok={confirmadas}", status_code=303)

    @router.post("/admin/aprovacoes/confirmar/{candidatura_id}")
    async def admin_aprovacoes_confirmar(request: Request, candidatura_id: int):
        """Ação rápida de aprovação individual na fila de aprovações."""
        from .actions import confirmar_candidatura

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            confirmar_candidatura(engine, candidatura_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/aprovacoes", str(exc))
        return RedirectResponse("/plantao/admin/aprovacoes?ok=1", status_code=303)

    @router.post("/admin/aprovacoes/recusar/{candidatura_id}")
    async def admin_aprovacoes_recusar(request: Request, candidatura_id: int, motivo: str = Form("")):
        """Ação rápida de recusa individual na fila de aprovações."""
        from .actions import recusar_candidatura

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            recusar_candidatura(engine, candidatura_id, gestor["id"], motivo=motivo, ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/aprovacoes", str(exc))
        return RedirectResponse("/plantao/admin/aprovacoes", status_code=303)

    @router.get("/partials/badge-pendentes", response_class=HTMLResponse)
    async def badge_pendentes(request: Request):
        from .queries import contar_candidaturas_pendentes
        n = contar_candidaturas_pendentes(engine)
        if n > 0:
            return HTMLResponse(
                f'<span class="ml-auto rounded-full bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{n}</span>'
            )
        return HTMLResponse("")

    @router.get("/admin/candidaturas", response_class=HTMLResponse)
    async def admin_candidaturas(request: Request, data_id: int = 0):
        from .queries import listar_candidaturas_por_data, listar_datas_por_mes

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        now = datetime.utcnow()
        datas = listar_datas_por_mes(engine, now.year, now.month, status="publicado")
        candidaturas = listar_candidaturas_por_data(engine, data_id) if data_id else []
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "admin/candidaturas.html",
            data_id=data_id,
            datas=datas,
            candidaturas=candidaturas,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/candidaturas/{candidatura_id}/confirmar")
    async def admin_confirmar_candidatura(request: Request, candidatura_id: int):
        from .actions import confirmar_candidatura

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            confirmar_candidatura(engine, candidatura_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/candidaturas", str(exc))
        return RedirectResponse("/plantao/admin/candidaturas?ok=1", status_code=303)

    @router.post("/admin/candidaturas/{candidatura_id}/recusar")
    async def admin_recusar_candidatura(request: Request, candidatura_id: int, motivo: str = Form("")):
        from .actions import recusar_candidatura

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            recusar_candidatura(
                engine,
                candidatura_id,
                gestor["id"],
                motivo=motivo,
                ip=request.client.host if request.client else "",
            )
        except ValueError as exc:
            return _redir_erro("/plantao/admin/candidaturas", str(exc))
        return RedirectResponse("/plantao/admin/candidaturas?ok=1", status_code=303)

    @router.get("/admin/sobreaviso", response_class=HTMLResponse)
    async def admin_sobreaviso_compat_redirect(request: Request):
        qs = str(request.url.query)
        target = "/plantao/admin/disponibilidade" + (f"?{qs}" if qs else "")
        return RedirectResponse(target, status_code=302)

    @router.get("/admin/disponibilidade", response_class=HTMLResponse)
    async def admin_disponibilidade(request: Request, data_id: int = 0):
        from .queries import listar_datas_por_mes, listar_disponibilidade_por_data

        gestor = _exige_gestor(request, "plantao_aprovar_candidaturas")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        now = datetime.utcnow()
        datas = listar_datas_por_mes(engine, now.year, now.month, tipo="disponibilidade", status="publicado")
        adesoes = listar_disponibilidade_por_data(engine, data_id) if data_id else []
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "admin/disponibilidade.html",
            data_id=data_id,
            datas=datas,
            adesoes=adesoes,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/disponibilidade/{data_id}/reordenar")
    async def admin_reordenar_disponibilidade(request: Request, data_id: int):
        from .actions import reordenar_disponibilidade

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        form = await request.form()
        nova_ordem_raw = str(form.get("nova_ordem", "")).strip()
        try:
            nova_ordem = [int(x) for x in nova_ordem_raw.split(",") if x.strip()]
            reordenar_disponibilidade(
                engine,
                data_id,
                nova_ordem,
                gestor["id"],
                ip=request.client.host if request.client else "",
            )
        except Exception as exc:
            return _redir_erro(f"/plantao/admin/disponibilidade?data_id={data_id}", str(exc))
        return RedirectResponse(f"/plantao/admin/disponibilidade?data_id={data_id}&ok=1", status_code=303)

    @router.get("/admin/relatorios", response_class=HTMLResponse)
    async def admin_relatorios(request: Request):
        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        return _render(request, "admin/relatorios.html")

    @router.get("/admin/relatorios/escalas", response_class=HTMLResponse)
    async def relatorio_escalas(request: Request, data_inicio: str = "", data_fim: str = "", local_id: int = 0):
        from .queries import relatorio_escalas_por_periodo

        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        if not data_inicio or not data_fim:
            hoje = datetime.utcnow().date()
            data_inicio = data_inicio or hoje.replace(day=1).isoformat()
            data_fim = data_fim or hoje.isoformat()
        dados = relatorio_escalas_por_periodo(engine, data_inicio, data_fim, local_id or None)
        return _render(request, "admin/relatorios_escalas.html", data_inicio=data_inicio, data_fim=data_fim, local_id=local_id, dados=dados)

    @router.get("/admin/relatorios/participacao", response_class=HTMLResponse)
    async def relatorio_participacao(request: Request, data_inicio: str = "", data_fim: str = ""):
        from .queries import relatorio_participacao_por_plantonista

        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        if not data_inicio or not data_fim:
            hoje = datetime.utcnow().date()
            data_inicio = data_inicio or hoje.replace(day=1).isoformat()
            data_fim = data_fim or hoje.isoformat()
        dados = relatorio_participacao_por_plantonista(engine, data_inicio, data_fim)
        return _render(request, "admin/relatorios_participacao.html", data_inicio=data_inicio, data_fim=data_fim, dados=dados)

    @router.get("/admin/relatorios/cancelamentos", response_class=HTMLResponse)
    async def relatorio_cancelamentos(request: Request, data_inicio: str = "", data_fim: str = ""):
        from .queries import relatorio_cancelamentos_trocas

        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        if not data_inicio or not data_fim:
            hoje = datetime.utcnow().date()
            data_inicio = data_inicio or hoje.replace(day=1).isoformat()
            data_fim = data_fim or hoje.isoformat()
        dados = relatorio_cancelamentos_trocas(engine, data_inicio, data_fim)
        return _render(request, "admin/relatorios_cancelamentos.html", data_inicio=data_inicio, data_fim=data_fim, dados=dados)

    @router.get("/admin/relatorios/pre-fechamento", response_class=HTMLResponse)
    async def relatorio_pre_fechamento(request: Request, data_inicio: str = "", data_fim: str = "", local_id: int = 0):
        from .queries import listar_datas_por_mes, relatorio_pre_fechamento

        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        if not data_inicio or not data_fim:
            hoje = datetime.utcnow().date()
            data_inicio = data_inicio or hoje.replace(day=1).isoformat()
            data_fim = data_fim or hoje.isoformat()
        dados = relatorio_pre_fechamento(engine, data_inicio, data_fim, local_id or None)
        now = datetime.utcnow()
        disponibilidades = listar_datas_por_mes(engine, now.year, now.month, local_id or None, tipo="disponibilidade")
        return _render(
            request,
            "admin/relatorios_pre_fechamento.html",
            data_inicio=data_inicio,
            data_fim=data_fim,
            local_id=local_id,
            dados=dados,
            disponibilidades=disponibilidades,
        )

    @router.get("/admin/locais", response_class=HTMLResponse)
    async def admin_locais(request: Request):
        from .queries import listar_locais

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        locais = listar_locais(engine, apenas_ativos=False)
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "admin/locais.html", locais=locais, csrf_token=csrf, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/locais/criar")
    async def admin_criar_local(
        request: Request,
        nome: str = Form(...),
        endereco: str = Form(""),
        cidade: str = Form(""),
        uf: str = Form(""),
        telefone: str = Form(""),
    ):
        from .actions import criar_local

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            criar_local(engine, nome, endereco, cidade, uf, telefone, gestor["id"])
        except ValueError as exc:
            return _redir_erro("/plantao/admin/locais", str(exc))
        return RedirectResponse("/plantao/admin/locais?ok=1", status_code=303)

    @router.get("/admin/tarifas", response_class=HTMLResponse)
    async def admin_tarifas(request: Request):
        from .queries import listar_tarifas_vigentes

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        tarifas = listar_tarifas_vigentes(engine, datetime.utcnow().date().isoformat())
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "admin/tarifas.html", tarifas=tarifas, csrf_token=csrf, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/tarifas/criar")
    async def admin_criar_tarifa(request: Request):
        from .actions import criar_tarifa

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        import json as _json
        form = await request.form()
        tipo_perfil = str(form.get("tipo_perfil", ""))
        valor_hora = float(form.get("valor_hora", "0") or 0)
        feriado_val = int(form["feriado"]) if form.get("feriado") not in (None, "") else None
        vigente_de = str(form.get("vigente_de", "2000-01-01"))
        vigente_ate = str(form.get("vigente_ate")) if form.get("vigente_ate") else None

        # Suporte a batch (múltiplos dias via _dias_json) ou dia único
        dias_json = form.get("_dias_json", "")
        if dias_json:
            try:
                dias = _json.loads(dias_json)
            except Exception:
                dias = []
        else:
            dias = []

        if form.get("dia_semana") not in (None, ""):
            dias = [int(form["dia_semana"])]

        if not dias:
            dias = [None]  # qualquer dia

        try:
            for dia in dias:
                criar_tarifa(
                    engine,
                    tipo_perfil=tipo_perfil,
                    valor_hora=valor_hora,
                    gestor_id=gestor["id"],
                    dia_semana=dia,
                    feriado=feriado_val,
                    vigente_de=vigente_de,
                    vigente_ate=vigente_ate,
                )
        except Exception as exc:
            return _redir_erro("/plantao/admin/tarifas", str(exc))
        return RedirectResponse("/plantao/admin/tarifas?ok=1", status_code=303)

    @router.post("/admin/tarifas/{tarifa_id}/editar")
    async def admin_editar_tarifa(request: Request, tarifa_id: int):
        from .actions import editar_tarifa

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        form = await request.form()
        try:
            editar_tarifa(
                engine,
                tarifa_id=tarifa_id,
                gestor_id=gestor["id"],
                tipo_perfil=str(form["tipo_perfil"]) if form.get("tipo_perfil") else None,
                dia_semana=int(form["dia_semana"]) if form.get("dia_semana") not in (None, "") else None,
                feriado=int(form["feriado"]) if form.get("feriado") not in (None, "") else None,
                valor_hora=float(form["valor_hora"]) if form.get("valor_hora") else None,
                vigente_de=str(form["vigente_de"]) if form.get("vigente_de") else None,
                vigente_ate=str(form["vigente_ate"]) if form.get("vigente_ate") else None,
            )
        except Exception as exc:
            return _redir_erro("/plantao/admin/tarifas", str(exc))
        return RedirectResponse("/plantao/admin/tarifas?ok=1", status_code=303)

    @router.post("/admin/tarifas/{tarifa_id}/excluir")
    async def admin_excluir_tarifa(request: Request, tarifa_id: int):
        from .actions import excluir_tarifa

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        ip = request.client.host if request.client else ""
        try:
            excluir_tarifa(engine, tarifa_id=tarifa_id, gestor_id=gestor["id"], ip=ip)
        except Exception as exc:
            return _redir_erro("/plantao/admin/tarifas", str(exc))
        return RedirectResponse("/plantao/admin/tarifas?ok=1", status_code=303)

    @router.get("/admin/feriados", response_class=HTMLResponse)
    async def admin_feriados(request: Request):
        from datetime import timedelta

        from .queries import listar_feriados_por_periodo

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        hoje = datetime.utcnow().date()
        fim = hoje + timedelta(days=365)
        feriados = listar_feriados_por_periodo(engine, hoje.isoformat(), fim.isoformat())
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "admin/feriados.html", feriados=feriados, csrf_token=csrf, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/feriados/criar")
    async def admin_criar_feriado(
        request: Request,
        data: str = Form(...),
        nome: str = Form(...),
        tipo: str = Form(...),
        local_id: str = Form(""),
    ):
        from .actions import criar_feriado

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        try:
            criar_feriado(engine, data, nome, tipo, int(local_id) if local_id else None, gestor["id"])
        except Exception as exc:
            return _redir_erro("/plantao/admin/feriados", str(exc))
        return RedirectResponse("/plantao/admin/feriados?ok=1", status_code=303)

    @router.get("/admin/configuracoes", response_class=HTMLResponse)
    async def admin_configuracoes(request: Request):
        from .actions import get_configuracao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        chaves = [
            "plantao_prazo_cancelamento_horas_uteis",
            "plantao_max_candidaturas_provisorias_por_vaga",
            "plantao_notif_disponibilidade_dias_antecedencia",
            "plantao_permitir_troca_sem_aprovacao_gestor",
            "plantao_api_key",
        ]
        cfg = {k: get_configuracao(engine, k, "") for k in chaves}
        csrf = getattr(request.state, "csrf_token", "")
        return _render(request, "admin/configuracoes.html", configuracoes=cfg, csrf_token=csrf, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/configuracoes/salvar")
    async def admin_salvar_configuracoes(request: Request):
        from .actions import salvar_configuracao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        await _validar_csrf_ou_403(request)
        form = await request.form()
        try:
            for chave in (
                "plantao_prazo_cancelamento_horas_uteis",
                "plantao_max_candidaturas_provisorias_por_vaga",
                "plantao_notif_disponibilidade_dias_antecedencia",
                "plantao_permitir_troca_sem_aprovacao_gestor",
                "plantao_api_key",
            ):
                if chave in form:
                    salvar_configuracao(engine, chave, str(form.get(chave, "")), gestor["id"])
        except Exception as exc:
            return _redir_erro("/plantao/admin/configuracoes", str(exc))
        return RedirectResponse("/plantao/admin/configuracoes?ok=1", status_code=303)

    @router.get("/admin/audit-log", response_class=HTMLResponse)
    async def admin_audit_log(
        request: Request,
        perfil_id: int = 0,
        entidade: str = "",
        data_inicio: str = "",
        data_fim: str = "",
        page: int = 1,
    ):
        gestor = _exige_gestor(request, "plantao_ver_relatorios")
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        page = max(page, 1)
        limit = 50
        offset = (page - 1) * limit
        where = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if perfil_id:
            where.append("ator_tipo='perfil' AND ator_id=:perfil_id")
            params["perfil_id"] = perfil_id
        if entidade:
            where.append("entidade=:entidade")
            params["entidade"] = entidade
        if data_inicio:
            where.append("criado_em >= :data_inicio")
            params["data_inicio"] = f"{data_inicio}T00:00:00"
        if data_fim:
            where.append("criado_em <= :data_fim")
            params["data_fim"] = f"{data_fim}T23:59:59"
        where_sql = " AND ".join(where)
        with engine.connect() as conn:
            logs = conn.execute(
                text(
                    f"SELECT * FROM plantao_audit_log WHERE {where_sql} "
                    "ORDER BY criado_em DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().all()
        return _render(
            request,
            "admin/audit_log.html",
            logs=[dict(r) for r in logs],
            filtros={"perfil_id": perfil_id, "entidade": entidade, "data_inicio": data_inicio, "data_fim": data_fim},
            page=page,
        )

    @router.get("/api/fechamento", response_class=JSONResponse)
    async def api_fechamento(
        request: Request,
        data_inicio: str,
        data_fim: str,
        local_id: int = 0,
    ):
        from .queries import get_fechamento_api

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return JSONResponse({"erro": "Nao autorizado."}, status_code=403)
        dados = get_fechamento_api(engine, data_inicio, data_fim, local_id or None)
        return JSONResponse({"data_inicio": data_inicio, "data_fim": data_fim, "turnos": dados})

    @router.get("/api/sobreaviso-ativo", response_class=JSONResponse)
    async def api_sobreaviso_ativo_compat(request: Request, data: str = "", hora: str = "", local_id: int = 0):
        return RedirectResponse(
            f"/plantao/api/disponibilidade-ativa?data={data}&hora={hora}&local_id={local_id}",
            status_code=301,
        )

    @router.get("/api/disponibilidade-ativa", response_class=JSONResponse)
    async def api_disponibilidade_ativa(
        request: Request,
        data: str,
        hora: str,
        local_id: int = 0,
    ):
        from .actions import get_configuracao
        from .queries import get_disponibilidade_ativa

        api_key = request.headers.get("X-Plantao-API-Key", "").strip()
        esperado = get_configuracao(engine, "plantao_api_key", "").strip()
        if not esperado or api_key != esperado:
            return JSONResponse({"erro": "API key invalida."}, status_code=403)
        lista = get_disponibilidade_ativa(engine, data, hora, local_id or None)
        return JSONResponse({"data": data, "hora": hora, "disponibilidade": lista})

    return router


def _render(request: Request, template: str, **ctx):
    platform_user = getattr(request.state, "user", None)
    return _templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "platform_name": settings.app_name,
            "platform_user": platform_user,
            "platform_permissions": store.get_user_permissions(platform_user) if platform_user else {},
            "module_name": ctx.pop("module_name", "Plantão"),
            "is_dev": settings.is_dev,
            **ctx,
        },
    )


async def _validar_csrf_ou_403(request: Request) -> None:
    from fastapi import HTTPException
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    if not await validar_csrf(request, raw_token):
        raise HTTPException(status_code=403, detail="Token CSRF invalido.")
