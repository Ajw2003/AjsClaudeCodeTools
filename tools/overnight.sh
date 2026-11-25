#!/bin/sh
# Start Claude Code for a run with nobody present (overnight).
#   HOUSE_RULES_UNATTENDED=on  house-rules plugin: every optional rule is off except autosave and the design loop,
#                              guard prompts are refused instead of asked, and AskUserQuestion / ExitPlanMode are
#                              denied so the agent decides itself. Decisions go to the QA ledger
#                              (ledger_note.py decide / park), not to a "Waiting on you" list.
#   ART_PIPELINE=unattended    art-pipeline plugin: the same idea, nothing waits on a person.
# --dangerously-skip-permissions means NOTHING asks before it runs. Use a throwaway branch or clone.
#   overnight.sh --interactive [args]   one normal claude session (the old behaviour).
#   overnight.sh "task text"            headless loop: runs claude -p, and while guarded steps stay open resumes the
#                                       SAME session by id (never --continue). Safety cap: HOUSE_RULES_OVERNIGHT_MAX_RESUMES (5).
set -eu
HOUSE_RULES_UNATTENDED=on
ART_PIPELINE=unattended
export HOUSE_RULES_UNATTENDED ART_PIPELINE
if [ "${1:-}" = "--interactive" ]; then
  shift
  exec claude --dangerously-skip-permissions "$@"
fi
sid=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=1000
CLAUDE_SESSION_ID=$sid
export CLAUDE_CODE_STOP_HOOK_BLOCK_CAP CLAUDE_SESSION_ID
here=$(dirname "$0")
note="$here/../claude-house-rules/plugins/house-rules/scripts/ledger_note.py"
max=${HOUSE_RULES_OVERNIGHT_MAX_RESUMES:-5}
resume_text='[Subagent hand-back] Resume: you stopped before every step in the guarded step list was done. Carry on with the next open step.'
claude -p "$*" --session-id "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
n=0
while :; do
  # exit 1 = steps open; 0 = all done or no list; anything else (2 etc.) = could not tell, so stop and say so
  rc=0
  python3 "$note" steps-status "feature" --session "$sid" || rc=$?
  [ "$rc" = 1 ] || { [ "$rc" = 0 ] || echo "overnight: could not read the step list (exit $rc); stopping" >&2; break; }
  if [ "$n" -ge "$max" ]; then
    echo "overnight: stopped after $max resumes with steps still open (HOUSE_RULES_OVERNIGHT_MAX_RESUMES)"
    break
  fi
  n=$((n + 1))
  claude -p "$resume_text" --resume "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
done
