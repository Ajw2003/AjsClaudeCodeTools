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

Run the 34-check test suite (proves the hooks match what the docs claim):

```bash
# PowerShell (sh is not on PATH here, so it needs the full path)
& "C:\Program Files\Git\bin\sh.exe" claude-house-rules/plugins/house-rules/scripts/verify.sh
```

```bash
# Git Bash — short form works
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Exit code 0 means all 34 checks passed. Each line prints the command tested, expected vs. actual
decision, and PASS/FAIL — read there is what fails, no need to open the script.

Install (or update) the plugin on a device, from PowerShell:

```bash
.\tools\install.ps1
```

Idempotent. Installs via `claude plugin marketplace add` / `claude plugin install`, then sets
`verbose: true` in `~/.claude/settings.json` (a UI setting the plugin itself cannot ship). Use
`-NoVerbose` to skip that part.

Prove the *published* plugin installs cleanly on a fresh machine (strips the local install, backs
up config, reinstalls from GitHub via the two documented CLI commands, then re-runs the 34-check
suite against the fresh clone):

```bash
.\tools\clean-install-test.ps1
```

Add `-Force` to skip the `STRIP` confirmation prompt, or `-SkipStrip` to only re-verify what's
currently installed. There is no build step and no linter — this repo is shell scripts and JSON.

## Architecture

### The plugin is four hooks, nothing else

Defined in [claude-house-rules/plugins/house-rules/hooks/hooks.json](claude-house-rules/plugins/house-rules/hooks/hooks.json),
implemented as POSIX `sh` scripts under `claude-house-rules/plugins/house-rules/scripts/`:

| Hook | Script | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `inject.sh` | every session | Prints `rules/house-rules.md` **and** `rules/environment.md` into context as `additionalContext`. This *is* the CLAUDE.md replacement. |
| `UserPromptSubmit` | `scope.sh` | every prompt | Restates a short reminder so the rules stay live 200 messages into a long session, after the SessionStart copy has faded from attention. |
| `PreToolUse` | `guard.sh` | `Bash`/`PowerShell` calls | Textually matches the pending command against rule patterns (hidden/background work, git mutations, destructive deletes). A match returns `permissionDecision: "ask"` — it never blocks outright, only prompts. |
| `PostToolUse` | `artifact.sh` | `Write`/`Edit` calls | Notices a `.md`/`.txt` write outside the project (temp dir, scratchpad, `~/.claude/plans`) and reminds *Claude* — not the user — to copy it into `docs/` before finishing. |

### Design constraints that shape every script here

- **No runtime dependency beyond `sh`, `grep`, `sed`, `awk`.** No node, no jq, no python. An
  earlier version parsed hook JSON with node; a missing node made the guard exit clean and let
  every command through unchecked. The fix was to stop parsing and match raw payload text
  instead — it over-triggers (a command that merely *mentions* a tripwire word also prompts) but
  it cannot silently go dark. Any new hook logic must preserve this: match text, don't parse JSON.
- **Each hook's failure mode is deliberate and matches what that hook event allows:**
  - `guard.sh` **fails closed, loudly** (`PreToolUse` can block) — missing `grep` or an unreadable
    payload writes to stderr and exits 2, so the command does not run.
  - `inject.sh` **fails loud, not closed** — a missing rules file still emits a `systemMessage`
    saying so, since there's nothing to block.
  - `scope.sh` **cannot fail at all, by construction** — on `UserPromptSubmit` a non-zero exit
    *erases the user's prompt*, so this hook has zero dependencies: one `printf` of a hardcoded
    string, no file read, no subprocess. Its text is therefore a second copy of a few rule
    phrases; `verify.sh` step 31 checks it hasn't drifted from `house-rules.md`.
  - `artifact.sh` **never obstructs** — `PostToolUse` can't block anyway (the write already
    happened); a missing `grep` just means the reminder is offline, reported via `systemMessage`.
- **`artifact.sh` matches narrowly on purpose**, extracting only the `file_path` field with
  `grep -o` rather than grepping the whole payload the way `guard.sh` does — otherwise a file
  whose *contents* mention `/tmp` would false-trigger on every save. Keep that distinction if you
  touch it: `guard.sh` is deliberately broad (over-triggering is cheap), `artifact.sh` is
  deliberately narrow (its output goes straight into Claude's next action, not a user prompt).
- **`verify.sh` is the source of truth for "does this actually work"**, not the README. It feeds
  real hook payloads through the scripts and asserts on the JSON decision returned. When adding a
  rule with a shell signature, add both a `guard.sh` pattern and a `verify.sh` case in the same
  change — untested rule text has no effect.

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
