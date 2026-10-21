#!/usr/bin/env python3
"""Build the reaper scythe from spec.json with Blender-as-a-module, and export it.

  python3.11 art/scythe/build_scythe.py

Writes art/scythe/scythe.glb, scythe.fbx and scythe.blend next to this script. Every outline below
is a point list measured in pixels off concept.jpg (374x534) and converted by to_metres(), so a fix
to the shape is a fix to those numbers, never a hand edit of the output.
"""
import json, math, os, sys

try:
    import bpy, bmesh
    from mathutils import Vector, Matrix
except ImportError:
    sys.exit("build_scythe.py: cannot import bpy; run it with the interpreter from setup_bpy.sh")

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "spec.json")))
METRES_PER_PX = 0.0035
SHAFT_X_PX, BUTT_Y_PX = 232, 530

# concept centreline of the shaft, top to butt (px)
SHAFT_PATH_PX = [(232, 58), (226, 100), (219, 150), (228, 190), (250, 222), (267, 255), (270, 290),
                 (263, 340), (253, 400), (250, 450), (258, 490), (252, 530)]
SHAFT_RADIUS = 0.030
SHAFT_TWISTS_PER_METRE = 4.0

# block, then a narrow spike out to +X that flares at its end
HEAD_OUTLINE_PX = [(203, 22), (250, 22), (250, 32), (266, 34), (271, 31), (273, 37), (271, 43), (266, 40),
                   (250, 42), (250, 60), (203, 60)]
HEAD_DEPTH = 0.065

# blade: back (convex) edge from the head out to the tip, then the cutting (concave) edge back
BLADE_OUTLINE_PX = [(225, 24), (200, 22), (175, 24), (150, 29), (130, 37), (115, 50), (105, 65), (99, 82),
                    (96, 99), (100, 95), (110, 75), (122, 62), (140, 54), (162, 50), (185, 49), (210, 50),
                    (225, 51)]
BLADE_SPINE_POINTS = 8  # the first 8 points are the back edge; the rest are the cutting edge
BLADE_SPINE_THICKNESS, BLADE_EDGE_THICKNESS = 0.014, 0.002


def to_metres(x_px, y_px):
    return ((x_px - SHAFT_X_PX) * METRES_PER_PX, (BUTT_Y_PX - y_px) * METRES_PER_PX)


def make_materials():
    mats = {}
    for m in SPEC["materials"]:
        h = m["hex"].lstrip("#")
        srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
        mat = bpy.data.materials.new(m["name"])
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (*linear, 1)
        bsdf.inputs["Metallic"].default_value = m["metallic"]
        bsdf.inputs["Roughness"].default_value = m["roughness"]
        mats[m["name"]] = mat
    return mats


def object_from_bmesh(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)  # slot before any face index is relied on
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def prism(name, outline_px, depth, material, y_centre=0.0):
    """Extrude an XZ outline (concept pixels) along Y. depth is one number, or one per outline point (a wedge)."""
    bm = bmesh.new()
    pts = [to_metres(x, y) for x, y in outline_px]
    depths = depth if isinstance(depth, list) else [depth] * len(pts)
    front = [bm.verts.new((x, y_centre - d / 2, z)) for (x, z), d in zip(pts, depths)]
    back = [bm.verts.new((x, y_centre + d / 2, z)) for (x, z), d in zip(pts, depths)]
    n = len(pts)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return object_from_bmesh(name, bm, material)


def catmull_rom(points, samples_per_span):
    pts = [points[0]] + points + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (Vector(p) for p in pts[i - 1:i + 3])
        for s in range(samples_per_span):
            t = s / samples_per_span
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(Vector(points[-1]))
    return out


def twisted_shaft(material):
    """Three-lobed section swept down the centreline and turned as it goes, so it reads as rope."""
    path = catmull_rom([(x, 0.0, z) for x, z in (to_metres(*p) for p in SHAFT_PATH_PX)], 12)
    segments, lobes, lobe_depth = 18, 3, 0.22
    bm = bmesh.new()
    rings, travelled = [], 0.0
    normal = Vector((0, 1, 0))
    for i, p in enumerate(path):
        if i:
            travelled += (p - path[i - 1]).length
        tangent = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        normal = (normal - tangent * normal.dot(tangent)).normalized()  # parallel transport
        binormal = tangent.cross(normal)
        twist = travelled * SHAFT_TWISTS_PER_METRE * 2 * math.pi
        ring = []
        for k in range(segments):
            a = 2 * math.pi * k / segments
            r = SHAFT_RADIUS * (1 - lobe_depth * 0.5 + lobe_depth * 0.5 * math.cos(lobes * (a + twist)))
            ring.append(bm.verts.new(p + (normal * math.cos(a) + binormal * math.sin(a)) * r))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            bm.faces.new((a[k], a[j], b[j], b[k]))
    for ring in (rings[0], rings[-1]):
        cap = bm.faces.new(ring)
        bmesh.ops.triangulate(bm, faces=[cap])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return object_from_bmesh("Shaft", bm, material)


def ellipsoid(name, centre, radii, material, segments=14, rings=8):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=1.0,
                              matrix=Matrix.LocRotScale(centre, None, radii))
    return object_from_bmesh(name, bm, material)


def box(name, centre, size, material):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale(centre, None, size))
    return object_from_bmesh(name, bm, material)


def skull(mats):
    """Skull boss on the front (-Y) face of the head, centred at concept (232, 38)."""
    x, z = to_metres(235, 40)
    face_y = -HEAD_DEPTH / 2
    parts = [
        ellipsoid("Cranium", (x, face_y, z + 0.006), (0.021, 0.012, 0.022), mats["SkullBone"]),
        box("Jaw", (x, face_y - 0.002, z - 0.018), (0.024, 0.016, 0.014), mats["SkullBone"]),
    ]
    for dx in (-0.008, 0.008):
        parts.append(ellipsoid("Eye", (x + dx, face_y - 0.009, z + 0.002), (0.0055, 0.004, 0.006),
                               mats["SocketDark"], 10, 6))
    parts.append(ellipsoid("Nose", (x, face_y - 0.010, z - 0.008), (0.0028, 0.003, 0.004),
                           mats["SocketDark"], 8, 5))
    return parts


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = make_materials()
    knob_x, knob_z = to_metres(218, 20)
    parts = [
        twisted_shaft(mats["RopeWood"]),
        prism("Head", HEAD_OUTLINE_PX, HEAD_DEPTH, mats["HeadIron"]),
        box("Knob", (knob_x, 0, knob_z), (0.05, 0.05, 0.03), mats["HeadIron"]),
        prism("Blade", BLADE_OUTLINE_PX, [BLADE_SPINE_THICKNESS] * BLADE_SPINE_POINTS
              + [BLADE_EDGE_THICKNESS] * (len(BLADE_OUTLINE_PX) - BLADE_SPINE_POINTS), mats["BladeSteel"]),
        *skull(mats),
    ]
    for o in bpy.context.scene.objects:
        o.select_set(o in parts)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    scythe = bpy.context.view_layer.objects.active
    scythe.name = scythe.data.name = SPEC["slug"]

    # ground it: the butt of the shaft sits on z = 0
    lowest = min((scythe.matrix_world @ v.co).z for v in scythe.data.vertices)
    for v in scythe.data.vertices:
        v.co.z -= lowest
    scythe.data.update()

    tris = sum(len(p.vertices) - 2 for p in scythe.data.polygons)
    height = max(v.co.z for v in scythe.data.vertices)
    if tris > SPEC["triangle_budget"]:
        sys.exit(f"build_scythe.py: {tris} tris is over the {SPEC['triangle_budget']} budget")
    if abs(height - SPEC["height_m"]) > 0.05:
        sys.exit(f"build_scythe.py: height {height:.3f} m is more than 5 cm off the spec's {SPEC['height_m']} m")

    out = lambda ext: os.path.join(HERE, "scythe" + ext)
    bpy.ops.export_scene.gltf(filepath=out(".glb"), export_format="GLB")
    bpy.ops.export_scene.fbx(filepath=out(".fbx"), axis_forward="-Z", axis_up="Y",
                             apply_scale_options="FBX_SCALE_UNITS")
    bpy.ops.wm.save_as_mainfile(filepath=out(".blend"), compress=True)
    print(f"build_scythe: {tris} tris, height {height:.3f} m -> scythe.glb .fbx .blend")


main()
