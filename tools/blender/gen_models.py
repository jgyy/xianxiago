"""Generates the world-dressing .glb models under assets/models/.

Every model is built from Blender primitives, skin-modifier branch
skeletons, displaced icospheres and upswept roof grids, textured with the
shared PNGs from gen_textures.py, and exported to .glb whose images point
at ../textures/ so Godot imports each texture once.

    python3.11 tools/blender/gen_models.py [name-filter] [--jobs N --part K]
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xg_common as xg  # noqa: E402  (imports bpy, which provides mathutils)
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import xg_mesh as xm  # noqa: E402
from xg_mesh import M  # noqa: E402

MODELS = []


def model(fn):
    MODELS.append((fn.__name__, fn))
    return fn


def variants(base, count, builder):
    """Registers base_a, base_b, ... each calling builder(seed, index)."""
    for i in range(count):
        name = "%s_%s" % (base, "abcdefgh"[i])

        def fn(i=i, name=name):
            return builder(1000 + sum(map(ord, base)) % 997 + i * 31, i)
        fn.__name__ = name
        MODELS.append((name, fn))


# ---------------------------------------------------------------------------
# TREES
# ---------------------------------------------------------------------------

def broadleaf_tree(seed, idx, bark, leaf, height=7.0, trunk_r=0.32, crown=3.2, depth=3, per=14,
                   card=1.25, gravity=0.0, droop=0.0, lean=0.12, children=(2, 3), leaf_tint=(1, 1, 1)):
    """Clear trunk to ~45% height, then limbs splitting into a rounded crown
    of leaf-card clusters on every outer twig."""
    rng = np.random.default_rng(seed)
    skel = [((0, 0, -0.3), -1, trunk_r * 1.6), ((0, 0, 0.25), 0, trunk_r * 1.25)]
    tips = []
    trunk_dir = Vector((rng.normal(0, lean), rng.normal(0, lean), 1.0))
    xm.grow_branches(rng, (0, 0, 0.25), trunk_dir, height * 0.62, trunk_r, 0, depth, skel, 1, segs=8,
                     spread=0.62, gravity=gravity, twist=0.14, children=children, tips=tips, child_len=0.6,
                     up_bias=0.9, first_branch=0.5)
    trunk = xm.skin_tree("trunk", skel, M(bark), subdiv=1)
    xm.box_uv(trunk, 0.6)
    xm.height_ao(trunk, 0.0, height * 0.6, 0.55, 1.0)
    clusters = []
    for p, par, r in skel:
        if r < trunk_r * 0.3 and p.z > height * 0.35:
            clusters.append((p, 0.8))
    for p, d, dpt in tips:
        clusters.append((p + d * 0.3, 1.0))
    if len(clusters) > 200:  # keep every tree in the same vertex budget
        keep = rng.choice(len(clusters), 200, replace=False)
        clusters = [clusters[k] for k in sorted(keep)]
    leaves = xm.cards(clusters, card * crown / 3.2, rng, per=per, mat=M(leaf), droop=droop, flat=0.3)
    zs = [p.z for p, _ in clusters] or [height]
    ctr = Vector((0, 0, (min(zs) + max(zs)) / 2))
    xm.foliage_normals(leaves, ctr - Vector((0, 0, 1.0)))
    xm.radial_ao(leaves, ctr, crown * 1.2, 0.45, 1.15, leaf_tint, seed=seed)
    return [trunk, leaves]


def pine_tree(seed, idx):
    """Layered conifer: straight trunk, drooping whorls of branches, each
    carrying flat needle pads so the silhouette reads as stacked tiers."""
    rng = np.random.default_rng(seed)
    h = rng.uniform(9.0, 12.0) + idx * 1.2
    r = 0.26 + 0.05 * idx
    skel = [((0, 0, -0.3), -1, r * 1.5)]
    for i in range(1, 16):
        z = h * i / 15
        skel.append(((rng.normal(0, 0.05), rng.normal(0, 0.05), z), i - 1, max(r * (1 - 0.95 * i / 15), 0.03)))
    clusters = []
    tiers = 8 + idx
    for t in range(tiers):
        f = t / (tiers - 1)
        z = h * (0.3 + 0.64 * f)
        span = (1.0 - f) ** 1.1 * (3.0 + 0.4 * idx) + 0.5
        n = 6 + int((1 - f) * 4)
        for k in range(n):
            a = k / n * math.tau + rng.normal(0, 0.25) + t * 0.7
            parent = min(int(round(z / h * 15)), 15)
            root = Vector(skel[parent][0])
            end = root + Vector((math.cos(a) * span, math.sin(a) * span, -span * 0.35 + 0.2))
            mid = root.lerp(end, 0.5) + Vector((0, 0, span * 0.12))
            skel.append((mid, parent, r * 0.18))
            skel.append((end, len(skel) - 1, 0.015))
            steps = max(2, int(span / 0.45))
            for j in range(steps):
                q = (j + 1) / steps
                pt = root.lerp(mid, min(q * 2, 1)) if q < 0.5 else mid.lerp(end, (q - 0.5) * 2)
                clusters.append((pt + Vector((0, 0, 0.1)), 0.55 + 0.5 * (1 - q) * (1 - f)))
    clusters.append((Vector(skel[15][0]), 0.6))
    trunk = xm.skin_tree("trunk", skel, M("bark_pine"), subdiv=1)
    xm.box_uv(trunk, 0.7)
    xm.height_ao(trunk, 0, h * 0.5, 0.5, 1.0)
    leaves = xm.cards(clusters, 1.7, rng, per=6, mat=M("leaf_pine"), droop=0.3, flat=0.6)
    xm.foliage_normals(leaves, Vector((0, 0, h * 0.35)))
    xm.radial_ao(leaves, Vector((0, 0, h * 0.5)), h * 0.5, 0.5, 1.1, (0.95, 1.0, 0.95), seed=seed)
    return [trunk, leaves]


variants("pine_tree", 4, pine_tree)
variants("maple_tree", 3, lambda s, i: broadleaf_tree(s, i, "bark_maple", "leaf_maple", 6.5 + i, 0.3, 3.0, 3, 16, 1.4, leaf_tint=(1.0, 0.95, 0.9)))
variants("cherry_tree", 3, lambda s, i: broadleaf_tree(s, i, "bark_cherry", "leaf_cherry", 5.5 + i * 0.7, 0.26, 3.0, 3, 18, 1.3, gravity=0.04, lean=0.2))
def willow_tree(seed, idx):
    rng = np.random.default_rng(seed)
    trunk, crown = broadleaf_tree(seed, idx, "bark_maple", "leaf_willow", 7.0 + idx, 0.4, 2.8, 2, 8, 1.3,
                                  children=(3, 4), lean=0.2)
    # curtains of hanging leaf strands from the outer crown
    verts, faces, uvs = [], [], []
    pts = [v.co.copy() for v in list(crown.data.vertices)[::7]]
    for p in pts:
        if p.z < 4.0:
            continue
        L = rng.uniform(2.0, 3.6)
        yaw = rng.uniform(0, math.tau)
        ax = Vector((math.cos(yaw), math.sin(yaw), 0)) * 0.35
        top = p
        bot = p + Vector((rng.normal(0, 0.2), rng.normal(0, 0.2), -L))
        i0 = len(verts)
        verts += [top - ax, top + ax, bot + ax * 0.4, bot - ax * 0.4]
        faces.append((i0, i0 + 1, i0 + 2, i0 + 3))
        u0 = rng.integers(0, 2) / 2
        uvs += [(u0, 1), (u0 + 0.5, 1), (u0 + 0.5, 0), (u0, 0)]
    strands = xm.mesh_obj("strands", verts, faces, M("leaf_willow"))
    layer = strands.data.uv_layers.new(name="UVMap")
    for poly in strands.data.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[strands.data.loops[li].vertex_index]
    xm.foliage_normals(strands, Vector((0, 0, 3.0)))
    xm.height_ao(strands, 1.0, 7.0, 0.5, 1.05)
    return [trunk, crown, strands]


variants("willow_tree", 2, willow_tree)
variants("ginkgo_tree", 2, lambda s, i: broadleaf_tree(s, i, "bark_birch", "leaf_ginkgo", 8.0 + i, 0.3, 2.6, 3, 16, 1.2, lean=0.05, children=(2, 2)))


def dead_tree(seed, idx):
    rng = np.random.default_rng(seed)
    skel = [((0, 0, -0.3), -1, 0.45), ((0, 0, 0.3), 0, 0.38)]
    tips = []
    xm.grow_branches(rng, (0, 0, 0.3), (0.1, 0.05, 1), 5.5 + idx, 0.34, 0, 3, skel, 1, segs=7, spread=0.7,
                     twist=0.3, children=(2, 3), tips=tips, child_len=0.7, up_bias=0.6)
    trunk = xm.skin_tree("trunk", skel, M("bark_dead"), subdiv=1)
    xm.box_uv(trunk, 0.6)
    xm.height_ao(trunk, 0, 4, 0.45, 1.0, (0.95, 0.92, 0.9))
    return [trunk]


variants("dead_tree", 2, dead_tree)


def twisted_pine(seed, idx):
    """Cliff-clinging huangshan pine: a gnarled trunk with flat cloud pads."""
    rng = np.random.default_rng(seed)
    skel = [((0, 0, -0.3), -1, 0.5)]
    pos = Vector((0, 0, 0))
    d = Vector((0.6, 0.2, 1)).normalized()
    for i in range(12):
        d = (d + Vector((rng.normal(0, 0.35), rng.normal(0, 0.35), 0.05))).normalized()
        pos = pos + d * 0.55
        skel.append((pos.copy(), len(skel) - 1, 0.42 * (1 - i / 14)))
    pads = []
    for i in range(4, 13, 2):
        base = len(skel)
        a = rng.uniform(0, math.tau)
        L = rng.uniform(1.6, 2.8)
        end = Vector(skel[i][0]) + Vector((math.cos(a) * L, math.sin(a) * L, rng.uniform(-0.1, 0.5)))
        skel.append((Vector(skel[i][0]).lerp(end, 0.5), i, 0.12))
        skel.append((end, base, 0.06))
        pads.append(end)
    pads.append(Vector(skel[12][0]))
    trunk = xm.skin_tree("trunk", skel, M("bark_pine"), subdiv=2)
    xm.box_uv(trunk, 0.7)
    xm.height_ao(trunk, 0, 6, 0.5, 1.0)
    clusters = []
    for p in pads:
        for k in range(10):
            clusters.append((p + Vector((rng.normal(0, 0.8), rng.normal(0, 0.8), rng.normal(0, 0.12))), 0.8))
    leaves = xm.cards(clusters, 1.4, rng, per=8, mat=M("leaf_pine"))
    for v in leaves.data.vertices:  # flatten pads into layered clouds
        v.co.z = v.co.z * 0.6 + 0.4 * round(v.co.z / 0.5) * 0.5
    xm.foliage_normals(leaves, Vector((0, 0, 2)))
    xm.radial_ao(leaves, Vector((0, 0, 3)), 4, 0.5, 1.1, seed=seed)
    return [trunk, leaves]


variants("twisted_pine", 2, twisted_pine)


def bamboo_cluster(seed, idx):
    rng = np.random.default_rng(seed)
    objs = []
    clusters = []
    n = 9 + idx * 4
    for k in range(n):
        x, y = rng.normal(0, 0.9 + idx * 0.3, 2)
        h = rng.uniform(6, 10)
        lean = Vector((rng.normal(0, 0.06), rng.normal(0, 0.06), 1)).normalized()
        stalk = xm.prim("cyl", M("bamboo"), vertices=12, radius=rng.uniform(0.06, 0.1), depth=h, loc=(0, 0, h / 2))
        xm.cyl_uv(stalk, 1.0, 0.5)
        stalk.rotation_euler = lean.to_track_quat("Z", "Y").to_euler()
        stalk.location = (x, y, 0)
        for p in stalk.data.polygons:
            p.use_smooth = True
        objs.append(stalk)
        for j in range(5):
            t = rng.uniform(0.45, 1.0)
            clusters.append((Vector((x, y, 0)) + lean * h * t, 0.8))
    leaves = xm.cards(clusters, 1.5, rng, per=10, mat=M("leaf_bamboo"), droop=0.4)
    xm.foliage_normals(leaves, Vector((0, 0, 7)))
    xm.radial_ao(leaves, Vector((0, 0, 8)), 4, 0.55, 1.1, seed=seed)
    return objs + [leaves]


variants("bamboo_cluster", 3, bamboo_cluster)


# ---------------------------------------------------------------------------
# ROCKS
# ---------------------------------------------------------------------------

def boulder(seed, idx):
    rng = np.random.default_rng(seed)
    mats = ["rock_mossy", "rock_lichen", "rock", "rock_mossy", "rock_lichen", "rock"]
    s = rng.uniform(1.0, 2.2)
    r = xm.rock(seed, (s * rng.uniform(1.0, 1.5), s * rng.uniform(0.8, 1.2), s * rng.uniform(0.6, 1.0)), 7,
                0.45, M(mats[idx % 6]))
    xm.box_uv(r, 0.5)
    xm.height_ao(r, 0, s, 0.55, 1.05)
    return [r]


variants("boulder", 6, boulder)


def cliff_spire(seed, idx):
    rng = np.random.default_rng(seed)
    h = rng.uniform(7, 12)
    objs = []
    for k in range(2 + idx % 2):
        r = xm.rock(seed + k, (rng.uniform(1.0, 1.8), rng.uniform(1.0, 1.8), 1.0), 6, 0.35, M("cliff"), flat=False)
        r.scale = (1, 1, h * rng.uniform(0.45, 0.8) / 2 * (1 if k == 0 else 0.7))
        r.location = (rng.normal(0, 0.8), rng.normal(0, 0.8), h * 0.3 * (1 if k == 0 else 0.5))
        xm.transform_apply(r)
        xm.displace(r, 0.3, 0.6, "CLOUDS", seed + 50 + k)
        objs.append(r)
    for o in objs:
        xm.box_uv(o, 0.35)
        xm.height_ao(o, 0, h, 0.5, 1.05)
    return objs


variants("cliff_spire", 4, cliff_spire)


def floating_isle(seed, idx):
    rng = np.random.default_rng(seed)
    top = xm.rock(seed, (4.5, 3.8, 1.0), 5, 0.4, M("moss"), flat=False)
    for v in top.data.vertices:
        if v.co.z > 0.2:
            v.co.z = 0.2 + (v.co.z - 0.2) * 0.2
    under = xm.rock(seed + 1, (3.8, 3.2, 4.5), 5, 0.6, M("cliff"), flat=False)
    for v in under.data.vertices:
        if v.co.z > 0:
            v.co.z *= 0.1
        else:
            k = -v.co.z / 4.5
            v.co.x *= (1 - k * 0.8)
            v.co.y *= (1 - k * 0.8)
    xm.box_uv(top, 0.4)
    xm.box_uv(under, 0.35)
    xm.height_ao(under, -4.5, 0, 0.4, 1.0)
    objs = [top, under]
    for t in range(1 + idx):
        tree = pine_tree(seed + 7 + t, 0) if t % 2 == 0 else broadleaf_tree(seed + 7 + t, 0, "bark_cherry", "leaf_cherry", 4.5, 0.2, 2.2, 2, 12, 1.0)
        off = Vector((rng.normal(0, 1.4), rng.normal(0, 1.2), 0.1))
        for o in tree:
            o.scale = (0.45, 0.45, 0.45)
            o.location = off
        objs += tree
    for o in objs:
        o.location.z += 12.0
    return objs


variants("floating_isle", 2, floating_isle)


@model
def stepping_stones():
    rng = np.random.default_rng(7)
    objs = []
    for k in range(7):
        r = xm.rock(100 + k, (rng.uniform(0.5, 0.8), rng.uniform(0.45, 0.7), 0.25), 4, 0.12, M("stone"))
        r.location = (k * 1.1, rng.normal(0, 0.3), 0)
        xm.transform_apply(r)
        xm.box_uv(r, 0.6)
        objs.append(r)
    return objs


@model
def rock_arch():
    objs = []
    for s in (-1, 1):
        p = xm.rock(300 + s, (1.3, 1.1, 4.0), 5, 0.4, M("rock_lichen"), flat=True)
        p.location = (s * 3.0, 0, 0)
        xm.transform_apply(p)
        objs.append(p)
    top = xm.rock(305, (4.6, 1.2, 1.0), 5, 0.4, M("rock_lichen"), flat=False)
    for v in top.data.vertices:
        v.co.z += 6.8 - 0.12 * v.co.x * v.co.x
    objs.append(top)
    for o in objs:
        xm.box_uv(o, 0.4)
        xm.height_ao(o, 0, 7, 0.5, 1.05)
    return objs


# ---------------------------------------------------------------------------
# SMALL VEGETATION
# ---------------------------------------------------------------------------

def grass_tuft(seed, idx):
    rng = np.random.default_rng(seed)
    pts = [(Vector((rng.normal(0, 0.4), rng.normal(0, 0.4), 0)), 1.0) for _ in range(30 + idx * 6)]
    g = xm.cards(pts, 0.7 + idx * 0.12, rng, per=6, mat=M("grass"), upright=True, uv_tiles=4)
    xm.foliage_normals(g, Vector((0, 0, -2.0)))
    xm.height_ao(g, 0, 0.8, 0.5, 1.1)
    return [g]


variants("grass_tuft", 4, grass_tuft)


def fern(seed, idx):
    rng = np.random.default_rng(seed)
    verts, faces, uvs = [], [], []
    for f in range(16 + idx * 6):
        a = f / (16 + idx * 6) * math.tau + rng.normal(0, 0.2)
        L = rng.uniform(0.9, 1.4)
        tilt = rng.uniform(0.5, 1.0)
        segs = 10
        for s in range(segs + 1):
            t = s / segs
            r = L * t
            z = math.sin(t * math.pi * 0.8) * tilt * 0.8 - t * t * 0.3
            c = Vector((math.cos(a) * r, math.sin(a) * r, z))
            side = Vector((-math.sin(a), math.cos(a), 0)) * 0.22
            verts += [c - side, c + side]
            uvs += [(0, t), (1, t)]
            if s:
                b = len(verts) - 4
                faces.append((b, b + 1, b + 3, b + 2))
    obj = xm.mesh_obj("fern", verts, faces, M("fern"), uvs)
    xm.modifier(obj, "SUBSURF", levels=1)
    xm.foliage_normals(obj, Vector((0, 0, -1.0)))
    xm.height_ao(obj, 0, 0.8, 0.5, 1.1)
    return [obj]


variants("fern", 2, fern)


def flower_patch(seed, idx):
    rng = np.random.default_rng(seed)
    pts = [(Vector((rng.normal(0, 0.8), rng.normal(0, 0.8), 0)), 1.0) for _ in range(26)]
    g = xm.cards(pts, 0.5, rng, per=5, mat=M("grass"), upright=True, uv_tiles=4)
    xm.foliage_normals(g, Vector((0, 0, -2.0)))
    xm.height_ao(g, 0, 0.6, 0.55, 1.1)
    heads = [(Vector((rng.normal(0, 0.8), rng.normal(0, 0.8), rng.uniform(0.3, 0.6))), 0.35) for _ in range(40 + 10 * idx)]
    fl = xm.cards(heads, 0.9, rng, per=2, mat=M("flowers"), uv_tiles=3)
    stems = []
    for p, _ in heads[::3]:
        st = xm.prim("cyl", M("grass"), vertices=5, radius=0.012, depth=p.z, loc=(p.x, p.y, p.z / 2))
        xm.box_uv(st, 1.0)
        stems.append(st)
    return [g, fl] + stems


variants("flower_patch", 3, flower_patch)


def mushroom_cluster(seed, idx):
    rng = np.random.default_rng(seed)
    objs = []
    for k in range(5 + idx * 3):
        x, y = rng.normal(0, 0.3, 2)
        h = rng.uniform(0.15, 0.5) * (1.6 if k == 0 else 1)
        stem = xm.prim("cyl", M("mushroom_stem"), vertices=16, radius=h * 0.12, depth=h, loc=(x, y, h / 2))
        xm.subsurf(stem, 1)
        cap = xm.prim("uvsphere", M("mushroom"), segments=24, ring_count=12, radius=h * 0.45, loc=(x, y, h))
        for v in cap.data.vertices:
            if v.co.z < 0:
                v.co.z *= 0.15
            v.co.z *= 0.7
        for o in (stem, cap):
            for p in o.data.polygons:
                p.use_smooth = True
            xm.box_uv(o, 3.0)
        objs += [stem, cap]
    return objs


variants("mushroom_cluster", 2, mushroom_cluster)


def bush(seed, idx):
    rng = np.random.default_rng(seed)
    leaf = ["leaf_broad", "leaf_maple", "leaf_cherry"][idx]
    skel = [((0, 0, -0.1), -1, 0.08)]
    tips = []
    for k in range(5):
        xm.grow_branches(rng, (0, 0, 0), (rng.normal(0, 0.6), rng.normal(0, 0.6), 1), 1.2, 0.06, 1, 2, skel, 0,
                         segs=4, spread=0.6, tips=tips)
    stems = xm.skin_tree("stems", skel, M("bark_maple"), subdiv=1)
    xm.box_uv(stems, 1.0)
    xm.height_ao(stems, 0, 1, 0.5, 1.0)
    clusters = [(p, 0.9) for p, _, _ in tips] + [(Vector((rng.normal(0, 0.5), rng.normal(0, 0.5), rng.uniform(0.4, 1.2))), 0.9) for _ in range(12)]
    leaves = xm.cards(clusters, 1.0, rng, per=14, mat=M(leaf))
    xm.foliage_normals(leaves, Vector((0, 0, 0.3)))
    xm.radial_ao(leaves, Vector((0, 0, 0.6)), 1.4, 0.5, 1.1, seed=seed)
    return [stems, leaves]


variants("bush", 3, bush)


@model
def lotus_pads():
    rng = np.random.default_rng(11)
    objs = []
    for k in range(14):
        p = xm.prim("grid", M("lotus_leaf"), x_subdivisions=12, y_subdivisions=12, size=rng.uniform(0.6, 1.1),
                    loc=(rng.normal(0, 1.4), rng.normal(0, 1.4), 0.02))
        for v in p.data.vertices:
            v.co.z = 0.08 * (v.co.x ** 2 + v.co.y ** 2) ** 0.5
        p.rotation_euler.z = rng.uniform(0, math.tau)
        me = p.data
        layer = me.uv_layers.active.data
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                layer[li].uv = (co.x + 0.5, co.y + 0.5)
        objs.append(p)
    for k in range(3):
        c = Vector((rng.normal(0, 1.0), rng.normal(0, 1.0), 0.25))
        for layer_i, (n, r, tilt) in enumerate(((8, 0.22, 0.9), (6, 0.16, 0.5))):
            for j in range(n):
                a = j / n * math.tau + layer_i * 0.3
                pet = xm.prim("uvsphere", M("lotus_flower"), segments=12, ring_count=8, radius=0.12,
                              loc=(c.x + math.cos(a) * r * 0.5, c.y + math.sin(a) * r * 0.5, c.z + 0.1))
                pet.scale = (0.5, 1.0, 0.25)
                pet.rotation_euler = (tilt, 0, a - math.pi / 2)
                xm.box_uv(pet, 2.0)
                objs.append(pet)
        core = xm.prim("uvsphere", M("glow_white"), segments=12, ring_count=8, radius=0.06, loc=tuple(c + Vector((0, 0, 0.12))))
        objs.append(core)
    return objs


@model
def reeds():
    rng = np.random.default_rng(12)
    pts = [(Vector((rng.normal(0, 0.8), rng.normal(0, 0.8), 0)), 1.0) for _ in range(40)]
    g = xm.cards(pts, 1.8, rng, per=4, mat=M("grass"), upright=True, uv_tiles=4)
    xm.foliage_normals(g, Vector((0, 0, -3.0)))
    xm.height_ao(g, 0, 1.8, 0.5, 1.1)
    heads = []
    for k in range(18):
        p = Vector((rng.normal(0, 0.8), rng.normal(0, 0.8), rng.uniform(1.4, 2.0)))
        h = xm.prim("cyl", M("leather"), vertices=8, radius=0.035, depth=0.25, loc=tuple(p))
        xm.box_uv(h, 2)
        heads.append(h)
    return [g] + heads


# ---------------------------------------------------------------------------
# ARCHITECTURE
# ---------------------------------------------------------------------------

def platform(w, d, h, mat="stone", steps=True):
    objs = [xm.box((0, 0, h / 2), (w, d, h), M(mat), 0.04)]
    if steps:
        for s in range(3):
            objs.append(xm.box((0, -d / 2 - 0.3 - s * 0.3, h * (2 - s) / 3 / 2), (w * 0.35, 0.6 + s * 0.6, h * (3 - s) / 3), M(mat), 0.02))
    for o in objs:
        xm.box_uv(o, 0.5)
    return objs


def ridge_ornaments(w, d, z, mat="gold"):
    objs = []
    for sx in (-1, 1):
        o = xm.prim("cone", M(mat), vertices=12, radius1=0.16, radius2=0.02, depth=0.7,
                    loc=(sx * w / 2, 0, z + 0.3), rot=(0, sx * 0.5, 0))
        xm.box_uv(o, 1.0)
        objs.append(o)
    ridge = xm.prim("cyl", M(mat), vertices=12, radius=0.09, depth=w, loc=(0, 0, z), rot=(0, math.pi / 2, 0))
    xm.box_uv(ridge, 1.0)
    objs.append(ridge)
    return objs


def pavilion(w, d, col_h, roof="roof_jade", hexa=False, tiers=1):
    objs = platform(w + 1.2, d + 1.2, 0.5)
    z = 0.5
    for t in range(tiers):
        k = 1.0 - 0.18 * t
        ww, dd = w * k, d * k
        pts = [(math.cos(a) * ww / 2, math.sin(a) * dd / 2) for a in np.linspace(0, math.tau, 7)[:-1]] if hexa else \
            [(x * ww / 2, y * dd / 2) for x in (-1, 1) for y in (-1, 1)]
        if not hexa and ww > 4:
            pts += [(0, y * dd / 2) for y in (-1, 1)]
        for x, y in pts:
            objs.append(xm.column(x, y, z, z + col_h, 0.16, M("lacquer")))
            base = xm.prim("cyl", M("stone"), vertices=16, radius=0.24, depth=0.18, loc=(x, y, z + 0.09))
            objs.append(base)
        # beams + railing
        for sgn in (-1, 1):
            objs.append(xm.box((0, sgn * dd / 2, z + col_h - 0.15), (ww + 0.3, 0.2, 0.3), M("lacquer"), 0.02))
            objs.append(xm.box((sgn * ww / 2, 0, z + col_h - 0.15), (0.2, dd + 0.3, 0.3), M("lacquer"), 0.02))
            objs.append(xm.box((0, sgn * dd / 2, z + col_h - 0.45), (ww, 0.08, 0.14), M("gold"), 0.01))
            if t == 0:
                objs.append(xm.box((sgn * ww / 2, 0, z + 0.55), (0.1, dd, 0.08), M("wood"), 0.01))
        roof_obj = xm.curved_roof(ww, dd, 1.2 + 0.2 * w / 4, overhang=0.9, upturn=0.55, mat=M(roof), z=z + col_h)
        objs.append(roof_obj)
        objs += ridge_ornaments(ww * 0.3 if not hexa else 0.3, dd, z + col_h + 1.25 + 0.2 * w / 4)
        z += col_h + 0.9
        col_h *= 0.75
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    finial = xm.prim("uvsphere", M("gold"), segments=16, ring_count=10, radius=0.22, loc=(0, 0, z + 0.9))
    xm.box_uv(finial, 1.0)
    objs.append(finial)
    return objs


@model
def pavilion_square():
    return pavilion(4.0, 4.0, 3.0)


@model
def pavilion_hex():
    return pavilion(4.2, 4.2, 3.0, "roof_crimson", hexa=True)


def pagoda(tiers, roof, w=4.5):
    objs = platform(w + 1.6, w + 1.6, 0.6)
    z = 0.6
    ww = w
    for t in range(tiers):
        h = 2.6 if t == 0 else 2.0
        objs.append(xm.box((0, 0, z + h / 2), (ww, ww, h), M("plaster"), 0.03))
        for x in (-1, 1):
            for y in (-1, 1):
                objs.append(xm.column(x * ww / 2, y * ww / 2, z, z + h, 0.14, M("lacquer")))
        for sgn in (-1, 1):
            objs.append(xm.box((0, sgn * (ww / 2 + 0.02), z + h * 0.45), (ww * 0.3, 0.06, h * 0.6), M("lacquer"), 0.01))
            objs.append(xm.box((sgn * (ww / 2 + 0.02), 0, z + h * 0.45), (0.06, ww * 0.3, h * 0.6), M("wood"), 0.01))
        objs.append(xm.curved_roof(ww, ww, 0.9, overhang=1.0, upturn=0.6, mat=M(roof), z=z + h))
        z += h + 0.6
        ww *= 0.82
    spire = xm.prim("cyl", M("gold"), vertices=16, radius=0.08, depth=2.2, loc=(0, 0, z + 1.1))
    objs.append(spire)
    for k in range(5):
        ring = xm.prim("torus", M("gold"), major_radius=0.3 - k * 0.04, minor_radius=0.04, loc=(0, 0, z + 0.4 + k * 0.35))
        objs.append(ring)
    for o in objs:
        if not o.data.uv_layers or o.data.uv_layers.active is None:
            xm.box_uv(o, 0.6)
    return objs


@model
def pagoda_small():
    return pagoda(3, "roof_jade", 4.0)


@model
def pagoda_tall():
    return pagoda(7, "roof_crimson", 5.0)


def gate(w=6.0, h=6.0, roof="roof_jade", posts=2):
    objs = []
    xs = np.linspace(-w / 2, w / 2, posts)
    for x in xs:
        objs.append(xm.column(x, 0, 0, h, 0.28, M("lacquer")))
        objs.append(xm.box((x, 0, 0.35), (0.9, 0.9, 0.7), M("stone"), 0.05))
    objs.append(xm.box((0, 0, h * 0.78), (w + 1.2, 0.35, 0.4), M("lacquer"), 0.03))
    objs.append(xm.box((0, 0, h * 0.62), (w + 0.4, 0.3, 0.3), M("lacquer"), 0.03))
    objs.append(xm.box((0, 0.18, h * 0.70), (w * 0.35, 0.06, 0.7), M("gold"), 0.02))
    objs.append(xm.curved_roof(w + 0.8, 0.8, 0.5, overhang=0.6, upturn=0.5, mat=M(roof), z=h * 0.84, hip=False, res=20))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


@model
def shrine_gate():
    return gate(5.0, 5.5, "roof_jade")


@model
def mountain_gate():
    objs = gate(9.0, 8.0, "roof_crimson", posts=4)
    tab = xm.box((0, 0.25, 5.6), (2.4, 0.08, 1.0), M("jade"), 0.02)
    xm.box_uv(tab, 0.5)
    return objs + [tab]


def stone_lantern(seed, idx):
    h = 1.6 + idx * 0.5
    mat = M(["stone", "rock_lichen", "bronze"][idx])
    objs = [xm.box((0, 0, 0.12), (0.8, 0.8, 0.24), mat, 0.04)]
    shaft = xm.prim("cyl", mat, vertices=8 if idx != 1 else 24, radius=0.16, depth=h * 0.5, loc=(0, 0, 0.24 + h * 0.25))
    objs.append(shaft)
    objs.append(xm.box((0, 0, 0.24 + h * 0.5 + 0.06), (0.62, 0.62, 0.12), mat, 0.03))
    box = xm.box((0, 0, 0.24 + h * 0.5 + 0.34), (0.5, 0.5, 0.44), mat, 0.03)
    objs.append(box)
    glow = xm.box((0, 0, 0.24 + h * 0.5 + 0.34), (0.52, 0.3, 0.26), M("lantern_paper"), 0.0)
    objs.append(glow)
    cap = xm.prim("cone", mat, vertices=8 if idx != 1 else 24, radius1=0.6, radius2=0.08, depth=0.45, loc=(0, 0, 0.24 + h * 0.5 + 0.78))
    objs.append(cap)
    top = xm.prim("uvsphere", mat, segments=16, ring_count=8, radius=0.1, loc=(0, 0, 0.24 + h * 0.5 + 1.05))
    objs.append(top)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
        for p in o.data.polygons:
            p.use_smooth = idx == 1
    return objs


variants("stone_lantern", 3, stone_lantern)


def stone_pillar(seed, idx):
    h = 5.0 + idx
    objs = [xm.box((0, 0, 0.3), (1.4, 1.4, 0.6), M("stone"), 0.06)]
    shaft = xm.prim("cyl", M("marble" if idx else "stone"), vertices=32, radius=0.45, depth=h, loc=(0, 0, 0.6 + h / 2))
    for p in shaft.data.polygons:
        p.use_smooth = True
    xm.bevel(shaft, 0.05, 3)
    xm.cyl_uv(shaft, 2.0, 0.5)
    objs.append(shaft)
    # coiled dragon ribbon
    verts, faces = [], []
    turns, segs = 3.0, 180
    for s in range(segs + 1):
        t = s / segs
        a = t * turns * math.tau
        z = 0.8 + t * (h - 0.6)
        r = 0.52 + 0.05 * math.sin(t * 40)
        c = Vector((math.cos(a) * r, math.sin(a) * r, z))
        verts += [tuple(c + Vector((0, 0, -0.09))), tuple(c + Vector((0, 0, 0.09)))]
        if s:
            b = len(verts) - 4
            faces.append((b, b + 2, b + 3, b + 1))
    rib = xm.mesh_obj("ribbon", verts, faces, M("gold" if idx else "jade"))
    xm.modifier(rib, "SOLIDIFY", thickness=0.1)
    xm.subsurf(rib, 1)
    xm.box_uv(rib, 1.0)
    objs.append(rib)
    objs.append(xm.box((0, 0, 0.6 + h + 0.2), (1.1, 1.1, 0.4), M("stone"), 0.05))
    orb = xm.prim("uvsphere", M("crystal"), segments=24, ring_count=12, radius=0.35, loc=(0, 0, 0.6 + h + 0.75))
    for p in orb.data.polygons:
        p.use_smooth = True
    objs.append(orb)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


variants("stone_pillar", 2, stone_pillar)


@model
def stone_arch():
    objs = []
    segs = 20
    for s in range(segs):
        a0 = math.pi * s / segs
        a1 = math.pi * (s + 1) / segs
        am = (a0 + a1) / 2
        blk = xm.box((0, 0, 0), (0.95, 1.2, 0.8), M("stone_brick"), 0.05)
        blk.rotation_euler.y = -am + math.pi / 2
        blk.location = (math.cos(am) * 3.0, 0, 3.5 + math.sin(am) * 3.0)
        objs.append(blk)
    for x in (-3.0, 3.0):
        objs.append(xm.box((x, 0, 1.75), (1.0, 1.3, 3.5), M("stone_brick"), 0.05))
    for o in objs:
        xm.box_uv(o, 0.6)
    return objs


@model
def arched_bridge():
    objs = []
    L, W = 10.0, 2.4
    verts, faces = [], []
    n = 40
    for i in range(n + 1):
        x = -L / 2 + L * i / n
        z = 1.8 * math.cos(x / L * math.pi) ** 1.2 if abs(x) < L / 2 else 0
        for y in (-W / 2, W / 2):
            verts.append((x, y, z + 0.1))
        if i:
            b = len(verts) - 4
            faces.append((b, b + 2, b + 3, b + 1))
    deck = xm.mesh_obj("deck", verts, faces, M("stone"))
    xm.modifier(deck, "SOLIDIFY", thickness=0.45)
    xm.box_uv(deck, 0.6)
    objs.append(deck)
    for i in range(0, n + 1, 4):
        x = -L / 2 + L * i / n
        z = 1.8 * math.cos(x / L * math.pi) ** 1.2
        for y in (-W / 2, W / 2):
            p = xm.box((x, y, z + 0.6), (0.18, 0.18, 0.9), M("marble"), 0.02)
            objs.append(p)
            objs.append(xm.prim("uvsphere", M("marble"), segments=12, ring_count=6, radius=0.12, loc=(x, y, z + 1.1)))
    for y in (-W / 2, W / 2):
        rv, rf = [], []
        for i in range(n + 1):
            x = -L / 2 + L * i / n
            z = 1.8 * math.cos(x / L * math.pi) ** 1.2
            rv += [(x, y, z + 0.4), (x, y, z + 0.85)]
            if i:
                b = len(rv) - 4
                rf.append((b, b + 2, b + 3, b + 1))
        rail = xm.mesh_obj("rail", rv, rf, M("marble"))
        xm.modifier(rail, "SOLIDIFY", thickness=0.1)
        xm.box_uv(rail, 0.8)
        objs.append(rail)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


@model
def plank_bridge():
    rng = np.random.default_rng(3)
    objs = []
    for i in range(24):
        x = -6 + i * 0.5
        z = -0.4 * math.cos(x / 12 * math.pi) + 0.8
        p = xm.box((x, 0, z), (0.42, 1.8 + rng.normal(0, 0.05), 0.08), M("wood"), 0.015)
        p.rotation_euler = (rng.normal(0, 0.03), rng.normal(0, 0.03), rng.normal(0, 0.03))
        objs.append(p)
    for x in (-6, -2, 2, 6):
        for y in (-0.95, 0.95):
            objs.append(xm.column(x, y, -1.0, 1.9, 0.08, M("wood")))
    for y in (-0.95, 0.95):
        rope = xm.prim("cyl", M("leather"), vertices=8, radius=0.03, depth=12.4, loc=(0, y, 1.6), rot=(0, math.pi / 2, 0))
        objs.append(rope)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.8)
    return objs


@model
def wall_segment():
    objs = [xm.box((0, 0, 1.5), (6.0, 0.6, 3.0), M("plaster"), 0.03),
            xm.box((0, 0, 0.3), (6.1, 0.7, 0.6), M("stone_brick"), 0.03)]
    objs.append(xm.curved_roof(6.0, 0.6, 0.3, overhang=0.3, upturn=0.15, mat=M("roof_jade"), z=3.0, hip=False, res=24, thickness=0.08))
    for x in (-2, 0, 2):
        win = xm.prim("torus", M("lacquer"), major_radius=0.45, minor_radius=0.06, loc=(x, 0.31, 1.8), rot=(math.pi / 2, 0, 0))
        objs.append(win)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


@model
def wall_corner():
    objs = []
    for rot in (0, math.pi / 2):
        seg = [xm.box((3, 0, 1.5), (6.0, 0.6, 3.0), M("plaster"), 0.03), xm.box((3, 0, 0.3), (6.1, 0.7, 0.6), M("stone_brick"), 0.03)]
        r = xm.curved_roof(6.0, 0.6, 0.3, overhang=0.3, upturn=0.15, mat=M("roof_jade"), z=3.0, hip=False, res=24, thickness=0.08)
        r.location.x = 3
        seg.append(r)
        for o in seg:
            xm.transform_apply(o)
            o.rotation_euler.z = rot
        objs += seg
    tower = xm.box((0, 0, 2.0), (1.4, 1.4, 4.0), M("stone_brick"), 0.04)
    objs.append(tower)
    objs.append(xm.curved_roof(1.4, 1.4, 0.8, overhang=0.5, upturn=0.35, mat=M("roof_jade"), z=4.0))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


@model
def stone_stairs():
    objs = []
    for s in range(14):
        objs.append(xm.box((0, s * 0.45, s * 0.25 + 0.125), (3.0, 0.5, 0.25 + s * 0.02), M("stone"), 0.03))
    for x in (-1.7, 1.7):
        for s in range(0, 14, 3):
            objs.append(xm.box((x, s * 0.45, s * 0.25 + 0.5), (0.3, 0.3, 1.0), M("marble"), 0.03))
    for o in objs:
        xm.box_uv(o, 0.6)
    return objs


@model
def spirit_well():
    objs = []
    ring = xm.prim("cyl", M("stone_brick"), vertices=32, radius=1.0, depth=0.9, loc=(0, 0, 0.45))
    inner = xm.prim("cyl", M("stone_brick"), vertices=32, radius=0.8, depth=1.0, loc=(0, 0, 0.5))
    xm.modifier(ring, "BOOLEAN", object=inner, operation="DIFFERENCE")
    import bpy
    bpy.data.objects.remove(inner)
    xm.cyl_uv(ring, 3.0, 1.0)
    objs.append(ring)
    water = xm.prim("cyl", M("glow_qi"), vertices=32, radius=0.8, depth=0.05, loc=(0, 0, 0.6))
    objs.append(water)
    for x in (-0.9, 0.9):
        objs.append(xm.column(x, 0, 0.9, 2.4, 0.07, M("wood")))
    objs.append(xm.curved_roof(2.0, 1.2, 0.6, overhang=0.3, upturn=0.25, mat=M("roof_crimson"), z=2.4, res=20, thickness=0.06))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.8)
    return objs


@model
def incense_burner():
    objs = []
    body = xm.prim("uvsphere", M("bronze"), segments=32, ring_count=16, radius=0.7, loc=(0, 0, 1.0))
    for v in body.data.vertices:
        if v.co.z > 0.3:
            v.co.z = 0.3 + (v.co.z - 0.3) * 0.2
    objs.append(body)
    for k in range(3):
        a = k / 3 * math.tau
        objs.append(xm.prim("cyl", M("bronze"), vertices=12, radius=0.08, depth=0.8, loc=(math.cos(a) * 0.5, math.sin(a) * 0.5, 0.4)))
    for sx in (-1, 1):
        objs.append(xm.prim("torus", M("bronze"), major_radius=0.2, minor_radius=0.05, loc=(sx * 0.7, 0, 1.35), rot=(math.pi / 2, 0, math.pi / 2)))
    lid = xm.prim("cone", M("gold"), vertices=24, radius1=0.5, radius2=0.1, depth=0.6, loc=(0, 0, 1.6))
    objs.append(lid)
    for k in range(5):
        objs.append(xm.prim("cyl", M("lacquer"), vertices=6, radius=0.015, depth=0.6, loc=(k * 0.08 - 0.16, 0, 1.9)))
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        xm.box_uv(o, 1.0)
    return objs


@model
def bell_tower():
    objs = platform(4.4, 4.4, 0.8)
    for x in (-1.6, 1.6):
        for y in (-1.6, 1.6):
            objs.append(xm.column(x, y, 0.8, 5.5, 0.18, M("lacquer")))
    objs.append(xm.box((0, 0, 5.4), (3.6, 3.6, 0.25), M("wood"), 0.02))
    bell = xm.prim("uvsphere", M("bronze"), segments=32, ring_count=16, radius=0.8, loc=(0, 0, 4.0))
    for v in bell.data.vertices:
        if v.co.z < 0:
            v.co.x *= 1 + (-v.co.z) * 0.4
            v.co.y *= 1 + (-v.co.z) * 0.4
        else:
            v.co.z *= 1.3
    for p in bell.data.polygons:
        p.use_smooth = True
    objs.append(bell)
    objs.append(xm.prim("cyl", M("wood"), vertices=12, radius=0.05, depth=0.7, loc=(0, 0, 5.1)))
    objs.append(xm.curved_roof(3.6, 3.6, 1.4, overhang=1.0, upturn=0.6, mat=M("roof_jade"), z=5.5))
    objs += ridge_ornaments(1.0, 3.6, 6.95)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


@model
def sect_hall():
    W, D = 12.0, 7.0
    objs = platform(W + 2, D + 2, 1.0)
    objs.append(xm.box((0, 0, 1.0 + 2.2), (W - 0.6, D - 0.6, 4.4), M("plaster"), 0.03))
    for i, x in enumerate(np.linspace(-W / 2, W / 2, 7)):
        for y in (-D / 2, D / 2):
            objs.append(xm.column(x, y, 1.0, 5.6, 0.25, M("lacquer")))
    for x in np.linspace(-W / 2 + 1, W / 2 - 1, 5):
        objs.append(xm.box((x, -D / 2 + 0.28, 2.8), (1.4, 0.08, 3.2), M("wood"), 0.02))
        objs.append(xm.box((x, -D / 2 + 0.25, 2.8), (1.2, 0.06, 2.9), M("talisman"), 0.0))
    objs.append(xm.box((0, 0, 5.7), (W + 0.6, D + 0.6, 0.35), M("lacquer"), 0.03))
    objs.append(xm.curved_roof(W, D, 3.0, overhang=1.4, upturn=0.9, mat=M("roof_jade"), z=5.8, res=36))
    objs += ridge_ornaments(W * 0.5, D, 8.8)
    plaque = xm.box((0, -D / 2 - 0.3, 5.0), (2.6, 0.12, 0.9), M("gold"), 0.03)
    objs.append(plaque)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.5)
    return objs


@model
def guardian_lion():
    objs = [xm.box((0, 0, 0.5), (1.2, 1.8, 1.0), M("stone"), 0.05)]
    skel = [((0, 0.3, 1.0), -1, 0.35), ((0, 0.1, 1.6), 0, 0.42), ((0, -0.1, 2.2), 1, 0.4), ((0, -0.25, 2.7), 2, 0.46)]
    for sx in (-1, 1):
        skel.append(((sx * 0.3, -0.4, 1.8), 1, 0.14))
        skel.append(((sx * 0.3, -0.55, 1.1), len(skel) - 1, 0.13))
        skel.append(((sx * 0.35, 0.6, 1.2), 0, 0.2))
    body = xm.skin_tree("lion", skel, M("stone"), subdiv=2)
    xm.displace(body, 0.06, 0.15, "CLOUDS", 5)
    objs.append(body)
    mane = xm.prim("ico", M("stone"), subdivisions=3, radius=0.5, loc=(0, -0.15, 2.65))
    xm.displace(mane, 0.2, 0.08, "VORONOI", 6)
    objs.append(mane)
    ball = xm.prim("uvsphere", M("bronze"), segments=24, ring_count=12, radius=0.22, loc=(0.3, -0.75, 1.2))
    objs.append(ball)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = o is not objs[0]
        xm.box_uv(o, 0.8)
    return objs


def stele(seed, idx):
    objs = []
    if idx == 0:
        turtle = xm.prim("uvsphere", M("stone"), segments=32, ring_count=16, radius=1.0, loc=(0, 0, 0.35))
        turtle.scale = (1.0, 1.5, 0.45)
        xm.transform_apply(turtle)
        xm.displace(turtle, 0.08, 0.1, "VORONOI", seed)
        objs.append(turtle)
    else:
        objs.append(xm.box((0, 0, 0.3), (1.6, 1.0, 0.6), M("stone"), 0.05))
    slab = xm.box((0, 0, 0.6 + 1.6), (1.2, 0.3, 3.2), M("marble" if idx == 0 else "rock_lichen"), 0.04)
    objs.append(slab)
    cap = xm.prim("cyl", M("stone"), vertices=32, radius=0.7, depth=0.3, loc=(0, 0, 0.6 + 3.3), rot=(math.pi / 2, 0, 0))
    objs.append(cap)
    tal = xm.box((0, -0.16, 2.3), (0.5, 0.02, 1.8), M("talisman"), 0.0)
    objs.append(tal)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = o is objs[0] and idx == 0
        if not o.data.uv_layers:
            xm.box_uv(o, 0.8)
    return objs


variants("stele", 2, stele)


@model
def meditation_platform():
    objs = []
    base = xm.prim("cyl", M("marble"), vertices=8, radius=3.0, depth=0.5, loc=(0, 0, 0.25))
    objs.append(base)
    top = xm.prim("cyl", M("jade"), vertices=8, radius=2.2, depth=0.2, loc=(0, 0, 0.6))
    objs.append(top)
    ring = xm.prim("torus", M("gold"), major_radius=1.6, minor_radius=0.04, loc=(0, 0, 0.72))
    objs.append(ring)
    cushion = xm.prim("cyl", M("silk_crimson"), vertices=24, radius=0.45, depth=0.15, loc=(0, 0, 0.78))
    xm.bevel(cushion, 0.06, 3)
    objs.append(cushion)
    for k in range(8):
        a = k / 8 * math.tau
        objs.append(xm.box((math.cos(a) * 2.7, math.sin(a) * 2.7, 0.9), (0.3, 0.3, 0.8), M("stone"), 0.03))
        objs.append(xm.prim("uvsphere", M("crystal"), segments=12, ring_count=8, radius=0.14, loc=(math.cos(a) * 2.7, math.sin(a) * 2.7, 1.45)))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 0.6)
    return objs


# ---------------------------------------------------------------------------
# SPIRIT PROPS
# ---------------------------------------------------------------------------

def crystal_cluster(seed, idx, mat="crystal", n=7, scale=1.0, base=True):
    rng = np.random.default_rng(seed)
    objs = []
    if base:
        b = xm.rock(seed, (1.0 * scale, 0.9 * scale, 0.35 * scale), 4, 0.15, M("rock"))
        xm.box_uv(b, 0.8)
        objs.append(b)
    for k in range(n):
        h = rng.uniform(0.6, 1.6) * scale * (1.5 if k == 0 else 1)
        c = xm.prim("cyl", M(mat), vertices=6, radius=h * 0.16, depth=h, loc=(0, 0, h / 2))
        tip = xm.prim("cone", M(mat), vertices=6, radius1=h * 0.16, radius2=0, depth=h * 0.35, loc=(0, 0, h + h * 0.175))
        crystal = xm.join([c, tip], "crystal")
        crystal.rotation_euler = (rng.normal(0, 0.45), rng.normal(0, 0.45), rng.uniform(0, math.tau))
        crystal.location = (rng.normal(0, 0.3 * scale), rng.normal(0, 0.3 * scale), 0.1 * scale)
        xm.transform_apply(crystal)
        xm.box_uv(crystal, 1.5)
        objs.append(crystal)
    return objs


variants("spirit_stone_cluster", 3, lambda s, i: crystal_cluster(s, i, ["crystal", "crystal_violet", "jade"][i], 7 + i * 2))


@model
def jade_crystal_formation():
    return crystal_cluster(77, 0, "jade", 14, 2.2)


@model
def alchemy_cauldron():
    objs = []
    body = xm.prim("uvsphere", M("bronze"), segments=40, ring_count=20, radius=1.2, loc=(0, 0, 1.6))
    for v in body.data.vertices:
        if v.co.z > 0.6:
            v.co.z = 0.6 + (v.co.z - 0.6) * 0.1
    xm.modifier(body, "SOLIDIFY", thickness=0.08)
    objs.append(body)
    for k in range(3):
        a = k / 3 * math.tau
        leg = xm.prim("cyl", M("bronze"), vertices=16, radius=0.14, depth=1.2, loc=(math.cos(a) * 0.8, math.sin(a) * 0.8, 0.6))
        objs.append(leg)
    for sx in (-1, 1):
        objs.append(xm.box((sx * 0.9, 0, 2.55), (0.12, 0.5, 0.6), M("bronze"), 0.03))
    fire = xm.prim("ico", M("glow_white"), subdivisions=2, radius=0.4, loc=(0, 0, 0.35))
    objs.append(fire)
    mist = xm.prim("ico", M("glow_qi"), subdivisions=3, radius=0.9, loc=(0, 0, 2.2))
    mist.scale = (1, 1, 0.12)
    objs.append(mist)
    band = xm.prim("torus", M("gold"), major_radius=1.22, minor_radius=0.06, loc=(0, 0, 1.6))
    objs.append(band)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        if not o.data.uv_layers or len(o.data.uv_layers) == 0:
            xm.box_uv(o, 0.8)
        else:
            xm.box_uv(o, 0.8)
    return objs


def banner_pole(seed, idx):
    objs = [xm.column(0, 0, 0, 6.0, 0.08, M("lacquer"))]
    objs.append(xm.prim("uvsphere", M("gold"), segments=16, ring_count=8, radius=0.14, loc=(0, 0, 6.1)))
    verts, faces, uvs = [], [], []
    W, H = 1.2, 3.5
    nx, ny = 12, 30
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            x = 0.1 + u * W
            z = 5.6 - (1 - v) * H
            y = 0.12 * math.sin(u * 5 + v * 3 + idx) * u
            verts.append((x if idx == 0 else 0.1 + u * 0.3, y if idx == 0 else 0.1 + u * W * 0.9, z))
            uvs.append((u * 0.5, v))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    flag = xm.mesh_obj("flag", verts, faces, M("banner"), uvs)
    for p in flag.data.polygons:
        p.use_smooth = True
    objs.append(flag)
    objs.append(xm.prim("cyl", M("lacquer"), vertices=8, radius=0.04, depth=1.5, loc=(0.75, 0, 5.6), rot=(0, math.pi / 2, 0)))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


variants("banner_pole", 2, banner_pole)


@model
def sword_in_stone():
    objs = []
    r = xm.rock(88, (1.2, 1.0, 0.8), 5, 0.3, M("rock_lichen"))
    xm.box_uv(r, 0.6)
    objs.append(r)
    blade = xm.prim("cube", M("iron"), loc=(0, 0, 1.9), scale=(0.07, 0.015, 1.0))
    xm.transform_apply(blade)
    for v in blade.data.vertices:
        if v.co.z > 2.7:
            v.co.x *= 0.1
    objs.append(blade)
    guard = xm.box((0, 0, 2.95), (0.5, 0.1, 0.08), M("gold"), 0.02)
    objs.append(guard)
    hilt = xm.prim("cyl", M("leather"), vertices=12, radius=0.035, depth=0.5, loc=(0, 0, 3.2))
    objs.append(hilt)
    pommel = xm.prim("uvsphere", M("jade"), segments=12, ring_count=8, radius=0.06, loc=(0, 0, 3.5))
    objs.append(pommel)
    tassel = xm.prim("cone", M("silk_crimson"), vertices=12, radius1=0.08, radius2=0.01, depth=0.4, loc=(0.05, 0, 3.3), rot=(math.pi, 0, 0))
    objs.append(tassel)
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.5)
    return objs


@model
def wine_gourd():
    objs = []
    a = xm.prim("uvsphere", M("wood"), segments=24, ring_count=12, radius=0.3, loc=(0, 0, 0.3))
    b = xm.prim("uvsphere", M("wood"), segments=24, ring_count=12, radius=0.2, loc=(0, 0, 0.72))
    c = xm.prim("cyl", M("lacquer"), vertices=12, radius=0.05, depth=0.12, loc=(0, 0, 0.95))
    cord = xm.prim("torus", M("silk_crimson"), major_radius=0.16, minor_radius=0.02, loc=(0, 0, 0.55))
    objs += [a, b, c, cord]
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        xm.box_uv(o, 2.0)
    return objs


@model
def barrel_stack():
    objs = []
    for i, (x, y, z) in enumerate(((0, 0, 0), (1.05, 0, 0), (0.52, 0, 0.95))):
        b = xm.prim("cyl", M("wood"), vertices=24, radius=0.48, depth=0.95, loc=(x, y, z + 0.475))
        for v in b.data.vertices:
            k = 1 + 0.12 * (1 - (v.co.z / 0.475) ** 2)
            v.co.x *= k
            v.co.y *= k
        xm.cyl_uv(b, 2.0, 1.0)
        objs.append(b)
        for dz in (0.15, 0.8):
            objs.append(xm.prim("torus", M("iron"), major_radius=0.5, minor_radius=0.025, loc=(x, y, z + dz)))
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


@model
def crate_stack():
    objs = []
    for (x, y, z, s) in ((0, 0, 0, 1.0), (1.05, 0.1, 0, 0.9), (0.4, 0, 1.0, 0.8)):
        objs.append(xm.box((x, y, z + s / 2), (s, s, s), M("wood"), 0.03))
        for dz in (0.15, 0.85):
            objs.append(xm.box((x, y, z + s * dz), (s + 0.03, s + 0.03, 0.07), M("iron"), 0.01))
    for o in objs:
        xm.box_uv(o, 1.0)
    return objs


@model
def talisman_post():
    objs = [xm.column(0, 0, 0, 3.0, 0.15, M("wood"))]
    rng = np.random.default_rng(5)
    for k in range(9):
        a = rng.uniform(0, math.tau)
        z = rng.uniform(1.2, 2.8)
        t = xm.box((math.cos(a) * 0.17, math.sin(a) * 0.17, z), (0.18, 0.01, 0.5), M("talisman"), 0.0)
        t.rotation_euler.z = a + math.pi / 2
        objs.append(t)
    objs.append(xm.prim("torus", M("silk_crimson"), major_radius=0.17, minor_radius=0.03, loc=(0, 0, 2.95)))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


def spirit_herb(seed, idx):
    rng = np.random.default_rng(seed)
    objs = []
    for k in range(7):
        a = k / 7 * math.tau
        leaf = xm.prim("uvsphere", M("moss"), segments=12, ring_count=8, radius=0.25,
                       loc=(math.cos(a) * 0.2, math.sin(a) * 0.2, 0.12))
        leaf.scale = (1.0, 0.35, 0.08)
        leaf.rotation_euler = (0.4, 0, a)
        objs.append(leaf)
    stalk = xm.prim("cyl", M("moss"), vertices=8, radius=0.02, depth=0.8, loc=(0, 0, 0.4))
    objs.append(stalk)
    glow = xm.prim("uvsphere", M("glow_qi" if idx == 0 else "glow_white"), segments=16, ring_count=8, radius=0.09, loc=(0, 0, 0.85))
    objs.append(glow)
    for k in range(5):
        berry = xm.prim("uvsphere", M("crystal_violet" if idx else "crystal"), segments=10, ring_count=6, radius=0.04,
                        loc=(rng.normal(0, 0.08), rng.normal(0, 0.08), 0.6 + rng.uniform(0, 0.2)))
        objs.append(berry)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        xm.box_uv(o, 2.0)
    return objs


variants("spirit_herb", 2, spirit_herb)


@model
def lotus_flower_glow():
    objs = []
    for layer_i, (n, r, tilt, s) in enumerate(((10, 0.35, 1.1, 0.3), (8, 0.25, 0.7, 0.25), (6, 0.15, 0.35, 0.2))):
        for j in range(n):
            a = j / n * math.tau + layer_i * 0.35
            pet = xm.prim("uvsphere", M("lotus_flower"), segments=16, ring_count=10, radius=s,
                          loc=(math.cos(a) * r, math.sin(a) * r, 0.25 + layer_i * 0.05))
            pet.scale = (0.45, 1.0, 0.18)
            pet.rotation_euler = (tilt, 0, a - math.pi / 2)
            objs.append(pet)
    objs.append(xm.prim("uvsphere", M("glow_white"), segments=16, ring_count=8, radius=0.1, loc=(0, 0, 0.35)))
    pad = xm.prim("cyl", M("lotus_leaf"), vertices=32, radius=0.9, depth=0.02, loc=(0, 0, 0.05))
    objs.append(pad)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        xm.box_uv(o, 1.0)
    return objs


@model
def qi_orb_shrine():
    objs = platform(2.4, 2.4, 0.4, "marble", steps=False)
    ped = xm.prim("cyl", M("marble"), vertices=32, radius=0.4, depth=1.4, loc=(0, 0, 1.1))
    xm.subsurf(ped, 1)
    objs.append(ped)
    orb = xm.prim("uvsphere", M("glow_qi"), segments=32, ring_count=16, radius=0.45, loc=(0, 0, 2.3))
    objs.append(orb)
    for k in range(3):
        ring = xm.prim("torus", M("gold"), major_radius=0.7, minor_radius=0.03, loc=(0, 0, 2.3), rot=(k * 1.0, k * 0.6, 0))
        objs.append(ring)
    for o in objs:
        for p in o.data.polygons:
            p.use_smooth = True
        if not o.data.uv_layers:
            xm.box_uv(o, 0.8)
    return objs


@model
def prayer_flags():
    objs = [xm.column(-4, 0, 0, 4.0, 0.08, M("wood")), xm.column(4, 0, 0, 4.0, 0.08, M("wood"))]
    cols = ["silk_crimson", "silk_jade", "silk_white", "silk_indigo", "banner"]
    for k in range(15):
        x = -3.6 + k * 0.52
        z = 3.8 - 0.8 * (1 - (x / 4) ** 2)
        f = xm.box((x, 0, z - 0.25), (0.36, 0.01, 0.5), M(cols[k % 5]), 0.0)
        objs.append(f)
    rope = []
    for k in range(40):
        x0 = -4 + k * 0.2
        z0 = 3.8 - 0.8 * (1 - (x0 / 4) ** 2)
        rope.append(xm.prim("cyl", M("leather"), vertices=6, radius=0.015, depth=0.21, loc=(x0 + 0.1, 0, z0), rot=(0, math.pi / 2, 0)))
    objs += rope
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


@model
def cloud_platform():
    rng = np.random.default_rng(31)
    objs = []
    for k in range(18):
        s = rng.uniform(0.6, 1.3)
        c = xm.prim("ico", M("cloud"), subdivisions=3, radius=s, loc=(rng.normal(0, 1.4), rng.normal(0, 1.4), rng.normal(0, 0.15)))
        c.scale = (1, 1, 0.55)
        objs.append(c)
    for o in objs:
        xm.transform_apply(o)
        xm.displace(o, 0.15, 0.4, "CLOUDS", 40)
        for p in o.data.polygons:
            p.use_smooth = True
        xm.box_uv(o, 0.5)
    for o in objs:
        o.location.z += 3.0
    return objs


@model
def hanging_lantern():
    objs = [xm.column(0, 0, 0, 3.4, 0.07, M("lacquer"))]
    objs.append(xm.box((0.6, 0, 3.3), (1.3, 0.1, 0.1), M("lacquer"), 0.02))
    lamp = xm.prim("uvsphere", M("lantern_paper"), segments=24, ring_count=16, radius=0.35, loc=(1.1, 0, 2.6))
    lamp.scale = (1, 1, 1.25)
    for p in lamp.data.polygons:
        p.use_smooth = True
    xm.transform_apply(lamp)
    xm.cyl_uv(lamp, 1.0, 1.0, (1.1, 0))
    objs.append(lamp)
    for dz in (0.44, -0.44):
        objs.append(xm.prim("cyl", M("lacquer"), vertices=16, radius=0.18, depth=0.06, loc=(1.1, 0, 2.6 + dz)))
    objs.append(xm.prim("cyl", M("silk_crimson"), vertices=8, radius=0.03, depth=0.4, loc=(1.1, 0, 1.95)))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


@model
def weapon_rack():
    objs = [xm.box((0, 0, 0.1), (2.2, 0.6, 0.2), M("wood"), 0.02)]
    for x in (-1.0, 1.0):
        objs.append(xm.column(x, 0, 0.2, 2.0, 0.06, M("lacquer")))
    for z in (0.9, 1.8):
        objs.append(xm.box((0, 0, z), (2.1, 0.1, 0.08), M("lacquer"), 0.01))
    for k in range(5):
        x = -0.8 + k * 0.4
        spear = xm.prim("cyl", M("wood"), vertices=8, radius=0.025, depth=2.6, loc=(x, 0.06, 1.4))
        tip = xm.prim("cone", M("iron"), vertices=8, radius1=0.05, radius2=0, depth=0.3, loc=(x, 0.06, 2.85))
        tas = xm.prim("cone", M("silk_crimson"), vertices=8, radius1=0.07, radius2=0.02, depth=0.18, loc=(x, 0.06, 2.62), rot=(math.pi, 0, 0))
        objs += [spear, tip, tas]
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


@model
def scroll_table():
    objs = [xm.box((0, 0, 0.55), (1.6, 0.8, 0.08), M("lacquer"), 0.02)]
    for x in (-0.7, 0.7):
        for y in (-0.32, 0.32):
            objs.append(xm.box((x, y, 0.26), (0.08, 0.08, 0.52), M("lacquer"), 0.01))
    scroll = xm.box((0, 0, 0.6), (0.9, 0.5, 0.01), M("talisman"), 0.0)
    objs.append(scroll)
    for x in (-0.45, 0.45):
        objs.append(xm.prim("cyl", M("wood"), vertices=12, radius=0.03, depth=0.55, loc=(x, 0, 0.62), rot=(math.pi / 2, 0, 0)))
    objs.append(xm.prim("cyl", M("celadon"), vertices=24, radius=0.1, depth=0.15, loc=(0.6, 0.25, 0.67)))
    objs.append(xm.prim("uvsphere", M("celadon"), segments=24, ring_count=12, radius=0.13, loc=(-0.6, 0.25, 0.72)))
    for o in objs:
        if not o.data.uv_layers:
            xm.box_uv(o, 1.0)
    return objs


@model
def distant_peak():
    """Big backdrop mountain with snow cap, placed far away by the world."""
    obj = xm.prim("grid", M("cliff"), x_subdivisions=160, y_subdivisions=160, size=120)
    for v in obj.data.vertices:
        r = math.hypot(v.co.x, v.co.y) / 60
        base = max(0.0, 1 - r) ** 1.7 * 55 - 8 * max(0.0, r - 0.8)
        n = sum(abs(xm.noise.noise(Vector((v.co.x * f / 30, v.co.y * f / 30, 1.3)))) / f for f in (1, 2, 4, 8))
        v.co.z = base * (0.7 + 0.6 * n) - 2
    for p in obj.data.polygons:
        p.use_smooth = True
    xm.box_uv(obj, 0.06)

    def tint(co):
        k = min(max((co.z - 30) / 12, 0), 1)
        return (0.6 + 1.2 * k, 0.62 + 1.2 * k, 0.66 + 1.2 * k)
    xm.vcol_gradient(obj, tint)
    return [obj]


# ---------------------------------------------------------------------------

WEATHERED = {"M_stone", "M_stone_brick", "M_marble", "M_rock_lichen", "M_plaster", "M_bronze", "M_wood", "M_lacquer"}


def weather(obj, seed):
    """Chipped, uneven surfaces for hand-cut stone / old timber: densify the
    low-poly block and push it around with a fine noise."""
    mats = {m.name for m in obj.data.materials if m}
    # only hand-cut blocks (bevelled boxes, cylinders); organic rocks and
    # trees already carry their own displacement detail
    if not mats & WEATHERED or len(obj.data.vertices) > 800:
        return
    if any(p.use_smooth for p in obj.data.polygons):
        return
    lo = min(obj.dimensions)
    if lo < 0.05:
        return
    xm.modifier(obj, "SUBSURF", subdivision_type="SIMPLE", levels=1, render_levels=1)
    xm.displace(obj, min(0.012, lo * 0.03), 0.06, "CLOUDS", seed)
    xm.smooth_by_angle(obj, 35.0)


def finish(name, objs):
    for k, o in enumerate(objs):
        weather(o, 500 + k)
    for o in objs:
        if "Col" not in o.data.color_attributes:
            xm.vcol_gradient(o, lambda co: (1.0, 1.0, 1.0))
    obj = xm.join(objs, name)
    # every model sits with its origin on the ground at the base centre
    path = os.path.join(xg.MODEL_DIR, name + ".glb")
    size = xm.export_glb(path, [obj])
    nverts = len(obj.data.vertices)
    return size, nverts


def preview(obj, path):
    """Quick Cycles render of the model for eyeballing (not shipped)."""
    import bpy
    scene = bpy.context.scene
    lo = Vector([min(v.co[i] for v in obj.data.vertices) for i in range(3)])
    hi = Vector([max(v.co[i] for v in obj.data.vertices) for i in range(3)])
    ctr = (lo + hi) / 2
    rad = max((hi - lo).length / 2, 0.5)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    d = Vector((1.0, -1.6, 0.35)).normalized()
    cam.location = ctr + d * rad * 2.2
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 40
    scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = (0.8, 0.2, 0.6)
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.65, 0.8, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    scene.world = world
    scene.cycles.samples = 12
    scene.cycles.transparent_max_bounces = 64
    scene.render.resolution_x = scene.render.resolution_y = 320
    scene.render.filepath = path
    scene.view_settings.view_transform = "Standard"
    bpy.ops.render.render(write_still=True)


def main():
    import bpy
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    flt = ""
    jobs, part = 1, 0
    prev_dir = None
    i = 0
    while i < len(args):
        if args[i] == "--preview":
            prev_dir = args[i + 1]
            i += 2
        elif args[i] == "--jobs":
            jobs = int(args[i + 1])
            i += 2
        elif args[i] == "--part":
            part = int(args[i + 1])
            i += 2
        else:
            flt = args[i]
            i += 1
    os.makedirs(xg.MODEL_DIR, exist_ok=True)
    todo = [(n, f) for k, (n, f) in enumerate(MODELS) if (not flt or flt in n) and k % jobs == part]
    for name, fn in todo:
        xg.reset_scene()
        xm._image_cache.clear()
        objs = fn()
        size, nv = finish(name, objs)
        if prev_dir:
            preview(bpy.data.objects[name], os.path.join(prev_dir, name + ".png"))
        xg.log("model %-28s %6d KB %7d verts" % (name, size // 1024, nv))
        bpy.ops.wm.read_factory_settings(use_empty=True)


if __name__ == "__main__":
    main()
