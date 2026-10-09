# The Honking Deep (eldritch goose boss)

A hero-tier boss built by the `art-pipeline` skill from a one-line prompt: a 5.1 m Canada goose
with three heads, a toothed mouth on its breast, bare finger bones breaking out of its wings and
bare ribs through its flanks, styled toward Bloodborne: soot, ash, grimy bone and dried blood, one
small sunken eye a side per head, nothing glowing. 124,068 triangles against a 200,000 budget; one
mesh, 12 materials, faces -Y, origin on the ground between the feet.

| File | What it is |
|---|---|
| `spec.json` | size, budget, materials (hex), build notes, and the design numbers everything is built from |
| `goose_design.py` | the design as pure Python: spec in, parts and mesh faces out (no Blender needed) |
| `draw_concept.py` | draws `concept.png`, front and side views with the reference human and palette, from those parts |
| `build_goose.py` | turns the parts into one Blender mesh, validates it, exports the model files |
| `goose.glb` / `goose.fbx` / `goose.blend` | the model |
| `views/` | the four review renders and `stats.json` |

Review sheet: `docs/art/reviews/goose-review.png`; recorded verdicts beside it.

Rebuild and re-review, from the repo root (needs `python3.11` with `bpy`, from
`claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/setup_bpy.sh`):

```bash
python3 art/goose/draw_concept.py
python3.11 art/goose/build_goose.py
python3.11 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/render_views.py art/goose/goose.glb --out art/goose/views
python3 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/review_sheet.py --concept art/goose/concept.png --views art/goose/views --title "The Honking Deep (eldritch goose boss)" --out docs/art/reviews/goose-review.png
```

`build_goose.py` refuses to export if the model is over budget, more than 0.15 m off the spec
height, below the ground, has a part that is not a closed shell, or loses a material.

What the review passes changed: pass 1 had barcode-like flank bars, washed-out and over-crowded
eyes, tentacles standing straight like extra legs, a needle of a tail and square feather tips;
pass 2 and 3 fixed those, and the validator caught a tentacle dipping 3 cm below the floor.
Passes 4-6 (the Bloodborne restyle) removed the 64 glowing eyes and the six tentacles, darkened the
palette, added ribs and rattier feathers, and turned blood stripes that read as tribal paint
(pass 5) into a ragged stain round the maw.

Known gaps: the blood stain's edge is blocky because paint is per face; the concept sheet draws
the body as one flat circle per ring, so its front view paints the whole breast disc red where the
model has only the stain; colours are flat per-face materials, not a baked texture, so there is no feather or skin detail below the geometry;
no rig, no animation clips, not yet imported into an engine.
