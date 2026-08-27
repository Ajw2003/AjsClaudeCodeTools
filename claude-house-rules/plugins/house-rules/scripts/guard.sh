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
# WHAT IT MATCHES AGAINST — a three-tier ladder, safest first:
#
#   1. Payload unreadable, or grep missing -> stderr + exit 2. BLOCKS. Unchanged behaviour:
#      there is no path through this script that silently lets a command past.
#   2. Payload readable but no "command" field -> fall back to matching the WHOLE payload,
#      exactly as this script always did. A tool whose input field is named something else
#      is still checked; it is never waved through.
#   3. "command" field found -> match against that alone.
#
# Tier 3 is the point of the ladder. The raw payload also carries the tool's `description`
# field, so matching the whole thing meant a command *described* as "check for uncommitted
# changes before we commit" prompted on the word commit. artifact.sh already extracts a
# single field for exactly this reason; this does the same. The extraction regex allows
# backslash-escaped quotes, so a command containing "quoted text" is not truncated.
#
# Matching is still textual and still deliberately broad WITHIN whatever it is matching:
# a command that genuinely mentions a tripwire word prompts. An extra keypress is cheaper
# than a missed commit.

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

# --- tier 2 / tier 3: decide what to match against ---------------------------------------

FIELD=$(printf '%s' "$PAYLOAD" | grep -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' | head -n 1)
if [ -n "$FIELD" ]; then
  SUBJECT="$FIELD"
else
  SUBJECT="$PAYLOAD"
fi

# --- helpers ----------------------------------------------------------------------------

R1=''  # Never hide work in a background window or a silent process
R3=''  # Never commit without asking
R4=''  # Never take a destructive action without checking first

matches() {
  printf '%s' "$SUBJECT" | grep -qiE "$1"
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
#
# Only verbs that actually write history, the index, or the remote. Navigational verbs
# (checkout, switch, branch, tag, remote, submodule, and a bare add) used to prompt here
# under the reason "mutates the repo, the index, or the working tree" — which was false for
# most of them. A prompt that says something untrue trains you to approve without reading,
# so they were removed. The genuinely destructive checkout/restore/stash forms did NOT get
# dropped: they moved to Rule 4 below, where they belong.

if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([^[:alnum:]-]|$)'; then
  add3 'reaches a remote (push)'
fi
if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*(commit|reset|revert|clean|rebase|merge|filter-branch|cherry-pick|am|apply)([^[:alnum:]-]|$)'; then
  add3 'writes history, the index, or the working tree'
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
# Discarding uncommitted work is destructive in a way the others are not: there is no trash,
# no reflog for unstaged edits, and nothing to undo it with. Each form gets its own reason
# line so the prompt names what is actually about to be lost.
if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*(checkout[[:space:]]+(--|\.([[:space:]]|$))|restore([^[:alnum:]-]|$))'; then
  add4 'throws away uncommitted edits to a file (git checkout -- / git restore)'
fi
if matches 'git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*stash[[:space:]]+(drop|clear)([^[:alnum:]-]|$)'; then
  add4 'deletes stashed work permanently (git stash drop / clear)'
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
