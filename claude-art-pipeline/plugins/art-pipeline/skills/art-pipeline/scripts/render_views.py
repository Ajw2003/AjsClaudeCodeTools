#!/usr/bin/env python3
"""Render review views of a model with Blender-as-a-module (bpy). Run with the BPY_PYTHON interpreter.

  render_views.py MODEL --out DIR [--samples 32] [--res 700] [--forward -Y] [--reference-height 1.8] [--no-reference]
                  [--background "#EDE6D6"]

MODEL: .fbx .glb .gltf .obj .blend. Writes DIR/{three_quarter,front,side,wireframe}.png and DIR/stats.json.
--forward is the world axis the model FACES after import into Blender (default -Y, which is where
glTF, and FBX exported from Blender for Unity, land). Cycles CPU only (EEVEE/Workbench need a GPU).
--background puts the renders on a flat colour (say, the concept sheet's paper) instead of the dark
studio: the model is lit exactly as before, rendered over a transparent film with the floor as a
shadow catcher, then composited onto the colour, so only the backdrop changes.
"""
import argparse, json, math, os, sys

try:
    import bpy
    from mathutils import Vector
except ImportError:
    sys.exit("render_views.py: cannot import bpy; run it with the interpreter from `sh setup_bpy.sh`")

AXES = {"+X": (1, 0), "-X": (-1, 0), "+Y": (0, 1), "-Y": (0, -1)}
VIEWS = [("three_quarter", -35.0, 16.0), ("front", 0.0, 0.0), ("side", 90.0, 0.0), ("wireframe", -35.0, 16.0)]


def fail(msg):
    sys.exit(f"render_views.py: {msg}")


def import_model(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".blend":
            bpy.ops.wm.open_mainfile(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        else:
            fail(f"unsupported format '{ext}' (want .fbx .glb .gltf .obj .blend)")
    except RuntimeError as e:
        fail(f"cannot read {path}: {e}")
    for o in [o for o in bpy.data.objects if o.type in ("CAMERA", "LIGHT")]:
        bpy.data.objects.remove(o)  # imported studio gear would pollute the lighting
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        fail(f"{path} has no mesh objects")
    return meshes


def world_points(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    pts, tris = [], 0
    for o in meshes:
        e = o.evaluated_get(dg)
        m = e.to_mesh()
        pts += [e.matrix_world @ v.co for v in m.vertices]
        tris += len(m.loop_triangles)
        e.to_mesh_clear()
    if not pts:
        fail("meshes have no vertices")
    return pts, tris


def bounds(pts):
    return (Vector(min(p[i] for p in pts) for i in range(3)), Vector(max(p[i] for p in pts) for i in range(3)))


def emission_mat(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    n.clear()
    em, clear, mix, out = (n.new(t) for t in ("ShaderNodeEmission", "ShaderNodeBsdfTransparent",
                                              "ShaderNodeMixShader", "ShaderNodeOutputMaterial"))
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    mix.inputs["Fac"].default_value = 0.4
    l.new(clear.outputs[0], mix.inputs[1]); l.new(em.outputs[0], mix.inputs[2]); l.new(mix.outputs[0], out.inputs[0])
    return m


def reference_figure(height, base_z, yaw0, centre_xy, lo_r, hi_r):
    """Faint grey box/capsule human beside the model (to the camera's right in the front view)."""
    import bmesh
    bm = bmesh.new()
    h = height
    def box(cx, cz, sx, sy, sz):
        bmesh.ops.create_cube(bm, size=1.0, matrix=__import__("mathutils").Matrix.LocRotScale(
            (cx, 0, cz), None, (sx, sy, sz)))
    def ball(cz, r):
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r,
                                  matrix=__import__("mathutils").Matrix.Translation((0, 0, cz)))
    box(-0.09 * h, 0.23 * h, 0.08 * h, 0.08 * h, 0.46 * h)   # legs
    box(0.09 * h, 0.23 * h, 0.08 * h, 0.08 * h, 0.46 * h)
    box(0, 0.62 * h, 0.30 * h, 0.15 * h, 0.32 * h)           # torso
    box(-0.20 * h, 0.60 * h, 0.07 * h, 0.08 * h, 0.34 * h)   # arms
    box(0.20 * h, 0.60 * h, 0.07 * h, 0.08 * h, 0.34 * h)
    ball(0.93 * h, 0.07 * h)                                 # head
    mesh = bpy.data.meshes.new("Ref"); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new("Ref", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler.z = yaw0
    mesh.materials.append(emission_mat("Ref", (0.55, 0.55, 0.55, 1), 0.5))
    obj.visible_shadow = False
    # place beside the model: along the camera-right axis, clear of the model's extent
    right = Vector((math.cos(yaw0), math.sin(yaw0), 0))
    off = hi_r + 0.12 * h + 0.3 * h
    obj.location = Vector((centre_xy[0], centre_xy[1], base_z)) + right * off
    bpy.context.view_layer.update()
    return obj


def onto_background(path, hex_colour):
    """Composite a transparent render onto a flat colour, in place."""
    try:
        from PIL import Image
    except ImportError:
        fail("--background needs Pillow in the bpy interpreter (setup_bpy.sh installs it)")
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        fail(f"--background wants a hex colour like #EDE6D6, got {hex_colour}")
    render = Image.open(path).convert("RGBA")
    flat = Image.new("RGBA", render.size, tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
    Image.alpha_composite(flat, render).convert("RGB").save(path)


def look_at(obj, direction):
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model"); ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=32); ap.add_argument("--res", type=int, default=700)
    ap.add_argument("--forward", default="-Y", choices=sorted(AXES) + ["+Z", "-Z"])
    ap.add_argument("--reference-height", type=float, default=1.8)
    ap.add_argument("--no-reference", action="store_true")
    ap.add_argument("--background", help="hex colour to composite the renders onto, e.g. #EDE6D6")
    a = ap.parse_args()
    if not os.path.isfile(a.model):
        fail(f"model not found: {a.model}")
    if a.forward in ("+Z", "-Z"):
        fail("--forward +Z/-Z is not a horizontal facing; give the post-import facing as +X -X +Y -Y")
    os.makedirs(a.out, exist_ok=True)

    meshes = import_model(os.path.abspath(a.model))
    pts, tris = world_points(meshes)
    lo, hi = bounds(pts)
    centre, size = (lo + hi) / 2, hi - lo
    if max(size) < 1e-6:
        fail("model is empty (zero-size bounds)")
    span = size.length
    fx, fy = AXES[a.forward]
    yaw0 = math.atan2(fx, -fy)  # camera azimuth 0 sits on the side the model faces

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True; sc.cycles.max_bounces = 3; sc.cycles.use_light_tree = False
    sc.render.resolution_x = sc.render.resolution_y = a.res
    sc.view_settings.view_transform = "AgX"
    sc.render.image_settings.file_format = "PNG"

    # dark warm backdrop (flat colour; lights do the shaping)
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.022, 0.015, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

    d = max(span, 0.25) * 2.2
    for name, pos, en, sz, col in (("Key", (0.75, -0.95, 0.85), 26, 0.6, (1.0, 0.86, 0.7)),
                                   ("Fill", (-1.1, -0.55, 0.25), 5, 1.0, (1.0, 0.78, 0.6)),
                                   ("Rim", (-0.3, 1.2, 1.0), 22, 0.6, (0.7, 0.76, 0.9))):
        ld = bpy.data.lights.new(name, "AREA"); ld.energy = en * d * d; ld.size = d * sz; ld.color = col
        lo_ = bpy.data.objects.new(name, ld)
        # rotate the rig so the key lights the model's front
        v = Vector(pos) * d
        v = Vector((v.x * math.cos(yaw0) - v.y * math.sin(yaw0), v.x * math.sin(yaw0) + v.y * math.cos(yaw0), v.z))
        lo_.location = centre + v
        look_at(lo_, centre - lo_.location)
        sc.collection.objects.link(lo_)

    gm = bpy.data.meshes.new("Ground"); g = max(span, 0.25) * 40
    gm.from_pydata([(-g, -g, lo.z), (g, -g, lo.z), (g, g, lo.z), (-g, g, lo.z)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("Ground", gm); sc.collection.objects.link(ground)
    if a.background:
        sc.render.film_transparent = True
        sc.render.image_settings.color_mode = "RGBA"
        ground.is_shadow_catcher = True
    gmat = bpy.data.materials.new("Ground"); gmat.use_nodes = True
    gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.045, 0.04, 1)
    gm.materials.append(gmat)

    right0 = Vector((math.cos(yaw0), math.sin(yaw0), 0))
    ref = None
    if not a.no_reference:
        hi_r = max((p - centre).dot(right0) for p in pts)
        ref = reference_figure(a.reference_height, lo.z, yaw0, (centre.x, centre.y), 0, hi_r)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.type = "ORTHO"
    cam.data.clip_start = 0.01; cam.data.clip_end = span * 40 + 50
    sc.collection.objects.link(cam); sc.camera = cam

    wire = bpy.data.materials.new("Wire"); wire.use_nodes = True
    n, l = wire.node_tree.nodes, wire.node_tree.links; n.clear()
    clay = n.new("ShaderNodeBsdfPrincipled"); clay.inputs["Base Color"].default_value = (0.1, 0.095, 0.085, 1)
    edge = n.new("ShaderNodeEmission"); edge.inputs["Color"].default_value = (0.86, 0.82, 0.73, 1)
    edge.inputs["Strength"].default_value = 1.4
    wf = n.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs["Size"].default_value = 0.8
    mix = n.new("ShaderNodeMixShader"); out = n.new("ShaderNodeOutputMaterial")
    l.new(wf.outputs[0], mix.inputs[0]); l.new(clay.outputs[0], mix.inputs[1])
    l.new(edge.outputs[0], mix.inputs[2]); l.new(mix.outputs[0], out.inputs[0])

    for name, az, el in VIEWS:
        yaw, pitch = yaw0 + math.radians(az), math.radians(el)
        toward = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
        fwd = -toward
        rgt = fwd.cross(Vector((0, 0, 1))).normalized(); up = rgt.cross(fwd).normalized()
        wf_view = name == "wireframe"
        ground.hide_render = wf_view
        if ref: ref.hide_render = wf_view or name != "front"
        corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        if ref and name == "front":
            rp = [ref.matrix_world @ Vector(c) for c in ref.bound_box]
            corners += rp
        us = [(c - centre).dot(rgt) for c in corners]; vs = [(c - centre).dot(up) for c in corners]
        target = centre + rgt * (max(us) + min(us)) / 2 + up * (max(vs) + min(vs)) / 2
        cam.data.ortho_scale = max(max(us) - min(us), max(vs) - min(vs)) * 1.14
        cam.location = target - fwd * (span * 4 + 1)
        look_at(cam, fwd)
        bpy.context.view_layer.material_override = wire if wf_view else None
        sc.cycles.samples = max(8, a.samples // 2) if wf_view else a.samples
        sc.render.filepath = os.path.join(a.out, name + ".png")
        bpy.ops.render.render(write_still=True)
        if not os.path.exists(sc.render.filepath):
            fail(f"render did not write {sc.render.filepath}")
        if a.background:
            onto_background(sc.render.filepath, a.background)

    arms = [o for o in sc.objects if o.type == "ARMATURE"]
    bones = [b.name for o in arms for b in o.data.bones]
    mats = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
    stats = {"model": os.path.basename(a.model), "triangles": tris,
             "bbox_m": [round(x, 3) for x in size], "height_m": round(size.z, 3),
             "mesh_count": len(meshes), "bones": {"count": len(bones), "names": bones}, "materials": mats,
             "forward": a.forward}
    with open(os.path.join(a.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(f"render_views: {tris} tris, bbox {stats['bbox_m']} m, {len(bones)} bones -> {a.out}")


main()
