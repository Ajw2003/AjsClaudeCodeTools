#!/bin/sh
# handover.sh — Stop hook.
#
# Rule: never hand over a command I have not run where they will run it. This is the only
# place in the plugin where that rule can actually be enforced.
#
# WHY IT HAS TO BE HERE. guard.sh sees commands Claude *runs*; runnable.sh sees runnable files
# Claude *writes*. A command typed straight into a reply passes neither — no hook event fires
# on assistant text. Stop is the one event that happens after the reply exists and before the
# turn ends, so it is the only point at which "you are about to hand this over" is checkable
# at all. It cannot read the reply either; what it can do is put the checklist in front of
# Claude at exactly the moment the turn would otherwise be delivered.
#
# DEPENDENCIES: /bin/sh and grep. No node, no jq, no python.
#
# FAILS OPEN, LOUDLY — the opposite of guard.sh, deliberately.
# guard.sh runs on PreToolUse, where a non-zero exit blocks one command; failing closed there
# costs a keypress. Here a non-zero exit STOPS THE TURN FROM ENDING. A handover check that
# fails closed does not protect anything, it wedges the session — the user cannot get a reply
# out at all. So every failure path prints a systemMessage and exits 0: the check goes offline
# visibly, and the turn still ends.
#
# STATELESS. Nothing is written anywhere. The one piece of state involved — has this hook
# already fired for this turn — is held by the harness and arrives in the payload as
# stop_hook_active. That is what makes a block-every-turn hook safe: the second pass sees the
# flag and stands down, so it can never loop. No $TEMP file, nothing to leak, nothing to reap.
#
# TOGGLE: set HOUSE_RULES_HANDOVER to off, 0 or false to disable it for a session. Unset means
# enabled, which is the default and the point.

set -u

# --- toggle: checked first, so a disabled hook costs nothing at all ----------------------

case "${HOUSE_RULES_HANDOVER:-on}" in
  off|OFF|Off|0|false|FALSE|False|no|NO|No) exit 0 ;;
esac

# --- preflight: go offline visibly, never wedge the turn ---------------------------------

if ! command -v grep >/dev/null 2>&1; then
  printf '{"systemMessage":"house-rules plugin: grep not found, so the command-handover check is offline for this session."}'
  exit 0
fi

PAYLOAD=$(cat 2>/dev/null) || {
  printf '{"systemMessage":"house-rules plugin: could not read the Stop payload, so the command-handover check is offline for this turn."}'
  exit 0
}

# Nothing to check is not a failed check.
[ -n "$PAYLOAD" ] || exit 0

# --- already fired this turn? then this is the retry, and it must be allowed to finish ---
#
# Matched textually, like everything else here. Spacing is allowed around the colon; only the
# literal true counts, so an absent or false flag falls through to the block below.
if printf '%s' "$PAYLOAD" | grep -qE '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

# --- the checklist -----------------------------------------------------------------------
#
# Hardcoded rather than read from rules/house-rules.md, for the same reason scope.sh hardcodes
# its reminder: a file read is a failure path, and this text has to be printable even when the
# rules file is not readable. That makes it a second copy, so verify.sh pins its key phrases
# against the rules document and fails on drift.
#
# The escape clause in the last sentence is load-bearing. This hook blocks every turn it sees
# fresh, so a turn that handed over no commands must be able to close in one cheap line rather
# than re-explaining the work.
NOTE='House rules, command handover - check before this turn ends. For every shell command in this reply, all five must be present: (1) the shell it runs in, named in the prose AND correct as the fence label - the fence label is what the Run button executes; (2) the absolute working directory to run it from; (3) the exact command, copy-pasteable, no placeholders; (4) what the user will see when it works; (5) UNTESTED: as the first word of the block if you did not run that exact command, in that shell, against those exact paths - running something similar is not running it. If anything is missing, fix the reply now. If this turn handed over no commands, say so in one line and stop - do not re-explain the work.'

printf '{"decision":"block","reason":"%s"}' "$NOTE"

exit 0
