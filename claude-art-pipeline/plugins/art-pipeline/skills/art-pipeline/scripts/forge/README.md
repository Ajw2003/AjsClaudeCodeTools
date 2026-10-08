# forge: an engine-free model forge

Blender-as-a-module (`bpy`), Pillow and the standard library; no engine, no repo layout assumed.
A new project writes a **spec JSON** and a **blueprints.py**; the forge builds, validates and
exports each asset. Extracted and simplified from PlunderSpell's ArtForge / EnemyForge / AnimForge
(see "What was dropped").

```bash
cd <this skill's folder>
python3.13 scripts/forge/build.py --spec examples/forge/spec.json \
    --blueprints examples/forge/blueprints.py --out /abs/path/out          # --only lantern to build one
```

Exit 0 only if every asset built passed the validator; 1 if any failed (the report names why); 2 on bad
input, including a blueprint slug the spec does not list and an `--only` slug with no blueprint. Use
the interpreter `setup_bpy.sh` printed (a Python with a matching `bpy` wheel and Pillow). The worked
example builds a 0.4 m lantern and a rigged 1.80 m humanoid (`dummy`, idle plus a 1.4 m/s walk) in
about two seconds, then look at them: `examples/forge/*-review.png` are what they looked like.

## Spec (`spec.json`)

```json
{"assets": {"lantern": {
  "name": "Lantern",            "height_m": 0.40,       "tolerance": 0.05,
  "dims": [0.16, 0.16, 0.40],   "dim_tolerance": 0.10,  "tri_budget": 1500,
  "families": {"iron": {"base": "#2E2C30"}, "wax": {"base": "#E8DCC0"}},
  "clips": {"idle": {}, "walk": {"speed": 1.4}}}}}
```

`height_m` and `families` are required. `name` (default: the slug in PascalCase) names the folder, files
and object. `tolerance` is the allowed height error as a fraction (default 0.05); `dims` (W = x, D = y,
H = z) is an optional per-axis bounding-box check; `tri_budget` defaults to 2000. A **family** is a named
colour; parts refer to it by key. At most 64 families per asset. `clips` is for rigged assets only.

## Blueprint API (`blueprints.py`)

`BLUEPRINTS = {slug: builder}`; `builder(entry) -> forge.Blueprint`. `entry` is the parsed spec entry
(`entry.height_m`, `entry.families`, ...). `from forge import Blueprint, Part, Human, arc_path, spline, ring_of, rounded_rect, section, gable_outline`.

`Blueprint(parts, bones=None, forward_bones=[], tri_budget=None, grounded=True)`. Setting `bones` makes it
rigged. Z is up, the model stands on z = 0, centred on x = y = 0 and faces **-Y**; metres.

`Part(kind, loc, size, mat, bone="Root", rot, mirror, segments, rings, taper, smooth, rigid, prop, bones, skirt, paint, extras)`.
`mat` is a spec family key. Kinds (`size` is the full extent; geometry-defining kinds take `size=(1,1,1)` for true metres):

| kind | what | data in `extras` |
|---|---|---|
| `box`, `cyl` (`taper` = top/bottom radius), `cone`, `sphere` (`segments`, `rings`) | unit primitives | - |
| `lathe` | revolve a profile (pots, hats, roofs) | `profile=[(r, z), ...]` bottom to top; `r = 0` end is a pole, `r > 0` end is capped |
| `prism` | extrude an outline (blades, plaques), concave ok | `outline=[(x, y), ...]`; depth is `size[2]` |
| `tube` | sweep a round/elliptic section along a path (handles, straps, rings) | `path`, `section=(rn, rb)`, optional `up`, `closed` |
| `loft` | skin a stack of rings (torsos, robes, shoes) | `rings=[[(x,y,z),...], ...]`, same point count, 1 point = pole |
| `sweep` | a tube whose section changes (limbs, tails) | `path`, `sections=[(rn, rb), ...]`, optional `up`, `power`, `offsets` |

`mirror=True` adds a copy across the YZ plane (a `.L` bone becomes `.R`). `smooth=True` shades every edge
smooth (edges sharper than 35 degrees stay hard otherwise). `paint=[{"mat", "min", "max"}]` restamps faces
whose centroid is inside a local box with another family, so trim stays on one shell.

**Rig rules per part** (rigged assets): `rigid` = bound 1.0 to `bone` (hats, buckles, feet); `prop` = rigid
and left out of the height check; `bones=[...]` = the only bones the part may be weighted to; `skirt={top,
bottom, left, right, strength, split}` = hands the part below a height to the thighs so a lifted knee does
not go through a robe; otherwise a part blends with its own bone, that bone's parent and children.

**Humanoid**: `fig = Human(height=entry.height_m)`; `fig.body(skin=, torso=, sleeves=, legs=, feet=, joints=)` returns
a mannequin's parts already bound; `fig.rig()` returns `{bones, forward_bones}` for `Blueprint(...)`;
`fig.joint("Head")`, `fig.bone(name)`, `fig.add_bone(...)` give landmarks and extra bones. Bones follow
Unity Humanoid (`UNITY_HUMANOID` maps them) with `.L`/`.R`: `Root > Hips > Spine > Chest > Neck > Head`,
`Chest > UpperArm > LowerArm > Hand`, `Hips > UpperLeg > LowerLeg > Foot`. Bind pose is an A-pose (25 degrees);
the engine's importer builds the T-pose avatar.

## Clips

`"clips": {"walk": {"speed": 1.4}, "idle": {}, "t_pose": {}}`; a clip name is `walk`, `idle` or a pose in
`forge.anim.POSES` (`a_pose`, `t_pose`, `arms_up`, `reach`, `crouch`; a 2-frame hold). All are authored on the
model's own rig, in place, 30 fps, looped (last key equals first). The walk is parametric: stride is
`speed * cycle` (step 0.43 of the height), a planted ankle slides back at exactly `speed` so in the world it
stands still, legs reach by two-bone IK and the hips drop only as far as needed. Bake reports
`foot_slide_mm` (flat-foot ankle drift in the world, limit 25 mm) in the validator output. A pose is
`{bone: (rx, ry, rz)}` degrees about world axes (negative X swings a hanging arm toward the front);
`"_hips": (x, y, z)` offsets the hips as a fraction of height, `"_pin_feet": True` holds the ankles by IK.
`forge.anim.apply_pose(rig, pose, height)` poses a rig for your own review renders.

## Outputs (`<out>/<Name>/`)

`<Name>.fbx` (Unity axes: Blender -Y front to Unity +Z, Z up to Y up, scale 1 m, no leaf bones; armature and
one take per clip when rigged), `<Name>.glb` (Y up, texture embedded, animations), `<Name>.blend`,
`Textures/<Name>_BaseMap.png` (the palette), `<Name>.report.json`. The material is **one slot**: a 128x128
palette PNG, one 16 px cell per family, with every face's UVs on its family's cell centre. No bake, no unwrap.

## Validator

Fails: loose geometry, non-manifold edges, inconsistent winding, inverted shells, zero-area faces;
anything but exactly one material slot or any UV outside 0..1; object not at the origin; lowest point not
at z = 0 (+-2 cm); triangles over budget; height outside `tolerance` (props excluded when rigged) or `dims`
outside `dim_tolerance`; static mesh with vertex groups. Rigged: any unweighted vertex, weights not summing
to 1, more than 4 influences, not exactly one bound Armature modifier, forward bones (`Foot.*`) not pointing
-Y, a clip whose planted foot slides over 25 mm, a clip missing from the re-imported FBX. Warnings: off-centre
silhouette, heat weighting fell back to distance weights. **A pass means the numbers are legal, not that it
looks right**: render it (`scripts/render_views.py`) and look.

## Traps this code already hit

- bmesh ops free and reuse vertex slots, so `bm.verts` iteration order is not creation order. Per-vertex
  facts (part, bone) are stamped in an int layer the moment the vertex exists (`kit.build_bmesh`); counting
  verts per part scrambled the skin weights.
- Positive X rotation tips a -Y toe *down*. A foot pitched about its ankle digs into the floor unless the
  ankle is raised (`Walk.ankle`); feet are `rigid` so shin weights cannot drag the toes under the floor.
- Heat weighting fails at random on disjoint islands; it is retried with sub-millimetre nudges, then the
  per-part rules and a distance-weight fallback still weight every vertex.

## What was dropped from ArtForge

The PlunderSpell content (ages, enemy/item/structure kinds, art-bible JSON, orpiment/lapis pigment
rules), PBR bakes (roughness, metallic, emission, wear and ridge shaders, packed maps) in favour of the
palette, edge bevel, `torus`/`ico`/`shard` kinds, the quadruped, clothing helpers (`torso_part` with
quilting, belts), the weapon bone and two-handed polearm IK, the AnimForge reference-skeleton retargeting,
foot-roll world-lock tuning, upper-body masks and the review-sheet plumbing, the per-asset review pose
stored on the rig, and the `bbox_overrides` escape hatch.
