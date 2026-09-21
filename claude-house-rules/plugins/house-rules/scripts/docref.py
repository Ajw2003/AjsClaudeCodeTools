#!/usr/bin/env python3
"""docref.py - keeps the doc-ref pointers the archivist leaves in code true.

    docref.py check [--root DIR] [--exclude GLOB ...]
    docref.py fix   [--root DIR] [--exclude GLOB ...] [--write]
    docref.py new   [--root DIR] [--exclude GLOB ...]

Design: docs/superpowers/specs/2026-09-20-pointer-integrity-design.md
STDLIB ONLY, Python 3.8+, no state kept between runs.
"""

import argparse
import fnmatch
import os
import random
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
    errors = []

    def _on_error(err):
        where = _norm(os.path.relpath(err.filename, root)) if getattr(err, "filename", None) else "."
        errors.append((where, str(err)))

    for dirpath, dirnames, filenames in os.walk(root, onerror=_on_error):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, root)
        for name in filenames:
            names.append(_norm(os.path.join(rel_dir, name)))
    return names, errors


def project_files(root):
    """(source, sorted paths, fallback reason, walk errors): git's file list, else a directory walk."""
    reason = ""
    try:
        proc = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if proc.returncode == 0:
            raw = proc.stdout.decode("utf-8", "replace").split("\0")
            return "git", sorted(set(_norm(n) for n in raw if n)), "", []
        err_lines = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        reason = err_lines[0] if err_lines else "git returned %d" % proc.returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        reason = "%s: %s" % (type(e).__name__, e)
    names, errors = _walk_names(root)
    return "directory walk", sorted(names), reason, errors


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
    source, names, reason, walk_errors = project_files(root)
    res = {
        "markers": {}, "pointers": [], "pointer_files": [], "malformed": [], "unreadable": list(walk_errors),
        "legacy": 0, "files": 0, "docs": 0, "binary": 0, "source": source, "fallback_reason": reason,
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
    via = res["source"]
    if res["fallback_reason"]:
        via += " (git unavailable: %s)" % res["fallback_reason"]
    print("docref: scanned %d files (%d docs) via %s; %d binary skipped"
          % (res["files"], res["docs"], via, res["binary"]))
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


def new_id(used, rng=random):
    """A 4-hex id not in `used`. Raises when the whole space is taken."""
    if len(used) >= 0x10000:
        raise RuntimeError("all 65536 ids are already in use")
    while True:
        candidate = "%04x" % rng.randrange(0x10000)
        if candidate not in used:
            return candidate


def cmd_new(root, excludes):
    res = scan(root, excludes)
    used = set(res["markers"]) | {p[2] for p in res["pointers"]}
    for rel, msg in res["unreadable"]:
        print("docref: warning: %s could not be read (%s); the id may collide with one used inside it"
              % (rel, msg), file=sys.stderr)
    print(new_id(used))
    return 0


def cmd_fix(root, excludes, write):
    res = scan(root, excludes)
    fixes = {pid: where[0][0] for pid, where in res["markers"].items() if len(where) == 1}
    verb = "rewrote" if write else "would rewrite"
    total = 0
    failed = 0
    for rel, msg in res["unreadable"]:
        print("%s  UNREADABLE  %s" % (rel, msg))
    for rel, full in res["pointer_files"]:
        try:
            text = _read_bytes(full).decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print("%s  UNREADABLE  %s" % (rel, e))
            failed += 1
            continue
        edits = []

        def repl(m, text=text, edits=edits):
            pid, raw = m.group(1), m.group(2)
            target = fixes.get(pid)
            pm = PATH_RE.match(raw)
            if not target or not pm or _norm(pm.group(0)) == target:
                return m.group(0)
            edits.append((text.count("\n", 0, m.start()) + 1, pm.group(0), target))
            head = m.group(0)[: m.start(2) - m.start(0)]
            return head + target + raw[pm.end():]

        new_text = POINTER_RE.sub(repl, text)
        if edits and write:
            try:
                with open(full, "w", encoding="utf-8", newline="") as f:
                    f.write(new_text)
            except OSError as e:
                print("%s  UNWRITABLE  %s" % (rel, e))
                failed += 1
                continue
        for line, old, target in edits:
            print("%s:%d  %s  %s -> %s" % (rel, line, verb, old, target))
        total += len(edits)
    print("docref: %s %d pointer(s)%s" % (verb, total, "" if write or not total else "; nothing written, pass --write to apply"))
    _, counts, _ = classify(res)
    unread = len(res["unreadable"])
    left = counts["dangling"] + counts["ambiguous"] + len(res["malformed"]) + unread
    if left:
        print("docref: still unresolved: %d dangling, %d ambiguous (duplicate id), %d malformed, "
              "%d unreadable - run docref.py check for the list"
              % (counts["dangling"], counts["ambiguous"], len(res["malformed"]), unread))
    if failed:
        print("docref: %d file(s) failed to read or write; see the lines above" % failed)
        return 2
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="docref.py", description="Keep doc-ref pointers true.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    helps = {
        "check": "report every pointer as ok, stale, dangling or malformed",
        "fix": "rewrite stale pointer paths by id (dry run unless --write)",
        "new": "print a 4-hex id no doc or pointer uses",
    }
    for name in ("check", "fix", "new"):
        p = sub.add_parser(name, help=helps[name])
        p.add_argument("--root", default=".")
        p.add_argument("--exclude", action="append", default=[], metavar="GLOB")
        if name == "fix":
            p.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if not os.path.isdir(root):
            print("docref: --root %s is not a directory" % root, file=sys.stderr)
            return 2
        if args.cmd == "check":
            return cmd_check(root, args.exclude)
        if args.cmd == "fix":
            return cmd_fix(root, args.exclude, args.write)
        return cmd_new(root, args.exclude)
    except Exception as e:  # last resort: say what broke, never a bare traceback or a silent 0
        print("docref: internal error: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
