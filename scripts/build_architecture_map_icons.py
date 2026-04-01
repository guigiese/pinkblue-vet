from __future__ import annotations

import json
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    RESAMPLING_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLING_LANCZOS = Image.LANCZOS


ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "poc" / "architecture-map"
RUNTIME_PATH = MAP_DIR / "data" / "pinkblue-map.runtime.json"
RAW_DIR = MAP_DIR / "assets" / "raw"
RENDERED_DIR = MAP_DIR / "assets" / "rendered"

RAW_SOURCES = {
    "github": "https://github.com/fluidicon.png",
    "claude": "https://cdn.prod.website-files.com/67ce28cfec624e2b733f8a52/681d52619fec35886a7f1a70_favicon.png",
    "telegram": "https://telegram.org/img/apple-touch-icon.png",
    "railway": "https://railway.com/apple-touch-icon.png",
    "jira": "https://id-frontend.prod-east.frontend.public.atl-paas.net/assets/favicon.9500e2a9.ico",
    "whatsapp-callmebot": "https://www.callmebot.com/wp-content/uploads/2019/10/Logo-carita_114.png",
    "nexio": "https://www.pathoweb.com.br/assets/favicon-1e943b88d3b6a1bcc073137c8df28c67.ico",
    "bitlab": "https://bitlabenterprise.com.br/bioanalises/favicon-white.ico",
}

HEALTH_COLORS = {
    "healthy": "#18a957",
    "warning": "#db8b1f",
    "problem": "#d64541",
    "dormant": "#7f8c8d",
}

INTERNAL_ICON_SPECS = {
    "local-workspace": {"label": "WS", "bg": "#E2E8F0", "fg": "#334155"},
    "codex": {"label": "CX", "bg": "#E9F7F2", "fg": "#0C7A69"},
    "pinkblue-site": {"label": "PB", "bg": "#EEF4FF", "fg": "#1D4ED8"},
    "lab-monitor": {"label": "LM", "bg": "#ECFDF3", "fg": "#0F9D58"},
}

BUBBLE_BACKGROUNDS = {
    "bitlab": (29, 78, 216, 255),
}

CATEGORY_STYLE_BY_ID = {
    "local-workspace": {"key": "local", "color": "#475569"},
    "github": {"key": "repo", "color": "#111827"},
    "jira": {"key": "planning", "color": "#0F766E"},
    "railway": {"key": "hosting", "color": "#2563EB"},
    "telegram": {"key": "channel", "color": "#0284C7"},
    "whatsapp-callmebot": {"key": "channel", "color": "#16A34A"},
    "bitlab": {"key": "lab", "color": "#0C7A69"},
    "nexio": {"key": "lab", "color": "#7C3AED"},
}

CATEGORY_STYLE_BY_KIND = {
    "ai": {"key": "ai", "color": "#D2672D"},
    "site": {"key": "site", "color": "#2563EB"},
    "system": {"key": "system", "color": "#0C7A69"},
    "platform": {"key": "platform", "color": "#2F6FED"},
    "external": {"key": "lab", "color": "#5F6B71"},
}


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RENDERED_DIR.mkdir(parents=True, exist_ok=True)


def download_if_needed(name: str, url: str) -> Path:
    suffix = ".ico" if ".ico" in url else ".png"
    path = RAW_DIR / f"{name}{suffix}"
    if path.exists():
        return path

    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def load_raw_icon(node_id: str) -> Image.Image | None:
    url = RAW_SOURCES.get(node_id)
    if not url:
        return None
    path = download_if_needed(node_id, url)
    with Image.open(path) as image:
        return image.convert("RGBA")


def fit_logo(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    logo = image.copy()
    logo.thumbnail(box, RESAMPLING_LANCZOS)
    return logo


def trim_transparent(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return image
    return image.crop(bbox)


def base_canvas() -> Image.Image:
    size = 128
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((18, 20, 110, 112), fill=(19, 33, 38, 40))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    image.alpha_composite(shadow)
    return image


def pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def draw_health_badge(draw: ImageDraw.ImageDraw, health: str) -> None:
    badge_color = HEALTH_COLORS.get(health, "#7f8c8d")
    draw.ellipse((82, 18, 108, 44), fill=(255, 255, 255, 255))
    draw.ellipse((86, 22, 104, 40), fill=badge_color)


def category_style(node: dict) -> dict[str, str]:
    return CATEGORY_STYLE_BY_ID.get(node["id"]) or CATEGORY_STYLE_BY_KIND.get(node["kind"], {"key": "platform", "color": "#475569"})


def draw_category_badge(image: Image.Image, node: dict) -> None:
    draw = ImageDraw.Draw(image)
    draw.ellipse((18, 18, 44, 44), fill=(255, 255, 255, 245), outline=(19, 33, 38, 22), width=1)
    style = category_style(node)
    color = style["color"]
    key = style["key"]

    if key == "ai":
        draw_ai_glyph(draw, color)
    elif key == "system":
        draw_system_glyph(draw, color)
    elif key == "platform":
        draw_platform_glyph(draw, color)
    elif key == "site":
        draw_site_glyph(draw, color)
    elif key == "local":
        draw_local_glyph(draw, color)
    elif key == "repo":
        draw_repo_glyph(draw, color)
    elif key == "planning":
        draw_planning_glyph(draw, color)
    elif key == "hosting":
        draw_hosting_glyph(draw, color)
    elif key == "channel":
        draw_channel_glyph(draw, color)
    elif key == "lab":
        draw_lab_glyph(draw, color)
    else:
        draw_platform_glyph(draw, color)


def draw_ai_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rounded_rectangle((26, 25, 36, 35), radius=2, outline=color, width=2)
    for x in (28, 34):
        draw.line((x, 21, x, 24), fill=color, width=2)
        draw.line((x, 36, x, 39), fill=color, width=2)
    for y in (27, 33):
        draw.line((22, y, 25, y), fill=color, width=2)
        draw.line((37, y, 40, y), fill=color, width=2)


def draw_system_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rounded_rectangle((24, 25, 38, 35), radius=2, outline=color, width=2)
    draw.line((28, 29, 31, 31), fill=color, width=2)
    draw.line((28, 33, 31, 31), fill=color, width=2)
    draw.line((33, 33, 37, 33), fill=color, width=2)


def draw_platform_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    for box in ((24, 24, 29, 29), (33, 24, 38, 29), (24, 33, 29, 38), (33, 33, 38, 38)):
        draw.rounded_rectangle(box, radius=1, outline=color, width=2)


def draw_site_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.ellipse((24, 24, 38, 38), outline=color, width=2)
    draw.line((31, 24, 31, 38), fill=color, width=2)
    draw.arc((26, 24, 36, 38), 90, 270, fill=color, width=2)
    draw.arc((26, 24, 36, 38), -90, 90, fill=color, width=2)
    draw.line((24, 31, 38, 31), fill=color, width=2)


def draw_local_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rounded_rectangle((24, 24, 38, 34), radius=2, outline=color, width=2)
    draw.line((28, 38, 34, 38), fill=color, width=2)
    draw.line((31, 34, 31, 38), fill=color, width=2)


def draw_repo_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.line((28, 27, 24, 31, 28, 35), fill=color, width=2)
    draw.line((34, 27, 38, 31, 34, 35), fill=color, width=2)


def draw_planning_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rounded_rectangle((25, 24, 37, 38), radius=2, outline=color, width=2)
    draw.rounded_rectangle((28, 22, 34, 26), radius=1, outline=color, width=2)
    draw.line((28, 30, 34, 30), fill=color, width=2)
    draw.line((28, 34, 33, 34), fill=color, width=2)


def draw_hosting_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.arc((23, 28, 31, 36), 180, 360, fill=color, width=2)
    draw.arc((28, 24, 36, 34), 180, 360, fill=color, width=2)
    draw.arc((33, 28, 41, 36), 180, 360, fill=color, width=2)
    draw.line((25, 36, 39, 36), fill=color, width=2)


def draw_channel_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rounded_rectangle((24, 25, 38, 35), radius=4, outline=color, width=2)
    draw.polygon(((29, 35), (29, 39), (33, 35)), outline=color, fill=None)
    draw.line((29, 35, 31, 38, 33, 35), fill=color, width=2)


def draw_lab_glyph(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.line((29, 24, 33, 24), fill=color, width=2)
    draw.line((30, 24, 30, 28), fill=color, width=2)
    draw.line((32, 24, 32, 28), fill=color, width=2)
    draw.polygon(((28, 28), (25, 36), (37, 36), (34, 28)), outline=color, fill=None)
    draw.line((28, 28, 25, 36, 37, 36, 34, 28), fill=color, width=2)


def draw_monogram_icon(node: dict, spec: dict[str, str]) -> Image.Image:
    size = 128
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 108, 108), fill=spec["bg"])

    font = pick_font(40)
    bbox = draw.textbbox((0, 0), spec["label"], font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2
    y = (size - text_h) / 2 - 3
    draw.text((x, y), spec["label"], fill=spec["fg"], font=font)

    draw_category_badge(image, node)
    draw_health_badge(draw, node.get("health", "healthy"))
    return image


def compose_node_icon(node: dict) -> Path:
    # This PNG is the final icon artifact consumed by Cytoscape.
    # Keep health and category badges baked in here instead of layering them later in the browser.
    if node["id"] in INTERNAL_ICON_SPECS:
        canvas = draw_monogram_icon(node, INTERNAL_ICON_SPECS[node["id"]])
        out = RENDERED_DIR / f"{node['id']}.png"
        canvas.save(out)
        return out

    size = 128
    canvas = base_canvas()

    bubble_bg = BUBBLE_BACKGROUNDS.get(node["id"], (255, 255, 255, 255))
    bubble = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bubble_draw = ImageDraw.Draw(bubble)
    bubble_draw.ellipse((18, 18, 110, 110), fill=bubble_bg)
    canvas.alpha_composite(bubble)

    raw_icon = load_raw_icon(node["id"])
    if raw_icon is None:
        raise RuntimeError(f"Missing raw icon source for {node['id']}")
    raw_icon = trim_transparent(raw_icon)

    logo = fit_logo(raw_icon, (54, 54))
    logo_x = (size - logo.width) // 2
    logo_y = 37 if node["id"] == "jira" else 36
    canvas.alpha_composite(logo, (logo_x, logo_y))

    draw_category_badge(canvas, node)
    draw_health_badge(ImageDraw.Draw(canvas), node.get("health", "healthy"))

    out = RENDERED_DIR / f"{node['id']}.png"
    canvas.save(out)
    return out


def main() -> None:
    ensure_dirs()
    map_data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))

    for node in map_data["nodes"]:
        icon_path = compose_node_icon(node)
        node["iconPath"] = f"./assets/rendered/{icon_path.name}"

    RUNTIME_PATH.write_text(
        json.dumps(map_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Built rendered icons in: {RENDERED_DIR}")


if __name__ == "__main__":
    main()
