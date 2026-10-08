"""Gate every model before it is called done.

Failures (non-zero exit from build.py):
  geometry   loose verts / wire edges, non-manifold edges, inconsistent winding, inverted
             shells (signed volume <= 0), zero-area faces
  material   exactly one material slot, every face on it, a UV map with every UV in 0..1
  placement  object at the origin with identity transform; lowest point at z = 0 (+-2 cm)
  budget     triangles <= tri_budget
  size       height within `tolerance` of the spec's height_m (rigged: props excluded);
             optional `dims` bbox per axis within `dim_tolerance`
  rigged     every vertex weighted, weights sum to 1, <= 4 influences, one Armature
             modifier, vertex groups all have bones, forward bones point -Y, heat
             weighting did not collapse, clips: foot slide <= 25 mm and every take present
  static     no vertex groups, no Armature modifier
Warnings are reported and do not fail: off-centre silhouette, distance-weighted fallback.

Passing means the numbers are legal. It cannot say the lantern looks like a lantern:
render it and look.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import bmesh
import bpy

from . import rig as rigmod

SLIDE_LIMIT_MM = 25.0


@dataclass
class Report:
    name: str
    stats: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def text(self) -> str:
        lines = [f"[{'PASS' if self.passed else 'FAIL'}] {self.name}",
                 "        " + "  ".join(f"{k}={v}" for k, v in self.stats.items())]
        lines += [f"        ! {f}" for f in self.failures] + [f"        ~ {w}" for w in self.warnings]
        return "\n".join(lines)


def _islands(bm) -> list[list]:
    parent = list(range(len(bm.verts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    buckets: dict[int, list] = {}
    for f in bm.faces:
        buckets.setdefault(find(f.verts[0].index), []).append(f)
    return list(buckets.values())


def _signed_volume(faces) -> float:
    total = 0.0
    for f in faces:
        v = f.verts
        for i in range(1, len(v) - 1):
            total += v[0].co.cross(v[i].co).dot(v[i + 1].co)
    return total / 6.0


def validate(obj, bp, vert_part: list[int] | None = None, build_info: dict | None = None) -> Report:
    entry = bp.entry
    rep = Report(bp.slug)
    fail, warn = rep.failures.append, rep.warnings.append

    if tuple(round(v, 6) for v in obj.location) != (0.0, 0.0, 0.0):
        fail(f"origin is not at the world origin: {tuple(obj.location)}")
    if tuple(round(v, 6) for v in obj.scale) != (1.0, 1.0, 1.0) or any(round(v, 6) for v in obj.rotation_euler):
        fail("object scale/rotation is not identity")

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.index_update()
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    rep.stats.update(vertices=len(bm.verts), triangles=tris, budget=bp.budget, islands=len(_islands(bm)))
    if tris > bp.budget:
        fail(f"{tris} triangles exceeds the {bp.budget} budget")

    n = sum(1 for v in bm.verts if not v.link_faces)
    if n:
        fail(f"{n} loose vertices with no faces")
    n = sum(1 for e in bm.edges if not e.link_faces)
    if n:
        fail(f"{n} wire edges with no faces")
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    if n:
        fail(f"{n} non-manifold edges (holes or internal faces)")
    n = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    if n:
        fail(f"{n} edges with inconsistent winding")
    n = sum(1 for shell in _islands(bm) if _signed_volume(shell) <= 0.0)
    if n:
        fail(f"{n} shells have inverted normals")
    n = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    if n:
        fail(f"{n} degenerate (zero-area) faces")

    uv = bm.loops.layers.uv.active
    if uv is None:
        fail("no UV map")
    else:
        bad = sum(1 for f in bm.faces if any(not (-0.001 <= c <= 1.001) for lp in f.loops for c in lp[uv].uv))
        if bad:
            fail(f"{bad} faces have UVs outside 0..1")
    if len(mesh.materials) != 1:
        fail(f"expected exactly one material slot, found {len(mesh.materials)}")
    if {f.material_index for f in bm.faces} - {0}:
        fail("faces reference missing material slots")

    zs = [v.co.z for v in bm.verts]
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    lowest = min(zs)
    size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - lowest)
    rep.stats.update(lowest_z=round(lowest, 4), bbox_m="x".join(f"{s:.3f}" for s in size))
    if bp.grounded and abs(lowest) > 0.02:
        fail(f"lowest point is at z={lowest:.3f}, not on the ground plane")
    for axis, c in (("X", (max(xs) + min(xs)) / 2), ("Y", (max(ys) + min(ys)) / 2)):
        if abs(c) > 0.35 * max(size[0], size[1], 0.01):
            warn(f"silhouette is off-centre in {axis} by {c:.2f} m")

    height = max(zs)
    if bp.rigged and vert_part is not None:
        props = {i for i, p in enumerate(bp.parts) if p.prop}
        body = [z for z, pid in zip(zs, vert_part) if pid // 2 not in props]
        if body:
            height = max(body)
            rep.stats["height_with_props_m"] = round(max(zs), 3)
    rep.stats.update(height_m=round(height, 3), height_spec_m=entry.height_m)
    if abs(height - entry.height_m) > entry.height_m * entry.tolerance:
        fail(f"height {height:.3f} m is not within +-{entry.tolerance * 100:.0f} % of the spec's "
             f"{entry.height_m:.3f} m")
    if entry.dims:
        for i, axis in enumerate("XYZ"):
            ratio = size[i] / entry.dims[i]
            if abs(ratio - 1.0) > entry.dim_tolerance:
                fail(f"{axis} extent {size[i]:.3f} m is {ratio * 100 - 100:+.0f} % off the spec's "
                     f"{entry.dims[i]:.3f} m (tolerance +-{entry.dim_tolerance * 100:.0f} %)")

    arm = [m for m in obj.modifiers if m.type == "ARMATURE"]
    if not bp.rigged:
        if obj.vertex_groups:
            fail(f"static mesh has {len(obj.vertex_groups)} vertex groups")
        if arm:
            fail("static mesh has an armature modifier")
    else:
        if len(arm) != 1 or arm[0].object is None:
            fail(f"expected exactly one bound Armature modifier, found {len(arm)}")
        else:
            bone_names = {b.name for b in arm[0].object.data.bones}
            missing = {g.name for g in obj.vertex_groups} - bone_names
            if missing:
                fail(f"vertex groups without bones: {sorted(missing)}")
            rep.stats["bones"] = len(bone_names)
        unweighted = bad_sum = over = 0
        for v in mesh.vertices:
            ws = [g.weight for g in v.groups if g.weight > 1e-6]
            if not ws:
                unweighted += 1
            elif abs(sum(ws) - 1.0) > 1e-3:
                bad_sum += 1
            if len(ws) > rigmod.MAX_INFLUENCES:
                over += 1
        if unweighted:
            fail(f"{unweighted} vertices are not assigned to any bone")
        if bad_sum:
            fail(f"{bad_sum} vertices have weights that do not sum to 1")
        if over:
            fail(f"{over} vertices have more than {rigmod.MAX_INFLUENCES} bone influences")
        fail_list = rigmod.facing_problems(bp.bones, bp.forward_bones)
        rep.failures.extend(fail_list)
        info = build_info or {}
        heat = info.get("heat", {})
        rep.stats["weights"] = ("heat" if heat.get("heat_ok") else "distance-fallback")
        rep.stats["mean_influences"] = info.get("rules", {}).get("mean_influences")
        if not heat.get("heat_ok"):
            warn(f"heat weighting unavailable ({heat.get('reason', 'collapsed to one bone')}); "
                 f"distance weights used")
        for name, m in info.get("clips", {}).items():
            rep.stats[f"clip_{name}"] = " ".join(f"{k}={v}" for k, v in m.items() if k in ("frames", "foot_slide_mm", "speed_mps", "stride_m"))
            if m.get("foot_slide_mm", 0.0) > SLIDE_LIMIT_MM:
                fail(f"clip {name}: planted foot slides {m['foot_slide_mm']} mm (limit {SLIDE_LIMIT_MM:.0f})")
    bm.free()
    return rep


def report_json(rep: Report) -> str:
    return json.dumps({"name": rep.name, "passed": rep.passed, "stats": rep.stats,
                       "failures": rep.failures, "warnings": rep.warnings}, indent=2)
