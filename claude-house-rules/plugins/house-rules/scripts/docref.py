#!/usr/bin/env python3
"""docref.py - keeps the doc-ref pointers the archivist leaves in code true.

    docref.py check [--root DIR] [--exclude GLOB ...]

Design: docs/superpowers/specs/2026-09-20-pointer-integrity-design.md
STDLIB ONLY, Python 3.8+, no state kept between runs.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys

MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*ref:([0-9A-Za-z]+)[ \t]*-->[ \t\r]*$")
POINTER_RE = re.compile(r"doc-ref[ \t]+([0-9A-Za-z]+)[ \t]+(?=\S*(?:/|\.md))(\S+)")
PATH_RE = re.compile(r"[\w./-]+?\.md(?![\w.-])")
ID_RE = re.compile(r"[0-9a-f]{4}\Z")
FENCE_RE = re.compile(r"^[ \t]*(?:" + "`" * 3 + "|~~~)")
LEGACY_RE = re.compile(r"docs/(?:systems/[\w.-]+\.md|Decisions\.md)")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _norm(path):
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _walk_names(root):
    names = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, root)
        for name in filenames:
            names.append(_norm(os.path.join(rel_dir, name)))
    return names


def project_files(root):
    """(source, sorted relative paths): what git says is the project, else a directory walk."""
    try:
        proc = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if proc.returncode == 0:
            raw = proc.stdout.decode("utf-8", "replace").split("\0")
            return "git", sorted(set(_norm(n) for n in raw if n))
    except (OSError, subprocess.TimeoutExpired):
        pass  # no usable git: the walk below is named as the file source in the output
    return "directory walk", sorted(_walk_names(root))


def _scan_doc(rel, lines, res):
    in_fence = False
    for n, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = MARKER_RE.match(line)
        if not m:
            continue
        if ID_RE.match(m.group(1)):
            res["markers"].setdefault(m.group(1), []).append((rel, n))
        else:
            res["malformed"].append((rel, n, "marker id %r is not 4 lowercase hex characters" % m.group(1)))


def _scan_code(rel, full, lines, res):
    has_pointer = False
    for n, line in enumerate(lines, 1):
        found = False
        for m in POINTER_RE.finditer(line):
            found = True
            pid, raw = m.group(1), m.group(2)
            pm = PATH_RE.match(raw)
            if not ID_RE.match(pid):
                res["malformed"].append((rel, n, "pointer id %r is not 4 lowercase hex characters" % pid))
            elif not pm:
                res["malformed"].append((rel, n, "pointer path %r does not end in .md" % raw))
            else:
                has_pointer = True
                res["pointers"].append((rel, n, pid, _norm(pm.group(0))))
        if not found and LEGACY_RE.search(line):
            res["legacy"] += 1
    if has_pointer:
        res["pointer_files"].append((rel, full))


def scan(root, excludes=()):
    source, names = project_files(root)
    res = {
        "markers": {}, "pointers": [], "pointer_files": [], "malformed": [], "unreadable": [],
        "legacy": 0, "files": 0, "docs": 0, "binary": 0, "source": source,
    }
    for rel in names:
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue  # listed by git but deleted from the work tree: nothing to read
        if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            continue
        in_docs = rel.startswith("docs/")
        if in_docs and not rel.endswith(".md"):
            continue
        try:
            text = _read_bytes(full).decode("utf-8")
        except UnicodeDecodeError:
            res["binary"] += 1
            continue
        except OSError as e:
            res["unreadable"].append((rel, str(e)))
            continue
        res["files"] += 1
        lines = text.split("\n")
        if in_docs:
            res["docs"] += 1
            _scan_doc(rel, lines, res)
        else:
            _scan_code(rel, full, lines, res)
    return res


def classify(res):
    findings = []
    info = []
    counts = {"ok": 0, "stale": 0, "dangling": 0, "ambiguous": 0}
    markers = res["markers"]
    for pid, where in sorted(markers.items()):
        if len(where) > 1:
            listed = ", ".join("%s:%d" % w for w in where)
            findings.append((where[0][0], where[0][1], "duplicate",
                             "id %s is claimed by %d markers: %s" % (pid, len(where), listed)))
    pointed = set()
    for rel, n, pid, path in res["pointers"]:
        pointed.add(pid)
        where = markers.get(pid)
        if not where:
            counts["dangling"] += 1
            findings.append((rel, n, "dangling", "no doc carries ref:%s (pointer says %s)" % (pid, path)))
        elif len(where) > 1:
            counts["ambiguous"] += 1
        elif where[0][0] != path:
            counts["stale"] += 1
            findings.append((rel, n, "stale",
                             "pointer says %s; ref:%s is in %s" % (path, pid, where[0][0])))
        else:
            counts["ok"] += 1
    for rel, n, msg in res["malformed"]:
        findings.append((rel, n, "malformed", msg))
    for rel, msg in res["unreadable"]:
        findings.append((rel, 0, "unreadable", msg))
    for pid, where in sorted(markers.items()):
        if pid not in pointed:
            info.append((where[0][0], where[0][1], "unreferenced marker ref:%s (no code points at it)" % pid))
    findings.sort(key=lambda f: (f[0], f[1]))
    return findings, counts, info


def cmd_check(root, excludes):
    res = scan(root, excludes)
    findings, counts, info = classify(res)
    for rel, n, kind, msg in findings:
        where = "%s:%d" % (rel, n) if n else rel
        print("%s  %s  %s" % (where, kind.upper(), msg))
    for rel, n, msg in info:
        print("%s:%d  INFO  %s" % (rel, n, msg))
    print("docref: scanned %d files (%d docs) via %s; %d binary skipped"
          % (res["files"], res["docs"], res["source"], res["binary"]))
    print("docref: %d pointers found: %d ok, %d stale, %d dangling, %d ambiguous"
          % (len(res["pointers"]), counts["ok"], counts["stale"], counts["dangling"], counts["ambiguous"]))
    duplicates = sum(1 for f in findings if f[2] == "duplicate")
    print("docref: %d malformed, %d duplicate ids, %d unreadable"
          % (len(res["malformed"]), duplicates, len(res["unreadable"])))
    print("docref: %d line(s) mention docs/systems/ or docs/Decisions.md with no doc-ref "
          "(legacy prose pointers, not tracked)" % res["legacy"])
    if res["docs"] == 0:
        print("docref: note: no docs/**/*.md found under this root, so every pointer reads as dangling")
    print("docref: OK" if not findings else "docref: PROBLEMS (%d)" % len(findings))
    return 1 if findings else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="docref.py", description="Keep doc-ref pointers true.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="report every pointer as ok, stale, dangling or malformed")
    check.add_argument("--root", default=".")
    check.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if not os.path.isdir(root):
            print("docref: --root %s is not a directory" % root, file=sys.stderr)
            return 2
        return cmd_check(root, args.exclude)
    except Exception as e:  # last resort: say what broke, never a bare traceback or a silent 0
        print("docref: internal error: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
