---
description: Scan a project, project-wide, for long-form comments the harvest hook would flag
argument-hint: [path] [--verbose] [--min-lines N] [--min-chars N]
---

The `harvest` `PostToolUse` hook only ever looks at text written in the current turn — by
design, so it never nags about an essay that predates the session. That means it can never
answer "does this project already have any long-form comments to port," only "did this edit
just add one." This command is that answer: a manual, project-wide sweep using the exact same
detection code (`scripts/harvest_scan.py` calls `hook._harvest_blocks` directly), so the two can
never disagree about what counts as an essay.

Run, in this project's own root, using the installed plugin's own copy of the script so it
always matches whatever version is actually installed — never a path you construct by hand:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/harvest_scan.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path — the cache holds several versions.

If `$ARGUMENTS` is empty, this scans the current directory with the built-in or
`HOUSE_RULES_HARVEST_MIN_LINES`/`HOUSE_RULES_HARVEST_MIN_CHARS`-overridden thresholds — the
script's own defaults, unrelated to whatever project this command happens to run in.

Report the output as it comes back: each `file:start-end  LlinesLc` block found, and the final
summary line. Then:

- If nothing was found, say so in one line. Do not invent follow-up work.
- If blocks were found, **do not port them automatically.** Deciding where each one belongs
  (which tier-4 system doc, or a dated `docs/Decisions.md` entry) is the judgement call the
  `harvest` rule reserves for a human-reviewed turn, not a mechanical sweep — these are often
  comments a person wrote before the plugin existed, not something Claude just produced. List
  what was found and ask whether to port some, all, or none of it, the same way `@house-rules:
  archivist` would if this had come from a live edit.
