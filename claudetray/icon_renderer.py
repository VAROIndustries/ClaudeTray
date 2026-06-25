from PIL import Image, ImageDraw, ImageFont


def _get_color(five_pct: float, seven_pct: float) -> tuple:
    max_pct = max(five_pct, seven_pct)
    if max_pct >= 80:
        return (239, 68, 68)  # red
    elif max_pct >= 60:
        return (234, 179, 8)  # yellow
    return (34, 197, 94)  # green


def _load_font(size: int):
    font_size = max(size // 3, 8)
    for name in ("arial.ttf", "Arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_icon(five_pct: float, seven_pct: float, size: int = 64) -> Image.Image:
    bg = (26, 26, 46, 255)
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)

    color = _get_color(five_pct, seven_pct)
    font = _load_font(size)

    five_text = str(int(five_pct))
    seven_text = str(int(seven_pct))

    # Top number (5h usage)
    bbox1 = draw.textbbox((0, 0), five_text, font=font)
    w1 = bbox1[2] - bbox1[0]
    h1 = bbox1[3] - bbox1[1]
    x1 = (size - w1) // 2
    y1 = size // 8
    draw.text((x1, y1), five_text, fill=color, font=font)

    # Divider line
    div_y = size // 2 - 1
    draw.line([(size // 6, div_y), (size - size // 6, div_y)], fill=(100, 100, 140), width=1)

    # Bottom number (7d usage)
    bbox2 = draw.textbbox((0, 0), seven_text, font=font)
    w2 = bbox2[2] - bbox2[0]
    x2 = (size - w2) // 2
    y2 = size // 2 + size // 16
    draw.text((x2, y2), seven_text, fill=color, font=font)

    return img
