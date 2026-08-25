#!/bin/sh
# inject.sh — SessionStart hook.
#
# Prints rules/house-rules.md back into Claude's context at the start of every session, in
# every project, on every device. This is the part that replaces copying a CLAUDE.md file
# into each repo.
#
# DEPENDENCIES: /bin/sh, sed and awk. No node, no jq, no python.
#
# NEVER FAILS SILENTLY. If the rules file cannot be read, it still prints a JSON object
# carrying a systemMessage, so a visible warning appears in the session instead of the
# rules quietly not being there.

set -u

HERE=$(dirname "$0")
RULES="$HERE/../rules/house-rules.md"

shout() {
  printf '{"systemMessage":"house-rules plugin: %s The rules were NOT loaded into this session."}' "$1"
  exit 0
}

command -v sed >/dev/null 2>&1 || shout 'sed not found on PATH.'
command -v awk >/dev/null 2>&1 || shout 'awk not found on PATH.'
[ -r "$RULES" ] || shout 'cannot read rules/house-rules.md.'

# Escape the markdown into a JSON string: backslashes, then double quotes, then strip CR,
# then fold every line ending into a literal \n.
BODY=$(sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\r$//' "$RULES" | awk '{printf "%s\\n", $0}')

[ -n "$BODY" ] || shout 'rules/house-rules.md is empty.'

PREAMBLE='The following are the user standing house rules. They apply to every project and override default behaviour. They are also enforced by a PreToolUse hook that will put a permission prompt in front of the user for mutating git commands, destructive commands, and backgrounded or hidden processes. That hook is a backstop, not permission to skip asking in chat first.\n\n'

printf '{"suppressOutput":true,"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s%s"}}' "$PREAMBLE" "$BODY"

exit 0
