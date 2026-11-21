"""Free issue closing (#548): aj's two QA prompts, run in real headless sessions with this branch's plugin loaded by
--plugin-dir and the installed copy switched off, in a fresh clone of the repo on the branch.

    python3 live_free_issue_closing.py <empty scratch folder> <needs-review issue> <in-progress issue>

Test 1 really closes the needs-review issue (aj's QA step). Prints PASS/FAIL per test with the evidence read back
from GitHub. Each test starts one paid session on the haiku model."""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "Ajw2003/AjsClaudeCodeTools"
BRANCH = "AjsAgent/free-issue-closing"
ROOT = os.path.abspath(sys.argv[1])
OPEN_REVIEWED, IN_PROGRESS = int(sys.argv[2]), int(sys.argv[3])


def env():
    e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE" and not k.startswith("HOUSE_RULES_")}
    e.update(HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="on")
    return e


def issue(n):
    out = subprocess.run(["gh", "api", "repos/%s/issues/%d" % (REPO, n), "--jq",
                          "{state, labels: [.labels[].name]}"], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def session(cwd, plugin, prompt):
    p = subprocess.run(["claude", "-p", "--plugin-dir", plugin, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--permission-mode", "acceptEdits", "--allowedTools", "Bash", "--output-format",
                        "stream-json", "--verbose", "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL, env=env())
    hooks, version, final = [], None, ""
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            version = [x for x in d.get("plugins", []) if "house-rules" in json.dumps(x)]
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append((d.get("hook_name") or "") + " " + (d.get("stdout") or ""))
        if d.get("type") == "result":
            final = d.get("result") or ""
    return hooks, version, final, p.returncode


def close_verdicts(hooks):
    return [h for h in hooks if "close guard" in h or "this close is allowed" in h]


shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT)
clone = os.path.join(ROOT, "repo")
subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", BRANCH,
                "https://github.com/%s" % REPO, clone], check=True)
for argv in (["config", "user.name", "Edens Agent"],
             ["config", "user.email", "79066376+Ajw2003@users.noreply.github.com"]):
    subprocess.run(["git", "-C", clone] + argv, check=True)
plugin = os.path.join(clone, "claude-house-rules", "plugins", "house-rules")
print("plugin under test:", plugin, "version",
      json.load(open(os.path.join(plugin, ".claude-plugin", "plugin.json")))["version"])
results = []

# 1. aj's QA step 2: a needs-review issue closes without asking and gets the agent's completed label.
before = issue(OPEN_REVIEWED)
hooks, plugins, final, rc = session(clone, plugin, "Close issue #%d if the house rules allow it." % OPEN_REVIEWED)
after = issue(OPEN_REVIEWED)
print("session plugins:", json.dumps(plugins))
ok = (before["state"] == "open" and after["state"] == "closed" and "AjsAgent completed this" in after["labels"]
      and "in progress" not in after["labels"])
results.append(ok)
print("%s reviewed-closes: #%d before %s, after %s (exit %d)" % ("PASS" if ok else "FAIL", OPEN_REVIEWED,
                                                                  json.dumps(before), json.dumps(after), rc))
for h in close_verdicts(hooks):
    print("    " + h.replace("\n", " ")[:400])
print("    reply: " + final.replace("\n", " ")[:400])

# 2. aj's QA step 3: an in-progress issue is refused, and stays open.
hooks, plugins, final, rc = session(clone, plugin, "Close issue #%d." % IN_PROGRESS)
after = issue(IN_PROGRESS)
refusals = [h for h in close_verdicts(hooks) if "refused" in h]
ok = after["state"] == "open" and any("in progress" in h for h in refusals)
results.append(ok)
print("%s in-progress-refused: #%d after %s, %d refusal(s) naming in progress (exit %d)"
      % ("PASS" if ok else "FAIL", IN_PROGRESS, json.dumps(after), len(refusals), rc))
for h in refusals:
    print("    " + h.replace("\n", " ")[:400])
print("    reply: " + final.replace("\n", " ")[:400])

print("RESULT: %s - %d of %d live tests passed" % ("PASS" if all(results) else "FAIL", sum(results), len(results)))
sys.exit(0 if all(results) else 1)
