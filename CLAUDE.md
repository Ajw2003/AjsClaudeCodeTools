# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal Claude Code plugin repo. It ships two plugins from one marketplace
(`.claude-plugin/marketplace.json` at the repo root), both installed with `claude plugin install`:

- **`house-rules`** turns aj's global CLAUDE.md-style rules into a Claude Code plugin so they
  follow every device and project via hooks instead of a file that has to be copied around.
- **`house-style`** does the same for the *look*: one pinned theme - fonts, colour, shape and
  prose voice - injected into every session, so visual work is built on a look that was chosen
  rather than one the model invented that turn.

**This root `CLAUDE.md` is a pointer, not a copy.** The actual rules text lives at
[claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md)
and is injected into every session by the plugin's `SessionStart` hook. Do not paste the rules
back into this file — Claude Code auto-loads every `CLAUDE.md` it finds, so a copy here would load
twice and the two would drift apart unnoticed. `verify.py`'s CLAUDE.md-duplication check fails if
that happens.

For the long-form rationale behind the constraints below — why the shim exists, why the output
style was forced then reversed, why the old state machinery was removed, where each file lives
and why — see [docs/architecture.md](docs/architecture.md). This file stays short on purpose: it
is auto-loaded every session and re-paid on every subagent spawn.

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
cannot ship, and which cover only the CLI and the IDE — see docs/architecture.md). Pass
`--no-verbose` / `--no-model` to skip a piece.

Prove the *published* plugin installs cleanly on a fresh machine (strips the local install, backs
up config, reinstalls from GitHub via the two documented CLI commands, then re-runs the suite
against the fresh clone):

```bash
python tools/clean_install_test.py
```

Pass `--force` to skip the `STRIP` confirmation prompt, or `--skip-strip` to only re-verify what's
currently installed. There is no build step and no linter — this repo is Python scripts, one
POSIX-sh shim (`run.sh`), and JSON.

Run the house-style suite (proves the themes are valid and varied, and the hooks decide
correctly). It needs no network - a suite that did would fail on exactly the machines the
offline fallback exists for:

```bash
python claude-house-rules/plugins/house-style/scripts/verify_style.py
```

Show, choose or pin the theme. `list` is the terminal picker, `gallery` writes the visual one:

```bash
python claude-house-rules/plugins/house-style/scripts/style.py list
python claude-house-rules/plugins/house-style/scripts/style.py use ledger
python claude-house-rules/plugins/house-style/scripts/style.py css signal
```

Measure what the *installed* plugin costs in tokens — the per-prompt `scope` split replayed
against your real transcripts, the per-session injection, and the failure paths that must never
exit non-zero:

```bash
python tools/measure_footprint.py
```

Reads the installed copy out of the plugin cache, not this repo, because those two can disagree;
pass `--repo` to measure the working tree before installing it. `verify.py` proves the hooks are
correct, this proves they are cheap — see [docs/measuring-footprint.md](docs/measuring-footprint.md).

## Architecture

### The plugin is one POSIX shim plus one Python file, dispatched by event

Defined in [claude-house-rules/plugins/house-rules/hooks/hooks.json](claude-house-rules/plugins/house-rules/hooks/hooks.json),
every hook command is `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`. `run.sh` resolves a
working Python interpreter and execs
[scripts/hook.py](claude-house-rules/plugins/house-rules/scripts/hook.py) with that event name;
every handler lives in that one file. Why a shim rather than calling `hook.py` directly, and how
`run.sh` probes for a working interpreter: see docs/architecture.md.

| Hook event | `run.sh` arg | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `inject` | every session | Prints `rules/house-rules.md` **and** the machine profile into context as `additionalContext`. This *is* the CLAUDE.md replacement. |
| `SessionStart` | `standards` | every session | Second entry on the same event, so a detection failure here can never take down the rules injection above. Selects and prints the coding standards docs from `rules/standards/` that apply to the repo it's sitting in — always `coding-philosophy.md`, plus `csharp-unity-standards.md` and/or `web-js-ts-node-standards.md` when their markers are detected across the repo root and one level of subdirectories, or an explicit `.claude/standards` override. Also catches the project root itself being a Unity project's `Assets/` folder (a normal way to open a Unity project) by checking one level *up* for `ProjectSettings/`/`*.csproj` when the root's directory name is exactly `Assets` — when that's true, detection re-scans from that real project root instead of `Assets/`, so a sibling Node service next to `Assets/` (not just the Unity markers) is still found. |
| `UserPromptSubmit` | `scope` | every prompt | Restates a short reminder so the rules stay live 200 messages into a long session, after the SessionStart copy has faded from attention. Emits a short pointer form by default and the full form only when the prompt looks command/file/build-shaped, gated statelessly on the payload's `prompt` field — every failure path falls back to the short form and exits 0, since a non-zero exit here erases the user's prompt. |
| `PreToolUse` | `guard` | `Bash`/`PowerShell` calls | Extracts the `command` field and textually matches it against rule patterns (hidden/background work, git history/index/remote writes, destructive deletes and discards). A match returns `permissionDecision: "ask"` — it never blocks outright, only prompts. |
| `PostToolUse` | `artifact` | `Write`/`Edit` calls | Notices a document write outside the project (temp dir, scratchpad, `~/.claude/plans`) and reminds *Claude* — not the user — to copy it into `docs/` before finishing. The extension list is every form a deliverable arrives as — `md`, `txt`, `html`, `csv`, `json`, `svg`, `pdf` — not the `md`/`txt` it shipped with: the rule says *every* artifact, and a narrower pattern let an `.html` report sit in the scratchpad unnoticed. Runnable extensions stay out; `runnable` owns those. |
| `Stop` | `handover` | a turn about to end **whose reply hands over a command and is not already in card shape** | Reads `last_assistant_message` — the documented field for the just-written reply — and stays silent when there is no fence, since no fence means no command was handed over and the check would only be noise the user has to watch Claude answer. It also stays silent when the reply already carries the card markers (`---`, `###`, `You should see:`), because firing on a compliant reply cannot end quietly — the turn continues, `suppressOutput` has no effect, and the only thing left to say is that nothing needed saying, which is exactly the *a card never announces its own compliance* rule being broken by the hook that enforces it. The cost is deliberate: a card-shaped reply missing a field now passes unchecked, traded for removing a defect that was visible on every correct handover. When it does fire it emits `hookSpecificOutput.additionalContext`, not `decision: "block"`: both continue the turn under the same loop protections, but the former is labelled *Stop hook feedback* rather than raising a hook error, and this is guidance working as designed. A payload with no `last_assistant_message` (an older CLI) still fires, so a version difference cannot silently disable it. The checklist: how the user gets there (folder as an absolute path, plus opening a prompt in it), shell named and correct as the fence label, exact command, expected output, `UNTESTED:` when it was not run, and one numbered step per action once there is more than one command. Stands down on the retry (`stop_hook_active`), on `HOUSE_RULES_HANDOVER=off`, and on any failure — it fails **open**, since a non-zero exit here would stop the turn ending at all. |
| `PostToolUse` | `runnable` | `Write` calls only | Notices a runnable file (`.sh`, `.ps1`, `.py`, `Dockerfile`, …) created inside the project and reminds *Claude* to run it before finishing. `Write` only, never `Edit`. |
| `PostToolUse` | `delegate` | `ExitPlanMode` calls | The plan just got approved, so the deliberation is over: reminds *Claude* to hand the implementation to `@house-rules:executor`, naming the plan's file path (the `ExitPlanMode` payload carries the plan as inline text, not a path, so this is on Claude to supply), instead of running it on the planning model. Trivial work (one file, a handful of steps or fewer) is done inline instead. |

The table above is checked against `hooks.json` by `verify.py`: an event registered as a hook but
missing from this table, or listed here but not registered, fails the suite. Why one subagent is
the primary mechanism for the model split (and why `opusplan` alone is not enough): see
docs/architecture.md.

### The second plugin: `house-style`

`claude-house-rules/plugins/house-style/` is built to the same shape - one `run.sh` shim, one
stdlib-only Python file (`scripts/style.py`), dispatched by event - and has its own suite,
`scripts/verify_style.py`. A theme is a JSON file in `themes/`; `themes/schema.md` is the
contract. Three ship: **Quarry** (warm editorial serif, and the fallback, because it is the
palette `step-card.html` already uses), **Ledger** (dense cool technical), **Signal**
(dark-first display).

| Hook event | `run.sh` arg | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `style` | every session | Resolves the active theme (`./.claude/style.json` → `~/.claude/house-style/active.json` → the fallback, checked fresh each call, nothing stored) and injects its tokens, its alternates, and its **prose voice** - the half that is not CSS, and the reason switching theme changes what gets written and not only how it looks. Fails loud, not closed. |
| `PreToolUse` | `styleguard` | `Artifact` calls | Reads the page about to be published. Carries a known `/* house-style: <name> */` marker → **silent**. No marker, or an unknown one → `permissionDecision: "ask"` naming the active theme and its alternates. Fails **closed** (exit 2) on a payload it cannot read at all, on the same three-tier ladder `guard` uses: parses and names a file → judge it; does not parse but a `file_path` is extractable → judge that; neither → block. |
| `PostToolUse` | `styled` | `Write` calls | An unthemed `.html`/`.svg`/`.css` written *inside* the project reminds Claude to render the tokens in and stamp the marker. Scratch paths are skipped - `house-rules`' `artifact` hook already owns the question of whether those belong in the project at all. Never obstructs. |

`verify_style.py` checks this table against `house-style/hooks.json` in both directions, exactly
as `verify.py` does for the table above. The two tables are independent; do not merge them.

Two constraints are worth knowing before touching it:

- **Google Fonts is the only webfont source that works.** Artifacts run under a CSP allowing
  stylesheets only from `fonts.googleapis.com` and font files only from `fonts.gstatic.com`,
  with no visible error on a blocked load. Fontsource is used as the keyless *metadata*
  catalogue; delivery is always Google. `validate()` enforces it, so a theme cannot regress here.
- **Every theme carries two font stacks.** `stack` for pages that can load a webfont,
  `systemStack` for those that cannot - `step-card.html` above is required to be self-contained
  and offline, and `verify.py` fails if an external reference appears in it. `style.py css
  <name> --system` emits the second form.

The catalogue is fetched **in Python at command time and inlined into the generated page**,
never by the page: the same CSP blocks `fetch` to every host without exception, so a gallery
that called the APIs itself would silently show nothing. Fetches fall through cache to the three
shipped themes and never raise - offline is a normal state, not a failure.

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
  - `scope` **must never raise or exit non-zero** — on `UserPromptSubmit` a non-zero exit
    *erases the user's prompt*, so every branch of its gating logic is wrapped to fall back to
    the short reminder. Its text (both forms) is a restatement of rule phrases; `verify.py`
    checks it hasn't drifted from `house-rules.md`. `runnable`'s reminder text is pinned the
    same way, for the same reason.
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
- **No hook keeps state between invocations.** `handover` runs at `Stop` and stores nothing,
  because the one fact it needs — has it already fired this turn — is held by the harness and
  arrives in the payload as `stop_hook_active`. `verify.py` fails if a dead state file or a
  stray `.sh` hook script return, or if anything other than `run.sh` is registered on any event.
  Why this replaced an earlier stateful design, and what that design cost: see
  docs/architecture.md.
- **`verify.py` is the source of truth for "does this actually work"**, not the README. It feeds
  real hook payloads through `hook.py` and asserts on the JSON decision returned. When adding a
  rule with a shell signature, add both a `guard` pattern and a `verify.py` case in the same
  change — untested rule text has no effect. It computes its own check count at runtime; don't
  write that number down anywhere, it will drift.

### The surfaces the step-card handover format actually reaches

The step card (defined in `rules/house-rules.md` under `#### The card`) is the fixed shape for
handing the user a command to run. What follows is a claim about which surfaces receive it, and
`docs/desktop-verification.md` is what substantiates each row — `verify.py` checks that every
surface named here has a matching check there.

| Surface | Interactive card | Markdown card | How it gets there |
|---|---|---|---|
| Claude Code — CLI | published page, 4+ steps or on request | yes | `inject` + `scope` + `handover` |
| Claude Code — IDE extension | inherits the CLI; not separately documented | yes | same |
| Claude Code — Desktop **Code** tab | published page, 4+ steps or on request | yes | same |
| Claude Code — web / cloud session | publishing undocumented; treat as unavailable | yes | ships with the repo install; cloud never reads `~/.claude/settings.json` |
| claude.ai chat — web / desktop | sometimes, model's discretion, unrequestable | yes | [docs/claude-ai-instructions.md](docs/claude-ai-instructions.md) |
| claude.ai chat — iOS / Android | **never** | yes | same |
| Claude Code — WSL session | no | **no** | **plugins are unavailable in WSL sessions entirely** |
| Claude Code — Desktop **Cowork** tab | no | **no** | sources skills and plugins from the claude.ai account, not `~/.claude` — this plugin covers the **Code** tab only |

### Editing the rules

Edit only [claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md).
If the new rule has a shell signature, add a matching pattern to `hook.py`'s `guard` handler and
a case to `verify.py`. If you reword a phrase that `hook.py`'s `scope`/`runnable`/`delegate`/
`handover` handlers also state, update the matching hardcoded string in `hook.py` too —
`verify.py`'s drift checks will fail otherwise. Run the verify command above before considering
an edit done; it's the only thing that proves a rule change actually took effect versus just
reading well.
