---
description: Create the three house labels a repo is missing, and list what was already there
argument-hint: [owner/repo]
---

This creates only the house labels a repo is missing: `AjsAgent created this`, `in progress` and
`needs review`. It never changes or deletes an existing label, whatever its colour or description.

Run, in this project's own root, using the installed plugin's own copy of the script so it always
matches whatever version is actually installed — never a path you construct by hand:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/labels.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path — the cache holds several versions.

Report the output as it comes back:

- Relay the repo, what was created and what was already there.
- Exit 1 because GitHub refused (for example HTTP 403 because the session has no access to that
  repo): say so and name the repo. Do not retry another way.
- Never edit or delete a label to "fix" a colour.
