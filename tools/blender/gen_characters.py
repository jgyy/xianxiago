"""Generates the rigged, animated male and female cultivator characters.

Body: skin-modifier skeleton + subdivision. Clothing: lathed hanfu robe,
bell sleeves, sash, boots, crossed collar. Hair and accessories differ per
variant. A named armature is built by hand, every part is weighted to its
nearest allowed bones, and idle / walk / run / jump / fall / glide actions
are keyframed and exported as glTF animations.

    python3.11 tools/blender/gen_characters.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xg_common as xg  # noqa: E402  (imports bpy first)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import xg_mesh as xm  # noqa: E402
from xg_mesh import M  # noqa: E402

FPS = 24
DETAIL = 1.0  # 1.0 = player model, 0.5 = lighter NPC model


def D(n, lo=6):
    """Segment count scaled by the current detail level."""
    return max(lo, int(round(n * DETAIL)))


# ---------------------------------------------------------------------------
# Proportions
# ---------------------------------------------------------------------------

def proportions(female):
    s = 0.95 if female else 1.0
    J = {
        "root": (0, 0, 0),
        "hips": (0, 0, 0.94 * s),
        "spine": (0, 0, 1.10 * s),
        "chest": (0, 0, 1.30 * s),
        "neck": (0, 0, 1.48 * s),
        "head": (0, 0, 1.56 * s),
        "head_top": (0, 0, 1.80 * s),
    }
    sh = 0.17 if female else 0.20
    hip = 0.09 if female else 0.10
    for side, sx in (("L", 1), ("R", -1)):
        J["shoulder." + side] = (sx * sh, 0.0, 1.42 * s)
        J["elbow." + side] = (sx * (sh + 0.08), 0.02, 1.15 * s)
        J["wrist." + side] = (sx * (sh + 0.12), -0.02, 0.90 * s)
        J["hand." + side] = (sx * (sh + 0.13), -0.03, 0.80 * s)
        J["hip." + side] = (sx * hip, 0.0, 0.90 * s)
        J["knee." + side] = (sx * (hip + 0.01), -0.01, 0.50 * s)
        J["ankle." + side] = (sx * (hip + 0.01), 0.02, 0.08 * s)
        J["toe." + side] = (sx * (hip + 0.01), -0.12, 0.03)
    return {k: Vector(v) for k, v in J.items()}


BONES = [
    # name, head joint, tail joint, parent
    ("hips", "hips", "spine", None),
    ("spine", "spine", "chest", "hips"),
    ("chest", "chest", "neck", "spine"),
    ("neck", "neck", "head", "chest"),
    ("head", "head", "head_top", "neck"),
]
for _s in ("L", "R"):
    BONES += [
        ("upper_arm." + _s, "shoulder." + _s, "elbow." + _s, "chest"),
        ("forearm." + _s, "elbow." + _s, "wrist." + _s, "upper_arm." + _s),
        ("hand." + _s, "wrist." + _s, "hand." + _s, "forearm." + _s),
        ("thigh." + _s, "hip." + _s, "knee." + _s, "hips"),
        ("shin." + _s, "knee." + _s, "ankle." + _s, "thigh." + _s),
        ("foot." + _s, "ankle." + _s, "toe." + _s, "shin." + _s),
    ]


# ---------------------------------------------------------------------------
# Geometry parts
# ---------------------------------------------------------------------------

def body(J, female, skin_mat):
    chest_r = 0.13 if female else 0.15
    skel = [
        (J["hips"], -1, 0.13 if female else 0.12),
        (J["spine"], 0, 0.105 if female else 0.12),
        (J["chest"], 1, chest_r),
        (J["neck"], 2, 0.05),
        (J["head"], 3, 0.055),
    ]
    idx = {"hips": 0, "spine": 1, "chest": 2, "neck": 3}
    for s in ("L", "R"):
        skel.append((J["shoulder." + s], idx["chest"], 0.055))
        skel.append((J["elbow." + s], len(skel) - 1, 0.042))
        skel.append((J["wrist." + s], len(skel) - 1, 0.032))
        skel.append((J["hand." + s], len(skel) - 1, 0.035))
        skel.append((J["hip." + s], idx["hips"], 0.085 if female else 0.08))
        skel.append((J["knee." + s], len(skel) - 1, 0.055))
        skel.append((J["ankle." + s], len(skel) - 1, 0.04))
        skel.append((J["toe." + s], len(skel) - 1, 0.035))
    obj = xm.skin_tree("body", skel, skin_mat, subdiv=2 if DETAIL >= 1.0 else 1)
    xm.box_uv(obj, 2.0)
    return obj


def head(J, female, skin_mat):
    h = J["head"] + Vector((0, 0, 0.1))
    objs = []
    skull = xm.prim("uvsphere", skin_mat, segments=D(40), ring_count=D(24), radius=0.105, loc=tuple(h))
    skull.scale = (0.88, 0.98, 1.12)
    xm.transform_apply(skull)
    for v in skull.data.vertices:  # tapered jaw
        dz = v.co.z - h.z
        if dz < 0:
            k = 1 + dz * (2.6 if female else 2.0)
            v.co.x = h.x + (v.co.x - h.x) * k
            v.co.y = h.y + (v.co.y - h.y) * (1 + dz * 1.2)
    objs.append(skull)
    nose = xm.prim("uvsphere", skin_mat, segments=12, ring_count=8, radius=0.018, loc=tuple(h + Vector((0, -0.1, -0.02))))
    nose.scale = (0.8, 1.0, 1.4)
    objs.append(nose)
    for sx in (1, -1):
        ear = xm.prim("uvsphere", skin_mat, segments=12, ring_count=8, radius=0.025, loc=tuple(h + Vector((sx * 0.092, 0.0, 0.0))))
        ear.scale = (0.4, 0.8, 1.3)
        objs.append(ear)
        eye = xm.prim("uvsphere", xm.material("eye", color=(0.05, 0.04, 0.04), rough=0.2), segments=16, ring_count=8, radius=0.016, loc=tuple(h + Vector((sx * 0.037, -0.088, 0.018))))
        eye.scale = (1.3 if female else 1.1, 0.5, 0.8 if female else 0.6)
        objs.append(eye)
        shine = xm.prim("uvsphere", M("glow_white"), segments=8, ring_count=4, radius=0.004, loc=tuple(h + Vector((sx * 0.033, -0.097, 0.024))))
        objs.append(shine)
        brow = xm.box(tuple(h + Vector((sx * 0.04, -0.093, 0.05 if female else 0.045))), (0.05, 0.01, 0.007 if female else 0.012), M("hair"), 0.003, 2)
        brow.rotation_euler.y = sx * (0.12 if female else -0.08)
        objs.append(brow)
    lips = xm.prim("uvsphere", M("silk_crimson") if female else skin_mat, segments=12, ring_count=6, radius=0.02,
                   loc=tuple(h + Vector((0, -0.092, -0.058))))
    lips.scale = (1.3, 0.4, 0.45)
    objs.append(lips)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        if not o.data.uv_layers:
            xm.box_uv(o, 3.0)
    return objs


def lathe(rings, mat, segments=48, name="lathe", uv_v=1.0, open_ends=True):
    """rings: list of (z, rx, ry, cx, cy). Builds a closed-around, open-ended
    surface of revolution with per-ring elliptical radii."""
    verts, faces, uvs = [], [], []
    for j, (z, rx, ry, cx, cy) in enumerate(rings):
        for i in range(segments + 1):
            a = i / segments * math.tau
            verts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry, z))
            uvs.append((i / segments * 2.0, z * uv_v))
    for j in range(len(rings) - 1):
        for i in range(segments):
            a = j * (segments + 1) + i
            faces.append((a, a + 1, a + segments + 2, a + segments + 1))
    obj = xm.mesh_obj(name, verts, faces, mat, uvs)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def robe(J, female, outer, inner, trim):
    s = J["hips"].z / 0.94
    objs = []
    hem = 0.03 if female else 0.1
    if female:
        prof = [(1.50, 0.07, 0.065), (1.44, 0.17, 0.11), (1.36, 0.19, 0.14), (1.26, 0.17, 0.13), (1.12, 0.14, 0.11),
                (1.02, 0.15, 0.12), (0.90, 0.19, 0.16), (0.70, 0.24, 0.21), (0.45, 0.30, 0.27), (0.20, 0.36, 0.33), (hem, 0.40, 0.37)]
    else:
        prof = [(1.50, 0.075, 0.07), (1.44, 0.20, 0.12), (1.36, 0.22, 0.15), (1.24, 0.21, 0.15), (1.10, 0.19, 0.14),
                (1.00, 0.19, 0.145), (0.88, 0.21, 0.17), (0.65, 0.25, 0.21), (0.40, 0.28, 0.25), (hem, 0.31, 0.28)]
    rings = []
    for k in range(len(prof) - 1):  # densify for smooth deformation
        z0, a0, b0 = prof[k]
        z1, a1, b1 = prof[k + 1]
        steps = 4
        for t in range(steps):
            f = t / steps
            rings.append((z0 + (z1 - z0) * f, a0 + (a1 - a0) * f, b0 + (b1 - b0) * f, 0.0, 0.0))
    rings.append((prof[-1][0], prof[-1][1], prof[-1][2], 0.0, 0.0))
    rings = [(z * s if z > 0.2 else z, rx, ry, cx, cy) for z, rx, ry, cx, cy in rings]
    outer_obj = lathe(rings, outer, D(64, 16), "robe", uv_v=1.5)
    # front overlap: open the robe slightly at the lower front with a wavy hem
    for v in outer_obj.data.vertices:
        if v.co.z < 0.5 * s:
            ang = math.atan2(v.co.y, v.co.x)
            v.co.z += 0.02 * math.sin(ang * 6)
    xm.modifier(outer_obj, "SOLIDIFY", thickness=0.012, offset=1.0)
    objs.append(outer_obj)
    # inner robe peeks at the collar
    inner_obj = lathe([(1.52 * s, 0.065, 0.06, 0, 0), (1.46 * s, 0.10, 0.09, 0, 0), (1.40 * s, 0.14, 0.11, 0, 0)], inner, 48, "collar")
    objs.append(inner_obj)
    # crossed collar trim strips (right over left)
    for sx in (1, -1):
        verts = []
        faces = []
        n = 12
        for i in range(n + 1):
            t = i / n
            p = Vector((sx * 0.085 * (1 - t) - 0.025 * t, -0.075 - 0.075 * math.sin(t * math.pi * 0.9), (1.49 - 0.42 * t) * s))
            w = Vector((sx * 0.03, 0, 0.02))
            verts += [tuple(p - w), tuple(p + w)]
            if i:
                b = len(verts) - 4
                faces.append((b, b + 1, b + 3, b + 2))
        strip = xm.mesh_obj("collar_trim", verts, faces, trim)
        xm.modifier(strip, "SOLIDIFY", thickness=0.006)
        xm.box_uv(strip, 4.0)
        objs.append(strip)
    # sash
    sash = xm.prim("torus", SLOT["sash"], major_radius=1.0, minor_radius=0.12,
                   major_segments=D(48), minor_segments=D(12), loc=(0, 0, 1.02 * s))
    sash.scale = (0.19 if female else 0.2, 0.15, 0.4)
    xm.transform_apply(sash)
    xm.box_uv(sash, 3.0)
    objs.append(sash)
    for k, dx in enumerate((-0.05, 0.03)):
        tail = xm.box((dx, -0.16, 0.8 * s), (0.05, 0.012, 0.4), SLOT["sash"], 0.004, 2)
        tail.rotation_euler.x = 0.08 * (k + 1)
        objs.append(tail)
    pend = xm.prim("uvsphere", M("jade"), segments=16, ring_count=8, radius=0.03, loc=(0.09, -0.16, 0.86 * s))
    pend.scale = (1.0, 0.4, 1.3)
    objs.append(pend)
    return objs


def sleeves(J, mat, female):
    objs = []
    for s in ("L", "R"):
        a, b, c = J["shoulder." + s], J["elbow." + s], J["wrist." + s]
        pts, radii = [], []
        steps = 18
        for i in range(steps + 1):
            t = i / steps
            p = a.lerp(b, t * 2) if t < 0.5 else b.lerp(c, (t - 0.5) * 2)
            pts.append(p)
            radii.append(0.07 + 0.065 * t ** 1.8 * (1.15 if female else 1.0))
        pts.append(c + (c - b).normalized() * 0.09)
        radii.append(radii[-1] * 1.05)
        verts, faces, uvs = [], [], []
        seg = D(32, 12)
        for i, (p, r) in enumerate(zip(pts, radii)):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            side = d.cross(Vector((0, 1, 0))).normalized()
            fwd = d.cross(side).normalized()
            t = i / (len(pts) - 1)
            for k in range(seg + 1):
                ang = k / seg * math.tau
                # bell sleeve: the lower-back edge hangs further down
                sag = max(0.0, -math.sin(ang)) * t * t * 0.07
                off = side * math.cos(ang) * r + fwd * math.sin(ang) * r * 1.1 - Vector((0, 0, sag))
                verts.append(tuple(p + off))
                uvs.append((k / seg * 2.0, t * 2.0))
        for i in range(len(pts) - 1):
            for k in range(seg):
                q = i * (seg + 1) + k
                faces.append((q, q + seg + 1, q + seg + 2, q + 1))
        sl = xm.mesh_obj("sleeve." + s, verts, faces, mat, uvs)
        xm.modifier(sl, "SOLIDIFY", thickness=0.01, offset=1.0)
        for p in sl.data.polygons:
            p.use_smooth = True
        objs.append(sl)
        cuff = xm.prim("torus", M("gold"), major_radius=radii[-1] * 1.02, minor_radius=0.008,
                       major_segments=32, minor_segments=6, loc=tuple(pts[-1]))
        cuff.rotation_euler = (c - b).to_track_quat("Z", "Y").to_euler()
        xm.box_uv(cuff, 4.0)
        objs.append(cuff)
    return objs


def boots(J):
    objs = []
    for s in ("L", "R"):
        a, t = J["ankle." + s], J["toe." + s]
        shaft = xm.prim("cyl", M("leather"), vertices=20, radius=0.05, depth=0.26, loc=tuple(a + Vector((0, 0, 0.05))))
        foot = xm.prim("uvsphere", M("leather"), segments=20, ring_count=10, radius=0.06, loc=tuple((a + t) / 2 + Vector((0, 0, -0.02))))
        foot.scale = (0.8, 1.9, 0.65)
        for o in (shaft, foot):
            for p in o.data.polygons:
                p.use_smooth = True
            xm.box_uv(o, 3.0)
        objs += [shaft, foot]
    return objs


def _smooth_uv(objs, scale=3.0):
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        if not o.data.uv_layers:
            xm.box_uv(o, scale)
    return objs


def _hair_cap(h, mat):
    import bmesh
    cap = xm.prim("uvsphere", mat, segments=D(40), ring_count=D(24), radius=0.112, loc=tuple(h + Vector((0, 0.008, 0.012))))
    cap.scale = (0.92, 1.0, 1.1)
    xm.transform_apply(cap)
    bm = bmesh.new()
    bm.from_mesh(cap.data)
    # keep the face open: drop verts on the front-lower part of the cap
    kill = [v for v in bm.verts if (v.co.y - h.y) < -0.03 and (v.co.z - h.z) < 0.045 or (v.co.z - h.z) < -0.075]
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(cap.data)
    bm.free()
    xm.modifier(cap, "SOLIDIFY", thickness=0.01)
    return cap


def _hair_sheet(J, h, mat, length=0.62, width=0.1):
    """Long hair falling down the back."""
    verts, faces, uvs = [], [], []
    rows, cols = D(24, 8), D(16, 8)
    for j in range(rows + 1):
        t = j / rows
        z = h.z + 0.03 - t * length
        w = width + 0.04 * math.sin(t * math.pi)
        back = 0.1 + 0.045 * t
        if z < J["chest"].z + 0.1:
            back += 0.06 * min(1.0, (J["chest"].z + 0.1 - z) / 0.1)
        for i in range(cols + 1):
            u = i / cols
            a = (u - 0.5) * 2.2
            verts.append((math.sin(a) * w, h.y + back * math.cos(a * 0.6) + 0.02, z))
            uvs.append((u * 0.5, t * 3.0))
    for j in range(rows):
        for i in range(cols):
            q = j * (cols + 1) + i
            faces.append((q, q + 1, q + cols + 2, q + cols + 1))
    sheet = xm.mesh_obj("long_hair", verts, faces, mat, uvs)
    xm.modifier(sheet, "SOLIDIFY", thickness=0.02)
    return sheet


def _tube(pts, r0, r1, mat, name="tube"):
    verts, faces = [], []
    seg = D(12, 6)
    n = len(pts) * 4
    for i in range(n):
        t = i / (n - 1)
        f = t * (len(pts) - 1)
        k = min(int(f), len(pts) - 2)
        p = pts[k].lerp(pts[k + 1], f - k)
        r = r0 + (r1 - r0) * t
        for j in range(seg):
            a = j / seg * math.tau
            verts.append((p.x + math.cos(a) * r, p.y + math.sin(a) * r * 0.75, p.z))
        if i:
            b = len(verts) - 2 * seg
            for j in range(seg):
                faces.append((b + j, b + (j + 1) % seg, b + seg + (j + 1) % seg, b + seg + j))
    return xm.mesh_obj(name, verts, faces, mat)


def hair_styles(J, female):
    """Returns {style_name: [objects]}; every style includes its own cap so
    exactly one style is shown at a time."""
    h = J["head"] + Vector((0, 0, 0.1))
    mat = SLOT["hair"]
    gold, jade = M("gold"), M("jade")
    styles = {}
    if female:
        # twin buns with gold pins and jade drops (default)
        o = [_hair_cap(h, mat), _hair_sheet(J, h, mat)]
        for sx in (1, -1):
            o.append(xm.prim("uvsphere", mat, segments=D(24), ring_count=D(12), radius=0.05, loc=tuple(h + Vector((sx * 0.075, 0.03, 0.09)))))
            o.append(xm.prim("cyl", gold, vertices=8, radius=0.004, depth=0.09, loc=tuple(h + Vector((sx * 0.1, 0.03, 0.12))), rot=(0, sx * 1.0, 0)))
            o.append(xm.prim("uvsphere", jade, segments=8, ring_count=6, radius=0.01, loc=tuple(h + Vector((sx * 0.13, 0.03, 0.06)))))
        styles["twin_buns"] = o
        # long straight hair with a centre part and side locks
        o = [_hair_cap(h, mat), _hair_sheet(J, h, mat, 0.72, 0.11)]
        for sx in (1, -1):
            o.append(_tube([h + Vector((sx * 0.09, -0.04, 0.0)), h + Vector((sx * 0.1, -0.03, -0.18)), h + Vector((sx * 0.1, -0.01, -0.34))], 0.02, 0.008, mat))
        styles["long_straight"] = o
        # high ponytail with ribbon
        o = [_hair_cap(h, mat)]
        o.append(xm.prim("uvsphere", mat, segments=D(20), ring_count=D(10), radius=0.04, loc=tuple(h + Vector((0, 0.07, 0.11)))))
        o.append(_tube([h + Vector((0, 0.09, 0.12)), h + Vector((0, 0.17, 0.0)), h + Vector((0, 0.18, -0.25)), h + Vector((0, 0.16, -0.5))], 0.035, 0.006, mat, "ponytail"))
        o.append(xm.prim("torus", SLOT["sash"], major_radius=0.035, minor_radius=0.01, loc=tuple(h + Vector((0, 0.1, 0.1))), rot=(1.2, 0, 0)))
        styles["high_ponytail"] = o
        # elegant single bun with crossed hairpins and a floral ornament
        o = [_hair_cap(h, mat)]
        o.append(xm.prim("uvsphere", mat, segments=D(24), ring_count=D(12), radius=0.06, loc=tuple(h + Vector((0, 0.07, 0.08)))))
        for a in (0.7, -0.7):
            o.append(xm.prim("cyl", gold, vertices=8, radius=0.004, depth=0.2, loc=tuple(h + Vector((0, 0.08, 0.09))), rot=(0, a, 0)))
        o.append(xm.prim("uvsphere", M("lotus_flower"), segments=12, ring_count=6, radius=0.025, loc=tuple(h + Vector((0.05, 0.05, 0.13)))))
        styles["pinned_bun"] = o
        # long braid over the shoulder
        o = [_hair_cap(h, mat)]
        pts = [h + Vector((0.06, 0.08, -0.05)), h + Vector((0.12, 0.02, -0.2)), h + Vector((0.14, -0.08, -0.4)), h + Vector((0.12, -0.1, -0.62))]
        for k in range(3):
            off = Vector((math.cos(k * 2.1) * 0.012, math.sin(k * 2.1) * 0.012, 0))
            o.append(_tube([p + off for p in pts], 0.022, 0.012, mat, "braid"))
        o.append(xm.prim("torus", SLOT["sash"], major_radius=0.018, minor_radius=0.007, loc=tuple(pts[-1])))
        styles["side_braid"] = o
    else:
        def topknot(extra_crown=False):
            o = [xm.prim("uvsphere", mat, segments=D(24), ring_count=D(12), radius=0.045, loc=tuple(h + Vector((0, 0.02, 0.13))))]
            o[0].scale = (1.0, 1.0, 0.85)
            o.append(xm.prim("cyl", gold, vertices=D(24), radius=0.035 if not extra_crown else 0.05, depth=0.03 if not extra_crown else 0.06,
                             loc=tuple(h + Vector((0, 0.02, 0.165)))))
            o.append(xm.prim("cyl", jade, vertices=8, radius=0.005, depth=0.13, loc=tuple(h + Vector((0, 0.02, 0.165))), rot=(0, math.pi / 2, 0)))
            return o
        styles["topknot"] = [_hair_cap(h, mat)] + topknot() + [
            _tube([h + Vector((0, 0.06, 0.12)), h + Vector((0, 0.13, 0.02)), h + Vector((0, 0.15, -0.15)), h + Vector((0, 0.14, -0.35))], 0.03, 0.004, mat, "ponytail")]
        styles["crowned_knot"] = [_hair_cap(h, mat)] + topknot(True)
        styles["long_loose"] = [_hair_cap(h, mat), _hair_sheet(J, h, mat, 0.55, 0.1)] + topknot()[:1]
        styles["half_up"] = [_hair_cap(h, mat), _hair_sheet(J, h, mat, 0.4, 0.1)] + topknot()
        o = [_hair_cap(h, mat)]
        o.append(xm.prim("cyl", SLOT["sash"], vertices=D(32), radius=0.108, depth=0.04, loc=tuple(h + Vector((0, 0.008, 0.03)))))
        styles["headband"] = o
    for objs in styles.values():
        _smooth_uv(objs)
    return styles


def accessories(J, female):
    """Optional pieces toggled per variation: {name: ([objects], allowed_bones)}."""
    h = J["head"] + Vector((0, 0, 0.1))
    acc = {}
    # conical bamboo douli hat
    hat = xm.prim("cone", M("wood"), vertices=D(40), radius1=0.34, radius2=0.01, depth=0.14, loc=tuple(h + Vector((0, 0.01, 0.16))))
    rim = xm.prim("torus", M("leather"), major_radius=0.34, minor_radius=0.006, major_segments=D(40), loc=tuple(h + Vector((0, 0.01, 0.09))))
    acc["hat"] = (_smooth_uv([hat, rim], 2.0), HEADB)
    if female:
        acc["ribbon"] = (_smooth_uv([ribbon(J)]), ARMS + ["spine"])
        veil = xm.prim("cyl", M("silk_white"), vertices=D(32), radius=0.12, depth=0.1, loc=tuple(h + Vector((0, -0.01, -0.05))))
        veil.scale = (1.0, 1.0, 1.0)
        acc["veil"] = (_smooth_uv([veil]), HEADB)
        acc["flute"] = (_smooth_uv([xm.prim("cyl", M("bamboo"), vertices=12, radius=0.012, depth=0.5,
                                            loc=(0.16, 0.12, J["hips"].z + 0.05), rot=(0, 0.5, 0))]), ["hips", "spine"])
    else:
        acc["sword"] = (_smooth_uv(sword_on_back(J)), ["chest"])
        beard = _tube([h + Vector((0, -0.08, -0.07)), h + Vector((0, -0.09, -0.13)), h + Vector((0, -0.07, -0.2))], 0.03, 0.005, SLOT["hair"], "beard")
        mus = []
        for sx in (1, -1):
            mus.append(_tube([h + Vector((sx * 0.01, -0.1, -0.045)), h + Vector((sx * 0.04, -0.095, -0.06)), h + Vector((sx * 0.05, -0.085, -0.1))], 0.006, 0.002, SLOT["hair"], "moustache"))
        acc["beard"] = (_smooth_uv([beard] + mus), HEADB)
        gourd_a = xm.prim("uvsphere", M("wood"), segments=16, ring_count=8, radius=0.06, loc=(0.2, 0.05, J["hips"].z - 0.08))
        gourd_b = xm.prim("uvsphere", M("wood"), segments=16, ring_count=8, radius=0.04, loc=(0.2, 0.05, J["hips"].z + 0.01))
        acc["gourd"] = (_smooth_uv([gourd_a, gourd_b]), ["hips"])
    cape_v, cape_f = [], []
    rows, cols = D(16, 6), D(12, 6)
    for j in range(rows + 1):
        t = j / rows
        z = J["neck"].z - t * (J["neck"].z - 0.35)
        w = 0.18 + t * 0.2
        for i in range(cols + 1):
            u = i / cols - 0.5
            cape_v.append((u * 2 * w, 0.14 + t * 0.12 + 0.03 * math.cos(u * 3), z))
    for j in range(rows):
        for i in range(cols):
            q = j * (cols + 1) + i
            cape_f.append((q, q + 1, q + cols + 2, q + cols + 1))
    cape = xm.mesh_obj("cape", cape_v, cape_f, SLOT["inner"])
    xm.box_uv(cape, 2.0)
    acc["cape"] = (_smooth_uv([cape]), ["chest", "spine", "hips", "thigh.L", "thigh.R"])
    return acc


def ribbon(J):
    """Floating pibo shawl: from one elbow, over the upper back, to the other."""
    pts = [J["elbow.L"] + Vector((0.06, 0.05, -0.35)), J["elbow.L"] + Vector((0.04, 0.05, 0.0)),
           J["shoulder.L"] + Vector((0.02, 0.14, 0.02)), Vector((0, 0.2, J["chest"].z + 0.05)),
           J["shoulder.R"] + Vector((-0.02, 0.14, 0.02)), J["elbow.R"] + Vector((-0.04, 0.05, 0.0)),
           J["elbow.R"] + Vector((-0.06, 0.05, -0.35)), J["elbow.R"] + Vector((-0.1, 0.08, -0.6))]
    pts = [J["elbow.L"] + Vector((0.1, 0.08, -0.6))] + pts
    verts, faces, uvs = [], [], []
    n = 80
    for i in range(n + 1):
        t = i / n
        f = t * (len(pts) - 1)
        k = min(int(f), len(pts) - 2)
        u = f - k
        # Catmull-Rom through the control points
        p0, p1, p2, p3 = pts[max(k - 1, 0)], pts[k], pts[k + 1], pts[min(k + 2, len(pts) - 1)]
        p = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
        w = Vector((0, 0.0, 0.045)) if 0.3 < t < 0.7 else Vector((0, 0.045, 0.0))
        verts += [tuple(p - w), tuple(p + w)]
        uvs += [(0, t * 6), (0.25, t * 6)]
        if i:
            b = len(verts) - 4
            faces.append((b, b + 1, b + 3, b + 2))
    obj = xm.mesh_obj("ribbon", verts, faces, SLOT["sash"], uvs)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def sword_on_back(J):
    objs = []
    c = Vector((0, 0.19, J["chest"].z - 0.12))
    scab = xm.prim("cyl", M("lacquer"), vertices=12, radius=0.022, depth=0.7, loc=tuple(c))
    scab.scale = (1.0, 0.5, 1.0)
    grip = xm.prim("cyl", M("leather"), vertices=10, radius=0.016, depth=0.16, loc=tuple(c + Vector((0, 0, 0.44))))
    guard = xm.box(tuple(c + Vector((0, 0, 0.36))), (0.1, 0.03, 0.022), M("gold"), 0.005, 2)
    pommel = xm.prim("uvsphere", M("jade"), segments=12, ring_count=6, radius=0.018, loc=tuple(c + Vector((0, 0, 0.53))))
    tassel = xm.prim("cone", M("silk_crimson"), vertices=10, radius1=0.004, radius2=0.025, depth=0.12, loc=tuple(c + Vector((0.02, 0, 0.47))))
    for o in (scab, grip, guard, pommel, tassel):
        xm.transform_apply(o)
        o.rotation_euler = (0, 0.6, 0)
        o.location = (0, 0, 0)
        objs.append(o)
    for o in objs:
        # rotate about the scabbard centre
        o.data.transform(__import__("mathutils").Matrix.Translation(-c))
        o.data.transform(__import__("mathutils").Matrix.Rotation(-0.55, 4, "Y"))
        o.data.transform(__import__("mathutils").Matrix.Translation(c))
        o.rotation_euler = (0, 0, 0)
        if not o.data.uv_layers:
            xm.box_uv(o, 3.0)
    return objs


# ---------------------------------------------------------------------------
# Rig + weights
# ---------------------------------------------------------------------------

def build_armature(J):
    arm_data = bpy.data.armatures.new("Rig")
    arm = bpy.data.objects.new("Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones
    for name, h, t, parent in BONES:
        b = eb.new(name)
        b.head = J[h]
        b.tail = J[t]
        b.align_roll(Vector((0, -1, 0)))  # local Z faces forward for every bone
        if parent:
            b.parent = eb[parent]
            b.use_connect = (eb[parent].tail - b.head).length < 1e-4
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (a + ab * t - p).length


def weight(obj, J, allowed, bias=None, power=5.0, top=2):
    bias = bias or {}
    segs = {n: (J[h], J[t]) for n, h, t, _ in BONES if n in allowed}
    groups = {n: obj.vertex_groups.get(n) or obj.vertex_groups.new(name=n) for n in segs}
    mw = obj.matrix_world
    for v in obj.data.vertices:
        p = mw @ v.co
        ds = sorted(((_seg_dist(p, a, b) * bias.get(n, 1.0), n) for n, (a, b) in segs.items()))[:top]
        ws = [(1.0 / max(d, 1e-3) ** power, n) for d, n in ds]
        tot = sum(w for w, _ in ws)
        for w, n in ws:
            groups[n].add([v.index], w / tot, "REPLACE")


ALL = [b[0] for b in BONES]
ARMS = [b for b in ALL if b.startswith(("upper_arm", "forearm", "hand"))] + ["chest"]
LEGS = [b for b in ALL if b.startswith(("thigh", "shin", "foot"))] + ["hips"]
HEADB = ["head", "neck"]


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def key_pose(arm, frame, pose, root_z=0.0):
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        rot = pose.get(pb.name, (0, 0, 0))
        pb.rotation_euler = tuple(math.radians(a) for a in rot)
        pb.keyframe_insert("rotation_euler", frame=frame)
    hips = arm.pose.bones["hips"]
    hips.location = (0, root_z, 0)  # bone-local Y is world up for the hips
    hips.keyframe_insert("location", frame=frame)


def mirror(pose):
    out = dict(pose)
    for k, (x, y, z) in pose.items():
        if k.endswith(".L"):
            out[k[:-2] + ".R"] = (x, -y, -z)
        elif k.endswith(".R"):
            out[k[:-2] + ".L"] = (x, -y, -z)
    return out


def arms_down(extra=0.0):
    return {"upper_arm.L": (0, 0, -4 - extra), "upper_arm.R": (0, 0, 4 + extra)}


def cycle(phase_fn, frames, amp):
    poses = []
    for f in range(0, frames + 1, max(frames // 8, 1)):
        ph = f / frames * math.tau
        poses.append((f + 1, phase_fn(ph, amp)))
    return poses


def walk_pose(ph, amp):
    s = math.sin(ph)
    c = math.cos(ph)
    p = {
        "thigh.L": (amp * s, 0, 0), "thigh.R": (-amp * s, 0, 0),
        "shin.L": (-max(0.0, -c) * amp * 1.3 - 5, 0, 0), "shin.R": (-max(0.0, c) * amp * 1.3 - 5, 0, 0),
        "foot.L": (max(0.0, -s) * 10, 0, 0), "foot.R": (max(0.0, s) * 10, 0, 0),
        "upper_arm.L": (-amp * 0.7 * s, 0, -6), "upper_arm.R": (amp * 0.7 * s, 0, 6),
        "forearm.L": (12 + max(0.0, -s) * amp * 0.5, 0, 0), "forearm.R": (12 + max(0.0, s) * amp * 0.5, 0, 0),
        "spine": (amp * 0.12, amp * 0.12 * s, 0), "chest": (0, -amp * 0.18 * s, 0),
        "neck": (0, amp * 0.1 * s, 0),
    }
    return p


def build_actions(arm):
    arm.animation_data_create()
    actions = {}

    def new_action(name, frames, poses, bob=None):
        act = bpy.data.actions.new(name)
        arm.animation_data.action = act
        for f, pose in poses:
            rz = bob(f) if bob else 0.0
            key_pose(arm, f, pose, rz)
        act.frame_range = (1, frames + 1)
        act.use_frame_range = True
        actions[name] = act
        track = arm.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, act)
        arm.animation_data.action = None

    # idle: slow breathing + sleeve sway (2 s)
    idle = []
    for f in range(0, 49, 6):
        ph = f / 48 * math.tau
        b = math.sin(ph)
        idle.append((f + 1, {"spine": (1.5 * b, 0, 0), "chest": (1.5 * b, 0, 0), "neck": (-1.5 * b, 0, 0),
                             "head": (0, 3 * math.sin(ph * 0.5), 0),
                             "upper_arm.L": (3 * b, 0, -5), "upper_arm.R": (3 * b, 0, 5),
                             "forearm.L": (10 + 2 * b, 0, 0), "forearm.R": (10 + 2 * b, 0, 0),
                             "thigh.L": (0, 0, 1), "thigh.R": (0, 0, -1)}))
    new_action("idle", 48, idle, lambda f: 0.004 * math.sin((f - 1) / 48 * math.tau))
    # walk (1 s) and run (0.6 s)
    new_action("walk", 24, cycle(walk_pose, 24, 28), lambda f: 0.025 * abs(math.cos((f - 1) / 24 * math.tau)))

    def run_pose(ph, amp):
        p = walk_pose(ph, amp)
        s = math.sin(ph)
        p["spine"] = (12, amp * 0.12 * s, 0)
        p["forearm.L"] = (70, 0, 0)
        p["forearm.R"] = (70, 0, 0)
        p["upper_arm.L"] = (-amp * 0.9 * s, 0, -10)
        p["upper_arm.R"] = (amp * 0.9 * s, 0, 10)
        p["neck"] = (-10, 0, 0)
        return p
    new_action("run", 16, cycle(run_pose, 16, 45), lambda f: 0.05 * abs(math.cos((f - 1) / 16 * math.tau)))
    # jump: tucked take-off pose
    jump = {"thigh.L": (55, 0, 0), "thigh.R": (35, 0, 0), "shin.L": (-90, 0, 0), "shin.R": (-70, 0, 0),
            "upper_arm.L": (-30, 0, -35), "upper_arm.R": (-30, 0, 35), "forearm.L": (40, 0, 0), "forearm.R": (40, 0, 0),
            "spine": (10, 0, 0)}
    new_action("jump", 12, [(1, jump), (13, jump)])
    fall = {"thigh.L": (20, 0, 5), "thigh.R": (-10, 0, -5), "shin.L": (-30, 0, 0), "shin.R": (-20, 0, 0),
            "upper_arm.L": (10, 0, -50), "upper_arm.R": (10, 0, 50), "forearm.L": (20, 0, 0), "forearm.R": (20, 0, 0)}
    fall2 = dict(fall)
    fall2["upper_arm.L"] = (5, 0, -58)
    fall2["upper_arm.R"] = (5, 0, 58)
    new_action("fall", 24, [(1, fall), (13, fall2), (25, fall)])
    # qinggong glide: arms spread like wings, legs trailing, gentle wave
    glide = []
    for f in range(0, 49, 8):
        ph = f / 48 * math.tau
        w = math.sin(ph)
        glide.append((f + 1, {"spine": (-8, 0, 0), "chest": (-6, 0, 0), "neck": (12, 0, 0),
                              "upper_arm.L": (-5, 0, -80 - 6 * w), "upper_arm.R": (-5, 0, 80 + 6 * w),
                              "forearm.L": (5, 0, -8 * w), "forearm.R": (5, 0, 8 * w),
                              "thigh.L": (-18, 0, 4), "thigh.R": (-8, 0, -4), "shin.L": (-25, 0, 0), "shin.R": (-45, 0, 0),
                              "foot.L": (30, 0, 0), "foot.R": (30, 0, 0)}))
    new_action("glide", 48, glide)
    # townsfolk: animated conversation and a friendly wave
    talk = []
    for f in range(0, 49, 6):
        ph = f / 48 * math.tau
        talk.append((f + 1, {"upper_arm.R": (25 + 12 * math.sin(ph * 2), 0, 12), "forearm.R": (60 + 20 * math.sin(ph * 2 + 1), 0, 0),
                             "upper_arm.L": (8 + 5 * math.sin(ph), 0, -6), "forearm.L": (30, 0, 0),
                             "head": (4 * math.sin(ph * 2), 6 * math.sin(ph), 0), "spine": (2 * math.sin(ph), 0, 0)}))
    new_action("talk", 48, talk)
    wave = []
    for f in range(0, 25, 3):
        ph = f / 24 * math.tau
        wave.append((f + 1, {"upper_arm.R": (20, 0, 150), "forearm.R": (10, 0, 25 * math.sin(ph * 2)),
                             "upper_arm.L": (0, 0, -5), "head": (0, 0, 5)}))
    new_action("wave", 24, wave)
    return actions


# ---------------------------------------------------------------------------

SLOT = {}


def slot_materials(female):
    """Tintable material per customisation slot. Base textures are neutral
    (white silk, fair skin, black hair) and Godot multiplies a per-variation
    colour into albedo, so one model covers every colourway."""
    SLOT.clear()
    SLOT["skin"] = xm.material("skin", albedo="skin_fair_albedo", rough=0.55)
    SLOT["hair"] = xm.material("hair", albedo="hair_black_albedo", rough=0.4)
    SLOT["robe"] = xm.material("robe", albedo="silk_white_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True)
    SLOT["inner"] = xm.material("inner", albedo="silk_white_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True)
    SLOT["sash"] = xm.material("sash", albedo="silk_white_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True)
    SLOT["boots"] = xm.material("boots", albedo="leather_belt_albedo", normal="leather_belt_normal", rough=0.7)


def build(female, npc=False):
    global DETAIL
    DETAIL = 0.5 if npc else 1.0
    xg.reset_scene()
    xm._image_cache.clear()
    slot_materials(female)
    J = proportions(female)
    groups = {}  # exported object name -> list of parts

    def add(group, objs, allowed, bias=None, power=5.0):
        for o in (objs if isinstance(objs, list) else [objs]):
            xm.transform_apply(o)
            weight(o, J, allowed, bias, power)
            groups.setdefault(group, []).append(o)

    add("body", body(J, female, SLOT["skin"]), ALL)
    add("body", head(J, female, SLOT["skin"]), HEADB)
    for style, objs in hair_styles(J, female).items():
        add("hair_" + style, objs, HEADB + ["chest"], {"head": 0.6})
    robe_parts = robe(J, female, SLOT["robe"], SLOT["inner"], M("gold"))
    inner = [o for o in robe_parts if o.name.startswith("collar")]
    sash = [o for o in robe_parts if o.data.materials and o.data.materials[0] in (SLOT["sash"], M("jade"))]
    outer = [o for o in robe_parts if o not in inner and o not in sash]
    add("inner", inner, ["chest", "neck", "spine"])
    add("sash", sash, ["hips", "spine"])
    add("robe", outer, ["hips", "spine", "chest", "thigh.L", "thigh.R", "shin.L", "shin.R"],
        {"hips": 0.55, "spine": 0.8, "chest": 0.8, "shin.L": 1.4, "shin.R": 1.4}, power=3.0)
    add("robe", sleeves(J, SLOT["robe"], female), ARMS)
    add("boots", boots(J), ["foot.L", "foot.R", "shin.L", "shin.R"])
    for name, (objs, bones) in accessories(J, female).items():
        add("acc_" + name, objs, bones, {"chest": 0.8}, power=3.0)
    arm = build_armature(J)
    meshes = []
    for group, objs in groups.items():
        for o in objs:
            if "Col" not in o.data.color_attributes:
                xm.vcol_gradient(o, lambda co: (1.0, 1.0, 1.0))
        mesh = xm.join(objs, group)
        mesh.parent = arm
        mod = mesh.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        meshes.append(mesh)
    build_actions(arm)
    os.makedirs(xg.CHAR_DIR, exist_ok=True)
    name = ("npc_" if npc else "cultivator_") + ("female" if female else "male")
    path = os.path.join(xg.CHAR_DIR, name + ".glb")
    size = xm.export_glb(path, meshes + [arm], extra_export=dict(
        export_animations=True, export_animation_mode="NLA_TRACKS", export_skins=True, export_def_bones=False,
        export_force_sampling=True, export_frame_step=1, export_anim_single_armature=True, export_reset_pose_bones=True))
    xg.log("character %s %d KB %d verts, parts: %s" % (name, size // 1024, sum(len(m.data.vertices) for m in meshes),
                                                       ", ".join(sorted(groups))))
    return meshes, arm


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    prev = args[args.index("--preview") + 1] if "--preview" in args else None
    for npc in (False, True):
        for female in (False, True):
            meshes, arm = build(female, npc)
            if prev:
                import gen_models
                arm.data.pose_position = "REST"
                shown = [m for m in meshes if not m.name.startswith(("hair_", "acc_")) or m.name in ("hair_topknot", "hair_twin_buns")]
                for m in meshes:
                    m.hide_render = m not in shown
                gen_models.preview(shown[0], os.path.join(prev, arm.name + ("_npc" if npc else "") + ("_f" if female else "_m") + ".png"))


if __name__ == "__main__":
    main()
