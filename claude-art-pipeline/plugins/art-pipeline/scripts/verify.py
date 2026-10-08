#!/usr/bin/env python3
"""verify.py - proves art-pipeline's hooks do what they claim.

    python claude-art-pipeline/plugins/art-pipeline/scripts/verify.py

Numbered PASS/FAIL lines, exit 0 on all-pass / 1 on any failure. Stdlib only. Builds throwaway
git repos with subprocess git.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
REVIEW = os.path.join(HERE, "review.py")
ART = os.path.join(HERE, "art.py")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
SH = shutil.which("sh") or "sh"
STEP = FAILURES = 0
TMP = []
SEEN_TXT = "front and side views match the concept: horns, tail and the red cloak all present"


def report(ok, title):
    global STEP, FAILURES
    STEP += 1
    FAILURES += 0 if ok else 1
    print(f"{STEP:2d}. {'PASS' if ok else 'FAIL'}  {title}")


def sh_git(cwd, *a):
    subprocess.run(["git"] + list(a), cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def mkrepo(art=True):
    d = tempfile.mkdtemp(prefix="art-pipeline-verify-")
    TMP.append(d)
    sh_git(d, "init", "-q")
    sh_git(d, "config", "user.name", "t")
    sh_git(d, "config", "user.email", "t@example.com")
    write(d, "README.md", "x")
    if art:
        write(d, "art/old.fbx", "old")
    sh_git(d, "add", "-A")
    sh_git(d, "commit", "-qm", "init")
    return d


def write(d, rel, text="data", mtime=None):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


def run(args, payload="", env=None, cwd=None):
    e = dict(os.environ)
    e.pop("ART_PIPELINE", None)
    e.update(env or {})
    p = subprocess.run(args, input=payload.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=cwd)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def hook(event, d, extra=None, env=None, session="s1"):
    pl = {"session_id": session, "cwd": d}
    pl.update(extra or {})
    return run([sys.executable, HOOK, event], json.dumps(pl), env)


def gate(d, env=None):
    rc, out, _ = hook("gate", d, env=env)
    return rc, (json.loads(out) if out.strip() else {})


def see(d, path):
    return hook("seen", d, {"tool_input": {"file_path": path}})


def record(d, model, sheet, verdict="pass", seen=SEEN_TXT):
    return run([sys.executable, REVIEW, "record", "--model", model, "--sheet", sheet,
                "--verdict", verdict, "--seen", seen], cwd=d)


def good_setup(d, model="art/hero.fbx", verdict="pass"):
    """changed model + fresh seen sheet + record; returns the sheet path."""
    now = time.time()
    write(d, model, "m", mtime=now - 100)
    sheet = write(d, "docs/art/sheets/hero.png", "png", mtime=now - 50)
    record(d, model, "docs/art/sheets/hero.png", verdict)
    see(d, sheet)
    return sheet


print("\nart-pipeline hooks - verification (Python)\n" + "=" * 42)
print(f"Interpreter: {sys.executable}\n")

spec = importlib.util.spec_from_file_location("art_pipeline_hook", HOOK)
hm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hm)

try:
    # 1 hooks.json <-> EVENTS
    reg = set()
    for entries in json.load(open(HOOKS_JSON))["hooks"].values():
        for e in entries:
            for h in e["hooks"]:
                m = re.search(r'run\.sh"\s+(\w+)', h["command"])
                if m:
                    reg.add(m.group(1))
    report(reg == set(hm.EVENTS), f"hooks.json registers exactly hook.py's events {sorted(hm.EVENTS)}")

    # 2-3 start
    d = mkrepo(art=True)
    rc, out, _ = hook("start", d)
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    led = os.path.join(d, ".git", "art-pipeline", "s1.json")
    ok = rc == 0 and "review record" in ctx and os.path.exists(led) and json.load(open(led))["seen"] == []
    report(ok, "start in a repo with art: context emitted, ledger in .git/art-pipeline")
    d2 = mkrepo(art=False)
    rc, out, _ = hook("start", d2)
    report(rc == 0 and out == "" and not os.path.exists(os.path.join(d2, ".git", "art-pipeline")),
           "start in a repo without art: silent, no ledger")
    nogit = tempfile.mkdtemp(prefix="art-pipeline-nogit-")
    TMP.append(nogit)
    rc, out, _ = hook("start", nogit)
    rc2, out2, _ = hook("gate", nogit)
    report(rc == 0 and out == "" and rc2 == 0 and out2 == "", "start and gate outside a git repo: nothing")

    # 4 seen
    see(d, os.path.join(d, "a", "..", "x.png"))
    see(d, os.path.join(d, "Foo.cs"))
    seen = json.load(open(led))["seen"]
    report(len(seen) == 1 and seen[0]["path"] == os.path.join(d, "x.png"), "seen records a png (normalized) and ignores a .cs")

    # 5 gate no changes
    rc, o = gate(d)
    report(rc == 0 and o == {}, "gate passes silently with no changed models")

    # 6 untracked fbx no record
    write(d, "art/hero.fbx", "m")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "art/hero.fbx" in o["reason"] and "no review record" in o["reason"]
           and "review.py" in o["reason"], "gate blocks a changed untracked .fbx with no record; reason names it")

    # 7 sheet older than model
    d = mkrepo(); hook("start", d)
    now = time.time()
    write(d, "art/hero.fbx", "m", mtime=now)
    sheet = write(d, "s.png", "p", mtime=now - 500)
    record(d, "art/hero.fbx", "s.png"); see(d, sheet)
    rc, o = gate(d)
    report(o.get("decision") == "block" and "older than the model" in o["reason"], "gate blocks when the sheet is older than the model")

    # 8 sheet not seen
    d = mkrepo(); hook("start", d)
    write(d, "art/hero.fbx", "m", mtime=now - 100)
    write(d, "s.png", "p", mtime=now - 50)
    record(d, "art/hero.fbx", "s.png")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "not opened" in o["reason"], "gate blocks when the sheet was not opened this session")

    # 9 all good
    d = mkrepo(); hook("start", d); good_setup(d)
    rc, o = gate(d)
    report(rc == 0 and o == {}, "gate passes with record + fresh sheet + seen + pass")

    # 10 waived
    d = mkrepo(); hook("start", d); good_setup(d, verdict="waived")
    rc, o = gate(d)
    report("decision" not in o and "WAIVED" in o.get("systemMessage", "") and "art/hero.fbx" in o["systemMessage"],
           "waived passes, listed in a systemMessage")

    # 11 fail verdict
    d = mkrepo(); hook("start", d); good_setup(d, verdict="fail")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "verdict is fail" in o["reason"], "fail verdict blocks")

    # 11b short seen rejected by the CLI and by the gate
    d = mkrepo(); hook("start", d)
    write(d, "art/hero.fbx", "m"); write(d, "s.png", "p")
    rc, _, err = record(d, "art/hero.fbx", "s.png", seen="looks ok")
    rc2, _, err2 = record(d, "art/nope.fbx", "s.png")
    report(rc == 1 and ">= 40" in err and rc2 == 1 and "does not exist" in err2, "review.py record rejects short --seen and missing files")

    # 12 loop guard
    d = mkrepo(); hook("start", d); write(d, "art/hero.fbx", "m")
    r = [gate(d)[1] for _ in range(3)]
    ok = r[0].get("decision") == "block" and r[1].get("decision") == "block" and "decision" not in r[2] \
        and "stopping with UNREVIEWED models: art/hero.fbx" in r[2].get("systemMessage", "")
    report(ok, "loop guard: blocks twice, releases on the 3rd identical block with a systemMessage")

    # 13 off switch
    rc, o = gate(d, env={"ART_PIPELINE": "off"})
    report(rc == 0 and "decision" not in o and "OFF" in o.get("systemMessage", ""), "ART_PIPELINE=off: gate says it is off, does not block")

    # 14 override
    d = mkrepo(); hook("start", d)
    write(d, ".art-pipeline.json", json.dumps({"model_globs": ["*.ma"], "review_dir": "rev"}))
    write(d, "art/a.fbx", "m"); write(d, "art/b.ma", "m")
    rc, o = gate(d)
    ok1 = "art/b.ma" in o.get("reason", "") and "art/a.fbx" not in o["reason"] and "rev/" in o["reason"]
    write(d, "node_modules/x/c.ma", "m")
    ok2 = "node_modules" not in gate(d)[1].get("reason", "")
    report(ok1 and ok2, ".art-pipeline.json overrides globs and review_dir; node_modules excluded")

    # 15 committed since start
    d = mkrepo(); hook("start", d)
    write(d, "art/new.glb", "m"); sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "model")
    rc, o = gate(d)
    report("art/new.glb" in o.get("reason", ""), "a model committed since session start is caught")

    # 16 corrupt ledger -> fail open with message
    d = mkrepo(); hook("start", d); write(d, "art/hero.fbx", "m")
    open(os.path.join(d, ".git", "art-pipeline", "s1.json"), "w").write("{not json")
    rc, out, _ = hook("gate", d)
    o = json.loads(out)
    report(rc == 0 and "decision" not in o and "internal error" in o["systemMessage"] and "NOT run" in o["systemMessage"],
           "gate fails open with a systemMessage on a corrupt ledger")

    # 17 status shares the logic
    d = mkrepo(); hook("start", d); good_setup(d); write(d, "art/other.obj", "m")
    rc, out, _ = run([sys.executable, REVIEW, "status"], cwd=d)
    report(rc == 0 and "PASS  art/hero.fbx" in out and "BLOCK  art/other.obj" in out, "review.py status reports per-model pass/block")

    # doc_check
    def dcrepo(cmd, **kw):
        d = mkrepo(); hook("start", d)
        write(d, ".art-pipeline.json", json.dumps(dict({"doc_check": cmd}, **kw)))
        sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "cfg")
        hook("start", d)
        return d
    d = dcrepo("echo ran > ran.txt"); write(d, "docs/scale.md", "x")
    rc, o = gate(d)
    report(o == {} and os.path.exists(os.path.join(d, "ran.txt")), "doc_check: configured check passes when docs changed (ran, silent)")
    d = dcrepo("echo ROSTER-DRIFT; exit 3"); write(d, "docs/scale.md", "x")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "ROSTER-DRIFT" in o["reason"] and "exited 3" in o["reason"], "doc_check: failing check blocks with its output")
    d = dcrepo("echo ran > ran.txt exit 3"); write(d, "notes.txt", "x")
    rc, o = gate(d)
    report(o == {} and not os.path.exists(os.path.join(d, "ran.txt")), "doc_check: not run when nothing relevant changed")
    d = dcrepo("sleep 5"); write(d, "docs/a.md", "x")
    rc, out, _ = run([sys.executable, "-c", "import sys;sys.path.insert(0,%r);import artlib;artlib.DOC_TIMEOUT=1;import hook;sys.argv=['h','gate'];sys.exit(hook.main(sys.argv))" % HERE],
                     json.dumps({"session_id": "s1", "cwd": d}))
    o = json.loads(out)
    report(rc == 0 and "decision" not in o and "timed out" in o["systemMessage"], "doc_check: timeout fails open with a systemMessage")
    d = mkrepo(); hook("start", d); write(d, "docs/a.md", "x")
    rc, out, _ = hook("gate", d)
    report(rc == 0 and out == "", "doc_check: missing config is silent")
    d = dcrepo("exit 1", doc_check_paths=["data/*"]); write(d, "docs/a.md", "x")
    ok1 = gate(d)[1] == {}
    write(d, "data/x.csv", "x")
    report(ok1 and gate(d)[1].get("decision") == "block", "doc_check_paths overrides the default paths")

    # --- asset ledger (art.py) ---
    def art(d, *a):
        return run([sys.executable, ART] + list(a), cwd=d)

    def sheet_for(d, name, seen_it=True):
        p = write(d, "docs/art/sheets/%s.png" % name, "png")
        if seen_it:
            see(d, p)
        return "docs/art/sheets/%s.png" % name

    def asset_json(d, slug):
        return json.load(open(os.path.join(d, "docs/art/assets", slug + ".json")))

    d = mkrepo(); hook("start", d)
    rc, out, _ = art(d, "new", "crate", "--kind", "prop")
    rc2, _, err2 = art(d, "new", "crate", "--kind", "prop")
    rc3, nx, _ = art(d, "next", "crate")
    rc4, st, _ = art(d, "status")
    report(rc == 0 and os.path.isfile(os.path.join(d, "docs/art/assets/crate.json")) and rc2 == 1 and "already exists" in err2
           and rc3 == 0 and "stage: brief" in nx and "--approved-by-user" in nx and "crate" in st and "brief" in st,
           "art.py new/next/status: creates the ledger, refuses a duplicate, next names the gate, status lists it")

    rc, _, err = art(d, "record", "crate", "--verdict", "pass")
    rc2, _, err2 = art(d, "advance", "crate")
    rc3, _, _ = art(d, "record", "crate", "--verdict", "pass", "--approved-by-user")
    rc4, out4, _ = art(d, "advance", "crate")
    report(rc == 1 and "user-approval gate" in err and len(err.strip().splitlines()) == 1 and rc2 == 1 and "no record" in err2
           and rc3 == 0 and rc4 == 0 and "-> concept" in out4,
           "approval gate: pass without --approved-by-user refused (one line), advance refused with no record, approved pass advances")

    rc, _, err = art(d, "skip", "crate", "--reason", " ")
    art(d, "skip", "crate", "--reason", "user said reuse the old spec")
    rc2, out2, _ = art(d, "advance", "crate")
    rc3, _, err3 = art(d, "advance", "crate")
    report(rc == 1 and rc2 == 0 and "-> spec" in out2 and rc3 == 1 and "no record" in err3,
           "skip with a reason advances; blank reason refused; advance refused on a stage with no record")

    sh = sheet_for(d, "spec1", seen_it=False)
    rc, _, err = art(d, "record", "crate", "--verdict", "fail", "--sheet", sh, "--seen", SEEN_TXT)
    rc2, _, err2 = art(d, "record", "crate", "--verdict", "fail", "--sheet", sh, "--seen", "short")
    rc3, _, err3 = art(d, "record", "crate", "--verdict", "fail", "--seen", SEEN_TXT)
    see(d, os.path.join(d, sh))
    ok_a = rc == 1 and "not opened" in err and rc2 == 1 and ">= 40" in err2 and rc3 == 1 and "--sheet" in err3
    rc, _, err = art(d, "record", "crate", "--verdict", "pass", "--sheet", sh, "--seen", SEEN_TXT)
    report(ok_a and rc == 1 and "needs 2 looks" in err,
           "look gate: unopened sheet, short --seen, missing sheet refused; first-look pass refused (min_looks 2)")
    rc, _, _ = art(d, "record", "crate", "--verdict", "fail", "--sheet", sh, "--seen", SEEN_TXT)
    rc2, _, err2 = art(d, "advance", "crate")
    rc3, _, _ = art(d, "record", "crate", "--verdict", "pass", "--sheet", sh, "--seen", SEEN_TXT)
    rc4, out4, _ = art(d, "advance", "crate")
    report(rc == 0 and rc2 == 1 and "last record is fail" in err2 and rc3 == 0 and rc4 == 0 and "-> model" in out4,
           "min_looks: fail then pass advances; advance refused while the last record is fail")

    art(d, "record", "crate", "--verdict", "fail", "--sheet", sh, "--seen", SEEN_TXT)
    art(d, "record", "crate", "--verdict", "pass", "--sheet", sh, "--seen", SEEN_TXT)
    rc, out, _ = art(d, "advance", "crate")
    a = asset_json(d, "crate")
    report(rc == 0 and "-> engine" in out and [r["verdict"] for r in a["history"] if r["stage"] in ("rig", "clips")] == ["n/a", "n/a"],
           "prop: advance from model lands on engine, rig and clips recorded n/a")
    rc, out, _ = art(d, "next", "crate")
    write(d, ".art-pipeline.json", json.dumps({"engine_capture": "unity-capture --asset {slug}"}))
    rc2, out2, _ = art(d, "next", "crate")
    report("no engine adapter configured" in out and "unity-capture --asset crate" in out2,
           "next at engine: no-adapter line without engine_capture, {slug} substituted with it")

    d = mkrepo(); hook("start", d)
    write(d, ".art-pipeline.json", json.dumps({"stage_outputs": {"spec": ["out/{slug}/*"]}}))
    art(d, "new", "orc", "--kind", "character")
    for _ in range(2):
        art(d, "skip", "orc", "--reason", "pre-approved by aj"); art(d, "advance", "orc")
    now = time.time()
    write(d, "out/orc/spec.json", "s", mtime=now)
    sh = write(d, "docs/art/sheets/o.png", "png", mtime=now - 200); see(d, sh)
    rc, _, err = art(d, "record", "orc", "--verdict", "fail", "--sheet", "docs/art/sheets/o.png", "--seen", SEEN_TXT)
    os.utime(sh, (now + 50, now + 50)); see(d, sh)
    rc2, _, _ = art(d, "record", "orc", "--verdict", "pass", "--sheet", "docs/art/sheets/o.png", "--seen", SEEN_TXT,
                    "--first-look-pass", "trivial single-number spec")
    rc3, out3, _ = art(d, "advance", "orc")
    for v in ("fail", "pass"):
        art(d, "record", "orc", "--verdict", v, "--sheet", "docs/art/sheets/o.png", "--seen", SEEN_TXT)
    rc4, out4, _ = art(d, "advance", "orc")
    rc5, out5, _ = art(d, "advance", "orc")
    report(rc == 1 and "older than" in err and rc2 == 0 and rc3 == 0 and "-> model" in out3 and rc4 == 0 and "-> rig" in out4 and rc5 == 1,
           "stage_outputs freshness enforced; --first-look-pass accepted; character goes model -> rig (not n/a)")

    rc, o = gate(d)
    msg = o.get("systemMessage", "")
    report("decision" not in o and "SKIPPED orc/brief: pre-approved by aj" in msg and "SKIPPED orc/concept" in msg
           and "FIRST-LOOK-PASS orc/spec: trivial single-number spec" in msg,
           "Stop gate: every skip and first-look-pass listed with its reason in a systemMessage")
    rc, out, _ = run([sys.executable, REVIEW, "status"], cwd=d)
    report("SKIPPED orc/brief" in out and "slug" in out and "orc" in out, "review.py status shows the asset notes and table")

    d = mkrepo(); hook("start", d)
    art(d, "new", "rock", "--kind", "set")
    sh = sheet_for(d, "r", seen_it=True)
    art(d, "record", "rock", "--verdict", "pass", "--approved-by-user", "--sheet", sh)
    ok_seen = gate(d)[1] == {}
    hook("start", d)  # same session id, seen-list reset: the sheet is no longer opened
    rc, o = gate(d)
    blocked = o.get("decision") == "block" and "rock/brief" in o["reason"] and "not opened" in o["reason"]
    p = os.path.join(d, "docs/art/assets/rock.json")
    a = json.load(open(p)); a["history"][0]["session"] = "other"; json.dump(a, open(p, "w"))
    ignored = gate(d)[1] == {}
    report(ok_seen and blocked and ignored,
           "Stop gate blocks a pass record whose sheet was not opened this session (other sessions' records ignored)")

    # 18-20 run.sh
    env_np = {"PATH": "", "ART_PIPELINE_PYTHON": ""}
    for ev, want in (("start", "NOT armed"), ("gate", "did NOT run")):
        rc, out, _ = run([SH, RUN, ev], "", env=env_np)
        try:
            ok = rc == 0 and want in json.loads(out)["systemMessage"]
        except Exception:
            ok = False
        report(ok, f"run.sh {ev}: no interpreter -> systemMessage, exit 0")
    rc, out, _ = run([SH, RUN, "seen"], "", env=env_np)
    report(rc == 0 and out == "", "run.sh seen: no interpreter -> exit 0 (start/gate already announce it)")
    d = mkrepo()
    rc, out, _ = run([SH, RUN, "start"], json.dumps({"session_id": "s1", "cwd": d}))
    report(rc == 0 and "art-pipeline:" in out, "run.sh start with a real interpreter reaches hook.py")
finally:
    for t in TMP:
        shutil.rmtree(t, ignore_errors=True)

print("\n" + "=" * 42)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
