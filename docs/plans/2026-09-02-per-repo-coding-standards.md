# Per-repo coding standards, loaded by the house-rules plugin

> **Revised 2026-09-02**, after the environment-agnostic Python port
> ([2026-09-03-environment-agnostic-python-port.md](2026-09-03-environment-agnostic-python-port.md))
> landed. The original draft targeted the old one-`.sh`-per-event layout — `inject.sh`,
> `scope.sh`, `verify.sh`, `install.ps1`. None of those files exist now. The design below is
> unchanged in substance; what changed is where the code goes: a new **handler in `hook.py`**,
> not a new shell script, and checks in `verify.py`, not `verify.sh`.

## Context

Three standards documents exist — `coding-philosophy.md`, `csharp-unity-standards.md`,
`web-js-ts-node-standards.md` — in two copies: `C:\Users\aj\Desktop\Coding-Standards\` (the
`Ajw2003/Coding-Standards` clone) and `C:\Users\aj\.claude\`. Only one of the six copies is
ever loaded: `~/.claude/CLAUDE.md` ends with `@~/.claude/coding-philosophy.md`. The two
ecosystem docs are imported by nothing, in any project, on any device — they say
"imported per-project" in their own headers and no project does it.

Worse, the one that *does* load only loads in the CLI and desktop on this machine. Cloud and
web sessions run on managed VMs that never receive `~/.claude/`, so the import line resolves
to nothing there. Same reason `opusplan` in `settings.json` does not reach the desktop Code
tab: **anything not shipped inside the plugin does not exist on every surface.**

The outcome wanted: every session, on every surface, gets the global philosophy plus exactly
the ecosystem standards the repo it is sitting in actually needs — with no per-repo setup for
a normal Unity or Node project, and a one-line file for anything unusual.

## Approach

Vendor the standards into the plugin, select them per repo at `SessionStart` in a new
`standards` handler in `hook.py`, and give the selection a rule in `house-rules.md` so the
injected text carries authority rather than being background reading.

`Ajw2003/Coding-Standards` stays the place the documents are authored. A sync script copies
them into the plugin and shows what changed, so the vendored copies are provably current
instead of hopefully current.

### 1. Vendor the documents

New directory `claude-house-rules/plugins/house-rules/rules/standards/`, holding copies of the
three files under their existing names. Keeping the source filenames means the sync is a
straight copy with no name mapping, and the marker file (below) names documents by filename
stem.

Strip the "Suggested location `~/.claude/…`, imported with `@~/.claude/…`" blockquote from the
vendored copies — that instruction is now wrong, and a document telling the reader to install
it a way that no longer works is worse than no note. Make this edit **upstream** in
`C:\Users\aj\Desktop\Coding-Standards` first, so the sync stays a pure copy.

Unlike `rules/environment.md`, these files are **committed** — they must ship with the plugin
and arrive on a fresh clone. Confirm `.gitignore` does not swallow `rules/standards/`.

### 2. `standards` — a second `SessionStart` handler in `hook.py`

New `event_standards()` in
[scripts/hook.py](../../claude-house-rules/plugins/house-rules/scripts/hook.py), registered in
[hooks/hooks.json](../../claude-house-rules/plugins/house-rules/hooks/hooks.json) as a second
`SessionStart` entry: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" standards`.

A separate handler rather than more text bolted onto `event_inject()` because the rules
injection must not be able to fail on account of standards detection. Separate hook entry, so
one returning nothing does not take the other down.

Constraints it inherits, unchanged from the port:

- **Stdlib-only Python**, like every other handler. Detection is `os.path.exists` /
  `os.listdir`, no `find`, no subprocess.
- **Fails loud, not closed**, exactly like `inject`: a missing or unreadable standards file
  emits `{"systemMessage": "…"}` naming what could not be loaded, and exits 0. `SessionStart`
  cannot block anything, so there is nothing to fail closed on.
- **Project directory** resolves as `os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()`.
  No payload grepping.
- `run.sh` needs a fallback arm for `standards` alongside its existing per-event arms — when
  no interpreter probes successfully, it should behave like `inject`'s arm (warn visibly,
  exit 0), not like `guard`'s (block).

Selection logic, in order:

1. If `$PROJECT/.claude/standards` exists it is authoritative. Read it, one document stem per
   line, ignoring blanks and `#` comments. Detection does not run.
2. Otherwise detect. **Results union — a repo is allowed to be more than one stack** — and
   scanning covers the repo root *and one level of subdirectories*, because a mixed repo
   usually keeps each stack in its own folder (`Game/`, `web/`, `server/`) rather than piling
   both sets of markers at the root:
   - `coding-philosophy` — always, unconditionally.
   - `csharp-unity-standards` — `ProjectSettings/ProjectVersion.txt` exists, or `Assets/` is a
     directory, or any `*.csproj` matches.
   - `web-js-ts-node-standards` — `package.json`, `tsconfig.json`, or `deno.json` exists.

   Depth is exactly one level, never recursive — walking a repo containing `node_modules/` or
   Unity's `Library/` is slow enough to be felt at every session start. The depth-1 pass skips
   `node_modules`, `Library`, `Temp`, `obj`, `bin`, `.git` for the same reason.
3. Any named document not present in `rules/standards/` is reported in a `systemMessage` rather
   than silently skipped — a typo in `.claude/standards` must be visible.

Output is one JSON object carrying `hookSpecificOutput.additionalContext`, plus optionally
`systemMessage` for anything that could not be loaded.

**The preamble is what makes a multi-stack repo work.** It names each selected document
*together with the directory whose markers selected it*, so a repo that is Unity under `Game/`
and Node at the root produces something like:

> Two coding standards documents apply to this project. `csharp-unity-standards.md` governs C#
> and Unity code — selected because Unity project markers were found in `Game/`.
> `web-js-ts-node-standards.md` governs HTML, CSS, JS, TS and Node code — selected because Node
> markers were found at the repo root. Each governs its own languages; do not apply one stack's
> conventions to the other's files. `coding-philosophy.md` applies to all of it.

Without that, both documents arrive as one undifferentiated wall of rules and the C# ends up
formatted like TypeScript. The per-document scope line, not the selection itself, is the part
that earns its keep in a mixed repo.

### 3. Make it a rule, not just context

Injected text with no rule behind it is background reading. Add one section to
`rules/house-rules.md`, matching the existing style (`## ` heading, prose, bolded `**Why:**`):

> `## Code follows the standards loaded for this project`

Content: the standards injected at session start are binding for code written in this repo;
where a file's existing style conflicts with them the file wins (that carry-over is already in
`coding-philosophy.md`); **a repo can be more than one stack, and when several documents load
each governs only its own languages — the preamble says which, and applying one stack's
conventions to another's files is the failure this rule exists to prevent**; a repo whose needs
differ pins its own set in `.claude/standards` rather than the standards being ignored quietly.

Then add one line to `SCOPE_REMINDER` in `hook.py` — the `scope` handler is the only thing
keeping a rule live at message 200. Phrase it with words that also appear in the new rule
section: `verify.py`'s drift check fails otherwise.

### 4. Sync script

New `tools/sync_standards.py` — Python, not PowerShell, matching what the port did to the rest
of `tools/`. Shape follows `tools/install.py` (Pass/Fail/Info helpers, failure tally,
idempotent, non-zero exit on failure):

- `--from` defaults to `C:\Users\aj\Desktop\Coding-Standards`; `git -C <path> pull` first so the
  copy reflects current remote state, and report the resulting commit.
- Copy `*.md` into `rules/standards/`, printing which files changed and which were already
  identical. Nothing is deleted from the destination without naming it.
- Run `git diff --stat` on the destination at the end, so the change is visible before commit.

### 5. Remove the superseded copies

Once the plugin injects the philosophy doc, `@~/.claude/coding-philosophy.md` makes it load
twice from two sources that can diverge — the exact trap this repo's `CLAUDE.md` warns about
for the rules text.

- Delete the `@~/.claude/coding-philosophy.md` line from `C:\Users\aj\.claude\CLAUDE.md`.
- Delete `coding-philosophy.md`, `csharp-unity-standards.md`, `web-js-ts-node-standards.md`
  from `C:\Users\aj\.claude\`.

Outside the repo and outside the worktree. Do them **last**, after injection is verified
working, and state each deletion before running it.

### 6. Documentation

Both hook tables are checked by `verify.py` and will fail the suite if not updated:

- `CLAUDE.md` — new `SessionStart` / `standards` row in the hook table, plus a short subsection
  under "Where things live, and why" covering `rules/standards/`, the `.claude/standards`
  marker, and why vendoring rather than a submodule (`claude plugin install` does not recurse
  submodules, so the directory would be empty on every fresh machine and in every cloud
  session).
- `claude-house-rules/README.md` — matching row, plus a user-facing note on `.claude/standards`.
- Neither doc may state a hook count or a check count — `verify.py` fails on both.

## Files touched

| File | Change |
|---|---|
| `claude-house-rules/plugins/house-rules/rules/standards/*.md` | new — three vendored documents (committed) |
| `claude-house-rules/plugins/house-rules/scripts/hook.py` | new `event_standards()`, dispatch entry, one `SCOPE_REMINDER` line |
| `claude-house-rules/plugins/house-rules/scripts/run.sh` | fallback arm for the `standards` event |
| `claude-house-rules/plugins/house-rules/hooks/hooks.json` | second `SessionStart` entry |
| `claude-house-rules/plugins/house-rules/rules/house-rules.md` | new rule section |
| `claude-house-rules/plugins/house-rules/scripts/verify.py` | new checks (below) |
| `tools/sync_standards.py` | new |
| `CLAUDE.md`, `claude-house-rules/README.md` | hook table rows + prose |
| `C:\Users\aj\.claude\CLAUDE.md`, `C:\Users\aj\.claude\*.md` | remove superseded copies |

## Verification

`verify.py` is the source of truth for whether this works, so the checks land in the same
change as the code. Add a `std_case(expect, title, fixture)` helper in the existing style,
building a fixture directory under the scratchpad and removing it after, invoking the handler
through `run_hook("standards", ...)` with `CLAUDE_PROJECT_DIR` pointed at the fixture:

1. A bare directory injects `coding-philosophy` and neither ecosystem document.
2. `ProjectSettings/ProjectVersion.txt` injects the C#/Unity document.
3. `package.json` injects the web document.
4. Both markers at the root injects all three.
5. **The mixed-repo case, modelled on the rock-skipping project**: `package.json` at the root
   and `Game/ProjectSettings/ProjectVersion.txt` one level down injects all three, and the
   preamble names `Game/` as the reason the Unity document loaded. This is the check that
   fails if detection ever regresses to root-only.
6. `node_modules/package.json` in an otherwise bare directory does **not** select the web
   document — the skip list is doing its job.
7. `.claude/standards` naming only `web-js-ts-node-standards` in a Unity-shaped directory
   injects the web document and **not** the Unity one — override beats detection.
8. `.claude/standards` naming a nonexistent document produces a `systemMessage`, not silence.
9. `run.sh standards` with no working interpreter still prints a visible warning and exits 0
   (mirrors the existing `inject` no-interpreter check).
10. `CLAUDE_PROJECT_DIR` unset falls back to `os.getcwd()` and still detects correctly.
11. Drift: the new `## ` heading appears in the hook-table check, and the new `SCOPE_REMINDER`
    phrase appears in `house-rules.md`.

Then run the suite. **PowerShell 5.1**, working directory
`C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools`:

```powershell
python claude-house-rules\plugins\house-rules\scripts\verify.py
```

Expect a numbered PASS line per check and a passing RESULT line, exit code 0.

End-to-end, beyond the suite:

- Run `tools\sync_standards.py`; confirm it reports the source commit and either copies or
  reports-identical for all three documents.
- Reinstall with `tools\bootstrap.ps1`, fully restart Claude Code, and in a Unity repo and a
  Node repo ask *"which coding standards are loaded for this project?"* — it must answer from
  context without opening a file, and the two answers must differ. If it goes looking for
  files, nothing was injected.
- In this repo (neither Unity nor Node), confirm only the philosophy document loads.
- **In the rock-skipping project**, ask the same question: it must name both ecosystem
  documents *and* say which part of the tree each governs. This is the case the whole design
  turns on, so check it on the real repo, not only against a fixture.
