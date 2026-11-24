# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built on branch `AjsAgent/review-command-step1` (commit 8446569, worktree /home/user/wt-review-step1), not merged. Diff read and matches the brief. verify.py parts core, docs and writing pass (272, 167, 24); make_page and design_loop were still running in the background. Steps 2 to 4 are not started.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Read the two background verify results (files v-make_page.txt and v-design_loop.txt in the scratchpad); if both pass, merge `AjsAgent/review-command-step1` into this branch, then start the step 2 builder (the command, #619). Then step 3, then step 4. When all four are built and acceptance tests are run, swap `in progress` for `needs review` on every issue and build the QA page.

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
