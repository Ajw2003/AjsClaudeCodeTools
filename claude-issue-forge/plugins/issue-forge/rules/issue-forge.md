# Issue Forge

STATUS: v0.1 draft. This is the methodology text the `inject` hook loads at `SessionStart` and
the text `suggest` points at when it flags a doc change or ledger-scanning command. Read the
hard rule below before running anything this plugin ships — it is not a runtime habit, it is a
constraint on this plugin's own design.

## The idea

This repo's own documentation already reads like a backlog: `docs/architecture-backlog.md` and
`docs/rules-backlog.md` are hand-maintained decision logs, one entry per candidate or decided
change, and `docs/sessions/*.md` session ledgers (from `tools/session_ledger.py`) flag actions a
`Stop` hook continuation took that the user never saw in the visible reply. Nothing in the repo
turns any of that into a GitHub issue a separate tool could then read and act on. `scripts/forge.py`
is that engine: it scans the configured sources, drafts scoped issues, and — only after the user
has seen the drafts and said which ones to create — creates them.

## The hard rule: creation always needs explicit chat confirmation

**Creating a GitHub issue is "publish/post public content" under the standing safety rules.**
That category requires explicit permission in chat every time, not a general one-time approval,
and never something inferred from the shape of a request. This means, concretely:

- `forge.py --create` is **never invoked by a hook**. No hook event in this plugin runs `gh issue
  create`, or any variant of it, under any condition. `hooks/hooks.json` registers only
  `SessionStart` (`inject`) and `PostToolUse` (`suggest`) — `suggest` only ever emits a
  `systemMessage`/`additionalContext` reminder to run `--dry-run`; it never shells out to `gh`.
- `forge.py --create <slugs>` is **never invoked by Claude** without first running
  `forge.py --dry-run`, showing the user the full drafted list (title, labels, body) for the
  slugs in question, and receiving an explicit go-ahead in chat naming which of them to create.
  "The scan found some candidates" is not that go-ahead. A vague "yes, do it" on an unreviewed
  list is not that go-ahead either — the user needs to have actually seen what will be posted.
- A `--dry-run` invocation may read from GitHub (`gh issue list --search`, for dedup) without
  asking first — reads need no confirmation under the standing rules. Only the `--create` write
  path is gated.
- This rule cannot be relaxed by a flag, an environment variable, or a future revision of
  `forge.py` without also updating this document — the engine's two-phase split (Phase A always
  read-only, Phase B always confirmed) is the mechanism that makes the rule true in code, not
  just in prose.

## Sources this plugin reads

- `docs/architecture-backlog.md`, `docs/rules-backlog.md` (or whichever files
  `ISSUE_FORGE_BACKLOG_FILES` names) — hand-maintained decision logs. Split on `\n## ` headings;
  a section counts as a candidate only if it contains a `**Status:** open` line, so decided/shipped
  entries and non-item sections (a "Baseline" preamble, say) are skipped by construction.
- `docs/sessions/*.md` session ledgers (skipping `-brief.md` companions) — one candidate per
  ledger whose `## Actions taken after the visible reply` table has data rows, not one candidate
  per row, since the row-level detail belongs in the issue body, not in the issue count.

## Dedup: a marker in the issue body, not a state file

Each candidate's slug (derived from its source file + heading) is checked against
`gh issue list --search "issue-forge:source=<slug>"` before it is drafted as new. The marker is
embedded as an HTML comment in the issue body itself (`<!-- issue-forge:source=<slug> -->`), so
there is no local state file that can go stale or drift from what GitHub actually has — consistent
with this repo's existing bias against hidden state (see `docs/architecture.md` on why `hook.py`
keeps none). A candidate whose marker is already present in an existing issue (open or closed) is
skipped in Phase A.

## What a hook can actually do here

`suggest` fires on a `PostToolUse` event for an `Edit|Write` on one of the configured backlog
files, or a `Bash` command that references `session_ledger.py` (ledgers are written by a plain
Python script via `open()`, not through the `Write` tool, so file-path matching alone would miss
a new ledger landing). Either way, it can only emit a reminder that Claude reads — the same
"nudge, don't act" posture `agent-router`'s `route` and `house-rules`' `delegate` use. It never
runs `forge.py` itself, dry-run or otherwise; running the scan is always something Claude (or the
user, via `/issue-forge:forge`) chooses to do next.

## What this is not

- Not an auto-filer. Nothing in this plugin creates an issue without a human reading the specific
  drafted text first.
- Not a guarantee the drafted issues are well-scoped — the parsing rules above are mechanical
  (heading + status line, or a non-empty ledger table), and a badly-titled backlog entry produces
  a badly-titled draft. The user reviewing Phase A output is exactly the check for that.
- Not a replacement for `house-rules`' own safety rules — it is one more surface (issue creation)
  those rules already covered under "publish/post public content"; this document exists to make
  the application of that rule to this specific engine explicit and testable, not to add a new
  rule.
