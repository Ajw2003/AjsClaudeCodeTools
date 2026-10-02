#!/usr/bin/env python3
"""stallcheck - the cheapest reliable test for "has this background work stalled?".

No model call, no parsing: it compares the age of the newest write to a file the work keeps
appending to against a threshold (default 300 s). A subagent appends a record to its transcript
for every message and tool call, so a transcript that has not changed for 5 minutes means no
progress. A background command appends to its output file the same way.

  python stallcheck.py --session ID --agent ID   only that session's / that agent's transcript
                                            (what the hook suggests; --session and --agent repeat)
  python stallcheck.py                      every subagent transcript of EVERY session touched in the
                                            last 3 hours (says so in a header line; noisy)
  python stallcheck.py --file OUT [--file ...]   also watch a background command's output file
  python stallcheck.py --watch              loop every 30 s; print only when something stalls or
                                            finishes; exit when nothing is left running
  python stallcheck.py --threshold 600      stall after 10 minutes instead of 5

Output is one line per item: `ok`, `STALLED`, or `finished`. Exit 0 when nothing is stalled,
1 when something is, 2 when nothing could be found to check (said in words, never silent).
A finished subagent is one whose transcript holds a SubagentStop record in its last 20 KB.
A long model call or a usage-limit wait writes nothing either, so it reads as STALLED: that is
the definition, not a bug - the answer to a STALLED line is to look, not to assume it died.
"""
import argparse
import glob
import os
import sys
import time

DEFAULT_THRESHOLD = 300
POLL_SECONDS = 30
LOOKBACK_SECONDS = 3 * 3600
TAIL_BYTES = 20000


def _age(path, now):
    return now - os.path.getmtime(path)


def _finished(path):
    """True when SubagentStop is the last record in the transcript's tail. A resumed agent writes
    records after its old SubagentStop; that is running again, not finished."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL_BYTES))
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    return bool(lines) and b"SubagentStop" in lines[-1]


def _subagent_files(now, sessions=(), agents=()):
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects", "*")
    files = []
    for session in (sessions or ["*"]):
        pattern = os.path.join(base, session, "subagents", "agent-*.jsonl")
        files.extend(glob.glob(pattern))
    if agents:
        wanted = set("agent-%s.jsonl" % a for a in agents)
        files = [p for p in files if os.path.basename(p) in wanted]
    return [p for p in sorted(set(files)) if _age(p, now) < LOOKBACK_SECONDS]


def _scope_words(sessions, agents):
    parts = []
    if sessions:
        parts.append("session " + ", ".join(sessions))
    if agents:
        parts.append("agent " + ", ".join(agents))
    return " and ".join(parts)


def _label(path):
    name = os.path.basename(path)
    if name.startswith("agent-") and name.endswith(".jsonl"):
        return "subagent " + name[len("agent-"):-len(".jsonl")]
    return "file " + path


def check(files, extra, threshold):
    """[(label, state, age_seconds)] where state is ok, STALLED or finished."""
    now = time.time()
    rows = []
    for path in files:
        age = _age(path, now)
        if _finished(path):
            rows.append((_label(path), "finished", age))
        else:
            rows.append((_label(path), "STALLED" if age >= threshold else "ok", age))
    for path in extra:
        if not os.path.exists(path):
            rows.append(("file " + path, "STALLED", float("inf")))
        else:
            age = _age(path, now)
            rows.append(("file " + path, "STALLED" if age >= threshold else "ok", age))
    return rows


def _fmt(row):
    label, state, age = row
    return "%-9s %s (no new activity for %s)" % (
        state, label, "unknown time" if age == float("inf") else "%d s" % age)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll", type=float, default=POLL_SECONDS, help=argparse.SUPPRESS)  # tests only
    parser.add_argument("--session", action="append", default=[])
    parser.add_argument("--agent", action="append", default=[])
    args = parser.parse_args()
    scope = _scope_words(args.session, args.agent)
    header = ("stallcheck: watching " + scope + " only." if scope else
              "stallcheck: no --session or --agent given, so this is watching ALL sessions' "
              "subagents from the last 3 hours.")

    if not args.watch:
        print(header)
        rows = check(_subagent_files(time.time(), args.session, args.agent), args.file, args.threshold)
        if not rows:
            if scope:
                print("stallcheck: found no subagent transcript from the last 3 hours for %s and "
                      "no --file to check, so nothing was checked." % scope)
            else:
                print("stallcheck: found no subagent transcripts from the last 3 hours and no --file "
                      "to check, so nothing was checked.")
            return 2
        for row in rows:
            print(_fmt(row))
        return 1 if any(r[1] == "STALLED" for r in rows) else 0

    print(header, flush=True)
    seen = {}
    last_alert = {}  # label -> time of the last STALLED print; a stall is re-announced every threshold
    while True:
        rows = check(_subagent_files(time.time(), args.session, args.agent), args.file, args.threshold)
        if not rows:
            print("stallcheck: nothing to watch" + (" for " + scope if scope else "") + ".")
            return 2
        for row in rows:
            now = time.time()
            changed = seen.get(row[0]) != row[1]
            repeat = row[1] == "STALLED" and now - last_alert.get(row[0], now) >= args.threshold
            if (changed and row[1] != "ok") or repeat:
                print(_fmt(row), flush=True)
                last_alert[row[0]] = now
            seen[row[0]] = row[1]
        if all(r[1] == "finished" for r in rows):
            print("stallcheck: everything watched has finished.", flush=True)
            return 0
        time.sleep(args.poll)


if __name__ == "__main__":
    sys.exit(main())
