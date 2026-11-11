"""Phase 2 check 7: a real headless session in a fresh clone of the pushed branch, using that clone's own plugin
(the installed copy switched off). Lists every hook that ran with its exit code, and names any hook that failed,
printed a traceback, or printed two JSON objects. Prints PASS/FAIL."""
import collections
import json
import subprocess
import sys

URL = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
clone = sys.argv[1]
subprocess.run(["git", "clone", "-q", "-b", "AjsAgent/session-handoff", URL, clone], check=True, timeout=600)
head = subprocess.run(["git", "-C", clone, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
p = subprocess.run(["claude", "-p", "--plugin-dir", clone + "/claude-house-rules/plugins/house-rules", "--settings",
                    json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                    "--output-format", "stream-json", "--verbose", "--include-hook-events", "Say ok and nothing else."],
                   cwd=clone, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
count, problems = collections.Counter(), []
for line in p.stdout.splitlines():
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if d.get("type") == "system" and d.get("subtype") == "hook_response":
        count[(d.get("hook_name"), d.get("exit_code"))] += 1
        out = (d.get("stdout") or "") + (d.get("stderr") or "")
        if d.get("exit_code") not in (0, None) or "Traceback" in out:
            problems.append("%s: %s" % (d.get("hook_name"), out[:300]))
        if (d.get("stdout") or "").strip().startswith("{"):  # plain text (another plugin's note) is allowed output
            try:
                json.loads(d["stdout"])
            except ValueError:
                problems.append("%s printed output that is not one JSON object: %s" % (d.get("hook_name"), d["stdout"][:200]))
print("fresh clone of AjsAgent/session-handoff at", head)
for (name, code), n in sorted(count.items(), key=str):
    print("  %d x %s, exit %s" % (n, name, code))
print("PASS" if count and not problems else "FAIL", " every hook in a real session exited 0 with one JSON object at most")
for x in problems:
    print("   ", x)
