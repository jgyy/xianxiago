"""Geometry, material and export helpers for the model generators."""

import json
import math
import os
import shutil
import struct
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

import xg_common as xg

# ---------------------------------------------------------------------------
# Materials: Principled BSDF fed by the shared textures in assets/textures.
# The exported .glb references those PNGs by relative URI (see export_glb),
# so every model shares one imported copy of each texture.
# ---------------------------------------------------------------------------

_image_cache = {}


def _image(name):
    if name in _image_cache and _image_cache[name].name in bpy.data.images:
        return _image_cache[name]
    path = os.path.join(xg.TEX_DIR, name + ".png")
    img = bpy.data.images.load(path, check_existing=True)
    img.name = name + ".png"
    _image_cache[name] = img
    return img


def material(name, albedo=None, normal=None, color=(1, 1, 1), rough=0.8, metal=0.0,
             alpha_clip=False, double_sided=False, emission=None, emission_strength=1.0,
             normal_strength=1.0, vcol=False):
    key = "M_" + name
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    base = None
    if albedo:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = _image(albedo)
        base = tex.outputs["Color"]
        if alpha_clip:
            # glTF exporter maps alpha -> Greater Than into alphaMode MASK
            cut = nodes.new("ShaderNodeMath")
            cut.operation = "GREATER_THAN"
            cut.inputs[1].default_value = 0.5
            links.new(tex.outputs["Alpha"], cut.inputs[0])
            links.new(cut.outputs[0], bsdf.inputs["Alpha"])
    if color != (1, 1, 1) or base is None:
        rgb = nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = tuple(color) + (1.0,)
        if base is None:
            base = rgb.outputs[0]
        else:
            mix = nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            links.new(base, mix.inputs[6])
            links.new(rgb.outputs[0], mix.inputs[7])
            base = mix.outputs[2]
    if vcol:
        ca = nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "Col"
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        links.new(base, mix.inputs[6])
        links.new(ca.outputs["Color"], mix.inputs[7])
        base = mix.outputs[2]
    links.new(base, bsdf.inputs["Base Color"])
    if normal:
        nt_img = nodes.new("ShaderNodeTexImage")
        nt_img.image = _image(normal)
        nt_img.image.colorspace_settings.name = "Non-Color"
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = normal_strength
        links.new(nt_img.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = tuple(emission) + (1.0,)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha_clip:
        mat.surface_render_method = "DITHERED"
    mat.use_backface_culling = not double_sided
    return mat


# Common palette so every model reads as the same world.
def M(kind):
    table = {
        "bark_pine": dict(albedo="bark_pine_albedo", normal="bark_pine_normal", rough=0.95, vcol=True),
        "bark_maple": dict(albedo="bark_maple_albedo", normal="bark_maple_normal", rough=0.95, vcol=True),
        "bark_cherry": dict(albedo="bark_cherry_albedo", normal="bark_cherry_normal", rough=0.85, vcol=True),
        "bark_birch": dict(albedo="bark_birch_albedo", normal="bark_birch_normal", rough=0.85, vcol=True),
        "bark_dead": dict(albedo="bark_maple_albedo", normal="bark_maple_normal", color=(0.78, 0.74, 0.70), rough=0.95, vcol=True),
        "bamboo": dict(albedo="bamboo_stalk_albedo", normal="bamboo_stalk_normal", rough=0.5),
        "leaf_pine": dict(albedo="leaves_pine_albedo", alpha_clip=True, double_sided=True, rough=0.9, vcol=True),
        "leaf_maple": dict(albedo="leaves_maple_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "leaf_cherry": dict(albedo="leaves_cherry_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "leaf_willow": dict(albedo="leaves_willow_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "leaf_bamboo": dict(albedo="leaves_bamboo_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "leaf_ginkgo": dict(albedo="leaves_ginkgo_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "leaf_broad": dict(albedo="leaves_broad_albedo", alpha_clip=True, double_sided=True, rough=0.8, vcol=True),
        "grass": dict(albedo="grass_blades_albedo", alpha_clip=True, double_sided=True, rough=0.9, vcol=True),
        "fern": dict(albedo="fern_frond_albedo", alpha_clip=True, double_sided=True, rough=0.85, vcol=True),
        "flowers": dict(albedo="flowers_meadow_albedo", alpha_clip=True, double_sided=True, rough=0.8),
        "lotus_leaf": dict(albedo="lotus_leaf_albedo", alpha_clip=True, double_sided=True, rough=0.5),
        "rock": dict(albedo="terrain_rock_albedo", normal="terrain_rock_normal", rough=0.9, vcol=True),
        "rock_mossy": dict(albedo="rock_mossy_albedo", normal="rock_mossy_normal", rough=0.9, vcol=True),
        "rock_lichen": dict(albedo="rock_lichen_albedo", normal="rock_lichen_normal", rough=0.9, vcol=True),
        "cliff": dict(albedo="terrain_cliff_albedo", normal="terrain_cliff_normal", rough=0.95, vcol=True),
        "stone": dict(albedo="stone_paving_albedo", normal="stone_paving_normal", rough=0.85),
        "stone_brick": dict(albedo="stone_bricks_albedo", normal="stone_bricks_normal", rough=0.9),
        "marble": dict(albedo="marble_white_albedo", normal="marble_white_normal", rough=0.35),
        "plaster": dict(albedo="plaster_wall_albedo", normal="plaster_wall_normal", rough=0.9),
        "wood": dict(albedo="wood_planks_albedo", normal="wood_planks_normal", rough=0.75),
        "lacquer": dict(albedo="lacquer_red_albedo", normal="lacquer_red_normal", rough=0.35),
        "roof_jade": dict(albedo="roof_tiles_jade_albedo", normal="roof_tiles_jade_normal", rough=0.35),
        "roof_crimson": dict(albedo="roof_tiles_crimson_albedo", normal="roof_tiles_crimson_normal", rough=0.4),
        "gold": dict(albedo="gold_trim_albedo", normal="gold_trim_normal", rough=0.3, metal=0.9),
        "bronze": dict(albedo="bronze_patina_albedo", normal="bronze_patina_normal", rough=0.5, metal=0.6),
        "iron": dict(albedo="iron_cast_albedo", normal="iron_cast_normal", rough=0.6, metal=0.7),
        "celadon": dict(albedo="celadon_glaze_albedo", normal="celadon_glaze_normal", rough=0.2),
        "jade": dict(albedo="jade_stone_albedo", normal="jade_stone_normal", rough=0.15, emission=(0.10, 0.35, 0.22), emission_strength=0.6),
        "crystal": dict(albedo="crystal_spirit_albedo", normal="crystal_spirit_normal", rough=0.1, emission=(0.25, 0.85, 0.80), emission_strength=1.6),
        "crystal_violet": dict(albedo="crystal_spirit_albedo", normal="crystal_spirit_normal", color=(0.85, 0.55, 1.0), rough=0.1, emission=(0.55, 0.30, 0.95), emission_strength=1.6),
        "talisman": dict(albedo="paper_talisman", double_sided=True, rough=0.9),
        "banner": dict(albedo="banner_silk", double_sided=True, rough=0.7),
        "lantern_paper": dict(albedo="lantern_paper", rough=0.8, emission=(1.0, 0.55, 0.22), emission_strength=2.0),
        "mushroom": dict(albedo="mushroom_cap", rough=0.6),
        "mushroom_stem": dict(albedo="plaster_wall_albedo", color=(0.95, 0.9, 0.8), rough=0.7),
        "leather": dict(albedo="leather_belt_albedo", normal="leather_belt_normal", rough=0.7),
        "silk_jade": dict(albedo="silk_jade_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True),
        "silk_white": dict(albedo="silk_white_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True),
        "silk_crimson": dict(albedo="silk_crimson_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True),
        "silk_indigo": dict(albedo="silk_indigo_albedo", normal="fabric_weave_normal", rough=0.5, double_sided=True),
        "skin_fair": dict(albedo="skin_fair_albedo", rough=0.55),
        "skin_tan": dict(albedo="skin_tan_albedo", rough=0.55),
        "hair": dict(albedo="hair_black_albedo", rough=0.4),
        "embroidery": dict(albedo="embroidery_cloud_albedo", alpha_clip=True, double_sided=True, rough=0.4, metal=0.5),
        "flower_pink": dict(albedo="leaves_cherry_albedo", alpha_clip=True, double_sided=True, rough=0.5, emission=(0.9, 0.5, 0.7), emission_strength=0.3),
        "moss": dict(albedo="terrain_moss_albedo", normal="terrain_moss_normal", rough=0.95),
        "dirt": dict(albedo="terrain_dirt_albedo", normal="terrain_dirt_normal", rough=0.95),
        "snow": dict(albedo="terrain_snow_albedo", normal="terrain_snow_normal", rough=0.6),
        "glow_white": dict(color=(1.0, 0.95, 0.8), emission=(1.0, 0.85, 0.55), emission_strength=4.0),
        "glow_qi": dict(color=(0.6, 1.0, 0.9), emission=(0.35, 1.0, 0.85), emission_strength=3.0),
        "cloud": dict(albedo="silk_white_albedo", color=(1.0, 1.0, 1.0), rough=0.9, emission=(0.6, 0.65, 0.7), emission_strength=0.3),
        "lotus_flower": dict(albedo="leaves_cherry_albedo", color=(1.0, 0.85, 0.9), double_sided=True, rough=0.5, emission=(0.9, 0.55, 0.7), emission_strength=0.5),
    }
    return material(kind, **table[kind])


# ---------------------------------------------------------------------------
# Object helpers
# ---------------------------------------------------------------------------

def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, mat=None, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    obj = _link(bpy.data.objects.new(name, me))
    if uvs is not None:
        layer = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uvs[me.loops[li].vertex_index]
    if mat:
        me.materials.append(mat)
    return obj


def prim(kind, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), **kw):
    ops = {
        "cube": bpy.ops.mesh.primitive_cube_add,
        "cyl": bpy.ops.mesh.primitive_cylinder_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "uvsphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "ico": bpy.ops.mesh.primitive_ico_sphere_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "plane": bpy.ops.mesh.primitive_plane_add,
        "grid": bpy.ops.mesh.primitive_grid_add,
    }
    ops[kind](location=loc, rotation=rot, **kw)
    obj = bpy.context.active_object
    obj.scale = scale
    if mat:
        obj.data.materials.append(mat)
    return obj


def modifier(obj, kind, apply=True, **props):
    m = obj.modifiers.new(kind.lower(), kind)
    for k, v in props.items():
        setattr(m, k, v)
    if apply:
        _apply(obj, m.name)
    return m


def _apply(obj, name):
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=name)


def bevel(obj, width=0.03, segments=3):
    modifier(obj, "BEVEL", width=width, segments=segments, limit_method="ANGLE")
    return obj


def subsurf(obj, levels=1):
    modifier(obj, "SUBSURF", levels=levels, render_levels=levels)
    return obj


def displace(obj, strength=0.3, scale=1.0, kind="VORONOI", seed=0, mid=0.5, direction="NORMAL"):
    tex = bpy.data.textures.new("disp%d" % seed, kind)
    if kind == "VORONOI":
        tex.noise_scale = scale
        tex.distance_metric = "DISTANCE"
        tex.weight_1 = 1.0
    elif kind == "CLOUDS":
        tex.noise_scale = scale
        tex.noise_depth = 4
    elif kind == "MUSGRAVE" if hasattr(bpy.types, "MusgraveTexture") else False:
        tex.noise_scale = scale
    m = obj.modifiers.new("disp", "DISPLACE")
    m.texture = tex
    m.strength = strength
    m.mid_level = mid
    m.direction = direction
    m.texture_coords = "LOCAL"
    # offset the texture space per seed so variants differ
    empty = bpy.data.objects.new("dispco%d" % seed, None)
    _link(empty)
    empty.location = (seed * 3.7, seed * 1.3, seed * 2.1)
    m.texture_coords = "OBJECT"
    m.texture_coords_object = empty
    _apply(obj, m.name)
    bpy.data.objects.remove(empty)
    return obj


def smooth_by_angle(obj, degrees=35.0):
    """Smooth shading with hard edges kept where faces meet sharply, so the
    exporter doesn't split every vertex of a subdivided flat-shaded block."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    limit = math.radians(degrees)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > limit)
    bm.to_mesh(obj.data)
    bm.free()


def transform_apply(obj):
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis = Matrix.Identity(4)


def join(objs, name="Model"):
    objs = [o for o in objs if o is not None]
    for o in objs:
        transform_apply(o)
    target = objs[0]
    if len(objs) > 1:
        with bpy.context.temp_override(object=target, active_object=target, selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def copy(obj, loc=None, rot=None, scale=None):
    new = obj.copy()
    new.data = obj.data.copy()
    _link(new)
    if loc is not None:
        new.location = loc
    if rot is not None:
        new.rotation_euler = rot
    if scale is not None:
        new.scale = scale
    return new


# ---------------------------------------------------------------------------
# UVs
# ---------------------------------------------------------------------------

def box_uv(obj, scale=1.0, offset=(0.0, 0.0)):
    """World-scale box projection: each face takes the plane its normal
    faces most, so tiling textures keep a constant texel density."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    layer = me.uv_layers.active.data
    mw = obj.matrix_world
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = mw @ me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else:
                u, v = co.x, co.y
            layer[li].uv = (u * scale + offset[0], v * scale + offset[1])
    return obj


def cyl_uv(obj, scale_u=1.0, scale_v=1.0, center=(0, 0)):
    """Cylindrical projection around local Z (trunks, stalks, columns)."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    layer = me.uv_layers.active.data
    for poly in me.polygons:
        us = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a = math.atan2(co.y - center[1], co.x - center[0]) / math.tau + 0.5
            us.append(a)
        # keep a face from straddling the seam
        if max(us) - min(us) > 0.5:
            us = [u + 1.0 if u < 0.5 else u for u in us]
        for li, u in zip(poly.loop_indices, us):
            co = me.vertices[me.loops[li].vertex_index].co
            layer[li].uv = (u * scale_u, co.z * scale_v)
    return obj


# ---------------------------------------------------------------------------
# Vertex colour (ambient occlusion-ish tint) and foliage normals
# ---------------------------------------------------------------------------

def vcol_gradient(obj, fn):
    me = obj.data
    if "Col" not in me.color_attributes:
        me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    attr = me.color_attributes["Col"]
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            c = fn(co)
            attr.data[li].color = (c[0], c[1], c[2], 1.0)
    return obj


def height_ao(obj, z0, z1, lo=0.55, hi=1.0, tint=(1, 1, 1)):
    def fn(co):
        t = min(max((co.z - z0) / max(z1 - z0, 1e-4), 0.0), 1.0)
        k = lo + (hi - lo) * t
        return (k * tint[0], k * tint[1], k * tint[2])
    return vcol_gradient(obj, fn)


def radial_ao(obj, center, radius, lo=0.5, hi=1.1, tint=(1, 1, 1), jitter=0.12, seed=0):
    c = Vector(center)

    def fn(co):
        d = (co - c).length / max(radius, 1e-4)
        k = lo + (hi - lo) * min(d, 1.0) + (noise.noise(co * 0.7 + Vector((seed, 0, 0))) * jitter)
        return (k * tint[0], k * tint[1], k * tint[2])
    return vcol_gradient(obj, fn)


def foliage_normals(obj, center):
    """Points every foliage normal away from the canopy centre so cards
    shade like one soft volume instead of flickering flat quads."""
    me = obj.data
    c = Vector(center)
    normals = []
    for loop in me.loops:
        v = me.vertices[loop.vertex_index].co - c
        if v.length < 1e-5:
            v = Vector((0, 0, 1))
        normals.append(v.normalized())
    me.normals_split_custom_set(normals)
    return obj


# ---------------------------------------------------------------------------
# Procedural building blocks
# ---------------------------------------------------------------------------

def skin_tree(name, skeleton, mat, subdiv=1):
    """skeleton: list of (pos, parent_index, radius). Builds a skinned,
    subdivided trunk/branch mesh."""
    verts = [p for p, _, _ in skeleton]
    edges = [(i, par) for i, (_, par, _) in enumerate(skeleton) if par >= 0]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], edges, [])
    obj = _link(bpy.data.objects.new(name, me))
    mod = obj.modifiers.new("skin", "SKIN")
    mod.use_smooth_shade = True
    for i, (_, _, r) in enumerate(skeleton):
        obj.data.skin_vertices[0].data[i].radius = (r, r)
    obj.data.skin_vertices[0].data[0].use_root = True
    _apply(obj, mod.name)
    if subdiv:
        subsurf(obj, subdiv)
    for p in obj.data.polygons:
        p.use_smooth = True
    obj.data.materials.append(mat)
    return obj


def grow_branches(rng, start, direction, length, radius, depth, max_depth, out, parent,
                  segs=6, spread=0.6, gravity=0.0, twist=0.25, taper=0.62, children=(2, 3),
                  tips=None, child_len=0.62, up_bias=0.25, first_branch=None, max_nodes=240):
    """Recursive branch skeleton for skin_tree."""
    d = Vector(direction).normalized()
    pos = Vector(start)
    idx = parent
    step = length / segs
    for s in range(segs):
        d = (d + Vector(rng.normal(0, twist, 3)) + Vector((0, 0, -gravity))).normalized()
        pos = pos + d * step
        r = radius * (1.0 - 0.75 * (s + 1) / segs)
        out.append((pos.copy(), idx, max(r, 0.012)))
        idx = len(out) - 1
        start = segs // 3 if first_branch is None or depth > 0 else int(segs * first_branch)
        if depth < max_depth and s >= start and rng.random() < 0.55 and len(out) < max_nodes:
            n = int(rng.integers(children[0], children[1] + 1)) if s == segs - 1 else 1
            for _ in range(n):
                side = Vector(rng.normal(0, 1, 3))
                side.z = abs(side.z) * up_bias
                cd = (d * (1 - spread) + side.normalized() * spread).normalized()
                grow_branches(rng, pos, cd, length * child_len * rng.uniform(0.7, 1.1), r * taper, depth + 1,
                              max_depth, out, idx, max(3, segs - 1), spread, gravity, twist, taper, children,
                              tips, child_len, up_bias, first_branch, max_nodes)
    if tips is not None:
        tips.append((pos.copy(), d.copy(), depth))
    return idx


def cards(center_list, size, rng, per=6, mat=None, name="cards", uv_tiles=2, upright=False, droop=0.0, flat=0.0):
    """Clusters of crossed quads (leaf/needle/grass cards). Each card maps a
    random sub-rectangle of the atlas so neighbours don't repeat."""
    verts, faces, uvs = [], [], []
    for c, sz in center_list:
        for _ in range(per):
            if upright:
                yaw = rng.uniform(0, math.tau)
                ax = Vector((math.cos(yaw), math.sin(yaw), 0))
                up = Vector((rng.normal(0, 0.15), rng.normal(0, 0.15), 1)).normalized()
            elif rng.random() < flat:
                # near-horizontal pad (pine tiers, lotus, cloud pads)
                n = Vector((rng.normal(0, 0.25), rng.normal(0, 0.25), 1)).normalized()
                ax = n.cross(Vector((rng.normal(), rng.normal(), 0.0))).normalized()
                up = n.cross(ax).normalized()
            else:
                ax = Vector(rng.normal(0, 1, 3)).normalized()
                up = Vector(rng.normal(0, 1, 3))
                up = (up - ax * up.dot(ax)).normalized()
                up = (up + Vector((0, 0, -droop))).normalized()
            s = sz * size * rng.uniform(0.75, 1.25)
            off = Vector(rng.normal(0, sz * 0.35, 3)) if not upright else Vector((rng.normal(0, sz * 0.4), rng.normal(0, sz * 0.4), 0))
            base = Vector(c) + off
            if upright:
                p = [base - ax * s * 0.5, base + ax * s * 0.5, base + ax * s * 0.5 + up * s, base - ax * s * 0.5 + up * s]
            else:
                p = [base - ax * s * 0.5 - up * s * 0.5, base + ax * s * 0.5 - up * s * 0.5,
                     base + ax * s * 0.5 + up * s * 0.5, base - ax * s * 0.5 + up * s * 0.5]
            i0 = len(verts)
            verts += p
            faces.append((i0, i0 + 1, i0 + 2, i0 + 3))
            u0 = rng.integers(0, uv_tiles) / uv_tiles
            v0 = rng.integers(0, uv_tiles) / uv_tiles if not upright else 0.0
            du = 1.0 / uv_tiles
            dv = du if not upright else 1.0
            uvs += [(u0, v0), (u0 + du, v0), (u0 + du, v0 + dv), (u0, v0 + dv)]
    obj = mesh_obj(name, verts, faces, mat)
    layer = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[obj.data.loops[li].vertex_index]
    return obj


def curved_roof(w, d, h, overhang=0.6, upturn=0.5, res=28, thickness=0.12, mat=None, hip=True, z=0.0,
                tile_pitch=0.28, tile_depth=0.05):
    """Upswept Chinese hip roof as a displaced grid + solidify, with the
    tile rows modelled as real corrugations running down each slope."""
    W, D = w / 2 + overhang, d / 2 + overhang
    tile_pitch = max(tile_pitch, 2 * max(W, D) / 44)
    res = min(140, max(res, int(2 * max(W, D) / tile_pitch * 3)))
    verts, faces, uvs = [], [], []
    for j in range(res + 1):
        for i in range(res + 1):
            x = -W + 2 * W * i / res
            y = -D + 2 * D * j / res
            tx, ty = min(abs(x) / W, 1.0), min(abs(y) / D, 1.0)
            t = max(tx, ty) if hip else ty
            zz = h * (1 - t) ** 1.6
            corner = (tx * ty) ** 3 if hip else tx ** 6 * ty
            zz += upturn * corner + upturn * 0.25 * t ** 4
            # corrugation runs across the slope direction of this facet
            across = x if (not hip or ty >= tx) else y
            zz += tile_depth * abs(math.sin(across / tile_pitch * math.pi))
            verts.append((x, y, z + zz))
            uvs.append((x * 0.5, (y if abs(y) / D >= abs(x) / W else x) * 0.5 + zz * 0.5))
    for j in range(res):
        for i in range(res):
            a = j * (res + 1) + i
            faces.append((a, a + 1, a + res + 2, a + res + 1))
    obj = mesh_obj("roof", verts, faces, mat, uvs)
    modifier(obj, "SOLIDIFY", thickness=thickness, offset=-1.0)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def column(x, y, z0, z1, r, mat, sides=24):
    obj = prim("cyl", mat, loc=(x, y, (z0 + z1) / 2), vertices=sides, radius=r, depth=z1 - z0)
    for p in obj.data.polygons:
        p.use_smooth = True
    bevel(obj, r * 0.15, 2)
    return obj


def box(loc, size, mat, bev=0.02, segs=3):
    obj = prim("cube", mat, loc=loc, scale=(size[0] / 2, size[1] / 2, size[2] / 2))
    transform_apply(obj)
    if bev:
        bevel(obj, bev, segs)
    return obj


def rock(seed, size=(1.0, 1.0, 0.8), subdiv=5, strength=0.35, mat=None, sink=0.15, flat=True, sharp=0.5):
    rng = np.random.default_rng(seed)
    obj = prim("ico", mat, subdivisions=subdiv, radius=1.0)
    displace(obj, strength * sharp, rng.uniform(0.5, 0.9), "VORONOI", seed)
    displace(obj, strength * 0.5, rng.uniform(0.25, 0.45), "CLOUDS", seed + 100)
    obj.scale = size
    transform_apply(obj)
    if flat:
        me = obj.data
        for v in me.vertices:
            if v.co.z < -size[2] * (1 - sink):
                v.co.z = -size[2] * (1 - sink) + (v.co.z + size[2] * (1 - sink)) * 0.15
        obj.location.z = size[2] * (1 - sink)
        transform_apply(obj)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


# ---------------------------------------------------------------------------
# Export: glTF separate -> repack as .glb with image URIs pointing at the
# shared assets/textures PNGs (relative to the .glb).
# ---------------------------------------------------------------------------

def export_glb(path, objs=None, extra_export=None, tex_rel="../textures/"):
    tmp = tempfile.mkdtemp(prefix="xg_gltf_")
    gltf_path = os.path.join(tmp, "model.gltf")
    for o in bpy.context.scene.objects:
        o.select_set(False)
    sel = objs if objs is not None else [o for o in bpy.context.scene.objects if o.type in ("MESH", "ARMATURE")]
    for o in sel:
        o.select_set(True)
    opts = dict(filepath=gltf_path, export_format="GLTF_SEPARATE", use_selection=True, export_apply=True,
                export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                export_image_format="AUTO", export_vertex_color="MATERIAL", export_animations=False)
    if extra_export:
        opts.update(extra_export)
    bpy.ops.export_scene.gltf(**opts)
    with open(gltf_path) as f:
        doc = json.load(f)
    bins = [b for b in doc.get("buffers", [])]
    assert len(bins) == 1, "expected one buffer"
    with open(os.path.join(tmp, bins[0]["uri"]), "rb") as f:
        blob = f.read()
    del doc["buffers"][0]["uri"]
    for img in doc.get("images", []):
        uri = img.get("uri", "")
        img["uri"] = tex_rel + os.path.basename(uri).replace("%20", " ")
        img.pop("mimeType", None)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    blob += b"\0" * ((4 - len(blob) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942))
        f.write(blob)
    shutil.rmtree(tmp, ignore_errors=True)
    return os.path.getsize(path)
