from PIL import Image, ImageDraw


def _bar_color(pct: float) -> tuple:
    if pct >= 80:
        return (239, 68, 68)  # red
    elif pct >= 60:
        return (234, 179, 8)  # yellow
    return (34, 197, 94)  # green


def render_icon(five_pct: float, seven_pct: float, size: int = 64) -> Image.Image:
    """Render two vertical fill bars side by side — left=5h, right=7d."""
    bg = (26, 26, 46, 255)
    border = (60, 60, 90, 255)
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)

    pad = max(size // 8, 1)
    gap = max(size // 8, 1)
    bar_w = (size - 2 * pad - gap) // 2
    bar_h = size - 2 * pad

    for i, pct in enumerate((five_pct, seven_pct)):
        x = pad + i * (bar_w + gap)
        y = pad
        color = _bar_color(pct)
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

    return img
