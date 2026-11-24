#!/usr/bin/env python3
"""acceptance.py - whole-feature acceptance evidence and the freshness-checked stamp (#595).

  acceptance.py tree [--root DIR]            fingerprint of the source tree (docs/qa/, docs/plans/*.html and the loop file left out)
  acceptance.py run --out DIR [--timeout S] -- CMD...   run CMD, save stdout, stderr, exit code to DIR/run-N.txt
  acceptance.py stamp FEATURE_DIR [--root DIR]   refuse unless `ledger.py status` says NEXT: done; else write FEATURE_DIR/acceptance-stamp.json
  acceptance.py check FEATURE_DIR [--root DIR]   exit 0 if the stamp's tree equals the current tree, else 1
Exit codes: 0 ok, 1 stale/missing, 2 refused or failed. STDLIB ONLY.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STAMP = "acceptance-stamp.json"


def tree(root):
    r = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True)
    if r.returncode != 0:
        sys.stderr.write("acceptance: git ls-files failed in %s: %s\n" % (root, r.stderr.decode("utf-8", "replace").strip()))
        sys.exit(2)
    lines = []
    for p in sorted(set(x for x in r.stdout.decode("utf-8").split("\0") if x)):
        # built pages are left out too (P3): building the QA page must not make the stamp stale
        if p.startswith("docs/qa/") or p == ".claude/house-rules-loop.json" or (p.startswith("docs/plans/") and p.endswith(".html")):
            continue
        fp = os.path.join(root, p)
        if not os.path.isfile(fp):  # tracked but deleted in the working tree
            continue
        with open(fp, "rb") as fh:
            lines.append("%s %s" % (p, hashlib.sha256(fh.read()).hexdigest()))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def stamp_problem(feature_folder, root):
    """'' when the stamp is current, else the message."""
    try:
        with open(os.path.join(feature_folder, STAMP), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        return "acceptance stamp missing"
    if not isinstance(st, dict) or st.get("tree") != tree(root):
        return "acceptance stamp is stale: the source changed after the run"
    return ""


def cmd_run(a):
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        sys.stderr.write("acceptance: run needs a command after --\n")
        return 2
    os.makedirs(a.out, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(a.out, "run-%d.txt" % n)):
        n += 1
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=a.timeout)
        out, err, code = r.stdout, r.stderr, str(r.returncode)
    except subprocess.TimeoutExpired as exc:
        out, err, code = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""), \
            "timed out after %s s" % a.timeout, "timeout"
    except OSError as exc:
        out, err, code = "", "could not start %s: %s" % (cmd[0], exc), "not-started"
    path = os.path.join(a.out, "run-%d.txt" % n)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("command: %s\nexit code: %s\n--- stdout ---\n%s\n--- stderr ---\n%s\n" % (" ".join(cmd), code, out, err))
    print(path)
    return 0


def cmd_stamp(a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "ledger.py"), "status", a.folder], capture_output=True, text=True)
    if not re.search(r"^NEXT: done$", r.stdout, re.M):
        sys.stderr.write("acceptance: refusing to stamp, ledger status for %s is not NEXT: done:\n%s%s" % (a.folder, r.stdout, r.stderr))
        return 2
    m = re.search(r"^rounds: (\d+)", r.stdout, re.M)
    st = {"tree": tree(a.root), "at": int(time.time()), "rounds": int(m.group(1)) if m else None}
    with open(os.path.join(a.folder, STAMP), "w", encoding="utf-8") as fh:
        json.dump(st, fh)
    print("acceptance: stamped %s" % os.path.join(a.folder, STAMP))
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="acceptance.py")
    sub = p.add_subparsers(dest="cmd_name", required=True)
    t = sub.add_parser("tree")
    t.add_argument("--root", default=".")
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("cmd", nargs=argparse.REMAINDER)
    for name in ("stamp", "check"):
        s = sub.add_parser(name)
        s.add_argument("folder")
        s.add_argument("--root", default=".")
    a = p.parse_args(argv)
    if a.cmd_name == "tree":
        print(tree(a.root))
        return 0
    if a.cmd_name == "run":
        return cmd_run(a)
    if a.cmd_name == "stamp":
        return cmd_stamp(a)
    msg = stamp_problem(a.folder, a.root)
    print(msg or "acceptance stamp current")
    return 1 if msg else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
