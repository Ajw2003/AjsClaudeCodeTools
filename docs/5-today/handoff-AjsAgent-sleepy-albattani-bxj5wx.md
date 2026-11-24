# Handoff: design review loop proposal

## What the work is for
Make the house-rules design loop smoother: a reviewer that checks designs and plans for flaws (not only wording), an acceptance run that tests and screenshots the finished feature before QA, no manual testing for aj, and questions parked and answered in one batch instead of halting work. In unattended mode, every departure from the build plan is logged in a deviations ledger shown first on the QA page.

## Where it stands
Design approved by aj (1A 2A 3A 4A 5* 6A 7A 8A; 5*: every page except review and QA pages is fully reviewed). Stage: Plan. Done: decisions entry, `docs/4-systems/review-loop.md`, parent issue #592 and steps #593 to #601, and the build plan page `docs/plans/2026-11-24-design-review-loop-plan.html` (editor pass applied, sent). Nothing is built. Overlap: unattended mode 2.87.0 is in main; 2.90.0 (#587 to #591) is only on `AjsAgent/affectionate-lovelace-r0zfgg`.

## The next step
aj answers "Build plan approved: design review loop". Then build step 1 (#593) with a builder helper, then steps 2, 3, 5 and 8 one at a time. Stop before step 6 until 2.90.0 merges and record steps 6 and 7 as owed.

## What is unverified
The other branch was read from its diffs, not run. Whether the agent sees the permission mode on every surface is unconfirmed (2.90.0's own note says the bypass value was not seen live). The 60-words-per-block limit was not counted, and other cited line numbers were not re-checked. Review cost and the two-round cap are unmeasured.

## The issue numbers
Parent #592; steps #593 (reviewer), #594 (stamp), #595 (acceptance run), #596 (QA gate), #597 (self-judging test), #598 (parked ledger), #599 (deviations ledger), #600 (combined approval), #601 (docs and tests). Related, on the other branch: #587 to #591.
