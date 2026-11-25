#!/usr/bin/env python3
"""time_hooks.py - how long one tool call costs in hook time (#626, step 1 of #625).

    python tools/time_hooks.py            print timings only
    python tools/time_hooks.py --save     also write docs/qa/speed-first/baseline.json
    python tools/time_hooks.py --compare  print before/after against the saved baseline
    python tools/time_hooks.py --quick    Write and Bash hook timings, N=1, nothing else

Replays the real PreToolUse/PostToolUse commands from hooks.json (`sh run.sh <event>`, payload on
stdin, CLAUDE_PLUGIN_ROOT set) against a throwaway git repo. Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules")
SCRIPTS = os.path.join(PLUGIN, "scripts")
BASELINE = os.path.join(ROOT, "docs", "qa", "speed-first", "baseline.json")
PART_TIMEOUT = 55
ISSUES = range(625, 632)
REPO_SLUG = "Ajw2003/AjsClaudeCodeTools"


def hooks_for(tool, phase):
    """Event names (the word after run.sh) hooks.json runs for this tool, in file order."""
    with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as f:
        groups = json.load(f)["hooks"][phase + "ToolUse"]
    names = []
    for g in groups:
        if re.fullmatch(g.get("matcher", ".*"), tool):
            for h in g["hooks"]:
                names.append(h["command"].rsplit(" ", 1)[1])
    return names


def make_sandbox():
    d = tempfile.mkdtemp(prefix="time_hooks_")
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", d] + args, check=True, capture_output=True)
    for name, text in (("README.md", "# sandbox\n"), ("a.py", "print(1)\n"), ("CHANGELOG.md", "# Changelog\n")):
        with open(os.path.join(d, name), "w") as f:
            f.write(text)
    subprocess.run(["git", "-C", d, "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", "init"], check=True, capture_output=True)
    return d


def payload(tool, phase, sandbox):
    inp = ({"file_path": os.path.join(sandbox, "new.txt"), "content": "hello\n"} if tool == "Write"
           else {"command": "echo hello", "description": "say hello"})
    p = {"session_id": "time-hooks", "cwd": sandbox, "transcript_path": os.path.join(sandbox, "t.jsonl"),
         "hook_event_name": phase + "ToolUse", "tool_name": tool, "tool_input": inp}
    if phase == "Post":
        p["tool_response"] = {"success": True} if tool == "Write" else {"stdout": "hello\n", "stderr": ""}
    return json.dumps(p)


def run_hook(name, data, sandbox, env):
    t0 = time.perf_counter()
    subprocess.run(["sh", os.path.join(SCRIPTS, "run.sh"), name], input=data, text=True, cwd=sandbox,
                   env=env, capture_output=True, timeout=60)
    return (time.perf_counter() - t0) * 1000


def time_tool_calls(n):
    """{tool: {"total_ms", "processes", "hooks": {phase/name: ms}}}; medians of n runs."""
    sandbox = make_sandbox()
    cfg = tempfile.mkdtemp(prefix="time_hooks_cfg_")  # keeps hook state out of the real ~/.claude
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=PLUGIN, CLAUDE_CONFIG_DIR=cfg, CLAUDE_PROJECT_DIR=sandbox)
    out = {}
    try:
        for tool in ("Write", "Bash"):
            runs = {}
            for _ in range(n):
                for phase in ("Pre", "Post"):
                    data = payload(tool, phase, sandbox)
                    for name in hooks_for(tool, phase):
                        runs.setdefault(phase + "/" + name, []).append(run_hook(name, data, sandbox, env))
            per = {k: round(statistics.median(v), 1) for k, v in runs.items()}
            totals = [sum(v[i] for v in runs.values()) for i in range(n)]
            # one sh and one python per hook command; run.sh may probe interpreters, so this is a floor
            out[tool] = {"total_ms": round(statistics.median(totals), 1), "hooks": per,
                         "processes": 2 * len(per)}
    finally:
        shutil.rmtree(sandbox, True)
        shutil.rmtree(cfg, True)
    return out


def time_labels(n):
    if not shutil.which("gh"):
        return "SKIPPED: gh is not installed"
    sys.path.insert(0, SCRIPTS)
    from house_rules import design_loop
    issues = [{"repo": REPO_SLUG, "number": i} for i in ISSUES]
    ms = []
    for _ in range(n):
        t0 = time.perf_counter()
        labels, note = design_loop._loop_labels({}, issues, record=False)
        ms.append((time.perf_counter() - t0) * 1000)
        if note:
            return "SKIPPED: GitHub read failed (%s)" % note
    return {"ms": round(statistics.median(ms), 1), "issues": len(issues)}


def time_parts():
    out = {}
    for part in ("core", "safe_git", "design_loop", "writing", "delegation", "docs", "make_page"):
        t0 = time.perf_counter()
        try:
            subprocess.run([sys.executable, os.path.join(SCRIPTS, "checks", part + ".py")],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=PART_TIMEOUT)
            out[part] = round(time.perf_counter() - t0, 1)
        except subprocess.TimeoutExpired:
            out[part] = "TIMEOUT"
    return out


def collect(quick, n):
    res = {"n": 1 if quick else n, "tool_calls": time_tool_calls(1 if quick else n)}
    if not quick:
        res["label_reads"] = time_labels(3)
        res["stop_judge"] = "SKIPPED: paid model call, not timed"
        res["verify_parts_s"] = time_parts()
    return res


def show(res):
    for tool, r in res["tool_calls"].items():
        print("%s call: %.1f ms total, %d processes started (sh + python per hook)" % (tool, r["total_ms"], r["processes"]))
        for k, v in r["hooks"].items():
            print("    %-24s %.1f ms" % (k, v))
    if "label_reads" in res:
        lr = res["label_reads"]
        print(lr if isinstance(lr, str) else "label reads (%d issues): %.1f ms" % (lr["issues"], lr["ms"]))
        print(res["stop_judge"])
        for p, s in res["verify_parts_s"].items():
            print("verify part %-12s %s" % (p, s if s == "TIMEOUT" else "%.1f s" % s))


def flat(res):
    f = {}
    for tool, r in res["tool_calls"].items():
        f[tool + " total ms"] = r["total_ms"]
        for k, v in r["hooks"].items():
            f["%s %s ms" % (tool, k)] = v
    if isinstance(res.get("label_reads"), dict):
        f["label reads ms"] = res["label_reads"]["ms"]
    for p, s in res.get("verify_parts_s", {}).items():
        f["verify %s s" % p] = s
    return f


def compare(before, after):
    b, a = flat(before), flat(after)
    for k in a:
        old = b.get(k, "n/a")
        print("%-40s before %-8s after %s" % (k, old, a[k]))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)
    res = collect(args.quick, 5)
    show(res)
    if args.compare:
        if not os.path.exists(BASELINE):
            print("SKIPPED compare: no saved baseline at %s" % BASELINE)
        else:
            with open(BASELINE, encoding="utf-8") as f:
                compare(json.load(f), res)
    if args.save:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print("saved %s" % BASELINE)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
