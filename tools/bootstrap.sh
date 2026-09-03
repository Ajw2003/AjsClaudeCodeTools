#!/bin/sh
# bootstrap.sh — thin bootstrap: find a working Python, then hand off to tools/install.py.
#
# All real install logic lives in Python (tools/install.py). This file's only job is finding
# an interpreter that actually runs code, the same way run.sh does for the hooks - PROBED, not
# just found on PATH (python3 can be a stub that is on PATH but does not run anything).
#
# If nothing probes successfully, this prints the one install command for the detected OS and
# stops - there is no working install path without Python, and this repo does not ask you to
# run a manual prerequisite step first without telling you exactly what to run.

set -u

HERE=$(dirname "$0")
# Save the caller's own args before `set --` starts reusing "$@" to hold interpreter candidates.
ORIG_ARGS="$*"

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
  echo ''
  echo 'No working Python interpreter found on PATH.'
  echo 'Run the command for your OS, then re-run tools/bootstrap.sh:'
  echo ''
  case "$(uname -s 2>/dev/null)" in
    Darwin) echo '  brew install python' ;;
    Linux)
      if command -v apt >/dev/null 2>&1; then
        echo '  sudo apt install python3'
      elif command -v dnf >/dev/null 2>&1; then
        echo '  sudo dnf install python3'
      else
        echo '  install Python 3 with your distribution'"'"'s package manager'
      fi
      ;;
    *) echo '  winget install Python.Python.3.12' ;;
  esac
  echo ''
  exit 1
fi

echo "Using interpreter: $*" >&2
INTERP="$*"

# shellcheck disable=SC2086
exec $INTERP "$HERE/install.py" $ORIG_ARGS
