"""
Generate assets/icon.ico for ClaudeTray.

Design: dark rounded-square background with a vertical fill-bar (gauge/battery meter)
at ~40% fill in green. Tick marks on the right. Simple and crisp at all sizes.
Sizes: 16, 32, 48, 256 -- packed into a single .ico file.
"""

import os
from PIL import Image, ImageDraw

BG      = (26,  26,  46, 255)   # #1a1a2e  dark navy
GREEN   = (34, 197,  94, 255)   # #22c55e  primary accent
GREEN_D = (16, 140,  50, 255)   # darker green for gradient bottom
TRACK   = (55,  55,  90, 255)   # empty track
BORDER  = (70,  70, 115, 255)   # outer ring
TICK    = (110, 110, 160, 255)  # tick marks


def lerp_color(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(4))


def draw_icon(size: int, fill_ratio: float = 0.42) -> Image.Image:
    s   = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    pad = max(1, s // 14)
    r   = max(2, s // 5)

    # Outer rounded-square
    d.rounded_rectangle(
        [pad, pad, s - pad - 1, s - pad - 1],
        radius=r,
        fill=BG,
        outline=BORDER,
        width=max(1, s // 48),
    )

    # Bar geometry
    bw   = max(4, s * 22 // 100)   # bar width
    bh   = max(6, s * 68 // 100)   # bar height
    bx0  = (s - bw) // 2 - max(1, s // 16)   # shift slightly left for ticks
    bx1  = bx0 + bw
    by0  = (s - bh) // 2
    by1  = by0 + bh
    brad = max(1, bw // 3)

    # Empty track
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=brad, fill=TRACK)

    # Green fill -- draw as a solid block using a mask for rounded corners
    fill_h  = max(1, int(bh * fill_ratio))
    fy0     = by1 - fill_h

    # Build fill on a scratch layer so we can mask with rounded rect
    fill_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill_layer)

    # Gradient: band-by-band from dark at bottom to bright at top
    for i in range(fill_h):
        # i=0 is the topmost row of the fill block; i=fill_h-1 is the bottom
        t   = i / max(fill_h - 1, 1)   # 0 = top, 1 = bottom
        col = lerp_color(GREEN, GREEN_D, t)
        y   = fy0 + i
        fd.line([(bx0, y), (bx1, y)], fill=col)

    # Mask to rounded bar shape (bottom portion)
    mask_layer = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask_layer)
    md.rounded_rectangle([bx0, by0, bx1, by1], radius=brad, fill=255)
    # Blank out the empty portion above the fill
    md.rectangle([bx0, by0, bx1, fy0 - 1], fill=0)

    img.paste(fill_layer, mask=mask_layer)

    # Tick marks (right side of bar), only at >= 32 px
    if s >= 32:
        tx0     = bx1 + max(1, s // 20)
        tx1     = tx0 + max(2, s // 10)
        n_ticks = 5
        lw      = max(1, s // 48)
        for n in range(n_ticks):
            ty = by0 + int(bh * n / (n_ticks - 1))
            d.line([(tx0, ty), (tx1, ty)], fill=TICK, width=lw)

    # Small highlight dot on fill top-left corner (>= 48 px only)
    if s >= 48 and fill_h > 4:
        dr = max(1, s // 40)
        hx = bx0 + dr + 1
        hy = fy0 + dr + 1
        d.ellipse([hx - dr, hy - dr, hx + dr, hy + dr], fill=(200, 255, 220, 180))

    return img


def main():
    sizes  = [16, 32, 48, 256]
    images = [draw_icon(s) for s in sizes]

    out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "icon.ico")

    # Pillow ICO save: first image is the base; append_images adds the rest
    images[-1].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print("Saved", out_path)

    for img, s in zip(images, sizes):
        p = os.path.join(out_dir, f"icon_{s}.png")
        img.save(p)
        print("  PNG preview:", p)


if __name__ == "__main__":
    main()
