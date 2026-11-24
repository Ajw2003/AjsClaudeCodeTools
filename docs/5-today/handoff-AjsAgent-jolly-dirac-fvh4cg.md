# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is merged (merge 9c9c79f): commands/review.md and scripts/review_plan.py; all seven verify.py parts passed on its final commit 4e94d17 (core 272, docs 167, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 3 (#620) is merged (merge 27233ed); all seven verify.py parts pass on it (docs 174, core 272, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 4 (#621) is merged (5fcddd6), plugin 2.94.0; all seven verify.py parts pass on it. Acceptance tests 1, 2 and 4 are saved in docs/qa/review-command/round-1/; the real sweep (15 batches, all no findings) used 88.9 s and 203,394 tokens against a notice estimate of 66,000 tokens, so deviation D2 was logged and a builder is fixing the estimate on branch AjsAgent/review-command-fix-estimate (worktree /home/user/wt-review-step5; rule: 10,000 tokens per batch plus 3,400 per file; plugin 2.94.1). Test 3 is done: a code-mode review of scripts/review_plan.py found 17 problems (2 high, 7 medium, 8 low), report saved in docs/qa/review-review-plan-2026-11-24/report.md, four reproduced by me. Tests 5, 6, 7 are not run.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

The review command is built, fixed and open as pull request 623 (plugin 2.94.1). All seven verify parts pass (1,602 checks) and acceptance tests 1 to 7 pass; the image-mode test was re-run with the reviewer told to read the repo's rules file, because the sandbox's installed plugin is 2.93.0 (docs/qa/review-command/round-2/results.md). The estimate-fix branch from the earlier handoff was never pushed, so its fix (10,000 tokens per batch plus 3,400 per file) and the D3 fixes were redone on this branch. What remains: aj's QA of the pull request, the 8 low findings of docs/qa/review-review-plan-2026-11-24/report.md, and issue #622 (stale deadline in the visual-loop skill).

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
