"""D9 and U3 with real git: approvals go through the real scope hook, edits through the real commitgate hook,
branches are switched and merged with real git. Prints PASS/FAIL per check."""
import json
import os
import subprocess
import sys
import time

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
root = sys.argv[1]
gh = root + "-labels.json"
env = dict(os.environ, HOUSE_RULES_AUTOSAVE="off", HOUSE_RULES_HANDOFF="off", HOUSE_RULES_LOOP_LABELS_FILE=gh,
           HOUSE_RULES_LOOP_ISSUES_FILE=root + "-issues.json", CLAUDE_PLUGIN_ROOT=PLUGIN)
results = []


def git(*a):
    p = subprocess.run(["git", "-C", root, "-c", "user.email=t@example.invalid", "-c", "user.name=t"] + list(a),
                       capture_output=True, text=True)
    if p.returncode:
        print("git", a, "failed:", p.stderr.strip())
    return p


def hook(name, payload):
    p = subprocess.run(["sh", os.path.join(PLUGIN, "scripts", "run.sh"), name], input=json.dumps(payload),
                       capture_output=True, text=True, cwd=root, env=env, timeout=30)
    return p.stdout


def say(prompt):
    out = hook("scope", {"hook_event_name": "UserPromptSubmit", "session_id": "s", "cwd": root, "prompt": prompt})
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        return out


def edit():
    out = hook("commitgate", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "s", "cwd": root,
                              "tool_input": {"file_path": os.path.join(root, "app.py"), "old_string": "x",
                                             "new_string": "y"}})
    try:
        d = json.loads(out)["hookSpecificOutput"]
        return d.get("permissionDecision") or "allow", d.get("permissionDecisionReason", "")
    except (ValueError, KeyError):
        return "allow", out


def stage():
    with open(os.path.join(root, ".claude", "house-rules-loop.json")) as f:
        return json.load(f)


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + detail[:400]))


os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
os.makedirs(os.path.join(root, "docs", "6-decisions"), exist_ok=True)
with open(os.path.join(root, "app.py"), "w") as f:
    f.write("x = 1\n")
with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "w") as f:
    f.write("log\n")
subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
git("remote", "add", "origin", "https://github.com/o/r.git")
git("add", "-A")
git("commit", "-qm", "init")
with open(gh, "w") as f:
    json.dump({"o/r#%d" % n: ["Feature", "AjsAgent created this", "in progress"] for n in (1, 2, 3, 4)}, f)
with open(root + "-issues.json", "w") as f:
    json.dump([], f)


def build(feature, issues):
    with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "a") as f:
        f.write("design %s %s\n" % (feature, time.time()))
    say("%s design approved 1A" % feature)
    say("Issues for %s: %s" % (feature, " ".join("#%d" % n for n in issues)))
    with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "a") as f:
        f.write("plan %s %s\n" % (feature, time.time()))
    return say("%s build plan approved" % feature)


# Branch "older": a feature built first. Branch "newer": built a few seconds later.
git("checkout", "-qb", "older")
build("Older thing", [1, 2])
git("add", "-A"); git("commit", "-qm", "older stage")
check("older branch is in Build and its edit is allowed", stage()["stage"] == "build" and edit()[0] == "allow",
      json.dumps(stage())[:300])
time.sleep(2)
git("checkout", "-qb", "newer", "main")
note = build("Newer thing", [3, 4])
git("add", "-A"); git("commit", "-qm", "newer stage")
check("newer branch is in Build and its edit is allowed", stage()["stage"] == "build" and edit()[0] == "allow", note)
git("checkout", "-q", "older")
d, why = edit()
check("D9: after a real checkout of the older branch, code edits are held", d == "deny" and "Continue from" in why, why)
time.sleep(1)
with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "a") as f:
    f.write("redo %s\n" % time.time())
say("Older thing design approved 1B")
with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "a") as f:
    f.write("replan %s\n" % time.time())
say("Older thing build plan approved")
d, why = edit()
check("D9: approving anew on the older branch releases the hold", d == "allow", why + json.dumps(stage())[:300])
# U3: the newer feature reaches QA on its branch, then merges into main.
git("add", "-A"); git("commit", "-qm", "older re-approved")
git("checkout", "-q", "newer")
with open(gh, "w") as f:
    json.dump({"o/r#%d" % n: ["Feature", "AjsAgent created this", "needs review"] for n in (1, 2, 3, 4)}, f)
hook("handover", {"hook_event_name": "Stop", "session_id": "s", "cwd": root, "stop_hook_active": False,
                  "last_assistant_message": "Ready for QA.", "transcript_path": ""})
check("the newer branch moved to QA once its issues said needs review", stage()["stage"] == "qa", json.dumps(stage())[:200])
git("add", "-A"); git("commit", "-qm", "qa stage")
git("checkout", "-q", "main")
git("merge", "-q", "--no-ff", "newer", "-m", "merge newer")
before = open(os.path.join(root, ".claude", "house-rules-loop.json")).read()
d, why = edit()
after = open(os.path.join(root, ".claude", "house-rules-loop.json")).read()
check("U3: on main after the real merge, the QA stage reads as Done (no QA lock message), file unchanged",
      "QA stage" not in why and "Done stage" in why and before == after, why)
print("LIVE BRANCH RESULT: %d of %d passed" % (sum(results), len(results)))
