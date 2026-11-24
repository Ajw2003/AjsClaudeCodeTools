#!/usr/bin/env python3
"""Runs each acceptance criterion (C1 to C9) of the design review loop and saves each one's own output.

    python docs/qa/design-review-loop/run_acceptance.py [C1 C5 ...]

With criterion ids it runs only those; with none it runs all nine. It prints a line before and after each
run, because each run takes one to two minutes.

Run it from the repo root on branch ccr-1839130d-clohr1. For every criterion it runs verify.py once per
search text (`verify.py --only <text>` runs only the checks whose title contains the text), saves the full
output to docs/qa/design-review-loop/round-2/cN-M.txt, and counts the PASS and FAIL check lines.
A criterion passes only when every search text matched at least one check and no check failed.
It then prints one `CN: PASS|FAIL - <reason> - <file>` line per criterion, in the format of a round file,
and writes the same lines to docs/qa/design-review-loop/round-2/round-2-draft.md.
It changes nothing else. STDLIB ONLY, Python 3.8+.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
VERIFY = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts", "verify.py")
OUT = os.path.join(ROOT, "docs", "qa", "design-review-loop", "round-2")

CRITERIA = [
    ("C1", "reviewer modes and model pins", ["agents exist, pinned"]),
    ("C2", "page review stamp states", ["stamp"]),
    ("C3", "acceptance stamp lifecycle", ["acceptance:"]),
    ("C4", "QA gate", ["unverified"]),
    ("C5", "self-judging test and its handover card", ["selftest:"]),
    ("C6", "combined approval", ["(#600"]),
    ("C7", "parked questions", ["#598"]),
    ("C8", "deviations ledger", ["#599"]),
    ("C9", "docs, reversals and version", ["reversal", "version"]),
]

PASS_RE = re.compile(r"^\s*\d+\.\s+PASS\b", re.M)
FAIL_RE = re.compile(r"^\s*\d+\.\s+FAIL\b", re.M)


def main():
    os.makedirs(OUT, exist_ok=True)
    lines, failed = [], 0
    only = [a.upper() for a in sys.argv[1:]]
    for cid, what, texts in CRITERIA:
        if only and cid not in only:
            continue
        notes, ok, first_file = [], True, ""
        for i, text in enumerate(texts, 1):
            name = "%s-%d.txt" % (cid.lower(), i)
            path = os.path.join(OUT, name)
            first_file = first_file or "round-2/" + name
            print("%s: running verify.py --only %r (1 to 2 minutes)..." % (cid, text), flush=True)
            r = subprocess.run([sys.executable, VERIFY, "--only", text], cwd=ROOT, capture_output=True,
                               text=True, timeout=900)
            with open(path, "w", encoding="utf-8") as f:
                f.write("$ verify.py --only %r\nexit %d\n\n%s\n--- stderr ---\n%s" % (text, r.returncode, r.stdout, r.stderr))
            p, fl = len(PASS_RE.findall(r.stdout)), len(FAIL_RE.findall(r.stdout))
            notes.append("%r: %d pass, %d fail, exit %d" % (text, p, fl, r.returncode))
            print("%s: done, %s" % (cid, notes[-1]), flush=True)
            if p == 0 or fl or r.returncode:
                ok = False
        failed += 0 if ok else 1
        lines.append("%s: %s - %s (%s) - %s" % (cid, "PASS" if ok else "FAIL", what, "; ".join(notes), first_file))
    lines.append("STATUS: %s" % ("pass" if not failed else "fail"))
    text = "# Round 2\n" + "\n".join(lines) + "\n"
    with open(os.path.join(OUT, "round-2-draft.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
