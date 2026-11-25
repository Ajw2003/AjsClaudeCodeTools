# Handoff: AjsAgent/review-models-per-mode (2026-11-24)

## What the work is for
aj asked for the review command's models to follow a measured comparison: Opus where the benchmark showed it matters, Sonnet elsewhere, and both models on code reviews because each found real bugs the other missed.

## Where it stands
Built and committed on this branch, cut from AjsAgent/speed-first at a2c38331. `review_plan.py` prints `model: default` for page, diff and plan, `opus+sonnet` for code and `sonnet` for codebase, image and style; `commands/review.md` tells the main session to run two reviewers one at a time for code and merge by `path:line`. The Decisions entry "Review models per mode", the review-command row, the delegate-execution and hook-engine lines, the "model set at spawn" wording and plugin 2.94.6 are in.

## The next step
Read the docs and delegation verify results, fix anything they show, then merge this branch into AjsAgent/speed-first (or open a pull request) once aj says which.

## What is unverified
The full verify run on this branch passes in every part (core 272, safe_git 282, design_loop 529, docs 176, writing 24, delegation 207, make_page 116: RESULT PASS - all 1606 checks passed, exit 0; run 2026-11-25). No live `/house-rules:review` run was made, so the two-reviewer merge step is untested. The benchmark is one run per mode; dollar cost was not measured.

## The issue numbers
Refs #617 (the review command). Not part of the speed first plan, issue #625.
