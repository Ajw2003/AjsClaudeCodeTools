# Architecture rationale

This is the long-form "why" behind `CLAUDE.md`'s design constraints — moved here so the root
`CLAUDE.md` (auto-loaded every session, and re-paid on every subagent spawn) stays small. Read
this when you need the reasoning behind a constraint, not just the constraint itself.

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

`HARVEST_MIN_LINES` / `HARVEST_MIN_CHARS` default to 5 / 300 and are overridable per machine.
The defaults are not a taste call: see
[`comment-harvest-calibration.md`](comment-harvest-calibration.md) for what 5/300 and 10/600
each catch in this repository, and why the higher pair was effectively switched off.

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
call, against `inject`'s ~6,200 tokens per session, re-paid on every subagent spawn. Frequency
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
— each device records its own, and it never ships with the plugin. `inject` reads it alongside
the rules; if it's missing (a fresh clone, always), `inject` falls back to live runtime
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
format, and it does not render on iOS or Android at all. The surface table in `CLAUDE.md` records
what is actually reachable.

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
