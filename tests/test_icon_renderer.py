from PIL import Image
from claudetray.icon_renderer import render_icon


def test_render_icon_returns_image():
    img = render_icon(41, 37)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_render_icon_custom_size():
    img = render_icon(50, 60, size=128)
    assert img.size == (128, 128)


def test_render_icon_zero_values():
    img = render_icon(0, 0)
    assert img.size == (64, 64)


def test_render_icon_max_values():
    img = render_icon(100, 100)
    assert img.size == (64, 64)


def test_render_icon_not_blank():
    img = render_icon(41, 37)
    pixels = list(img.getdata())
    bg_color = (26, 26, 46, 255)
    non_bg = [p for p in pixels if p != bg_color]
    assert len(non_bg) > 0, "Icon should contain rendered text, not just background"
