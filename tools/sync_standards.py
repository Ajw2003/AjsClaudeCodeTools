#!/usr/bin/env python3
"""sync_standards.py — pulls the coding standards docs from Ajw2003/Coding-Standards and
copies them into rules/standards/, so the vendored copies are provably current instead of
hopefully current.

Ajw2003/Coding-Standards stays the place the documents are authored. This script is the one
step between an edit there and it shipping with the plugin.

Shape follows tools/install.py: Pass/Fail/Info helpers, a failure tally, idempotent, non-zero
exit on failure.

Usage:
    python tools/sync_standards.py [--from PATH]
"""

import argparse
import filecmp
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "rules", "standards")
DEFAULT_SOURCE = r"C:\Users\aj\Desktop\Coding-Standards"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", default=DEFAULT_SOURCE)
    args = parser.parse_args()
    source = args.source

    failures = 0

    def ok(msg):
        print(f"  PASS  {msg}")

    def bad(msg):
        nonlocal failures
        failures += 1
        print(f"  FAIL  {msg}")

    def info(msg):
        print(f"        {msg}")

    print()
    print("sync-standards")
    print("==============")

    print()
    print("1. Preflight")
    if not os.path.isdir(source):
        bad(f"source directory does not exist: {source}")
        sys.exit(1)
    ok(f"source  {source}")
    if not os.path.isdir(DEST):
        bad(f"destination directory does not exist: {DEST}")
        sys.exit(1)
    ok(f"destination  {DEST}")

    print()
    print("2. Pull the upstream repo")
    info(f"git -C {source} pull")
    proc = subprocess.run(
        ["git", "-C", source, "pull"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for line in (proc.stdout + proc.stderr).splitlines():
        print(f"        {line}")
    if proc.returncode != 0:
        bad("git pull failed - the lines above say why")
    else:
        ok("git pull succeeded")

    rev = subprocess.run(
        ["git", "-C", source, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    commit = rev.stdout.strip() if rev.returncode == 0 else "unknown"
    ok(f"source is now at commit {commit}")

    print()
    print("3. Copy *.md into rules/standards/")
    source_md = sorted(f for f in os.listdir(source) if f.lower().endswith(".md"))
    if not source_md:
        bad(f"no *.md files found in {source}")
    changed = []
    identical = []
    for name in source_md:
        src_path = os.path.join(source, name)
        dst_path = os.path.join(DEST, name)
        was_identical = os.path.isfile(dst_path) and filecmp.cmp(src_path, dst_path, shallow=False)
        with open(src_path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        with open(dst_path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        if was_identical:
            identical.append(name)
            ok(f"{name} — already identical")
        else:
            changed.append(name)
            ok(f"{name} — copied (changed)")

    print()
    print("4. Summary")
    info(f"changed:   {', '.join(changed) if changed else '(none)'}")
    info(f"identical: {', '.join(identical) if identical else '(none)'}")

    print()
    print("5. git diff --stat on the destination")
    diff = subprocess.run(
        ["git", "-C", ROOT, "diff", "--stat", "--", DEST],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    diff_out = (diff.stdout + diff.stderr).strip()
    if diff_out:
        for line in diff_out.splitlines():
            print(f"        {line}")
    else:
        info("(no diff — destination matches what's already committed)")

    print()
    print("---------------------")
    if failures == 0:
        print(f"RESULT: PASS - synced from {source} at commit {commit}.")
    else:
        print(f"RESULT: FAIL - {failures} check(s) failed.")
    print()

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
