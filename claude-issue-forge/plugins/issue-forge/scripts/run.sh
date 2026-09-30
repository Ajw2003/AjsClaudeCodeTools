#!/bin/sh
# run.sh — resolves a working Python interpreter and hands the event name + stdin payload to
# hook.py. Ported unchanged in shape from house-rules'/prompt-workshop's/agent-router's run.sh —
# see those files for the full rationale on why this probes instead of trusting `command -v`.
#
# Resolution order: $ISSUE_FORGE_PYTHON (if set, probed too), python3, python, py -3.

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
if [ -n "${ISSUE_FORGE_PYTHON:-}" ]; then
  # shellcheck disable=SC2086
  set -- $ISSUE_FORGE_PYTHON
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
      printf '{"systemMessage":"issue-forge plugin: no working Python interpreter found on PATH. Rules guidance was NOT loaded into this session."}'
      exit 0
      ;;
    *)
      # suggest (PostToolUse) can't block anyway - going quiet here just means no reminder was
      # made for this call, same fail-open posture as house-rules' artifact/runnable handlers.
      exit 0
      ;;
  esac
fi

if [ "${ISSUE_FORGE_DEBUG:-}" = 1 ]; then
  echo "issue-forge run.sh: HERE=$HERE interpreter=$* event=$EVENT" >&2
fi

exec "$@" "$HERE/hook.py" "$EVENT"
