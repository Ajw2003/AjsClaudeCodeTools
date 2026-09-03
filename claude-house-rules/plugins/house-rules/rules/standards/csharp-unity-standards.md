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
  see Performance below.
- One class per file, filename matches class name (Unity/Rider expect this anyway).

## Project & folder structure

```
Assets/
  _Project/            # your code + content, kept separate from imported packages
    Scripts/
      Runtime/
      Editor/
    ScriptableObjects/
    Prefabs/
    Scenes/
  Plugins/              # third-party assets
```

- Assembly definitions (`.asmdef`) per major module (e.g. `Combat`, `Inventory`, `UI`) once
  a project grows past a handful of scripts — keeps compile times sane and enforces
  boundaries.
- Editor-only scripts go under an `Editor/` folder (or an `Editor`-only asmdef).

## Unity-specific patterns

- **Cache component references** in `Awake()`/`Start()`; never call `GetComponent<T>()` or
  `Find`/`FindObjectOfType` inside `Update()`, `FixedUpdate()`, or any per-frame callback.
- **Null-checks on `UnityEngine.Object`** should use Unity's overloaded `==`, not `?.` —
  `?.` skips Unity's "fake null" check for destroyed objects. `if (target != null)`, not
  `target?.DoThing()`, when `target` is a `MonoBehaviour`/`GameObject`/etc.
- **`ScriptableObject`s for shared data/config** (item definitions, tunable values) rather
  than hardcoding or duplicating across prefabs.
- **Coroutines vs. `async`/`await`**: coroutines for anything tied to Unity's frame loop or
  `yield return new WaitForSeconds(...)`-style timing; `async`/`await` for I/O (web requests,
  file access) where you don't need frame-precise control. Don't mix both for the same task.
- **Events**: prefer a lightweight C# event/`UnityEvent` or a ScriptableObject-based event
  channel over direct references between unrelated systems — keeps things decoupled and
  testable.
- **Serialization**: use `[SerializeField]` on private fields you want visible in the
  Inspector, rather than making the field public just to expose it.

## Performance

- Avoid allocations in per-frame code (`Update`, `OnGUI`, etc.) — no `new` on lists/arrays,
  no LINQ, no string concatenation in a hot loop. Reuse buffers instead.
- Pool frequently instantiated/destroyed objects (bullets, particles, enemies) rather than
  `Instantiate`/`Destroy` in a loop.
- Profile before optimizing — use the Unity Profiler to confirm a bottleneck exists before
  restructuring code around it.

## Testing

- Unity Test Framework (NUnit-based): **EditMode tests** for pure logic (no scene needed),
  **PlayMode tests** only when behavior genuinely depends on the Unity runtime/scene.
- Keep gameplay logic in plain C# classes where possible (not `MonoBehaviour`s) so it's
  testable without a scene.

## Tooling (Rider)

- Commit a shared `.editorconfig` at the repo root so Rider's formatter matches these
  conventions for everyone (and for Claude Code editing the same files).
- Enable Rider's Unity-specific inspections (e.g. "Expensive call in Update," fake-null
  warnings) — they catch most of the mistakes listed above automatically.
