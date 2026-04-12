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
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from pb_platform.auth import (
    attach_user_to_request,
    gerar_csrf_token,
    has_permission,
    validar_csrf,
)
from pb_platform.settings import settings
from .notifications import (
    contar_nao_lidas,
    listar_notificacoes,
    marcar_lida,
    marcar_todas_lidas,
)

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
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
        if not has_permission(request, "plantao_access"):
            return RedirectResponse("/login?erro=sem_permissao", status_code=303)
        # Popula state para compatibilidade com templates que usam 'perfil'
        request.state.plantonista = user
        raw_token = request.cookies.get(settings.session_cookie_name, "")
        request.state.csrf_token = gerar_csrf_token(raw_token)
        return user

    def _exige_gestor(request: Request):
        """
        Valida que há um usuário da plataforma logado com permissão manage_plantao.
        Popula request.state.gestor.
        Retorna o user dict ou uma RedirectResponse.
        """
        user = attach_user_to_request(request)
        if not user:
            return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
        if not has_permission(request, "manage_plantao"):
            return HTMLResponse("<h1>403 — Acesso restrito a gestores de plantão.</h1>", status_code=403)
        request.state.gestor = user
        request.state.user = user
        raw_token = request.cookies.get(settings.session_cookie_name, "")
        request.state.csrf_token = gerar_csrf_token(raw_token)
        return user

    # ── Redirects de compatibilidade (rotas de auth antigas) ─────────────────

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    async def landing(request: Request):
        user = attach_user_to_request(request)
        if user and has_permission(request, "plantao_access"):
            return RedirectResponse("/plantao/escalas", status_code=303)
        return RedirectResponse("/login", status_code=303)

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

    @router.get("/escalas", response_class=HTMLResponse)
    async def escalas_page(request: Request, mes: int = 0, ano: int = 0, local_id: int = 0):
        from .queries import listar_datas_com_vagas_abertas, listar_datas_por_mes, listar_locais

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil

        now = datetime.utcnow()
        ano = ano or now.year
        mes = mes or now.month
        local_sel = local_id or None
        datas_mes = listar_datas_por_mes(engine, ano, mes, local_sel, status="publicado")
        vagas_abertas = listar_datas_com_vagas_abertas(engine, local_sel, perfil["tipo"])
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_escalas.html",
            perfil=perfil,
            locais=listar_locais(engine),
            mes=mes,
            ano=ano,
            local_id=local_id,
            datas_mes=datas_mes,
            vagas_abertas=vagas_abertas,
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

    @router.get("/meus-turnos", response_class=HTMLResponse)
    async def meus_turnos_page(request: Request):
        from .queries import listar_candidaturas_por_perfil

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        candidaturas = listar_candidaturas_por_perfil(engine, perfil["id"])
        grupos = {
            "confirmado": [c for c in candidaturas if c["status"] == "confirmado"],
            "provisorio": [c for c in candidaturas if c["status"] == "provisorio"],
            "lista_espera": [c for c in candidaturas if c["status"] == "lista_espera"],
            "cancelado": [c for c in candidaturas if c["status"] == "cancelado"],
            "recusado": [c for c in candidaturas if c["status"] == "recusado"],
        }
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_meus_turnos.html",
            perfil=perfil,
            candidaturas=candidaturas,
            grupos=grupos,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

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

    @router.get("/trocas", response_class=HTMLResponse)
    async def trocas_page(request: Request):
        from .queries import listar_substituicoes_abertas, listar_trocas_por_perfil

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        trocas = listar_trocas_por_perfil(engine, perfil["id"])
        substituicoes_abertas = listar_substituicoes_abertas(engine, perfil["tipo"])
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_trocas.html",
            perfil=perfil,
            trocas=trocas,
            substituicoes_abertas=substituicoes_abertas,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

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

    @router.get("/sobreaviso", response_class=HTMLResponse)
    async def sobreaviso_page(request: Request):
        from .queries import listar_datas_por_mes, listar_sobreaviso_por_perfil

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        now = datetime.utcnow()
        minhas_adesoes = listar_sobreaviso_por_perfil(engine, perfil["id"])
        sobreavisos_abertos = listar_datas_por_mes(
            engine,
            now.year,
            now.month,
            tipo="sobreaviso",
            status="publicado",
        )
        csrf = getattr(request.state, "csrf_token", "")
        return _render(
            request,
            "plantao_sobreaviso.html",
            perfil=perfil,
            minhas_adesoes=minhas_adesoes,
            sobreavisos_abertos=sobreavisos_abertos,
            csrf_token=csrf,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/sobreaviso/{data_id}/aderir")
    async def aderir_sobreaviso_action(request: Request, data_id: int):
        from .actions import aderir_sobreaviso

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            aderir_sobreaviso(engine, data_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/sobreaviso", str(exc))
        return RedirectResponse("/plantao/sobreaviso?ok=1", status_code=303)

    @router.post("/sobreaviso/{adesao_id}/cancelar")
    async def cancelar_sobreaviso_action(request: Request, adesao_id: int):
        from .actions import cancelar_sobreaviso

        perfil = _exige_plantonista(request)
        if isinstance(perfil, RedirectResponse):
            return perfil
        await _validar_csrf_ou_403(request)
        try:
            cancelar_sobreaviso(engine, adesao_id, perfil["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/sobreaviso", str(exc))
        return RedirectResponse("/plantao/sobreaviso?ok=1", status_code=303)

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
        from .queries import listar_perfis

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        pendentes = listar_perfis(engine, status="pendente")
        ativos = listar_perfis(engine, status="ativo")
        inativos = listar_perfis(engine, status="inativo")
        rejeitados = listar_perfis(engine, status="rejeitado")
        return _render(
            request,
            "admin/cadastros.html",
            pendentes=pendentes,
            ativos=ativos,
            inativos=inativos,
            rejeitados=rejeitados,
        )

    @router.post("/admin/cadastros/{perfil_id}/aprovar")
    async def admin_aprovar_cadastro(request: Request, perfil_id: int):
        from .actions import aprovar_plantonista

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            aprovar_plantonista(engine, perfil_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.post("/admin/cadastros/{perfil_id}/rejeitar")
    async def admin_rejeitar_cadastro(request: Request, perfil_id: int, motivo: str = Form("")):
        from .actions import rejeitar_plantonista

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
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

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            desativar_plantonista(engine, perfil_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/cadastros", str(exc))
        return RedirectResponse("/plantao/admin/cadastros", status_code=303)

    @router.get("/admin/escalas", response_class=HTMLResponse)
    async def admin_escalas(request: Request, mes: int = 0, ano: int = 0, local_id: int = 0):
        from .queries import listar_datas_por_mes, listar_locais

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        now = datetime.utcnow()
        ano = ano or now.year
        mes = mes or now.month
        local_sel = local_id or None
        datas = listar_datas_por_mes(engine, ano, mes, local_sel)
        locais = listar_locais(engine)
        return _render(
            request,
            "admin/escalas.html",
            mes=mes,
            ano=ano,
            local_id=local_id,
            locais=locais,
            datas=datas,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/escalas/criar")
    async def admin_criar_data(request: Request):
        from .actions import criar_data_plantao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor

        form = await request.form()
        try:
            local_id = int(form.get("local_id", 0))
            tipo = str(form.get("tipo", "presencial"))
            subtipo = str(form.get("subtipo", "regular"))
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
            criar_data_plantao(
                engine,
                local_id=local_id,
                tipo=tipo,
                subtipo=subtipo,
                data=data_ref,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                posicoes=posicoes,
                gestor_id=gestor["id"],
                observacoes=observacoes,
                ip=request.client.host if request.client else "",
            )
        except Exception as exc:
            return _redir_erro("/plantao/admin/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/{data_id}/publicar")
    async def admin_publicar_data(request: Request, data_id: int):
        from .actions import publicar_data_plantao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            publicar_data_plantao(engine, data_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/{data_id}/cancelar")
    async def admin_cancelar_data(request: Request, data_id: int):
        from .actions import cancelar_data_plantao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            cancelar_data_plantao(engine, data_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.post("/admin/escalas/gerar-mensal")
    async def admin_gerar_mensal(
        request: Request,
        local_id: int = Form(...),
        ano: int = Form(...),
        mes: int = Form(...),
    ):
        from .actions import gerar_escala_mensal

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            gerar_escala_mensal(engine, local_id, ano, mes, gestor["id"])
        except ValueError as exc:
            return _redir_erro("/plantao/admin/escalas", str(exc))
        return RedirectResponse("/plantao/admin/escalas?ok=1", status_code=303)

    @router.get("/admin/candidaturas", response_class=HTMLResponse)
    async def admin_candidaturas(request: Request, data_id: int = 0):
        from .queries import listar_candidaturas_por_data, listar_datas_por_mes

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        now = datetime.utcnow()
        datas = listar_datas_por_mes(engine, now.year, now.month, status="publicado")
        candidaturas = listar_candidaturas_por_data(engine, data_id) if data_id else []
        return _render(
            request,
            "admin/candidaturas.html",
            data_id=data_id,
            datas=datas,
            candidaturas=candidaturas,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/candidaturas/{candidatura_id}/confirmar")
    async def admin_confirmar_candidatura(request: Request, candidatura_id: int):
        from .actions import confirmar_candidatura

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        try:
            confirmar_candidatura(engine, candidatura_id, gestor["id"], ip=request.client.host if request.client else "")
        except ValueError as exc:
            return _redir_erro("/plantao/admin/candidaturas", str(exc))
        return RedirectResponse("/plantao/admin/candidaturas?ok=1", status_code=303)

    @router.post("/admin/candidaturas/{candidatura_id}/recusar")
    async def admin_recusar_candidatura(request: Request, candidatura_id: int, motivo: str = Form("")):
        from .actions import recusar_candidatura

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
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
    async def admin_sobreaviso(request: Request, data_id: int = 0):
        from .queries import listar_datas_por_mes, listar_sobreaviso_por_data

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        now = datetime.utcnow()
        datas = listar_datas_por_mes(engine, now.year, now.month, tipo="sobreaviso", status="publicado")
        adesoes = listar_sobreaviso_por_data(engine, data_id) if data_id else []
        return _render(
            request,
            "admin/sobreaviso.html",
            data_id=data_id,
            datas=datas,
            adesoes=adesoes,
            erro=request.query_params.get("erro", ""),
            ok=request.query_params.get("ok", ""),
        )

    @router.post("/admin/sobreaviso/{data_id}/reordenar")
    async def admin_reordenar_sobreaviso(request: Request, data_id: int):
        from .actions import reordenar_sobreaviso

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        form = await request.form()
        nova_ordem_raw = str(form.get("nova_ordem", "")).strip()
        try:
            nova_ordem = [int(x) for x in nova_ordem_raw.split(",") if x.strip()]
            reordenar_sobreaviso(
                engine,
                data_id,
                nova_ordem,
                gestor["id"],
                ip=request.client.host if request.client else "",
            )
        except Exception as exc:
            return _redir_erro(f"/plantao/admin/sobreaviso?data_id={data_id}", str(exc))
        return RedirectResponse(f"/plantao/admin/sobreaviso?data_id={data_id}&ok=1", status_code=303)

    @router.get("/admin/relatorios", response_class=HTMLResponse)
    async def admin_relatorios(request: Request):
        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        return _render(request, "admin/relatorios.html")

    @router.get("/admin/relatorios/escalas", response_class=HTMLResponse)
    async def relatorio_escalas(request: Request, data_inicio: str = "", data_fim: str = "", local_id: int = 0):
        from .queries import relatorio_escalas_por_periodo

        gestor = _exige_gestor(request)
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

        gestor = _exige_gestor(request)
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

        gestor = _exige_gestor(request)
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

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        if not data_inicio or not data_fim:
            hoje = datetime.utcnow().date()
            data_inicio = data_inicio or hoje.replace(day=1).isoformat()
            data_fim = data_fim or hoje.isoformat()
        dados = relatorio_pre_fechamento(engine, data_inicio, data_fim, local_id or None)
        now = datetime.utcnow()
        sobreavisos = listar_datas_por_mes(engine, now.year, now.month, local_id or None, tipo="sobreaviso")
        return _render(
            request,
            "admin/relatorios_pre_fechamento.html",
            data_inicio=data_inicio,
            data_fim=data_fim,
            local_id=local_id,
            dados=dados,
            sobreavisos=sobreavisos,
        )

    @router.get("/admin/locais", response_class=HTMLResponse)
    async def admin_locais(request: Request):
        from .queries import listar_locais

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        locais = listar_locais(engine, apenas_ativos=False)
        return _render(request, "admin/locais.html", locais=locais, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

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
        return _render(request, "admin/tarifas.html", tarifas=tarifas, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/tarifas/criar")
    async def admin_criar_tarifa(request: Request):
        from .actions import criar_tarifa

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        form = await request.form()
        try:
            criar_tarifa(
                engine,
                tipo_perfil=str(form.get("tipo_perfil", "")),
                valor_hora=float(form.get("valor_hora", "0") or 0),
                gestor_id=gestor["id"],
                dia_semana=int(form["dia_semana"]) if form.get("dia_semana") not in (None, "") else None,
                subtipo_turno=str(form.get("subtipo_turno")) if form.get("subtipo_turno") else None,
                vigente_de=str(form.get("vigente_de", "2000-01-01")),
                vigente_ate=str(form.get("vigente_ate")) if form.get("vigente_ate") else None,
            )
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
        return _render(request, "admin/feriados.html", feriados=feriados, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

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
            "plantao_notif_sobreaviso_dias_antecedencia",
            "plantao_permitir_troca_sem_aprovacao_gestor",
            "plantao_api_key",
        ]
        cfg = {k: get_configuracao(engine, k, "") for k in chaves}
        return _render(request, "admin/configuracoes.html", configuracoes=cfg, erro=request.query_params.get("erro", ""), ok=request.query_params.get("ok", ""))

    @router.post("/admin/configuracoes/salvar")
    async def admin_salvar_configuracoes(request: Request):
        from .actions import salvar_configuracao

        gestor = _exige_gestor(request)
        if isinstance(gestor, RedirectResponse) or isinstance(gestor, HTMLResponse):
            return gestor
        form = await request.form()
        try:
            for chave in (
                "plantao_prazo_cancelamento_horas_uteis",
                "plantao_max_candidaturas_provisorias_por_vaga",
                "plantao_notif_sobreaviso_dias_antecedencia",
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
        gestor = _exige_gestor(request)
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
    async def api_sobreaviso_ativo(
        request: Request,
        data: str,
        hora: str,
        local_id: int = 0,
    ):
        from .actions import get_configuracao
        from .queries import get_sobreaviso_ativo

        api_key = request.headers.get("X-Plantao-API-Key", "").strip()
        esperado = get_configuracao(engine, "plantao_api_key", "").strip()
        if not esperado or api_key != esperado:
            return JSONResponse({"erro": "API key invalida."}, status_code=403)
        lista = get_sobreaviso_ativo(engine, data, hora, local_id or None)
        return JSONResponse({"data": data, "hora": hora, "sobreaviso": lista})

    return router


def _render(request: Request, template: str, **ctx):
    return _templates.TemplateResponse(request, template, {"request": request, **ctx})


async def _validar_csrf_ou_403(request: Request) -> None:
    from fastapi import HTTPException
    raw_token = request.cookies.get(settings.session_cookie_name, "")
    if not await validar_csrf(request, raw_token):
        raise HTTPException(status_code=403, detail="Token CSRF invalido.")
