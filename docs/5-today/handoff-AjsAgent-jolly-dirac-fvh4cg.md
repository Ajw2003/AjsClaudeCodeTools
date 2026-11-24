# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is with a builder in /home/user/wt-review-step2 (branch AjsAgent/review-command-step2); its report is not read yet. Steps 3 and 4 are not started. Measured for the sweep notice: 10 markdown files took 71.3 seconds and 43,991 tokens (7.1 seconds and 4,400 tokens per file), so a batch is at most 8 files. Deviation D1 (docs/qa/review-command/ledger.md): a small scripts/review_plan.py is added beyond the plan.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Read the step 2 builder's report and its quoted runs, run the verify.py parts myself (core, docs, then the others in the background), merge `AjsAgent/review-command-step2` if they pass, then start step 3 (#620, verify.py cases) in a new worktree made by hand with `git worktree add` from this branch's HEAD. Then step 4. When all four are built and the acceptance tests are run, swap `in progress` for `needs review` on every issue and build the QA page.

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
