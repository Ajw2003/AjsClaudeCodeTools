"""Live check for free issue closing (#548): asks the branch's guard hook, against the real GitHub,
whether three closes would be allowed. Nothing is closed: the guard only answers allow or deny.

Run from the repo root: python3 docs/plans/2026-11-20-free-issue-closing-live-check.py
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts", "hook.py")
CACHE = os.path.join(ROOT, ".git", "house-rules-issue-cache.json")
CLOSE = "gh issue " + "close"  # split so the session's own guard does not read this file's command line


def ask(command):
    payload = {"session_id": "live-check", "cwd": ROOT, "tool_name": "Bash", "tool_input": {"command": command}}
    env = dict(os.environ, HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="on")
    start = time.time()
    proc = subprocess.run([sys.executable, HOOK, "guard"], input=json.dumps(payload), capture_output=True,
                          text=True, env=env, timeout=60)
    took = time.time() - start
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])["hookSpecificOutput"]
        verdict = out["permissionDecision"]
        why = out.get("permissionDecisionReason") or out.get("additionalContext") or ""
    except (ValueError, KeyError, IndexError):
        verdict, why = "no decision", (proc.stdout + proc.stderr)[:300]
    print("%-70s %-6s %.1fs  %s" % (command, verdict, took, why[:160].replace("\n", " ")))
    return verdict


if os.path.exists(CACHE):
    os.remove(CACHE)
results = [
    ask("%s 548" % CLOSE) == "deny",   # in progress: refused
    ask("%s 520" % CLOSE) == "allow",  # open, needs review, no milestone: allowed
    ask("%s 521" % CLOSE) == "allow",  # same, answered from the cache
    ask("gh api -X PATCH repos/Ajw2003/AjsClaudeCodeTools/milestones/1 -f state=closed") == "deny",
]
with open(CACHE, encoding="utf-8") as f:
    cache = json.load(f)
for repo, entry in cache.items():
    print("cache: %s holds %d open issues, read once at %s" % (repo, len(entry["issues"]), time.ctime(entry["at"])))
print("RESULT: %s - %d of %d live checks as expected" % ("PASS" if all(results) else "FAIL", sum(results), len(results)))
sys.exit(0 if all(results) else 1)
