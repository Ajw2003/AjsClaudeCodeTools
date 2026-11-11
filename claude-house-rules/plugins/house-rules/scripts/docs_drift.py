#!/usr/bin/env python3
"""docs_drift.py - finds living docs that cite code that moved, shrank or is gone.

    docs_drift.py [--root DIR]

Prints one line per drifted citation: `doc:line  cites  path:line  (gone | line N past the end,
file has M lines)`. Exit 1 when any, 0 when none, 2 when it could not tell. The guard imports
this file to name the docs that cite what a commit changes (house_rules/docs.py).

STDLIB ONLY, Python 3.8+.
"""

import argparse
import os
import re
import subprocess
import sys
import time

# Living docs only. docs/6-decisions/ (append-only history), docs/plans/, docs/sessions/,
# docs/audits/, docs/generated/ and docs/2-roadmap/triage/ are never scanned: their old line
# numbers were true for their date.
LIVING_DOCS = [
    "docs/1-landing/",
    "docs/2-roadmap/",
    "docs/3-state/",
    "docs/4-systems/",
    "docs/5-today/",
    "docs/architecture.md",
    "docs/README.md",
    "README.md",
    "CLAUDE.md",
]
EXCLUDED_DIRS = ["docs/2-roadmap/triage/"]

CITE_RE = re.compile(
    r"(?<![\w./\\-])(\w[\w./-]*\.(?:json|js|mjs|tsx|ts|py|sh|cs|ps1|bat))(?!\w)(?::(\d+)(?:[-–](\d+))?)?"
)


def living_doc_paths(root):
    """Repo-relative paths of the living docs that exist under root."""
    out = []
    for entry in LIVING_DOCS:
        full = os.path.join(root, entry)
        if entry.endswith("/"):
            for dirpath, _dirs, names in os.walk(full):
                for n in names:
                    if n.endswith(".md"):
                        rel = os.path.relpath(os.path.join(dirpath, n), root).replace(os.sep, "/")
                        if not any(rel.startswith(x) for x in EXCLUDED_DIRS):
                            out.append(rel)
        elif os.path.isfile(full):
            out.append(entry)
    return sorted(set(out))


def tracked_files(root, timeout=None):
    proc = subprocess.run(
        ["git", "ls-files"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError("git ls-files exited %d" % proc.returncode)
    return [p for p in proc.stdout.decode("utf-8", "replace").splitlines() if p]


def citations(text):
    """[(line_number, cited_path, cited_line_or_None, as_written)] found in a doc's text."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in CITE_RE.finditer(line):
            path = m.group(1)
            if path.startswith("./"):
                path = path[2:]
            nums = [int(g) for g in (m.group(2), m.group(3)) if g]
            found.append((n, path, max(nums) if nums else None, m.group(0)))
    return found


def resolve(root, cited, tracked):
    """('file', repo_path) | ('gone', None) | ('ambiguous', [repo paths])."""
    if os.path.isfile(os.path.join(root, cited)):
        return "file", cited
    matches = [t for t in tracked if (t == cited or t.endswith("/" + cited))
               and os.path.isfile(os.path.join(root, t))]
    if len(matches) == 1:
        return "file", matches[0]
    if not matches:
        return "gone", None
    return "ambiguous", matches


def _line_count(root, rel):
    with open(os.path.join(root, rel), "rb") as f:
        return len(f.read().decode("utf-8", "replace").splitlines())


def scan(root, tracked, deadline=None, docs=None):
    """Walk the living docs. Returns (rows, complete). Each row is a dict: doc, line, cited,
    as_written, status ('ok'|'gone'|'past'), path (resolved repo path or None), cited_line,
    total (file's line count or None). Ambiguous citations are left out. complete is False
    when the deadline ran out before every doc was read."""
    rows = []
    for doc in docs if docs is not None else living_doc_paths(root):
        if deadline is not None and time.time() > deadline:
            return rows, False
        try:
            with open(os.path.join(root, doc), "rb") as f:
                text = f.read().decode("utf-8", "replace")
        except OSError:
            continue
        for n, cited, cline, written in citations(text):
            kind, path = resolve(root, cited, tracked)
            if kind == "gone" and "/" not in cited:
                continue  # a bare name that is no repo file is usually a runtime file (settings.json)
            if kind == "ambiguous":
                # several files share the name (hook.py): drift only when the line is past the end of every one
                if cline is None:
                    continue
                biggest = max(_line_count(root, p) for p in path)
                if cline <= biggest:
                    continue
                rows.append({"doc": doc, "line": n, "cited": cited, "as_written": written, "path": None,
                             "cited_line": cline, "total": biggest, "status": "past", "every": len(path)})
                continue
            row = {"doc": doc, "line": n, "cited": cited, "as_written": written, "path": path,
                   "cited_line": cline, "total": None, "status": "ok"}
            if kind == "gone":
                row["status"] = "gone"
            elif cline is not None:
                total = _line_count(root, path)
                row["total"] = total
                if cline > total:
                    row["status"] = "past"
            rows.append(row)
    return rows, True


def drift_line(r):
    cite = "%s:%d" % (r["cited"], r["cited_line"]) if r["cited_line"] is not None else r["cited"]
    if r["status"] == "gone":
        why = "gone"
    elif r.get("every"):
        why = "line %d past the end of all %d files with that name, the longest has %d lines" % (
            r["cited_line"], r["every"], r["total"])
    else:
        why = "line %d past the end, file has %d lines" % (r["cited_line"], r["total"])
    return "%s:%d  cites  %s  (%s)" % (r["doc"], r["line"], cite, why)


def main(argv=None):
    ap = argparse.ArgumentParser(description="List living-doc citations of code that drifted.")
    ap.add_argument("--root", default=os.getcwd())
    args = ap.parse_args(argv)
    root = args.root
    try:
        tracked = tracked_files(root)
    except Exception as exc:
        print("docs_drift: could not list tracked files in %s (%s)" % (root, exc))
        return 2
    rows, _complete = scan(root, tracked)
    drift = [r for r in rows if r["status"] != "ok"]
    for r in drift:
        print(drift_line(r))
    print("docs_drift: %d drifted citation(s) in %d living doc(s)"
          % (len(drift), len(living_doc_paths(root))))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
