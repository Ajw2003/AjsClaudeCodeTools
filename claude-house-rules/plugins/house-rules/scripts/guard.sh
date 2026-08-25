#!/bin/sh
# guard.sh — PreToolUse hook for Bash / PowerShell.
#
# Reads the pending shell command as a hook payload on stdin. If the command trips one of
# the house rules, prints a JSON decision asking Claude Code to put a permission prompt in
# front of the user, naming the rule. Otherwise prints nothing and the command runs.
#
# DEPENDENCIES: /bin/sh and grep. Nothing else. No node, no jq, no python.
# That is the point — this file must never be the reason the rules stop being enforced.
#
# FAILS CLOSED, LOUDLY. If grep is missing or the payload is unreadable, it writes to
# stderr and exits 2, which is a blocking error: the command does not run and the reason
# is shown. There is no path through this script that silently lets a command past.
#
# MATCHING is textual, against the whole raw payload rather than a parsed command field
# (parsing JSON in POSIX sh is where the runtime dependency came from). So it over-triggers
# rather than under-triggers: a command that merely mentions a tripwire word will also
# prompt. An extra keypress is cheaper than a missed commit.

set -u

# --- preflight: shout rather than shrug -------------------------------------------------

if ! command -v grep >/dev/null 2>&1; then
  echo "house-rules guard: grep not found on PATH, so the rules cannot be enforced." >&2
  echo "Blocking this command rather than letting it through unchecked." >&2
  echo "Fix PATH, or disable the house-rules plugin deliberately." >&2
  exit 2
fi

PAYLOAD=$(cat 2>/dev/null) || {
  echo "house-rules guard: could not read the hook payload from stdin." >&2
  echo "Blocking this command rather than letting it through unchecked." >&2
  exit 2
}

# An empty payload means there is nothing to check, not that a check failed.
[ -n "$PAYLOAD" ] || exit 0

# --- helpers ----------------------------------------------------------------------------

R1=''  # Never hide work in a background window or a silent process
R3=''  # Never commit without asking
R4=''  # Never take a destructive action without checking first

matches() {
  printf '%s' "$PAYLOAD" | grep -qiE "$1"
}

# Reason text must stay free of double quotes and real newlines: it is interpolated into a
# JSON string below, and \\n here becomes the two characters \n, which JSON reads as a break.
add1() { R1="$R1\\n    - $1"; }
add3() { R3="$R3\\n    - $1"; }
add4() { R4="$R4\\n    - $1"; }

# --- Rule: Never hide work in a background window or a silent process -------------------

if matches '\-WindowStyle[[:space:]]+Hidden'; then
  add1 'starts a hidden window you cannot watch'
fi
if matches 'Start-Process'; then
  add1 'spawns a separate process with Start-Process'
fi
if matches 'Start-Job|[[:space:]]-AsJob'; then
  add1 'runs the work as a background job'
fi
if matches '(^|[^[:alnum:]_.-])(nohup|setsid|disown)([^[:alnum:]_-]|$)'; then
  add1 'detaches the process from your terminal'
fi
if matches '[^&]&[[:space:]]*\\?"'; then
  add1 'backgrounds the command with a trailing ampersand'
fi

# --- Rule: Never commit without asking ---------------------------------------------------

if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([^[:alnum:]-]|$)'; then
  add3 'reaches a remote (push)'
fi
if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*(add|commit|checkout|switch|reset|revert|stash|rm|mv|branch|merge|rebase|clean|tag|cherry-pick|am|apply|remote|submodule|filter-branch)([^[:alnum:]-]|$)'; then
  add3 'mutates the repo, the index, or the working tree'
fi

# --- Rule: Never take a destructive action without checking first ------------------------

if matches '(^|[^[:alnum:]_./-])rm[[:space:]]+-[^[:space:]]*[rf]'; then
  add4 'deletes files recursively or by force'
fi
if matches 'Remove-Item'; then
  add4 'deletes files (Remove-Item)'
fi
if matches '(del|erase)[[:space:]]+/[fqs]|rmdir[[:space:]]+/s'; then
  add4 'deletes files (del /f or rmdir /s)'
fi
if matches 'Stop-Process|taskkill|pkill|kill[[:space:]]+-9'; then
  add4 'kills a running process'
fi
if matches 'Clear-Content|truncate[[:space:]]+-s'; then
  add4 'truncates or overwrites file contents in place'
fi

# --- decision ----------------------------------------------------------------------------

if [ -z "$R1" ] && [ -z "$R3" ] && [ -z "$R4" ]; then
  exit 0
fi

REASON='Your house rules want you asked before this runs:'
if [ -n "$R1" ]; then
  REASON="$REASON\\n\\n  Rule: Never hide work in a background window or a silent process$R1"
fi
if [ -n "$R3" ]; then
  REASON="$REASON\\n\\n  Rule: Never commit without asking$R3"
fi
if [ -n "$R4" ]; then
  REASON="$REASON\\n\\n  Rule: Never take a destructive action without checking first$R4"
fi
REASON="$REASON\\n\\nApprove to let it run, or reject and Claude will explain what it was about to do."

printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}' "$REASON"

exit 0
