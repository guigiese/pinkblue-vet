from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from pb_platform.auth import user_permissions
from pb_platform.settings import settings
from pb_platform.storage import store
from web.state import state

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STANDARD_STATUSES = ["Pronto", "Parcial", "Em Andamento", "Analisando", "Recebido", "Cancelado"]
EXAMES_PAGE_SIZE = 20


def _default_module_name(path: str) -> str:
    if path.startswith("/labmonitor"):
        return "Lab Monitor"
    if path.startswith("/plantao"):
        return "Plantão"
    return "Plataforma"


def _render(request: Request, template: str, **ctx):
    platform_user = getattr(request.state, "user", None)
    module_name = ctx.pop("module_name", _default_module_name(request.url.path))
    return templates.TemplateResponse(
        request,
        template,
        {
            "request": request,
            "platform_name": settings.app_name,
            "module_name": module_name,
            "platform_user": platform_user,
            "platform_permissions": user_permissions(platform_user) if platform_user else {},
            "is_dev": settings.is_dev,
            **ctx,
        },
    )
