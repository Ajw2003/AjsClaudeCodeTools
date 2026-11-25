# Speed first: measured results (2026-11-25)

Measured in the Linux cloud sandbox (4 cores), not on aj's PC, so absolute numbers differ from `baseline.json`. "Old" is `main` before the speed work, "new" is this branch (step 3 plus step 5). Each figure is the median of 5 runs, taken with the helpers in `tools/time_hooks.py`.

| What | Old (main) | New (this branch) | Change |
|---|---|---|---|
| Hook time for one Write call | 649 ms, 18 processes | 145 ms, 4 processes | 4.5 times faster |
| Hook time for one Bash call | 458 ms, 12 processes | 163 ms, 4 processes | 2.8 times faster |
| One hook-log line (step 5, #630) | 0.384 ms | 0.011 ms | 35 times faster |
| GitHub label reads, 7 issues (step 4, #629) | 591 ms, already run at the same time | no change needed | the reads were already parallel (`design_loop.py:826`) |

## Verify parts, wall seconds (five run at once, so each is slower than alone)

core 28, safe_git 47, design_loop 60, delegation 54, make_page 100; docs 53 and writing 8 come from the old baseline. The old baseline recorded TIMEOUT for five of these at a 55 s cap. make_page is the longest at 100 s: the first target for step 6 (#631).

## Failing checks, this branch against main

The sets are identical: core 3, safe_git 3, design_loop 1 and delegation 2 checks fail on both `main` and this branch in the sandbox. The merge added no failure. Step 3 added four passing checks (safe_git 282 to 286) and step 5 added two (core 271 to 273).

## Not done yet

Step 2 (#627, load less per event) is worth at most about 40 ms per process, and only 2 processes per phase remain. Step 6 (#631, easy test wins) needs a profile of make_page (100 s) first. The full `verify.py` has not been run end to end.
