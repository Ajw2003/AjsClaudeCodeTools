# C# / Unity 6 Standards, detail

> The always-injected core is `rules/standards/csharp-unity-standards.md`. This file holds
> the sections moved out of it to keep that document under its size budget; the section
> text is unchanged. Read this file before writing or verifying Unity C# code.

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

## Verifying compilation

"Compiles fine" is not a claim to make from reading the code — see "A shim that compiles is not
proof the real code does" in the global rules. Before saying Unity/C# code builds, verify it
against the real toolchain, not a stand-in for Unity's own APIs.

- **First: the `unity` CLI and the Unity plugin, where they apply.** Check for the `unity`
  CLI on `PATH` and the `unity:*` skills (see "Unity work starts with the Unity plugin and the
  Unity CLI" in the core Unity standards), and use them to compile and read errors through the real
  Editor, including one that is already open.
- **Fallback only: Unity itself, in batch mode.** Use this only when that check found no CLI
  and no plugin, and I cannot install them myself. Say so first, then run against the real
  project: `Unity -batchmode -quit -projectPath <path> -logFile <logPath>` (or the platform's
  Unity executable, e.g. `Unity.exe` on Windows), then check `<logPath>` for `error CS` — Unity
  can exit 0 with compile errors logged, so the exit code alone is not enough. Batch mode cannot
  open a project the Editor already has open.
- **Last fallback: `dotnet build`/`msbuild` against the project's own generated `.csproj`/`.sln`**
  (Unity generates one per assembly definition) when the Unity Editor itself isn't installed or
  reachable here. This still resolves against the real Unity DLLs referenced in that `.csproj`,
  so it remains a real check.
- **Never a substitute for any of these:** a fake `UnityEngine` namespace, a reimplemented
  `MonoBehaviour`, or any other hand-rolled stand-in for the engine, built so a file compiles
  standalone outside Unity. That proves the stand-in compiles, not the code — do not report a
  result from it.
- **Nothing available** — no Unity install, no matching SDK, no way to invoke either from this
  machine: say so explicitly and label the code `UNTESTED:` rather than asserting it compiles.

## Tooling (Rider)

- Commit a shared `.editorconfig` at the repo root so Rider's formatter matches these
  conventions for everyone (and for Claude Code editing the same files).
- Enable Rider's Unity-specific inspections (e.g. "Expensive call in Update," fake-null
  warnings) — they catch most of the mistakes listed above automatically.
