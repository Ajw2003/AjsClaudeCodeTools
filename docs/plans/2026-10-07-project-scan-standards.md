# Plan: load standards by scanning the project at session start

Date: 2026-10-07. Status: proposed, waiting on approval.

## What aj asked for

At session start, quickly search the project and load only the house-rules standards that fit it.
Unity standards load only when the scan finds Unity signs (`MonoBehaviour`, the old Input Manager,
the new Input System, and so on). The same for other languages and engines, driven by a list of key
terms. A manual override.

Decisions taken on 2026-10-07 (asked, answered):

- **Scope: house-rules documents only.** The scan picks `rules/standards/*.md`. It does not turn
  other plugins (such as the `unity` plugin) on or off.
- **Detect and write documents** for the new ecosystems, not detection alone.
- **Override: add/remove on top.** `.claude/standards` keeps working as a full list; lines starting
  `+` or `-` adjust what the scan found instead of replacing it.

## What exists today (checked against the code)

`event_standards` in `scripts/hook.py` looks one folder deep for file names only: Unity is
`Assets/`, `ProjectSettings/ProjectVersion.txt` or any `.csproj`; Node is `package.json`,
`tsconfig.json` or `deno.json`. It never reads file contents. `.claude/standards` replaces
detection entirely. Combined output must stay under 9,500 characters (`verify.py`). Issue #43 already
asks to split detection from the wording.

## Design

**The key-term list** is a data file, `rules/standards/detect.json`, so adding a term is a one-line
edit, not a code change. Each entry names an ecosystem id, the document it loads, file-name markers,
the file extensions worth reading, and content key terms. First draft of ecosystems:

| id | loads | example key terms |
|---|---|---|
| unity | csharp-unity-standards | `MonoBehaviour`, `ScriptableObject`, `UnityEngine`, `UnityEngine.InputSystem`, `Input.GetAxis`, `ProjectVersion.txt` |
| dotnet | csharp-dotnet-standards | `.csproj` / `.sln` with no Unity terms, `Microsoft.NET.Sdk` |
| godot | godot-standards | `project.godot`, `extends Node`, `@export`, `GodotSharp` |
| unreal | unreal-cpp-standards | `*.uproject`, `UCLASS(`, `GENERATED_BODY()`, `UPROPERTY(` |
| web | web-js-ts-node-standards | `package.json`, `tsconfig.json`, `deno.json` |
| python | python-standards | `pyproject.toml`, `requirements.txt`, `def __init__(self` |
| cpp | cpp-standards | `CMakeLists.txt`, `#include <`, `std::` (not when Unreal matched) |
| rust | rust-standards | `Cargo.toml`, `fn main()`, `use std::` |
| go | go-standards | `go.mod`, `package main`, `func main()` |

**The quick scan.** File-name markers are checked first, as now. Then a bounded content scan: walks
up to four folders deep, skips heavy folders (`node_modules`, `Library`, `Temp`, `obj`, `bin`,
`.git`, `Intermediate`, `Saved`, `target`, `.venv`, `venv`, `build`, `dist`), reads only the listed
extensions, at most the first 64 KB of each file, at most 400 files, and stops at 1.5 seconds. Each
ecosystem stops being searched once found. When a limit cuts the scan short the output says so
(nothing fails silently).

**Behaviour change to flag:** a lone `.csproj` with no Unity terms will load the new .NET document
instead of the Unity one. Recorded in `Decisions.md`.

**The override.** `.claude/standards` lines:

- `unity` or `csharp-unity-standards` (no prefix) — the file is the full list, as today.
- `+python` — add to what the scan found. `-cpp` — remove it.
- `HOUSE_RULES_STANDARDS_SCAN=off` — skip the content scan; file-name markers only.

The session-start message says, per document, why it loaded: which marker or term, in which file,
or "added in `.claude/standards`".

**The size budget.** With up to nine documents, one project can exceed 9,500 characters. Each new
document is a short core (about 1,500 characters) in the same shape as `csharp-unity-standards.md`.
When the total still exceeds the budget, documents past the limit are listed by path with one line
saying to read them before editing that language, rather than silently dropped.

**The new documents** (`csharp-dotnet`, `godot`, `unreal-cpp`, `python`, `cpp`, `rust`, `go`)
are authored here in `rules/standards/`. `Ajw2003/Coding-Standards` is where standards are normally
authored; `tools/sync_standards.py` copies in and never deletes, so these survive a sync, but they
should be copied upstream afterwards. A follow-up issue tracks that.

## Steps (one issue each, under one parent)

1. Split `event_standards` into `detect` and `render` (existing issue #43). No behaviour change.
2. Add `detect.json` and the bounded content scan, with the report of what matched.
3. Add `+`/`-` override lines and `HOUSE_RULES_STANDARDS_SCAN=off`.
4. Make rendering budget-aware: documents over the limit become path pointers.
5. Write the seven new standards documents.
6. `verify.py` cases for every ecosystem, false positives, overrides, scan time on a large fixture,
   and the budget; docs (tier 4 hook-engine, decisions entry, roadmap, state, today); version bump.

Steps 2–5 each carry their own `verify.py` cases; step 6 closes the gaps and runs the full suite twice.
