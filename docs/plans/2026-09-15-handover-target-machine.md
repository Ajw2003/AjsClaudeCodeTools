# Distinguish "the machine I run on" from "the machine a handover targets"

## Context

The Step 2 command I handed over earlier today in a different session assumed Linux/bash — wrong, the user is on
Windows/PowerShell. Root cause, confirmed by reading the code: `rules/house-rules.md`'s "Find out
what machine you are on, then build for that" rule and `hook.py`'s `_detect_environment()`
(scripts/hook.py:98-121) only ever describe **the machine executing this session's tool-calls**.
For a local CLI/IDE/Desktop-Code-tab session that machine and the user's own machine are the same
box, so the rule has always been correct there. This session is remote (confirmed:
`CLAUDE_CODE_REMOTE=true` and `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default` are set in its
environment) — the sandbox `hook.py` runs on is Linux, the user's actual machine is Windows, and
nothing in the rule or the injected "This machine" profile ever flagged that these could differ.
The rule's own example text even lists "a cloud session on Linux" as just another machine to
build for, reinforcing the conflation instead of catching it.

This repo already has the evidence needed to fix this without guessing: `docs/example-environment.md`
is a committed "worked example" record of aj's real machine (Windows 11 Pro, PowerShell 5.1
Desktop edition, Git Bash for POSIX, `sh`/`bash` **not** on PATH), dated 2026-08-25, kept in `docs/`
specifically so it survives a fresh clone even though `rules/environment.md` itself is
machine-local and gitignored. The user has now separately confirmed PowerShell was in fact right.

The fix: give the plugin a second, distinct machine-local record — the machine a **handed-over
command** targets — that is only ever relevant on a remote session, is never confused with the
sandbox's own profile, and once recorded, answers this automatically for the rest of this and
every future session in this same remote environment, with no re-asking.

## Design

**New file: `rules/handover-target.md`** — machine-local, gitignored, same shape and lifecycle as
`rules/environment.md`, but answering a different question: not "what does `hook.py` run on"
(that's `environment.md`, still correct and unchanged — `guard`/`runnable` correctly keep
targeting the sandbox, since that's genuinely where Claude's own tool-calls execute) but "what
machine will a human run a step-card's command on." Absent by default. Never auto-filled by
runtime detection (impossible — `hook.py` cannot detect a different physical machine), only by
being told and recorded.

**`hook.py`'s `event_inject()`** (scripts/hook.py:178+) gets a new, cheap, conditional block:
- Reads a new env-overridable path `HOUSE_RULES_HANDOVER_TARGET_FILE` (default
  `rules/handover-target.md`), mirroring the existing `HOUSE_RULES_ENV_FILE` pattern used for
  `envfile` (scripts/hook.py:181-183).
- Only does anything when `os.environ.get("CLAUDE_CODE_REMOTE")` is truthy — on a normal local
  session this must add zero text and zero cost, matching the "why" that already governs this
  handler (most sessions are local; this file's whole design principle is not making the common
  path pay for the rare one).
- Remote + file recorded → inject its content under a heading clearly distinct from "This
  machine," e.g. "## The human's own machine (for anything I hand over to them)" — recorded,
  build a step-card for exactly that, same as `environment.md`'s "recorded? build for exactly
  that" rule.
- Remote + file missing/empty → inject an instruction: this session is remote, the machine
  profile above is the sandbox's, not necessarily the user's; before the first handed-over
  command, find out theirs — check `docs/example-environment.md` if present (say it's inferred
  and from when, not confirmed), or ask — then record the confirmed answer into
  `rules/handover-target.md` so a later session does not have to ask again.

**`rules/house-rules.md`** — extend "Find out what machine you are on, then build for that" with
a short clause: the machine I execute tool-calls on and the machine a handed-over command targets
are the same question on a local session, and a **different** one on a remote session (the harness
says so directly — "a managed remote execution environment... in the cloud rather than on the
user's machine" — and `CLAUDE_CODE_REMOTE` confirms it). On remote, I answer the second question
the same way as the first: recorded in `rules/handover-target.md`? Build for exactly that. Not
recorded? Find out right then — hard evidence first (a repo's own machine record, something
they've told me), a direct question only if neither exists — then write it down.

**`scripts/verify.py`** — three cases mirroring the existing environment.md tests
(scripts/verify.py:749-774):
1. Not remote (no `CLAUDE_CODE_REMOTE` in the test env) → `inject` output is unchanged from
   today — no handover-target text at all. Regression guard for the common path.
2. Remote (`CLAUDE_CODE_REMOTE=true` in the test env) + no handover-target file → output contains
   the "find out theirs" instruction.
3. Remote + `HOUSE_RULES_HANDOVER_TARGET_FILE` pointed at a fixture file with recorded content →
   output contains that content.
Plus a drift check tying a phrase between the new house-rules.md clause and hook.py's new
instruction text, same pattern as every other drift check in this file (e.g. the scope-reminder
drift check at scripts/verify.py:669-716).

**`.gitignore`** — add `claude-house-rules/plugins/house-rules/rules/handover-target.md` right
after the existing `environment.md` entry (.gitignore:4-5), same comment style.

**`CLAUDE.md`** (root, hook table) — extend the `inject` row's description to mention the new
remote-only handover-target behavior in one clause.

## Dogfooding

- Write `claude-house-rules/plugins/house-rules/rules/handover-target.md` for real in this
  session's own environment, from the evidence already gathered: Windows 11, PowerShell (5.1
  Desktop edition per `docs/example-environment.md`, dated 2026-08-25 — noted as last-confirmed
  then, re-confirmed today 2026-09-15 that PowerShell is the right shell), Git Bash for POSIX
  commands, `sh`/`bash` not on PATH. This makes the fix immediately real for the rest of this
  session and any future session in this same remote environment — no more asking.
- Add a `docs/Decisions.md` entry recording this exact incident and fix: what went wrong (Step 2
  assumed Linux/bash), why (environment detection conflated sandbox with handover target), the
  fix (the new file + conditional inject block), evidence cited (`CLAUDE_CODE_REMOTE`,
  `docs/example-environment.md`).

## Verification

`python claude-house-rules/plugins/house-rules/scripts/verify.py` from the repo root — exit 0, no
FAIL lines.

## Commit / push

New branch off current `main` (the sixth-tier branch already merged) — same two-commit split as
before: (1) the plugin fix (house-rules.md, hook.py, verify.py, .gitignore, CLAUDE.md), (2) the
dogfooding (`rules/handover-target.md` for this session — note: gitignored, so this commit only
adds the Decisions.md entry; the handover-target.md file itself is intentionally never committed).
Push and open a PR the same way as the last two changes; merge once CI is green, same as before.

## Execution

Multi-file, behavior-changing (hook.py) — delegate to `@house-rules:executor` with this plan
file's path, same as the last two changes.
