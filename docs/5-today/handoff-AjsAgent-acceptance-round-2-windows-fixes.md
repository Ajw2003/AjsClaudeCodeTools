# Handoff: acceptance round 2 passed, waiting on QA

## What the work is for
Finish the design review loop (parent issue #592) by recording acceptance round 2 from real output on aj's Windows PC, stamping it, and handing it over for QA.

## Where it stands
Two Windows-only bugs are fixed on branch `AjsAgent/acceptance-round-2-windows-fixes` (cut from `pc-acceptance-round-2`): the close-facts tests faked `gh` with a shell script (now a Python stand-in), and the review stamp hashed CRLF differently from LF. A rerun of `run_acceptance.py` on aj's PC passed C1 to C9. `round-1.md` (written from `report.md`) and `round-2.md` are recorded, `ledger.py check` is valid, and `acceptance.py check` says the stamp is current. The QA page is built at `docs/plans/2026-11-24-design-review-loop-qa.html`.

## The next step
Wait for aj's reply on the QA page: "QA passed: design review loop", or what failed. On a pass, mark the issues and pull request #604 ready for aj's merge decision; on a fail, fix on this branch and rerun the failing criterion with `run_acceptance.py C<n>`.

## What is unverified
A full `verify.py` run after both fixes passed 1572 of 1581 checks; nine fail on Windows (guard x3, page checks x2, waitfor x3, node x1), the same nine as before the stamp fix, uninvestigated and not compared against a clean `main`. The deviation check is a phrase heuristic never seen firing live. No test covers the two-round cap or changed-pick re-review. Round 1 was recorded afterwards from the report, not from a fresh run.

## The issue numbers
Parent #592; pull request #604 (`Refs #592`).
