---
description: Show the last lines of the hook message log (default 30)
argument-hint: [N]
---

The plugin's status messages (what a hook decided, "looked, nothing to do", "saved") go to a log
file in the temp folder, not the chat. This command prints the newest lines of it. It is a command
you run, not a hook.

Run this from the plugin root (the log is found through the temp folder, so no plugin path is built by hand). `$ARGUMENTS` is the number of lines:

```
python3 -c "import sys,os,tempfile; n=int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else 30; p=os.path.join(tempfile.gettempdir(),'house-rules-hook-log.txt'); print(''.join(open(p,encoding='utf-8').readlines()[-n:]),end='') if os.path.exists(p) else print('NO LOG: '+p)" $ARGUMENTS
```

If it prints `NO LOG:` or nothing, say so in one line and explain: the log only exists once a hook
has written to it; `HOUSE_RULES_TRACE=off` writes nothing, and the no-op traces ("looked, nothing to
do") are written only under `HOUSE_RULES_TRACE=verbose`. `HOUSE_RULES_TRACE=chat` also prints every
message in the chat. Do not go looking for the log elsewhere.

Report the lines as they come back, each is `UTC time, message`.
