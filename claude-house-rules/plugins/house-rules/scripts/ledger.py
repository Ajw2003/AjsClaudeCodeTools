#!/usr/bin/env python3
"""ledger.py - the machine-checkable part of the visual loop (#566).

  ledger.py check DIR       DIR = docs/qa/<feature>; validates criteria.md and every round-N.md
  ledger.py status DIR      rounds so far, failing criteria of the latest round, and a NEXT: line
  ledger.py new-round DIR   writes the next round-N.md skeleton (refuses after a pass or at the cap)

criteria.md:  C1. <text> | proof: <still|flow|video|frames> | page: <path or url>
round-N.md:   # Round N, then one line per criterion
              C1: PASS|FAIL - <what the image shows> - <image path, relative to DIR or the working folder>
              and a last line  STATUS: pass|fail
Exit codes: check 0 valid / 1 problems; status 0 done / 1 fix or blocked; 4 bad usage. STDLIB ONLY.
"""
import json
import os
import re
import sys

DEFAULTS = {"max_rounds": 4, "ledger_dir": "docs/qa/<feature>"}
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rules", "visual.json")
CRIT = re.compile(r"^C(\d+)\. (.+) \| proof: (still|flow|video|frames) \| page: (\S.*)$")
VERD = re.compile(r"^C(\d+): (PASS|FAIL) - (.+) - (\S+)$")


def load_visual():
    path = os.environ.get("HOUSE_RULES_VISUAL_FILE") or FILE
    out = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("the top level is not an object")
    except (OSError, ValueError) as exc:
        sys.stderr.write("house-rules visual: the settings file %s could not be read (%s: %s); using the built-in numbers.\n"
                         % (path, type(exc).__name__, str(exc)[:120]))
        return out
    m = data.get("max_rounds")
    if isinstance(m, int) and not isinstance(m, bool) and m > 0:
        out["max_rounds"] = m
    elif "max_rounds" in data:
        sys.stderr.write("house-rules visual: max_rounds in %s is %r, not a positive whole number; using %d.\n"
                         % (path, m, DEFAULTS["max_rounds"]))
    if isinstance(data.get("ledger_dir"), str) and data["ledger_dir"]:
        out["ledger_dir"] = data["ledger_dir"]
    return out


def usage(msg):
    sys.stderr.write("ledger.py: %s\nusage: ledger.py check|status|new-round DIR\n" % msg)
    return 4


def read_criteria(d):
    """(list of criterion numbers in order, problems)"""
    path = os.path.join(d, "criteria.md")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError as exc:
        return [], ["criteria.md cannot be read (%s)" % exc.strerror]
    nums, probs = [], []
    for i, ln in enumerate(lines, 1):
        if not ln.strip() or ln.startswith("#"):
            continue
        m = CRIT.match(ln)
        if not m:
            probs.append("criteria.md line %d is not 'C<n>. <text> | proof: <still|flow|video|frames> | page: <path or url>'" % i)
        else:
            nums.append(int(m.group(1)))
    if len(set(nums)) != len(nums):
        probs.append("criteria.md numbers a criterion more than once")
    if not nums and not probs:
        probs.append("criteria.md holds no criteria")
    return nums, probs


def rounds_in(d):
    out = []
    for f in os.listdir(d):
        m = re.match(r"^round-(\d+)\.md$", f)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def read_round(d, n, nums):
    """(verdicts {num: (PASS|FAIL, image)}, status or None, problems)"""
    name = "round-%d.md" % n
    try:
        lines = open(os.path.join(d, name), encoding="utf-8").read().splitlines()
    except OSError as exc:
        return {}, None, ["%s cannot be read (%s)" % (name, exc.strerror)]
    probs, seen, status = [], {}, None
    if not lines or lines[0].strip() != "# Round %d" % n:
        probs.append("%s does not start with '# Round %d'" % (name, n))
    for ln in lines[1:]:
        if not ln.strip():
            continue
        m = VERD.match(ln)
        if m:
            c = int(m.group(1))
            if c in seen:
                probs.append("%s judges C%d more than once" % (name, c))
            seen[c] = (m.group(2), m.group(4))
            img = m.group(4)
            if not (os.path.isfile(os.path.join(d, img)) or os.path.isfile(img)):
                probs.append("%s: C%d cites an image that does not exist (%s)" % (name, c, img))
        elif re.match(r"^STATUS: (pass|fail)$", ln):
            status = ln.split()[1]
        else:
            probs.append("%s has a line that is neither a verdict nor STATUS: %s" % (name, ln[:60]))
    for c in nums:
        if c not in seen:
            probs.append("%s does not judge C%d" % (name, c))
    for c in seen:
        if c not in nums:
            probs.append("%s judges C%d, which is not in criteria.md" % (name, c))
    if status is None:
        probs.append("%s has no STATUS line" % name)
    else:
        want = "pass" if seen and all(v[0] == "PASS" for v in seen.values()) and not probs else "fail"
        if status != want and not (status == "fail" and probs):
            probs.append("%s says STATUS: %s but its verdict lines say %s" % (name, status, want))
    return seen, status, probs


def cmd_check(d):
    nums, probs = read_criteria(d)
    rs = rounds_in(d)
    if rs != list(range(1, len(rs) + 1)):
        probs.append("round numbers are not consecutive from 1 (found %s)" % rs)
    for n in rs:
        probs += read_round(d, n, nums)[2]
    if probs:
        print("ledger: %d problem(s) in %s" % (len(probs), d))
        for p in probs:
            print("  - " + p)
        return 1
    print("ledger: %s is valid (%d criteria, %d rounds)" % (d, len(nums), len(rs)))
    return 0


def cmd_status(d):
    nums, probs = read_criteria(d)
    rs = rounds_in(d)
    mx = load_visual()["max_rounds"]
    print("rounds: %d (cap %d)" % (len(rs), mx))
    if probs or not rs:
        print("ledger: nothing to judge yet (%s)" % ("; ".join(probs) or "no round file"))
        print("NEXT: fix" if not probs else "NEXT: fix (criteria.md is broken)")
        return 1
    seen, status, rprobs = read_round(d, rs[-1], nums)
    failing = sorted(c for c, v in seen.items() if v[0] == "FAIL")
    print("failing in round %d: %s" % (rs[-1], ", ".join("C%d" % c for c in failing) or "none"))
    if status == "pass" and not failing and not rprobs:
        print("NEXT: done")
        return 0
    if len(rs) >= mx:
        print("NEXT: blocked - write %s listing what still fails and why" % os.path.join(d, "blocked.md"))
    else:
        print("NEXT: fix")
    return 1


def cmd_new_round(d):
    nums, probs = read_criteria(d)
    if probs:
        print("ledger: refusing, criteria.md is not valid: " + "; ".join(probs))
        return 1
    rs = rounds_in(d)
    if rs:
        seen, status, _ = read_round(d, rs[-1], nums)
        if status == "pass":
            print("ledger: refusing, round %d already passed" % rs[-1])
            return 1
    mx = load_visual()["max_rounds"]
    if len(rs) >= mx:
        print("ledger: refusing, the cap of %d rounds is reached; write blocked.md" % mx)
        return 1
    n = len(rs) + 1
    body = "# Round %d\n" % n + "".join("C%d: FAIL - not yet judged - \n" % c for c in nums) + "STATUS: fail\n"
    with open(os.path.join(d, "round-%d.md" % n), "w", encoding="utf-8") as fh:
        fh.write(body)
    print("ledger: wrote %s" % os.path.join(d, "round-%d.md" % n))
    return 0


def main(argv):
    if len(argv) != 2 or argv[0] not in ("check", "status", "new-round"):
        return usage("expected a command and one folder")
    if not os.path.isdir(argv[1]):
        return usage("%s is not a folder" % argv[1])
    return {"check": cmd_check, "status": cmd_status, "new-round": cmd_new_round}[argv[0]](argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
