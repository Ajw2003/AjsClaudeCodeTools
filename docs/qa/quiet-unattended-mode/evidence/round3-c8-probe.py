"""Round-3 QA probe for C8: the choices check fires only when nobody is present, only once per step list,
and not when the ledger already holds a K row. Run: python3 round3-c8-probe.py <plugin scripts dir>"""
import os, sys, json, subprocess, tempfile
sys.path.insert(0, sys.argv[1])
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp()
for k in ("HOUSE_RULES_UNATTENDED", "HOUSE_RULES_LOOP"): os.environ.pop(k, None)
from house_rules import design_loop as dl
d = os.path.realpath(tempfile.mkdtemp())
def git(*a): return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=d, check=True, capture_output=True)
git("init", "-q", "-b", "feat"); open(os.path.join(d, "a.py"), "w").write("x=1\n"); git("add", "-A"); git("commit", "-qm", "init")
g = os.path.join(d, ".git"); plan = os.path.join(d, "p.page.json")
json.dump({"test_command": "true", "changes": [["c", "Step 1: a", "", None, "", None, None, "echo 1"]]}, open(plan, "w"))
tr = os.path.join(d, "t.jsonl"); open(tr, "w").write(json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "go"}}) + "\n")
def pl(sid, mode):
    p = {"session_id": sid, "cwd": d, "transcript_path": tr}
    if mode is not None: p["permission_mode"] = mode
    return json.dumps(p)
def done_list(sid, feature="Quiet Mode"):
    dl.record_steps(g, feature, plan, sid)
    st = dl._loop_read(g)[0]
    for x in st["steps"][sid]["steps"]: x["stuck"] = True  # a stuck step counts as closed; "done" needs a run file at the current tree
    dl._loop_write(g, st)
def chk(sid, mode): return dl.step_stop_check(pl(sid, mode), "All done.")[0]
r = {}
for i, mode in enumerate(["default", "auto", "acceptEdits", "plan", None, "weird"]):
    sid = "att%d" % i; done_list(sid)
    r["attended_%s_no_block" % mode] = all(chk(sid, mode) is None for _ in range(3))
    r["attended_%s_no_flag" % mode] = not dl._loop_read(g)[0]["steps"][sid].get("choices_asked")
done_list("byp"); seq = [chk("byp", "bypassPermissions") for _ in range(10)]
r["bypass_blocks_first_only"] = bool(seq[0]) and all(x is None for x in seq[1:])
r["bypass_text"] = bool(seq[0]) and "decide Quiet Mode" in seq[0] and "--assumption" in seq[0] and "No choices made" in seq[0]
os.environ["HOUSE_RULES_UNATTENDED"] = "on"
done_list("una"); seq = [chk("una", "default") for _ in range(10)]
r["unattended_blocks_first_only"] = bool(seq[0]) and all(x is None for x in seq[1:])
os.environ.pop("HOUSE_RULES_UNATTENDED")
# a K row in docs/qa/<feature slug>/ledger.md means no block
os.makedirs(os.path.join(d, "docs", "qa", "quiet-mode"), exist_ok=True)
open(os.path.join(d, "docs", "qa", "quiet-mode", "ledger.md"), "w").write("| K1 | 1 | c | a | w | u |\n")
done_list("logged"); r["logged_no_block"] = chk("logged", "bypassPermissions") is None
# an open step still gets the step-list block, never the choices text
dl.record_steps(g, "Quiet Mode", plan, "open1")
b = chk("open1", "bypassPermissions"); r["open_step_gets_step_block"] = bool(b) and "step list: not finished" in b and "No choices made" not in b
print(json.dumps(r, indent=1)); print("ALL PASS" if all(r.values()) else "SOME FAILED")
