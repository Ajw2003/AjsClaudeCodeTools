#!/usr/bin/env python3
"""review_plan.py - pick the review mode and count the sweep, so numbers are counted, not guessed (#619).

  review_plan.py mode [TARGET] [--style] [--root DIR] [--model M] [--effort E]
                                                        -> mode:, report:, model:, effort:, (plan) design:
  review_plan.py units [--root DIR]                     -> unit lines, folders, files, batches, notice
  review_plan.py batches [--root DIR]                   -> <unit><TAB><n><TAB><file,file,...>

Files come from `git ls-files -co --exclude-standard`, so .git and ignored files are skipped.
A batch is at most 6 files of one unit: markdown ran at 7.1 s a file (8 x 7.1 = 57 s, right at the 60 s agent
deadline), and code files run slower, so 6 files (43 s on markdown) leaves headroom.
Sweep token estimate: 10,000 per batch plus 3,400 per file, fitted to the real 15-batch sweep (203,394 tokens).
--model and --effort may sit anywhere in the text; each prints its value, or `default` (the reviewer's own setting, Opus). Without --model, code prints `opus+sonnet` (two reviewers) and codebase/image/style print `sonnet`.
Exit 0 on success, 2 when the TARGET does not exist or --model/--effort is not a known value, 3 when --root or git cannot be used. STDLIB ONLY.
"""
import argparse
import datetime
import math
import re
import subprocess
import sys
from pathlib import Path

IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
BATCH = 6
SEC, TOK_BATCH, TOK_FILE = 7.1, 10000, 3400
GENERIC = {"build-plan", "proposal", "design"}  # folder-style pages named by their folder, not by themselves
MODELS = ("opus", "sonnet", "haiku", "fable")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Decisions.md 2026-11-24 "Review models per mode": Opus for page, diff and plan; code runs Opus then Sonnet (each found real
# bugs the other missed); the rest run on Sonnet. Acceptance is absent: it is not reached through review_plan.py.
SONNET_MODES = {"codebase", "image", "style"}
DUAL_MODES = {"code"}
META = re.compile(r'<meta\s+name=["\']house-rules-page["\']\s+content=["\']build-plan["\']', re.I)


def strip_date(name):
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)


def designs_of(plan):
    """Design pages next to a plan: same name minus -plan/-build-plan (date ignored), or a folder's proposal/design."""
    want = {"proposal", "design"} if plan.stem == "build-plan" else {strip_date(re.sub(r"-(build-)?plan$", "", plan.stem))}
    return sorted(f for f in plan.parent.iterdir()
                  if f.is_file() and f != plan and f.suffix == plan.suffix and strip_date(f.stem) in want)


def cmd_mode(a):
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"error: --root {a.root} is not a folder")
        return 3
    words = list(a.words)
    a.target = words.pop(0) if words else None
    if words and words[0].lower() == "style":
        a.style = True
        words.pop(0)
    criteria = " ".join(words) or "none"
    if a.target is None:
        mode, tpath = "diff", None
    else:
        tpath = Path(a.target)
        if not tpath.is_absolute():
            tpath = root / tpath
        if not tpath.exists():
            print(f"error: {a.target} not found")
            return 2
        if a.style:
            mode = "style"
        elif tpath.resolve() == root:
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
    elif mode == "codebase":
        name = root.name
    elif tpath.is_file():
        name = strip_date(tpath.parent.name if tpath.stem in GENERIC else tpath.stem)
    else:
        name = tpath.name
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "target"
    print(f"mode: {mode}")
    print(f"report: docs/qa/review-{name}-{datetime.date.today().isoformat()}")
    print(f"criteria: {criteria}")
    print(f"model: {a.overrides.get('model') or ('opus+sonnet' if mode in DUAL_MODES else 'sonnet' if mode in SONNET_MODES else 'default')}")
    print(f"effort: {a.overrides.get('effort', 'default')}")
    if mode == "plan":
        found = designs_of(tpath)
        print(f"design: {found[0] if len(found) == 1 else 'ambiguous' if found else 'none'}")
        if len(found) > 1:
            for f in found:
                print(f"candidate: {f}")
    return 0


def units_of(root):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "-co", "--exclude-standard"],
                           cwd=root, capture_output=True, text=True, encoding="utf-8")
    except OSError as e:
        print(f"error: cannot run git in {root}: {e}")
        sys.exit(3)
    if r.returncode != 0:
        print(f"error: git ls-files failed in {root}: {r.stderr.strip()}")
        sys.exit(3)
    units = {}
    for f in sorted(set(x for x in r.stdout.split("\0") if x)):
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
        tokens = nb * TOK_BATCH + files * TOK_FILE
        print(f"notice: This sweep covers {folders} folders, {files} files, in {nb} batches run one at a time. "
              f"Estimated time about {m} minutes and about {tokens:,} tokens (7.1 seconds per file, "
              f"and {TOK_BATCH:,} tokens per batch plus {TOK_FILE:,} per file, fitted to a measured 15-batch sweep); "
              f"code files take longer, so treat both as a minimum.")
    return 0


def cmd_batches(a):
    for u, n, fs in batches_of(units_of(a.root)):
        print(f"{u}\t{n}\t{','.join(fs)}")
    return 0


def pull_overrides(argv):
    """Take --model/--effort (also --flag=value) out of a `mode` call, wherever they sit in the criteria text."""
    out, found, i = [], {}, 0
    while i < len(argv):
        w = argv[i]
        name, eq, val = w.partition("=")
        if argv[:1] == ["mode"] and name in ("--model", "--effort"):
            if not eq:
                i += 1
                val = argv[i] if i < len(argv) else ""
            found[name[2:]] = val.lower()
        else:
            out.append(w)
        i += 1
    return out, found


def main():
    argv, found = pull_overrides(sys.argv[1:])
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest="cmd", required=True)
    m = s.add_parser("mode")
    m.add_argument("words", nargs="*")
    m.add_argument("--style", action="store_true")
    m.add_argument("--root", default=".")
    m.set_defaults(f=cmd_mode)
    for n, f in (("units", cmd_units), ("batches", cmd_batches)):
        q = s.add_parser(n)
        q.add_argument("--root", default=".")
        q.set_defaults(f=f)
    a = p.parse_args(argv)
    for key, allowed in (('model', MODELS), ('effort', EFFORTS)):
        if key in found and found[key] not in allowed:
            print(f"error: --{key} {found[key] or '(missing)'} is not one of {', '.join(allowed)}")
            return 2
    a.overrides = found
    try:
        rc = a.f(a)
        sys.stdout.flush()
        return rc
    except BrokenPipeError:
        sys.stderr.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
