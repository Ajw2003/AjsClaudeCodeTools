# Trial: tree-sitter for the docs context layer's code map

Run 2026-10-18 for #306 (decisions log, "2026-10-18 - Docs map and freshness: aj's answers"). The
question: can `tree-sitter-language-pack` find every definition and reference in aj's real code,
fast enough for a hook?

## Setup

- A scratch Python 3.13 virtual environment outside the repo, with `tree-sitter-language-pack`
  1.22.1, which brought in `tree-sitter` 0.26.0. Nothing was installed into the system Python.
- `trial.py` (this folder) uses our own queries, not the package's tag queries, because those miss
  C# structs, enums, constructors, properties and plain calls.
- Corpora, read only:
  - This repo (`AjsClaudeCodeTools-329`): 26 Python files and 55 HTML pages.
  - PlunderSpell's own scripts (`Assets/_Project/Scripts`): 544 C# files. Third-party PurrNet is left out.
  - focus-deck-app: 14 JavaScript files, 3 HTML pages and 1 CSS file.
- No TypeScript project exists on this machine. The TypeScript and TSX grammars load and their queries
  compile, but nothing was measured.

Command, run twice with identical output (`output.txt`):

    <venv>/Scripts/python trial.py this-repo=<repo> PlunderSpell=<Assets/_Project/Scripts> focus-deck=<focus-deck-app>

## Results

| Language | Files | Definitions | References | Parse + query time |
|---|---|---|---|---|
| C# (PlunderSpell) | 544 | 5,334 | 18,157 | 0.53 s |
| Python (this repo) | 26 | 704 | 11,470 | 0.18 s |
| HTML (this repo) | 55 | 1,704 element ids | 60 src/href | 0.09 s |
| JavaScript (focus-deck) | 14 | 112 | 920 | 0.02 s |
| CSS (focus-deck) | 1 | 142 rule sets | 0 | under 0.01 s |

A whole run over all three projects took 1.0 s of wall time; one file took 0.12 s, Python's start-up
included. One page failed to parse cleanly: `docs/generated/architecture-review-2026-09-07.html`.

## Hand count against the tool

I read three files per language and counted by hand. Where the first run missed something, the query
was fixed and the count rerun; both numbers are given.

| Language | Files | Definitions | References, first run | References, after the fix |
|---|---|---|---|---|
| Python | `tools/_plugin_sync.py`, `tools/diff_parts.py` | 6 of 6 | 12 of 12 in `_plugin_sync.py`; `diff_parts.py` calls not counted | no fix needed |
| C# | `StateMachine.cs`, `CoinPouch.cs`, `GuardAttackSignaller.cs` | 20 of 20 | 14 of 21 | 21 of 21 |
| JavaScript | `project-filter.js`, `complexity.js`, `sync.js` | 20 of 20 | every call to the project's own functions, and both imports | no fix needed |
| HTML | `index.html`, `migrate-from-artifact.html`, `settings.html` | 17 of 17 ids | 6 of 7 in `index.html` | 7 of 7 |
| CSS | first 45 lines of `app.css` | 3 of 3 rule sets | none to find | none |

Python was checked on two files, not three; the third chosen file (`harvest_scan.py`) was not read.

What the first C# run missed: null-safe calls (`previous?.Exit()`, `Attacked?.Invoke(k)`) and event
subscriptions (`_signal.onChanged += OnReplicated`). In Unity code the subscriptions are the links
between systems, so the map needs them. The HTML miss was `<script src>`, which the grammar holds as a
separate node from other elements.

## What the trial shows

- **Speed is not a problem.** A full project costs about a second, and a hook only reparses the files
  that changed.
- **Definitions are reliable** in every language: 66 of 66 by hand.
- **References need our own queries, checked per language.** Both misses were query gaps, fixed in one
  line each. A test file of known cases per language belongs in the build.
- **Names alone don't resolve every call.** tree-sitter reads syntax, not types. In PlunderSpell, 25% of
  references match more than one definition (Unity methods such as `Update` x55 and `Awake` x54), and
  48% match none in the project (Unity and .NET calls). The map can say "these 55 classes define
  Update" but not which one a given call reaches. A dependency line built from names must say when
  it is ambiguous, rather than guess.
- **Script inside a page isn't read.** JavaScript written in an HTML page's own script tag is skipped.
  The house-rules pages are built that way, so the map would miss their code unless the build parses
  script tags as JavaScript.
- **Grammars download on first use.** Version 1.22.1 ships without grammars. It fetched 7 of them
  (12 MB) into `%LOCALAPPDATA%\tree-sitter-language-pack\v1.22.1\libs` the first time each language was
  asked for. The download address is not printed and was not found in the package's files. A fresh
  machine needs network access once, or the build must prefetch them at install.

## Not checked

- TypeScript and TSX on real code: no project here uses them.
- Python's third file, and CSS beyond its first 45 lines.
- Whether the grammar download works behind a proxy or offline, and where it downloads from.
- macOS and Linux wheels: only Windows was tried.
