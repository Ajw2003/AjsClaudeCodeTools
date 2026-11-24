#!/usr/bin/env python3
"""ledger_note.py - park a question in a feature's QA ledger instead of stopping work (#598).

  ledger_note.py park FEATURE --step S --question Q --default D --affects A [--answer HOW]

Appends row P<n> to the Parked decisions table of docs/qa/<folder>/ledger.md under the git project
root (created with both tables if absent). Prints `parked P<n> in <path>`. STDLIB ONLY.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_page import qa_folder  # noqa: E402  (one folder rule, shared with the QA page)

HEAD = """# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
"""
ROW = re.compile(r"^\| P(\d+) ", re.M)


def cell(s):
    return " ".join(s.split()).replace("|", "\\|")


def main(argv):
    ap = argparse.ArgumentParser(prog="ledger_note.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("park")
    p.add_argument("feature")
    for o in ("step", "question", "default", "affects"):
        p.add_argument("--" + o, required=True)
    p.add_argument("--answer", default="Reply with the answer to restore your choice; the default is easy to undo.")
    a = ap.parse_args(argv)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if r.returncode:
        sys.stderr.write("ledger_note.py: not inside a git project (%s)\n" % r.stderr.strip())
        return 2
    path = os.path.join(r.stdout.strip(), "docs", "qa", qa_folder(a.feature), "ledger.md")
    text = HEAD
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    n = max([int(x) for x in ROW.findall(text)] or [0]) + 1
    row = "| P%d | %s |\n" % (n, " | ".join(cell(x) for x in (a.step, a.question, a.default, a.affects, a.answer)))
    # Insert after the last P row, else after the Parked table's divider; a later section stays intact.
    lines = text.splitlines(True)
    at = None
    for i, ln in enumerate(lines):
        if ln.startswith("| P") or (at is None and ln.startswith("|---") and i and "Question" in lines[i - 1]):
            at = i + 1
    if at is None:
        sys.stderr.write("ledger_note.py: %s has no Parked decisions table; add one or move the file away\n" % path)
        return 2
    if not lines[at - 1].endswith("\n"):
        lines[at - 1] += "\n"
    lines.insert(at, row)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("parked P%d in %s" % (n, path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
