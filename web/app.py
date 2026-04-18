import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core import run_historical_backfill_until_complete, run_monitor_loop
from modules.lab_monitor.notifiers.telegram_polling import register_webhook
from modules.plantao.schema import init_schema
from modules.plantao.router import make_router as make_plantao_router
from modules.plantao.jobs import run_plantao_jobs
from pb_platform.auth import (
    attach_user_to_request,
    auth_bypassed,
    default_redirect_for_user,
    forbidden_response,
    gerar_csrf_token,
    has_permission,
    path_requires_auth,
    redirect_to_login,
    required_permission,
    user_permissions,
)
from pb_platform.settings import settings
from pb_platform.storage import store
from web.card_sandbox import CARD_SANDBOX_DIR
from web.ops_map import OPS_MAP_DIR
from web.routers import auth as auth_router
from web.routers import admin as admin_router
from web.routers import platform as platform_router
from web.routers import labmonitor as labmonitor_router
from web.state import state

APP_URL = os.environ.get("APP_URL", "https://pinkblue-vet-production.up.railway.app")

plantao_engine = store.engine


@asynccontextmanager
async def lifespan(app):
    expired = store.cleanup_expired_sessions()
    users = store.list_users()
    print(f"[Startup] {len(users)} usuário(s) no banco, {expired} sessão(ões) expirada(s) removida(s)")
    if os.environ.get("MONITOR_EMBEDDED", "true").lower() not in ("false", "0", "no"):
        monitor_thread = threading.Thread(target=run_monitor_loop, args=(state,), daemon=True)
        monitor_thread.start()
    else:
        print("[Startup] MONITOR_EMBEDDED=false — monitor não iniciado (usar workers/monitor_worker.py)")
    register_webhook(APP_URL)
    init_schema(plantao_engine)
    plantao_jobs_thread = threading.Thread(
        target=run_plantao_jobs, args=(plantao_engine,), daemon=True
    )
    plantao_jobs_thread.start()
    yield


app = FastAPI(lifespan=lifespan, title="PinkBlue Vet")
app.mount("/ops-map-static", StaticFiles(directory=str(OPS_MAP_DIR)), name="ops_map_static")
app.mount("/sandboxes/cards-static", StaticFiles(directory=str(CARD_SANDBOX_DIR)), name="cards_sandbox_static")

app.include_router(make_plantao_router(plantao_engine))
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(platform_router.router)
app.include_router(labmonitor_router.router)


@app.middleware("http")
async def platform_auth_middleware(request: Request, call_next):
    if auth_bypassed(request):
        request.state.user = {"email": "tests@pinkbluevet.local", "role": "admin",
                               "nome": "Teste", "status": "ativo"}
        return await call_next(request)

    user = attach_user_to_request(request)

    session_token = request.cookies.get(settings.session_cookie_name, "")
    request.state.csrf_token = gerar_csrf_token(session_token)

    if path_requires_auth(request.url.path) and not user:
        return redirect_to_login(request)
    if user and request.url.path == "/login":
        return RedirectResponse(url=default_redirect_for_user(user), status_code=303)
    if user and request.url.path == "/cadastro":
        return RedirectResponse(url=default_redirect_for_user(user), status_code=303)
    permission = required_permission(request.url.path, request.method)
    if permission and user and not has_permission(request, permission):
        return forbidden_response(request)
    return await call_next(request)


if settings.is_dev:
    from fastapi import Form

    @app.get("/dev/switch-user")
    async def dev_list_users(request: Request):
        users = [
            {"id": u["id"], "email": u["email"], "role": u["role"], "nome": u["nome"]}
            for u in store.list_users()
            if u.get("status") == "ativo"
        ]
        return JSONResponse(users)

    @app.post("/dev/switch-user")
    async def dev_switch_user(request: Request, user_id: int = Form(...)):
        user = store.get_user_by_id(user_id)
        if not user or user.get("status") != "ativo":
            return RedirectResponse(url="/", status_code=303)
        token = store.create_session(user["id"])
        destination = default_redirect_for_user(user)
        response = RedirectResponse(url=destination, status_code=303)
        response.set_cookie(
            settings.session_cookie_name,
            token,
            httponly=True,
            samesite="lax",
            max_age=settings.session_ttl_days * 24 * 60 * 60,
        )
        return response
