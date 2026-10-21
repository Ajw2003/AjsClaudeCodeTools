#!/usr/bin/env python3
"""check_verify_inventory.py - proves the check inventory in docs/4-systems/verify-suites.md adds up (#369).

    python tools/check_verify_inventory.py                      # structure only; says so
    python tools/check_verify_inventory.py --output run.txt     # also compare against a saved verify.py run
    python tools/check_verify_inventory.py --run                # run verify.py once (about 2 minutes) and compare

What it proves, from the doc section "Which part every check belongs to (#369)":
  1. the grouped list covers check numbers 1..N once each: no gap, no overlap, no number past N;
  2. N equals the total in the summary table, and each part's count in the summary table equals the
     sum of that part's rows in the grouped list;
  3. the multi-part count stated in the doc equals the rows that name an "Also touches" part;
  4. with a verify.py run (--output or --run): the run printed exactly N numbered result lines, its
     RESULT line says "all N checks passed", and every row's "First check as printed" is a prefix of
     what the run printed for that row's first check number (so the numbers match the real run).
Stdlib only. Exit 0 = everything held, 1 = something did not, 2 = the doc section could not be read.
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOC = os.path.join(ROOT, "docs", "4-systems", "verify-suites.md")
VERIFY = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts", "verify.py")
HEADING = "## Which part every check belongs to (#369)"

problems = []


def fail(msg):
    problems.append(msg)
    print("FAIL  " + msg)


def ok(msg):
    print("ok    " + msg)


def section(text, heading, level):
    """The lines under `heading` up to the next heading of the same or higher level."""
    lines = text.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        return None
    out = []
    for ln in lines[start + 1 :]:
        m = re.match(r"^(#+) ", ln)
        if m and len(m.group(1)) <= level:
            break
        out.append(ln)
    return out


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=DOC)
    ap.add_argument("--output", help="a saved copy of verify.py's output to compare against")
    ap.add_argument("--run", action="store_true", help="run verify.py once and compare against it")
    args = ap.parse_args()

    text = open(args.doc, encoding="utf-8").read()
    sec = section(text, HEADING, 2)
    if sec is None:
        print("could not find the heading %r in %s" % (HEADING, args.doc))
        return 2
    summary = section(text, "### Summary: checks and seconds per part", 3)
    grouped = section(text, "### The full grouped list", 3)
    if not summary or not grouped:
        print("could not find the Summary and The full grouped list subsections under the heading")
        return 2

    # 2a. summary table
    parts = {}
    total_row = None
    for ln in summary:
        if not ln.startswith("|") or ln.startswith("|---") or ln.startswith("| Part"):
            continue
        c = cells(ln)
        name = c[0].replace("*", "")
        n = int(c[1].replace("*", ""))
        if name == "Total":
            total_row = n
        else:
            parts[name] = n
    if total_row is None or not parts:
        print("the summary table has no Total row or no parts")
        return 2

    # 1. grouped list
    seen = {}
    rows = []
    for ln in grouped:
        if not ln.startswith("| ") or ln.startswith("| Checks") or ln.startswith("|---"):
            continue
        c = cells(ln)
        rng = c[0]
        m = re.match(r"^(\d+)(?:-(\d+))?$", rng)
        if not m:
            fail("a grouped-list row has an unreadable check range: %r" % rng)
            continue
        lo = int(m.group(1)); hi = int(m.group(2) or m.group(1))
        if hi < lo:
            fail("row %s runs backwards" % rng)
            continue
        rows.append((lo, hi, c[2], c[3], c[6]))
        for n in range(lo, hi + 1):
            if n in seen:
                fail("check %d is listed twice (rows %s and %s)" % (n, seen[n], rng))
            seen[n] = rng
    n_max = max(seen) if seen else 0
    gaps = [n for n in range(1, n_max + 1) if n not in seen]
    if gaps:
        fail("checks missing from the list: %s" % gaps[:20])
    else:
        ok("the grouped list covers 1..%d with no gap" % n_max)
    if not any("listed twice" in p for p in problems):
        ok("no check is listed twice")

    # 2. totals and per-part sums
    listed = len(seen)
    if listed != total_row:
        fail("the list holds %d checks but the summary table total is %d" % (listed, total_row))
    else:
        ok("list total %d = summary total %d" % (listed, total_row))
    by_part = {}
    for lo, hi, part, _also, _first in rows:
        by_part[part] = by_part.get(part, 0) + hi - lo + 1
    for name, n in parts.items():
        if by_part.get(name, 0) != n:
            fail("part %r: summary says %d, the list sums to %d" % (name, n, by_part.get(name, 0)))
    for name in by_part:
        if name not in parts:
            fail("part %r is in the list but not in the summary table" % name)
    if sum(parts.values()) != total_row:
        fail("the summary rows add to %d but its Total row says %d" % (sum(parts.values()), total_row))
    if not problems:
        ok("each part's summary count equals the sum of its rows (%s)" % ", ".join("%s %d" % kv for kv in parts.items()))

    # 3. multi-part count
    multi = sum(hi - lo + 1 for lo, hi, _p, also, _f in rows if also)
    m = re.search(r"Multi-part checks: (\d+)\.", text)
    if not m:
        fail("the doc does not state 'Multi-part checks: N.'")
    elif int(m.group(1)) != multi:
        fail("the doc says %s multi-part checks, the list's Also-touches rows add to %d" % (m.group(1), multi))
    else:
        ok("multi-part count %d matches the list" % multi)

    # 4. compare with a real run
    out_text = None
    if args.run:
        print("running verify.py once (about 2 minutes)...")
        p = subprocess.run([sys.executable, VERIFY], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        out_text = p.stdout.decode("utf-8", "replace")
    elif args.output:
        out_text = open(args.output, encoding="utf-8", errors="replace").read()
    if out_text is None:
        print("NOT COMPARED to a live run (pass --output FILE or --run); the checks above are structural only.")
    else:
        printed = {}
        for ln in out_text.split("\n"):
            mm = re.match(r"^\s*(\d+)\. (PASS|FAIL|SKIP)  (.*)$", ln)
            if mm:
                printed[int(mm.group(1))] = mm.group(3)
        if sorted(printed) != list(range(1, len(printed) + 1)):
            fail("the run's numbered result lines are not 1..%d" % len(printed))
        if len(printed) != listed:
            fail("the run printed %d numbered results, the list holds %d" % (len(printed), listed))
        else:
            ok("the run printed %d numbered results = the list" % listed)
        rm = re.search(r"RESULT: PASS - all (\d+) checks passed", out_text)
        if not rm or int(rm.group(1)) != listed:
            fail("the run's RESULT line does not say 'all %d checks passed'" % listed)
        else:
            ok("RESULT line says all %s checks passed" % rm.group(1))
        bad = 0
        for lo, hi, _p, _a, first in rows:
            got = printed.get(lo, "").replace("|", "/")
            if not got.startswith(first):
                bad += 1
                fail("row %d-%d: first check should read %r, the run printed %r" % (lo, hi, first, got[:50]))
        if not bad:
            ok("all %d rows start at the check the run printed under that number" % len(rows))

    print()
    if problems:
        print("RESULT: FAIL - %d problem(s)." % len(problems))
        return 1
    print("RESULT: PASS - the inventory adds up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
