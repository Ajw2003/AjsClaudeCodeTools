#!/usr/bin/env python3
"""waitfor - the one way to wait: a clock, a done-test and a deadline, never an unbounded wait.

  waitfor.py --kind command|agent|build|ci --check "<shell command>" [--watch-file PATH]
             [--agent ID --session ID] [--deadline S] [--first-check S] [--interval S]
             [--stalled-after N] [--label TEXT]

The check command runs at each check: exit 0 = DONE, 1 = not yet, any other code = FAILED.
Stall detection reuses stallcheck.check: a wait is STALLED when the watched file / agent transcript
shows no new activity (older than one interval) across --stalled-after consecutive checks.
Exit codes: 0 done, 1 failed, 2 stalled, 3 timed out, 4 bad usage. Defaults come from load_waits().
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from house_rules import waits  # noqa: E402
import stallcheck  # noqa: E402


def say(msg):
    print("waitfor: " + msg, flush=True)


def header(name, first, interval, deadline, kind):
    return "%s: first check at %ss, then every %ss, deadline %ss (kind %s)" % (name, first, interval, deadline, kind)


def run_check(cmd, timeout):
    """(code, output); a command that cannot start is code -1 with the error text; code None = still running at the cap."""
    # On Windows a plain shell=True runs cmd.exe, which cannot read the POSIX checks this tool is given
    # (`;`, `test`, `$(...)`); use the sh that Git for Windows ships, and fall back to cmd.exe without it.
    sh = shutil.which("sh") if os.name == "nt" else None
    try:
        proc = subprocess.Popen([sh, "-c", cmd] if sh else cmd, shell=not sh, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as exc:
        return -1, "%s: %s" % (type(exc).__name__, exc)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out.decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        # the whole tree, or a child holding the pipe would hang us
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, 9)
        proc.communicate()
        return None, ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--kind", required=True, choices=sorted(waits.DEFAULTS["deadline_seconds"]))
    ap.add_argument("--check", required=True)
    ap.add_argument("--watch-file", action="append", default=[])
    ap.add_argument("--agent", action="append", default=[])
    ap.add_argument("--session", action="append", default=[])
    ap.add_argument("--deadline", type=float)
    ap.add_argument("--first-check", type=float)
    ap.add_argument("--interval", type=float)
    ap.add_argument("--stalled-after", type=int)
    ap.add_argument("--label")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 4 if exc.code else 0
    cfg = waits.load_waits()
    pick = lambda v, k: cfg[k] if v is None else v  # noqa: E731
    first = pick(args.first_check, "first_check_seconds")
    interval = pick(args.interval, "interval_seconds")
    stalled_after = pick(args.stalled_after, "stalled_after_quiet_checks")
    deadline = pick(args.deadline, "deadline_seconds") if args.deadline is not None else cfg["deadline_seconds"].get(args.kind)
    if not deadline or deadline <= 0 or first <= 0 or interval <= 0 or stalled_after <= 0:
        say("bad usage: no positive deadline/first-check/interval/stalled-after for kind %s; refusing an unbounded wait." % args.kind)
        return 4
    fmt = lambda n: int(n) if n == int(n) else n  # noqa: E731
    say(header(args.label or args.check, fmt(first), fmt(interval), fmt(deadline), args.kind))

    watching = bool(args.watch_file or args.agent or args.session)
    start = time.time()
    quiet = n = 0
    last = "no check has run yet"
    delay = first
    while True:
        left = deadline - (time.time() - start)
        if left <= 0:
            say("timed out: gave up after %ds; still unknown: %s" % (deadline, last))
            return 3
        time.sleep(min(delay, left))
        delay = interval
        n += 1
        at = time.time() - start
        code, out = run_check(args.check, max(1, deadline - (time.time() - start)))
        if code is None:
            say("timed out: gave up after %ds; still unknown: the check command was still running at the deadline" % deadline)
            return 3
        if code == 0:
            say("check %d at %ds: done. DONE after %ds." % (n, at, at))
            return 0
        if code != 1:
            say("check %d at %ds: FAILED, the check exited %d: %s" % (n, at, code, out))
            return 1
        last = out or "the check exited 1 with no output"
        note = "not yet" + (" (%s)" % out.splitlines()[-1] if out else "")
        if watching:
            files = stallcheck._subagent_files(time.time(), args.session, args.agent) if (args.agent or args.session) else []
            rows = stallcheck.check(files, args.watch_file, interval)
            if rows and all(r[1] != "ok" for r in rows) and any(r[1] == "STALLED" for r in rows):
                quiet += 1
            else:
                quiet = 0
            note += "; quiet checks %d/%d" % (quiet, stalled_after)
            last += " (%s)" % "; ".join(stallcheck._fmt(r) for r in rows) if rows else " (nothing found to watch)"
        say("check %d at %ds: %s" % (n, at, note))
        if watching and quiet >= stalled_after:
            say("STALLED: gave up after %ds; still unknown: %s" % (at, last))
            return 2


if __name__ == "__main__":
    sys.exit(main())
