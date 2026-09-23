#!/usr/bin/env python3
"""session_ledger_render.py — turns transcript records into the session-ledger markdown.

Split out of tools/session_ledger.py (docs/Decisions.md, 2026-09-23, doc-ref c67d) so hook.py's
verdict handler can render a subagent's transcript into docs/sessions/ from inside the plugin
cache, where tools/ does not exist - only the shipped plugin package does. tools/session_ledger.py
imports build_turns/render/is_github_write/GIT_MUTATING from here, so there is exactly one copy
of the rendering logic; its own CLI (argparse, file discovery, writing the file) stays in tools/.

STDLIB ONLY, matching hook.py and verify.py.
"""

import re

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
    exactly how an action becomes invisible. A transcript with no human-origin "user" record
    (a subagent transcript, for instance) produces zero turns - build_turns never guesses a
    boundary that is not actually there.
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
