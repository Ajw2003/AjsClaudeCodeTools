---
description: Check, and optionally repair, the doc-ref pointers the archivist leaves in code
argument-hint: check|fix [--write] [--exclude GLOB] | new
---

The archivist moves long comments into `docs/` and leaves a pointer behind: `doc-ref <id> <path>`
in the code, and a `<!-- ref:<id> -->` marker line under the moved note's heading in the doc.
`scripts/docref.py` proves those pointers still lead somewhere, and repairs the ones a doc move
made stale. It is a command you run, not a hook: nothing runs it for you.

Run, in this project's own root, using the installed plugin's own copy of the script so it always
matches whatever version is actually installed — never a path you construct by hand:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path — the cache holds several versions.

If `$ARGUMENTS` is empty, run it with `check`.

- `check` — every pointer is ok, stale (the doc moved), dangling (no doc carries that id),
  ambiguous (two docs claim the id) or malformed. Exit 1 means it found something.
- `fix` — shows the stale paths it would rewrite. `fix --write` rewrites them. It resolves by id
  only, and never touches a dangling, ambiguous or malformed pointer.
- `new` — prints an unused 4-hex id, for the archivist to put on a new marker.
- `--exclude` patterns match the whole relative posix path, case-sensitively, and `*` matches across
  `/`; a pattern that matches no file is reported as a note. Besides the states above, findings
  can be `duplicate` (two markers claim one id, which is what makes a pointer to it ambiguous),
  `unreadable` or `undecodable` (a file it could not read or decode). Exit 2 means the run itself
  failed (bad `--root`, an internal error, or `fix --write` could not rewrite a file).

Report the output as it comes back. Then:

- Clean run: say so in one line. Do not invent follow-up work.
- **Dangling** pointers are a decision for the user, not something to repair on your own: either
  the note was deleted (remove the pointers) or its marker was lost (restore it). List them and
  ask which.
- Legacy prose pointers ("see the Traps section of physics.md") are counted, never judged. Do not
  convert them unless asked.
