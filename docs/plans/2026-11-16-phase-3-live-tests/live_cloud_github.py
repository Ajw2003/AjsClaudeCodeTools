"""Unverified item 3 on the phase 3 QA page: a real cloud session's save reaching GitHub with this branch's plugin.
Runs in this cloud container (CLAUDE_CODE_REMOTE=true), on the throwaway branch ajsagent/phase-3-live-cloud of the
real repo. Session 1 in clone A creates notes.txt without committing; after it ends, GitHub's branch must hold a
`wip: autosave` commit with notes.txt. Then a fresh clone B from GitHub must have the file. Prints PASS/FAIL."""
import json, os, shutil, subprocess, sys

URL = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
BR = sys.argv[2] if len(sys.argv) > 2 else "ajsagent/phase-3-live-cloud"
PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
ROOT = sys.argv[1]

def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith("HOUSE_RULES_")}
    e.update(CLAUDE_CODE_REMOTE="true", HOUSE_RULES_LOOP="off", HOUSE_RULES_ISSUES="off")
    return e

def git(d, *a, check=True):
    p = subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True, timeout=300)
    if check and p.returncode:
        raise SystemExit("git %s failed: %s" % (" ".join(a), p.stderr.strip()))
    return p.stdout.strip()

def session(cwd, prompt):
    p = subprocess.run(["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--permission-mode", "acceptEdits", "--output-format", "stream-json", "--verbose",
                        "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL, env=env())
    hooks = []
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "hook_response":
            hooks.append("%s: %s" % (d.get("hook_name"), (d.get("stdout") or "")[:200]))
    return hooks

shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT)
a, b = os.path.join(ROOT, "a"), os.path.join(ROOT, "b")
subprocess.run(["git", "clone", "-q", "--depth", "5", "-b", "AjsAgent/phase-3-handoff", URL, a], check=True, timeout=600)
git(a, "config", "user.name", "Edens Agent")
git(a, "config", "user.email", "edens-agent@users.noreply.github.com")
git(a, "switch", "-q", "-c", BR)
git(a, "push", "-q", "-u", "origin", BR)
start = git(a, "rev-parse", "HEAD")
print("branch", BR, "pushed at", start[:7])

hooks = session(a, "Run this shell command and nothing else: echo hello > notes.txt")
remote = git(a, "ls-remote", "origin", "refs/heads/" + BR).split()[0]
git(a, "fetch", "-q", "origin", BR)
subj = git(a, "log", "-1", "--format=%s", remote)
files = git(a, "show", "--name-only", "--format=", remote).split()
ok = remote != start and subj == "wip: autosave" and "notes.txt" in files
print("%s session 1: GitHub's %s moved %s -> %s, newest commit %r with %s" % (
    "PASS" if ok else "FAIL", BR, start[:7], remote[:7], subj, files))
for h in hooks:
    if "autosave" in h.lower():
        print("    hook " + h.replace("\n", " "))

subprocess.run(["git", "clone", "-q", "--depth", "5", "-b", BR, URL, b], check=True, timeout=600)
got = open(os.path.join(b, "notes.txt")).read().strip() if os.path.isfile(os.path.join(b, "notes.txt")) else None
print("%s fresh clone from GitHub has notes.txt: %r" % ("PASS" if got == "hello" else "FAIL", got))
