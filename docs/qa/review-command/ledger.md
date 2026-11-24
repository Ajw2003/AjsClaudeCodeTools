# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | 2 (#619) | Step 2 builds commands/review.md only; the command does the mode choice, batching and notice figures itself. | Also builds scripts/review_plan.py, a small script that picks the mode, counts files, makes batches of at most 8 files and prints the over-12-folders notice. | A command file is instructions to a model; counts and batch sizes the user is shown must be counted by code, and the plan's own acceptance tests 1 and 4 need something runnable to check. | Delete scripts/review_plan.py and move its rules back into commands/review.md as prose; the acceptance tests 1 and 4 would then need a manual run. |
| D2 | 2 and 3 (#619, #620), found in acceptance test 4 | The sweep notice estimates tokens as 4,400 per file. | Change the estimate to about 10,000 tokens per batch plus 3,400 per file, and change the verify case, the notice text and the docs to match. | A real 15-batch sweep of one-line files used 203,394 tokens, 3.1 times the 66,000 estimated; a reviewer costs about 13,500 tokens even for a one-file batch. aj asked for an approximate usage, so the estimate must hold for small batches too. | Set the per-file figure back to 4,400 tokens with no per-batch figure in scripts/review_plan.py and the notice text, and restore the verify case and docs wording. |
| D3 | 2 (#619), found in acceptance test 3 | scripts/review_plan.py picks the mode, finds a plan's design page and counts the sweep as written in step 2. | Fix the 2 high and 7 medium findings of the code-mode review (docs/qa/review-review-plan-2026-11-24/report.md): the design lookup for -build-plan and folder-style plans, ./ and the absolute repo path meaning codebase, a clean error for a missing --root or git, report names for folder-style plans, an unambiguous design match, target resolved against --root, headroom in the batch size; verify cases for each. | A real review of the shipped helper script reproduced four of these as wrong behaviour for pages and paths that exist in this repo; they are defects in the approved feature, not new features. | Revert the commit that fixes them; the eight low findings are not touched. |

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
