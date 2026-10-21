#!/usr/bin/env python3
"""review.py - write review records and show gate status. Shares artlib with the Stop gate.

  review.py record --model PATH --sheet PNG --verdict pass|fail|waived --seen "TEXT"
  review.py status
Run from inside the repo. Stdlib only."""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402


def rel(root, p):
    return os.path.relpath(os.path.abspath(p), root).replace(os.sep, "/")


def main(argv):
    ap = argparse.ArgumentParser(prog="review.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--model", required=True)
    r.add_argument("--sheet", required=True)
    r.add_argument("--verdict", required=True, choices=["pass", "fail", "waived"])
    r.add_argument("--seen", required=True)
    sub.add_parser("status")
    a = ap.parse_args(argv[1:])
    info = artlib.repo_info(os.getcwd())
    if not info:
        print("review.py: not inside a git repo", file=sys.stderr)
        return 2
    root, gitdir = info
    cfg = artlib.load_config(root)
    if a.cmd == "record":
        model, sheet = rel(root, a.model), rel(root, a.sheet)
        errs = []
        if not os.path.isfile(os.path.join(root, model)):
            errs.append("model %s does not exist" % model)
        if not os.path.isfile(os.path.join(root, sheet)):
            errs.append("sheet %s does not exist" % sheet)
        if len(a.seen.strip()) < artlib.MIN_SEEN:
            errs.append("--seen must be >= %d chars (say what you saw)" % artlib.MIN_SEEN)
        if errs:
            print("review.py: " + "; ".join(errs), file=sys.stderr)
            return 1
        d = os.path.join(root, cfg["review_dir"])
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, artlib.record_name(model))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"model": model, "sheet": sheet, "verdict": a.verdict, "seen": a.seen,
                       "date": artlib.now()}, fh, indent=2)
            fh.write("\n")
        print(path)
        return 0
    # status: newest ledger stands in for "this session"
    leds = glob.glob(os.path.join(gitdir, "art-pipeline", "*.json"))
    sid = os.path.basename(max(leds, key=os.path.getmtime))[:-5] if leds else ""
    _, _, res, bad = artlib.evaluate(root, gitdir, sid)
    print("ledger: %s" % (sid or "(none - nothing counts as seen)"))
    if not res:
        print("no changed models")
    for m, st, pr in res:
        print("%s  %s" % ("PASS" if st not in ("fail", "timeout") else ("BLOCK" if st == "fail" else "UNCHECKED"), m)
              + ("  [waived]" if st == "waived" else ""))
        for p in pr:
            print("      - " + p)
    for b in bad:
        print("unreadable record: " + b)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
