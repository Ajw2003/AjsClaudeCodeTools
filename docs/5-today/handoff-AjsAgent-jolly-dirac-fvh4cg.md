# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is merged (merge 9c9c79f): commands/review.md and scripts/review_plan.py; all seven verify.py parts passed on its final commit 4e94d17 (core 272, docs 167, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 3 (#620) is merged (merge 27233ed); all seven verify.py parts pass on it (docs 174, core 272, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 4 (#621, docs and plugin 2.94.0) is merged (merge 5fcddd6); all seven verify.py parts pass on it. All four build steps are done. Acceptance tests are running, outputs in docs/qa/review-command/round-1/: test 1 (mode choice) and 2 (eight modes) pass; test 4's real sweep (14 one-file folders plus a root file, fixture path in fixture-path.txt there, 15 batches, one reviewer at a time) is in progress: batch 1 (d01) was spawned, the rest are not. Tests 3, 5, 6, 7 are not run.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Finish the sweep: spawn one codebase-mode reviewer per remaining batch (d02 to d14, then `root files`), one at a time, same prompt as batch 1 (fixture root in round-1/fixture-path.txt), recording each batch's seconds and tokens from the harness. Then merge findings ordered [high], [medium], [low], then by file, save report.md in round-1/, and compare real time and tokens with the notice's estimate. Then tests 3 (a real code-mode review of scripts/review_plan.py with the report saved by the main session), 5 (no argument is diff mode; style with no stated style stops; image with no criteria uses hierarchy, contrast, alignment, consistency) and 6 and 7 (visual loop cases pass in verify; ranking). Save outputs under round-1/, write the verdict, then swap `in progress` for `needs review` on #617 to #621 and build the QA page with make_page.py QA mode. Ask aj at QA about the notice threshold (9 folders but 96 batches in this repo).

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
