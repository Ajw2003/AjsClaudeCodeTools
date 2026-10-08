# com.aj.art-pipeline (Unity adapter)

Editor-only UPM package; URP 17.3 (Unity 6000.3). Install in a project's `Packages/manifest.json`:

    "com.aj.art-pipeline": "https://github.com/Ajw2003/AjsClaudeCodeTools.git?path=/claude-art-pipeline/unity#<ref>"

(or `file:<abs path to claude-art-pipeline/unity>` for local work).

## Sidecar

Models under `Assets/Art/Generated/` (override: EditorPrefs `AjArtPipeline.Root`) are handled only when
`<Model>.art.json` sits beside the FBX:

    {"kind":"character","rig":"humanoid","clips":[{"name":"idle","loop":true},{"name":"walk","loop":true}],"emission_strength":1}

`rig` is `humanoid | generic | none`. Textures `<Model>_BaseMap/_MetallicGloss/_Normal/_Emission.png`
(beside the FBX or in `Textures/`) become a URP Lit material; `_ORM/_MetallicGloss/_Metallic/_Roughness/_Normal`
import linear. Humanoid maps Hips/Spine/Chest/Neck/Head/Shoulder|UpperArm|LowerArm|Hand .L/.R and
UpperLeg|LowerLeg|Foot .L/.R, skipping bones the model lacks; the rest pose is recorded on first import.

## Menu (Tools/Art Pipeline) and batch

- Ensure URP: `ArtPipelineSetup.EnsureURP`
- Make Prefab From Selected Model: `Assets/Art/Prefabs/<Name>.prefab` (+ `.controller`, Speed blend tree idle/walk, for humanoids).
  Batch: `-executeMethod AjArtPipeline.ArtPipelineBuild.MakePrefabBatch -artModel Assets/..fbx`
- Capture: `-executeMethod AjArtPipeline.ArtPipelineCapture.Run -artModel Assets/..fbx -artOut <abs dir>` writes
  three_quarter/front/side (+walk for humanoids) PNGs and `stats.json`; normally driven by
  `skills/art-pipeline/scripts/unity_capture.py`.
