# Handoff: finishing the design review loop

## What the work is for
Finish the design review loop (parent issue #592): a reviewer that checks designs and plans for flaws, an acceptance run of the finished feature before QA, questions parked in a ledger instead of halting work, and a deviations ledger for runs with nobody present.

## Where it stands
The unmerged branch `AjsAgent/sleepy-albattani-bxj5wx` is merged into this branch, with its conflicts resolved (changelog kept both sides, the stage file kept the design review loop's own, `delegation.py` kept both test blocks). Step 7 (#599) now has tests and an end-of-reply `deviation` check, and step 9 (#601) is done: systems doc rewritten as built, four reversal entries in the decisions log, plugin 2.92.0. My own full runs before the notes were written: `verify.py` 1577 of 1577, `tools/verify_tools.py` exit 0, `docref.py check` OK, `docs_drift.py` 0 drifted. The reviewer helper's acceptance run is under way and has not reported.

## The next step
Read the reviewer's report in `docs/qa/design-review-loop/`, fix any FAIL, run `scripts/acceptance.py stamp design-review-loop`, build the QA page with the page builder, send it, and open the pull request with `Refs #592`, never Closes.

## What is unverified
The acceptance run result. The deviation check is a phrase heuristic and has not been seen firing in a live session. Nothing was run on Windows. One pagecheck case fails when `checks/design_loop.py` is run alone and passes in the full run; it also fails on a clean `main`, cause not found.

## The issue numbers
Parent #592; steps #593 to #601 (this session finished #599 and #601). Related, already merged: #583 to #586.
