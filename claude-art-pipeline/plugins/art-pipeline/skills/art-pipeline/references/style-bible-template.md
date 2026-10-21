# Style bible template

Copy to `docs/art/BRIEF.md` and fill in every section before anything is drawn. Each line should be
checkable against a sheet or a model: a colour with a hex, a size in metres, a budget in triangles.
Write "none" rather than deleting a section.

---

# <Project> art brief

Source of truth for the look: <pitch doc, mood board>. Source of truth for sizes: <scale doc>.

## What gets made

| Kind | Count | Notes |
|---|---|---|
| Characters (players) | | one shared body? per-player variation? |
| Creatures / enemies | | roles: e.g. patrol, ranged, heavy, special |
| Props (pick-ups, loot) | | the gameplay data each maps to |
| Set pieces / modules | | the grid cell they fit |

## The register

One paragraph: what world this is and what it is not. Who the enemies are (people? monsters?),
what never appears. The rule a designer uses to reject an idea.

## Scale

- Standard figure: <height> m, eyes <m>, body radius <m>. Every size is stated against it.
- Room/zone clear heights, door and archway sizes, the grid cell.
- No character taller than the shortest space it must move through.
- Models stand on their origin (z = 0), centred, facing <axis> (Blender −Y → Unity +Z is the
  default the scripts assume).

## Look

- Rendering style (stylised / painterly / realistic), and the one sentence that settles arguments
  ("the silhouette reads at ten paces in the dark before any face does").
- Surfaces: how wear, dirt and edge highlights are placed.
- Palette: named pigments with hex and **what each is reserved for** (e.g. gold only for value,
  violet only for magic). A pigment rule a validator can check by name and hex distance.
- Things that must never appear.

## Budgets

| Kind | Triangles (LOD0) | Texture set | LODs |
|---|---|---|---|
| | | | |

## Rig and animation

- Skeleton standard (Unity Humanoid, Generic for quadrupeds, …) and bone naming.
- Root motion or in place; who moves the body (physics, NavMesh, character controller).
- The movement speeds clips must match (walk, run, crouch), in m/s, from the code.
- Clip list per kind, with lengths and events (footstep, hit, release).
- What happens on death (clip, ragdoll, vanish) — decided by the owner, recorded.

## Concept sheet conventions

- Canvas size, background, grid, ground line, fonts for titles and labels.
- Characters: views, reference figure, ladder, callouts. Props: hero view, scale bar, grab points.
  Set pieces: elevation, plan, sockets.
- Palette strip of the asset's own materials.

## Where it goes

| Path | What |
|---|---|
| `docs/art/BRIEF.md` | this brief |
| `docs/art/data/*.json` | the spec, the single source |
| `docs/art/concept/` | concept sheets (source and PNG) |
| `docs/art/models/` | model review sheets |
| `docs/art/anim/` | clip review sheets and MP4s |
| `docs/art/reviews/` | review records the gate reads |
| `<models folder>` | FBX, glTF, .blend, textures |
| `Tools/<Forge>/` | the generators |
