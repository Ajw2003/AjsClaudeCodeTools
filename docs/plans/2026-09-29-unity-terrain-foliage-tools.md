# Unity terrain + foliage: free tools, gaps, and a build scope

Status: research only. Nothing here was run in Unity. The sandbox has no `unity` CLI and no
`unity:*` skills, and `docs.unity3d.com` is blocked by the egress proxy, so Unity's own Terrain
Tools page was **not** read; its feature list below comes from search snippets plus general
knowledge and is marked as such. Repo facts come from the GitHub READMEs fetched on 2026-09-29.
Maintenance state and Unity-6/URP compatibility of every community repo are **unchecked**.

## What Unreal gives you (the target)

| Area | Unreal feature |
|---|---|
| Landscape | Sculpt / smooth / flatten / ramp / erosion / noise brushes, heightmap import/export |
| Landscape | Non-destructive **edit layers** (stack, blend, reorder, toggle) |
| Landscape | Weight-painted material layers via a layer-blend material node |
| Foliage | Foliage Type asset: density, scale min/max (per axis or uniform), Z offset, random yaw/pitch, align-to-normal, slope min/max, height min/max, cull distance, LODs |
| Foliage | Paint / erase / select / fill / reapply tools, per-layer filter ("only on grass layer") |
| Foliage | Procedural Foliage Volume: seeded spawning simulation over an area |

## Free options that exist for Unity

### Terrain (sculpt, height, layers)

| Tool | Covers | Gaps |
|---|---|---|
| Unity built-in Terrain | Raise/lower, smooth, paint texture layers, holes, trees, details | Basic brushes only, no edit layers |
| Unity **Terrain Tools** package (`com.unity.terrain-tools`, free, Package Manager) | Erosion, more sculpt brushes, brush mask filters, Terrain Toolbox (heightmap/splatmap import-export, batch tiles), Stamp Terrain (from search snippets, unverified) | No non-destructive edit-layer stack |
| [Terrain Tools 3 Mixer](https://forum.unity.com/threads/free-terrain-tools-3-mixer-open-source-github.1143332) | Stack/order tools by drag and drop | Built for Terrain Tools v3; v4 fit unchecked |
| [Path Paint Tool](https://github.com/Roland09/PathPaintTool) | Paths, roads, river beds on Terrain | Add-on only |
| [UnityRuntimeTerrain](https://github.com/JohannHotzel/UnityRuntimeTerrain) | Runtime sculpt/dig, layer painting with falloff, layer re-normalisation | Runtime focus, not an editor workflow |
| [Terra](https://github.com/brooteskan/Terra) | Layer-based, World-Creator-style landforms and masks | README says early WIP |

### Foliage (paint, scatter, render)

| Tool | Covers | Gaps |
|---|---|---|
| [santorr/UnityFoliageTool](https://github.com/santorr/UnityFoliageTool) | Closest to Unreal's foliage editor: GPU instancing, paint/erase/fill, density, world cells, wind shader | README: no LOD, no frustum culling, WIP; no licence stated (do not copy code without one) |
| [MoonbowPony/FoliageTool](https://github.com/MoonbowPony/FoliageTool) (MIT) | Biome rule-sets, slope/height/texture filters, Perlin noise, up to 64 layered brushes, Splines | Says "experimental, not for production"; bakes into Terrain details, not a runtime instancer |
| [Unity-Grass-Instancer](https://github.com/MangoButtermilch/Unity-Grass-Instancer) | GPU-instanced grass with frustum/occlusion culling examples | Sample project, not a painter |
| GPUPlantPainter, Foliage Renderer (see [search hit](https://discussions.unity.com/t/the-gpuplantpainter/935591)) | Painting on any mesh; indirect-instanced Terrain trees/details | Licence and price unchecked |

Paid tools people compare against (GPU Instancer, Vegetation Studio, MicroVerse) are out of scope
because the ask is free.

## Verdict

**No single free tool matches the Unreal pipeline.** Nearest free stack today:

1. Unity Terrain + Terrain Tools 4 for sculpt, heightmaps, erosion, stamps, texture layers.
2. Terrain layers with a height-blend shader for materials.
3. A foliage painter: fork or wrap MoonbowPony/FoliageTool (MIT) for rules, or use
   santorr/UnityFoliageTool as a reference only (no licence).

What is **missing in every free option**: non-destructive terrain edit layers, and a foliage type
asset with full min/max randomisation plus per-terrain-layer filtering, rendered fast at scale.

## Build scope (if you build the missing parts)

Sizes are rough estimates for one developer, not measured.

### Phase 0: decide the base (0.5 day)
Keep Unity `Terrain` as the data store. Rewriting terrain is the expensive path and buys little.

### Phase 1: Foliage Type + painter (about 1-2 weeks) — the core ask
- `FoliageType` ScriptableObject: mesh + materials, density per unit area, uniform-or-per-axis
  **scale min/max**, height (Y) offset min/max, random yaw / pitch / roll ranges, align-to-normal
  0-1, slope min/max, altitude min/max, allowed terrain layers with weight threshold, cull
  distance, shadow flags.
- Editor tool (`EditorTool` + Scene-view overlay): paint, erase, fill-area, re-apply, brush
  radius/strength/falloff, per-type toggles.
- Storage: instances in grid cells (for example 64 m) as a `ScriptableObject` or scene sidecar, so
  huge scenes stream and diff sanely.
- Seeded randomness so re-apply is reproducible.

### Phase 2: Rendering (about 1-2 weeks)
- `Graphics.RenderMeshIndirect` or `BatchRendererGroup` per cell, compute-shader frustum + distance
  culling, LOD by distance, wind via vertex shader. Must work with URP (say which pipeline you use).
- Fallback path: bake grass to Unity Terrain details for platforms without compute.

### Phase 3: Procedural spawn volumes (about 1 week)
- Volume component, Poisson-disk sampling, rules (slope, height, layer, noise mask, min spacing per
  type, exclusion from other types). Later: Unreal-style seeded "age and shade" simulation.

### Phase 4: Terrain edit layers (about 2-3 weeks) — the hard one
- Layer stack of heightmap render textures with blend modes (add, subtract, max, set), masks, and
  reorder/toggle; compute shader flattens the stack into `TerrainData` heights on change.
- Brushes write into the active layer instead of the terrain. Hole and splat layers follow the
  same pattern later.

### Phase 5: Material rules (about 1 week)
- Height-blend terrain shader (Shader Graph or hand-written), auto-material rules by slope/altitude
  that write splatmap weights, so foliage can filter on the result.

### Suggested order
Phase 1 then 2 gives you the foliage workflow you described in about a month, on top of free
Terrain Tools. Phases 4-5 are optional polish; start with Terrain Tools until you actually hit the
"can't undo an old sculpt" wall.

## Open questions for the next step
1. Render pipeline: built-in, URP or HDRP? Unity version?
2. Target: PC only, or mobile/console (decides compute-shader culling)?
3. Scene scale: single terrain or tiled world?
4. Grass-blade scale (millions of instances) or mostly meshes (trees, rocks, bushes)?
