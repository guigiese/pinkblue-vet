from __future__ import annotations

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse

from .settings import settings
from .storage import store


PUBLIC_PATH_PREFIXES = (
    "/login",
    "/logout",
    "/telegram/webhook/",
    "/ops-map-static/",
    "/sandboxes/cards-static/",
)


def path_requires_auth(path: str) -> bool:
    if not settings.auth_enabled:
        return False
    if path == "/favicon.ico":
        return False
    return not any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def auth_bypassed(request: Request) -> bool:
    return bool(getattr(request.app.state, "disable_auth", False))


def attach_user_to_request(request: Request) -> dict | None:
    token = request.cookies.get(settings.session_cookie_name)
    user = store.get_user_for_session(token)
    request.state.user = user
    return user


def redirect_to_login(request: Request) -> RedirectResponse:
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=f"/login?next={quote(target)}", status_code=303)


def is_admin(request: Request) -> bool:
    user = getattr(request.state, "user", None)
    return bool(user and user.get("role") == "admin")
