# The hook engine

## What it owns

Dispatching every `house-rules` hook event — `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
`PostToolUse`, `Stop`, `SubagentStart`, `SubagentStop` — to the one handler that enforces the
corresponding rule from
[`rules/house-rules.md`](../../claude-house-rules/plugins/house-rules/rules/house-rules.md), at
the moment Claude Code actually fires that event. If this is wrong, the rules stop being
enforced and become prose nobody is checking against — a permission prompt that should have
fired doesn't, or a reminder that should have reached Claude never does.

It does **not** own: whether the rule text itself is right (that's the rules document), whether
the claims in this doc are still true (that's
[`verify-suites.md`](verify-suites.md)'s job), or getting the plugin onto a machine in the first
place (that's [`plugin-distribution.md`](plugin-distribution.md)).

## How it works

Every hook command in
[`hooks/hooks.json`](../../claude-house-rules/plugins/house-rules/hooks/hooks.json) is identical:
`sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`.
[`scripts/run.sh`](../../claude-house-rules/plugins/house-rules/scripts/run.sh) is the one
POSIX-sh file left in the plugin, and its only job is finding a Python interpreter that actually
runs code — it **probes** each candidate (runs it, checks the output) rather than trusting
`command -v`, because on this machine `python3` is the Windows Store App Execution Alias stub:
on PATH, found by `command -v`, but it prints an install nag and exits 0 without running
anything. Trusting PATH membership would silently disable every hook the same way a missing
`node` once did (an earlier, pre-Python version parsed payloads with `node`).

`run.sh` execs
[`scripts/hook.py`](../../claude-house-rules/plugins/house-rules/scripts/hook.py) with the event
name as `argv[1]`; the payload always arrives on stdin
(`hook.py:1-6`). `main()` looks the event up in the `EVENTS` dispatch table
(`hook.py:2034-2046`) and calls the matching handler:

| Event | Handler | Fires on |
|---|---|---|
| `SessionStart` | `event_inject` | every session — prints the rules + machine profile |
| `SessionStart` | `event_standards` | every session — prints applicable per-repo coding standards |
| `UserPromptSubmit` | `event_scope` | every prompt — restates the short rule reminder |
| `PreToolUse` (`Bash`/`PowerShell`) | `event_guard` | before a shell command runs |
| `PreToolUse` (`Write`) | `event_guardwrite` | before a `Write` would replace an existing file's entire contents |
| `PostToolUse` (`Write`/`Edit`) | `event_artifact` | a document written outside the project |
| `PostToolUse` (`Write`) | `event_runnable` | a runnable file just created |
| `PostToolUse` (`Write`/`Edit`) | `event_harvest` | a comment block has grown into an essay |
| `PostToolUse` (`ExitPlanMode`) | `event_delegate` | a plan was just approved |
| `SubagentStart` | `event_announce` | any subagent spawns |
| `SubagentStop` | `event_verdict` | any subagent finishes |
| `Stop` | `event_handover` | a turn ends handing over an untested-looking command |

Full per-handler behavior, including *why* each one is shaped the way it is, is the subject of
[`docs/architecture.md`](../architecture.md) — this doc states what's true now and what breaks it;
that one carries the reasoning and post-mortems, per the [[sixth-documentation-tier]] boundary
between tier 4 and `docs/6-decisions/Decisions.md`.

Every handler is **stateless**: nothing is written to disk between invocations, nothing carries
over between turns. An earlier version enforced the deliver-a-whole-workflow rule with a `Stop`
hook that kept session state in the temp directory; it leaked a file for every session that
ended unexpectedly, and any unrelated shell command silently defeated it. That machinery is gone
on purpose — `verify.py` fails if it reappears.

## Invariants

- **`hook.py` is stdlib-only Python** (`hook.py:8-10`) — no third-party imports, nothing beyond
  CPython 3.8+. `run.sh` is the one POSIX-sh dependency in the whole plugin.
- **Every handler's failure mode is fixed and deliberate** (`hook.py:16-34`, the module
  docstring): `guard` fails **closed** — an unreadable payload or internal error writes to
  stderr and returns `2`, blocking the command (`event_guard`, `hook.py:793-803`); `inject` fails
  **loud, not closed** — a missing rules file still emits a `systemMessage`; `scope` **cannot
  fail** — it never reads a file or raises, because a non-zero exit on `UserPromptSubmit` erases
  the user's prompt; `artifact`/`runnable`/`delegate`/`harvest` never obstruct but never go quiet
  — every failure emits a `systemMessage` and exits 0; `handover`, `announce`, `verdict` fail
  **open and loud** — a `decision: "block"` from any of them would stop a turn or a subagent from
  ever finishing.
- **Nothing fails silently.** `verify.py` enforces this structurally over `hook.py`'s own source:
  no `except` block may return or `pass` without emitting, writing to stderr, or recording the
  problem for its caller. An `except` that *recovers* — assigns a fallback and continues — is not
  the defect; the defect is giving up without saying so. `main()`'s last-resort net
  (`hook.py:2049-2085`) catches anything a handler itself missed and speaks for every event.
- **`guard` reads the branch from `.git/HEAD`, never from `git rev-parse`.** `guard` runs on
  every `Bash`/`PowerShell` call and is the one handler that fails closed, so a subprocess on
  that path is a subprocess that can wedge the user's shell for as long as it hangs (a stale
  index lock, a network filesystem, an AV scan on first exec). Reading one file cannot hang that
  way, and it keeps `guard` working where `git` isn't on `PATH`. `verify.py` fails if
  `branch_ownership()` ever reaches for `subprocess`, `os.popen`, `os.system`, or
  `check_output`.
  <!-- ref:ee0f -->
- **No hook keeps state between invocations** — `verify.py` fails if a dead state file or a
  stray `.sh` hook script reappears, or if anything other than `run.sh` is registered on any
  event.
- **Matching is textual**, not semantic, even where it costs a false positive (`echo "git
  commit"` still prompts) — an extra keypress is cheaper than a missed commit.
- **The `guard` trace decodes the command for display; matching still runs on the raw JSON
  slice.** `_guard_subject` deliberately returns the raw slice with escapes intact, because
  matching against escapes intact is what keeps the patterns honest. Printing that raw slice to
  the user would show `"command": "git status"` rather than `git status`, so `_trace_subject`
  (`hook.py:1006-1014`) decodes a copy for the one-line trace only; the match itself never sees
  the decoded form.
  <!-- ref:361f -->
- **`standards` detects a Unity project opened at its `Assets/` folder, not just at its root.**
  Opening a Unity project directly at `Assets/` is a normal workflow, but `_standards_scan_dirs`
  never sees the sibling `ProjectSettings/`/`*.csproj` markers one level up. `_unity_markers_in_
  parent` (`hook.py:340-349`) checks narrowly — the directory must be named exactly `Assets` and
  its parent must carry a real Unity marker (`ProjectSettings/ProjectVersion.txt`, or another
  Unity-marker file) — so a coincidentally-named `Assets/` folder in a non-Unity repo doesn't
  false-positive. When it matches, detection re-scans from that real project root instead of
  `Assets/`, so a sibling Node service next to `Assets/` is still found too.
  <!-- ref:0d4d -->
- **`guardwrite` treats any `Write` to a file that already exists as a full-file replacement,
  full stop — there is no size threshold or content diff that lets a "small" rewrite through.**
  `Write` always replaces a file's entire contents; there is no partial form. A full rewrite is a
  delete and a recreate wearing a single tool call, whether it goes through `rm` (which `guard`'s
  broadened `rm` pattern also now catches with no flag needed) or through `Write` targeting a path
  that is already on disk. Git being able to recover the old blob afterward does not make the loss
  safe, because nobody reviews the diff line by line before an unattended write ships — which is
  the exact failure this hook exists to catch: a scheduled, unattended task once rewrote a CSS file
  wholesale instead of touching the one rule that needed to change, and the regression sat
  unnoticed until someone found it later. `event_guardwrite` (`hook.py`, after `event_guard`) always
  asks in this case; it cannot know *why* a rewrite is happening, only *that* one is about to, so
  the reason it names is what will be discarded, and the "why" is left to whatever Claude has
  already said in chat, per the rule in `rules/house-rules.md`.
  <!-- ref:bf94 -->

## Traps

- **A shim that finds an interpreter on PATH is not proof it runs code.** The `python3` stub
  above is the concrete example this plugin was built around; `run.sh` probing rather than
  checking `command -v` is the fix, and any future interpreter-selection change that reverts to
  a PATH check reopens this.
- **`guard`'s git-prefix regex had a hole `-C` fell through.** Every git pattern shared a prefix
  meant to skip global options (`git\s+(-[^\s]+\s+)*`); it could match a flag but not a flag's
  *argument*, so `git -C /other/repo commit` consumed `-C `, met `/other/repo`, and never reached
  the subcommand — the pattern matched **nothing**, and the command sailed through unchecked.
  Invisible while the answer was always "prompt anyway"; load-bearing the moment `-C` became
  something that should have *withheld* the branch-ownership exemption. Now a shared `_GIT`
  constant knows which global options take a separate argument.
- **The `harvest` scan is budget-bounded, not size-capped, and the first draft got this
  backwards.** Skipping files over a byte ceiling is a silent failure wearing a performance
  argument — the check just doesn't run, and nobody is told which file it skipped. An O(n²)
  accumulator rebuilding each comment run's line list per line took **22 seconds** on a 4.8 MB
  file, past `hooks.json`'s 10-second timeout, so in practice the harness killed the hook rather
  than the hook reporting anything; fixed, the same file scans in 0.29s. Any future change to the
  harvest scan that reintroduces per-line quadratic work reopens this at the next large file.
- **`verify.py`'s guard/branch cases must use hand-written fixture `.git/HEAD` files, not
  whichever branch the suite happens to be run from.** Once a decision depends on branch
  ownership, a suite that inherits the developer's real branch makes the result a property of
  the checkout: it would pass on `main`, fail on a `claude/…` branch, and agree with neither —
  CI checks out a detached `HEAD`.
- **Every uncertainty in branch ownership resolves to "not mine," never to "assume it's fine."**
  The user's branch, a detached `HEAD`, a directory that isn't a repo, an unreadable `HEAD` all
  fall through to a prompt. A change that adds a new "can't tell" case must route it the same
  way, not default it open.
  <!-- ref:d2a4 -->
