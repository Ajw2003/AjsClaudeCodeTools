#!/usr/bin/env python3
"""review_plan.py - pick the review mode and count the sweep, so numbers are counted, not guessed (#619).

  review_plan.py mode [TARGET] [--style] [--root DIR]   -> mode:, report:, (plan) design:
  review_plan.py units [--root DIR]                     -> unit lines, folders, files, batches, notice
  review_plan.py batches [--root DIR]                   -> <unit><TAB><n><TAB><file,file,...>

Files come from `git ls-files -co --exclude-standard`, so .git and ignored files are skipped.
A batch is at most 8 files of one unit (8 x 7.1 s = 57 s, under the 60 s agent deadline).
Exit 0 on success, 2 when the TARGET does not exist. STDLIB ONLY.
"""
import argparse
import datetime
import math
import re
import subprocess
import sys
from pathlib import Path

IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
BATCH = 8
SEC, TOK = 7.1, 4400
META = re.compile(r'<meta\s+name=["\']house-rules-page["\']\s+content=["\']build-plan["\']', re.I)


def cmd_mode(a):
    root = Path(a.root).resolve()
    if a.target is None:
        mode, tpath = "diff", None
    else:
        tpath = Path(a.target)
        if not tpath.is_absolute():
            tpath = Path.cwd() / tpath
        if not tpath.exists():
            print(f"error: {a.target} not found")
            return 2
        if a.style:
            mode = "style"
        elif a.target == ".":
            mode = "codebase"
        elif tpath.suffix.lower() in IMAGES:
            mode = "image"
        elif tpath.suffix.lower() == ".html" and tpath.is_file():
            text = tpath.read_text(encoding="utf-8", errors="replace")
            mode = "plan" if META.search(text) else "page"
        else:
            mode = "code"
    if a.target is None:
        name = root.name
    elif a.target == ".":
        name = Path.cwd().resolve().name if a.root == "." else root.name
    else:
        name = tpath.name
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "target"
    print(f"mode: {mode}")
    print(f"report: docs/qa/review-{name}-{datetime.date.today().isoformat()}")
    if mode == "plan":
        cand = tpath.with_name(re.sub(r"-plan$", "", tpath.stem) + tpath.suffix)
        print(f"design: {cand if cand != tpath and cand.exists() else 'none'}")
    return 0


def units_of(root):
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"error: git ls-files failed in {root}: {r.stderr.strip()}")
        sys.exit(3)
    units = {}
    for f in sorted(set(x for x in r.stdout.splitlines() if x)):
        if not (Path(root) / f).is_file():
            continue
        u = f.split("/", 1)[0] if "/" in f else "root files"
        units.setdefault(u, []).append(f)
    return units


def batches_of(units):
    for u in sorted(units):
        fs = sorted(units[u])
        for i in range(0, len(fs), BATCH):
            yield u, i // BATCH + 1, fs[i:i + BATCH]


def cmd_units(a):
    units = units_of(a.root)
    for u in sorted(units):
        print(f"unit: {u} files: {len(units[u])}")
    folders = len([u for u in units if u != "root files"])
    files = sum(len(v) for v in units.values())
    nb = sum(1 for _ in batches_of(units))
    print(f"folders: {folders}")
    print(f"files: {files}")
    print(f"batches: {nb}")
    if folders > 12:
        m = math.ceil(files * SEC / 60)
        print(f"notice: This sweep covers {folders} folders, {files} files, in {nb} batches run one at a time. "
              f"Estimated time about {m} minutes and about {files * TOK:,} tokens (7.1 seconds and 4,400 tokens "
              f"per file, measured on one 10-file markdown batch); code files take longer, so treat both as a minimum.")
    return 0


def cmd_batches(a):
    for u, n, fs in batches_of(units_of(a.root)):
        print(f"{u}\t{n}\t{','.join(fs)}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="cmd", required=True)
    m = s.add_parser("mode")
    m.add_argument("target", nargs="?")
    m.add_argument("--style", action="store_true")
    m.add_argument("--root", default=".")
    m.set_defaults(f=cmd_mode)
    for n, f in (("units", cmd_units), ("batches", cmd_batches)):
        q = s.add_parser(n)
        q.add_argument("--root", default=".")
        q.set_defaults(f=f)
    a = p.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
