"""Geometry kit: part kinds, assembly into one bmesh, palette UVs, authoring helpers.

A model is a flat list of `Part` records. Each becomes one closed, manifold island
(never welded to its neighbours) in a single joined mesh; the joined mesh has ONE
material whose texture is a palette (see materials.py), so a face's family is stored
as its UV: every loop of a face sits on the centre of that family's palette cell.

Kinds (all sizes in metres; `size` is the FULL extent, so a unit box is 1 m):
  box, cyl (taper = top radius / bottom radius), cone, sphere   unit primitives
  lathe  extras["profile"] = [(r, z), ...] bottom to top; r == 0 end = pole, r > 0 end = flat cap
  prism  extras["outline"] = [(x, y), ...] extruded along Z, depth = size[2] (unit prism spans z -0.5..0.5)
  tube   extras["path"] = [(x, y, z), ...], extras["section"] = (rn, rb), optional "up", "closed"
  loft   extras["rings"] = [[(x, y, z), ...], ...] same point count per ring (1 point = pole at either end)
  sweep  extras["path"], extras["sections"] = [(rn, rb), ...] one per path point, optional
         "up", "power" (2 ellipse, 4 rounded box), "offsets"; (0, 0) at an end = pointed tip

Per-part options: mirror (second copy across the YZ plane; ".L" bone becomes ".R"),
smooth (shade every edge smooth), paint (list of {"mat", "min", "max"} boxes in LOCAL
coordinates; faces whose centroid falls inside are restamped with that family, so trim
stays on the same shell), and the rig rules rigid / prop / bones / skirt (see rig.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import bpy  # noqa: F401  (importing bpy is what makes bmesh importable)
import bmesh
from mathutils import Euler, Matrix, Vector
from mathutils.geometry import tessellate_polygon

SMOOTH_ANGLE = math.radians(35.0)   # edges sharper than this stay hard
MIRROR = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))


@dataclass
class Part:
    kind: str
    loc: tuple = (0.0, 0.0, 0.0)
    size: tuple = (1.0, 1.0, 1.0)
    mat: str = ""
    bone: str = "Root"
    rot: tuple = (0.0, 0.0, 0.0)      # XYZ euler degrees
    mirror: bool = False
    segments: int = 12
    rings: int = 8                    # sphere only
    taper: float = 1.0                # cyl only
    smooth: bool = False
    rigid: bool = False               # every vertex bound 1.0 to `bone`
    prop: bool = False                # rigid, and left out of the height check
    bones: list | None = None         # the only bones this part may be weighted to
    skirt: dict | None = None         # see rig._skirt_weights
    paint: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------
# New primitives. Each returns (verts, faces) created in `bm`, in local metres.
# --------------------------------------------------------------------------------

def _faces_volume(faces) -> float:
    total = 0.0
    for face in faces:
        verts = face.verts
        origin = verts[0].co
        for i in range(1, len(verts) - 1):
            total += origin.cross(verts[i].co).dot(verts[i + 1].co)
    return total / 6.0


def _orient_outward(bm, faces: list) -> None:
    """Flip a freshly built closed island if it came out inside-out."""
    if _faces_volume(faces) < 0.0:
        bmesh.ops.reverse_faces(bm, faces=faces)


def _lathe(bm, part: Part):
    profile = [(float(r), float(z)) for r, z in part.extras["profile"]]
    if len(profile) < 2:
        raise ValueError("lathe profile needs at least two points")
    segments = max(3, part.segments)
    eps = 1e-6
    for i, (r, _z) in enumerate(profile):
        if r < -eps:
            raise ValueError(f"lathe profile point {i} has negative radius {r}")
        if r <= eps and 0 < i < len(profile) - 1:
            raise ValueError(f"lathe profile point {i} has zero radius mid-profile; "
                             "only the first and last points may be poles")

    rows = []
    verts = []
    for r, z in profile:
        if r <= eps:
            pole = bm.verts.new((0.0, 0.0, z))
            rows.append([pole])
            verts.append(pole)
        else:
            row = []
            for j in range(segments):
                theta = 2.0 * math.pi * j / segments
                row.append(bm.verts.new((math.cos(theta) * r, math.sin(theta) * r, z)))
            rows.append(row)
            verts.extend(row)

    faces = []
    for a, b in zip(rows, rows[1:]):
        for j in range(segments):
            k = (j + 1) % segments
            if len(a) == 1 and len(b) == 1:
                raise ValueError("lathe profile has two consecutive poles")
            if len(a) == 1:
                quad = (a[0], b[k], b[j])
            elif len(b) == 1:
                quad = (a[j], a[k], b[0])
            else:
                quad = (a[j], a[k], b[k], b[j])
            faces.append(bm.faces.new(quad))
    if len(rows[0]) > 1:
        faces.append(bm.faces.new(list(reversed(rows[0]))))
    if len(rows[-1]) > 1:
        faces.append(bm.faces.new(rows[-1]))

    _orient_outward(bm, faces)
    return verts, faces


def _signed_area(points) -> float:
    return 0.5 * sum(points[i][0] * points[(i + 1) % len(points)][1]
                     - points[(i + 1) % len(points)][0] * points[i][1]
                     for i in range(len(points)))


def _prism(bm, part: Part):
    outline = [(float(x), float(y)) for x, y in part.extras["outline"]]
    if len(outline) >= 2 and outline[0] == outline[-1]:
        outline = outline[:-1]
    if len(outline) < 3:
        raise ValueError("prism outline needs at least three points")
    if abs(_signed_area(outline)) < 1e-10:
        raise ValueError("prism outline has zero area")
    if _signed_area(outline) < 0.0:
        outline.reverse()   # counter-clockwise from +Z

    n = len(outline)
    bottom = [bm.verts.new((x, y, -0.5)) for x, y in outline]
    top = [bm.verts.new((x, y, 0.5)) for x, y in outline]

    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bottom[i], bottom[j], top[j], top[i])))

    # Polygon fill copes with concave outlines; a fan or a single n-gon would not
    # triangulate the same way in every importer.
    triangles = tessellate_polygon([[Vector((x, y, 0.0)) for x, y in outline]])
    for tri in triangles:
        a, b, c = tri
        pa, pb, pc = outline[a], outline[b], outline[c]
        ccw = ((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])) > 0.0
        if not ccw:
            b, c = c, b
        faces.append(bm.faces.new((top[a], top[b], top[c])))
        faces.append(bm.faces.new((bottom[a], bottom[c], bottom[b])))

    _orient_outward(bm, faces)
    return bottom + top, faces


def _tube(bm, part: Part):
    path = [Vector(p) for p in part.extras["path"]]
    closed = bool(part.extras.get("closed", False))
    if closed and (path[0] - path[-1]).length < 1e-9:
        path = path[:-1]
    if len(path) < 2:
        raise ValueError("tube path needs at least two points")
    rn, rb = part.extras.get("section", (0.01, 0.01))
    sides = max(3, part.segments)
    count = len(path)

    def tangent(i):
        if closed:
            t = path[(i + 1) % count] - path[(i - 1) % count]
        elif i == 0:
            t = path[1] - path[0]
        elif i == count - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        if t.length < 1e-9:
            raise ValueError(f"tube path doubles back on itself at point {i}")
        return t.normalized()

    t0 = tangent(0)
    hint = part.extras.get("up")
    if hint is None:
        axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
        hint = min(axes, key=lambda a: abs(a.dot(t0)))
    normal = Vector(hint) - Vector(hint).dot(t0) * t0
    if normal.length < 1e-6:
        raise ValueError("tube 'up' hint is parallel to the path")
    normal.normalize()

    rings = []
    verts = []
    for i in range(count):
        t = tangent(i)
        # Parallel transport: remove the tangential component, keep the twist minimal.
        normal = (normal - normal.dot(t) * t)
        if normal.length < 1e-6:
            raise ValueError(f"tube frame collapsed at point {i}")
        normal.normalize()
        binormal = t.cross(normal)
        # A mitred joint: widen the section where the path bends so the wall
        # keeps its thickness through the corner.
        scale, bend = 1.0, None
        if 0 < i < count - 1 or closed:
            prev = (path[i] - path[(i - 1) % count]).normalized()
            bend = prev - prev.dot(t) * t
            if bend.length > 1e-6:
                bend.normalize()
                scale = 1.0 / max(0.35, prev.dot(t))
            else:
                bend = None
        ring = []
        for j in range(sides):
            phi = 2.0 * math.pi * j / sides
            offset = normal * (math.cos(phi) * rn) + binormal * (math.sin(phi) * rb)
            if bend is not None:
                # Only the component in the bend plane needs the mitre stretch.
                offset = offset + bend * (offset.dot(bend) * (scale - 1.0))
            ring.append(bm.verts.new(path[i] + offset))
        rings.append(ring)
        verts.extend(ring)

    faces = []
    spans = count if closed else count - 1
    for i in range(spans):
        a, b = rings[i], rings[(i + 1) % count]
        for j in range(sides):
            k = (j + 1) % sides
            faces.append(bm.faces.new((a[j], a[k], b[k], b[j])))
    if not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))

    _orient_outward(bm, faces)
    return verts, faces


def _loft(bm, part: Part):
    """Skin a stack of rings (any shape, same point count) into one closed solid.

    Promoted from items_bronze.py's module-local `bronze_loft` (identical code, so
    the amphora-family items build the same). A ring of one point is a pole and may
    only sit at either end; `closed=True` joins the last ring back to the first
    (a torus-like loop, no caps). Open ends with r > 0 are capped flat.
    """
    rings = [[tuple(map(float, p)) for p in ring] for ring in part.extras["rings"]]
    width = max(len(r) for r in rings)
    rows, verts = [], []
    for i, ring in enumerate(rings):
        if len(ring) == 1:
            if 0 < i < len(rings) - 1:
                raise ValueError(f"loft ring {i} is a pole mid-stack")
        elif len(ring) != width:
            raise ValueError(f"loft ring {i} has {len(ring)} points, expected {width}")
        row = [bm.verts.new(p) for p in ring]
        rows.append(row)
        verts.extend(row)
    closed = bool(part.extras.get("closed", False))
    if closed and any(len(r) == 1 for r in rows):
        raise ValueError("a closed loft cannot have poles")
    faces = []
    for a, b in zip(rows, rows[1:] + (rows[:1] if closed else [])):
        for j in range(width):
            k = (j + 1) % width
            if len(a) == 1 and len(b) == 1:
                raise ValueError("loft has two consecutive poles")
            if len(a) == 1:
                quad = (a[0], b[k], b[j])
            elif len(b) == 1:
                quad = (a[j], a[k], b[0])
            else:
                quad = (a[j], a[k], b[k], b[j])
            faces.append(bm.faces.new(quad))
    if not closed and len(rows[0]) > 1:
        faces.append(bm.faces.new(list(reversed(rows[0]))))
    if not closed and len(rows[-1]) > 1:
        faces.append(bm.faces.new(rows[-1]))
    _orient_outward(bm, faces)
    return verts, faces


def _sweep(bm, part: Part):
    """A tube whose section changes along its path: limbs, tails, necks, horns.

    extras["path"]     [(x, y, z), ...] in metres (>= 2 points)
    extras["sections"] one (rn, rb) per path point: half-extents along the frame
                       normal and binormal. A section of (0, 0) at either END makes
                       that end a pole (a pointed tip) instead of a flat cap.
    extras["up"]       hint for the frame normal (as `tube`); rn lies along it.
    extras["power"]    superellipse exponent of the section (2 = ellipse, 4 = a
                       rounded box — sleeves, planks). Default 2.
    extras["offsets"]  optional [(dn, db), ...] shifts each ring's centre along its
                       normal/binormal: a calf that bulges backward, a belly that
                       hangs, without bending the path (and so the bone) itself.
    Frames are parallel-transported like `tube`, but corners are not mitred: a
    sweep is meant for smooth, well-sampled paths (use kit.spline).
    """
    path = [Vector(p) for p in part.extras["path"]]
    sections = [tuple(map(float, s)) for s in part.extras["sections"]]
    offsets = part.extras.get("offsets") or [(0.0, 0.0)] * len(path)
    if len(path) < 2 or len(sections) != len(path) or len(offsets) != len(path):
        raise ValueError(f"sweep needs >= 2 path points with one section/offset each "
                         f"(path {len(path)}, sections {len(sections)}, offsets {len(offsets)})")
    for i, (rn, rb) in enumerate(sections):
        pole = rn <= 1e-6 and rb <= 1e-6
        if pole and 0 < i < len(path) - 1:
            raise ValueError(f"sweep section {i} is zero mid-path; only ends may be poles")
        if not pole and (rn <= 1e-6 or rb <= 1e-6):
            raise ValueError(f"sweep section {i} {sections[i]} is flat on one axis")
    sides = max(3, part.segments)
    power = float(part.extras.get("power", 2.0))

    def tangent(i):
        if i == 0:
            t = path[1] - path[0]
        elif i == len(path) - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        if t.length < 1e-9:
            raise ValueError(f"sweep path doubles back on itself at point {i}")
        return t.normalized()

    t0 = tangent(0)
    hint = part.extras.get("up")
    if hint is None:
        axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
        hint = min(axes, key=lambda a: abs(a.dot(t0)))
    normal = Vector(hint) - Vector(hint).dot(t0) * t0
    if normal.length < 1e-6:
        raise ValueError("sweep 'up' hint is parallel to the path")
    normal.normalize()

    def superellipse(phi):
        c, s = math.cos(phi), math.sin(phi)
        e = 2.0 / power
        return (math.copysign(abs(c) ** e, c), math.copysign(abs(s) ** e, s))

    rows, verts = [], []
    for i, p in enumerate(path):
        t = tangent(i)
        normal = normal - normal.dot(t) * t
        if normal.length < 1e-6:
            raise ValueError(f"sweep frame collapsed at point {i}")
        normal.normalize()
        binormal = t.cross(normal)
        rn, rb = sections[i]
        dn, db = offsets[i]
        centre = p + normal * dn + binormal * db
        if rn <= 1e-6 and rb <= 1e-6:
            pole = bm.verts.new(centre)
            rows.append([pole])
            verts.append(pole)
            continue
        row = []
        for j in range(sides):
            u, v = superellipse(2.0 * math.pi * j / sides)
            row.append(bm.verts.new(centre + normal * (u * rn) + binormal * (v * rb)))
        rows.append(row)
        verts.extend(row)

    faces = []
    for a, b in zip(rows, rows[1:]):
        for j in range(sides):
            k = (j + 1) % sides
            if len(a) == 1:
                quad = (a[0], b[k], b[j])
            elif len(b) == 1:
                quad = (a[j], a[k], b[0])
            else:
                quad = (a[j], a[k], b[k], b[j])
            faces.append(bm.faces.new(quad))
    if len(rows[0]) > 1:
        faces.append(bm.faces.new(list(reversed(rows[0]))))
    if len(rows[-1]) > 1:
        faces.append(bm.faces.new(rows[-1]))
    _orient_outward(bm, faces)
    return verts, faces


_NEW_BUILDERS = {"lathe": _lathe, "prism": _prism, "tube": _tube,
                 "loft": _loft, "sweep": _sweep}

# --------------------------------------------------------------------------------
# Unit primitives
# --------------------------------------------------------------------------------

def _call_with_radius(op, bm, **kwargs):
    """Call a bmesh primitive op across Blender's radius/diameter argument renames."""
    try:
        return op(bm, **kwargs)
    except TypeError:
        swapped = {}
        for key, value in kwargs.items():
            if key == "radius":
                swapped["diameter"] = value * 2.0
            elif key.startswith("radius"):
                swapped["diameter" + key[len("radius"):]] = value * 2.0
            else:
                swapped[key] = value
        return op(bm, **swapped)


def _primitive(bm, part: Part):
    kind = part.kind
    if kind == "box":
        return _call_with_radius(bmesh.ops.create_cube, bm, size=1.0)["verts"]
    if kind in ("cyl", "cone"):
        top = 0.0 if kind == "cone" else 0.5 * part.taper
        return _call_with_radius(bmesh.ops.create_cone, bm, cap_ends=True, cap_tris=False,
                                 segments=max(3, part.segments), radius1=0.5, radius2=top,
                                 depth=1.0)["verts"]
    if kind == "sphere":
        return _call_with_radius(bmesh.ops.create_uvsphere, bm, u_segments=max(3, part.segments),
                                 v_segments=max(2, part.rings), radius=0.5)["verts"]
    raise ValueError(f"unknown part kind: {kind!r}")


KINDS = ("box", "cyl", "cone", "sphere", "lathe", "prism", "tube", "loft", "sweep")


# --------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------

def _mirror_bone(bone: str, mirrored: bool) -> str:
    return bone[:-2] + ".R" if mirrored and bone.endswith(".L") else bone


def families_used(parts: list[Part]) -> list[str]:
    """Every family the parts put on the mesh (paint included), first-use order."""
    out: list[str] = []
    for part in parts:
        for key in [part.mat] + [r["mat"] for r in part.paint]:
            if key not in out:
                out.append(key)
    return out


def _face_family(face, regions, default: str) -> str:
    centre = face.calc_center_median()
    for region in reversed(regions):   # later regions paint over earlier ones
        lo, hi = region["min"], region["max"]
        if all(lo[a] <= centre[a] <= hi[a] for a in range(3)):
            return region["mat"]
    return default


def build_bmesh(parts: list[Part], cells: dict[str, tuple[float, float]]):
    """Assemble parts into one bmesh with palette UVs.

    `cells` maps family -> (u, v) palette-cell centre. Returns (bm, vert_part,
    vert_bone): per vertex index (bm.to_mesh keeps bm.verts order), the part id
    (part_number * 2 + mirrored) and the bone name it was built on.
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    # bmesh ops free and reuse vertex slots, so iteration order is NOT creation order:
    # stamp each vertex with its part the moment it exists (an int layer survives to_mesh).
    part_layer = bm.verts.layers.int.new("forge_part")
    bone_of: dict[int, str] = {}
    for number, part in enumerate(parts):
        if part.kind not in KINDS:
            raise ValueError(f"part {number}: unknown kind {part.kind!r}; kinds are {KINDS}")
        for key in [part.mat] + [r["mat"] for r in part.paint]:
            if key not in cells:
                raise ValueError(f"part {number} ({part.kind}) uses family {key!r}, "
                                 f"not in the asset's families {sorted(cells)}")
        if any(abs(s) < 1e-9 for s in part.size):
            raise ValueError(f"part {number} ({part.kind}) has a zero size component")
        for r in part.paint:
            if {"mat", "min", "max"} - set(r):
                raise ValueError(f"part {number}: paint region {r} needs mat/min/max")

        for mirrored in ((False, True) if part.mirror else (False,)):
            if part.kind in _NEW_BUILDERS:
                verts, faces = _NEW_BUILDERS[part.kind](bm, part)
            else:
                verts = _primitive(bm, part)
                faces = list({f for v in verts for f in v.link_faces})
            # Families are decided in local space, before placement moves the verts.
            fams = [_face_family(f, part.paint, part.mat) if part.paint else part.mat
                    for f in faces]
            for r in part.paint:
                if r["mat"] != part.mat and r["mat"] not in fams:
                    raise ValueError(f"part {number} ({part.kind}): paint region {r} contains "
                                     f"no face centroid; put profile/outline points on the band edges")
            basis = (Matrix.Translation(Vector(part.loc))
                     @ Euler([math.radians(a) for a in part.rot], "XYZ").to_matrix().to_4x4()
                     @ Matrix.Diagonal(Vector(part.size).to_4d()))
            if mirrored:
                basis = MIRROR @ basis
            bmesh.ops.transform(bm, matrix=basis, verts=verts)
            if basis.determinant() < 0.0:   # a reflection turns the island inside-out
                bmesh.ops.reverse_faces(bm, faces=faces)
            # Edge hardness is set after placement (non-uniform scale changes angles).
            for edge in {e for f in faces for e in f.edges}:
                edge.smooth = part.smooth or edge.calc_face_angle(0.0) <= SMOOTH_ANGLE
            for face, fam in zip(faces, fams):
                face.smooth = True
                for loop in face.loops:
                    loop[uv_layer].uv = cells[fam]
            pid = number * 2 + (1 if mirrored else 0)
            bone_of[pid] = _mirror_bone(part.bone, mirrored)
            for vert in verts:
                vert[part_layer] = pid
    bm.verts.index_update()
    bm.faces.index_update()
    vert_part = [v[part_layer] for v in bm.verts]
    vert_bone = [bone_of[p] for p in vert_part]
    return bm, vert_part, vert_bone


# --------------------------------------------------------------------------------
# Authoring helpers for blueprints
# --------------------------------------------------------------------------------

def ring_of(count: int, radius: float, z: float, start_deg: float = 0.0,
            face_out: bool = True, **part_kwargs) -> list[Part]:
    """Repeat a part evenly around the Z axis."""
    base_loc = part_kwargs.pop("loc", (0.0, 0.0, 0.0))
    base_rot = part_kwargs.pop("rot", (0.0, 0.0, 0.0))
    out = []
    for i in range(count):
        yaw = start_deg + 360.0 * i / count
        theta = math.radians(yaw)
        out.append(Part(
            loc=(base_loc[0] + math.cos(theta) * radius,
                 base_loc[1] + math.sin(theta) * radius,
                 base_loc[2] + z),
            rot=(base_rot[0], base_rot[1], base_rot[2] + (yaw if face_out else 0.0)),
            **part_kwargs,
        ))
    return out


def arc_path(centre, radius: float, start_deg: float, end_deg: float, steps: int,
             axis_u=(1.0, 0.0, 0.0), axis_v=(0.0, 0.0, 1.0)) -> list[tuple]:
    """Points on a circular arc in the plane spanned by axis_u, axis_v (for tubes)."""
    c, u, v = Vector(centre), Vector(axis_u), Vector(axis_v)
    out = []
    for i in range(steps + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        out.append(tuple(c + u * (math.cos(a) * radius) + v * (math.sin(a) * radius)))
    return out


def rounded_rect(width: float, height: float, radius: float, steps: int = 3,
                 cx: float = 0.0, cy: float = 0.0) -> list[tuple]:
    """A rectangle outline with rounded corners, for prisms."""
    radius = min(radius, width / 2.0, height / 2.0)
    hw, hh = width / 2.0 - radius, height / 2.0 - radius
    out = []
    for corner, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        start = 90.0 * corner
        for i in range(steps + 1):
            a = math.radians(start + 90.0 * i / steps)
            out.append((cx + sx * hw + math.cos(a) * radius,
                        cy + sy * hh + math.sin(a) * radius))
    return out


def gable_outline(width: float, shoulder: float, apex: float,
                  base: float = 0.0) -> list[tuple]:
    """A house-shaped outline in XY: rectangle from `base` to `shoulder`, then a
    gable rising to a point at `apex`. For panels, pediments and shrine roofs."""
    hw = width / 2.0
    return [(-hw, base), (hw, base), (hw, shoulder), (0.0, apex), (-hw, shoulder)]


def spline(points, per_segment: int = 3) -> list[tuple]:
    """Catmull-Rom through `points` (2D or 3D), `per_segment` samples per span.

    For tube paths and lathe profiles that should read as curves: pass a handful of
    control points and let this add the in-betweens. Endpoints are kept exactly.
    """
    pts = [Vector(p) if len(p) == 3 else Vector((p[0], p[1], 0.0)) for p in points]
    dim = len(points[0])
    if len(pts) < 3:
        return [tuple(p) for p in points]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for step in range(per_segment):
            t = step / per_segment
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(tuple(q)[:dim])
    out.append(tuple(pts[-1])[:dim])
    return out


def section(centre, half_u: float, half_v: float, n: int, u_axis=(1.0, 0.0, 0.0),
            v_axis=(0.0, 1.0, 0.0), power: float = 2.0, start_deg: float = 0.0,
            bulge=None) -> list[tuple]:
    """One loft ring: a superellipse of `n` points around `centre`.

    `half_u` / `half_v` are half-extents along `u_axis` / `v_axis` (default: a
    horizontal ring, u = X, v = Y). `power` 2 is an ellipse, 3-4 a rounded box.
    `bulge(angle_rad) -> factor` scales the radius per direction (a chest that
    projects forward, a flat back). Every ring in one loft must use the same `n`
    and `start_deg` so point j lines up with point j.
    """
    c, u, v = Vector(centre), Vector(u_axis), Vector(v_axis)
    e = 2.0 / power
    out = []
    for j in range(n):
        a = math.radians(start_deg) + 2.0 * math.pi * j / n
        ca, sa = math.cos(a), math.sin(a)
        k = bulge(a) if bulge else 1.0
        out.append(tuple(c + u * (math.copysign(abs(ca) ** e, ca) * half_u * k)
                         + v * (math.copysign(abs(sa) ** e, sa) * half_v * k)))
    return out
