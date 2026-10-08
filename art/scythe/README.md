# Reaper scythe

A 1.80 m prop built by the `art-pipeline` skill from a reference image (`concept.jpg`).

| File | What it is |
|---|---|
| `concept.jpg` | the reference image, used as the concept sheet |
| `spec.json` | size, triangle budget, materials (hex), build notes |
| `build_scythe.py` | the blueprint: rebuilds every model file below from the spec |
| `scythe.glb` / `scythe.fbx` / `scythe.blend` | the model (one mesh, 5 materials, 5372 tris, faces -Y) |
| `views/` | the four review renders and `stats.json` |

Review sheet: `docs/art/reviews/scythe-review.png`; recorded verdicts beside it.

Rebuild and re-review, from the repo root (needs `python3.11` with `bpy`, from
`claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/setup_bpy.sh`):

```bash
python3.11 art/scythe/build_scythe.py
python3.11 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/render_views.py art/scythe/scythe.glb --out art/scythe/views
python3.11 claude-art-pipeline/plugins/art-pipeline/skills/art-pipeline/scripts/review_sheet.py --concept art/scythe/concept.jpg --views art/scythe/views --title "Reaper scythe" --out docs/art/reviews/scythe-review.png
```

Known gaps (pass 2): the shaft wanders smoothly where the concept has two sharp elbows and a
hooked butt; colours are flat materials, not a baked texture, so the concept's pitting is absent.
