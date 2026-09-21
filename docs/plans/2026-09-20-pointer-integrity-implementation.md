# Pointer Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every code-to-doc pointer a stable ID and ship `docref.py`, a checker/fixer/ID-generator that keeps those pointers true, wired into `verify.py`, a `/house-rules:docref` command, and the archivist.

**Architecture:** One new stdlib-only script, `scripts/docref.py`, with three subcommands (`check`, `fix`, `new`). It scans doc files for `ref:` markers and every other project file for `doc-ref <id> <path>` pointers, classifies each pointer (ok / stale / dangling / ambiguous), and rewrites stale paths by ID. It is a command, not a hook. `verify.py` proves it with fixture projects in temp dirs; the archivist and rules text are changed to emit the new pointer.

**Tech Stack:** Python 3.8+ stdlib only (same floor as `hook.py`), the existing `verify.py` harness, Markdown.

**Spec:** [docs/superpowers/specs/2026-09-20-pointer-integrity-design.md](../superpowers/specs/2026-09-20-pointer-integrity-design.md). Brief it descends from: [2026-09-20-harvest-content-rules-and-pointer-integrity.md](2026-09-20-harvest-content-rules-and-pointer-integrity.md).

## Global Constraints

- **Working directory and branch:** `C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools`, branch `claude/pointer-integrity`. Commit there; do not push, merge or open a PR.
- **Shell on this machine:** Windows 11, PowerShell (Bash tool also available). Use `python`, forward slashes work in paths.
- **`docref.py` is stdlib-only, CPython 3.8+.** No third-party imports, and nothing newer than 3.8: no `str.removeprefix`, no `list[str]`-style generics, no `match` statements.
- **Keeps no state between runs.** No cache file, no log file.
- **Nothing fails silently.** Every path meaning "I could not tell" prints a line saying so. An unreadable file is named and forces a non-zero exit. An internal error prints to stderr and exits 2.
- **Exit codes:** `check` 0 clean / 1 problems found / 2 internal error. `fix` 0 unless internal error (2).
- **ID grammar:** 4 lowercase hex characters. **Marker grammar:** the comment `<!-- ref:ID -->` alone on its own line in a doc. **Pointer grammar:** `doc-ref ID PATH` anywhere on a line in a non-doc file, PATH ending in `.md`, relative to the project root, forward slashes.
- **Doc files** are `docs/**/*.md` (markers are read only from these, and never from inside a fenced code block). **Everything else** is scanned for pointers; nothing under `docs/` is.
- **Never write a well-formed example pointer in prose or comments** outside `verify.py` and `docref.py`. Use placeholders (`doc-ref <id> <path>`), which the grammar does not match. The live check in Task 3 runs on this repo's own files and would flag a concrete example as dangling.
- **Keep comments in `docref.py` short** (well under 500 characters per block). The harvest hook flags longer ones; rationale lives in the Decisions entry (Task 5).
- **`verify.py` computes its own check count.** Never write that number anywhere.
- **The plugin version becomes 2.28.0** (Task 5). Do not bump it earlier.
- **The `guard` hook may prompt** on `git add`; approving that is expected. A plain `git commit` on a `claude/` branch does not prompt.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `claude-house-rules/plugins/house-rules/scripts/docref.py` | create | scan, classify, check, fix, new |
| `claude-house-rules/plugins/house-rules/scripts/verify.py` | modify | fixture tests for docref, command check, live check, drift phrases |
| `claude-house-rules/plugins/house-rules/commands/docref.md` | create | `/house-rules:docref` |
| `claude-house-rules/plugins/house-rules/agents/archivist.md` | modify | emit `doc-ref` pointers and markers, use `docref.py new` and `fix` |
| `claude-house-rules/plugins/house-rules/rules/house-rules.md` | modify | pointer wording in the long-form rule |
| `claude-house-rules/plugins/house-rules/scripts/hook.py` | modify | the same wording in the harvest reminder string |
| `claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md` | modify | mention `docref fix` where it says "fix the pointers" |
| `claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json` | modify | 2.27.0 to 2.28.0 |
| `docs/Decisions.md`, `docs/architecture.md`, `CLAUDE.md`, `claude-house-rules/README.md`, the spec, the handoff plan | modify | record the decisions, document the command |

`docref.py` is one file on purpose: it is about 250 lines with one responsibility, and it must be a single script the command can invoke.

---

### Task 1: `docref.py check`, test-first

**Files:**
- Create: `claude-house-rules/plugins/house-rules/scripts/docref.py`
- Modify: `claude-house-rules/plugins/house-rules/scripts/verify.py` (append a section after the versioncheck cleanup, immediately before the final `print()` / `print("-" * 32)` result block near the end of the file)

**Interfaces:**
- Consumes: `make_fixture(files)` and `report(result, title)` from `verify.py` (already defined above the insertion point; `make_fixture` writes text files into a new temp dir and returns its path).
- Produces (in `docref.py`):
  - `scan(root, excludes=()) -> dict` with keys `markers` (`{id: [(rel, line), ...]}`), `pointers` (`[(rel, line, id, path), ...]`), `pointer_files` (`[(rel, full_path), ...]`), `malformed` (`[(rel, line, message), ...]`), `unreadable` (`[(rel, message), ...]`), `legacy` (int), `files`, `docs`, `binary` (ints), `source` (`"git"` or `"directory walk"`).
  - `classify(res) -> (findings, counts, info)`: `findings` is `[(rel, line, kind, message), ...]` sorted by file and line, `counts` is `{"ok", "stale", "dangling", "ambiguous"}`, `info` is `[(rel, line, message), ...]`.
  - `cmd_check(root, excludes) -> int` (the exit code).
  - `main(argv=None) -> int`.
  - CLI: `python docref.py check [--root DIR] [--exclude GLOB]...`.
- In `verify.py`: `docref_run(root, *args) -> (rc, stdout, stderr)` and `docref_case(title, files, args, expect_rc, expect_in=(), expect_out=(), after=None, setup=None)`, used by Task 2 and 3.

- [ ] **Step 1: Write the failing tests**

Find the end of the versioncheck section in `verify.py` (the lines `if os.path.isfile(marker_c):` / `    os.remove(marker_c)` just above the final `print()` and `print("-" * 32)`). Insert this block directly after them:

```python
# --- docref.py: the doc-ref pointer checker ----------------------------------------------------
# Design: docs/superpowers/specs/2026-09-20-pointer-integrity-design.md
DOCREF = os.path.join(HERE, "docref.py")
FENCE = "`" * 3


def docref_run(root, *args):
    cmd = [sys.executable, DOCREF, args[0], "--root", root] + list(args[1:])
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def docref_case(title, files, args, expect_rc, expect_in=(), expect_out=(), after=None, setup=None):
    d = make_fixture(files)
    try:
        if setup is not None:
            setup(d)
        rc, out, err = docref_run(d, *args)
        problems = []
        if rc != expect_rc:
            problems.append(f"exit {rc}, expected {expect_rc}")
        for needle in expect_in:
            if needle not in out:
                problems.append(f"output is missing {needle!r}")
        for needle in expect_out:
            if needle in out:
                problems.append(f"output should not contain {needle!r}")
        if after is not None:
            ok, detail = after(d)
            if not ok:
                problems.append(detail)
        if not problems:
            report("PASS", title)
            print("          " + (out.strip().splitlines() or ["(no output)"])[-1][:100])
        else:
            report("FAIL", title)
            for p in problems:
                print(f"          {p}")
            print(f"          stdout: {out[:400]!r} stderr: {err[:200]!r}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


DR_DOC = "## Traps\n<!-- ref:a3f9 -->\nBody.\n"

docref_case(
    "docref check: a pointer whose id is in exactly one doc, at the recorded path, is ok",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "int x;\n// doc-ref a3f9 docs/systems/physics.md\n"},
    ["check"], 0,
    expect_in=["1 ok, 0 stale, 0 dangling", "docref: OK"],
)

docref_case(
    "docref check: a pointer whose doc moved is reported stale, naming the doc it moved to",
    {"docs/systems/new.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/old.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:1  STALE", "docs/systems/new.md", "1 stale"],
)

docref_case(
    "docref check: a pointer whose id no doc carries is dangling, with file and line",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "int x;\n// doc-ref beef docs/systems/physics.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:2  DANGLING", "1 dangling", "docref: PROBLEMS"],
)

docref_case(
    "docref check: one id claimed by two markers is a duplicate, and pointers to it are ambiguous",
    {"docs/a.md": DR_DOC, "docs/b.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["DUPLICATE", "a3f9", "1 ambiguous"],
)

docref_case(
    "docref check: an uppercase pointer id is malformed, not silently ignored",
    {"docs/a.md": DR_DOC, "src/a.c": "// doc-ref A3F9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:1  MALFORMED", "not 4 lowercase hex"],
)

docref_case(
    "docref check: a marker with a 3-character id is malformed",
    {"docs/a.md": "## T\n<!-- ref:abc -->\n"},
    ["check"], 1,
    expect_in=["docs/a.md:2  MALFORMED"],
)

docref_case(
    "docref check: a marker inside a fenced code block is ignored",
    {
        "docs/a.md": "Example:\n" + FENCE + "\n<!-- ref:a3f9 -->\n" + FENCE + "\n",
        "src/a.c": "// doc-ref a3f9 docs/a.md\n",
    },
    ["check"], 1,
    expect_in=["DANGLING"],
)

docref_case(
    "docref check: a marker quoted inline in prose is not a marker",
    {"docs/a.md": "Put `<!-- ref:a3f9 -->` under the heading.\n", "src/a.c": "// doc-ref a3f9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["DANGLING"],
)

docref_case(
    "docref check: a marker nobody points at is information, not a failure",
    {"docs/a.md": DR_DOC},
    ["check"], 0,
    expect_in=["docs/a.md:2  INFO", "unreferenced", "docref: OK"],
)

docref_case(
    "docref check: a project with no docs and no pointers says so and passes",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["0 pointers found", "no docs/**/*.md", "docref: OK"],
)

docref_case(
    "docref check: prose pointers are counted as legacy, not judged",
    {"docs/systems/physics.md": "## T\n", "src/a.c": "// see docs/systems/physics.md, Traps\n"},
    ["check"], 0,
    expect_in=["1 line(s) mention docs/systems/", "legacy prose pointers"],
)

docref_case(
    "docref check: the words doc-ref in ordinary prose are not a pointer",
    {"src/a.c": "// the doc-ref token is what carries the id\n"},
    ["check"], 0,
    expect_in=["0 pointers found"],
)

docref_case(
    "docref check: --exclude skips a matching file",
    {"src/bad.c": "// doc-ref beef docs/none.md\n"},
    ["check", "--exclude", "src/bad.c"], 0,
    expect_in=["0 pointers found"],
)


def _dr_write_binary(d):
    with open(os.path.join(d, "blob.bin"), "wb") as f:
        f.write(b"\xff\xfe\x00\x01")


docref_case(
    "docref check: a binary file is counted as skipped, not read and not an error",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["1 binary skipped", "via directory walk"],
    setup=_dr_write_binary,
)


def _dr_git_setup(d):
    for args in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", "-C", d] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    with open(os.path.join(d, "src", "untracked.c"), "w", encoding="utf-8") as f:
        f.write("// doc-ref beef docs/none.md\n")


if shutil.which("git"):
    docref_case(
        "docref check: in a git work tree it reads tracked and untracked files and skips ignored ones",
        {
            ".gitignore": "ignored/\n",
            "docs/x.md": "## T\n<!-- ref:a3f9 -->\n",
            "src/tracked.c": "// doc-ref a3f9 docs/x.md\n",
            "ignored/bad.c": "// doc-ref beef docs/none.md\n",
        },
        ["check"], 1,
        expect_in=["src/untracked.c:1  DANGLING", "via git"],
        expect_out=["ignored/bad.c"],
        setup=_dr_git_setup,
    )
else:
    report("FAIL", "docref check: in a git work tree it reads tracked and untracked files")
    print("          git is not on PATH; this machine's environment says it should be")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (PowerShell, from anywhere):

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "docref"
```

Expected: every `docref check:` line reads `FAIL`, with `exit 2, expected ...` because `docref.py` does not exist yet. No traceback from `verify.py` itself.

- [ ] **Step 3: Write `docref.py` with the `check` subcommand**

Create `claude-house-rules/plugins/house-rules/scripts/docref.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "docref"
```

Expected: every `docref check:` line reads `PASS`. If one fails, read its indented detail lines: they give the exit code and the first 400 characters of stdout. Fix `docref.py`, not the test, unless the test contradicts the spec.

Then confirm nothing else regressed:

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-Object -Last 8
```

Expected: `RESULT: PASS - all N checks passed.`

- [ ] **Step 5: Commit**

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" add claude-house-rules/plugins/house-rules/scripts/docref.py claude-house-rules/plugins/house-rules/scripts/verify.py
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" commit -m "feat: add docref.py check for doc-ref pointer integrity" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `docref.py fix` and `new`, plus loud failures

**Files:**
- Modify: `claude-house-rules/plugins/house-rules/scripts/docref.py`
- Modify: `claude-house-rules/plugins/house-rules/scripts/verify.py` (append after Task 1's block)

**Interfaces:**
- Consumes: `scan`, `classify`, `_read_bytes`, `_norm`, `POINTER_RE`, `PATH_RE`, `ID_RE` from Task 1; `docref_run`, `docref_case`, `make_fixture`, `report` in `verify.py`.
- Produces: `new_id(used, rng=random) -> str`, `cmd_fix(root, excludes, write) -> int`, `cmd_new(root, excludes) -> int`; CLI `python docref.py fix [--root DIR] [--exclude GLOB]... [--write]` and `python docref.py new [--root DIR] [--exclude GLOB]...`.

- [ ] **Step 1: Write the failing tests**

Append to `verify.py`, directly after Task 1's block:

```python
DR_STALE = {"docs/systems/new.md": DR_DOC, "src/a.c": "int x;\n// doc-ref a3f9 docs/old.md\n"}


def _dr_file_has(rel, needle, absent=None):
    def _check(d):
        with open(os.path.join(d, rel), "rb") as f:
            data = f.read().decode("utf-8")
        if needle not in data:
            return False, f"{rel} does not contain {needle!r}"
        if absent is not None and absent in data:
            return False, f"{rel} still contains {absent!r}"
        return True, ""
    return _check


docref_case(
    "docref fix: without --write it reports what it would change and writes nothing",
    DR_STALE, ["fix"], 0,
    expect_in=["would rewrite", "docs/old.md -> docs/systems/new.md", "nothing written"],
    after=_dr_file_has("src/a.c", "docs/old.md"),
)


def _dr_fixed_then_clean(d):
    ok, detail = _dr_file_has("src/a.c", "docs/systems/new.md", absent="docs/old.md")(d)
    if not ok:
        return ok, detail
    rc, out, err = docref_run(d, "check")
    return (rc == 0, f"check still exits {rc} after fix: {out[-200:]!r}")


docref_case(
    "docref fix --write: repairs a stale path by id, and check is clean afterwards",
    DR_STALE, ["fix", "--write"], 0,
    expect_in=["rewrote", "docs/old.md -> docs/systems/new.md"],
    after=_dr_fixed_then_clean,
)


def _dr_write_crlf(d):
    with open(os.path.join(d, "src", "a.c"), "wb") as f:
        f.write(b"int x;\r\n// doc-ref a3f9 docs/old.md\r\n")


def _dr_crlf_kept(d):
    with open(os.path.join(d, "src", "a.c"), "rb") as f:
        got = f.read()
    want = b"int x;\r\n// doc-ref a3f9 docs/systems/new.md\r\n"
    return got == want, f"bytes after fix were {got!r}, wanted {want!r}"


docref_case(
    "docref fix --write: keeps CRLF line endings byte-for-byte",
    DR_STALE, ["fix", "--write"], 0,
    after=_dr_crlf_kept, setup=_dr_write_crlf,
)

docref_case(
    "docref fix --write: keeps a trailing comment closer on the same line",
    {"docs/systems/new.md": DR_DOC, "src/a.c": "/* doc-ref a3f9 docs/old.md */\n"},
    ["fix", "--write"], 0,
    after=_dr_file_has("src/a.c", "/* doc-ref a3f9 docs/systems/new.md */"),
)

docref_case(
    "docref fix --write: leaves a dangling pointer alone and says it is unresolved",
    {
        "docs/systems/new.md": DR_DOC,
        "src/a.c": "// doc-ref a3f9 docs/old.md\n// doc-ref beef docs/gone.md\n",
    },
    ["fix", "--write"], 0,
    expect_in=["still unresolved: 1 dangling"],
    after=_dr_file_has("src/a.c", "doc-ref beef docs/gone.md"),
)

docref_case(
    "docref fix --write: refuses to touch pointers to a duplicated id",
    {"docs/a.md": DR_DOC, "docs/b.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/zzz.md\n"},
    ["fix", "--write"], 0,
    expect_in=["still unresolved", "1 ambiguous"],
    after=_dr_file_has("src/a.c", "docs/zzz.md"),
)

docref_case(
    "docref fix: with nothing stale it says so and exits 0",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/systems/physics.md\n"},
    ["fix", "--write"], 0,
    expect_in=["0 pointer(s)"],
)

_d = make_fixture({"docs/a.md": DR_DOC, "src/a.c": "// doc-ref beef docs/none.md\n"})
try:
    _rc, _out, _err = docref_run(_d, "new")
    _id = _out.strip()
    if _rc == 0 and re.fullmatch(r"[0-9a-f]{4}", _id) and _id not in ("a3f9", "beef"):
        report("PASS", "docref new: prints a 4-hex id not used by any marker or pointer")
        print(f"          printed {_id}")
    else:
        report("FAIL", "docref new: prints a 4-hex id not used by any marker or pointer")
        print(f"          rc={_rc} stdout={_out[:80]!r} stderr={_err[:120]!r}")
finally:
    shutil.rmtree(_d, ignore_errors=True)

import importlib.util

_spec = importlib.util.spec_from_file_location("docref_under_test", DOCREF)
docref_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docref_mod)


class _SeqRng:
    def __init__(self, seq):
        self.seq = list(seq)

    def randrange(self, n):
        return self.seq.pop(0)


if docref_mod.new_id({"a3f9"}, _SeqRng([0xA3F9, 0xA3F9, 0x0001])) == "0001":
    report("PASS", "docref new_id: skips ids that are already used and returns the first free one")
else:
    report("FAIL", "docref new_id: skips ids that are already used and returns the first free one")

try:
    docref_mod.new_id({"%04x" % i for i in range(0x10000)})
    report("FAIL", "docref new_id: says so when all 65536 ids are used")
except RuntimeError as _e:
    report("PASS", "docref new_id: says so when all 65536 ids are used")
    print(f"          {_e}")

# An unreadable file must be named and must fail the check - not be skipped quietly.
import contextlib
import io

_d = make_fixture({"docs/a.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/a.md\n"})
_orig_read = docref_mod._read_bytes


def _boom(path):
    if path.endswith("a.c"):
        raise PermissionError("denied on purpose")
    return _orig_read(path)


docref_mod._read_bytes = _boom
_buf = io.StringIO()
try:
    with contextlib.redirect_stdout(_buf):
        _rc = docref_mod.main(["check", "--root", _d])
finally:
    docref_mod._read_bytes = _orig_read
    shutil.rmtree(_d, ignore_errors=True)
if _rc == 1 and "src/a.c  UNREADABLE  denied on purpose" in _buf.getvalue():
    report("PASS", "docref check: an unreadable file is named and fails the check")
else:
    report("FAIL", "docref check: an unreadable file is named and fails the check")
    print(f"          rc={_rc} stdout={_buf.getvalue()[:300]!r}")

_proc = subprocess.run(
    [sys.executable, DOCREF, "check", "--root", os.path.join(ROOT, "no", "such", "dir")],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
if _proc.returncode == 2 and b"is not a directory" in _proc.stderr:
    report("PASS", "docref check: a --root that is not a directory exits 2 and says why on stderr")
else:
    report("FAIL", "docref check: a --root that is not a directory exits 2 and says why on stderr")
    print(f"          rc={_proc.returncode} stderr={_proc.stderr[:160]!r}")
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "docref (fix|new)"
```

Expected: the `docref fix` and `docref new` lines FAIL (argparse rejects the unknown subcommand, exit 2). `verify.py` itself will stop with an `AttributeError: ... has no attribute 'new_id'` at the `docref_mod.new_id` line: that is the expected failure for this step, since the module lacks the function.

- [ ] **Step 3: Implement `fix`, `new`, and the parser entries**

In `docref.py`, add `import random` to the import block (alphabetical, after `import os`):

```python
import argparse
import fnmatch
import os
import random
import re
import subprocess
import sys
```

Insert these functions immediately above `def main`:

```python
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
    print(new_id(used))
    return 0


def cmd_fix(root, excludes, write):
    res = scan(root, excludes)
    fixes = {pid: where[0][0] for pid, where in res["markers"].items() if len(where) == 1}
    verb = "rewrote" if write else "would rewrite"
    total = 0
    for rel, full in res["pointer_files"]:
        text = _read_bytes(full).decode("utf-8")
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
        for line, old, target in edits:
            print("%s:%d  %s  %s -> %s" % (rel, line, verb, old, target))
        if edits and write:
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
        total += len(edits)
    print("docref: %s %d pointer(s)%s" % (verb, total, "" if write or not total else "; nothing written, pass --write to apply"))
    _, counts, _ = classify(res)
    left = counts["dangling"] + counts["ambiguous"] + len(res["malformed"])
    if left:
        print("docref: still unresolved: %d dangling, %d ambiguous (duplicate id), %d malformed - "
              "run docref.py check for the list" % (counts["dangling"], counts["ambiguous"], len(res["malformed"])))
    return 0
```

Replace the whole `main` function (from `def main(argv=None):` to the `return 2` line at the end of its `except`) with:

```python
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
```

Also update the module docstring's usage block to list all three subcommands:

```python
"""docref.py - keeps the doc-ref pointers the archivist leaves in code true.

    docref.py check [--root DIR] [--exclude GLOB ...]
    docref.py fix   [--root DIR] [--exclude GLOB ...] [--write]
    docref.py new   [--root DIR] [--exclude GLOB ...]

Design: docs/superpowers/specs/2026-09-20-pointer-integrity-design.md
STDLIB ONLY, Python 3.8+, no state kept between runs.
"""
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "docref"
```

Expected: every `docref` line reads `PASS`. If `docref fix --write: keeps CRLF ...` fails, the write path is translating line endings: confirm the `open(..., newline="")` argument is present and that the text was decoded from bytes, not read in text mode.

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-Object -Last 8
```

Expected: `RESULT: PASS - all N checks passed.`

- [ ] **Step 5: Commit**

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" add claude-house-rules/plugins/house-rules/scripts/docref.py claude-house-rules/plugins/house-rules/scripts/verify.py
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" commit -m "feat: add docref fix and new, and loud failures for unreadable files" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: the `/house-rules:docref` command and the live check

**Files:**
- Create: `claude-house-rules/plugins/house-rules/commands/docref.md`
- Modify: `claude-house-rules/plugins/house-rules/scripts/verify.py` (append after Task 2's block)

**Interfaces:**
- Consumes: `docref_run`, `absent_repo_files`, `skip_repo_check`, `read`, `HERE`, `ROOT`, `report` in `verify.py`.
- Produces: the slash command `/house-rules:docref`; two `verify.py` checks (command shape, live run on this repo).

- [ ] **Step 1: Write the failing tests**

Append to `verify.py`:

```python
# --- /house-rules:docref exists and runs the installed docref.py -------------------------------
DOCREF_CMD = os.path.join(HERE, "..", "commands", "docref.md")
drdrift = []
if not os.path.isfile(DOCREF_CMD):
    drdrift.append("commands/docref.md is missing")
else:
    _dr_cmd_text = read(DOCREF_CMD)
    for needle in ["docref.py", "${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS",
                   "the plugin root did not resolve", "fix --write"]:
        if needle not in _dr_cmd_text:
            drdrift.append(f"docref.md is missing {needle!r}")
    if re.search(r"\$CLAUDE_PLUGIN_ROOT", _dr_cmd_text):
        drdrift.append("docref.md uses bare $CLAUDE_PLUGIN_ROOT (must be braced)")
if not drdrift:
    report("PASS", "/house-rules:docref exists and runs the installed docref.py")
    print("          resolves via ${CLAUDE_PLUGIN_ROOT}, never a hand-built cache path")
else:
    report("FAIL", "/house-rules:docref exists and runs the installed docref.py")
    print(f"          {'; '.join(drdrift)}")

# --- the repo's own docs and code pass docref check ----------------------------------------------
# verify.py and docref.py are excluded: they hold well-formed example pointers on purpose.
_dr_live = "docref check passes on this repo's own docs and code"
_absent = absent_repo_files("docs/Decisions.md", "docs/README.md")
if _absent:
    skip_repo_check(_dr_live, _absent)
else:
    _rc, _out, _err = docref_run(
        ROOT, "check",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/verify.py",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/docref.py",
    )
    if _rc == 0:
        report("PASS", _dr_live)
        print("          " + [l for l in _out.splitlines() if "pointers found" in l][0])
    else:
        report("FAIL", _dr_live)
        print(f"          exit {_rc}: {_out[-500:]!r} {_err[:200]!r}")
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "house-rules:docref|docref check passes"
```

Expected: `/house-rules:docref exists ...` FAILs with `commands/docref.md is missing`. The live check should already PASS (this repo has no pointers yet); that is fine, it is a regression guard, not a red test.

- [ ] **Step 3: Write the command file**

Create `claude-house-rules/plugins/house-rules/commands/docref.md`:

```markdown
---
description: Check, and optionally repair, the doc-ref pointers the archivist leaves in code
argument-hint: check|fix [--write] [--exclude GLOB] | new
---

The archivist moves long comments into `docs/` and leaves a pointer behind: `doc-ref <id> <path>`
in the code, and a `<!-- ref:<id> -->` marker line under the moved note's heading in the doc.
`scripts/docref.py` proves those pointers still lead somewhere, and repairs the ones a doc move
made stale. It is a command you run, not a hook: nothing runs it for you.

Run, in this project's own root, using the installed plugin's own copy of the script so it always
matches whatever version is actually installed — never a path you construct by hand:

` ` `
python "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py" $ARGUMENTS
` ` `

If the path in the command you are about to run does not begin with a real absolute plugin
directory (it is empty, still shows `${CLAUDE_PLUGIN_ROOT}`, or begins with `/scripts`), STOP and
tell the user the plugin root did not resolve. Do not search `~/.claude/plugins` for a copy or
guess a path — the cache holds several versions.

If `$ARGUMENTS` is empty, run it with `check`.

- `check` — every pointer is ok, stale (the doc moved), dangling (no doc carries that id),
  ambiguous (two docs claim the id) or malformed. Exit 1 means it found something.
- `fix` — shows the stale paths it would rewrite. `fix --write` rewrites them. It resolves by id
  only, and never touches a dangling, ambiguous or malformed pointer.
- `new` — prints an unused 4-hex id, for the archivist to put on a new marker.

Report the output as it comes back. Then:

- Clean run: say so in one line. Do not invent follow-up work.
- **Dangling** pointers are a decision for the user, not something to repair on your own: either
  the note was deleted (remove the pointers) or its marker was lost (restore it). List them and
  ask which.
- Legacy prose pointers ("see the Traps section of physics.md") are counted, never judged. Do not
  convert them unless asked.
```

**Important:** in the file you write, the fence around the `python` line must be three real backticks, not the spaced `` ` ` ` `` shown above (spaced here only so this plan's own code block survives). Compare with `commands/harvest-scan.md`, which uses a plain triple-backtick fence.

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "house-rules:docref|docref check passes"
```

Expected: both `PASS`. Then the full run:

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-Object -Last 8
```

Expected: `RESULT: PASS - all N checks passed.` The existing `harvest-scan` check also loops over every file in `commands/` looking for a bare `$CLAUDE_PLUGIN_ROOT`, so it now covers `docref.md` too.

- [ ] **Step 5: Commit**

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" add claude-house-rules/plugins/house-rules/commands/docref.md claude-house-rules/plugins/house-rules/scripts/verify.py
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" commit -m "feat: add /house-rules:docref and a live docref check on this repo" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: archivist, rules text and harvest reminder emit the new pointer

**Files:**
- Modify: `claude-house-rules/plugins/house-rules/scripts/verify.py` (three existing phrase lists)
- Modify: `claude-house-rules/plugins/house-rules/agents/archivist.md`
- Modify: `claude-house-rules/plugins/house-rules/rules/house-rules.md`
- Modify: `claude-house-rules/plugins/house-rules/scripts/hook.py` (the harvest reminder string, near line 1849)
- Modify: `claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md`

**Interfaces:**
- Consumes: the existing drift checks in `verify.py` (rules phrases near line 1599, emitted-reminder phrases near line 1617, archivist phrases near line 1743).
- Produces: the pointer wording `doc-ref <id> <path>` and the marker wording `<!-- ref:<id> -->` in all four places, and the pointer to `docref.py`.

Order matters here: the drift lists change first, so the test fails until every restatement agrees.

- [ ] **Step 1: Write the failing tests (extend the drift lists)**

In `verify.py`:

1. The rules-drift list (the line beginning `for phrase in ["long-form", "one-line pointer", "@house-rules:archivist", "docs/systems", "docs/Decisions.md"]:`). Add `"doc-ref"` and `"docref.py"`:

```python
for phrase in ["long-form", "one-line pointer", "@house-rules:archivist", "docs/systems", "docs/Decisions.md", "doc-ref", "docref.py"]:
```

2. The emitted-reminder list (the `for phrase in [` block containing `"one-line pointer",` and `"the user was not prompted",`). Add two entries:

```python
    "doc-ref",
    "docref.py",
```

3. The archivist phrase list (the line `for phrase in ("not injected", "one-line pointer", "Nothing fails silently", "docs/systems"):`):

```python
for phrase in ("not injected", "one-line pointer", "Nothing fails silently", "docs/systems",
               "doc-ref", "<!-- ref:", "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py", "fix --write"):
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-String "harvest reminder|archivist subagent"
```

Expected: three FAILs, each naming the missing phrase (`doc-ref`, `docref.py`, and the archivist's `<!-- ref:` / `${CLAUDE_PLUGIN_ROOT}/scripts/docref.py` / `fix --write`).

- [ ] **Step 3: Edit the four texts**

**`rules/house-rules.md`.** Replace:

```
`docs/Decisions.md` instead. Either way the site keeps a **one-line pointer** naming the
document and section, so the code still leads to the reasoning. Anything a reader genuinely
```

with:

```
`docs/Decisions.md` instead. Either way the site keeps a **one-line pointer**
`doc-ref <id> <path>` (in that language's comment syntax), where `<id>` is the 4-hex marker
`<!-- ref:<id> -->` on its own line under the moved note's heading, made with `docref.py new` —
so the code still leads to the reasoning and `docref.py check` can prove it still does. Anything a reader genuinely
```

**`hook.py`.** In the harvest reminder string, replace the two adjacent string literals:

```python
    "a dated entry in docs/Decisions.md instead. Either way, leave a one-line pointer at the "
    "site naming the document and section, so the code still leads to the reasoning. Anything "
```

with:

```python
    "a dated entry in docs/Decisions.md instead. Either way, leave a one-line pointer at the "
    "site: doc-ref <id> <path>, where <id> is a 4-hex ref marker on its own line under the "
    "moved note's heading in the doc, made with docref.py new, so the code still leads to the "
    "reasoning and docref.py check can prove it still does. Anything "
```

**`agents/archivist.md`.** Four edits.

(a) Replace the bullet:

```
- **Leave a one-line pointer** at the site, in that language's comment syntax, naming the
  document and the section — the code must still lead to the reasoning.
```

with:

```
- **Give the moved note an id, and leave a one-line pointer** at the site. Get an unused id with
  `python "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py" new`. In the doc, put `<!-- ref:<id> -->` on
  its own line directly under the moved note's heading. At the site, in that language's comment
  syntax, leave `doc-ref <id> <path>` (the path is the doc, from the project root, ending in
  `.md`) — the code must still lead to the reasoning. If that path does not begin with a real
  absolute plugin directory (it is empty, or still shows `${CLAUDE_PLUGIN_ROOT}`), say so in your
  report and leave the id for the caller to allocate; do not invent one.
```

(b) In "Pass 1", replace `At each original site, leave the one-line pointer aimed at this\nstaging file for now.` with:

```
At each original site, leave `doc-ref <id> <path>` aimed at this staging file for now; the
staging entry carries its `<!-- ref:<id> -->` marker line from the start.
```

(c) In "Pass 2", replace `Once a block lands at its real destination, update its original site's one-line pointer to name\nthat destination instead of the staging file, and delete the entry from the staging file.` with:

```
Once a block lands at its real destination, move its marker line with it, then run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py" fix --write`, which repoints every site by id
instead of you editing each one. Delete the entry from the staging file.
```

(d) In the digest, replace `pointer so the code still leads to it. Route by what it is:` (the second line of the first digest bullet; read the surrounding text before editing) so that the bullet states the id. Concretely, replace:

```
- Long-form reasoning belongs in a document, not a comment; the site keeps a one-line
  pointer so the code still leads to it. Route by what it is:
```

with:

```
- Long-form reasoning belongs in a document, not a comment; the site keeps a one-line
  pointer, `doc-ref <id> <path>`, backed by a `<!-- ref:<id> -->` marker under the note's
  heading, so the code still leads to it. Route by what it is:
```

**`skills/project-docs/SKILL.md`.** Replace:

```
Move, then
  fix the pointers.
```

with:

```
Move, then
  fix the pointers — `/house-rules:docref fix --write` does it for code pointers in the
  `doc-ref` form.
```

and replace:

```
   Fix every pointer into the moved documents — do not leave the link graph broken.
```

with:

```
   Fix every pointer into the moved documents — do not leave the link graph broken. Code
   pointers in the `doc-ref` form are repaired mechanically by `/house-rules:docref fix --write`.
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-Object -Last 8
```

Expected: `RESULT: PASS - all N checks passed.` The live docref check must still pass: it scans the rules, archivist and skill files you just edited, and would fail if any of them contains a well-formed example pointer. If it does, replace that example with a placeholder.

- [ ] **Step 5: Commit**

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" add claude-house-rules/plugins/house-rules/agents/archivist.md claude-house-rules/plugins/house-rules/rules/house-rules.md claude-house-rules/plugins/house-rules/scripts/hook.py claude-house-rules/plugins/house-rules/scripts/verify.py claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" commit -m "feat: archivist, rules and harvest reminder now emit doc-ref pointers" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: docs, version bump, and verification at real scale

**Files:**
- Modify: `claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json`
- Modify: `docs/Decisions.md`, `docs/architecture.md`, `CLAUDE.md`, `claude-house-rules/README.md`
- Modify: `docs/superpowers/specs/2026-09-20-pointer-integrity-design.md`, `docs/plans/2026-09-20-harvest-content-rules-and-pointer-integrity.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a documented, versioned, verified change ready for a pull request.

- [ ] **Step 1: Bump the version**

In `plugin.json` change `"version": "2.27.0"` to `"version": "2.28.0"`. Then check whether any other file records the plugin version:

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" grep -n "2\.27\.0" -- ":!docs/sessions" ":!docs/Decisions.md"
```

Expected: no hits other than `plugin.json`'s old value (already changed) and historical mentions in docs. If `.claude-plugin/marketplace.json` or another file pins `2.27.0` as the current version, update it too.

- [ ] **Step 2: Record the decision in `docs/Decisions.md`**

Insert a new entry as the first one (immediately after the header's `---` line, above the existing `## 2026-09-20 — Size the harvest threshold by characters alone, default 500` entry), in the same format:

```markdown
## 2026-09-20 — Pointers carry a stable id, and a command keeps them true

**Context.** The archivist left "a one-line pointer naming the document and section". Nothing
checked it, so a renamed heading or a doc moved to `docs/archive/` left the pointer lying, silently.
The `project-docs` skill said to "fix the pointers" when a doc moves, with no tool behind it.

**Decision.** A moved note gets a 4-hex id. In the doc it is a `<!-- ref:<id> -->` marker alone on
its own line under the heading; in code it is `doc-ref <id> <path>` in any language's comment
syntax. `scripts/docref.py` has `check` (ok / stale / dangling / ambiguous / malformed),
`fix --write` (rewrites stale paths by id only), and `new` (an unused id). It is a command, run by
`verify.py` and `/house-rules:docref`, **not a hook**: a doc-write hook is deferred until its cost
can be measured against a working checker. Existing prose pointers are left alone and only counted.

Two refinements over the spec, found while writing the plan: (1) a marker must be alone on its
line, so a doc that quotes one inline does not register a fake marker; (2) the file list is
`git ls-files --cached --others --exclude-standard` when the root is a git work tree, else a
directory walk, and the output names which — so ignored build output is never read and a note
moved into an uncommitted doc is still seen.

**Alternatives rejected.** Path plus heading anchor (a rename is indistinguishable from a
delete, so the fixer can only guess); fuzzy-matched heading text (repairs are guesses a person
must review); a hook on doc writes (adds file reads to the write path before we know what they
cost); extending `harvest_scan.py` (a different job, finding comments to move, in the same file).

**Why.** A pointer that can lie silently is worse than none: it is trusted. An id makes the
common failure (doc moved or renamed) mechanical, and everything that is not mechanical
(a deleted note) is reported with `file:line` for a person to decide.

**Status.** Standing. Piece B of the harvest content-rules work; A and C build on it.
```

- [ ] **Step 3: Document it in `docs/architecture.md`, `CLAUDE.md` and the README**

`docs/architecture.md`: append a section at the end of the file:

```markdown
## `docref.py` is a command, not a hook

`scripts/docref.py` checks and repairs the `doc-ref` pointers the archivist leaves in code (see
the Decisions entry of 2026-09-20). It is stdlib-only and keeps no state, like `hook.py`, but it
is deliberately not registered on any event: `hooks.json` is unchanged and the events table in
`CLAUDE.md` stays as it was. It reads the file list from `git ls-files` (tracked plus untracked
non-ignored) so build output is never scanned, falling back to a directory walk outside a git
work tree, and says which it used. A doc-write hook that calls it is a possible follow-up, to be
priced with `tools/measure_footprint.py` before it is built.
```

`CLAUDE.md`: in the Commands section, after the paragraph that describes `tools/session_ledger.py` and before `## Architecture`, add the following (the snippet is fenced with four backticks because it contains its own three-backtick `bash` block):

````markdown
Check that the code-to-doc pointers still lead somewhere — the `doc-ref <id> <path>` lines the
archivist leaves, resolved against `<!-- ref:<id> -->` markers in `docs/`:

```bash
python claude-house-rules/plugins/house-rules/scripts/docref.py check
```

`fix --write` repairs pointers whose doc moved, by id only; `new` prints an unused id. Also
available as `/house-rules:docref`. It is a command, not a hook, and `verify.py` runs it against
this repo's own files (excluding itself and `docref.py`, which hold example pointers on purpose).
````

`claude-house-rules/README.md`: after the harvest row's sentence about `/house-rules:harvest-scan`, this file has no separate commands list, so add one sentence to the same table row, before the closing `|`:

```
 The pointer that move leaves is `doc-ref <id> <path>`; `/house-rules:docref` (`scripts/docref.py`) checks that each one still resolves and repairs the ones whose doc has moved.
```

- [ ] **Step 4: Update the spec and the handoff plan**

In `docs/superpowers/specs/2026-09-20-pointer-integrity-design.md`:

- Replace the line beginning `- **Pointer scan scope.** Every tracked text file that is not under \`docs/\`.` with:

```
- **Pointer scan scope.** Every project file that is not under `docs/`. In a git work tree that
  means `git ls-files --cached --others --exclude-standard` (tracked, plus untracked and not
  ignored); otherwise a directory walk skipping `.git`, `node_modules`, `__pycache__`, `.venv`
  and `venv`. The output names which. Docs link to each other with ordinary links, not `doc-ref`.
```

- In the marker bullet, after `on the line directly under its heading.` add `The marker must be alone on its line, so a doc that quotes one inline does not register a fake marker.`
- Add an `--exclude GLOB` bullet to the `check` description: `**\`--exclude GLOB\`** (repeatable, on every subcommand) skips matching relative paths; the repo's own live check uses it for files that hold example pointers on purpose.`

In `docs/plans/2026-09-20-harvest-content-rules-and-pointer-integrity.md`, in the **Status** paragraph at the top, append: `Piece B (pointer integrity) is designed and built: see [the design spec](../superpowers/specs/2026-09-20-pointer-integrity-design.md) and [its implementation plan](2026-09-20-pointer-integrity-implementation.md). Pieces A and C are still open.`

- [ ] **Step 5: Verify everything, at real scale**

Run each and read the result.

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py" | Select-Object -Last 8
```

Expected: `RESULT: PASS - all N checks passed.` with no SKIP lines (this is a repo checkout).

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\tools\verify_tools.py" | Select-Object -Last 6
```

Expected: a PASS result line (this proves the tools suite is unaffected).

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\docref.py" check --root "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" --exclude "claude-house-rules/plugins/house-rules/scripts/verify.py" --exclude "claude-house-rules/plugins/house-rules/scripts/docref.py"
```

Expected: `docref: 0 pointers found: 0 ok, 0 stale, 0 dangling, 0 ambiguous`, a `via git` line, a nonzero legacy count, `docref: OK`. Record the legacy count: it sizes the migration pass the user asked for next.

Now the realistic-scale run. This is read-only (`check` never writes):

```powershell
python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\docref.py" check --root "C:\Users\aj\Desktop\GameDev\RockSkipping"
```

Expected: it finishes without error, prints `via git`, a plausible file count (RockSkipping has about 127 source files), `0 pointers found`, and a legacy count. Confirm the run did not take unreasonably long or descend into `Library/` (the file count would be in the tens of thousands if it did). If it errors or is slow, fix `docref.py` with a failing fixture test first, do not skip this step.

- [ ] **Step 6: Commit and report**

```powershell
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" add -A
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" status --short
git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" commit -m "docs: record pointer-integrity decision and bump plugin to 2.28.0" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Check `status --short` before committing: only the files listed in this plan (plus `docs/superpowers/plans` none) should appear. Then report to the user: the final `verify.py` RESULT line, the real `check` counts for this repo and for RockSkipping (including the legacy line counts), and that the migration pass is the next piece of work. Do not push, merge, or open a pull request.

---

## Self-review against the spec

- **Data model** (marker, pointer, ID grammar, states, split/merge/delete): Task 1 implements the grammar and the ok / stale / dangling / duplicate / malformed / unreferenced states (ambiguous is the pointer-side view of a duplicate); Task 2 implements stale repair and the refusal on duplicates; split and merge need no code, as the spec says, and are covered by the stale-path tests.
- **`check`, `fix`, `new`, exit codes, counts always printed, unreadable forces non-zero, legacy count:** Tasks 1 and 2.
- **`/house-rules:docref`:** Task 3.
- **Archivist, rules text, `hook.py` strings, drift-pinned:** Task 4, drift lists extended first.
- **`verify.py` fixtures, live check with SKIP outside a checkout:** Tasks 1-3.
- **Testing approach (test-first, CRLF, shared id, no-docs project, real-scale run on this repo and RockSkipping):** Tasks 1, 2 and 5.
- **Docs and housekeeping (Decisions, architecture, version bump):** Task 5.
- **Deviations found while planning, recorded in the spec by Task 5:** marker alone on its line; git-based file list with a walk fallback; `--exclude`.
- **Out of scope, not built:** no hook, no content classification, no drift detection, no migration of legacy prose pointers (the count from Step 5 scopes that follow-up).
- **Open risk, unverified:** the archivist's `${CLAUDE_PLUGIN_ROOT}` path assumes the variable is substituted inside an agent definition the way it is inside a command. Nothing here proves it. The archivist text carries a fallback (report it and leave the id to the caller), and the first real archivist run after this ships should confirm or refute it.
