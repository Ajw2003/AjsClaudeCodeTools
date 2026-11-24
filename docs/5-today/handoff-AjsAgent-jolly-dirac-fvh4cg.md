# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command build)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes (code, codebase, image, style), not duplicated.

## Where it stands

- Design and build plan approved ("Design approved: review command 1A 2A 3*", "Build plan approved: review command 1A 2A 3A"). Stage: Build. Decisions entry written.
- Issues: parent #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version), all `in progress`. #622 is the stale deadline line in the visual-loop skill, not part of this build.
- Step 1 (#618) is built and merged into this branch (merge 23ab05b). All seven verify.py parts pass on it from my own runs: core 272, docs 167, writing 24, design_loop 529, make_page 116, safe_git 282, delegation 204 (same 204 on the baseline). Step 2 (#619) is merged (merge 9c9c79f): commands/review.md and scripts/review_plan.py; all seven verify.py parts passed on its final commit 4e94d17 (core 272, docs 167, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 3 (#620) is merged (merge 27233ed); all seven verify.py parts pass on it (docs 174, core 272, writing 24, safe_git 282, delegation 204, design_loop 529, make_page 116). Step 4 (#621) is merged (5fcddd6), plugin 2.94.0; all seven verify.py parts pass on it. Acceptance tests 1, 2 and 4 are saved in docs/qa/review-command/round-1/; the real sweep (15 batches, all no findings) used 88.9 s and 203,394 tokens against a notice estimate of 66,000 tokens, so deviation D2 was logged and a builder is fixing the estimate on branch AjsAgent/review-command-fix-estimate (worktree /home/user/wt-review-step5; rule: 10,000 tokens per batch plus 3,400 per file; plugin 2.94.1). Test 3 (code-mode review of scripts/review_plan.py) is running; tests 5, 6, 7 are not run.
- aj's answers: reports saved by the main session; sweep folder by folder, no cap, notice over 12 folders; a folder is split into batches that fit the 60-second agent deadline; repo-root files are reviewed as one unit; mode lists go in `review-loop.md` and the command keeps `review-command.md`.

## The next step

Read the fix builder's report; run all seven verify.py parts myself in the worktree (background, one after another, new output file, the `all N checks passed` line of each); merge AjsAgent/review-command-fix-estimate (keep both sides of any CHANGELOG.md conflict in one command and commit the resolved file). Save test 3's report to docs/qa/review-review-plan-<date>/report.md (the main session writes it). Run test 5 (no argument is diff mode; style with no stated style stops; image with no criteria uses hierarchy, contrast, alignment, consistency), test 6 (visual-loop verify cases pass; already covered by the delegation part) and test 7 (ranking: spawn a reviewer on a fixture file seeded with a real bug and check merge order [high], [medium], [low], then file). Write the round verdict, swap `in progress` for `needs review` on #617 to #621, build the QA page with make_page.py QA mode. Ask aj at QA about the notice threshold (9 folders but 96 batches in this repo).

## What is unverified

- Nothing built has been run yet; no verify.py result exists for this feature.
- The per-batch time and token figures in the sweep notice must be measured in step 2; none exist yet.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (60-second segments), #622 (visual-loop skill quotes old deadlines).
