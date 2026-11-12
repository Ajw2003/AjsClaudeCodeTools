"""Phase 2 step 3, live: the real closablemerge hook, real GitHub (pull request #485, already merged), real git.

A fresh clone of this repo gets a local branch for #485's head at its merged commit, a clean helper worktree on a
second copy of that branch's history, and a helper worktree with an unsaved file. The hook runs as it would after
the merge. Nothing on GitHub is changed: the hook only reads the pull request. Prints PASS/FAIL per check.
"""
import json
import os
import subprocess
import sys
import time

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
URL = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
work = sys.argv[1]
clone = os.path.join(work, "clone")
results = []


def git(*a, cwd=None):
    p = subprocess.run(["git"] + list(a), cwd=cwd or clone, capture_output=True, text=True, timeout=300)
    return p.stdout.strip()


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + str(detail)[:800]))


subprocess.run(["git", "clone", "-q", URL, clone], check=True, timeout=600)
pr = json.loads(subprocess.run(["gh", "api", "repos/Ajw2003/AjsClaudeCodeTools/pulls/485", "--jq",
                                "{ref: .head.ref, sha: .head.sha}"], capture_output=True, text=True).stdout)
git("fetch", "-q", "origin", pr["sha"])
git("branch", pr["ref"], pr["sha"])
dirty = os.path.join(clone, ".claude", "worktrees", "unsaved")
git("worktree", "add", "-q", "-b", "helper-unsaved", dirty, pr["sha"])
with open(os.path.join(dirty, "wip.txt"), "w") as f:
    f.write("unsaved helper work\n")
check("setup: the local branch exists at the merged commit", git("rev-parse", pr["ref"]) == pr["sha"])

payload = {"hook_event_name": "PostToolUse", "tool_name": "mcp__github__merge_pull_request", "session_id": "live",
           "cwd": clone, "tool_input": {"owner": "Ajw2003", "repo": "AjsClaudeCodeTools", "pullNumber": 485},
           "tool_response": {"merged": True}}
env = dict(os.environ, CLAUDE_PLUGIN_ROOT=PLUGIN, CLAUDE_PROJECT_DIR=clone, HOUSE_RULES_AUTOSAVE="off")
t = time.time()
p = subprocess.run(["sh", os.path.join(PLUGIN, "scripts", "run.sh"), "closablemerge"], input=json.dumps(payload),
                   capture_output=True, text=True, cwd=clone, env=env, timeout=30)
secs = time.time() - t
out = p.stdout + p.stderr
print("hook output:", out[:900])
check("the hook exited 0 inside its 10-second limit (%.1f s)" % secs, p.returncode == 0 and secs < 10, out)
check("the merged branch was deleted, read from real GitHub", git("branch", "--list", pr["ref"]) == ""
      and ("branch " + pr["ref"]) in out, out)
check("the helper copy with an unsaved file was kept, the file is still there, and the note names it",
      os.path.isfile(os.path.join(dirty, "wip.txt")) and "worktree .claude/worktrees/unsaved" in out, out)
print("LIVE CLEANUP RESULT: %d of %d passed" % (sum(results), len(results)))
