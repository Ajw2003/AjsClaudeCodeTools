# Tooling and traps

## Blender as a Python module

No Blender install and no `blender` binary: `pip install bpy` gives Blender as an importable
module, and scripts run as `python3.11 script.py`, never `blender --background --python`.

- **Match the wheel to the interpreter.** `bpy` 5.0.x ships for CPython 3.11 only; 5.1 and later
  for 3.13. Plain `python3` is often neither. `scripts/setup_bpy.sh` finds one that works,
  installs `bpy` and Pillow into it, and prints the command prefix to use.
- **Cycles on the GPU when present, CPU in a GPU-less container**. EEVEE and Workbench do not raise without a
  GPU (still true) or `libEGL.so.1`: they abort the interpreter. Freestyle crashes headless too (its auto-created
  line set has no line style); draw wireframes with a Wireframe shader node instead.
- `import bpy` must come before `mathutils` and friends.
- Renders at 32 samples and 700 px per view take about a minute for six views on 4 cores. Keep
  review renders small; they are for looking, not for shipping.

## The blueprint pattern

One module per asset family, `BLUEPRINTS = {slug: builder}`; a builder takes the parsed spec entry
and returns parts. The registry refuses a slug the spec does not list. Part kinds that cover almost
everything: `box`, `cyl`, `cone`, `sphere`, `lathe` (revolve a profile: pots, hats, helmets),
`prism` (extrude an outline: blades, plaques), `tube` (sweep a section along a path: handles,
straps, chains), `loft` (skin a stack of rings: torsos, robes, shoes), `sweep` (a tube whose
section changes: limbs, tails). Paint bands restamp faces inside a box with another material, so
trim stays on the same shell.

## Rigging

- Name bones for the engine's humanoid standard, with Blender `.L`/`.R` suffixes; keep one
  explicit map from engine bone names to yours, shared by the forge and the engine importer, and
  test that they match.
- Bind pose: A-pose with the arms where the blueprint put them; the engine's importer enforces a
  T-pose for the avatar.
- Heat weighting, then rules per part: rigid props, parts limited to named bones, a skirt rule that
  hands weight to the thighs below the hip (without it a lifted knee goes through a robe).
- A thing that must come off later (a hat, a helmet, a lantern) gets its own rigid bone.

## Clips

- Author on one reference skeleton; retarget to each model the way the engine will (Humanoid), and
  review on the real model, not the reference.
- Gaits are parameters (speed, cycle, duty, stride, bob, lean, arm swing), solved with foot IK, so
  the stride matches the in-game speed and the foot-slide metric proves it.
- A clip that must play over another (casting while walking) is authored for an upper-body mask and
  reviewed both alone and over locomotion.
- Export animation-only FBX per family, re-import to check every take, and write a manifest the
  engine importer and its tests read (loop flags, events, lengths).

## Engine (Unity)

- An `AssetPostprocessor` owns every import setting by path: rig type, avatar bone map, clip
  names and loop flags (`OnPreprocessAnimation` over `defaultClipAnimations`), URP Lit materials
  from the baked maps, data textures (ORM, metallic-gloss, masks) imported linear.
- A Humanoid avatar needs the rest pose recorded on first import; record it in
  `OnPostprocessModel` and reimport once.
- Generate animator controllers and prefab installs from an Editor menu (`AnimatorController`,
  `BlendTree`, `AvatarMask`, `PrefabUtility.LoadPrefabContents`); never wire them by hand.
- First-person games: draw the local player's own body as shadows only.
- A cloud session without Unity cannot run any of this: say UNTESTED, hand over the menu item.

## Traps that already cost a day

- **bmesh handles and index order go stale** after an op reallocates; stamp each element (material
  index, bone id) the moment it is created.
- **Material indices clamp to the slot count.** Writing index 3 to a mesh with no slots silently
  becomes 0: attach materials before writing face indices, and assert the families after baking.
- **Bevel interpolates float attributes** across the mesh; keep per-face identity in integer face
  data (material slots, an int face layer), never a float attribute.
- **A clamped bevel still leaves slivers** on thin trim: `use_clamp_overlap` plus a
  dissolve-degenerate pass.
- **8-bit emission maps clamp at 1.0;** scale the glow back up in the shipping material (and use the
  same multiplier, as HDR, in the engine).
- **`Renderer.bounds` lies about skinned meshes** in Unity (padded import bounds); measure baked
  vertices (`BakeMesh(useScale: true)` through `localToWorldMatrix`) when deciding heights or feet.
- **Metals render too warm** in a warm review studio; judge silver and steel from the baked colour.
- **Validation passing proves nothing about the look.** Every one of these traps passed validation.
- **Docs drift when the roster changes.** A scale doc kept a retired enemy roster for weeks; a
  drift check in CI is the fix (stage 8).
