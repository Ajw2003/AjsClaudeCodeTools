---
description: Set up the three house labels on this repo, or on a repo you name, creating only the missing ones
argument-hint: "[owner/repo]"
---

The issue workflow puts `AjsAgent created this` on every issue, and the design loop reads
`in progress` and `needs review` to tell whose move it is. `scripts/labels.py` creates whichever of
those three labels the repo is missing. It never changes or deletes a label that already exists,
whatever its colour or description.

Run it in this project's root, using the installed plugin's own copy of the script so it always
matches the installed version. Never use a path you construct by hand:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/labels.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path, because the cache holds several versions.

With no argument it works on this folder's GitHub remote; `owner/repo` names another repo.

- Exit 0: every house label is now present. Each line says `created` or `already there`.
- Exit 1: some labels could not be created. The `FAILED` lines say why, for example no permission
  on that repo.
- Exit 2: the repo could not be checked at all, for example when `gh` is not installed or the
  folder has no GitHub remote. The line says which.

Report the lines as they come back, in one short list. A failure is reported with its reason,
never retried by another route.
