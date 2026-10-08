"""One asset: blueprint -> mesh -> (rig, weights, clips) -> validate -> FBX, GLB, .blend.

Output for an entry named Lantern, in <out>/Lantern/:
  Lantern.fbx   Unity axes (Blender -Y front -> Unity +Z, Z up -> Y up), 1 unit = 1 m, mesh
                (+ armature and one take per clip when rigged); no leaf bones
  Lantern.glb   glTF binary, Y up, the same content, texture embedded
  Lantern.blend the scene as built (texture path relative)
  Textures/Lantern_BaseMap.png   the palette
  Lantern.report.json            the validator's report (+ clip metrics)
"""

from __future__ import annotations

import json
import os

import bpy

from . import anim, kit, materials, rig as rigmod, validate as validate_mod
from .blueprint import Blueprint
from .spec import Entry


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def build_object(bp: Blueprint, texture_path: str):
    """The joined mesh with its one palette material (and rigid vertex groups if rigged)."""
    families = bp.ordered_families()
    materials.write_palette(texture_path, families, bp.entry.families)
    bm, vert_part, vert_bone = kit.build_bmesh(bp.parts, materials.cell_centres(families))
    mesh = bpy.data.meshes.new(bp.entry.name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(materials.build_material(f"{bp.entry.name}_Mat", texture_path))
    mesh.update()
    obj = bpy.data.objects.new(bp.entry.name, mesh)
    bpy.context.collection.objects.link(obj)
    if bp.rigged:
        groups: dict[str, list[int]] = {}
        for i, bone in enumerate(vert_bone):
            groups.setdefault(bone, []).append(i)
        for bone, idx in groups.items():
            obj.vertex_groups.new(name=bone).add(idx, 1.0, "REPLACE")
    return obj, vert_part


def _select(*objs) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[-1]


def export(obj, rig, actions, bp: Blueprint, model_dir: str) -> dict:
    name = bp.entry.name
    scene = bpy.context.scene
    objs = [obj] if rig is None else [obj, rig]
    if actions:
        scene.render.fps = anim.FPS
        scene.frame_start = 0
        scene.frame_end = max(int(a.frame_range[1]) for a in actions)
        rig.animation_data.action = None
        for a in actions:      # one NLA strip per action: the exporters write each as a take
            track = rig.animation_data.nla_tracks.new()
            track.name = a.name
            track.strips.new(a.name, 0, a).name = a.name
    elif rig is not None:
        anim.reset_pose(rig)
    _select(*objs)
    fbx = os.path.join(model_dir, f"{name}.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx, use_selection=True,
        object_types={"MESH"} if rig is None else {"ARMATURE", "MESH"},
        add_leaf_bones=False, bake_anim=bool(actions),
        bake_anim_use_all_bones=True, bake_anim_use_nla_strips=True,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
        mesh_smooth_type="FACE", use_mesh_modifiers=False,
        path_mode="RELATIVE", embed_textures=False,
        apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
        axis_forward="-Z", axis_up="Y")
    glb = os.path.join(model_dir, f"{name}.glb")
    _select(*objs)
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=False, export_animations=bool(actions))
    blend = os.path.join(model_dir, f"{name}.blend")
    bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    # Sidecar the Unity package's importer reads (claude-art-pipeline/unity/README.md).
    sidecar = os.path.join(model_dir, f"{name}.art.json")
    clips = []
    for a in actions:
        clip = a.name.split("|")[-1]
        clips.append({"name": clip, "loop": bool(bp.entry.clips.get(clip, {}).get("loop", True))})
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump({"kind": bp.entry.raw.get("kind") or ("character" if rig else "prop"),
                   "rig": "humanoid" if rig else "none", "clips": clips}, fh)
    return {"fbx": fbx, "glb": glb, "blend": blend, "sidecar": sidecar}


def read_back_takes(fbx: str, expected: dict) -> list[str]:
    """Re-import the FBX in a fresh scene and check every clip is a take of the right length."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    got = {}
    for a in bpy.data.actions:
        name = a.name.split("|")[-1]
        got[name] = tuple(int(round(v)) for v in a.frame_range)
    problems = []
    for clip, m in expected.items():
        if clip not in got:
            problems.append(f"clip {clip!r} is not a take in the exported FBX (found {sorted(got)})")
        elif got[clip][1] - got[clip][0] != m["frames"]:
            problems.append(f"clip {clip!r} has {got[clip][1] - got[clip][0]} frames in the FBX, "
                            f"expected {m['frames']}")
    return problems


def build_asset(entry: Entry, builder, out_dir: str) -> validate_mod.Report:
    reset_scene()
    bp = builder(entry)
    if not isinstance(bp, Blueprint):
        raise TypeError(f"{entry.slug}: the builder must return a forge.Blueprint, got {type(bp).__name__}")
    bp.slug, bp.entry = entry.slug, entry
    model_dir = os.path.join(out_dir, entry.name)
    os.makedirs(model_dir, exist_ok=True)
    obj, vert_part = build_object(bp, os.path.join(model_dir, "Textures", f"{entry.name}_BaseMap.png"))

    rig, actions, info = None, [], {}
    if bp.rigged:
        rig = rigmod.build_armature(bp.bones, entry.name, obj)
        heat = rigmod.heat_weights(obj, rig)
        rules = rigmod.apply_bind_rules(obj, bp.parts, bp.bones, vert_part, use_heat=heat["heat_ok"])
        info.update(heat=heat, rules=rules)
        if entry.clips:
            actions, info["clips"] = anim.bake_clips(rig, entry.height_m, entry.clips)
    elif entry.clips:
        raise ValueError(f"{entry.slug}: the spec lists clips but the blueprint has no rig")

    rep = validate_mod.validate(obj, bp, vert_part, info)
    files = export(obj, rig, actions, bp, model_dir)
    if actions:
        rep.failures += read_back_takes(files["fbx"], info["clips"])
    with open(os.path.join(model_dir, f"{entry.name}.report.json"), "w", encoding="utf-8") as fh:
        fh.write(validate_mod.report_json(rep))
    rep.stats["files"] = model_dir
    return rep
