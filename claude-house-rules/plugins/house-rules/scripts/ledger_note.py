#!/usr/bin/env python3
"""ledger_note.py - park a question in a feature's QA ledger instead of stopping work (#598).

  ledger_note.py decide FEATURE --step S --choice C --assumption A --why W --undo U   (#638)
  ledger_note.py park FEATURE --step S --question Q --default D --affects A --category CAT --tried "CMD -> OUTPUT" [--answer HOW]
  ledger_note.py deviate FEATURE --step S --plan P --done D --why W --undo U   (#599)

deviate also takes --step-action add|replace|delete [--step-id N] [--check CMD]: delete is always refused,
replace keeps --step-id and needs a new --check, and a "Finish:" step is never touched.

Appends row K<n> to the Choices table (added to an older ledger without one), P<n> to the Parked
decisions table (hard stops only), or D<n> to the Deviations table of
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

## Choices

| # | Step | Choice made | Assumption | Why | How to undo |
|---|---|---|---|---|---|

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
"""


CATEGORIES = ("licence", "login", "purchase", "deletion", "money", "secrets", "other-people", "outward-post")


def cell(s):
    return " ".join(s.split()).replace("|", "\\|")


def main(argv):
    ap = argparse.ArgumentParser(prog="ledger_note.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("decide")
    k.add_argument("feature")
    for o in ("step", "choice", "assumption", "why", "undo"):
        k.add_argument("--" + o, required=True)
    p = sub.add_parser("park")
    p.add_argument("feature")
    for o in ("step", "question", "default", "affects"):
        p.add_argument("--" + o, required=True)
    p.add_argument("--category", required=True, choices=CATEGORIES)
    p.add_argument("--tried", required=True)
    p.add_argument("--answer", default="Reply with the answer to restore your choice; the default is easy to undo.")
    d = sub.add_parser("deviate")
    d.add_argument("feature")
    for o in ("step", "plan", "done", "why", "undo"):
        d.add_argument("--" + o, required=True)
    d.add_argument("--step-action", choices=("add", "replace", "delete"))
    d.add_argument("--step-id")
    d.add_argument("--check")
    a = ap.parse_args(argv)
    if a.cmd == "deviate" and a.step_action:
        err = None
        if a.step_action == "delete":
            err = "a step is never deleted; deviate by replacing it with a new check, or park a question"
        elif a.step.strip().lower().startswith("finish:"):
            err = "a Finish: step cannot be changed by a deviation"
        elif a.step_action == "replace" and not (a.step_id and a.check):
            err = "replacing a step needs --step-id N (the step keeps its id) and a new --check"
        elif a.step_action == "add" and not a.check:
            err = "adding a step needs a --check"
        if err:
            sys.stderr.write("ledger_note.py: refused: %s\n" % err)
            return 2
        a.done += " [step %s%s: check `%s`]" % (a.step_action, " " + a.step_id if a.step_id else "", a.check)
    if a.cmd == "decide":
        L, head, vals, verb = "K", "Choice made", (a.step, a.choice, a.assumption, a.why, a.undo), "decided"
    elif a.cmd == "park":
        if "->" not in a.tried:
            sys.stderr.write('ledger_note.py: --tried must be "<command> -> <output>"\n')
            return 2
        L, head, vals, verb = "P", "Question", (a.step, "[%s] %s (tried: %s)" % (a.category, a.question, a.tried), a.default, a.affects, a.answer), "parked"
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
    if L == "K" and "## Choices" not in text:  # an older ledger: add the table above Deviations, else at the end
        tbl = HEAD[HEAD.index("## Choices"):HEAD.index("## Deviations")].splitlines(True)
        i = next((j for j, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        if i and not lines[i - 1].endswith("\n"):
            lines[i - 1] += "\n"
        lines[i:i] = tbl
    at = None
    for i, ln in enumerate(lines):
        if ln.startswith("| %s" % L) or (at is None and ln.startswith("|---") and i and head in lines[i - 1]):
            at = i + 1
    if at is None:
        sys.stderr.write("ledger_note.py: %s has no %s table; add one or move the file away\n" % (path, {"P": "Parked decisions", "D": "Deviations"}[L]))
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
