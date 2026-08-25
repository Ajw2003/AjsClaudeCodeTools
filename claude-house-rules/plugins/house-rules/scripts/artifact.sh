#!/bin/sh
# artifact.sh — PostToolUse hook for Write / Edit.
#
# Rule: every artifact lives in the project directory. Some are not written there first — plan
# mode writes plan files to ~/.claude/plans, and scratch documents land in the session temp
# directory. This hook notices that and reminds Claude, in context, to copy the file into the
# project before finishing.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# IT NEVER PROMPTS THE USER. PostToolUse cannot block anyway (the write already happened), and
# this deliberately does not try to be a gate. The nudge goes to Claude; the user sees nothing.
# Always exits 0.
#
# MATCHING is deliberately narrow, unlike guard.sh. It greps out the file_path field alone
# rather than the whole payload, because a Write payload also carries the file CONTENTS - and a
# document that merely mentions /tmp would otherwise trigger on every save. verify.sh pins that.

set -u

if ! command -v grep >/dev/null 2>&1; then
  printf '{"systemMessage":"house-rules plugin: grep not found, so the artifact-location reminder is offline for this session."}'
  exit 0
fi

PAYLOAD=$(cat 2>/dev/null) || exit 0
[ -n "$PAYLOAD" ] || exit 0

# Pull out just "file_path":"..." — the first one, which is the tool's own target.
FIELD=$(printf '%s' "$PAYLOAD" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1)
[ -n "$FIELD" ] || exit 0

# Only documents. A script or source file written to a temp path is scratch work, not an artifact.
printf '%s' "$FIELD" | grep -qiE '\.(md|txt)"$' || exit 0

# Paths that are outside any project. Backslashes arrive doubled inside JSON, so accept either
# separator, one or more times.
OUTSIDE=0
printf '%s' "$FIELD" | grep -qiE '[\/]+\.claude[\/]+plans[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qiE 'AppData[\/]+Local[\/]+Temp[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qiE '(^|[\/:"])(tmp|temp)[\/]+' && OUTSIDE=1
printf '%s' "$FIELD" | grep -qi 'scratchpad' && OUTSIDE=1

[ "$OUTSIDE" -eq 1 ] || exit 0

NOTE='House rules, artifact custody: that document was written outside the project directory, so it is not tracked and will not outlive this session. Before you finish this task, copy it into the project as a real file - docs/ for documents, docs/plans/ for plans - and tell the user the path. This is a reminder to you; the user was not prompted and does not need to do anything.'

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' "$NOTE"

exit 0
