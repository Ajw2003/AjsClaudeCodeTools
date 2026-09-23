# Architecture rationale

This is the hook-by-hook reference, the design constraints `hook.py`/`run.sh` are built on, and
the long-form "why" behind them — moved here (2026-09-22, "rules that actually load") so the root
`CLAUDE.md` (auto-loaded every session) stays small. Read this when you need the table, the
constraint, or the reasoning behind it.

**SessionStart's `additionalContext` is not re-paid on subagent spawn — it is never given to a
subagent at all**, but **`SubagentStart`'s `additionalContext` IS** — both tested directly with
`claude -p` (docs/plans/2026-09-22-rules-that-actually-load.md; docs/Decisions.md, 2026-09-23,
doc-ref c67d). A spawned `general-purpose` subagent could not see a word planted by a SessionStart
hook in the parent session, but could see one planted by its own `SubagentStart` hook. That is
why `subagentrules` exists: a third `SubagentStart` entry that re-injects a *subagent core*,
generated from `house-rules.md`'s own `<!-- subagent -->`-marked sections, at the one lifecycle
point proven to reach it. `@house-rules:executor` and `@house-rules:archivist` additionally carry
their own rules digest in their own `agents/*.md` file, belt-and-braces (`verify.py`'s
`digestdrift` check enforces it). The probe also found the other direction does **not** exist: at
`SubagentStop`, neither `additionalContext` nor `systemMessage` reaches the *parent* session's
model context in the same turn — only the interactive UI shows a `SubagentStop` `systemMessage`,
which is why `verdict`'s audit summary rides that one proven channel rather than a second one that
was assumed to work and does not.

## The plugin is one POSIX shim plus one Python file, dispatched by event

Defined in [claude-house-rules/plugins/house-rules/hooks/hooks.json](../claude-house-rules/plugins/house-rules/hooks/hooks.json),
every hook command is `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`. `run.sh` resolves a
working Python interpreter and execs
[scripts/hook.py](../claude-house-rules/plugins/house-rules/scripts/hook.py) with that event name;
every handler lives in that one file. Why a shim rather than calling `hook.py` directly, and how
`run.sh` probes for a working interpreter: see the section right below this one.

| Hook event | `run.sh` arg | Fires on | Effect |
|---|---|---|---|
| `SessionStart` | `inject` | every session | Prints `rules/house-rules.md` into context as `additionalContext`, with every `${CLAUDE_PLUGIN_ROOT}` in it substituted for the real absolute plugin path so the `rules/detail/*.md` pointers it names are actually openable. This *is* the CLAUDE.md replacement. |
| `SessionStart` | `profile` | every session | Second entry on the same event, split out of `inject` in 2.17.1 because the per-hook `additionalContext` limit is 10,000 chars and a recorded `rules/environment.md` can by itself be large enough to push a combined block over it — see docs/Decisions.md. Prints the machine profile (a hand-verified `rules/environment.md`, or a runtime-detected fallback) plus preflight warnings. On a remote session (`CLAUDE_CODE_REMOTE` set) it also appends a distinct block for `rules/handover-target.md` — the human's own machine, as opposed to the sandbox `hook.py` runs on — recorded content when present, or an instruction to find out and record it when not; a local session adds nothing here. Truncates only the machine-profile portion of its own output with a visible notice naming the oversized file, rather than silently exceeding the limit, if the recorded profile is itself too large — the preflight warnings and the remote handover-target block are never the part cut. A failure here cannot take `inject` down with it — separate hook entry, same fail-loud pattern. |
| `SessionStart` | `standards` | every session | Third entry on the same event, so a detection failure here can never take down the rules injection above. Selects and prints the coding standards docs from `rules/standards/` that apply to the repo it's sitting in — always `coding-philosophy.md`, plus `csharp-unity-standards.md` and/or `web-js-ts-node-standards.md` when their markers are detected across the repo root and one level of subdirectories, or an explicit `.claude/standards` override. Also catches the project root itself being a Unity project's `Assets/` folder (a normal way to open a Unity project) by checking one level *up* for `ProjectSettings/`/`*.csproj` when the root's directory name is exactly `Assets` — when that's true, detection re-scans from that real project root instead of `Assets/`, so a sibling Node service next to `Assets/` (not just the Unity markers) is still found. |
| `SessionStart` | `docstiers` | every session | Fourth entry on the same event, its own hook entry so a failure here can never affect `inject`/`profile`/`standards`. Checks the project root (`CLAUDE_PROJECT_DIR`, else `cwd`) for the six documentation tiers named in `skills/project-docs/SKILL.md` — `docs/README.md`, `docs/Roadmap.md`, `docs/ProjectState.md`, at least one file under `docs/systems/`, `docs/Today.md`, `docs/Decisions.md`. All present: emits nothing at all — the one other deliberate silent exception besides `handover`, since this runs every session and a trace would cost something on every one of them for what is usually true. Any missing: `additionalContext` names exactly which tiers are missing and instructs loading `house-rules:project-docs` and scaffolding them before any other work, in every repo, including one that is not a git repository at all. In a git repository, also reads the remote's owner from `.git/config` (no subprocess — handles `https://` and `git@host:` URL forms, and a worktree's `.git` file redirect) against `HOUSE_RULES_GITHUB_OWNER` (default `Ajw2003`, case-insensitive); not owned, or the remote can't be read at all, adds one more instruction: add every scaffolded path to `.git/info/exclude`, so the new docs never leave the machine or enter that repo's history. Fails loud via `systemMessage`, like `inject`. |
| `SessionStart` | `versioncheck` | every session | Fifth entry on the same event. Compares three copies of the plugin version — installed, the local marketplace clone, and GitHub's default branch — because the marketplace clone can itself go stale independently of the installed copy (`marketplace add` does not re-fetch a marketplace the device has already seen). A mismatch prints a loud, impossible-to-miss `additionalContext` banner naming which copies disagree and the exact `claude plugin marketplace update` / `claude plugin update` commands to fix it, and telling Claude to ask the user's permission to run those commands itself on this exact machine, then stop and wait for the user's answer instead of continuing into unrelated work; only if the user declines, or the session has no shell tool, does Claude fall back to handing them over through the normal step-card format, marked `UNTESTED:` since the hook relayed them rather than Claude running them on this machine. It also writes a session-keyed marker file so `guard` can also surface it as a real permission prompt on the session's first `Bash`/`PowerShell` call — the one deliberate, scoped exception to "no hook keeps state between invocations" (see below). `HOUSE_RULES_VERSION_CHECK=off` disables the whole check; `HOUSE_RULES_VC_GITHUB_URL` points a fork at its own repo instead of `Ajw2003/AjsClaudeCodeTools`. Network failures are best-effort and never treated as "out of date" — only an actual version mismatch is. |
| `UserPromptSubmit` | `scope` | every prompt | Restates a short reminder so the rules stay live 200 messages into a long session, after the SessionStart copy has faded from attention. Emits a short pointer form by default and the full form only when the prompt looks command/file/build-shaped, gated statelessly on the payload's `prompt` field — every failure path falls back to the short form and exits 0, since a non-zero exit here erases the user's prompt. |
| `PreToolUse` | `guard` | `Bash`/`PowerShell` calls | Extracts the `command` field and textually matches it against rule patterns (hidden/background work, git history/index/remote writes, destructive deletes and discards). A match returns `permissionDecision: "ask"` — it never blocks outright, only prompts. **Branch-aware since 2.16.0:** a plain `commit` or `push` stops prompting when `.git/HEAD` says the checkout is on a `claude/…` branch, because the commit rule already allows those there. Nothing else is exempt — force-push, `reset`, `revert`, `clean`, `rebase`, `merge`, `cherry-pick`, `am` and `apply` prompt on every branch, and so does any command carrying `-C`/`--git-dir`/`--work-tree`, which names a repo other than the one the branch was read from. Every uncertainty (their branch, a detached HEAD, an unreadable or absent repo) lands on the prompting side and the prompt says which. Also consumes `versioncheck`'s session-keyed out-of-date marker if one is waiting: the first `Bash`/`PowerShell` call of an out-of-date session prompts once for that reason alone, even if the command itself trips no other rule, then the marker is deleted so later calls don't repeat it. |
| `PreToolUse` | `guardwrite` | `Write` calls | The other half of the destructive-action rule: `guard` catches a shell command deleting a file, this catches `Write` doing the same thing under a different name. `Write` always replaces a file's entire contents, so any call that targets a path already on disk is a full-file replacement by definition — this checks only whether the target already exists, never the size of the change, because there is no such thing as a small `Write`. When it does, it asks every time, naming the path and (when both counts are readable) how many existing lines would be discarded for how many new ones. It cannot know *why* a rewrite is happening, only *that* one is about to — the reason is left to whatever Claude has already said in chat, per the "Edit in place" rule. Fails closed like `guard`: an unreadable payload or internal error blocks the write rather than letting it through unchecked. A brand-new path is not a replacement and is never asked about. |
| `PostToolUse` | `artifact` | `Write`/`Edit` calls | Notices a document write outside the project (temp dir, scratchpad, `~/.claude/plans`) and reminds *Claude* — not the user — to copy it into the project before finishing. The extension list is every form a deliverable arrives as — `md`, `txt`, `html`, `csv`, `json`, `svg`, `pdf` — not the `md`/`txt` it shipped with: the rule says *every* artifact, and a narrower pattern let an `.html` report sit in the scratchpad unnoticed. Routing is extension-aware: hand-authored `md`/`txt` go to `docs/` (or `docs/plans/` for a plan), while tool-produced `html`/`csv`/`json`/`svg`/`pdf` go to `docs/generated/` instead, so generated deliverables don't mix into hand-written documentation. Runnable extensions stay out; `runnable` owns those. |
| `Stop` | `handover` | a turn about to end **whose reply hands over a command and is not already in card shape** | Reads `last_assistant_message` — the documented field for the just-written reply — and stays silent when there is no fence, since no fence means no command was handed over and the check would only be noise the user has to watch Claude answer. It also stays silent when the reply already carries the card markers (`---`, `###`, `You should see:`), because firing on a compliant reply cannot end quietly — the turn continues, `suppressOutput` has no effect, and the only thing left to say is that nothing needed saying, which is exactly the *a card never announces its own compliance* rule being broken by the hook that enforces it. The cost is deliberate: a card-shaped reply missing a field now passes unchecked, traded for removing a defect that was visible on every correct handover. When it does fire it emits `hookSpecificOutput.additionalContext`, not `decision: "block"`: both continue the turn under the same loop protections, but the former is labelled *Stop hook feedback* rather than raising a hook error, and this is guidance working as designed. A payload with no `last_assistant_message` (an older CLI) still fires, so a version difference cannot silently disable it. The checklist: how the user gets there (folder as an absolute path, plus opening a prompt in it), shell named and correct as the fence label, exact command, expected output, `UNTESTED:` when it was not run, and one numbered step per action once there is more than one command. Stands down on the retry (`stop_hook_active`), on `HOUSE_RULES_HANDOVER=off`, and on any failure — it fails **open**, since a non-zero exit here would stop the turn ending at all. |
| `PostToolUse` | `runnable` | `Write` calls only | Notices a runnable file (`.sh`, `.ps1`, `.py`, `Dockerfile`, …) created inside the project and reminds *Claude* to run it before finishing. A compiled-language file (`.cs`) gets a different reminder instead: compile it with the real toolchain — Unity in batch mode, or `dotnet build`/`msbuild` against the project's own `.csproj` — never a hand-rolled stand-in for the engine's APIs (a fake `UnityEngine`, a stub assembly) that only proves the stand-in compiles. `Write` only, never `Edit`. |
| `PostToolUse` | `harvest` | `Write`/`Edit` calls | Reads the body just written (`content`, or `new_string` for an `Edit`) and finds comment blocks that have grown into essays - design rationale, a post-mortem, a derivation, a platform quirk. Reminds *Claude* to move each into the tier-4 system doc that owns that code before the turn ends, leaving a **one-line pointer** at the site, and to hand the mechanical move to `@house-rules:archivist`. This is the one handler that reads a payload's *contents* rather than just its `file_path`, because the comment body is the subject; reading the payload rather than the file on disk keeps it stateless and means it only ever sees text written **this turn**, never a pre-existing essay in a file it merely touched. Source extensions only, so a write to `docs/` is silent by construction. The threshold (`HARVEST_MIN_CHARS`, default 500 - characters are the only size criterion, so wrapping and indentation cannot move a comment across it) is tunable via `HOUSE_RULES_HARVEST_MIN_CHARS`; a bad value is announced and the default used, never silently ignored. Large files are scanned, not skipped - a wall-clock budget bounds the *work* and an overrun says so by name. Emits a one-line decision **trace on every source-file write whether or not it fires**, naming what it measured, so the near-misses are visible and threshold tuning is evidence rather than guesswork; the trace never claims a run failed the size threshold when it actually met it and was rejected for another reason (a file header, a license block, commented-out code). `HOUSE_RULES_HARVEST=quiet` drops the trace, `=off` disables both, `HOUSE_RULES_DEBUG=1` adds per-run rejection reasons. The file-header exemption applies only to a `Write`'s whole-file `content` — never to an `Edit`'s `new_string` fragment, whose own line 1 is wherever the edit starts, not the file's. `/house-rules:harvest-scan` (`commands/harvest-scan.md`) runs the same detection code by hand across a whole project via `scripts/harvest_scan.py` (the hook only ever sees text written in the current turn), see [comment-harvest-calibration.md](comment-harvest-calibration.md). |
| `PostToolUse` | `delegate` | `ExitPlanMode` calls | The plan just got approved, so the deliberation is over: reminds *Claude* to hand the implementation to `@house-rules:executor`, naming the plan's file path (the `ExitPlanMode` payload carries the plan as inline text, not a path, so this is on Claude to supply), instead of running it on the planning model. Trivial work (one file, a handful of steps or fewer) is done inline instead. |
| `SubagentStart` | `announce` | every subagent spawn | Says out loud what a delegation used to keep to itself: which agent is starting, what the **installed** `agents/<name>.md` *declares* it should run on (model and effort, parsed from that file, never a literal in `hook.py`), the effort the payload's own `effort` field reports, the plugin version, and an 8-hex fingerprint of the agent definition — which answers *which digest, from which version, was in its context*. Registered with **no matcher**, so every subagent is reported, not only the two this plugin ships; an agent it does not ship is named and reported as having no declaration to compare against, which is still the useful half. If `CLAUDE_CODE_SUBAGENT_MODEL` or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set it says so — that is the documented way a declared model silently is not what runs. |
| `SubagentStart` | `subagentrules` | every subagent spawn | A third, separate `SubagentStart` entry from `announce`: injects the **subagent core**, generated at emit time from the sections of `rules/house-rules.md` marked `<!-- subagent -->` right under their heading (docs tiers, nothing fails silently, evidence before claims, artifacts in the project, commit on own branches, destructive actions, edit in place), plus a fixed mandate that the final report list every command run and its result verbatim, every file written or edited, and anything it could not do. One source, no second copy to drift; `${CLAUDE_PLUGIN_ROOT}` expanded the same way `inject` does it. Own budget, `SUBAGENT_CORE_CHAR_LIMIT = 4,500`, well under the per-hook 10,000 limit. Also tells the user the transcript's **expected** path, before the transcript exists, so it is findable without waiting for `verdict`. |
| `SubagentStop` | `verdict` | every subagent finish | Turns the declaration into **evidence**: reports the model that actually served the subagent, read out of the subagent's own transcript, and MATCH/MISMATCH against what the agent declares, plus the transcript path it **actually found**. The transcript is **probed, never assumed** — an `agent_transcript_path` field if the payload carries one (it is not in the documented reference), then `<dir of transcript_path>/<session>/subagents/agent-<agent_id>.jsonl`, the layout observed live; the docs warn the entry format is internal and changes between releases, so every path that cannot tell names what it tried. Also emits an **audit summary** built from the transcript itself — each `Bash`/`PowerShell` command paired with its matching `tool_result`'s exit status, every file `Write`/`Edit`'d, tool-use counts — capped at 40 commands of 160 chars each, plus an instruction to reconcile the subagent's own report against this record and flag every unsupported claim before relaying it. `HOUSE_RULES_SUBAGENT_LEDGER=on` (off by default) additionally renders the full transcript into `docs/sessions/` with the shared renderer in `scripts/session_ledger_render.py`. Fails **open and loud** like `handover`: `decision: "block"` here would send the subagent back to work. |

The table above is checked against `hooks.json` by `verify.py`: an event registered as a hook but
missing from this table, or listed here but not registered, fails the suite. Why one subagent is
the primary mechanism for the model split (and why `opusplan` alone is not enough): see the
section right below.

## Design constraints that shape `hook.py` and `run.sh`

- **`hook.py` is stdlib-only Python.** No third-party imports, no pip install, nothing beyond
  what ships with CPython 3.8+. `run.sh` is the one POSIX-sh dependency left in the whole
  plugin, and its only job is finding a working interpreter — it does no rule matching itself.
- **Each handler's failure mode is deliberate and matches what that hook event allows:**
  - `guard` and `guardwrite` **fail closed, loudly** (`PreToolUse` can block) — an unreadable
    payload or any internal error writes to stderr and exits 2, so the command or write does not
    run. `run.sh` extends this all the way down: no working interpreter at all is also a blocking
    failure for either one.
  - `inject` **fails loud, not closed** — a missing/unreadable rules file still emits a
    `systemMessage`, since there's nothing to block. `run.sh` does the same when no interpreter
    can be found at all.
  - `scope` **must never raise or exit non-zero** — on `UserPromptSubmit` a non-zero exit
    *erases the user's prompt*, so every branch of its gating logic is wrapped to fall back to
    the short reminder. Its text (both forms) is a restatement of rule phrases; `verify.py`
    checks it hasn't drifted from `house-rules.md`. `runnable`'s reminder text is pinned the
    same way, for the same reason.
  - `artifact`, `runnable`, `delegate` and `harvest` **never obstruct, and never go quiet** —
    `PostToolUse` can't block anyway (the write already happened), so they always exit 0; but
    every path meaning *I could not tell* (empty payload, unparseable JSON, missing field,
    scan budget exceeded, any internal error) says so via `systemMessage`. Silence from one of
    these means it looked and there was nothing to do — nothing else.
- **Nothing fails silently**, and `verify.py` enforces it over `hook.py`'s own source: no
  `except` block may return or pass without emitting, writing to stderr, or recording the
  problem for its caller to report. An `except` that *recovers* — assigns a fallback and
  carries on — is not the defect. `main()`'s last-resort net speaks for **every** event, not
  just `guard` and `inject`; `scope` is the one deliberate exception, recovering to its short
  reminder rather than reporting, because a non-zero exit there erases the user's prompt.
  See the rule in `rules/house-rules.md` and the reversal it forced on `handover`'s
  empty-payload case, recorded further down this document.
- **Every handler with a silent success path traces its decision, on by default.** `guard`'s
  allow, `artifact`, `runnable` and `harvest` each emit a one-line `systemMessage` saying what
  they looked at and what they concluded, whether or not they fire. `inject`, `standards`,
  `scope` and `delegate` do **not** — they always emit something already, so a trace there
  would duplicate the proof it exists to provide, at the most expensive possible frequency
  (`scope` runs on every prompt). `handover` is the one deliberate exception with a silent
  path: tracing its stand-down would announce a compliant card's own compliance, which
  `rules/house-rules.md` forbids, and would put a line on the end of every ordinary turn.
  **stderr is not an alternative** — a hook that exits 0 has its stderr sent to the debug log
  only, never the transcript, so a trace written there is off by default in name only.
  `HOUSE_RULES_TRACE=off` is the single lever and silences no reminder;
  `HOUSE_RULES_HARVEST=quiet` drops just harvest's; `HOUSE_RULES_DEBUG=1` adds harvest's
  per-run rejection reasons. `tools/measure_footprint.py` section 4 prices all of it.
- **Every handler extracts the one field it cares about**, rather than matching the whole
  payload. `artifact` and `runnable` read `file_path`, so a file whose *contents* mention `/tmp`
  doesn't false-trigger on every save. `guard` reads `command`, so a call *described* as
  "check for uncommitted changes before we commit" doesn't prompt on the word commit. Matching
  stays deliberately broad *within* the extracted field — over-triggering there is cheap.
- **`guard` reads the branch from `.git/HEAD`, never from `git rev-parse`.** It runs on every
  shell call and blocks the command when it fails, so a subprocess that hung would wedge the
  user's shell for as long as it hung; one file read cannot, and it keeps guard working where
  `git` is not on PATH. `verify.py` fails if `branch_ownership()` ever reaches for a subprocess.
  Guard cases are judged against fixture repos with a hand-written `.git/HEAD`, not against
  whichever branch the suite happens to be run from — otherwise the same suite passes on `main`,
  fails on a `claude/` branch, and agrees with neither CI nor a developer.
- **`guard`'s three-tier ladder is the shape to preserve** if you touch its input handling.
  Unreadable payload or any internal error → stderr and `exit 2`, blocking. Payload readable but
  no `command` field → fall back to matching the whole payload, exactly as it behaved before the
  extraction existed. Field found → match that alone. The middle tier is what keeps a tool whose
  input field is named something else from being either waved through *or* blocked outright.
- **No hook keeps state between invocations, with one deliberate, scoped exception.**
  `handover` runs at `Stop` and stores nothing, because the one fact it needs — has it already
  fired this turn — is held by the harness and arrives in the payload as `stop_hook_active`.
  `verify.py` fails if a dead state file from the old design (`track-write.sh`,
  `clear-pending.sh`, `deliverable.sh`) or a stray `.sh` hook script return, or if anything other
  than `run.sh` is registered on any event. `versioncheck` is the one hook allowed to write new
  state: a session-keyed marker file, read and deleted by `guard` on the session's first
  `Bash`/`PowerShell` call. The state is stateless in every way that mattered for the old
  design's failure — it never grows unboundedly (`guard` deletes it on read), it is keyed to one
  session (`session_id`), and a stray leftover from a crashed session simply never gets read by
  any other session, unlike the old shared `$TEMP` file that leaked across them. Why this is a
  scoped exception rather than a reversal, and what the old stateful design cost: see the
  `versioncheck` section further down.
- **`verify.py` is the source of truth for "does this actually work"**, not the README. It feeds
  real hook payloads through `hook.py` and asserts on the JSON decision returned. When adding a
  rule with a shell signature, add both a `guard` pattern and a `verify.py` case in the same
  change — untested rule text has no effect. It computes its own check count at runtime; don't
  write that number down anywhere, it will drift.

## Why a shim in front of the Python file, rather than calling `hook.py` directly

`hooks.json` cannot itself probe for an interpreter, and `python`/`python3`/`py` availability
and naming varies by OS — `py` is the Windows launcher, which ships with the official Python
installer and picks an installed interpreter for you, so it exists on Windows and nowhere else.
Worse, on this machine `python3` is the Windows Store App Execution
Alias stub: on PATH, found by `command -v`, but it prints an install nag to stdout and exits 0
instead of running anything. Trusting `command -v` would silently disable every hook the same
way a missing `node` once did. `run.sh` **probes** each candidate — actually runs it and checks
the output — rather than trusting that being on PATH means it works. See `run.sh`'s own
comments for the full resolution order and each event's fallback behaviour when no interpreter
probes successfully.

## One subagent, for the model split — the primary mechanism, not the fallback

`agents/executor.md` registers `@house-rules:executor`, pinned to `model: sonnet` at
`effort: low`, for running a plan that has already been decided. The `delegate` handler (in the
hook table) is what actually asks for that delegation, on `ExitPlanMode`.

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

### The model is now observed, not declared

Until 2.18.0 the split rested entirely on a *declaration*. `agents/executor.md` says
`model: sonnet`; nothing checked it. The agent list shows type and status but no model, and the
completion notification reports tokens, tool uses and duration and no model either. So a
delegation that fell back to the parent model, or a digest that had drifted, looked identical
from outside to one that worked — the failure was silent by construction. That is what the
`announce` and `verdict` handlers fix, and the distinction between the two is the whole point:

- **`announce` (`SubagentStart`) reports the declaration**, read out of the installed
  `agents/<name>.md` rather than hardcoded in `hook.py` — so the line is a report of what
  shipped, not a claim `hook.py` makes about it. It also names the plugin version and an 8-hex
  fingerprint of the agent definition, which is what answers *which digest was in its context*.
  And it warns when `CLAUDE_CODE_SUBAGENT_MODEL` or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set,
  because that is the documented mechanism by which `model: sonnet` is silently not what runs.
- **`verdict` (`SubagentStop`) reports the evidence** — the model that actually served the
  subagent, read from the subagent's own transcript, and MATCH or MISMATCH against the
  declaration.

**The transcript is probed, never assumed, and that is deliberate.** Two candidates are tried in
order: an `agent_transcript_path` field if the payload carries one, and
`<dir of transcript_path>/<session>/subagents/agent-<agent_id>.jsonl`. The first is *not* in the
documented hook reference — it may be there, so it is tried, but nothing rests on it. The second
is the layout observed live: a subagent gets its own JSONL file, every `assistant` entry carries
`message.model`, and `isSidechain: true` marks the sidechain. Measured on one session, the parent
reported `claude-opus-5` across 55 assistant entries while the subagent it spawned reported
`claude-haiku-4-5-20251001` across 26 — which is also a working demonstration that a declared
model and a served model are two different facts.

The docs warn that the transcript entry format is internal to Claude Code and changes between
releases. That is exactly why every path that cannot tell **says what it tried** rather than
going quiet or guessing: no transcript found (listing the candidate paths), unreadable, or no
`assistant` entry carrying a model. An `agents/<name>.md` that is shipped but unreadable is
reported as such rather than collapsing into "no declaration shipped" — a broken install and a
normal one must not print the same line.

Both fail **open and loud**, like `handover`. A non-zero exit at a subagent lifecycle event must
never wedge anything, and `decision: "block"` on `SubagentStop` would send the subagent back to
work rather than reporting anything. Neither is registered with a matcher: the complaint these
answer was *I could not tell which agent was running*, which is about every subagent, not only
the two this plugin ships. `HOUSE_RULES_DELEGATION=off` is the single lever, and they are
deliberately **not** `HOUSE_RULES_TRACE`-gated — the report is the feature, not a narration of an
otherwise-silent path, and gating it behind the trace lever would make the thing being shipped
optional by default.

### Why the delegation kept not happening

The other half of 2.18.0 is a regression fix, and it is worth recording how it hid. `77e2141`
established that the harness gates autonomous subagent spawning behind the user explicitly asking
**or** the target agent's description marking it for proactive use, and amended the injected note
to say that the delegation is therefore *authorized*, not merely suggested. `ec6105e` — the
shell-to-Python port — rewrote `delegate.sh` into `DELEGATE_NOTE` and dropped that sentence. It
survived in `house-rules.md` and in both agent descriptions, but not in the one text that is in
context at the moment the model decides whether to spawn.

It passed every check because the delegate drift check ran in **one direction**: it asserted each
phrase still appeared in `house-rules.md`, never that it still appeared in the restatement it was
named for. This is the gap `docs/architecture-backlog.md` entry 1 predicted, realised and paid
for. The check is now bidirectional over the emitted reminder as well, which was confirmed by
re-introducing the original regression and watching three checks fail.

The skip-it exception moved the same way, from prose to a count. "Work small enough that
describing it costs more than doing it" is a judgement call, and a judgement call about whether to
delegate is one the planning model talks itself past. It is now *one file AND three steps or
fewer*, stated identically in the rules, the reminder and the executor's own description, with the
skip required to be said out loud in a line that names the count — an exception used silently is
indistinguishable from the rule being forgotten.

Every handler is stateless. Nothing writes to `$TEMP`, and there is no state to reap. That is
load-bearing, not incidental — see the deliverable note in `CLAUDE.md`'s design constraints.

## `harvest` reads the payload's contents, and every other handler deliberately does not

`artifact` and `runnable` match on `file_path` alone and never look at what was written —
`verify.py` pins that with a case named *"a file whose CONTENTS mention a temp path is judged
on where it actually is"*. The reasoning is that a file whose body happens to mention `/tmp`
should not trip a check about where the file lives.

`harvest` breaks that invariant on purpose, because for it the comment body **is** the subject:
there is no way to notice an essay from a path. Two properties keep the departure narrow:

- **It reads the payload, not the file on disk.** So it stays stdin-only and stateless like
  every other handler, and — more usefully — it only ever sees text written *this turn*. A
  pre-existing essay in a file that was merely touched is invisible to it, which is what stops
  the reminder becoming a standing nag on legacy code.
- **`Write` carries the whole file, `Edit` carries a fragment.** For a `Write`, content line
  numbers are the file's, so the reminder cites `file:a-b`. For an `Edit`, `new_string`'s
  offsets mean nothing in the file, so the ranges are withheld and the reminder says to find
  the blocks by reading the file. Emitting them anyway would put a confidently wrong
  `file:line` into a document whose own convention is to cite `file:line`.

### The scan is budget-bounded, not size-capped

The first draft skipped files over a byte ceiling. That is a silent failure wearing a
performance argument: the check does not run and nobody is told which file it did not run on.
Instead there is no ceiling — any file is scanned — and a wall-clock budget bounds the *work*,
with an overrun emitting a `systemMessage` naming the file and its size.

Hand-testing is what made this real. A 4.8 MB file took **22 seconds**, past `hooks.json`'s 10s
timeout, so in practice the harness killed the hook rather than the hook reporting anything. The
cause was an O(n²) accumulator rebuilding each comment run's line list per line; fixed, the same
file scans in 0.29s. `verify.py` now carries both regressions — a multi-megabyte scan that must
finish inside the timeout, and a forced overrun that must name the file. Neither was caught by
the suite as originally written, which is the argument for verification step 3 existing at all.

### Thresholds are tunable because they were guessed, then measured

`HARVEST_MIN_CHARS` defaults to 500 and is overridable per machine. There is no line-count
threshold: it was 3 lines OR 150 chars, and the OR made three short lines qualify.
The default is not a taste call: see
[`comment-harvest-calibration.md`](comment-harvest-calibration.md) for what different values
catch, and why the earlier 3 / 150 default flagged 831 blocks in a real project.

### The file-header exemption is Write-only, and the trace names the real rejection reason

`_harvest_blocks()` exempts a comment run starting at line 1 (or line 2 under a shebang or
encoding line) as a module docstring rather than an essay buried in the body of the file. That
is only true when the text really is the whole file — a `Write`'s `content`, or a standalone
scan of a file on disk. An `Edit`'s `new_string` is a replacement fragment with its own line
numbering starting from wherever the edit begins, so a comment block placed at the top of an
edit was getting exempted purely by coincidence of where the edit started. `_harvest_blocks()`
takes a `full_file` flag now, and `event_harvest()` passes `full_file=ranged` — true only for a
`Write` — so an `Edit` never gets the exemption. See `docs/Decisions.md`, "Fix the harvest
handler treating an Edit fragment's line 1 as the file's header".

The same entry fixed `_harvest_trace()`'s summary line, which always read "none met N lines / M
chars" regardless of *why* a run was rejected — including when a run was long enough to clear
the threshold but excluded for cause (a file header, a license block, commented-out code). That
produced a self-contradictory trace: a measured run bigger than the stated threshold, right next
to a claim that nothing reached it. The trace now only says "none met" when the longest run's
own rejection reason genuinely was its size; otherwise it names the real reason.

## `guard` is branch-aware, and reads the branch from a file rather than from `git`

The commit rule was rewritten in 2.16.0 to draw its line at branch *ownership* — commit freely on
a branch I created, mutate nothing on one the user authored — but `guard` went on prompting for
every mutating git command regardless of branch. The hook and the rule it cites by name disagreed,
and the hook was the one the user actually felt. That was left deliberately for one release,
because making it branch-aware needed doing against an up-to-date checkout rather than bolted onto
the rule change.

### Why `.git/HEAD` and not `git rev-parse --abbrev-ref HEAD`

`rev-parse` is the obvious way to ask, and it is the wrong one here. `guard` runs on `PreToolUse`
for every `Bash` and `PowerShell` call, and it is the one handler that **fails closed** — an
internal error exits 2 and the command does not run. A subprocess on that path is a subprocess on
the critical path of every shell command the user issues, in the handler whose failure mode is
"your command does not run". A `git` that hangs — a stale index lock, a network-backed filesystem,
an antivirus scan on first exec — wedges the shell for as long as it hangs.

Reading `.git/HEAD` cannot hang in any of those ways. It also keeps `guard` working where `git` is
not on `PATH`, which is the same reasoning that keeps `hook.py` stdlib-only: the checker must not
be a bigger dependency than the thing it checks. Measured on the Windows desktop, the whole
ownership read costs **46 µs** from the repo root and **73 µs** from two directories down, against
roughly 30 ms of interpreter startup that is paid anyway.

`verify.py` fails if `branch_ownership()` ever reaches for `subprocess`, `os.popen`, `os.system` or
`check_output`. That check was itself wrong on its first run: it searched the function text for the
string `rev-parse`, which appears in the docstring precisely to say it is not used, so the check
reported a violation of the thing the code was getting right. It now looks for call syntax only —
a lesson about greping prose for the absence of an idea.

### What the exemption does and does not cover

Only a plain `commit` and a plain `push`, and only on a branch named `claude/…`. Everything else
in the bucket prompts on every branch:

- **Force-push** rewrites history that was already safely on the remote. A checkpoint adds; this
  replaces. It is the one push that can destroy something already backed up.
- **`reset`, `revert`, `clean`** discard work that is not yet a checkpoint — including the user's
  uncommitted edits sitting in the same tree, which do not become mine because the branch is.
- **`rebase`, `merge`, `cherry-pick`, `am`, `apply`** are how a hook would end up finishing an
  operation the user started, which the rule forbids *even on a branch named after me*.
- **Any command carrying `-C`, `--git-dir` or `--work-tree`** acts on a repo other than the one the
  branch was read from, so the exemption cannot be justified and is withheld.

Every way of not knowing — the user's branch, a detached `HEAD`, a directory that is not a repo, an
unreadable `HEAD` — resolves to *not mine* and therefore to a prompt. That is `guard`'s existing
fail-closed posture applied to a new input, and the prompt names which of them it was: a rule about
branch ownership is useless in a prompt that does not say which branch you are on.

### The pre-existing hole this exposed

Every git pattern shared a prefix meant to skip global options: `git\s+(-[^\s]+\s+)*`. It can
match a flag but not a flag's *argument*, so in `git -C /other/repo commit` the scan consumed
`-C ` , met `/other/repo`, and stopped — the subcommand was never reached and the command matched
**nothing**. `git -C <path> commit` and `git -C <path> push` had been walking straight past the
guard since the patterns were ported from the shell scripts. It was invisible while the answer was
always "prompt anyway for something", and became load-bearing the moment `-C` was what *withheld*
an exemption. The prefix is now a shared `_GIT` constant that knows which global options take a
separate argument, and `GUARD_R4`'s git patterns were fixed with it.

### Fixture repos, not the developer's branch

`verify.py`'s guard cases used to inherit whatever branch the suite happened to be run from. Once
the decision depends on the branch, that makes the suite's result a property of the developer's
checkout: it passed on `main`, failed on a `claude/` branch, and would have agreed with neither —
CI checks out a detached `HEAD`. Each case now names the branch it is judged against, using
throwaway directories containing nothing but a hand-written `.git/HEAD`. That the fixture is one
file is not a shortcut; it is the same fact that makes the read cheap enough to do on every call.

### A repo-only check skips outside the repo, rather than failing

`verify.py` ships inside the plugin, so it runs from two places: this repo, and the installed
copy in `~/.claude/plugins/cache/`. Seven of its checks read files that only the repo has —
`CLAUDE.md`, `claude-house-rules/README.md`, `docs/claude-ai-instructions.md`,
`docs/desktop-verification.md`, `tools/install.py`. Run from the cache, five of those reported
`FAIL` and two passed vacuously, so the installed copy's verdict was permanently red for a
reason that had nothing to do with the hooks. A `RESULT` line that is always red is one you
stop reading, and it takes the real failures down with it.

Those checks now report a third state, `SKIP`, which does not affect the exit code. The
distinction rests on `IN_REPO` — the presence of `.claude-plugin/marketplace.json` beside the
plugin directory, which is true in a checkout and false in the cache. **Inside a repo the skip
is unreachable**: a missing `CLAUDE.md` there is still a `FAIL`, because there it means the
file was deleted rather than never shipped. That property is what the suite tests when it is
run from a checkout, and it is checked directly by a case that compares the marker against a
second, unrelated repo-only file (`tools/verify_tools.py`) — if those two ever disagree, every
skip below them is untrustworthy and the suite says so instead of skipping quietly.

Two of the seven are half-skips. The page-rule check and the architecture-table check each have
a half that reads something the plugin *does* ship (`rules/house-rules.md`, `scripts/`); that
half still runs from the cache, and the check only reports `SKIP` if it passed. A drift in the
shipped half is still a failure wherever the suite is run.

## Nothing fails silently, and the plugin's own hooks were violating it

The rule landed with the `harvest` work and immediately indicted existing code, which is the
only reason it is worth having. Before it:

- `main()`'s last-resort net emitted for `guard` and `inject` and returned 0 **in silence** for
  every other event, so an internal crash in `scope`, `artifact`, `runnable`, `delegate` or
  `handover` produced no output at all.
- `event_delegate` had no `try` at all.
- Three `except OSError: pass` blocks in the standards scanners treated an unreadable directory
  as a directory with no markers in it — so a permissions problem made a repo's coding standards
  quietly not load.
- `read_payload` returned `""` for both an empty stdin and an unreadable one.
- `handover` treated an empty payload as "nothing to check" rather than "the check never got its
  input". **This is a reversal:** `verify.py` previously asserted that silence, under the title
  *"an empty payload is nothing to check, not a failed check"*. It now asserts the opposite, and
  the check says so at the call site.

`verify.py` enforces the rule structurally rather than by memory: it reads `hook.py` and fails
any `except` block whose body returns or passes without emitting, writing to stderr, or
recording the problem for its caller to report. An `except` that *recovers* — assigns a
fallback and carries on — is not the defect and is not flagged; the defect is giving up quietly.

`scope` is the one deliberate exception, and its exemption is named in the suite: a non-zero
exit on `UserPromptSubmit` erases the user's prompt, so its contract is to recover to the short
reminder rather than to report. Emitting that fallback is how it speaks.

### The trace ships on, and which handlers get one is measured, not assumed

The default output has to answer *did this run, on what, and what did it decide*. A diagnostic
switched off by default is never enabled until someone is already lost.

**stderr cannot answer it.** The hooks documentation is explicit: stderr from a hook that exits 0
goes to the debug log only, never the transcript, and Claude never sees it. Every trace path here
exits 0, so a trace written to stderr would be off by default in everything but name. The choice
is a `systemMessage` or nothing.

Which handlers need one was settled by running them rather than by argument. Four **already**
emit on every invocation — `inject`, `standards`, `scope` and `delegate` — so a trace there
duplicates the proof it exists to provide, at the worst possible frequency: `scope` runs on every
prompt. Four have a genuinely silent success path and get a trace: `guard`'s allow, `artifact`,
`runnable`, `harvest`.

`guard` was the real judgement call, because it fires on every shell command. The measurement
settles it: section 4 of `measure_footprint.py` puts its trace at ~52 chars (~13 tokens) per
call, against `inject`'s ~6,200 tokens paid once per session (not per subagent spawn — see the
correction above). Frequency
was the right worry and the number is small.

**`handover` is the one deliberate exception**, and not on cost grounds. Its stand-down fires
when the reply hands over no command *or is already in card shape*. Tracing the second case is
exactly the "a card never announces its own compliance" defect the `Stop` gate was narrowed to
remove — the line would appear, visibly, at the end of every correct handover. The first would
put a line on the end of every ordinary turn. Silence there already means "I looked and there was
nothing to do", which is what the rule asks; nothing is hidden. `verify.py` asserts both the
silence and the rule that requires it, so this cannot be quietly "fixed" later.

`HOUSE_RULES_TRACE=off` is the single lever and silences no reminder — `guard` still prompts,
`harvest` still reminds. `HOUSE_RULES_HARVEST=quiet` drops just harvest's trace;
`HOUSE_RULES_DEBUG=1` adds harvest's per-run rejection reasons.

## The machine profile is data, not code, and is not committed

`claude-house-rules/plugins/house-rules/rules/environment.md` is machine-local and **gitignored**
— each device records its own, and it never ships with the plugin. `profile` (a separate
`SessionStart` entry from `inject` since 2.17.1, so a large recorded profile can never push the
rules core over the per-hook limit) reads it; if it's missing (a fresh clone, always), `profile`
falls back to live runtime
detection (`hook.py`'s `_detect_environment`: OS, Python, and whether `git`/`sh`/`bash`/`pwsh`/
`powershell`/`node`/`npm` are on PATH) rather than a static "go find out" message or a Windows-11
default. A hand-written `rules/environment.md` still wins when present — runtime detection
cannot know RAM, GPU, or CRLF config, only a human recording it can. A worked example, including
the `sh`/`bash`-not-on-PATH trap discovered on this machine, is preserved at
[example-environment.md](example-environment.md).

## Where things live, and why

- **`.claude-plugin/marketplace.json`** must stay at the **repo root** — that's where
  `claude plugin marketplace add` looks. Its plugin entries are paths relative to the repo root
  (currently one: `./claude-house-rules/plugins/house-rules`). Any future plugin in this repo is
  another entry in this same list, not a new marketplace file.
- **`claude-house-rules/plugins/house-rules/`** is the plugin itself — everything under it is what
  gets published and installed on another machine. Treat its `rules/house-rules.md` as the only
  real copy of that text; everything else referencing the rules (`CLAUDE.md`, `hook.py`'s
  hardcoded reminder strings) is a pointer or a restatement, checked for drift by `verify.py`.
- **`claude-house-rules/plugins/house-rules/output-styles/`** and **`templates/`** hold the
  forced `handover-cards` output style and `step-card.html`, the page form of the step card.
  `step-card.html` is self-contained by rule — no external script, stylesheet, font or fetch —
  because a machine mid-install may not have a network, and `verify.py` fails if one appears.
  Claude fills its `STEPS` array and changes nothing else.
- **`docs/claude-ai-instructions.md`** is the chat-surface half: the text to paste into
  claude.ai → Settings → Instructions, which is the only mechanism that reaches plain chat and
  the phone. Committed so it can be diffed against the rules rather than silently drifting.
- **`docs/plans/`** holds implementation plans as real, committed files — per the rules
  themselves, artifacts never live only in a chat transcript or a temp directory.
- **`claude-house-rules/plugins/house-rules/skills/`** holds skills carrying the detail behind a
  rule too large to inject every session. Currently one: **`project-docs/`**, the five-tier
  documentation structure. The split is deliberate and is the pattern to copy — the rule
  *Documentation goes in tiers* stays short enough to live in `rules/house-rules.md` and fire
  unprompted in every session, while the tier spec, the per-tier contents and the scaffolding
  steps sit in the skill and load only when a repo's docs are actually being built or
  restructured. `verify.py` checks that the rule still names the skill and the skill still
  specifies all five tiers, because a rule pointing at a skill nobody shipped reads as though the
  detail is somewhere findable.
- **`tools/`** holds device-setup and release-verification scripts, not plugin code — nothing here
  ships to an installed copy of the plugin. `clean_install_test.py` now byte-compares the installed
  copy against the repo, and `--skip-strip` is the mode that catches a stale install, because a
  strip deletes the cache and therefore guarantees a fresh clone.
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

## The step-card handover format, and which surfaces it actually reaches

Steps the user has to run are handed over in one fixed shape — the step card — defined in
`rules/house-rules.md` under `#### The card` and injected into every session by `inject`. The
format deliberately uses only `---`, `###`, `**bold**`, plain paragraphs and top-level fenced
blocks: that is the set that survives every renderer this reaches. Box-drawing borders, a fence
inside a blockquote, a command in a table, and a fence nested in a list item are all banned, each
because it breaks in at least one of them. Do not paste the template into `CLAUDE.md` — it lives
in `house-rules.md` and `verify.py` fails on a second copy there.

The comparison that prompted it — claude.ai chat's interactive step widget — cannot be
reproduced. It is the **custom visuals** feature: model-discretion, beta, no documented emission
format, and it does not render on iOS or Android at all. The table below records what is
actually reachable, and `docs/desktop-verification.md` is what substantiates each row —
`verify.py` checks that every surface named here has a matching check there.

| Surface | Interactive card | Markdown card | How it gets there |
|---|---|---|---|
| Claude Code — CLI | offered at 2+ steps, published on request | yes | `inject` + `scope` + `handover` |
| Claude Code — IDE extension | inherits the CLI; not separately documented | yes | same |
| Claude Code — Desktop **Code** tab | offered at 2+ steps, published on request | yes | same |
| Claude Code — web / cloud session | publishing undocumented; treat as unavailable | yes | ships with the repo install; cloud never reads `~/.claude/settings.json` |
| claude.ai chat — web / desktop | sometimes, model's discretion, unrequestable | yes | [claude-ai-instructions.md](claude-ai-instructions.md) |
| claude.ai chat — iOS / Android | **never** | yes | same |
| Claude Code — WSL session | no | **no** | **plugins are unavailable in WSL sessions entirely** |
| Claude Code — Desktop **Cowork** tab | no | **no** | sources skills and plugins from the claude.ai account, not `~/.claude` — this plugin covers the **Code** tab only |

The markdown card is the only row that is yes wherever the plugin reaches at all — the last two
rows of that table are surfaces the plugin does not reach, which is a different failure from a
surface that cannot render the card. It is still the load-bearing deliverable, and the published
page is an escalation. The page is always additive: the inline card is written first and in full,
and if publishing fails or is unavailable the reply still stands on its own.

## Why the output style is forced (reversed in 2.4.0)

`output-styles/handover-cards.md` sets `force-for-plugin: true`, so it applies automatically
wherever the plugin is enabled.

2.3.0 shipped it **un-forced**, on the argument that forcing silently displaces whatever style the
user selected. That argument assumed the user could select one, and they cannot: `/output-style`
was deprecated in v2.1.73 and **removed in v2.1.91**, and the desktop app has no style picker at
all — `outputStyle` has to be written into a settings file by hand. Un-forced therefore meant
unreachable on the surface this is actually used on, and reaching it would have required exactly
the manual config editing the rules forbid. What forcing displaces is a settings-file value, not a
live choice.

Two limits stand regardless, and are the reason the injected rules remain the primary mechanism
rather than the style: output styles apply to the **main conversation only** — a subagent runs its
own system prompt, so `@house-rules:executor` is governed by `inject`, not by the style — and they
are read once at session start, so a change needs `/clear` or a new session.

`verify.py` asserts the field is **present**. It previously asserted the opposite; either way the
check exists so the decision cannot flip by accident, in whichever direction it currently points.

## `versioncheck` checks three copies of the version, not two

`inject` and `standards` assume the plugin they are running as is the one to trust. `versioncheck`
exists because that assumption broke on a real machine: `claude plugin marketplace add` answers
"already on disk" for a marketplace the device has seen before and does not re-fetch it, so a
machine that never separately ran `marketplace update` can sit on an old marketplace clone
indefinitely — and `claude plugin update` in that state reports "already at the latest version,"
naming the **old** version, because it never saw a newer one to update to (see `install_steps()`
in `tools/install.py` and the Commands section of `CLAUDE.md`). Comparing only the installed copy
against GitHub would miss this failure mode entirely on a machine where `plugin update` itself
lies; comparing installed against the local marketplace clone alone would miss it too, since both
can be stale together. Three copies — installed, the local marketplace clone, and GitHub's default
branch — is the minimum that can distinguish "you haven't run `plugin update`" from "your
marketplace clone itself never re-fetched" and point at the right one of the two commands.

The marketplace clone's plugin.json is found at a fixed relative path
(`claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json`) under whichever directory
sits inside `~/.claude/plugins/marketplaces/`, matching the `source` field this plugin's own
`marketplace.json` declares for itself. Only the top level of that directory is scanned, one
entry per marketplace a device has ever added — never deep — so a marketplace clone with a
different repo layout is reported as "could not tell," not treated as a mismatch.

### Why versioncheck's marker is a deliberate exception, not a reversal

`SessionStart` hooks cannot block a session — they can only add `additionalContext`, which is
easy to miss deep in a long transcript. The only hook event that can actually raise a real
permission prompt is `PreToolUse`, i.e. `guard`, but `guard`'s own design deliberately never
shells out or reaches the network on its hot path (it reads `.git/HEAD` directly rather than
calling `git`, precisely so a hung subprocess can never wedge every command in the session) — so
`guard` cannot redo the three-way version check itself on every call.

The reconciliation: `versioncheck` runs the check once, at `SessionStart`, and when it finds a
mismatch it writes a small marker file keyed by `session_id` under the OS temp directory. `guard`
reads that one file on the session's first `Bash`/`PowerShell` call, folds its reasons into the
permission prompt (even when the command itself trips no other rule), and deletes the file — so
the prompt fires once, not on every subsequent command.

This is new state, and CLAUDE.md's "no hook keeps state between invocations" bullet used to be
unconditional. It is kept as a scoped exception rather than reversed outright because the earlier
stateful design this repo removed (`track-write.sh` / `clear-pending.sh` / `deliverable.sh`,
recorded above) failed for a specific, avoidable reason: its `$TEMP` state file was shared rather
than session-scoped, so it leaked across sessions and went stale in ways nothing ever cleaned up.
`versioncheck`'s marker avoids exactly that failure mode: it is keyed to one `session_id`, so a
stray file from a crashed session is simply never read by any other session's `guard` call, and
the common path deletes it immediately after `guard` consumes it. `verify.py` tests both the
write and the consume-once behavior directly (`run_hook("versioncheck", ...)` then two
back-to-back `run_hook("guard", ...)` calls with the same `session_id`), rather than only
asserting the marker file's absence the way the old regression check does for the removed design.

## `docref.py` is a command, not a hook

`scripts/docref.py` checks and repairs the `doc-ref` pointers the archivist leaves in code (see
the Decisions entry of 2026-09-20). It is stdlib-only and keeps no state, like `hook.py`, but it
is deliberately not registered on any event: `hooks.json` is unchanged and the events table in
`CLAUDE.md` stays as it was. It reads the file list from `git ls-files` (tracked plus untracked
non-ignored) so build output is never scanned, falling back to a directory walk outside a git
work tree, and says which it used; a fallback names the reason git was unavailable, and walk
errors (unreadable directories) are UNREADABLE findings that fail the check. `fix` exits 2 if any
pointer file it found could not be read or written, and `new` warns on stderr when a file was
unreadable, since the id it prints may then collide. A doc-write hook that calls it is a possible
follow-up, to be priced with `tools/measure_footprint.py` before it is built.
