"""Phase 3 step 12 (#533): live headless sessions for save (PC, cloud), pickup, pages off. Prints PASS/FAIL + evidence;
writes live_phase3-result.txt beside itself. Usage: python live_phase3.py <scratch root>"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1]
PLUGIN = "/home/user/AjsClaudeCodeTools/claude-house-rules/plugins/house-rules"
OUT = []

def say(s):
    print(s, flush=True); OUT.append(s)

def check(ok, what, ev=""):
    say("%s %s" % ("PASS" if ok else "FAIL", what))
    if ev: say("    evidence: " + ev.replace("\n", "\n    "))

def env(cloud=False, loop="off"):
    e = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
    e.update(HOUSE_RULES_LOOP=loop, HOUSE_RULES_ISSUES="off", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
             GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if cloud: e["CLAUDE_CODE_REMOTE"] = "true"
    return e

def git(d, *a):
    p = subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True, env=env())
    return (p.stdout + p.stderr).strip() if p.returncode else p.stdout.strip()

def session(cwd, prompt, e):
    p = subprocess.run(["claude", "-p", "--plugin-dir", PLUGIN, "--settings",
                        json.dumps({"enabledPlugins": {"house-rules@aj-house-rules": False}}), "--model", "haiku",
                        "--permission-mode", "acceptEdits",  # added so headless file writes are not blocked
                        "--output-format", "stream-json", "--verbose", "--include-hook-events", prompt],
                       cwd=cwd, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL, env=e)
    ev = []
    for l in p.stdout.splitlines():
        try: ev.append(json.loads(l))
        except ValueError: pass
    if not ev: say("    session produced no events; stderr: " + p.stderr[:300])
    return ev

def hooks(ev):
    return [d for d in ev if d.get("type") == "system" and d.get("subtype") == "hook_response"]

def mkrepo(name, branch):
    d = os.path.join(ROOT, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    bare = os.path.join(ROOT, name + "-origin.git"); shutil.rmtree(bare, ignore_errors=True)
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    git(d, "init", "-q", "-b", branch); open(d + "/README.md", "w").write("x\n")
    git(d, "add", "."); git(d, "commit", "-qm", "init"); git(d, "remote", "add", "origin", bare)
    git(d, "push", "-q", "origin", branch)
    return d, bare

PROMPT = "Create notes.txt containing hello, do not commit"

# 1
d1, b1 = mkrepo("pc", "AjsAgent/live"); before = git(d1, "rev-parse", "HEAD")
session(d1, PROMPT, env())
refs = git(b1, "for-each-ref", "--format=%(refname)", "refs/house-rules/saves/AjsAgent/live/").split()
tree = git(b1, "ls-tree", "-r", "--name-only", refs[0]) if refs else ""
check(bool(refs) and "notes.txt" in tree and ".house-rules/handoff-facts.md" in tree, "1 live_save_pc: origin has a save ref with notes.txt and handoff-facts.md", "refs %s\ntree %s" % (refs, tree))
check(git(d1, "rev-parse", "HEAD") == before, "1 live_save_pc: branch got no new commit", git(d1, "log", "--oneline"))

# 2
d2, b2 = mkrepo("cloud", "ajsagent/live")
session(d2, PROMPT, env(cloud=True))
log = git(b2, "log", "--format=%s", "ajsagent/live"); files = git(b2, "ls-tree", "-r", "--name-only", "ajsagent/live")
sv = git(b2, "for-each-ref", "refs/house-rules/saves/")
check("wip: autosave" in log and "notes.txt" in files, "2 live_save_cloud: origin branch has `wip: autosave` commit with notes.txt", "log %s\nfiles %s" % (log, files))
check(sv == "", "2 live_save_cloud: no saves ref on origin", sv)

# 3 (note committed by git in folder 1, pushed first)
os.makedirs(d1 + "/docs/5-today", exist_ok=True)
open(d1 + "/docs/5-today/handoff-AjsAgent-live.md", "w").write("Handoff: finish notes.txt greeting.\n")
git(d1, "add", "docs/5-today/handoff-AjsAgent-live.md"); git(d1, "commit", "-qm", "handoff note"); git(d1, "push", "-q", "origin", "AjsAgent/live")
d3 = os.path.join(ROOT, "pc-second"); shutil.rmtree(d3, ignore_errors=True)
subprocess.run(["git", "clone", "-q", "-b", "AjsAgent/live", b1, d3], check=True)
ev = session(d3, "Say ok", env())
ctx = "\n".join((h.get("stdout") or "") for h in hooks(ev) if "SessionStart" in json.dumps(h)[:400])
ctx = ctx.replace("\\n", "\n")
cmd = next((l.split("Restore command: ", 1)[1].strip() for l in ctx.splitlines() if "Restore command: " in l), "").rstrip('"')
check("notes.txt" in ctx and "git apply" in ctx and "finish notes.txt greeting" in ctx, "3 live_pickup: SessionStart output lists notes.txt, restore command, and the note", ctx[:1500])
if cmd:
    r = subprocess.run(cmd, shell=True, cwd=d3, capture_output=True, text=True)
    got = open(d3 + "/notes.txt").read() if os.path.exists(d3 + "/notes.txt") else "<missing>"
    check("hello" in got.lower(), "3 live_pickup: restore command ran, notes.txt contains hello", "cmd %s\nrc %s %s\ncontent %r" % (cmd, r.returncode, r.stderr[:200], got))
else:
    check(False, "3 live_pickup: no restore command found to run")

# 4
d4 = os.path.join(ROOT, "pages"); shutil.rmtree(d4, ignore_errors=True); os.makedirs(d4)
session(d4, "pages off", env())
mf = d4 + "/.claude/house-rules-mode.json"; txt = open(mf).read() if os.path.exists(mf) else ""
check('"pages": "off"' in txt or '"pages":"off"' in txt, "4 live_pages_off: mode file has pages off", txt)
ev = session(d4, "Explain in about 250 words how a hash table works.", env(loop="on"))
bad = [h for h in hooks(ev) if "page" in (h.get("stdout") or "").lower() and "block" in (h.get("stdout") or "").lower()]
check(bool(hooks(ev)) and not bad, "4 live_pages_off: no Stop hook block about a page after pages off", "%d hook responses; offenders %s" % (len(hooks(ev)), [b.get("stdout", "")[:300] for b in bad]))
d5 = os.path.join(ROOT, "pages-q"); shutil.rmtree(d5, ignore_errors=True); os.makedirs(d5)
session(d5, "should I type pages off?", env())
check(not os.path.exists(d5 + "/.claude/house-rules-mode.json"), "4 live_pages_off: 'should I type pages off?' saves nothing", str(os.listdir(d5 + "/.claude")) if os.path.isdir(d5 + "/.claude") else "no .claude folder")

open(os.path.join(HERE, "live_phase3-result.txt"), "w").write("\n".join(OUT) + "\n")
