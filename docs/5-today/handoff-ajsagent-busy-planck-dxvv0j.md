# Handoff: branch ajsagent/busy-planck-dxvv0j

## What the work is for
aj asked for a critical whole-repo review, then chose the order for acting on it: hook speed first, then code quality, then the guard holes.

## Where it stands
The review is saved in `docs/qa/review-ajsclaudecodetools-2026-11-24/report.md` and pushed. A proposal page for the speed work is at `docs/plans/speed-first-proposal.html` (content in `docs/plans/speed-first-proposal.page.json`, pictures in `docs/plans/speed-first-proposal-pics/`). No code has been changed.

## The next step
aj answers the three questions on the proposal page and sends the approval line (`Design approved: speed first`, naming the options). After that: a build plan with one issue per step, then a builder on a branch, measuring before and after.

## What is unverified
- The speed targets are not set: the timing script that gives the baseline is step 1 of the proposal and is not built.
- The per-call figures (66 ms, 9 processes per Write, 748 ms) come from reviewer measurements, not a run of mine.
- The docs prose batches, the markdown and template batches, agent-router and prompt-workshop were not reviewed.
- Reviewers read the largest files by pattern, not line by line.
- The full `verify.py` run could not be timed under the 55 second cap.
- Windows behaviour, the install scripts and the Stop-time model judge were read from code, not run.

## Issue numbers
None opened yet for the speed work; they are created with the build plan after approval. Earlier work on this repo is under pull request 623 (issue 617).
