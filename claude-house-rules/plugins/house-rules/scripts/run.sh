#!/bin/sh
# run.sh — the one thing every hooks.json entry calls. Resolves a working Python interpreter
# and hands the event name + stdin payload to hook.py. Everything else lives in hook.py; this
# file's only job is finding an interpreter that actually runs code.
#
# WHY A PROBE, NOT `command -v`. On this machine `python3` is the Windows Store App Execution
# Alias stub: it is on PATH, `command -v python3` finds it, but running it prints a refusal to
# STDOUT and exits 0. Treating "found on PATH" as "works" would exec that stub for every hook,
# Claude Code would see exit 0 with no JSON decision, and every guarded command would run
# unchecked — the exact node failure this plugin was built to avoid, reproduced with Python.
#
# So each candidate is PROBED: actually run it and check the output, not the exit code.
#   probe() { [ "$("$@" -c 'print(9)' 2>/dev/null)" = 9 ]; }
# The stub prints its install nag instead of "9" and is rejected. First candidate that probes
# wins. `py -3` is two words, so candidates are tried via `set --` / "$@", never a single
# variable that would get word-split by exec.
#
# Resolution order: $HOUSE_RULES_PYTHON (if set, probed too — not trusted blindly), python3,
# python, py -3.
#
# DEPENDENCIES: /bin/sh only. This file must never itself need the thing it is looking for.
#
# FALLBACK WHEN NOTHING PROBES. What happens depends on which hook is calling, because the
# three hook events have different failure contracts:
#   - guard (PreToolUse)   -> fails CLOSED: 3 lines on stderr, exit 2. Blocks the command.
#   - inject (SessionStart)-> fails LOUD, not closed: a systemMessage JSON on stdout, exit 0.
#   - everything else      -> nothing on stdout, exit 0. PostToolUse/Stop/UserPromptSubmit
#                              hooks either cannot block (PostToolUse) or must never block
#                              (UserPromptSubmit erases the prompt on non-zero exit; Stop
#                              wedges the session on non-zero exit).

set -u

# dirname is an external binary, and a broken PATH is exactly when this file has to still
# work. Parameter expansion instead, so the shim really does depend on nothing but sh.
case "$0" in
  */*) HERE=${0%/*} ;;
  *)   HERE=. ;;
esac
EVENT="${1:-}"

probe() {
  [ "$("$@" -c 'print(9)' 2>/dev/null)" = 9 ]
}

PY=''
if [ -n "${HOUSE_RULES_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $HOUSE_RULES_PYTHON
  if probe "$@"; then
    PY=set
  fi
fi

if [ -z "$PY" ]; then
  set -- python3
  if probe "$@"; then
    PY=set
  else
    set -- python
    if probe "$@"; then
      PY=set
    else
      set -- py -3
      if probe "$@"; then
        PY=set
      fi
    fi
  fi
fi

if [ -z "$PY" ]; then
  case "$EVENT" in
    guard)
      echo "house-rules guard: no working Python interpreter found on PATH." >&2
      echo "Blocking this command rather than letting it through unchecked." >&2
      echo "Run /house-rules:doctor, or set HOUSE_RULES_PYTHON to a working interpreter." >&2
      exit 2
      ;;
    inject)
      printf '{"systemMessage":"house-rules plugin: no working Python interpreter found on PATH. The rules were NOT loaded into this session. Run /house-rules:doctor."}'
      exit 0
      ;;
    *)
      exit 0
      ;;
  esac
fi

if [ "${HOUSE_RULES_DEBUG:-}" = 1 ]; then
  echo "house-rules run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
