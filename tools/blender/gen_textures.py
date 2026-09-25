"""Generates the 100 tileable textures under assets/textures/.

Each texture is a Blender procedural shader graph (noise / voronoi / wave /
brick nodes) baked to an image with Cycles, then made seamless. Normal maps
are derived from a separately baked height graph.

    python3.11 tools/blender/gen_textures.py [name-filter]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import xg_common as xg  # noqa: E402

SIZE = (1024, 1024)
TEXTURES = []  # (name, fn) where fn() -> list of (suffix, array, alpha)


def register(fn):
    TEXTURES.append((fn.__name__, fn))
    return fn


# ---------------------------------------------------------------------------
# small shared building blocks
# ---------------------------------------------------------------------------

def suv(nb, sx, sy=None):
    sy = sx if sy is None else sy
    return nb.vmath("MULTIPLY", nb.uv(), nb.vec(sx, sy, 1.0))


def offs(nb, v, ox, oy=0.0, oz=0.0):
    return nb.vmath("ADD", v, nb.vec(ox, oy, oz))


def rot(nb, v, angle):
    n = nb._new("ShaderNodeVectorRotate", rotation_type="Z_AXIS")
    nb._set(n.inputs["Vector"], v)
    nb._set(n.inputs["Angle"], angle)
    return n.outputs[0]


def fract(nb, x):
    return nb.math("FRACT", x)


def bake(build, size=SIZE, seamless=True):
    arr = xg.bake_graph(build, size)
    return xg.make_seamless(arr) if seamless else arr


def pair(color_fn, height_fn, strength=4.0, size=SIZE, seamless=True):
    col = bake(color_fn, size, seamless)[..., :3]
    h = bake(height_fn, size, seamless)[..., 0]
    return [("albedo", col, False), ("normal", xg.normal_from_height(h, strength), False)]


def rgba(color_fn, alpha_fn, size=SIZE, seamless=False, suffix="albedo"):
    col = bake(color_fn, size, seamless)[..., :3]
    a = bake(alpha_fn, size, seamless)[..., :1]
    # Fill transparent texels with the mean opaque colour so mipmaps and
    # bilinear filtering don't bleed a dark fringe around cut-out edges.
    solid = a[..., 0] > 0.5
    if solid.any():
        col = np.where(solid[..., None], col, col[solid].mean(axis=0))
    return [(suffix, np.concatenate([col, a], axis=-1), True)]


def single(color_fn, size=SIZE, seamless=True, suffix=None):
    return [(suffix, bake(color_fn, size, seamless)[..., :3], False)]


def speckle(nb, v, scale, thresh=0.08):
    """Small dots: 1 inside, 0 outside."""
    d = nb.voronoi(v, scale, rand=1.0)
    return nb.math("LESS_THAN", d, thresh)


def leaf_cells(nb, scale, a, b, tip=0.35, jitter=1.0, rand_angle=3.14):
    """Scattered leaf shapes inside voronoi cells.
    Returns (mask, cell_color, local_y, local_x)."""
    v = suv(nb, scale)
    vn = nb._new("ShaderNodeTexVoronoi", feature="F1")
    nb._set(vn.inputs["Vector"], v)
    nb._set(vn.inputs["Scale"], 1.0)
    nb._set(vn.inputs["Randomness"], jitter)
    center = vn.outputs["Position"]
    cell = vn.outputs["Color"]
    local = nb.vmath("SUBTRACT", v, center)
    ang = nb.mul(nb.gray(cell), rand_angle * 2.0)
    local = rot(nb, local, ang)
    lx, ly, _ = nb.xyz(local)
    # teardrop: narrower toward +y tip
    taper = nb.maprange(ly, -b, b, 1.0, tip)
    ex = nb.math("DIVIDE", lx, nb.mul(taper, a))
    ey = nb.math("DIVIDE", ly, b)
    r = nb.vmath("LENGTH", nb.vec(ex, ey, 0.0))
    mask = nb.math("LESS_THAN", r, 1.0)
    return mask, cell, ly, lx, r


# ---------------------------------------------------------------------------
# TERRAIN (albedo + normal)
# ---------------------------------------------------------------------------

@register
def terrain_grass():
    def col(nb):
        uv = nb.uv()
        base = nb.ramp(nb.noise(uv, 3.0, 6, 0.55), [
            (0.30, (0.13, 0.30, 0.09)), (0.50, (0.24, 0.44, 0.13)), (0.72, (0.46, 0.55, 0.20))])
        blades = nb.noise(suv(nb, 90, 14), 1.0, 8, 0.7, distortion=0.4)
        bl = nb.ramp(blades, [(0.35, (0.55, 0.62, 0.52)), (0.62, (1.1, 1.08, 0.95))])
        c = nb.mix(base, bl, 1.0, "MULTIPLY")
        tips = nb.smooth(0.62, 0.8, nb.noise(suv(nb, 140, 40), 1.0, 4, 0.6))
        c = nb.mix(c, nb.rgb(0.70, 0.72, 0.36), nb.mul(tips, 0.45))
        dry = nb.smooth(0.55, 0.75, nb.noise(offs(nb, uv, 7.1), 6.0, 5, 0.6))
        c = nb.mix(c, nb.rgb(0.58, 0.52, 0.26), nb.mul(dry, 0.35))
        clover = speckle(nb, suv(nb, 45), 1.0, 0.12)
        return nb.mix(c, nb.rgb(0.20, 0.42, 0.14), nb.mul(clover, 0.6))

    def hgt(nb):
        return nb.add(nb.mul(nb.noise(suv(nb, 90, 14), 1.0, 8, 0.7, distortion=0.4), 0.8),
                      nb.mul(nb.noise(nb.uv(), 12.0, 4), 0.2))
    return pair(col, hgt, 5.0)


@register
def terrain_meadow():
    def col(nb):
        uv = nb.uv()
        base = nb.ramp(nb.noise(uv, 4.0, 6, 0.6), [
            (0.3, (0.22, 0.40, 0.12)), (0.55, (0.38, 0.52, 0.16)), (0.8, (0.56, 0.60, 0.24))])
        streak = nb.ramp(nb.noise(suv(nb, 70, 18), 1.0, 7, 0.65), [(0.3, (0.6, 0.66, 0.55)), (0.7, (1.1, 1.1, 1.0))])
        c = nb.mix(base, streak, 1.0, "MULTIPLY")
        fl1 = speckle(nb, suv(nb, 38), 1.0, 0.06)
        fl2 = speckle(nb, offs(nb, suv(nb, 31), 3.3), 1.0, 0.05)
        fl3 = speckle(nb, offs(nb, suv(nb, 27), 9.1), 1.0, 0.045)
        patch = nb.smooth(0.45, 0.6, nb.noise(offs(nb, uv, 2.2), 5.0, 3))
        c = nb.mix(c, nb.rgb(0.96, 0.93, 0.80), nb.mul(fl1, patch))
        c = nb.mix(c, nb.rgb(0.95, 0.60, 0.72), nb.mul(fl2, patch))
        return nb.mix(c, nb.rgb(0.98, 0.80, 0.25), nb.mul(fl3, nb.sub(1.0, patch)))

    def hgt(nb):
        return nb.add(nb.noise(suv(nb, 70, 18), 1.0, 7, 0.65),
                      nb.mul(speckle(nb, suv(nb, 38), 1.0, 0.06), 0.5))
    return pair(col, hgt, 4.0)


@register
def terrain_moss():
    def col(nb):
        uv = nb.uv()
        n = nb.noise(uv, 18.0, 10, 0.7, distortion=0.3)
        c = nb.ramp(n, [(0.25, (0.10, 0.22, 0.07)), (0.5, (0.22, 0.40, 0.10)), (0.75, (0.48, 0.60, 0.18))])
        clumps = nb.voronoi(suv(nb, 60), 1.0, feature="F1")
        c = nb.mix(c, nb.rgb(0.08, 0.16, 0.05), nb.mul(nb.smooth(0.2, 0.55, clumps), 0.5))
        spores = speckle(nb, suv(nb, 150), 1.0, 0.12)
        return nb.mix(c, nb.rgb(0.75, 0.70, 0.30), nb.mul(spores, 0.5))

    def hgt(nb):
        return nb.sub(1.0, nb.add(nb.mul(nb.voronoi(suv(nb, 60), 1.0), 0.7), nb.mul(nb.noise(nb.uv(), 18, 10, 0.7), 0.3)))
    return pair(col, hgt, 5.0)


@register
def terrain_dirt():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 6.0, 8, 0.6), [
            (0.3, (0.26, 0.18, 0.11)), (0.55, (0.42, 0.31, 0.19)), (0.8, (0.56, 0.44, 0.29))])
        grit = nb.ramp(nb.noise(uv, 180.0, 3, 0.5), [(0.3, (0.7, 0.7, 0.7)), (0.7, (1.15, 1.12, 1.1))])
        c = nb.mix(c, grit, 1.0, "MULTIPLY")
        peb = nb.math("LESS_THAN", nb.voronoi(suv(nb, 40), 1.0), 0.18)
        return nb.mix(c, nb.rgb(0.55, 0.50, 0.44), nb.mul(peb, 0.6))

    def hgt(nb):
        peb = nb.smooth(0.25, 0.0, nb.voronoi(suv(nb, 40), 1.0))
        return nb.add(nb.mul(peb, 0.6), nb.mul(nb.noise(nb.uv(), 30, 8), 0.4))
    return pair(col, hgt, 4.0)


@register
def terrain_forest_floor():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 8.0, 8, 0.6), [
            (0.3, (0.18, 0.12, 0.07)), (0.6, (0.33, 0.22, 0.12)), (0.85, (0.45, 0.33, 0.16))])
        mask, cell, ly, lx, r = leaf_cells(nb, 22.0, 0.22, 0.40)
        leafc = nb.ramp(nb.gray(cell), [(0.0, (0.55, 0.30, 0.10)), (0.4, (0.70, 0.45, 0.14)),
                                        (0.7, (0.42, 0.22, 0.10)), (1.0, (0.62, 0.52, 0.20))])
        c = nb.mix(c, leafc, nb.mul(mask, 0.85))
        needles = nb.smooth(0.7, 0.78, nb.wave(suv(nb, 12, 3), 6.0, 12.0, 3))
        return nb.mix(c, nb.rgb(0.52, 0.38, 0.20), nb.mul(needles, 0.5))

    def hgt(nb):
        mask, cell, ly, lx, r = leaf_cells(nb, 22.0, 0.22, 0.40)
        return nb.add(nb.mul(mask, 0.5), nb.mul(nb.noise(nb.uv(), 25, 8), 0.5))
    return pair(col, hgt, 4.0)


@register
def terrain_rock():
    def col(nb):
        uv = nb.uv()
        n = nb.noise(uv, 5.0, 10, 0.62, distortion=0.2)
        c = nb.ramp(n, [(0.3, (0.30, 0.30, 0.31)), (0.55, (0.47, 0.45, 0.43)), (0.8, (0.62, 0.60, 0.56))])
        cracks = nb.voronoi(suv(nb, 8), 1.0, feature="DISTANCE_TO_EDGE")
        c = nb.mix(c, nb.rgb(0.16, 0.15, 0.15), nb.smooth(0.03, 0.0, cracks))
        lichen = nb.smooth(0.62, 0.7, nb.noise(offs(nb, uv, 4.4), 14.0, 6))
        c = nb.mix(c, nb.rgb(0.62, 0.64, 0.42), nb.mul(lichen, 0.6))
        warm = nb.noise(offs(nb, uv, 1.7), 3.0, 3)
        return nb.mix(c, nb.rgb(0.58, 0.48, 0.38), nb.mul(nb.smooth(0.5, 0.7, warm), 0.4))

    def hgt(nb):
        return nb.add(nb.mul(nb.noise(nb.uv(), 5.0, 10, 0.62, distortion=0.2), 0.7),
                      nb.mul(nb.smooth(0.0, 0.06, nb.voronoi(suv(nb, 8), 1.0, feature="DISTANCE_TO_EDGE")), 0.3))
    return pair(col, hgt, 6.0)


@register
def terrain_cliff():
    def col(nb):
        uv = nb.uv()
        warp = nb.noise(uv, 3.0, 4)
        strata = nb.wave(nb.vmath("ADD", suv(nb, 1, 1), nb.vec(0, nb.mul(warp, 0.3), 0)), 3.0, 4.0, 6, direction="Y")
        c = nb.ramp(strata, [(0.0, (0.36, 0.33, 0.31)), (0.35, (0.52, 0.47, 0.42)),
                             (0.6, (0.40, 0.38, 0.37)), (1.0, (0.62, 0.58, 0.52))])
        grain = nb.ramp(nb.noise(uv, 60, 6), [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.12, 1.1, 1.08))])
        c = nb.mix(c, grain, 1.0, "MULTIPLY")
        streak = nb.smooth(0.55, 0.7, nb.noise(suv(nb, 30, 3), 1.0, 5))
        return nb.mix(c, nb.rgb(0.25, 0.24, 0.24), nb.mul(streak, 0.4))

    def hgt(nb):
        warp = nb.noise(nb.uv(), 3.0, 4)
        return nb.wave(nb.vmath("ADD", nb.uv(), nb.vec(0, nb.mul(warp, 0.3), 0)), 3.0, 4.0, 6, direction="Y", profile="SAW")
    return pair(col, hgt, 7.0)


@register
def terrain_snow():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 5.0, 8, 0.55), [
            (0.3, (0.80, 0.85, 0.93)), (0.6, (0.93, 0.95, 0.98)), (0.85, (1.0, 1.0, 1.0))])
        spark = speckle(nb, suv(nb, 200), 1.0, 0.05)
        c = nb.mix(c, nb.rgb(1.0, 1.0, 1.0), spark)
        drift = nb.wave(uv, 4.0, 6.0, 4, direction="DIAGONAL")
        return nb.mix(c, nb.rgb(0.70, 0.78, 0.90), nb.mul(nb.smooth(0.7, 0.95, drift), 0.4))

    def hgt(nb):
        return nb.add(nb.wave(nb.uv(), 4.0, 6.0, 4, direction="DIAGONAL"), nb.mul(nb.noise(nb.uv(), 40, 6), 0.3))
    return pair(col, hgt, 2.0)


@register
def terrain_sand():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 5.0, 6), [(0.3, (0.66, 0.56, 0.38)), (0.7, (0.84, 0.74, 0.54))])
        rip = nb.wave(nb.vmath("ADD", uv, nb.vmath("SCALE", nb.noise(uv, 3, 3, color=True), scale=0.08)), 9.0, 2.0, 2)
        c = nb.mix(c, nb.rgb(0.55, 0.45, 0.30), nb.mul(nb.smooth(0.6, 0.95, rip), 0.4))
        grain = nb.ramp(nb.noise(uv, 300, 2), [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.15, 1.12, 1.1))])
        return nb.mix(c, grain, 1.0, "MULTIPLY")

    def hgt(nb):
        uv = nb.uv()
        return nb.wave(nb.vmath("ADD", uv, nb.vmath("SCALE", nb.noise(uv, 3, 3, color=True), scale=0.08)), 9.0, 2.0, 2)
    return pair(col, hgt, 3.0)


@register
def terrain_pebbles():
    def col(nb):
        v = suv(nb, 26)
        vn = nb._new("ShaderNodeTexVoronoi", feature="SMOOTH_F1")
        nb._set(vn.inputs["Vector"], v)
        nb._set(vn.inputs["Scale"], 1.0)
        d = vn.outputs["Distance"]
        cellc = nb.ramp(nb.gray(vn.outputs["Color"]), [(0.0, (0.40, 0.38, 0.36)), (0.3, (0.62, 0.58, 0.52)),
                                                        (0.6, (0.48, 0.44, 0.40)), (1.0, (0.72, 0.68, 0.62))])
        stone = nb.smooth(0.42, 0.34, d)
        ground = nb.ramp(nb.noise(nb.uv(), 40, 6), [(0.3, (0.22, 0.18, 0.13)), (0.7, (0.34, 0.28, 0.20))])
        c = nb.mix(ground, cellc, stone)
        return nb.mix(c, nb.rgb(0.2, 0.2, 0.2), nb.mul(nb.noise(nb.uv(), 90, 4), 0.25))

    def hgt(nb):
        v = suv(nb, 26)
        d = nb.voronoi(v, 1.0, feature="SMOOTH_F1")
        return nb.sub(1.0, nb.math("POWER", nb.math("MINIMUM", nb.mul(d, 2.2), 1.0), 2.0))
    return pair(col, hgt, 6.0)


@register
def terrain_mud():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 7, 8), [(0.3, (0.17, 0.12, 0.08)), (0.7, (0.32, 0.24, 0.15))])
        wet = nb.smooth(0.5, 0.65, nb.noise(offs(nb, uv, 5), 4, 4))
        c = nb.mix(c, nb.rgb(0.10, 0.08, 0.06), nb.mul(wet, 0.6))
        crack = nb.voronoi(suv(nb, 12), 1.0, feature="DISTANCE_TO_EDGE")
        return nb.mix(c, nb.rgb(0.08, 0.06, 0.04), nb.mul(nb.smooth(0.03, 0.0, crack), nb.sub(1.0, wet)))

    def hgt(nb):
        crack = nb.voronoi(suv(nb, 12), 1.0, feature="DISTANCE_TO_EDGE")
        return nb.add(nb.smooth(0.0, 0.05, crack), nb.mul(nb.noise(nb.uv(), 20, 6), 0.3))
    return pair(col, hgt, 5.0)


@register
def terrain_macro():
    def col(nb):
        uv = nb.uv()
        a = nb.noise(uv, 3.0, 6, 0.55)
        b = nb.noise(offs(nb, uv, 11.0), 7.0, 6, 0.5)
        c = nb.noise(offs(nb, uv, 23.0), 1.5, 3, 0.5)
        return nb.vec(a, b, c)
    return single(col, suffix=None)


# ---------------------------------------------------------------------------
# ARCHITECTURE (albedo + normal)
# ---------------------------------------------------------------------------

def roof(base_lo, base_hi, name_seed):
    def tiles(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        cols, rows = 8.0, 16.0
        across = nb.math("SINE", nb.mul(u, cols * 6.283185))
        along = fract(nb, nb.add(nb.mul(v, rows), nb.mul(nb.math("FLOOR", nb.mul(u, cols)), 0.0)))
        return across, along

    def col(nb):
        across, along = tiles(nb)
        shade = nb.maprange(across, -1, 1, 0.35, 1.0)
        lip = nb.smooth(0.8, 1.0, along)
        glaze = nb.ramp(nb.noise(offs(nb, nb.uv(), name_seed), 12, 6), [(0.3, base_lo), (0.7, base_hi)])
        c = nb.mix(glaze, nb.rgb(0.0, 0.0, 0.0), nb.mul(nb.sub(1.0, shade), 0.7))
        c = nb.mix(c, nb.rgb(0.05, 0.05, 0.05), nb.mul(lip, 0.5))
        spec = nb.smooth(0.85, 1.0, across)
        c = nb.mix(c, nb.rgb(0.95, 0.95, 0.85), nb.mul(spec, 0.25))
        grime = nb.smooth(0.55, 0.75, nb.noise(nb.uv(), 6, 6))
        return nb.mix(c, nb.rgb(0.20, 0.20, 0.16), nb.mul(grime, 0.35))

    def hgt(nb):
        across, along = tiles(nb)
        return nb.mul(nb.maprange(across, -1, 1, 0.0, 1.0), nb.add(0.5, nb.mul(along, 0.5)))
    return pair(col, hgt, 6.0)


@register
def roof_tiles_jade():
    return roof((0.10, 0.36, 0.30), (0.26, 0.62, 0.50), 1.0)


@register
def roof_tiles_crimson():
    return roof((0.42, 0.10, 0.07), (0.70, 0.22, 0.12), 5.0)


@register
def wood_planks():
    def col(nb):
        uv = nb.uv()
        bc, bf = nb.brick(uv, 4.0, mortar=0.006, width=1.0, height=0.125, offset=0.5, smooth=0.2,
                          c1=(0.55, 0.36, 0.20), c2=(0.36, 0.22, 0.12), bias=0.0)
        grain = nb.wave(nb.vmath("MULTIPLY", uv, nb.vec(1, 12, 1)), 2.0, 6.0, 6, direction="X", kind="BANDS")
        g = nb.ramp(nb.noise(suv(nb, 3, 60), 1.0, 8, 0.6), [(0.3, (0.7, 0.66, 0.62)), (0.7, (1.12, 1.08, 1.0))])
        c = nb.mix(bc, g, 1.0, "MULTIPLY")
        c = nb.mix(c, nb.rgb(0.25, 0.14, 0.07), nb.mul(nb.smooth(0.7, 1.0, grain), 0.35))
        knots = nb.smooth(0.08, 0.0, nb.voronoi(suv(nb, 6, 12), 1.0))
        c = nb.mix(c, nb.rgb(0.18, 0.10, 0.05), nb.mul(knots, 0.7))
        return nb.mix(c, nb.rgb(0.10, 0.06, 0.03), bf)

    def hgt(nb):
        _, bf = nb.brick(nb.uv(), 4.0, mortar=0.006, width=1.0, height=0.125, smooth=0.2)
        return nb.add(nb.mul(nb.sub(1.0, bf), 0.7), nb.mul(nb.noise(suv(nb, 3, 60), 1.0, 8, 0.6), 0.3))
    return pair(col, hgt, 5.0)


@register
def lacquer_red():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 8, 8, 0.5), [(0.3, (0.48, 0.07, 0.05)), (0.7, (0.66, 0.12, 0.07))])
        grain = nb.noise(suv(nb, 4, 80), 1.0, 6, 0.6)
        c = nb.mix(c, nb.rgb(0.35, 0.05, 0.04), nb.mul(nb.smooth(0.55, 0.7, grain), 0.4))
        wear = nb.smooth(0.66, 0.72, nb.noise(offs(nb, uv, 3), 10, 8, 0.7))
        c = nb.mix(c, nb.rgb(0.30, 0.18, 0.10), wear)
        return nb.mix(c, nb.rgb(0.95, 0.45, 0.30), nb.mul(nb.smooth(0.8, 0.95, nb.noise(uv, 3, 2)), 0.15))

    def hgt(nb):
        wear = nb.smooth(0.66, 0.72, nb.noise(offs(nb, nb.uv(), 3), 10, 8, 0.7))
        return nb.add(nb.mul(nb.sub(1.0, wear), 0.6), nb.mul(nb.noise(suv(nb, 4, 80), 1.0, 6), 0.2))
    return pair(col, hgt, 3.0)


@register
def stone_bricks():
    def col(nb):
        uv = nb.uv()
        bc, bf = nb.brick(uv, 4.0, mortar=0.025, width=0.5, height=0.25, smooth=0.3,
                          c1=(0.60, 0.58, 0.54), c2=(0.44, 0.43, 0.41), bias=0.0)
        n = nb.ramp(nb.noise(uv, 30, 8, 0.6), [(0.3, (0.72, 0.72, 0.72)), (0.7, (1.1, 1.08, 1.05))])
        c = nb.mix(bc, n, 1.0, "MULTIPLY")
        moss = nb.mul(bf, nb.smooth(0.4, 0.6, nb.noise(uv, 8, 5)))
        c = nb.mix(c, nb.rgb(0.24, 0.24, 0.22), bf)
        c = nb.mix(c, nb.rgb(0.22, 0.38, 0.14), moss)
        chips = nb.smooth(0.72, 0.8, nb.noise(offs(nb, uv, 2), 20, 6))
        return nb.mix(c, nb.rgb(0.32, 0.31, 0.29), nb.mul(chips, 0.6))

    def hgt(nb):
        _, bf = nb.brick(nb.uv(), 4.0, mortar=0.025, width=0.5, height=0.25, smooth=0.3)
        return nb.sub(nb.mul(nb.sub(1.0, bf), 0.8), nb.mul(nb.smooth(0.72, 0.8, nb.noise(offs(nb, nb.uv(), 2), 20, 6)), 0.2))
    return pair(col, hgt, 6.0)


@register
def stone_paving():
    def col(nb):
        v = suv(nb, 6)
        vn = nb._new("ShaderNodeTexVoronoi", feature="F1")
        nb._set(vn.inputs["Vector"], v)
        nb._set(vn.inputs["Scale"], 1.0)
        edge = nb.voronoi(v, 1.0, feature="DISTANCE_TO_EDGE")
        cellc = nb.ramp(nb.gray(vn.outputs["Color"]), [(0.0, (0.46, 0.44, 0.41)), (0.5, (0.60, 0.57, 0.52)), (1.0, (0.52, 0.50, 0.47))])
        n = nb.ramp(nb.noise(nb.uv(), 40, 8), [(0.3, (0.78, 0.78, 0.78)), (0.7, (1.1, 1.08, 1.04))])
        c = nb.mix(cellc, n, 1.0, "MULTIPLY")
        gap = nb.smooth(0.04, 0.015, edge)
        return nb.mix(c, nb.rgb(0.18, 0.24, 0.12), gap)

    def hgt(nb):
        edge = nb.voronoi(suv(nb, 6), 1.0, feature="DISTANCE_TO_EDGE")
        return nb.add(nb.smooth(0.015, 0.06, edge), nb.mul(nb.noise(nb.uv(), 40, 8), 0.2))
    return pair(col, hgt, 5.0)


@register
def plaster_wall():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 6, 8, 0.55), [(0.3, (0.82, 0.78, 0.68)), (0.7, (0.93, 0.90, 0.82))])
        stain = nb.smooth(0.55, 0.8, nb.noise(suv(nb, 3, 0.6), 2.0, 6))
        c = nb.mix(c, nb.rgb(0.60, 0.56, 0.46), nb.mul(stain, 0.5))
        crack = nb.smooth(0.01, 0.0, nb.voronoi(suv(nb, 5), 1.0, feature="DISTANCE_TO_EDGE"))
        return nb.mix(c, nb.rgb(0.45, 0.42, 0.36), nb.mul(crack, nb.smooth(0.5, 0.7, nb.noise(uv, 4, 3))))

    def hgt(nb):
        return nb.noise(nb.uv(), 25, 8, 0.6)
    return pair(col, hgt, 2.0)


@register
def marble_white():
    def col(nb):
        uv = nb.uv()
        vein = nb.wave(uv, 2.5, 14.0, 8, direction="DIAGONAL", profile="SIN")
        c = nb.ramp(vein, [(0.0, (0.60, 0.62, 0.62)), (0.08, (0.90, 0.90, 0.88)), (1.0, (0.97, 0.96, 0.94))])
        return nb.mix(c, nb.rgb(0.80, 0.84, 0.82), nb.mul(nb.noise(uv, 8, 6), 0.3))

    def hgt(nb):
        return nb.mul(nb.noise(nb.uv(), 30, 4), 0.3)
    return pair(col, hgt, 1.0)


@register
def bronze_patina():
    def col(nb):
        uv = nb.uv()
        bronze = nb.ramp(nb.noise(uv, 20, 6), [(0.3, (0.42, 0.28, 0.14)), (0.7, (0.62, 0.44, 0.22))])
        pat = nb.smooth(0.45, 0.62, nb.noise(offs(nb, uv, 9), 7, 10, 0.7, distortion=0.4))
        c = nb.mix(bronze, nb.ramp(nb.noise(uv, 40, 4), [(0.3, (0.24, 0.52, 0.44)), (0.7, (0.42, 0.68, 0.58))]), pat)
        return nb.mix(c, nb.rgb(0.12, 0.10, 0.08), nb.mul(nb.smooth(0.7, 0.85, nb.noise(uv, 30, 6)), 0.5))

    def hgt(nb):
        return nb.smooth(0.45, 0.62, nb.noise(offs(nb, nb.uv(), 9), 7, 10, 0.7, distortion=0.4))
    return pair(col, hgt, 3.0)


def cloud_motif(nb, scale):
    """Xiangyun-style scrolling cloud rings inside a lattice of cells."""
    v = suv(nb, scale)
    vn = nb._new("ShaderNodeTexVoronoi", feature="F1")
    nb._set(vn.inputs["Vector"], v)
    nb._set(vn.inputs["Scale"], 1.0)
    nb._set(vn.inputs["Randomness"], 0.0)
    local = nb.vmath("SUBTRACT", v, vn.outputs["Position"])
    r = nb.vmath("LENGTH", local)
    lx, ly, _ = nb.xyz(local)
    ang = nb.math("ARCTAN2", ly, lx)
    spiral = nb.math("SINE", nb.add(nb.mul(r, 40.0), ang))
    ring = nb.mul(nb.smooth(0.3, 0.8, spiral), nb.smooth(0.48, 0.38, r))
    return ring


@register
def gold_trim():
    def col(nb):
        uv = nb.uv()
        g = nb.ramp(nb.noise(uv, 10, 6), [(0.3, (0.62, 0.44, 0.12)), (0.7, (0.92, 0.72, 0.30))])
        m = cloud_motif(nb, 8)
        c = nb.mix(g, nb.rgb(0.40, 0.26, 0.06), nb.mul(nb.sub(1.0, m), 0.5))
        return nb.mix(c, nb.rgb(0.25, 0.18, 0.08), nb.mul(nb.smooth(0.65, 0.8, nb.noise(uv, 25, 6)), 0.3))

    def hgt(nb):
        return cloud_motif(nb, 8)
    return pair(col, hgt, 5.0)


@register
def celadon_glaze():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 4, 5), [(0.3, (0.52, 0.68, 0.58)), (0.7, (0.66, 0.80, 0.70))])
        crackle = nb.voronoi(suv(nb, 14), 1.0, feature="DISTANCE_TO_EDGE")
        crackle2 = nb.voronoi(suv(nb, 37), 1.0, feature="DISTANCE_TO_EDGE")
        c = nb.mix(c, nb.rgb(0.30, 0.40, 0.34), nb.smooth(0.012, 0.0, crackle))
        return nb.mix(c, nb.rgb(0.42, 0.54, 0.46), nb.mul(nb.smooth(0.01, 0.0, crackle2), 0.6))

    def hgt(nb):
        return nb.smooth(0.0, 0.02, nb.voronoi(suv(nb, 14), 1.0, feature="DISTANCE_TO_EDGE"))
    return pair(col, hgt, 1.5)


# ---------------------------------------------------------------------------
# BARK (albedo + normal)
# ---------------------------------------------------------------------------

def bark(lo, mid, hi, ridge_scale=(10, 1.4), dist=6.0, seed=0.0, plates=False):
    def pattern(nb):
        v = offs(nb, suv(nb, ridge_scale[0], ridge_scale[1]), seed)
        if plates:
            return nb.sub(1.0, nb.smooth(0.0, 0.12, nb.voronoi(v, 1.0, feature="DISTANCE_TO_EDGE")))
        return nb.wave(v, 1.0, dist, 8, direction="X", profile="SAW")

    def col(nb):
        p = pattern(nb)
        c = nb.ramp(p, [(0.0, lo), (0.5, mid), (1.0, hi)])
        n = nb.ramp(nb.noise(nb.uv(), 50, 8), [(0.3, (0.75, 0.75, 0.75)), (0.7, (1.12, 1.1, 1.05))])
        c = nb.mix(c, n, 1.0, "MULTIPLY")
        lichen = nb.smooth(0.63, 0.7, nb.noise(offs(nb, nb.uv(), seed + 3), 9, 6))
        return nb.mix(c, nb.rgb(0.50, 0.58, 0.40), nb.mul(lichen, 0.5))

    def hgt(nb):
        return nb.add(nb.mul(pattern(nb), 0.8), nb.mul(nb.noise(nb.uv(), 50, 8), 0.2))
    return pair(col, hgt, 7.0)


@register
def bark_pine():
    return bark((0.16, 0.10, 0.07), (0.38, 0.24, 0.15), (0.55, 0.38, 0.25), (5, 3), plates=True)


@register
def bark_cherry():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(suv(nb, 2, 20), 1.0, 6), [(0.3, (0.26, 0.14, 0.12)), (0.7, (0.40, 0.22, 0.18))])
        lent = nb.smooth(0.1, 0.0, nb.voronoi(suv(nb, 3, 40), 1.0))
        c = nb.mix(c, nb.rgb(0.62, 0.50, 0.42), nb.mul(lent, 0.8))
        return nb.mix(c, nb.rgb(0.14, 0.08, 0.07), nb.mul(nb.smooth(0.6, 0.8, nb.noise(uv, 30, 6)), 0.4))

    def hgt(nb):
        return nb.add(nb.smooth(0.12, 0.0, nb.voronoi(suv(nb, 3, 40), 1.0)), nb.mul(nb.noise(nb.uv(), 30, 6), 0.3))
    return pair(col, hgt, 4.0)


@register
def bark_maple():
    return bark((0.20, 0.16, 0.12), (0.36, 0.30, 0.24), (0.50, 0.44, 0.36), (12, 1.2), 9.0, 2.0)


@register
def bark_birch():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 8, 6), [(0.3, (0.82, 0.80, 0.74)), (0.7, (0.94, 0.92, 0.88))])
        dash = nb.smooth(0.72, 0.8, nb.noise(suv(nb, 3, 30), 1.0, 3))
        c = nb.mix(c, nb.rgb(0.12, 0.11, 0.10), dash)
        return nb.mix(c, nb.rgb(0.55, 0.50, 0.42), nb.mul(nb.smooth(0.6, 0.75, nb.noise(uv, 20, 6)), 0.4))

    def hgt(nb):
        return nb.sub(1.0, nb.smooth(0.72, 0.8, nb.noise(suv(nb, 3, 30), 1.0, 3)))
    return pair(col, hgt, 3.0)


@register
def bamboo_stalk():
    def col(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        node = nb.smooth(0.03, 0.0, nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(v, 4.0)), 0.5)))
        node = nb.smooth(0.46, 0.5, nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(v, 4.0)), 0.5)))
        c = nb.ramp(nb.noise(suv(nb, 8, 2), 1.0, 5), [(0.3, (0.36, 0.52, 0.18)), (0.7, (0.56, 0.68, 0.26))])
        streak = nb.noise(suv(nb, 60, 2), 1.0, 4)
        c = nb.mix(c, nb.rgb(0.70, 0.74, 0.40), nb.mul(nb.smooth(0.6, 0.75, streak), 0.4))
        c = nb.mix(c, nb.rgb(0.30, 0.34, 0.12), node)
        return nb.mix(c, nb.rgb(0.76, 0.70, 0.40), nb.mul(nb.smooth(0.7, 0.9, nb.noise(uv, 5, 4)), 0.5))

    def hgt(nb):
        _, v, _ = nb.xyz(nb.uv())
        return nb.sub(1.0, nb.smooth(0.44, 0.5, nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(v, 4.0)), 0.5))))
    return pair(col, hgt, 6.0)


# ---------------------------------------------------------------------------
# FOLIAGE CARDS (RGBA, alpha-scissored in engine)
# ---------------------------------------------------------------------------

def leaf_card(scale, a, b, lo, hi, tip=0.35, vein=True, extra=None):
    def col(nb):
        mask, cell, ly, lx, r = leaf_cells(nb, scale, a, b, tip)
        c = nb.ramp(nb.gray(cell), [(0.0, lo), (1.0, hi)])
        if vein:
            v = nb.smooth(0.05, 0.0, nb.math("ABSOLUTE", lx))
            c = nb.mix(c, nb.rgb(0.9, 0.9, 0.6), nb.mul(v, 0.25))
        c = nb.mix(c, nb.rgb(0.0, 0.0, 0.0), nb.mul(nb.smooth(0.6, 1.0, r), 0.3))
        if extra:
            c = extra(nb, c)
        return c

    def alpha(nb):
        mask, cell, ly, lx, r = leaf_cells(nb, scale, a, b, tip)
        return mask
    return rgba(col, alpha)


@register
def leaves_maple():
    return leaf_card(7, 0.36, 0.44, (0.62, 0.10, 0.05), (0.95, 0.48, 0.12), tip=0.6)


@register
def leaves_cherry():
    def col(nb):
        mask, cell, ly, lx, r = leaf_cells(nb, 10, 0.34, 0.40, 0.9)
        c = nb.ramp(nb.gray(cell), [(0.0, (0.96, 0.66, 0.76)), (0.5, (0.99, 0.82, 0.87)), (1.0, (0.92, 0.50, 0.64))])
        return nb.mix(c, nb.rgb(0.80, 0.30, 0.45), nb.mul(nb.smooth(0.5, 0.0, r), 0.4))

    def alpha(nb):
        return leaf_cells(nb, 10, 0.34, 0.40, 0.9)[0]
    return rgba(col, alpha)


@register
def leaves_willow():
    return leaf_card(9, 0.10, 0.48, (0.30, 0.50, 0.16), (0.56, 0.70, 0.30), tip=0.2)


@register
def leaves_bamboo():
    return leaf_card(7, 0.12, 0.46, (0.22, 0.44, 0.14), (0.48, 0.66, 0.22), tip=0.15)


@register
def leaves_ginkgo():
    return leaf_card(8, 0.38, 0.34, (0.90, 0.72, 0.12), (0.98, 0.88, 0.40), tip=1.4)


@register
def leaves_broad():
    return leaf_card(8, 0.26, 0.42, (0.14, 0.34, 0.10), (0.36, 0.56, 0.18), tip=0.4)


@register
def leaves_pine():
    def needles(nb):
        # dense radiating sprays: solid core + many thick spokes, so the
        # card keeps its coverage when mipmapped at a distance
        v = suv(nb, 5)
        vn = nb._new("ShaderNodeTexVoronoi", feature="F1")
        nb._set(vn.inputs["Vector"], v)
        nb._set(vn.inputs["Scale"], 1.0)
        local = nb.vmath("SUBTRACT", v, vn.outputs["Position"])
        lx, ly, _ = nb.xyz(local)
        r = nb.vmath("LENGTH", local)
        ang = nb.math("ARCTAN2", ly, lx)
        spokes = nb.math("GREATER_THAN", nb.math("SINE", nb.add(nb.mul(ang, 26.0), nb.mul(nb.gray(vn.outputs["Color"]), 9.0))), -0.35)
        core = nb.math("LESS_THAN", r, 0.3)
        return nb.mul(nb.math("MAXIMUM", spokes, core), nb.math("LESS_THAN", r, nb.add(0.62, nb.mul(nb.noise(v, 3.0, 2), 0.1))))

    def col(nb):
        c = nb.ramp(nb.noise(nb.uv(), 8, 4), [(0.3, (0.08, 0.24, 0.14)), (0.7, (0.20, 0.40, 0.22))])
        return nb.mix(c, nb.rgb(0.40, 0.56, 0.30), nb.mul(nb.noise(suv(nb, 180, 9), 1.0, 2), 0.4))
    return rgba(col, needles)


@register
def grass_blades():
    def blades(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        stripes = nb.noise(nb.vec(nb.mul(u, 60.0), 0.0, 0.0), 1.0, 2)
        height = nb.maprange(nb.noise(nb.vec(nb.mul(u, 23.0), 3.0, 0.0), 1.0, 2), 0.3, 0.7, 0.35, 1.0)
        return nb.mul(nb.math("GREATER_THAN", stripes, 0.5), nb.math("LESS_THAN", v, height))

    def col(nb):
        _, v, _ = nb.xyz(nb.uv())
        c = nb.ramp(v, [(0.0, (0.10, 0.22, 0.06)), (0.6, (0.32, 0.52, 0.16)), (1.0, (0.70, 0.74, 0.34))])
        return nb.mix(c, nb.rgb(0.55, 0.56, 0.22), nb.mul(nb.noise(suv(nb, 80, 1), 1.0, 2), 0.3))
    return rgba(col, blades)


@register
def fern_frond():
    def shape(nb):
        u, v, _ = nb.xyz(nb.uv())
        cu = nb.math("ABSOLUTE", nb.sub(u, 0.5))
        width = nb.mul(nb.math("SINE", nb.mul(v, 3.14159)), 0.45)
        leaflet = nb.math("SINE", nb.add(nb.mul(v, 110.0), nb.mul(cu, 30.0)))
        return nb.mul(nb.math("LESS_THAN", cu, width), nb.math("GREATER_THAN", nb.add(leaflet, nb.smooth(0.02, 0.0, cu)), -0.2))

    def col(nb):
        u, v, _ = nb.xyz(nb.uv())
        c = nb.ramp(v, [(0.0, (0.12, 0.30, 0.10)), (1.0, (0.38, 0.60, 0.20))])
        return nb.mix(c, nb.rgb(0.2, 0.3, 0.1), nb.smooth(0.01, 0.0, nb.math("ABSOLUTE", nb.sub(u, 0.5))))
    return rgba(col, shape)


@register
def flowers_meadow():
    def petals(nb):
        v = suv(nb, 9)
        vn = nb._new("ShaderNodeTexVoronoi", feature="F1")
        nb._set(vn.inputs["Vector"], v)
        nb._set(vn.inputs["Scale"], 1.0)
        local = nb.vmath("SUBTRACT", v, vn.outputs["Position"])
        lx, ly, _ = nb.xyz(local)
        r = nb.vmath("LENGTH", local)
        ang = nb.math("ARCTAN2", ly, lx)
        petal = nb.add(0.22, nb.mul(nb.math("ABSOLUTE", nb.math("SINE", nb.mul(ang, 2.5))), 0.16))
        return nb.math("LESS_THAN", r, petal), r, vn.outputs["Color"]

    def col(nb):
        m, r, cell = petals(nb)
        c = nb.ramp(nb.gray(cell), [(0.0, (0.96, 0.92, 0.84)), (0.35, (0.94, 0.55, 0.68)), (0.65, (0.60, 0.50, 0.92)), (1.0, (0.98, 0.80, 0.24))], "CONSTANT")
        return nb.mix(c, nb.rgb(0.98, 0.78, 0.20), nb.smooth(0.08, 0.04, r))

    def alpha(nb):
        return petals(nb)[0]
    return rgba(col, alpha)


@register
def lotus_leaf():
    def col(nb):
        uv = nb.uv()
        c = nb.vmath("SUBTRACT", uv, nb.vec(0.5, 0.5, 0))
        r = nb.vmath("LENGTH", c)
        lx, ly, _ = nb.xyz(c)
        ang = nb.math("ARCTAN2", ly, lx)
        veins = nb.smooth(0.9, 1.0, nb.math("COSINE", nb.mul(ang, 22.0)))
        base = nb.ramp(r, [(0.0, (0.52, 0.66, 0.30)), (0.5, (0.22, 0.46, 0.20))])
        base = nb.mix(base, nb.rgb(0.60, 0.72, 0.40), nb.mul(veins, 0.4))
        return nb.mix(base, nb.rgb(0.10, 0.22, 0.10), nb.mul(nb.noise(uv, 20, 6), 0.3))

    def alpha(nb):
        c = nb.vmath("SUBTRACT", nb.uv(), nb.vec(0.5, 0.5, 0))
        lx, ly, _ = nb.xyz(c)
        notch = nb.mul(nb.math("GREATER_THAN", lx, 0.0), nb.math("LESS_THAN", nb.math("ABSOLUTE", ly), nb.mul(lx, 0.12)))
        return nb.mul(nb.math("LESS_THAN", nb.vmath("LENGTH", c), 0.49), nb.sub(1.0, notch))
    return rgba(col, alpha)


# ---------------------------------------------------------------------------
# CHARACTER FABRICS / SKIN / HAIR
# ---------------------------------------------------------------------------

def silk(lo, hi, motif_col=None, motif_scale=5.0):
    def col(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        weave = nb.mul(nb.math("SINE", nb.mul(u, 1600.0)), nb.math("SINE", nb.mul(v, 1600.0)))
        c = nb.ramp(nb.noise(uv, 3, 4), [(0.3, lo), (0.7, hi)])
        sheen = nb.smooth(0.4, 0.8, nb.noise(suv(nb, 2, 8), 1.0, 3))
        c = nb.mix(c, nb.rgb(1.0, 1.0, 1.0), nb.mul(sheen, 0.12))
        c = nb.mix(c, nb.rgb(0.0, 0.0, 0.0), nb.mul(nb.maprange(weave, -1, 1, 0, 1), 0.08))
        if motif_col is not None:
            c = nb.mix(c, nb.rgb(*motif_col), nb.mul(cloud_motif(nb, motif_scale), 0.55))
        return c
    return single(col, suffix="albedo")


@register
def silk_jade():
    return silk((0.10, 0.40, 0.34), (0.20, 0.58, 0.48), (0.80, 0.90, 0.80))


@register
def silk_white():
    return silk((0.84, 0.86, 0.84), (0.97, 0.97, 0.95), (0.60, 0.76, 0.78))


@register
def silk_crimson():
    return silk((0.46, 0.06, 0.08), (0.70, 0.14, 0.14), (0.94, 0.72, 0.30))


@register
def silk_indigo():
    return silk((0.10, 0.12, 0.30), (0.20, 0.24, 0.48), (0.70, 0.74, 0.92))


@register
def fabric_weave():
    def col(nb):
        u, v, _ = nb.xyz(nb.uv())
        a = nb.math("SINE", nb.mul(u, 400.0))
        b = nb.math("SINE", nb.mul(v, 400.0))
        h = nb.add(nb.mul(nb.maprange(a, -1, 1, 0, 1), nb.math("GREATER_THAN", b, 0.0)),
                   nb.mul(nb.maprange(b, -1, 1, 0, 1), nb.math("LESS_THAN", b, 0.0)))
        h = nb.add(h, nb.mul(nb.noise(nb.uv(), 60, 4), 0.2))
        return h
    h = bake(col)[..., 0]
    return [("normal", xg.normal_from_height(h, 2.0), False)]


@register
def embroidery_cloud():
    def col(nb):
        m = cloud_motif(nb, 4)
        return nb.mix(nb.rgb(0.86, 0.66, 0.26), nb.rgb(0.98, 0.88, 0.56), m)

    def alpha(nb):
        return nb.math("GREATER_THAN", cloud_motif(nb, 4), 0.2)
    return rgba(col, alpha)


def skin(lo, hi):
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 6, 6), [(0.3, lo), (0.7, hi)])
        pores = nb.ramp(nb.noise(uv, 220, 2), [(0.3, (0.94, 0.92, 0.92)), (0.7, (1.03, 1.02, 1.02))])
        c = nb.mix(c, pores, 1.0, "MULTIPLY")
        return nb.mix(c, nb.rgb(0.90, 0.55, 0.50), nb.mul(nb.smooth(0.55, 0.75, nb.noise(uv, 3, 3)), 0.12))
    return single(col, suffix="albedo")


@register
def skin_fair():
    return skin((0.90, 0.74, 0.62), (0.97, 0.84, 0.74))


@register
def skin_tan():
    return skin((0.74, 0.54, 0.40), (0.86, 0.66, 0.50))


@register
def hair_black():
    def col(nb):
        strands = nb.noise(suv(nb, 200, 3), 1.0, 6, 0.6)
        c = nb.ramp(strands, [(0.3, (0.03, 0.03, 0.04)), (0.6, (0.10, 0.09, 0.10)), (0.8, (0.28, 0.26, 0.30))])
        band = nb.smooth(0.35, 0.5, nb.noise(suv(nb, 2, 1), 1.0, 2))
        return nb.mix(c, nb.rgb(0.34, 0.34, 0.42), nb.mul(band, 0.2))
    return single(col, suffix="albedo")


@register
def leather_belt():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 10, 8), [(0.3, (0.24, 0.13, 0.07)), (0.7, (0.40, 0.24, 0.12))])
        grain = nb.voronoi(suv(nb, 90), 1.0, feature="DISTANCE_TO_EDGE")
        return nb.mix(c, nb.rgb(0.12, 0.07, 0.04), nb.mul(nb.smooth(0.05, 0.0, grain), 0.5))

    def hgt(nb):
        return nb.smooth(0.0, 0.08, nb.voronoi(suv(nb, 90), 1.0, feature="DISTANCE_TO_EDGE"))
    return pair(col, hgt, 3.0)


# ---------------------------------------------------------------------------
# SKY / WATER / FX
# ---------------------------------------------------------------------------

def periodic_vec(nb, u, freq=1.0, radius=1.0, z=0.0):
    """Maps u in [0,1] onto a circle so noise sampled along it wraps."""
    a = nb.mul(u, 6.283185 * freq)
    return nb.vec(nb.mul(nb.math("COSINE", a), radius), nb.mul(nb.math("SINE", a), radius), z)


@register
def sky_clouds():
    def col(nb):
        uv = nb.uv()
        base = nb.noise(uv, 3.0, 10, 0.58, distortion=0.25)
        billow = nb.noise(offs(nb, uv, 4.0), 7.0, 8, 0.55)
        d = nb.smooth(0.46, 0.78, nb.add(nb.mul(base, 0.75), nb.mul(billow, 0.3)))
        return nb.vec(d, nb.smooth(0.5, 0.9, base), billow)
    return single(col, suffix=None)


@register
def sky_clouds_wispy():
    def col(nb):
        uv = nb.uv()
        w = nb.noise(nb.vmath("MULTIPLY", uv, nb.vec(1.0, 5.0, 1.0)), 2.5, 10, 0.62, distortion=0.8)
        d = nb.smooth(0.5, 0.82, w)
        return nb.vec(d, d, d)
    return single(col, suffix=None)


@register
def sky_stars():
    def col(nb):
        uv = nb.uv()
        s1 = nb.smooth(0.06, 0.0, nb.voronoi(suv(nb, 90), 1.0))
        s2 = nb.smooth(0.10, 0.0, nb.voronoi(offs(nb, suv(nb, 30), 7.0), 1.0))
        bright = nb.add(nb.mul(s1, 0.6), s2)
        neb = nb.smooth(0.5, 0.8, nb.noise(uv, 2.5, 10, 0.6, distortion=0.4))
        c = nb.mix(nb.rgb(0.0, 0.0, 0.0), nb.rgb(0.20, 0.10, 0.32), nb.mul(neb, 0.5))
        c = nb.mix(c, nb.rgb(0.10, 0.28, 0.34), nb.mul(nb.smooth(0.55, 0.85, nb.noise(offs(nb, uv, 3), 3.5, 8)), 0.35))
        return nb.mix(c, nb.rgb(1.0, 0.97, 0.90), nb.math("MINIMUM", bright, 1.0))
    return single(col, suffix=None)


def mountain_band(ridge_lo, ridge_hi, freq, far_col, near_col, mist_col, seed):
    size = (2048, 512)

    def ridge(nb):
        u, v, _ = nb.xyz(nb.uv())
        p = periodic_vec(nb, u, 1.0, freq, seed)
        n = nb.noise(p, 1.0, 10, 0.55)
        peaks = nb.math("POWER", nb.noise(offs(nb, p, 0, 0, 3.0), 0.6, 4, 0.5), 2.0)
        line = nb.maprange(nb.add(nb.mul(n, 0.6), nb.mul(peaks, 0.8)), 0.2, 1.0, ridge_lo, ridge_hi)
        return v, line, p

    def col(nb):
        v, line, p = ridge(nb)
        depth = nb.math("DIVIDE", v, line)
        c = nb.mix(nb.rgb(*mist_col), nb.rgb(*near_col), nb.smooth(0.0, 0.9, depth))
        c = nb.mix(c, nb.rgb(*far_col), nb.mul(nb.smooth(0.7, 1.0, depth), 0.5))
        rock = nb.noise(nb.vmath("ADD", p, nb.vec(0, 0, nb.mul(v, 12.0))), 6.0, 8)
        return nb.mix(c, nb.rgb(0.0, 0.0, 0.0), nb.mul(nb.smooth(0.55, 0.8, rock), 0.12))

    def alpha(nb):
        v, line, _ = ridge(nb)
        solid = nb.smooth(0.004, -0.004, nb.sub(v, line))
        return nb.mul(solid, nb.smooth(0.0, 0.25, v))
    return rgba(col, alpha, size=size, seamless=False, suffix=None)


@register
def sky_mountains_far():
    return mountain_band(0.30, 0.85, 3.0, (0.52, 0.60, 0.72), (0.36, 0.46, 0.58), (0.86, 0.84, 0.80), 1.0)


@register
def sky_mountains_near():
    return mountain_band(0.15, 0.55, 5.0, (0.24, 0.36, 0.38), (0.16, 0.28, 0.28), (0.76, 0.80, 0.78), 9.0)


@register
def water_normal():
    def hgt(nb):
        uv = nb.uv()
        a = nb.noise(nb.vmath("MULTIPLY", uv, nb.vec(1.0, 2.0, 1.0)), 6.0, 6, 0.5)
        b = nb.noise(offs(nb, uv, 3.0), 14.0, 4, 0.5)
        return nb.add(nb.mul(a, 0.7), nb.mul(b, 0.3))
    h = bake(hgt)[..., 0]
    return [(None, xg.normal_from_height(h, 8.0), False)]


@register
def water_foam():
    def col(nb):
        uv = nb.uv()
        f = nb.voronoi(suv(nb, 14), 1.0, feature="DISTANCE_TO_EDGE")
        n = nb.noise(uv, 10, 8)
        v = nb.mul(nb.smooth(0.08, 0.0, f), nb.smooth(0.35, 0.6, n))
        return nb.vec(v, v, v)
    return single(col, suffix=None)


@register
def spirit_mist():
    def col(nb):
        uv = nb.uv()
        d = nb.smooth(0.35, 0.8, nb.noise(uv, 3.0, 8, 0.6, distortion=0.6))
        return nb.vec(d, d, d)
    return single(col, suffix=None)


@register
def qi_glow():
    def col(nb):
        c = nb.vmath("SUBTRACT", nb.uv(), nb.vec(0.5, 0.5, 0))
        r = nb.vmath("LENGTH", c)
        lx, ly, _ = nb.xyz(c)
        return nb.mix(nb.rgb(0.35, 0.95, 0.80), nb.rgb(1.0, 1.0, 0.92), nb.smooth(0.1, 0.0, r))

    def alpha(nb):
        r = nb.vmath("LENGTH", nb.vmath("SUBTRACT", nb.uv(), nb.vec(0.5, 0.5, 0)))
        return nb.math("POWER", nb.smooth(0.5, 0.0, r), 2.0)
    return rgba(col, alpha, suffix=None)


@register
def crystal_spirit():
    def col(nb):
        uv = nb.uv()
        f = nb.voronoi(suv(nb, 6), 1.0, feature="DISTANCE_TO_EDGE")
        c = nb.ramp(nb.noise(uv, 5, 6), [(0.3, (0.30, 0.82, 0.78)), (0.7, (0.62, 0.95, 0.90))])
        c = nb.mix(c, nb.rgb(0.90, 1.0, 0.98), nb.smooth(0.03, 0.0, f))
        return nb.mix(c, nb.rgb(0.10, 0.40, 0.46), nb.mul(nb.smooth(0.5, 0.8, nb.noise(uv, 12, 6)), 0.4))

    def hgt(nb):
        return nb.smooth(0.0, 0.2, nb.voronoi(suv(nb, 6), 1.0, feature="DISTANCE_TO_EDGE"))
    return pair(col, hgt, 5.0)


@register
def jade_stone():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 4, 10, 0.6, distortion=0.6), [(0.25, (0.12, 0.42, 0.28)), (0.5, (0.36, 0.66, 0.46)), (0.8, (0.78, 0.90, 0.76))])
        return nb.mix(c, nb.rgb(0.05, 0.20, 0.12), nb.mul(nb.smooth(0.6, 0.75, nb.noise(offs(nb, uv, 2), 10, 8)), 0.4))

    def hgt(nb):
        return nb.mul(nb.noise(nb.uv(), 30, 4), 0.3)
    return pair(col, hgt, 1.0)


@register
def rock_mossy():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 6, 10, 0.6), [(0.3, (0.32, 0.32, 0.30)), (0.7, (0.55, 0.53, 0.50))])
        moss = nb.smooth(0.48, 0.58, nb.noise(offs(nb, uv, 6), 4, 8, 0.65))
        mc = nb.ramp(nb.noise(uv, 60, 6), [(0.3, (0.16, 0.32, 0.08)), (0.7, (0.36, 0.52, 0.14))])
        return nb.mix(c, mc, moss)

    def hgt(nb):
        uv = nb.uv()
        return nb.add(nb.mul(nb.noise(uv, 6, 10, 0.6), 0.6), nb.mul(nb.smooth(0.48, 0.58, nb.noise(offs(nb, uv, 6), 4, 8, 0.65)), 0.4))
    return pair(col, hgt, 5.0)


@register
def rock_lichen():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 8, 10, 0.6), [(0.3, (0.44, 0.42, 0.40)), (0.7, (0.64, 0.62, 0.58))])
        l1 = nb.smooth(0.10, 0.06, nb.voronoi(suv(nb, 30), 1.0))
        l2 = nb.smooth(0.12, 0.08, nb.voronoi(offs(nb, suv(nb, 22), 3), 1.0))
        c = nb.mix(c, nb.rgb(0.86, 0.74, 0.30), nb.mul(l1, 0.8))
        return nb.mix(c, nb.rgb(0.70, 0.78, 0.66), nb.mul(l2, 0.7))

    def hgt(nb):
        return nb.noise(nb.uv(), 8, 10, 0.6)
    return pair(col, hgt, 5.0)


@register
def iron_cast():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 20, 8), [(0.3, (0.14, 0.14, 0.15)), (0.7, (0.28, 0.27, 0.27))])
        rust = nb.smooth(0.55, 0.7, nb.noise(offs(nb, uv, 4), 6, 10, 0.7))
        return nb.mix(c, nb.ramp(nb.noise(uv, 70, 4), [(0.3, (0.34, 0.14, 0.06)), (0.7, (0.56, 0.28, 0.10))]), rust)

    def hgt(nb):
        return nb.add(nb.noise(nb.uv(), 20, 8), nb.mul(nb.smooth(0.55, 0.7, nb.noise(offs(nb, nb.uv(), 4), 6, 10, 0.7)), 0.4))
    return pair(col, hgt, 3.0)


@register
def paper_talisman():
    def col(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        c = nb.ramp(nb.noise(uv, 30, 8), [(0.3, (0.86, 0.68, 0.24)), (0.7, (0.96, 0.82, 0.40))])
        fib = nb.noise(suv(nb, 8, 120), 1.0, 3)
        c = nb.mix(c, nb.rgb(0.80, 0.60, 0.20), nb.mul(fib, 0.2))
        cu = nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(u, 4.0)), 0.5))
        glyph = nb.mul(nb.smooth(0.12, 0.08, cu), nb.smooth(0.3, 0.6, nb.noise(suv(nb, 12, 40), 1.0, 2)))
        return nb.mix(c, nb.rgb(0.62, 0.06, 0.04), glyph)
    return single(col, suffix=None)


@register
def banner_silk():
    def col(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        c = nb.ramp(nb.noise(uv, 4, 4), [(0.3, (0.56, 0.08, 0.08)), (0.7, (0.74, 0.14, 0.12))])
        border = nb.math("GREATER_THAN", nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(u, 2.0)), 0.5)), 0.44)
        c = nb.mix(c, nb.rgb(0.92, 0.72, 0.28), border)
        return nb.mix(c, nb.rgb(0.95, 0.80, 0.40), nb.mul(cloud_motif(nb, 4), 0.6))
    return single(col, suffix=None)


@register
def mushroom_cap():
    def col(nb):
        uv = nb.uv()
        c = nb.ramp(nb.noise(uv, 5, 5), [(0.3, (0.62, 0.16, 0.10)), (0.7, (0.86, 0.32, 0.14))])
        dots = nb.smooth(0.16, 0.10, nb.voronoi(suv(nb, 10), 1.0))
        return nb.mix(c, nb.rgb(0.98, 0.94, 0.86), dots)
    return single(col, suffix=None)


@register
def lantern_paper():
    def col(nb):
        uv = nb.uv()
        u, v, _ = nb.xyz(uv)
        ribs = nb.smooth(0.03, 0.0, nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(v, 8.0)), 0.5)))
        ribs = nb.smooth(0.46, 0.5, nb.math("ABSOLUTE", nb.sub(fract(nb, nb.mul(v, 8.0)), 0.5)))
        c = nb.ramp(nb.noise(uv, 10, 6), [(0.3, (0.92, 0.36, 0.14)), (0.7, (1.0, 0.56, 0.24))])
        fib = nb.noise(suv(nb, 60, 6), 1.0, 3)
        c = nb.mix(c, nb.rgb(1.0, 0.75, 0.40), nb.mul(fib, 0.25))
        return nb.mix(c, nb.rgb(0.30, 0.08, 0.04), ribs)
    return single(col, suffix=None)


# ---------------------------------------------------------------------------

def main():
    flt = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "")
    os.makedirs(xg.TEX_DIR, exist_ok=True)
    xg.reset_scene()
    import bpy
    bpy.context.scene.view_settings.view_transform = "Standard"
    written = []
    for name, fn in TEXTURES:
        if flt and flt not in name:
            continue
        for suffix, arr, alpha in fn():
            fname = name + ("_" + suffix if suffix else "") + ".png"
            path = os.path.join(xg.TEX_DIR, fname)
            xg.save_png(arr, path, alpha=alpha)
            written.append(fname)
            xg.log("wrote", fname, os.path.getsize(path) // 1024, "KB")
    xg.log("total files:", len(written))


if __name__ == "__main__":
    main()
