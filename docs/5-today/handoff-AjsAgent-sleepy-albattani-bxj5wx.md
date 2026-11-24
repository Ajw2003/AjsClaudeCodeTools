# Handoff: design review loop proposal

## What the work is for
Make the house-rules design loop smoother: a reviewer that checks designs and plans for flaws (not only wording), an acceptance run that tests and screenshots the finished feature before QA, no manual testing for aj, and questions parked and answered in one batch instead of halting work. In unattended mode, every departure from the build plan is logged in a deviations ledger shown first on the QA page.

## Where it stands
Build stage, approved by aj. Built and committed: step 1 (#593), 2 (#594), 3 (#595), 5 (#597) and 8 (#600). Version 2.90.0 (the `AjsAgent/affectionate-lovelace-r0zfgg` branch) was merged into this branch at aj's request; on the merged tree my own runs passed `verify.py` 1523 of 1523 and `tools/verify_tools.py` exit 0. Step 4 (#596, QA gate) is being rebuilt by a helper and is NOT committed: check `git status` first. aj decided a docs-only feature also needs an acceptance run (no bypass). Steps 6 (#598), 7 (#599) and 9 (#601) are not started; 6 and 7 are no longer blocked. aj asked for the pull request to be opened when the build is ready. Deviations D1 to D9, parked decisions P1 to P3 and the question-hold incident are in `docs/qa/design-review-loop/ledger.md`.

## The next step
When the step 4 helper reports, check its files and re-run `python claude-house-rules/plugins/house-rules/scripts/verify.py` yourself, then commit. Then build step 6, step 7, step 9, run the acceptance run of this feature, build the QA page, and open the pull request (`Refs #592`, never Closes). End every reply during Build with a statement of the next step, not a question: a question holds code edits (issue #506).

## What is unverified
The self-test template was run for real on Python 3.8.20 and 3.13 (exit 0, 1 and 2 paths on 3.13); it was not run on Windows, which this Linux sandbox cannot do. One pagecheck case ("HOUSE_RULES_LOOP=off allows a hand-written Write and a hand-written publish") failed in two standalone design_loop runs by the step 2 helper and passed in both full runs; the cause was not found, so it may be flaky. The stamp check has not been seen firing in a live session. The merge was committed by an automatic save (`d03b8f2`); a local git rule in `.git/info/attributes` (not committed) keeps this branch's stage file in merges. Whether the agent sees the permission mode on every surface is unconfirmed (2.90.0's own note says the bypass value was not seen live). The 60-words-per-block limit was not counted, and other cited line numbers were not re-checked. Review cost and the two-round cap are unmeasured.

## The issue numbers
Parent #592; steps #593 (reviewer), #594 (stamp), #595 (acceptance run), #596 (QA gate), #597 (self-judging test), #598 (parked ledger), #599 (deviations ledger), #600 (combined approval), #601 (docs and tests). Related, on the other branch: #587 to #591.
