#!/usr/bin/env python3
"""Copy the shared library into every plugin that uses it (#439).

The library lives once: claude-house-rules/plugins/house-lib/house_lib/. Each plugin in
TARGETS gets a copy at <plugin>/scripts/house_lib/. `--check` changes nothing: it exits 1
naming each file that differs or is missing (or extra in a copy), 0 when all match.
Stdlib only. Optional --source/--root let tests run against a temp folder.
"""
import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = "claude-house-rules/plugins/house-lib/house_lib"
# Target plugins: add one line per plugin that vendors the library.
TARGETS = [
    "claude-house-rules/plugins/house-rules/scripts/house_lib",
]


def _files(folder):
    out = {}
    for dirpath, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in names:
            if n.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, n)
            out[os.path.relpath(full, folder).replace(os.sep, "/")] = full
    return out


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def problems(root, source=SOURCE, targets=TARGETS):
    src_dir = os.path.join(root, source)
    if not os.path.isdir(src_dir):
        return ["library source missing: %s" % source]
    src = _files(src_dir)
    found = []
    for t in targets:
        dst = _files(os.path.join(root, t))
        for rel, full in sorted(src.items()):
            if rel not in dst:
                found.append("missing: %s/%s" % (t, rel))
            elif _read(full) != _read(dst[rel]):
                found.append("differs: %s/%s" % (t, rel))
        for rel in sorted(set(dst) - set(src)):
            found.append("extra (not in source): %s/%s" % (t, rel))
    return found


def sync(root, source=SOURCE, targets=TARGETS):
    src_dir = os.path.join(root, source)
    for t in targets:
        dst_dir = os.path.join(root, t)
        if os.path.isdir(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print("synced %s" % t)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if any copy differs")
    ap.add_argument("--root", default=REPO, help="repo root (default: this repo)")
    args = ap.parse_args(argv)
    if args.check:
        found = problems(args.root)
        for line in found:
            print(line)
        if found:
            print("sync_library: %d problem(s); run python tools/sync_library.py" % len(found))
            return 1
        print("sync_library: all copies match the source")
        return 0
    if not os.path.isdir(os.path.join(args.root, SOURCE)):
        print("library source missing: %s" % SOURCE)
        return 1
    sync(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
