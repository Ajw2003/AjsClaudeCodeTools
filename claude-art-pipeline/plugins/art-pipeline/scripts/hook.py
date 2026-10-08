#!/usr/bin/env python3
"""hook.py - art-pipeline hook handlers (stdlib only). Gate logic lives in artlib.py.

  start (SessionStart)  fails LOUD: on an internal error says so in a systemMessage, exit 0.
                        Silent only when it looked and there is nothing to do (no git repo,
                        no art in the repo).
  seen  (PostToolUse/Read)  never blocks, never non-zero. A ledger it cannot write is announced
                        in a systemMessage.
  gate  (Stop)          fails OPEN, LOUD: any internal error -> systemMessage naming it, no
                        block. Blocks (decision:block) only on a definite unmet model, and
                        releases with a loud systemMessage on the 3rd identical block.
                        Off switch: ART_PIPELINE=off (announced in a systemMessage).

Ledger: <git-dir>/art-pipeline/<session_id>.json, so it is never committed.
JSON is emitted with separators=(",", ":"), like house-rules.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


def payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace").strip()
        return json.loads(raw) if raw else {}
    except Exception as exc:
        sys.stderr.write("art-pipeline: unreadable hook payload: %s\n" % exc)
        return {}


def where(p):
    return p.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def event_start():
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg = artlib.load_config(root)
    if not artlib.tracked_has_art(root, cfg):
        return 0
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    artlib.save_ledger(path, {"start": artlib.head_sha(root), "seen": [], "blocks": {}})
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
          "art-pipeline: any model you change this session must have a review sheet you opened "
          "and a review record before you stop; see the art-pipeline skill."}})
    return 0


def event_seen():
    p = payload()
    fp = (p.get("tool_input") or {}).get("file_path")
    if not isinstance(fp, str) or not fp.lower().endswith(artlib.IMG_EXT):
        return 0
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    path = artlib.ledger_path(info[1], p.get("session_id"))
    led = artlib.load_ledger(path)
    base = p.get("cwd") or os.getcwd()
    led["seen"].append({"path": os.path.normpath(os.path.join(base, fp)), "t": artlib.now()})
    artlib.save_ledger(path, led)
    return 0


def event_gate():
    if os.environ.get("ART_PIPELINE", "").strip().lower() == "off":
        emit({"systemMessage": "art-pipeline: gate is OFF (ART_PIPELINE=off); models were not checked."})
        return 0
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg, led, res, bad = artlib.evaluate(root, gitdir, p.get("session_id"))
    unmet = [(m, pr) for m, st, pr in res if st == "fail"]
    waived = [m for m, st, _ in res if st == "waived"]
    notes = ["art-pipeline: " + pr[0] for m, st, pr in res if st == "timeout"]
    for m, st, pr in res:
        if st == "report":
            notes.append("art-pipeline: " + "; ".join(pr))
    if waived:
        notes.append("art-pipeline: WAIVED review for: " + ", ".join(waived))
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    if not unmet:
        if led["blocks"]:
            led["blocks"] = {}
            artlib.save_ledger(path, led)
        if bad:
            notes.append("art-pipeline: unreadable review records ignored: " + "; ".join(bad))
        if notes:
            emit({"systemMessage": " | ".join(notes)})
        return 0
    key = "|".join(sorted(m for m, _ in unmet))
    n = led["blocks"].get(key, 0) + 1
    led["blocks"] = {key: n}
    artlib.save_ledger(path, led)
    if n >= artlib.MAX_BLOCKS:
        notes.append("art-pipeline: stopping with UNREVIEWED models: " + ", ".join(m for m, _ in unmet)
                     + " (blocked %d times with the same set; releasing the stop)" % (n - 1))
        emit({"systemMessage": " | ".join(notes)})
        return 0
    lines = ["art-pipeline: these models changed this session and are not reviewed:"]
    for m, pr in unmet:
        lines.append("- %s" % m)
        lines += ["    * " + x for x in pr]
    if bad:
        lines.append("Unreadable review records: " + "; ".join(bad))
    if any(m != "doc_check" and not m.startswith("asset:") for m, _ in unmet):
        lines.append("To fix models: " + artlib.fix_hint(cfg))
    lines += notes
    emit({"decision": "block", "reason": "\n".join(lines)})
    return 0


EVENTS = {"start": event_start, "seen": event_seen, "gate": event_gate}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    h = EVENTS.get(event)
    if h is None:
        return 0
    try:
        return h()
    except BaseException as exc:
        detail = "%s: %s" % (type(exc).__name__, exc)
        extra = {"start": "The review gate may not be armed.", "seen": "A viewed sheet may not have been recorded.",
                 "gate": "The gate did NOT run; changed models are UNREVIEWED (failing open)."}[event]
        emit({"systemMessage": "art-pipeline plugin: the %s hook hit an internal error (%s). %s" % (event, detail, extra)})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
