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
twice and the two would drift apart unnoticed. `verify.py`'s CLAUDE.md-duplication check fails if
that happens.

## Commands

All commands run from the repo root.

Run the test suite (proves the hooks match what the docs claim):

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Works the same from PowerShell or Git Bash — it is plain Python, not a shell script, so there is
no full-path/short-form split to remember. Exit code 0 means every check passed. Each line prints
the case tested, expected vs. actual decision, and PASS/FAIL — read there is what fails, no need
to open the script.

Install (or update) the plugin on a device — `tools/bootstrap.ps1` (PowerShell) or
`tools/bootstrap.sh` (any POSIX shell) probes for a working Python the same way `run.sh` does,
then hands off to `tools/install.py`, where the real logic lives:

```bash
.\tools\bootstrap.ps1
```

Idempotent. Installs via `claude plugin marketplace add` / `claude plugin install`, then sets
`verbose: true` and `model: opusplan` in `~/.claude/settings.json` (settings the plugin itself
cannot ship). Pass `--no-verbose` / `--no-model` to skip a piece.

Prove the *published* plugin installs cleanly on a fresh machine (strips the local install, backs
up config, reinstalls from GitHub via the two documented CLI commands, then re-runs the suite
against the fresh clone):

```bash
python tools/clean_install_test.py
```

Pass `--force` to skip the `STRIP` confirmation prompt, or `--skip-strip` to only re-verify what's
currently installed. There is no build step and no linter — this repo is Python scripts, one
POSIX-sh shim (`run.sh`), and JSON.

## Architecture

### The plugin is one POSIX shim plus one Python file, dispatched by event

Defined in [claude-house-rules/plugins/house-rules/hooks/hooks.json](claude-house-rules/plugins/house-rules/hooks/hooks.json),
every hook command is `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`. `run.sh` resolves a
working Python interpreter and execs
[scripts/hook.py](claude-house-rules/plugins/house-rules/scripts/hook.py) with that event name;
every handler lives in that one file.

| Hook event | `run.sh` arg | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `inject` | every session | Prints `rules/house-rules.md` **and** the machine profile into context as `additionalContext`. This *is* the CLAUDE.md replacement. |
| `SessionStart` | `standards` | every session | Second entry on the same event, so a detection failure here can never take down the rules injection above. Selects and prints the coding standards docs from `rules/standards/` that apply to the repo it's sitting in — always `coding-philosophy.md`, plus `csharp-unity-standards.md` and/or `web-js-ts-node-standards.md` when their markers are detected across the repo root and one level of subdirectories, or an explicit `.claude/standards` override. Also catches the project root itself being a Unity project's `Assets/` folder (a normal way to open a Unity project) by checking one level *up* for `ProjectSettings/`/`*.csproj` when the root's directory name is exactly `Assets` — when that's true, detection re-scans from that real project root instead of `Assets/`, so a sibling Node service next to `Assets/` (not just the Unity markers) is still found. |
| `UserPromptSubmit` | `scope` | every prompt | Restates a short reminder so the rules stay live 200 messages into a long session, after the SessionStart copy has faded from attention. |
| `PreToolUse` | `guard` | `Bash`/`PowerShell` calls | Extracts the `command` field and textually matches it against rule patterns (hidden/background work, git history/index/remote writes, destructive deletes and discards). A match returns `permissionDecision: "ask"` — it never blocks outright, only prompts. |
| `PostToolUse` | `artifact` | `Write`/`Edit` calls | Notices a `.md`/`.txt` write outside the project (temp dir, scratchpad, `~/.claude/plans`) and reminds *Claude* — not the user — to copy it into `docs/` before finishing. |
| `Stop` | `handover` | every turn about to end | Blocks the turn **once** with the command-handover checklist: how the user gets there (folder as an absolute path, plus opening a prompt in it), shell named and correct as the fence label, exact command, expected output, `UNTESTED:` when it was not run, and one numbered step per action once there is more than one command. Stands down on the retry (`stop_hook_active`), on `HOUSE_RULES_HANDOVER=off`, and on any failure — it fails **open**, since a non-zero exit here would stop the turn ending at all. |
| `PostToolUse` | `runnable` | `Write` calls only | Notices a runnable file (`.sh`, `.ps1`, `.py`, `Dockerfile`, …) created inside the project and reminds *Claude* to run it before finishing. `Write` only, never `Edit`. |
| `PostToolUse` | `delegate` | `ExitPlanMode` calls | The plan just got approved, so the deliberation is over: reminds *Claude* to hand the implementation to `@house-rules:executor` instead of running it on the planning model. No dependencies, no payload read. |

### Why a shim in front of the Python file, rather than calling `hook.py` directly

`hooks.json` cannot itself probe for an interpreter, and `python`/`python3`/`py` availability
and naming varies by OS — worse, on this machine `python3` is the Windows Store App Execution
Alias stub: on PATH, found by `command -v`, but it prints an install nag to stdout and exits 0
instead of running anything. Trusting `command -v` would silently disable every hook the same
way a missing `node` once did. `run.sh` **probes** each candidate — actually runs it and checks
the output — rather than trusting that being on PATH means it works. See `run.sh`'s own
comments for the full resolution order and each event's fallback behaviour when no interpreter
probes successfully.

### One subagent, for the model split — the primary mechanism, not the fallback

`agents/executor.md` registers `@house-rules:executor`, pinned to `model: sonnet` at
`effort: low`, for running a plan that has already been decided. The `delegate` handler (above)
is what actually asks for that delegation, on `ExitPlanMode`.

**A hook cannot set the model** — no hook output changes it, a `SessionStart` hook may only be
*told* which model is running, and there is no `$CLAUDE_MODEL`. So the split rests on two things
outside the hooks, and neither belongs in `hook.py`'s guard handler. **The subagent is the
primary one; the setting is a CLI convenience on top.**

- **`agents/executor.md`'s frontmatter works on every surface.** Agent definitions ship with the
  plugin, so `@house-rules:executor` runs on Sonnet wherever the plugin is installed — terminal,
  IDE, desktop Code tab, cloud session. It only helps if something asks for the delegation,
  which is what the `delegate` handler and the delegation rule in `house-rules.md` now do.
- **`"model": "opusplan"` in `~/.claude/settings.json` covers the CLI and the IDE only**, and
  only at the plan-mode boundary. Three separate reasons it does nothing in the desktop app's
  **Code** tab: the model there comes from the picker next to the send button, which is a
  session-level selection and outranks the `model` field in any settings file (the desktop docs
  map both `--model` and `ANTHROPIC_MODEL` to that dropdown); `opusplan` is an alias, not a
  model, so it is not in the picker at all; and cloud sessions run on managed VMs that never
  receive a settings file deployed to the device, which is the only place `tools/install.py`
  can write. Auto and accept-edits sessions miss it for a fourth reason that applies even in the
  CLI — they never enter plan mode, so the one boundary `opusplan` switches at is never crossed.

`verify.py` checks all of it: the agent still pins Sonnet, `install.py` still writes
`opusplan`, the `delegate` handler is still registered on `ExitPlanMode` and still names the
same agent the rules name, and the docs still say the setting covers only the CLI and the IDE —
asserting the setting exists is not asserting the split works, which is exactly how this went
unnoticed once already. It also fails if the agent sets `hooks`, `mcpServers` or
`permissionMode`, which plugin subagents silently ignore — a field that reads as configuration
and does nothing is worse than no field.

Every handler is stateless. Nothing writes to `$TEMP`, and there is no state to reap. That is
load-bearing, not incidental — see the deliverable note below.

The table above is checked against `hooks.json` by `verify.py`: an event registered as a hook
but missing from this table, or listed here but not registered, fails the suite. This section
cannot silently go stale the way it did once already.

### Design constraints that shape `hook.py` and `run.sh`

- **`hook.py` is stdlib-only Python.** No third-party imports, no pip install, nothing beyond
  what ships with CPython 3.8+. `run.sh` is the one POSIX-sh dependency left in the whole
  plugin, and its only job is finding a working interpreter — it does no rule matching itself.
- **Each handler's failure mode is deliberate and matches what that hook event allows:**
  - `guard` **fails closed, loudly** (`PreToolUse` can block) — an unreadable payload or any
    internal error writes to stderr and exits 2, so the command does not run. `run.sh` extends
    this all the way down: no working interpreter at all is also a blocking failure for `guard`.
  - `inject` **fails loud, not closed** — a missing/unreadable rules file still emits a
    `systemMessage`, since there's nothing to block. `run.sh` does the same when no interpreter
    can be found at all.
  - `scope` **cannot fail at all, by construction** — on `UserPromptSubmit` a non-zero exit
    *erases the user's prompt*, so this handler is one fixed string, no file read, no
    subprocess. Its text is therefore a second copy of a few rule phrases; `verify.py` checks it
    hasn't drifted from `house-rules.md`. `runnable`'s reminder text is pinned the same way, for
    the same reason.
  - `artifact` and `runnable` **never obstruct** — `PostToolUse` can't block anyway (the write
    already happened); any internal error just means the reminder is offline, reported via
    `systemMessage`.
- **Every handler extracts the one field it cares about**, rather than matching the whole
  payload. `artifact` and `runnable` read `file_path`, so a file whose *contents* mention `/tmp`
  doesn't false-trigger on every save. `guard` reads `command`, so a call *described* as
  "check for uncommitted changes before we commit" doesn't prompt on the word commit. Matching
  stays deliberately broad *within* the extracted field — over-triggering there is cheap.
- **`guard`'s three-tier ladder is the shape to preserve** if you touch its input handling.
  Unreadable payload or any internal error → stderr and `exit 2`, blocking. Payload readable but
  no `command` field → fall back to matching the whole payload, exactly as it behaved before the
  extraction existed. Field found → match that alone. The middle tier is what keeps a tool whose
  input field is named something else from being either waved through *or* blocked outright.
- **No hook keeps state between invocations.** What is banned is the state, not the `Stop`
  event: `handover` runs there and stores nothing, because the one fact it needs — has it
  already fired this turn — is held by the harness and arrives in the payload as
  `stop_hook_active`. `verify.py` fails if the dead scripts, the state file, or a stray `.sh`
  hook script return, or if anything other than `run.sh` is registered on any event. An earlier
  design enforced "deliver a whole workflow" with three scripts and a `Stop` hook: one recorded
  written files under `$TEMP`, one cleared that record when any shell command ran, one blocked
  `Stop` if the record survived. It leaked a state file forever whenever a session ended without
  `Stop` firing, it broke the plugin's own "artifacts never live in a temp directory" rule, and
  any unrelated `ls` defeated it. All of that bought only "don't nag twice". `runnable` is the
  reminder with no memory; `verify.py` fails if any of the machinery reappears.
- **`verify.py` is the source of truth for "does this actually work"**, not the README. It feeds
  real hook payloads through `hook.py` and asserts on the JSON decision returned. When adding a
  rule with a shell signature, add both a `guard` pattern and a `verify.py` case in the same
  change — untested rule text has no effect. It computes its own check count at runtime; don't
  write that number down anywhere, it will drift.

### The machine profile is data, not code, and is not committed

`claude-house-rules/plugins/house-rules/rules/environment.md` is machine-local and **gitignored**
— each device records its own, and it never ships with the plugin. `inject` reads it alongside
the rules; if it's missing (a fresh clone, always), `inject` falls back to live runtime
detection (`hook.py`'s `_detect_environment`: OS, Python, and whether `git`/`sh`/`bash`/`pwsh`/
`powershell`/`node`/`npm` are on PATH) rather than a static "go find out" message or a Windows-11
default. A hand-written `rules/environment.md` still wins when present — runtime detection
cannot know RAM, GPU, or CRLF config, only a human recording it can. A worked example, including
the `sh`/`bash`-not-on-PATH trap discovered on this machine, is preserved at
[docs/example-environment.md](docs/example-environment.md).

### Where things live, and why

- **`.claude-plugin/marketplace.json`** must stay at the **repo root** — that's where
  `claude plugin marketplace add` looks. Its plugin entries are paths relative to the repo root
  (currently one: `./claude-house-rules/plugins/house-rules`). Any future plugin in this repo is
  another entry in this same list, not a new marketplace file.
- **`claude-house-rules/plugins/house-rules/`** is the plugin itself — everything under it is what
  gets published and installed on another machine. Treat its `rules/house-rules.md` as the only
  real copy of that text; everything else referencing the rules (this file, `hook.py`'s hardcoded
  reminder strings) is a pointer or a restatement, checked for drift by `verify.py`.
- **`claude-house-rules/plugins/house-rules/output-styles/`** and **`templates/`** hold the
  opt-in `handover-cards` output style and `step-card.html`, the page form of the step card.
  `step-card.html` is self-contained by rule — no external script, stylesheet, font or fetch —
  because a machine mid-install may not have a network, and `verify.py` fails if one appears.
  Claude fills its `STEPS` array and changes nothing else.
- **`docs/claude-ai-instructions.md`** is the chat-surface half: the text to paste into
  claude.ai → Settings → Instructions, which is the only mechanism that reaches plain chat and
  the phone. Committed so it can be diffed against the rules rather than silently drifting.
- **`docs/plans/`** holds implementation plans as real, committed files — per the rules
  themselves, artifacts never live only in a chat transcript or a temp directory.
- **`tools/`** holds device-setup and release-verification scripts, not plugin code — nothing here
  ships to an installed copy of the plugin.
- **`claude-house-rules/plugins/house-rules/rules/standards/`** holds the vendored per-ecosystem
  coding standards docs (`coding-philosophy.md`, `csharp-unity-standards.md`,
  `web-js-ts-node-standards.md`), **committed** — unlike `rules/environment.md`, these must ship
  with the plugin and arrive on a fresh clone. They are vendored copies, not a git submodule:
  `claude plugin install` does not recurse submodules, so the directory would be empty on every
  fresh machine and in every cloud session. `Ajw2003/Coding-Standards` stays the place the
  documents are authored; `tools/sync_standards.py` pulls it and copies the changes in, so the
  vendored copies are provably current rather than hopefully current. A repo names its own set
  in **`.claude/standards`** (one document stem per line) when the `standards` hook's detection
  gets it wrong or a project's needs differ from what got detected — that file, not the vendored
  docs, is the thing worth gitignoring per-project if it's local-only.

### The step-card handover format, and which surfaces it actually reaches

Steps the user has to run are handed over in one fixed shape — the step card — defined in
`rules/house-rules.md` under `#### The card` and injected into every session by `inject`. The
format deliberately uses only `---`, `###`, `**bold**`, plain paragraphs and top-level fenced
blocks: that is the set that survives every renderer this reaches. Box-drawing borders, a fence
inside a blockquote, a command in a table, and a fence nested in a list item are all banned, each
because it breaks in at least one of them. Do not paste the template into this file — it lives in
`house-rules.md` and `verify.py` fails on a second copy here.

The comparison that prompted it — claude.ai chat's interactive step widget — cannot be
reproduced. It is the **custom visuals** feature: model-discretion, beta, no documented emission
format, and it does not render on iOS or Android at all. What is reachable:

| Surface | Interactive card | Markdown card | How it gets there |
|---|---|---|---|
| Claude Code — CLI | published page, 4+ steps or on request | yes | `inject` + `scope` + `handover` |
| Claude Code — IDE extension | inherits the CLI; not separately documented | yes | same |
| Claude Code — Desktop **Code** tab | published page, 4+ steps or on request | yes | same |
| Claude Code — web / cloud session | publishing undocumented; treat as unavailable | yes | ships with the repo install; cloud never reads `~/.claude/settings.json` |
| claude.ai chat — web / desktop | sometimes, model's discretion, unrequestable | yes | [docs/claude-ai-instructions.md](docs/claude-ai-instructions.md) |
| claude.ai chat — iOS / Android | **never** | yes | same |

The markdown card is the only row that is yes everywhere, which is why it is the load-bearing
deliverable and the published page is an escalation. The page is always additive: the inline card
is written first and in full, and if publishing fails or is unavailable the reply still stands on
its own.

### Why the output style is shipped un-forced

`output-styles/handover-cards.md` restates the card format, and deliberately does **not** set
`force-for-plugin: true`. Only one output style is active at a time, so forcing one silently
displaces whatever style the user selected — and since this plugin is installed globally on every
device by design, that override would be permanent, in every repo, with no way to keep the rules
while dropping the style. The plugin already owns the system-prompt region at `SessionStart` and
restates the rules on every prompt via `scope`, so forcing the slot buys little. Output styles
also apply to the main conversation only — a subagent runs its own system prompt, so
`@house-rules:executor` is governed by the injected rules, not by that file. `verify.py` asserts
the field is **absent**, the same way it asserts `executor.md` sets no field subagents ignore: the
decision is the thing under test, not the file's existence.

### Editing the rules

Edit only [claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md).
If the new rule has a shell signature, add a matching pattern to `hook.py`'s `guard` handler and
a case to `verify.py`. If you reword a phrase that `hook.py`'s `scope`/`runnable`/`delegate`/
`handover` handlers also state, update the matching hardcoded string in `hook.py` too —
`verify.py`'s drift checks will fail otherwise. Run the verify command above before considering
an edit done; it's the only thing that proves a rule change actually took effect versus just
reading well.
