# Handoff: reviewer model review

## What the work is for
aj asked whether Opus is the right model for the `house-rules:reviewer` agent, or whether Sonnet or Haiku would do with little quality loss.

## Where it stands
The reviewer was reviewed in code mode and the report is saved at `docs/qa/review-reviewer-2026-11-24/report.md`. Verdict (judgement, no benchmark): keep Opus for page mode and for the stuck-builder diff, use Sonnet for the other modes, Haiku for none. Nine findings are listed; none is fixed. No plugin code changed.

## The next step
aj chooses: fix findings 1 and 2 (pass the `review-modes.md` path, refresh the description), or build a Sonnet reviewer variant (second agent file plus `TIERS` and pin-check entries in `scripts/checks/common.py` and `delegation.py`).

## What is unverified
No Sonnet or Haiku run was compared with Opus. Findings 2 and 4 to 9 came from the reviewer's report and were not re-run; the model settings, the `waitfor.py` path and the `review-modes` line were re-checked.

## Issue numbers
None opened for this work. The review command itself is pull request 623, `Refs #617`.
