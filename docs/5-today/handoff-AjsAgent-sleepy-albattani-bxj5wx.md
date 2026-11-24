# Handoff: design review loop proposal

## What the work is for
Make the house-rules design loop smoother: a reviewer that checks designs and plans for flaws (not only wording), an acceptance run that tests and screenshots the finished feature before QA, no manual testing for aj, and questions parked and answered in one batch instead of halting work. In unattended mode, every departure from the build plan is logged in a deviations ledger shown first on the QA page.

## Where it stands
Build stage, approved by aj ("Build plan approved: design review loop"). Step 1 (#593, reviewer modes) is built and committed (`b7072bc`); my own full `verify.py` run passed 1444 of 1444 and a real page-mode run found seven findings. Step 2 (#594, review stamp) is built and committed; my own full `verify.py` run passed 1453 of 1453. Step 3 (#595, acceptance run) is built and committed; my own full run passed 1465 of 1465. Step 5 (#597) is next. Deviations D1 to D4 and parked decisions P1 and P2 are in `docs/qa/design-review-loop/ledger.md`. Steps 6 and 7 wait for 2.90.0 to merge.

## The next step
Build step 5 (#597), then step 8 (#600, parked decision P1 decides its design) one at a time, record steps 6 and 7 as owed, then 4 and 9.

## What is unverified
One pagecheck case ("HOUSE_RULES_LOOP=off allows a hand-written Write and a hand-written publish") failed in two standalone design_loop runs by the step 2 helper and passed in both full runs; the cause was not found, so it may be flaky. The stamp check has not been seen firing in a live session. The other branch was read from its diffs, not run. Whether the agent sees the permission mode on every surface is unconfirmed (2.90.0's own note says the bypass value was not seen live). The 60-words-per-block limit was not counted, and other cited line numbers were not re-checked. Review cost and the two-round cap are unmeasured.

## The issue numbers
Parent #592; steps #593 (reviewer), #594 (stamp), #595 (acceptance run), #596 (QA gate), #597 (self-judging test), #598 (parked ledger), #599 (deviations ledger), #600 (combined approval), #601 (docs and tests). Related, on the other branch: #587 to #591.
