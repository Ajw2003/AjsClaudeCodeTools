---
description: Check the plain-English doc copies under docs/plain/ against the plain-docs rules
argument-hint: [path]
---

`house-rules:plain-docs` (the skill) writes a plain-English copy of a technical doc.
`scripts/plain_docs_check.py` is the other half: it proves a plain copy actually follows the
rules the skill writes to, rather than trusting that it does. It is a command you run, not a
hook: nothing runs it for you.

Run, in this project's own root, using the installed plugin's own copy of the script so it always
matches whatever version is actually installed - never a path you construct by hand:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/plain_docs_check.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path - the cache holds several versions.

If `$ARGUMENTS` is empty, it checks every `.md` under `docs/plain/` in this project. Pass a
single file path to check just that one file instead.

Report the output as it comes back. Then:

- Clean run (no `FAIL` lines): say so in one line. `WARN` lines (a stale copy, or one over a
  quarter of its source's length) are informative, not something to fix on your own initiative -
  surface them and ask whether to redo the copy now or leave it.
- **`FAIL` lines are for the `house-rules:plain-docs` skill to fix**, not this command - load
  that skill and follow its steps for each flagged file, then run this check again until it's
  clean.
- The to-do lines it prints (`*(no plain copy yet)*` and `*(needs a doc)*`) are not failures.
  Report them as the running list of work still open, and do not start any of it unless asked.
