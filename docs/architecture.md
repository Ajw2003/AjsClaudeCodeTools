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
