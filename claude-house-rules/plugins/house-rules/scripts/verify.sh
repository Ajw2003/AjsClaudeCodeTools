#!/bin/sh
# verify.sh — proves the house-rules hooks actually do what they claim.
#
# Run it yourself, any time, on any machine:
#
#     sh plugins/house-rules/scripts/verify.sh
#
# It feeds real hook payloads to guard.sh and inject.sh and prints a numbered PASS/FAIL
# line for each, then a final verdict. Exit code 0 = all passed, 1 = something failed.
# Nothing is hidden: every command tested is printed alongside its result.
#
# Depends on /bin/sh, grep, sed and awk — the same things the hooks depend on, so if this
# script runs at all, the hooks can run too.

set -u

HERE=$(dirname "$0")
GUARD="$HERE/guard.sh"
INJECT="$HERE/inject.sh"
SH=$(command -v sh)

STEP=0
FAILURES=0

esc() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

payload_for() {
  printf '{"session_id":"verify","tool_name":"Bash","tool_input":{"command":"%s"}}' "$(esc "$1")"
}

report() { # $1=PASS|FAIL  $2=title
  STEP=$((STEP + 1))
  if [ "$1" = FAIL ]; then FAILURES=$((FAILURES + 1)); fi
  printf '%2d. %s  %s\n' "$STEP" "$1" "$2"
}

printf '\n'
printf 'house-rules hooks - verification\n'
printf '================================\n'
printf 'Shell:  %s\n' "$SH"
printf 'Guard:  %s\n' "$GUARD"
printf 'Inject: %s\n' "$INJECT"
printf '\n'
printf 'Steps 1-20 feed one shell command each to the guard and check the decision:\n'
printf '  "ask"  = Claude Code will show you a permission prompt naming the rule.\n'
printf '  "pass" = the command runs with no extra prompt.\n'
printf 'Steps 21-23 check that the hooks cannot fail silently.\n'
printf '\n'

# Fields: expect | rule-title-that-must-be-cited (empty when expecting pass) | command
# No field may contain a | character. Fed in by redirect, not a pipe, so the loop runs in
# this shell and the tally below is real.
while IFS='|' read -r EXPECT RULE CMD; do
  [ -n "${CMD:-}" ] || continue

  OUT=$(payload_for "$CMD" | "$SH" "$GUARD" 2>/dev/null)
  if [ -z "$OUT" ]; then
    GOT=pass
  else
    case "$OUT" in
      *'"permissionDecision":"ask"'*) GOT=ask ;;
      *) GOT=malformed ;;
    esac
  fi

  RESULT=PASS
  CITED=''
  [ "$GOT" = "$EXPECT" ] || RESULT=FAIL
  if [ -n "$RULE" ]; then
    case "$OUT" in
      *"$RULE"*) CITED='; rule cited correctly' ;;
      *) CITED="; RULE NOT CITED (wanted: $RULE)"; RESULT=FAIL ;;
    esac
  fi

  report "$RESULT" "$CMD"
  printf '          expected %s, got %s%s\n' "$EXPECT" "$GOT" "$CITED"
done <<'EOF'
pass||git status
pass||git log --oneline -n 20
pass||git diff HEAD~1
pass||npm test
pass||ls -la src
pass||Get-ChildItem C:\Users
pass||npm run build && npm test
ask|Never commit without asking|git commit -m "wip"
ask|Never commit without asking|git add -A
ask|Never commit without asking|git push origin main
ask|Never commit without asking|git push --force-with-lease
ask|Never commit without asking|git checkout -b feature/x
ask|Never commit without asking|git reset --hard origin/main
ask|Never hide work in a background window or a silent process|Start-Process powershell -WindowStyle Hidden -ArgumentList "-File build.ps1"
ask|Never hide work in a background window or a silent process|npm run dev > dev.log 2>&1 &
ask|Never hide work in a background window or a silent process|nohup ./long-task.sh
ask|Never hide work in a background window or a silent process|Start-Job -ScriptBlock { ./build.ps1 }
ask|Never take a destructive action without checking first|rm -rf node_modules
ask|Never take a destructive action without checking first|Remove-Item -Recurse -Force ./dist
ask|Never take a destructive action without checking first|taskkill /IM node.exe /F
EOF

printf '\n'

# --- 21. fail-closed: a guard that cannot run must BLOCK, not shrug ----------------------
# PATH="" makes grep unfindable, standing in for any broken environment.
payload_for 'git commit -m x' | PATH="" "$SH" "$GUARD" >/dev/null 2>/dev/null
CODE=$?
ERR=$(payload_for 'git commit -m x' | PATH="" "$SH" "$GUARD" 2>&1 >/dev/null)
if [ "$CODE" -eq 2 ] && [ -n "$ERR" ]; then
  report PASS 'guard that cannot run exits 2 (blocking) and explains itself on stderr'
  printf '          said: %s\n' "$(printf '%s' "$ERR" | head -n 1)"
else
  report FAIL 'guard that cannot run exits 2 (blocking) and explains itself on stderr'
  printf '          exit code was %s; stderr was: %s\n' "$CODE" "$ERR"
fi

# --- 22. the rules actually reach the session --------------------------------------------
OUT=$("$SH" "$INJECT" 2>/dev/null </dev/null)
MISSING=''
for H in \
  'Never hide work in a background window or a silent process' \
  'Build things the user can run, verify, and keep' \
  'Never commit without asking' \
  'Never take a destructive action without checking first'
do
  case "$OUT" in
    *"$H"*) ;;
    *) MISSING="$MISSING; $H" ;;
  esac
done
if [ -z "$MISSING" ]; then
  report PASS 'SessionStart injects all four rules into context'
  printf '          %s characters injected\n' "$(printf '%s' "$OUT" | wc -c | tr -d ' ')"
else
  report FAIL 'SessionStart injects all four rules into context'
  printf '          missing%s\n' "$MISSING"
fi

# --- 23. inject fail-loud: a broken environment must still say something ------------------
OUT2=$(PATH="" "$SH" "$INJECT" 2>/dev/null </dev/null)
case "$OUT2" in
  *systemMessage*'NOT loaded'*)
    report PASS 'inject that cannot run still prints a visible warning'
    printf '          said: %s\n' "$OUT2" ;;
  *)
    report FAIL 'inject that cannot run still prints a visible warning'
    printf '          got: %s\n' "$OUT2" ;;
esac

printf '\n'
printf -- '--------------------------------\n'
if [ "$FAILURES" -eq 0 ]; then
  printf 'RESULT: PASS - all %s checks passed. The hooks are behaving as written.\n' "$STEP"
else
  printf 'RESULT: FAIL - %s of %s checks failed. See the FAIL lines above.\n' "$FAILURES" "$STEP"
fi
printf '\n'
printf 'Dependencies used by the hooks: sh, grep, sed, awk. No node, no jq, no python.\n'
printf 'Matching is textual, so a command that merely mentions a tripwire word will also\n'
printf 'prompt. That is deliberate - an extra keypress is cheaper than a missed commit.\n'
printf '\n'

[ "$FAILURES" -eq 0 ] || exit 1
exit 0
