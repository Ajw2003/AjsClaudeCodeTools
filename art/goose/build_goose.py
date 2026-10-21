#!/usr/bin/env python3
"""Build the eldritch goose from spec.json with Blender-as-a-module, validate it, and export it.

  python3.11 art/goose/build_goose.py

  GOOSE_TEXTURE_PX=1024 python3.11 art/goose/build_goose.py   # quicker, lower-resolution bake

Writes art/goose/goose.glb, goose.fbx and goose.blend next to this script, and the baked textures to
art/goose/textures/. The shapes come from goose_design.py (pure Python, shared with the concept
sheet); this script turns them into one Blender mesh, checks it against the spec, has
goose_texture.py bake its surfaces into one texture set, and exports. A fix to the shape
is a fix to spec.json or goose_design.py, never a hand edit of the output.
"""
import os, sys

try:
    import bpy, bmesh
except ImportError:
    sys.exit("build_goose.py: cannot import bpy; run it with the interpreter from setup_bpy.sh")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import goose_design as g  # noqa: E402  (bpy must be imported first)
import goose_texture  # noqa: E402

HEIGHT_TOLERANCE_M = 0.15


def srgb_to_linear(hex_code):
    h = hex_code.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]


def make_materials(spec):
    mats = []
    for m in spec["materials"]:
        mat = bpy.data.materials.new(m["name"])
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        colour = (*srgb_to_linear(m["hex"]), 1)
        bsdf.inputs["Base Color"].default_value = colour
        bsdf.inputs["Metallic"].default_value = m["metallic"]
        bsdf.inputs["Roughness"].default_value = m["roughness"]
        if m.get("emission"):
            bsdf.inputs["Emission Color"].default_value = colour
            bsdf.inputs["Emission Strength"].default_value = m["emission"]
        mats.append(mat)
    return mats


def build_mesh(spec, parts_mesh, mats):
    verts, faces, face_mats = parts_mesh.verts, parts_mesh.faces, parts_mesh.materials
    index = {m.name: k for k, m in enumerate(mats)}
    unknown = sorted(set(face_mats) - set(index))
    if unknown:
        sys.exit(f"build_goose.py: parts use materials the spec does not list: {unknown}")
    mesh = bpy.data.meshes.new(spec["slug"])
    for m in mats:
        mesh.materials.append(m)  # slots first: indices written to a slotless mesh clamp to 0
    mesh.from_pydata(verts, [], faces)
    mesh.polygons.foreach_set("material_index", [index[n] for n in face_mats])
    mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
    for name, corners in (("Pattern", parts_mesh.pattern_uv), ("Shape", parts_mesh.shape_uv)):
        layer = mesh.uv_layers.new(name=name)
        layer.data.foreach_set("uv", [x for face in corners for uv in face for x in uv])  # loops follow face order
    mesh.attributes.new("pattern_kind", "FLOAT", "FACE").data.foreach_set("value", [float(k) for k in parts_mesh.patterns])
    mesh.update()

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # every part is its own closed shell
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(clean_customdata=False)

    obj = bpy.data.objects.new(spec["slug"], mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def validate(spec, obj, face_mats, mats):
    mesh = obj.data
    problems = []
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    if tris > spec["triangle_budget"]:
        problems.append(f"{tris} tris is over the {spec['triangle_budget']} budget")
    zs = [v.co.z for v in mesh.vertices]
    height = max(zs)
    if abs(height - spec["height_m"]) > HEIGHT_TOLERANCE_M:
        problems.append(f"height {height:.3f} m is more than {HEIGHT_TOLERANCE_M} m off the spec's {spec['height_m']} m")
    if min(zs) < -0.001:
        problems.append(f"lowest vertex {min(zs):.3f} m is below the ground")
    used = {mats[p.material_index].name for p in mesh.polygons}
    if used != set(face_mats):
        problems.append(f"material slots after build {sorted(used)} differ from the parts' {sorted(set(face_mats))}")
    bm = bmesh.new()
    bm.from_mesh(mesh)
    open_edges = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    if open_edges:
        problems.append(f"{open_edges} non-manifold edges: some part is not a closed shell")
    if problems:
        sys.exit("build_goose.py: validation failed:\n  " + "\n  ".join(problems))
    return tris, height


def main():
    spec = g.load_spec()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = g.build_parts(spec)
    parts_mesh = g.mesh_parts(parts)
    mats = make_materials(spec)
    obj = build_mesh(spec, parts_mesh, mats)
    tris, height = validate(spec, obj, parts_mesh.materials, mats)
    pixels = int(os.environ.get("GOOSE_TEXTURE_PX", spec["texture"]["pixels"]))
    textures = goose_texture.bake(obj, spec, os.path.join(HERE, "textures"), pixels)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    out = lambda ext: os.path.join(HERE, "goose" + ext)
    bpy.ops.export_scene.gltf(filepath=out(".glb"), export_format="GLB")
    bpy.ops.export_scene.fbx(filepath=out(".fbx"), axis_forward="-Z", axis_up="Y",
                             apply_scale_options="FBX_SCALE_UNITS", path_mode="RELATIVE")
    bpy.ops.wm.save_as_mainfile(filepath=out(".blend"), compress=True)
    xs = [v.co.x for v in obj.data.vertices]
    print(f"build_goose: {len(parts)} parts, {tris} tris, height {height:.3f} m, "
          f"span {max(xs) - min(xs):.2f} m, {len(mats)} materials baked to {pixels} px textures -> goose.glb .fbx .blend")


main()
