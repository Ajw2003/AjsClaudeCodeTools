# issue-forge

STATUS: shell / v0.1. A third offshoot of the `house-rules` formula in this repo, alongside
`prompt-workshop` and `agent-router` — same one-shim-plus-one-Python-file plugin shape, same
"nothing fails silently on the paths that can speak" discipline. This one scans this repo's own
documentation (backlog logs and session ledgers) for issue-worthy items, drafts scoped GitHub
issues from them, and creates them only after the user has seen the drafts and said which ones to
create — a separate external tool of the user's can then read those GitHub issues and
auto-populate them as tasks.

See [docs/offshoots-plan.md](../docs/offshoots-plan.md) at the repo root for the plan this was
built against and what's still open.

## Read this before anything else: the hard confirmation rule

**Creating a GitHub issue is "publish/post public content" under the standing safety rules —
it requires explicit permission in chat every time.** This plugin's hook (`suggest`) only ever
notices a relevant doc change and reminds Claude to *offer* running the read-only scan; it never
shells out to `gh` itself. The engine (`scripts/forge.py`) is a strict two-phase split: Phase A
(`--dry-run`) reads from GitHub for dedup and needs no confirmation; Phase B (`--create <slugs>`)
is the only thing that posts, and is never run without the user first seeing the drafted list and
naming, in chat, exactly which ones to create. Full explanation in
[rules/issue-forge.md](plugins/issue-forge/rules/issue-forge.md).

## What it actually does

Every hook, defined in
[plugins/issue-forge/hooks/hooks.json](plugins/issue-forge/hooks/hooks.json), runs
`sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`, which resolves a working Python interpreter
and hands off to [scripts/hook.py](plugins/issue-forge/scripts/hook.py):

| Hook event | Matcher | When | What it does |
|---|---|---|---|
| `SessionStart` | — | every session | the `inject` handler prints [rules/issue-forge.md](plugins/issue-forge/rules/issue-forge.md) — the methodology and the hard confirmation rule — into Claude's context. |
| `PostToolUse` | `Edit\|Write` | after a file write | the `suggest` handler reads `file_path`; if it matches a configured backlog file (`docs/architecture-backlog.md`, `docs/rules-backlog.md` by default, overridable via `ISSUE_FORGE_BACKLOG_FILES`), it reminds Claude to offer running `scripts/forge.py --dry-run`. Never blocks; always traces. |
| `PostToolUse` | `Bash` | after a shell command | the `suggest` handler reads `command`; if it references `session_ledger.py` (ledgers are written via plain `open()`, not the `Write` tool, so file-path matching alone can't catch a new one landing), it reminds Claude the same way. |

There is also [`/issue-forge:forge`](plugins/issue-forge/commands/forge.md) to run the scan on
demand and walk through the confirmation flow explicitly.

## `scripts/forge.py` — the scan/draft/create engine

```bash
python scripts/forge.py --dry-run --repo <owner/repo>      # Phase A: read-only scan + draft
python scripts/forge.py --create <slug1,slug2> --repo ...  # Phase B: only after chat go-ahead
```

- **Sources:** `docs/architecture-backlog.md` / `docs/rules-backlog.md` (or whatever
  `ISSUE_FORGE_BACKLOG_FILES` names), split on `\n## ` headings, keeping only sections whose text
  contains `**Status:** open`; and `docs/sessions/*.md` session ledgers (skipping `-brief.md`
  companions), one candidate per ledger whose `## Actions taken after the visible reply` table
  has data rows.
- **Dedup:** a stable slug per candidate, checked against
  `gh issue list --repo <owner/repo> --state all --search "issue-forge:source=<slug>"` — the
  marker embedded in the issue body is the whole mechanism, no local state file.
- **Issue body:** a generic template — Context / Why it matters / Proposed change / Source —
  since the downstream tool's schema isn't known yet. Labels are always `source:<origin>`, plus
  a `strength:*` label for architecture-backlog items that already carry one.

## What's deliberately still rough (v0.1)

- The Context/Why/Proposed extraction from each backlog entry is a labeled-paragraph heuristic
  (`**The friction.**`, `**Evidence.**`, `**What would change.**`, …) — an entry that doesn't use
  those exact labels drafts less cleanly. The Phase A chat review is the intended backstop.
- No coverage, by design, of a real end-to-end `gh issue create` against a live repo — `verify.py`
  stops at a stubbed `gh` runner, the same documented limitation `tools/verify_tools.py` carries
  for anything that shells out to a real CLI.
- Nothing verifies a created issue stays in sync if its source backlog entry is later edited —
  the marker prevents a duplicate, not staleness.

## Running the test suite

```bash
python claude-issue-forge/plugins/issue-forge/scripts/verify.py
```

48 checks: the inject fail-loud contract, suggest's never-blocks/always-traces contract on both
matchers, backlog/ledger parsing against fixtures shaped like the real docs structure, the
dedup/create logic against a stubbed `gh`, the hard confirmation rule's presence in both
`rules/issue-forge.md` and the shape of `hook.py`/`forge.py`, and the hooks.json/EVENTS parity
check.

## Installing it

Not yet published as an everyday-installable marketplace entry — listed in
`.claude-plugin/marketplace.json` at the repo root as `issue-forge`. Install the same way
`house-rules` is:

```bash
claude plugin marketplace add ajw2003/ajsclaudecodetools
claude plugin marketplace update aj-house-rules
claude plugin install issue-forge@aj-house-rules
```
