# The Honking Deep (eldritch goose boss)

A hero-tier boss built by the `art-pipeline` skill from a one-line prompt: a Canada goose gone feral
in a dead maple wood, styled toward Bloodborne, standing proud like a real goose (body traced off a
photo, necks upright, heads high). Three heads, each a gore-caked mask: wrinkled hide, bony brows in
a scowl over one sunken eye, cheeks split back from the beak and lined with teeth, a beak crowded
with broken, blood-rooted teeth, and dead bare maple branches torn out through the skull. Ragged
hackles down every neck, blood run down from the jaws; bare finger bones breaking out of the wings
and bare ribs through the flanks; a maple leaf branded into the breast above a matted bib of
blood-soaked feathers; mud up the legs. Soot, ash, grimy bone and dried blood, nothing glowing.
6.75 m to the crown's twig tips, 272,380 triangles against a 300,000 budget; one mesh, one
material reading three baked 4096 px textures (colour with ambient occlusion folded in, normal,
roughness); faces -Y, origin on the ground between the feet.

| File | What it is |
|---|---|
| `spec.json` | size, budget, materials (hex), build notes, and the design numbers everything is built from |
| `goose_design.py` | the design as pure Python: spec in, parts and mesh faces out (no Blender needed) |
| `draw_concept.py` | draws `concept.png`, front and side views with the reference human and palette, from those parts |
| `build_goose.py` | turns the parts into one Blender mesh, validates it, has `goose_texture.py` bake it, exports the model files |
| `goose_texture.py` | procedural surfaces per material (feather barbs and shafts, scalloped plumage, hide, bark, bone, scutes, blood, mud, grit, the brand decal) baked into one texture set |
| `textures/` | the baked colour, normal and roughness images (4096 px JPEG) the model reads |
| `goose.glb` / `goose.fbx` / `goose.blend` | the model |
| `views/` | the four review renders and `stats.json` |

Review sheet: `docs/art/reviews/goose-review.png`; recorded verdicts beside it.

Rebuild and re-review, from the repo root (needs `python3.11` with `bpy`, from
`claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/setup_bpy.sh`):

```bash
python3 art/goose/draw_concept.py
python3.11 art/goose/build_goose.py
python3.11 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/render_views.py art/goose/goose.glb --out art/goose/views --res 900 --background "#EDE6D6"
python3 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/review_sheet.py --concept art/goose/concept.png --views art/goose/views --title "The Honking Deep (eldritch goose boss)" --out docs/art/reviews/goose-review.png
```

The full build takes about 10 minutes on this cloud sandbox's 4 CPU cores (Cycles on CPU);
`GOOSE_TEXTURE_PX=1024` before the build command bakes small for a quick look in under a minute.

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
Passes 12-19 moved the surface detail into baked textures (the brand, feather barbs, hide, bark,
blood, grime), cut the last maple leaves (they looked alive), re-traced the body off a photo of a
standing goose (pass 13: the body tilts down to the tail, the chest no longer bulges), blended the
main neck into the chest and stood the goose up proud, made the breast bib hang like matted
feathers rather than a row of teeth (pass 15), gave the heads hide, brows, split cheeks, crowded
bloody teeth and torn skin round the crown roots, lumped every tube so nothing reads as machined,
added hackles, mud and occlusion, and set per-colour render gains so the lit render reaches the
concept sheet's tones (measured breast 82 vs the concept's 102, up from 64).

Known gaps: the lit render is still a little lighter on the black necks (31 vs 18) and darker on the
breast (82 vs 102) than the concept's flat colours; the brand and blood are baked at 4096 px over the
whole model, so they soften up close; no rig, no animation clips, not yet imported into an engine.
