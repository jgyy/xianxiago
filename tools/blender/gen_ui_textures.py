"""Generates the Xianxia HUD art under assets/ui/.

Material fields (rice paper, jade marbling, gold leaf, lacquered wood,
vermilion seal paste, ink / mist noise) are Blender procedural shader
graphs baked with Cycles through xg_common.bake_graph. The motif shapes
(scroll, rings, seal, xiangyun curls, bagua trigrams, icons) are signed
distance fields composed in numpy, and relief lighting is derived from
those fields, so every texture is resolution-independent and reproducible.

    /opt/bpy5/bin/python tools/blender/gen_ui_textures.py [name-filter]

All images are RGBA PNGs with the top row first once saved.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import xg_common as xg  # noqa: E402

OUT_DIR = os.path.join(xg.ROOT, "assets", "ui")
ASSETS = []  # (name, fn) where fn() -> (h, w, 4) array, top row first

INK = np.array([0.05, 0.055, 0.065], np.float32)
PAPER_LIGHT = np.array([0.95, 0.91, 0.80], np.float32)
VERMILION = np.array([0.78, 0.16, 0.09], np.float32)


def register(fn):
    ASSETS.append((fn.__name__, fn))
    return fn


# ---------------------------------------------------------------------------
# Blender-baked material fields (returned top row first)
# ---------------------------------------------------------------------------

def _iso_uv(nb, w, h, scale=1.0, off=(0.0, 0.0)):
    uv = nb.vmath("MULTIPLY", nb.uv(), nb.vec(scale * w / h, scale, 1.0))
    return nb.vmath("ADD", uv, nb.vec(off[0], off[1], 0.0))


def field(build, w, h):
    arr = xg.bake_graph(build, (w, h), name="ui_field")
    return np.ascontiguousarray(arr[::-1, :, :3])


def paper_field(w, h, seed=0.0):
    def build(nb):
        uv = _iso_uv(nb, w, h, 1.0, (seed, seed * 0.7))
        fibres = nb.noise(nb.vmath("MULTIPLY", uv, nb.vec(3.0, 40.0, 1.0)), 6.0, 5.0, 0.65)
        grain = nb.noise(uv, 220.0, 2.0, 0.5)
        blot = nb.noise(uv, 2.5, 6.0, 0.62, distortion=0.4)
        f = nb.add(nb.mul(fibres, 0.3), nb.add(nb.mul(grain, 0.2), nb.mul(blot, 0.5)))
        return nb.ramp(f, [(0.30, (0.78, 0.69, 0.52)), (0.46, (0.90, 0.84, 0.70)),
                           (0.58, (0.95, 0.91, 0.80)), (0.72, (0.98, 0.95, 0.87))])
    return field(build, w, h)


def jade_field(w, h, seed=0.0, dark=False):
    def build(nb):
        uv = _iso_uv(nb, w, h, 1.0, (seed, 1.3 * seed))
        marble = nb.wave(uv, 1.6, distortion=14.0, detail=6.0, direction="Y")
        cloud = nb.noise(uv, 3.5, 6.0, 0.6, distortion=0.8)
        fleck = nb.noise(uv, 40.0, 2.0, 0.5)
        f = nb.add(nb.mul(marble, 0.35), nb.add(nb.mul(cloud, 0.55), nb.mul(fleck, 0.1)))
        if dark:
            stops = [(0.25, (0.02, 0.09, 0.07)), (0.5, (0.05, 0.20, 0.15)),
                     (0.7, (0.10, 0.32, 0.24)), (0.85, (0.22, 0.46, 0.36))]
        else:
            stops = [(0.25, (0.06, 0.26, 0.19)), (0.48, (0.14, 0.45, 0.33)),
                     (0.66, (0.33, 0.66, 0.52)), (0.85, (0.70, 0.90, 0.78))]
        return nb.ramp(f, stops)
    return field(build, w, h)


def gold_field(w, h):
    def build(nb):
        uv = _iso_uv(nb, w, h, 1.0)
        ham = nb.noise(uv, 28.0, 3.0, 0.55)
        leaf = nb.voronoi(uv, 9.0, feature="F1", out="Distance")
        f = nb.add(nb.mul(ham, 0.7), nb.mul(leaf, 0.3))
        return nb.ramp(f, [(0.2, (0.66, 0.47, 0.17)), (0.5, (0.83, 0.64, 0.28)),
                           (0.8, (0.95, 0.80, 0.44))])
    return field(build, w, h)


def wood_field(w, h):
    def build(nb):
        uv = _iso_uv(nb, w, h, 1.0)
        grain = nb.wave(nb.vmath("MULTIPLY", uv, nb.vec(9.0, 0.6, 1.0)), 3.0,
                        distortion=6.0, detail=4.0, direction="X")
        n = nb.noise(uv, 12.0, 4.0, 0.6)
        f = nb.add(nb.mul(grain, 0.6), nb.mul(n, 0.4))
        return nb.ramp(f, [(0.2, (0.16, 0.05, 0.035)), (0.55, (0.30, 0.09, 0.05)),
                           (0.85, (0.46, 0.16, 0.08))])
    return field(build, w, h)


def vermilion_field(w, h):
    def build(nb):
        uv = _iso_uv(nb, w, h, 1.0)
        n = nb.noise(uv, 18.0, 5.0, 0.6)
        return nb.ramp(n, [(0.3, (0.60, 0.08, 0.05)), (0.55, (0.78, 0.15, 0.08)),
                           (0.75, (0.88, 0.25, 0.12))])
    return field(build, w, h)


def noise_pack(w, h, scales=(8.0, 3.0, 40.0), stretch=(1.0, 1.0), seed=0.0):
    """Three independent fBm fields in R, G, B (roughly 0..1, mean 0.5)."""
    def build(nb):
        uv = nb.vmath("MULTIPLY", _iso_uv(nb, w, h, 1.0, (seed, seed)), nb.vec(stretch[0], stretch[1], 1.0))
        a = nb.noise(uv, scales[0], 6.0, 0.6)
        b = nb.noise(nb.vmath("ADD", uv, nb.vec(17.3, 5.1, 0.0)), scales[1], 6.0, 0.6)
        c = nb.noise(nb.vmath("ADD", uv, nb.vec(-9.7, 31.4, 0.0)), scales[2], 4.0, 0.5)
        return nb.vec(a, b, c)
    return field(build, w, h)


# ---------------------------------------------------------------------------
# numpy shape toolkit (image space: x right, y down)
# ---------------------------------------------------------------------------

def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x + 0.5, y + 0.5


def aa(d, width=1.0):
    return np.clip(0.5 - d / width, 0.0, 1.0)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sd_box(x, y, cx, cy, hw, hh, r=0.0):
    qx = np.abs(x - cx) - hw + r
    qy = np.abs(y - cy) - hh + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_circle(x, y, cx, cy, r):
    return np.hypot(x - cx, y - cy) - r


def polyline(x, y, pts, pad=40.0):
    """Distance to a polyline plus the normalised arc length of the nearest
    point. Evaluated only inside the polyline's padded bounding box."""
    pts = np.asarray(pts, np.float32)
    best = np.full(x.shape, 1e6, np.float32)
    s = np.zeros(x.shape, np.float32)
    x0 = max(int(pts[:, 0].min() - pad), 0)
    x1 = min(int(pts[:, 0].max() + pad) + 1, x.shape[1])
    y0 = max(int(pts[:, 1].min() - pad), 0)
    y1 = min(int(pts[:, 1].max() + pad) + 1, x.shape[0])
    if x0 >= x1 or y0 >= y1:
        return best, s
    sx, sy = x[y0:y1, x0:x1], y[y0:y1, x0:x1]
    seg = pts[1:] - pts[:-1]
    lens = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(lens)])
    total = max(cum[-1], 1e-6)
    b = best[y0:y1, x0:x1]
    ss = s[y0:y1, x0:x1]
    for i in range(len(seg)):
        ax, ay = pts[i]
        dx, dy = seg[i]
        t = np.clip(((sx - ax) * dx + (sy - ay) * dy) / max(lens[i] ** 2, 1e-6), 0.0, 1.0)
        d = np.hypot(sx - ax - t * dx, sy - ay - t * dy)
        m = d < b
        b = np.where(m, d, b)
        ss = np.where(m, (cum[i] + t * lens[i]) / total, ss)
    best[y0:y1, x0:x1] = b
    s[y0:y1, x0:x1] = ss
    return best, s


def spiral(cx, cy, r0, r1, a0, turns, n=160, cw=True, ease=1.0):
    t = np.linspace(0.0, 1.0, n) ** ease
    sign = 1.0 if cw else -1.0
    a = a0 + sign * turns * math.tau * t
    r = r0 + (r1 - r0) * t
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], axis=-1)


def brush_stroke(x, y, pts, w0, w1, taper=0.12):
    """Signed distance of a tapered brush stroke along pts, plus a 0..1
    'dome' height across the stroke for relief lighting."""
    d, s = polyline(x, y, pts, pad=max(w0, w1) + 4)
    width = (w0 + (w1 - w0) * s) * (0.35 + 0.65 * sstep(0.0, taper, s)) * (0.35 + 0.65 * sstep(1.0, 1.0 - taper, s))
    sd = d - width
    dome = np.sqrt(np.clip(1.0 - d / np.maximum(width, 1e-3), 0.0, 1.0))
    return sd, dome


def blur(a, r):
    """Approximate Gaussian blur: three separable box passes of radius r."""
    r = int(max(r, 1))
    out = a.astype(np.float32)
    for _ in range(3):
        for axis in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[axis] = (r + 1, r)
            p = np.pad(out, pad, mode="edge")
            c = np.cumsum(p, axis=axis)
            n = out.shape[axis]
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
            lo = np.take(c, np.arange(0, n), axis=axis)
            out = (hi - lo) / (2 * r + 1)
    return out


LIGHT = np.array([-0.45, -0.6, 0.66], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)


def relief(h, strength=1.0):
    gy, gx = np.gradient(h.astype(np.float32) * strength)
    n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    diff = np.clip(n @ LIGHT, 0.0, 1.0)
    spec = np.clip(n @ HALF, 0.0, 1.0) ** 40
    return diff, spec


def metal(base, h, strength=6.0, ambient=0.35, shine=0.9):
    diff, spec = relief(h, strength)
    col = base * (ambient + (1.0 - ambient) * 1.25 * diff)[..., None]
    col += (spec * shine)[..., None] * np.array([1.0, 0.94, 0.78], np.float32)
    return col


def over(dst, rgb, a):
    """Composite rgb with alpha a over the RGBA dst (straight alpha)."""
    a = np.clip(a, 0.0, 1.0)[..., None]
    da = dst[..., 3:4]
    out_a = a + da * (1.0 - a)
    safe = np.maximum(out_a, 1e-6)
    dst[..., :3] = (rgb * a + dst[..., :3] * da * (1.0 - a)) / safe
    dst[..., 3:4] = out_a
    return dst


def canvas(w, h):
    return np.zeros((h, w, 4), np.float32)


def lerp(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim and np.ndim(a) and np.ndim(a) > t.ndim:
        t = t[..., None]
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# reusable motifs
# ---------------------------------------------------------------------------

def xiangyun_paths(ox, oy, s, flip=False):
    """Auspicious-cloud curl polylines in a ~ (300 x 160) * s box."""
    fx = -1.0 if flip else 1.0

    def P(pts):
        pts = np.asarray(pts, np.float32)
        return np.stack([ox + fx * pts[:, 0] * s, oy + pts[:, 1] * s], axis=-1)

    big = spiral(0, 0, 62, 10, math.pi * 0.95, 1.35, cw=True, ease=0.85) + [95, 95]
    small = spiral(0, 0, 40, 7, math.pi * 0.05, 1.25, cw=False, ease=0.85) + [205, 100]
    top = spiral(0, 0, 30, 6, math.pi * 0.6, 1.2, cw=True, ease=0.85) + [150, 42]
    tail = np.array([[40, 150], [110, 158], [180, 150], [240, 140], [285, 124], [300, 108]], np.float32)
    return [(P(big), 11, 6), (P(small), 9, 5), (P(top), 7, 4), (P(tail), 9, 3)]


def draw_strokes(img, x, y, strokes, gold, outline=3.0, relief_strength=5.0):
    sd = np.full(x.shape, 1e6, np.float32)
    dome = np.zeros(x.shape, np.float32)
    for pts, w0, w1 in strokes:
        s, dm = brush_stroke(x, y, pts, w0, w1)
        dome = np.where(s < sd, dm, dome)
        sd = np.minimum(sd, s)
    edge = aa(sd - outline, 1.2)
    img = over(img, np.broadcast_to(np.array([0.22, 0.12, 0.04], np.float32), img[..., :3].shape), edge * 0.85)
    col = metal(gold, dome * 3.0, relief_strength)
    return over(img, col, aa(sd, 1.2))


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------

@register
def scroll_panel():
    """Horizontal rice-paper scroll with lacquered rollers and gold caps.
    9-slice margins: 84 left/right, 50 top/bottom."""
    W, H = 1024, 256
    x, y = grid(W, H)
    paper = paper_field(W, H, 0.3)
    n = noise_pack(W, H, (30.0, 4.0, 60.0))
    img = canvas(W, H)

    d = sd_box(x, y, W / 2, H / 2, 460, 94, 2) + (n[..., 0] - 0.5) * 6.0
    inside = -d
    age = 0.72 + 0.28 * sstep(0.0, 26.0, inside)
    stain = sstep(0.58, 0.75, n[..., 1]) * 0.12
    col = paper * age[..., None] * (1.0 - stain)[..., None]
    col = lerp(col, np.array([0.55, 0.42, 0.26], np.float32), stain * 0.4)
    # thin ink-wash rule inside top and bottom edges
    for yy in (48.0, H - 48.0):
        line = np.exp(-((y - yy) / 1.3) ** 2) * sstep(92, 130, x) * sstep(W - 92, W - 130, x)
        col = lerp(col, INK, line * (0.35 + 0.25 * n[..., 2]))
    img = over(img, col, aa(d, 1.5))

    # roller shadows onto paper
    rollers = np.zeros((H, W), np.float32)
    for cx in (42.0, W - 42.0):
        rollers = np.maximum(rollers, aa(sd_box(x, y, cx, H / 2, 24, 118, 6)))
    shadow = blur(np.roll(rollers, (4, 5), axis=(0, 1)), 6) * aa(d)
    img[..., :3] *= (1.0 - 0.45 * shadow)[..., None]

    wood = wood_field(W, H)
    gold = gold_field(W, H)
    for cx in (42.0, W - 42.0):
        u = np.clip((x - cx) / 22.0, -1.0, 1.0)
        cyl = np.sqrt(np.clip(1.0 - u * u, 0.0, 1.0))
        spec = np.exp(-((u + 0.38) / 0.12) ** 2)
        body_d = sd_box(x, y, cx, H / 2, 22, 106, 3)
        body = wood * (0.3 + 0.8 * cyl)[..., None] + (spec * 0.35)[..., None]
        img = over(img, body, aa(body_d))
        for cy in (18.0, H - 18.0):
            cap_d = sd_box(x, y, cx, cy, 27, 14, 7)
            uc = np.clip((x - cx) / 27.0, -1.0, 1.0)
            hc = np.sqrt(np.clip(1.0 - uc * uc, 0.0, 1.0)) * 8.0
            hc += np.cos((y - cy) * 0.9) * 0.6  # turned rings
            capcol = metal(gold, hc, 1.5)
            img = over(img, capcol, aa(cap_d))
    return img


@register
def paper_panel():
    """Square rice-paper panel with ink-wash border, for Theme panels.
    9-slice margins: 48."""
    S = 512
    x, y = grid(S, S)
    paper = paper_field(S, S, 1.7)
    n = noise_pack(S, S, (24.0, 5.0, 3.0))
    d = sd_box(x, y, S / 2, S / 2, S / 2 - 10, S / 2 - 10, 10) + (n[..., 0] - 0.5) * 7.0
    inside = -d
    wash = (1.0 - sstep(0.0, 40.0 + 20.0 * n[..., 2], inside)) * 0.55
    col = lerp(paper * (0.85 + 0.15 * sstep(0, 30, inside))[..., None], INK * 2.5, wash * 0.5)
    frame = np.exp(-((inside - 24.0) / 1.2) ** 2) * (0.5 + 0.5 * n[..., 1])
    col = lerp(col, INK, frame * 0.6)
    img = canvas(S, S)
    return over(img, col, aa(d, 1.5))


def plate(W, H, radius, fill, rim_w=5.0, rim_gold=None, inner_line=True):
    x, y = grid(W, H)
    gold = gold_field(W, H) if rim_gold is None else rim_gold
    d = sd_box(x, y, W / 2, H / 2, W / 2 - 3, H / 2 - 3, radius)
    img = canvas(W, H)
    # soft drop shadow
    sh = blur(aa(sd_box(x, y, W / 2 + 1, H / 2 + 2, W / 2 - 4, H / 2 - 4, radius)), 2)
    img = over(img, np.zeros((H, W, 3), np.float32), sh * 0.5)
    inside = -d
    dome = sstep(0.0, 18.0, inside)
    body = fill * (0.75 + 0.35 * dome)[..., None]
    body = lerp(body, fill * 1.6, np.exp(-((y - H * 0.18) / (H * 0.12)) ** 2) * 0.25 * aa(d))
    img = over(img, body, aa(d))
    rim_h = np.clip(1.0 - np.abs(inside - rim_w / 2.0) / (rim_w / 2.0), 0.0, 1.0)
    img = over(img, metal(gold, np.sqrt(rim_h) * 3.0, 3.0), aa(inside - rim_w, 1.0) * aa(d))
    if inner_line:
        line = np.exp(-((inside - rim_w - max(2.0, rim_w)) / 0.8) ** 2)
        img[..., :3] = lerp(img[..., :3], gold * 0.9, line * 0.8)
    return img


@register
def key_plate():
    """Small lacquer keycap for key hints, drawn 1:1. 9-slice margins: 12."""
    S = 64
    fill = np.full((S, S, 3), [0.07, 0.10, 0.09], np.float32)
    fill *= (0.85 + 0.3 * noise_pack(S, S, (10.0, 3.0, 25.0))[..., :1])
    return plate(S, S, 8, fill, rim_w=2.5)


@register
def prompt_plate():
    """Dark lacquer tooltip / prompt plate with gold rim and cloud tips.
    9-slice margins: 40 left/right, 28 top/bottom."""
    W, H = 512, 128
    n = noise_pack(W, H, (10.0, 3.0, 60.0))
    fill = np.array([0.045, 0.075, 0.07], np.float32) * (0.8 + 0.4 * n[..., :1])
    return plate(W, H, 22, fill, rim_w=5.0)


@register
def button_normal():
    W, H = 256, 96
    n = noise_pack(W, H, (10.0, 3.0, 60.0))
    fill = np.array([0.06, 0.10, 0.09], np.float32) * (0.85 + 0.3 * n[..., :1])
    return plate(W, H, 18, fill, rim_w=4.0)


@register
def button_hover():
    W, H = 256, 96
    fill = jade_field(W, H, 2.1, dark=True) * 1.3
    return plate(W, H, 18, fill, rim_w=4.0)


@register
def button_pressed():
    W, H = 256, 96
    fill = jade_field(W, H, 4.2, dark=True) * 0.7
    return plate(W, H, 18, fill, rim_w=4.0, inner_line=False)


@register
def jade_plaque():
    """Vertical jade tablet with gold rim, carved groove and ruyi curls."""
    W, H = 256, 512
    x, y = grid(W, H)
    jade = jade_field(W, H, 0.8)
    gold = gold_field(W, H)
    n = noise_pack(W, H, (6.0, 2.0, 30.0))
    img = canvas(W, H)
    cx, cy, hw, hh = W / 2, H / 2, W / 2 - 8, H / 2 - 8
    d = np.maximum(sd_box(x, y, cx, cy, hw, hh, 14),
                   (np.abs(x - cx) + np.abs(y - cy) - (hw + hh - 34)) / math.sqrt(2))
    sh = blur(aa(d - 2), 5)
    img = over(img, np.zeros((H, W, 3), np.float32), np.roll(sh, (6, 4), axis=(0, 1)) * 0.55)
    inside = -d
    # translucent jade: brighter core, darker toward the rim, darker centre
    dome = sstep(0.0, 60.0, inside)
    body = jade * (0.55 + 0.45 * dome)[..., None]
    body *= (0.78 + 0.22 * np.abs((y - cy) / hh))[..., None]
    diff, spec = relief(dome * 20.0, 1.0)
    body += (spec * 0.25)[..., None]
    sheen = np.exp(-(((x - cx * 0.7) / 30.0) ** 2)) * 0.08 * dome
    body += sheen[..., None]
    img = over(img, body, aa(d))
    # carved groove
    groove = inside - 24.0
    img[..., :3] *= (1.0 - 0.45 * np.exp(-(groove / 1.3) ** 2))[..., None]
    img[..., :3] += (0.18 * np.exp(-((groove + 2.0) / 1.0) ** 2))[..., None] * np.array([0.6, 0.9, 0.8])
    # gold rim
    rim_h = np.clip(1.0 - np.abs(inside - 6.0) / 6.0, 0.0, 1.0)
    img = over(img, metal(gold, np.sqrt(rim_h) * 4.0, 3.0), aa(inside - 12.0, 1.0) * aa(d))
    # ruyi curls top and bottom
    strokes = []
    for (oy, fy) in ((56.0, 1.0), (H - 56.0, -1.0)):
        for flip in (False, True):
            sp = spiral(0, 0, 18, 4, math.pi * (0.5 if fy > 0 else 1.5), 1.1, cw=not flip if fy > 0 else flip, ease=0.9)
            sp = sp + [cx + (-22 if not flip else 22), oy]
            strokes.append((sp, 4.5, 2.5))
        strokes.append((np.array([[cx - 44, oy + fy * 22], [cx, oy + fy * 30], [cx + 44, oy + fy * 22]]), 3.5, 3.5))
    img = draw_strokes(img, x, y, strokes, gold, outline=2.0, relief_strength=3.0)
    img[..., :3] *= (0.92 + 0.08 * n[..., 2:3])
    return img


@register
def seal_stamp():
    """Vermilion seal-paste square with worn edges and a reversed border.
    A calligraphy glyph is laid over it in-engine."""
    S = 256
    x, y = grid(S, S)
    red = vermilion_field(S, S)
    n = noise_pack(S, S, (14.0, 40.0, 5.0), seed=3.0)
    d = sd_box(x, y, S / 2, S / 2, 108, 108, 12) + (n[..., 0] - 0.5) * 12.0
    inside = -d
    border = np.exp(-((inside - 16.0) / 3.2) ** 4)
    a = aa(d, 1.5)
    a *= 1.0 - border * 0.92
    worn = sstep(0.60, 0.72, n[..., 1]) * 0.8 + sstep(0.62, 0.8, n[..., 2]) * 0.35
    a *= np.clip(1.0 - worn, 0.0, 1.0)
    a *= 0.82 + 0.18 * n[..., 2]
    img = canvas(S, S)
    return over(img, red, a)


@register
def ink_stroke():
    """Tapered dry-brush ink underline."""
    W, H = 1024, 128
    x, y = grid(W, H)
    n = noise_pack(W, H, (5.0, 3.0, 20.0), stretch=(0.08, 3.0), seed=1.0)
    n2 = noise_pack(W, H, (10.0, 2.0, 50.0), seed=7.0)
    s = np.clip((x - 24.0) / (W - 48.0), 0.0, 1.0)
    yc = H / 2 + 8.0 * np.sin(s * math.pi * 1.15 + 0.3) - 6.0 * s
    press = 1.0 + 0.5 * np.exp(-((s - 0.04) / 0.05) ** 2)
    half = (32.0 * (1.0 - 0.7 * s ** 1.4)) * press * sstep(0.0, 0.03, s)
    half *= 1.0 + (n2[..., 0] - 0.5) * 0.5
    d = np.abs(y - yc) - half
    inx = sstep(0.0, 12.0, x) * sstep(W, W - 8.0, x)
    body = aa(d, 2.0) * inx
    dry = sstep(0.2 + 0.45 * s, 0.3 + 0.45 * s, n[..., 0] + 0.2 * (1.0 - s))
    body *= 0.25 + 0.75 * dry
    body = np.maximum(body * (0.8 + 0.2 * n[..., 2]), 0.0)
    halo = blur(body, 5) * 0.28 * (1.0 - s)
    a = np.clip(np.maximum(body * 0.95, halo), 0.0, 1.0)
    col = np.broadcast_to(INK, (H, W, 3)) + (1.0 - body)[..., None] * 0.08
    img = canvas(W, H)
    return over(img, col, a)


@register
def cloud_ornament():
    """Gold xiangyun (auspicious cloud) curl."""
    W, H = 512, 256
    x, y = grid(W, H)
    gold = gold_field(W, H)
    img = canvas(W, H)
    strokes = xiangyun_paths(90, 40, 1.25)
    return draw_strokes(img, x, y, strokes, gold, outline=3.0)


@register
def gold_corner():
    """Gold filigree corner (top-left orientation; flip for the others)."""
    S = 256
    x, y = grid(S, S)
    gold = gold_field(S, S)
    img = canvas(S, S)
    strokes = [
        (np.array([[26, 150], [22, 90], [30, 52], [52, 30], [90, 22], [150, 26], [230, 22]], np.float32), 6.0, 2.0),
        (np.array([[26, 150], [20, 230]], np.float32), 5.0, 2.0),
        (spiral(0, 0, 26, 5, math.pi * 1.25, 1.3, cw=True, ease=0.85) + [78, 78], 6.0, 3.0),
        (spiral(0, 0, 14, 3, math.pi * 0.0, 1.1, cw=False, ease=0.9) + [150, 50], 4.0, 2.5),
        (spiral(0, 0, 14, 3, math.pi * 1.5, 1.1, cw=True, ease=0.9) + [50, 150], 4.0, 2.5),
    ]
    img = draw_strokes(img, x, y, strokes, gold, outline=2.5, relief_strength=4.0)
    dot = sd_circle(x, y, 46, 46, 7)
    img = over(img, metal(VERMILION * np.ones((S, S, 3), np.float32), np.sqrt(np.clip(-dot / 7.0, 0, 1)) * 6.0, 2.0), aa(dot))
    return img


def _ring_parts(S, x, y):
    r = np.hypot(x - S / 2, y - S / 2)
    ang = np.arctan2(x - S / 2, -(y - S / 2))  # 0 at top, clockwise
    return r, ang


@register
def qi_ring_under():
    """Radial qi gauge background: dark jade track, gold rims, ink core."""
    S = 512
    x, y = grid(S, S)
    r, ang = _ring_parts(S, x, y)
    jade = jade_field(S, S, 5.0, dark=True)
    gold = gold_field(S, S)
    n = noise_pack(S, S, (4.0, 10.0, 30.0))
    img = canvas(S, S)
    shadow = blur(aa(r - 246.0), 6)
    img = over(img, np.zeros((S, S, 3), np.float32), np.roll(shadow, (5, 3), axis=(0, 1)) * 0.5)
    core = jade * 0.55 * (0.7 + 0.3 * sstep(170, 40, r))[..., None]
    core = lerp(core, INK, 0.35 + 0.25 * n[..., 0])
    img = over(img, core, aa(r - 172.0) * 0.92)
    track = jade * (0.35 + 0.25 * sstep(228, 190, r))[..., None]
    img = over(img, track, aa(r - 228.0) * aa(186.0 - r))
    # inner hairline and 24 carved marks on the core edge
    img[..., :3] = lerp(img[..., :3], gold, np.exp(-((r - 152.0) / 1.0) ** 2) * 0.7)
    return _ring_rims(img, x, y, r, ang, gold)


def _ring_rims(img, x, y, r, ang, gold):
    for r0, r1 in ((228.0, 246.0), (172.0, 188.0)):
        mid, half = (r0 + r1) / 2, (r1 - r0) / 2
        h = np.sqrt(np.clip(1.0 - np.abs(r - mid) / half, 0.0, 1.0)) * 4.0
        img = over(img, metal(gold, h, 3.0), aa(r - r1) * aa(r0 - r))
    # 24 notches on the outer rim, heavier every 90 degrees
    k = ang / (math.tau / 24.0)
    dist = np.abs(k - np.round(k)) * (math.tau / 24.0) * r
    major = (np.round(k) % 6 == 0)
    width = np.where(major, 2.6, 1.3)
    notch = aa(dist - width, 1.0) * aa(r - 245.0) * aa(230.0 - r)
    img[..., :3] = lerp(img[..., :3], np.array([0.20, 0.11, 0.03], np.float32), notch * 0.85)
    return img


@register
def qi_ring_over():
    """Gold rims only, laid over the radial fill so its edges sit in a groove."""
    S = 512
    x, y = grid(S, S)
    r, ang = _ring_parts(S, x, y)
    img = canvas(S, S)
    img = _ring_rims(img, x, y, r, ang, gold_field(S, S))
    # a faint glassy highlight across the top of the track
    hl = np.exp(-((r - 214.0) / 7.0) ** 2) * sstep(0.2, -0.9, np.cos(ang + 0.0) * -1.0) * 0.18
    return over(img, np.ones((S, S, 3), np.float32), hl * aa(r - 228.0) * aa(188.0 - r))


@register
def qi_ring_fill():
    """Luminous flowing jade qi for the radial fill."""
    S = 512
    x, y = grid(S, S)
    r, ang = _ring_parts(S, x, y)

    def build(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        cx, cy = nb.sub(u, 0.5), nb.sub(v, 0.5)
        rad = nb.math("SQRT", nb.add(nb.mul(cx, cx), nb.mul(cy, cy)))
        a = nb.math("ARCTAN2", cy, cx)
        # swirl: sample noise along angle so the qi appears to flow around
        # sample on a circle (cos/sin of the angle) so there is no seam
        swirl = nb.add(a, nb.mul(rad, 6.0))
        p = nb.vec(nb.mul(nb.math("COSINE", swirl), 1.6), nb.mul(nb.math("SINE", swirl), 1.6), nb.mul(rad, 16.0))
        f = nb.noise(p, 2.5, 6.0, 0.6, distortion=1.2)
        return nb.ramp(f, [(0.25, (0.10, 0.55, 0.42)), (0.5, (0.30, 0.88, 0.66)),
                           (0.7, (0.62, 1.0, 0.84)), (0.85, (0.92, 1.0, 0.95))])
    qi = field(build, S, S)
    band = np.clip(1.0 - np.abs(r - 207.0) / 21.0, 0.0, 1.0)
    col = qi * (0.7 + 0.45 * band)[..., None]
    img = canvas(S, S)
    return over(img, col, aa(r - 229.0) * aa(185.0 - r))


@register
def qi_ring_glow():
    """Soft halo around the ring, pulsed when qi is full."""
    S = 512
    x, y = grid(S, S)
    r, _ = _ring_parts(S, x, y)
    a = np.exp(-((r - 210.0) / 34.0) ** 2) * 0.85
    a *= aa(r - 254.0, 6.0)
    col = np.broadcast_to(np.array([0.55, 1.0, 0.82], np.float32), (S, S, 3))
    img = canvas(S, S)
    return over(img, col, a)


TRIGRAMS = [(1, 1, 1), (0, 1, 1), (0, 1, 0), (0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1), (1, 1, 0)]


@register
def sundial_face():
    """Rotating shichen dial: paper band for the twelve branches (glyphs are
    labels in-engine), jade bagua ring with gold trigrams, taiji centre."""
    S = 512
    x, y = grid(S, S)
    r, ang = _ring_parts(S, x, y)
    paper = paper_field(S, S, 2.5)
    jade = jade_field(S, S, 3.3, dark=True)
    gold = gold_field(S, S)
    n = noise_pack(S, S, (6.0, 20.0, 3.0))
    img = canvas(S, S)
    # paper band 166..234
    band = paper * (0.82 + 0.18 * sstep(234, 200, r))[..., None]
    img = over(img, band, aa(r - 234.0))
    # twelve sector dividers (between branches) + 24 hour ticks + 96 ke ticks
    for count, rin, width, alpha in ((12, 170, 1.4, 0.8), (24, 222, 1.1, 0.75), (96, 228, 0.7, 0.5)):
        off = 0.5 if count == 12 else 0.0
        k = ang / (math.tau / count) - off
        dist = np.abs(k - np.round(k)) * (math.tau / count) * r
        tick = aa(dist - width, 1.0) * sstep(rin - 1, rin + 1, r) * aa(r - 232.0)
        img[..., :3] = lerp(img[..., :3], INK, tick * alpha)
    for rr in (170.0, 230.0):
        img[..., :3] = lerp(img[..., :3], INK, np.exp(-((r - rr) / 1.0) ** 2) * 0.8)
    # vermilion dots marking noon (Wu, bottom of dial = 180 deg) and midnight
    for a0, c in ((math.pi, VERMILION), (0.0, INK)):
        px, py = S / 2 + 175.0 * math.sin(a0), S / 2 - 175.0 * math.cos(a0)
        img = over(img, np.broadcast_to(c, (S, S, 3)), aa(sd_circle(x, y, px, py, 4.0)))
    # jade bagua ring 100..166
    ring = jade * (0.6 + 0.4 * sstep(100, 166, r))[..., None]
    img = over(img, ring, aa(r - 166.0))
    trig = np.zeros((S, S), np.float32)
    for i, lines in enumerate(TRIGRAMS):
        a0 = i * math.tau / 8.0
        da = np.angle(np.exp(1j * (ang - a0)))
        tang = da * r  # arc-length offset from the trigram's axis
        for j, solid in enumerate(lines):
            rr = 114.0 + j * 16.0
            seg = np.maximum(np.abs(tang) - 19.0, np.abs(r - rr) - 4.0)
            if not solid:
                seg = np.maximum(seg, 4.0 - np.abs(tang))
            trig = np.maximum(trig, aa(seg, 1.0))
    img = over(img, metal(gold, blur(trig, 1) * 3.0, 2.0), trig)
    # gold rings
    for rr, w in ((166.0, 3.0), (100.0, 3.0)):
        h = np.sqrt(np.clip(1.0 - np.abs(r - rr) / w, 0.0, 1.0)) * 3.0
        img = over(img, metal(gold, h, 2.0), aa(np.abs(r - rr) - w))
    # taiji centre
    cx, cy, R = S / 2, S / 2, 96.0
    px, py = x - cx, y - cy
    yin = (px > 0)
    yin = np.where(np.hypot(px, py + R / 2) < R / 2, False, yin)
    yin = np.where(np.hypot(px, py - R / 2) < R / 2, True, yin)
    yin = np.where(np.hypot(px, py + R / 2) < R / 7, True, yin)
    yin = np.where(np.hypot(px, py - R / 2) < R / 7, False, yin)
    yin_f = blur(yin.astype(np.float32), 1)
    light = paper * 0.95
    dark = lerp(INK[None, None, :] * np.ones((S, S, 3), np.float32), jade * 0.4, 0.4)
    taiji = lerp(light, dark, yin_f)
    img = over(img, taiji, aa(r - R))
    img[..., :3] *= (0.94 + 0.06 * n[..., 2:3])
    return img


@register
def sundial_frame():
    """Static bronze-gold bezel with a vermilion flame pointer at the top."""
    S = 512
    x, y = grid(S, S)
    r, ang = _ring_parts(S, x, y)
    gold = gold_field(S, S)
    img = canvas(S, S)
    sh = blur(aa(r - 252.0) * aa(228.0 - r), 5)
    img = over(img, np.zeros((S, S, 3), np.float32), np.roll(sh, (5, 3), axis=(0, 1)) * 0.5)
    h = np.sqrt(np.clip(1.0 - np.abs(r - 241.0) / 12.0, 0.0, 1.0)) * 5.0
    h += np.cos(r * 1.4) * 0.4
    bronze = gold * np.array([0.9, 0.82, 0.7], np.float32)
    img = over(img, metal(bronze, h, 3.0), aa(r - 253.0) * aa(229.0 - r))
    # pointer: flame / teardrop hanging into the paper band
    px, py = x - S / 2, y
    tip_y = 42.0
    hw = 11.0 * np.clip((tip_y - py) / 28.0, 0.0, 1.0) ** 0.7
    d = np.abs(px) - hw
    d = np.where(py > tip_y, np.hypot(px, py - tip_y), d)
    d = np.minimum(d, sd_circle(x, y, S / 2, 14.0, 12.0))
    img = over(img, np.broadcast_to(np.array([0.25, 0.12, 0.03], np.float32), (S, S, 3)), aa(d - 2.5))
    dome = np.sqrt(np.clip(-d / 10.0, 0.0, 1.0)) * 5.0
    img = over(img, metal(vermilion_field(S, S), dome, 2.0, ambient=0.5), aa(d))
    return img


def _icon_canvas(S=128):
    x, y = grid(S, S)
    return x, y, canvas(S, S)


@register
def icon_qi():
    S = 128
    x, y, img = _icon_canvas(S)
    jade = jade_field(S, S, 6.0) * 1.15
    gold = gold_field(S, S)
    cx, cy, R = 64.0, 80.0, 34.0
    t = np.clip((y - 10.0) / (cy - 10.0), 0.0, 1.0)
    hw = R * np.sqrt(np.clip(1.0 - (1.0 - t) ** 2, 0.0, 1.0)) * t ** 0.35
    d_up = np.where(y < cy, np.abs(x - cx) - hw, 1e3)
    d = np.minimum(d_up, sd_circle(x, y, cx, cy, R))
    d = np.where(y < 10.0, np.maximum(d, 10.0 - y), d)
    img = over(img, np.broadcast_to(np.array([0.1, 0.18, 0.12], np.float32), (S, S, 3)), aa(d - 3.0) * 0.9)
    dome = blur(aa(d), 6) * 14.0
    img = over(img, metal(jade, dome, 1.0, ambient=0.55, shine=1.2), aa(d))
    strokes = [(spiral(0, 0, 18, 3, math.pi * 0.2, 1.2, cw=False, ease=0.9) + [cx + 2, cy + 2], 3.0, 1.5)]
    img = draw_strokes(img, x, y, strokes, gold, outline=1.0, relief_strength=2.0)
    return img


@register
def icon_sword():
    S = 128
    x, y, img = _icon_canvas(S)
    gold = gold_field(S, S)
    # rotate coordinates 45 degrees so the jian lies diagonally
    c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
    u = (x - 64) * c + (y - 64) * s
    v = -(x - 64) * s + (y - 64) * c + 64
    ux = u  # across blade
    blade_hw = 5.5 * np.clip((v - 4.0) / 14.0, 0.0, 1.0) ** 0.6
    d_blade = np.maximum(np.abs(ux) - blade_hw, np.maximum(4.0 - v, v - 86.0))
    steel = np.broadcast_to(np.array([0.78, 0.84, 0.86], np.float32), (S, S, 3))
    ridge = np.clip(1.0 - np.abs(ux) / np.maximum(blade_hw, 1e-3), 0.0, 1.0) * 4.0
    img = over(img, np.zeros((S, S, 3), np.float32), aa(d_blade - 2.0) * 0.8)
    img = over(img, metal(steel, ridge, 1.0, ambient=0.45), aa(d_blade))
    d_guard = sd_box(ux, v, 0.0, 90.0, 17.0, 4.5, 3.0)
    d_hilt = sd_box(ux, v, 0.0, 104.0, 4.0, 10.0, 2.0)
    d_pom = sd_circle(ux, v, 0.0, 118.0, 5.0)
    wrap = np.broadcast_to(np.array([0.12, 0.10, 0.09], np.float32), (S, S, 3)) * (0.8 + 0.4 * (np.sin(v * 1.8) > 0))[..., None]
    img = over(img, np.zeros((S, S, 3), np.float32), aa(np.minimum(np.minimum(d_guard, d_hilt), d_pom) - 1.8) * 0.8)
    img = over(img, wrap, aa(d_hilt))
    gd = np.minimum(d_guard, d_pom)
    img = over(img, metal(gold, np.sqrt(np.clip(-gd / 4.0, 0, 1)) * 3.0, 2.0), aa(gd))
    # vermilion tassel
    def to_xy(uu, vv):
        return [64 + uu * c - (vv - 64) * s, 64 + uu * s + (vv - 64) * c]
    tassel = np.array([to_xy(0, 122), [22, 110], [16, 122], [14, 126]], np.float32)
    ts, _ = brush_stroke(x, y, tassel, 3.2, 2.0, taper=0.15)
    img = over(img, np.broadcast_to(VERMILION, (S, S, 3)), aa(ts))
    return img


@register
def icon_lotus():
    S = 128
    x, y, img = _icon_canvas(S)
    bx, by = 64.0, 96.0
    petals = [(-70, 30, 0.8), (70, 30, 0.8), (-38, 38, 0.92), (38, 38, 0.92), (0, 44, 1.0)]
    for angle_deg, length, shade in petals:
        a = math.radians(angle_deg)
        # petal axis points up (negative y) rotated by angle
        ax, ay = math.sin(a), -math.cos(a)
        px, py = x - bx, y - by
        along = px * ax + py * ay
        across = -px * ay + py * ax
        t = np.clip(along / (length * 2.0), 0.0, 1.0)
        width = 15.0 * np.clip(np.sin(t * math.pi), 0.0, 1.0) ** 0.8 + 0.5
        d = np.maximum(np.abs(across) - width, np.maximum(-along, along - length * 2.0))
        col = lerp(np.array([0.93, 0.55, 0.62], np.float32) * np.ones((S, S, 3), np.float32),
                   np.array([1.0, 0.93, 0.9], np.float32), t)
        col = col * (0.7 + 0.3 * shade) * (0.75 + 0.25 * np.clip(1 - np.abs(across) / np.maximum(width, 1), 0, 1))[..., None]
        img = over(img, np.broadcast_to(np.array([0.35, 0.08, 0.14], np.float32), (S, S, 3)), aa(d - 1.8) * 0.8)
        img = over(img, col, aa(d))
    leaf = sd_box(x, y, 64, 104, 44, 6, 6)
    jade = jade_field(S, S, 9.0)
    img = over(img, np.broadcast_to(np.array([0.04, 0.12, 0.08], np.float32), (S, S, 3)), aa(leaf - 1.8))
    img = over(img, jade, aa(leaf))
    return img


@register
def icon_sun():
    S = 128
    x, y, img = _icon_canvas(S)
    r, ang = _ring_parts(S, x, y)
    gold = gold_field(S, S)
    k = ang / (math.tau / 12.0)
    ray_w = np.abs(k - np.round(k)) * (math.tau / 12.0) * r
    d_ray = np.maximum(ray_w - 5.0 * np.clip((56.0 - r) / 22.0, 0.0, 1.0), np.maximum(r - 58.0, 30.0 - r))
    img = over(img, metal(gold, blur(aa(d_ray), 2) * 3.0, 2.0), aa(d_ray))
    d = r - 32.0
    img = over(img, np.broadcast_to(np.array([0.3, 0.1, 0.03], np.float32), (S, S, 3)), aa(d - 2.0))
    img = over(img, metal(gold, np.sqrt(np.clip(-d / 6.0, 0, 1)) * 3.0, 2.0), aa(d))
    inner = r - 26.0
    img = over(img, metal(vermilion_field(S, S), np.sqrt(np.clip(-inner / 26.0, 0, 1)) * 10.0, 1.0, ambient=0.6), aa(inner))
    return img


@register
def icon_moon():
    S = 128
    x, y, img = _icon_canvas(S)
    n = noise_pack(S, S, (10.0, 25.0, 4.0), seed=5.0)
    glow = np.exp(-((np.hypot(x - 64, y - 64) - 30.0) / 14.0) ** 2) * 0.35
    img = over(img, np.broadcast_to(np.array([0.75, 0.85, 1.0], np.float32), (S, S, 3)), glow)
    d = np.maximum(sd_circle(x, y, 64, 64, 40), -sd_circle(x, y, 84, 52, 36))
    silver = np.array([0.86, 0.9, 0.96], np.float32) * (0.78 + 0.3 * n[..., :1]) * (1.0 - 0.18 * sstep(0.55, 0.7, n[..., 1:2]))
    img = over(img, np.broadcast_to(np.array([0.12, 0.16, 0.26], np.float32), (S, S, 3)), aa(d - 2.0))
    img = over(img, silver, aa(d))
    return img


@register
def vignette():
    """Ink-wash edge vignette stretched over the whole screen."""
    W, H = 1024, 576
    x, y = grid(W, H)
    n = noise_pack(W, H, (3.0, 8.0, 1.6), seed=2.0)
    ex = (x / W - 0.5) * 2.0
    ey = (y / H - 0.5) * 2.0
    v = np.sqrt((np.abs(ex) ** 2.6 + np.abs(ey) ** 2.6)) ** (1 / 1.3)
    v = v + (n[..., 0] - 0.5) * 0.55 + (n[..., 1] - 0.5) * 0.18
    a = sstep(0.8, 1.6, v) * 0.92
    edge = np.minimum(np.minimum(x, W - x) / W, np.minimum(y, H - y) / H)
    a = np.maximum(a, sstep(0.05, 0.0, edge + (n[..., 2] - 0.5) * 0.04) * 0.6)
    col = lerp(np.broadcast_to(INK, (H, W, 3)), np.array([0.08, 0.13, 0.12], np.float32), n[..., 2])
    img = canvas(W, H)
    return over(img, col, a)


# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    filt = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ""
    xg.reset_scene()
    for name, fn in ASSETS:
        if filt and filt not in name:
            continue
        xg.log("ui:", name)
        img = fn()
        path = os.path.join(OUT_DIR, name + ".png")
        xg.save_png(np.ascontiguousarray(img[::-1]), path, alpha=True)
    xg.log("done")


if __name__ == "__main__":
    main()
