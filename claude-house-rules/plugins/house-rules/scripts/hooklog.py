#!/usr/bin/env python3
"""hooklog.py - prints the last N lines (default 30) of the hook message log.

    python hooklog.py [N]

The plugin's status messages go to this log, not the chat (docs/4-systems/hook-message-log.md).
Stdlib only, like hook.py.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_rules.core import HOOK_LOG_NAME  # noqa: E402


def main(argv):
    n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 30
    path = os.path.join(tempfile.gettempdir(), HOOK_LOG_NAME)
    if not os.path.exists(path):
        print("NO LOG: %s (no hook has written to it yet)" % path)
        return 0
    with open(path, encoding="utf-8") as f:
        sys.stdout.write("".join(f.readlines()[-n:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
