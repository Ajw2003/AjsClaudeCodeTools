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
SCOPE="$HERE/scope.sh"
ARTIFACT="$HERE/artifact.sh"
ROOT="$HERE/../../../.."
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
printf 'Scope:  %s\n' "$SCOPE"
printf 'Artif:  %s\n' "$ARTIFACT"
printf '\n'
printf 'Steps 1-20 feed one shell command each to the guard and check the decision:\n'
printf '  "ask"  = Claude Code will show you a permission prompt naming the rule.\n'
printf '  "pass" = the command runs with no extra prompt.\n'
printf 'Steps 21-23 check that the hooks cannot fail silently.\n'
printf 'Steps 24-32 check the scope reminder, the artifact reminder, and rule drift.\n'
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
  'The machine is fixed' \
  'Build only what was asked' \
  'Read the docs first, then check them against the code' \
  'Build for a human working alone' \
  'hands are for decisions, not labour' \
  'Deliver a whole workflow, not a starting point' \
  'Every artifact lives in the project directory' \
  'Never hide work in a background window or a silent process' \
  'Never commit without asking' \
  'Never take a destructive action without checking first'
do
  case "$OUT" in
    *"$H"*) ;;
    *) MISSING="$MISSING; $H" ;;
  esac
done
if [ -z "$MISSING" ]; then
  report PASS 'SessionStart injects every rule heading into context'
  printf '          %s characters injected\n' "$(printf '%s' "$OUT" | wc -c | tr -d ' ')"
else
  report FAIL 'SessionStart injects every rule heading into context'
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

# --- 24-25. the scope reminder reaches every prompt ---------------------------------------
# scope.sh has NO dependencies by design: on UserPromptSubmit a non-zero exit erases the
# user's prompt, so that hook must not be able to fail. Step 25 proves it by emptying PATH.
check_scope() { # $1=title  $2=nonempty to run with PATH emptied
  # PATH="" has to be written out literally as an assignment prefix; passing it in a
  # variable does not work, the shell would look for a command named PATH="".
  if [ -n "$2" ]; then
    OUT=$(PATH="" "$SH" "$SCOPE" 2>/dev/null </dev/null)
  else
    OUT=$("$SH" "$SCOPE" 2>/dev/null </dev/null)
  fi
  BAD=''
  case "$OUT" in *'"hookEventName":"UserPromptSubmit"'*) ;; *) BAD='wrong or missing hookEventName' ;; esac
  case "$OUT" in *'Windows 11'*) ;; *) BAD="$BAD; environment line missing" ;; esac
  case "$OUT" in *'only what was asked'*) ;; *) BAD="$BAD; scope line missing" ;; esac
  if [ -z "$BAD" ]; then
    report PASS "$1"
    printf '          %s characters of reminder injected\n' "$(printf '%s' "$OUT" | wc -c | tr -d ' ')"
  else
    report FAIL "$1"
    printf '          %s\n' "$BAD"
  fi
}
check_scope 'scope reminder is emitted ahead of every prompt' ''
check_scope 'scope reminder still works with PATH empty (it depends on nothing)' broken-path

# --- 26-30. the artifact reminder fires on documents written outside a project -------------
# Narrow on purpose: it reads the file_path field only, never the file contents. Step 29 is
# the case that would over-trigger if it grepped the whole payload the way guard.sh does.
art_case() { # $1=expect remind|silent  $2=title  $3=file_path  $4=extra payload
  OUT=$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s"%s}}' "$3" "$4" | "$SH" "$ARTIFACT" 2>/dev/null)
  case "$OUT" in
    *'artifact custody'*) GOT=remind ;;
    '') GOT=silent ;;
    *) GOT=malformed ;;
  esac
  if [ "$GOT" = "$1" ]; then report PASS "$2"; else report FAIL "$2"; fi
  printf '          expected %s, got %s\n' "$1" "$GOT"
}
art_case remind 'plan written to ~/.claude/plans is flagged for copying into the project' \
  'C:\\Users\\aj\\.claude\\plans\\some-plan.md' ''
art_case remind 'document written to the session scratchpad is flagged' \
  'C:\\Users\\aj\\AppData\\Local\\Temp\\claude\\scratchpad\\notes.md' ''
art_case silent 'document written inside the project is left alone' \
  'C:\\Users\\aj\\Desktop\\ClaudeDev\\AjsClaudeCodeTools\\docs\\plans\\x.md' ''
art_case silent 'file whose CONTENTS mention a temp path is left alone' \
  'C:\\Users\\aj\\Desktop\\proj\\README.md' ',"content":"put it in /tmp/ or scratchpad"'
art_case silent 'script in a temp directory is scratch work, not an artifact' \
  'C:\\Users\\aj\\AppData\\Local\\Temp\\build.sh' ''

# --- 31. the reminder in scope.sh has not drifted from the rules document ------------------
# scope.sh hardcodes its text so it cannot fail at runtime. That makes it a second copy of
# the wording, so this is the check that stops the two saying different things.
RULES_FILE="$HERE/../rules/house-rules.md"
DRIFT=''
for PHRASE in 'Windows 11' 'portability work' 'only what was asked' 'ask instead of assuming' 'project directory'; do
  if grep -qi "$PHRASE" "$SCOPE" 2>/dev/null; then
    grep -qi "$PHRASE" "$RULES_FILE" 2>/dev/null || DRIFT="$DRIFT; $PHRASE"
  fi
done
if [ -z "$DRIFT" ]; then
  report PASS 'scope.sh reminder still matches the rules document'
  printf '          every key phrase in the reminder appears in rules/house-rules.md\n'
else
  report FAIL 'scope.sh reminder still matches the rules document'
  printf '          in scope.sh but missing from house-rules.md%s\n' "$DRIFT"
fi

# --- 32. the rules have not been re-duplicated into CLAUDE.md ------------------------------
# The plugin injects the rules. A full copy in CLAUDE.md means the same text loads twice and
# the two can drift apart silently. A short pointer file is fine; no file at all is fine.
ROOT_CLAUDE="$ROOT/CLAUDE.md"
if [ ! -f "$ROOT_CLAUDE" ]; then
  report PASS 'repo CLAUDE.md is not a second copy of the rules'
  printf '          no CLAUDE.md at the repo root; the plugin is the only source\n'
elif grep -q 'Never take a destructive action without checking first' "$ROOT_CLAUDE" 2>/dev/null; then
  report FAIL 'repo CLAUDE.md is not a second copy of the rules'
  printf '          it holds a full copy of the rules; it should be a pointer\n'
else
  report PASS 'repo CLAUDE.md is not a second copy of the rules'
  printf '          it is a pointer (%s bytes), not a copy\n' "$(wc -c <"$ROOT_CLAUDE" | tr -d ' ')"
fi

printf '\n'
printf -- '--------------------------------\n'
if [ "$FAILURES" -eq 0 ]; then
  printf 'RESULT: PASS - all %s checks passed. The hooks are behaving as written.\n' "$STEP"
else
  printf 'RESULT: FAIL - %s of %s checks failed. See the FAIL lines above.\n' "$FAILURES" "$STEP"
fi
printf '\n'
printf 'Dependencies used by the hooks: sh, grep, sed, awk. No node, no jq, no python.\n'
printf 'scope.sh depends on nothing at all - a failing UserPromptSubmit hook would\n'
printf 'erase your prompt, so that one has no failure path to hit.\n'
printf 'Matching is textual, so a command that merely mentions a tripwire word will also\n'
printf 'prompt. That is deliberate - an extra keypress is cheaper than a missed commit.\n'
printf '\n'

[ "$FAILURES" -eq 0 ] || exit 1
exit 0
