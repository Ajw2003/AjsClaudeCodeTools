"""Armature, skin weights and per-part bind rules.

Order: per-part rigid vertex groups -> armature -> Blender heat weighting (retried:
it fails at random on meshes of disjoint islands, and can "succeed" with every
vertex on one bone) -> `apply_bind_rules`, which enforces what each Part says:

- rigid / prop   every vertex 1.0 on `part.bone` (hats, buckles, lanterns, held props)
- bones=[...]    the only bones the part may be weighted to (plus its own); other heat
                 weights are dropped and the rest renormalised. ".L" swaps to ".R" on
                 the mirrored copy.
- skirt={...}    the part below a height is handed to the thighs (a robe or skirt):
                 {"top": z, "bottom": z, "left": "UpperLeg.L", "right": "UpperLeg.R",
                 "strength": 0.75, "split": 0.05}. Without it a lifted knee goes through the robe.
- otherwise      the part may blend with its own bone, that bone's parent and children
                 (never Root, unless the part is on Root).

A vertex left with no allowed weight is blended between the two nearest allowed bone
segments by distance. If heat weighting fails outright every non-rigid vertex gets
those distance weights, and the report says so. Every vertex ends weighted, <= 4
influences, normalised.
"""

from __future__ import annotations

import bpy
from mathutils import Vector

from .kit import Part, _mirror_bone

MAX_INFLUENCES = 4
MIN_WEIGHT = 0.02
HEAT_TRIES = 6


def expand_bones(bones: list[dict]) -> list[dict]:
    """Expand mirror=True records (".L" bones) into a matching ".R" across the YZ plane."""
    out = []
    for b in bones:
        out.append({k: v for k, v in b.items() if k != "mirror"})
        if b.get("mirror"):
            if not b["name"].endswith(".L"):
                raise ValueError(f"mirrored bone {b['name']!r} must end in '.L'")
            f = {k: v for k, v in b.items() if k != "mirror"}
            f["name"] = b["name"][:-2] + ".R"
            f["head"] = (-b["head"][0], b["head"][1], b["head"][2])
            f["tail"] = (-b["tail"][0], b["tail"][1], b["tail"][2])
            if b.get("parent") and b["parent"].endswith(".L"):
                f["parent"] = b["parent"][:-2] + ".R"
            out.append(f)
    return out


def build_armature(bones: list[dict], name: str, mesh_obj=None):
    """Create the rig (roll 0, not connected); with `mesh_obj`, parent it with an Armature modifier."""
    data = bpy.data.armatures.new(f"{name}_Rig")
    rig = bpy.data.objects.new(f"{name}_Rig", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    made = {}
    specs = expand_bones(bones)
    for s in specs:
        b = data.edit_bones.new(s["name"])
        b.head, b.tail = Vector(s["head"]), Vector(s["tail"])
        if b.length < 1e-4:
            raise ValueError(f"bone {s['name']!r} has zero length")
        made[s["name"]] = b
    for s in specs:
        if s.get("parent"):
            made[s["name"]].parent = made[s["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    if mesh_obj is not None:
        unbound = {g.name for g in mesh_obj.vertex_groups} - set(made)
        if unbound:
            raise ValueError(f"vertex groups with no matching bone: {sorted(unbound)}")
        mesh_obj.parent = rig
        mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
    return rig


def _heat_once(mesh_obj, rig) -> dict:
    """Blender heat weights, smoothed, limited to 4, normalised; rigid weights as a net."""
    rigid = [[(g.group, g.weight) for g in v.groups] for v in mesh_obj.data.vertices]
    names = [g.name for g in mesh_obj.vertex_groups]
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError as error:
        return {"auto_weights": False, "reason": str(error)}
    lookup = {n: mesh_obj.vertex_groups.get(n) for n in names}
    for vert in mesh_obj.data.vertices:    # vertices heat missed fall back to rigid
        if vert.groups and sum(g.weight for g in vert.groups) > 1e-4:
            continue
        for gi, w in rigid[vert.index]:
            lookup[names[gi]].add([vert.index], w, "REPLACE")
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.object.vertex_group_smooth(group_select_mode="ALL", factor=0.5, repeat=3)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=MAX_INFLUENCES)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    infl = [len([g for g in v.groups if g.weight > 1e-4]) for v in mesh_obj.data.vertices]
    return {"auto_weights": True, "max_influences": max(infl) if infl else 0}


def heat_weights(mesh_obj, rig) -> dict:
    """`_heat_once` with retries (rigid restored, mesh and rig nudged < 1 mm between tries)."""
    names = [g.name for g in mesh_obj.vertex_groups]
    rigid = [[(names[g.group], g.weight) for g in v.groups] for v in mesh_obj.data.vertices]
    stats: dict = {}
    for attempt in range(1, HEAT_TRIES + 1):
        if attempt > 1:
            mesh_obj.vertex_groups.clear()
            groups = {n: mesh_obj.vertex_groups.new(name=n) for n in names}
            for i, ws in enumerate(rigid):
                for n, w in ws:
                    groups[n].add([i], w, "REPLACE")
            off = (0.00037 * attempt, -0.00021 * attempt, 0.00013 * attempt)
            mesh_obj.location = rig.location = off
            bpy.context.view_layer.update()
        stats = _heat_once(mesh_obj, rig)
        if attempt > 1:
            mesh_obj.location = rig.location = (0.0, 0.0, 0.0)
            mesh_obj.matrix_parent_inverse.identity()
            bpy.context.view_layer.update()
        if not stats.get("auto_weights") or stats.get("max_influences", 0) > 1:
            break
    stats["heat_attempts"] = attempt
    stats["heat_ok"] = bool(stats.get("auto_weights") and stats.get("max_influences", 0) > 1)
    mods = [m for m in mesh_obj.modifiers if m.type == "ARMATURE"]   # parent_set adds its own
    for extra in mods[1:]:
        mesh_obj.modifiers.remove(extra)
    if mods:
        mods[0].object = rig
    return stats


# ---- bind rules ----------------------------------------------------------------

def _hierarchy(bones):
    parent, children = {}, {}
    for s in expand_bones(bones):
        parent[s["name"]] = s.get("parent")
        children.setdefault(s["name"], [])
    for n, p in parent.items():
        if p:
            children.setdefault(p, []).append(n)
    return parent, children


def allowed_bones(part: Part, mirrored: bool, parent: dict, children: dict) -> set[str]:
    bone = _mirror_bone(part.bone, mirrored)
    if part.rigid or part.prop:
        return {bone}
    if part.bones is not None:
        names = {_mirror_bone(n, mirrored) for n in part.bones} | {bone}
    else:
        names = {bone, *children.get(bone, [])}
        if parent.get(bone):
            names.add(parent[bone])
        if bone != "Root":
            names.discard("Root")
    unknown = names - set(parent)
    if unknown:
        raise ValueError(f"part on {bone!r} allows bones the rig does not have: {sorted(unknown)}")
    return names


def _smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _skirt_weights(weights, co, skirt):
    top, bottom = skirt["top"], skirt["bottom"]
    if co.z >= top:
        return weights
    left, right = skirt.get("left", "UpperLeg.L"), skirt.get("right", "UpperLeg.R")
    share = skirt.get("strength", 0.75) * _smoothstep(top, bottom, co.z)
    split = skirt.get("split", 0.05)
    to_left = _smoothstep(-split, split, co.x)
    rest = {n: w for n, w in weights.items() if n not in (left, right)}
    total = sum(rest.values())
    out = {n: w / total * (1.0 - share) for n, w in rest.items()} if total > 1e-6 else {}
    if not out:
        share = 1.0
    out[left] = out.get(left, 0.0) + share * to_left
    out[right] = out.get(right, 0.0) + share * (1.0 - to_left)
    return {n: w for n, w in out.items() if w > MIN_WEIGHT}


def _nearest_weights(co, allowed, segments):
    """Inverse-distance (power 4) weights to the two nearest allowed bone segments."""
    scored = []
    for name in allowed:
        head, tail = segments[name]
        axis = tail - head
        t = max(0.0, min(1.0, (co - head).dot(axis) / max(axis.length_squared, 1e-12)))
        scored.append(((co - (head + axis * t)).length, name))
    scored.sort()
    raw = {n: 1.0 / max(d, 1e-3) ** 4 for d, n in scored[:2]}
    total = sum(raw.values())
    return {n: w / total for n, w in raw.items()}


def apply_bind_rules(obj, parts: list[Part], bones: list[dict], vert_part: list[int],
                     use_heat: bool = True) -> dict:
    parent, children = _hierarchy(bones)
    segments = {s["name"]: (Vector(s["head"]), Vector(s["tail"])) for s in expand_bones(bones)}
    rules = {}
    for pid in set(vert_part):
        part, mirrored = parts[pid // 2], bool(pid % 2)
        rules[pid] = (_mirror_bone(part.bone, mirrored),
                      allowed_bones(part, mirrored, parent, children),
                      bool(part.rigid or part.prop), part.skirt)
    groups = {g.index: g.name for g in obj.vertex_groups}
    by_name = {g.name: g for g in obj.vertex_groups}
    for bone, *_ in rules.values():
        if bone not in by_name:
            by_name[bone] = obj.vertex_groups.new(name=bone)

    rigid_n = fallback = 0
    new = []
    for vert in obj.data.vertices:
        bone, allowed, rigid, skirt = rules[vert_part[vert.index]]
        if rigid:
            new.append({bone: 1.0})
            rigid_n += 1
            continue
        weights = ({groups[g.group]: g.weight for g in vert.groups
                    if g.weight > MIN_WEIGHT and groups[g.group] in allowed} if use_heat else {})
        if skirt:
            weights = _skirt_weights(weights, vert.co, skirt)
        if not weights:
            weights = _nearest_weights(vert.co, allowed, segments)
            fallback += 1
        top = sorted(weights.items(), key=lambda kv: -kv[1])[:MAX_INFLUENCES]
        total = sum(w for _n, w in top)
        new.append({n: w / total for n, w in top} if total > 1e-4 else {bone: 1.0})

    everything = list(range(len(obj.data.vertices)))
    for g in obj.vertex_groups:
        g.remove(everything)
    for i, ws in enumerate(new):
        for n, w in ws.items():
            by_name[n].add([i], w, "REPLACE")
    used = {n for w in new for n in w}
    for g in list(obj.vertex_groups):
        if g.name not in used:
            obj.vertex_groups.remove(g)
    infl = [len(w) for w in new]
    return {"rigid_vertices": rigid_n, "distance_weighted_vertices": fallback,
            "max_influences": max(infl), "mean_influences": round(sum(infl) / len(infl), 2)}


def facing_problems(bones: list[dict], forward_bones: list[str]) -> list[str]:
    """Each forward bone must point toward -Y (the model's front)."""
    specs = {s["name"]: s for s in expand_bones(bones)}
    out = []
    for name in forward_bones:
        if name not in specs:
            out.append(f"forward bone {name!r} is not in the rig")
            continue
        d = Vector(specs[name]["tail"]) - Vector(specs[name]["head"])
        if not (d.y < -1e-4 and abs(d.y) >= abs(d.x)):
            out.append(f"{name} points {tuple(round(c, 3) for c in d)}, not toward -Y: "
                       f"the model does not face -Y")
    if not forward_bones:
        out.append("blueprint names no forward_bones, so facing cannot be checked")
    return out
