#!/usr/bin/env python3
"""harvest_scan.py — run the comment-harvest detector over a whole project by hand.

The `harvest` hook only ever looks at text written in the current turn (PostToolUse on
Write/Edit) - by design, so it never nags about an essay that predates the session. That is
also exactly why it cannot answer "does this project already have any" - nothing ever hands it
a file that was not just touched. This script is the manual, project-wide answer: point it at a
directory and it walks every source file, running the same detection code the hook uses
(`hook._harvest_blocks`), so the two can never disagree about what counts as an essay.

Usage:
    python "$CLAUDE_PLUGIN_ROOT/scripts/harvest_scan.py" [path] [--min-lines N] [--min-chars N] [--verbose]

    path          Directory to scan. Defaults to the current directory.
    --min-lines   Overrides HOUSE_RULES_HARVEST_MIN_LINES / the built-in default.
    --min-chars   Overrides HOUSE_RULES_HARVEST_MIN_CHARS / the built-in default.
    --verbose     Also print files where nothing qualified, and why the closest run missed.

Exits 0 whether or not it finds anything - this is a report, not a gate, same as the hook it
shares code with. Exits 1 only when the scan itself could not run (a bad path).
"""

import argparse
import os
import sys
import time as _time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook  # noqa: E402 - path must be set up before this import

# Generated/vendored/dependency trees a source-extension glob would otherwise walk into.
# Unity-specific (Library, Temp, Obj, Logs) sits next to the general-purpose ones because this
# is the tree the handler most commonly runs against in practice.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "Build", "Builds", "bin", "obj", "Library", "Temp", "Logs",
}


def _iter_source_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if hook._HARVEST_EXT_RE.search(name):
                yield os.path.join(dirpath, name)


def main(argv):
    parser = argparse.ArgumentParser(
        description="Scan a project for long-form comments the harvest hook would flag."
    )
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--min-lines", type=int, default=None)
    parser.add_argument("--min-chars", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv[1:])

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("harvest_scan: %r is not a directory" % args.path, file=sys.stderr)
        return 1

    problems = []
    min_lines = args.min_lines
    if min_lines is None:
        min_lines = hook._harvest_threshold(
            "HOUSE_RULES_HARVEST_MIN_LINES", hook.HARVEST_MIN_LINES, problems
        )
    min_chars = args.min_chars
    if min_chars is None:
        min_chars = hook._harvest_threshold(
            "HOUSE_RULES_HARVEST_MIN_CHARS", hook.HARVEST_MIN_CHARS, problems
        )
    for p in problems:
        print("harvest_scan: %s - using the default" % p, file=sys.stderr)

    total_files = 0
    total_blocks = 0
    flagged_files = 0
    for path in sorted(_iter_source_files(root)):
        total_files += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            print("harvest_scan: could not read %s (%s)" % (path, exc), file=sys.stderr)
            continue

        rel = os.path.relpath(path, root)
        deadline = _time.time() + hook.HARVEST_BUDGET_SECONDS
        blocks, misses, timed_out = hook._harvest_blocks(
            text, min_lines, min_chars, deadline, args.verbose, full_file=True
        )
        if timed_out:
            print(
                "%s: scan abandoned past its %gs budget (%d bytes)"
                % (rel, hook.HARVEST_BUDGET_SECONDS, len(text))
            )
            continue
        if blocks:
            flagged_files += 1
            total_blocks += len(blocks)
            for start, end, n_lines, n_chars in blocks:
                print("%s:%d-%d  %dL/%dc" % (rel, start, end, n_lines, n_chars))
        elif args.verbose and misses:
            longest = max(misses, key=lambda m: (m[2], m[3]))
            print(
                "%s: no block - longest run %dL/%dc (%s)"
                % (rel, longest[2], longest[3], longest[4])
            )

    print("---")
    print(
        "%d source file%s scanned under %s, %d block%s in %d file%s at %d lines / %d chars."
        % (
            total_files,
            "" if total_files == 1 else "s",
            root,
            total_blocks,
            "" if total_blocks == 1 else "s",
            flagged_files,
            "" if flagged_files == 1 else "s",
            min_lines,
            min_chars,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
