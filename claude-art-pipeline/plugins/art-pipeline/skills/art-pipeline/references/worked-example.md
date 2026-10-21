# Worked example: Ajw2003/PlunderSpell

A four-player co-op heist in Unity 6. Everything below was built by code in Blender-as-a-module and
reviewed by eye, 2026-09 to 2026-10. Copy the shape, not the content. Paths are in that repo;
`docs/art/WORKFLOW.md` there is the project's own copy of this pipeline.

## What it produced

| Stage | Output |
|---|---|
| Brief | `docs/art/BRIEF.md`: register (the household, not monsters), scale (1.80 m human, five zone heights, 12 m cell), six pigments with reserved uses, budgets, sheet conventions |
| Scale | `docs/4-systems/scale.md`: the standard human, room and archway heights, the full enemy roster with heights and zones |
| Concept | `docs/art/concept/<age>/<slug>.svg` + `.png` for 48 assets (4 Ages × 3 structures, 4 enemies, 5 items); the wizard's proposal plates and page on branch `claude/wizard-character-plan` |
| Spec | `docs/art/data/<age>.json` (+ `lair.json` for the player), validated by `Tools/ArtBible/build_art_bible.py`, which also writes the per-Age handoff sheets and an illustrated mood board |
| Model | `Tools/ArtForge/` (on top of `Tools/EnemyForge/`): 20 items, 16 rigged enemies, the wizard; outputs `Assets/Models/ArtBible/<Kind>/<Age>/<Name>/` |
| Review | `docs/art/models/<age>/<slug>.png`: concept left, six views right (¾, front beside the reference human, side, posed, posed front, wireframe) |
| Clips | `Tools/ArtForge/anim_forge/`, `anim.py` (enemies), `anim_player.py` (the wizard); `anim_spec.json` is the clip taxonomy; FBX in `Assets/Models/ArtBible/Animations/`; sheets and MP4s in `docs/art/anim/` |
| Engine | `ArtBibleModelImporter.cs` (import by path), `ArtBibleEnemyForge.cs` (prefabs and roster), `WizardPlayerSetup.cs` (animator + prefab install), `WizardAnimationDriver.cs` (parameters only) |
| Docs agree | `Tools/docs/check_art_docs.py` + `check_doc_links.py`, run by `.github/workflows/docs.yml` |

## Commands, as run there

```bash
pip install bpy==5.0.1 pillow                         # with python3.11
python3 Tools/ArtBible/build_art_bible.py --only high # validate a spec
NODE_PATH="$(npm root -g)" node Tools/ArtBible/render_png.cjs high   # SVG -> PNG
python3.11 Tools/ArtForge/build.py enemies --age high --only lantern-warden
python3.11 Tools/ArtForge/render.py enemies --age high --only lantern-warden
python3.11 Tools/ArtForge/build.py players            # the wizard
python3.11 Tools/ArtForge/anim.py build && python3.11 Tools/ArtForge/anim.py review
python3.11 Tools/ArtForge/anim_player.py build && python3.11 Tools/ArtForge/anim_player.py review
python3 Tools/docs/check_art_docs.py
```

## How the work was split

- Concept: four workers, one per Age, each with a saved brief (`Tools/ArtBible/worker_brief.md`)
  and only its own Age's paths. All four were cut off by a usage limit at once; an autosave
  (`Tools/autosave.sh`) meant nothing was lost, and `docs/art/HANDOFF.md` is the resume procedure.
- Models: one worker per Age (`Tools/ArtForge/enemy_worker_brief.md`), two reference blueprints
  first to set the bar.
- The wizard: one builder for the model, one for the clips, the coordinator for the engine side.

## Lessons it paid for

- Two reference assets (a humanoid and a quadruped) built and reviewed to a high bar before
  fanning out saved every later worker from guessing.
- A design that is the owner's (the player's look, a death that contradicts an approved plan) went
  back to the owner as a question; craft defaults did not.
- The player is 1.80 m to the crown with the hat extra, so the collider and the room fit did not
  change.
- One material slot means per-player colour needs a baked dye mask (white where dyed), imported
  linear.
