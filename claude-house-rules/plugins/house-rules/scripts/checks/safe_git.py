#!/usr/bin/env python3
"""checks/safe_git.py - the safe git part: the guard, the branch and commit rules, the prompt timer (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/safe_git.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: safe_git")
print("=" * 43)
print()



# --- guard cases: 29 commands ---------------------------------------------------------------
# All judged from REPO_THEIRS, which is on main: the default branch, where a commit, push or
# merge is refused outright (#197). BRANCH_CASES below covers every other branch.
GUARD_CASES = [
    ("pass", None, "git status"),
    ("pass", None, "git log --oneline -n 20"),
    ("pass", None, "git diff HEAD~1"),
    ("pass", None, "npm test"),
    ("pass", None, "ls -la src"),
    ("pass", None, r"Get-ChildItem C:\Users"),
    ("pass", None, "npm run build && npm test"),
    ("deny", "is the default branch", 'git commit -m "wip"'),
    ("pass", None, "git add -A"),
    ("deny", "is the default branch", "git push origin main"),
    ("deny", "is the default branch", "git push --force-with-lease"),
    ("pass", None, "git checkout -b feature/x"),
    ("pass", None, "git switch main"),
    ("pass", None, "git branch -d old-feature"),
    ("pass", None, "git tag v1.2.0"),
    # #291: each destructive step is refused, and the refusal names the safe way (the cited text).
    ("deny", "commit the work on a new branch first", "git reset --hard origin/main"),
    # #292: background and hidden work, and a wait piped through tail/head, run without a prompt.
    ("pass", None, 'Start-Process powershell -WindowStyle Hidden -ArgumentList "-File build.ps1"'),
    ("pass", None, "npm run dev > dev.log 2>&1 &"),
    ("pass", None, "nohup ./long-task.sh"),
    ("pass", None, "until grep -q done status.txt; do sleep 5; done | tail -5"),
    ("pass", None, "timeout 600 ./run_tests.sh | head -40"),
    ("pass", None, "git log | head -5"),
    ("pass", None, "cat build.log | tail -50"),
    ("pass", None, "python sleepy.py | tail"),
    ("pass", None, "Start-Job -ScriptBlock { ./build.ps1 }"),
    ("deny", "move the folder into a `_to_delete/` folder", "rm -rf node_modules"),
    ("deny", "move the file into a `_to_delete/` folder", "rm styles.css"),  # never committed
    ("deny", "move the folder into a `_to_delete/` folder", "Remove-Item -Recurse -Force ./dist"),
    ("pass", None, "taskkill /IM node.exe /F"),
    ("pass", None, "kill 1234"),
    ("deny", "commit the work on a new branch first", "git checkout -- src/app.js"),
    ("deny", "commit the work on a new branch first", "git restore src/app.js"),
    ("deny", "keep the stash", "git stash drop"),
    ("deny", "keep the stash", "git stash clear"),
    ("deny", "for clean, move the files into a `_to_delete/` folder", "git clean -fdx"),
    ("deny", "rewrite on a copy branch", "git filter-branch --tree-filter x HEAD"),
    ("deny", "write a new file beside it", "truncate -s 0 app.log"),
    ("deny", "is the default branch", 'echo "starting" && git commit -m "wip"'),
    # #200: a new line or tab before the word used to hide it, since the subject is JSON-encoded.
    ("deny", "_to_delete/", "ls\nrm -rf build"),
    ("deny", "_to_delete/", "ls\trm -rf build"),
    ("deny", "_to_delete/", "ls &&\nrm -rf build"),
    ("pass", None, "ls\nnohup ./long-task.sh"),
    ("pass", None, "ls\nsetsid ./long-task.sh"),
    ("pass", None, "sleep 99 &\nls"),
    ("pass", None, "ls\nsleep 5 | tail -1"),
    ("pass", None, "ls -la\necho done"),
    ("pass", None, "make 2>&1\nls"),
    # #189: a quoted -c value with a space in it used to end git's option run early, so no
    # rule keyed on the subcommand ever matched.
    ("deny", "is the default branch", 'git -c user.name="aj\'s agent" commit -m "wip"'),
    ("deny", "commit the work on a new branch first", "git -c 'core.pager=less -R' reset --hard"),
    ("deny", "keep the stash", 'git -c "user.name=aj s agent" stash drop'),
]

for expect, rule, cmd in GUARD_CASES:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(REPO_THEIRS))
    if '"permissionDecision":"ask"' in out:
        got = "ask"
    elif '"permissionDecision":"deny"' in out:
        got = "deny"
    elif not out.strip() or "no house rule matched" in out:
        # Not prompting is the decision; the allow path now says so out loud rather than
        # being indistinguishable from the hook never having run.
        got = "pass"
    else:
        got = "malformed"
    result = "PASS" if got == expect else "FAIL"
    cited = ""
    if rule:
        if rule in out:
            cited = "; rule cited correctly"
        else:
            cited = f"; RULE NOT CITED (wanted: {rule})"
            result = "FAIL"
    report(result, cmd)
    print(f"          expected {expect}, got {got}{cited}")

print()

# --- branch-aware guard: the same command, judged by whose branch the checkout is on ---------
BRANCH_CASES = [
    # Off the default branch, a commit, an ordinary push and a merge or rebase run unasked (#197).
    (REPO_MINE, "claude/some-topic", "pass", None, 'git commit -m "checkpoint"'),
    (REPO_MINE, "claude/some-topic", "pass", None, "git push origin HEAD"),
    (REPO_MINE, "claude/some-topic", "pass", None, "git -c user.name=x commit -m y"),
    # Force-pushing rewrites history that was already safe, so it is not a checkpoint and the
    # exemption does not reach it - on any branch. #291: refused, naming the safe way.
    (REPO_MINE, "claude/some-topic", "deny", "push a new branch instead", "git push --force-with-lease"),
    (REPO_MINE, "claude/some-topic", "deny", "push a new branch instead", "git push -f origin HEAD"),
    # Discarding unsaved work is refused; replaying commits loses nothing (old ones stay in the reflog).
    (REPO_MINE, "claude/some-topic", "deny", "commit the work on a new branch first", "git reset --hard origin/main"),
    (REPO_MINE, "claude/some-topic", "pass", None, "git rebase -i HEAD~3"),
    (REPO_MINE, "claude/some-topic", "pass", None, "git merge main"),
    (REPO_MINE, "claude/some-topic", "pass", None, "git cherry-pick abc123"),
    # Deleting a branch, here or on the remote, is refused: aj deletes branches.
    (REPO_MINE, "claude/some-topic", "deny", "leave the branch for aj to delete", "git branch -D old"),
    (REPO_MINE, "claude/some-topic", "deny", "leave the branch for aj to delete", "git push origin --delete old"),
    # A push whose destination is the default branch is refused from any branch.
    (REPO_MINE, "claude/some-topic", "deny", DEFAULT, "git push origin HEAD:main"),
    # A command naming another repo is not talking about the branch we just read: refused, with the rewrite.
    (REPO_MINE, "claude/some-topic", "deny", "run it as plain `git ...`", 'git -C /other/repo commit -m "x"'),
    (REPO_MINE, "claude/some-topic", "deny", "run it as plain `git ...`", "git --git-dir=/other/.git push"),
    # Ownership buys nothing outside the commit rule.
    (REPO_MINE, "claude/some-topic", "deny", "_to_delete/", "rm -rf build"),
    # The default branch refuses; so does a branch I could not read (#291).
    (REPO_THEIRS, "main", "deny", DEFAULT, 'git commit -m "wip"'),
    (REPO_THEIRS, "main", "deny", DEFAULT, "git push origin main"),
    (REPO_DETACHED, "a detached HEAD", "deny", "git switch -c " + TEST_AGENT_PREFIX + "<topic>", 'git commit -m "wip"'),
    (REPO_NONE, "a directory that is not a repo", "deny", "git switch -c " + TEST_AGENT_PREFIX + "<topic>", 'git commit -m "wip"'),
    # #291: a commit on a branch the guard can't confirm is mine is refused, naming a new branch.
    (REPO_THEIRS_FEATURE, "feature/theirs", "deny", "git switch -c " + TEST_AGENT_PREFIX + "<topic>", 'git commit -m "wip"'),
]

for project_dir, label, expect, rule, cmd in BRANCH_CASES:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(project_dir))
    if '"permissionDecision":"ask"' in out:
        got = "ask"
    elif '"permissionDecision":"deny"' in out:
        got = "deny"
    elif not out.strip() or "no house rule matched" in out or '"permissionDecision":"allow"' in out:
        got = "pass"
    else:
        got = "malformed"
    result = "PASS" if got == expect else "FAIL"
    cited = ""
    if rule:
        if rule in out:
            cited = "; rule cited correctly"
        else:
            cited = f"; RULE NOT CITED (wanted: {rule})"
            result = "FAIL"
    report(result, f"{cmd}   [on {label}]")
    print(f"          expected {expect}, got {got}{cited}")

# The prompt has to say why the exemption did not apply, or the user is left reading a rule
# about branch ownership with no way to tell which branch they are on. Each of the three ways
# it can fail to apply names itself.
prompt_problems = []
for project_dir, cmd, wanted in [
    (REPO_THEIRS, 'git reset --hard HEAD', "`main` is the default branch"),
    (REPO_DETACHED, 'git commit -m "wip"', "HEAD is detached"),
    (REPO_NONE, 'git commit -m "wip"', "not inside a git repository"),
    (REPO_MINE, 'git -C /other/repo commit -m "x"', "names another repo"),
]:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(project_dir))
    if wanted not in out:
        prompt_problems.append(f"{cmd} in {os.path.basename(project_dir)}: no {wanted!r}")
if not prompt_problems:
    report("PASS", "a prompt the branch exemption could have silenced says why it did not")
    print("          names the branch, the detached HEAD, the missing repo, or the other repo")
else:
    report("FAIL", "a prompt the branch exemption could have silenced says why it did not")
    for p in prompt_problems:
        print(f"          {p}")

# --- #153: destructive git steps run unasked only on my branch with the work saved elsewhere ---
_sv_root = os.path.join(_FIXTURE_ROOT, "saved")
_sv_remote, _sv_repo = os.path.join(_sv_root, "remote.git"), os.path.join(_sv_root, "work")
os.makedirs(_sv_repo, exist_ok=True)


def _sv_git(*args, cwd=_sv_repo):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


_sv_git("init", "-q", "--bare", _sv_remote, cwd=_sv_root)
_sv_git("init", "-q")
_sv_git("switch", "-q", "-c", "claude/saved-topic")
with open(os.path.join(_sv_repo, "f.txt"), "w") as _f:
    _f.write("one\n")
_sv_git("add", "f.txt")
_sv_git("commit", "-q", "-m", "one")
_sv_git("remote", "add", "origin", _sv_remote)
_sv_git("push", "-q", "-u", "origin", "claude/saved-topic")


def _sv_guard(cmd):
    code, out, err = run_hook("guard", payload_for(cmd), env=verbose_env(env_in(_sv_repo)))
    m = re.search(r'"permissionDecision":"(ask|deny)"', out)
    return (m.group(1) if m else "pass"), out


def _sv_case(title, ok, detail):  # commit_case is defined further down this file
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


_sv_fail = []
for _cmd in ("git reset --hard HEAD", "git restore f.txt", "git checkout -- f.txt"):
    _got, _out = _sv_guard(_cmd)
    if _got != "pass" or "every commit on a remote" not in _out:
        _sv_fail.append("%s: %s %r" % (_cmd, _got, _out[:120]))
_sv_case(
    "guard: off the default branch with a clean tree and every commit pushed, reset/restore/checkout -- run unasked",
    not _sv_fail, "; ".join(_sv_fail) or "3 commands passed, each trace names the saved-elsewhere check",
)
_sv_fail = []
for _cmd in ("git push --force-with-lease", "git clean -fdx", "git stash drop", "git branch -D other", "rm -r sub"):
    if _sv_guard(_cmd)[0] != "deny":
        _sv_fail.append(_cmd)
_sv_case(
    "guard: even with the work saved, force-push, clean, stash drop, branch -D and a recursive rm are refused (#291)",
    not _sv_fail, "not refused: %s" % ", ".join(_sv_fail) if _sv_fail else "all 5 refused",
)
# #291: deletes are narrowed. A committed, unchanged file goes through; an edited or a never-committed one is refused.
_sv_del_clean = _sv_guard("rm f.txt")
with open(os.path.join(_sv_repo, "new.txt"), "w") as _f:
    _f.write("never committed\n")
_sv_del_new = _sv_guard("rm new.txt")
os.remove(os.path.join(_sv_repo, "new.txt"))
with open(os.path.join(_sv_repo, "f.txt"), "a") as _f:
    _f.write("uncommitted\n")
_sv_del_dirty = _sv_guard("rm f.txt")
_sv_case(
    "guard: deleting a committed, unchanged file goes through; an edited or never-committed file is refused, naming _to_delete/ (#291)",
    _sv_del_clean[0] == "pass" and _sv_del_new[0] == "deny" and _sv_del_dirty[0] == "deny"
    and "_to_delete/" in _sv_del_new[1] and "_to_delete/" in _sv_del_dirty[1],
    "clean %s | new %s | dirty %s" % (_sv_del_clean[0], _sv_del_new[0], _sv_del_dirty[0]),
)
_sv_dirty = _sv_guard("git reset --hard HEAD")
_sv_git("checkout", "--", "f.txt")
with open(os.path.join(_sv_repo, "f.txt"), "a") as _f:
    _f.write("two\n")
_sv_git("commit", "-q", "-am", "two")
_sv_unpushed = _sv_guard("git reset --hard HEAD~1")
_sv_case(
    "guard: an uncommitted change or an unpushed commit makes reset refused, and the refusal says which",
    _sv_dirty[0] == "deny" and "1 uncommitted or untracked file would be lost" in _sv_dirty[1]
    and _sv_unpushed[0] == "deny" and "1 commit on this branch is not on any remote" in _sv_unpushed[1],
    "dirty %r | unpushed %r" % (_sv_dirty[1][-160:], _sv_unpushed[1][-160:]),
)
_sv_git("push", "-q")
_sv_git("switch", "-q", "-c", "main")
_sv_git("push", "-q", "-u", "origin", "main")
_sv_theirs = _sv_guard("git reset --hard HEAD")
_sv_case(
    "guard: on the default branch, reset is refused even with a clean tree and everything pushed",
    _sv_theirs[0] == "deny" and "`main` is the default branch" in _sv_theirs[1], "out %r" % (_sv_theirs[1][-160:],),
)

# The exemption is a silent success path, and guard's silent paths trace by contract.
code, out, err = run_hook("guard", payload_for("git commit -m x"), env=verbose_env(env_in(REPO_MINE)))
if '"systemMessage"' in out and "claude/some-topic" in out and "not the default branch" in out:
    report("PASS", "an exempted command traces the branch it was exempted on")
    print(f"          said: {json.loads(out)['systemMessage']}")
else:
    report("FAIL", "an exempted command traces the branch it was exempted on")
    print(f"          got: {out!r}")

# A worktree's .git is a file, not a directory. Getting this wrong would silently downgrade
# every worktree to "not a repo" - which prompts, so it would never have been noticed.
_wt = os.path.join(_FIXTURE_ROOT, "worktree")
os.makedirs(_wt)
with open(os.path.join(_wt, ".git"), "w", encoding="utf-8") as f:
    f.write("gitdir: %s\n" % os.path.join(REPO_MINE, ".git"))
code, out, err = run_hook("guard", payload_for("git commit -m x"), env=verbose_env(env_in(_wt)))
if "not the default branch" in out:
    report("PASS", "a linked worktree resolves its branch through the gitdir: pointer")
    print("          .git as a file is followed, not mistaken for an unreadable repo")
else:
    report("FAIL", "a linked worktree resolves its branch through the gitdir: pointer")
    print(f"          got: {out!r}")

# Branch ownership follows where the command runs (payload cwd), not CLAUDE_PROJECT_DIR: a
# subagent's linked worktree on its own agent-prefix branch while the main checkout is on main.
if shutil.which("git"):
    def _own_git(d, *a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", d] + list(a),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def _own_branch_repo(name, branch):
        d = os.path.join(_FIXTURE_ROOT, name)
        os.makedirs(d)
        _own_git(d, "init", "-q", "-b", "main")
        _own_git(d, "commit", "-q", "--allow-empty", "-m", "init")
        if branch != "main":
            _own_git(d, "switch", "-q", "-c", branch)
        return d

    def _own_ask(cmd, project, cwd=None, **extra):
        pl = {"session_id": "verify", "tool_name": "Bash", "tool_input": {"command": cmd}}
        if cwd:
            pl["cwd"] = cwd
        env = env_in(project)
        env["HOUSE_RULES_OWNED_BRANCHES"] = ""  # no extras (an empty value still counts as set, #341)
        env.update(extra)
        out = run_hook("guard", json.dumps(pl), env=env)[1]
        m = re.search(r'"permissionDecision":"(\w+)"', out)
        return m.group(1) if m else "silent"

    _own_main = _own_branch_repo("own-main", "main")
    _own_wt = os.path.join(_FIXTURE_ROOT, "own-main-wt")
    _own_git(_own_main, "worktree", "add", "-q", "-b", TEST_AGENT_PREFIX + "sub", _own_wt)
    _own_ccr = _own_branch_repo("own-ccr", "ccr-a03de58c-0j19tb")
    _own_foo = _own_branch_repo("own-foo", "foo/x")
    _own_res = {
        "wt commit": _own_ask("git commit -m x", _own_main, _own_wt),
        "wt push": _own_ask("git push", _own_main, _own_wt),
        "wt force push": _own_ask("git push --force", _own_main, _own_wt),
        "wt merge": _own_ask("git merge other", _own_main, _own_wt),
        "no cwd": _own_ask("git commit -m x", _own_main),
        "cd into wt": _own_ask('cd "%s" && git commit -m x' % _own_wt, _own_main, _own_main),
        "two cds": _own_ask("cd %s && cd %s && git commit -m x" % (_own_wt, _own_main), _own_main, _own_main),
        "ccr": _own_ask("git commit -m x", _own_ccr),
        "foo off": _own_ask("git commit -m x", _own_foo),
        "foo on": _own_ask("git commit -m x", _own_foo, HOUSE_RULES_OWNED_BRANCHES="bar/, foo/"),
    }
    _own_res["-C wt"] = _own_ask("git -C %s commit -m x" % _own_wt, _own_main, _own_main)
    # #203: "cd" inside a commit message is not a directory change.
    _own_res["cd in message"] = _own_ask('git commit -m "fix cd handling"', _own_main, _own_wt)
    # #291: a force push, a folder the guard can't follow (two cds) and a branch not confirmed mine
    # (foo/x without HOUSE_RULES_OWNED_BRANCHES) are refused, not asked.
    _own_want = {"wt commit": "allow", "wt push": "allow", "wt force push": "deny", "wt merge": "allow",
                 "no cwd": "deny", "cd into wt": "allow", "two cds": "deny", "ccr": "allow",
                 "foo off": "deny", "foo on": "allow", "-C wt": "allow",
                 "cd in message": "allow"}
    if _own_res == _own_want:
        report("PASS", "guard judges the branch by the payload cwd, a leading cd and git -C")
        print("          worktree commit/push/merge allowed; force push, main, two cds and a branch not mine refused")
    else:
        report("FAIL", "guard judges the branch by the payload cwd, a leading cd and git -C")
        print(f"          got: {_own_res}")
else:
    report("SKIP", "guard judges ownership by the payload cwd (real git worktree)")
    print("          no git binary on PATH")

# --- #198: a prompt nobody can answer is refused, not left waiting ----------------------------
# Inside a subagent (payload agent_id) or when aj last wrote longer ago than the prompt timeout,
# guard refuses instead of asking, and the refusal goes on the waiting-on-you list.
_ua_dir = os.path.join(_FIXTURE_ROOT, "unattended")
os.makedirs(_ua_dir)
subprocess.run(["git", "init", "-q", "-b", "AjsAgent/ua", _ua_dir], check=True)


def _ua_guard(session, extra=None, env_extra=None, tool="Bash", tool_input=None):
    # #291: a destructive step is asked about only when it cites a source proving no safe way exists.
    pl = {"session_id": session, "cwd": _ua_dir, "tool_name": tool,
          "tool_input": tool_input or {"command": "rm -rf build", "description": "no safe way: the rm manual page"}}
    pl.update(extra or {})
    e = env_in(_ua_dir)
    e.pop("HOUSE_RULES_PROMPT_TIMEOUT", None)
    e.update(env_extra or {})
    return run_hook("guardwrite" if tool == "Write" else "guard", json.dumps(pl), env=e)[1]


def _ua_seen(session, ago):
    p = os.path.join(tempfile.gettempdir(), "house-rules-last-seen-%s" % session)
    with open(p, "w", encoding="utf-8") as f:
        f.write(str(time.time() - ago))
    atexit.register(lambda: os.path.exists(p) and os.remove(p))


def _ua_dec(out):
    m = re.search(r'"permissionDecision":"(\w+)"', out)
    return m.group(1) if m else "silent"


_ua_sub = _ua_guard("verify-ua-sub", {"agent_id": "a1"})
_ua_sub_off = _ua_guard("verify-ua-sub-off", {"agent_id": "a1"}, {"HOUSE_RULES_PROMPT_TIMEOUT": "off"})
_ua_sub_commit = _ua_guard("verify-ua-sub-c", {"agent_id": "a1"}, tool_input={"command": "git commit -m x"})
with open(os.path.join(_ua_dir, "kept.txt"), "w", encoding="utf-8") as _f:
    _f.write("a\nb\n")
subprocess.run(["git", "-C", _ua_dir, "add", "kept.txt"], check=True)
_ua_sub_write = _ua_guard("verify-ua-sub-w", {"agent_id": "a1"}, tool="Write",
                          tool_input={"file_path": os.path.join(_ua_dir, "kept.txt"), "content": "c\n"})
_ua_case_ok = (_ua_dec(_ua_sub) == "deny" and "inside a helper (subagent)" in _ua_sub
               and _ua_dec(_ua_sub_off) == "ask" and _ua_dec(_ua_sub_commit) == "allow"
               and _ua_dec(_ua_sub_write) == "deny")
report("PASS" if _ua_case_ok else "FAIL",
       "guard: inside a subagent a destructive step (and a full-file Write) is refused, not asked; a commit still runs")
print("          rm %s, rm with timer off %s, commit %s, Write %s"
      % (_ua_dec(_ua_sub), _ua_dec(_ua_sub_off), _ua_dec(_ua_sub_commit), _ua_dec(_ua_sub_write)))

# --- #261: replay the 2026-10-15 audit entries (docs/guard-friction-audit-2026-10-15.md) --------
_fr_sid = "verify-fr-sub"
_fr_scratch = "/tmp/claude-0/%s/%s/scratchpad" % (re.sub(r"[^A-Za-z0-9]", "-", _ua_dir), _fr_sid)


def _fr(cmd, agent=True):
    out = _ua_guard(_fr_sid, {"agent_id": "a1"} if agent else None, tool_input={"command": cmd})
    try:
        reason = json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason", "")
    except (ValueError, KeyError):
        reason = ""
    return _ua_dec(out), reason


_fr_fail = []
_fr_top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=_ua_dir, stdout=subprocess.PIPE,
                         universal_newlines=True).stdout.strip()
for _n, _cmd in (
    ("1", "G=%s; git -C $G add f && git -C $G commit -m x -- f && git -C $G push -q origin AjsAgent/ua" % _ua_dir),
    ("2", "git -C %s commit -m x" % _ua_dir),
    ("3", "cd %s && git commit -m x" % _ua_dir),
    ("3b", "cd %s; git commit -m x" % _ua_dir),
    ("3c", 'D="%s"; cd ${D} && git commit -m x' % _ua_dir),
    ("5", "sleep 1; ls | head"),
    ("7", "python3 x.py | tail -5"),
    ("7b", "until grep x f; do sleep 1; done | tail"),
    ("8", "rm -rf %s/build" % _fr_scratch),
    ("9", "cd /nonexistent/other && git commit -m x"),
):
    _d, _r = _fr(_cmd)
    if _d == "deny" and "Do not retry" in _r:
        _fr_fail.append("%s: refused with Do not retry" % _n)
    elif _n == "9" and not (_d == "deny" and ("run it as plain `git ...` from %s, with no cd, -C or variables, "
                                              "and it will be checked normally" % _fr_top) in _r):
        _fr_fail.append("9: %s %r" % (_d, _r[-160:]))
    elif _n != "9" and _d == "deny":  # #292: 7b (a wait piped through tail) now runs too
        _fr_fail.append("%s: refused %r" % (_n, _r[-160:]))
for _cmd in ("rm -rf /home/user/x", "git push origin main", "rm -rf %s/../x" % _fr_scratch, "rm -rf /tmp/claude-0/*"):
    _d, _r = _fr(_cmd)
    if _d != "deny" or (_cmd.startswith("rm -rf /home") and "_to_delete/" not in _r) \
            or (_cmd.startswith("git push") and "Do not retry" not in _r):
        _fr_fail.append("still-refused %r: %s" % (_cmd, _d))
if _fr("kill -9 1")[0] == "deny":  # #292: killing a process no longer stops the agent
    _fr_fail.append("kill -9 1 was refused")
_d, _r = _fr("S=%s/old-plugin; rm -rf $S" % _fr_scratch)
if _d == "deny":
    _fr_fail.append("rm via a same-command assignment inside the scratchpad was refused %r" % _r[-120:])
_d, _r = _fr("S=/home/user/x; rm -rf $S")
if _d != "deny" or "_to_delete/" not in _r:
    _fr_fail.append("rm via an assignment outside the scratchpad: %s %r" % (_d, _r[-120:]))
_sv_case("guard: audit entries 1, 2, 3, 5, 7, 8, 9 no longer dead-end routine work; deletes and a push to main still refuse",
         not _fr_fail, "; ".join(_fr_fail) or "routine ones pass or get the rewrite text; deletes name _to_delete/")

_ua_seen("verify-ua-away", 600)
_ua_seen("verify-ua-here", 30)
_ua_away = _ua_guard("verify-ua-away")
_ua_here = _ua_guard("verify-ua-here")
_ua_never = _ua_guard("verify-ua-never-wrote")
report("PASS" if _ua_dec(_ua_away) == "ask" and "aj has not written" not in _ua_away
       and _ua_dec(_ua_here) == "ask" and _ua_dec(_ua_never) == "ask" else "FAIL",
       "guard (#290): aj idle past the timeout still gets an ask, not an immediate deny; same when recent or no record")
print("          away %s, here %s, no record %s" % (_ua_dec(_ua_away), _ua_dec(_ua_here), _ua_dec(_ua_never)))

_ua_list = os.path.join(_ua_dir, ".git", "house-rules", "waiting-on-you.json")
try:
    _ua_entries = json.load(open(_ua_list, encoding="utf-8"))
except (OSError, ValueError):
    _ua_entries = []
_ua_st = {e.get("session_id"): e.get("status") for e in _ua_entries}
_ua_scope = run_hook("scope", json.dumps({"session_id": "verify-ua-sub", "prompt": "back now"}),
                     env=env_in(_ua_dir))[1]
_ua_seen_file = os.path.join(tempfile.gettempdir(), "house-rules-last-seen-verify-ua-sub")
report("PASS" if _ua_st.get("verify-ua-sub") == "refused" and "verify-ua-away" not in _ua_st
       and "rm -rf build" in _ua_scope and not os.path.isfile(_ua_seen_file) else "FAIL",
       "guard: a subagent refusal goes on the waiting-on-you list and scope reports it; an idle-aj ask is not listed")
print("          statuses %r, scope reported it: %s" % (_ua_st, "rm -rf build" in _ua_scope))
if os.path.isfile(_ua_seen_file):
    os.remove(_ua_seen_file)

# --- guard's commit-time docs-tier reminder: real git fixtures, since this path itself uses -----
# git diff --cached, unlike the rest of guard which stays subprocess-free.
if shutil.which("git"):
    def _git(d, *args):
        subprocess.run(
            ["git", "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

    def _docs_guard_repo(name, branch, files, staged):
        d = os.path.join(_FIXTURE_ROOT, name)
        os.makedirs(d)
        _git(d, "init", "-q")
        _git(d, "config", "user.email", "t@t.com")
        _git(d, "config", "user.name", "t")
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(d, "add", "README.md")
        _git(d, "commit", "-q", "-m", "init")
        if branch != "main" and branch != "master":
            _git(d, "checkout", "-q", "-b", branch)
        for path, content in files.items():
            full = os.path.join(d, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        if staged:
            _git(d, "add", *staged)
        return d

    DOCSGUARD_CLAUDE_SOURCE_ONLY = _docs_guard_repo(
        "docsguard-claude-source-only", "claude/topic", {"a.py": "print(1)\n"}, ["a.py"]
    )
    DOCSGUARD_CLAUDE_SOURCE_AND_DOCS = _docs_guard_repo(
        "docsguard-claude-source-and-docs", "claude/topic",
        {"a.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, ["a.py", "docs/ProjectState.md"],
    )
    DOCSGUARD_CLAUDE_CONFIG_ONLY = _docs_guard_repo(
        "docsguard-claude-config-only", "claude/topic", {"config.json": "{}\n"}, ["config.json"]
    )
    DOCSGUARD_MAIN_SOURCE_ONLY = _docs_guard_repo(
        "docsguard-main-source-only", "main", {"a.py": "print(1)\n"}, ["a.py"]
    )

    docsguard_cases = [
        (
            "a claude/ branch commit with a staged source file and nothing under docs/ gets a "
            "docs reminder, still allowed",
            DOCSGUARD_CLAUDE_SOURCE_ONLY, "allow", True,
        ),
        (
            "a claude/ branch commit with a staged source file AND a staged docs/ file gets no "
            "reminder",
            DOCSGUARD_CLAUDE_SOURCE_AND_DOCS, "allow", False,
        ),
        (
            "a claude/ branch commit with no staged source file (config only) gets no reminder",
            DOCSGUARD_CLAUDE_CONFIG_ONLY, "allow", False,
        ),
        (
            "a default-branch commit is refused before any docs reminder",
            DOCSGUARD_MAIN_SOURCE_ONLY, "deny", False,
        ),
    ]
    for title, repo, expect_decision, expect_reminder in docsguard_cases:
        code, out, err = run_hook("guard", payload_for('git commit -m "wip"'), env=env_in(repo))
        problems = []
        if code != 0:
            problems.append(f"exit {code}, must never be non-zero")
        if expect_decision == "allow":
            if '"permissionDecision":"ask"' in out:
                problems.append("guard asked, expected a silent/allow decision")
        elif '"permissionDecision":"deny"' not in out or "is the default branch" not in out:
            problems.append("guard did not refuse, expected it to (the default branch refuses a commit)")
        has_reminder = "documentation goes in tiers" in out.lower() or "Documentation goes in tiers" in out
        if expect_reminder and not has_reminder:
            problems.append("no docs-tier reminder in the output, expected one")
        if not expect_reminder and has_reminder:
            problems.append("a docs-tier reminder fired, expected none")
        if not problems:
            report("PASS", title)
            print(f"          {out[:200]}")
        else:
            report("FAIL", title)
            for p in problems:
                print(f"          {p}")

    # git missing/unusable: guard's decision must be UNCHANGED (still exempted-allow on a
    # claude/ branch commit), with a "could not tell" note replacing the reminder, not silence.
    _no_git_env = env_in(DOCSGUARD_CLAUDE_SOURCE_ONLY)
    _no_git_env["PATH"] = _FIXTURE_ROOT  # a directory with no git binary in it
    code, out, err = run_hook("guard", payload_for('git commit -m "wip"'), env=_no_git_env)
    if (
        code == 0
        and '"permissionDecision":"ask"' not in out
        and "not the default branch" in out
        and "could not tell" in out
    ):
        report("PASS", "a missing git binary leaves guard's own decision unchanged, and says so")
        print(f"          {out[:200]}")
    else:
        report("FAIL", "a missing git binary leaves guard's own decision unchanged, and says so")
        print(f"          exit {code}, out {out[:200]!r}")

    # A command naming another repo: guard already prompts (RULE_COMMIT); the docs check must
    # not try to resolve that other repo's staged files, and says it could not tell rather than
    # silently assuming either answer.
    code, out, err = run_hook(
        "guard",
        payload_for('git -C /some/other/repo commit -m "wip"'),
        env=env_in(DOCSGUARD_CLAUDE_SOURCE_ONLY),
    )
    # #291: refused with the rewrite named, before the docs check reads any other repo's staged files.
    if '"permissionDecision":"deny"' in out and "another repo" in out and "run it as plain `git ...`" in out:
        report("PASS", "a -C/--git-dir commit is refused naming the rewrite, not answered with another repo's files")
        print(f"          {out[:250]}")
    else:
        report("FAIL", "a -C/--git-dir commit is refused naming the rewrite, not answered with another repo's files")
        print(f"          out {out[:250]!r}")

    # --- what a commit will ACTUALLY include, not just what is already staged -----------------
    # doc-ref c79f docs/6-decisions/Decisions.md: guard fires before the command it judges runs, so a
    # docs-only-staged-right-now check misses an add-then-commit or an -a/-am commit entirely.
    DOCSGUARD_ADD_THEN_COMMIT_SOURCE = _docs_guard_repo(
        "docsguard-add-then-commit-source", "claude/topic", {"f.py": "print(1)\n"}, staged=[]
    )
    DOCSGUARD_ADD_THEN_COMMIT_WITH_DOCS = _docs_guard_repo(
        "docsguard-add-then-commit-with-docs", "claude/topic",
        {"f.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, staged=[],
    )
    DOCSGUARD_ADD_DOT_WITH_DOCS = _docs_guard_repo(
        "docsguard-add-dot-with-docs", "claude/topic",
        {"f.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, staged=[],
    )

    def _docs_guard_repo_with_tracked_change(name):
        # -am needs a file that is TRACKED and modified, not staged - a plain new file (never
        # committed) is not what -a stages.
        d = os.path.join(_FIXTURE_ROOT, name)
        os.makedirs(d)
        _git(d, "init", "-q")
        _git(d, "config", "user.email", "t@t.com")
        _git(d, "config", "user.name", "t")
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(d, "add", "README.md")
        _git(d, "commit", "-q", "-m", "init")
        _git(d, "checkout", "-q", "-b", "claude/topic")
        with open(os.path.join(d, "tracked.py"), "w", encoding="utf-8") as f:
            f.write("print(1)\n")
        _git(d, "add", "tracked.py")
        _git(d, "commit", "-q", "-m", "add tracked")
        with open(os.path.join(d, "tracked.py"), "w", encoding="utf-8") as f:
            f.write("print(2)\n")
        return d

    DOCSGUARD_AM_SOURCE_ONLY = _docs_guard_repo_with_tracked_change("docsguard-am-source-only")
    DOCSGUARD_QUOTED_PATH = _docs_guard_repo(
        "docsguard-quoted-path", "claude/topic", {"my file.py": "print(1)\n"}, staged=[]
    )

    effective_cases = [
        (
            "git add f.py && git commit -m f",
            "add-then-commit of a new source file, nothing under docs/, gets the reminder",
            DOCSGUARD_ADD_THEN_COMMIT_SOURCE, True,
        ),
        (
            "git add f.py docs/ProjectState.md && git commit -m f",
            "add-then-commit that also adds a docs/ path gets no reminder",
            DOCSGUARD_ADD_THEN_COMMIT_WITH_DOCS, False,
        ),
        (
            "git add . && git commit -m f",
            "git add . with an untracked docs/ change present gets no reminder",
            DOCSGUARD_ADD_DOT_WITH_DOCS, False,
        ),
        (
            "git commit -am f",
            "-am against a tracked, modified source file with nothing under docs/ gets the reminder",
            DOCSGUARD_AM_SOURCE_ONLY, True,
        ),
        (
            'git add "my file.py" && git commit -m x',
            "a quoted add path with a space is tokenized as one argument (shlex), and gets the reminder",
            DOCSGUARD_QUOTED_PATH, True,
        ),
    ]
    for cmd, title, repo, expect_reminder in effective_cases:
        code, out, err = run_hook("guard", payload_for(cmd), env=env_in(repo))
        has_reminder = "documentation goes in tiers" in out.lower()
        if code == 0 and has_reminder == expect_reminder:
            report("PASS", title)
            print(f"          {out[:200]}")
        else:
            report("FAIL", title)
            print(f"          exit {code}, expected reminder={expect_reminder}, out {out[:250]!r}")

    # Unbalanced quotes in an add statement: shlex.split raises ValueError, which must read as
    # "could not tell" - never a guess, and never a change to guard's own decision.
    code, out, err = run_hook(
        "guard", payload_for('git add "unbalanced.py && git commit -m x'), env=env_in(DOCSGUARD_QUOTED_PATH)
    )
    if code == 0 and '"permissionDecision":"ask"' not in out and "not the default branch" in out and "could not tell" in out.lower():
        report("PASS", "an add statement with unbalanced quotes is a could-not-tell, not a guess")
        print(f"          {out[:200]}")
    else:
        report("FAIL", "an add statement with unbalanced quotes is a could-not-tell, not a guess")
        print(f"          exit {code}, out {out[:250]!r}")
else:
    report("SKIP", "guard's commit-time docs-tier reminder (real git fixtures)")
    print("          no git binary on PATH")

print()

# The branch is read from a file, never by running git. A subprocess here would sit on the
# critical path of every shell command, in the one handler that blocks when it fails.
_hook_src = read(SAFE_GIT)  # branch_ownership moved to the safe git part (#358)
_own = _hook_src[_hook_src.index("def branch_ownership") :]
_own = _own[: _own.index("\ndef ", 1)]
# Call syntax only, not prose. Why the docstring names rev-parse: docs/architecture.md, "Why `.git/HEAD` and not `git rev-parse --abbrev-ref HEAD`".
_shelling = [c for c in ("subprocess.", "os.popen(", "os.system(", "check_output") if c in _own]
if not _shelling:
    report("PASS", "branch ownership is read from .git/HEAD, never by shelling out to git")
    print("          guard blocks on failure, so it must not depend on a process that can hang")
else:
    report("FAIL", "branch ownership is read from .git/HEAD, never by shelling out to git")
    print(f"          branch_ownership() reached for: {', '.join(_shelling)}")

print()

# --- fail-closed: an internal error in guard must BLOCK, not shrug --------------------------
crash_snippet = (
    "import sys, hook\n"
    "def boom():\n"
    "    raise OSError('simulated stdin failure')\n"
    "hook.safe_git.read_payload = boom\n"  # #358: event_guard lives in the safe git part now
    "sys.exit(hook.main(['hook.py', 'guard']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
code, out, err = proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
    "utf-8", "replace"
)
if code == 2 and err.strip() and not out.strip():
    report("PASS", "guard that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          said: {err.strip().splitlines()[0]}")
else:
    report("FAIL", "guard that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          exit code was {code}; stdout={out!r} stderr={err!r}")

# --- the guard matches the command field, not the whole payload -----------------------------
desc_payload = json.dumps(
    {
        "session_id": "verify",
        "tool_name": "Bash",
        "tool_input": {
            "command": "npm test",
            "description": "check for uncommitted changes before we commit and push",
        },
    }
)
code, out, err = run_hook("guard", desc_payload, env=verbose_env())
if '"permissionDecision"' not in out and "`npm test`" in out:
    report("PASS", "a harmless command with a git-mentioning description does not prompt")
    print("          no prompt, and the trace names `npm test` - the command, not the description")
else:
    report("FAIL", "a harmless command with a git-mentioning description does not prompt")
    print(f"          got: {out}")

# --- the fallback tier: no command field must never mean "wave it through" ------------------
nocmd_payload = json.dumps(
    {"session_id": "verify", "tool_name": "PowerShell", "tool_input": {"script": "git commit -m wip"}}
)
code, out, err = run_hook("guard", nocmd_payload, env=env_in(REPO_THEIRS))
if '"permissionDecision":"deny"' in out and "is the default branch" in out:
    report("PASS", "a payload with no command field still gets checked (whole-payload fallback)")
    print("          fell back to the old behaviour rather than passing it unchecked")
else:
    report("FAIL", "a payload with no command field still gets checked (whole-payload fallback)")
    print(f"          got: {out}")

print()

# --- guardwrite: a Write that would replace an existing file's entire contents asks first ----
RULE_EDIT_IN_PLACE = "Edit in place; a full rewrite is a delete, not an edit"


def guardwrite_payload(file_path, content="new content\n"):
    return json.dumps(
        {
            "session_id": "verify",
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


_gw_dir = tempfile.mkdtemp(prefix="house-rules-guardwrite-")
atexit.register(shutil.rmtree, _gw_dir, True)
_gw_existing = os.path.join(_gw_dir, "styles.css")
with open(_gw_existing, "w", encoding="utf-8") as f:
    f.write("body { color: red; }\n.header { margin: 0; }\n")
_gw_new = os.path.join(_gw_dir, "new-file.css")

code, out, err = run_hook("guardwrite", guardwrite_payload(_gw_existing))
if (
    '"permissionDecision":"deny"' in out
    and RULE_EDIT_IN_PLACE in out
    and os.path.basename(_gw_existing) in out
    and "2 existing line(s)" in out
    and "edit it in place with the Edit tool" in out
):
    report("PASS", "Write over a file I did not create is refused, naming the fix: edit it in place (#293)")
    print("          names the file, cites the rule, counts the discarded lines and gives the fix")
else:
    report("FAIL", "Write over a file I did not create is refused, naming the fix: edit it in place (#293)")
    print(f"          got: {out}")

code, out, err = run_hook("guardwrite", guardwrite_payload(_gw_new))
if '"permissionDecision"' not in out:
    report("PASS", "Write to a brand-new path does not ask - there is nothing to discard yet")
    print("          no prompt for a file that does not already exist")
else:
    report("FAIL", "Write to a brand-new path does not ask - there is nothing to discard yet")
    print(f"          got: {out}")

code, out, err = run_hook("guardwrite", "")
if code == 0 and '"permissionDecision"' not in out:
    report("PASS", "guardwrite with an empty payload does not crash or silently allow-by-default")
    print("          exits 0 with no permission decision, same contract as guard's empty case")
else:
    report("FAIL", "guardwrite with an empty payload does not crash or silently allow-by-default")
    print(f"          exit code {code}, got: {out}")

nofile_payload = json.dumps({"session_id": "verify", "tool_name": "Write", "tool_input": {"content": "x"}})
code, out, err = run_hook("guardwrite", nofile_payload)
if code == 0 and '"permissionDecision"' not in out:
    report("PASS", "guardwrite with no file_path field does not ask")
    print("          nothing to resolve on disk, so nothing to check")
else:
    report("FAIL", "guardwrite with no file_path field does not ask")
    print(f"          exit code {code}, got: {out}")


# --- #344: an Edit that replaces more than half a file's lines is a wholesale rewrite --------------------------
_ge_file = os.path.join(_gw_dir, "tracked-hundred.txt")
with open(_ge_file, "w", encoding="utf-8") as f:
    f.write("".join("line %03d\n" % i for i in range(100)))
subprocess.run(["git", "init", "-q", _gw_dir], check=False)
subprocess.run(["git", "-C", _gw_dir, "add", "tracked-hundred.txt"], check=False)  # tracked, so not an own untracked file


def _ge_payload(n, tool="Edit", replace_all=False, old=None):
    old_s = old if old is not None else "".join("line %03d\n" % i for i in range(n))
    return json.dumps({"session_id": "verify", "tool_name": tool, "tool_input": {
        "file_path": _ge_file, "old_string": old_s, "new_string": "x\n", "replace_all": replace_all}})


_ge_env = dict(os.environ, CLAUDE_PROJECT_DIR=_gw_dir)
code, out, err = run_hook("guardwrite", _ge_payload(51), env=_ge_env)
if '"permissionDecision":"deny"' in out and "51 of the 100 lines" in out and "approval by name" in out:
    report("PASS", "an Edit replacing 51 of a file's 100 lines is refused like a whole-file Write (#344)")
else:
    report("FAIL", "an Edit replacing 51 of a file's 100 lines is refused like a whole-file Write (#344)")
    print(f"          got: {out} {err}")
code, out, err = run_hook("guardwrite", _ge_payload(49), env=_ge_env)
if '"permissionDecision"' not in out and code == 0:
    report("PASS", "an Edit replacing 49 of a file's 100 lines passes (#344)")
else:
    report("FAIL", "an Edit replacing 49 of a file's 100 lines passes (#344)")
    print(f"          got: {out} {err}")
code, out, err = run_hook("guardwrite", _ge_payload(50), env=_ge_env)
if '"permissionDecision"' not in out:
    report("PASS", "an Edit replacing exactly half (50 of 100 lines) passes: the bar is more than half (#344)")
else:
    report("FAIL", "an Edit replacing exactly half (50 of 100 lines) passes: the bar is more than half (#344)")
code, out, err = run_hook("guardwrite", _ge_payload(0, replace_all=True, old="line 0"), env=_ge_env)
if '"permissionDecision":"deny"' in out:
    report("PASS", "a replace_all Edit counts old_string's line count times its occurrences (#344)")
else:
    report("FAIL", "a replace_all Edit counts old_string's line count times its occurrences (#344)")
    print(f"          got: {out} {err}")

# fail-closed: an internal error in guardwrite must BLOCK, not shrug - same contract as guard,
# since this is also a PreToolUse hook that can stop a tool call from running.
crash_snippet_gw = (
    "import sys, hook\n"
    "def boom():\n"
    "    raise OSError('simulated stdin failure')\n"
    "hook.safe_git.read_payload = boom\n"  # #358: event_guardwrite lives in the safe git part now
    "sys.exit(hook.main(['hook.py', 'guardwrite']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet_gw], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
code, out, err = proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
    "utf-8", "replace"
)
if code == 2 and err.strip() and not out.strip():
    report("PASS", "guardwrite that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          said: {err.strip().splitlines()[0]}")
else:
    report("FAIL", "guardwrite that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          exit code was {code}; stdout={out!r} stderr={err!r}")

# --- the commit rule draws the line at branch ownership, and records both reversals ----------
# It has now been rewritten twice for the same reason, so what is pinned here is the shape that
# survived: who owns the branch, not whether permission was granted for this change. The earlier
# "open pull request" wording gated on a state only reachable *after* the first commit, which is
# exactly the commit that protects a day's work.
missing = [
    ph
    for ph in [
        "On a branch I created",
        "On a branch the user authored",
        "I do not finish what the user started",
        "ephemeral container",
        "mis-drawn",
    ]
    if ph.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the commit rule draws the line at branch ownership and records both reversals")
    print("          my branches: commit freely; theirs: mutate nothing; both losses written down")
else:
    report("FAIL", "the commit rule draws the line at branch ownership and records both reversals")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# --- the guard cites rules that actually exist in the rules document -------------------------
# It cites a rule by its heading, and nothing checked that the heading was still there. Renaming
# "Never commit without asking" to "Never commit to `main` without asking" would have left the
# permission prompt naming a rule the user could not find - a silent drift in the one place the
# plugin speaks directly to them.
bucket_titles = re.findall(r'^\s*\("([^"]+)", GUARD_R\d+\),', read(SAFE_GIT), re.MULTILINE)
headings = [ln.lstrip("# ").strip() for ln in rules_text.split("\n") if ln.startswith("## ")]
orphans = [t for t in bucket_titles if t not in headings]
if bucket_titles and not orphans:
    report("PASS", "every rule the guard cites is a real heading in the rules document")
    print(f"          {len(bucket_titles)} bucket titles, all found in house-rules.md")
else:
    report("FAIL", "every rule the guard cites is a real heading in the rules document")
    for o in orphans:
        print(f"          guard cites {o!r}, which is not a heading in house-rules.md")
    if not bucket_titles:
        print("          no GUARD_BUCKETS titles were found at all - the pattern has drifted")
for event, payload, needle, why in trace_cases[:1]:  # guard
    code, out, err = run_hook(event, payload, env=verbose_env())
    if code == 0 and '"systemMessage"' in out and needle in out:
        report("PASS", f"{event} traces its decision on {why}")
        print(f"          says what it looked at and what it concluded; names {needle!r}")
    else:
        report("FAIL", f"{event} traces its decision on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
for event, payload, needle, why in trace_cases[:1]:  # guard
    code, out, err = run_hook(event, payload, env=_dflt)
    if code == 0 and not out.strip():
        report("PASS", f"{event} is silent by default on {why}")
        print("          no-op decision, nothing emitted (HOUSE_RULES_TRACE unset)")
    else:
        report("FAIL", f"{event} is silent by default on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
    code, out, err = run_hook(event, payload, env=verbose_env())
    if code == 0 and needle in out and '"systemMessage"' in out:
        report("PASS", f"HOUSE_RULES_TRACE=verbose restores the {event} trace on {why}")
    else:
        report("FAIL", f"HOUSE_RULES_TRACE=verbose restores the {event} trace on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
for event, payload, needle in (
    ("guard", "", "guard: empty payload"),
    ("guardwrite", "", "guardwrite: empty payload"),
    ("guardwrite", json.dumps({"tool_input": {}}), "no file_path field"),
):
    code, out, err = run_hook(event, payload, env=_dflt)
    if code == 0 and needle in out and '"systemMessage"' in out:
        report("PASS", f"{event} still prints its 'could not tell' trace by default ({needle})")
    else:
        report("FAIL", f"{event} still prints its 'could not tell' trace by default ({needle})")
        print(f"          exit {code}, got: {out[:160]!r}")


_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-own", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
_ctx = _stop_context(out)
commit_case(
    "Stop: a file this turn wrote, still uncommitted on a claude/ branch, gets 'commit it now, scoped'",
    "commit on your own branch" in _ctx and "a.py" in _ctx and "`claude/topic`" in _ctx and "git commit -- <paths>" in _ctx,
    "context: %r" % _ctx[:160],
)

_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-main", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
_ctx = _stop_context(out)
commit_case(
    "Stop: the same on the user's main says to branch off to the agent's <prefix>/<topic> first",
    "not one of your own branches" in _ctx and "branch off first" in _ctx and ("git switch -c " + TEST_AGENT_PREFIX + "<topic>") in _ctx,
    "context: %r" % _ctx[:160],
)

_r = _commit_repo("main", committed=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-committed", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed and committed a.py."),
    env=_project_env(_r),
)
commit_case(
    "Stop: a file this turn wrote that is already committed stays silent",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_r = _commit_repo("main", committed=["a.py", "theirs.py"], dirty=["theirs.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-not-theirs", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
commit_case(
    "Stop: the user's own uncommitted edit, which this turn never wrote, never trips the check",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-toggle", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r, HOUSE_RULES_COMMIT_CHECK="off"),
)
commit_case(
    "Stop: HOUSE_RULES_COMMIT_CHECK=off switches the commit check off",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_nogit = tempfile.mkdtemp(prefix="house-rules-nogit-", dir=_FIXTURE_ROOT)
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-nogit", [os.path.join(_nogit, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_nogit),
)
commit_case(
    "Stop: outside a git repo the commit check says it could not tell, and never blocks",
    "commit check could not tell" in out and '"decision"' not in out and '"additionalContext"' not in out,
    "stdout: %r" % out[:160],
)


_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py")
commit_case(
    "branchnudge: the first uncommitted change on a non-claude/ branch says to branch off now",
    "branch off now" in out and "`main`" in out and '"PostToolUse"' in out and '"permissionDecision"' not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("main", committed=["a.py", "b.py"], dirty=["a.py", "b.py"])
out = _nudge(_r, "b.py")
commit_case(
    "branchnudge: a second uncommitted change is not the first, so it stays quiet",
    "branch off now" not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py")
commit_case(
    "branchnudge: on a claude/ branch there is nothing to nudge",
    "branch off now" not in out,
    "stdout: %r" % out[:160],
)
for _br, _owned in (("AjsAgent/x", True), ("claude/x", True), ("main", False), ("feature/x", False)):
    _r = _commit_repo(_br, committed=["a.py"], dirty=["a.py"])
    out = _nudge(_r, "a.py")
    commit_case(
        "branchnudge: `%s` is %s" % (_br, "owned (AjsAgent/ and claude/ both count), no nudge" if _owned
                                     else "not owned, so it nudges"),
        ("branch off now" not in out) == _owned,
        "stdout: %r" % out[:160],
    )
_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py", HOUSE_RULES_COMMIT_CHECK="off")
commit_case(
    "branchnudge: HOUSE_RULES_COMMIT_CHECK=off switches it off",
    out.strip() == "",
    "stdout: %r" % out[:160],
)
commit_case(
    "branchnudge is wired to PostToolUse Write|Edit in hooks.json",
    bool(re.search(r'"matcher": "Write\|Edit",\s*"hooks": \[\s*\{\s*"type": "command",\s*"command": "sh \\"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/run\.sh\\" branchnudge"', hooks_json_text)),
    "hooks.json PostToolUse entry",
)


_cc_cmd = 'gh pr create --title T --body "Refs #1"'
_cc_url = "https://github.com/o/r/pull/7"
out = _creditcheck(_cc_cmd, _cc_url + "\n", lambda p: ("Done.\n\nGenerated with [Claude Code](https://claude.ai/code)", None))
commit_case("creditcheck: a body with a Claude credit gets the warning",
            "added a Claude credit to " + _cc_url in out and "say so in your reply" in out, "stdout: %r" % out[:200])
out = _creditcheck(_cc_cmd, _cc_url + "\n", lambda p: ("Done.\n\n" + TEST_PR_CREDIT + "", None))
commit_case("creditcheck: a clean body gets the clean line",
            "read back " + _cc_url + "; no Claude credit on it." in out, "stdout: %r" % out[:200])
out = _creditcheck(_cc_cmd, _cc_url + "\n", lambda p: (None, "gh timed out after 10 seconds"))
commit_case("creditcheck: a failed fetch says it could not read back",
            "could not read back " + _cc_url in out and "unknown" in out, "stdout: %r" % out[:200])
out = _creditcheck(_cc_cmd, "nothing useful\n", lambda p: ("", None))
commit_case("creditcheck: no address in the output says it could not read back",
            "could not read back" in out and "unknown" in out, "stdout: %r" % out[:200])
out = _creditcheck("ls", "a b\n", lambda p: ("", None))
commit_case("creditcheck: a non-matching command prints nothing", out.strip() == "", "stdout: %r" % out[:200])
out = _creditcheck(_cc_cmd, _cc_url + "\n", lambda p: ("", None), off=True)
commit_case("creditcheck: HOUSE_RULES_ATTRIBUTION=off prints nothing", out.strip() == "", "stdout: %r" % out[:200])
commit_case(
    "creditcheck is wired to PostToolUse Bash with a 15 second timeout in hooks.json",
    bool(re.search(r'"matcher": "Bash",\s*"hooks": \[\s*\{\s*"type": "command",\s*"command": "sh \\"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/run\.sh\\" creditcheck",\s*"timeout": 15', hooks_json_text)),
    "hooks.json PostToolUse entry",
)

# -- #176: cloud sessions move off claude/<name> onto AjsAgent/<name> ---------------------------------
def _ab_repo(branch, extra_branch=None):
    d = tempfile.mkdtemp(prefix="hr-ab-", dir=_FIXTURE_ROOT)
    g = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(g + ["init", "-q", "-b", branch], cwd=d, check=True)
    subprocess.run(g + ["commit", "-q", "--allow-empty", "-m", "x"], cwd=d, check=True)
    if extra_branch:
        subprocess.run(["git", "branch", extra_branch], cwd=d, check=True)
    return d


def _ab_out(d, remote=True, **extra):
    e = env_in(d, HOUSE_RULES_ENV_FILE=EXAMPLE_ENV, **extra)
    e.pop("CLAUDE_CODE_REMOTE", None)
    if remote:
        e["CLAUDE_CODE_REMOTE"] = "true"
    e.pop("HOUSE_RULES_AGENT_BRANCH", None)
    e.update(extra)
    return run_hook("profile", "", env=e)[1]


_ab1 = _ab_out(_ab_repo("claude/foo"))
_ab2 = _ab_out(_ab_repo("claude/foo", TEST_AGENT_PREFIX + "foo"))
_ab3, _ab4 = _ab_out(_ab_repo(TEST_AGENT_PREFIX + "foo")), _ab_out(_ab_repo("main"))
_ab5 = _ab_out(_ab_repo("claude/foo"), remote=False)
_ab6 = _ab_out(_ab_repo("claude/foo"), HOUSE_RULES_AGENT_BRANCH="off")
_ab7 = _ab_out(tempfile.mkdtemp(prefix="hr-ab-nogit-", dir=_FIXTURE_ROOT))
commit_case(
    "agent-branch: claude/foo is told to git switch -c <agent prefix>foo, with aj's standing permission",
    ("git switch -c " + TEST_AGENT_PREFIX + "foo") in _ab1 and ("git push -u origin " + TEST_AGENT_PREFIX + "foo") in _ab1 and "standing permission" in _ab1,
    "out %r" % _ab1[-420:],
)
commit_case(
    "agent-branch: an existing <agent prefix>foo gets git switch <agent prefix>foo, no -c",
    ("git switch " + TEST_AGENT_PREFIX + "foo") in _ab2 and "switch -c" not in _ab2,
    "out %r" % _ab2[-200:],
)
commit_case(
    "agent-branch: <agent prefix>foo, main, a local session, and the kill switch add no switch text",
    all("git switch" not in o for o in (_ab3, _ab4, _ab5, _ab6)),
    "hit idx %s" % [i for i, o in enumerate((_ab3, _ab4, _ab5, _ab6)) if "git switch" in o],
)
commit_case(
    "agent-branch: outside a git repo it does not crash and says the branch was not read",
    "Agent branch check: branch not read" in _ab7 and "git switch" not in _ab7,
    "out %r" % _ab7[-200:],
)

# -- #133: credit aj's agent, never Claude -------------------------------------------------------------
_att_trailer = "git commit -m \"$(cat <<'EOF'\nfix: thing\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nEOF\n)\""
_att_gen = "git commit -m \"feat: x\n\nGenerated with [Claude Code](https://claude.com/claude-code)\""
_att_ok = "git commit -m \"$(cat <<'EOF'\nfix: thing\n\n" + TEST_COMMIT_CREDIT + "\nEOF\n)\""
_att_word = "git commit -m \"docs: rename the Claude setting\""
_oa1, _oa2, _oa3, _oa4 = _iss_guard(_att_trailer), _iss_guard(_att_gen), _iss_guard(_att_ok), _iss_guard(_att_word)
commit_case(
    "attribution: a commit crediting Claude (co-author trailer or Generated-with line) is refused, naming the replacement",
    _iss_decision(_oa1) == "deny" and _iss_decision(_oa2) == "deny"
    and "" + TEST_COMMIT_CREDIT + "" in _iss_reason(_oa1) and "no email" in _iss_reason(_oa1),
    "out %r | %r" % (_oa1[:140], _oa2[:100]),
)
_ota3 = _iss_decision(_oa3) != "deny" or "credit " + TEST_AGENT_NAME + "" not in _iss_reason(_oa3)
commit_case(
    "attribution: crediting " + TEST_AGENT_NAME + " with no email passes, and a subject that merely mentions Claude passes",
    "credit " + TEST_AGENT_NAME + "" not in _oa3 and "credit " + TEST_AGENT_NAME + "" not in _oa4,
    "out %r | %r" % (_oa3[:100], _oa4[:100]),
)
_opr1 = _iss_guard('gh pr create --title T --body "Refs #5\n\nGenerated with [Claude Code](https://claude.com/claude-code)"')
_opr2 = _iss_guard('gh pr create --title T --body "Refs #5\n\nOpened by AJ\'s agent"')
_opr3 = _iss_guard('gh pr create --title T --body "Refs #5\n\nhttps://claude.ai/code/session_abc"')
commit_case(
    "attribution: a pull request body crediting Claude or linking a Claude session is refused; crediting " + TEST_AGENT_NAME + " passes",
    _iss_decision(_opr1) == "deny" and "credit " + TEST_AGENT_NAME + "" in _iss_reason(_opr1)
    and _iss_decision(_opr3) == "deny" and "credit " + TEST_AGENT_NAME + "" not in _opr2 and _opr2.strip() == "",
    "out %r | %r | %r" % (_opr1[:90], _opr2[:60], _opr3[:90]),
)
# #189: every form from the issue's table, the quoted -c ones included, is refused.
_att_body = ' -m "fix\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"'
_att_heredoc = " -F - <<'EOF'\nfix\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nEOF"
_att_forms = [
    "git commit" + _att_body,
    "git -c user.name=x commit" + _att_body,
    "git -c user.name=aj -c user.email=a@b commit" + _att_heredoc,
    "git -c user.name=\"" + TEST_AGENT_NAME + "\" commit" + _att_body,
    "git -c user.name=\"" + TEST_AGENT_NAME + "\" -c user.email=a@b commit -q" + _att_heredoc,
    "git -c 'user.name=aj s agent' commit" + _att_body,
]
_att_missed = [f for f in _att_forms if _iss_decision(_iss_guard(f)) != "deny"]
commit_case(
    "attribution: a Claude trailer is refused however -c sets the author, quoted values with spaces included",
    not _att_missed,
    "allowed %r" % _att_missed,
)
_oc1 = _iss_guard('gh issue comment 5 --body "Co-Authored-By: Claude <x>"')
_off = _iss_guard(_att_trailer, HOUSE_RULES_ATTRIBUTION="off")
commit_case(
    "attribution: an issue comment crediting Claude is refused, and HOUSE_RULES_ATTRIBUTION=off disables the check",
    _iss_decision(_oc1) == "deny" and "credit " + TEST_AGENT_NAME + "" not in _off,
    "out %r | off %r" % (_oc1[:90], _off[:80]),
)
# -- #316: the credit check also covers gh api and curl writes to GitHub ---------------------------------
_a316_bad = "Co-Authored-By: Claude <noreply@anthropic.com>"
_a316_dir = tempfile.mkdtemp()
_a316_bf = os.path.join(_a316_dir, "bad.txt").replace("\\", "/")
_a316_cf = os.path.join(_a316_dir, "clean.txt").replace("\\", "/")
_a316_bj = os.path.join(_a316_dir, "bad.json").replace("\\", "/")
_a316_cj = os.path.join(_a316_dir, "clean.json").replace("\\", "/")
for _p, _t in ((_a316_bf, _a316_bad), (_a316_cf, "" + TEST_PR_CREDIT + ""),
               (_a316_bj, json.dumps({"body": _a316_bad})), (_a316_cj, json.dumps({"body": "" + TEST_PR_CREDIT + ""}))):
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_t)
_a316_routes = lambda b, fb, fj: [
    "gh api repos/o/r/pulls -f title=t -f body=\"%s\"" % b,
    "gh api repos/o/r/issues -f title=t -f body=\"%s\"" % b,
    "gh api -X PATCH repos/o/r/issues/5 -f body=\"%s\"" % b,
    "gh api repos/o/r/issues/5/comments -F body=@%s" % fb,
    "gh api repos/o/r/pulls --input %s" % fj,
    "curl -X POST https://api.github.com/repos/o/r/pulls -d '{\"body\":\"%s\"}'" % b,
]
_a316_missed = [c for c in _a316_routes(_a316_bad, _a316_bf, _a316_bj) if _iss_decision(_iss_guard(c)) != "deny"]
_a316_false = [c for c in _a316_routes("" + TEST_PR_CREDIT + "", _a316_cf, _a316_cj) if _iss_decision(_iss_guard(c)) == "deny"]
_a316_get = _iss_guard("gh api repos/o/r/pulls/5")
commit_case(
    "attribution: gh api and curl writes crediting Claude are refused on every route; clean bodies and a plain GET pass",
    not _a316_missed and not _a316_false and _iss_decision(_a316_get) != "deny",
    "allowed %r | wrongly refused %r | get %r" % (_a316_missed, _a316_false, _a316_get[:80]),
)
# -- #317: the footer GitHub appends is recognised ------------------------------------------------------
_a317_foot = "Summary\n\n_Generated by [Claude Code](https://claude" + ".ai/code)_\n"
_a317_tf = os.path.join(_a316_dir, "foot.txt").replace("\\", "/")
_a317_jf = os.path.join(_a316_dir, "foot.json").replace("\\", "/")
_a317_pf = os.path.join(_a316_dir, "prose.txt").replace("\\", "/")
for _p, _t in ((_a317_tf, _a317_foot), (_a317_jf, json.dumps({"body": _a317_foot})),
               (_a317_pf, "Refs #5\n\nThis was reviewed with Claude in mind")):
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_t)
_a317_pr = _iss_guard("gh pr create --title t --body-file %s" % _a317_tf)
_a317_api = _iss_guard("gh api repos/o/r/pulls --input %s" % _a317_jf)
_a317_prose = _iss_guard("gh pr create --title t --body-file %s" % _a317_pf)
commit_case(
    "attribution: the platform-appended footer is refused via gh pr create and gh api --input; prose mentioning Claude passes",
    _iss_decision(_a317_pr) == "deny" and _iss_decision(_a317_api) == "deny" and _iss_decision(_a317_prose) != "deny",
    "pr %r | api %r | prose %r" % (_a317_pr[:80], _a317_api[:80], _a317_prose[:200]),
)

# -- #178: the same credit check on GitHub MCP writes ---------------------------------------------------
def _gg(tool, env_extra=None, **tool_input):
    e = dict(os.environ)
    e.pop("HOUSE_RULES_ATTRIBUTION", None)
    e.update(env_extra or {})
    pl = json.dumps({"session_id": "verify", "tool_name": tool, "tool_input": tool_input})
    return run_hook("guardgithub", pl, env=e)[1]


def _ggd(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except (ValueError, KeyError, TypeError):
        return "allow"


_gh = "mcp__github__"
_g1 = _gg(_gh + "create_pull_request", title="T", head="AjsAgent/x", body="Refs #5\n\nGenerated with [Claude Code](https://claude.com/claude-code)")
_g2 = _gg(_gh + "create_pull_request", title="T", head="AjsAgent/x", body="Refs #5\n\n" + TEST_PR_CREDIT + "")
commit_case(
    "guardgithub: a pull request body crediting Claude is denied; crediting " + TEST_AGENT_NAME + " is allowed",
    _ggd(_g1) == "deny" and "pull request or issue text" in _g1 and _ggd(_g2) == "allow",
    "out %r | %r" % (_g1[:120], _g2[:80]),
)
_g3 = _gg(_gh + "issue_write", method="create", title="T", body="x\n\nCo-Authored-By: Claude <a@b>")
_g4 = _gg(_gh + "push_files", branch="AjsAgent/x", message="fix\n\nClaude-Session: https://x", files=[{"path": "a", "content": "x"}])
_g5 = _gg(_gh + "push_files", branch="AjsAgent/x", message="fix\n\n" + TEST_COMMIT_CREDIT + "",
          files=[{"path": "a", "content": "Co-Authored-By: Claude <noreply@anthropic.com>"}])
commit_case(
    "guardgithub: an issue trailer and a push_files commit message are denied; file content naming the patterns is not scanned",
    _ggd(_g3) == "deny" and _ggd(_g4) == "deny" and "commit message" in _g4 and _ggd(_g5) == "allow",
    "out %r | %r | %r" % (_g3[:80], _g4[:80], _g5[:80]),
)
_g6 = _gg(_gh + "create_branch", branch="claude/x")
_g7 = _gg(_gh + "create_branch", branch="AjsAgent/x")
_g8 = _gg(_gh + "create_pull_request", title="T", head="claude/x", body="" + TEST_PR_CREDIT + "")
_g9 = _gg(_gh + "push_files", branch="claude/x", message="fix\n\n" + TEST_COMMIT_CREDIT + "", files=[])
commit_case(
    "guardgithub: a new claude/ branch (create_branch, PR head) is denied naming AjsAgent/; AjsAgent/ and a push to an existing claude/ branch are allowed",
    _ggd(_g6) == "deny" and "" + TEST_AGENT_PREFIX + "<topic>" in _g6 and _ggd(_g7) == "allow"
    and _ggd(_g8) == "deny" and _ggd(_g9) == "allow",
    "out %r | %r | %r | %r" % (_g6[:60], _g7[:40], _g8[:60], _g9[:40]),
)
_g10 = _gg("mcp__GitHub__create_pull_request", title="T", head="AjsAgent/x", body="Generated with [Claude Code]")
_g11 = _gg("mcp__GitHub__create_branch", branch="claude/x")
_g12 = _gg(_gh + "create_branch", {"HOUSE_RULES_ATTRIBUTION": "off"}, branch="claude/x")
commit_case(
    "guardgithub: the mcp__GitHub__ prefix is checked the same way, and HOUSE_RULES_ATTRIBUTION=off allows",
    _ggd(_g10) == "deny" and _ggd(_g11) == "deny" and _ggd(_g12) == "allow",
    "out %r | %r | off %r" % (_g10[:60], _g11[:60], _g12[:60]),
)
_g13 = _gg(_gh + "push_files", branch="main", message="fix\n\n" + TEST_COMMIT_CREDIT + "", files=[])
_g14 = _gg(_gh + "create_or_update_file", branch="master", message="fix", path="a", content="x")
_g15 = _gg(_gh + "create_or_update_file", branch="AjsAgent/x", message="fix", path="a", content="x")
commit_case(
    "guardgithub: a file write straight to main or master is refused; one to another branch is allowed",
    _ggd(_g13) == "deny" and "is the default branch" in _g13 and _ggd(_g14) == "deny" and _ggd(_g15) == "allow",
    "out %r | %r | %r" % (_g13[:80], _g14[:60], _g15[:40]),
)
_hj = json.load(open(os.path.join(HERE, "..", "hooks", "hooks.json"), encoding="utf-8"))
_gm = [b["matcher"] for b in _hj["hooks"]["PreToolUse"]
       if any(h["command"].endswith(" guardgithub") for h in b["hooks"])]
_names = ["create_pull_request", "update_pull_request", "issue_write", "add_issue_comment",
          "update_issue_comment", "add_reply_to_pull_request_comment", "add_comment_to_pending_review",
          "pull_request_review_write", "push_files", "create_or_update_file", "create_branch"]
commit_case(
    "guardgithub: the hooks.json matcher fully matches every GitHub write tool under both prefixes, and not a read tool",
    len(_gm) == 1 and all(re.fullmatch(_gm[0], p + n) for p in ("mcp__github__", "mcp__GitHub__") for n in _names)
    and not re.fullmatch(_gm[0], "mcp__github__issue_read") and not re.fullmatch(_gm[0], "mcp__GitHub__get_file_contents"),
    "matchers %r" % (_gm,),
)
_opw = _iss_call("guard", _iss_payload("PreToolUse", "PowerShell", _dp, command=_att_trailer), _dp)[1]
commit_case(
    "attribution: the same refusal applies through the PowerShell tool",
    _iss_decision(_opw) == "deny" and "credit " + TEST_AGENT_NAME + "" in _iss_reason(_opw),
    "out %r" % _opw[:140],
)


def _au_profile(d, remote=True, **extra):
    return _ab_out(d, remote=remote, **extra)


_ap1 = _au_profile(_au_bad)
_ap2, _ap3 = _au_profile(_au_good), _au_profile(_au_bad, remote=False)
_ap4 = _au_profile(_au_bad, HOUSE_RULES_ATTRIBUTION="off")
commit_case(
    "author: a remote profile with a Claude identity says to run the repo-local git config; good identity, local session and kill switch add nothing",
    "Git identity is Claude" in _ap1 and "git config user.email" in _ap1 and all("Git identity is Claude" not in o for o in (_ap2, _ap3, _ap4)),
    "out %r" % _ap1[-260:],
)
for _restatement in [RESTATEMENTS[_i] for _i in (1, 2)]:  # safe git
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

# --- the "What trips the guard" README table matches GUARD_R3/GUARD_R4's actual git verbs -----
# Why this tokenizes the table instead of hand-copying the verb list, and the incident that
# made it necessary: docs/4-systems/verify-suites.md, Invariants ("The guarded-verb list is
# never hand-copied into a doc").
GUARDED_GIT_VERBS = [
    "push", "commit", "reset", "revert", "clean", "rebase", "merge",
    "filter-branch", "cherry-pick", "am", "apply", "checkout", "restore", "stash",
]
NAVIGATIONAL_GIT_VERBS = ["add", "switch", "branch", "tag", "remote", "submodule"]

guarddrift = []
_guard_table_absent = absent_repo_files(readme_rel)
if _guard_table_absent:
    skip_repo_check(
        "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs",
        _guard_table_absent,
    )
else:
    readme_text_guard = read(readme_path)
    table_match = re.search(r"### What trips the guard\n\n(?:\|.*\n)+", readme_text_guard)
    if not table_match:
        guarddrift.append("no 'What trips the guard' table found under that heading")
    else:
        table_tokens = set()
        for span in re.findall(r"`([^`]+)`", table_match.group(0)):
            table_tokens.update(re.split(r"[\s/,]+", span.strip()))
        for verb in GUARDED_GIT_VERBS:
            if verb not in table_tokens:
                guarddrift.append(f"the table does not mention `{verb}`, which hook.py actually matches")
        for verb in NAVIGATIONAL_GIT_VERBS:
            if verb in table_tokens:
                guarddrift.append(f"the table claims `{verb}` trips the guard, but hook.py deliberately does not match it")
    if not guarddrift:
        report("PASS", "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs")
        print(f"          all {len(GUARDED_GIT_VERBS)} guarded verbs present, "
              f"all {len(NAVIGATIONAL_GIT_VERBS)} deliberately-dropped verbs absent")
    else:
        report("FAIL", "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs")
        print(f"          {'; '.join(guarddrift)}")


def _pt_decision(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["decision"]
    except Exception:
        return {}


_p1 = _pt_run()
_d1 = _pt_decision(_p1[1])
try:
    _pt_entries = json.load(open(_pt_state, encoding="utf-8"))
except Exception:
    _pt_entries = []
commit_case(
    "prompttimer: an unanswered prompt is denied after the timeout, message == reason, state holds one timed-out entry",
    _p1[0] == 0 and _d1.get("behavior") == "deny" and _d1.get("message") == _d1.get("reason")
    and "refused" in _d1.get("message", "") and "rm -rf /tmp/pt-victim" in _d1.get("message", "")
    and len(_pt_entries) == 1 and _pt_entries[0]["status"] == "timed-out"
    and _pt_entries[0]["session_id"] == "pt-sess" and len(_pt_entries[0]["key"]) == 16
    and _pt_entries[0]["summary"] == "rm -rf /tmp/pt-victim",
    "out %r entries %r" % (_p1[1][:120], _pt_entries),
)
commit_case(
    "prompttimer: the 1-second timeout waits about 1 second (not 0, not 10)",
    0.9 <= _p1[3] <= 5, "elapsed %.2fs" % _p1[3],
)
_p2 = _pt_run()
commit_case(
    "prompttimer (#290): the same action again in the same session waits its own full timer, not denied at once",
    _p2[3] >= 0.9 and "already timed out" not in _pt_decision(_p2[1]).get("message", ""),
    "elapsed %.2fs out %r" % (_p2[3], _p2[1][:100]),
)
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_p3 = _pt_run(HOUSE_RULES_PROMPT_TIMEOUT="OFF")
commit_case(
    "prompttimer: HOUSE_RULES_PROMPT_TIMEOUT=off makes no decision and writes no state",
    _p3[0] == 0 and _p3[1] == "" and not os.path.exists(_pt_state) and _p3[3] < 0.9,
    "out %r state exists %s" % (_p3[1], os.path.exists(_pt_state)),
)
os.makedirs(os.path.dirname(_pt_state), exist_ok=True)
with open(_pt_state, "w", encoding="utf-8") as _f:
    _f.write("{not json")
_p4 = _pt_run()
commit_case(
    "prompttimer: a corrupt state file is reported loudly and the prompt is still denied after the timeout",
    _p4[0] == 0 and _pt_decision(_p4[1]).get("behavior") == "deny" and _p4[3] >= 0.9
    and "could not read" in _p4[2] and _pt_state in _p4[2] and "Traceback" not in _p4[2],
    "elapsed %.2fs stderr %r" % (_p4[3], _p4[2][:200]),
)
_p5 = _pt_run("{not json")
_p5b = _pt_run(json.dumps({"session_id": "x"}))
commit_case(
    "prompttimer: a malformed payload makes no decision, says so on stderr and exits 0",
    _p5[0] == 0 and _p5[1] == "" and "could not read" in _p5[2] and _p5[3] < 0.9
    and _p5b[0] == 0 and _p5b[1] == "" and "could not read" in _p5b[2],
    "stderr %r / %r" % (_p5[2][:100], _p5b[2][:100]),
)
_pt_src = read(SAFE_GIT)  # prompttimer moved to the safe git part (#358); its block now ends at a marker line
_pt_block = _pt_src[_pt_src.index("# prompttimer - PermissionRequest"):_pt_src.index("# End of the prompttimer block")]
commit_case(
    "prompttimer: the handler source has no route to an allow decision",
    "allow" not in _pt_block.lower() and 'behavior": "deny"' in _pt_block,
    "%d characters of handler source scanned" % len(_pt_block),
)
_pt_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"].get("PermissionRequest", [])
commit_case(
    "prompttimer: hooks.json wires PermissionRequest to prompttimer with a 330 second timeout",
    len(_pt_hj) == 1 and "matcher" not in _pt_hj[0] and len(_pt_hj[0]["hooks"]) == 1
    and _pt_hj[0]["hooks"][0]["command"].endswith('run.sh" prompttimer') and _pt_hj[0]["hooks"][0]["timeout"] == 330,
    "entry %r" % (_pt_hj,),
)

shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_pt_pl = lambda cmd, sid="pt-sess": json.dumps({"hook_event_name": "PermissionRequest", "session_id": sid,
                                                "tool_name": "Bash", "tool_input": {"command": cmd}})
_pt_res = {}


def _pt_thread(name, cmd):
    _pt_res[name] = _pt_run(_pt_pl(cmd))


_ths = [threading.Thread(target=_pt_thread, args=("a", "echo concurrent-a")),
        threading.Thread(target=_pt_thread, args=("b", "echo concurrent-b"))]
for _t in _ths:
    _t.start()
for _t in _ths:
    _t.join()
try:
    _pt_c = json.load(open(_pt_state, encoding="utf-8"))
except Exception:
    _pt_c = []
commit_case(
    "prompttimer: two concurrent runs on different actions leave 2 entries (the lock keeps both)",
    len(_pt_c) == 2 and {e["summary"] for e in _pt_c} == {"echo concurrent-a", "echo concurrent-b"}
    and not os.path.exists(_pt_state + ".lock"),
    "entries %r" % (_pt_c,),
)

# a stale lock is removed and reported
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
os.makedirs(os.path.dirname(_pt_state), exist_ok=True)
with open(_pt_state + ".lock", "w") as _f:
    _f.write("")
os.utime(_pt_state + ".lock", (time.time() - 60, time.time() - 60))
_s1 = _pt_run(_pt_pl("echo stale-lock"))
commit_case(
    "prompttimer: a lock older than 15 s is removed, reported on stderr, and the entry is still written",
    "stale lock" in _s1[2] and not os.path.exists(_pt_state + ".lock")
    and _pt_decision(_s1[1]).get("behavior") == "deny"
    and any(e["summary"] == "echo stale-lock" for e in json.load(open(_pt_state, encoding="utf-8"))),
    "stderr %r" % (_s1[2][:200],),
)

# scope: a real prompt lists the entry, marks it reported; a retry then waits
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_pt_run()  # times out: one timed-out entry for rm -rf /tmp/pt-victim in pt-sess
_pt_scope_env = _pt_env()


def _pt_scope(prompt, sid="pt-sess"):
    return run_hook("scope", json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": sid,
                                         "prompt": prompt}), env=_pt_scope_env)


_n1 = _pt_scope("<task-notification><task-id>abc</task-id><status>completed</status></task-notification>")
_state_n1 = json.load(open(_pt_state, encoding="utf-8"))
commit_case(
    "scope: a background task-notification prompt changes nothing and lists nothing",
    _n1[0] == 0 and "waiting on you" not in _n1[1] and _state_n1[0]["status"] == "timed-out",
    "out %r state %r" % (_n1[1][:150], _state_n1),
)
_r1 = _pt_scope("hello, back now")
_state_r1 = json.load(open(_pt_state, encoding="utf-8"))
try:
    _r1ctx = json.loads(_r1[1])["hookSpecificOutput"]["additionalContext"]
except Exception:
    _r1ctx = ""
commit_case(
    "scope: a real prompt lists the session's timed-out action, marks it reported, one JSON object on stdout",
    _r1[0] == 0 and "1 action waiting on you since" in _r1ctx and "(local time)" in _r1ctx
    and "- Bash: rm -rf /tmp/pt-victim" in _r1ctx and "aj is here now" in _r1ctx
    and len(_state_r1) == 1 and _state_r1[0]["status"] == "reported",
    "out %r state %r" % (_r1[1][:200], _state_r1),
)
_r2 = _pt_run()
commit_case(
    "prompttimer: after scope reported it, the same action waits instead of being re-denied at once",
    _r2[3] >= 0.9 and "already timed out" not in _pt_decision(_r2[1]).get("message", ""),
    "elapsed %.2fs out %r" % (_r2[3], _r2[1][:100]),
)
_r3 = _pt_scope("again", sid="quiet-sess")
commit_case(
    "scope: a session with nothing waiting gets nothing extra",
    "action waiting on you" not in _r3[1] and "actions waiting on you" not in _r3[1],
    "out %r" % (_r3[1][:150],),
)

# issuelist: other sessions' entries are shown and dropped; >7-day entries pruned; empty says nothing
_now = time.time()
with open(_pt_state, "w", encoding="utf-8") as _f:
    json.dump([
        {"session_id": "old-sess", "key": "k1", "tool": "Bash", "summary": "git push origin main",
         "started": _now - 3600, "status": "timed-out"},
        {"session_id": "old-sess2", "key": "k2", "tool": "Write", "summary": "ancient.txt",
         "started": _now - 8 * 86400, "status": "timed-out"},
        {"session_id": "new-sess", "key": "k3", "tool": "Bash", "summary": "mine stays",
         "started": _now - 5, "status": "waiting"},
    ] + [{"session_id": "filler%d" % _k, "key": "f%d" % _k, "tool": "Bash", "summary": "filler %d" % _k,
          "started": _now - 100 - _k, "status": "timed-out"} for _k in range(9)], _f)
_il_env = _pt_env(HOUSE_RULES_ISSUES="off")
_i1 = run_hook("issuelist", json.dumps({"hook_event_name": "SessionStart", "session_id": "new-sess",
                                        "cwd": _pt_repo}), env=_il_env)
try:
    _io = json.loads(_i1[1])
except Exception:
    _io = {}
_left = json.load(open(_pt_state, encoding="utf-8"))
commit_case(
    "issuelist: another session's entry is shown to Claude and aj in one JSON object, then dropped; >7-day entries pruned",
    _i1[0] == 0 and "Left waiting on you by an earlier session" in _io.get("hookSpecificOutput", {}).get("additionalContext", "")
    and "git push origin main" in _io["hookSpecificOutput"]["additionalContext"]
    and "ancient.txt" not in _io["hookSpecificOutput"]["additionalContext"]
    and _io["hookSpecificOutput"]["additionalContext"].count("\n- ") == 10
    and "git push origin main" in _io.get("systemMessage", "")
    and [e["summary"] for e in _left] == ["mine stays"],
    "out %r left %r" % (_i1[1][:200], _left),
)
_i2 = run_hook("issuelist", json.dumps({"hook_event_name": "SessionStart", "session_id": "new-sess",
                                        "cwd": _pt_repo}), env=_il_env)
commit_case(
    "issuelist: with nothing left by other sessions it says nothing",
    _i2[0] == 0 and _i2[1] == "", "out %r" % (_i2[1][:100],),
)

# guard: the timeout line, omitted when off
_g_payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "g", "tool_name": "Bash",
                         "tool_input": {"command": "rm -rf /tmp/pt-victim", "description": "no safe way: rm(1)"},
                         "cwd": _pt_repo})
_gw_payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "g", "tool_name": "Write",
                          "tool_input": {"file_path": os.path.join(_pt_repo, "existing.txt"), "content": "x\n"},
                          "cwd": _pt_repo})
with open(os.path.join(_pt_repo, "existing.txt"), "w") as _f:
    _f.write("a\nb\n")
subprocess.run(["git", "-C", _pt_repo, "add", "existing.txt"], check=True)
_gline = "refused (never approved) and added to the waiting-on-you list."
_ge = _pt_env(HOUSE_RULES_PROMPT_TIMEOUT="300")
_geoff = _pt_env(HOUSE_RULES_PROMPT_TIMEOUT="off")
_g1, _g2 = run_hook("guard", _g_payload, env=_ge), run_hook("guardwrite", _gw_payload, env=_ge)
_g3, _g4 = run_hook("guard", _g_payload, env=_geoff), run_hook("guardwrite", _gw_payload, env=_geoff)
commit_case(
    # #293: guardwrite no longer asks (a whole-file Write is refused), so only guard's cited prompt carries the line.
    "guard: the prompt says 'If nobody answers within 5 minutes...' before the Approve line; off omits it",
    "If nobody answers within 5 minutes, this is " + _gline in _g1[1]
    and _g1[1].index("If nobody answers") < _g1[1].index("Approve to let it run")
    and _gline not in _g3[1] and "Approve to let it run" in _g3[1]
    and '"permissionDecision":"deny"' in _g2[1] and _gline not in _g2[1],
    "guard %r | guardwrite %r | off %r" % (_g1[1][-250:], _g2[1][-250:], _g3[1][-150:]),
)


shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_q1 = _pt_run(_pt_tool("AskUserQuestion", {"questions": [{"question": "Which one?"}]}))
_q2 = _pt_run(_pt_tool("ExitPlanMode", {"plan": "1. do it"}))
commit_case(
    "prompttimer: AskUserQuestion and ExitPlanMode get no timer - no decision, no state, said on stderr",
    all(x[0] == 0 and x[1] == "" and x[3] < 0.9 and "question for aj" in x[2] for x in (_q1, _q2))
    and not os.path.exists(_pt_state),
    "q1 %r q2 %r state %s" % (_q1[2][:120], _q2[2][:120], os.path.exists(_pt_state)),
)

_a1 = _pt_run()  # the first prompt times out
_a2 = _pt_run(_pt_pl("git push -q origin claude/x"))
_a2d = _pt_decision(_a2[1])
commit_case(
    "prompttimer (#290): after one timeout, a DIFFERENT guard prompt in the same session waits its own full timer",
    _a1[3] >= 0.9 and _a2[3] >= 0.9 and _a2d.get("behavior") == "deny"
    and "already went unanswered" not in _a2d.get("message", ""),
    "elapsed %.2fs out %r" % (_a2[3], _a2[1][:120]),
)
_a3 = _pt_run(_pt_pl("git push -q origin claude/x", sid="other-sess"))
commit_case(
    "prompttimer: another session's timeout does not refuse this session's prompt at once",
    _a3[3] >= 0.9 and "already went unanswered" not in _pt_decision(_a3[1]).get("message", ""),
    "elapsed %.2fs" % _a3[3],
)
# (a) a second guard prompt after a timeout is ASKED by the guard normally, not refused
_a5 = _ua_guard("verify-290-a", tool_input={"command": "rm -rf build", "description": "no safe way: rm(1)"})
_a5b = _ua_guard("verify-290-a", tool_input={"command": "rm -rf other-build", "description": "no safe way: rm(1)"})
commit_case(
    "guard (#290): after a prompt timed out, a second guard prompt is asked normally",
    _ua_dec(_a5) == "ask" and _ua_dec(_a5b) == "ask", "first %s second %s" % (_ua_dec(_a5), _ua_dec(_a5b)),
)
# (b) a dialog no guard raised gets no timer and no refusal
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_b1 = _pt_run(_pt_tool("Artifact", {"action": "publish"}), guarded=False)
_b2 = _pt_run(_pt_tool("mcp__github__create_issue", {"title": "x"}), guarded=False)
commit_case(
    "prompttimer (#290): a dialog no guard raised (Artifact, mcp__ tool) gets no timer, no refusal, no state, said on stderr",
    all(x[0] == 0 and x[1] == "" and x[3] < 0.9 and "no house-rules guard raised" in x[2] for x in (_b1, _b2))
    and not os.path.exists(_pt_state),
    "b1 %r b2 %r" % (_b1[2][:100], _b2[2][:100]),
)

session_c = "vc-guard-consumes"
run_hook(
    "versioncheck",
    vc_payload(session_c),
    vc_env(HOUSE_RULES_VC_MARKETPLACE="99.0.0", HOUSE_RULES_VC_GITHUB="99.0.0"),
)
marker_c = vc_marker_path(session_c)
guard_payload = json.dumps(
    {"session_id": session_c, "tool_name": "Bash", "tool_input": {"command": "ls"}}
)
rc1, out1, err1 = run_hook("guard", guard_payload)
rc2, out2, err2 = run_hook("guard", guard_payload)
ok = (
    "PLUGIN OUT OF DATE" in out1
    and '"permissionDecision":"ask"' in out1
    and "PLUGIN OUT OF DATE" not in out2
    and '"permissionDecision":"ask"' not in out2
    and not os.path.isfile(marker_c)
)
if ok:
    report("PASS", "guard surfaces versioncheck's marker once, on the first shell call, then stops")
    print("          first `ls` call prompts for the stale plugin alone; the second call is silent")
else:
    report("FAIL", "guard surfaces versioncheck's marker once, on the first shell call, then stops")
    print(
        f"          out1={out1[:200]!r} out2={out2[:200]!r} "
        f"marker exists after: {os.path.isfile(marker_c)}"
    )
if os.path.isfile(marker_c):
    os.remove(marker_c)

# ---- never-blocked list (#289): own-branch commits, make_page pages, own files go through ----
def _nb_bash(repo, cmd):
    pl = json.dumps({"session_id": "verify", "cwd": repo, "tool_name": "Bash", "tool_input": {"command": cmd}})
    return run_hook("guard", pl, env=_project_env(repo))[1]


def _nb_refused(out):
    return '"permissionDecision":"ask"' in out or '"permissionDecision":"deny"' in out
_nb_h = _commit_repo("worktree-agent-abc123", committed=["a.py"])
_nb_cases = [
    ("git commit on an AjsAgent/ branch goes through with no prompt",
     not _nb_refused(_nb_bash(_nb_r, 'git commit -m "x"'))),
    ("git push on a helper's worktree branch goes through with no prompt",
     not _nb_refused(_nb_bash(_nb_h, "git push origin worktree-agent-abc123"))),
    ("a force-push on an AjsAgent/ branch is NOT let through by the never-blocked list",
     _nb_refused(_nb_bash(_nb_r, "git push --force origin AjsAgent/topic"))),
]
_nb_new = os.path.join(_nb_r, "mine.py")
with open(_nb_new, "w", encoding="utf-8") as f:
    f.write("print(1)\n")
_nb_old = os.path.join(_nb_r, "a.py")
_, _o, _ = run_hook("guardwrite", guardwrite_payload(_nb_new), env=_project_env(_nb_r))
_nb_cases.append(("Write over an untracked file made in the project goes through with no prompt", _o == ""))
_, _o, _ = run_hook("guardwrite", guardwrite_payload(_nb_old), env=_project_env(_nb_r))
_nb_cases.append(("Write over a tracked file is refused, naming the in-place fix (#293)",
                  '"permissionDecision":"deny"' in _o and "edit it in place" in _o))
_, _o, _ = run_hook("guardgithub", json.dumps({"session_id": "v293", "tool_name": "mcp__github__create_branch",
                                                "tool_input": {"branch": "claude/topic"}}), env=_e293)
_nb_cases.append(("enforced: a claude/ branch on GitHub is refused, naming " + TEST_AGENT_PREFIX + "<topic> (#293)",
                  '"permissionDecision":"deny"' in _o and "" + TEST_AGENT_PREFIX + "<topic>" in _o))
_, _o, _ = run_hook("guardgithub", json.dumps({"session_id": "v293", "tool_name": "mcp__github__issue_write",
                                                "tool_input": {"method": "create", "title": "t", "body": "Just a body."}}),
                    env=_e293)
_nb_cases.append(("enforced: an issue missing its sections is refused, naming each missing section (#293)",
                  '"permissionDecision":"deny"' in _o and "Depends on" in _o and "Done when" in _o and "Add them" in _o))
for _t, _ok in _nb_cases:
    report("PASS" if _ok else "FAIL", "never-blocked: " + _t)


# --- #349 (step 4 of #381): deletes follow whose branch it is, the credit line is derived, snapshots go once merged ---
def _349_git(d, *a, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", d] + list(a),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def _349_repo(name, branch):
    d = os.path.join(_FIXTURE_ROOT, name)
    os.makedirs(d)
    _349_git(d, "init", "-q", "-b", "main")
    with open(os.path.join(d, "keep.txt"), "w") as f:
        f.write("committed\n")
    _349_git(d, "add", "keep.txt")
    _349_git(d, "commit", "-q", "-m", "init")
    _349_git(d, "switch", "-q", "-c", branch)
    return d


def _349_rm(d):
    env = env_in(d)
    env["HOUSE_RULES_OWNED_BRANCHES"] = ""
    pl = {"session_id": "v349", "cwd": d, "tool_name": "Bash", "tool_input": {"command": "rm keep.txt"}}
    out = run_hook("guard", json.dumps(pl), env=env)[1]
    m = re.search(r'"permissionDecision":"(\w+)"', out)
    return (m.group(1) if m else "pass"), out


_349_mine, _349_theirs = _349_repo("d349-mine", TEST_AGENT_PREFIX + "del"), _349_repo("d349-theirs", "someoneelse/del")
_349_a, _349_b = _349_rm(_349_mine), _349_rm(_349_theirs)
commit_case(
    "deletes (#349): a committed, unchanged file is deleted without a prompt on the agent's own branch",
    _349_a[0] == "pass", "decision %s | out %r" % (_349_a[0], _349_a[1][:160]),
)
commit_case(
    "deletes (#349): the same delete on someone else's branch is refused, naming the branch and the safe way",
    _349_b[0] == "deny" and "someoneelse/del" in _349_b[1] and "not a branch of the agent's own" in _349_b[1]
    and "_to_delete/" in _349_b[1],
    "decision %s | out %r" % (_349_b[0], _349_b[1][-300:]),
)

# (c) the automatic work-in-progress commit message
from house_rules import delegation as _349_deleg  # noqa: E402
_349_msg = _349_deleg._wip_message("wip: x", "session_abc123")
commit_case(
    "wip commit (#349): the message carries the derived credit line and no Claude line",
    _349_msg.endswith("\n\n" + TEST_COMMIT_CREDIT) and not re.search(r"claude|anthropic|co-authored", _349_msg, re.IGNORECASE),
    "message %r" % _349_msg,
)

# (d) the attribution check accepts the derived credit line and refuses a Claude co-author
_349_ok = _iss_guard("git commit -m \"fix: x\n\n" + TEST_COMMIT_CREDIT + "\"")
_349_pr = _iss_guard("gh pr create --title T --body \"Refs #5\n\n" + TEST_PR_CREDIT + "\"")
_349_bad = _iss_guard("git commit -m \"fix: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\"")
commit_case(
    "credit check (#349): 'Committed by " + TEST_AGENT_NAME + "' and 'Opened by " + TEST_AGENT_NAME + "' pass; a Claude co-author is refused",
    "credits Claude" not in _iss_reason(_349_ok) and "credits Claude" not in _iss_reason(_349_pr)  # other guards may still speak
    and _iss_decision(_349_bad) == "deny" and "credits Claude" in _iss_reason(_349_bad)
    and TEST_COMMIT_CREDIT in _iss_reason(_349_bad) and TEST_PR_CREDIT in _iss_reason(_349_bad),
    "ok %r | pr %r | bad %r" % (_349_ok[:80], _349_pr[:80], _iss_reason(_349_bad)[:160]),
)

# (e) a snapshot ref goes, locally and on origin, once its helper's branch is merged; an unmerged one stays
_349_root = os.path.join(_FIXTURE_ROOT, "snap349")
_349_remote, _349_work = os.path.join(_349_root, "remote.git"), os.path.join(_349_root, "work")
os.makedirs(_349_work)
_349_git(_349_root, "init", "-q", "--bare", _349_remote)
_349_git(_349_work, "init", "-q", "-b", "main")
with open(os.path.join(_349_work, "a.txt"), "w") as f:
    f.write("base\n")
_349_git(_349_work, "add", "a.txt")
_349_git(_349_work, "commit", "-q", "-m", "base")
_349_git(_349_work, "remote", "add", "origin", _349_remote)
_349_git(_349_work, "push", "-q", "-u", "origin", "main")


def _349_snapshot(branch, extra_file=None):
    """Make branch with one commit, then a snapshot ref on top of it (with an unsaved file when extra_file), pushed."""
    _349_git(_349_work, "switch", "-q", "-c", branch, "main")
    with open(os.path.join(_349_work, branch + ".txt"), "w") as f:
        f.write("work\n")
    _349_git(_349_work, "add", "-A")
    _349_git(_349_work, "commit", "-q", "-m", "helper work")
    idx = os.path.join(_349_work, ".git", "snap-index")
    env = dict(os.environ, GIT_INDEX_FILE=idx)
    subprocess.run(["git", "-C", _349_work, "read-tree", "HEAD"], check=True, env=env)
    if extra_file:
        with open(os.path.join(_349_work, extra_file), "w") as f:
            f.write("unsaved\n")
    subprocess.run(["git", "-C", _349_work, "add", "-A"], check=True, env=env)
    tree = subprocess.run(["git", "-C", _349_work, "write-tree"], check=True, env=env, stdout=subprocess.PIPE).stdout.decode().strip()
    os.remove(idx)
    if extra_file:
        os.remove(os.path.join(_349_work, extra_file))
    sha = _349_git(_349_work, "commit-tree", tree, "-p", "HEAD", "-m", "snap").stdout.decode().strip()
    ref = "refs/house-rules/autosave/" + branch
    _349_git(_349_work, "update-ref", ref, sha)
    _349_git(_349_work, "push", "-q", "origin", ref + ":" + ref)
    _349_git(_349_work, "switch", "-q", "main")
    return ref


def _349_has(ref, remote=False):
    d = _349_remote if remote else _349_work
    return _349_git(d, "rev-parse", "--verify", "-q", ref, check=False).returncode == 0


_349_merged = _349_snapshot("worktree-agent-merged349")
_349_open = _349_snapshot("worktree-agent-open349")
_349_unsaved = _349_snapshot("worktree-agent-unsaved349", extra_file="unsaved.txt")
_349_git(_349_work, "merge", "-q", "--no-ff", "-m", "merge helper", "worktree-agent-merged349")
_349_git(_349_work, "merge", "-q", "--no-ff", "-m", "merge helper", "worktree-agent-unsaved349")
_349_swp = run_hook("worktreesweep", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi", "session_id": "v349",
                    "cwd": _349_work}), env=env_in(_349_work))
commit_case(
    "snapshot (#349): the snapshot ref is deleted locally and on origin once its helper's branch is merged",
    not _349_has(_349_merged) and not _349_has(_349_merged, True) and "dropped the snapshot" in _349_swp[1],
    "local %s, origin %s | out %r | err %r" % (_349_has(_349_merged), _349_has(_349_merged, True), _349_swp[1][:200], _349_swp[2][:200]),
)
commit_case(
    "snapshot (#349): a snapshot whose branch is unmerged, or that holds unsaved work, is kept",
    _349_has(_349_open) and _349_has(_349_open, True) and _349_has(_349_unsaved) and _349_has(_349_unsaved, True),
    "open %s/%s, unsaved %s/%s" % (_349_has(_349_open), _349_has(_349_open, True), _349_has(_349_unsaved), _349_has(_349_unsaved, True)),
)

# (f) run.sh settingsgate with no interpreter fails closed, like guard
_349_env = dict(os.environ)
_349_env.pop("HOUSE_RULES_PYTHON", None)
_349_env["PATH"] = ""
_349_sg = run_shell([RUN, "settingsgate"], payload="{}", env=_349_env)
_349_gd = run_shell([RUN, "guard"], payload="{}", env=_349_env)
commit_case(
    "run.sh settingsgate with no working interpreter fails closed (exit 2, a stderr message), as guard does (#349)",
    _349_sg[0] == 2 and "settingsgate" in _349_sg[2] and "Blocking" in _349_sg[2] and _349_gd[0] == 2,
    "settingsgate exit %s stderr %r | guard exit %s" % (_349_sg[0], _349_sg[2][:160], _349_gd[0]),
)


finish()
