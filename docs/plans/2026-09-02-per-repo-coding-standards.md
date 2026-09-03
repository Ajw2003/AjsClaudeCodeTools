# Per-repo coding standards, loaded by the house-rules plugin

## Context

Three standards documents exist — `coding-philosophy.md`, `csharp-unity-standards.md`,
`web-js-ts-node-standards.md` — in two byte-identical copies, at
`C:\Users\aj\Desktop\Coding-Standards\` (the `Ajw2003/Coding-Standards` clone) and at
`C:\Users\aj\.claude\`. Only one of the six copies is ever loaded: `~/.claude/CLAUDE.md`
ends with `@~/.claude/coding-philosophy.md`. The two ecosystem docs are imported by nothing,
in any project, on any device — they say "imported per-project" in their own headers and no
project does it.

Worse, the one that *does* load only loads in the CLI and desktop on this machine. Cloud and
web sessions run on managed VMs that never receive `~/.claude/`, so the import line resolves
to nothing there. The same reason `opusplan` in `settings.json` does not reach the desktop
Code tab applies here: **anything not shipped inside the plugin does not exist on every
surface.**

The outcome wanted: every session, on every surface, gets the global philosophy plus exactly
the ecosystem standards that the repo it is sitting in actually needs — with no per-repo
setup for a normal Unity or Node project, and a one-line file for anything unusual.

## Approach

Vendor the standards into the plugin, select them per repo at `SessionStart` with a new
sibling hook to `inject.sh`, and give the selection a rule in `house-rules.md` so the
injected text carries authority rather than being background reading.

`Ajw2003/Coding-Standards` stays the place the documents are authored. A sync script copies
them into the plugin and shows what changed, so the vendored copies are provably current
instead of hopefully current.

### 1. Vendor the documents

New directory `claude-house-rules/plugins/house-rules/rules/standards/`, holding copies of
the three files under their existing names (`coding-philosophy.md`,
`csharp-unity-standards.md`, `web-js-ts-node-standards.md`). Keeping the source filenames
means the sync is a straight copy with no name mapping, and the marker file (below) names
documents by filename stem.

Strip the "Suggested location `~/.claude/…`, imported with `@~/.claude/…`" blockquote lines
from the vendored copies as part of the sync — that instruction is now wrong, and a document
that tells the reader to install it a way that no longer works is worse than no note. This
edit belongs upstream in `Coding-Standards` so the sync stays a pure copy; make it there
first, in the working clone at `C:\Users\aj\Desktop\Coding-Standards`.

### 2. `standards.sh` — a second `SessionStart` hook

New `claude-house-rules/plugins/house-rules/scripts/standards.sh`, registered in
`claude-house-rules/plugins/house-rules/hooks/hooks.json` as a second entry on `SessionStart`
alongside `inject.sh`. A separate script rather than more `%s` slots in `inject.sh` because
the rules injection must not be able to fail on account of standards detection, and because
`inject.sh`'s four-argument `printf` is deliberately fixed-shape.

It follows every constraint the existing scripts follow:

- **Dependencies: `sh`, `sed`, `awk` only.** No JSON parsing — reuse `inject.sh`'s
  `escape_file()` verbatim (copy it; a shared library file would be a new `.sh` in
  `scripts/` that `verify.sh` would then demand be registered as a hook).
- **Fails loud, not closed**, exactly like `inject.sh`: a missing or unreadable standards
  file emits `{"systemMessage":"…"}` naming what could not be loaded and exits 0.
  `SessionStart` cannot block anything, so there is nothing to fail closed on.
- **Project directory** resolves as `${CLAUDE_PROJECT_DIR:-$PWD}`. No payload grepping.

Selection logic, in order:

1. If `$PROJECT/.claude/standards` exists, it is authoritative. Read it, one document stem
   per line, ignoring blank lines and `#` comments. Detection does not run.
2. Otherwise detect. **Results union — a repo is allowed to be more than one stack**, and
   scanning covers the repo root *and one level of subdirectories*, because a mixed repo
   usually keeps each stack in its own folder (`Game/`, `web/`, `server/`) rather than
   piling both sets of markers at the root:
   - `coding-philosophy` — always, unconditionally.
   - `csharp-unity-standards` — if `ProjectSettings/ProjectVersion.txt` exists, or `Assets/`
     is a directory, or any `*.csproj` matches.
   - `web-js-ts-node-standards` — if `package.json`, `tsconfig.json`, or `deno.json` exists.

   Depth is exactly one level, never recursive — a `find` over a repo containing
   `node_modules/` or Unity's `Library/` is slow enough to be felt at every session start.
   The depth-1 pass skips `node_modules`, `Library`, `Temp`, `obj`, `bin` and `.git` for the
   same reason. One `for D in "$P" "$P"/*/` loop, no `find`.
3. Any named document not present in `rules/standards/` is reported in a `systemMessage`
   rather than silently skipped — a typo in `.claude/standards` must be visible.

Output is one JSON object carrying `hookSpecificOutput.additionalContext`, and optionally a
`systemMessage` for anything that could not be loaded.

**The preamble is what makes a multi-stack repo work.** It names each selected document
*together with the directory whose markers selected it*, so a repo that is Unity under
`Game/` and Node at the root produces something like:

> Two coding standards documents apply to this project. `csharp-unity-standards.md` governs
> C# and Unity code — selected because Unity project markers were found in `Game/`.
> `web-js-ts-node-standards.md` governs HTML, CSS, JS, TS and Node code — selected because
> Node markers were found at the repo root. Each governs its own languages; do not apply one
> stack's conventions to the other's files. `coding-philosophy.md` applies to all of it.

Without that, both documents arrive as one undifferentiated wall of rules and the C# ends up
formatted like TypeScript. The per-document scope line, not the selection itself, is the part
that earns its keep in a mixed repo.

### 3. Make it a rule, not just context

Injected text with no rule behind it is background reading. Add one section to
`claude-house-rules/plugins/house-rules/rules/house-rules.md`, matching the existing style
(an `## ` heading, prose, a bolded `**Why:**` close):

> `## Code follows the standards loaded for this project`

Content: the standards injected at session start are binding for code written in this repo;
where a file's existing style conflicts with them, the file wins (that carry-over is already
in `coding-philosophy.md`); **a repo can be more than one stack, and when several documents
load, each governs only its own languages — the preamble says which, and applying one
stack's conventions to another's files is the failure this rule exists to prevent**; a repo
whose needs differ pins its own set in `.claude/standards` rather than the standards being
ignored quietly.

Then add one line to the hardcoded reminder in
`claude-house-rules/plugins/house-rules/scripts/scope.sh` — it is the only thing that keeps a
rule live at message 200. Phrase it using words that also appear in the new rule section,
because `verify.sh` step 31 fails on drift between the two.

### 4. Sync script

New `tools/sync-standards.ps1`, following the shape of `tools/install.ps1` (Pass/Fail/Info
helpers, a failure tally, idempotent, exits non-zero on failure):

- `-From` defaults to `C:\Users\aj\Desktop\Coding-Standards`; `git -C <path> pull` first so
  the copy is from the current remote state, and report the resulting commit.
- Copy `*.md` into `rules/standards/`, printing which files changed and which were already
  identical. Nothing is deleted from the destination without naming it.
- Run `git diff --stat` on the destination at the end so the change is visible before commit.

### 5. Remove the superseded copies

Once the plugin injects the philosophy doc, `@~/.claude/coding-philosophy.md` makes it load
twice from two sources that can diverge — the exact trap the repo's own `CLAUDE.md` warns
about for the rules text.

- Delete the `@~/.claude/coding-philosophy.md` line from `C:\Users\aj\.claude\CLAUDE.md`.
- Delete `coding-philosophy.md`, `csharp-unity-standards.md`, `web-js-ts-node-standards.md`
  from `C:\Users\aj\.claude\`.

These are outside the repo and outside the worktree. Do them last, after the injection is
verified working, and state each deletion before running it.

### 6. Documentation

Both hook tables are checked by `verify.sh` and will fail the suite if not updated:

- `CLAUDE.md` — new `| \`SessionStart\` |` row for `standards.sh`, plus a short subsection
  under "Where things live, and why" covering `rules/standards/`, the `.claude/standards`
  marker, and why vendoring rather than a submodule (`claude plugin install` does not recurse
  submodules, so the directory would be empty on every fresh machine and in every cloud
  session).
- `claude-house-rules/README.md` — matching table row, and a user-facing note on
  `.claude/standards`.
- Neither doc may state a hook count or a check count — `verify.sh` fails on both.

## Files touched

| File | Change |
|---|---|
| `claude-house-rules/plugins/house-rules/rules/standards/*.md` | new — three vendored documents |
| `claude-house-rules/plugins/house-rules/scripts/standards.sh` | new — detection + injection |
| `claude-house-rules/plugins/house-rules/hooks/hooks.json` | register on `SessionStart` |
| `claude-house-rules/plugins/house-rules/rules/house-rules.md` | new rule section |
| `claude-house-rules/plugins/house-rules/scripts/scope.sh` | one reminder line |
| `claude-house-rules/plugins/house-rules/scripts/verify.sh` | new checks (below) |
| `tools/sync-standards.ps1` | new |
| `CLAUDE.md`, `claude-house-rules/README.md` | hook table rows + prose |
| `C:\Users\aj\.claude\CLAUDE.md`, `C:\Users\aj\.claude\*.md` | remove superseded copies |

## Verification

`verify.sh` is the source of truth for whether this works, so the checks land in the same
change as the code. Add cases in the existing style — a helper like `check_standards`
taking expected-substring and title, running `standards.sh` against a fixture directory
created under the shell's own temp and removed after:

1. A bare directory injects `coding-philosophy` and neither ecosystem document.
2. A directory with `ProjectSettings/ProjectVersion.txt` injects the C#/Unity document.
3. A directory with `package.json` injects the web document.
4. A directory with both markers at the root injects both, plus the philosophy.
5. **The mixed-repo case, modelled on the rock-skipping project**: a fixture with
   `package.json` at the root and `Game/ProjectSettings/ProjectVersion.txt` one level down
   injects all three documents, and the preamble names `Game/` as the reason the Unity
   document loaded. This is the check that fails if detection ever regresses to root-only.
6. `node_modules/package.json` in an otherwise bare directory does **not** by itself select
   the web document — the skip list is doing its job.
7. `.claude/standards` naming only `web-js-ts-node-standards` in a Unity-shaped directory
   injects the web document and **not** the Unity one — the override beats detection.
8. `.claude/standards` naming a nonexistent document produces a `systemMessage`, not silence.
9. `standards.sh` run with `PATH=""` still prints a visible warning (mirrors step 23).
10. `CLAUDE_PROJECT_DIR` unset falls back to `$PWD` and still detects correctly.
11. Drift: every `## ` heading in the new rule section appears in the injection (extend the
    step-22 heading list), and the new `scope.sh` phrase appears in `house-rules.md`.

Then run the suite — this is the command that proves the change, run from the worktree root:

```bash
& "C:\Program Files\Git\bin\sh.exe" claude-house-rules/plugins/house-rules/scripts/verify.sh
```

PowerShell 5.1, working directory
`C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\.claude\worktrees\dynamic-coding-standards-20a0ee`.
Expect a numbered PASS line per check and a passing RESULT line, exit code 0.

End-to-end, beyond the suite:

- Run `tools\sync-standards.ps1` and confirm it reports the source commit and either copies
  or reports-identical for all three documents.
- Reinstall with `tools\install.ps1`, fully restart Claude Code, and in a Unity repo and a
  Node repo ask *"which coding standards are loaded for this project?"* — it must answer
  from context without opening a file, and the two answers must differ. If it goes looking
  for files, nothing was injected.
- In this repo (neither Unity nor Node), confirm only the philosophy document loads.
- **In the rock-skipping project**, ask the same question: it must name both ecosystem
  documents *and* say which part of the tree each one governs. This is the case the whole
  design turns on, so check it on the real repo, not only against the test fixture.
