# art-pipeline → a skill for any Unity project: what it would take

Date: 2026-10-07. Status: built on branch claude/modest-hawking-d4w2bv (issues #167-#171); proven once end to end, see docs/3-state/ProjectState.md section 3. Source: branch `claude/art-pipeline`
(PR Ajw2003/AjsClaudeCodeTools#166, issues #161–#164), read at `466c6cd`.

## Where it stands

It is already a plugin (`claude-art-pipeline/plugins/art-pipeline/`), not just notes:

| Piece | What it does | Portable today? |
|---|---|---|
| `skills/art-pipeline/SKILL.md` + `references/` | 8 stages (brief → concept → spec → model → rig → clips → engine → docs), a look-gate after each | Yes - loads by description in any project once the plugin is installed |
| `scripts/setup_bpy.sh` | finds/installs Blender-as-a-module | Yes - ran here: installed `bpy` 5.2.2 into Python 3.13 |
| `scripts/render_views.py`, `review_sheet.py` | ¾/front/side/wire renders + concept-beside-renders sheet | Mostly - **relative `--out` breaks on Windows** (see below) |
| Stop-hook gate (`hook.py`, `artlib.py`, `review.py`) | session can't end while a changed model has no fresh, opened, written review | Yes |
| The forge (blueprints, bake, export, validator, rig, clips) | builds the models and animations | **No - lives only in PlunderSpell's `Tools/ArtForge/`**; the skill only describes it |
| Unity side (importer, animator generator, driver) | stage 7 | **No - prose only; stage 7 ends in "UNTESTED, hand the user a menu item"** |

Blockers to install: PR #166 CI fails (`check_plugin_version_bump`: house-rules docs changed
without a version bump), and the branch is 17 commits behind `origin/main`.

## Verified on this machine (2026-10-07)

- `sh setup_bpy.sh` → `BPY_PYTHON=python3.13 (bpy 5.2.2 LTS)`.
- `render_views.py cone.glb --out views` → saved to `C:\views\` then failed
  `render did not write views\three_quarter.png`. Blender resolves a relative render path against
  the drive root on Windows. With an absolute `--out` all four views + `stats.json` rendered
  (62 tris, 1.2 m) in ~2 s. Fix: `os.path.abspath(args.out)`.
- Unity 6 is installed (`6000.0.51f1` … `6000.3.15f1` under `C:\Program Files\Unity\Hub\Editor`),
  so stage 7 does not have to be UNTESTED here.
- RTX 5070 present; the "Cycles CPU only" rule comes from the GPU-less cloud container and is
  slower than needed here.

## What's missing for "concept to in-game, on any Unity project, in a rigid loop"

1. **A shipped forge.** Every new project currently re-derives PlunderSpell's ArtForge from a
   prose description. Extract the generic part into the skill's `scripts/`: part kinds
   (box/cyl/cone/sphere/lathe/prism/tube/loft/sweep), bake to one texture set, FBX export with
   Unity axes, the validator, the humanoid figure/rig library, the gait + pose clip library.
   Projects keep only their blueprints and spec JSON.
2. **A Unity drop-in.** A small `Editor/` package the skill copies into `Assets/` (or a UPM git
   package): spec-driven `AssetPostprocessor`, animator/prefab generator, and an
   `ArtCapture.Capture` method run with `Unity.exe -batchmode -projectPath … -executeMethod`
   that opens a fixed test scene, spawns the prefab, renders fixed cameras to PNG. That PNG
   becomes the in-engine panel on the review sheet, so stage 7's LOOK is something Claude does,
   not something handed over. (`unity:unity-cli` can drive a running editor as the alternative.)
3. **The rigid structure as state, not prose.** Today the gate only checks "changed model has a
   review". Stage order is advice. Needed: one ledger per asset (`docs/art/assets/<slug>.json`:
   current stage, each gate's verdict + sheet + what was seen, iteration count) and a
   `art.py next <slug>` / `art.py advance <slug>` that refuses to move past a stage without its
   gate record (concept approved by user → spec matches sheet → model reviewed → rig posed →
   clips reviewed → in-engine capture reviewed). Gate extends to check the ledger, not just models.
   "Iterate" = minimum one fail→fix→re-look cycle recorded per stage before `pass`.
4. **Windows fixes.** Absolute paths in `render_views.py`; let it use GPU Cycles when present;
   `setup_bpy.sh` assumes POSIX names (works under Git Bash, untested in PowerShell).
5. **Ship it.** Rebase on main, bump the version the check wants, get #166 green, install.

## Decided (aj, 2026-10-07)

- **Engine-agnostic core, Unity first.** Ledger, forge, gate and review sheets know nothing about
  an engine. Stage 7 calls an engine adapter named in `.art-pipeline.json`
  (`"engine": "unity"`); Unity is the only adapter built now.
- **URP first.** The Unity importer builds URP Lit materials and the capture scene uses URP;
  Built-in/HDRP are not handled until asked for.
- **Unity side installs from git** as a UPM package kept in this repo, added to a project's
  `Packages/manifest.json` as
  `"com.aj.art-pipeline": "https://github.com/Ajw2003/AjsClaudeCodeTools.git?path=/claude-art-pipeline/unity#<tag>"`.
- **A user-approval gate can be skipped with a recorded reason.** `art.py advance <slug> --skip
  "<reason>"` writes verdict `skipped` plus the reason into the ledger; it never passes silently -
  `review.py status` and the Stop gate list every skip.

## Order of work (one child issue of #161 each)

1. (#167) Ship what exists: rebase `claude/art-pipeline` on main, the version bump CI wants, #166 green.
2. (#168) Windows fixes: absolute `--out`, GPU Cycles when present.
3. (#169) The per-asset ledger and `art.py next/advance`, gate reads it, skips recorded.
4. (#170) The forge extracted from PlunderSpell into the skill's `scripts/`, engine-free.
5. (#171) The Unity UPM package: URP importer, animator/prefab generator, batchmode capture feeding
   the review sheet.
