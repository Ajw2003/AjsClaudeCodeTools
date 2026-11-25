#!/bin/sh
# C10 round 2 probe: guard refusal with nobody present writes no waiting-on-you entry and no approve/timeout text
H=$1; S=$2
for case in on bypass subagent attended; do
  R=$(mktemp -d "$S/r3-c10-$case-XXXX"); git -C "$R" init -q; git -C "$R" commit -q --allow-empty -m init
  mode=default; un=off; extra=""
  [ $case = on ] && un=on
  [ $case = bypass ] && mode=bypassPermissions
  [ $case = subagent ] && extra=',"agent_id":"a1"'
  pl='{"session_id":"qa-c10-'$case'","cwd":"'$R'","permission_mode":"'$mode'","tool_name":"Bash","tool_input":{"command":"rm -rf build","description":"no safe way: the rm manual page"}'$extra'}'
  out=$(cd "$R" && printf '%s' "$pl" | CLAUDE_PROJECT_DIR=$R HOUSE_RULES_UNATTENDED=$un HOUSE_RULES_PROMPT_TIMEOUT=600 HOUSE_RULES_HANDOFF=off python3 "$H" guard 2>"$R/err")
  wl=$(ls "$R/.git/house-rules/" 2>/dev/null | tr '\n' ' ')
  echo "== $case: decision=$(printf '%s' "$out" | grep -o '"permissionDecision": *"[a-z]*"') waiting-dir=[$wl]"
  printf '%s' "$out" | python3 -c 'import json,sys;d=json.load(sys.stdin)["hookSpecificOutput"]["permissionDecisionReason"];l=d.lower().replace("-"," ");print("  approve:", "approve to let it run" in l, "| waiting on you:", "waiting on you" in l, "| nobody answers:", "nobody answers" in l, "| final report:", "final report" in l, "| ledger_note.py decide:", "ledger_note.py decide" in d);print("  says UNATTENDED=on:", "HOUSE_RULES_UNATTENDED=on" in d, "| says Refused:", "refused" in l);print("  full:", d.replace("\n"," / "))'
done
