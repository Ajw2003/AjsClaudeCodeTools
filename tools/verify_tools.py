#!/usr/bin/env python3
"""verify_tools.py — proves the scripts in tools/ do what they claim.

    python tools/verify_tools.py

verify.py covers the plugin's hooks. Nothing covered tools/, and that gap has already cost
something real: clean_install_test.py's cleanliness check contradicted its own strip step for as
long as it existed, and was found only by running the script twice by hand. A tool nothing tests
is a tool whose bugs are found by the person relying on it.

Same shape as verify.py deliberately: stdlib only, no test framework, one numbered PASS/FAIL line
per case, and the count computed at runtime so it cannot drift.

WHAT THIS CANNOT COVER, stated rather than implied: anything that shells out to the `claude` CLI
or mutates a real machine's config. clean_install_test.py's install and strip steps are exercised
by running it, not from here; what is covered is the decision logic lifted out of it. install.py
is covered the same way - install_steps() is asserted as a VALUE, so the order of the four CLI
commands is pinned without any of them running.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import clean_install_test  # noqa: E402
import install  # noqa: E402
import measure_footprint  # noqa: E402
import session_ledger  # noqa: E402

STEP = 0
FAILURES = 0


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    print(f"{STEP:2d}. {result}  {title}")


def check(condition, title, detail):
    report("PASS" if condition else "FAIL", title)
    print(f"          {detail}")


def rec(**kw):
    return json.dumps(kw)


def human(text, ts="2026-09-09T01:00:00Z"):
    return rec(type="user", origin={"kind": "human"},
               message={"role": "user", "content": text}, timestamp=ts)


def stop_feedback(hook="~/.claude/stop-hook-git-check.sh", ts="2026-09-09T01:00:05Z"):
    return rec(type="user", origin=None, timestamp=ts, message={
        "role": "user",
        "content": f"Stop hook feedback:\n[{hook}]: There are 1 unpushed commit(s).",
    })


def tool_use(name, inp, ts="2026-09-09T01:00:10Z"):
    return rec(type="assistant", timestamp=ts, message={
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "t1", "name": name, "input": inp}],
    })


def injection(event, content, ts="2026-09-09T01:00:01Z"):
    return rec(type="attachment", timestamp=ts, attachment={
        "type": "hook_additional_context", "hookEvent": event,
        "hookName": event, "content": content, "toolUseID": event,
    })


def write_transcript(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def turns_from(lines):
    path = write_transcript(lines)
    try:
        records, _ = session_ledger.load(path)
        return session_ledger.build_turns(records)
    finally:
        os.unlink(path)


print("tools/ - verification")
print("=====================")
print()

# --- session_ledger: the failure it was built for -----------------------------------------
# A Stop hook continues the turn, so work after it happens past the reply the user read. The
# first version of this tool keyed on the stop_hook_summary record, which the harness writes
# AFTER that work - so it missed the very incident it exists to surface.
turns = turns_from([
    human("push the branch please"),
    tool_use("Bash", {"command": "git status"}),
    stop_feedback(),
    tool_use("Bash", {"command": "git push -u origin feature"}),
    tool_use("mcp__github__update_pull_request", {"owner": "o", "repo": "r"}),
])
cont = turns[0]["continuation"] if turns else []
check(
    len(turns) == 1 and len(cont) == 2,
    "an action after Stop hook feedback is recorded as a turn continuation",
    f"1 turn, {len(cont)} continuation action(s) - expected 2 (the push and the PR update)",
)
check(
    any("git push" in c[1] for c in cont) and any("update_pull_request" in c[0] for c in cont),
    "the continuation names both the push and the pull-request write",
    f"got: {[c[0] + ' ' + c[1][:28] for c in cont]}",
)
check(
    all(c[3] for c in cont),
    "both continuation actions are flagged repo-mutating",
    f"mutating flags: {[c[3] for c in cont]}",
)

# --- and work BEFORE the stop hook is not a continuation ----------------------------------
# commands holds every call in the turn - the read before the hook, and both writes after it.
# continuation holds only what came after. The read must appear in one and not the other.
before = [c for c in turns[0]["commands"] if c[1] == "git status"] if turns else []
check(
    turns and len(turns[0]["commands"]) == 3 and before
    and not any(c[1] == "git status" for c in turns[0]["continuation"]),
    "work before the Stop hook is recorded, but not as a continuation",
    f"{len(turns[0]['commands']) if turns else 0} commands in the turn; "
    f"git status present={bool(before)}, and absent from the continuation",
)

# --- a turn with no Stop hook has no continuation at all ----------------------------------
plain = turns_from([
    human("just look at something"),
    tool_use("Bash", {"command": "ls -la"}),
])
check(
    plain and not plain[0]["continuation"],
    "a turn that never hit a Stop hook reports no continuation",
    f"continuation entries: {len(plain[0]['continuation']) if plain else 'no turns'}",
)

# --- GitHub reads must not be recorded as writes ------------------------------------------
# "Any tool not ending in _read" counted actions_list - a read - as repo-mutating. In an audit
# record, mislabelling a read as a write is worse than omitting it, because the record is trusted.
reads = ["mcp__github__actions_list", "mcp__github__list_branches",
         "mcp__github__get_commit", "mcp__github__search_code",
         "mcp__github__pull_request_read"]
writes = ["mcp__github__create_pull_request", "mcp__github__update_pull_request",
          "mcp__github__merge_pull_request", "mcp__github__add_issue_comment",
          "mcp__github__delete_file", "mcp__github__push_files"]
misread = [n for n in reads if session_ledger.is_github_write(n)]
miswrite = [n for n in writes if not session_ledger.is_github_write(n)]
check(
    not misread and not miswrite,
    "GitHub reads are not logged as writes, and writes are not missed",
    f"{len(reads)} reads and {len(writes)} writes classified correctly"
    if not misread and not miswrite
    else f"reads called writes: {misread}; writes called reads: {miswrite}",
)

# --- git-mutating detection runs on the WHOLE command, not the truncated display -----------
long_cmd = "echo " + "x" * 200 + " && git commit -m wip"
check(
    bool(session_ledger.GIT_MUTATING.search(long_cmd))
    and not session_ledger.GIT_MUTATING.search("git status && git log --oneline"),
    "a mutating verb past the display truncation is still detected, and reads are not",
    "the flag is computed on the full command; only the display is shortened",
)

# --- turns are split on human prompts only ------------------------------------------------
multi = turns_from([
    human("first"),
    tool_use("Bash", {"command": "ls"}),
    rec(type="user", origin={"kind": "task-notification"},
        message={"role": "user", "content": "a background task finished"},
        timestamp="2026-09-09T01:00:20Z"),
    human("second"),
    tool_use("Bash", {"command": "pwd"}),
])
check(
    len(multi) == 2 and len(multi[0]["notifications"]) == 1,
    "turns split on human prompts, and a notification is recorded without starting one",
    f"{len(multi)} turns; {len(multi[0]['notifications']) if multi else 0} notification(s) in turn 1",
)

# --- hook injections are attributed to their event ----------------------------------------
inj = turns_from([
    human("do a thing"),
    injection("UserPromptSubmit", "House rules reminder: ..."),
    injection("PostToolUse", "harvest: A.cs - no blocks"),
])
check(
    inj and len(inj[0]["injections"]) == 2
    and {i[0] for i in inj[0]["injections"]} == {"UserPromptSubmit", "PostToolUse"},
    "hook injections are recorded against the event that produced them",
    f"events: {sorted(i[0] for i in inj[0]['injections']) if inj else 'none'}",
)

# --- the rendered ledger surfaces the continuation, not just the data structure ------------
path = write_transcript([
    human("push it"), stop_feedback(),
    tool_use("Bash", {"command": "git push -u origin feature"}),
])
try:
    records, _ = session_ledger.load(path)
    body = session_ledger.render(session_ledger.build_turns(records), path, "test-session", 0)
finally:
    os.unlink(path)
check(
    "## Actions taken after the visible reply" in body
    and "git push" in body.split("## Every turn")[0]
    and "**1**" in body,
    "the rendered ledger puts the continuation in its own section, above everything else",
    "the section exists, names the push, and the header counts it",
)

# --- every failure path is loud and non-zero ----------------------------------------------
for args, label in (
    (["--transcript", "/nonexistent-transcript.jsonl"], "a transcript that does not exist"),
    (["--session", "no-such-session-anywhere"], "a session id that matches nothing"),
):
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "session_ledger.py")] + args,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    err = proc.stderr.decode("utf-8", "replace")
    check(
        proc.returncode != 0 and "session_ledger:" in err,
        f"session_ledger given {label} says so and exits non-zero",
        f"exit {proc.returncode}, stderr: {err.strip()[:90] or '(silent - BAD)'}",
    )

bad = write_transcript(["not json at all", "{{{"])
try:
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "session_ledger.py"), "--transcript", bad],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
finally:
    os.unlink(bad)
check(
    proc.returncode != 0 and "zero records" in proc.stderr.decode("utf-8", "replace"),
    "session_ledger given an unparseable transcript names the problem and exits non-zero",
    f"exit {proc.returncode}, stderr: {proc.stderr.decode('utf-8', 'replace').strip()[:90]}",
)

# --- clean_install_test: the check that was wrong for as long as it existed ----------------
# It asserted the enabledPlugins KEY was absent, contradicting the strip step above it, which
# deliberately leaves the key so unrelated plugins survive. It passed only on a machine with no
# settings.json at all - which is why running the script twice was what exposed it.
PID = clean_install_test.PLUGIN_ID
MKT = clean_install_test.MARKETPLACE
cases = [
    ({"enabledPlugins": {}}, False, "the empty key the CLI's uninstall leaves behind"),
    ({"enabledPlugins": {"other@mkt": True}}, False, "an unrelated plugin still registered"),
    ({}, False, "a settings file with neither key"),
    (None, False, "no settings at all"),
    ({"enabledPlugins": {PID: True}}, True, "our plugin genuinely still registered"),
    ({"extraKnownMarketplaces": {MKT: {}}}, True, "our marketplace genuinely still registered"),
]
wrong = [
    why for settings, should_be_dirty, why in cases
    if bool(clean_install_test.residual_config(settings)) != should_be_dirty
]
check(
    not wrong,
    "clean_install_test calls a machine dirty only when OUR entries remain",
    f"{len(cases)} states classified correctly" if not wrong else f"wrong for: {'; '.join(wrong)}",
)

# --- measure_footprint: the reminder and the trace must not be collapsed -------------------
# reminder_text() folds them into one value, which is right for sections 1-3 and is how the
# harvest trace shipped unmeasured in 2.13.0. split_output() is what keeps them apart.
both = json.dumps({
    "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "REMINDER"},
    "systemMessage": "TRACE",
})
r, t = measure_footprint.split_output(both)
check(
    r == "REMINDER" and t == "TRACE",
    "split_output keeps a reminder and a trace apart when one call emits both",
    f"reminder={r!r}, trace={t!r}",
)
r2, t2 = measure_footprint.split_output(json.dumps({"systemMessage": "TRACE ONLY"}))
r3, t3 = measure_footprint.split_output("not json")
check(
    (r2, t2) == ("", "TRACE ONLY") and (r3, t3) == ("not json", ""),
    "split_output handles a trace-only call and a non-JSON stdout without raising",
    f"trace-only={t2!r}; non-json reminder={r3!r}",
)
r4, _ = measure_footprint.split_output(json.dumps({
    "hookSpecificOutput": {"permissionDecision": "ask", "permissionDecisionReason": "BECAUSE"}}))
check(
    r4 == "BECAUSE",
    "split_output counts guard's permission prompt as the reminder it is",
    f"reminder={r4!r}",
)

# --- install.py's upgrade path ----------------------------------------------------------------
# tools/ had no coverage of install.py at all, and the gap cost something concrete: the command
# sequence could install the plugin on a fresh machine and was UNABLE to upgrade one that already
# had it. `claude plugin marketplace add` answers "already on disk" for a marketplace the device
# has seen before and does not re-fetch, so the cached clone stayed on the old commit and
# `plugin update` reported "already at the latest version" naming the OLD version - a confident
# wrong answer. Reproduced against the real CLI before the fix: a stale cache registered 2.17.0;
# with `marketplace update` inserted, the same stale cache reported "updated from 2.17.0 to
# 2.18.0". These checks pin the ORDER, which is the load-bearing part, without shelling out to
# the claude CLI or touching a real machine's config.
steps = install.install_steps()
argvs = [argv for argv, _ in steps]
flat = [" ".join(a) for a in argvs]


def step_index(*words):
    for i, a in enumerate(argvs):
        if all(w in a for w in words):
            return i
    return -1


i_add = step_index("marketplace", "add")
i_mupd = step_index("marketplace", "update")
i_inst = step_index("install")
i_pupd = step_index("update", install.PLUGIN_ID)

check(
    i_mupd != -1,
    "install.py refreshes the marketplace clone, not just declares it",
    f"marketplace update present at step {i_mupd + 1} of {len(steps)}" if i_mupd != -1
    else "NO `plugin marketplace update` - an existing install can never be upgraded",
)

check(
    i_add != -1 and i_mupd != -1 and i_add < i_mupd,
    "marketplace add runs before marketplace update",
    f"add at {i_add + 1}, update at {i_mupd + 1} - add declares it, update re-fetches it",
)

check(
    i_mupd != -1 and i_pupd != -1 and i_mupd < i_pupd,
    "the clone is refreshed before the plugin registration is re-pointed",
    f"marketplace update at {i_mupd + 1}, plugin update at {i_pupd + 1} - reversed, the "
    "registration would be re-pointed at a stale clone",
)

check(
    i_inst != -1 and i_pupd != -1 and i_inst < i_pupd,
    "plugin install runs before plugin update",
    f"install at {i_inst + 1}, update at {i_pupd + 1} - install is a no-op once registered, "
    "update is the verb that re-points it",
)

check(
    all(a and a[0] == "plugin" for a in argvs),
    "every install step is a `claude plugin` subcommand",
    f"{len(argvs)} steps, all under `plugin`: {flat}",
)

check(
    all(isinstance(msg, str) and msg.strip() for _, msg in steps),
    "every install step carries a failure message, so none can fail silently",
    f"{len(steps)} steps, {len(steps)} non-empty messages",
)

check(
    install.MARKETPLACE in " ".join(flat) and install.REPO in " ".join(flat),
    "the steps name this repo's marketplace and remote, not a hardcoded copy",
    f"marketplace={install.MARKETPLACE!r}, repo={install.REPO!r}",
)

# The docstring is the only place the reasoning lives, and the reasoning is the reason the
# order cannot be rearranged by someone tidying up. Pin that it still says why.
doc = (install.install_steps.__doc__ or "").lower()
check(
    "already on disk" in doc and "re-fetch" in doc,
    "install_steps explains why the order matters, not just what the order is",
    "the docstring names the add-does-not-re-fetch trap the order exists to avoid",
)

# --- update.bat states the same four commands, in the same order -------------------------------
# The order is now written in TWO places: install_steps() and the double-clickable
# tools/update.bat. That is a restatement, and this repo's whole recent history is restatements
# drifting apart unnoticed - the delegate reminder lost a load-bearing sentence exactly this way.
# So the two are bound here rather than trusted to stay in step. update.bat is deliberately NOT
# generated from install_steps(): it must run with no Python at all, which is the point of it.
BAT = os.path.join(HERE, "update.bat")
bat_present = os.path.isfile(BAT)
bat_raw = open(BAT, "rb").read() if bat_present else b""
bat_text = bat_raw.decode("utf-8", "replace")

# Strip the `call ` prefix and the trailing report-only `plugin list`, which is not an
# install step and deliberately has no counterpart in install_steps().
bat_cmds = [
    line.strip()[len("call claude "):]
    for line in bat_text.splitlines()
    if line.strip().startswith("call claude plugin")
    and line.strip() != "call claude plugin list"
]

check(
    bat_present,
    "tools/update.bat exists, so the plugin can be updated by double-click",
    f"{BAT} present" if bat_present else "update.bat is missing",
)

check(
    bat_cmds == flat,
    "update.bat issues exactly install_steps(), in the same order",
    f"bat={bat_cmds}" if bat_cmds != flat else
    f"both run the same {len(flat)} commands in the same order",
)

# Running a .cmd from a .bat without `call` hands control over and never returns, so the
# script would stop dead after the first command. On Windows the claude CLI IS claude.cmd.
bare = [
    line.strip() for line in bat_text.splitlines()
    if line.strip().startswith("claude ")
]
check(
    not bare,
    "every claude invocation in update.bat uses `call`",
    "without it the batch file stops after the first command, since claude is claude.cmd"
    if not bare else f"bare invocations that will end the script early: {bare}",
)

# Double-clicked from Explorer the window closes the instant the script ends, so without a
# pause the output - including any failure - is unreadable.
check(
    "pause" in bat_text.lower(),
    "update.bat pauses before exiting, so a double-click is readable",
    "pause present; without it the console closes before the result can be read",
)

check(
    "errorlevel" in bat_text.lower() and ":failed" in bat_text,
    "update.bat checks every command and reports a failure rather than pressing on",
    "errorlevel checks and a :failed branch are present",
)

# cmd.exe mis-parses an LF-only batch file with goto labels. .gitattributes pins eol=crlf;
# this asserts the committed bytes actually are CRLF, since the attribute alone is a promise.
CRLF = b"\r\n"
LF = b"\n"
n_crlf = bat_raw.count(CRLF)
n_bare_lf = bat_raw.count(LF) - n_crlf
check(
    bat_present and n_crlf > 0 and n_bare_lf == 0,
    "update.bat is CRLF throughout, which cmd.exe needs for its goto labels",
    "{0} CRLF line endings, {1} bare LF".format(n_crlf, n_bare_lf),
)

check(
    "*.bat text eol=crlf" in open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read(),
    ".gitattributes pins *.bat to CRLF so checkout does not depend on core.autocrlf",
    "the attribute is declared, so a Windows clone gets CRLF regardless of local git config",
)

print()
print("-" * 32)
if FAILURES:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed. See the FAIL lines above.")
else:
    print(f"RESULT: PASS - all {STEP} checks passed. The tools behave as written.")
print()
print("Not covered here: anything that shells out to the claude CLI or changes a real")
print("machine's config. clean_install_test.py's strip and install steps are proven by")
print("running that script; what is covered is the decision logic lifted out of it.")
sys.exit(1 if FAILURES else 0)
