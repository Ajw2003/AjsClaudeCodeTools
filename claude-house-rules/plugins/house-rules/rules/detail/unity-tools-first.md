# Unity work starts with the Unity plugin and the Unity CLI

When a task touches a Unity project — scenes, prefabs, materials, shaders, packages, compile
errors, the Editor log, a build, a test run — my first move is to check what Unity tooling this
session has, and then to use it without being asked.

- **The Unity plugin.** Look at the skill listing for `unity:*` skills. Any whose description
  fits the task gets invoked before I start: `unity:unity-cli` for driving the Editor or the
  command line, `unity:unity-package-management` for packages, `unity:migrate-birp-to-urp` for
  pink materials after a pipeline change, `unity:ui` before any UI work, and so on.
- **The `unity` CLI.** Check it is on `PATH` (`command -v unity` in bash, `Get-Command unity` in
  PowerShell). When it is, use it to inspect and change a running Editor — hierarchy, assets,
  logs, compiling, running C# in the live Editor — instead of hand-editing scene or asset YAML,
  grepping `Editor.log`, or asking the user to click into the Editor for me.
- **Neither is available**, or the Editor it needs is not running or not connected: say which
  one, and why, in one line, then fall back to reading files and logs directly. A fallback taken
  silently hides that the better route existed.
- **Compiling** follows the same order. The CLI and plugin come first. Batch mode is only for
  when neither exists and I cannot install them myself. See "Verifying compilation" in
  `rules/standards/csharp-unity-standards.md`.

This sits under "Build only what was asked": checking for the tools and using them is how I do
the task, not an extra task. It does not license changes the request did not cover.

**Why:** the plugin and the CLI were installed and loaded, and I still only used them when the
user named them. On 2026-09-25 a merge left every URP material magenta in PlunderSpell; I
diagnosed it by grepping `Editor.log` and then had to ask the user to click into Unity so it
would recompile, when the CLI could have driven the open Editor and confirmed the fix itself.
The user wants these tools used proactively, as the default route into Unity.
