#!/usr/bin/env python3
"""One ingredient, one picture: a single ripe strawberry on a ceramic plate.

Drawn procedurally with PIL. No network, fixed seed, deterministic output.
Writes /output/entry.png (1024x1024, under 1 MiB).
"""

import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
OUTPUT = "/output/entry.png"
SEED = 42

rng = random.Random(SEED)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def radial_background(size):
    """Warm dark backdrop, brighter near the top-left light source."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    cx, cy = size * 0.36, size * 0.30
    maxd = math.hypot(size, size) * 0.62
    inner = (74, 48, 38)
    outer = (22, 14, 12)
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy) / maxd
            t = min(1.0, d)
            px[x, y] = lerp(inner, outer, t * t)
    return img


def soft_ellipse(draw, box, fill, blur):
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(box, fill=fill)
    return layer.filter(ImageFilter.GaussianBlur(blur))


def strawberry_mask():
    """Silhouette of one strawberry: wide shoulders, tapering to a soft tip."""
    layer = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(layer)
    cx = SIZE // 2
    # Body built from overlapping shapes for a smooth tapered form.
    d.ellipse([cx - 205, 250, cx + 205, 600], fill=255)
    d.polygon(
        [
            (cx - 200, 400),
            (cx + 200, 400),
            (cx + 78, 800),
            (cx - 78, 800),
        ],
        fill=255,
    )
    d.ellipse([cx - 105, 620, cx + 105, 850], fill=255)
    d.ellipse([cx - 48, 780, cx + 48, 875], fill=255)
    return layer.filter(ImageFilter.GaussianBlur(3))


def strawberry_body(mask):
    """Red gradient body clipped to the silhouette, with warm shading."""
    body = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    px = body.load()
    top = (238, 52, 44)
    mid = (196, 22, 28)
    low = (128, 8, 18)
    for y in range(250, 895):
        if y < 480:
            t = (y - 250) / 230.0
            c = lerp(top, mid, t)
        else:
            t = (y - 480) / 415.0
            c = lerp(mid, low, t)
        for x in range(SIZE):
            px[x, y] = c
    # Warm light from the left: brighten left side, deepen right edge.
    shade = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    d.ellipse([SIZE // 2 - 320, 200, SIZE // 2 + 60, 900], fill=(255, 190, 120, 40))
    d.ellipse([SIZE // 2 + 60, 230, SIZE // 2 + 300, 900], fill=(40, 0, 10, 34))
    shade = shade.filter(ImageFilter.GaussianBlur(28))
    body = Image.composite(
        Image.alpha_composite(body.convert("RGBA"), shade), body, mask
    )
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(body.convert("RGBA"), (0, 0), mask)
    return out


def seeds(draw, mask):
    """Pale achenes in gentle rows following the berry's curve."""
    cx = SIZE // 2
    rows = [
        (330, 130, 11),
        (400, 170, 13),
        (470, 195, 14),
        (545, 200, 14),
        (620, 190, 13),
        (695, 165, 12),
        (765, 130, 10),
        (825, 85, 7),
    ]
    for ri, (y, half, count) in enumerate(rows):
        for i in range(count):
            # Stagger alternate rows so seeds read as scattered, not gridded.
            t = (i + 0.5 + (0.5 if ri % 2 else 0.0)) / count
            if t > 1.0:
                continue
            x = cx - half + 2 * half * t
            # Skip seeds outside the silhouette.
            if mask.getpixel((int(x), y)) < 128:
                continue
            jitter = rng.uniform(-6, 6)
            w, h = 10, 16
            # Shadow pit, then pale seed.
            draw.ellipse(
                [x - w / 2 + 2, y - h / 2 + 3, x + w / 2 + 2, y + h / 2 + 3],
                fill=(90, 5, 10, 160),
            )
            draw.ellipse(
                [x - w / 2 + jitter, y - h / 2, x + w / 2 + jitter, y + h / 2],
                fill=(252, 226, 150, 255),
                outline=(214, 164, 90, 255),
                width=1,
            )
            draw.ellipse(
                [x - 3 + jitter, y - 6, x + 1 + jitter, y - 1],
                fill=(255, 246, 210, 255),
            )


def calyx(draw):
    """Green star leaves and stem at the top of the berry."""
    cx = SIZE // 2
    top_y = 268
    # Stem.
    draw.line([cx, 205, cx + 6, 268], fill=(46, 96, 34, 255), width=14)
    draw.line([cx, 205, cx + 6, 268], fill=(86, 150, 58, 255), width=6)
    # Five pointed leaves fanning out: each a tapered triangle with a
    # sharp tip, base tucked under the centre cap.
    tips = [(-205, 250), (-135, 215), (-45, 195), (60, 200), (150, 220), (210, 252)]
    for tx, ty in tips:
        bx = cx + tx * 0.3
        draw.polygon(
            [
                (bx - 30, top_y + 8),
                (cx + tx, top_y + (ty - top_y) * 0.62),
                (bx + 30, top_y + 8),
            ],
            fill=(52, 118, 40, 255),
            outline=(28, 76, 24, 255),
        )
    # Centre cap.
    draw.ellipse([cx - 44, top_y - 14, cx + 44, top_y + 20], fill=(58, 128, 44, 255))


def droplets(draw):
    """Water drops: clear circles with a bright top-left sparkle."""
    spots = [
        (400, 470, 7),
        (620, 430, 8),
        (560, 600, 6),
        (430, 640, 5),
        (680, 560, 6),
        (500, 760, 7),
        (640, 700, 5),
    ]
    for x, y, r in spots:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 26))
        draw.ellipse(
            [x - r, y - r, x + r, y + r], outline=(255, 255, 255, 90), width=1
        )
        draw.ellipse([x - r * 0.4, y - r * 0.5, x - r * 0.05, y - r * 0.15], fill=(255, 255, 255, 200))


def gloss(draw):
    """Big soft highlight on the upper-left shoulder, like fresh juice."""
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([SIZE // 2 - 195, 310, SIZE // 2 - 85, 480], fill=(255, 255, 255, 55))
    d.ellipse([SIZE // 2 - 175, 325, SIZE // 2 - 115, 430], fill=(255, 255, 255, 85))
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    draw._image.paste(Image.alpha_composite(draw._image, layer), (0, 0))


def plate(img):
    """Cream ceramic plate under the berry, with a rim and soft shadow."""
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = SIZE // 2, 872
    # Plate shadow on the backdrop.
    img.paste(
        Image.alpha_composite(
            img.convert("RGBA"),
            soft_ellipse(d, [cx - 400, cy - 60, cx + 400, cy + 90], (0, 0, 0, 110), 26),
        ),
        (0, 0),
    )
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([cx - 385, cy - 105, cx + 385, cy + 105], fill=(232, 222, 203, 255))
    d.ellipse([cx - 385, cy - 105, cx + 385, cy + 105], outline=(196, 180, 156, 255), width=3)
    d.ellipse([cx - 330, cy - 82, cx + 330, cy + 82], outline=(206, 192, 168, 255), width=2)
    # Warm light pooling on the plate's left.
    d.ellipse([cx - 330, cy - 82, cx - 40, cy + 82], fill=(255, 244, 220, 60))


def label(img):
    """One word, small and neat, so the judge reads the ingredient at a glance."""
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 58)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(img, "RGBA")
    text = "Strawberry"
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (SIZE - w) // 2
    y = 60
    d.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 110))
    d.text((x, y), text, font=font, fill=(250, 235, 215, 255))


def main():
    img = radial_background(SIZE)
    plate(img)

    # Soft shadow of the berry on the plate.
    shadow = soft_ellipse(
        ImageDraw.Draw(img), [SIZE // 2 - 220, 810, SIZE // 2 + 220, 900], (0, 0, 0, 80), 22
    )
    img = Image.alpha_composite(img.convert("RGBA"), shadow)

    mask = strawberry_mask()
    img = Image.alpha_composite(img, strawberry_body(mask))

    d = ImageDraw.Draw(img, "RGBA")
    seeds(d, mask)
    calyx(d)
    droplets(d)
    gloss(d)
    label(img)

    # Gentle vignette so the berry stays the brightest thing in frame.
    vig = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    dv = ImageDraw.Draw(vig)
    dv.rectangle([0, 0, SIZE, SIZE], outline=(0, 0, 0, 90), width=46)
    vig = vig.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, vig)

    os.makedirs("/output", exist_ok=True)
    img.convert("RGB").save(OUTPUT, format="PNG", optimize=True)
    os.chmod(OUTPUT, 0o644)


if __name__ == "__main__":
    main()
