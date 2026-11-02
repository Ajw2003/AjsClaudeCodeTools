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
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import check_plugin_version_bump  # noqa: E402
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
# Why this exists and how the fix was reproduced against the real CLI before being trusted:
# docs/6-decisions/Decisions.md, "Reproduce the install-upgrade fix against the real CLI before trusting it".
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
# Why update.bat restates rather than calls install_steps(), and why the two are bound here:
# doc-ref 20e2 docs/4-systems/plugin-distribution.md (Invariants).
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

_owner = measure_footprint.event_plugins(measure_footprint.repo_plugin_dirs())
check(
    all(_owner.get(e) == "rule-enforcement" for e in ("inject", "showrule", "scope", "subagentrules"))
    and _owner.get("guard") == "house-rules",
    "measure_footprint points each event at the plugin whose hooks.json declares it",
    f"inject/showrule/scope/subagentrules -> {_owner.get('inject')}, guard -> {_owner.get('guard')}",
)

check(
    "*.bat text eol=crlf" in open(os.path.join(ROOT, ".gitattributes"), encoding="utf-8").read(),
    ".gitattributes pins *.bat to CRLF so checkout does not depend on core.autocrlf",
    "the attribute is declared, so a Windows clone gets CRLF regardless of local git config",
)

# --- check_plugin_version_bump.decide(): pure policy, no git, no subprocess ----------------
decide_cases = [
    ([], "1.0.0", "1.0.0", True, "no plugin files"),
    (["claude-house-rules/plugins/house-rules/rules/house-rules.md"], "1.0.0", "1.0.0",
     False, "changed, version unmoved"),
    (["claude-house-rules/plugins/house-rules/rules/house-rules.md"], "1.0.0", "1.1.0",
     True, "changed, version increased"),
    (["claude-house-rules/plugins/house-rules/rules/house-rules.md"], "1.1.0", "1.0.0",
     False, "changed, version decreased"),
    (["README.md"], "1.0.0", "1.0.0", True, "non-plugin file changed, version unmoved"),
    (["CLAUDE.md"], "1.0.0", "1.0.0", False, "root CLAUDE.md changed, version unmoved"),
    (["CLAUDE.md"], "1.0.0", "1.1.0", True, "root CLAUDE.md changed, version increased"),
    (["docs/README.md"], "1.0.0", "1.0.0", False, "docs/ file changed, version unmoved"),
    (["docs/README.md"], "1.0.0", "1.1.0", True, "docs/ file changed, version increased"),
]
decide_wrong = []
for changed, old, new, expect_ok, label in decide_cases:
    ok_, msg_ = check_plugin_version_bump.decide(changed, old, new)
    if ok_ != expect_ok:
        decide_wrong.append(f"{label}: expected ok={expect_ok}, got ok={ok_} ({msg_!r})")
check(
    not decide_wrong,
    "check_plugin_version_bump.decide() gates on a real increase, not just a change",
    f"{len(decide_cases)} cases matched" if not decide_wrong else "; ".join(decide_wrong),
)

invalid_version_raised = False
try:
    check_plugin_version_bump.decide(
        ["claude-house-rules/plugins/house-rules/rules/house-rules.md"], "1.0.0", "not-a-version",
    )
except check_plugin_version_bump.VersionBumpCheckError:
    invalid_version_raised = True
check(
    invalid_version_raised,
    "decide() names an unparseable version as a failure rather than silently passing",
    "VersionBumpCheckError raised for a non-semver version string" if invalid_version_raised
    else "no exception raised - an unparseable version was silently accepted",
)

# --- check_plugin_version_bump: a real end-to-end case against actual git ------------------
# The pure decide() tests above never touch changed_paths()/plugin_version_at() at all - this
# repo's own testing rule ("against the mechanism, not my model of it") applies here precisely
# because the original bug was a mismatch between "how a version string is compared" as assumed
# versus how `claude plugin update`'s real gate behaves.
git_fixture = tempfile.mkdtemp(prefix="version-bump-fixture-")
try:
    def run_git(*args):
        proc = subprocess.run(
            ["git"] + list(args), cwd=git_fixture,
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {args} failed: {proc.stderr}")
        return proc.stdout

    run_git("init", "-q")
    run_git("config", "user.email", "test@example.com")
    run_git("config", "user.name", "Test")

    plugin_json_rel = check_plugin_version_bump.PLUGIN_JSON_PATH
    plugin_json_abs = os.path.join(git_fixture, plugin_json_rel)
    os.makedirs(os.path.dirname(plugin_json_abs), exist_ok=True)
    with open(plugin_json_abs, "w", encoding="utf-8") as f:
        json.dump({"name": "house-rules", "version": "1.0.0"}, f)
    run_git("add", ".")
    run_git("commit", "-q", "-m", "base")
    run_git("branch", "-q", "-f", "base-ref")

    rules_rel = "claude-house-rules/plugins/house-rules/rules/house-rules.md"
    rules_abs = os.path.join(git_fixture, rules_rel)
    os.makedirs(os.path.dirname(rules_abs), exist_ok=True)
    with open(rules_abs, "w", encoding="utf-8") as f:
        f.write("a new rule\n")
    with open(plugin_json_abs, "w", encoding="utf-8") as f:
        json.dump({"name": "house-rules", "version": "1.1.0"}, f)
    run_git("add", ".")
    run_git("commit", "-q", "-m", "bump")

    real_cwd = os.getcwd()
    os.chdir(git_fixture)
    try:
        real_changed = check_plugin_version_bump.changed_paths("base-ref", "HEAD")
        real_old = check_plugin_version_bump.plugin_version_at("base-ref")
        real_new = check_plugin_version_bump.plugin_version_at("HEAD")
    finally:
        os.chdir(real_cwd)

    real_ok, real_msg = check_plugin_version_bump.decide(real_changed, real_old, real_new)
    check(
        rules_rel in real_changed and real_old == "1.0.0" and real_new == "1.1.0" and real_ok,
        "changed_paths()/plugin_version_at() against real git match a real bumped commit",
        f"changed={real_changed}, old={real_old}, new={real_new}, ok={real_ok} ({real_msg})",
    )

    bad_ref_raised = False
    try:
        check_plugin_version_bump.plugin_version_at("this-ref-does-not-exist")
    except check_plugin_version_bump.VersionBumpCheckError:
        bad_ref_raised = True
    check(
        bad_ref_raised,
        "plugin_version_at() fails loud on a bad ref rather than returning None",
        "VersionBumpCheckError raised for a nonexistent ref" if bad_ref_raised
        else "no exception raised for a bad ref",
    )
finally:
    shutil.rmtree(git_fixture, ignore_errors=True)

# --- check_plugin_version_bump: every plugin is gated (main(), real git, temp repo) ----------
bump_script = os.path.join(ROOT, "tools", "check_plugin_version_bump.py")
multi = tempfile.mkdtemp(prefix="version-bump-multi-")
try:
    def mgit(*args):
        proc = subprocess.run(["git"] + list(args), cwd=multi, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git {args} failed: {proc.stderr}")
    def mwrite(rel, content):
        full = os.path.join(multi, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    def mplugin(name, version):
        mwrite(f"claude-house-rules/plugins/{name}/.claude-plugin/plugin.json",
               json.dumps({"name": name, "version": version}))
    def mrun():
        proc = subprocess.run([sys.executable, bump_script, "--base", "base-ref", "--head", "HEAD"],
                              cwd=multi, capture_output=True, text=True)
        return proc.returncode, proc.stdout
    mgit("init", "-q"); mgit("config", "user.email", "t@example.com"); mgit("config", "user.name", "T")
    mplugin("house-rules", "1.0.0"); mplugin("rule-enforcement", "0.1.0")
    mgit("add", "."); mgit("commit", "-q", "-m", "base"); mgit("branch", "-q", "-f", "base-ref")

    # a second plugin changed without a bump fails, and the output names it
    mwrite("claude-house-rules/plugins/rule-enforcement/scripts/x.py", "x\n")
    mgit("add", "."); mgit("commit", "-q", "-m", "change")
    code_a, out_a = mrun()
    check(
        code_a == 1 and "rule-enforcement: FAIL" in out_a and "house-rules: PASS" in out_a,
        "version-bump check fails a second plugin changed without a bump and names each verdict",
        out_a.strip().replace("\n", " | "),
    )

    # bumping it passes; a brand-new plugin passes as new
    mplugin("rule-enforcement", "0.1.1"); mplugin("fresh-plugin", "0.1.0")
    mwrite("claude-house-rules/plugins/fresh-plugin/scripts/y.py", "y\n")
    mgit("add", "."); mgit("commit", "-q", "-m", "bump and new")
    code_b, out_b = mrun()
    check(
        code_b == 0 and "fresh-plugin: PASS - new plugin" in out_b and "rule-enforcement: PASS" in out_b,
        "version-bump check passes a bumped plugin and a plugin that is new on the base",
        out_b.strip().replace("\n", " | "),
    )

    # house-rules behaviour unchanged: docs/ alone still needs a house-rules bump, and does not
    # count for another plugin
    mwrite("docs/a.md", "doc\n")
    mgit("add", "."); mgit("commit", "-q", "-m", "docs")
    code_c, out_c = mrun()
    check(
        code_c == 1 and "house-rules: FAIL" in out_c and "rule-enforcement: PASS" in out_c,
        "version-bump check: docs/ still needs a house-rules bump and counts for no other plugin",
        out_c.strip().replace("\n", " | "),
    )
    mplugin("house-rules", "1.0.1")
    mgit("add", "."); mgit("commit", "-q", "-m", "bump hr")
    code_d, out_d = mrun()
    check(code_d == 0, "version-bump check passes once house-rules is bumped for a docs/ change",
          out_d.strip().replace("\n", " | "))
finally:
    shutil.rmtree(multi, ignore_errors=True)

# --- install.py's hash-verify-and-self-heal step --------------------------------------------
def _make_tree(root, files):
    os.makedirs(root, exist_ok=True)
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


heal_root = tempfile.mkdtemp(prefix="install-self-heal-")
try:
    src_dir = os.path.join(heal_root, "source")
    dst_dir = os.path.join(heal_root, "installed")
    _make_tree(src_dir, {"a.txt": "same", "b.txt": "same"})
    _make_tree(dst_dir, {"a.txt": "same", "b.txt": "same"})

    reinstall_calls = []
    matched = install.verify_and_self_heal(
        src_dir, dst_dir, lambda: reinstall_calls.append(1),
        ok=lambda m: None, bad=lambda m: None, info=lambda m: None,
    )
    check(
        matched and not reinstall_calls,
        "install.py's self-heal step does not reinstall when the cache already matches source",
        f"matched={matched}, reinstall attempted={bool(reinstall_calls)}",
    )

    # Now make them differ, and give the reinstall a fake that actually fixes it.
    _make_tree(dst_dir, {"a.txt": "STALE", "b.txt": "same"})
    reinstall_calls = []

    def fake_reinstall_fixes_it():
        reinstall_calls.append(1)
        _make_tree(dst_dir, {"a.txt": "same", "b.txt": "same"})

    healed = install.verify_and_self_heal(
        src_dir, dst_dir, fake_reinstall_fixes_it,
        ok=lambda m: None, bad=lambda m: None, info=lambda m: None,
    )
    check(
        healed and len(reinstall_calls) == 1,
        "install.py's self-heal step reinstalls on a mismatch and re-verifies",
        f"healed={healed}, reinstall attempted {len(reinstall_calls)} time(s)",
    )

    # And when the reinstall does NOT fix it, the step must report failure, not silently pass.
    _make_tree(dst_dir, {"a.txt": "STILL STALE", "b.txt": "same"})
    bad_messages = []
    still_broken = install.verify_and_self_heal(
        src_dir, dst_dir, lambda: None,
        ok=lambda m: None, bad=lambda m: bad_messages.append(m), info=lambda m: None,
    )
    check(
        not still_broken and bad_messages,
        "install.py's self-heal step reports failure loudly when the reinstall does not fix it",
        f"still_broken(ok)={still_broken}, bad() called {len(bad_messages)} time(s)",
    )
finally:
    shutil.rmtree(heal_root, ignore_errors=True)

# --- install.py's settings step (attribution, #133) ------------------------------------------
def _run_settings(initial, skip=()):
    d = tempfile.mkdtemp(prefix="install-settings-")
    path = os.path.join(d, "settings.json")
    if initial is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(initial)
    msgs = {"ok": [], "bad": []}
    install.apply_settings(d, set(skip), msgs["ok"].append, msgs["bad"].append, lambda m: None)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = None
    shutil.rmtree(d, ignore_errors=True)
    return text, msgs


_want = {"commit": "Committed by AJ's agent", "pr": "Opened by AJ's agent", "sessionUrl": False}
_t, _m = _run_settings(None)
_j = json.loads(_t)
check(_j.get("attribution") == _want and not _m["bad"],
      "install.py writes attribution into a missing settings file", f"got {_j.get('attribution')!r}")
_t, _m = _run_settings(json.dumps({"theme": "dark", "hooks": {"a": 1}}))
_j = json.loads(_t)
check(_j.get("attribution") == _want and _j.get("theme") == "dark" and _j.get("hooks") == {"a": 1},
      "install.py writes attribution and preserves every other key", f"got {_j!r}")
_t, _m = _run_settings(json.dumps({"attribution": {"commit": "Co-Authored-By: Claude", "pr": "x"}}))
check(json.loads(_t).get("attribution") == _want,
      "install.py replaces a different existing attribution exactly", f"got {_t!r}")
_t, _m = _run_settings(json.dumps({"attribution": {"commit": "mine"}}), skip=("attribution",))
check(json.loads(_t).get("attribution") == {"commit": "mine"},
      "install.py --no-attribution leaves attribution alone", f"got {_t!r}")
_t, _m = _run_settings(None)
check(any("reads back attribution" in x for x in _m["ok"]),
      "install.py reads attribution back after writing", f"ok lines {_m['ok']!r}")
_t, _m = _run_settings("{not json")
check(_t == "{not json" and _m["bad"],
      "install.py reports a settings file that does not parse and does not overwrite it",
      f"file now {_t!r}, bad {_m['bad']!r}")

# --- diff_parts: a file's changes split into the parts they belong to (#242) ---------------
import diff_parts as _dp
_dpr = tempfile.mkdtemp(prefix="diff-parts-")
subprocess.run(["git", "init", "-q", _dpr], check=True)
_dpg = ["git", "-C", _dpr, "-c", "user.name=t", "-c", "user.email=t@t"]
with open(os.path.join(_dpr, "m.py"), "w") as _f:
    _f.write("def a():\n    return 1\n\n\ndef b():\n    return 2\n")
subprocess.run(_dpg + ["add", "."], check=True)
subprocess.run(_dpg + ["commit", "-qm", "one"], check=True)
with open(os.path.join(_dpr, "m.py"), "w") as _f:
    _f.write("def a():\n    return 1\n\n\ndef b():\n    return 3\n\n\n# why c exists\ndef c():\n    return 4\n")
subprocess.run(_dpg + ["commit", "-qam", "two"], check=True)
_dpo = _dp.parts(_dpr, "HEAD~1", "HEAD", "m.py")
_dpn = subprocess.run(["git", "-C", _dpr, "diff", "--numstat", "HEAD~1", "HEAD"], capture_output=True, text=True).stdout.split()
_dpp = {p[0]: (p[1], p[2]) for p in _dpo["parts"]}
check([_dpo["added"], _dpo["removed"]] == [int(_dpn[0]), int(_dpn[1])],
      "diff_parts: the totals equal git diff --numstat", f"got {_dpo['added']} {_dpo['removed']}, git {_dpn[:2]}")
check(_dpp.get("b") == (1, 1) and _dpp.get("c") == (5, 0),
      "diff_parts: a changed line belongs to its function, and a comment above a function to that function",
      f"got {_dpp!r}")

# --- sync_library.py: --check passes on a matching copy, fails on a changed one (#439) ------
import sync_library as _sl
_slr = tempfile.mkdtemp(prefix="sync-library-")
try:
    _make_tree(os.path.join(_slr, _sl.SOURCE), {"__init__.py": "", "a.py": "A = 1\n"})
    _sl.sync(_slr)
    check(_sl.problems(_slr) == [] and _sl.main(["--check", "--root", _slr]) == 0,
          "sync_library --check passes on a matching copy", f"problems={_sl.problems(_slr)!r}")
    _slt = os.path.join(_slr, _sl.TARGETS[0], "a.py")
    with open(_slt, "w") as _f:
        _f.write("A = 2\n")
    _slp = _sl.problems(_slr)
    check(_sl.main(["--check", "--root", _slr]) == 1 and len(_slp) == 1 and "a.py" in _slp[0],
          "sync_library --check fails naming a changed file", f"problems={_slp!r}")
    os.remove(_slt)
    _slp = _sl.problems(_slr)
    check(len(_slp) == 1 and _slp[0].startswith("missing") and "a.py" in _slp[0],
          "sync_library --check fails naming a missing file", f"problems={_slp!r}")
finally:
    shutil.rmtree(_slr, ignore_errors=True)

# --- replay_hooks.py: the diff and the classes, on a tiny fake pair of plugins (#452) -------
import replay_hooks as _rh


def _comb(**kw):
    c = {f: [] for f in _rh.FIELDS}
    c.update(kw)
    return c


check(_rh.compare(_comb(context=["A one. B two."]), _comb(context=["A one. B two."])) == [],
      "replay_hooks: identical outputs give no difference", "expected []")
_d = _rh.compare(_comb(context=["Rules text. Link sentence."]), _comb(context=["Rules text.", "Link sentence."]))
check(len(_d) == 1 and _d[0]["cls"].startswith("block boundary"),
      "replay_hooks: the same text split into more blocks is a block-boundary difference", f"got {_d!r}")
_d = _rh.compare(_comb(context=["Keep this. `HOUSE_RULES_LOOP=off` turns it off."]), _comb(context=["Keep this."]))
check(len(_d) == 1 and _d[0]["side"] == "old" and _d[0]["cls"] == "text no longer mentions removed switches",
      "replay_hooks: a dropped off-switch sentence is explained, not hidden", f"got {_d!r}")
_d = _rh.compare(_comb(context=["Paths are under <HR>/rules."]), _comb(context=["Paths are under <RE>/rules."]))
check([x["cls"] for x in _d] == ["rule loading moved", "rule loading moved"],
      "replay_hooks: a changed plugin root token is 'rule loading moved'", f"got {_d!r}")
_d = _rh.compare(_comb(blocks=["block: - commit: Files are committed."]), _comb(blocks=["block: - commit (block 1 of 3): Files are committed."]))
check([x["cls"] for x in _d] == ["three blocks then lock"] * 2,
      "replay_hooks: block 1 of 3 against block-once is 'three blocks then lock'", f"got {_d!r}")
_d = _rh.compare(_comb(stderr=["house-rules design-loop lock: could not split a statement (unbalanced quotes) to look for sed -i / tee; skipping that statement."]), _comb())
check(len(_d) == 1 and _d[0]["cls"] == "2.74.2 bug fixed: quote-aware statement split",
      "replay_hooks: the old-only 'could not split a statement' stderr line is the quote-aware split fix", f"got {_d!r}")
_d = _rh.compare(_comb(), _comb(stderr=["house-rules design-loop lock: could not split a statement (unbalanced quotes) to look for sed -i / tee; skipping that statement."]))
check(len(_d) == 1 and _d[0]["cls"] == "UNEXPLAINED",
      "replay_hooks: the same line appearing only in NEW stays UNEXPLAINED", f"got {_d!r}")
_d = _rh.compare(_comb(stderr=["some other old noise"]), _comb())
check(len(_d) == 1 and _d[0]["cls"] == "UNEXPLAINED",
      "replay_hooks: any other old-only stderr line stays UNEXPLAINED", f"got {_d!r}")
_d = _rh.compare(_comb(decisions=["deny: refused one"]), _comb(decisions=["allow: fine"]))
check(sorted(x["cls"] for x in _d) == ["UNEXPLAINED", "UNEXPLAINED"],
      "replay_hooks: a changed decision no rule covers is UNEXPLAINED", f"got {_d!r}")
check(_rh.matches({"matcher": "Write|Edit"}, "Edit") and not _rh.matches({"matcher": "Write|Edit"}, "MultiEdit")
      and _rh.matches({"matcher": ""}, "") and not _rh.matches({"matcher": "Bash"}, ""),
      "replay_hooks: a matcher is a whole-name regex, empty matches everything", "matcher results wrong")
_p = _rh.parse_output(0, json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                      "permissionDecisionReason": "no"}, "systemMessage": "sm"}), "")
check(_p["decisions"] == ["deny: no"] and _p["system"] == ["sm"] and not _p["misc"],
      "replay_hooks: a deny decision and a systemMessage are read from hook JSON", f"got {_p!r}")
_p = _rh.parse_output(2, "", "refused on stderr")
check(_p["stderr"] == ["refused on stderr"] and _p["misc"] == ["exit code 2"],
      "replay_hooks: an exit-2 stderr refusal is kept, with its exit code", f"got {_p!r}")

_rhr = tempfile.mkdtemp(prefix="replay-fake-")
try:
    def _fake(root, name, outputs):
        d = os.path.join(root, name)
        os.makedirs(os.path.join(d, "hooks"))
        os.makedirs(os.path.join(d, "scripts"))
        groups = [{"hooks": [{"type": "command", "command": 'sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" %s' % ev, "timeout": 10}]}
                  for ev in outputs]
        with open(os.path.join(d, "hooks", "hooks.json"), "w") as f:
            json.dump({"hooks": {"UserPromptSubmit": groups}}, f)
        with open(os.path.join(d, "scripts", "run.sh"), "w") as f:
            f.write('cat >/dev/null\ncase "$1" in\n')
            for ev, text in outputs.items():
                f.write("%s) printf '%%s' '%s';;\n" % (ev, json.dumps(
                    {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}})))
            f.write("esac\n")
        return d

    _o = os.path.join(_rhr, "o")
    _n = os.path.join(_rhr, "n")
    _fake(_o, "alpha", {"one": "Shared. `HOUSE_RULES_LOOP=off` turns it off."})
    _fake(_n, "alpha", {"one": "Shared."})
    _fake(_n, "beta", {"two": "A surprise nobody approved."})
    _op, _np = _rh.load_plugins(_o), _rh.load_plugins(_n)
    _sc = [x for x in _rh.scenarios() if x["name"] == "UserPromptSubmit ordinary prompt"]
    check(_rh.coverage(_op, _sc, "OLD") == [] and _rh.coverage(_np, _sc, "NEW") == []
          and len(_rh.coverage(_np, [], "NEW")) == 2,
          "replay_hooks: coverage names the hook entries no scenario reaches", "coverage wrong")
    _old, _new = _rh.replay(_op, _np, _sc, os.path.join(_rhr, "w"))
    _rows, _counts, _ident = _rh.full_report(_old, _new, _sc)
    _k = _sc[0]["name"]
    check(_old[_k]["ran"] == ["alpha:one"] and sorted(_new[_k]["ran"]) == ["alpha:one", "beta:two"]
          and _counts == {"text no longer mentions removed switches": 1, "UNEXPLAINED": 1} and _ident == 0,
          "replay_hooks: a fake pair is replayed per plugin and each difference is classified",
          f"ran {_old[_k]['ran']} / {_new[_k]['ran']}, counts {dict(_counts)!r}")
    _txt = _rh.render(_rows, _counts, _ident, _old, _new, [], "fake", ("alpha 0", "alpha, beta"))
    check("A surprise nobody approved." in _txt.split("## Every difference")[0],
          "replay_hooks: the report quotes every UNEXPLAINED difference in full", "quote missing before the full list")
finally:
    shutil.rmtree(_rhr, ignore_errors=True)

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
