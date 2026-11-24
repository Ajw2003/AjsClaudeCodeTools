# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is merged (merge 9c9c79f): commands/review.md and scripts/review_plan.py; all seven verify.py parts passed on its final commit 4e94d17 (core 272, docs 167, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 3 (#620) is built on AjsAgent/review-command-step3 (worktree /home/user/wt-review-step3, final commit 1d979ba): seven new cases in checks/docs.py, each shown failing against a broken file; builder's docs run 174 passed. My seven-part verify run is writing to v-step3-final.txt in the scratchpad (a line per part, then DONE). Step 4 (#621) is not started.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Read v-step3-final.txt; if all seven parts show `all N checks passed` merge AjsAgent/review-command-step3 (expect a CHANGELOG.md conflict: keep both sides, remove only the marker lines, and commit the resolved file by hand before anything else). Then start step 4 (#621) in a worktree made by hand from this branch's HEAD: add review-loop.md to the mode-list check in checks/docs.py, update review-loop.md's mode lists, correct the review-command.md doc, write the Decisions entry (already written; check it), bump the plugin version, update Today. Then run the plan's seven acceptance tests, swap `in progress` for `needs review`, build the QA page. Ask aj at QA about the notice threshold (9 folders but 96 batches in this repo).

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
