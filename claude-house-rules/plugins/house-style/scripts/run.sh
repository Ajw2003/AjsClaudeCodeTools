#!/bin/sh
# run.sh — the one thing every hooks.json entry calls. Resolves a working Python interpreter
# and hands the event name + stdin payload to style.py. Everything else lives in style.py; this
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
# Resolution order: $HOUSE_STYLE_PYTHON (if set, probed too — not trusted blindly), python3,
# python, py -3.
#
# DEPENDENCIES: /bin/sh only. This file must never itself need the thing it is looking for.
#
# FALLBACK WHEN NOTHING PROBES. What happens depends on which hook is calling, because the
# hook events have different failure contracts:
#   - styleguard (PreToolUse) -> fails CLOSED: 3 lines on stderr, exit 2. Blocks the publish.
#   - style (SessionStart)    -> fails LOUD, not closed: a systemMessage JSON on stdout, exit 0.
#                              Never blocks - there is nothing at session start to block, but
#                              an unstyled session nobody was told about is worse than noise.
#   - everything else         -> nothing on stdout, exit 0. styled is PostToolUse, which
#                              cannot block anyway: the write already happened.

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
if [ -n "${HOUSE_STYLE_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $HOUSE_STYLE_PYTHON
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
    styleguard)
      echo "house-style styleguard: no working Python interpreter found on PATH." >&2
      echo "Blocking this publish rather than shipping an unchecked page." >&2
      echo "Set HOUSE_STYLE_PYTHON to a working interpreter, or run /house-style list." >&2
      exit 2
      ;;
    style)
      printf '{"systemMessage":"house-style plugin: no working Python interpreter found on PATH. No house style was loaded into this session; artifacts will be built unstyled."}'
      exit 0
      ;;
    *)
      exit 0
      ;;
  esac
fi

if [ "${HOUSE_STYLE_DEBUG:-}" = 1 ]; then
  echo "house-style run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/style.py" "$EVENT"
