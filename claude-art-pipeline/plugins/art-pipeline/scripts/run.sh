#!/bin/sh
# run.sh — the one thing every hooks.json entry in this plugin calls. Resolves a working
# Python interpreter and hands the event name + stdin payload to hook.py. Everything else
# lives in hook.py; this file's only job is finding an interpreter that actually runs code.
#
# Ported from prompt-workshop's, itself from house-rules' scripts/run.sh (see that file for the full rationale on
# why this probes instead of trusting `command -v`, and why word-splitting is avoided). Only
# the env var names and the per-event fallback messages differ.
#
# Resolution order: $ART_PIPELINE_PYTHON (if set, probed too), python3, python, py -3.

set -u

# A Windows caller may pass a backslash path (C:\x\run.sh); sh would see no "/" and use cwd.
SELF=$(printf '%s' "$0" | tr '\\' '/')
case "$SELF" in
  */*) HERE=${SELF%/*} ;;
  *)   HERE=. ;;
esac
EVENT="${1:-}"

probe() {
  [ "$("$@" -c 'print(9)' 2>/dev/null)" = 9 ]
}

PY=''
if [ -n "${ART_PIPELINE_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $ART_PIPELINE_PYTHON
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
    start)
      printf '{"systemMessage":"art-pipeline plugin: no working Python interpreter found on PATH. The review gate is NOT armed this session and will NOT run at Stop."}'
      ;;
    gate)
      printf '{"systemMessage":"art-pipeline plugin: no working Python interpreter found on PATH. The review gate did NOT run - any changed models are UNREVIEWED."}'
      ;;
    *)
      # seen: emits nothing and exits 0 - acceptable only because start already announced the
      # missing interpreter; the gate then announces again at Stop.
      ;;
  esac
  exit 0
fi

if [ "${ART_PIPELINE_DEBUG:-}" = 1 ]; then
  echo "art-pipeline run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
