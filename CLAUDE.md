# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal Claude Code plugin repo. It ships one plugin, `house-rules`, which turns aj's global
CLAUDE.md-style rules into a Claude Code plugin so they follow every device and project via hooks
instead of a file that has to be copied around. The plugin is published as a GitHub marketplace
(`.claude-plugin/marketplace.json` at the repo root) and installed with `claude plugin install`.

**This root `CLAUDE.md` is a pointer, not a copy.** The actual rules text lives at
[claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md)
and is injected into every session by the plugin's `SessionStart` hook. Do not paste the rules
back into this file — Claude Code auto-loads every `CLAUDE.md` it finds, so a copy here would load
twice and the two would drift apart unnoticed. `verify.sh` step 32 fails if that happens.

## Commands

All commands run from the repo root.

Run the test suite (proves the hooks match what the docs claim):

```bash
# PowerShell (sh is not on PATH here, so it needs the full path)
& "C:\Program Files\Git\bin\sh.exe" claude-house-rules/plugins/house-rules/scripts/verify.sh
```

```bash
# Git Bash — short form works
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Exit code 0 means every check passed. Each line prints the command tested, expected vs. actual
decision, and PASS/FAIL — read there is what fails, no need to open the script.

Install (or update) the plugin on a device, from PowerShell:

```bash
.\tools\install.ps1
```

Idempotent. Installs via `claude plugin marketplace add` / `claude plugin install`, then sets
`verbose: true` in `~/.claude/settings.json` (a UI setting the plugin itself cannot ship). Use
`-NoVerbose` to skip that part.

Prove the *published* plugin installs cleanly on a fresh machine (strips the local install, backs
up config, reinstalls from GitHub via the two documented CLI commands, then re-runs the
suite against the fresh clone):

```bash
.\tools\clean-install-test.ps1
```

Add `-Force` to skip the `STRIP` confirmation prompt, or `-SkipStrip` to only re-verify what's
currently installed. There is no build step and no linter — this repo is shell scripts and JSON.

## Architecture

### The plugin is seven hooks on five events, nothing else

Defined in [claude-house-rules/plugins/house-rules/hooks/hooks.json](claude-house-rules/plugins/house-rules/hooks/hooks.json),
implemented as POSIX `sh` scripts under `claude-house-rules/plugins/house-rules/scripts/`:

| Hook | Script | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `inject.sh` | every session | Prints `rules/house-rules.md` **and** `rules/environment.md` into context as `additionalContext`. This *is* the CLAUDE.md replacement. |
| `UserPromptSubmit` | `scope.sh` | every prompt | Restates a short reminder so the rules stay live 200 messages into a long session, after the SessionStart copy has faded from attention. |
| `PreToolUse` | `guard.sh` | `Bash`/`PowerShell` calls | Extracts the `command` field and textually matches it against rule patterns (hidden/background work, git history/index/remote writes, destructive deletes and discards). A match returns `permissionDecision: "ask"` — it never blocks outright, only prompts. |
| `PostToolUse` | `artifact.sh` | `Write`/`Edit` calls | Notices a `.md`/`.txt` write outside the project (temp dir, scratchpad, `~/.claude/plans`) and reminds *Claude* — not the user — to copy it into `docs/` before finishing. |
| `Stop` | `handover.sh` | every turn about to end | Blocks the turn **once** with the command-handover checklist: shell named and correct as the fence label, absolute working directory, exact command, expected output, `UNTESTED:` when it was not run. Stands down on the retry (`stop_hook_active`), on `HOUSE_RULES_HANDOVER=off`, and on any failure — it fails **open**, since a non-zero exit here would stop the turn ending at all. |
| `PostToolUse` | `runnable.sh` | `Write` calls only | Notices a runnable file (`.sh`, `.ps1`, `.py`, `Dockerfile`, …) created inside the project and reminds *Claude* to run it before finishing. `Write` only, never `Edit`. |
| `PostToolUse` | `delegate.sh` | `ExitPlanMode` calls | Reminds *Claude* that the plan is settled and implementation should go to `@house-rules:executor`, so execution reaches the Desktop Code tab and cloud sessions too — surfaces where the `opusplan` setting below does nothing. No payload field needed; a bare `printf`, same zero-dependency shape as `scope.sh`. |

### One subagent, for the model split — the primary mechanism, not the fallback

`agents/executor.md` registers `@house-rules:executor`, pinned to `model: sonnet` at
`effort: low`, for running a plan that has already been decided. `delegate.sh` (above) is what
actually asks for that delegation, on `ExitPlanMode`.

**A hook cannot set the model** — no hook output changes it, a `SessionStart` hook may only be
*told* which model is running, and there is no `$CLAUDE_MODEL`. The `"model": "opusplan"`
setting `tools/install.ps1` writes into `~/.claude/settings.json` switches Opus → Sonnet
automatically at the plan-mode boundary, but it is a **CLI/IDE convenience on top of the
subagent, not the primary mechanism** — it does nothing on three surfaces:

- **The Desktop Code tab.** The model dropdown next to the send button is a session-level
  override that outranks `~/.claude/settings.json`'s `model` field entirely, and `opusplan` is
  an alias reachable only via `/model`, `--model`, `ANTHROPIC_MODEL`, or a settings file — the
  dropdown doesn't offer it as a choice.
- **Cloud sessions.** They run on Anthropic-managed VMs and never receive a device's local
  `settings.json`, so the setting simply isn't there to read.
- **Auto and Accept-edits sessions**, on any surface. `opusplan` only switches at the
  plan-mode boundary; a session that never enters plan mode stays on whatever model it started
  on, start to finish.

The subagent is the one thing that reaches all of those, because agent frontmatter is honoured
wherever the plugin is installed. `verify.sh` checks the agent still pins Sonnet, that
`install.ps1` still writes `opusplan` (still correct for the surfaces it does cover), and that
`delegate.sh` is actually wired to `ExitPlanMode` and actually names the executor. It also fails
if the agent sets `hooks`, `mcpServers` or `permissionMode`, which plugin subagents silently
ignore — a field that reads as configuration and does nothing is worse than no field.

**Reaching the surface is not the same as being allowed to spawn on it.** A live Auto-mode
session hit this: `delegate.sh`'s nudge fired after `ExitPlanMode`, the user then typed a plain
"implement the plan", and Claude reasoned its own system prompt forbade calling the Agent tool
without an explicit per-turn ask — so it executed the plan itself, on the planning model,
exactly what this whole mechanism exists to avoid. The Agent tool's own instructions gate
autonomous spawning behind two things: the user explicitly asking, or the target agent's
description saying to use it proactively. `delegate.sh` asking Claude to delegate satisfies
neither on its own — it's Claude prompting Claude, not the user. The fix is that
`agents/executor.md`'s description now says "Use PROACTIVELY", the literal phrase the harness
checks for, so the gate is satisfied before the nudge is even read. `verify.sh` greps the
description for that word for the same reason it checks everything else here: reading well is
not the same as still being true.

Every one of those scripts is stateless. Nothing writes to `$TEMP`, and there is no state to
reap. That is load-bearing, not incidental — see the deliverable note below.

The table above is checked against `hooks.json` by `verify.sh`: a script registered as a hook
but missing from this table, or listed here but not registered, fails the suite. This section
cannot silently go stale the way it did once already.

### Design constraints that shape every script here

- **No runtime dependency beyond `sh`, `grep`, `sed`, `awk`.** No node, no jq, no python. An
  earlier version parsed hook JSON with node; a missing node made the guard exit clean and let
  every command through unchecked. The fix was to stop parsing and match text with `grep`
  instead — it over-triggers (a command that genuinely *mentions* a tripwire word also prompts)
  but it cannot silently go dark. Any new hook logic must preserve this: match text with `grep`,
  don't parse JSON.
- **Each hook's failure mode is deliberate and matches what that hook event allows:**
  - `guard.sh` **fails closed, loudly** (`PreToolUse` can block) — missing `grep` or an unreadable
    payload writes to stderr and exits 2, so the command does not run.
  - `inject.sh` **fails loud, not closed** — a missing rules file still emits a `systemMessage`
    saying so, since there's nothing to block.
  - `scope.sh` **cannot fail at all, by construction** — on `UserPromptSubmit` a non-zero exit
    *erases the user's prompt*, so this hook has zero dependencies: one `printf` of a hardcoded
    string, no file read, no subprocess. Its text is therefore a second copy of a few rule
    phrases; `verify.sh` checks it hasn't drifted from `house-rules.md`. `runnable.sh`'s
    reminder text is pinned the same way, for the same reason.
  - `artifact.sh` and `runnable.sh` **never obstruct** — `PostToolUse` can't block anyway (the
    write already happened); a missing `grep` just means the reminder is offline, reported via
    `systemMessage`.
- **Every hook extracts the one field it cares about**, rather than grepping the whole payload.
  `artifact.sh` and `runnable.sh` read `file_path`, so a file whose *contents* mention `/tmp`
  doesn't false-trigger on every save. `guard.sh` reads `command`, so a call *described* as
  "check for uncommitted changes before we commit" doesn't prompt on the word commit. Matching
  stays deliberately broad *within* the extracted field — over-triggering there is cheap.
- **`guard.sh`'s three-tier ladder is the shape to preserve** if you touch its input handling.
  Unreadable payload or missing `grep` → stderr and `exit 2`, blocking. Payload readable but no
  `command` field → fall back to matching the whole payload, exactly as it behaved before the
  extraction existed. Field found → match that alone. The middle tier is what keeps a tool whose
  input field is named something else from being either waved through *or* blocked outright.
- **No hook keeps state between invocations.** What is banned is the state, not the `Stop`
  event: `handover.sh` runs there and stores nothing, because the one fact it needs — has it
  already fired this turn — is held by the harness and arrives in the payload as
  `stop_hook_active`. `verify.sh` was narrowed to match (it used to fail on any `Stop` hook at
  all, a proxy that outlawed the only event where the handover rule is enforceable); it now
  fails if the dead scripts or the state file return, or if anything other than `handover.sh`
  is registered on `Stop`. An earlier design enforced "deliver a whole
  workflow" with three scripts and a `Stop` hook: one recorded written files under `$TEMP`, one
  cleared that record when any shell command ran, one blocked `Stop` if the record survived. It
  leaked a state file forever whenever a session ended without `Stop` firing, it broke the
  plugin's own "artifacts never live in a temp directory" rule, and any unrelated `ls` defeated
  it. All of that bought only "don't nag twice". `runnable.sh` is the reminder with no memory;
  `verify.sh` fails if any of the machinery reappears.
- **`verify.sh` is the source of truth for "does this actually work"**, not the README. It feeds
  real hook payloads through the scripts and asserts on the JSON decision returned. When adding a
  rule with a shell signature, add both a `guard.sh` pattern and a `verify.sh` case in the same
  change — untested rule text has no effect. It computes its own check count at runtime; don't
  write that number down anywhere, it will drift.

### The machine profile is data, not code

[claude-house-rules/plugins/house-rules/rules/environment.md](claude-house-rules/plugins/house-rules/rules/environment.md)
records the actual discovered machine (OS, shells, hardware, what's really on PATH) rather than
assuming Windows-11-defaults. `inject.sh` injects it alongside the rules; if it's missing, the
injection says `NOT RECORDED YET` and instructs the session to discover and record facts rather
than guess. The one trap already caught here: **`sh`/`bash` are not on PATH** even though Git for
Windows is installed — only `C:\Program Files\Git\cmd` (holding `git.exe`) is on PATH, so shell
scripts must be invoked by full path (`C:\Program Files\Git\bin\sh.exe`) from PowerShell, and only
work in short form (`sh script.sh`) from inside a Git Bash window.

### Where things live, and why

- **`.claude-plugin/marketplace.json`** must stay at the **repo root** — that's where
  `claude plugin marketplace add` looks. Its plugin entries are paths relative to the repo root
  (currently one: `./claude-house-rules/plugins/house-rules`). Any future plugin in this repo is
  another entry in this same list, not a new marketplace file.
- **`claude-house-rules/plugins/house-rules/`** is the plugin itself — everything under it is what
  gets published and installed on another machine. Treat its `rules/*.md` as the only real copies
  of that text; everything else referencing the rules (this file, `scope.sh`'s hardcoded string)
  is a pointer or a restatement, checked for drift by `verify.sh`.
- **`docs/plans/`** holds implementation plans as real, committed files — per the rules
  themselves, artifacts never live only in a chat transcript or a temp directory.
- **`tools/`** holds device-setup and release-verification scripts, not plugin code — nothing here
  ships to an installed copy of the plugin.

### Editing the rules

Edit only [claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md).
If the new rule has a shell signature, add a matching pattern to `guard.sh` and a case to
`verify.sh`. If you reword a phrase that `scope.sh` also states, update `scope.sh` too —
`verify.sh` step 31 will fail otherwise. Run the verify command above before considering an edit
done; it's the only thing that proves a rule change actually took effect versus just reading well.
