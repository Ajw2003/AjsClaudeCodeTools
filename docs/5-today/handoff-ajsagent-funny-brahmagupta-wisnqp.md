# Handoff: reviewer model review

## What the work is for
aj asked whether Opus is the right model for the `house-rules:reviewer` agent, or whether Sonnet or Haiku would do with little quality loss.

## Where it stands
The reviewer was reviewed in code mode and the report is saved at `docs/qa/review-reviewer-2026-11-24/report.md`. Verdict (judgement, no benchmark): keep Opus for page mode and for the stuck-builder diff, use Sonnet for the other modes, Haiku for none. Nine findings are listed. The top three (the `review-modes.md` path, the `waitfor.py` path, the stale description) are fixed in `agents/reviewer.md` and the plugin is 2.94.2; verify passes (1,606 checks). The `verdict` hook now compares a typed model (plugin 2.94.4) and findings 4 to 8 are fixed; finding 9 is left because the reviewer's bullets are its fallback when no modes path reaches it. Later in the session the command gained `--model` and `--effort` overrides (plugin 2.94.3) and now passes the real `review-modes.md` and `waitfor.py` paths in the spawn prompt, because an agent file may not expand `${CLAUDE_PLUGIN_ROOT}`.

## The next step
aj decides whether to build a Sonnet reviewer variant (second agent file plus `TIERS` and pin-check entries in `scripts/checks/common.py` and `delegation.py`).

## What is unverified
No Sonnet or Haiku run was compared with Opus. Not tested live: a real `/house-rules:review ... --model sonnet` run (the sandbox has plugin 2.94.1 installed), and the new `verdict` override comparison in a live session. Findings 4 to 9 came from the reviewer's report and were not re-run.

## Issue numbers
None opened for this work. The review command itself is pull request 623, `Refs #617`.
