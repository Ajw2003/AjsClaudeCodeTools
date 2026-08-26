#!/bin/sh
# deliverable.sh — Stop hook.
#
# Rule: deliver a whole workflow, not a starting point. If track-write.sh recorded a runnable
# file for this session and clear-pending.sh never saw a shell command run afterward, that file
# was written but never verified to work. Block once, name it, and let Claude decide whether to
# run it or explain why running does not apply.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# NEVER FAILS CLOSED ON ITS OWN ACCOUNT. Unlike guard.sh, a broken environment here should let
# Stop through, not hold the session hostage over a missing nag — so any failure to read the
# payload or the state file exits 0 rather than blocking.
#
# "stop_hook_active" being true means Claude Code already re-ran this hook once as part of the
# same block/continue cycle; blocking again would loop, so that case exits 0 silently.

set -u

command -v grep >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat 2>/dev/null) || exit 0
[ -n "$PAYLOAD" ] || exit 0

case "$PAYLOAD" in
  *'"stop_hook_active":true'*) exit 0 ;;
esac

SESSION=$(printf '%s' "$PAYLOAD" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
[ -n "$SESSION" ] || exit 0

STATE_FILE="${TEMP:-${TMP:-/tmp}}/house-rules-deliverable/$SESSION.txt"
[ -s "$STATE_FILE" ] || exit 0

LIST=$(sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' "$STATE_FILE" 2>/dev/null | awk '{printf "  - %s\\n", $0}')
[ -n "$LIST" ] || exit 0

rm -f "$STATE_FILE" 2>/dev/null

REASON="You wrote the following file(s) but never ran or verified them this turn:\n$LIST\nRun them (or start and confirm they work), or say why running does not apply, before finishing."

printf '{"hookSpecificOutput":{"hookEventName":"Stop","decision":"block","reason":"%s"}}' "$REASON"

exit 0
