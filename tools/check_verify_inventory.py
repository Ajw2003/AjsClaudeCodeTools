#!/usr/bin/env python3
"""check_verify_inventory.py - proves the check inventory in docs/4-systems/verify-suites.md adds up (#369, #370).

    python tools/check_verify_inventory.py                      # structure only; says so
    python tools/check_verify_inventory.py --output run.txt     # also compare against a saved verify.py run
    python tools/check_verify_inventory.py --run                # run verify.py once (about 40 seconds) and compare

What it proves, from the doc section "Which part every check belongs to (#369)" (numbered as the single
10,407-line verify.py printed them, before the split) and the section "The split layout (#370)":
  1. the grouped list covers check numbers 1..N once each: no gap, no overlap, no number past N;
  2. N equals the total in the summary table, and each part's count in the summary table equals the
     sum of that part's rows in the grouped list;
  3. the multi-part count stated in the doc equals the rows that name an "Also touches" part;
  3b. the per-part counts in "Checks per part after the split" equal the inventory's counts adjusted by
     the rows of "Checks placed differently from the inventory", each moved range really belongs to the
     part it is moved from, and every part has a file under checks/;
  4. with a verify.py run (--output or --run): the numbers in the old inventory no longer apply (each part
     numbers its own checks from 1), so the run is compared per part instead: each part's section printed
     the number of results the split table says, numbered 1..n, the run printed N results in all with a
     RESULT line "all N checks passed", and every inventory row's "First check as printed" is a prefix of a
     check printed by the part the table puts that row in.
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
CHECKS = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts", "checks")
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


def norm(name):
    """A part as the inventory spells it ('safe git', 'tools/make_page') to its file name ('safe_git', 'make_page')."""
    n = name.replace("`", "").replace("*", "").strip().lower()
    if n.startswith("tools/"):
        n = n[len("tools/"):]
    return n.replace(" ", "_")


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

    # 3b. the split (#370): each part's count after the move equals the inventory's count adjusted by the moves
    part_of = {}
    for lo, hi, part, _also, _first in rows:
        for n in range(lo, hi + 1):
            part_of[n] = norm(part)
    n_before_split = len(problems)
    inv = {norm(k): v for k, v in parts.items() if v}     # session triage has 0 checks and no file
    expected = dict(inv)
    moves = []
    split_per = section(text, "### Checks per part after the split", 3)
    split_moves = section(text, "### Checks placed differently from the inventory", 3)
    if not split_per or split_moves is None:
        fail("the doc has no 'Checks per part after the split' and 'Checks placed differently from the inventory' tables")
        split_per = split_per or []
        split_moves = split_moves or []
    for ln in split_moves:
        if not ln.startswith("| ") or ln.startswith("| Checks") or ln.startswith("|---"):
            continue
        c = cells(ln)
        mm = re.match(r"^(\d+)(?:-(\d+))?$", c[0])
        if not mm:
            fail("a moves-table row has an unreadable check range: %r" % c[0])
            continue
        lo = int(mm.group(1)); hi = int(mm.group(2) or mm.group(1))
        src, dst, cnt = norm(c[1]), norm(c[2]), int(c[3])
        if cnt != hi - lo + 1:
            fail("moves row %s says %d checks but the range holds %d" % (c[0], cnt, hi - lo + 1))
        wrong = sorted({part_of.get(n) for n in range(lo, hi + 1)} - {src})
        if wrong:
            fail("moves row %s: the inventory puts some of those checks in %s, not only in %s" % (c[0], wrong, src))
        expected[src] = expected.get(src, 0) - cnt
        expected[dst] = expected.get(dst, 0) + cnt
        moves.append((lo, hi, dst))
    after = {}
    for ln in split_per:
        if not ln.startswith("| ") or ln.startswith("| Part") or ln.startswith("|---"):
            continue
        c = cells(ln)
        name = norm(c[0].replace("*", "").replace("`", ""))
        if name == "total":
            after["total"] = int(c[1].replace("*", ""))
        else:
            after[name] = int(c[1].replace("*", ""))
    if not after:
        fail("the 'Checks per part after the split' table has no rows")
    else:
        for name, n in expected.items():
            if after.get(name) != n:
                fail("part %s: inventory %d adjusted by the moves gives %d, the split table says %s"
                     % (name, inv.get(name, 0), n, after.get(name)))
        for name in after:
            if name != "total" and name not in expected:
                fail("part %s is in the split table but not in the inventory" % name)
        if after.get("total") != sum(v for k, v in after.items() if k != "total"):
            fail("the split table's rows add to %d but its Total says %s" % (sum(v for k, v in after.items() if k != "total"), after.get("total")))
        elif after.get("total") != listed:
            fail("the split table's total is %s, the inventory's is %d" % (after.get("total"), listed))
        if len(problems) == n_before_split:
            ok("split table = inventory counts adjusted by %d move(s): %s" % (len(moves), ", ".join("%s %d" % (k, v) for k, v in after.items() if k != "total")))
    for name in after:
        if name != "total" and not os.path.isfile(os.path.join(CHECKS, name + ".py")):
            fail("checks/%s.py does not exist" % name)

    # 4. compare with a real run: per-part counts against what each part file printed
    out_text = None
    if args.run:
        print("running verify.py once (about 40 seconds)...")
        p = subprocess.run([sys.executable, VERIFY], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        out_text = p.stdout.decode("utf-8", "replace")
    elif args.output:
        out_text = open(args.output, encoding="utf-8", errors="replace").read()
    if out_text is None:
        print("NOT COMPARED to a live run (pass --output FILE or --run); the checks above are structural only.")
    else:
        printed = {}
        cur = None
        for ln in out_text.split("\n"):
            pm = re.match(r"^PART (\w+) - ", ln)
            if pm:
                cur = pm.group(1)
                printed[cur] = []
                continue
            mm = re.match(r"^\s*(\d+)\. (PASS|FAIL|SKIP)  (.*)$", ln)
            if mm and cur:
                printed[cur].append((int(mm.group(1)), mm.group(3)))
        if not printed:
            fail("the run printed no 'PART <name> - ...' sections; is this the runner's output?")
        for name, n in after.items():
            if name == "total":
                continue
            got = printed.get(name)
            if got is None:
                fail("the run has no section for part %s" % name)
                continue
            if [g[0] for g in got] != list(range(1, len(got) + 1)):
                fail("part %s: its numbered results are not 1..%d" % (name, len(got)))
            if len(got) != n:
                fail("part %s printed %d numbered results, the split table says %d" % (name, len(got), n))
            else:
                ok("part %s printed %d numbered results = the table" % (name, n))
        grand = sum(len(v) for v in printed.values())
        if grand != listed:
            fail("the run printed %d numbered results in all, the inventory holds %d" % (grand, listed))
        final = re.findall(r"^RESULT: PASS - all (\d+) checks passed", out_text, re.M)    # each part prints one; the last is the runner's
        if not final or int(final[-1]) != listed:
            fail("the run's last RESULT line does not say 'all %d checks passed'" % listed)
        else:
            ok("the runner's RESULT line says all %s checks passed" % final[-1])
        # every inventory row's first check was printed by the part the row belongs to (after the moves)
        bad = 0
        for lo, hi, part, _a, first in rows:
            dest = norm(part)
            for mlo, mhi, mdst in moves:
                if mlo <= lo and hi <= mhi:
                    dest = mdst
            titles = [t.replace("|", "/") for _n, t in printed.get(dest, [])]
            if not any(t.startswith(first) for t in titles):
                bad += 1
                fail("row %d-%d: no check in part %s starts with %r" % (lo, hi, dest, first))
        if not bad:
            ok("all %d rows' first checks were printed by the part the table puts them in" % len(rows))

    print()
    if problems:
        print("RESULT: FAIL - %d problem(s)." % len(problems))
        return 1
    print("RESULT: PASS - the inventory adds up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
