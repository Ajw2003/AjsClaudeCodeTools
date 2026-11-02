#!/usr/bin/env python3
"""verify.py - proves the rule-enforcement hooks do what they claim (#440).

    python claude-house-rules/plugins/rule-enforcement/scripts/verify.py

Runs checks/rule_enforcement.py (one part, the same layout as house-rules' scripts/checks/), prints its
output whole, and exits 0 only if every check passed. CI runs it beside house-rules' verify.py.
STDLIB ONLY, like hook.py.
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PART = os.path.join(HERE, "checks", "rule_enforcement.py")
RESULT_RE = re.compile(r"^RESULT: (PASS|FAIL)", re.MULTILINE)


def main():
    proc = subprocess.run([sys.executable, PART], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    text = proc.stdout.decode("utf-8", "replace")
    print(text, end="")
    m = RESULT_RE.search(text)
    if proc.returncode == 0 and m and m.group(1) == "PASS":
        print("rule-enforcement verify: every check passed.")
        return 0
    print("rule-enforcement verify: FAILED (exit %d%s)." % (proc.returncode, "" if m else ", no RESULT line - crashed?"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
