# Handoff: design review loop proposal

## What the work is for
Make the house-rules design loop smoother: a reviewer that checks designs and plans for flaws (not only wording), an acceptance run that tests and screenshots the finished feature before QA, no manual testing for aj, and questions parked and answered in one batch instead of halting work.

## Where it stands
Proposal page written and built: `docs/plans/2026-11-24-design-review-loop.html`, source `docs/plans/2026-11-24-design-review-loop.page.json`, pictures in `docs/plans/2026-11-24-design-review-loop-pics/`. Nothing is built and the loop is still at Design. The page builder reported no page errors or overflow in light and dark.

## The next step
aj answers with "Design approved: design review loop" plus eight picks. Then log the decision in `docs/6-decisions/Decisions.md` (including the four named reversals), write the build plan page, review it, and create one issue per step.

## What is unverified
The editor pass was applied and the page rebuilt. The 60-words-per-block limit was not counted. The claim that the QA builder refuses an empty unverified list was confirmed in `make_page.py:281`; the other cited line references were not re-checked. Review cost and the two-round cap are unmeasured.

## The issue numbers
None yet for this proposal. Overlap: unattended mode 2.87.0 is in main; "never wait" 2.90.0 (issues #587 to #591) is only on branch AjsAgent/affectionate-lovelace-r0zfgg and is not merged. Build this on top of that branch after it merges.

## Overlap found with other sessions
`event_noask` (house_rules/core.py) already refuses AskUserQuestion and ExitPlanMode in unattended or bypass sessions and says to choose a reversible option and record it in the report (branch AjsAgent/affectionate-lovelace-r0zfgg, 2.90.0). The proposal was trimmed to what is new: the deviations ledger, the plan as contract, attended-mode parking, the reviewer and the acceptance run.
