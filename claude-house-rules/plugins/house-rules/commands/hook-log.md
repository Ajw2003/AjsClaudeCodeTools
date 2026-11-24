---
description: Show the last lines of the hook message log (default 30)
argument-hint: [N]
---

The plugin's status messages (what a hook decided, "looked, nothing to do", "saved") go to a log
file in the temp folder, not the chat. This command prints the newest lines of it. It is a command
you run, not a hook.

Run, using the installed plugin's own copy of the script so it always matches the installed
version. `$ARGUMENTS` is the number of lines:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/hooklog.py" $ARGUMENTS
```

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and tell
the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy.

If it prints `NO LOG:` or nothing, say so in one line and explain: the log only exists once a hook
has written to it; `HOUSE_RULES_TRACE=off` writes nothing, and the no-op traces ("looked, nothing to
do") are written only under `HOUSE_RULES_TRACE=verbose`. `HOUSE_RULES_TRACE=chat` also prints every
message in the chat. Do not go looking for the log elsewhere.

Report the lines as they come back, each is `UTC time, message`.
