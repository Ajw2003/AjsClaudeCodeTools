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
TRACK="$HERE/track-write.sh"
CLEARP="$HERE/clear-pending.sh"
DELIVER="$HERE/deliverable.sh"
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
printf 'Track:  %s\n' "$TRACK"
printf 'ClearP: %s\n' "$CLEARP"
printf 'Deliver:%s\n' "$DELIVER"
printf '\n'
printf 'Steps 1-20 feed one shell command each to the guard and check the decision:\n'
printf '  "ask"  = Claude Code will show you a permission prompt naming the rule.\n'
printf '  "pass" = the command runs with no extra prompt.\n'
printf 'Steps 21-23 check that the hooks cannot fail silently.\n'
printf 'Steps 24-34 check the scope reminder, the artifact reminder, the machine profile,\n'
printf 'and drift between the two places the rules are worded.\n'
printf 'Steps 35-40 check the deliverable-reminder hooks: track-write, clear-pending, deliverable.\n'
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
  'Match response depth to the task' \
  'Build only what was asked' \
  'Read the docs first, then check them against the code' \
  'Build for a human working alone' \
  'hands are for decisions, not labour' \
  'Deliver a whole workflow, not a starting point' \
  'Never hand over a command I have not run' \
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
  case "$OUT" in *'response depth'*) ;; *) BAD="$BAD; response-depth line missing" ;; esac
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
for PHRASE in 'response depth' 'Windows 11' 'portability work' 'only what was asked' 'ask instead of assuming' 'project directory' 'hand over a command'; do
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


# --- 33. the recorded machine profile actually reaches the session -------------------------
# Rule 1 says to build for the environment that is written down. That only works if the thing
# written down is in context, so this checks the profile is injected, not merely present.
OUT=$("$SH" "$INJECT" 2>/dev/null </dev/null)
MISSING_ENV=''
case "$OUT" in *'This machine'*) ;; *) MISSING_ENV='no machine profile in the injection' ;; esac
case "$OUT" in *'PowerShell'*) ;; *) MISSING_ENV="$MISSING_ENV; no shell recorded" ;; esac
case "$OUT" in *'NOT on PATH'*) ;; *) MISSING_ENV="$MISSING_ENV; the sh-not-on-PATH trap is not recorded" ;; esac
if [ -z "$MISSING_ENV" ]; then
  report PASS 'SessionStart injects the recorded machine profile'
  printf '          rules + machine profile = %s characters\n' "$(printf '%s' "$OUT" | wc -c | tr -d ' ')"
else
  report FAIL 'SessionStart injects the recorded machine profile'
  printf '          %s\n' "$MISSING_ENV"
fi

# --- 34. an unrecorded machine reads as "go and find out", never as "assume" ----------------
# Uses the override so the real environment.md is never moved out from under a live session.
OUT=$(HOUSE_RULES_ENV_FILE=/nonexistent-on-purpose "$SH" "$INJECT" 2>/dev/null </dev/null)
case "$OUT" in
  *'NOT RECORDED YET'*)
    report PASS 'a missing machine profile becomes an instruction to discover it'
    printf '          the session is told to go and find the facts, not to assume them\n' ;;
  *)
    report FAIL 'a missing machine profile becomes an instruction to discover it'
    printf '          the injection said nothing about the profile being absent\n' ;;
esac

# --- 35-40. the deliverable hooks: write a runnable file, verify it nags, verify running it ---
# clears the nag. A dedicated session id, cleaned up before and after, so these steps are
# deterministic and never collide with a real session's state.
DSESSION="verify-deliverable-$$"
DSTATE_DIR="${TEMP:-${TMP:-/tmp}}/house-rules-deliverable"
DSTATE_FILE="$DSTATE_DIR/$DSESSION.txt"
rm -f "$DSTATE_FILE" 2>/dev/null

write_payload() { # $1=file_path
  printf '{"session_id":"%s","tool_name":"Write","tool_input":{"file_path":"%s"}}' "$DSESSION" "$1"
}
run_payload() { # $1=session_id
  printf '{"session_id":"%s","tool_name":"Bash","tool_input":{"command":"npm test"}}' "$1"
}
stop_payload() { # $1=session_id  $2=nonempty for stop_hook_active:true
  if [ -n "$2" ]; then
    printf '{"session_id":"%s","stop_hook_active":true}' "$1"
  else
    printf '{"session_id":"%s","stop_hook_active":false}' "$1"
  fi
}

write_payload 'C:\\proj\\build.sh' | "$SH" "$TRACK" >/dev/null 2>/dev/null
if [ -f "$DSTATE_FILE" ] && grep -qF 'build.sh' "$DSTATE_FILE" 2>/dev/null; then
  report PASS 'track-write.sh records a runnable (.sh) file that was written'
else
  report FAIL 'track-write.sh records a runnable (.sh) file that was written'
fi

BEFORE=$(wc -l <"$DSTATE_FILE" 2>/dev/null | tr -d ' ')
write_payload 'C:\\proj\\notes.md' | "$SH" "$TRACK" >/dev/null 2>/dev/null
AFTER=$(wc -l <"$DSTATE_FILE" 2>/dev/null | tr -d ' ')
if [ "$BEFORE" = "$AFTER" ]; then
  report PASS 'track-write.sh ignores a non-runnable (.md) file'
else
  report FAIL 'track-write.sh ignores a non-runnable (.md) file'
  printf '          state file grew from %s to %s lines on a .md write\n' "$BEFORE" "$AFTER"
fi

OUT=$(stop_payload "$DSESSION" '' | "$SH" "$DELIVER" 2>/dev/null)
case "$OUT" in
  *'"decision":"block"'*'build.sh'*)
    report PASS 'deliverable.sh blocks Stop when a written file was never run, and names it' ;;
  *)
    report FAIL 'deliverable.sh blocks Stop when a written file was never run, and names it'
    printf '          got: %s\n' "$OUT" ;;
esac
if [ -f "$DSTATE_FILE" ]; then
  report FAIL 'deliverable.sh clears the state file after nagging once'
else
  report PASS 'deliverable.sh clears the state file after nagging once'
fi

write_payload 'C:\\proj\\build2.sh' | "$SH" "$TRACK" >/dev/null 2>/dev/null
run_payload "$DSESSION" | "$SH" "$CLEARP" >/dev/null 2>/dev/null
if [ -f "$DSTATE_FILE" ]; then
  report FAIL 'clear-pending.sh clears the state file once a shell command runs'
else
  report PASS 'clear-pending.sh clears the state file once a shell command runs'
fi

write_payload 'C:\\proj\\build3.sh' | "$SH" "$TRACK" >/dev/null 2>/dev/null
OUT=$(stop_payload "$DSESSION" yes | "$SH" "$DELIVER" 2>/dev/null)
if [ -z "$OUT" ] && [ -f "$DSTATE_FILE" ]; then
  report PASS 'deliverable.sh does not re-nag when stop_hook_active is true'
else
  report FAIL 'deliverable.sh does not re-nag when stop_hook_active is true'
  printf '          got: %s\n' "$OUT"
fi
rm -f "$DSTATE_FILE" 2>/dev/null

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
