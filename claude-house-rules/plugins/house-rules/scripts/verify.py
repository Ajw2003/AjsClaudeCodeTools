#!/usr/bin/env python3
"""verify.py - proves the house-rules hooks actually do what they claim.

Run it yourself, any time, on any machine:

    python claude-house-rules/plugins/house-rules/scripts/verify.py              # every part, at the same time
    python .../verify.py --parts core,safe_git                                    # only the named parts
    python .../verify.py --changed                                                # only the parts a change touched
    python .../verify.py --serial                                                 # one part after another, to debug

The checks live in checks/, one file per part (core, safe_git, design_loop, writing, delegation, docs,
make_page) plus checks/common.py, the setup they share. Each part file also runs alone:
`python checks/<part>.py` prints its own numbered results and its own RESULT line. This script starts the
parts as separate processes (as many at once as the machine has cores), prints each part's output whole in a
fixed order, adds up the checks, and exits 0 only if every part passed. CI runs it with no options, which
means every part. The layout is explained in docs/4-systems/verify-suites.md, "The split layout (#370)".

Each part feeds real hook payloads to hook.py's handlers and prints a numbered PASS/FAIL line for each, then
a verdict. Exit code 0 = all passed, 1 = something failed (or a part crashed), 2 = bad options. Nothing is
hidden: every case tested is printed alongside its result.

A third state, SKIP, exists for the handful of checks that read files the repo ships and the
plugin package does not (docs/, tools/, CLAUDE.md, the README). Run from the installed plugin
cache those used to report FAIL, where the honest answer is "not applicable here" - and a
RESULT line that is always red is one you stop reading. A skip never affects the exit code,
and it is only ever reached from outside a repo checkout: inside one, a missing file is still
a failure.

STDLIB ONLY. No third-party imports - the same constraint hook.py is built on.

The check count is never hardcoded anywhere that references it (here or in any doc) - it is
computed at runtime, so it cannot drift out from under an added case.
"""

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.join(HERE, "checks")
PLUGIN_REL = "claude-house-rules/plugins/house-rules/"

# Fixed order: the order each part's output is printed in, whatever order they finish in.
PARTS = ["core", "safe_git", "design_loop", "writing", "delegation", "docs", "make_page"]
# Start the slow ones first so a 4-core machine is not left waiting on one long part at the end.
START_ORDER = ["safe_git", "design_loop", "make_page", "core", "delegation", "docs", "writing"]
PART_TIMEOUT_SECONDS = 900

RESULT_RES = [
    re.compile(r"^RESULT: PASS - all (\d+) checks passed\."),
    re.compile(r"^RESULT: PASS - (\d+) of (\d+) checks passed, (\d+) skipped\."),
    re.compile(r"^RESULT: FAIL - (\d+) of (\d+) checks failed\."),
]
SKIP_LINE = re.compile(r"^\s*\d+\. SKIP  (.*)$")


# ---------------------------------------------------------------- --changed: which parts a change touched

def _git(args, cwd):
    p = subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def changed_files():
    """(files, base_description) or (None, why_not): what differs from the merge base with origin/main, plus
    uncommitted and untracked files. Paths are relative to the repository root."""
    rc, top, err = _git(["rev-parse", "--show-toplevel"], HERE)
    if rc != 0:
        return None, "this is not a git checkout (%s)" % err.strip()
    top = top.strip()
    rc, base, err = _git(["merge-base", "origin/main", "HEAD"], top)
    if rc != 0:
        return None, "no merge base with origin/main (%s)" % (err.strip() or "origin/main is not fetched")
    base = base.strip()
    files = set()
    # `git diff <commit>` compares the working tree with that commit, so it holds the branch's commits and
    # every uncommitted change to a tracked file in one list.
    rc, out, err = _git(["diff", "--name-only", base], top)
    if rc != 0:
        return None, "git diff failed (%s)" % err.strip()
    files.update(l for l in out.splitlines() if l)
    rc, out, err = _git(["ls-files", "--others", "--exclude-standard"], top)
    if rc != 0:
        return None, "git ls-files failed (%s)" % err.strip()
    files.update(l for l in out.splitlines() if l)
    return sorted(files), "merge base %s with origin/main, plus uncommitted and untracked files" % base[:8]


# Files outside the plugin that some check reads, and the parts whose checks read them. Anything else outside
# the plugin is still read by two whole-repo scans (docs: docref and plain_docs_check over every doc and code
# file; delegation: the scan for the retired executor agent over every text file), so it maps to those two.
_DOC_READERS = {
    "docs/architecture.md": ["core", "design_loop", "docs", "delegation"],
    "docs/claude-ai-instructions.md": ["core", "docs", "delegation"],
    "docs/desktop-verification.md": ["core", "docs", "delegation"],
    "docs/example-environment.md": ["core", "safe_git", "docs", "delegation"],
    "claude-house-rules/README.md": ["core", "safe_git", "docs", "delegation"],
    "CLAUDE.md": ["core", "design_loop", "docs", "delegation"],
    ".claude-plugin/marketplace.json": ["core", "docs", "delegation"],
}

_SCRIPT_PARTS = {  # scripts/<file> -> parts
    "clarity.py": ["writing", "design_loop"],     # the clear-writing cases live in design_loop.py (see the doc)
    "make_page.py": ["make_page"],
    "docref.py": ["docs"],
    "plain_docs_check.py": ["docs"],
    "harvest_scan.py": ["docs"],
    "stallcheck.py": ["delegation"],
    "labels.py": ["design_loop"],
}

_PLUGIN_DIRS = {  # plugin subfolder or file -> parts
    "templates/decision-summary.page.json": ["make_page"],
    "templates/handover-page.html": ["design_loop", "make_page"],
    "templates/step-card.html": ["core", "make_page"],
    "templates/": ["core", "design_loop", "make_page"],
    "commands/docref.md": ["docs"],
    "commands/harvest-scan.md": ["docs"],
    "commands/plain-docs.md": ["docs"],
    "commands/labels.md": ["design_loop"],
    "commands/doctor.md": ["core"],
    "skills/project-docs/": ["core", "docs"],
    "skills/plain-docs/": ["docs"],
    "agents/archivist.md": ["delegation", "docs"],
    "agents/": ["delegation"],
    "output-styles/": ["core"],
    ".claude-plugin/": ["core", "design_loop", "make_page"],
}


def parts_for(path):
    """(parts, reason) for one changed path. Unsure means every part."""
    every = (list(PARTS), "no single part is known to own it, so every part")
    if path.startswith(PLUGIN_REL):
        rel = path[len(PLUGIN_REL):]
        m = re.match(r"^scripts/house_rules/(\w+)\.py$", rel)
        if m:
            name = m.group(1)
            if name == "writing":
                return ["writing", "design_loop"], "house_rules/writing.py is the writing part, and the clear-writing cases live in checks/design_loop.py"
            if name in PARTS and name != "core":
                return [name], "house_rules/%s.py is the %s part" % (name, name)
            return every[0], "house_rules/%s.py is imported by every part" % name
        m = re.match(r"^scripts/checks/(\w+)\.py$", rel)
        if m:
            name = m.group(1)
            if name in PARTS and name != "core":
                return [name], "checks/%s.py holds the %s checks" % (name, name)
            if name == "core":
                return every[0], "checks/core.py: a change to core means every part"
            return every[0], "checks/%s.py is shared by every part" % name
        if rel in ("scripts/hook.py", "scripts/run.sh", "scripts/verify.py", "hooks/hooks.json"):
            return every[0], "%s is what every part runs or is run by" % rel
        m = re.match(r"^scripts/([\w.]+)$", rel)
        if m and m.group(1) in _SCRIPT_PARTS:
            return _SCRIPT_PARTS[m.group(1)], "%s is exercised by %s" % (m.group(1), ", ".join(_SCRIPT_PARTS[m.group(1)]))
        for prefix, parts in sorted(_PLUGIN_DIRS.items(), key=lambda kv: -len(kv[0])):
            if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)):
                return parts, "%s is read by %s" % (prefix.rstrip("/"), ", ".join(parts))
        return every
    if path in _DOC_READERS:
        return _DOC_READERS[path], "%s is read by %s" % (path, ", ".join(_DOC_READERS[path]))
    return ["docs", "delegation"], "outside the plugin, so only the whole-repo scans read it (docs: docref and plain_docs_check; delegation: the retired-agent scan)"


def choose_changed():
    files, why = changed_files()
    if files is None:
        return list(PARTS), ["--changed could not tell what changed: %s. Running every part." % why]
    lines = ["--changed compares against %s: %d changed file(s)." % (why, len(files))]
    chosen = set()
    for f in files:
        parts, reason = parts_for(f)
        chosen.update(parts)
        lines.append("  %s -> %s (%s)" % (f, ", ".join(parts) if len(parts) < len(PARTS) else "every part", reason))
        if len(chosen) == len(PARTS):
            lines.append("  (every part is now chosen; the remaining files are not listed)")
            break
    return [p for p in PARTS if p in chosen], lines


# ---------------------------------------------------------------- running the parts

def run_part(part, timeout):
    path = os.path.join(CHECKS, part + ".py")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, path], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        out = p.stdout.decode("utf-8", "replace")
        rc = p.returncode
        note = ""
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        rc = None
        note = "timed out after %d seconds" % timeout
    except OSError as e:
        out = ""
        rc = None
        note = "could not start: %s" % e
    return {"part": part, "out": out, "rc": rc, "note": note, "seconds": time.time() - t0}


def judge(res):
    """Fill in checks, failed, skipped, ok and why for one part's result."""
    res.update(checks=0, failed=0, skipped=[], ok=False)
    out = res["out"]
    res["skipped"] = [m.group(1) for m in (SKIP_LINE.match(l) for l in out.splitlines()) if m]
    verdict = None
    for line in out.splitlines():
        for i, rx in enumerate(RESULT_RES):
            m = rx.match(line)
            if m:
                verdict = (i, m)
    if res["note"]:
        res["why"] = res["note"]
    elif verdict is None:
        res["why"] = "exited %s without its RESULT line (crashed?)" % res["rc"]
    else:
        i, m = verdict
        g = [int(x) for x in m.groups()]
        if i == 0:
            res["checks"], res["failed"] = g[0], 0
        elif i == 1:
            res["checks"], res["failed"] = g[1], 0
        else:
            res["checks"], res["failed"] = g[1], g[0]
        if (res["failed"] == 0) != (res["rc"] == 0):
            res["why"] = "exit code %s does not match its RESULT line" % res["rc"]
        elif res["failed"]:
            res["why"] = "%d check(s) failed" % res["failed"]
        else:
            res["ok"] = True
            res["why"] = "passed"
    if not res["ok"] and not res["failed"]:
        res["failed"] = 1       # a part that crashed or stopped without a verdict counts as a failure
    return res


def main(argv):
    ap = argparse.ArgumentParser(description="Run the house-rules hook checks (every part, at the same time, by default).")
    ap.add_argument("--parts", help="comma-separated parts to run: " + ", ".join(PARTS))
    ap.add_argument("--changed", action="store_true", help="run only the parts a change touched (git diff against the merge base with origin/main, plus uncommitted files)")
    ap.add_argument("--serial", action="store_true", help="run the parts one after another instead of at the same time")
    ap.add_argument("--timeout", type=int, default=PART_TIMEOUT_SECONDS, help="seconds before a part counts as hung (default %(default)s)")
    args = ap.parse_args(argv)
    if args.parts and args.changed:
        ap.error("--parts and --changed cannot be combined")

    if args.parts:
        wanted = [p.strip() for p in args.parts.split(",") if p.strip()]
        bad = [p for p in wanted if p not in PARTS]
        if bad or not wanted:
            ap.error("unknown part(s) %s; the parts are: %s" % (", ".join(bad) or "(none given)", ", ".join(PARTS)))
        chosen = [p for p in PARTS if p in wanted]
        why = ["--parts named: %s." % ", ".join(chosen)]
    elif args.changed:
        chosen, why = choose_changed()
    else:
        chosen = list(PARTS)
        why = ["no option given: every part (%s)." % ", ".join(chosen)]

    cores = os.cpu_count() or 1
    workers = 1 if args.serial else max(1, min(cores, len(chosen)))
    print()
    print("house-rules hooks - verification (Python)")
    print("===========================================")
    print(f"Interpreter: {sys.executable}")
    print(f"hook.py:     {os.path.join(HERE, 'hook.py')}")
    print(f"run.sh:      {os.path.join(HERE, 'run.sh')}")
    for l in why:
        print(l)
    print("Ran: %s (%s)" % (", ".join(chosen) if chosen else "no part",
                            "one at a time" if args.serial else "%d at once on %d core(s)" % (workers, cores)))
    print()
    if not chosen:
        print("-" * 32)
        print("RESULT: PASS - 0 checks run. No changed file maps to a part, so there was nothing to run.")
        print()
        return 0

    t0 = time.time()
    results = {}
    order = [p for p in START_ORDER if p in chosen] if not args.serial else list(chosen)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {p: ex.submit(run_part, p, args.timeout) for p in order}
        for part in chosen:                    # fixed order, each part's output whole
            res = judge(futs[part].result())
            results[part] = res
            print("=" * 78)
            print("PART %s - %s (%.1f s)" % (part, res["why"], res["seconds"]))
            print("=" * 78)
            sys.stdout.write(res["out"] if res["out"].endswith("\n") or not res["out"] else res["out"] + "\n")
            sys.stdout.flush()
    wall = time.time() - t0

    total = sum(r["checks"] for r in results.values())
    failed = sum(r["failed"] for r in results.values())
    skipped = [(p, t) for p in chosen for t in results[p]["skipped"]]
    bad_parts = [p for p in chosen if not results[p]["ok"]]

    print("=" * 78)
    print("Parts:")
    for p in chosen:
        r = results[p]
        print("  %-12s %4d checks  %-6s %5.1f s  %s" % (p, r["checks"], "PASS" if r["ok"] else "FAIL", r["seconds"], r["why"]))
    print("  wall-clock %.1f s" % wall)
    print()
    print("-" * 32)
    if not bad_parts and not skipped:
        print(f"RESULT: PASS - all {total} checks passed. The hooks are behaving as written.")
    elif not bad_parts:
        print(f"RESULT: PASS - {total - len(skipped)} of {total} checks passed, {len(skipped)} skipped.")
        print("        The hooks are behaving as written. Skipped checks read files that ship in the")
        print("        repo and not in the plugin package, so from an installed copy they are not")
        print("        applicable rather than failing:")
        for p, t in skipped:
            print(f"          - {t}")
        print("        Run it from a repo checkout to check those too.")
    else:
        print(f"RESULT: FAIL - {failed} of {total} checks failed. Failing part(s): {', '.join(bad_parts)}. See the FAIL lines above.")
        for p in bad_parts:
            print(f"        {p}: {results[p]['why']}")
        if skipped:
            print(f"        {len(skipped)} more were skipped as repo-only; see the SKIP lines.")
    print()
    print("Dependencies used by the hooks: run.sh (POSIX sh) + a probed Python interpreter.")
    print("No node, no jq required by hook.py itself - stdlib only.")
    print("Matching is textual, so a command that merely mentions a tripwire word will also")
    print("prompt. That is deliberate - an extra keypress is cheaper than a missed commit.")
    print()
    return 0 if not bad_parts else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
