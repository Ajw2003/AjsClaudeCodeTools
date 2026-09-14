#!/bin/sh
# run.sh — resolves a working Python interpreter and hands the event name + stdin payload to
# hook.py. Ported unchanged in shape from house-rules'/prompt-workshop's run.sh — see those
# files for the full rationale on why this probes instead of trusting `command -v`.
#
# This plugin is a placeholder: one event (`inject`) so far. When this offshoot gets a real
# purpose, extend the EVENT case below the same way house-rules and prompt-workshop do — one
# fallback message per event, matched to that event's fail-open/fail-loud contract.
#
# Resolution order: $OFFSHOOT2_PYTHON (if set, probed too), python3, python, py -3.

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
if [ -n "${OFFSHOOT2_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $OFFSHOOT2_PYTHON
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
      printf '{"systemMessage":"offshoot-2 plugin: no working Python interpreter found on PATH. Nothing was loaded into this session."}'
      exit 0
      ;;
    *)
      exit 0
      ;;
  esac
fi

if [ "${OFFSHOOT2_DEBUG:-}" = 1 ]; then
  echo "offshoot-2 run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
