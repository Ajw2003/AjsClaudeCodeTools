"""Live end-to-end run of the phase 1 design loop: real headless Claude sessions, this branch's plugin only.

GitHub is replaced by the plugin's own stand-in files (HOUSE_RULES_LOOP_LABELS_FILE / _ISSUES_FILE), so the
labels can be flipped between sessions. Prints one line per step: what was sent, the stage after, and PASS/FAIL.
"""
import json
import os
import subprocess
import sys
import time

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
root = sys.argv[1]
labels_file = os.path.join(root + "-gh", "labels.json")
issues_file = os.path.join(root + "-gh", "issues.json")
os.makedirs(root + "-gh", exist_ok=True)
results = []


def git(*args):
    return subprocess.run(["git", "-C", root, "-c", "user.email=t@example.invalid", "-c", "user.name=t"] + list(args),
                          capture_output=True, text=True)


def setup():
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    os.makedirs(os.path.join(root, "docs", "6-decisions"), exist_ok=True)
    with open(os.path.join(root, ".claude", "house-rules-loop.json"), "w") as f:
        json.dump({"feature": "", "stage": "design", "skip": False, "approvals": []}, f)
    with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "w") as f:
        f.write("# Decisions\n\nan entry\n")
    with open(os.path.join(root, "app.py"), "w") as f:
        f.write("x = 1\n")
    subprocess.run(["git", "init", "-q", "-b", "feat-demo", root], check=True)
    git("remote", "add", "origin", "https://github.com/o/r.git")
    git("add", "-A")
    git("commit", "-qm", "init")
    set_labels("in progress")
    with open(issues_file, "w") as f:
        json.dump([], f)


def set_labels(label, numbers=(10, 11, 12)):
    with open(labels_file, "w") as f:
        json.dump({"o/r#%d" % n: ["Feature", "AjsAgent created this", label] for n in numbers}, f)


def log(text):
    with open(os.path.join(root, "docs", "6-decisions", "Decisions.md"), "a") as f:
        f.write(text + "\n")


def state():
    with open(os.path.join(root, ".claude", "house-rules-loop.json")) as f:
        return json.load(f)


def session(prompt):
    env = dict(os.environ, HOUSE_RULES_LOOP_LABELS_FILE=labels_file, HOUSE_RULES_LOOP_ISSUES_FILE=issues_file,
               HOUSE_RULES_AUTOSAVE="off", HOUSE_RULES_HANDOFF="off")
    t = time.time()
    proc = subprocess.run(
        ["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
         json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}),
         "--model", "haiku", "--permission-mode", "acceptEdits", "--output-format", "stream-json", "--verbose",
         prompt], cwd=root, env=env, capture_output=True, text=True, timeout=400)
    replies, hooks = [], []
    for line in proc.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "text":
                    replies.append(c["text"])
                if c.get("type") == "tool_use":
                    replies.append("[tool %s %s]" % (c["name"], json.dumps(c.get("input"))[:80]))
        if d.get("type") == "user":
            for c in d.get("message", {}).get("content", []) if isinstance(d.get("message", {}).get("content"), list) else []:
                if c.get("type") == "tool_result":
                    hooks.append("[result %s]" % str(c.get("content"))[:200])
        if d.get("type") == "system" and d.get("subtype") not in ("init",):
            hooks.append("[system %s %s]" % (d.get("subtype"), json.dumps(d)[:300]))
    return replies, hooks, round(time.time() - t, 1)


def step(name, prompt, check):
    replies, hooks, secs = session(prompt)
    st = state()
    ok = False
    try:
        ok = bool(check(st, replies, hooks))
    except Exception as exc:  # a check that crashes is a FAIL with the reason, never silent
        replies.append("check crashed: %r" % exc)
    results.append((name, ok))
    print("%s  %-55s stage=%s feature=%r held=%s reopened=%s (%ss)" % (
        "PASS" if ok else "FAIL", name, st.get("stage"), st.get("feature"), st.get("held"), st.get("reopened"), secs))
    if not ok:
        print("   replies:", [r[:300] for r in replies])
        print("   hooks:", hooks[:8])
    sys.stdout.flush()
    return replies, hooks


def app():
    with open(os.path.join(root, "app.py")) as f:
        return f.read()


setup()
step("1 feature-first design approval", "Widget design approved 1A. Reply in one sentence; change no files.",
     lambda s, r, h: s["stage"] == "plan" and s["feature"] == "Widget")
step("2 issues recorded by aj", "Issues for Widget: #10 #11 #12. Reply in one sentence; change no files.",
     lambda s, r, h: [i["number"] for i in s.get("issues", [])] == [10, 11, 12])
log("build plan for Widget")
step("3 feature-first build plan approval", "Widget build plan approved. Reply in one sentence; change no files.",
     lambda s, r, h: s["stage"] == "build")
step("4 code edit open in Build", "Use the Edit tool to change app.py so it says x = 2. Then reply 'done.' Do not ask questions.",
     lambda s, r, h: "x = 2" in app())
set_labels("needs review")
step("5 needs review starts QA at reply end", "Reply with the single word: ready.",
     lambda s, r, h: s["stage"] == "qa")
step("6 code edit refused in QA", "Use the Edit tool to change app.py so it says x = 3. If it is refused, reply 'refused.' and stop.",
     lambda s, r, h: "x = 3" not in app())
step("7 QA failed returns to Build in one message",
     "QA failed: Widget the button is grey. Reply in one sentence; change no files.",
     lambda s, r, h: s["stage"] == "build" and len(s.get("issues", [])) == 3)
step("8 edit refused while issues still say needs review",
     "Use the Edit tool to change app.py so it says x = 4. If it is refused, reply 'refused.' and stop.",
     lambda s, r, h: "x = 4" not in app() and s["stage"] == "build")
set_labels("in progress")
step("9 edit opens once issues are back to in progress",
     "Use the Edit tool to change app.py so it says x = 5. Then reply 'done.' Do not ask questions.",
     lambda s, r, h: "x = 5" in app() and s["stage"] == "build")
step("10 a reply ending in a question holds code edits",
     "Reply with exactly this one line and nothing else: Should the button be blue or green?",
     lambda s, r, h: s.get("held") is True)
step("11 aj's next message clears the hold and the edit goes through",
     "Blue. Use the Edit tool to change app.py so it says x = 6. Then reply 'done.' Do not ask questions.",
     lambda s, r, h: "x = 6" in app() and not s.get("held"))
step("12 'I went with' is sent back once",
     "Reply with exactly this line: I went with option B for the layout. If the reply is sent back to you, rewrite it as a question with options instead.",
     lambda s, r, h: len([x for x in r if not x.startswith("[tool")]) >= 2)
log("design for Gadget")
step("13 a reply offering one approval line is recorded",
     "Reply with exactly these two lines and nothing else:\nThe Gadget page is ready.\nDesign approved: Gadget",
     lambda s, r, h: s.get("offered") == ["Design approved: Gadget"])
step("14 a bare 'Approve 2B' sends that line; the old feature is kept",
     "Approve 2B",
     lambda s, r, h: s["stage"] == "plan" and s["feature"] == "Gadget" and "widget" in (s.get("features") or {}))
ok = sum(1 for _n, o in results if o)
print("LIVE RESULT: %d of %d steps passed" % (ok, len(results)))
