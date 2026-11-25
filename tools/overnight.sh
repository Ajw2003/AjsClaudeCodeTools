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
#                                       SAME session by id (never --continue). Limits: HOUSE_RULES_OVERNIGHT_MAX_HOURS (24 h of work),
#                                       HOUSE_RULES_OVERNIGHT_NO_PROGRESS (5 restarts with no step closed); then one final QA-page pass.
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
slept=0
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
      slept=$((slept + secs)); $sleeper "$secs"
    else
      wait_kind=crash
      backoff=$((backoff == 0 ? 30 : backoff * 2)); [ "$backoff" -le 900 ] || backoff=900
      echo "overnight: claude crashed; backing off $backoff s before the next resume"
      slept=$((slept + backoff)); $sleeper "$backoff"
    fi
  else
    backoff=0
  fi
}
mkdir -p "$sfdir"; touch "$mark"
claude -p "$*" --session-id "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
after_run
# Two real limits: 24 h of work (wall clock minus waits) and 5 restarts with no step closed. Rate-limit waits never count.
clock=${HOUSE_RULES_OVERNIGHT_NOW:-date +%s}
max_secs=$((${HOUSE_RULES_OVERNIGHT_MAX_HOURS:-24} * 3600))
max_np=${HOUSE_RULES_OVERNIGHT_NO_PROGRESS:-5}
t0=$($clock)
noprog=0
prev=""
reason=""
while :; do
  # exit 1 = steps open; 0 = all done or no list; anything else (2 etc.) = could not tell, so stop and say so
  rc=0
  out=$(python3 "$note" steps-status "feature" --session "$sid") || rc=$?
  echo "$out"
  if [ "$rc" != 1 ]; then
    [ "$rc" = 0 ] || { echo "overnight: could not read the step list (exit $rc); stopping" >&2; break; }
    case "$out" in
      "NO STEP LIST") reason="no step list was recorded for this session" ;;
      *STUCK*) x=${out#ALL DONE (}; reason="all steps closed, but some are stuck: ${x%)}" ;;
      *) reason="all steps done" ;;
    esac
    break
  fi
  open=${out#OPEN }
  # a rate-limited run says nothing about progress, so it is not compared
  if [ -n "$prev" ] && [ "$wait_kind" != rate_limit ]; then
    if [ "$open" -lt "$prev" ]; then noprog=0; else noprog=$((noprog + 1)); fi
  fi
  prev=$open
  if [ $(($($clock) - t0 - slept)) -ge "$max_secs" ]; then reason="24-hour limit"; break; fi
  if [ "$noprog" -ge "$max_np" ]; then reason="5 restarts with no step closed"; break; fi
  touch "$mark"
  claude -p "$resume_text" --resume "$sid" --dangerously-skip-permissions || echo "overnight: claude exited with an error; checking the step list" >&2
  after_run
done
if [ -n "$reason" ]; then
  echo "overnight: loop ended: $reason"
  claude -p "[Subagent hand-back] Final pass: the run is ending ($reason). Build the QA page now from the ledger, list every open or stuck step first, and do not start new work." --resume "$sid" --dangerously-skip-permissions || echo "overnight: final pass failed" >&2
  rm -f "$sf"
fi
exit 0
