#!/usr/bin/env python3
"""ledger_note.py - park a question in a feature's QA ledger instead of stopping work (#598).

  ledger_note.py park FEATURE --step S --question Q --default D --affects A [--answer HOW]
  ledger_note.py deviate FEATURE --step S --plan P --done D --why W --undo U   (#599)

Appends row P<n> to the Parked decisions table (or D<n> to the Deviations table) of
docs/qa/<folder>/ledger.md under the git project root (created with both tables if absent). Prints
`parked P<n> in <path>` or `deviated D<n> in <path>`. STDLIB ONLY.
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
    d = sub.add_parser("deviate")
    d.add_argument("feature")
    for o in ("step", "plan", "done", "why", "undo"):
        d.add_argument("--" + o, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "park":
        L, head, vals, verb = "P", "Question", (a.step, a.question, a.default, a.affects, a.answer), "parked"
    else:
        L, head, vals, verb = "D", "The plan said", (a.step, a.plan, a.done, a.why, a.undo), "deviated"
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
    n = max([int(x) for x in re.findall(r"^\| %s(\d+) " % L, text, re.M)] or [0]) + 1
    row = "| %s%d | %s |\n" % (L, n, " | ".join(cell(x) for x in vals))
    # Insert after the last row of this kind, else after its table's divider; a later section stays intact.
    lines = text.splitlines(True)
    at = None
    for i, ln in enumerate(lines):
        if ln.startswith("| %s" % L) or (at is None and ln.startswith("|---") and i and head in lines[i - 1]):
            at = i + 1
    if at is None:
        sys.stderr.write("ledger_note.py: %s has no %s table; add one or move the file away\n" % (path, "Parked decisions" if L == "P" else "Deviations"))
        return 2
    if not lines[at - 1].endswith("\n"):
        lines[at - 1] += "\n"
    lines.insert(at, row)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("%s %s%d in %s" % (verb, L, n, path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
