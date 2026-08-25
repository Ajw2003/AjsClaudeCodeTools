#!/bin/sh
# inject.sh — SessionStart hook.
#
# Prints rules/house-rules.md back into Claude's context at the start of every session, in
# every project, on every device. This is the part that replaces copying a CLAUDE.md file
# into each repo.
#
# It also prints rules/environment.md, the recorded description of this machine. The first
# rule says to build for the environment that is written down rather than an assumed one, so
# the written-down one has to actually be in context. If that file is missing, this prints an
# instruction to go and discover it instead - a missing machine profile must read as "find
# out", never as "assume".
#
# DEPENDENCIES: /bin/sh, sed and awk. No node, no jq, no python.
#
# NEVER FAILS SILENTLY. If the rules file cannot be read, it still prints a JSON object
# carrying a systemMessage, so a visible warning appears in the session instead of the
# rules quietly not being there.

set -u

HERE=$(dirname "$0")
RULES="$HERE/../rules/house-rules.md"
# Overridable only so verify.sh can exercise the "profile is missing" path without
# moving the real file out from under a live session.
ENVFILE="${HOUSE_RULES_ENV_FILE:-$HERE/../rules/environment.md}"

shout() {
  printf '{"systemMessage":"house-rules plugin: %s The rules were NOT loaded into this session."}' "$1"
  exit 0
}

command -v sed >/dev/null 2>&1 || shout 'sed not found on PATH.'
command -v awk >/dev/null 2>&1 || shout 'awk not found on PATH.'
[ -r "$RULES" ] || shout 'cannot read rules/house-rules.md.'

# Escape a markdown file into a JSON string: backslashes, then double quotes, then strip CR,
# then fold every line ending into a literal \n.
escape_file() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\r$//' "$1" | awk '{printf "%s\\n", $0}'
}

BODY=$(escape_file "$RULES")
[ -n "$BODY" ] || shout 'rules/house-rules.md is empty.'

# The machine profile is optional on disk but never optional in context: absent, it becomes a
# standing instruction to go and find out.
if [ -r "$ENVFILE" ]; then
  ENVBODY=$(escape_file "$ENVFILE")
else
  ENVBODY=''
fi
if [ -z "$ENVBODY" ]; then
  ENVBODY='# This machine\n\nNOT RECORDED YET. rules/environment.md is missing or empty, so nothing is known about this machine beyond the Windows 11 / PowerShell 5.1 default.\n\nBefore relying on any environment fact - a shell, a tool, a version, a path - discover it by running the check, then write what you found into rules/environment.md. Do not assume it.\n'
fi

PREAMBLE='The following are the user standing house rules. They apply to every project and override default behaviour. They are also enforced by a PreToolUse hook that will put a permission prompt in front of the user for mutating git commands, destructive commands, and backgrounded or hidden processes. That hook is a backstop, not permission to skip asking in chat first.\n\n'

SEPARATOR='\n\n---\n\nThe machine these rules run on, as recorded. The first rule says to build for what is written here rather than what seems likely:\n\n'

printf '{"suppressOutput":true,"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s%s%s%s"}}' \
  "$PREAMBLE" "$BODY" "$SEPARATOR" "$ENVBODY"

exit 0
