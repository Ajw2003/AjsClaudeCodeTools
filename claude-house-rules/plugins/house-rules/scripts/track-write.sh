#!/bin/sh
# track-write.sh — PostToolUse hook for Write.
#
# Rule: deliver a whole workflow, not a starting point. A runnable file that gets written
# but never run is not delivered. This remembers which "runnable" files were written this
# session so deliverable.sh can nag, once, if none of them were ever executed before Stop.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# NEVER OBSTRUCTS. PostToolUse cannot block anyway — the write already happened — and state
# here is a best-effort nag, not a rule with teeth. If grep is missing, the payload cannot be
# read, or the state directory cannot be written, this exits 0 silently rather than losing or
# corrupting the write that already happened.

set -u

command -v grep >/dev/null 2>&1 || exit 0

PAYLOAD=$(cat 2>/dev/null) || exit 0
[ -n "$PAYLOAD" ] || exit 0

SESSION=$(printf '%s' "$PAYLOAD" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
FIELD=$(printf '%s' "$PAYLOAD" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1)
[ -n "$SESSION" ] && [ -n "$FIELD" ] || exit 0

FILEPATH=$(printf '%s' "$FIELD" | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
[ -n "$FILEPATH" ] || exit 0

# Runnable by extension, or a bare Dockerfile / docker-compose file with no extension.
BASE=$(printf '%s' "$FILEPATH" | grep -oE '[^\\/]+$')
printf '%s' "$BASE" | grep -qiE '\.(py|js|mjs|cjs|ts|sh|ps1|bat|cmd)$' ||
  printf '%s' "$BASE" | grep -qiE '^(dockerfile|docker-compose\.ya?ml)$' || exit 0

STATE_DIR="${TEMP:-${TMP:-/tmp}}/house-rules-deliverable"
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
STATE_FILE="$STATE_DIR/$SESSION.txt"

grep -qxF "$FILEPATH" "$STATE_FILE" 2>/dev/null || printf '%s\n' "$FILEPATH" >>"$STATE_FILE" 2>/dev/null

exit 0
