# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | 2 (#619) | Step 2 builds commands/review.md only; the command does the mode choice, batching and notice figures itself. | Also builds scripts/review_plan.py, a small script that picks the mode, counts files, makes batches of at most 8 files and prints the over-12-folders notice. | A command file is instructions to a model; counts and batch sizes the user is shown must be counted by code, and the plan's own acceptance tests 1 and 4 need something runnable to check. | Delete scripts/review_plan.py and move its rules back into commands/review.md as prose; the acceptance tests 1 and 4 would then need a manual run. |

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
