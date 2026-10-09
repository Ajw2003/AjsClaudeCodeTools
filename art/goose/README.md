# The Honking Deep (eldritch goose boss)

A hero-tier boss built by the `art-pipeline` skill from a one-line prompt: a Canada goose gone feral
in a dead maple wood, styled toward Bloodborne. Three heads, each crowned with dead bare maple
branches spread like antlers; one small sunken eye a side; bare finger bones breaking out of its
wings and bare ribs through its flanks; rotting maple leaves matted into its plumage; a maple leaf
branded into its breast above a skirt of blood-soaked feathers. Soot, ash, grimy bone, dried blood
and rotting maple red, nothing glowing. 6.52 m to the crown's twig tips, 161,844 triangles against a
200,000 budget; one mesh, 14 materials, faces -Y, origin on the ground between the feet.

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
Passes 7-11 (dead maple) replaced the quill crests with dead maple crowns (enlarged after pass 7
read as spindly), scattered rotting leaves (made fewer and larger after pass 7's read as red
flecks), removed the breast maw and the blood stain, and put a maple-leaf brand bent to the breast
in their place, with blood-soaked breast feathers below it.

Known gaps: colours are flat per-face materials, not a baked texture, so there is no feather, bark
or skin detail below the geometry; flat leaves on a curved back can sit a centimetre or two proud at
their edges; no rig, no animation clips, not yet imported into an engine.
