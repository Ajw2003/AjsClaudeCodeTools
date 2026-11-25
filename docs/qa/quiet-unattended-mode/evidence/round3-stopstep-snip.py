# copy of the #640 stop-step snippet from scripts/checks/design_loop.py (round 3 QA), printing its case dict
import os, sys, json, subprocess, tempfile
here = sys.argv[1]
sys.path.insert(0, here)
cfg = tempfile.mkdtemp(); os.environ["CLAUDE_CONFIG_DIR"] = cfg
for k in ("HOUSE_RULES_UNATTENDED", "HOUSE_RULES_LOOP"): os.environ.pop(k, None)
from house_rules import design_loop as dl, core
d = os.path.realpath(tempfile.mkdtemp())
def git(*a): return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=d, check=True, capture_output=True)
git("init", "-q", "-b", "feat"); open(os.path.join(d, "a.py"), "w").write("x=1\n"); git("add", "-A"); git("commit", "-qm", "init")
g = os.path.join(d, ".git"); plan = os.path.join(d, "p.page.json")
json.dump({"test_command": "true", "changes": [["c", "Step 1: a", "", None, "", None, None, "echo 1"]]}, open(plan, "w"))
dl.record_steps(g, "f", plan, "s1")
tr = os.path.join(d, "t.jsonl")
def user(): return json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "go"}})
open(tr, "w").write(user() + "\n")
def pl(sid="s1", mode="default"): return json.dumps({"session_id": sid, "cwd": d, "transcript_path": tr, "permission_mode": mode})
def chk(reply, sid="s1", mode="default"): return dl.step_stop_check(pl(sid, mode), reply)
rec = lambda: dl._loop_read(g)[0]["steps"]["s1"]
r = {}
b = chk("All done, here is the summary.")[0]
r["normal"] = bool(b) and "Step 1: a" in b and "--step 1 --start" in b and "--poll" in b and "park" in b and "--tried" in b
r["needs_you"] = bool(chk("NEEDS YOU: the licence.")[0])
r["empty"] = bool(chk("")[0])
r["no_list"] = chk("x", sid="other") == (None, None)
r["question_attended"] = chk("hmm\nQUESTION FOR YOU: which colour?")[0] is None
r["question_nobody"] = bool(chk("QUESTION FOR YOU: which colour?", mode="bypassPermissions")[0])
os.environ["HOUSE_RULES_UNATTENDED"] = "on"; r["question_unattended"] = bool(chk("QUESTION FOR YOU: x")[0]); os.environ.pop("HOUSE_RULES_UNATTENDED")
r["stuck_after_3"] = any(s.get("stuck") for s in rec()["steps"])
r["stuck_listed"] = bool(dl.steps_stuck(g, pl()))
open(tr, "a").write(user() + "\n")
chk("x"); open(tr, "a").write(user() + "\n")
chk("x"); r["reset_on_message"] = sum(rec()["blocks"].values()) == 1
for _ in range(20):
    if chk("x")[0] is None: break
r["allowed_when_all_stuck"] = chk("x")[0] is None and len(dl.steps_stuck(g, pl())) == len(rec()["steps"])
stub = os.path.join(d, "judge.py"); open(stub, "w").write("print('{\"ok\": false, \"criterion\": \"C2\", \"reason\": \"x\"}')\n")
os.environ.update(HOUSE_RULES_JUDGE="on", HOUSE_RULES_JUDGE_CMD=stub, HOUSE_RULES_ROADBLOCKS_STATE=os.path.join(d, "rb.json"))
os.environ.pop("HOUSE_RULES_ROADBLOCKS", None)
def jb(sid):
    if os.path.exists(os.environ["HOUSE_RULES_ROADBLOCKS_STATE"]): os.remove(os.environ["HOUSE_RULES_ROADBLOCKS_STATE"])
    return [bool(core.roadblock_check(pl(sid), "I finished the thing.", False)[0]) for _ in range(3)]
r["judge_once_with_list"] = jb("s1") == [True, False, False]
r["judge_old_without_list"] = jb("none") == [True, True, False]
# live run: an autosave commit at every stop must not count as progress, or a looping agent is never marked stuck
dl.record_steps(g, "f", plan, "s3")
os.makedirs(os.path.join(d, "docs", "5-today"), exist_ok=True)
for i in range(5):
    open(os.path.join(d, "docs", "5-today", "n%d.md" % i), "w").write("x\n"); git("add", "-A"); git("commit", "-qm", "wip: autosave")
    chk("x", sid="s3")
r["stuck_despite_autosave_commits"] = any(s.get("stuck") for s in dl._loop_read(g)[0]["steps"]["s3"]["steps"])
# round-2 C8: with every step closed and nobody present, one block asks for the choices made unasked (none logged yet)
def allstuck(sid):
    dl.record_steps(g, "f", plan, sid)
    st = dl._loop_read(g)[0]
    for x in st["steps"][sid]["steps"]: x["stuck"] = True
    dl._loop_write(g, st)
allstuck("s4"); allstuck("s5")
r["choices_attended_none"] = chk("x", sid="s4", mode="default")[0] is None
_c1 = chk("x", sid="s1", mode="bypassPermissions")[0]
r["choices_block"] = bool(_c1) and "ledger_note.py" in _c1 and " decide " in _c1 and "No choices made" in _c1
r["choices_once"] = chk("x", sid="s1", mode="bypassPermissions")[0] is None
os.makedirs(os.path.join(d, "docs", "qa", "f"), exist_ok=True)
open(os.path.join(d, "docs", "qa", "f", "ledger.md"), "w").write("| K1 | s | c | a | w | u |\n")
r["choices_skipped_when_logged"] = chk("x", sid="s5", mode="bypassPermissions")[0] is None
print(r)
print(all(r.values()))
