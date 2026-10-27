#!/usr/bin/env python3
"""checks/delegation.py - the delegation part: the helper agents, autosave, the audit hooks, stallcheck (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/delegation.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: delegation")
print("=" * 43)
print()


# --- the delegate reminder fires after ExitPlanMode -------------------------------------------
code, out, err = run_hook("delegate", "")
if '"hookEventName":"PostToolUse"' in out and "@house-rules:builder" in out:
    report("PASS", "delegate reminds Claude to hand the plan to the builder subagent")
    print("          names @house-rules:builder and carries the right hookEventName")
else:
    report("FAIL", "delegate reminds Claude to hand the plan to the builder subagent")
    print(f"          got: {out}")
if '"matcher": "ExitPlanMode"' in hooks_json_text and 'run.sh\\" delegate' in hooks_json_text:
    report("PASS", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json wires ExitPlanMode to run.sh delegate")
else:
    report("FAIL", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json does not wire ExitPlanMode to run.sh delegate")
for ev, needle in (
    ("delegate", "delegate"),
):
    snippet = (
        "import sys, hook\n"
        "import house_rules.core as core\n"
        "real_emit = hook.emit\n"
        "state = {'first': True}\n"
        "def one_shot_boom(obj):\n"
        "    if state['first']:\n"
        "        state['first'] = False\n"
        "        raise OSError('simulated internal failure')\n"
        "    real_emit(obj)\n"
        "hook.emit = core.emit = hook.docs.emit = hook.safe_git.emit = one_shot_boom\n"  # #358: the parts hold their own emit
        "hook.delegation.emit = hook.design_loop.emit = hook.writing.emit = one_shot_boom\n"  # #359: and so do these three
        f"sys.exit(hook.main(['hook.py', '{ev}']))\n"
    )
    # stdin must be closed: these handlers really do read the payload now, and an inherited
    # stdin would block the whole suite waiting for input that never comes.
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=HERE,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if ev == "scope":
        spoke = bool(out.strip())
    else:
        spoke = "systemMessage" in out or err.strip()
    if proc.returncode == 0 and spoke:
        report("PASS", f"an internal crash in {ev} is announced rather than swallowed")
        print("          exits 0 without obstructing, but does not go quiet")
    else:
        report("FAIL", f"an internal crash in {ev} is announced rather than swallowed")
        print(f"          exit {proc.returncode}, stdout {out[:120]!r}, stderr {err[:120]!r}")
_, out, _ = run_hook("delegate", json.dumps({"tool_name": "ExitPlanMode", "tool_input": {
    "plan": "Port the stock page to GitHub Pages as a static site."}}))
pv_case("delegate: an approved port plan with no keep/change/drop inventory gets the parity note",
        "carries no keep/change/drop" in out, "note=%s" % ("carries no keep/change/drop" in out))
_, out, _ = run_hook("delegate", json.dumps({"tool_name": "ExitPlanMode", "tool_input": {
    "plan": "Port the page. Parity: keep search, drop server sync."}}))
pv_case("delegate: a port plan that carries its inventory does not", "carries no keep/change/drop" not in out,
        "note=%s" % ("carries no keep/change/drop" in out))

# audit: a subagent's uncommitted files are named, because the parent owns that commit.
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
_sub = _hand_transcript("subagent-wrote", [
    json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "w1", "name": "Write", "input": {"file_path": os.path.join(_r, "a.py")}}]}}),
])
_audit_snippet = "import sys, hook\nprint(hook.delegation._audit_report(sys.argv[1]))\n"  # #359: the audit report lives in the delegation part
_p = subprocess.run([sys.executable, "-c", _audit_snippet, _sub], cwd=HERE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=_project_env(_r))
_aout = _p.stdout.decode("utf-8", "replace")
commit_case(
    "audit: a file the subagent wrote that is still uncommitted is named, and the commit is the parent's",
    "uncommitted: a.py" in _aout and "The commit is yours now" in _aout,
    "audit: %r" % _aout[-200:],
)

# subagentcommit: a subagent cannot finish with files it wrote still uncommitted - it is sent
# back once (decision "block", probed on CLI 2.1.284), and the retry is let through.
def _subagent_stop(paths, active=False, **env_extra):
    tr = _hand_transcript("subcommit-%d" % len(os.listdir(_HAND_ROOT)), [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "s%d" % i, "name": "Write", "input": {"file_path": p}}]}})
        for i, p in enumerate(paths)
    ])
    payload = json.dumps({"hook_event_name": "SubagentStop", "agent_type": "house-rules:builder",
                          "agent_transcript_path": tr, "stop_hook_active": active})
    return run_hook("subagentcommit", payload, env=_project_env(_FIXTURE_ROOT, **env_extra))[1]


_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")])
commit_case(
    "subagentcommit: a subagent finishing with a file it wrote still uncommitted is sent back to commit it",
    '"decision": "block"' in out.replace('":"', '": "') and "a.py" in out and "commit on your own branch" in out,
    "stdout: %r" % out[:160],
)
commit_case(
    "subagentcommit: its instruction respects a 'do not run git' delegation",
    "told you not to run git" in out,
    "stdout: %r" % out[:160],
)
out = _subagent_stop([os.path.join(_r, "a.py")], active=True)
commit_case(
    "subagentcommit: the retry (stop_hook_active) is never blocked again - it only reports",
    '"decision"' not in out and "still uncommitted after being asked once" in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")])
commit_case(
    "subagentcommit: a subagent that committed what it wrote finishes without being held",
    '"decision"' not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")], HOUSE_RULES_COMMIT_CHECK="off")
commit_case(
    "subagentcommit: HOUSE_RULES_COMMIT_CHECK=off switches it off",
    out.strip() == "",
    "stdout: %r" % out[:160],
)
# The project dir is _FIXTURE_ROOT (not a repo); the file lives in its own repo, like a worktree.
_wt = _commit_repo("worktree-agent-1", committed=["w.py"], dirty=["w.py"])
out = _subagent_stop([os.path.join(_wt, "w.py")])
commit_case(
    "subagentcommit: a file in a separate worktree is judged in that worktree's repo, not the project dir",
    '"decision"' in out and "w.py" in out and "worktree-agent-1" in out,
    "stdout: %r" % out[:200],
)
commit_case(
    "subagentcommit is wired to SubagentStop in hooks.json",
    'run.sh\\" subagentcommit' in hooks_json_text,
    "hooks.json SubagentStop entry",
)


def _as_repo(branch, backdate_minutes=0):
    bare = tempfile.mkdtemp(prefix="house-rules-origin-", dir=_FIXTURE_ROOT)
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    d = tempfile.mkdtemp(prefix="house-rules-autosave-", dir=_FIXTURE_ROOT)
    _as_git(d, "init", "-q", "-b", branch)
    with open(os.path.join(d, "base.py"), "w", encoding="utf-8") as f:
        f.write("base\n")
    _as_git(d, "add", "-A")
    env = dict(os.environ)
    if backdate_minutes:
        when = "@%d +0000" % int(time.time() - backdate_minutes * 60)
        env.update(GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    _as_git(d, "commit", "-q", "-m", "base", env=env)
    _as_git(d, "remote", "add", "origin", bare)
    return d, bare


def _as_payload(event, tool, path, cwd):
    return json.dumps({"hook_event_name": event, "tool_name": tool, "session_id": "s1", "cwd": cwd,
                       "tool_input": {"file_path": path} if tool != "Bash" else {"command": "true"}})


def _as_env(**extra):
    e = _project_env(_FIXTURE_ROOT, **extra)
    e.pop("HOUSE_RULES_AUTOSAVE", None)
    e.update(extra)
    return e


def _as_ref(d, branch):
    return _as_git(d, "rev-parse", "--verify", "-q", "refs/house-rules/autosave/" + branch)


def _as_remote_ref(bare, branch):
    return _as_git(bare, "rev-parse", "--verify", "-q", "refs/house-rules/autosave/" + branch)


_d, _bare = _as_repo("worktree-agent-x")
_head0 = _as_git(_d, "rev-parse", "HEAD")
_p = _as_write(_d, "new.py")
_t0 = time.time()
_, out, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _p, _d), env=_as_env())
out_first_autosave = out
_elapsed = time.time() - _t0
_local = _as_ref(_d, "worktree-agent-x")
commit_case(
    "autosave: an edit on a worktree-agent- branch saves an untracked file to the autosave ref and pushes it",
    bool(_local) and "new.py" in _as_git(_d, "ls-tree", "--name-only", _local)
    and _as_remote_ref(_bare, "worktree-agent-x") == _local,
    "local %s, origin %s, out %r" % (_local[:9], _as_remote_ref(_bare, "worktree-agent-x")[:9], out[:120]),
)
commit_case(
    "autosave: the branch, the real index and the working tree are left exactly as they were",
    _as_git(_d, "rev-parse", "HEAD") == _head0 and _as_git(_d, "diff", "--cached", "--name-only") == ""
    and _as_git(_d, "status", "--porcelain") == "?? new.py",
    "status %r" % _as_git(_d, "status", "--porcelain"),
)
commit_case("autosave: one edit stays well inside the 10 s hook budget", _elapsed < 5, "took %.2fs" % _elapsed)
_p = _as_write(_d, "new.py", "y\n")
run_hook("autosave", _as_payload("PostToolUse", "Edit", _p, _d), env=_as_env())
_local2 = _as_ref(_d, "worktree-agent-x")
_rate_ok = _local2 != _local and _as_remote_ref(_bare, "worktree-agent-x") == _local
_stamp = os.path.join(_as_git(_d, "rev-parse", "--absolute-git-dir"), "house-rules-autosave-worktree-agent-x.pushed")
with open(_stamp, "w", encoding="utf-8") as f:
    f.write("%s %s" % (time.time() - 120, _local))
_p = _as_write(_d, "new.py", "z\n")
run_hook("autosave", _as_payload("PostToolUse", "Edit", _p, _d), env=_as_env())
commit_case(
    "autosave: pushes at most once a minute; the local ref still moves, and the next push after the window catches up",
    _rate_ok and _as_remote_ref(_bare, "worktree-agent-x") == _as_ref(_d, "worktree-agent-x"),
    "second edit local-only: %s; after the window origin matches: %s"
    % (_rate_ok, _as_remote_ref(_bare, "worktree-agent-x") == _as_ref(_d, "worktree-agent-x")),
)
_quiet = []
for _br in ("main", "claude/x"):
    _dq, _ = _as_repo(_br)
    _pq = _as_write(_dq, "new.py")
    _, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
    if _as_ref(_dq, _br) or oq.strip():
        _quiet.append("%s: ref %r, out %r" % (_br, _as_ref(_dq, _br), oq[:80]))
_dq, _ = _as_repo("worktree-agent-off")
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env(HOUSE_RULES_AUTOSAVE="off"))
if _as_ref(_dq, "worktree-agent-off") or oq.strip():
    _quiet.append("HOUSE_RULES_AUTOSAVE=off still acted: out %r" % oq[:80])
commit_case(
    "autosave: does nothing on main, on a claude/ branch, or with HOUSE_RULES_AUTOSAVE=off",
    not _quiet, "; ".join(_quiet) or "no ref and no output in all three",
)
# .git/HEAD fast path (2.48.0): a branch that is not worktree-agent-* is ruled out by reading
# .git/HEAD, so no git subprocess is spawned. The probe counts subprocess.Popen constructions
# (subprocess.run goes through Popen) while running hook.py unmodified.
_SPAWN_PROBE = (
    "import sys, subprocess, runpy\n"
    "n = [0]\n"
    "orig = subprocess.Popen.__init__\n"
    "def counting(self, *a, **k):\n"
    "    n[0] += 1\n"
    "    orig(self, *a, **k)\n"
    "subprocess.Popen.__init__ = counting\n"
    "hook, event = sys.argv[1], sys.argv[2]\n"
    "sys.argv = [hook, event]\n"
    "try:\n"
    "    runpy.run_path(hook, run_name='__main__')\n"
    "finally:\n"
    "    sys.stderr.write('SPAWNS=%d' % n[0])\n"
)


def _as_spawns(event, payload, env):
    proc = subprocess.run([sys.executable, "-c", _SPAWN_PROBE, HOOK, event], input=payload.encode("utf-8"),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    m = re.search(r"SPAWNS=(\d+)", proc.stderr.decode("utf-8", "replace"))
    return (int(m.group(1)) if m else -1), proc.stdout.decode("utf-8", "replace")


_fast = []
for _ev in ("autosave", "commitgate"):
    _dq, _ = _as_repo("main")
    _pq = _as_write(_dq, "new.py")
    _n, _o = _as_spawns(_ev, _as_payload("PostToolUse" if _ev == "autosave" else "PreToolUse", "Write", _pq, _dq), _as_env())
    if _n != 0 or _o.strip():
        _fast.append("%s on main: %d spawns, out %r" % (_ev, _n, _o[:60]))
commit_case(
    "autosave/commitgate: a non-subagent branch is ruled out from .git/HEAD with zero git subprocesses",
    not _fast, "; ".join(_fast) or "0 spawns and no output on main for both handlers",
)
_dq, _ = _as_repo("worktree-agent-fast")
_pq = _as_write(_dq, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), _as_env())
commit_case(
    "autosave: a worktree-agent- branch still takes the full path after the fast check (unchanged behaviour)",
    _n > 0 and bool(_as_ref(_dq, "worktree-agent-fast")),
    "%d spawns, autosave ref %r" % (_n, _as_ref(_dq, "worktree-agent-fast")[:9]),
)
_dq, _ = _as_repo("worktree-agent-det")
_as_git(_dq, "checkout", "-q", "--detach")
_pq = _as_write(_dq, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), _as_env())
commit_case(
    "autosave: a detached HEAD spawns no git subprocess and saves nothing",
    _n == 0 and not _o.strip() and not _as_ref(_dq, "worktree-agent-det"),
    "%d spawns, out %r" % (_n, _o[:60]),
)
_dq, _ = _as_repo("main")
_wt = os.path.join(_FIXTURE_ROOT, "wt-agent-%d" % int(time.time() * 1000))
_as_git(_dq, "worktree", "add", "-q", "-b", "worktree-agent-wt", _wt)
_wf_is_file = os.path.isfile(os.path.join(_wt, ".git"))
_pq = _as_write(_wt, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _wt), _as_env())
_wt2 = os.path.join(_FIXTURE_ROOT, "wt-plain-%d" % int(time.time() * 1000))
_as_git(_dq, "worktree", "add", "-q", "-b", "feature-plain", _wt2)
_pq2 = _as_write(_wt2, "new.py")
_n2, _o2 = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq2, _wt2), _as_env())
commit_case(
    "autosave: a linked worktree (.git is a file) is resolved for both branch kinds",
    _wf_is_file and _n > 0 and bool(_as_ref(_wt, "worktree-agent-wt")) and _n2 == 0 and not _o2.strip(),
    ".git file %s; agent branch: %d spawns, ref %r; plain branch: %d spawns" % (_wf_is_file, _n, _as_ref(_wt, "worktree-agent-wt")[:9], _n2),
)
_dq, _ = _as_repo("worktree-agent-noreach")
_as_git(_dq, "remote", "set-url", "origin", os.path.join(_FIXTURE_ROOT, "no-such-origin.git"))
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
oq_unreach = oq
commit_case(
    "autosave: an unreachable origin is said out loud, and the save is still kept locally",
    "could not push refs/house-rules/autosave/worktree-agent-noreach" in oq and bool(_as_ref(_dq, "worktree-agent-noreach")),
    "out %r" % oq[:160],
)
_dq, _ = _as_repo("worktree-agent-old", backdate_minutes=20)
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
oq_checkpoint = oq
_dfresh, _ = _as_repo("worktree-agent-fresh")
_pf = _as_write(_dfresh, "new.py")
run_hook("autosave", _as_payload("PostToolUse", "Write", _pf, _dfresh), env=_as_env())
commit_case(
    "autosave: 10 minutes without a commit makes the hook commit for the subagent; a fresh commit does not",
    _as_git(_dq, "log", "-1", "--format=%s") == "wip: checkpoint - 10 min without a commit"
    and _as_git(_dq, "status", "--porcelain") == "" and "committed 1 file(s)" in oq
    and _as_git(_dfresh, "log", "-1", "--format=%s") == "base",
    "old: %r, status %r; fresh: %r" % (_as_git(_dq, "log", "-1", "--format=%s"),
                                       _as_git(_dq, "status", "--porcelain"), _as_git(_dfresh, "log", "-1", "--format=%s")),
)
# #405: the commit the hook makes for a helper credits aj's agent, with no Claude trailer or session link.
_wip_body = _as_git(_dq, "log", "-1", "--format=%B")
_wip_credit = [w for w in ("Co-Authored-By", "anthropic", "Claude-Session", "claude" + ".ai") if w.lower() in _wip_body.lower()]
commit_case(
    "autosave: the hook's own commit ends with Committed by AJ's agent and carries no Claude credit",
    _wip_body.strip().endswith("Committed by AJ's agent") and not _wip_credit,
    "body %r, credit found %r" % (_wip_body[-120:], _wip_credit),
)

_dg, _ = _as_repo("worktree-agent-gate")
_as_write(_dg, "a.py")
_pg = _as_write(_dg, "b.py")
_, o2, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
_as_write(_dg, "c.py")
_, o3, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
commit_case(
    "commitgate: 2 uncommitted files pass; 3 block the edit, naming the files, with nothing committed",
    o2.strip() == "" and '"permissionDecision":"deny"' in o3 and "a.py" in o3 and "c.py" in o3
    and _as_git(_dg, "log", "-1", "--format=%s") == "base",
    "2 files: %r; 3 files: %r" % (o2[:60], o3[:140]),
)
_, o4, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
commit_case(
    "commitgate: asked once and ignored, the hook commits everything itself and lets the edit through",
    _as_git(_dg, "log", "-1", "--format=%s") == "wip: autosave - subagent did not commit when asked"
    and _as_git(_dg, "status", "--porcelain") == "" and "deny" not in o4 and "committed 3 file(s)" in o4,
    "last commit %r, out %r" % (_as_git(_dg, "log", "-1", "--format=%s"), o4[:140]),
)
_gq = []
_dm, _ = _as_repo("main")
for _n in ("a.py", "b.py", "c.py", "d.py"):
    _pm = _as_write(_dm, _n)
_, om, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pm, _dm), env=_as_env())
if om.strip():
    _gq.append("main: %r" % om[:80])
_db, _ = _as_repo("worktree-agent-bash")
for _n in ("a.py", "b.py", "c.py"):
    _as_write(_db, _n)
_, ob, _ = run_hook("commitgate", _as_payload("PreToolUse", "Bash", _db, _db), env=_as_env())
if ob.strip():
    _gq.append("Bash: %r" % ob[:80])
commit_case(
    "commitgate: never gates main, and never gates Bash (the subagent needs it to commit)",
    not _gq, "; ".join(_gq) or "both passed with no output",
)

_ds, _bs = _as_repo("worktree-agent-done")
_ps = _as_write(_ds, "s.py")
run_hook("autosave", _as_payload("PostToolUse", "Write", _ps, _ds), env=_as_env())
_had = bool(_as_remote_ref(_bs, "worktree-agent-done"))
_as_git(_ds, "add", "-A")
_as_git(_ds, "commit", "-q", "-m", "feat: s")
out = run_hook("subagentcommit", json.dumps({
    "hook_event_name": "SubagentStop", "agent_type": "house-rules:builder", "stop_hook_active": False,
    "agent_transcript_path": _hand_transcript("autosave-done", [json.dumps({"type": "assistant", "message": {
        "content": [{"type": "tool_use", "id": "d1", "name": "Write", "input": {"file_path": _ps}}]}})])}),
    env=_project_env(_FIXTURE_ROOT))[1]
commit_case(
    "subagentcommit: a clean finish deletes the autosave ref locally and on origin",
    _had and not _as_ref(_ds, "worktree-agent-done") and not _as_remote_ref(_bs, "worktree-agent-done"),
    "on origin before: %s; after: local %r origin %r; out %r"
    % (_had, _as_ref(_ds, "worktree-agent-done"), _as_remote_ref(_bs, "worktree-agent-done"), out[:80]),
)
_dr, _ = _as_repo("worktree-agent-retry")
_pr = _as_write(_dr, "r.py")
out = _subagent_stop([_pr], active=True)
_dc, _ = _as_repo("claude/retry")
_pc = _as_write(_dc, "r.py")
out_c = _subagent_stop([_pc], active=True)
commit_case(
    "subagentcommit: a retry still uncommitted is committed by the hook on a worktree-agent- branch, never on claude/",
    _as_git(_dr, "log", "-1", "--format=%s") == "wip: autosave - subagent did not commit when asked"
    and _as_git(_dr, "status", "--porcelain") == "" and "committed 1 file(s)" in out
    and _as_git(_dc, "log", "-1", "--format=%s") == "base" and _as_git(_dc, "status", "--porcelain") == "?? r.py",
    "worktree-agent: %r; claude/: %r" % (_as_git(_dr, "log", "-1", "--format=%s"), _as_git(_dc, "log", "-1", "--format=%s")),
)

_dmain, _ = _as_repo("main")
_sweep_old = os.path.join(_FIXTURE_ROOT, "wt-sweep-old")
_sweep_new = os.path.join(_FIXTURE_ROOT, "wt-sweep-new")
_sweep_mine = os.path.join(_FIXTURE_ROOT, "wt-sweep-claude")
_as_git(_dmain, "worktree", "add", "-q", "-b", "worktree-agent-old", _sweep_old)
_as_git(_dmain, "worktree", "add", "-q", "-b", "worktree-agent-new", _sweep_new)
_as_git(_dmain, "worktree", "add", "-q", "-b", "claude/sweep", _sweep_mine)
_long_ago = time.time() - 20 * 60
for _wt in (_sweep_old, _sweep_mine):
    os.utime(_as_write(_wt, "left.py"), (_long_ago, _long_ago))
_as_write(_sweep_new, "live.py")
_, osw, _ = run_hook("worktreesweep", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi",
                                                  "cwd": _dmain, "session_id": "s1"}),
                     env=_project_env(_dmain))
commit_case(
    "worktreesweep: the parent commits a subagent worktree left untouched 10+ min, and leaves a live one and claude/ alone",
    _as_git(_sweep_old, "log", "-1", "--format=%s") == "wip: parent checkpoint of subagent work"
    and _as_git(_sweep_old, "status", "--porcelain") == "" and "worktree-agent-old" in osw
    and _as_git(_sweep_new, "status", "--porcelain") == "?? live.py"
    and _as_git(_sweep_mine, "status", "--porcelain") == "?? left.py",
    "old: %r; live: %r; claude/: %r; out %r" % (_as_git(_sweep_old, "log", "-1", "--format=%s"),
                                                _as_git(_sweep_new, "status", "--porcelain"),
                                                _as_git(_sweep_mine, "status", "--porcelain"), osw[:100]),
)
_, osw2, _ = run_hook("worktreesweep", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi",
                                                   "cwd": _dmain}), env=_project_env(_dmain))
commit_case(
    "worktreesweep: says nothing when there is nothing to commit",
    osw2.strip() == "", "out %r" % osw2[:100],
)
_multi = []
for _name, _o in (("autosave", out_first_autosave), ("autosave unreachable origin", oq_unreach),
                  ("autosave checkpoint", oq_checkpoint), ("commitgate deny", o3),
                  ("commitgate fallback", o4), ("worktreesweep", osw)):
    try:
        json.loads(_o)
    except ValueError:
        _multi.append("%s: %r" % (_name, _o[:100]))
commit_case(
    "autosave, commitgate and worktreesweep each print exactly one JSON object per call",
    not _multi, "; ".join(_multi) or "all six outputs parse as one object",
)
commit_case(
    "autosave, commitgate and worktreesweep are wired in hooks.json",
    all('run.sh\\" %s' % e in hooks_json_text for e in ("autosave", "commitgate", "worktreesweep")),
    "hooks.json PostToolUse / PreToolUse / UserPromptSubmit entries",
)

commit_case(
    "the builder and archivist commit as they go, not only if asked",
    all(
        phrase in read(os.path.join(HERE, "..", "agents", n))
        and "only if asked to commit" not in read(os.path.join(HERE, "..", "agents", n))
        for n, phrase in (("builder.md", "Commit as you go"), ("archivist.md", "Commit each finished piece as you go"))
    ),
    "agents/builder.md, agents/archivist.md",
)
for _restatement in [RESTATEMENTS[_i] for _i in (5,)]:  # delegation
    _source_text = _restatement.source()
    if _restatement.case_sensitive:
        _in_rules = lambda p: p in rules_text
        _in_source = lambda p: p in _source_text
    else:
        _in_rules = lambda p: p.lower() in rules_text.lower()
        _in_source = lambda p: p.lower() in _source_text.lower()
    _missing_rules = [p for p in _restatement.phrases if not _in_rules(p)]
    _missing_source = [
        p for p in list(_restatement.phrases) + list(_restatement.emitted_only) if not _in_source(p)
    ]
    if not _missing_rules and not _missing_source:
        report("PASS", f"{_restatement.name} matches the rules document, both ways")
        print("          every phrase appears in house-rules.md AND in what it emits")
    else:
        report("FAIL", f"{_restatement.name} matches the rules document, both ways")
        if _missing_rules:
            print(f"          missing from house-rules.md: {'; '.join(_missing_rules)}")
        if _missing_source:
            print(f"          missing from the emitted restatement: {'; '.join(_missing_source)}")

# --- the delegation nudge fires when a plan is approved ----------------------------------------
def check_delegate(title, empty_path):
    env = dict(os.environ)
    if empty_path:
        env["PATH"] = ""
    code, out, err = run_hook("delegate", "", env=env)
    bad = []
    if '"hookEventName":"PostToolUse"' not in out:
        bad.append("wrong or missing hookEventName")
    if "@house-rules:builder" not in out:
        bad.append("it does not name the builder subagent")
    if "one file" not in out or "three steps or fewer" not in out:
        bad.append("the skip-it exception is not stated as a count (one file, three steps)")
    if "proactiv" not in out:
        bad.append("it does not say the delegation is authorized for proactive use")
    if not bad:
        report("PASS", title)
        print(f"          {len(out)} characters of delegation nudge injected")
    else:
        report("FAIL", title)
        print(f"          {'; '.join(bad)}")


check_delegate("the delegation nudge is emitted when plan mode is exited", False)
check_delegate("the delegation nudge still works with PATH empty (it depends on nothing)", True)

# --- delegate is registered on ExitPlanMode, and nowhere else ---------------------------------
deldrift = []
if '"matcher": "ExitPlanMode"' not in hooks_json_text:
    deldrift.append("hooks.json has no ExitPlanMode matcher")
if "@house-rules:builder" not in rules_text:
    deldrift.append("house-rules.md no longer states the delegation rule")
if not deldrift:
    report("PASS", "delegate runs on ExitPlanMode and matches the rules document")
    print("          the nudge fires at the plan boundary and names the agent the rules name")
else:
    report("FAIL", "delegate runs on ExitPlanMode and matches the rules document")
    print(f"          {'; '.join(deldrift)}")

# --- house-rules.md states the delegation rule exactly once (F6 merge) -----------------------
heading_hits = [m for m in re.finditer(r"^## .*delegat.*$", rules_text, re.IGNORECASE | re.MULTILINE)]
if len(heading_hits) == 1:
    report("PASS", "house-rules.md states the delegation rule exactly once")
    print(f"          one heading: {heading_hits[0].group(0)}")
else:
    report("FAIL", "house-rules.md states the delegation rule exactly once")
    print(f"          found {len(heading_hits)} delegation headings: {[m.group(0) for m in heading_hits]}")


# --- the tier agents exist, each pinned to its model, with the tool allowlist the plan set -------
TIER_TOOLS = {
    "scout": ["Read", "Grep", "Glob"],
    "builder": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "reviewer": ["Read", "Grep", "Glob", "Bash"],
    "editor": ["Read"],
}
agentdrift = []
for _name, _model in TIERS.items():
    _f = os.path.join(AGENTS_DIR, _name + ".md")
    if not os.path.isfile(_f):
        agentdrift.append(f"agents/{_name}.md is missing")
        continue
    _t = read(_f)
    if not re.search(rf"^model: {_model}$", _t, re.MULTILINE):
        agentdrift.append(f"{_name}.md does not pin model: {_model}")
    if not re.search(rf"^name: {_name}$", _t, re.MULTILINE):
        agentdrift.append(f"{_name}.md has no name: {_name}")
    _tm = re.search(r"^tools:\s*(.+)$", _t, re.MULTILINE)
    _got = [x.strip() for x in _tm.group(1).split(",")] if _tm else []
    if _got != TIER_TOOLS[_name]:
        agentdrift.append(f"{_name}.md tools are {_got}, expected {TIER_TOOLS[_name]}")
    if "Agent" in _got:
        agentdrift.append(f"{_name}.md allows the Agent tool, so it could start subagents")
    _body = _t.split("---", 2)[-1].strip().splitlines()
    if len(_body) > 15:
        agentdrift.append(f"{_name}.md body is {len(_body)} lines, the limit is 15")
    for dead in ["hooks", "mcpServers", "permissionMode"]:
        if re.search(rf"^{dead}:", _t, re.MULTILINE):
            agentdrift.append(f"{_name}.md sets {dead}, which plugin subagents ignore")
if os.path.isfile(os.path.join(AGENTS_DIR, "executor.md")):
    agentdrift.append("agents/executor.md still exists, it was retired")
if not agentdrift:
    report("PASS", "the scout, builder, reviewer and editor agents exist, pinned to haiku, sonnet, opus and sonnet")
    print("          short tool allowlists, no Agent tool, bodies of 15 lines or fewer, executor.md gone")
else:
    report("FAIL", "the scout, builder, reviewer and editor agents exist, pinned to haiku, sonnet, opus and sonnet")
    print(f"          {'; '.join(agentdrift)}")

# --- no live file still names the retired executor agent ----------------------------------------
_stale = []
_skip_dirs = {".git", "node_modules", "__pycache__", "sessions", "archive", "plans", "generated", "worktrees"}
for _dp, _dns, _fns in os.walk(ROOT):
    _dns[:] = [d for d in _dns if d not in _skip_dirs and d != "6-decisions"]
    for _fn in _fns:
        if not _fn.endswith((".md", ".py", ".json", ".sh", ".bat", ".ps1", ".yml", ".html")):
            continue
        _fp = os.path.join(_dp, _fn)
        if os.path.abspath(_fp) == os.path.abspath(__file__):
            continue
        try:
            if "house-rules:executor" in read(_fp):
                _stale.append(os.path.relpath(_fp, ROOT))
        except OSError:
            pass
if not _stale:
    report("PASS", "no live file still names house-rules:executor")
    print("          docs/sessions, docs/archive, docs/plans and past Decisions entries are history and not scanned")
else:
    report("FAIL", "no live file still names house-rules:executor")
    print(f"          still named in: {', '.join(_stale)}")

# --- archivist.md does not claim the rules are already in its context, and carries a digest ----
# A clean spawn was asked directly and answered no: SessionStart additionalContext does not
# reach subagents. The tier files carry no digest (the subagentrules hook injects the core);
# archivist.md keeps its own, so only it is checked here.
digestdrift = []
if not os.path.isfile(ARCHIVIST):
    digestdrift.append("agents/archivist.md is missing")
else:
    agent_text = read(ARCHIVIST)
    if "already in this session" in agent_text.lower():
        digestdrift.append("archivist.md still claims the rules are already in its context")
    for phrase in [
        "not injected",
        "hand over a command you have not run",
        "step-card format",
        "commit messages",
    ]:
        if phrase.lower() not in agent_text.lower():
            digestdrift.append(f"archivist.md digest is missing: {phrase!r}")
if not digestdrift:
    report("PASS", "archivist.md carries its own rules digest instead of assuming inherited context")
    print("          no 'already in this session' claim; the digest covers the load-bearing rules")
else:
    report("FAIL", "archivist.md carries its own rules digest instead of assuming inherited context")
    print(f"          {'; '.join(digestdrift)}")

# --- the scout and builder descriptions authorize proactive use ----------------------------------------
_proactive = [n for n in ("scout", "builder")
              if "proactiv" not in read(os.path.join(AGENTS_DIR, n + ".md")).lower()]
if not _proactive:
    report("PASS", "the scout and builder descriptions authorize proactive use")
    print('          description contains "proactively", satisfying the Agent tool\'s own gate')
else:
    report("FAIL", "the scout and builder descriptions authorize proactive use")
    print(f'          {", ".join(_proactive)}: description has no "proactively" (or similar) wording')

# --- scope's go-ahead clause closes the no-plan-mode delegation gap --------------------------
# delegate only fires on ExitPlanMode. Auto and accept-edits sessions never cross that
# boundary - and house-rules.md says the delegation rule covers them anyway - so a go-ahead
# typed into an ordinary session used to get no delegation reminder at all. The prompt text is
# the only stateless place to notice it.
def scope_text(prompt):
    payload = json.dumps(
        {"session_id": "verify", "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    )
    code, out, err = run_hook("scope", payload)
    try:
        return code, json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return code, ""


goahead = []
for prompt in ("go ahead", "implement it in two groups", "do it", "proceed", "ship it",
               "make the changes", "apply those fixes", "execute the plan"):
    code, text = scope_text(prompt)
    if code != 0:
        goahead.append(f"{prompt!r} exited {code} - scope must never exit non-zero")
    if "@house-rules:builder" not in text:
        goahead.append(f"{prompt!r} is a go-ahead but got no delegation clause")
for prompt in ("what does this function do?", "explain the guard handler",
               "why did the suite fail?"):
    code, text = scope_text(prompt)
    if "@house-rules:builder" in text:
        goahead.append(f"{prompt!r} is a question, not a go-ahead, but got the clause")
if not goahead:
    report("PASS", "scope adds the delegation clause on a go-ahead and not on a question")
    print("          closes the gap where delegate never fires outside plan mode")
else:
    report("FAIL", "scope adds the delegation clause on a go-ahead and not on a question")
    for g in goahead:
        print(f"          {g}")

# The clause restates the rule, so it is drift-checked in both directions like the delegate
# reminder - and it must never be able to take the prompt down with it.
clause_drift = []
_, goahead_text = scope_text("go ahead and implement it")
for phrase in ("@house-rules:builder", "proactiv", "one file", "three steps or fewer"):
    if phrase.lower() not in goahead_text.lower():
        clause_drift.append(f"{phrase!r} missing from the emitted go-ahead clause")
    if phrase.lower() not in rules_text.lower():
        clause_drift.append(f"{phrase!r} missing from rules/house-rules.md")
for label, payload in (
    ("empty payload", ""),
    ("unparseable payload", "not json {{{ go ahead"),
    ("no prompt field", '{"session_id":"v","hook_event_name":"UserPromptSubmit"}'),
    ("prompt field with an escaped quote", '{"prompt":"go ahead \\"now\\" implement it"}'),
):
    code, out, err = run_hook("scope", payload)
    if code != 0:
        clause_drift.append(f"{label} exited {code} - this ERASES the user's prompt")
    if "additionalContext" not in out:
        clause_drift.append(f"{label} emitted no reminder at all: {out[:80]!r}")
if not clause_drift:
    report("PASS", "the go-ahead clause matches the rules and cannot erase a prompt")
    print("          same phrases as house-rules.md; every failure path still exits 0 with a reminder")
else:
    report("FAIL", "the go-ahead clause matches the rules and cannot erase a prompt")
    for c in clause_drift:
        print(f"          {c}")


def _transcript(agent_id, lines):
    d = os.path.join(_SUB_ROOT, "sess1", "subagents")
    if not os.path.isdir(d):
        os.makedirs(d)
    path = os.path.join(d, "agent-%s.jsonl" % agent_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _assistant(model=None, content=None):
    msg = {"role": "assistant", "content": content if content is not None else []}
    if model:
        msg["model"] = model
    return json.dumps({"type": "assistant", "message": msg})


_transcript("sonnet", [json.dumps({"type": "user"}), _assistant("claude-sonnet-4-5-20250929"),
                       _assistant("claude-sonnet-4-5-20250929")])
_transcript("opus", [_assistant("claude-opus-5")])
_transcript("nomodel", [_assistant()])
_transcript("notools", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I've launched the fix."}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I'll report back once it's done."}]),
])
_transcript("deferral", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Edit"}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I'll report back shortly."}]),
])
_transcript("normal", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Edit"}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Bash"},
                                               {"type": "text", "text": "Done - ran the tests, all green."}]),
])
def _user_result(tool_use_id, is_error=False):
    return json.dumps({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "tool_use_id": tool_use_id, "is_error": is_error}]},
    })


# audit1: the case the audit summary exists for - one ok command, one failing command, one
# write, seen from the transcript itself, never from what the subagent says about itself.
_transcript("audit1", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                "input": {"command": "pytest -q"}}]),
    _user_result("t1", is_error=False),
    _assistant("claude-sonnet-4-5-20250929", [
        {"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": "/proj/a.py"}},
        {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "false"}},
    ]),
    _user_result("t3", is_error=True),
])
# auditbig: 45 commands, to prove the 40-command cap and the "N more" line.
_transcript("auditbig", sum((
    [_assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "id": "b%d" % i, "name": "Bash",
                                                 "input": {"command": "echo %d" % i}}]),
     _user_result("b%d" % i)]
    for i in range(45)
), []))


def sub_payload(**kw):
    base = {"session_id": "sess1", "transcript_path": _PARENT}
    base.update(kw)
    return json.dumps(base)


# announce names the agent, what it DECLARES, the plugin version and the digest fingerprint.
code, out, err = run_hook("announce", sub_payload(
    hook_event_name="SubagentStart", agent_type="house-rules:builder", agent_id="x1", effort="low"
))
ann = []
if code != 0:
    ann.append(f"exit {code}, must never be non-zero")
for needle in ("house-rules:builder", "declared model sonnet", "digest ", "house-rules 2."):
    if needle not in out:
        ann.append(f"announce output does not mention {needle!r}")
if not ann:
    report("PASS", "announce reports the agent, its declared model and the digest it carries")
    print(f"          {out[:150]}")
else:
    report("FAIL", "announce reports the agent, its declared model and the digest it carries")
    for a in ann:
        print(f"          {a}")

# The declared model is READ FROM the agent file, not hardcoded in hook.py - otherwise the
# line is hook.py's claim about the agent rather than a report of what actually shipped.
_src = read(DELEGATION)  # #359: _declared and event_announce live in the delegation part
_decl = _src[_src.index("def _declared("):_src.index("def event_announce(")]
litdrift = []
if "_read_text(path)" not in _decl:
    litdrift.append("_declared does not read the agent file")
if not re.search(r'r"\^model:', _decl):
    litdrift.append("_declared does not parse the frontmatter model field")
for lit in ('"sonnet"', "'sonnet'", '"opus"', '"haiku"'):
    if lit in _decl:
        litdrift.append(f"_declared hardcodes {lit}, so the line is a claim, not a report")
if not litdrift:
    report("PASS", "announce reads the declared model from the agent file, not a literal")
    print("          the value comes from agents/<name>.md frontmatter, so it reports what shipped")
else:
    report("FAIL", "announce reads the declared model from the agent file, not a literal")
    for l in litdrift:
        print(f"          {l}")

# An agent the plugin does not ship is the common case, not an error.
code, out, err = run_hook("announce", sub_payload(agent_type="Explore", agent_id="x2"))
if code == 0 and "Explore" in out and "no declaration" in out:
    report("PASS", "announce still names an agent the plugin does not ship")
    print("          reports the agent and says there is no declaration to compare against")
else:
    report("FAIL", "announce still names an agent the plugin does not ship")
    print(f"          exit {code}, out {out[:160]!r}")

# A set model-override env var is the documented way "model: sonnet" is not what runs.
_ovr = dict(os.environ)
_ovr["CLAUDE_CODE_SUBAGENT_MODEL_FORCE"] = "opus"
code, out, err = run_hook("announce", sub_payload(agent_type="house-rules:builder"), env=_ovr)
if "CLAUDE_CODE_SUBAGENT_MODEL_FORCE" in out and "may not be what runs" in out:
    report("PASS", "announce warns when a model-override env var is set")
    print("          names the variable that can silently override the declared model")
else:
    report("FAIL", "announce warns when a model-override env var is set")
    print(f"          out {out[:200]!r}")

# verdict turns the declaration into evidence: the model that actually served the subagent.
code, out, err = run_hook("verdict", sub_payload(
    hook_event_name="SubagentStop", agent_type="house-rules:builder", agent_id="sonnet"
))
if code == 0 and "claude-sonnet-4-5-20250929" in out and "MATCH" in out and "2 assistant turns" in out:
    report("PASS", "verdict reports the model that actually served the subagent")
    print(f"          {out[:150]}")
else:
    report("FAIL", "verdict reports the model that actually served the subagent")
    print(f"          exit {code}, out {out[:200]!r}")

# The case the whole feature exists for: declared Sonnet, actually ran on something else.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="opus"))
if code == 0 and "MISMATCH" in out and "claude-opus-5" in out:
    report("PASS", "verdict reports MISMATCH when the observed model is not the declared one")
    print("          a delegation that did not run on what it declares is now visible")
else:
    report("FAIL", "verdict reports MISMATCH when the observed model is not the declared one")
    print(f"          exit {code}, out {out[:200]!r}")

# The completion-sanity check: zero tool calls across the whole transcript is exactly the
# hollow "stop" that let a duplicate delegation get dispatched.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "0 tool calls" in out:
    report("PASS", "verdict flags a completion with zero tool calls")
    print("          a status-update-only finish is now visible, not read as done work")
else:
    report("FAIL", "verdict flags a completion with zero tool calls")
    print(f"          exit {code}, out {out[:200]!r}")

# One tool call present (so the zero-tool-calls path does not fire), but the last message
# still reads like a deferral - the other half of the same signal.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="deferral"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "i'll report back" in out.lower():
    report("PASS", "verdict flags a last message that matches a deferral phrase")
    print("          names the phrase, does not fire the zero-tool-calls branch instead")
else:
    report("FAIL", "verdict flags a last message that matches a deferral phrase")
    print(f"          exit {code}, out {out[:200]!r}")

# An ordinary finish - tool calls present, last message an ordinary summary - must not
# false-positive as a suspicious completion.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="normal"))
if code == 0 and "SUSPICIOUS COMPLETION" not in out:
    report("PASS", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print("          no false positive on a normal completion")
else:
    report("FAIL", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print(f"          exit {code}, out {out[:200]!r}")

# Nothing fails silently: every "I could not tell" path says so, and says what it tried.
quiet = []
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="ghost"))
if code != 0 or "unverified" not in out or "tried:" not in out:
    quiet.append(f"missing transcript: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="nomodel"))
if code != 0 or "unverified" not in out:
    quiet.append(f"transcript with no model field: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", '{"agent_type":"house-rules:builder"}')
if code != 0 or "unverified" not in out:
    quiet.append(f"not enough fields to locate one: exit {code}, out {out[:120]!r}")
for ev in ("announce", "verdict"):
    code, out, err = run_hook(ev, "")
    if code != 0 or "systemMessage" not in out:
        quiet.append(f"{ev} on an empty payload: exit {code}, out {out[:120]!r}")
    code, out, err = run_hook(ev, "not json at all {{{")
    if code != 0:
        quiet.append(f"{ev} on unparseable input: exit {code}")
if not quiet:
    report("PASS", "announce and verdict never go quiet and never exit non-zero")
    print("          every path meaning 'I could not tell' says so, naming what it tried")
else:
    report("FAIL", "announce and verdict never go quiet and never exit non-zero")
    for q in quiet:
        print(f"          {q}")

# One lever, and it is NOT the trace lever - the report is the feature, not a trace.
_off = dict(os.environ)
_off["HOUSE_RULES_DELEGATION"] = "off"
deloff = []
for ev, pl in (("announce", sub_payload(agent_type="house-rules:builder")),
               ("verdict", sub_payload(agent_type="house-rules:builder", agent_id="sonnet"))):
    code, out, err = run_hook(ev, pl, env=_off)
    if out.strip():
        deloff.append(f"{ev} still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
_tron = dict(os.environ)
_tron["HOUSE_RULES_TRACE"] = "off"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="sonnet"), env=_tron)
if "claude-sonnet" not in out:
    deloff.append("HOUSE_RULES_TRACE=off silenced the verdict, which is not a trace")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"), env=_off)
if out.strip():
    deloff.append(f"suspicious-completion report still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"), env=_tron)
if "SUSPICIOUS COMPLETION" not in out:
    deloff.append("HOUSE_RULES_TRACE=off silenced the suspicious-completion report, which is not a trace")
if not deloff:
    report("PASS", "HOUSE_RULES_DELEGATION=off silences both, and the trace lever does not")
    print("          the model report is the deliverable, so it is not trace-gated")
else:
    report("FAIL", "HOUSE_RULES_DELEGATION=off silences both, and the trace lever does not")
    for d in deloff:
        print(f"          {d}")

# announce/verdict are registered on the subagent lifecycle events, with no matcher - the
# complaint was "I could not tell which agent", which covers every subagent, not just ours.
subwire = []
_hj = json.loads(read(HOOKS_JSON))["hooks"]
for ev, handler in (("SubagentStart", "announce"), ("SubagentStop", "verdict")):
    entries = _hj.get(ev)
    if not entries:
        subwire.append(f"hooks.json has no {ev} entry")
        continue
    if any("matcher" in e for e in entries):
        subwire.append(f"{ev} is scoped by a matcher, so it misses other agents")
    if not any(handler in h.get("command", "") for e in entries for h in e.get("hooks", [])):
        subwire.append(f"{ev} does not dispatch run.sh {handler}")
if not subwire:
    report("PASS", "announce and verdict are wired to the subagent lifecycle, unmatched")
    print("          hooks.json reports every subagent, not only the two this plugin ships")
else:
    report("FAIL", "announce and verdict are wired to the subagent lifecycle, unmatched")
    for s in subwire:
        print(f"          {s}")

# run.sh's no-interpreter fallback must speak for these two, or a machine with no Python
# reports a delegation as silently fine.
shfall = []
_rs = read(RUN)
for ev in ("announce", "verdict"):
    if ("    %s)" % ev) not in _rs:
        shfall.append(f"run.sh has no per-event fallback for {ev}")
if not shfall:
    report("PASS", "run.sh names announce and verdict in its no-interpreter fallback")
    print("          no working Python still reports that the delegation went unchecked")
else:
    report("FAIL", "run.sh names announce and verdict in its no-interpreter fallback")
    for s in shfall:
        print(f"          {s}")

# --- subagentrules: a subagent core, generated from house-rules.md, injected at SubagentStart --
# Judged against the real rules file, since a hand-copied fixture core would only prove the
# handler can read a fixture, not that it stays in sync with the rules a human session sees.
code, out, err = run_hook("subagentrules", sub_payload(
    hook_event_name="SubagentStart", agent_type="house-rules:builder", agent_id="x1"
))
sar = []
if code != 0:
    sar.append(f"exit {code}, must never be non-zero")
try:
    parsed = json.loads(out)
    core = parsed["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    sar.append(f"could not parse subagentrules output: {exc}")
    core = ""
for needle in (
    "Documentation goes in tiers", "Nothing fails silently", "Evidence before claims",
    "Every artifact lives in the project directory", "Commit constantly on my own branches",
    "Never take a destructive action", "Edit in place",
    "final report must list every command you ran and its result verbatim",
):
    if needle not in core:
        sar.append(f"subagent core is missing {needle!r}")
if "${CLAUDE_PLUGIN_ROOT}" in core:
    sar.append("subagent core still carries a literal ${CLAUDE_PLUGIN_ROOT}")
if "<!-- subagent -->" in core:
    sar.append("subagent core leaked the <!-- subagent --> marker into the subagent's own text")
if len(core) > 4_500:
    sar.append(f"subagent core is {len(core)} chars, over its own 4,500-char budget")
if not sar:
    report("PASS", "subagentrules generates a subagent core from house-rules.md's marked sections")
    print(f"          {len(core)} chars, all marked sections present, no literal placeholder")
else:
    report("FAIL", "subagentrules generates a subagent core from house-rules.md's marked sections")
    for s in sar:
        print(f"          {s}")

# A section NOT marked <!-- subagent --> (e.g. "Open source first") must not
# appear as its own heading in the core - otherwise "marked sections only" is not what ships.
if "## Open source first; paid is the last resort" in core:
    report("FAIL", "subagentrules includes only the sections marked <!-- subagent -->")
    print("          an unmarked heading leaked into the subagent core")
else:
    report("PASS", "subagentrules includes only the sections marked <!-- subagent -->")
    print("          an unmarked rule (open source first) is absent from the subagent core")

# SubagentStart also tells the user the transcript's EXPECTED path, before it exists.
if code == 0 and "systemMessage" in parsed and "transcript expected at" in parsed["systemMessage"] \
        and os.path.join("sess1", "subagents", "agent-x1.jsonl") in parsed["systemMessage"]:
    report("PASS", "subagentrules tells the user the expected transcript path at SubagentStart")
    print(f"          {parsed['systemMessage'][:150]}")
else:
    report("FAIL", "subagentrules tells the user the expected transcript path at SubagentStart")
    print(f"          out {out[:200]!r}")

# Never blocks a spawn: empty payload and unparseable input both still exit 0.
sarq = []
code, out, err = run_hook("subagentrules", "")
if code != 0 or "systemMessage" not in out:
    sarq.append(f"empty payload: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("subagentrules", "not json at all {{{")
if code != 0:
    sarq.append(f"unparseable payload: exit {code}")
if not sarq:
    report("PASS", "subagentrules never blocks a subagent spawn")
    print("          empty and unparseable payloads both still exit 0")
else:
    report("FAIL", "subagentrules never blocks a subagent spawn")
    for s in sarq:
        print(f"          {s}")

# Registered as its OWN SubagentStart entry, unmatched, separate from announce.
_hj2 = json.loads(read(HOOKS_JSON))["hooks"]
sarwire = []
starts = _hj2.get("SubagentStart") or []
if not any("subagentrules" in h.get("command", "") for e in starts for h in e.get("hooks", [])):
    sarwire.append("hooks.json's SubagentStart has no subagentrules dispatch")
announce_entries = [e for e in starts if any("announce" in h.get("command", "") for h in e.get("hooks", []))]
subagentrules_entries = [e for e in starts if any("subagentrules" in h.get("command", "") for h in e.get("hooks", []))]
if announce_entries and subagentrules_entries and announce_entries[0] is subagentrules_entries[0]:
    sarwire.append("announce and subagentrules share one hook entry instead of two separate ones")
if any("matcher" in e for e in starts):
    sarwire.append("SubagentStart is scoped by a matcher, so it misses other agents")
if not sarwire:
    report("PASS", "subagentrules is its own SubagentStart entry, separate from announce")
    print("          both fire, unmatched, on every subagent spawn")
else:
    report("FAIL", "subagentrules is its own SubagentStart entry, separate from announce")
    for s in sarwire:
        print(f"          {s}")

if ("    subagentrules)" in read(RUN)):
    report("PASS", "run.sh names subagentrules in its no-interpreter fallback")
    print("          no working Python still reports the subagent got no rules")
else:
    report("FAIL", "run.sh names subagentrules in its no-interpreter fallback")

# --- agentcap (2.50.0, #112): at most two running subagents, none started by a subagent -------
_cap_state = os.path.join(_FIXTURE_ROOT, "cap-agents.json")


def _cap_env(**extra):
    e = dict(os.environ)
    e["HOUSE_RULES_AGENTS_STATE"] = _cap_state
    e.pop("HOUSE_RULES_AGENTS", None)
    e.update(extra)
    return e


def _cap_spawn(agent_id="", tool_input=None, **extra):
    pl = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
          "tool_input": tool_input or {"prompt": "x", "run_in_background": False}}
    if agent_id:
        pl["agent_id"] = agent_id
    return run_hook("agentcap", json.dumps(pl), env=_cap_env(**extra))


def _cap_denied(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        return False


def _cap_start(aid, atype="house-rules:builder"):
    return run_hook("announce", sub_payload(hook_event_name="SubagentStart", agent_type=atype, agent_id=aid), env=_cap_env())


def _cap_stop(aid, atype="house-rules:builder"):
    return run_hook("verdict", sub_payload(hook_event_name="SubagentStop", agent_type=atype, agent_id=aid), env=_cap_env())


if os.path.exists(_cap_state):
    os.remove(_cap_state)
_c0 = _cap_spawn()
_cap_start("capA")
_c1 = _cap_spawn()
_cap_start("capB")
_c2 = _cap_spawn()
commit_case(
    "agentcap: the first and second spawn are allowed, the third is denied naming both running agents",
    not _cap_denied(_c0[1]) and not _cap_denied(_c1[1]) and _cap_denied(_c2[1])
    and "capA" in _c2[1] and "capB" in _c2[1] and "Wait for one to finish" in _c2[1],
    "out %r" % _c2[1][:200],
)
_cap_stop("capA")
_c3 = _cap_spawn()
commit_case(
    "agentcap: a record is cleared by SubagentStop, so a spawn is allowed again",
    not _cap_denied(_c3[1]) and "capA" not in open(_cap_state, encoding="utf-8").read(),
    "after stop: %r" % open(_cap_state, encoding="utf-8").read()[:120],
)
_stale = time.time() - 46 * 60
with open(_cap_state, "w", encoding="utf-8") as _f:
    json.dump({"agents": [{"id": "old1", "type": "x", "start": _stale}, {"id": "old2", "type": "x", "start": _stale}]}, _f)
_c4 = _cap_spawn()
commit_case(
    "agentcap: records older than 45 minutes are ignored",
    not _cap_denied(_c4[1]), "out %r" % _c4[1][:120],
)
with open(_cap_state, "w", encoding="utf-8") as _f:
    json.dump({"agents": [{"id": "k1", "type": "x", "start": time.time()}, {"id": "k2", "type": "x", "start": time.time()}]}, _f)
_c5 = _cap_spawn(HOUSE_RULES_AGENTS="off")
_c5b = _cap_spawn()
commit_case(
    "agentcap: HOUSE_RULES_AGENTS=off disables the cap (and the same state denies without it)",
    _c5[1].strip() == "" and _cap_denied(_c5b[1]), "off: %r; on: %r" % (_c5[1][:60], _c5b[1][:60]),
)
with open(_cap_state, "w", encoding="utf-8") as _f:
    _f.write("{not json")
_c6 = _cap_spawn()
try:
    _c6msg = json.loads(_c6[1]).get("systemMessage", "")
except ValueError:
    _c6msg = "unparseable"
commit_case(
    "agentcap: a corrupt state file fails open and says so in one line",
    _c6[0] == 0 and not _cap_denied(_c6[1]) and "could not read" in _c6msg and "allowed" in _c6msg,
    "systemMessage %r" % _c6msg[:160],
)
os.remove(_cap_state)
_c7 = _cap_spawn(agent_id="sub9")
commit_case(
    "agentcap: a spawn made by a subagent (payload carries agent_id) is denied",
    _cap_denied(_c7[1]) and "sub9" in _c7[1], "out %r" % _c7[1][:160],
)

# No background helpers: a helper aj cannot watch is refused unless run_in_background is false.
for _bg_input, _bg_why in (({"prompt": "x"}, "was left out"),
                           ({"prompt": "x", "run_in_background": True}, "is true"),
                           ({"prompt": "x", "run_in_background": False, "isolation": "remote"}, "remote")):
    _bg = _cap_spawn(tool_input=_bg_input)
    commit_case(
        "agentcap: a background helper is refused (run_in_background %s)" % _bg_why
        if _bg_why != "remote" else "agentcap: isolation remote is refused as a background helper",
        _cap_denied(_bg[1]) and "no background helpers" in _bg[1] and _bg_why in _bg[1],
        "out %r" % _bg[1][:200],
    )
_bg_open = _cap_spawn()
_bg_on = _cap_spawn(tool_input={"prompt": "x"}, HOUSE_RULES_BACKGROUND_HELPERS="on")
commit_case(
    "agentcap: run_in_background false is allowed, and HOUSE_RULES_BACKGROUND_HELPERS=on allows a background helper",
    not _cap_denied(_bg_open[1]) and not _cap_denied(_bg_on[1]),
    "open %r; on %r" % (_bg_open[1][:120], _bg_on[1][:120]),
)
if os.path.exists(_cap_state):
    os.remove(_cap_state)

# --- verdict's audit summary: built from the transcript, not the subagent's own report --------
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"))
audit = []
if code != 0:
    audit.append(f"exit {code}, must never be non-zero")
for needle in (
    "transcript found at", "tool uses:", "FAILED commands", "cmd: Bash [ERROR]: false",
    "wrote: Write /proj/a.py", "other commands: 1 ok (not listed)",
    "Reconcile the subagent's report against this record",
):
    if needle not in out:
        audit.append(f"audit summary is missing {needle!r}")
if not audit:
    report("PASS", "verdict's audit summary reports commands with exit status and files written")
    print("          built from the transcript itself: counts, the failed command in full, the written file, the ok count")
else:
    report("FAIL", "verdict's audit summary reports commands with exit status and files written")
    for a in audit:
        print(f"          {a}")

# The cap: 45 commands in the fixture, at most 40 shown plus an explicit "N more".
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="auditbig"))
if code == 0 and "cmd: Bash [ok]" not in out and "other commands: 45 ok (not listed)" in out and "Bash x45" in out and len(out) < 1500:
    report("PASS", "verdict's audit summary counts ok commands instead of listing them, and stays small")
    print(f"          45 ok commands -> one count line, {len(out)} chars (< 1500)")
else:
    report("FAIL", "verdict's audit summary counts ok commands instead of listing them, and stays small")
    print(f"          exit {code}, len={len(out)}, out[-200:]={out[-200:]!r}")

# --- HOUSE_RULES_SUBAGENT_LEDGER: off by default, renders docs/sessions/<...> when on ---------
_ledger_root = tempfile.mkdtemp(prefix="house-rules-ledger-")
atexit.register(shutil.rmtree, _ledger_root, True)
_ledger_off = dict(os.environ)
_ledger_off["CLAUDE_PROJECT_DIR"] = _ledger_root
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"), env=_ledger_off)
_ledger_dir = os.path.join(_ledger_root, "docs", "sessions")
if "LEDGER" not in out and not os.path.isdir(_ledger_dir):
    report("PASS", "HOUSE_RULES_SUBAGENT_LEDGER is off by default - no docs/sessions/ write")
    print("          no LEDGER line, no docs/sessions/ directory created")
else:
    report("FAIL", "HOUSE_RULES_SUBAGENT_LEDGER is off by default - no docs/sessions/ write")
    print(f"          out {out[:150]!r}, ledger dir exists={os.path.isdir(_ledger_dir)}")

_ledger_on = dict(_ledger_off)
_ledger_on["HOUSE_RULES_SUBAGENT_LEDGER"] = "on"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"), env=_ledger_on)
_written = [f for f in os.listdir(_ledger_dir)] if os.path.isdir(_ledger_dir) else []
if code == 0 and "LEDGER: rendered" in out and any(f.endswith(".md") for f in _written):
    report("PASS", "HOUSE_RULES_SUBAGENT_LEDGER=on renders the subagent transcript into docs/sessions/")
    print(f"          wrote {_written}")
else:
    report("FAIL", "HOUSE_RULES_SUBAGENT_LEDGER=on renders the subagent transcript into docs/sessions/")
    print(f"          exit {code}, out {out[:200]!r}, dir listing {_written}")

_ledger_files = [os.path.join(_ledger_dir, f) for f in _written if f.endswith(".md")]
_ledger_text = open(_ledger_files[0], encoding="utf-8").read() if _ledger_files else ""
if "false" in _ledger_text and "Bash" in _ledger_text:
    report("PASS", "the subagent ledger lists the helper's Bash commands (heading opens its turn)")
    print(f"          ledger {os.path.basename(_ledger_files[0])} names the Bash command")
else:
    report("FAIL", "the subagent ledger lists the helper's Bash commands (heading opens its turn)")
    print(f"          ledger text {_ledger_text[:300]!r}")

# A failure rendering the ledger (unreadable transcript) says so and never crashes verdict.
_ledger_bad_root = tempfile.mkdtemp(prefix="house-rules-ledger-bad-")
atexit.register(shutil.rmtree, _ledger_bad_root, True)
_ledger_bad = dict(os.environ)
_ledger_bad["CLAUDE_PROJECT_DIR"] = _ledger_bad_root
_ledger_bad["HOUSE_RULES_SUBAGENT_LEDGER"] = "on"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="ghost"), env=_ledger_bad)
# "ghost" has no transcript file at all, so verdict returns before ever reaching the ledger
# step - this proves that early return, not the ledger call, never crashes.
if code == 0 and "unverified" in out:
    report("PASS", "an unreadable/missing subagent transcript never crashes verdict, ledger or not")
    print("          missing-transcript path returns before the ledger step, exit 0")
else:
    report("FAIL", "an unreadable/missing subagent transcript never crashes verdict, ledger or not")
    print(f"          exit {code}, out {out[:150]!r}")


code, out, err = run_hook("audit", post_agent_payload())
aud = []
if code != 0:
    aud.append(f"exit {code}, must never be non-zero")
try:
    core_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    aud.append(f"could not parse audit output: {exc}")
    core_ctx = ""
for needle in (
    "finished (foreground)", "FAILED commands", "cmd: Bash [ERROR]: false", "wrote: Write /proj/a.py",
    "Reconcile the subagent's report against this record",
):
    if needle not in core_ctx:
        aud.append(f"audit's additionalContext is missing {needle!r}")
if not aud:
    report("PASS", "audit hands the subagent's audit summary to the parent MODEL after a foreground return")
    print(f"          {core_ctx[:150]}")
else:
    report("FAIL", "audit hands the subagent's audit summary to the parent MODEL after a foreground return")
    for a in aud:
        print(f"          {a}")
code, out, err = run_hook("audit", _async_payload)
# #292: the 5-minute stall-check reminder is gone, so a backgrounded call's launch gets neither an audit
# nor a reminder; its hand-back is audited when it arrives.
if code == 0 and not out.strip() and code_off == 0 and not out_off.strip():
    report("PASS", "audit gives no audit and no stall-check reminder on a backgrounded call's async_launched PostToolUse (#292)")
    print("          nothing to audit yet, and no reminder, with autosave on or off")
else:
    report("FAIL", "audit gives no audit and no stall-check reminder on a backgrounded call's async_launched PostToolUse (#292)")
    print(f"          exit {code}, out {out[:150]!r}; autosave off: exit {code_off}, out {out_off[:80]!r}")


# --- stallcheck.py (issue 120). The agentcap cases live with the spawn-cap tests above.
import tempfile as _cap_tf
def _cap_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print("          " + detail)

_sc = os.path.join(HERE, "stallcheck.py")
_home = _cap_tf.mkdtemp(prefix="house-rules-home-", dir=_FIXTURE_ROOT)
_sd = os.path.join(_home, ".claude", "projects", "p", "s", "subagents")
os.makedirs(_sd)
_henv = dict(os.environ, HOME=_home, USERPROFILE=_home)


def _sc_file(name, text, age_s):
    path = os.path.join(_sd, "agent-%s.jsonl" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.utime(path, (time.time() - age_s, time.time() - age_s))


def _sc_run(*extra):
    pr = subprocess.run([sys.executable, _sc] + list(extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_henv)
    return pr.returncode, pr.stdout.decode("utf-8", "replace")


# #122: a row that stays STALLED is printed again every threshold period, not once.
_sc_file("stuck122", '{"type":"assistant"}\n', 600)
try:
    _pr = subprocess.run([sys.executable, _sc, "--watch", "--threshold", "1", "--poll", "0.2", "--agent", "stuck122"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_henv, timeout=4)
    _o = _pr.stdout.decode("utf-8", "replace")
except subprocess.TimeoutExpired as _e:
    _o = (_e.stdout or b"").decode("utf-8", "replace")  # expected: the watch never ends; the limit stops it
_cap_case("stallcheck: --watch re-prints a row that stays STALLED every threshold period (#122)",
          _o.count("STALLED") >= 2, "STALLED lines in 4 s: %d, out %r" % (_o.count("STALLED"), _o[:200]))
os.remove(os.path.join(_sd, "agent-stuck122.jsonl"))
_sc_file("fresh", '{"type":"assistant"}\n', 20)
_c, _o = _sc_run()
_cap_case("stallcheck: a transcript written 20 s ago is ok, exit 0", _c == 0 and "ok" in _o and "fresh" in _o, "exit %d out %r" % (_c, _o[:100]))
_sc_file("quiet", '{"type":"assistant"}\n', 600)
_c, _o = _sc_run()
_cap_case("stallcheck: a transcript silent for 10 minutes is STALLED, exit 1",
          _c == 1 and "STALLED" in _o and "quiet" in _o, "exit %d out %r" % (_c, _o[:160]))
_sc_file("done", '{"type":"attachment","attachment":{"hookEvent":"SubagentStop"}}\n', 3000)
_c, _o = _sc_run("--threshold", "9999")
_cap_case("stallcheck: a transcript holding SubagentStop is finished, never STALLED",
          "finished  subagent done" in _o, "out %r" % _o[:200])
_sc_file("resumed", '{"type":"attachment","attachment":{"hookEvent":"SubagentStop"}}\n{"type":"assistant"}\n', 5)
_c, _o = _sc_run("--agent", "resumed")
_cap_case("stallcheck: a transcript with records after SubagentStop (resumed agent) is ok, not finished",
          "ok" in _o and "finished" not in _o, "out %r" % _o[:200])
os.remove(os.path.join(_sd, "agent-resumed.jsonl"))
_c, _o = _sc_run("--file", os.path.join(_home, "no-such.out"))
_cap_case("stallcheck: a watched file that does not exist is STALLED, not skipped", _c == 1 and "no-such.out" in _o, "exit %d out %r" % (_c, _o[:160]))
for _n in os.listdir(_sd):
    os.remove(os.path.join(_sd, _n))
_c, _o = _sc_run()
_cap_case("stallcheck: with nothing to check it says so and exits 2, never silent",
          _c == 2 and "nothing was checked" in _o, "exit %d out %r" % (_c, _o[:160]))

# Scope (issue 123): a watch covers only the calling session's / named agent's transcripts.
_sdA = os.path.join(_home, ".claude", "projects", "p", "sessA", "subagents")
_sdB = os.path.join(_home, ".claude", "projects", "p", "sessB", "subagents")
os.makedirs(_sdA)
os.makedirs(_sdB)
for _d, _n in ((_sdA, "aaa"), (_sdA, "xxx"), (_sdB, "bbb")):
    with open(os.path.join(_d, "agent-%s.jsonl" % _n), "w", encoding="utf-8") as _f:
        _f.write('{"type":"assistant"}' + chr(10))
_c, _o = _sc_run("--session", "sessA")
_cap_case("stallcheck: --session sessA reports only sessA's agents, never sessB's",
          _c == 0 and "aaa" in _o and "xxx" in _o and "bbb" not in _o, "exit %d out %r" % (_c, _o[:200]))
_c, _o = _sc_run("--agent", "xxx")
_cap_case("stallcheck: --agent xxx reports only that agent",
          _c == 0 and "xxx" in _o and "aaa" not in _o and "bbb" not in _o, "exit %d out %r" % (_c, _o[:200]))
_c, _o = _sc_run("--session", "sessA", "--agent", "bbb")
_cap_case("stallcheck: --session sessA with another session's agent matches nothing, exit 2, says so",
          _c == 2 and "sessA" in _o and "bbb" in _o and "nothing was checked" in _o, "exit %d out %r" % (_c, _o[:200]))
_c, _o = _sc_run("--session", "nosuch")
_cap_case("stallcheck: a --session matching nothing exits 2 and names the session",
          _c == 2 and "nosuch" in _o and "nothing was checked" in _o and "bbb" not in _o, "exit %d out %r" % (_c, _o[:200]))
_c, _o = _sc_run()
_cap_case("stallcheck: no-flag mode says it is watching all sessions",
          "watching ALL sessions" in _o and "aaa" in _o and "bbb" in _o, "exit %d out %r" % (_c, _o[:200]))

audq = []
code, out, err = run_hook("audit", "")
if code != 0 or "systemMessage" not in out:
    audq.append(f"empty payload: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("audit", "not json at all {{{")
if code != 0:
    audq.append(f"unparseable payload: exit {code}")
if not audq:
    report("PASS", "audit never blocks a PostToolUse call, even on a bad payload")
    print("          empty and unparseable payloads both still exit 0")
else:
    report("FAIL", "audit never blocks a PostToolUse call, even on a bad payload")
    for a in audq:
        print(f"          {a}")

_hj3 = json.loads(read(HOOKS_JSON))["hooks"]
audwire = []
posts = _hj3.get("PostToolUse") or []
audit_entries = [e for e in posts if any("audit" in h.get("command", "") and "\" audit" in h.get("command", "") for h in e.get("hooks", []))]
if not any(e.get("matcher") == "Agent|Task" for e in posts):
    audwire.append("hooks.json's PostToolUse has no Agent|Task matcher for audit")
if not any("\" audit" in h.get("command", "") for e in posts for h in e.get("hooks", [])):
    audwire.append("hooks.json's PostToolUse has no audit dispatch")
if not audwire:
    report("PASS", "audit is its own PostToolUse entry matched on Agent|Task")
    print("          separate from artifact/runnable/harvest/delegate")
else:
    report("FAIL", "audit is its own PostToolUse entry matched on Agent|Task")
    for a in audwire:
        print(f"          {a}")

if ("    audit)" in read(RUN)):
    report("PASS", "run.sh names audit in its no-interpreter fallback")
else:
    report("FAIL", "run.sh names audit in its no-interpreter fallback")

# --- rclink: the Remote Control transcript link (#383) -------------------------------------
def _rc_payload(result):
    return json.dumps({"session_id": "verify", "tool_name": "mcp__hearthbot__start_remote_control",
                       "tool_input": {}, "tool_response": [{"type": "text", "text": json.dumps({"result": result})}]})


def _rc_env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_PROJECTS_SESSION", "HOUSE_RULES_WORKTRACKING")}
    e.update(kw)
    return e


def _rc_case(title, result, env, expect_fire):
    code, out, err = run_hook("rclink", _rc_payload(result), env=env)
    problems = []
    if code != 0:
        problems.append(f"exit {code}, must never be non-zero")
    if expect_fire:
        try:
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        except Exception as exc:
            problems.append(f"could not parse output: {exc}")
            ctx = ""
        for needle in ("remote_control_status", "Transcript of the session on your PC", 'kind "link"'):
            if needle not in ctx:
                problems.append(f"additionalContext is missing {needle!r}")
    elif out.strip():
        problems.append(f"expected no output, got {out[:120]!r}")
    report("FAIL" if problems else "PASS", title)
    for p in problems:
        print(f"          {p}")


_rc_case("rclink fires on a `started` Remote Control result and asks for the link to be posted and attached",
         "started", _rc_env(CLAUDE_CODE_PROJECTS_SESSION="1"), True)
_rc_case("rclink fires on an `already_running` result", "already_running",
         _rc_env(CLAUDE_CODE_PROJECTS_SESSION="1"), True)
_rc_case("rclink is silent on an `asked` result (nothing started yet)", "asked",
         _rc_env(CLAUDE_CODE_PROJECTS_SESSION="1"), False)
_rc_case("rclink is silent outside a Projects session (CLAUDE_CODE_PROJECTS_SESSION unset)", "started",
         _rc_env(), False)
_rc_case("rclink is silent with HOUSE_RULES_WORKTRACKING=off", "started",
         _rc_env(CLAUDE_CODE_PROJECTS_SESSION="1", HOUSE_RULES_WORKTRACKING="off"), False)

# --- thread link: the thread's own transcript link at session start (#400) ----------------
def _tl_ctx(**kw):
    e = {k: v for k, v in os.environ.items()
         if k not in ("CLAUDE_CODE_PROJECTS_SESSION", "CLAUDE_CODE_REMOTE_SESSION_ID", "HOUSE_RULES_WORKTRACKING")}
    e.update(kw)
    code, ctx, err = _additional_context("inject", "", env=e)
    return ctx or ""


def _tl_case(title, ctx, must, must_not=()):
    problems = [f"missing {n!r}" for n in must if n not in ctx]
    problems += [f"unexpected {n!r}" for n in must_not if n in ctx]
    report("FAIL" if problems else "PASS", title)
    for p in problems:
        print(f"          {p}")


_tl_case("inject carries the thread's transcript link in a project thread",
         _tl_ctx(CLAUDE_CODE_PROJECTS_SESSION="1", CLAUDE_CODE_REMOTE_SESSION_ID="cse_TEST123"),
         ("/code/session_TEST123", "Transcript of this thread's session", "cse_TEST123"))
_tl_case("inject adds no transcript link outside a project thread",
         _tl_ctx(CLAUDE_CODE_REMOTE_SESSION_ID="cse_TEST123"), (), ("/code/session_", "could not build"))
_tl_case("inject names CLAUDE_CODE_REMOTE_SESSION_ID when the id is malformed",
         _tl_ctx(CLAUDE_CODE_PROJECTS_SESSION="1", CLAUDE_CODE_REMOTE_SESSION_ID="bogus"),
         ("could not build the thread's transcript link", "CLAUDE_CODE_REMOTE_SESSION_ID"), ("/code/session_",))
_tl_case("inject names CLAUDE_CODE_REMOTE_SESSION_ID when the id is missing",
         _tl_ctx(CLAUDE_CODE_PROJECTS_SESSION="1"),
         ("could not build the thread's transcript link", "CLAUDE_CODE_REMOTE_SESSION_ID"), ("/code/session_",))
_tl_case("inject adds no transcript link with HOUSE_RULES_WORKTRACKING=off",
         _tl_ctx(CLAUDE_CODE_PROJECTS_SESSION="1", CLAUDE_CODE_REMOTE_SESSION_ID="cse_TEST123",
                 HOUSE_RULES_WORKTRACKING="off"), (), ("/code/session_", "could not build"))

# --- userpromptaudit: the background half, UserPromptSubmit --------------------------------
def _task_notification(task_id, status="completed"):
    return (
        "<task-notification>\n<task-id>%s</task-id>\n<tool-use-id>toolu_x</tool-use-id>\n"
        "<output-file>/x</output-file>\n<status>%s</status>\n<summary>Agent finished</summary>\n"
        "<result>done</result>\n</task-notification>" % (task_id, status)
    )


def userprompt_payload(prompt, **kw):
    base = {"session_id": "sess1", "transcript_path": _PARENT, "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    base.update(kw)
    return json.dumps(base)


code, out, err = run_hook("userpromptaudit", userprompt_payload(_task_notification("audit1")))
upa = []
if code != 0:
    upa.append(f"exit {code}, must never be non-zero")
try:
    up_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    upa.append(f"could not parse userpromptaudit output: {exc}")
    up_ctx = ""
for needle in (
    "finished (background)", "FAILED commands", "cmd: Bash [ERROR]: false",
    "Reconcile the subagent's report against this record",
):
    if needle not in up_ctx:
        upa.append(f"userpromptaudit's additionalContext is missing {needle!r}")
if not upa:
    report("PASS", "userpromptaudit hands the audit summary to the parent model on a background hand-back")
    print(f"          {up_ctx[:150]}")
else:
    report("FAIL", "userpromptaudit hands the audit summary to the parent model on a background hand-back")
    for a in upa:
        print(f"          {a}")

# --- work trail: a project thread keeps a helper's rendered transcript (#397) ---------------
import tempfile as _wt_tf

_WT_STRIP = ("CLAUDE_CODE_PROJECTS_SESSION", "CLAUDE_CODE_REMOTE_SESSION_ID", "HOUSE_RULES_WORKTRAIL_DIR")


def _wt_env(trail, projects="1"):
    e = {k: v for k, v in os.environ.items() if k not in _WT_STRIP}
    if projects:
        e["CLAUDE_CODE_PROJECTS_SESSION"] = projects
    if trail:
        e["HOUSE_RULES_WORKTRAIL_DIR"] = trail
    return e


def _wt_ctx(event, payload, env):
    code, out, err = run_hook(event, payload, env=env)
    try:
        return code, json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return code, ""


def _wt_check(title, problems):
    report("FAIL" if problems else "PASS", title)
    for p in problems:
        print(f"          {p}")


for _wt_event, _wt_payload in (("audit", post_agent_payload()),
                               ("userpromptaudit", userprompt_payload(_task_notification("audit1")))):
    _wt_dir = _wt_tf.mkdtemp(prefix="house-rules-worktrail-")
    _wt_code, _wt_c = _wt_ctx(_wt_event, _wt_payload, _wt_env(_wt_dir))
    _wt_files = [os.path.join(_wt_dir, n) for n in os.listdir(_wt_dir)]
    _wt_p = []
    if _wt_code != 0:
        _wt_p.append(f"exit {_wt_code}")
    if len(_wt_files) != 1:
        _wt_p.append(f"expected one trail file, found {_wt_files}")
    else:
        _wt_text = open(_wt_files[0], encoding="utf-8").read()
        if "pytest -q" not in _wt_text:
            _wt_p.append("trail file lacks the fixture command 'pytest -q'")
        # The raw readout, not a summary: a header saying so, and each tool call and result.
        for _wt_want in ("# Raw transcript readout", "tool call: Bash", "tool result ("):
            if _wt_want not in _wt_text:
                _wt_p.append("trail file lacks %r" % _wt_want)
        if "Work trail for this helper: " + _wt_files[0] not in _wt_c:
            _wt_p.append("additionalContext does not name the trail path")
        if "audit1" not in os.path.basename(_wt_files[0]):
            _wt_p.append("file name lacks the agent id")
    _wt_check(f"{_wt_event} in a project thread writes the work trail and names its path", _wt_p)

_wt_dir = _wt_tf.mkdtemp(prefix="house-rules-worktrail-")
_wt_code, _wt_c = _wt_ctx("audit", post_agent_payload(), _wt_env(_wt_dir, projects=""))
_wt_code0, _wt_c0 = _wt_ctx("audit", post_agent_payload(), _wt_env("", projects=""))
_wt_p = []
if os.listdir(_wt_dir):
    _wt_p.append("a trail file was written outside a project thread")
if _wt_c != _wt_c0 or "Work trail" in _wt_c or not _wt_c:
    _wt_p.append("output differs outside a project thread")
_wt_check("audit outside a project thread writes no work trail and is unchanged", _wt_p)

_wt_dir = _wt_tf.mkdtemp(prefix="house-rules-worktrail-")
_wt_bad = os.path.join(_wt_dir, "afile")
open(_wt_bad, "w").close()
_wt_code, _wt_c = _wt_ctx("audit", post_agent_payload(), _wt_env(_wt_bad))
_wt_p = [] if "could not write the work trail" in _wt_c and _wt_code == 0 else [f"got {_wt_c[-200:]!r}"]
_wt_check("a work trail that cannot be written is named in additionalContext", _wt_p)

# The ordinary case: a ordinary prompt must never be touched, and never even emit anything -
# a non-zero exit or a wrong additionalContext here would corrupt or erase the user's prompt.
code, out, err = run_hook("userpromptaudit", userprompt_payload("please fix the failing test"))
if code == 0 and not out.strip():
    report("PASS", "userpromptaudit is silent on an ordinary prompt")
    print("          no additionalContext, no systemMessage - nothing to say")
else:
    report("FAIL", "userpromptaudit is silent on an ordinary prompt")
    print(f"          exit {code}, out {out[:150]!r}")

# A notification for a still-running task carries nothing finished to audit yet.
code, out, err = run_hook("userpromptaudit", userprompt_payload(_task_notification("audit1", status="running")))
if code == 0 and not out.strip():
    report("PASS", "userpromptaudit is silent on a not-yet-completed task notification")
else:
    report("FAIL", "userpromptaudit is silent on a not-yet-completed task notification")
    print(f"          exit {code}, out {out[:150]!r}")

upq = []
code, out, err = run_hook("userpromptaudit", "")
if code != 0 or out.strip():
    upq.append(f"empty payload: exit {code}, out {out[:120]!r} (must be silent, exit 0)")
code, out, err = run_hook("userpromptaudit", "not json at all {{{")
if code != 0 or out.strip():
    upq.append(f"unparseable payload: exit {code}, out {out[:120]!r}")
if not upq:
    report("PASS", "userpromptaudit never erases the prompt - exit 0 and silent on bad payloads")
else:
    report("FAIL", "userpromptaudit never erases the prompt - exit 0 and silent on bad payloads")
    for u in upq:
        print(f"          {u}")

upwire = []
prompts = _hj3.get("UserPromptSubmit") or []
if not any("\" userpromptaudit" in h.get("command", "") for e in prompts for h in e.get("hooks", [])):
    upwire.append("hooks.json's UserPromptSubmit has no userpromptaudit dispatch")
scope_entries = [e for e in prompts if any("\" scope" in h.get("command", "") for h in e.get("hooks", []))]
upa_entries = [e for e in prompts if any("\" userpromptaudit" in h.get("command", "") for h in e.get("hooks", []))]
if scope_entries and upa_entries and scope_entries[0] is upa_entries[0]:
    upwire.append("scope and userpromptaudit share one hook entry instead of two separate ones")
if not upwire:
    report("PASS", "userpromptaudit is its own UserPromptSubmit entry, separate from scope")
else:
    report("FAIL", "userpromptaudit is its own UserPromptSubmit entry, separate from scope")
    for u in upwire:
        print(f"          {u}")

# --- the "reported update" rule is present, in its own words -----------------------------------
# Not a drift check - nothing else in hook.py restates this rule's wording, since it's a
# verification habit like its two neighbors, not something mechanically checkable at a hook
# boundary. A straightforward presence check, same shape as the standards/tiered-docs ones above.
if "## A reported update is not a completed one" in rules_text:
    report("PASS", "house-rules.md states the reported-update-is-not-a-completed-one rule")
    print("          the rule heading is present")
else:
    report("FAIL", "house-rules.md states the reported-update-is-not-a-completed-one rule")
    print("          heading missing from rules/house-rules.md")
_nb_cases = []
_, _o, _ = run_hook("agentcap", json.dumps({"session_id": "v293", "agent_id": "sub1", "tool_name": "Agent",
                                             "tool_input": {"prompt": "x"}}), env=_e293)
_nb_cases.append(("enforced: a helper starting its own helper is refused, naming the fix: report back (#293)",
                  '"permissionDecision":"deny"' in _o and "Report back to the parent" in _o))
for _t, _ok in _nb_cases:
    report("PASS" if _ok else "FAIL", "never-blocked: " + _t)


# --- links owed: the end-of-turn check for a link that was never posted (#398) ---------------
def _lo_transcript(name, injected, uses):
    lines = [json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "go"}})]
    for text in injected:
        lines.append(json.dumps({"type": "attachment", "attachment": {
            "type": "hook_additional_context", "hookEvent": "PostToolUse", "content": text}}))
    for i, (tool, inp) in enumerate(uses):
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "lo%d" % i, "name": tool, "input": inp}]}}))
    return _hand_transcript(name, lines)


def _lo_run(transcript, retry=False, **env_extra):
    e = {k: v for k, v in os.environ.items() if k not in _WT_STRIP}
    e["HOUSE_RULES_COMMIT_CHECK"] = "off"
    e.update(env_extra)
    _, out, _ = run_hook("handover", stop_payload(transcript_path=transcript, stop_hook_active=retry,
                                                  last_assistant_message="ok"), env=e)
    try:
        o = json.loads(out)
    except Exception:
        o = {}
    return (o.get("hookSpecificOutput") or {}).get("additionalContext", ""), o.get("systemMessage", "")


_LO_RC = "House rules, work tracking: Remote Control just started (or was already running) for this session."
RCLINK_BASE = "https://claude.ai" + "/code/session_"
_LO_PT = {"CLAUDE_CODE_PROJECTS_SESSION": "1"}
_lo_a = _lo_transcript("lo-a", [_LO_RC], [("mcp__hearthbot__post_message", {"text": "hello"})])
_lo_ctx, _lo_sys = _lo_run(_lo_a, **_LO_PT)
_wt_check("links owed: a Remote Control note with no posted link is named at Stop",
          [] if "links owed" in _lo_ctx and "Remote Control" in _lo_ctx else [f"got {_lo_ctx!r}"])
_lo_b = _lo_transcript("lo-b", [_LO_RC], [("mcp__hearthbot__post_message",
                       {"attached_outputs": [{"kind": "link", "url": RCLINK_BASE + "abc"}]})])
_lo_ctx, _lo_sys = _lo_run(_lo_b, **_LO_PT)
_wt_check("links owed: a posted /code/session_ link silences it",
          [] if "links owed" not in _lo_ctx + _lo_sys else [f"got {_lo_ctx!r}"])
_lo_ctx, _lo_sys = _lo_run(_lo_a, retry=True, **_LO_PT)
_wt_check("links owed: on the retry it reports in systemMessage only",
          [] if "links owed" in _lo_sys and "links owed" not in _lo_ctx else [f"ctx {_lo_ctx!r} sys {_lo_sys!r}"])
_lo_x = "/mnt/project-files/work-trail/2026-01-01-helper-x1.md"
_lo_d = _lo_transcript("lo-d", ["Helper done. Work trail for this helper: %s. Attach it." % _lo_x],
                       [("mcp__hearthbot__post_message", {"text": "hello"})])
_lo_ctx, _lo_sys = _lo_run(_lo_d, **_LO_PT)
_wt_check("links owed: a work trail never posted is named by path",
          [] if "links owed" in _lo_ctx and _lo_x in _lo_ctx else [f"got {_lo_ctx!r}"])
_lo_d2 = _lo_transcript("lo-d2", ["Work trail for this helper: %s. Attach it." % _lo_x],
                        [("mcp__hearthbot__post_message", {"attached_outputs": [{"kind": "file", "path": _lo_x}]})])
_lo_ctx, _lo_sys = _lo_run(_lo_d2, **_LO_PT)
_wt_check("links owed: a posted work trail path silences it",
          [] if "links owed" not in _lo_ctx + _lo_sys else [f"got {_lo_ctx!r}"])
_lo_e = _lo_transcript("lo-e", [], [("mcp__hearthbot__update_progress_checklist", {"text": "Plain header\n- [ ] x"})])
_lo_ctx, _lo_sys = _lo_run(_lo_e, CLAUDE_CODE_REMOTE_SESSION_ID="cse_TEST1", **_LO_PT)
_wt_check("links owed: a checklist header without the thread link is named",
          [] if "links owed" in _lo_ctx and "checklist header" in _lo_ctx else [f"got {_lo_ctx!r}"])
_lo_e2 = _lo_transcript("lo-e2", [], [("mcp__hearthbot__update_progress_checklist",
                        {"text": "[Transcript](%sTEST1)\n- [ ] x" % RCLINK_BASE})])
_lo_ctx, _lo_sys = _lo_run(_lo_e2, CLAUDE_CODE_REMOTE_SESSION_ID="cse_TEST1", **_LO_PT)
_wt_check("links owed: a checklist header with the thread link is fine",
          [] if "links owed" not in _lo_ctx + _lo_sys else [f"got {_lo_ctx!r}"])
_lo_ctx, _lo_sys = _lo_run(_lo_a)
_wt_check("links owed: silent outside a project thread",
          [] if "links owed" not in _lo_ctx + _lo_sys else [f"got {_lo_ctx!r}"])


finish()
