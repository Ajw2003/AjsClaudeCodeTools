#!/bin/sh
# runnable.sh — PostToolUse hook for Write.
#
# Rule: deliver a whole workflow, not a starting point. A runnable file that gets written but
# never run is not delivered. This notices a runnable file being created inside the project
# and reminds Claude, in context, to run it before finishing.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# STATELESS BY CONSTRUCTION. An earlier version of this rule spanned three scripts and a Stop
# hook: track-write.sh recorded written files under $TEMP, clear-pending.sh deleted that record
# when any shell command ran, and deliverable.sh blocked Stop if the record survived. That
# bought exactly one thing — not nagging twice — and cost: a state file that leaked forever
# whenever a session ended without Stop firing (nothing ever reaped it), a rule the plugin
# enforces on others while breaking it itself (artifacts never live in a temp directory), and
# a nag any unrelated `ls` silently defeated. The reminder is the whole value; the state
# machine only suppressed duplicates. This is the reminder, with no memory at all.
#
# The cost of that, stated plainly: it fires on every runnable file created. The two cheapest
# false positives are cut instead — see below.
#
# IT NEVER PROMPTS THE USER. PostToolUse cannot block anyway (the write already happened).
# The nudge goes to Claude; the user sees nothing. Always exits 0.
#
# MATCHING is narrow, like artifact.sh and unlike guard.sh: it reads the file_path field alone,
# never the file contents, so a script that merely mentions a temp path is judged on where it
# actually is.

set -u

if ! command -v grep >/dev/null 2>&1; then
  printf '{"systemMessage":"house-rules plugin: grep not found, so the run-what-you-wrote reminder is offline for this session."}'
  exit 0
fi

PAYLOAD=$(cat 2>/dev/null) || exit 0
[ -n "$PAYLOAD" ] || exit 0

# Pull out just "file_path":"..." — the first one, which is the tool's own target.
FIELD=$(printf '%s' "$PAYLOAD" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1)
[ -n "$FIELD" ] || exit 0

# Runnable by extension, or a bare Dockerfile / docker-compose file with no extension.
BASE=$(printf '%s' "$FIELD" | grep -oE '[^\\/]+$')
printf '%s' "$BASE" | grep -qiE '\.(py|js|mjs|cjs|ts|sh|ps1|bat|cmd)"$' ||
  printf '%s' "$BASE" | grep -qiE '^(dockerfile|docker-compose\.ya?ml)"$' || exit 0

# False positive cut 1 is free and lives in hooks.json: this hook is registered on Write only,
# never Edit. Iterating on a script you are plainly already working on is where the reminder
# is least useful and fires most often.
#
# False positive cut 2 is here: a script written to a scratch location is not a deliverable.
# These are the same known-outside-the-project patterns artifact.sh uses, deliberately reusing
# one idea rather than introducing a second — no cwd extraction, no $CLAUDE_PROJECT_DIR, no
# prefix comparison of Windows paths inside JSON.
OUTSIDE=0
printf '%s' "$FIELD" | grep -qiE '[\/]+\.claude[\/]+plans[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qiE 'AppData[\/]+Local[\/]+Temp[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qiE '(^|[\/:"])(tmp|temp)[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qi 'scratchpad' && OUTSIDE=1

[ "$OUTSIDE" -eq 1 ] && exit 0

# Written at creation time, so it cannot say "you never ran it" — nothing has had the chance
# yet. It is a forward commitment instead of an accusation. verify.sh pins these phrases
# against rules/house-rules.md, the way it already pins scope.sh, so this copy cannot drift.
NOTE='House rules, whole workflows: you just created a runnable file. A runnable file you have not run is a starting point, not a whole workflow. Before you finish this task, run it and confirm it works, or say why running does not apply. Never hand over a command you have not run. This is a reminder to you; the user was not prompted and does not need to do anything.'

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' "$NOTE"

exit 0
