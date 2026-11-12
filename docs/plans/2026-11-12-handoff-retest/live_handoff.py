"""Live re-test of the session handoff (#406) with real headless sessions and the real GitHub repo.

Session A edits a file in a fresh clone and does not commit; the autosave pushes a snapshot ref. Session B, in a
second fresh clone, is shown the pickup and runs the restore command it printed, through the plugin's own guards.
Only this branch's plugin runs (the installed copy is switched off). Prints PASS/FAIL per check.
"""
import json
import os
import subprocess
import sys
import time

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
URL = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
BRANCH = "AjsAgent/handoff-qa-2"
work = sys.argv[1]
os.makedirs(work, exist_ok=True)
a, b = os.path.join(work, "A"), os.path.join(work, "B")
results = []
MARK = "handoff QA line %d" % int(time.time())


def run(cmd, cwd=None, timeout=120):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + str(detail)[:600]))
    sys.stdout.flush()


def session(cwd, prompt):
    env = dict(os.environ)
    proc = subprocess.run(
        ["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
         json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}),
         "--model", "haiku", "--permission-mode", "acceptEdits", "--allowedTools", "Bash", "--output-format",
         "stream-json", "--verbose", "--include-hook-events", prompt],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    texts, hooks, tools = [], [], []
    for line in proc.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "text":
                    texts.append(c["text"])
                if c.get("type") == "tool_use":
                    tools.append(json.dumps(c.get("input"))[:300])
        if d.get("type") == "user" and isinstance(d.get("message", {}).get("content"), list):
            for c in d["message"]["content"]:
                if c.get("type") == "tool_result":
                    tools.append("RESULT " + str(c.get("content"))[:400])
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append(json.dumps(d))
    return texts, hooks, tools


# Clone A, make the test branch from the session-handoff head, push it.
run(["git", "clone", "-q", "-b", "AjsAgent/session-handoff", URL, a], timeout=300)
run(["git", "-C", a, "checkout", "-qb", BRANCH])
rc, out = run(["git", "-C", a, "push", "-q", "-u", "origin", BRANCH], timeout=120)
check("test branch pushed", rc == 0, out)

texts, hooks, tools = session(a, (
    "Append this exact line to the end of docs/5-today/Today.md: %s\n"
    "Use the Edit or Write tool. Do NOT commit, do NOT push, and do not run git at all, even if a hook asks you "
    "to; this is a handoff test where the change must stay uncommitted. Then reply 'done.'" % MARK))
rc, status = run(["git", "-C", a, "status", "--short"])
check("session A left Today.md edited and uncommitted", " M docs/5-today/Today.md" in status or "M docs/5-today/Today.md" in status,
      status + " | " + " ".join(tools)[:300])
rc, refs = run(["git", "ls-remote", URL, "refs/house-rules/autosave/" + BRANCH], timeout=60)
check("the snapshot ref is on GitHub", rc == 0 and refs.strip() != "", refs)
snap = refs.split()[0] if refs.strip() else ""
if snap:
    run(["git", "-C", a, "fetch", "-q", "origin", "refs/house-rules/autosave/%s" % BRANCH], timeout=120)
    rc, shown = run(["git", "-C", a, "show", "FETCH_HEAD:docs/5-today/Today.md"])
    check("the snapshot holds session A's new line", MARK in shown, shown[-300:])

# Clone B, fresh; its session start shows the pickup; the model runs the restore it printed.
run(["git", "clone", "-q", "-b", BRANCH, URL, b], timeout=300)
texts, hooks, tools = session(b, (
    "The session-start pickup message lists files that exist only in the saved snapshot and prints a "
    "'Restore command:'. aj approves running it: run that exact restore command with the Bash tool, then run "
    "`git status --short`, and reply with what happened. Do not commit."))
pickup = [h for h in hooks if "house-rules pickup" in h]
check("session B opened with the pickup", bool(pickup), " ".join(hooks)[:400])
restore_line = ""
for h in pickup:
    i = h.find("Restore command:")
    if i >= 0:
        restore_line = h[i:i + 300]
check("the pickup's restore command leaves out the stage file", restore_line and "house-rules-loop.json" not in restore_line,
      restore_line)
refused = [t for t in tools if "refused" in t.lower() or "denied" in t.lower()]
with open(os.path.join(b, "docs", "5-today", "Today.md"), encoding="utf-8") as f:
    got = f.read()
check("session B ran the restore and Today.md now has session A's line", MARK in got,
      "tools: " + " || ".join(tools)[:600])
check("no guard refused the restore", not refused, refused)
with open(os.path.join(a, "docs", "5-today", "Today.md"), encoding="utf-8") as f:
    want = f.read()
check("B's restored Today.md is identical to A's", got == want, "lengths %d vs %d" % (len(got), len(want)))
print("LIVE HANDOFF RESULT: %d of %d passed" % (sum(results), len(results)))
