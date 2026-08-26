#!/bin/sh
# clear-pending.sh — PostToolUse hook for Bash|PowerShell.
#
# Something actually got executed this turn, so whatever track-write.sh recorded for this
# session no longer needs a nag: clear it.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# NEVER OBSTRUCTS. PostToolUse cannot block anyway. If grep is missing or the payload is
# unreadable, this exits 0 silently — worst case is a stale nag at Stop, never a blocked command.

set -u

command -v grep >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat 2>/dev/null) || exit 0
[ -n "$PAYLOAD" ] || exit 0

SESSION=$(printf '%s' "$PAYLOAD" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
[ -n "$SESSION" ] || exit 0

rm -f "${TEMP:-${TMP:-/tmp}}/house-rules-deliverable/$SESSION.txt" 2>/dev/null

exit 0
