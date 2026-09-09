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

STDLIB ONLY, matching hook.py and verify.py.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys

# Mutating git verbs, the same family guard prompts on. A ledger that hid these would be missing
# the actions most worth auditing.
GIT_MUTATING = re.compile(
    r"\bgit\s+(-[^\s]+\s+)*(add|commit|push|checkout|switch|reset|revert|stash|rm|mv|branch"
    r"|merge|rebase|clean|tag|cherry-pick)\b",
    re.IGNORECASE,
)
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")

STOP_FEEDBACK = re.compile(r"^\s*Stop hook feedback", re.IGNORECASE)
HOOK_NAME = re.compile(r"\[([^\]]+)\]")

# An explicit list of GitHub verbs that change something. The first cut used "any name not
# ending in _read", which labelled actions_list - a read - as repo-mutating. A record that
# mislabels reads as writes is worse than no record, because it is trusted.
GITHUB_WRITES = (
    "create_", "update_", "add_", "delete_", "merge_", "push_", "fork_", "enable_",
    "disable_", "request_", "resolve_", "unresolve_", "run_", "sub_issue_write",
    "issue_write", "pull_request_review_write", "actions_run_trigger",
)


def is_github_write(name):
    tail = name.replace("mcp__github__", "")
    return any(tail.startswith(p) or tail == p for p in GITHUB_WRITES)


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


def one_line(text, limit=100):
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def text_of(message):
    """The human-readable text of a message, whatever shape its content is in."""
    content = (message or {}).get("content")
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return " ".join(parts)


def build_turns(records):
    """Split the session at each genuine human prompt, and mark what happened inside each turn.

    A turn continuation is the span after a Stop hook fires and before the next human prompt.
    Everything the assistant does there happens past the reply the user actually read, which is
    exactly how an action becomes invisible.
    """
    turns = []
    current = None

    def new_turn(prompt, ts):
        return {
            "prompt": prompt,
            "time": ts,
            "injections": [],
            "notifications": [],
            "commands": [],
            "writes": [],
            "continuation": [],
            "stop_hooks": [],
            "in_continuation": False,
        }

    for r in records:
        kind = r.get("type")
        ts = r.get("timestamp", "")

        if kind == "user":
            origin = r.get("origin") or {}
            if origin.get("kind") == "human":
                if current:
                    turns.append(current)
                current = new_turn(one_line(text_of(r.get("message")), 160), ts)
                continue
            if origin.get("kind") and current:
                current.setdefault("notifications", []).append(
                    (origin.get("kind"), one_line(text_of(r.get("message")), 110), ts)
                )
                continue
            # Stop hook feedback arrives as an ordinary user record with no origin, and it is
            # what CONTINUES the turn - so this, not the stop_hook_summary, is where a
            # continuation begins. The summary record is written after the work it summarises,
            # so keying on it opened the window too late and missed every action inside it.
            # Found by running this against the very incident it was built for.
            if current is not None:
                body = text_of(r.get("message"))
                if STOP_FEEDBACK.search(body or ""):
                    m = HOOK_NAME.search(body)
                    current["stop_hooks"].append((m.group(1) if m else "a Stop hook", ts))
                    current["in_continuation"] = True
            continue

        if current is None:
            continue

        if kind == "attachment":
            a = r.get("attachment") or {}
            if a.get("type") == "hook_additional_context":
                current["injections"].append(
                    (a.get("hookEvent") or a.get("hookName") or "?",
                     one_line(a.get("content"), 110), ts)
                )
            continue

        if kind == "system" and r.get("subtype") == "stop_hook_summary":
            # Supplementary only: this is written after the turn's work, so it records which
            # hooks ran, not when the continuation started.
            continue

        if kind == "assistant":
            for block in (r.get("message") or {}).get("content") or []:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                name = block.get("name") or "?"
                inp = block.get("input") or {}
                if name == "Bash":
                    cmd = inp.get("command") or ""
                    entry = ("Bash", one_line(cmd, 90), ts, bool(GIT_MUTATING.search(cmd)))
                    current["commands"].append(entry)
                    if current["in_continuation"]:
                        current["continuation"].append(entry)
                elif name in WRITE_TOOLS:
                    entry = (name, one_line(inp.get("file_path"), 70), ts, False)
                    current["writes"].append(entry)
                    if current["in_continuation"]:
                        current["continuation"].append(entry)
                elif name.startswith("mcp__github__") and is_github_write(name):
                    entry = (name.replace("mcp__github__", "github:"), "", ts, True)
                    current["commands"].append(entry)
                    if current["in_continuation"]:
                        current["continuation"].append(entry)

    if current:
        turns.append(current)
    return turns


def render(turns, path, session_id, bad_lines):
    out = []
    A = out.append
    A("# Session ledger — `%s`" % session_id)
    A("")
    A("Generated by `tools/session_ledger.py` from the session transcript. This is the **raw**")
    A("record: mechanical, complete, and the source of truth. Any readable summary alongside it")
    A("is commentary and can be checked against this.")
    A("")
    A("| | |")
    A("|---|---|")
    A("| Transcript | `%s` |" % path)
    A("| Turns (human prompts) | %d |" % len(turns))
    A("| Hook injections | %d |" % sum(len(t["injections"]) for t in turns))
    A("| Notifications | %d |" % sum(len(t["notifications"]) for t in turns))
    A("| Shell commands | %d |" % sum(len(t["commands"]) for t in turns))
    A("| Repo-mutating commands | %d |" % sum(
        1 for t in turns for c in t["commands"] if c[3]))
    A("| **Actions in turn continuations** | **%d** |" % sum(
        len(t["continuation"]) for t in turns))
    if bad_lines:
        A("| Unparseable transcript lines | %d (skipped) |" % bad_lines)
    A("")

    cont = [(i, t) for i, t in enumerate(turns, 1) if t["continuation"]]
    A("## Actions taken after the visible reply")
    A("")
    A("A Stop hook continues the turn, so anything here happened **after** the reply the user")
    A("read. This is the section this ledger exists for: it is where an action becomes invisible.")
    A("")
    if not cont:
        A("None in this session.")
    else:
        A("| Turn | Prompted by | Action | Time |")
        A("|---|---|---|---|")
        for i, t in cont:
            trigger = t["stop_hooks"][0][0] if t["stop_hooks"] else "a Stop hook"
            for name, detail, ts, mutating in t["continuation"]:
                mark = " **(repo-mutating)**" if mutating else ""
                A("| %d | `%s` | `%s` %s%s | %s |" % (
                    i, trigger, name, detail, mark, ts[11:19] if len(ts) > 19 else ts))
    A("")

    A("## Every turn")
    A("")
    for i, t in enumerate(turns, 1):
        A("### Turn %d — %s" % (i, t["time"][:19].replace("T", " ")))
        A("")
        A("**Asked:** %s" % (t["prompt"] or "*(no text)*"))
        A("")
        rows = []
        for ev, content, ts in t["injections"]:
            rows.append(("injection", ev, content))
        for kind, content, ts in t["notifications"]:
            rows.append(("notification", kind, content))
        for cmd, ts in t["stop_hooks"]:
            rows.append(("stop hook", cmd, "turn continued past the visible reply"))
        for name, detail, ts, mutating in t["commands"]:
            rows.append(("command" + (" (mutating)" if mutating else ""), name, detail))
        for name, detail, ts, _ in t["writes"]:
            rows.append(("write", name, detail))
        if not rows:
            A("*Nothing recorded.*")
        else:
            A("| What | Source | Detail |")
            A("|---|---|---|")
            for what, src, detail in rows:
                A("| %s | `%s` | %s |" % (what, src, detail.replace("|", "\\|")))
        A("")
    return "\n".join(out) + "\n"


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
