"""Procedural surfaces for the goose, baked into one texture set (colour, normal, roughness).

Imported by build_goose.py after bpy. Every face carries a pattern_kind attribute (goose_design.PATTERNS)
and two UV maps written by the mesher: "Pattern" (metres around/across and along each part) and
"Shape" (0..1 along the part, and the fraction where dried blood starts, 9 for none). One shader per
material reads them, so a feather gets barbs and a shaft, a tube gets scalloped plumage, a branch gets
bark, and the breast brand is projected in from goose_design.decal_image. The shaders exist only to
be baked: the exported model has one material reading the three baked images through the "Bake" UV map.
"""
import math, os

import bpy
from PIL import Image

import goose_design as g


class Graph:
    """Small helpers for building a shader node tree; inputs can be sockets or plain numbers."""

    def __init__(self, material):
        material.use_nodes = True
        self.tree = material.node_tree
        self.nodes, self.links = self.tree.nodes, self.tree.links
        self.nodes.clear()

    def node(self, kind, **props):
        n = self.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def feed(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.links.new(value, socket)
        else:
            socket.default_value = value

    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        """c is the third input: COMPARE's epsilon, for one."""
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for socket, value in zip(n.inputs, (a, b, c)):
            self.feed(socket, value)
        return n.outputs[0]

    def smooth(self, lo, hi, x):
        """smoothstep from lo to hi."""
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self.feed(n.inputs["From Min"], lo)
        self.feed(n.inputs["From Max"], hi)
        self.feed(n.inputs["Value"], x)
        return n.outputs["Result"]

    def remap(self, x, lo, hi, out_lo, out_hi):
        n = self.node("ShaderNodeMapRange", clamp=True)
        for name, v in (("Value", x), ("From Min", lo), ("From Max", hi), ("To Min", out_lo), ("To Max", out_hi)):
            self.feed(n.inputs[name], v)
        return n.outputs["Result"]

    def lerp(self, a, b, t):
        return self.math("ADD", a, self.math("MULTIPLY", self.math("SUBTRACT", b, a), t))

    def vec(self, x, y, z=0.0):
        n = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.feed(n.inputs[i], v)
        return n.outputs[0]

    def split(self, vector):
        n = self.node("ShaderNodeSeparateXYZ")
        self.feed(n.inputs[0], vector)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs["Scale"], scale)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def vlerp(self, a, b, t):
        return self.vmath("ADD", a, self.vmath("SCALE", self.vmath("SUBTRACT", b, a), scale=t))

    def noise(self, vector, scale, detail=3.0, roughness=0.55, distortion=0.0):
        n = self.node("ShaderNodeTexNoise", noise_dimensions="3D")
        self.feed(n.inputs["Vector"], vector)
        for name, v in (("Scale", scale), ("Detail", detail), ("Roughness", roughness), ("Distortion", distortion)):
            self.feed(n.inputs[name], v)
        return n.outputs["Fac"]

    def wave(self, vector, scale, distortion, detail=2.0):
        n = self.node("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
        self.feed(n.inputs["Vector"], vector)
        for name, v in (("Scale", scale), ("Distortion", distortion), ("Detail", detail), ("Detail Scale", 1.5)):
            self.feed(n.inputs[name], v)
        return n.outputs["Fac"]

    def voronoi(self, vector, scale, feature="F1"):
        n = self.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature=feature)
        self.feed(n.inputs["Vector"], vector)
        self.feed(n.inputs["Scale"], scale)
        return n.outputs["Distance"]


def linear(hex_code):
    h = hex_code.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def surface_patterns(G, kind, u, v):
    """(tone, height) for every pattern kind; tone multiplies the material colour, height drives the bump."""
    au = G.math("ABSOLUTE", u)
    out = {}

    # plumage: overlapping feather scallops with fine barb streaks running down each one
    scallop = G.voronoi(G.vec(G.math("MULTIPLY", u, 6.0), G.math("MULTIPLY", v, 9.0)), 1.0)
    streak = G.wave(G.vec(u, G.math("MULTIPLY", v, 0.15)), 60.0, 6.0)
    tone = G.math("MULTIPLY", G.remap(scallop, 0.15, 0.65, 0.62, 1.05), G.remap(streak, 0.0, 1.0, 0.78, 1.08))
    out["plumage"] = (tone, G.math("ADD", G.math("MULTIPLY", streak, 0.4), scallop))

    # vane: a pale shaft down the middle, diagonal barbs, ragged splits where the barbs have parted
    shaft = G.math("SUBTRACT", 1.0, G.smooth(0.003, 0.011, au))
    barbs = G.wave(G.vec(G.math("ADD", au, G.math("MULTIPLY", v, 0.55)), 0.0), 220.0, 2.0)
    split = G.smooth(0.58, 0.66, G.noise(G.vec(G.math("MULTIPLY", au, 8.0), G.math("MULTIPLY", v, 3.0)), 1.0))
    tone = G.math("MULTIPLY", G.remap(barbs, 0.0, 1.0, 0.62, 1.0), G.remap(split, 0.0, 1.0, 1.0, 0.45))
    tone = G.lerp(tone, 1.45, shaft)
    out["vane"] = (tone, G.math("ADD", G.math("MULTIPLY", barbs, 0.6), G.math("SUBTRACT", shaft, split)))

    # bark: long ridges down the branch, split by cracks
    ridges = G.wave(G.vec(u, G.math("MULTIPLY", v, 0.12)), 25.0, 8.0, 4.0)
    crack = G.math("SUBTRACT", 1.0, G.smooth(0.0, 0.06, G.voronoi(G.vec(G.math("MULTIPLY", u, 6.0),
                                                                   G.math("MULTIPLY", v, 2.0)), 1.0, "DISTANCE_TO_EDGE")))
    tone = G.math("MULTIPLY", G.remap(ridges, 0.0, 1.0, 0.55, 1.1), G.remap(crack, 0.0, 1.0, 1.0, 0.3))
    out["bark"] = (tone, G.math("SUBTRACT", ridges, crack))

    # bone: grime in the pores and hairline cracks
    pores = G.noise(G.vec(u, v), 8.0, 6.0)
    hairline = G.math("SUBTRACT", 1.0, G.smooth(0.0, 0.03, G.voronoi(G.vec(u, v), 12.0, "DISTANCE_TO_EDGE")))
    tone = G.math("MULTIPLY", G.remap(pores, 0.3, 0.7, 0.6, 1.08), G.remap(hairline, 0.0, 1.0, 1.0, 0.45))
    out["bone"] = (tone, G.math("SUBTRACT", pores, hairline))

    # wet: mouths and eyes, a little mottling only
    mottle = G.noise(G.vec(u, v), 14.0)
    out["wet"] = (G.remap(mottle, 0.3, 0.7, 0.75, 1.1), G.math("MULTIPLY", mottle, 0.3))

    # skin: the scutes and pebbling of a goose's legs and feet
    scute = G.voronoi(G.vec(u, v), 40.0)
    out["skin"] = (G.remap(scute, 0.1, 0.6, 0.7, 1.1), scute)

    # hide: the heads' wrinkled, leathery skin, deep creases running across, veins and pocks
    creases = G.wave(G.vec(G.math("MULTIPLY", v, 1.0), G.math("MULTIPLY", u, 0.2)), 70.0, 9.0, 4.0)
    veins = G.math("SUBTRACT", 1.0, G.smooth(0.0, 0.035, G.voronoi(G.vec(u, v), 18.0, "DISTANCE_TO_EDGE")))
    pocks = G.smooth(0.62, 0.7, G.noise(G.vec(u, v), 45.0, 2.0))
    tone = G.math("MULTIPLY", G.remap(creases, 0.0, 1.0, 0.55, 1.15), G.remap(veins, 0.0, 1.0, 1.0, 0.6))
    tone = G.math("MULTIPLY", tone, G.remap(pocks, 0.0, 1.0, 1.0, 0.5))
    out["hide"] = (tone, G.math("SUBTRACT", G.math("SUBTRACT", creases, veins), pocks))

    tone_sum, height_sum = 0.0, 0.0
    for index, name in enumerate(g.PATTERNS):
        weight = G.math("COMPARE", kind, float(index), 0.1)
        tone_sum = G.math("ADD", tone_sum, G.math("MULTIPLY", out[name][0], weight))
        height_sum = G.math("ADD", height_sum, G.math("MULTIPLY", out[name][1], weight))
    return tone_sum, height_sum


def build_shader(material, colour_hex, roughness, decal, decal_images, T, gain=1.0):
    """The baking shader for one material. T: the spec's "texture" block (blood and brand colours, strengths);
    gain: this material's albedo multiplier from T["albedo_gain"]."""
    G = Graph(material)
    pattern_uv = G.node("ShaderNodeUVMap", uv_map="Pattern").outputs[0]
    shape_uv = G.node("ShaderNodeUVMap", uv_map="Shape").outputs[0]
    kind = G.node("ShaderNodeAttribute", attribute_name="pattern_kind", attribute_type="GEOMETRY").outputs["Fac"]
    position = G.node("ShaderNodeTexCoord").outputs["Object"]
    u, v, _ = G.split(pattern_uv)
    along, soak, _ = G.split(shape_uv)

    tone, height = surface_patterns(G, kind, u, v)
    grime = G.remap(G.noise(position, 0.6, 4.0), 0.35, 0.65, T["grime_dark"], 1.05)
    colour = G.vmath("SCALE", linear(colour_hex), scale=G.math("MULTIPLY", G.math("MULTIPLY", tone, grime), gain))
    rough = roughness

    # mud climbing from the ground, patchy at its edge, and dark grit speckled over everything
    _, _, height_z = G.split(position)
    mud = G.math("SUBTRACT", 1.0, G.smooth(T["mud_low"], T["mud_high"],
                                         G.math("ADD", height_z, G.math("MULTIPLY", G.noise(position, 3.0), 0.5))))
    colour = G.vlerp(colour, G.vmath("SCALE", linear(T["mud_hex"]), scale=G.remap(G.noise(position, 25.0), 0.3, 0.7, 0.6, 1.2)),
                     G.math("MULTIPLY", mud, 0.85))
    rough = G.lerp(rough, 0.95, mud)
    grit = G.smooth(0.66, 0.72, G.noise(position, 160.0, 1.0))
    colour = G.vmath("SCALE", colour, scale=G.remap(grit, 0.0, 1.0, 1.0, 0.35))

    # dried blood soaking up each feather from the tip, with a ragged front
    drips = G.noise(G.vec(G.math("MULTIPLY", u, 9.0), G.math("MULTIPLY", v, 0.6)), 1.0, 3.0)  # stretched along the part
    front = G.math("ADD", along, G.math("MULTIPLY", G.math("SUBTRACT", drips, 0.5), T["blood_drip_reach"]))
    soaked = G.smooth(G.math("SUBTRACT", soak, 0.05), G.math("ADD", soak, 0.05), front)
    blood = G.vmath("SCALE", linear(T["blood_hex"]), scale=G.remap(G.noise(position, 14.0), 0.3, 0.7, 0.6, 1.25))
    colour = G.vlerp(colour, blood, soaked)
    rough = G.lerp(rough, T["blood_roughness"], soaked)

    # the breast brand, projected along the breast normal from the decal frame
    offset = G.vmath("SUBTRACT", position, decal["centre"])
    extent = 2 * g.DECAL_HALF_EXTENT * decal["size"]
    image_x = G.math("ADD", G.math("DIVIDE", G.vmath("DOT_PRODUCT", offset, decal["side"]), extent), 0.5)
    image_y = G.math("ADD", G.math("DIVIDE", G.vmath("DOT_PRODUCT", offset, decal["up"]), extent), 0.5)
    depth = G.math("ABSOLUTE", G.vmath("DOT_PRODUCT", offset, decal["normal"]))
    on_breast = G.math("MULTIPLY", G.math("SUBTRACT", 1.0, G.smooth(decal["depth"] * 0.7, decal["depth"], depth)),
                       G.math("COMPARE", kind, float(g.PATTERNS.index("plumage")), 0.1))
    samples = []
    for image in decal_images:
        tex = G.node("ShaderNodeTexImage", image=image, extension="CLIP", interpolation="Linear")
        G.feed(tex.inputs["Vector"], G.vec(image_x, image_y))
        samples.append(G.math("MULTIPLY", tex.outputs["Color"], on_breast))
    interior, rim = samples
    char = G.vmath("SCALE", linear(T["brand_char_hex"]), scale=G.remap(G.noise(position, 20.0), 0.3, 0.7, 0.6, 1.3))
    colour = G.vlerp(colour, char, interior)
    colour = G.vlerp(colour, linear(T["brand_rim_hex"]), rim)
    rough = G.lerp(rough, T["brand_roughness"], interior)
    height = G.math("ADD", height, G.math("SUBTRACT", G.math("MULTIPLY", rim, 1.2), G.math("MULTIPLY", interior, 0.5)))

    bump = G.node("ShaderNodeBump")
    G.feed(bump.inputs["Strength"], T["bump_strength"])
    G.feed(bump.inputs["Distance"], 0.01)
    G.feed(bump.inputs["Height"], height)
    bsdf = G.node("ShaderNodeBsdfPrincipled")
    G.feed(bsdf.inputs["Base Color"], colour)
    G.feed(bsdf.inputs["Roughness"], rough)
    G.feed(bsdf.inputs["Metallic"], 0.0)
    G.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    out = G.node("ShaderNodeOutputMaterial")
    G.links.new(bsdf.outputs[0], out.inputs["Surface"])


def decal_to_images(decal, pixels=1024):
    """The brand's interior and rim masks as Blender images (packed, so the .blend carries them)."""
    images = []
    for name, mask in zip(("brand_interior", "brand_rim"), g.decal_image(pixels)):
        img = bpy.data.images.new(name, pixels, pixels, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        flipped = mask.transpose(Image.FLIP_TOP_BOTTOM).convert("RGBA")  # Blender images start at the bottom row
        img.pixels.foreach_set([c / 255 for c in flipped.tobytes()])
        img.pack()
        images.append(img)
    return images


def darken_by_occlusion(colour, occlusion, strength):
    """Fold baked ambient occlusion into the colour, so every crevice, socket and fold is dark grime."""
    import numpy as np
    count = colour.size[0] * colour.size[1] * 4
    c = np.empty(count, dtype=np.float32)
    o = np.empty(count, dtype=np.float32)
    colour.pixels.foreach_get(c)
    occlusion.pixels.foreach_get(o)
    c, o = c.reshape(-1, 4), o.reshape(-1, 4)
    c[:, :3] *= (1 - strength + strength * o[:, :1])
    colour.pixels.foreach_set(c.ravel())
    colour.update()


def bake(obj, spec, out_dir, pixels):
    """Shade every material procedurally, smart-UV the mesh into "Bake", bake colour, normal and roughness,
    then swap the materials for one that reads the baked images. Returns the image file paths."""
    T = spec["texture"]
    decal = next(p for p in g.build_parts(spec) if p["kind"] == "decal")
    decal_images = decal_to_images(decal)
    by_name = {m["name"]: m for m in spec["materials"]}
    for material in obj.data.materials:
        m = by_name[material.name]
        gain = T["albedo_gain"].get(material.name, 1.0)
        build_shader(material, m["hex"], m["roughness"], decal, decal_images, T, gain)

    mesh = obj.data
    bake_uv = mesh.uv_layers.new(name="Bake")
    mesh.uv_layers.active = bake_uv
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = T["bake_samples"]
    sc.render.bake.margin = 6
    targets = {}
    for pass_name, colour_space in (("basecolor", "sRGB"), ("normal", "Non-Color"), ("roughness", "Non-Color"),
                                    ("occlusion", "Non-Color")):
        img = bpy.data.images.new(f"goose_{pass_name}", pixels, pixels, alpha=False)
        img.colorspace_settings.name = colour_space
        targets[pass_name] = img
    holders = []
    for material in mesh.materials:
        holder = material.node_tree.nodes.new("ShaderNodeTexImage")
        material.node_tree.nodes.active = holder
        holders.append(holder)
    for pass_name, kwargs in (("basecolor", {"type": "DIFFUSE", "pass_filter": {"COLOR"}}),
                              ("normal", {"type": "NORMAL", "normal_space": "TANGENT"}),
                              ("roughness", {"type": "ROUGHNESS"}),
                              ("occlusion", {"type": "AO"})):
        sc.cycles.samples = T["ao_samples"] if pass_name == "occlusion" else T["bake_samples"]
        for holder in holders:
            holder.image = targets[pass_name]
        bpy.ops.object.bake(use_clear=True, **kwargs)
    darken_by_occlusion(targets["basecolor"], targets.pop("occlusion"), T["occlusion_strength"])

    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for pass_name, img in targets.items():
        path = os.path.join(out_dir, f"goose_{pass_name}.jpg")
        img.filepath_raw = path
        img.file_format = "JPEG"
        img.save()
        if not os.path.isfile(path):
            raise RuntimeError(f"goose_texture: baking wrote no {path}")
        paths[pass_name] = path

    shipped = bpy.data.materials.new("goose")
    G = Graph(shipped)
    uv = G.node("ShaderNodeUVMap", uv_map="Bake").outputs[0]
    bsdf = G.node("ShaderNodeBsdfPrincipled")
    reads = {}
    for pass_name, img in targets.items():
        tex = G.node("ShaderNodeTexImage", image=img)
        G.links.new(uv, tex.inputs["Vector"])
        reads[pass_name] = tex.outputs["Color"]
    G.links.new(reads["basecolor"], bsdf.inputs["Base Color"])
    G.links.new(G.split(reads["roughness"])[0], bsdf.inputs["Roughness"])
    normal_map = G.node("ShaderNodeNormalMap", uv_map="Bake")
    G.links.new(reads["normal"], normal_map.inputs["Color"])
    G.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    G.feed(bsdf.inputs["Metallic"], 0.0)
    out = G.node("ShaderNodeOutputMaterial")
    G.links.new(bsdf.outputs[0], out.inputs["Surface"])

    mesh.materials.clear()
    mesh.materials.append(shipped)
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    for name in ("Pattern", "Shape"):
        mesh.uv_layers.remove(mesh.uv_layers[name])
    mesh.attributes.remove(mesh.attributes["pattern_kind"])
    mesh.update()
    return paths
