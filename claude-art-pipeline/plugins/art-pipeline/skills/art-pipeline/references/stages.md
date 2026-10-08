# The stages, in full

Paths below are the defaults; a project that already has its own layout keeps it and says so in
its brief. Every stage's outputs are committed, sheets and renders included: they are the record of
what was looked at.

## 0. Protect the work

Long Blender runs and multi-worker batches get cut off (usage limits, a reclaimed container).
Commit on your own branch after every asset, or run an autosave that commits and pushes only the
paths this run writes, every few minutes. Never a broad `git add -A`: another worker may be writing
elsewhere in the same checkout.

## 1. Brief and style bible

Before anything is drawn. Copy `style-bible-template.md` to `docs/art/BRIEF.md` and fill it in
from the project's pitch, mood board and scale doc. If the project has no scale doc, write one
first: one standard figure (a 1.80 m human is a good default) that every room, door, prop and
creature is measured against.

**Gate:** the user approves the brief. Register, palette and scale are theirs.

## 2. Concept

One sheet per asset, drawn by code so it can be regenerated:

- SVG from a shared sheet template (frame, grid, ground line, title block, palette strip), rendered
  to PNG with headless Chromium (Playwright `page.screenshot` of the SVG at 2×); or Pillow plates.
- Characters: front and side orthographic views at one scale, the reference human beside them, a
  metre ladder, callouts naming parts and materials. Props: a hero ¾ view, front and side, a scale
  bar, grab points. Set pieces: elevation or section plus a plan on the grid cell.
- A palette strip of the asset's own materials, hex labelled.

When the design is the user's to choose (a player character, a new faction), draw the options as
plates and set them side by side on a proposal page (an HTML artifact). Record the choice in a plan
and a dated decision entry, with the rejected options, so nobody proposes them again.

**Gate:** open every PNG. On scale against the ladder and the human; no label overlapping a drawing
or another label; colours only from the entry's materials; every number on the sheet equals the
spec. Fix the generator, never the SVG by hand; re-render; look again.

## 3. Spec

One structured entry per asset (JSON is simplest), the single source the model, the engine and the
docs are generated from: slug, name, height or W×D×H, triangle and texture budget, materials
(name, hex, roughness and wear notes), build bullets with real sizes ("Hat: cone 0.55 m tall,
brim 0.40 m dia, tip bends back 30°"), and for characters the rig, the clip list and anything
detachable. A validator script checks counts, required fields and scale rules, and refuses to write
anything until the whole set passes.

**Gate:** the sheet and the JSON agree. A worker who writes the spec after drawing can contradict
the drawing.

## 4. Model

A blueprint per asset, in code: a list of parts (lathe, loft, sweep, tube, prism, box…) each with
a material family and, for rigged assets, a bone. The forge builds the mesh, bevels, unwraps, bakes
one texture set, and exports FBX (engine axes), glTF and `.blend`. A validator checks: closed and
manifold, consistent winding, UVs in 0–1, one material slot, identity transforms, grounded, under
the triangle budget, the height or bbox within tolerance of the spec, and (rigged) every vertex
weighted, at most 4 influences, weights summing to 1.

Then the review sheet: the concept on the left; three-quarter, front (beside the reference human),
side and wireframe renders on the right; a caption with triangles against budget, size against
spec, bones. `scripts/render_views.py` and `scripts/review_sheet.py` make one for any model when
the project has no renderer of its own.

**Gate:** open the sheet. Silhouette and proportion against the concept; colours; key details
present; the caption's numbers. At least one improvement pass. A real conflict between the spec's
size line and its build notes is recorded as an override with the reason; the model is never
shrunk to pass.

## 5. Rig and pose

A figure library gives bones the engine's standard rig expects (Unity Humanoid names with `.L`/`.R`
suffixes), heat weighting with per-part rules (rigid props, a skirt that hands weight to the thighs,
parts limited to named bones), and extra bones for anything that must come off or swing (a hat, a
lantern ring). The review sheet adds a posed three-quarter and front view: an arm raised, the head
turned, a knee lifted.

**Gate:** the posed views bend without tearing, nothing passes through the body, props follow the
hands.

## 6. Clips

Keyframed by code on one shared reference skeleton, so one clip retargets to every humanoid:

- named poses (bone rotations), clips as timed pose keys with easing, anticipation and overshoot;
- locomotion from a parametric gait (stride, cadence, bob) matched to the in-game speed, so feet do
  not slide; in place, no root motion, when the engine moves the body;
- foot IK to the floor while grounded; events (footstep, hit, release) at normalized times;
- export per family (base, weapon, signature) as animation-only FBX; re-import to verify every take
  and frame count; write a manifest with loop flags, events and metrics.

Review per clip: 8 stills on the actual target model, a foot-contact trace for locomotion, an MP4.

**Gate:** feet do not slide (metric under 1 cm), nothing below the floor, the pose reads as the
action at a glance, and a one-shot ends where the next state expects it (a death ends lying still).

## 7. Engine

Everything set in code, nothing in the Inspector:

- an import postprocessor: rig type and bone map by path, loop flags per clip, materials built from
  the baked maps, data textures imported linear;
- an editor menu that generates the animator (blend trees by speed, layers with masks) and installs
  the model on the prefab;
- a runtime driver that only sets animator parameters, reading what the body is doing; on a
  networked game, anything the movement does not show (crouch, cast) is synced by the owner;
- tests: classification, loop flags against the manifest, driver parameters from inputs.

**Gate:** a capture in the engine. If this machine cannot run the engine, the work is labelled
UNTESTED and the user gets the exact menu item and what they should see.

## 8. Docs agree, then commit

Update the project's docs in the tier that changed (state, today, the system doc for the asset
family, the scale doc's roster). Then run the project's doc-drift check: a small script that
compares the docs with the data and code (every asset in the spec appears in the roster doc at the
same size; every roster entry still exists; every path a doc names exists) and fails on any
difference. If the project has none, write one; wire it into CI. Docs that describe art drift the
moment a roster changes.

Rebuild the batch twice (the second run meets the state the first left), commit every output,
push.
