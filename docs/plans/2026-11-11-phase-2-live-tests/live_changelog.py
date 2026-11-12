"""Phase 2 step 2, live: real headless Claude sessions with only this branch's plugin.

1. In a repo whose root has CHANGELOG.md, a session edits app.py and is told nothing about the changelog; the
   end-of-turn check should send the turn back once, and the session should then add a changelog line.
2. In a repo with every docs tier but no CHANGELOG.md, the session-start note should name the missing changelog.
Prints PASS/FAIL per check.
"""
import json
import os
import subprocess
import sys

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
work = sys.argv[1]
results = []
TRAIL = []  # what the sessions said and did, printed when a check fails


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + str(detail)[:3000]))
    sys.stdout.flush()


def repo(path, files):
    os.makedirs(path, exist_ok=True)
    for rel, text in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
    subprocess.run(["git", "init", "-q", "-b", "AjsAgent/cl-test", path], check=True)
    for k, v in (("user.name", "Edens Agent"), ("user.email", "agent@example.invalid")):
        subprocess.run(["git", "-C", path, "config", k, v], check=True)
    subprocess.run(["git", "-C", path, "add", "-A"], check=True)
    subprocess.run(["git", "-C", path, "commit", "-qm", "init"], check=True)


def session(cwd, prompt):
    env = dict(os.environ, HOUSE_RULES_AUTOSAVE="off", HOUSE_RULES_HANDOFF="off")  # the loop stays on: the checkpoint table needs it
    p = subprocess.run(
        ["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
         json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
         "--permission-mode", "acceptEdits", "--output-format", "stream-json", "--verbose", "--include-hook-events",
         prompt], cwd=cwd, env=env, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
    hooks = []
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append(json.dumps(d))
        if d.get("type") == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "text":
                    TRAIL.append("SAID: " + c["text"][:300])
                if c.get("type") == "tool_use":
                    TRAIL.append("TOOL: %s %s" % (c["name"], json.dumps(c.get("input"))[:200]))
    return hooks


tiers = {"docs/1-landing/README.md": "# Landing\n", "docs/2-roadmap/Roadmap.md": "# Roadmap\n",
         "docs/3-state/ProjectState.md": "# State\n", "docs/4-systems/app.md": "# App\n",
         "docs/5-today/Today.md": "# Today\n", "docs/6-decisions/Decisions.md": "# Decisions\n"}
a = os.path.join(work, "with-changelog")
repo(a, dict(tiers, **{"app.py": "x = 1\n", "CHANGELOG.md": "# Changelog\n\n## Unreleased\n"}))
hooks = session(a, "skip design. Use the Edit tool to change app.py so it says x = 2. Then reply 'done.' "
                   "If a hook sends your reply back, do what it asks.")
sent_back = [h for h in hooks if "changelog: Every change adds a line" in h]  # the checkpoint row's own rule text
check("a turn that edited app.py without a changelog line was sent back by the changelog check", bool(sent_back),
      " | ".join(h[:200] for h in hooks if "Stop" in h)[:500])
with open(os.path.join(a, "CHANGELOG.md")) as f:
    log = f.read()
check("after being sent back, the session added a line under Unreleased", log.count("\n- ") >= 1,
      log + " || " + " || ".join(TRAIL) + " || STOP HOOKS: " + " | ".join(h[-400:] for h in hooks if "Stop" in h))

b = os.path.join(work, "no-changelog")
repo(b, dict(tiers, **{"app.py": "x = 1\n"}))
hooks = session(b, "Reply with the single word: ok.")
start = [h for h in hooks if "SessionStart" in h and "CHANGELOG" in h]
check("session start names the missing CHANGELOG.md", bool(start), " | ".join(h[:150] for h in hooks)[:500])
print("LIVE CHANGELOG RESULT: %d of %d passed" % (sum(results), len(results)))
