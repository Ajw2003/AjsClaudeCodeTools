#!/usr/bin/env python3
"""stallcheck - the cheapest reliable test for "has this background work stalled?".

No model call, no parsing: it compares the age of the newest write to a file the work keeps
appending to against a threshold (default 300 s). A subagent appends a record to its transcript
for every message and tool call, so a transcript that has not changed for 5 minutes means no
progress. A background command appends to its output file the same way.

  python stallcheck.py                      every subagent transcript touched in the last 3 hours
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
    """True when the transcript's tail holds a SubagentStop record."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - TAIL_BYTES))
        return b"SubagentStop" in f.read()


def _subagent_files(now):
    pattern = os.path.join(os.path.expanduser("~"), ".claude", "projects", "*", "*", "subagents",
                           "agent-*.jsonl")
    return [p for p in glob.glob(pattern) if _age(p, now) < LOOKBACK_SECONDS]


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
    args = parser.parse_args()

    if not args.watch:
        rows = check(_subagent_files(time.time()), args.file, args.threshold)
        if not rows:
            print("stallcheck: found no subagent transcripts from the last 3 hours and no --file "
                  "to check, so nothing was checked.")
            return 2
        for row in rows:
            print(_fmt(row))
        return 1 if any(r[1] == "STALLED" for r in rows) else 0

    seen = {}
    while True:
        rows = check(_subagent_files(time.time()), args.file, args.threshold)
        if not rows:
            print("stallcheck: nothing to watch.")
            return 2
        for row in rows:
            if seen.get(row[0]) != row[1] and row[1] != "ok":
                print(_fmt(row), flush=True)
            seen[row[0]] = row[1]
        if all(r[1] == "finished" for r in rows):
            print("stallcheck: everything watched has finished.", flush=True)
            return 0
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
