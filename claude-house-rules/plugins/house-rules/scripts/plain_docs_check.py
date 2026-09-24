#!/usr/bin/env python3
"""plain_docs_check.py - checks the plain-English copies under docs/plain/ against the rules
the house-rules:plain-docs skill writes to.

    plain_docs_check.py [--root DIR] [FILE]
    plain_docs_check.py [--root DIR] --queue

Design: docs/plans/2026-09-24-plain-docs-skill.md
STDLIB ONLY, Python 3.8+, no state kept between runs.

Header format (first line of every plain copy, exactly):

    <!-- plain copy of: <source path, repo-relative, forward slashes> @ <40-hex git blob hash> -->

The hash is the source file's `git hash-object` blob hash at the time the plain copy was last
written. The checker recomputes the source's current blob hash the same way and compares; a
mismatch is reported as WARN (stale), never FAIL - the plan is explicit that a stale copy is a
warning, not a build-breaker.

With no FILE argument, every `.md` under `docs/plain/` (relative to --root) is checked. With a
FILE argument, only that one file is checked (it does not need to already sit under
docs/plain/). A repo with no docs/plain/ folder at all is not silently skipped: it is reported
in one line, and the run still exits 0, since there is nothing to check.

Exit 0 means no FAIL-level problem was found (warnings do not affect the exit code). Exit 1
means at least one FAIL was found. Exit 2 means the run itself could not proceed (bad --root, an
unreadable file passed directly, or an internal error) - never a silent 0.

--queue prints the project-wide work list instead: every eligible source (docs/systems/*.md
except README.md, then docs/README.md, docs/ProjectState.md, docs/Roadmap.md, in that order),
each with MISSING/STALE/CURRENT and its mirrored plain-copy path, a DEFERRED line for
docs/architecture.md if present, and an EXCLUDED summary naming what's left out and why. It is a
listing, not a check - it always exits 0.
"""

import argparse
import os
import re
import subprocess
import sys

# Small, editable list. Whole-word, case-insensitive. Add to this list as new jargon slips
# through; it is meant to be tuned, not exhaustive on day one.
BANNED_WORDS = [
    "payload",
    "stdin",
    "stdout",
    "dispatch",
    "handler",
    "idempotent",
    "shim",
    "argv",
    "callback",
    "boilerplate",
    "serialize",
    "deserialize",
]

HEADER_RE = re.compile(
    r"^<!--\s*plain copy of:\s*(?P<path>\S+)\s*@\s*(?P<hash>[0-9a-f]{40})\s*-->\s*$"
)
FULL_DOC_LINK_RE = re.compile(r"^Full technical doc:\s*\[[^\]]+\]\(([^)]+)\)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
DASH_RE = re.compile(r"[–—]")  # en dash, em dash
FILE_LINE_RE = re.compile(r"\b[\w./-]+\.\w+:\d+\b")
FILE_PATH_RE = re.compile(r"\b[\w-]+(?:/[\w.-]+)+\.[A-Za-z]{1,6}\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[A-Za-z0-9']+")
RELATED_ENTRY_RE = re.compile(
    r"\[([^\]]+\.md)\]\(([^)]+)\)\s*(\*\(no plain copy yet\)\*)?"
)

# The project-wide queue's source list and order, shared with the plain-docs skill's "all"/
# "stale" modes so the two never drift apart. docs/systems/*.md (except README.md, an index, not
# a system) sorted by name, then these three root docs in this fixed order, each only if present.
QUEUE_FIXED_SOURCES = ["docs/README.md", "docs/ProjectState.md", "docs/Roadmap.md"]
QUEUE_SYSTEMS_INDEX = "docs/systems/README.md"

# Shown as DEFERRED: eligible in principle, but the skill only takes it on once the others have
# proven useful; never queued automatically.
QUEUE_DEFERRED_SOURCE = "docs/architecture.md"

# Folders/files left out of the queue entirely, with the reason shown in the EXCLUDED summary.
QUEUE_EXCLUDED_GROUPS = [
    ("docs/Decisions.md", "history, would go stale as fast as it was written"),
    ("docs/plans/", "working notes, would go stale as fast as it was written"),
    ("docs/archive/", "history, would go stale as fast as it was written"),
    ("docs/sessions/", "per-session audit records, not documentation of the system"),
    ("docs/generated/", "generated output, not authored documentation"),
    ("docs/plain/", "the plain copies themselves"),
    ("docs/systems/README.md", "an index, not a system"),
]


def _norm(path):
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def find_root(explicit):
    if explicit:
        return os.path.abspath(explicit)
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if proc.returncode == 0:
            top = proc.stdout.decode("utf-8", "replace").strip()
            if top:
                return os.path.abspath(top)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return os.path.abspath(".")


def blob_hash(path):
    """git's blob hash for a file's current on-disk content, without needing it committed."""
    try:
        proc = subprocess.run(
            ["git", "hash-object", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def strip_link_urls(line):
    """Replace each markdown link's URL (not its visible text) with spaces, same length, so
    banned-word/dash/path checks never fire on a link target, only on prose."""
    def repl(m):
        text, url = m.group(1), m.group(2)
        return "[" + text + "](" + (" " * len(url)) + ")"
    return MD_LINK_RE.sub(repl, line)


def fenced_ranges(lines):
    """1-indexed (start, end) ranges of fenced code blocks (``` or ~~~), CommonMark-ish."""
    ranges = []
    open_fence = None
    start = 0
    for n, line in enumerate(lines, 1):
        m = FENCE_RE.match(line.rstrip("\n"))
        if m:
            run = m.group(1)
            if open_fence is None:
                open_fence = run[0]
                start = n
            elif run[0] == open_fence:
                ranges.append((start, n))
                open_fence = None
    if open_fence is not None:
        ranges.append((start, len(lines)))
    return ranges


def in_ranges(n, ranges):
    return any(s <= n <= e for s, e in ranges)


class Result:
    def __init__(self, path):
        self.path = path
        self.fails = []
        self.warns = []
        self.infos = []

    def fail(self, line, msg):
        self.fails.append((line, msg))

    def warn(self, line, msg):
        self.warns.append((line, msg))

    def info(self, line, msg):
        self.infos.append((line, msg))


def check_file(root, rel_path, todo_no_plain, todo_needs_doc):
    """rel_path is repo-relative, forward slashes, under root."""
    full = os.path.join(root, rel_path)
    res = Result(rel_path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        res.fail(0, "could not read this file: %s" % e)
        return res
    except UnicodeDecodeError:
        res.fail(0, "not valid UTF-8")
        return res

    lines = text.split("\n")
    fences = fenced_ranges(lines)
    for start, end in fences:
        res.fail(start, "a fenced code block (lines %d-%d). No code detail; the full-doc link covers that." % (start, end))

    # --- header ---
    header_hash = None
    source_rel = None
    if not lines or not HEADER_RE.match(lines[0]):
        res.fail(1, "missing or malformed header. First line must be exactly "
                     "'<!-- plain copy of: <source path> @ <40-hex blob hash> -->'")
    else:
        m = HEADER_RE.match(lines[0])
        source_rel = _norm(m.group("path"))
        header_hash = m.group("hash")
        source_full = os.path.join(root, source_rel)
        if not os.path.isfile(source_full):
            res.fail(1, "source file %r does not exist" % source_rel)
        else:
            current_hash = blob_hash(source_full)
            if current_hash and current_hash != header_hash:
                res.warn(1, "stale: source %r has changed since this copy was written "
                             "(header says %s, source is now %s)" % (source_rel, header_hash, current_hash))

    # --- full-doc link under the title ---
    has_full_link = False
    for n, line in enumerate(lines, 1):
        if in_ranges(n, fences):
            continue
        if FULL_DOC_LINK_RE.match(line.strip()):
            has_full_link = True
            break
    if not has_full_link:
        res.fail(0, "missing the 'Full technical doc: [...](...)' line under the title")

    # --- word count vs source ---
    if source_rel:
        source_full = os.path.join(root, source_rel)
        if os.path.isfile(source_full):
            try:
                with open(source_full, "r", encoding="utf-8") as f:
                    source_text = f.read()
                source_words = len(WORD_RE.findall(source_text))
                body_text = "\n".join(lines[1:])  # exclude the header comment line
                body_words = len(WORD_RE.findall(body_text))
                if source_words > 0:
                    ratio = body_words / source_words
                    if ratio > 1.0 / 3:
                        res.fail(0, "word count %d is over a third of the source's %d (%.0f%%)"
                                     % (body_words, source_words, ratio * 100))
                    elif ratio > 1.0 / 4:
                        res.warn(0, "word count %d is over a quarter of the source's %d (%.0f%%); "
                                     "aim for a quarter unless the system is too dense" % (body_words, source_words, ratio * 100))
            except (OSError, UnicodeDecodeError) as e:
                res.warn(0, "could not read source to compare word counts: %s" % e)

    # --- per-line prose checks (dashes, banned words, file:line, file paths) ---
    for n, raw_line in enumerate(lines, 1):
        if n == 1 or in_ranges(n, fences):
            continue
        prose = strip_link_urls(raw_line)
        if DASH_RE.search(prose):
            res.fail(n, "contains an em dash or en dash; use a full stop, comma or colon instead")
        for word in BANNED_WORDS:
            if re.search(r"\b%s\b" % re.escape(word), prose, re.IGNORECASE):
                res.fail(n, "uses the banned word %r" % word)
        for fm in FILE_LINE_RE.finditer(prose):
            res.fail(n, "a file:line reference in prose: %r" % fm.group(0))
        for pm in FILE_PATH_RE.finditer(prose):
            res.fail(n, "a file path in prose: %r (link targets are fine; this is outside one)" % pm.group(0))

    # --- links: broken relative links, and related-section rules ---
    for n, raw_line in enumerate(lines, 1):
        if in_ranges(n, fences):
            continue
        for lm in MD_LINK_RE.finditer(raw_line):
            url = lm.group(2)
            if "://" in url or url.startswith("#") or url.startswith("mailto:"):
                continue
            target = url.split("#", 1)[0]
            if not target:
                continue
            target_full = os.path.normpath(os.path.join(os.path.dirname(full), target))
            if not os.path.isfile(target_full):
                res.fail(n, "broken relative link: %r does not resolve to a file" % url)

    # --- Related section: no-plain-copy-yet / needs-a-doc bookkeeping, and the fail rule ---
    in_related = False
    for n, raw_line in enumerate(lines, 1):
        stripped = raw_line.strip()
        if stripped.startswith("**Related"):
            in_related = True
            continue
        if in_related and stripped.startswith("**") and not stripped.startswith("**Related"):
            in_related = False
        if not in_related:
            continue
        if "*(needs a doc)*" in raw_line:
            todo_needs_doc.append((rel_path, n, raw_line.strip()))
            continue
        for rm in RELATED_ENTRY_RE.finditer(raw_line):
            target_path, marked_no_plain = rm.group(2), rm.group(3)
            target = target_path.split("#", 1)[0]
            if "://" in target:
                continue
            target_full = os.path.normpath(os.path.join(os.path.dirname(full), target))
            target_rel = _norm(os.path.relpath(target_full, root))
            if marked_no_plain:
                todo_no_plain.append((rel_path, n, target_rel))
                # if a plain copy now exists for this technical doc, the pointer is stale -> FAIL
                if "/systems/" in target_rel or target_rel.startswith("docs/") and not target_rel.startswith("docs/plain/"):
                    plain_equivalent = _plain_equivalent(root, target_rel)
                    if plain_equivalent and os.path.isfile(os.path.join(root, plain_equivalent)):
                        res.fail(n, "related link points at %r marked '(no plain copy yet)', "
                                     "but a plain copy now exists at %r - upgrade the pointer"
                                     % (target_rel, plain_equivalent))
            else:
                # unmarked link to a technical (non-plain) doc: only OK if no plain copy exists
                if target_rel.startswith("docs/") and not target_rel.startswith("docs/plain/") and target_rel.endswith(".md"):
                    plain_equivalent = _plain_equivalent(root, target_rel)
                    if plain_equivalent and os.path.isfile(os.path.join(root, plain_equivalent)):
                        res.fail(n, "related link to %r is unmarked, but that doc already has a "
                                     "plain copy at %r - link to the plain copy instead"
                                     % (target_rel, plain_equivalent))

    # --- sentence length: info only ---
    prose_lines = [strip_link_urls(l) for i, l in enumerate(lines, 1) if i > 1 and not in_ranges(i, fences)]
    prose_text = " ".join(l for l in prose_lines if l.strip() and not l.strip().startswith("<!--"))
    sentences = [s for s in SENTENCE_SPLIT_RE.split(prose_text) if s.strip()]
    if sentences:
        total_words = sum(len(WORD_RE.findall(s)) for s in sentences)
        avg = total_words / len(sentences)
        res.info(0, "average sentence length: %.1f words over %d sentences" % (avg, len(sentences)))

    return res


def _plain_equivalent(root, technical_rel):
    """docs/systems/x.md -> docs/plain/systems/x.md, else None if it's not under docs/."""
    technical_rel = _norm(technical_rel)
    if not technical_rel.startswith("docs/"):
        return None
    rest = technical_rel[len("docs/"):]
    if rest.startswith("plain/"):
        return None
    return "docs/plain/" + rest


def find_plain_files(root):
    plain_dir = os.path.join(root, "docs", "plain")
    if not os.path.isdir(plain_dir):
        return None
    found = []
    for dirpath, dirnames, filenames in os.walk(plain_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in (".git",))
        for name in sorted(filenames):
            if name.endswith(".md"):
                full = os.path.join(dirpath, name)
                found.append(_norm(os.path.relpath(full, root)))
    return sorted(found)


def build_queue(root):
    """The project-wide list of eligible sources, in fixed order, each with its status
    (MISSING / STALE / CURRENT) and its mirrored plain-copy path. Returns
    (entries, deferred_present, excluded_lines, unlisted_md) where entries is a list of
    (source_rel, status, plain_rel) and unlisted_md is the sorted list of docs/*.md files not in
    the eligible list and not one of the named excluded files."""
    docs_dir = os.path.join(root, "docs")
    if not os.path.isdir(docs_dir):
        return None

    sources = []
    systems_dir = os.path.join(docs_dir, "systems")
    if os.path.isdir(systems_dir):
        for name in sorted(os.listdir(systems_dir)):
            if not name.endswith(".md") or name == "README.md":
                continue
            sources.append(_norm(os.path.join("docs", "systems", name)))
    for rel in QUEUE_FIXED_SOURCES:
        if os.path.isfile(os.path.join(root, rel)):
            sources.append(rel)

    entries = []
    for source_rel in sources:
        plain_rel = _plain_equivalent(root, source_rel)
        plain_full = os.path.join(root, plain_rel)
        if not os.path.isfile(plain_full):
            status = "MISSING"
        else:
            current_hash = blob_hash(os.path.join(root, source_rel))
            header_hash = None
            try:
                with open(plain_full, "r", encoding="utf-8") as f:
                    first_line = f.readline()
                m = HEADER_RE.match(first_line.rstrip("\n"))
                if m:
                    header_hash = m.group("hash")
            except OSError:
                pass
            if header_hash is None or (current_hash and current_hash != header_hash):
                status = "STALE"
            else:
                status = "CURRENT"
        entries.append((source_rel, status, plain_rel))

    deferred_present = os.path.isfile(os.path.join(root, QUEUE_DEFERRED_SOURCE))

    # docs/*.md at the top level, not README/ProjectState/Roadmap, not Decisions.md, not
    # architecture.md (named separately as DEFERRED) - named explicitly so nothing is silently
    # skipped.
    named_elsewhere = set(QUEUE_FIXED_SOURCES) | {"docs/Decisions.md", QUEUE_DEFERRED_SOURCE}
    unlisted_md = []
    for name in sorted(os.listdir(docs_dir)):
        full = os.path.join(docs_dir, name)
        if not os.path.isfile(full) or not name.endswith(".md"):
            continue
        rel = _norm(os.path.join("docs", name))
        if rel in named_elsewhere:
            continue
        unlisted_md.append(rel)

    return entries, deferred_present, unlisted_md


def print_queue(root):
    result = build_queue(root)
    if result is None:
        print("plain_docs_check: no docs/ folder under %s - nothing to queue" % root)
        return 0

    entries, deferred_present, unlisted_md = result

    missing = stale = current = 0
    for source_rel, status, plain_rel in entries:
        print("%s  %s  %s" % (source_rel, status, plain_rel))
        if status == "MISSING":
            missing += 1
        elif status == "STALE":
            stale += 1
        else:
            current += 1

    deferred = 0
    if deferred_present:
        print("%s  DEFERRED  done only once the others have proven useful" % QUEUE_DEFERRED_SOURCE)
        deferred = 1

    excluded_names = [group for group, _reason in QUEUE_EXCLUDED_GROUPS]
    print("EXCLUDED: %s" % ", ".join(excluded_names)
          + (" - and %s (not in the eligible list)" % ", ".join(unlisted_md) if unlisted_md else ""))
    for group, reason in QUEUE_EXCLUDED_GROUPS:
        print("  %s: %s" % (group, reason))
    if unlisted_md:
        print("  any other docs/*.md not in the eligible list: %s" % ", ".join(unlisted_md))

    print("plain_docs_check: queue: %d missing, %d stale, %d current, %d deferred"
          % (missing, stale, current, deferred))
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="plain_docs_check.py",
        description="Check plain-English doc copies under docs/plain/ against the plain-docs rules.",
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--queue", action="store_true",
                         help="print the project-wide work list (MISSING/STALE/CURRENT/DEFERRED/"
                              "EXCLUDED) instead of checking anything; always exits 0")
    parser.add_argument("file", nargs="?", default=None,
                         help="check only this one file, instead of every .md under docs/plain/")
    args = parser.parse_args(argv)

    try:
        root = find_root(args.root)
        if not os.path.isdir(root):
            print("plain_docs_check: --root %s is not a directory" % root, file=sys.stderr)
            return 2

        if args.queue:
            return print_queue(root)

        if args.file:
            file_full = os.path.abspath(args.file)
            if not os.path.isfile(file_full):
                print("plain_docs_check: %s is not a file" % args.file, file=sys.stderr)
                return 2
            targets = [_norm(os.path.relpath(file_full, root))]
        else:
            targets = find_plain_files(root)
            if targets is None:
                print("plain_docs_check: no docs/plain/ folder under %s - nothing to check" % root)
                return 0
            if not targets:
                print("plain_docs_check: docs/plain/ exists under %s but holds no .md files - "
                      "nothing to check" % root)
                return 0

        any_fail = False
        todo_no_plain = []
        todo_needs_doc = []
        results = []
        for rel in targets:
            res = check_file(root, rel, todo_no_plain, todo_needs_doc)
            results.append(res)
            if res.fails:
                any_fail = True

        for res in results:
            for n, msg in sorted(res.fails):
                where = "%s:%d" % (res.path, n) if n else res.path
                print("%s  FAIL  %s" % (where, msg))
            for n, msg in sorted(res.warns):
                where = "%s:%d" % (res.path, n) if n else res.path
                print("%s  WARN  %s" % (where, msg))
            for n, msg in sorted(res.infos):
                where = "%s:%d" % (res.path, n) if n else res.path
                print("%s  INFO  %s" % (where, msg))

        total_fails = sum(len(r.fails) for r in results)
        total_warns = sum(len(r.warns) for r in results)
        print("plain_docs_check: checked %d file(s): %d fail, %d warn"
              % (len(results), total_fails, total_warns))

        if todo_no_plain:
            print("plain_docs_check: to-do, plain copies not yet written (%d):" % len(todo_no_plain))
            for rel_path, n, target in sorted(set((t[0], t[1], t[2]) for t in todo_no_plain)):
                print("  %s:%d -> %s" % (rel_path, n, target))
        if todo_needs_doc:
            print("plain_docs_check: to-do, systems that need a technical doc first (%d):" % len(todo_needs_doc))
            for rel_path, n, line in todo_needs_doc:
                print("  %s:%d  %s" % (rel_path, n, line))

        print("plain_docs_check: OK" if not any_fail else "plain_docs_check: PROBLEMS")
        return 1 if any_fail else 0
    except Exception as e:  # last resort: say what broke, never a bare traceback or a silent 0
        print("plain_docs_check: internal error: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
