from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pb_platform.auth import user_permissions
from pb_platform.settings import settings
from pb_platform.storage import store
from web.card_sandbox import (
    CARD_SANDBOX_VARIANTS,
    DEFAULT_CARD_SANDBOX_VARIANT,
    get_card_sandbox_groups,
    get_card_sandbox_runtime,
    get_card_sandbox_variant,
)
from web.ops_map import get_ops_map_runtime
from web.shared import STANDARD_STATUSES, _render
from web.state import state

router = APIRouter()


@router.get("/")
async def landing(request: Request):
    platform_user = getattr(request.state, "user", None)
    if platform_user:
        perms = user_permissions(platform_user)
        has_labmonitor = perms.get("labmonitor_access") or perms.get("manage_labmonitor")
        has_plantao = perms.get("plantao_access") or perms.get("manage_plantao")
        modules_count = sum([bool(has_labmonitor), bool(has_plantao)])
        if modules_count == 1:
            if has_plantao:
                return RedirectResponse(url="/plantao/", status_code=302)
            if has_labmonitor:
                return RedirectResponse(url="/labmonitor", status_code=302)
    return _render(request, "index.html", users=store.list_users())


@router.get("/ops-map")
async def ops_map_redirect():
    return RedirectResponse(url="/ops-map/", status_code=307)


@router.get("/ops-map/")
async def ops_map_page(request: Request):
    return _render(request, "ops_map.html")


@router.get("/ops-map/data/runtime.json")
async def ops_map_runtime():
    return JSONResponse(get_ops_map_runtime())


@router.get("/sandboxes/cards")
async def cards_sandbox_redirect():
    return RedirectResponse(url="/sandboxes/cards/", status_code=307)


@router.get("/sandboxes/cards/")
async def cards_sandbox_page(
    request: Request,
    lab: str = "",
    status: str = "",
    q: str = "",
    variant: str = DEFAULT_CARD_SANDBOX_VARIANT,
):
    variant_cfg = get_card_sandbox_variant(variant)
    return _render(
        request,
        "cards_sandbox_mirror.html",
        groups=get_card_sandbox_groups(lab, status, q),
        labs_cfg=state.config["labs"],
        statuses=STANDARD_STATUSES,
        lab_filter=lab,
        status_filter=status,
        q=q,
        variants=CARD_SANDBOX_VARIANTS,
        variant_filter=variant_cfg["id"],
        variant_cfg=variant_cfg,
        default_variant_id=DEFAULT_CARD_SANDBOX_VARIANT,
    )


@router.get("/sandboxes/cards/data/runtime.json")
async def cards_sandbox_runtime():
    return JSONResponse(get_card_sandbox_runtime())


@router.get("/sandboxes/cards/partials/exames")
async def cards_sandbox_partial_exames(
    request: Request,
    lab: str = "",
    status: str = "",
    q: str = "",
    variant: str = DEFAULT_CARD_SANDBOX_VARIANT,
):
    variant_cfg = get_card_sandbox_variant(variant)
    return _render(
        request,
        "partials/cards_sandbox_table.html",
        groups=get_card_sandbox_groups(lab, status, q),
        variant_cfg=variant_cfg,
    )
