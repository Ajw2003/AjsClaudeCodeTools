# art-pipeline

STATUS: v0.2. Offshoot of the `house-rules` plugin formula (one `run.sh` shim, one stdlib Python
file). Makes game art by code - concept, model, rig, animation - and never calls a model done
until someone has looked at it beside its concept. The skills (under
`plugins/art-pipeline/skills/`) carry the method; the hooks here carry the gate. Engine-agnostic
core; Unity (URP) is the first engine adapter.

## Install

    claude plugin marketplace add Ajw2003/AjsClaudeCodeTools
    claude plugin install art-pipeline@aj-house-rules

In a Unity project, add the package to `Packages/manifest.json` (the ref is `main` once merged; until
then `claude/modest-hawking-d4w2bv`):

    "com.aj.art-pipeline": "https://github.com/Ajw2003/AjsClaudeCodeTools.git?path=/claude-art-pipeline/unity#main"

and point the engine stage at the capture script in `.art-pipeline.json` at the repo root:

    {"engine": "unity",
     "engine_capture": "python <plugin>/skills/art-pipeline/scripts/unity_capture.py --project <abs project> --model Assets/Art/Generated/{slug}/{slug}.fbx --out docs/art/engine/{slug}"}

## The pieces

| Piece | Where | What |
|---|---|---|
| Stage ledger | `plugins/art-pipeline/scripts/art.py` | `new`, `next`, `record`, `skip --reason`, `advance`, `status`: one asset at a time through brief, concept, spec, model, rig, clips, engine |
| Forge | `plugins/art-pipeline/skills/art-pipeline/scripts/forge/` | spec JSON + blueprints -> validated FBX/GLB/.blend and the `.art.json` sidecar; humanoid rig, idle and walk ([forge/README.md](plugins/art-pipeline/skills/art-pipeline/scripts/forge/README.md)) |
| Review renders | `.../scripts/render_views.py`, `review_sheet.py` | Blender views (GPU when present) and the concept-beside-renders sheet; the sheet also takes a Unity capture folder |
| Unity adapter | `unity/` (UPM package) + `.../scripts/unity_capture.py` | URP importer from the sidecar, prefab/animator generator, batchmode capture beside a 1.80 m capsule ([unity/README.md](unity/README.md)) |

## The gate

| Event | Handler | Does |
|---|---|---|
| `SessionStart` | `start` | In a git repo that has model files, records HEAD and an empty seen-list in `<git-dir>/art-pipeline/<session>.json` (never committed) and tells Claude the rule. Fails loud. |
| `PostToolUse` (Read) | `seen` | Appends any `.png/.jpg/.jpeg/.webp` Claude opens to the ledger. Never blocks. |
| `Stop` | `gate` | Models changed this session (committed since start, modified, added, untracked; `*.fbx *.glb *.gltf *.blend *.obj`) each need a review record. Blocks until they have one. Fails open, loudly. |

A record is `<review_dir>/*.review.json` (default `docs/art/reviews`):
`{"model","sheet","verdict":"pass|fail|waived","seen" (>= 40 chars),"date"}`. It counts only if
the sheet PNG exists, is at least as new as the model, and was opened this session. `fail` blocks;
`waived` passes but is announced. Write one with
`python scripts/review.py record --model M --sheet S.png --verdict pass --seen "..."`;
`review.py status` shows what would pass.

Asset ledger: `scripts/art.py` keeps `docs/art/assets/<slug>.json` per asset (stages brief, concept,
spec, model, rig, clips, engine, done; rig/clips n/a for prop/set). Brief and concept need
`--approved-by-user`; the others need a Read-opened `--sheet` and `--seen`, and a pass needs
`min_looks` (default 2) records unless `--first-look-pass "<reason>"`. Skipping a gate needs
`art.py skip --reason`. At Stop, every ledger changed this session is checked (a pass naming an
unopened sheet blocks) and every skip and first-look-pass is listed with its reason. Extra config:
`asset_dir`, `min_looks`, `engine` (default unity), `engine_capture` (command, `{slug}`),
`stage_outputs` ({stage: [globs with {slug}]}). `review.py status` also prints the asset table.

Override per project with `.art-pipeline.json` at the repo root:
`{"model_globs": [...], "exclude": [...], "review_dir": "..."}`.

Doc-drift check: add `"doc_check": "<shell command>"` (run from the repo root, 60 s timeout) and
optionally `"doc_check_paths": [...]` (fnmatch on repo-relative paths, default
`["docs/**", "**/*.json"]`). At Stop it runs only when this session changed a model or a matching
path. Non-zero exit blocks with the last 20 lines of output; a timeout fails open with a
systemMessage; not configured is silent. It shares the loop guard (key `doc_check`) and shows in
`review.py status`.

Loop guard: the 3rd consecutive block for the same unmet set releases the stop with a loud
`UNREVIEWED models` systemMessage. Fail modes: start loud, seen never blocks, gate fails open
loudly.

## Off switch

`ART_PIPELINE=off` - the gate says it is off and does not check. `ART_PIPELINE_PYTHON` picks the
interpreter, `ART_PIPELINE_DEBUG=1` traces `run.sh`.

Verify: `python claude-art-pipeline/plugins/art-pipeline/scripts/verify.py`. Design notes:
[docs/offshoots-plan.md](../docs/offshoots-plan.md).
