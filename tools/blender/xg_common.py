"""Shared helpers for the headless-Blender asset pipeline.

Run the generators with either a Blender binary or the `bpy` wheel:

    blender -b --python tools/blender/gen_textures.py
    python3.11 tools/blender/gen_textures.py        # with `pip install bpy`

Everything uses fixed seeds, so re-running a generator reproduces the same
assets (the bytes can differ by float rounding).
"""

import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEX_DIR = os.path.join(ROOT, "assets", "textures")
MODEL_DIR = os.path.join(ROOT, "assets", "models")
CHAR_DIR = os.path.join(ROOT, "assets", "characters")


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.bake.margin = 0
    return scene


# ---------------------------------------------------------------------------
# Node-graph DSL. Every helper returns an output socket so procedural
# materials read like expressions: nb.ramp(nb.noise(uv, 8), [...]).
# ---------------------------------------------------------------------------

class NodeBuilder:
    def __init__(self, tree):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links

    def _new(self, kind, **props):
        node = self.nodes.new(kind)
        for key, value in props.items():
            setattr(node, key, value)
        return node

    def _set(self, sock, value):
        if hasattr(value, "is_output") or isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, sock)
        elif value is not None:
            sock.default_value = value

    def uv(self):
        return self._new("ShaderNodeTexCoord").outputs["UV"]

    def value(self, v):
        n = self._new("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def vec(self, x, y=None, z=0.0):
        n = self._new("ShaderNodeCombineXYZ")
        self._set(n.inputs[0], x)
        self._set(n.inputs[1], y if y is not None else 0.0)
        self._set(n.inputs[2], z)
        return n.outputs[0]

    def xyz(self, v):
        n = self._new("ShaderNodeSeparateXYZ")
        self._set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vmath(self, op, a, b=None, scale=None):
        n = self._new("ShaderNodeVectorMath", operation=op)
        self._set(n.inputs[0], a)
        if b is not None:
            self._set(n.inputs[1], b)
        if scale is not None:
            self._set(n.inputs[3], scale)
        out = n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]
        return out

    def math(self, op, a, b=None, c=None, clamp=False):
        n = self._new("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._set(n.inputs[0], a)
        if b is not None:
            self._set(n.inputs[1], b)
        if c is not None:
            self._set(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def smooth(self, e0, e1, x):
        n = self._new("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self._set(n.inputs["Value"], x)
        self._set(n.inputs["From Min"], e0)
        self._set(n.inputs["From Max"], e1)
        return n.outputs["Result"]

    def maprange(self, x, a0, a1, b0=0.0, b1=1.0):
        n = self._new("ShaderNodeMapRange")
        self._set(n.inputs["Value"], x)
        self._set(n.inputs["From Min"], a0)
        self._set(n.inputs["From Max"], a1)
        self._set(n.inputs["To Min"], b0)
        self._set(n.inputs["To Max"], b1)
        return n.outputs["Result"]

    def noise(self, vec, scale=5.0, detail=4.0, rough=0.5, distortion=0.0, w=None, lac=2.0, ftype="FBM", color=False):
        n = self._new("ShaderNodeTexNoise", noise_dimensions="4D" if w is not None else "3D")
        n.noise_type = ftype
        self._set(n.inputs["Vector"], vec)
        if w is not None:
            self._set(n.inputs["W"], w)
        self._set(n.inputs["Scale"], scale)
        self._set(n.inputs["Detail"], detail)
        self._set(n.inputs["Roughness"], rough)
        self._set(n.inputs["Lacunarity"], lac)
        self._set(n.inputs["Distortion"], distortion)
        return n.outputs["Color" if color else "Fac"]

    def voronoi(self, vec, scale=5.0, feature="F1", metric="EUCLIDEAN", rand=1.0, out="Distance", detail=0.0):
        n = self._new("ShaderNodeTexVoronoi", feature=feature, distance=metric)
        self._set(n.inputs["Vector"], vec)
        self._set(n.inputs["Scale"], scale)
        self._set(n.inputs["Randomness"], rand)
        if "Detail" in n.inputs:
            self._set(n.inputs["Detail"], detail)
        return n.outputs[out]

    def wave(self, vec, scale=5.0, distortion=0.0, detail=2.0, kind="BANDS", profile="SIN", direction="X"):
        n = self._new("ShaderNodeTexWave", wave_type=kind, wave_profile=profile)
        if kind == "BANDS":
            n.bands_direction = direction
        else:
            n.rings_direction = "SPHERICAL"
        self._set(n.inputs["Vector"], vec)
        self._set(n.inputs["Scale"], scale)
        self._set(n.inputs["Distortion"], distortion)
        self._set(n.inputs["Detail"], detail)
        return n.outputs["Fac"]

    def ramp(self, fac, stops, interp="LINEAR"):
        """stops: [(pos, (r,g,b[,a])), ...] colors given in display (sRGB) space."""
        n = self._new("ShaderNodeValToRGB")
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        for i, (pos, col) in enumerate(stops):
            el = cr.elements[0] if i == 0 else cr.elements.new(pos)
            el.position = pos
            el.color = tuple(col) + ((1.0,) if len(col) == 3 else ())
        self._set(n.inputs[0], fac)
        return n.outputs["Color"]

    def mix(self, a, b, fac, blend="MIX"):
        n = self._new("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        self._set(n.inputs["Factor"], fac)
        self._set(n.inputs[6], a)
        self._set(n.inputs[7], b)
        return n.outputs[2]

    def rgb(self, r, g, b):
        n = self._new("ShaderNodeRGB")
        n.outputs[0].default_value = (r, g, b, 1.0)
        return n.outputs[0]

    def brick(self, vec, scale, mortar=0.02, width=0.5, height=0.25, offset=0.5, smooth=0.1, c1=(1, 1, 1), c2=(0.5, 0.5, 0.5), bias=0.0):
        n = self._new("ShaderNodeTexBrick", offset=offset, offset_frequency=2, squash=1.0, squash_frequency=2)
        self._set(n.inputs["Vector"], vec)
        self._set(n.inputs["Scale"], scale)
        self._set(n.inputs["Mortar Size"], mortar)
        self._set(n.inputs["Mortar Smooth"], smooth)
        self._set(n.inputs["Brick Width"], width)
        self._set(n.inputs["Row Height"], height)
        self._set(n.inputs["Bias"], bias)
        self._set(n.inputs["Color1"], tuple(c1) + (1.0,))
        self._set(n.inputs["Color2"], tuple(c2) + (1.0,))
        self._set(n.inputs["Mortar"], (0, 0, 0, 1))
        return n.outputs["Color"], n.outputs["Fac"]

    def gray(self, color):
        n = self._new("ShaderNodeRGBToBW")
        self._set(n.inputs[0], color)
        return n.outputs[0]

    def emit_out(self, sock):
        em = self._new("ShaderNodeEmission")
        self._set(em.inputs["Color"], sock)
        out = self._new("ShaderNodeOutputMaterial")
        self.links.new(em.outputs[0], out.inputs["Surface"])
        return out


# ---------------------------------------------------------------------------
# Baking
# ---------------------------------------------------------------------------

_bake_plane = None


def _plane():
    global _bake_plane
    if _bake_plane is None or _bake_plane.name not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=2.0)
        _bake_plane = bpy.context.active_object
        _bake_plane.name = "BakePlane"
    return _bake_plane


def bake_graph(build, size, name="bake"):
    """Bakes the socket returned by build(nb) to a float RGBA numpy array
    (h, w, 4), bottom row first (Blender's pixel order)."""
    plane = _plane()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    nb = NodeBuilder(tree)
    sock = build(nb)
    nb.emit_out(sock)
    img = bpy.data.images.new(name, size[0], size[1], alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    tnode = tree.nodes.new("ShaderNodeTexImage")
    tnode.image = img
    tree.nodes.active = tnode
    plane.data.materials.clear()
    plane.data.materials.append(mat)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    plane.select_set(True)
    bpy.context.view_layer.objects.active = plane
    bpy.ops.object.bake(type="EMIT", margin=0)
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(size[1], size[0], 4)
    bpy.data.images.remove(img)
    bpy.data.materials.remove(mat)
    return arr


def make_seamless(arr, band=0.6):
    """Offset-and-crossfade so the texture tiles. A pattern whose period
    divides half the image size survives untouched; noise is blended."""
    # One separable pass per axis: the rolled copy's own seam lands on the
    # centre line where the original has full weight, so it never shows.
    for axis in (1, 0):
        n = arr.shape[axis]
        t = np.abs(np.linspace(-1.0, 1.0, n))
        wgt = np.clip((1.0 - t) / band, 0.0, 1.0)
        wgt = wgt * wgt * (3 - 2 * wgt)
        shape = [1] * arr.ndim
        shape[axis] = n
        wgt = wgt.reshape(shape)
        rolled = np.roll(arr, n // 2, axis=axis)
        arr = arr * wgt + rolled * (1.0 - wgt)
    return arr


def normal_from_height(height, strength=4.0):
    """Tangent-space normal map (OpenGL / Godot convention: +Y green up)."""
    h = height.astype(np.float32)
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    n = np.stack([-dx * strength * h.shape[1] / 256.0, -dy * strength * h.shape[0] / 256.0, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save_png(arr, path, alpha=False, compression=15):
    """arr: (h, w, 3|4) floats 0..1, bottom row first."""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., : arr.shape[2]] = arr[..., :4]
    if not alpha:
        rgba[..., 3] = 1.0
    rgba = np.clip(rgba, 0.0, 1.0)
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=alpha)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    scene = bpy.context.scene
    scene.render.image_settings.color_mode = "RGBA" if alpha else "RGB"
    scene.render.image_settings.compression = compression
    img.save_render(path, scene=scene)
    bpy.data.images.remove(img)


def log(*args):
    print("[xg]", *args, flush=True)
    sys.stdout.flush()


def seeded(seed):
    return np.random.default_rng(seed)


TAU = math.tau
