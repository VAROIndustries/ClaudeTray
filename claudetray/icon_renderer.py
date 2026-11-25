from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

BADGE_COLORS = {
    "permission": (220, 38, 38),   # red: a session is blocked on you
    "question": (217, 140, 20),    # amber: Claude asked you something
    "done": (34, 140, 80),         # green: sessions finished, your turn
}


@lru_cache(maxsize=8)
def _badge_font(px: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _bar_color(pct: float, dimmed: bool = False) -> tuple:
    if pct >= 80:
        color = (239, 68, 68)  # red
    elif pct >= 60:
        color = (234, 179, 8)  # yellow
    else:
        color = (34, 197, 94)  # green
    if dimmed:
        # Blend toward grey to show stale data
        return tuple((c + 80) // 3 for c in color)
    return color


def render_icon(five_pct: float, seven_pct: float, size: int = 64,
                dimmed: bool = False, badge: int = 0, badge_kind: str = "") -> Image.Image:
    """Render two vertical fill bars side by side — left=5h, right=7d.

    With `badge` > 0, a numbered circle in the bottom-right corner shows how
    many Claude sessions are waiting on you, colored by the most urgent kind.
    """
    bg = (26, 26, 46, 255)
    border = (40, 40, 60, 255) if dimmed else (60, 60, 90, 255)
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)

    pad = max(size // 12, 1)
    gap = max(size // 16, 1)
    bar_w = (size - 2 * pad - gap) // 2
    bar_h = size - 2 * pad

    for i, pct in enumerate((five_pct, seven_pct)):
        x = pad + i * (bar_w + gap)
        y = pad
        color = _bar_color(pct, dimmed)
        clamped = max(0.0, min(100.0, pct))

        # Bar outline
        draw.rectangle([x, y, x + bar_w - 1, y + bar_h - 1], outline=border)

        # Fill from bottom
        fill_h = int(bar_h * clamped / 100.0)
        if fill_h > 0:
            fill_top = y + bar_h - fill_h
            bottom = y + bar_h - 2
            if fill_top > bottom:
                fill_top = bottom
            draw.rectangle([x + 1, fill_top, x + bar_w - 2, bottom], fill=color)

    if badge > 0:
        d = int(size * 0.62)
        x0 = y0 = size - d
        draw.ellipse([x0, y0, size - 1, size - 1], fill=BADGE_COLORS.get(badge_kind, BADGE_COLORS["done"]),
                     outline=(255, 255, 255), width=max(size // 32, 1))
        text = "9+" if badge > 9 else str(badge)
        font = _badge_font(int(d * (0.55 if len(text) > 1 else 0.72)))
        draw.text((x0 + d / 2, y0 + d / 2), text, fill=(255, 255, 255), font=font, anchor="mm")

    return img
