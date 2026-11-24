# Handoff: design review loop proposal

## What the work is for
Make the house-rules design loop smoother: a reviewer that checks designs and plans for flaws (not only wording), an acceptance run that tests and screenshots the finished feature before QA, no manual testing for aj, and questions parked and answered in one batch instead of halting work. In unattended mode, every departure from the build plan is logged in a deviations ledger shown first on the QA page.

## Where it stands
Proposal page written, trimmed for overlap, editor pass applied, rebuilt and sent: `docs/plans/2026-11-24-design-review-loop.html` (source `.page.json`, pictures in `-pics/`). Nothing is built and the loop is still at Design. Overlap found: unattended mode 2.87.0 is in main; "never wait" 2.90.0 (issues #587 to #591) is only on branch `AjsAgent/affectionate-lovelace-r0zfgg`. The page now covers only what those do not.

## The next step
aj answers with "Design approved: design review loop" plus eight picks. Then log the decision in `docs/6-decisions/Decisions.md` (four named reversals), write the build plan page on top of the 2.90.0 branch once it merges, review it, and create one issue per step.

## What is unverified
The other branch was read from its diffs, not run. Whether the agent sees the permission mode on every surface is unconfirmed (2.90.0's own note says the bypass value was not seen live). The 60-words-per-block limit was not counted, and other cited line numbers were not re-checked. Review cost and the two-round cap are unmeasured.

## The issue numbers
None yet for this proposal. Related, on the other branch: #587 to #591.
