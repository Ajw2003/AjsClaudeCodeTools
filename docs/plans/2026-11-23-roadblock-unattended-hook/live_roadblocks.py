"""Roadblock detection fix (#587): real headless sessions with this branch's plugin loaded by --plugin-dir and the
installed copy switched off, so the plugin under test is exactly the branch code (the desktop app runs the claude.ai
account's copy, which follows main, so it cannot test a branch).

    python live_roadblocks.py <empty scratch folder>

Prints PASS/FAIL per test with the hook evidence. Each test starts one paid session on the haiku model (a few cents)."""
import json, os, shutil, subprocess, sys

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                      "claude-house-rules", "plugins", "house-rules"))
ROOT = os.path.abspath(sys.argv[1])


def env(**extra):
    e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE" and not k.startswith("HOUSE_RULES_")}
    e.update(HOUSE_RULES_LOOP="off", HOUSE_RULES_ISSUES="off")
    e.update(extra)
    return e


def repo(name):
    d = os.path.join(ROOT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for argv in (["init", "-q", "-b", "AjsAgent/live-test"], ["config", "user.name", "Edens Agent"],
                 ["config", "user.email", "edens-agent@users.noreply.github.com"]):
        subprocess.run(["git", "-C", d] + argv, check=True)
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("# live test\n")
    subprocess.run(["git", "-C", d, "add", "-A"], check=True)
    subprocess.run(["git", "-C", d, "commit", "-qm", "init"], check=True)
    return d


def session(cwd, prompt, mode="acceptEdits", **extra_env):
    p = subprocess.run(["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--permission-mode", mode, "--allowedTools", "Bash", "Write", "--output-format",
                        "stream-json", "--verbose", "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL,
                       env=env(**extra_env))
    hooks, result = [], ""
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append((d.get("hook_name") or "") + " | " + (d.get("stdout") or "") + (d.get("output") or ""))
        if d.get("type") == "result":
            result = str(d.get("result") or "")
    return hooks, result, p.returncode


def roadblock_blocks(hooks):
    return [h for h in hooks if "House rules, roadblocks" in h]


def goal_blocks(hooks):
    return [h for h in hooks if "of 6)" in h]


def show(lines, n=500):
    for h in lines:
        print("    " + h.replace("\n", " ")[:n])


print("plugin under test:", PLUGIN, "version",
      json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))["version"])

# 1. A claim written with a curly apostrophe, no tool run, is blocked.
d = repo("curly")
hooks, result, rc = session(d, "Do not use any tools. Reply with exactly this one sentence and nothing else: "
                               "I can’t verify that zzqqtool is installed.")
b = roadblock_blocks(hooks)
print("%s curly apostrophe: %d roadblock block(s) (exit %d)" % ("PASS" if b else "FAIL", len(b), rc))
show(b)

# 2. A claim after only `git ls-files` is blocked (the probe never named the target).
d = repo("lsfiles")
hooks, result, rc = session(d, "Run `git ls-files` once with the Bash tool. Then reply with exactly this one "
                               "sentence and nothing else: I can't find zzqqtool, it is not installed.")
b = roadblock_blocks(hooks)
print("%s git ls-files only: %d roadblock block(s) (exit %d)" % ("PASS" if b else "FAIL", len(b), rc))
show(b)

# 3. Three failed attempts by different methods, related and listed in the reply, are left alone.
d = repo("threeways")
hooks, result, rc = session(d, "With the Bash tool run these three commands one at a time, each in its own call: "
                               "`which zzqqtool`, then `ls /usr/bin | grep zzqqtool`, then `pip show zzqqtool`. "
                               "Then reply with exactly: I can't find zzqqtool. I tried which, ls and pip show; "
                               "all three failed, so it is not installed.")
b = roadblock_blocks(hooks)
print("%s three different methods listed: %d roadblock block(s), expected 0 (exit %d)"
      % ("PASS" if not b else "FAIL", len(b), rc))
show(b)

# 4. Unattended: a stall phrase with the goal unreached is blocked by the goal check and the session carries on.
d = repo("stall")
hooks, result, rc = session(d, "Goal: create three files a.txt, b.txt and c.txt, each containing its own letter. Work one file "
                               "per turn: this turn create only a.txt, then end your reply with exactly the words: "
                               "Next step: create b.txt and c.txt. Do not create b.txt or c.txt in this turn.",
                            HOUSE_RULES_UNATTENDED="on")
g = goal_blocks(hooks)
files = [n for n in ("a.txt", "b.txt", "c.txt") if os.path.isfile(os.path.join(d, n))]
print("%s unattended stall: %d goal block(s); files present: %s (exit %d)"
      % ("PASS" if g else "FAIL", len(g), files, rc))
show(g)

# 5. Bypass mode: NOT TESTABLE in a headless session. `claude -p` answers "AskUserQuestion is disabled for this
# session" even with CLAUDE_CODE_ENABLE_ASK_USER_QUESTION_TOOL=1 (seen in the raw stream on 2026-11-23), so the model
# never reaches the denial hook; that path is covered by the fixture cases in scripts/checks/core.py only.
print("SKIP bypass question: the question tool does not exist in headless sessions; covered by fixture cases only")
print("final replies are in each test's folder under", ROOT)
