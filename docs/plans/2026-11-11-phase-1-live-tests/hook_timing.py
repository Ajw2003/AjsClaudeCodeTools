"""Time the hooks phase 1 touches, old (installed 2.76.0) against new (this branch), on a fresh clone of this
branch with its real GitHub origin. Each hook runs 5 times; prints the median seconds and any non-zero exit."""
import json
import os
import statistics
import subprocess
import sys
import time

clone = sys.argv[1]
if not os.path.isdir(clone):
    subprocess.run(["git", "clone", "-q", "-b", "AjsAgent/session-handoff",
                    "https://github.com/Ajw2003/AjsClaudeCodeTools.git", clone], check=True)
roots = {"2.76.0": "/root/.claude/plugins/cache/aj-house-rules/house-rules/2.76.0",
         "2.78.0": "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"}
reply = "Step 3 is done and pushed. Next you'll hear step 4."
payloads = {
    "scope": {"hook_event_name": "UserPromptSubmit", "session_id": "t", "cwd": clone, "prompt": "how is it going"},
    "commitgate": {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "t", "cwd": clone,
                   "tool_input": {"file_path": os.path.join(clone, "claude-house-rules/plugins/house-rules/scripts/hook.py"),
                                  "old_string": "a", "new_string": "b"}},
    "guard": {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "t", "cwd": clone,
              "tool_input": {"command": "git status"}},
    "handover": {"hook_event_name": "Stop", "session_id": "t", "cwd": clone, "stop_hook_active": False,
                 "last_assistant_message": reply, "transcript_path": ""},
    "subagentrules": {"hook_event_name": "SubagentStart", "session_id": "t", "cwd": clone, "agent_type": "builder"},
}
env = dict(os.environ, HOUSE_RULES_AUTOSAVE="off")
for name, payload in payloads.items():
    row = [name]
    for ver, root in roots.items():
        times, codes, out = [], set(), ""
        for _ in range(5):
            t = time.time()
            p = subprocess.run(["sh", os.path.join(root, "scripts", "run.sh"), name], input=json.dumps(payload),
                               capture_output=True, text=True, cwd=clone, env=dict(env, CLAUDE_PLUGIN_ROOT=root),
                               timeout=30)
            times.append(time.time() - t)
            codes.add(p.returncode)
            out = (p.stdout + p.stderr).strip()
        row.append("%s %.2fs exit %s" % (ver, statistics.median(times), sorted(codes)))
        if ver == "2.78.0":
            row.append("out: " + out[:220].replace("\n", " "))
    print(" | ".join(row))
