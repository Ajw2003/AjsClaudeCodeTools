# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | Step 2 (#627) and Step 3 (#628) | Step 2 loads only one module per event, then step 3 merges processes. | Step 3 goes first. Step 2 is paused: the parts register their hooks into core when imported (delegation.py:2195, safe_git.py:2125, design_loop.py:3604-3612), so loading one module per event drops hooks and fails 11 core checks. The attempt is saved on branch AjsAgent/speed-step2-attempt. | Measured on this PC (median of 9): bare Python 50 ms, core only 128 ms, all seven parts 169 ms, so step 2 saves at most about 41 ms per process, while step 3 cuts 18 processes per Write to 2. | Resume step 2 after step 3 with a per-event list of modules to load, starting from the saved branch. |

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
