# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Choices

| # | Step | Choice made | Assumption | Why | How to undo |
|---|---|---|---|---|---|

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | 1 (#638) | Restore a speed first entry under features in the stage file, with a test | Not done: the stage-file guard refuses hand edits, so the entry was not added and the test was removed | Only aj's approval messages may move the stage; merging this branch into main conflicts on that file visibly, so speed first's Build state is not silently overwritten | Add the entry through a merge of main or by aj, then restore the test |
| D2 | 1 (#638) | park stores its category and attempt in separate columns | park stores them inside the Question cell as [category] question (tried: ...) | The ledger table has no spare columns and a new column would break older ledgers | Add two columns and migrate older rows |
| D3 | 1 (#638) | Update the pinned noask deny text test at checks/design_loop.py:3295 | Left unchanged: that text is built in core.py:2792 and is rewritten in step 12 (#643) | Step 12 owns the unattended and denied-question messages; until then that text still names park without a category | Rewrite the core.py text now |
| D4 | 15 (#644) | A look choice in an unattended run is always logged | Reversed after round 2: criterion C8 is back to its original meaning, and a hook was added instead (a stop with every step closed and no logged choice is blocked once, in unattended and bypass only) | Live run 5 (sonnet, neutral prompt) chose a teal header and logged nothing, so the rules alone do not make a model log; narrowing the criterion would have hidden that | Remove `_choices_check` in design_loop.py |

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
