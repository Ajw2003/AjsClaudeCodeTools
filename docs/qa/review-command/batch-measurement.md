# Batch measurement for the sweep notice (step 2, #619)

Measured 2026-11-24 by running the reviewer in `codebase` mode on one batch: the 7 files in
`claude-house-rules/plugins/house-rules/commands/` plus `agents/builder.md`, `reviewer.md` and
`scout.md` (10 files, 322 lines, 20,076 characters, all markdown).

| Measure | Value | Source |
|---|---|---|
| Time | 71.3 seconds | subagent transcript first to last line (21:48:00 to 21:49:11); the harness reported 71,304 ms |
| Tokens | 43,991 | the harness's `subagent_tokens` for that run |
| Per file | about 7.1 seconds and 4,400 tokens | the two figures divided by 10 |

**What follows.** Ten files already took longer than the 60-second agent deadline in
`rules/waits.json`, so one batch is capped at 8 files (8 x 7.1 = 57 seconds, about 35,000 tokens).
The figures come from markdown. Large code files take longer per file, so treat every estimate
as a minimum.

## What the reviewer found (20 findings, none fixed here)

These are real problems in `commands/` and `agents/`, outside this feature. Examples:
`commands/doctor.md:13` uses `ver`, which does not exist in Git Bash; `agents/builder.md:20` and
`agents/reviewer.md:20` use a relative `scripts/waitfor.py` path that resolves inside the user's
project; `commands/harvest-scan.md:32` can report an abandoned scan as clean. The full list is in
the session record; no issue is opened unless aj asks.
