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
# Resolution order: $HOUSE_RULES_PYTHON (if set, probed too — not trusted blindly), else the
# cached interpreter in $HERE/.python-cache (see INTERPRETER CACHE below), else python3,
# python, py -3.
#
# DEPENDENCIES: /bin/sh only. This file must never itself need the thing it is looking for.
#
# FALLBACK WHEN NOTHING PROBES. All four events here are non-blocking, so none fails closed:
#   - inject, showrule (SessionStart) -> fails LOUD: a systemMessage JSON on stdout, exit 0.
#   - subagentrules (SubagentStart)   -> fails LOUD, same: a systemMessage on stdout, exit 0.
#   - scope (UserPromptSubmit)        -> nothing on stdout, exit 0 (a non-zero exit erases the
#                                       user's prompt).
# Same shape and wording as house-rules' scripts/run.sh, which these events were moved out of
# (#440, docs/4-systems/plugin-split.md).

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

# INTERPRETER CACHE. Probing python3 (the Windows Store stub) costs ~65 ms on every hook call,
# so the command that last passed `probe` is remembered in $HERE/.python-cache. Only a probed-
# good command is ever written, so the stub can never be cached. A cached command is trusted
# only while its first word still resolves (`command -v`); otherwise the file is deleted and
# the normal probe order runs again. The plugin directory is replaced on update, which resets
# the cache. A read-only plugin directory just means no cache - never a failure.
CACHE="$HERE/.python-cache"
FROM_CACHE=''

PY=''
if [ -n "${HOUSE_RULES_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $HOUSE_RULES_PYTHON
  if probe "$@"; then
    PY=set
    FROM_CACHE=override
  fi
elif [ -f "$CACHE" ]; then
  CACHED=''
  { IFS= read -r CACHED; } < "$CACHE" 2>/dev/null || :
  # shellcheck disable=SC2086
  set -- $CACHED
  if [ $# -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
    PY=set
    FROM_CACHE=yes
  else
    rm -f "$CACHE" 2>/dev/null || :
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
  if [ -n "$PY" ]; then
    # The braces matter: a failed `> file` prints its error before a trailing 2>/dev/null applies.
    { printf '%s
' "$*" > "$CACHE"; } 2>/dev/null || :
  fi
fi

if [ -z "$PY" ]; then
  case "$EVENT" in
    inject)
      printf '{"systemMessage":"house-rules plugin: no working Python interpreter found on PATH. The rules were NOT loaded into this session. Run /house-rules:doctor."}'
      exit 0
      ;;
    showrule)
      printf '{"systemMessage":"house-rules plugin: no working Python interpreter found on PATH. The show-don'"'"'t-tell rule was NOT loaded into this session. Run /house-rules:doctor."}'
      exit 0
      ;;
    subagentrules)
      printf '{"systemMessage":"house-rules plugin: no working Python interpreter found on PATH. This subagent did NOT receive the house rules core. Run /house-rules:doctor."}'
      exit 0
      ;;
    *)
      exit 0
      ;;
  esac
fi

if [ "${HOUSE_RULES_DEBUG:-}" = 1 ]; then
  echo "house-rules run.sh: HERE=$HERE interpreter=$* event=$EVENT cache=${FROM_CACHE:-no}" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
