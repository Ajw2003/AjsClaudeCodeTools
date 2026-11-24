# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is merged (merge 9c9c79f): commands/review.md and scripts/review_plan.py; all seven verify.py parts passed on its final commit 4e94d17 (core 272, docs 167, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 3 (#620) is merged (merge 27233ed); all seven verify.py parts pass on it (docs 174, core 272, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 4 (#621, docs and version 2.94.0) is with a builder in /home/user/wt-review-step4 (branch AjsAgent/review-command-step4); its report is not read yet.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Read the step 4 builder's report. Run docref.py check, docs_drift.py, plain_docs_check.py and all seven verify.py parts in the worktree (background, one after another, new output file, read the `all N checks passed` line of each). Merge AjsAgent/review-command-step4 (expect a CHANGELOG.md conflict: keep both sides in one command, commit the resolved file, confirm no markers in HEAD). Then run the plan's seven acceptance tests (they include real reviewer spawns for a mode run and a 14-folder sweep on a small test folder), save outputs under docs/qa/review-command/, swap `in progress` for `needs review` on #617 to #621, and build the QA page with make_page.py QA mode. Ask aj at QA about the notice threshold (9 folders but 96 batches in this repo).

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
