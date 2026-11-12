"""Phase 2 step 4, live: real headless Claude sessions with only this branch's plugin, real git, real Git LFS.

Session 1 is asked to commit a real 60 MB file: the guard should refuse it. Then aj's "LFS approved: big.bin" is
sent twice (in a cloud session GitHub's billing API is refused, so the first is pending and asks again), and a
session is asked to track and commit it: it should go in through LFS, so git stores a pointer. Separately, a
session start in a repo with a 6 GB generated folder should name it. Nothing is pushed. Prints PASS/FAIL.
"""
import json
import os
import subprocess
import sys

PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
work = sys.argv[1]
results, trail = [], []


def check(name, ok, detail=""):
    results.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "\n   " + str(detail)[:1500]))
    sys.stdout.flush()


def git(d, *a):
    return subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True).stdout.strip()


def repo(d):
    os.makedirs(os.path.join(d, ".claude"), exist_ok=True)
    os.makedirs(os.path.join(d, "docs", "6-decisions"), exist_ok=True)
    with open(os.path.join(d, ".claude", "house-rules-loop.json"), "w") as f:
        json.dump({"feature": "assets", "stage": "build", "skip": False, "approvals": []}, f)
    with open(os.path.join(d, "docs", "6-decisions", "Decisions.md"), "w") as f:
        f.write("# Decisions\n")
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("test\n")
    subprocess.run(["git", "init", "-q", "-b", "AjsAgent/bigfiles", d], check=True)
    for k, v in (("user.name", "Edens Agent"), ("user.email", "agent@example.invalid")):
        git(d, "config", k, v)
    git(d, "add", "-A")
    git(d, "commit", "-qm", "init")


def session(d, prompt):
    env = dict(os.environ, HOUSE_RULES_AUTOSAVE="off", HOUSE_RULES_HANDOFF="off")
    p = subprocess.run(
        ["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
         json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
         "--permission-mode", "acceptEdits", "--allowedTools=Bash", "--output-format", "stream-json", "--verbose",
         "--include-hook-events", prompt], cwd=d, env=env, capture_output=True, text=True, timeout=600,
        stdin=subprocess.DEVNULL)
    hooks = []
    for line in p.stdout.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("type") == "system" and o.get("subtype") == "hook_response":
            hooks.append(json.dumps(o))
        if o.get("type") == "user" and isinstance(o.get("message", {}).get("content"), list):
            for c in o["message"]["content"]:
                if c.get("type") == "tool_result":
                    trail.append("RESULT " + str(c.get("content"))[:300])
        if o.get("type") == "assistant":
            for c in o.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    trail.append("TOOL " + json.dumps(c.get("input"))[:200])
    return hooks


a = os.path.join(work, "assets")
repo(a)
with open(os.path.join(a, "big.bin"), "wb") as f:
    f.write(os.urandom(60 * 1024 * 1024))
head0 = git(a, "rev-parse", "HEAD")
session(a, "Run exactly: git add big.bin && git commit -m 'add big.bin'  . If it is refused, reply 'refused' and stop.")
check("a real session's commit of a real 60 MB file is refused", git(a, "rev-parse", "HEAD") == head0,
      " || ".join(trail[-6:]))
hooks = session(a, "LFS approved: big.bin")
st = json.load(open(os.path.join(a, ".claude", "house-rules-loop.json")))
check("aj's first 'LFS approved: big.bin' in a cloud session is pending (the billing read falls back to this repo)",
      "big.bin" in (st.get("lfs_pending") or []) and "big.bin" not in (st.get("lfs_approved") or []), st)
session(a, "LFS approved: big.bin")
st = json.load(open(os.path.join(a, ".claude", "house-rules-loop.json")))
check("the same line again records it as approved", "big.bin" in (st.get("lfs_approved") or []), st)
trail.clear()
session(a, "Run exactly: git lfs install --local && git lfs track big.bin && git add .gitattributes big.bin && "
           "git commit -m 'add big.bin through LFS'  . Then reply 'done'.")
blob = subprocess.run(["git", "-C", a, "show", "HEAD:big.bin"], capture_output=True).stdout[:200]
check("the approved file is committed through Git LFS (git holds a pointer, not 60 MB)",
      git(a, "rev-parse", "HEAD") != head0 and blob.startswith(b"version https://git-lfs.github.com/spec"),
      repr(blob) + " || " + " || ".join(trail[-6:]))

b = os.path.join(work, "disk")
repo(b)
with open(os.path.join(b, ".gitignore"), "w") as f:
    f.write("node_modules/\n")
os.makedirs(os.path.join(b, "node_modules", "pkg"))
with open(os.path.join(b, "node_modules", "pkg", "blob"), "wb") as f:
    f.truncate(6 * 1024**3)
hooks = session(b, "Reply with the single word: ok.")
disk = [h for h in hooks if "SessionStart" in h and "node_modules" in h]
check("session start names the 6 GB generated folder", bool(disk), " | ".join(h[:200] for h in hooks if "SessionStart" in h)[:800])
print("LIVE BIG FILES RESULT: %d of %d passed" % (sum(results), len(results)))
