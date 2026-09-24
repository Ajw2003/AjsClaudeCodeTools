#!/usr/bin/env python3
"""session_ledger.py — turns a session transcript into a record a person can audit.

Claude Code already writes a per-session transcript. It is complete and it is unreadable: this
repo's own is 3.2 MB of JSON Lines, so in practice nobody opens it, and an unread record is not a
record. This distils one into `docs/sessions/`, committed, so "what actually happened, and what
prompted it" is answerable from the repo months later.

It reads and never writes to the transcript, adds nothing to any hook, and keeps no state. That
is deliberate: instrumenting the hooks to log their own decisions would duplicate a record that
already exists, put file I/O on guard's per-shell-command path, and reverse the "no hook keeps
state" constraint CLAUDE.md calls load-bearing.

WHY IT EXISTS. On 2026-09-09 a Stop hook reported an unpushed commit. Hook feedback continues the
turn, so the push and a pull-request update happened AFTER the visible reply had been written.
Two turns later the assistant stated it had not pushed, while the commit sat on the remote. The
transcript held the answer the whole time. Nothing was missing except a way to read it - so the
"turn continuations" section below is the one this tool exists for.

The actual rendering (build_turns/render and the constants they use) lives in
claude-house-rules/plugins/house-rules/scripts/session_ledger_render.py, not here (docs/6-decisions/Decisions.md,
2026-09-23, doc-ref c67d): hook.py's verdict handler needs the same renderer for a subagent
transcript, and it runs from inside the installed plugin cache, where this tools/ directory does
not exist. This file is the CLI: find a transcript, load it, call the shared renderer, write the
file.

STDLIB ONLY, matching hook.py and verify.py.
"""

import argparse
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "claude-house-rules", "plugins", "house-rules", "scripts",
))
from session_ledger_render import (  # noqa: E402
    GIT_MUTATING, GITHUB_WRITES, HOOK_NAME, STOP_FEEDBACK, WRITE_TOOLS,
    build_turns, is_github_write, one_line, render, text_of,
)

__all__ = [
    "GIT_MUTATING", "GITHUB_WRITES", "HOOK_NAME", "STOP_FEEDBACK", "WRITE_TOOLS",
    "build_turns", "is_github_write", "one_line", "render", "text_of",
    "die", "find_transcript", "load", "main",
]


def die(message):
    """Fail loudly. Nothing here is worth failing silently over."""
    sys.stderr.write("session_ledger: %s\n" % message)
    sys.exit(1)


def find_transcript(session_id=None):
    """Locate a transcript. Hooks get transcript_path in their payload; run by hand we search."""
    root = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(root):
        die("no transcript directory at %s - nothing to read." % root)
    hits = glob.glob(os.path.join(root, "*", "*.jsonl"))
    hits = [h for h in hits if os.path.sep + "subagents" + os.path.sep not in h]
    if session_id:
        hits = [h for h in hits if session_id in os.path.basename(h)]
        if not hits:
            die("no transcript found for session %r under %s" % (session_id, root))
    if not hits:
        die("no session transcripts found under %s" % root)
    return max(hits, key=os.path.getmtime)


def load(path):
    """Read the transcript, skipping records that will not parse rather than dying on them."""
    records, bad = [], 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    bad += 1
    except OSError as exc:
        die("could not read %s: %s" % (path, exc))
    if not records:
        die("%s parsed to zero records - the format may have changed." % path)
    return records, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transcript", help="path to a session .jsonl (default: most recent)")
    ap.add_argument("--session", help="session id to find a transcript for")
    ap.add_argument("--out", default=None, help="output directory (default: docs/sessions)")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing a file")
    args = ap.parse_args(argv)

    path = args.transcript or find_transcript(args.session)
    if not os.path.isfile(path):
        die("no such transcript: %s" % path)
    records, bad = load(path)
    session_id = os.path.splitext(os.path.basename(path))[0]
    turns = build_turns(records)
    body = render(turns, path, session_id, bad)

    if args.stdout:
        sys.stdout.write(body)
        return 0

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = args.out or os.path.join(here, "docs", "sessions")
    try:
        os.makedirs(outdir, exist_ok=True)
    except OSError as exc:
        die("could not create %s: %s" % (outdir, exc))
    stamp = datetime.date.today().isoformat()
    dest = os.path.join(outdir, "%s-%s.md" % (stamp, session_id))
    try:
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    except OSError as exc:
        die("could not write %s: %s" % (dest, exc))

    print("wrote %s" % dest)
    print("  %d turns, %d injections, %d actions after a visible reply" % (
        len(turns),
        sum(len(t["injections"]) for t in turns),
        sum(len(t["continuation"]) for t in turns),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
