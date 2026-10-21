#!/usr/bin/env python3
"""checks/design_loop.py - the design loop part: the stage machine, the issue and pull request rules, the page checks, the checkpoint table, and the clear-writing cases that share its project folder (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/design_loop.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: design_loop")
print("=" * 43)
print()


# --- issue workflow (2.49.0): #108 PR Refs rule, #109 issue close asks, #110 plan -> issues gate ---
# Every case runs against a throwaway repo in _FIXTURE_ROOT. A stub `gh` on PATH writes a marker
# file when it is run, so "the hooks never run gh on a tool call" is asserted, not assumed.
# Plan: docs/plans/issue-workflow-build-plan.md.
_ISS_PLAN5 = "# Plan\n\n1. one\n2. two\n3. three\n4. four\n5. five\n"
_ISS_PLAN3 = "# Plan\n\n1. one\n2. two\n3. three\n"
_ISS_MARK = os.path.join(_FIXTURE_ROOT, "gh-was-run.marker")


def _iss_stub(body_ok=True):
    """Write a stub gh into _ISS_STUBDIR. It records that it ran, then prints two issues (or fails)."""
    if os.name == "nt":
        path = os.path.join(_ISS_STUBDIR, "gh.cmd")
        lines = ["@echo off", "echo ran> \"%s\"" % _ISS_MARK]
        if body_ok == "empty":
            lines.append("echo []")
        elif body_ok:
            lines.append("echo [{\"number\":7,\"title\":\"Fix the login screen\"},{\"number\":3,\"title\":\"Add sound\"}]")
        else:
            lines += ["echo HTTP 401: bad credentials 1>&2", "exit /b 1"]
        open(path, "w", encoding="utf-8", newline="\r\n").write("\r\n".join(lines) + "\r\n")
    else:
        path = os.path.join(_ISS_STUBDIR, "gh")
        lines = ["#!/bin/sh", "echo ran > '%s'" % _ISS_MARK]
        if body_ok == "empty":
            lines.append("echo '[]'")
        elif body_ok:
            lines.append("echo '[{\"number\":7,\"title\":\"Fix the login screen\"},{\"number\":3,\"title\":\"Add sound\"}]'")
        else:
            lines += ["echo 'HTTP 401: bad credentials' >&2", "exit 1"]
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        os.chmod(path, 0o755)


def _iss_state_path(d):
    return os.path.join(_as_git(d, "rev-parse", "--absolute-git-dir"), "house-rules-issues.json")


def _iss_state(d):
    try:
        return json.load(open(_iss_state_path(d), encoding="utf-8"))
    except (OSError, ValueError):
        return None


_iss_stub(True)
_issues_outputs = []

# -- #110: delegate counts steps and writes the state -----------------------------------------
_d = _iss_repo()
_, _o, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _d, plan=_ISS_PLAN5), _d)
_issues_outputs.append(("delegate 5 steps", _o))
_st = _iss_state(_d)
_ctx = _stop_context(_o)
commit_case(
    "issues: a 5-step plan writes the gate state and the delegate note says to create the issues",
    bool(_st) and _st.get("needs_issues") is True and _st.get("plan_steps") == 5 and "5 steps" in _ctx
    and "parent issue" in _ctx and "AjsAgent created this" in _ctx and "in progress" in _ctx
    and "Claude completed this" not in _ctx,
    "state %r" % _st,
)
_d3 = _iss_repo()
_, _o3, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _d3, plan=_ISS_PLAN3), _d3)
_issues_outputs.append(("delegate 3 steps", _o3))
commit_case(
    "issues: a 3-step plan writes nothing and the note names the count",
    _iss_state(_d3) is None and "counts 3 step(s)" in _stop_context(_o3),
    "state %r" % _iss_state(_d3),
)
_dh = _iss_repo()
_, _oh, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dh,
                      plan="## Steps\n\n### Step 1 - a\n### Step 2 - b\n### Change 3 - c\n- [ ] d\n"), _dh)
commit_case(
    "issues: '### Step', '### Change' headings and '- [ ]' items count as steps",
    (_iss_state(_dh) or {}).get("plan_steps") == 4, "state %r" % _iss_state(_dh),
)

# -- #110: the gate in commitgate --------------------------------------------------------------
_fp = lambda rel: os.path.join(_d, rel)
_, _og, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp("Assets/Foo.cs"), content="x"), _d)
_issues_outputs.append(("gate deny", _og))
commit_case(
    "issues: with the gate closed, a Write to a source file is denied naming both missing pieces",
    _iss_decision(_og) == "deny" and "parent issue" in _iss_reason(_og) and "child issue" in _iss_reason(_og),
    "out %r" % _og[:160],
)
_, _oe, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Edit", _d, file_path=_fp("src/a.py")), _d)
_, _on, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "NotebookEdit", _d, notebook_path=_fp("n.ipynb")), _d)
commit_case(
    "issues: Edit and NotebookEdit on source files are denied too",
    _iss_decision(_oe) == "deny" and _iss_decision(_on) == "deny", "edit %r notebook %r" % (_oe[:60], _on[:60]),
)
_allowed = []
for _rel in ("docs/x.md", "docs/sub/y.json", "README.md", "src/notes.md", ".claude/settings.json"):
    _, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp(_rel)), _d)
    if _oa.strip():
        _allowed.append((_rel, _oa[:60]))
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=os.path.join(_FIXTURE_ROOT, "elsewhere.cs")), _d)
if _oa.strip():
    _allowed.append(("outside project", _oa[:60]))
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_iss_state_path(_d)), _d)
if _oa.strip():
    _allowed.append(("state file", _oa[:60]))
commit_case(
    "issues: docs/, .md files, .claude/, files outside the project and the state file stay editable",
    not _allowed, "denied: %r" % _allowed,
)
_, _ob, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Bash", _d, command="true"), _d)
commit_case("issues: Bash is never gated", _ob.strip() == "", "out %r" % _ob[:80])

# -- #110: recording creations clears the gate --------------------------------------------------
_label_cmd = 'gh issue create --title "t" --body "b" --label "AjsAgent created this" --label bug'
_bare_cmd = 'gh issue create --title "t" --body "b" --label bug'


def _iss_created(d, cmd, n):
    return _iss_call("autosave", dict(_iss_payload("PostToolUse", "Bash", d, command=cmd),
                                      tool_response={"stdout": "https://github.com/o/r/issues/%d\n" % n}), d)


_, _ou, _ = _iss_created(_d, _bare_cmd, 50)
_issues_outputs.append(("unlabelled create", _ou))
_st = _iss_state(_d)
commit_case(
    "issues: an unlabelled `gh issue create` gets a correction note and does not count",
    "without the `AjsAgent created this` label" in _ou and _st["needs_issues"] is True
    and _st["created"] and _st["created"][0]["labelled"] is False,
    "state %r out %r" % (_st, _ou[:100]),
)
_, _o1, _ = _iss_created(_d, _label_cmd, 51)
_st1 = _iss_state(_d)
_, _o2, _ = _iss_created(_d, _label_cmd, 52)
_issues_outputs.append(("labelled create 2", _o2))
_st2 = _iss_state(_d)
commit_case(
    "issues: the gate clears after two labelled issues (parent plus one child), not after one",
    _st1["needs_issues"] is True and _st2["needs_issues"] is False and "unblocked" in _o2
    and _st2["created"][-1] == {"repo": "o/r", "number": 52, "labelled": True},
    "after one %r, after two %r" % (_st1["needs_issues"], _st2["needs_issues"]),
)
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp("Assets/Foo.cs")), _d)
commit_case("issues: once cleared the same source Write is allowed", _oa.strip() == "", "out %r" % _oa[:80])
_old_label_cmd = 'gh issue create --title "t" --body "b" --label "Claude created this" --label bug'
for _lc, _nm in ((_label_cmd, "AjsAgent created this"), (_old_label_cmd, "Claude created this (old)")):
    _dl = _iss_repo()
    _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dl, plan=_ISS_PLAN5), _dl)
    _iss_created(_dl, _lc, 70)
    _stl = _iss_state(_dl)
    commit_case(
        "issues: a `gh issue create` with the `%s` label counts as labelled" % _nm,
        _stl["created"] and _stl["created"][0]["labelled"] is True, "state %r" % (_stl,),
    )
_dn = _iss_repo()
_, _onone, _ = _iss_created(_dn, _label_cmd, 60)
commit_case(
    "issues: a `gh issue create` with no plan state is not recorded and says nothing",
    _onone.strip() == "" and _iss_state(_dn) is None, "out %r" % _onone[:80],
)
_dm = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dm, plan=_ISS_PLAN5), _dm)
_, _omiss, _ = _iss_call("autosave", dict(_iss_payload("PostToolUse", "Bash", _dm, command=_label_cmd),
                                          tool_response={"stdout": "error: network down"}), _dm)
commit_case(
    "issues: a `gh issue create` whose output has no issue URL is said out loud and not counted",
    "no issue URL" in _omiss and _iss_state(_dm)["created"] == [], "out %r" % _omiss[:120],
)

# -- #110: stop line, corrupt state, kill switch, subagent worktree -----------------------------
_ds = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _ds, plan=_ISS_PLAN5), _ds)
_, _ostop, _ = run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_ds), env=_iss_env())
_issues_outputs.append(("stop", _ostop))
commit_case(
    "issues: Stop adds one line while the gate is still closed and does not block",
    "plans become issues" in _stop_context(_ostop) and '"decision"' not in _ostop,
    "out %r" % _ostop[:160],
)
_, _ostop2, _ = run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_d), env=_iss_env())
commit_case("issues: Stop stays silent once the gate is cleared", "plans become issues" not in _ostop2, "out %r" % _ostop2[:100])

_dc = _iss_repo()
open(_iss_state_path(_dc), "w", encoding="utf-8").write("{not json")
_, _oc, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dc, file_path=os.path.join(_dc, "a.cs")), _dc)
_issues_outputs.append(("corrupt state", _oc))
commit_case(
    "issues: a corrupt state file is reported in one line and treated as no gate",
    "could not read house-rules-issues.json" in _oc and _iss_decision(_oc) is None,
    "out %r" % _oc[:160],
)

_dk = _iss_repo()
_, _ok, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk, plan=_ISS_PLAN5), _dk,
                      HOUSE_RULES_ISSUES="off")
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk, plan=_ISS_PLAN5), _dk)  # state now exists
_, _ogk, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dk, file_path=os.path.join(_dk, "a.cs")), _dk,
                       HOUSE_RULES_ISSUES="off")
_, _opk, _ = _iss_call("guard", _iss_payload("PreToolUse", "Bash", _dk, command='gh pr create --title T --body "Closes #5"'), _dk,
                       HOUSE_RULES_ISSUES="off")
_, _ock, _ = _iss_call("guard", _iss_payload("PreToolUse", "Bash", _dk, command="gh issue close 5"), _dk,
                       HOUSE_RULES_ISSUES="off")
_dk2 = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk2, plan=_ISS_PLAN5), _dk2, HOUSE_RULES_ISSUES="off")
commit_case(
    "issues: HOUSE_RULES_ISSUES=off writes no state and disables the gate, the PR rule and the close prompt",
    _iss_state(_dk2) is None and _ogk.strip() == "" and _opk.strip() == "" and _ock.strip() == "",
    "gate %r pr %r close %r" % (_ogk[:40], _opk[:40], _ock[:40]),
)

_dw = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dw, plan=_ISS_PLAN5), _dw)
_wt = os.path.join(_FIXTURE_ROOT, "iss-subagent-wt")
_as_git(_dw, "worktree", "add", "-q", "-b", "worktree-agent-iss", _wt)
_, _osub, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _wt, file_path=os.path.join(_wt, "a.cs")), _wt)
_, _omain, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dw, file_path=os.path.join(_dw, "a.cs")), _dw)
commit_case(
    "issues: the main session's gate does not apply inside a subagent worktree (its own git directory)",
    _iss_decision(_omain) == "deny" and _osub.strip() == "", "main %r subagent %r" % (_iss_decision(_omain), _osub[:60]),
)


_pr = lambda body: 'gh pr create --title "T" --body "%s"' % body
_ocl = _iss_guard(_pr("Closes #5"))
_issues_outputs.append(("pr closes", _ocl))
commit_case(
    "pr: a body with 'Closes #5' is denied and the reason explains the merge-time close",
    _iss_decision(_ocl) == "deny" and "before the user has tested" in _iss_reason(_ocl), "out %r" % _ocl[:140],
)
_bad = []
for _b in ("Fixes #5", "resolved #5", "FIXED owner/repo#7", "Close: #9", "closes https://github.com/o/r/issues/4"):
    if _iss_decision(_iss_guard(_pr(_b))) != "deny":
        _bad.append(_b)
commit_case("pr: every closing word in any tense, any case, with #N, owner/repo#N or a URL is denied", not _bad, "not denied: %r" % _bad)
_onr = _iss_guard(_pr("Just a change"))
commit_case(
    "pr: a body with no Refs / Part of / No-issue is denied",
    _iss_decision(_onr) == "deny" and "Refs #N" in _iss_reason(_onr), "out %r" % _onr[:140],
)
_bad = []
for _b in ("Refs #5", "Refs owner/repo#5", "Part of #12", "Summary\\n\\nNo-issue: typo fix"):
    if _iss_guard(_pr(_b)).strip():
        _bad.append(_b)
commit_case("pr: Refs #N, Refs owner/repo#N, Part of #N and a No-issue line are allowed", not _bad, "not allowed: %r" % _bad)
_heredoc = "gh pr create --title T --body \"$(cat <<'EOF'\n## Summary\nthings\n\nRefs #108, #109\nEOF\n)\""
commit_case("pr: a heredoc body carrying Refs is allowed", _iss_guard(_heredoc).strip() == "", "out %r" % _iss_guard(_heredoc)[:100])
_bf = os.path.join(_dp, "body.md")
open(_bf, "w", encoding="utf-8").write("Summary\n\nRefs #5\n")
_bfc = os.path.join(_dp, "bodyc.md")
open(_bfc, "w", encoding="utf-8").write("Summary\n\nFixes #5\n")
_bfn = os.path.join(_dp, "bodyn.md")
open(_bfn, "w", encoding="utf-8").write("Summary only\n")
commit_case(
    "pr: --body-file / -F is read: Refs allowed, closing word denied, no link denied",
    _iss_guard("gh pr create --title T --body-file body.md").strip() == ""
    and _iss_decision(_iss_guard("gh pr create -t T -F bodyc.md")) == "deny"
    and _iss_decision(_iss_guard("gh pr create --title T --body-file bodyn.md")) == "deny",
    "three file cases",
)
_ou = _iss_guard("gh pr create --title T --body-file missing.md")
_ow = _iss_guard("gh pr create --web")
_os = _iss_guard("gh pr create --title T --body-file -")
commit_case(
    "pr: an unreadable body file, stdin, and --web / no body all ask instead of allowing",
    _iss_decision(_ou) == "ask" and "could not read" in _iss_reason(_ou)
    and _iss_decision(_ow) == "ask" and _iss_decision(_os) == "ask",
    "missing %r web %r stdin %r" % (_iss_decision(_ou), _iss_decision(_ow), _iss_decision(_os)),
)
commit_case(
    "pr: commands that only mention gh pr create (a commit message, an echo) are not checked",
    all(_iss_guard(c).strip() == "" for c in ('echo "gh pr create is checked"', 'grep -r "gh pr create" docs')),
    "two commands that only mention it",
)

# -- #177: a commit authored as Claude is refused ----------
AGENT_IDENTITY_FIX_TEXT = (
    "git config user.name \"AJ's agent\" && git config user.email \"79066376+Ajw2003@users.noreply.github.com\""
)
_au1 = _iss_guard("git commit -m x", _au_bad)
_au2 = _iss_guard("git commit -m x", _au_good)
_au3 = _iss_guard('git commit --author "Claude <noreply@anthropic.com>" -m x', _au_good)
_au4 = _iss_guard("git -c user.name=\"AJ's agent\" -c user.email=79066376+Ajw2003@users.noreply.github.com commit -m x", _au_bad)
_au5 = _iss_guard("GIT_AUTHOR_EMAIL=noreply@anthropic.com git commit -m x", _au_good)
_au6 = _iss_guard("git commit --author='Claudette <c@example.com>' -m x", _au_bad)
_au7 = _iss_guard("git commit -m x", _au_bad, HOUSE_RULES_ATTRIBUTION="off")
_au9 = _iss_guard("git -c user.name=\"AJ's agent\" -c user.email=bot@anthropic.com commit -m x", _au_good)
_au10 = _iss_guard("git -c \"user.name=Claude\" commit -m x", _au_good)
_au11 = _iss_guard("git -c \"user.name=AJ's agent\" -c 'user.email=79066376+Ajw2003@users.noreply.github.com' commit -m x", _au_bad)
_au8 = _iss_call("guard", _iss_payload("PreToolUse", "PowerShell", _au_bad, command="git commit -m x"), _au_bad)[1]
commit_case(
    "author: a Claude repo identity is refused with the repo-local fix command; AJ's agent passes",
    _iss_decision(_au1) == "deny" and AGENT_IDENTITY_FIX_TEXT in _iss_reason(_au1) and "--global" not in _iss_reason(_au1)
    and _iss_decision(_au2) != "deny",
    "out %r | %r" % (_au1[:200], _au2[:80]),
)
commit_case(
    "author: --author Claude and GIT_AUTHOR_EMAIL at anthropic.com are refused; inline -c identity overrides a Claude config",
    _iss_decision(_au3) == "deny" and _iss_decision(_au5) == "deny" and _iss_decision(_au4) != "deny",
    "out %r | %r | %r" % (_au3[:80], _au5[:80], _au4[:80]),
)
commit_case(
    "author: a quoted -c identity with a space is read (#189): a Claude email or name is refused, AJ's agent overrides a Claude config",
    _iss_decision(_au9) == "deny" and _iss_decision(_au10) == "deny" and _iss_decision(_au11) != "deny"
    and AGENT_IDENTITY_FIX_TEXT in _iss_reason(_au9),
    "out %r | %r | %r" % (_au9[:80], _au10[:80], _au11[:80]),
)
commit_case(
    "author: a name merely containing claude passes, and HOUSE_RULES_ATTRIBUTION=off disables the check",
    _iss_decision(_au6) != "deny" and _iss_decision(_au7) != "deny",
    "out %r | %r" % (_au6[:80], _au7[:80]),
)
commit_case(
    "author: the same refusal applies through the PowerShell tool",
    _iss_decision(_au8) == "deny" and AGENT_IDENTITY_FIX_TEXT in _iss_reason(_au8),
    "out %r" % _au8[:140],
)

# -- #109: gh issue close ---------------------------------------------------------------------------
_occ = _iss_guard("gh issue close 5")
_issues_outputs.append(("issue close", _occ))
commit_case(
    "close: `gh issue close` with nothing recorded is refused (#363), naming what is missing",
    _iss_decision(_occ) == "deny" and "refused to close #5" in _iss_reason(_occ) and "no QA pass is recorded" in _iss_reason(_occ),
    "out %r" % _occ[:160],
)
_bad = []
for _c in ("gh issue close 5 --comment done", "gh issue edit 5 --state closed", "cd x && gh issue close 5",
           "gh api -X PATCH repos/o/r/issues/5 -f state=closed", "gh api repos/o/r/issues/5 --method PATCH -f state=closed"):
    if _iss_decision(_iss_guard(_c)) != "deny":
        _bad.append(_c)
commit_case("close: edit --state closed, a chained close and gh api PATCH to closed are also refused (#363)", not _bad, "not refused: %r" % _bad)
_bad = []
for _c in ("gh issue comment 5 --body hi", 'gh issue create --title t --body b', "gh issue edit 5 --add-label bug",
           "gh api repos/o/r/issues/5", 'git commit -m "gh issue close 5 is gated"'):
    if _iss_decision(_iss_guard(_c)) in ("ask", "deny") and "close guard" in _iss_reason(_iss_guard(_c)):
        _bad.append(_c)
commit_case("close: comment, create, label edits, reads and a commit message mentioning it are not affected", not _bad, "affected: %r" % _bad)
os.makedirs(os.path.join(_dp, ".claude"), exist_ok=True)  # #363: an allowed close, so the delete check is what speaks
with open(os.path.join(_dp, ".claude", "house-rules-loop.json"), "w", encoding="utf-8") as _f:
    json.dump({"skip": False, "approvals": [], "stage": "done", "closable": [
        {"feature": "f", "issues": [{"repo": "", "number": 5}], "qa_at": 1, "qa": "QA passed: f",
         "merged_pr": {"repo": "o/r", "number": 2, "at": 1}}]}, _f)
_ocm = _iss_guard("rm old.txt && gh issue close 5")
os.remove(os.path.join(_dp, ".claude", "house-rules-loop.json"))
commit_case(
    "close: a chained command whose delete is unsafe is refused as a whole, naming the safe way (#291)",
    _iss_decision(_ocm) == "deny" and "deletes one or more files" in _iss_reason(_ocm) and "_to_delete/" in _iss_reason(_ocm),
    "out %r" % _ocm[:120],
)

# -- SessionStart open-issue list (issuelist) ---------------------------------------------------------
_dl = _iss_repo(remote="https://github.com/o/r.git")
if os.path.exists(_ISS_MARK):
    os.remove(_ISS_MARK)
_, _ol, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
_issues_outputs.append(("issuelist", _ol))
_lctx = _stop_context(_ol)
commit_case(
    "issuelist: a GitHub repo gets the open issue titles as SessionStart context",
    "#7 Fix the login screen" in _lctx and "#3 Add sound" in _lctx and "SessionStart" in _ol and len(_lctx) < 1200,
    "out %r" % _ol[:160],
)
_cachef = os.path.join(_as_git(_dl, "rev-parse", "--absolute-git-dir"), "house-rules-issues-cache.json")
try:
    _lmsg = json.loads(_ol).get("systemMessage", "")
except ValueError:
    _lmsg = "unparseable"
commit_case(
    "issuelist: the user sees `house-rules: 2 open issues loaded` in the same single JSON object as the context",
    _lmsg == "house-rules: 2 open issues loaded" and _lctx != "" and _ol.strip().count("\n") == 0,
    "systemMessage %r" % _lmsg,
)
_iss_stub(False)
_, _ol2, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
commit_case(
    "issuelist: a second start within 60 s uses the cache and does not call gh again",
    os.path.isfile(_cachef) and "#7 Fix the login screen" in _stop_context(_ol2), "out %r" % _ol2[:100],
)
os.remove(_cachef)
_, _ol3, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
commit_case(
    "issuelist: a gh failure prints `could not list open issues (<reason>)` and no context",
    "could not list open issues (HTTP 401: bad credentials" in _ol3 and _stop_context(_ol3) == "", "out %r" % _ol3[:160],
)
commit_case(
    "issuelist: a gh failure shows no 'loaded' note, only the could-not-list message",
    "loaded" not in _ol3 and "open issues" in _ol3, "out %r" % _ol3[:100],
)
os.remove(_cachef) if os.path.exists(_cachef) else None
_iss_stub("empty")
_, _ol3b, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
try:
    _emsg = json.loads(_ol3b).get("systemMessage", "")
except ValueError:
    _emsg = "unparseable"
commit_case(
    "issuelist: an empty list shows `house-rules: no open issues`",
    _emsg == "house-rules: no open issues", "systemMessage %r" % _emsg,
)
os.remove(_cachef) if os.path.exists(_cachef) else None
_iss_stub(True)
_dnr = _iss_repo(remote="git@example.com:o/r.git")
_, _ol4, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dnr}, _dnr)
_dnr2 = _iss_repo()
_, _ol5, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dnr2}, _dnr2)
_ig_spec = _ig_util.spec_from_file_location("hook_nogh", HOOK)
_ig_mod = _ig_util.module_from_spec(_ig_spec)
_ig_spec.loader.exec_module(_ig_mod)
_ig_which = shutil.which
shutil.which = lambda *_a, **_k: None
try:
    _ig_res = _ig_mod.design_loop._open_issues_text(_dl)
finally:
    shutil.which = _ig_which
_ol6 = "" if _ig_res == ("", None) else "unexpected result %r" % (_ig_res,)
commit_case(
    "issuelist: no GitHub remote, no remote at all, or no gh on PATH is silent (nothing to list)",
    _ol4.strip() == "" and _ol5.strip() == "" and _ol6.strip() == "", "out %r %r %r" % (_ol4[:40], _ol5[:40], _ol6[:40]),
)
_, _ol7, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl, HOUSE_RULES_ISSUES="off")
commit_case("issuelist: HOUSE_RULES_ISSUES=off prints nothing", _ol7.strip() == "", "out %r" % _ol7[:60])

# -- constraints the plan sets --------------------------------------------------------------------------
if os.path.exists(_ISS_MARK):
    os.remove(_ISS_MARK)
_iss_stub(True)
_dq = _iss_repo(remote="https://github.com/o/r.git")
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dq, plan=_ISS_PLAN5), _dq)
_iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dq, file_path=os.path.join(_dq, "a.cs")), _dq)
_iss_created(_dq, _label_cmd, 1)
_iss_guard("gh issue close 5", _dq)
_iss_guard('gh pr create --title T --body "Refs #1"', _dq)
run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_dq), env=_iss_env())
commit_case(
    "issues: delegate, commitgate, the Bash PostToolUse entry, guard and handover never run gh (no network on a tool call)",
    not os.path.exists(_ISS_MARK), "gh stub marker present: %s" % os.path.exists(_ISS_MARK),
)
_multi = []
for _name, _o in _issues_outputs:
    if not _o.strip():
        continue
    try:
        json.loads(_o)
    except ValueError:
        _multi.append("%s: %r" % (_name, _o[:80]))
commit_case("issues: every new output parses as exactly one JSON object", not _multi, "; ".join(_multi) or "%d outputs checked" % len(_issues_outputs))
_rules_text = read(RULES_FILE)
_detail = os.path.join(DETAIL_DIR, "issue-workflow.md")
commit_case(
    "issues: the rules section and its detail file exist, and the plugin is 2.72.0",
    "becomes issues" in _rules_text and "rules/detail/issue-workflow.md" in _rules_text and os.path.isfile(_detail)
    and "HOUSE_RULES_ISSUES=off" in read(_detail)
    and json.load(open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"] == "2.72.0",
    "rules section + detail file + version",
)

# --- nothing publishes a page unasked, and the rule and the table say the same thing ---------
# The threshold used to live in two places that nothing compared: rules/house-rules.md drove the
# behaviour, CLAUDE.md's table described it, and only the surface NAMES above were ever checked.
# So the table could have said one number while the rule said another, and the first symptom
# would have been a page the user did not ask for.
pubdrift = []
for phrase in [
    "I never publish a page unasked",
    "two or more steps",
    "A single-step card is not offered a page at all",
]:
    if phrase.lower() not in rules_text.lower():
        pubdrift.append(f"rules/house-rules.md no longer says {phrase!r}")
# The replaced wording must be GONE from the operative text and PRESENT in the Why - those are
# two different rules ("nothing stale") and ("when a decision reverses, say what it used to say"),
# and a check that greps the whole section can only ever satisfy one of them. Splitting the
# section at its Why is what lets both be enforced at once.
_sec = rules_text.split("#### When a card is worth publishing as a page", 1)
if len(_sec) != 2:
    pubdrift.append("the publishing section is missing from rules/house-rules.md")
else:
    _body = _sec[1].split(chr(10) + "## ", 1)[0]
    _operative, _, _why = _body.partition("**Why:**")
    for stale in ["four or more steps", "below four steps"]:
        if stale in _operative.lower():
            pubdrift.append(f"the operative rule still carries the replaced wording {stale!r}")
    if "four or more steps" not in _why.lower():
        pubdrift.append("the Why does not record the four-step rule this replaced")
_absent = absent_repo_files("docs/architecture.md")
if _absent:
    pass  # the rules half above still ran; only the table half is unavailable here
elif os.path.isfile(ARCHDOC):
    table_text = read(ARCHDOC)
    rows = [ln for ln in table_text.splitlines() if ln.startswith("| Claude Code")]
    offered = [ln for ln in rows if "offered at 2+ steps" in ln]
    if not offered:
        pubdrift.append("no architecture.md surface row states 'offered at 2+ steps'")
    if "4+ steps" in table_text:
        pubdrift.append("docs/architecture.md still advertises the replaced '4+ steps' threshold")
else:
    pubdrift.append("no docs/architecture.md to check")
if pubdrift and _absent:
    report("FAIL", "the page rule and the architecture.md table agree, and nothing publishes unasked")
    for p in pubdrift:
        print(f"          {p}")
elif _absent:
    skip_repo_check(
        "the page rule and the architecture.md table agree, and nothing publishes unasked",
        _absent,
        extra="the rules half was checked here and passed; only the table half is unavailable",
    )
elif not pubdrift:
    report("PASS", "the page rule and the architecture.md table agree, and nothing publishes unasked")
    print("          rule: offer at 2+ steps, publish only on request; table says the same")
else:
    report("FAIL", "the page rule and the architecture.md table agree, and nothing publishes unasked")
    for p in pubdrift:
        print(f"          {p}")

# --- the design loop: stage tracker, approvals and the code lock (#225) ------------------------
_loop_dir = tempfile.mkdtemp(prefix="house-rules-loop-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _loop_dir], check=True)
_loop_labels_file = os.path.join(_FIXTURE_ROOT, "loop-labels.json")
_loop_env = dict(os.environ, HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="off", HOUSE_RULES_AUTOSAVE="off",
                 HOUSE_RULES_LOOP_LABELS_FILE=_loop_labels_file)


def _loop_gh(label, *numbers):
    """#236: what the stand-in for GitHub says each issue's labels are."""
    try:
        have = json.load(open(_loop_labels_file, encoding="utf-8"))
    except (OSError, ValueError):
        have = {}
    for n in numbers:
        have["o/r#%d" % n] = ["Feature", "AjsAgent created this", label]
    with open(_loop_labels_file, "w", encoding="utf-8") as f:
        json.dump(have, f)


def _loop_post(tool, tool_input, response):
    p = {"hook_event_name": "PostToolUse", "tool_name": tool, "session_id": "loop", "cwd": _loop_dir,
         "tool_input": tool_input, "tool_response": response}
    return run_hook("autosave", json.dumps(p), env=_loop_env)[1]


def _loop_state():
    try:
        return json.load(open(os.path.join(_loop_dir, ".claude", "house-rules-loop.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _loop_stop():
    return run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_loop_dir), env=_loop_env)[1]


def _loop_edit(rel, **extra):
    p = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "loop", "cwd": _loop_dir,
         "tool_input": {"file_path": os.path.join(_loop_dir, rel)}}
    p.update(extra)
    _, out, _ = run_hook("commitgate", json.dumps(p), env=_loop_env)
    try:
        return json.loads(out)["hookSpecificOutput"].get("permissionDecision") or "allow"
    except Exception:
        return "allow"


def _loop_say(prompt, session="loop"):
    p = {"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": _loop_dir, "prompt": prompt}
    _, out, _ = run_hook("scope", json.dumps(p), env=_loop_env)
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def _loop_log(line):
    d = os.path.join(_loop_dir, "docs", "6-decisions")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "Decisions.md"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _loop_issue(number, labelled=True, via="mcp"):
    if via == "mcp":
        p = {"hook_event_name": "PostToolUse", "tool_name": "mcp__github__issue_write", "session_id": "loop",
             "cwd": _loop_dir, "tool_input": {"method": "create", "title": "t",
             "labels": ["Feature", "AjsAgent created this"] if labelled else ["Feature"]},
             "tool_response": {"url": "https://github.com/o/r/issues/%d" % number}}
    else:
        p = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "loop", "cwd": _loop_dir,
             "tool_input": {"command": 'gh issue create --title t --label "%s"' % ("AjsAgent created this" if labelled else "x")},
             "tool_response": {"stdout": "https://github.com/o/r/issues/%d\n" % number}}
    run_hook("autosave", json.dumps(p), env=_loop_env)


def _loop_stage():
    try:
        return json.load(open(os.path.join(_loop_dir, ".claude", "house-rules-loop.json"), encoding="utf-8"))["stage"]
    except (OSError, ValueError, KeyError):
        return "design (no file)"


_loop_cases = []
_loop_cases.append(("a fresh project refuses a code edit", _loop_edit("app.py") == "deny"))
_loop_cases.append(("docs/, .claude/ and .md files stay open",
                    _loop_edit("docs/page.html") == _loop_edit(".claude/x.json") == _loop_edit("notes.md") == "allow"))
_n = _loop_say("looks good, approved")
_loop_cases.append(('a bare "approved" moves nothing and asks which', "names no stage and feature" in _n
                    and _loop_stage() == "design (no file)"))
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(("a build-plan approval before its design moves nothing", "nothing moved" in _n
                    and _loop_stage() == "design (no file)"))
_n = _loop_say("Design approved: blockers")
_loop_cases.append(("an approval in a project with no decisions log moves nothing",
                    "no decisions log" in _n and _loop_stage() == "design (no file)"))
_loop_log("design decisions for blockers")
_n = _loop_say("Design approved: blockers")
_loop_cases.append(('"Design approved: <feature>" moves to Plan, code still closed',
                    _loop_stage() == "plan" and "now Plan" in _n and _loop_edit("app.py") == "deny"))
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(("a build-plan approval with no feature issues moves nothing",
                    "labelled issue(s)" in _n and _loop_stage() == "plan"))
_loop_issue(101, labelled=False)
_loop_issue(102)
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(("an unlabelled issue does not count toward the feature's issues",
                    "has 1 labelled issue(s)" in _n and _loop_stage() == "plan"))
_loop_issue(103, via="bash")
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(("issues from the GitHub tool and from gh both count, so the next check is reached",
                    "labelled issue(s)" not in _n and _loop_stage() == "plan"))
_loop_log("plan decisions for blockers")
_loop_gh("in progress", 101, 102)
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(("label check: a build-plan approval is refused while an issue isn't in progress, naming it",
                    "not labelled `in progress`: #103" in _n and _loop_stage() == "plan"))
_loop_gh("in progress", 103)
_n = _loop_say("Build plan approved: blockers")
_loop_cases.append(('"Build plan approved: <feature>" opens code', _loop_stage() == "build"
                    and _loop_edit("app.py") == "allow"))
_loop_say("hello", session="other")
_loop_cases.append(('"Build plan approved" carries the hand-to-a-helper instruction', "@house-rules:builder" in _n))
_g = _loop_say("go ahead and build it")
_loop_cases.append(("with the loop on, a go-ahead message no longer gets the guess", "reads like a go-ahead" not in _g))
_sp = {"hook_event_name": "SubagentStart", "session_id": "loop", "agent_id": "h1", "agent_type": "house-rules:builder",
       "cwd": _loop_dir, "transcript_path": os.path.join(_FIXTURE_ROOT, "loop.jsonl")}
_, _so, _ = run_hook("subagentrules", json.dumps(_sp), env=_loop_env)
try:
    _so = json.loads(_so)["hookSpecificOutput"]["additionalContext"]
except Exception:
    pass
_loop_cases.append(("a helper starts knowing the feature, its stage and issues, and that it only builds",
                    '"blockers"' in _so and "Build" in _so and "#102" in _so and "never design" in _so))
_loop_cases.append(("the stage carries into a new session", _loop_stage() == "build"
                    and _loop_edit("app.py", session_id="other") == "allow"))
_loop_log("build log for blockers")
_loop_cases.append(("label check: quiet at the end of a reply when every label fits", "design loop" not in _loop_stop()))
_loop_gh("needs review", 102)
_loop_cases.append(("label check: in Build, a code edit is refused while an issue isn't in progress",
                    _loop_edit("app.py") == "deny"))
_loop_cases.append(("label check: the end-of-reply check names the wrong label",
                    "should be labelled `in progress`" in _loop_stop() and "#102" in _loop_stop()))
_n = _loop_say("QA passed: blockers")
_loop_cases.append(("label check: a QA answer before every issue says needs review moves nothing",
                    "QA starts only once" in _n and "#101" in _n and _loop_stage() == "build"))
os.remove(_loop_labels_file)
_o = _loop_post("mcp__github__issue_write", {"method": "update", "owner": "o", "repo": "r", "issue_number": 101,
                "labels": ["Feature", "needs review"]}, {"url": "https://github.com/o/r/issues/101"})
_o += _loop_post("Bash", {"command": 'gh issue edit 102 --add-label "needs review" --remove-label "in progress"'},
                 {"stdout": "https://github.com/o/r/issues/102\n"})
_loop_cases.append(("label check: label changes from the GitHub tool and from gh are recorded",
                    _loop_state().get("labels", {}).get("o/r#101") == ["Feature", "needs review"]
                    and _loop_state().get("labels", {}).get("o/r#102") == ["Feature", "AjsAgent created this", "needs review"]))
_o = _loop_post("Bash", {"command": 'gh api repos/o/r/issues/201/labels -f "labels[]=in progress"'}, [{"name": "in progress"}])
_o += _loop_post("Bash", {"command": "gh api -X POST repos/o/r/issues/202/labels -f 'labels[]=needs review' -f labels[]=bug"}, [{"name": "bug"}])
_loop_cases.append(("#278: a REST label add (gh api .../issues/N/labels) is recorded against the issue in the path",
                    _loop_state().get("labels", {}).get("o/r#201") == ["in progress"]
                    and _loop_state().get("labels", {}).get("o/r#202") == ["needs review", "bug"]))
_o = _loop_post("Bash", {"command": "gh api -X DELETE repos/o/r/issues/201/labels/in%20progress"}, "")
_loop_cases.append(("#278: a REST label remove with %20 is recorded as removing `in progress`",
                    _loop_state().get("labels", {}).get("o/r#201") == []))
_loop_post("Bash", {"command": "gh api --method DELETE repos/o/r/issues/202/labels/bug"}, "")
_loop_cases.append(("#278: the --method DELETE form is recorded too",
                    _loop_state().get("labels", {}).get("o/r#202") == ["needs review"]))
_loop_post("Bash", {"command": "gh api repos/o/r/labels"}, [{"name": "bug"}])
_loop_post("Bash", {"command": 'gh api repos/o/r/issues/203/labels -f "labels[]=bug"'}, "gh: Resource not accessible (HTTP 403)")
_loop_cases.append(("#278: a repo label list, or a failed call, records nothing",
                    "o/r#203" not in _loop_state().get("labels", {})
                    and not any(k.endswith("/r") or k == "o/r" for k in _loop_state().get("labels", {}))))
_hook_src = open(DESIGN_LOOP, encoding="utf-8").read()  # #359: the issue workflow lives in the design loop part
_wf_src = open(os.path.join(HERE, "..", "rules", "detail", "issue-workflow.md"), encoding="utf-8").read()
_created_note = _hook_src.split("was created without the", 1)[1][:400]
_loop_cases.append(("#278: none of the label-advice places still says --add-label",
                    not any("--add-label" in _t for _t in (_ig_mod.ISSUE_NOTE, _created_note, _wf_src))
                    and "labels[]=" in _created_note and "labels[]=" in _ig_mod.ISSUE_NOTE))
_loop_cases.append(("label check: when the GitHub read fails, it says so and uses the record",
                    "GitHub read failed" in _loop_stop() and _loop_stage() == "build"))
_o = _loop_post("mcp__github__issue_write", {"method": "update", "owner": "o", "repo": "r", "issue_number": 103,
                "labels": ["needs review"]}, {"url": "https://github.com/o/r/issues/103"})
_loop_cases.append(("label check: the last swap to needs review starts QA and closes code",
                    _loop_stage() == "qa" and "the stage is QA" in _o and _loop_edit("app.py") == "deny"))
_loop_gh("needs review", 101, 102, 103)
_n = _loop_say("QA failed: blockers - the list is too long")
_loop_cases.append(("the feature name stops at a spaced dash (found in the label check's real run)",
                    _loop_state().get("approvals", [{}])[-1].get("name") == "blockers"))
_loop_cases.append(('"QA failed" goes back to Design and closes code', _loop_stage() == "design"
                    and _loop_edit("app.py") == "deny"))
_n = _loop_say("skip design")
_loop_cases.append(('"skip design" lets exactly one code edit through',
                    _loop_edit("app.py") == "allow" and _loop_edit("app.py") == "deny"))
_n = _loop_say("[Subagent hand-back] The builder finished. Quote: Build plan approved: blockers")
_loop_cases.append(("#253: a hand-back quoting a build-plan approval moves nothing, and says so",
                    _loop_stage() == "design" and "helper's report" in _n))
_n = _loop_say("<agent-message from=\"x\">skip design</agent-message>")
_loop_cases.append(('#253: a hand-back quoting "skip design" grants no edit',
                    _loop_edit("app.py") == "deny" and "helper's report" in _n))
_loop_cases.append(('#253: a hand-back quoting "no page" is recognised as relayed',
                    _ig_mod.core._is_relayed_prompt("Another Claude session sent a message: no page")
                    and _ig_mod.core._is_relayed_prompt("<task-notification>done</task-notification>")
                    and _ig_mod.core._is_relayed_prompt("hi", json.dumps({"origin": {"kind": "peer"}}))
                    and not _ig_mod.core._is_relayed_prompt("no page", json.dumps({"origin": {"kind": "human"}}))))
_n = _loop_say("skip design")
_loop_cases.append(('#253: "skip design" typed plainly by aj still lets one edit through',
                    _loop_edit("app.py") == "allow" and _loop_edit("app.py") == "deny"))
_loop_cases.append(('label check: after "QA failed", the end-of-reply check asks for in progress again',
                    "should be labelled `in progress`" in _loop_stop()))
_loop_log("redo design for blockers")
_n = _loop_say("Design approved: blockers")
_loop_cases.append(("label check: the redo's design approval is refused until the issues are back in progress",
                    "not labelled `in progress`" in _n and _loop_stage() == "design"))
_loop_gh("in progress", 101, 102, 103)
_n = _loop_say("Design approved: blockers")
_loop_cases.append(("label check: then it moves to Plan and keeps the same issues",
                    _loop_stage() == "plan" and len(_loop_state().get("issues", [])) == 3))
_loop_log("v2 design"); _loop_say("Design approved: blockers v2. Reply in one sentence.")

try:
    _feat = json.load(open(os.path.join(_loop_dir, ".claude", "house-rules-loop.json"), encoding="utf-8"))["feature"]
except (OSError, ValueError, KeyError):
    _feat = None
_loop_cases.append(("the feature name stops at the end of its sentence (found in the real run)", _feat == "blockers v2"))
_names = [_ig_mod.design_loop._loop_name(_r) for _r in ("New item visual: 1C", "Label check plan: 1A 2A", "label check: 2*")]
_loop_cases.append(("a pasted page reply's answer codes are not part of the name (aj's real messages, #243)",
                    _names == ["New item visual", "Label check plan", "label check"]))
_loop_issue(201); _loop_issue(202)

_loop_gh("in progress", 201, 202)
_loop_post("mcp__github__create_pull_request", {"owner": "o", "repo": "r"}, {"url": "https://github.com/o/r/pull/9"})
_loop_cases.append(("#267: a pull request opening in Plan moves nothing", _loop_stage() == "plan"))
_loop_log("v2 plan"); _loop_say("Build plan approved: blockers v2")

_loop_post("mcp__github__create_pull_request", {"owner": "o", "repo": "r"}, {"error": "422 validation failed"})
_loop_post("Bash", {"command": 'gh pr create --body "Refs #267"'}, {"stdout": "", "stderr": "no commits"})
_loop_cases.append(("#267: a failed pull request creation (no URL) leaves Build", _loop_stage() == "build"))
_o = _loop_post("mcp__github__create_pull_request", {"owner": "o", "repo": "r"}, {"url": "https://github.com/o/r/pull/9"})
_loop_cases.append(("#267: the GitHub tool opening a pull request in Build starts QA", _loop_stage() == "qa" and "pull request" in _o))
_loop_cases.append(("#267: after that a code edit is refused", _loop_edit("app.py") == "deny"))
_back = _loop_state(); _back["stage"] = "build"

json.dump(_back, open(os.path.join(_loop_dir, ".claude", "house-rules-loop.json"), "w", encoding="utf-8"))
_loop_post("Bash", {"command": 'gh pr create --body "Refs #267"'}, {"stdout": "https://github.com/o/r/pull/10\n"})
_loop_cases.append(("#267: gh pr create opening a pull request in Build starts QA", _loop_stage() == "qa"))
_loop_gh("needs review", 201, 202)
_loop_log("v2 build"); _n = _loop_say("QA passed: blockers v2")

_loop_cases.append(('"QA passed" moves to Done and closes code', _loop_stage() == "done"
                    and _loop_edit("app.py") == "deny"))
_loop_cases.append(("a helper's edit is held by the same lock",
                    _loop_edit("app.py", agent_id="helper1") == "deny"))
_loop_env["HOUSE_RULES_LOOP"] = "off"
_loop_cases.append(("HOUSE_RULES_LOOP=off lifts the lock", _loop_edit("app.py") == "allow"))
_loop_env["HOUSE_RULES_LOOP"] = "on"
os.makedirs(os.path.join(_loop_dir, ".claude"), exist_ok=True)
with open(os.path.join(_loop_dir, ".claude", "house-rules-loop.json"), "w") as _f:
    _f.write("{not json")
_p = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "loop", "cwd": _loop_dir,
      "tool_input": {"file_path": os.path.join(_loop_dir, "app.py")}}
_, _o, _ = run_hook("commitgate", json.dumps(_p), env=_loop_env)
_loop_cases.append(("an unreadable tracker says so instead of failing silently", "could not read house-rules-loop.json" in _o))
# -- #262: one stage per repo (worktrees share it) and the lock covers script writes ------------
_wt_main = tempfile.mkdtemp(prefix="house-rules-wt-", dir=_FIXTURE_ROOT)
_wt_tree = _wt_main + "-tree"
for _a in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"],
           ["worktree", "add", "-q", "-b", "wt-branch", _wt_tree]):
    subprocess.run(["git"] + _a, cwd=_wt_main, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wt_stage(stage):
    os.makedirs(os.path.join(_wt_main, ".claude"), exist_ok=True)
    with open(os.path.join(_wt_main, ".claude", "house-rules-loop.json"), "w", encoding="utf-8") as f:
        json.dump({"feature": "f", "stage": stage, "skip": False, "approvals": []}, f)


def _wt_gate(tool, tool_input, cwd):
    p = {"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": "wt", "cwd": cwd, "tool_input": tool_input}
    _, out, _ = run_hook("commitgate", json.dumps(p), env=_loop_env)
    try:
        h = json.loads(out)["hookSpecificOutput"]
        return h.get("permissionDecision") or "allow", h.get("permissionDecisionReason", "")
    except Exception:
        return "allow", ""


def _wt_bash(cmd, cwd=None):
    return _wt_gate("Bash", {"command": cmd}, cwd or _wt_main)


def _wt_raw(cmd):
    """The commitgate's whole output for a Bash command, to read its report-only note (#309)."""
    p = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "wt", "cwd": _wt_main,
         "tool_input": {"command": cmd}}
    return run_hook("commitgate", json.dumps(p), env=_loop_env)[1]


_wt_heredoc = "python3 - <<'E'\nopen('app.py', 'w').write('x = 1')\nE"
_wt_stage("build")
_wt_a = _wt_gate("Edit", {"file_path": os.path.join(_wt_tree, "app.py")}, _wt_tree)[0]
_wt_b = _wt_bash(_wt_heredoc)[0]
_wt_c = _wt_bash("sed -i 's/a/b/' app.py")[0]
_wt_stage("design")
_wt_d = _wt_gate("Edit", {"file_path": os.path.join(_wt_tree, "app.py")}, _wt_tree)[0]
_wt_e = _wt_bash(_wt_heredoc)
_wt_f = _wt_bash("sed -i 's/a/b/' app.py")[0]
_wt_g = _wt_bash("echo hi > notes.md")[0]
_wt_h = _wt_bash("echo hi >> app.py")[0]
_wt_i = _wt_bash("python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" app.py")
_wt_j = _wt_bash("cat f | tee out.py")[0]
_wt_k = _wt_bash("ls -la 2>&1 | grep x; echo done > /dev/null")[0]
_wt_l = _wt_bash("python3 -c \"open('docs/x.txt', 'w').write('x')\"")[0]
_wt_m = _wt_raw(_wt_heredoc)
_wt_n = _wt_raw("python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" app.py")
_wt_loop_off = dict(_loop_env, HOUSE_RULES_LOOP="off")
_, _wt_o, _ = run_hook("commitgate", json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "wt",
                       "cwd": _wt_main, "tool_input": {"command": _wt_heredoc}}), env=_wt_loop_off)
for _t, _ok in (
        ("a worktree reads the main checkout's stage: Build lets its Edit through", _wt_a == "allow"),
        ("a worktree reads the main checkout's stage: Design refuses its Edit", _wt_d == "deny"),
        ("a python heredoc writing a .py file is allowed in Build", _wt_b == "allow"),
        ("#309: a python heredoc writing a .py file in Design goes through, reported as what the lock would have refused",
         _wt_e[0] == "allow" and "report only, #309" in _wt_m and "app.py" in _wt_m and "Design stage" in _wt_m),
        ("#309: sed -i on a .py file is allowed in Build, and in Design too, with a report",
         _wt_c == "allow" and _wt_f == "allow"),
        ("a Bash write to a .md file stays open in Design", _wt_g == "allow"),
        ("#309: a >> redirect into a .py file and tee go through in Design", _wt_h == "allow" and _wt_j == "allow"),
        ("#309: a script whose target path is a variable goes through, and the report says the file couldn't be named",
         _wt_i[0] == "allow" and "a file it can't name" in _wt_n),
        ("redirects to /dev/null and a write into docs/ stay open", _wt_k == "allow" and _wt_l == "allow"),
        ("HOUSE_RULES_LOOP=off leaves script writes alone", "deny" not in _wt_o)):
    _loop_cases.append((_t, _ok))
# -- #265: the stage lives in a committed .claude file and survives a fresh clone ---------------
_wt_stage("build")
_sf = os.path.join(_wt_main, ".claude", "house-rules-loop.json")
_g = lambda *a, cwd=_wt_main: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=cwd,
                                             check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
_g("add", ".claude/house-rules-loop.json"); _g("commit", "-q", "-m", "stage")

_clone = _wt_main + "-clone"
subprocess.run(["git", "clone", "-q", _wt_main, _clone], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
_clone_edit = _wt_gate("Edit", {"file_path": os.path.join(_clone, "app.py")}, _clone)[0]
_wt_stage("design")
_stage_edits = [_wt_gate(t, {"file_path": _sf}, _wt_tree)[0] for t in ("Write", "Edit")]
_wt_stage("build")
_stage_edits += [_wt_gate(t, {"file_path": _sf}, _wt_tree)[0] for t in ("Write", "Edit")]
_stage_sh = _wt_bash("echo '{}' > .claude/house-rules-loop.json")[0]
_leg = tempfile.mkdtemp(prefix="house-rules-legacy-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _leg], check=True)
with open(os.path.join(_leg, ".git", "house-rules-loop.json"), "w") as _f:
    json.dump({"feature": "old", "stage": "design", "skip": False, "approvals": []}, _f)
_leg_a = _wt_gate("Edit", {"file_path": os.path.join(_leg, "app.py")}, _leg)[0]  # Design: deny proves it was read
_leg_p = {"hook_event_name": "UserPromptSubmit", "session_id": "leg", "cwd": _leg, "prompt": "skip design"}
run_hook("scope", json.dumps(_leg_p), env=_loop_env)
_leg_new = os.path.join(_leg, ".claude", "house-rules-loop.json")
for _t, _ok in (
        ("the stage committed in one checkout reads back in a fresh git clone", _clone_edit == "allow"),
        ("a Write and an Edit of the stage file are refused in Build and in Design", _stage_edits == ["deny"] * 4),
        ("a shell redirect into the stage file is refused", _stage_sh == "deny"),
        ("a legacy .git stage file is read (its Design stage refuses the edit)", _leg_a == "deny"),
        ("the next write after a legacy read lands in .claude/", os.path.isfile(_leg_new)
         and json.load(open(_leg_new, encoding="utf-8")).get("feature") == "old")):
    _loop_cases.append((_t, _ok))
# -- #266: the QA edit that got through, and a feature name that keeps "QA stage" ---------------
_qa_state = {"feature": "f", "stage": "build", "skip": False, "approvals": [],
             "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2)],
             "labels": {"o/r#%d" % n: ["Feature", "in progress"] for n in (1, 2)}}
_qa_sf = os.path.join(_wt_main, ".claude", "house-rules-loop.json")
with open(_qa_sf, "w", encoding="utf-8") as _f:
    json.dump(_qa_state, _f)
_qa_env = dict(_loop_env, HOUSE_RULES_LOOP_LABELS_FILE=os.path.join(_FIXTURE_ROOT, "no-such-labels.json"))  # GitHub read fails
for _n in (1, 2):
    run_hook("autosave", json.dumps({"hook_event_name": "PostToolUse", "tool_name": "mcp__github__issue_write",
             "session_id": "qa", "cwd": _wt_tree, "tool_input": {"method": "update", "owner": "o", "repo": "r", "issue_number": _n,
             "labels": ["Feature", "needs review"]}, "tool_response": {"url": "https://github.com/o/r/issues/%d" % _n}}),
             env=_qa_env)
_qa_edits = []
for _cwd in (_wt_main, _wt_tree):
    _p = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "qa", "cwd": _cwd,
          "tool_input": {"file_path": os.path.join(_cwd, "claude-house-rules/plugins/house-rules/templates/handover-page.html")}}
    _qa_edits.append(json.loads(run_hook("commitgate", json.dumps(_p), env=_qa_env)[1] or "{}")
                     .get("hookSpecificOutput", {}).get("permissionDecision", "allow"))
_loop_cases.append(("#266: with every issue swapped to needs review through the GitHub tool, an Edit is refused from the main checkout and a worktree",
                    _qa_edits == ["deny", "deny"]))
_wt_stage("design")
os.makedirs(os.path.join(_wt_main, "docs", "6-decisions"), exist_ok=True)
with open(os.path.join(_wt_main, "docs", "6-decisions", "Decisions.md"), "w", encoding="utf-8") as _f:
    _f.write("design decisions\n")
run_hook("scope", json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "qa", "cwd": _wt_main,
         "prompt": "Design approved: enforced QA stage: 1A 2A 3A 4A"}), env=_loop_env)
_loop_cases.append(('#266: "Design approved: enforced QA stage: 1A 2A 3A 4A" records "enforced QA stage"',
                    json.load(open(_qa_sf, encoding="utf-8")).get("feature") == "enforced QA stage"))
_loop_cases.append(('#266: "Build plan approved: enforced QA stage: 1A 2A" names "enforced QA stage"; a pasted "Build plan: 1A" is still cut',
                    _ig_mod.design_loop._loop_name("enforced QA stage: 1A 2A") == "enforced QA stage"
                    and _ig_mod.design_loop._loop_name("blockers v2 Build plan: 1A 2A") == "blockers v2"))
# -- #226: the long-reply reminder -------------------------------------------------------------
def _long_reply(text):
    # Held for a page: since #283 the retry keeps blocking on the page rule (up to the limit), and past
    # the limit it reports the long-reply note. Either one means the reply was held for a page.
    _, out, _ = run_hook("handover", stop_payload(last_assistant_message=text, cwd=_loop_dir,
                                                  stop_hook_active=True, session_id="verify-long"), env=_loop_env)
    return "show don't tell: this reply is" in out or "- page:" in out


_loop_cases.append(("a 160-word reply with no page link is held for a page (#282)", _long_reply(" ".join(["word"] * 160))))
_loop_cases.append(("a 159-word reply is not (#282)", not _long_reply(" ".join(["word"] * 159))))
_words250 = " ".join(["word"] * 250)
_loop_cases.append(("a 250-word reply with no page link gets the reminder", _long_reply(_words250)))
_loop_cases.append(("a 250-word reply that links a page does not",
                    not _long_reply(_words250 + " https://claude.ai/artifact/abc")))
_loop_cases.append(("a 150-word reply does not", not _long_reply(" ".join(["word"] * 150))))
_loop_cases.append(("words inside a code block are not counted",
                    not _long_reply(" ".join(["word"] * 150) + "\n```\n" + " ".join(["x"] * 200) + "\n```")))
_loop_env["HOUSE_RULES_LOOP"] = "off"
_loop_cases.append(("HOUSE_RULES_LOOP=off also turns the reminder off", not _long_reply(_words250)))
_loop_env["HOUSE_RULES_LOOP"] = "on"

# -- #233: the handover page template -----------------------------------------------------------
_tpl_path = os.path.join(HERE, "..", "templates", "handover-page.html")
_tpl = read(_tpl_path) if os.path.isfile(_tpl_path) else ""
_tpl_missing = [m for m in ('data-part="short"', 'data-part="changes"', 'data-part="choices"', 'data-part="wrapup"',
                            "Copy my reply", 'class="owntext"', "const PAGE = {", "What you need to do",
                            '<div class="flow">', "<small>What exists today</small>", "<small>How it impacts you</small>",
                            '<div class="files">',
                            # #254: picture slots, the tap-to-enlarge overlay and the before-and-after slider
                            'data-pic="', "const picOf", "lightbox", 'type="range"')
                if m not in _tpl]
_loop_cases.append(("the handover template has its four parts, the own-answer box, the copy-reply, the New-item flow and the picture slots",
                    bool(_tpl) and not _tpl_missing))
_sdt_detail = read(os.path.join(DETAIL_DIR, "show-dont-tell.md"))
_loop_cases.append(("the rule names the template and its four parts",
                    all(w in _sdt_detail for w in ("templates/handover-page.html", "In short", "Changes", "Choices", "Wrap-up"))))

for _t, _ok in _loop_cases:
    report("PASS" if _ok else "FAIL", "design loop: " + _t)

# --- #362: the closable record - a QA pass saves the feature's issues, a merge stamps them ------
_cl_dir = tempfile.mkdtemp(prefix="house-rules-closable-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _cl_dir], check=True)
_cl_file = os.path.join(_cl_dir, ".claude", "house-rules-loop.json")
_cl_env = dict(_loop_env, HOUSE_RULES_LOOP="on")


def _cl_set(state):
    os.makedirs(os.path.join(_cl_dir, ".claude"), exist_ok=True)
    with open(_cl_file, "w", encoding="utf-8") as f:
        json.dump(dict({"skip": False, "approvals": [], "issues": []}, **state), f)
    os.makedirs(os.path.join(_cl_dir, "docs", "6-decisions"), exist_ok=True)
    with open(os.path.join(_cl_dir, "docs", "6-decisions", "Decisions.md"), "a", encoding="utf-8") as f:
        f.write("an entry written at %r\n" % time.time())


def _cl_state():
    try:
        return json.load(open(_cl_file, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _cl_say(prompt):
    p = {"hook_event_name": "UserPromptSubmit", "session_id": "cl", "cwd": _cl_dir, "prompt": prompt}
    run_hook("scope", json.dumps(p), env=_cl_env)


def _cl_merge(tool, tool_input, response, env=None):
    p = {"hook_event_name": "PostToolUse", "tool_name": tool, "session_id": "cl", "cwd": _cl_dir,
         "tool_input": tool_input, "tool_response": response}
    return run_hook("closablemerge", json.dumps(p), env=env or _cl_env)[1]


_cl_issues = [{"repo": "o/r", "number": 7, "labelled": True}, {"repo": "o/r", "number": 8, "labelled": True}]
_cl_open = {"feature": "f", "issues": [], "qa_at": 1, "qa": "QA passed: f", "merged_pr": None}
_cl_cases = []
_cl_set({"feature": "alpha", "stage": "qa", "issues": _cl_issues})
_cl_say("QA failed: alpha")
_cl_cases.append(("a QA failure creates no closable entry", not _cl_state().get("closable")))
_cl_set({"feature": "alpha", "stage": "qa", "issues": _cl_issues})
_cl_say("QA passed: alpha")
_c = _cl_state().get("closable") or [{}]
_cl_cases.append(("a QA pass saves a closable entry holding the feature's issues",
                  len(_c) == 1 and _c[0].get("feature") == "alpha" and _c[0].get("qa") == "QA passed: alpha"
                  and _c[0].get("issues") == [{"repo": "o/r", "number": 7}, {"repo": "o/r", "number": 8}]
                  and _c[0].get("merged_pr") is None and isinstance(_c[0].get("qa_at"), int)))
_cl_say("Design approved: beta")
_cl_cases.append(("the closable entry survives a following Design approved for another feature",
                  _cl_state().get("stage") == "plan" and _cl_state().get("issues") == []
                  and len(_cl_state().get("closable") or []) == 1))
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_cl_merge("mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pullNumber": 12}, {"merged": False})
_cl_merge("Bash", {"command": "gh pr merge 13 --squash"}, {"stdout": "", "stderr": "boom", "exit_code": 1})
_cl_cases.append(("a merge with merged false, or a failing gh pr merge, stamps nothing",
                  _cl_state()["closable"][0]["merged_pr"] is None))
_cl_merge("mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pullNumber": 12}, {"merged": True})
_m = _cl_state()["closable"][0]["merged_pr"] or {}
_cl_cases.append(("an MCP merge payload with merged true stamps an unstamped entry",
                  _m.get("repo") == "o/r" and _m.get("number") == 12 and isinstance(_m.get("at"), int)))
_cl_merge("Bash", {"command": "gh pr merge 99 --squash"}, {"stdout": "", "exit_code": 0})
_cl_cases.append(("an already-stamped entry is not restamped", _cl_state()["closable"][0]["merged_pr"]["number"] == 12))
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_cl_merge("Bash", {"command": "gh pr merge 14 --squash"}, {"stdout": "", "exit_code": 0})
_cl_cases.append(("a gh pr merge Bash payload stamps an unstamped entry",
                  (_cl_state()["closable"][0]["merged_pr"] or {}).get("number") == 14))
# The real Bash result may carry no exit code: then only gh's own success line counts as a merge.
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_cl_merge("Bash", {"command": "gh pr merge 16 --squash"}, {"stdout": "", "stderr": ""})
_cl_merge("Bash", {"command": "gh pr merge 16 --auto"}, {"stdout": "", "stderr": "! Pull request #16 will be automatically merged"})
_cl_cases.append(("with no exit code, a gh pr merge with no success line, or an auto-merge, stamps nothing",
                  _cl_state()["closable"][0]["merged_pr"] is None))
_cl_merge("Bash", {"command": "gh pr merge 16 --squash"}, {"stdout": "", "stderr": "✓ Squashed and merged pull request #16 (title)"})
_cl_cases.append(("with no exit code, gh's success line stamps the entry",
                  (_cl_state()["closable"][0]["merged_pr"] or {}).get("number") == 16))
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_o = _cl_merge("Bash", {"command": "gh pr merge 15"}, {"exit_code": 0}, env=dict(_cl_env, HOUSE_RULES_LOOP="off"))
_cl_cases.append(("HOUSE_RULES_LOOP=off stamps nothing and says so",
                  _cl_state()["closable"][0]["merged_pr"] is None and "HOUSE_RULES_LOOP=off" in _o))
# #374: the real GitHub tool replies are a list holding one text block (recorded 2026-10-21).
_w_merge = [{"type": "text", "text": "{\"sha\":\"ed36dc31e8907157117de6a72f48db31de606601\",\"merged\":true,\"message\":\"Pull Request successfully merged\"}"}]
_w_nomerge = [{"type": "text", "text": "{\"sha\":\"ed36dc31e8907157117de6a72f48db31de606601\",\"merged\":false,\"message\":\"Pull Request not mergeable\"}"}]
_w_ti = {"owner": "Ajw2003", "repo": "AjsClaudeCodeTools", "pullNumber": 373}
_cl_set({"stage": "done", "closable": [dict(_cl_open)]})
_cl_merge("mcp__github__merge_pull_request", _w_ti, _w_nomerge)
_cl_cases.append(("a wrapped GitHub tool merge reply with merged false stamps nothing",
                  _cl_state()["closable"][0]["merged_pr"] is None))
_cl_merge("mcp__github__merge_pull_request", _w_ti, _w_merge)
_m = _cl_state()["closable"][0]["merged_pr"] or {}
_cl_cases.append(("a wrapped GitHub tool merge reply stamps a waiting closable entry",
                  _m.get("repo") == "Ajw2003/AjsClaudeCodeTools" and _m.get("number") == 373))
for _t, _ok in _cl_cases:
    report("PASS" if _ok else "FAIL", "closable record: " + _t)

# --- #363: the close guard - an issue closes only on recorded QA + merge evidence or an approved list ---
def _cg_gh(cmd, env=None):
    p = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "cg", "cwd": _cl_dir,
         "tool_input": {"command": cmd}}
    return run_hook("guard", json.dumps(p), env=env or _iss_env())[1]


def _cg_mcp(ti, env=None):
    p = {"hook_event_name": "PreToolUse", "tool_name": "mcp__github__issue_write", "session_id": "cg",
         "cwd": _cl_dir, "tool_input": ti}
    return run_hook("guardgithub", json.dumps(p), env=env or _iss_env())[1]


def _cg_ctx(o):
    try:
        return json.loads(o)["hookSpecificOutput"].get("additionalContext", "")
    except Exception:
        return ""


_cg_mrg = {"repo": "o/r", "number": 20, "at": 1}
_cg_ready = {"feature": "f", "issues": [{"repo": "o/r", "number": 7}], "qa_at": 1, "qa": "QA passed: f", "merged_pr": _cg_mrg}
_cg_nomerge = dict(_cg_ready, merged_pr=None)
_cg_cases = []
_cg_mc = {"method": "update", "owner": "o", "repo": "r", "issue_number": 7, "state": "closed", "state_reason": "completed"}
_cl_set({"stage": "done", "closable": [dict(_cg_ready, issues=[dict(i) for i in _cg_ready["issues"]])]})
_o = _cg_gh("gh issue close 7 -R o/r")
_cg_cases.append(("gh close with a QA pass and a merge is allowed, with the comment/label instruction",
                  _iss_decision(_o) == "allow" and "QA passed: f" in _cg_ctx(_o) and "o/r#20" in _cg_ctx(_o)
                  and "AjsAgent completed this" in _cg_ctx(_o) and "in%20progress" in _cg_ctx(_o)))
_cg_cases.append(("an allowed close removes nothing in PreToolUse", bool(_cl_state().get("closable"))))
def _cg_post(tool, ti, resp):
    p = {"hook_event_name": "PostToolUse", "tool_name": tool, "session_id": "cg", "cwd": _cl_dir,
         "tool_input": ti, "tool_response": resp}
    return run_hook("closablemerge", json.dumps(p), env=_cl_env)[1]
_cg_post("Bash", {"command": "gh issue close 7 -R o/r"}, {"stdout": "", "stderr": "boom", "exit_code": 1})
_cg_o = _cg_gh("gh issue close 7 -R o/r")
_cg_cases.append(("a failed gh close keeps the evidence and a retry is still allowed",
                  bool(_cl_state().get("closable")) and _iss_decision(_cg_o) == "allow"))
_cg_post("Bash", {"command": "gh issue close 7 -R o/r"}, {"stdout": "", "stderr": "", "exit_code": 0})
_cg_cases.append(("a successful gh close removes the issue and its now-empty closable entry", not _cl_state().get("closable")))
_cl_set({"stage": "done", "closable": [dict(_cg_nomerge)]})
_o = _cg_gh("gh issue close 7 -R o/r")
_cg_cases.append(("gh close with a QA pass but no merge is refused, naming the missing merge",
                  _iss_decision(_o) == "deny" and "passed QA but no merged pull request is recorded since" in _iss_reason(_o)
                  and bool(_cl_state().get("closable"))))
_cl_set({"stage": "done"})
_o = _cg_gh("gh issue close 7")
_cg_cases.append(("gh close with nothing recorded is refused, naming the missing QA pass",
                  _iss_decision(_o) == "deny" and "no QA pass is recorded for a feature that holds #7" in _iss_reason(_o)))
_cl_set({"stage": "done", "closable": [dict(_cg_ready, issues=[{"repo": "o/r", "number": 7}, {"repo": "o/r", "number": 8}])]})
_o = _cg_mcp(_cg_mc)
_cg_cases.append(("MCP issue_write close with a QA pass and a merge is allowed",
                  _iss_decision(_o) == "allow" and "AjsAgent completed this" in _cg_ctx(_o)))
_cg_post("mcp__github__issue_write", _cg_mc, {"error": "forbidden"})
_cg_cases.append(("a failed MCP close keeps the evidence", len(_cl_state()["closable"][0]["issues"]) == 2))
_cg_post("mcp__github__issue_write", _cg_mc, {"state": "closed", "url": "https://github.com/o/r/issues/7"})
_cg_cases.append(("a successful MCP close removes that issue; the entry keeps the other one",
                  [i["number"] for i in _cl_state()["closable"][0]["issues"]] == [8]))
_cl_set({"stage": "done", "closable": [dict(_cg_nomerge)]})
_o = _cg_mcp(_cg_mc)
_cg_cases.append(("MCP issue_write close with a QA pass but no merge is refused", _iss_decision(_o) == "deny" and "no merged pull request" in _iss_reason(_o)))
_cl_set({"stage": "done"})
_o = _cg_mcp(_cg_mc)
_cg_cases.append(("MCP issue_write close with nothing recorded is refused", _iss_decision(_o) == "deny" and "no QA pass is recorded" in _iss_reason(_o)))
_cg_cases.append(("MCP issue_write that is not a close is not checked",
                  _iss_decision(_cg_mcp({"method": "update", "owner": "o", "repo": "r", "issue_number": 7, "state": "open"})) is None))
_o = _cg_mcp(dict(_cg_mc, state_reason="not_planned"))
_cg_cases.append(("a not-planned MCP close without a sweep entry is refused",
                  _iss_decision(_o) == "deny" and "a not-planned close needs an approved sweep or a named list" in _iss_reason(_o)))
_cl_set({"stage": "done", "closable": [dict(_cg_ready)]})
_o = _cg_gh("gh issue close 7 -R o/r --reason 'not planned'")
_cg_cases.append(("a not-planned gh close is refused even for a QA-and-merge issue", _iss_decision(_o) == "deny" and "not-planned" in _iss_reason(_o)))
_cl_set({"stage": "done", "sweep": [{"repo": "o/r", "number": 9, "action": "not_planned", "replaced_by": 306}]})
_o = _cg_gh("gh issue close 9 -R o/r --reason 'not planned'")
_cg_cases.append(("a not-planned gh close is allowed with a matching sweep entry, which is then removed",
                  _iss_decision(_o) == "allow" and "#306" in _cg_ctx(_o) and bool(_cl_state().get("sweep"))))
_cg_post("Bash", {"command": "gh issue close 9 -R o/r --reason 'not planned'"}, {"stdout": "Closed issue #9", "stderr": ""})
_cg_cases.append(("a close with no exit code is proven by gh's success line, which removes the sweep entry",
                  not _cl_state().get("sweep")))
_cl_set({"stage": "done", "sweep": [{"repo": "o/r", "number": 9, "action": "not_planned", "replaced_by": 306}]})
_o = _cg_gh("gh issue close 9 -R o/r")
_cg_cases.append(("a completed close is refused when the sweep entry says not_planned", _iss_decision(_o) == "deny"))
_cl_set({"stage": "done", "sweep": [{"repo": "o/r", "number": 9, "action": "completed", "replaced_by": None}]})
_o = _cg_mcp(dict(_cg_mc, issue_number=9, state_reason=None))
_cg_cases.append(("an MCP close with no reason is allowed for a sweep completed entry", _iss_decision(_o) == "allow" and bool(_cl_state().get("sweep"))))
_cg_post("Bash", {"command": "gh issue close 9 -R o/r"}, {"stdout": "", "stderr": ""})
_cg_cases.append(("with no exit code and no success line, nothing is removed", bool(_cl_state().get("sweep"))))
_cl_set({"stage": "done", "closable": [dict(_cg_ready)]})
_o1 = _cg_gh("gh issue close --comment done")
_o2 = _cg_mcp({"method": "update", "owner": "o", "repo": "r", "state": "closed"})
_cg_cases.append(("a close with no issue number is refused, saying so, on both routes",
                  all(_iss_decision(x) == "deny" and "could not tell which issue" in _iss_reason(x) for x in (_o1, _o2))
                  and bool(_cl_state().get("closable"))))
_cl_set({"stage": "done"})
_o = _cg_gh("gh issue close 7", env=_iss_env(HOUSE_RULES_ISSUES="off"))
_cg_cases.append(("HOUSE_RULES_ISSUES=off keeps its old behaviour: the close guard does not run on either route",
                  "close guard" not in _o and "refused" not in _o
                  and _cg_mcp(_cg_mc, env=_iss_env(HOUSE_RULES_ISSUES="off")).find("close guard") < 0))
# #374: wrapped replies from the GitHub tool (recorded 2026-10-21).
_w_close = [{"type": "text", "text": "{\"id\":\"5952121313\",\"url\":\"https://github.com/Ajw2003/AjsClaudeCodeTools/issues/371\"}"}]
_w_err = "Error: failed to create issue: Something went wrong while executing your query"
_w_mc = {"method": "update", "owner": "Ajw2003", "repo": "AjsClaudeCodeTools", "issue_number": 371, "state": "closed", "state_reason": "completed"}
_w_row = {"repo": "Ajw2003/AjsClaudeCodeTools", "number": 371, "action": "completed", "replaced_by": None}
_cl_set({"stage": "done", "closable": [dict(_cg_ready, issues=[{"repo": "Ajw2003/AjsClaudeCodeTools", "number": 371}, {"repo": "o/r", "number": 8}])]})
_cg_post("mcp__github__issue_write", _w_mc, _w_err)
_cg_cases.append(("an error string reply for a close removes nothing from the closable entry",
                  len(_cl_state()["closable"][0]["issues"]) == 2))
_cg_post("mcp__github__issue_write", _w_mc, _w_close)
_cg_cases.append(("a wrapped GitHub tool close reply removes the issue from its closable entry",
                  [i["number"] for i in _cl_state()["closable"][0]["issues"]] == [8]))
_cl_set({"stage": "done", "sweep": [dict(_w_row), dict(_w_row, number=372)]})
_cg_post("mcp__github__issue_write", _w_mc, _w_err)
_cg_cases.append(("an error string reply for a close removes nothing from the sweep list", len(_cl_state()["sweep"]) == 2))
_cg_post("mcp__github__issue_write", _w_mc, _w_close)
_cg_cases.append(("a wrapped GitHub tool close reply removes the issue from the sweep list",
                  [r["number"] for r in _cl_state()["sweep"]] == [372]))
for _t, _ok in _cg_cases:
    report("PASS" if _ok else "FAIL", "close guard: " + _t)

# --- #364: sweep approvals and named not-planned lists feed the close guard ---------------------
_sw_cases = []
_sw_mp = os.path.join(HERE, "make_page.py")
os.makedirs(os.path.join(_cl_dir, "docs"), exist_ok=True)
with open(os.path.join(_cl_dir, "docs", "page-style.json"), "w", encoding="utf-8") as _f:
    json.dump({"use": "defaults"}, _f)


def _sw_say(prompt):
    p = {"hook_event_name": "UserPromptSubmit", "session_id": "sw", "cwd": _cl_dir, "prompt": prompt}
    return run_hook("scope", json.dumps(p), env=_cl_env)[1]


def _sw_build(name, rows):
    page = {"title": "Sweep " + name, "eyebrow": "e", "approval": "x",
            "short": {"lead": "Plain.", "hint": "h", "key": [["We", ""]], "items": [["bulb", "Idea", "The idea", "", "c", "r"]]},
            "changes": [["new", "A thing", "One line.", None, "Detail.", None, None]],
            "wrapup": {"summary": "s", "changing": "c", "blocking": "b", "next": "n", "todo": ["t"]},
            "sweep": rows}
    path = os.path.join(_cl_dir, name + ".page.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(page, f)
    r = subprocess.run([sys.executable, _sw_mp, "build", path, "--project", _cl_dir], capture_output=True,
                       text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def _sw_row(n, action, by=None):
    return {"repo": "o/r", "number": n, "title": "Issue %d" % n, "action": action, "replaced_by": by,
            "evidence": "Evidence for %d." % n}


_sw_rows = [_sw_row(301, "completed"), _sw_row(302, "not_planned", 306), _sw_row(303, "keep"), _sw_row(304, "completed")]
_cl_set({"stage": "done"})
_rc, _o = _sw_build("sw1", _sw_rows)
_sw_pg = None
try:
    _m = re.search(r"^const PAGE = (\{.*?^\});$", open(os.path.join(_cl_dir, "docs", "plans", "sw1.html"), encoding="utf-8").read(),
                   re.S | re.M)
    _sw_pg = json.loads(_m.group(1))
except (OSError, AttributeError, ValueError):
    _sw_pg = {}
_sw_cases.append(("a sweep page builds, shows each row's evidence, and records sweep_proposed without the keep row",
                  _rc == 0 and _sw_pg.get("approval") == "Sweep approved: issues"
                  and sum("Evidence for" in str(c) for c in _sw_pg.get("changes", [])) == 4
                  and [x["number"] for x in _cl_state().get("sweep_proposed", [])] == [301, 302, 304]
                  and _cl_state()["sweep_proposed"][1] == {"repo": "o/r", "number": 302, "action": "not_planned", "replaced_by": 306}))
_rc, _o = _sw_build("sw2", [_sw_row(5, "not_planned")])
_sw_cases.append(("make_page refuses a not_planned sweep row with no replaced_by",
                  _rc == 2 and "needs replaced_by" in _o))
_rc, _o = _sw_build("sw3", [_sw_row(5, "maybe")])
_sw_cases.append(("make_page refuses a sweep action that is not completed, not_planned or keep",
                  _rc == 2 and "action must be completed, not_planned or keep" in _o))
_cl_set({"stage": "done", "sweep_proposed": [{"repo": "o/r", "number": 301, "action": "completed", "replaced_by": None},
                                            {"repo": "o/r", "number": 302, "action": "not_planned", "replaced_by": 306}]})
_sw_n = _sw_say("Sweep approved: issues")
_sw_cases.append(("Sweep approved: issues moves the proposed rows into sweep and clears sweep_proposed",
                  [x["number"] for x in _cl_state().get("sweep", [])] == [301, 302] and "sweep_proposed" not in _cl_state()
                  and "Recorded 2 sweep row(s) for the close guard." in _sw_n))
_o1 = _cg_gh("gh issue close 301 -R o/r")
_o2 = _cg_gh("gh issue close 302 -R o/r --reason \"not planned\" --comment \"replaced by #306\"")
_o3 = _cg_gh("gh issue close 302 -R o/r")
_o4 = _cg_gh("gh issue close 999 -R o/r")
_sw_cases.append(("the guard allows the approved closes with the matching action and refuses a wrong action",
                  _iss_decision(_o1) == "allow" and _iss_decision(_o2) == "allow" and _iss_decision(_o3) == "deny"))
_sw_cases.append(("an issue on neither list is still refused", _iss_decision(_o4) == "deny"))
_cl_set({"stage": "done", "sweep_proposed": [{"repo": "o/r", "number": 301, "action": "completed", "replaced_by": None},
                                            {"repo": "o/r", "number": 302, "action": "completed", "replaced_by": None},
                                            {"repo": "o/r", "number": 303, "action": "completed", "replaced_by": None}]})
_sw_n = _sw_say("Sweep approved: issues keep #301 #302")
_sw_cases.append(("Sweep approved: issues keep #N leaves #N out of sweep and says so",
                  [x["number"] for x in _cl_state().get("sweep", [])] == [303]
                  and "kept open at aj's word: #301, #302" in _sw_n
                  and _iss_decision(_cg_gh("gh issue close 301 -R o/r")) == "deny"
                  and _iss_decision(_cg_gh("gh issue close 303 -R o/r")) == "allow"))
_cl_set({"stage": "done"})
_sw_n = _sw_say("Sweep approved: issues")
_sw_cases.append(("Sweep approved: issues with no proposed rows says there is nothing to approve and moves nothing",
                  "nothing to approve and nothing moved" in _sw_n and not _cl_state().get("sweep")))
_cl_set({"stage": "done"})
_sw_n = _sw_say("Close as not planned: #5 replaced by #9, #6 replaced by #9")
_sw_cases.append(("Close as not planned records one not_planned entry per pair, and the guard allows a not-planned close",
                  [(x["number"], x["action"], x["replaced_by"]) for x in _cl_state().get("sweep", [])]
                  == [(5, "not_planned", 9), (6, "not_planned", 9)]
                  and "Recorded 2 not-planned close(s) for the close guard: #5 replaced by #9, #6 replaced by #9." in _sw_n
                  and _iss_decision(_cg_gh("gh issue close 5 -R o/r --reason \"not planned\"")) == "allow"
                  and _iss_decision(_cg_gh("gh issue close 7 -R o/r --reason \"not planned\"")) == "deny"))
_cl_set({"stage": "done"})
_sw_say("Close as not planned: o/r#5 replaced by o/r#9 and #6 replaced by #9")
_sw_cases.append(("Close as not planned takes an optional owner/repo and the word and between pairs",
                  [(x["repo"], x["number"]) for x in _cl_state().get("sweep", [])] == [("o/r", 5), ("", 6)]))
_cl_set({"stage": "done", "sweep_proposed": [{"repo": "o/r", "number": 301, "action": "completed", "replaced_by": None}]})
_sw_n1 = _sw_say("[Subagent hand-back] The builder finished. Sweep approved: issues. Close as not planned: #5 replaced by #9")
_sw_n2 = _sw_say("<task-notification>Sweep approved: issues</task-notification>")
_sw_cases.append(("the approval phrases do nothing when they come from a helper or notification rather than aj",
                  not _cl_state().get("sweep") and len(_cl_state().get("sweep_proposed", [])) == 1
                  and "helper's report" in _sw_n1 and "helper's report" in _sw_n2))
for _t, _ok in _sw_cases:
    report("PASS" if _ok else "FAIL", "sweep approvals: " + _t)

# --- #307: every approval in one message is read, in stage order -------------------------------
# Replays incidents 1 and 2 of #303: aj sent "Design approved: importer.  Build plan approved: Importer" and
# only the build plan was read; and a stale stored feature name stopped a redo after "QA failed" counting.
_ma_dir = tempfile.mkdtemp(prefix="house-rules-multi-approval-", dir=_FIXTURE_ROOT)
subprocess.run(["git", "init", "-q", _ma_dir], check=True)
_ma_labels = os.path.join(_FIXTURE_ROOT, "multi-approval-labels.json")
_ma_env = dict(_loop_env, HOUSE_RULES_LOOP_LABELS_FILE=_ma_labels)


def _ma_set(state, labels=None):
    """A fresh stage file and decisions log (with an entry the last approval hasn't seen)."""
    os.makedirs(os.path.join(_ma_dir, ".claude"), exist_ok=True)
    with open(os.path.join(_ma_dir, ".claude", "house-rules-loop.json"), "w", encoding="utf-8") as f:
        json.dump(dict({"skip": False, "approvals": [], "issues": []}, **state), f)
    os.makedirs(os.path.join(_ma_dir, "docs", "6-decisions"), exist_ok=True)
    with open(os.path.join(_ma_dir, "docs", "6-decisions", "Decisions.md"), "a", encoding="utf-8") as f:
        f.write("an entry written at %r\n" % time.time())
    with open(_ma_labels, "w", encoding="utf-8") as f:
        json.dump(labels or {}, f)


def _ma_say(prompt):
    p = {"hook_event_name": "UserPromptSubmit", "session_id": "multi", "cwd": _ma_dir, "prompt": prompt}
    _, out, _ = run_hook("scope", json.dumps(p), env=_ma_env)
    try:
        note = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        note = ""
    state = json.load(open(os.path.join(_ma_dir, ".claude", "house-rules-loop.json"), encoding="utf-8"))
    return note, state


_ma_set({"feature": "Label setup", "stage": "design"})
_n, _s = _ma_say("Design approved: importer.  Build plan approved: Importer")
report("PASS" if (_s["stage"] == "plan" and _s.get("feature") == "importer"
                  and 'Design approved: importer' in _n and "Build plan approved: Importer" in _n) else "FAIL",
       "design loop (#307): a design and a build-plan approval in one message - the design moves the stage, "
       "and the build plan gets its own refusal")
if _s["stage"] != "plan":
    print("          stage %r, feature %r, note %r" % (_s["stage"], _s.get("feature"), _n[:300]))

_ma_set({"feature": "Label setup", "stage": "design", "redo": True,
         "approvals": [{"stage": "QA failed", "name": "Importer", "at": 1}],
         "issues": [{"repo": "o/r", "number": 7, "labelled": True}]},
        {"o/r#7": ["Feature", "AjsAgent created this", "in progress"]})
_n, _s = _ma_say("Design approved: Importer")
report("PASS" if (_s["stage"] == "plan" and _s.get("feature") == "Importer"
                  and [i.get("number") for i in _s.get("issues", [])] == [7]) else "FAIL",
       "design loop (#307): after \"QA failed: Importer\", \"Design approved: Importer\" is the redo even "
       "when the stored feature name is stale - its issues are kept")
if _s.get("issues") != [{"repo": "o/r", "number": 7, "labelled": True}]:
    print("          feature %r, issues %r, note %r" % (_s.get("feature"), _s.get("issues"), _n[:300]))

# #327: an unchanged decisions log no longer refuses; the approval counts and the note asks for the entry.
_ma_set({"feature": "demo", "stage": "plan",
         "issues": [{"repo": "o/r", "number": n, "labelled": True} for n in (1, 2, 3)]},
        {"o/r#%d" % n: ["Feature", "AjsAgent created this", "in progress"] for n in (1, 2, 3)})
_ma_log = os.path.join(_ma_dir, "docs", "6-decisions", "Decisions.md")
_ma_st = os.path.join(_ma_dir, ".claude", "house-rules-loop.json")
_ma_d = json.load(open(_ma_st, encoding="utf-8"))
_ma_d["log_mark"] = hashlib.sha256(open(_ma_log, "rb").read()).hexdigest()
json.dump(_ma_d, open(_ma_st, "w", encoding="utf-8"))
_n, _s = _ma_say("Build plan approved: demo")
report("PASS" if (_s["stage"] == "build" and "docs/6-decisions/Decisions.md" in _n and "nothing moved" not in _n
                  and _s.get("log_mark") == _ma_d["log_mark"] and "log_ask" not in _s) else "FAIL",
       "design loop (#327): \"Build plan approved: <feature>\" with an unchanged decisions log moves Plan to Build "
       "on the first message, the note names docs/6-decisions/Decisions.md, and the log mark is kept")
if _s["stage"] != "build":
    print("          stage %r, note %r" % (_s["stage"], _n[:300]))

_ma_set({"feature": "", "stage": "design"})
_n, _s = _ma_say("Design approved: blockers")
report("PASS" if (_s["stage"] == "plan" and _s.get("feature") == "blockers"
                  and 'Design loop: aj wrote "Design approved: blockers". The stage is now Plan.' in _n)
       else "FAIL", "design loop (#307): a single design approval behaves as before")

# --- #308: only issues made in the stage file's own repo count toward its feature ---------------
# Replays incident 3 of #303: issues opened in another repo were recorded as this feature's issues.
subprocess.run(["git", "-C", _ma_dir, "remote", "add", "origin", "https://github.com/me/own.git"], check=True)
_ma_set({"feature": "Importer", "stage": "plan"})


def _ma_issue(url):
    p = {"hook_event_name": "PostToolUse", "tool_name": "mcp__github__issue_write", "session_id": "multi",
         "cwd": _ma_dir, "tool_input": {"method": "create", "title": "t", "labels": ["AjsAgent created this"]},
         "tool_response": {"url": url}}
    out = run_hook("autosave", json.dumps(p), env=_ma_env)[1]
    state = json.load(open(os.path.join(_ma_dir, ".claude", "house-rules-loop.json"), encoding="utf-8"))
    return out, [(i.get("repo"), i.get("number")) for i in state.get("issues", [])]


_out, _rec = _ma_issue("https://github.com/Ajw2003/AjsClaudeCodeTools/issues/301")
report("PASS" if (_rec == [] and "made in another repo" in _out) else "FAIL",
       "design loop (#308): an issue made in another repo isn't recorded for this feature, and a note says so")
if _rec:
    print("          recorded %r, output %r" % (_rec, _out[:300]))
_out, _rec = _ma_issue("https://github.com/me/own/issues/12")
report("PASS" if _rec == [("me/own", 12)] else "FAIL",
       "design loop (#308): an issue made in the stage file's own repo is recorded as before")

# --- label setup: create only the missing house labels (#275) ---------------------------------
import labels as _lb
_lb_dir = tempfile.mkdtemp(prefix="house-rules-labels-", dir=_FIXTURE_ROOT)
_lb_file = os.path.join(_lb_dir, "labels.json")
_lb_repo = "owner/repo"
_lb_house = [l[0] for l in _lb.HOUSE_LABELS]
_lb_cases = []


def _lb_run(initial):
    """Run ensure_labels against the stand-in file; (result, file contents after)."""
    if initial is not None:
        with open(_lb_file, "w", encoding="utf-8") as f:
            f.write(initial)
    elif os.path.exists(_lb_file):
        os.remove(_lb_file)
    os.environ[_lb.REPO_LABELS_FILE_ENV] = _lb_file
    try:
        res = _lb.ensure_labels(_lb_repo)
    finally:
        del os.environ[_lb.REPO_LABELS_FILE_ENV]
    after = open(_lb_file, encoding="utf-8").read() if os.path.exists(_lb_file) else None
    return res, after


_r, _a = _lb_run("{}")
_lb_cases.append(("all three missing: all three created and written to the file",
                  _r["created"] == _lb_house and not _r["present"] and json.loads(_a)[_lb_repo] == _lb_house))
_r, _a = _lb_run(json.dumps({_lb_repo: ["bug", "in progress", "needs review"]}))
_lb_cases.append(("one missing: only it is created", _r["created"] == ["AjsAgent created this"]
                  and sorted(_r["present"]) == ["in progress", "needs review"]))
_lb_all = json.dumps({_lb_repo: ["bug"] + _lb_house}, indent=3)
_r, _a = _lb_run(_lb_all)
_lb_cases.append(("all present: nothing created and the file is unchanged byte for byte",
                  not _r["created"] and not _r["failed"] and not _r["error"] and _a == _lb_all
                  and _lb.summary_note(_r, _lb_repo) == ""))
_r, _a = _lb_run(json.dumps({_lb_repo: ["In Progress", "needs review", "AjsAgent created this"]}))
_lb_cases.append(("a label in a different case counts as present, not created",
                  not _r["created"] and "in progress" in _r["present"]))
_r, _a = _lb_run(None)
_lb_cases.append(("stand-in file missing: error set, nothing raised, the note names the failure",
                  bool(_r["error"]) and not _r["created"] and _r["error"] in _lb.summary_note(_r, _lb_repo)
                  and "could not check" in _lb.summary_note(_r, _lb_repo)))
_lb_empty = tempfile.mkdtemp(prefix="house-rules-nogh-", dir=_FIXTURE_ROOT)
_lb_env = {k: v for k, v in os.environ.items() if k != _lb.REPO_LABELS_FILE_ENV}
_lb_env["PATH"] = _lb_empty
_lb_p = subprocess.run([sys.executable, "-c",
                        "import sys,json; sys.path.insert(0, %r); import labels; "
                        "print(json.dumps(labels.ensure_labels('owner/repo')))" % HERE],
                       capture_output=True, text=True, env=_lb_env)
try:
    _lb_gh = json.loads(_lb_p.stdout)["error"]
except (ValueError, KeyError):
    _lb_gh = ""
_lb_cases.append(("no stand-in and gh not on PATH: error says gh is not installed", "gh is not installed" in _lb_gh))
_lb_cfg = os.path.join(_lb_dir, "gitdir")
os.makedirs(_lb_cfg, exist_ok=True)


def _lb_repo_for(url):
    with open(os.path.join(_lb_cfg, "config"), "w", encoding="utf-8") as f:
        f.write('[remote "origin"]\n\turl = %s\n' % url)
    return _lb.repo_from_git(_lb_cfg)


_lb_cases.append(("repo_from_git reads https, ssh and cloud-proxy URLs",
                  _lb_repo_for("https://github.com/o/r.git")[0] == "o/r"
                  and _lb_repo_for("https://github.com/o/r")[0] == "o/r"
                  and _lb_repo_for("git@github.com:o/r.git")[0] == "o/r"
                  and _lb_repo_for("http://local_proxy@127.0.0.1:1234/git/o/r")[0] == "o/r"))
_lb_nr = _lb_repo_for("https://gitlab.com/o/r.git")
_lb_cases.append(("repo_from_git gives None and a note for a non-GitHub URL", _lb_nr[0] is None and bool(_lb_nr[1])))
_lb_src = open(os.path.join(HERE, "labels.py"), encoding="utf-8").read()
_lb_cases.append(("labels.py has no --force, -X DELETE, PATCH or label edit",
                  not any(w in _lb_src for w in ("--" + "force", "-X " + "DELETE", "PA" + "TCH", "label " + "edit"))))

# #277: the command's script, run as /house-rules:labels runs it.
def _lb_cli(*args, cwd=None):
    with open(_lb_file, "w", encoding="utf-8") as f:
        json.dump({_lb_repo: ["bug", "needs review"]}, f)
    p = subprocess.run([sys.executable, os.path.join(HERE, "labels.py")] + list(args), capture_output=True, text=True,
                       cwd=cwd or _lb_dir, env=dict(os.environ, **{_lb.REPO_LABELS_FILE_ENV: _lb_file}))
    return p.returncode, p.stdout


_c, _o = _lb_cli(_lb_repo)
_lb_cases.append(("labels.py owner/repo creates the two missing labels, lists the one already there, exit 0 (#277)",
                  _c == 0 and "created         AjsAgent created this" in _o and "created         in progress" in _o
                  and "already there   needs review" in _o))
_c, _o = _lb_cli("not a repo")
_lb_cases.append(("labels.py with a bad repo name exits 2 and says what a name looks like (#277)",
                  _c == 2 and "owner/repo" in _o))
_lb_git = os.path.join(_lb_dir, "clone")
os.makedirs(_lb_git, exist_ok=True)
subprocess.run(["git", "init", "-q", _lb_git], check=True)
subprocess.run(["git", "-C", _lb_git, "remote", "add", "origin", "https://github.com/%s.git" % _lb_repo], check=True)
_c, _o = _lb_cli(cwd=_lb_git)
_lb_cases.append(("labels.py with no argument works on the folder's GitHub remote (#277)",
                  _c == 0 and ("labels on %s:" % _lb_repo) in _o and "created" in _o))
# #276: the hook creates the missing labels when they are first needed, and its note names them.
import importlib.util as _lb_util
_lb_hook_spec = _lb_util.spec_from_file_location("hook_for_labels", HOOK)
_lb_hook = _lb_util.module_from_spec(_lb_hook_spec)
_lb_hook_spec.loader.exec_module(_lb_hook)
with open(_lb_file, "w", encoding="utf-8") as f:
    json.dump({_lb_repo: ["bug"]}, f)
os.environ[_lb.REPO_LABELS_FILE_ENV] = _lb_file
try:
    _lb_note = _lb_hook.design_loop._house_labels_note(_lb_git)
    _lb_again = _lb_hook.design_loop._house_labels_note(_lb_git)
    _lb_none = _lb_hook.design_loop._house_labels_note(_lb_empty)
finally:
    del os.environ[_lb.REPO_LABELS_FILE_ENV]
_lb_cases.append(("the hook's label note names the labels it created, then says nothing once they exist (#276)",
                  "created the missing labels" in _lb_note and "`in progress`" in _lb_note and _lb_again == ""
                  and _lb_none == ""))

for _t, _ok in _lb_cases:
    report("PASS" if _ok else "FAIL", "label setup: " + _t)

# --- the clear writing check: the shared checker and where it runs (#247, #248) -----------------
import clarity as _cw
_cw_cases = []


def _cw_has(fn, text, phrase):
    return any(phrase in p for p in fn(text))


# Each detector, against a real failure from 2026-10-14/15 and its honest rewrite.
_cw_cases.append(('vague: "about 43 tests" is flagged (aj: "not the kind of thing that is ambiguous")',
                  _cw_has(_cw.vague_claims, "The pull request adds about 43 tests.", "about 43")))
_cw_cases.append(("vague: an estimate that says why it's an estimate passes",
                  not _cw.vague_claims("New file, estimated 25 lines, because it isn't written yet.")))
_cw_cases.append(('vague: "should work" is flagged; "should work from now on" (a rule, not a guess) is not',
                  _cw.vague_claims("It should work now.") and not _cw.vague_claims("Every page should work from now on.")))
_cw_cases.append(('not-checked: a list label "Not checked:" is not a confession (the false alarm of 2026-10-15)',
                  not _cw.unreasoned_not_checked("**Not checked:** vague numbers, by any hook.")
                  and _cw.unreasoned_not_checked("I haven't checked the CI logs.")))
_cw_cases.append(('bare-ref: "see #229." alone is flagged; with its title, or a quoted title after it, it passes',
                  _cw_has(_cw.bare_references, "Rerun it; see #229.", "#229")
                  and not _cw.bare_references("See #229 (the stale temp file flake).")
                  and not _cw.bare_references('Filed as #228, "Audit every house rule".')))
_cw_cases.append(('bare-ref: a quoted example ("see #229" alone) and a step card ("Step 1 of 3") pass',
                  not _cw.bare_references('Including "see #229" alone as a test.')
                  and not _cw.bare_references("### Step 1 of 3 — open the folder")))
_cw_cases.append(('bare-ref (#339): "see round 1, answer 7." and "as answer 2 said." are flagged',
                  _cw_has(_cw.bare_references, "Then see round 1, answer 7.", "answer 7")
                  and _cw_has(_cw.bare_references, "That is as answer 2 said.", "answer 2")))
_cw_cases.append(('bare-ref (#339): a round and question with a description, "question 3 (title)", and quotes pass',
                  not _cw.bare_references("Round 2, question 1, where the agent's name comes from: the GitHub login plus sAgent.")
                  and not _cw.bare_references("See question 3 (where the rule goes).")
                  and not _cw.bare_references('Including "see answer 7" alone as a test.')
                  and not _cw.bare_references("See #229 (the stale temp file flake).")))
_cw_cases.append(('bare-ref: "option D showed the text" is flagged; "option D: delete the cache" is not',
                  _cw.bare_references("On that look, option D showed the trimmed text.")
                  and not _cw.bare_references("Pick option D: delete the cache.")))
_cw_cases.append(("repeat: three sentences opening \"Nothing\" in a row, and a repeated four-word phrase, are flagged",
                  _cw.repetition("Nothing changed. Nothing else has changed. Nothing new.")
                  and _cw.repetition("The check on the count passed. The check on the newest commit is running.")))
_cw_cases.append(("repeat: parallel list items and a phrase quoted twice are not",
                  not _cw.repetition("- two sections moved out of the main rules file\n- one line moved out of the standards")
                  and not _cw.repetition('He said "ask instead of assuming", and the rule says "ask instead of assuming".')))
_cw_cases.append(("jargon and long sentences are flagged; code spans are not read",
                  _cw.jargon("The payload is read.") and not _cw.jargon("The `payload` field is read.")
                  and _cw.long_sentences(" ".join(["word"] * 45) + ".")))
_cw_cases.append(("issue sections: all three found, or each missing one named",
                  not _cw.missing_issue_sections("## Depends on\nx\n## Depended on by\ny\n## Done when\nz")
                  and _cw.missing_issue_sections("## Depends on\nx") == ["Depended on by", "Done when"]))
_cw_cases.append(("page text: a template page's PAGE strings are what gets read",
                  "about 43 tests" in _cw.page_text('<p>Hi there all</p><script>const PAGE = {\n lead: "It adds about 43 tests in all."\n};</script>')))

# The reply check: one note, quiet on a clean reply, off with its switch.
def _cw_stop(text, env=None):
    return run_hook("handover", stop_payload(last_assistant_message=text, cwd=_loop_dir), env=env or _loop_env)[1]


_cw_cases.append(("reply (#324): a vague number and a bare reference get no writing note",
                  "write it so nothing is left to guess" not in _cw_stop("The suite adds about 43 tests; see #229.")))
_cw_cases.append(("reply (#324): a bare reference and a vague number get no writing note and no report line",
                  "write it so nothing is left to guess" not in _cw_stop("Go with option B; it adds about 43 tests; see #229.")
                  and "writing check (report only" not in _cw_stop("Go with option B; it adds about 43 tests; see #229.")))
_cw_cases.append(("reply: a clean reply gets no writing note",
                  "write it so nothing is left to guess" not in _cw_stop("The suite adds 43 tests: 616 on main, 659 here.")))

# The page check: a write to docs/plans/*.html.
_cw_pages = os.path.join(_loop_dir, "docs", "plans")
os.makedirs(_cw_pages, exist_ok=True)


def _cw_page(html):
    path = os.path.join(_cw_pages, "probe.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    p = {"hook_event_name": "PostToolUse", "tool_name": "Write", "session_id": "loop", "cwd": _loop_dir,
         "tool_input": {"file_path": path, "content": html}}
    return run_hook("artifact", json.dumps(p), env=_loop_env)[1]


_cw_cases.append(("page: a page under docs/plans with a vague number is named before publishing",
                  "the page probe.html" in _cw_page("<p>This adds about 43 tests to the suite.</p>")))
_cw_cases.append(("page: a clean page gets no note",
                  "the page probe.html" not in _cw_page("<p>This adds 43 tests to the suite.</p>")))

# The issue check: the GitHub tool and gh.
_CW_GOOD_BODY = "## Depends on\nNothing.\n## Depended on by\nNothing.\n## Done when\nIt passes."


def _cw_issue_tool(body):
    p = {"hook_event_name": "PreToolUse", "tool_name": "mcp__github__issue_write", "session_id": "loop",
         "cwd": _loop_dir, "tool_input": {"method": "create", "owner": "o", "repo": "r", "title": "t", "body": body}}
    return run_hook("guardgithub", json.dumps(p), env=dict(_loop_env, HOUSE_RULES_ISSUES="on"))[1]


def _cw_issue_gh(body):
    p = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "loop", "cwd": _loop_dir,
         "tool_input": {"command": "gh issue create --title t --body %s" % json.dumps(body)}}
    return run_hook("guard", json.dumps(p), env=dict(_loop_env, HOUSE_RULES_ISSUES="on"))[1]


_cw_cases.append(("issue: the GitHub tool's issue with no sections is refused, naming all three",
                  '"deny"' in _cw_issue_tool("Just a title.") and "Done when" in _cw_issue_tool("Just a title.")))
_cw_cases.append(("issue: the GitHub tool's issue with all three sections goes through",
                  "missing" not in _cw_issue_tool(_CW_GOOD_BODY)))
_cw_cases.append(("issue: gh issue create with no sections is refused; with them it is not",
                  "is missing" in _cw_issue_gh("Just a title.") and "is missing" not in _cw_issue_gh(_CW_GOOD_BODY)))

# The editor reminder (#249): a page written, or a long reply, with no editor helper run this turn.
_CW_USER = json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "make the page"}})
_CW_WRITE = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write",
                        "input": {"file_path": os.path.join(_cw_pages, "plan.html"), "content": "<p>x</p>"}}]}})
_CW_EDITOR = json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Agent",
                         "input": {"subagent_type": "house-rules:editor", "prompt": "edit the page"}}]}})
_cw_t_page = _hand_transcript("cw-page", [_CW_USER, _CW_WRITE])
_cw_t_edited = _hand_transcript("cw-edited", [_CW_USER, _CW_WRITE, _CW_EDITOR])
_cw_t_none = _hand_transcript("cw-none", [_CW_USER])


def _cw_editor(transcript, text="The page is up."):
    return run_hook("handover", stop_payload(last_assistant_message=text, cwd=_loop_dir, stop_hook_active=True,
                                             transcript_path=transcript), env=_loop_env)[1]


_cw_cases.append(("editor: writing a page under docs/plans with no editor run gets the reminder",
                  "no @house-rules:editor helper ran" in _cw_editor(_cw_t_page)))
_cw_cases.append(("editor: the same turn with the editor helper run stays quiet about it",
                  "no @house-rules:editor helper ran" not in _cw_editor(_cw_t_edited)))
def _cw_editor_on(transcript, text):
    return run_hook("handover", stop_payload(last_assistant_message=text, cwd=_loop_dir, stop_hook_active=True,
                                             transcript_path=transcript), env=dict(_loop_env, HOUSE_RULES_EDITOR="on"))[1]


_cw_200 = " ".join(["Words"] * 200) + ". https://claude.ai/artifact/abc"
# #325: with HOUSE_RULES_EDITOR=on a reply of 160 words or more with no editor run gets the reminder; a short one does not.
_cw_cases.append(("editor: with HOUSE_RULES_EDITOR=on, a reply of 160 words or more with no editor run gets the reminder; a short one does not",
                  "no @house-rules:editor helper ran" in _cw_editor_on(_cw_t_none, _cw_200)
                  and "no @house-rules:editor helper ran" not in _cw_editor_on(_cw_t_none, "Done.")))
_cw_cases.append(("editor (#325): a 200-word reply with no page and no editor run gets no editor reminder by default",
                  "no @house-rules:editor helper ran" not in _cw_editor(_cw_t_none, _cw_200)))
_cw_cases.append(("editor (#325): a turn that wrote a docs/plans page still owes the editor by default",
                  "no @house-rules:editor helper ran" in _cw_editor(_cw_t_page)))

# A page written by a shell command never passes the Write hook (found in the real run, #250).
with open(os.path.join(_cw_pages, "shellpage.html"), "w", encoding="utf-8") as _f:
    _f.write("<p>This adds about 43 tests to the suite.</p>")
_cw_t_shell = _hand_transcript("cw-shell", [
    json.dumps({"type": "user", "origin": {"kind": "human"}, "timestamp": "2000-01-01T00:00:00Z",
                "message": {"content": "make the page"}}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
                "input": {"command": "printf '<p>x</p>' > docs/plans/shellpage.html"}}]}})])
_cw_shell_out = _cw_editor(_cw_t_shell)
_cw_cases.append(("page: a page written by a shell command is checked at the end of the reply, editor reminder too",
                  "the page shellpage.html" in _cw_shell_out and "no @house-rules:editor helper ran" in _cw_shell_out))

# #284: in a git repository a page counts as written only when git shows it new, edited, or committed
# since aj's message; a cloned page has a fresh file time but an old commit, so it does not count.
import importlib.util as _pc_util
_pc_spec = _pc_util.spec_from_file_location("hook_for_page_scan", HOOK)
_pc_hook = _pc_util.module_from_spec(_pc_spec)
_pc_spec.loader.exec_module(_pc_hook)
_pc_repo = tempfile.mkdtemp(prefix="hr-pagescan-")
os.makedirs(os.path.join(_pc_repo, "docs", "plans"))
for _n in ("cloned.html", "edited.html"):
    with open(os.path.join(_pc_repo, "docs", "plans", _n), "w", encoding="utf-8") as _f:
        _f.write("<p>old</p>\n")
_pc_genv = dict(os.environ, GIT_AUTHOR_DATE="2000-01-01T00:00:00Z", GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")
for _a in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "old pages"]):
    subprocess.run(["git"] + _a, cwd=_pc_repo, env=_pc_genv, capture_output=True)
_pc_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60))
for _n in ("cloned.html", "edited.html"):
    os.utime(os.path.join(_pc_repo, "docs", "plans", _n), None)  # a clone or checkout sets a fresh file time
with open(os.path.join(_pc_repo, "docs", "plans", "edited.html"), "a", encoding="utf-8") as _f:
    _f.write("<p>new line</p>\n")
with open(os.path.join(_pc_repo, "docs", "plans", "new.html"), "w", encoding="utf-8") as _f:
    _f.write("<p>new</p>\n")
_pc_t = _hand_transcript("pagescan", [json.dumps({"type": "user", "origin": {"kind": "human"}, "timestamp": _pc_stamp,
                                                   "message": {"content": "make the page"}})])
_pc_pages, _pc_problem = _pc_hook.writing._pages_changed_this_turn(_pc_t, _pc_repo)
_pc_names = sorted(os.path.basename(p) for p in _pc_pages)
_cw_cases.append(("page scan: a cloned page with a fresh file time is not counted; edited and new pages are (#284)",
                  _pc_problem is None and _pc_names == ["edited.html", "new.html"]))
shutil.rmtree(_pc_repo, True)

# During an uncommitted merge, a page the other branch brought in unchanged is not this turn's work;
# a page edited during the merge still is. Before this, every merged page re-fired the page and editor
# notes on every reply until the merge was committed.
_pm_repo = tempfile.mkdtemp(prefix="hr-pagemerge-")
os.makedirs(os.path.join(_pm_repo, "docs", "plans"))
_pm_git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=_pm_repo,
                                    env=_pc_genv, capture_output=True)
_pm_git("init", "-q", "-b", "base")
with open(os.path.join(_pm_repo, "docs", "plans", "base.html"), "w", encoding="utf-8") as _f:
    _f.write("<p>base</p>\n")
_pm_git("add", ".")
_pm_git("commit", "-qm", "base")
_pm_git("checkout", "-q", "-b", "other")
for _n in ("merged.html", "touched.html"):
    with open(os.path.join(_pm_repo, "docs", "plans", _n), "w", encoding="utf-8") as _f:
        _f.write("<p>from the other branch</p>\n")
_pm_git("add", ".")
_pm_git("commit", "-qm", "other pages")
_pm_git("checkout", "-q", "base")
with open(os.path.join(_pm_repo, "docs", "plans", "base.html"), "a", encoding="utf-8") as _f:
    _f.write("<p>base moves on</p>\n")
_pm_git("commit", "-qam", "base moves on")
_pm_git("merge", "--no-ff", "--no-commit", "other")
with open(os.path.join(_pm_repo, "docs", "plans", "touched.html"), "a", encoding="utf-8") as _f:
    _f.write("<p>edited during the merge</p>\n")
_pm_pages, _pm_problem = _pc_hook.writing._pages_changed_this_turn(_pc_t, _pm_repo)
_pm_names = sorted(os.path.basename(p) for p in _pm_pages)
_cw_cases.append(("page scan: during a merge, a page brought in unchanged is not counted; one edited during it is",
                  _pm_problem is None and _pm_names == ["touched.html"]))
shutil.rmtree(_pm_repo, True)

for _t, _ok in _cw_cases:
    report("PASS" if _ok else "FAIL", "clear writing: " + _t)

# --- the checkpoint table (#256): a miss blocks once, then only reports on the retry -----------
_ck_cases = []
_CK_ENV = dict(_loop_env, HOUSE_RULES_COMMIT_CHECK="off", HOUSE_RULES_LOOP="on")


def _ck_user(text, extra=()):
    return [json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": text}})] + list(extra)


def _ck_run(transcript, reply, active=False, env=None):
    _, out, _ = run_hook("handover", stop_payload(last_assistant_message=reply, cwd=_loop_dir, stop_hook_active=active,
                                                  transcript_path=transcript), env=env or _CK_ENV)
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    return data.get("decision") == "block", data.get("reason", ""), out


def _ck_triple(label, rule, transcript, bad, good, env=None, good_transcript=None):
    blocked, reason, _o = _ck_run(transcript, bad, env=env)
    _ck_cases.append(("%s: a miss blocks once, naming the %s rule" % (label, rule), blocked and ("- %s:" % rule) in reason))
    blocked, _r, out = _ck_run(transcript, bad, active=True, env=env)
    _ck_cases.append(("%s: the same reply on the retry only reports, never blocks" % label, not blocked and out.strip() != ""))
    blocked, _r, _o = _ck_run(good_transcript or transcript, good, env=env)
    _ck_cases.append(("%s: a compliant reply passes" % label, not blocked))


_ck_t_plain = _hand_transcript("ck-plain", _ck_user("what is up"))
_ck_t_read = _hand_transcript("ck-read", _ck_user("check it", [json.dumps({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "r1", "name": "Bash", "input": {"command": "python3 t.py"}}]}})]))
_ck_t_edited = _hand_transcript("ck-edited", [_CW_USER, _CW_WRITE, _CW_EDITOR])

# 1 page rule (long reply) - editor ran, so only the page rule is in play
_ck_long = " ".join(["Words"] * 230) + "."
_ck_t_ed_only = _hand_transcript("ck-ed-only", _ck_user("explain", [_CW_EDITOR]))
_CK_PAGE_NOTE = "page checkpoint (report only, #309)"
_ck_b, _ck_reason, _ck_o = _ck_run(_ck_t_ed_only, _ck_long)
_ck_cases.append(("page (#309): a long reply with no page is not blocked, and the report names the page rule",
                  not _ck_b and _CK_PAGE_NOTE in _ck_o))
_ck_cases.append(("page: the report gives the exact build command", "make_page.py" in _ck_o and "build <content.json>" in _ck_o))
_ck_cases.append(("page: the report never offers \"no page\" to the agent (#283)",
                  "no page" not in _ck_o[_ck_o.find(_CK_PAGE_NOTE):][:400].lower()))
# #323: the first stop continues the turn (additionalContext); the retry reports to aj only (systemMessage).
_ck_t_323 = _hand_transcript("ck-323", _ck_user("explain 323", [_CW_EDITOR]))
_, _ck_o1, _ = run_hook("handover", stop_payload(last_assistant_message=_ck_long, cwd=_loop_dir,
                        transcript_path=_ck_t_323), env=_CK_ENV)
_, _ck_o2, _ = run_hook("handover", stop_payload(last_assistant_message=_ck_long, cwd=_loop_dir,
                        stop_hook_active=True, transcript_path=_ck_t_323), env=_CK_ENV)
try:
    _ck_j1, _ck_j2 = json.loads(_ck_o1), json.loads(_ck_o2)
except ValueError:
    _ck_j1, _ck_j2 = {}, {}
_ck_cases.append(("#323: the first stop gives additionalContext",
                  "additionalContext" in _ck_j1.get("hookSpecificOutput", {})))
_ck_cases.append(("#323: the retry gives no additionalContext (the page note is said once per message, #326, so the first stop carries it)",
                  "hookSpecificOutput" not in _ck_j2 and _CK_PAGE_NOTE in _ck_j1.get("hookSpecificOutput", {}).get("additionalContext", "")))
# #310: replays the 2026-10-16 dodge - a 165-word reply was flagged, then a 70-word retry cleared it.
_ck_165 = " ".join(["Words"] * 165) + "."
_ck_70 = " ".join(["Short"] * 70) + "."
_ck_t_dodge = _hand_transcript("ck-dodge", _ck_user("explain the dodge", [_CW_EDITOR]))
_ck_run(_ck_t_dodge, _ck_165)
_ck_b, _, _ck_o = _ck_run(_ck_t_dodge, _ck_70, active=True)
_ck_cases.append(("page (#310/#326): a 70-word retry after a flagged 165-word reply to the same message gets no repeat of the note (said once per message)",
                  not _ck_b and _CK_PAGE_NOTE not in _ck_o and "none is linked yet" not in _ck_o))
_ck_t_once = _hand_transcript("ck-once", _ck_user("explain once", [_CW_EDITOR]))
_, _, _ck_o1 = _ck_run(_ck_t_once, _ck_165)
_, _, _ck_o2 = _ck_run(_ck_t_once, _ck_165)
_ck_cases.append(("page (#326): two long replies to one message of aj's with no page link give the note on the first only",
                  _CK_PAGE_NOTE in _ck_o1 and _CK_PAGE_NOTE not in _ck_o2))
_ck_b, _, _ck_o = _ck_run(_ck_t_dodge, _ck_70 + " https://claude.ai/artifact/abc", active=True)
_ck_cases.append(("page (#310): a reply that links a page clears what was owed", not _ck_b and _CK_PAGE_NOTE not in _ck_o))
_ck_b, _, _ck_o = _ck_run(_ck_t_dodge, _ck_70, active=True)
_ck_cases.append(("page (#310): after the link, a short reply to the same message gets no report", _CK_PAGE_NOTE not in _ck_o))
_ck_run(_ck_t_dodge, _ck_165)
_ck_b, _, _ck_o = _ck_run(_hand_transcript("ck-dodge-next", _ck_user("a new question", [_CW_EDITOR])), _ck_70)
_ck_cases.append(("page (#310): a new message from aj starts with nothing owed", _CK_PAGE_NOTE not in _ck_o))
_ck_t_nopage = _hand_transcript("ck-nopage", _ck_user("explain it, no page", [_CW_EDITOR]))
_ck_b1, _, _ck_o1 = _ck_run(_ck_t_nopage, _ck_long)
_ck_b2, _, _ck_o2 = _ck_run(_ck_t_nopage, _ck_long, active=True)
_ck_cases.append(("page: aj's own \"no page\" means no report, first pass and retry",
                  not _ck_b1 and not _ck_b2 and _CK_PAGE_NOTE not in _ck_o1 + _ck_o2))
_ck_b, _, _ck_o = _ck_run(_ck_t_ed_only, _ck_long + " https://claude.ai/artifact/abc")
_ck_cases.append(("page: a compliant reply passes with no report", not _ck_b and _CK_PAGE_NOTE not in _ck_o))
# #330: a page link counts only when it opens inside the session folder
_pl_cwd = tempfile.mkdtemp(prefix="pl-cwd-")
_pl_out = "file:///" + os.path.join(os.path.dirname(_pl_cwd), "elsewhere", "x.html").replace("\\", "/")
_ck_cases.append(("page links (#330): a markdown link to a page inside cwd counts",
                  _cc_mod.core._reply_links_page("See [p](docs/plans/x.html)", _pl_cwd)))
_ck_cases.append(("page links (#330): a ../Sibling/docs/plans/x.html link does not count",
                  not _cc_mod.core._reply_links_page("See [p](../Sibling/docs/plans/x.html)", _pl_cwd)))
_ck_cases.append(("page links (#330): a file:/// link outside cwd does not count",
                  not _cc_mod.core._reply_links_page("See " + _pl_out, _pl_cwd)))
_ck_cases.append(("page links (#330): a claude.ai artifact link counts",
                  _cc_mod.core._reply_links_page("See https://claude.ai/artifact/abc", _pl_cwd)))
_ck_cases.append(("page links (#330): a bare page.html counts",
                  _cc_mod.core._reply_links_page("See page.html", _pl_cwd)))
_ck_cases.append(("page links (#330): [x.html](../Sibling/x.html) does not count on its link text",
                  not _cc_mod.core._reply_links_page("See [x.html](../Sibling/docs/plans/x.html)", _pl_cwd)))
_ck_cases.append(("page links (#330): the outside-folder note names the path",
                  "../Sibling/docs/plans/x.html is outside" in _cc_mod.design_loop._check_page(
                      {"reply": "See [x.html](../Sibling/docs/plans/x.html)", "cwd": _pl_cwd, "long_words": 200})))
# 2 editor
_ck_triple("editor", "editor", _cw_t_page, "The page is up.", "The page is up.", good_transcript=_ck_t_edited)
# 3 evidence
_ck_triple("evidence", "evidence", _ck_t_plain, "All done, the tests passed.", "All done, the tests passed.",
           good_transcript=_ck_t_read)
# 4 commit
_ck_repo_dirty = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
_ck_repo_clean = _commit_repo("claude/topic", committed=["a.py"])
_ck_t_w_dirty = _wrote_transcript("ck-w-dirty", [os.path.join(_ck_repo_dirty, "a.py")])
_ck_t_w_clean = _wrote_transcript("ck-w-clean", [os.path.join(_ck_repo_clean, "a.py")])
_ck_cenv = lambda root: _project_env(root, HOUSE_RULES_LOOP="on", HOUSE_RULES_ISSUES="off", HOUSE_RULES_AUTOSAVE="off",
                                     HOUSE_RULES_LOOP_LABELS_FILE=_loop_labels_file)
_ck_b, _ck_r, _ = _ck_run(_ck_t_w_dirty, "Changed the file.", env=_ck_cenv(_ck_repo_dirty))
_ck_cases.append(("commit: a turn that left its file uncommitted blocks once, naming the commit rule", _ck_b and "- commit:" in _ck_r))
_ck_b, _, _o = _ck_run(_ck_t_w_dirty, "Changed the file.", active=True, env=_ck_cenv(_ck_repo_dirty))
_ck_cases.append(("commit: the same reply on the retry only reports", not _ck_b and "uncommitted" in _o))
_ck_b, _, _ = _ck_run(_ck_t_w_clean, "Changed the file.", env=_ck_cenv(_ck_repo_clean))
_ck_cases.append(("commit: a committed file passes", not _ck_b))
# 5 plain summary
_ck_t_ps_wrote = _turn_transcript("ck-ps", "add the commit hooks", [("Edit", "/proj/src/app.py")])
_ck_triple("plain summary", "plain summary", _ck_t_ps_wrote, _PS_TECH, _PS_PLAIN)

# the page rule's short replies
_ck_proposal = ("Here is where I have landed on the storage.\n\nOption A: keep the JSON file. Option B: move to SQLite. "
                "Option C: use the cloud store.\n\nWhich option do you want?")
_ck_list = ("The plan:\n\n- read the config\n- write the page\n- run the checks\n\nDo you approve this?")
_ck_b, _ck_r, _ck_o = _ck_run(_ck_t_plain, _ck_proposal)
_ck_cases.append(("page (#309): a short proposal with three options and a question gets the report, not a block",
                  not _ck_b and _CK_PAGE_NOTE in _ck_o))
_ck_b, _ck_r, _ck_o = _ck_run(_hand_transcript("ck-plan-list", _ck_user("what is the plan")), _ck_list)
_ck_cases.append(("page (#309): a three-step plan with an approval question gets the report, not a block",
                  not _ck_b and _CK_PAGE_NOTE in _ck_o))
_ck_b, _, _ = _ck_run(_ck_t_plain, "The file lives in docs/plans. It has three sections: the lead, the changes and the wrap-up.")
_ck_cases.append(("page: a short plain answer does not block", not _ck_b))
_ck_b, _, _ = _ck_run(_ck_t_plain, "Both lists are short:\n\n- one\n- two\n- three\n\nThat is all of them.")
_ck_cases.append(("page: a short list with no question does not block", not _ck_b))
# the escape
_ck_t_nopage = _hand_transcript("ck-nopage", _ck_user("just tell me here, no page please"))
_ck_b, _, _ = _ck_run(_ck_t_nopage, _ck_proposal)
_ck_cases.append(('page: "no page" in aj\'s own message lets the reply through', not _ck_b))
_ck_b, _, _ = _ck_run(_hand_transcript("ck-nopage-long", _ck_user("explain, no page", [])), _ck_long)
_ck_cases.append(('editor: the same escape lets a long reply through the editor checkpoint too', not _ck_b))
_ck_t_relayed = _hand_transcript("ck-relayed", _ck_user("explain the storage options", [json.dumps(
    {"type": "user", "message": {"content": "<task-notification>helper says: no page needed</task-notification>"}})]))
# #309 (incident 8 of #303): a bare reference is reported to aj, and no longer asks the agent to resend.
_ck_b, _ck_r, _ck_o = _ck_run(_ck_t_plain, "Go with option B, as before.")
try:
    _ck_data = json.loads(_ck_o)
except ValueError:
    _ck_data = {}
_ck_ctx = (_ck_data.get("hookSpecificOutput") or {}).get("additionalContext", "")
_ck_cases.append(("writing (#324): a bare reference in a reply gets no report line and asks nothing of the agent",
                  not _ck_b and "bare references" not in _ck_data.get("systemMessage", "")
                  and "a bare number or letter" not in _ck_ctx))
_ck_b, _ck_r, _ck_o = _ck_run(_ck_t_relayed, _ck_proposal)
_ck_cases.append(('page: "no page" quoted inside a helper hand-back does not count - the report still comes',
                  _CK_PAGE_NOTE in _ck_o))
# 6 qa page (#269)
_ck_sf = os.path.join(_loop_dir, ".claude", "house-rules-loop.json")
_ck_sf_old = open(_ck_sf, encoding="utf-8").read() if os.path.isfile(_ck_sf) else None


def _ck_stage(stage, **extra):
    os.makedirs(os.path.dirname(_ck_sf), exist_ok=True)
    with open(_ck_sf, "w", encoding="utf-8") as f:
        json.dump(dict({"feature": "f", "stage": stage, "skip": False, "approvals": []}, **extra), f)


_ck_qa_page = "docs/plans/f-qa.html"
_ck_stage("qa")
_ck_b, _ck_r, _ = _ck_run(_ck_t_plain, "The build is ready.")
_ck_cases.append(("qa page: in QA with no page built a reply blocks, naming the rule and make_page.py",
                  _ck_b and "- qa page:" in _ck_r and "make_page.py" in _ck_r and "no QA page is built" in _ck_r))
_ck_b, _, _o = _ck_run(_ck_t_plain, "The build is ready.", active=True)
_ck_cases.append(("qa page: the retry never blocks", not _ck_b))
_ck_stage("qa", qa_page=_ck_qa_page)
_ck_b, _ck_r, _ = _ck_run(_ck_t_plain, "The build is ready.")
_ck_cases.append(("qa page: built but not linked blocks, saying so", _ck_b and "not linked" in _ck_r))
_ck_cases.append(("blocked checkpoint reason asks for what changed only, not the reply again",
                  "send only what changed" in _ck_r and "send the reply again" not in _ck_r))
_ck_b, _, _ = _ck_run(_ck_t_nopage, "The build is ready.")
_ck_cases.append(('qa page: "no page" in aj\'s message does not skip it', _ck_b))
_ck_b, _, _ = _ck_run(_ck_t_plain, "QA page: %s" % _ck_qa_page)
_ck_cases.append(("qa page: a reply linking the page path passes and records it",
                  not _ck_b and json.load(open(_ck_sf, encoding="utf-8")).get("qa_page_linked") is True))
_ck_b, _, _ = _ck_run(_ck_t_plain, "The build is ready.")
_ck_cases.append(("qa page: a later reply without the link passes", not _ck_b))
_ck_stage("qa", qa_page=_ck_qa_page)
_ck_b, _, _ = _ck_run(_ck_t_plain, "Here: https://claude.ai/artifact/abc123")
_ck_cases.append(("qa page: a claude.ai artifact link passes", not _ck_b))
_ck_stage("qa", qa_page=_ck_qa_page)
_ck_b, _, _ = _ck_run(_ck_t_plain, "QA page: %s" % _ck_qa_page, active=True)
_ck_cases.append(("qa page: a retry reply linking the page does not block and records it",
                  not _ck_b and json.load(open(_ck_sf, encoding="utf-8")).get("qa_page_linked") is True))
_ck_stage("qa", qa_page=_ck_qa_page)
_ck_b, _, _ = _ck_run(_ck_t_plain, "The build is ready.", active=True)
_ck_cases.append(("qa page: a retry reply without the link does not block and records nothing",
                  not _ck_b and "qa_page_linked" not in json.load(open(_ck_sf, encoding="utf-8"))))
for _st in ("build", "design"):
    _ck_stage(_st)
    _ck_b, _, _ = _ck_run(_ck_t_plain, "The build is ready.")
    _ck_cases.append(("qa page: the %s stage never blocks" % _st, not _ck_b))
if _ck_sf_old is None:
    os.remove(_ck_sf)
else:
    open(_ck_sf, "w", encoding="utf-8").write(_ck_sf_old)
# the switch
_ck_b, _, out = _ck_run(_ck_t_plain, _ck_proposal, env=dict(_CK_ENV, HOUSE_RULES_LOOP="off"))
_ck_cases.append(("HOUSE_RULES_LOOP=off turns every checkpoint off", not _ck_b))
_ck_b, _, _ = _ck_run(_ck_t_plain, "All done, the tests passed.", env=dict(_CK_ENV, HOUSE_RULES_LOOP="off"))
_ck_cases.append(("HOUSE_RULES_LOOP=off also stops the evidence checkpoint", not _ck_b))

for _t, _ok in _ck_cases:
    report("PASS" if _ok else "FAIL", "checkpoints: " + _t)

# ---- pagecheck: the page check before saving or publishing (#257) ----
_pc_tmp = tempfile.mkdtemp(prefix="pc-")
_pc_env = dict(os.environ, HOUSE_RULES_LOOP="on")
_pc_off = dict(os.environ, HOUSE_RULES_LOOP="off")
_pc_hand = "<!doctype html>\n<html><body>by hand</body></html>\n"
_pc_built = "<!doctype html>\n<!-- house-rules make_page 9.9.9 -->\n<html><body>built</body></html>\n"


def _pc_file(name, text):
    p = os.path.join(_pc_tmp, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _pc(tool, ti, env=None):
    _rc, out, _err = run_hook("pagecheck", json.dumps({"tool_name": tool, "tool_input": ti}), env=env or _pc_env)
    return out


def _pc_denied(out):
    return '"permissionDecision":"deny"' in out


_pc_plans = os.path.join(_pc_tmp, "docs", "plans", "x.html")
_pc_elsewhere = os.path.join(_pc_tmp, "notes", "x.html")
_pc_hand_f = _pc_file("hand.html", _pc_hand)
_pc_built_f = _pc_file("built.html", _pc_built)
_pc_data_f = _pc_file("data.json", "{}")
_pc_cases = []
_o = _pc("Write", {"file_path": _pc_plans, "content": _pc_hand})
_pc_cases.append(("Write of a hand-written docs/plans page is refused, naming the page and the builder command",
                  _pc_denied(_o) and _pc_plans in _o and "make_page.py build <content.json>" in _o))
_pc_cases.append(("Write of a builder page under docs/plans is allowed",
                  _pc("Write", {"file_path": _pc_plans, "content": _pc_built}) == ""))
_pc_cases.append(("Write of an .html outside docs/plans is allowed",
                  _pc("Write", {"file_path": _pc_elsewhere, "content": _pc_hand}) == ""))
_pc_cases.append(("Artifact publish of a hand-written page is refused",
                  _pc_denied(_pc("Artifact", {"file_path": _pc_hand_f}))))
_pc_cases.append(("Artifact publish of a hand-written page named in files is refused",
                  _pc_denied(_pc("Artifact", {"files": {"index": _pc_hand_f}}))))
_pc_cases.append(("Artifact publish of a builder page is allowed",
                  _pc("Artifact", {"file_path": _pc_built_f}) == ""))
_o = _pc("Artifact", {"action": "read", "file_path": _pc_hand_f})
_pc_cases.append(("Artifact read is skipped with a note", not _pc_denied(_o) and "skipped" in _o))
_o = _pc("Artifact", {"action": "list"})
_pc_cases.append(("Artifact list is skipped with a note", not _pc_denied(_o) and "skipped" in _o))
_o = _pc("Artifact", {"asset": True, "file_path": _pc_hand_f})
_pc_cases.append(("Artifact asset upload is skipped with a note", not _pc_denied(_o) and "asset upload" in _o))
_o = _pc("Artifact", {"type": "chart", "file_path": _pc_data_f})
_pc_cases.append(("Artifact typed data file is skipped with a note", not _pc_denied(_o) and "skipped" in _o))
_o = _pc("Artifact", {"file_path": os.path.join(_pc_tmp, "missing.html")})
_pc_cases.append(("Artifact unreadable file is allowed with a note", not _pc_denied(_o) and "could not read" in _o))
_pc_cases.append(("HOUSE_RULES_LOOP=off allows a hand-written Write and a hand-written publish",
                  _pc("Write", {"file_path": _pc_plans, "content": _pc_hand}, _pc_off) == ""
                  and _pc("Artifact", {"file_path": _pc_hand_f}, _pc_off) == ""))
_pc_cases.append(("a payload with no tool_input fails open with a note",
                  "could not run" in _pc("Write", None)))
for _t, _ok in _pc_cases:
    report("PASS" if _ok else "FAIL", "pagecheck: " + _t)
shutil.rmtree(_pc_tmp, True)
_nb_cases = []
_nb_pg = os.path.join(_nb_r, "built.html")
with open(_nb_pg, "w", encoding="utf-8") as f:
    f.write("<!doctype html>\n<!-- house-rules make_page 9.9.9 -->\n<html></html>\n")
_nb_cases.append(("publishing a make_page.py page goes through with no prompt or refusal",
                  run_hook("pagecheck", json.dumps({"tool_name": "Artifact", "tool_input": {"file_path": _nb_pg}}),
                           env=dict(_project_env(_nb_r), HOUSE_RULES_LOOP="on"))[1] == ""))
for _t, _ok in _nb_cases:
    report("PASS" if _ok else "FAIL", "never-blocked: " + _t)


# --- #375: one issue list per feature - a second design approval keeps the first feature's issues ----
def _pf_issue(number):
    p = {"hook_event_name": "PostToolUse", "tool_name": "mcp__github__issue_write", "session_id": "cl",
         "cwd": _cl_dir, "tool_input": {"method": "create", "title": "t", "labels": ["Feature", "AjsAgent created this"]},
         "tool_response": {"url": "https://github.com/o/r/issues/%d" % number}}
    run_hook("autosave", json.dumps(p), env=_cl_env)


def _pf_note(prompt):
    p = {"hook_event_name": "UserPromptSubmit", "session_id": "cl", "cwd": _cl_dir, "prompt": prompt}
    try:
        return json.loads(run_hook("scope", json.dumps(p), env=_cl_env)[1])["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def _pf_log():
    with open(os.path.join(_cl_dir, "docs", "6-decisions", "Decisions.md"), "a", encoding="utf-8") as f:
        f.write("an entry written at %r\n" % time.time())


def _pf_two_features():
    """The 2026-10-21 sequence, through real payloads: A to build with 2 issues, then B to build."""
    _cl_set({"stage": "design"})
    _pf_log(); _pf_note("Design approved: alpha")
    _pf_issue(701); _pf_issue(702)
    _loop_gh("in progress", 701, 702)
    _pf_log(); _pf_note("Build plan approved: alpha")
    _pf_log(); _pf_note("Design approved: beta")
    _pf_issue(711); _pf_issue(712)
    _loop_gh("in progress", 711, 712)
    _pf_log(); _pf_note("Build plan approved: beta")
    _loop_gh("needs review", 701, 702)


def _pf_nums(issues):
    return sorted(i.get("number") for i in issues)


_pf_cases = []
_pf_two_features()
_st = _cl_state()
_pf_cases.append(("a design approval during build keeps the old feature's issues under its name, and the new one builds with its own",
                  _st.get("stage") == "build" and _st.get("feature") == "beta" and _pf_nums(_st.get("issues", [])) == [711, 712]
                  and _pf_nums((_st.get("features") or {}).get("alpha", {}).get("issues", [])) == [701, 702]
                  and (_st.get("features") or {}).get("alpha", {}).get("stage") == "build"))
_n = _pf_note("QA passed: alpha")
_st = _cl_state()
_c = _st.get("closable") or [{}]
_pf_cases.append(("QA passed for the older feature records its issues as closable, drops it from the map, leaves the current feature in build",
                  len(_c) == 1 and _c[0].get("feature") == "alpha" and _pf_nums(_c[0].get("issues", [])) == [701, 702]
                  and "alpha" not in (_st.get("features") or {}) and _st.get("stage") == "build"
                  and _st.get("feature") == "beta" and _pf_nums(_st.get("issues", [])) == [711, 712]
                  and "moved, not the current one" in _n and '"beta" is unchanged' in _n))
_pf_two_features()
_loop_gh("in progress", 702)
_n = _pf_note("QA passed: alpha")
_st = _cl_state()
_pf_cases.append(("QA passed for a stored feature with an issue still in progress is refused, naming it, and nothing moves",
                  "#702" in _n and "Nothing moved" in _n and not _st.get("closable")
                  and "alpha" in (_st.get("features") or {}) and _st.get("stage") == "build"))
_cl_set({"feature": "alpha", "stage": "qa", "issues": _cl_issues})
_st = _cl_state(); _st.pop("features", None)
with open(_cl_file, "w", encoding="utf-8") as f:
    json.dump(_st, f)
_loop_gh("needs review", 7, 8)
_pf_note("QA passed: alpha")
_st = _cl_state()
_pf_cases.append(("a stage file with no features key loads and the current feature's QA pass works as before",
                  _st.get("stage") == "done" and len(_st.get("closable") or []) == 1 and "features" not in _st))
_pf_two_features()
_n = _pf_note("QA failed: alpha")
_st = _cl_state()
_a = (_st.get("features") or {}).get("alpha", {})
_pf_cases.append(("QA failed for a stored feature keeps it in the map back in build marked redo, and the current feature is unchanged",
                  _a.get("stage") == "build" and _a.get("redo") is True and _pf_nums(_a.get("issues", [])) == [701, 702]
                  and not _st.get("closable") and _st.get("stage") == "build" and _st.get("feature") == "beta"
                  and "stays in the kept features" in _n))
_pf_note("QA passed: alpha")
_st = _cl_state()
_pf_cases.append(("a stored feature that failed QA can pass a later QA once its issues say needs review",
                  len(_st.get("closable") or []) == 1 and "alpha" not in (_st.get("features") or {})
                  and _st.get("stage") == "build"))
for _t, _ok in _pf_cases:
    report("PASS" if _ok else "FAIL", "per-feature issues: " + _t)



finish()
