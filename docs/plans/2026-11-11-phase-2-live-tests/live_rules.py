"""Phase 2 step 5, live: real headless Claude sessions with only this branch's plugin.

1. A session writes `speed = 5` into a Python file: the harvest hook should name it (a value someone may tune).
2. A session writes one file in each of two repos: the end-of-turn report should name both repos.
Prints PASS/FAIL per check.
"""
import json
import os
import subprocess
import sys

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
work = sys.argv[1]
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + str(detail)[:1200]))
    sys.stdout.flush()


def repo(d):
    os.makedirs(os.path.join(d, ".claude"), exist_ok=True)
    with open(os.path.join(d, ".claude", "house-rules-loop.json"), "w") as f:
        json.dump({"feature": "game", "stage": "build", "skip": False, "approvals": []}, f)
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("test\n")
    subprocess.run(["git", "init", "-q", "-b", "AjsAgent/rules", d], check=True)
    for k, v in (("user.name", "Edens Agent"), ("user.email", "agent@example.invalid")):
        subprocess.run(["git", "-C", d, "config", k, v], check=True)
    subprocess.run(["git", "-C", d, "add", "-A"], check=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", "init"], check=True)


def session(d, prompt):
    env = dict(os.environ, HOUSE_RULES_AUTOSAVE="off", HOUSE_RULES_HANDOFF="off")
    p = subprocess.run(
        ["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
         json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
         "--permission-mode", "acceptEdits", "--add-dir", work, "--output-format", "stream-json", "--verbose",
         "--include-hook-events", prompt], cwd=d, env=env, capture_output=True, text=True, timeout=600,
        stdin=subprocess.DEVNULL)
    return [l for l in p.stdout.splitlines() if '"hook_response"' in l]


a = os.path.join(work, "game")
repo(a)
hooks = session(a, "Use the Write tool to create player.py containing exactly two lines: `speed = 5` and "
                   "`name = \"hero\"`. Then reply 'done.' Do not change anything else.")
hit = [h for h in hooks if "PostToolUse" in h and "player.py" in h and "speed" in h]
check("harvest names `speed = 5` in player.py as a value someone may want to tune", bool(hit),
      " | ".join(h[:300] for h in hooks if "PostToolUse" in h)[:1200])

b = os.path.join(work, "tools")
repo(b)
hooks = session(a, "Use the Write tool to create %s and %s, each containing the single line `x = 1`. "
                   "Then reply 'done.'" % (os.path.join(a, "one.py"), os.path.join(b, "two.py")))
both = [h for h in hooks if "Stop" in h and "game" in h and "tools" in h and "issue" in h.lower()]
check("a turn that wrote files in two repos gets the report naming both", bool(both),
      " | ".join(h[-500:] for h in hooks if "Stop" in h)[:1200])
print("LIVE RULES RESULT: %d of %d passed" % (sum(results), len(results)))
