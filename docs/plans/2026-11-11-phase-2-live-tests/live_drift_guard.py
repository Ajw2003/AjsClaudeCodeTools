"""Phase 2 step 1, live: the real guard hook judges a real `git commit` in a throwaway repo whose docs cite the
changed file. Prints what the guard emitted and PASS/FAIL."""
import json
import os
import subprocess
import sys

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
root = sys.argv[1]
os.makedirs(os.path.join(root, "docs", "4-systems"), exist_ok=True)
with open(os.path.join(root, "app.py"), "w") as f:
    f.write("".join("x%d = %d\n" % (i, i) for i in range(20)))
with open(os.path.join(root, "docs", "4-systems", "app.md"), "w") as f:
    f.write("The setting is at `app.py:5`, and the old one at `app.py:400`.\n")
g = ["git", "-C", root]
subprocess.run(["git", "init", "-q", "-b", "AjsAgent/drift-test", root], check=True)
subprocess.run(["git", "-C", root, "config", "user.name", "Edens Agent"], check=True)
subprocess.run(["git", "-C", root, "config", "user.email", "agent@example.invalid"], check=True)
subprocess.run(g + ["add", "-A"], check=True)
subprocess.run(g + ["commit", "-qm", "init"], check=True)
with open(os.path.join(root, "app.py"), "a") as f:
    f.write("x20 = 20\n")
subprocess.run(g + ["add", "app.py"], check=True)
payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s", "cwd": root,
           "tool_input": {"command": "git commit -m 'change app'"}}
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=PLUGIN, CLAUDE_PROJECT_DIR=root, HOUSE_RULES_AUTOSAVE="off")
p = subprocess.run(["sh", os.path.join(PLUGIN, "scripts", "run.sh"), "guard"], input=json.dumps(payload),
                   capture_output=True, text=True, cwd=root, env=env, timeout=30)
out = p.stdout + p.stderr
print("exit", p.returncode)
print(out[:1500])
ok = "docs/4-systems/app.md" in out and "app.py:400" in out and "past the end" in out
print("PASS" if ok else "FAIL", " the real guard names the citing doc and the drifted line for a real commit")
