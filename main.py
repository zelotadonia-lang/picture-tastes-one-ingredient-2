#!/usr/bin/env python3
"""One ingredient, one picture: a single ripe strawberry on a ceramic plate.

Competition: the-picture-that-tastes-of-one-20261122-2047
("The picture that tastes of one ingredient"). One ingredient only: a
strawberry, drawn procedurally with the Python 3.13 standard library alone.
No third-party imports: no PIL, no numpy. The PNG encoder, the rasteriser
(ellipse / polygon scanline fills, alpha compositing) and the box blur
(summed-area table, O(1) per pixel) are all implemented here.

Writes /output/entry.png (1024x1024, under 1 MiB). Deterministic:
random.Random(42), no clock, no dict/set iteration affecting output.
"""

import math
import os
import random
import struct
import zlib

SIZE = 1024
OUTPUT = "/output/entry.png"
SEED = 42

rng = random.Random(SEED)

# Canvas: flat RGB bytearray, 3 bytes per pixel.
canvas = bytearray(SIZE * SIZE * 3)


def _idx(x, y):
    return (y * SIZE + x) * 3


def blend_pixel(x, y, r, g, b, a):
    """Alpha-composite one pixel over the canvas."""
    if a <= 0 or x < 0 or x >= SIZE or y < 0 or y >= SIZE:
        return
    if a >= 255:
        i = _idx(x, y)
        canvas[i] = r
        canvas[i + 1] = g
        canvas[i + 2] = b
        return
    i = _idx(x, y)
    ia = 255 - a
    canvas[i] = (r * a + canvas[i] * ia) // 255
    canvas[i + 1] = (g * a + canvas[i + 1] * ia) // 255
    canvas[i + 2] = (b * a + canvas[i + 2] * ia) // 255


def fill_span(y, x0, x1, r, g, b, a):
    """Fill a horizontal run of pixels on row y."""
    if y < 0 or y >= SIZE:
        return
    x0 = max(0, x0)
    x1 = min(SIZE - 1, x1)
    if x1 < x0:
        return
    if a >= 255:
        n = x1 - x0 + 1
        canvas[_idx(x0, y):_idx(x0, y) + 3 * n] = bytes((r, g, b)) * n
        return
    for x in range(x0, x1 + 1):
        blend_pixel(x, y, r, g, b, a)


def fill_ellipse(cx, cy, rx, ry, color, alpha=255):
    """Scanline-filled ellipse."""
    r, g, b = color
    for y in range(cy - ry, cy + ry + 1):
        t = (y - cy) / ry
        if t < -1.0 or t > 1.0:
            continue
        dx = int(rx * math.sqrt(1.0 - t * t))
        fill_span(y, cx - dx, cx + dx, r, g, b, alpha)


def fill_polygon(points, color, alpha=255):
    """Scanline-filled polygon (even-odd)."""
    r, g, b = color
    ys = [p[1] for p in points]
    y0, y1 = max(0, min(ys)), min(SIZE - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, yy0 = points[i]
            x1, yy1 = points[(i + 1) % n]
            if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                xs.append(x0 + (y - yy0) * (x1 - x0) / (yy1 - yy0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            fill_span(y, int(xs[k]), int(xs[k + 1]), r, g, b, alpha)


def draw_line(x0, y0, x1, y1, color, width, alpha=255):
    """Thick line drawn as a chain of small filled circles."""
    length = max(1, int(math.hypot(x1 - x0, y1 - y0)))
    rad = max(1, width // 2)
    for s in range(length + 1):
        t = s / length
        fill_ellipse(
            int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
            rad, rad, color, alpha,
        )


def box_blur_gray(data, w, h, radius):
    """Box blur of a grayscale buffer via a summed-area table (O(1)/pixel)."""
    stride = w + 1
    ii = [0] * (stride * (h + 1))
    for y in range(h):
        s = 0
        row = y * w
        irow = (y + 1) * stride
        prow = y * stride
        for x in range(w):
            s += data[row + x]
            ii[irow + x + 1] = ii[prow + x + 1] + s
    out = bytearray(w * h)
    for y in range(h):
        y0 = y - radius
        if y0 < 0:
            y0 = 0
        y1 = y + radius
        if y1 > h - 1:
            y1 = h - 1
        top = y0 * stride
        bot = (y1 + 1) * stride
        area_h = y1 - y0 + 1
        for x in range(w):
            x0 = x - radius
            if x0 < 0:
                x0 = 0
            x1 = x + radius
            if x1 > w - 1:
                x1 = w - 1
            total = ii[bot + x1 + 1] - ii[top + x1 + 1] - ii[bot + x0] + ii[top + x0]
            out[y * w + x] = total // ((x1 - x0 + 1) * area_h)
    return out


def paint_background():
    """Warm dark backdrop, brighter near the top-left light source."""
    cx, cy = 368, 307
    maxd = 900.0
    inner = (74, 48, 38)
    outer = (22, 14, 12)
    for y in range(SIZE):
        dy = y - cy
        base = y * SIZE * 3
        for x in range(SIZE):
            dx = x - cx
            d = math.sqrt(dx * dx + dy * dy) / maxd
            if d > 1.0:
                d = 1.0
            t = d * d
            i = base + x * 3
            canvas[i] = int(inner[0] + (outer[0] - inner[0]) * t)
            canvas[i + 1] = int(inner[1] + (outer[1] - inner[1]) * t)
            canvas[i + 2] = int(inner[2] + (outer[2] - inner[2]) * t)


def paint_plate():
    """Cream ceramic plate under the berry, with rim and soft shadow."""
    cx, cy = SIZE // 2, 872
    # Soft shadow: concentric translucent ellipses, darkest in the middle.
    for k, a in ((0, 34), (1, 26), (2, 18)):
        fill_ellipse(cx, cy + 8, 400 - k * 22, 92 - k * 10, (0, 0, 0), a)
    # Plate body and inner well (leaves a rim ring).
    fill_ellipse(cx, cy, 385, 105, (232, 222, 203))
    fill_ellipse(cx, cy, 330, 82, (240, 232, 214))
    # Rim lines.
    for y in range(cy - 105, cy + 106):
        t = (y - cy) / 105.0
        if abs(t) > 1.0:
            continue
        dx = int(385 * math.sqrt(1.0 - t * t))
        blend_pixel(cx - dx, y, 196, 180, 156, 200)
        blend_pixel(cx + dx, y, 196, 180, 156, 200)
    # Warm light pooling on the plate's left.
    fill_ellipse(cx - 185, cy, 150, 80, (255, 244, 220), 60)


def strawberry_mask():
    """Feathered silhouette of one strawberry: wide shoulders, soft tip.

    Built from overlapping shapes inside a cropped box, then box-blurred
    (radius 2) through the summed-area table for a soft edge.
    """
    x0, y0 = 300, 240
    w, h = 424, 650
    mask = bytearray(w * h)
    for y in range(y0, y0 + h):
        row = (y - y0) * w
        for x in range(x0, x0 + w):
            inside = False
            # Shoulders: ellipse centred (512, 425).
            ex = (x - 512) / 205.0
            ey = (y - 425) / 175.0
            if ex * ex + ey * ey <= 1.0:
                inside = True
            # Taper: half-width shrinks from 200 at y=400 to 78 at y=800.
            if not inside and 400 <= y <= 800:
                half = 200 - (y - 400) * (122.0 / 400.0)
                if abs(x - 512) <= half:
                    inside = True
            # Tip: ellipse centred (512, 735), plus a small round tip.
            if not inside:
                tx = (x - 512) / 105.0
                ty = (y - 735) / 115.0
                if tx * tx + ty * ty <= 1.0:
                    inside = True
            if not inside:
                ux = (x - 512) / 48.0
                uy = (y - 822) / 55.0
                if ux * ux + uy * uy <= 1.0:
                    inside = True
            if inside:
                mask[row + (x - x0)] = 255
    return box_blur_gray(mask, w, h, 2), x0, y0, w


def paint_strawberry(mask, mx0, my0, mw):
    """Red gradient body clipped to the mask, warm light from the left."""
    top = (238, 52, 44)
    mid = (206, 26, 32)
    low = (140, 12, 22)
    # Per-row base colour (vertical gradient) and per-column light factor.
    row_color = []
    for y in range(250, 890):
        if y < 480:
            t = (y - 250) / 230.0
            row_color.append((
                top[0] + (mid[0] - top[0]) * t,
                top[1] + (mid[1] - top[1]) * t,
                top[2] + (mid[2] - top[2]) * t,
            ))
        else:
            t = (y - 480) / 415.0
            row_color.append((
                mid[0] + (low[0] - mid[0]) * t,
                mid[1] + (low[1] - mid[1]) * t,
                mid[2] + (low[2] - mid[2]) * t,
            ))
    light = []
    for x in range(mx0, mx0 + mw):
        nx = (x - 512) / 205.0
        if nx < -1.0:
            nx = -1.0
        elif nx > 1.0:
            nx = 1.0
        light.append(1.0 - 0.22 * nx)
    for yi, y in enumerate(range(250, 890)):
        br, bg, bb = row_color[yi]
        mrow = (y - my0) * mw
        for xi, x in enumerate(range(mx0, mx0 + mw)):
            a = mask[mrow + xi]
            if a == 0:
                continue
            f = light[xi]
            r = br * f
            g = bg * f
            b = bb * f
            if r > 255:
                r = 255.0
            if g > 255:
                g = 255.0
            if b > 255:
                b = 255.0
            i = _idx(x, y)
            if a >= 255:
                canvas[i] = int(r)
                canvas[i + 1] = int(g)
                canvas[i + 2] = int(b)
            else:
                ia = 255 - a
                canvas[i] = (int(r) * a + canvas[i] * ia) // 255
                canvas[i + 1] = (int(g) * a + canvas[i + 1] * ia) // 255
                canvas[i + 2] = (int(b) * a + canvas[i + 2] * ia) // 255


def paint_seeds(mask, mx0, my0, mw):
    """Pale achenes in gentle staggered rows following the berry's curve."""
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
            t = (i + 0.5 + (0.5 if ri % 2 else 0.0)) / count
            if t > 1.0:
                continue
            x = int(cx - half + 2 * half * t)
            if x < mx0 or x >= mx0 + mw or y < my0 or y >= my0 + 650:
                continue
            if mask[(y - my0) * mw + (x - mx0)] < 128:
                continue
            jitter = rng.uniform(-6, 6)
            jx = int(x + jitter)
            sw = int(rng.uniform(4, 6))
            sh = int(rng.uniform(7, 9))
            # Shadow pit, then the pale seed, then a tiny bright tip.
            fill_ellipse(jx + 2, y + 3, sw, sh, (90, 5, 10), 160)
            fill_ellipse(jx, y, sw, sh, (252, 226, 150))
            fill_ellipse(jx - 2, y - 4, 2, 3, (255, 246, 210))


def paint_calyx():
    """Green star leaves and stem at the top of the berry."""
    cx = SIZE // 2
    top_y = 268
    draw_line(cx, 205, cx + 6, 268, (46, 96, 34), 14)
    draw_line(cx, 205, cx + 6, 268, (86, 150, 58), 6)
    tips = [(-170, 246), (-115, 214), (-40, 196), (55, 200), (125, 218), (172, 248)]
    for tx, ty in tips:
        bx = cx + int(tx * 0.3)
        tip_y = top_y + int((ty - top_y) * 0.62)
        fill_polygon(
            [(bx - 48, top_y + 8), (cx + tx, tip_y), (bx + 48, top_y + 8)],
            (52, 118, 40),
        )
        draw_line(bx - 48, top_y + 8, cx + tx, tip_y, (28, 76, 24), 2)
        draw_line(bx + 48, top_y + 8, cx + tx, tip_y, (28, 76, 24), 2)
    fill_ellipse(cx, top_y + 3, 44, 17, (58, 128, 44))


def paint_droplets():
    """Water drops: faint discs with a bright top-left sparkle."""
    spots = [
        (400, 470, 7),
        (620, 430, 8),
        (560, 600, 6),
        (430, 640, 5),
        (620, 560, 6),
        (500, 760, 7),
        (600, 700, 5),
    ]
    for x, y, r in spots:
        # Bright rim, paler centre, then a sharp sparkle at top-left.
        fill_ellipse(x, y, r, r, (255, 255, 255), 70)
        fill_ellipse(x, y, max(1, r - 2), max(1, r - 2), (255, 255, 255), 30)
        fill_ellipse(int(x - r * 0.3), int(y - r * 0.35), max(1, r // 3), max(1, r // 3),
                     (255, 255, 255), 220)


def paint_gloss():
    """Soft highlight on the upper-left shoulder, like fresh juice."""
    cx = SIZE // 2
    # Five nested ellipses, alpha rising toward the centre, so the sheen
    # fades smoothly instead of showing hard rings.
    for rx, ry, a in ((84, 116, 6), (74, 102, 8), (64, 88, 11),
                      (54, 74, 14), (44, 60, 18), (34, 46, 23), (24, 33, 28)):
        fill_ellipse(cx - 140, 395, rx, ry, (255, 255, 255), a)


def paint_vignette():
    """Gentle darkening toward the corners so the berry stays brightest."""
    cx = cy = SIZE // 2
    limit2 = int((0.62 * 724) ** 2)
    for y in range(SIZE):
        dy = y - cy
        for x in range(SIZE):
            dx = x - cx
            d2 = dx * dx + dy * dy
            if d2 <= limit2:
                continue
            d = math.sqrt(d2) / 724.0
            f = 1.0 - 0.22 * ((d - 0.62) / 0.38) ** 2
            i = _idx(x, y)
            canvas[i] = int(canvas[i] * f)
            canvas[i + 1] = int(canvas[i + 1] * f)
            canvas[i + 2] = int(canvas[i + 2] * f)


def write_png(path):
    """PNG encoder: signature, IHDR, IDAT (zlib, filter 0), IEND."""
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        raw += canvas[y * SIZE * 3:(y + 1) * SIZE * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def main():
    paint_background()
    paint_plate()
    # Soft shadow of the berry on the plate.
    fill_ellipse(SIZE // 2, 855, 220, 42, (0, 0, 0), 26)
    fill_ellipse(SIZE // 2, 855, 180, 32, (0, 0, 0), 30)
    mask, mx0, my0, mw = strawberry_mask()
    paint_strawberry(mask, mx0, my0, mw)
    paint_seeds(mask, mx0, my0, mw)
    paint_calyx()
    paint_droplets()
    paint_gloss()
    paint_vignette()
    os.makedirs("/output", exist_ok=True)
    size = write_png(OUTPUT)
    os.chmod(OUTPUT, 0o644)
    print("wrote %s (%d bytes)" % (OUTPUT, size))


if __name__ == "__main__":
    main()
