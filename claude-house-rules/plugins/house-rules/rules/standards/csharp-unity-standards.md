# C# / Unity 6 Standards

> Scope: all Unity projects. Assumes `coding-philosophy.md` also applies — this doc only
> covers what's specific to C# and Unity. Project-specific architecture notes still belong
> in that project's own `CLAUDE.md`.

## C# style

- **Naming**: `PascalCase` for classes, methods, properties, public fields. `camelCase` for
  local variables and parameters. Private fields: `_camelCase` (leading underscore) so
  they're visually distinct from parameters/locals at a glance.
- **Braces**: Allman style (opening brace on its own line) — matches Rider/Unity defaults.
- Enable **nullable reference types** (`<Nullable>enable</Nullable>`) on new projects; on
  existing ones, opt in file-by-file rather than a big-bang migration.
- Prefer `var` when the type is obvious from the right-hand side; use the explicit type when
  it isn't (e.g. return values from a method call with a non-obvious name).
- LINQ is fine in setup/editor/non-hot-path code. Avoid it in anything called every frame —
  see Performance in the detail file.
- One class per file, filename matches class name (Unity/Rider expect this anyway).
- **Input**: the new Input System via the project's input actions; never `UnityEngine.Input`.

## Read the detail file before Unity C#

Before writing or verifying Unity C# code, read
`${CLAUDE_PLUGIN_ROOT}/rules/standards/csharp-unity-detail.md` first. It holds: Project &
folder structure, Unity-specific patterns, Performance, Testing, Verifying compilation,
Tooling (Rider).

## Unity work starts with the Unity plugin and the Unity CLI

Before any Unity task, check for the `unity:*` skills and the `unity` CLI, then use them
unprompted — never wait to be told. Missing or unreachable → say so, then fall back. See
`${CLAUDE_PLUGIN_ROOT}/rules/detail/unity-tools-first.md`.
