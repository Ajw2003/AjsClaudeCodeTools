# Handoff: finishing the design review loop

## What the work is for
Finish the design review loop (parent issue #592): a reviewer that checks designs and plans for flaws, an acceptance run of the finished feature before QA, questions parked in a ledger instead of halting work, and a deviations ledger for runs with nobody present.

## Where it stands
The unmerged branch `AjsAgent/sleepy-albattani-bxj5wx` is merged into this branch, with its conflicts resolved (changelog kept both sides, the stage file kept the design review loop's own, `delegation.py` kept both test blocks). Step 7 (#599) now has tests and an end-of-reply `deviation` check, and step 9 (#601) is done: systems doc rewritten as built, four reversal entries in the decisions log, plugin 2.92.0. My own full runs before the notes were written: `verify.py` 1577 of 1577, `tools/verify_tools.py` exit 0, `docref.py check` OK, `docs_drift.py` 0 drifted. The acceptance run reported: 6 of 9 criteria pass; C1 (no saved reviewer findings), C5 (card format unchecked) and C6 (combined approval does not refuse with no plan issues) fail. Report: `docs/qa/design-review-loop/report.md`.

## The next step
Read the test run of `docs/qa/design-review-loop/run_acceptance.py`, fix any search text that matches no check, then hand aj the one command to run it (aj chose option A). Record `round-2.md` from the saved outputs with `ledger.py`, run `scripts/acceptance.py stamp docs/qa/design-review-loop`, build the QA page with the page builder and send it. Pull request #604 is open (`Refs #592`). The test run of the runner (search texts fixed after the first run showed four matched no check) was started in the background and its result is unread. aj also asked for the roadblock judge's over-zealous firing to be noted: `docs/roadblock-judge-friction-2026-11-24.md` (nothing changed).

## What is unverified
C1, C5 and C6 are fixed and tested, but the acceptance run was not repeated as recorded rounds, so there is no acceptance stamp. Open risks on the plan page: no test for the two-round cap, changed picks re-review, or separate tests for page-mode facts and plan-mode checks. The report was written by the main session from the helper's throwaway-clone evidence. The deviation check is a phrase heuristic and has not been seen firing in a live session. Nothing was run on Windows. One pagecheck case fails when `checks/design_loop.py` is run alone and passes in the full run; it also fails on a clean `main`, cause not found.

## The issue numbers
Parent #592; steps #593 to #601 (this session finished #599 and #601). Related, already merged: #583 to #586.
