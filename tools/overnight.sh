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
sleeper=${HOUSE_RULES_OVERNIGHT_SLEEP:-sleep}
sfdir=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/house-rules-steps
sf="$sfdir/stopfailure-$sid.json"
mark="$sfdir/.overnight-start-$sid"
backoff=0
wait_kind=""
# After a claude run: act on a stopfailure file newer than the run's start, then delete it.
# wait_kind ends up rate_limit, crash or empty.
after_run() {
  wait_kind=""
  if [ -f "$sf" ] && [ ! "$mark" -nt "$sf" ]; then
    wait_kind=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kind"])' "$sf") || wait_kind=crash
    reset_at=$(python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get("reset_at"); print(int(v) if v else "")' "$sf") || reset_at=""
    rm -f "$sf"
    if [ "$wait_kind" = rate_limit ]; then
      if [ -n "$reset_at" ]; then secs=$((reset_at + 30 - $(date +%s))); else secs=${HOUSE_RULES_OVERNIGHT_RATE_WAIT:-300}; fi
      [ "$secs" -gt 0 ] || secs=0
      echo "overnight: rate limit hit; waiting $secs s for it to reset (this resume is not counted)"
      $sleeper "$secs"
    else
      wait_kind=crash
      backoff=$((backoff == 0 ? 30 : backoff * 2)); [ "$backoff" -le 900 ] || backoff=900
      echo "overnight: claude crashed; backing off $backoff s before the next resume"
      $sleeper "$backoff"
    fi
  else
    backoff=0
  fi
}
mkdir -p "$sfdir"; touch "$mark"
claude -p "$*" --session-id "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
after_run
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
  [ "$wait_kind" = rate_limit ] || n=$((n + 1))
  touch "$mark"
  claude -p "$resume_text" --resume "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
  after_run
done
