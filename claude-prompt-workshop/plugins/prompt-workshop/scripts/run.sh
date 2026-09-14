#!/bin/sh
# run.sh — the one thing every hooks.json entry in this plugin calls. Resolves a working
# Python interpreter and hands the event name + stdin payload to hook.py. Everything else
# lives in hook.py; this file's only job is finding an interpreter that actually runs code.
#
# Ported unchanged from house-rules' scripts/run.sh (see that file for the full rationale on
# why this probes instead of trusting `command -v`, and why word-splitting is avoided). Only
# the env var names and the per-event fallback messages differ.
#
# Resolution order: $PROMPT_WORKSHOP_PYTHON (if set, probed too), python3, python, py -3.

set -u

case "$0" in
  */*) HERE=${0%/*} ;;
  *)   HERE=. ;;
esac
EVENT="${1:-}"

probe() {
  [ "$("$@" -c 'print(9)' 2>/dev/null)" = 9 ]
}

PY=''
if [ -n "${PROMPT_WORKSHOP_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $PROMPT_WORKSHOP_PYTHON
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
    inject)
      printf '{"systemMessage":"prompt-workshop plugin: no working Python interpreter found on PATH. The workshop methodology was NOT loaded into this session."}'
      exit 0
      ;;
    *)
      # workshop (UserPromptSubmit) must never block or erase the prompt - same contract as
      # house-rules' scope handler. Going quiet here just means the workshop check did not run.
      exit 0
      ;;
  esac
fi

if [ "${PROMPT_WORKSHOP_DEBUG:-}" = 1 ]; then
  echo "prompt-workshop run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
