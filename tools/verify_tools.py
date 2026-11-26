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
import time

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

# --- #477 (A8): a failed settings write leaves the old settings.json whole ---
import tempfile
_a8 = tempfile.mkdtemp(prefix="install-a8-")
with open(os.path.join(_a8, "settings.json"), "w", encoding="utf-8") as f:
    json.dump({"mine": "keep me"}, f)
_real_dump = install.json.dump
def _a8_fail(obj, f, **kw):
    f.write('{"half": ')
    raise OSError("disk full")
install.json.dump = _a8_fail
try:
    install.apply_settings(_a8, set(), lambda m: None, lambda m: None, lambda m: None)
except OSError:
    pass  # the failure this case simulates
finally:
    install.json.dump = _real_dump
with open(os.path.join(_a8, "settings.json"), encoding="utf-8") as f:
    _a8_after = json.load(f)
check(_a8_after == {"mine": "keep me"}, "install.py: a failed settings write keeps the old settings.json",
      "after a simulated disk-full write the file read back as %r" % (_a8_after,))


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


_want = {"commit": "Committed by Edens Agent", "pr": "Opened by Edens Agent", "sessionUrl": False}
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

# --- #482 (A13): the installer's file check ignores the cache files running the hooks writes ---
from _plugin_sync import tree_hash, diff_trees  # noqa: E402
_ts = tempfile.mkdtemp(); _td = tempfile.mkdtemp()
for _root in (_ts, _td):
    open(os.path.join(_root, "a.py"), "w").write("x = 1\n")
os.makedirs(os.path.join(_td, "__pycache__"))
open(os.path.join(_td, "__pycache__", "a.cpython-313.pyc"), "wb").write(b"\0")
open(os.path.join(_td, ".python-cache"), "w").write("python3\n")
check(diff_trees(tree_hash(_ts), tree_hash(_td)) == [],
      "A13: tree_hash ignores __pycache__, .pyc and .python-cache", f"diff {diff_trees(tree_hash(_ts), tree_hash(_td))}")
shutil.rmtree(_ts, True); shutil.rmtree(_td, True)

# --- #482 (A16): a failed reinstall says the plugin is now uninstalled, and how to put it back ---
_fu = tempfile.mkdtemp(prefix="force-update-")
_fb = os.path.join(_fu, "bin"); os.makedirs(_fb)
if os.name == "nt":  # Windows cannot run a #!/bin/sh file as `claude`; a .cmd stub is found by shutil.which
    with open(os.path.join(_fb, "claude.cmd"), "w") as _f:
        _f.write('@echo off\r\nif "%2"=="install" exit /b 1\r\nexit /b 0\r\n')
else:
    with open(os.path.join(_fb, "claude"), "w") as _f:
        _f.write('#!/bin/sh\n[ "$2" = install ] && exit 1\nexit 0\n')
    os.chmod(os.path.join(_fb, "claude"), 0o755)
_fr = subprocess.run([sys.executable, os.path.join(HERE, "force_update.py"), "--skip-marketplace-update"],
                     capture_output=True, text=True, timeout=60,
                     env=dict(os.environ, PATH=_fb + os.pathsep + os.environ["PATH"], HOME=_fu, USERPROFILE=_fu))
_fo = _fr.stdout + _fr.stderr
check(_fr.returncode != 0 and "UNINSTALLED" in _fo and "claude plugin install house-rules@aj-house-rules -y" in _fo,
      "A16: force_update says the plugin is UNINSTALLED when the reinstall fails, and the command to fix it",
      f"rc={_fr.returncode} out={_fo[-300:]!r}")
shutil.rmtree(_fu, True)

# --- #482 (A18): diff_parts counts a removed '---' line (a Markdown rule) as content ---
_ar = tempfile.mkdtemp(prefix="diff-parts-dash-")
subprocess.run(["git", "init", "-q", _ar], check=True)
_ag = ["git", "-C", _ar, "-c", "user.name=t", "-c", "user.email=t@t"]
with open(os.path.join(_ar, "m.md"), "w") as _f:
    _f.write("top\n---\nmiddle\nend\n")
subprocess.run(_ag + ["add", "."], check=True)
subprocess.run(_ag + ["commit", "-qm", "one"], check=True)
with open(os.path.join(_ar, "m.md"), "w") as _f:
    _f.write("top\nend\n")
subprocess.run(_ag + ["commit", "-qam", "two"], check=True)
_aro = _dp.parts(_ar, "HEAD~1", "HEAD", "m.md")
check(_aro["removed"] == 2, "A18: diff_parts counts a removed --- line, so removed equals git's numstat (2)",
      f"removed={_aro['removed']}")
shutil.rmtree(_ar, True)

# --- #482 (A20): verify_and_self_heal's one failure is counted once, by bad(), not again by main() ---
import inspect  # noqa: E402
_hb = []
_hs, _hd = tempfile.mkdtemp(), tempfile.mkdtemp()
open(os.path.join(_hs, "a.txt"), "w").write("new")
open(os.path.join(_hd, "a.txt"), "w").write("old")
install.verify_and_self_heal(_hs, _hd, lambda: None, ok=lambda m: None, bad=_hb.append, info=lambda m: None)
check(len(_hb) == 1 and "if not verify_and_self_heal(" not in inspect.getsource(install.main),
      "A20: a failed self-heal is one failure: bad() once, and main() adds none of its own",
      f"bad() called {len(_hb)} time(s)")
shutil.rmtree(_hs, True); shutil.rmtree(_hd, True)

# --- #532: use_branch.py switches the plugin to a branch build and back (needs network + claude) ---
def _use_branch_case():
    import use_branch
    if shutil.which("claude") is None or shutil.which("git") is None:
        print("SKIP  #532 use_branch: 'claude' or 'git' is not on PATH, so the switch was NOT tested.")
        return
    br = "AjsAgent/phase-3-handoff"
    ls = subprocess.run(["git", "ls-remote", "origin", f"refs/heads/{br}", "refs/heads/main"],
                        capture_output=True, text=True, timeout=60)
    heads = {l.split()[1]: l.split()[0][:7] for l in ls.stdout.splitlines()}
    if ls.returncode != 0 or len(heads) != 2:
        print(f"SKIP  #532 use_branch: git ls-remote origin failed or lacks {br}/main "
              f"({ls.stderr.strip() or 'no output'}), so the switch was NOT tested.")
        return
    old = os.environ.get("CLAUDE_CONFIG_DIR")
    cfg = tempfile.mkdtemp(prefix="use-branch-")
    os.environ["CLAUDE_CONFIG_DIR"] = cfg
    try:
        try:
            got = use_branch.switch(br)
        except SystemExit as e:
            print(f"SKIP  #532 use_branch: claude could not reach the repo ({e}), so the switch was NOT tested.")
            return
        want = heads[f"refs/heads/{br}"]
        check(got[0] == br and got[2][:7] == want, "#532: use_branch switches to the branch: ref and commit match origin",
              f"got ref={got[0]} commit={got[2]}, origin {br}={want}")
        got = use_branch.switch("main")
        want = heads["refs/heads/main"]
        check(got[0] is None and got[2][:7] == want, "#532: use_branch main: ref gone, commit equals origin/main",
              f"got ref={got[0]} commit={got[2]}, origin main={want}")
    finally:
        if old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = old
        shutil.rmtree(cfg, True)
_use_branch_case()

def _overnight_case():
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, "claude"), "w") as f:
            f.write('#!/bin/sh\necho "$HOUSE_RULES_UNATTENDED $ART_PIPELINE $*"\n')
        os.chmod(os.path.join(d, "claude"), 0o755)
        env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"])
        p = subprocess.run(["sh", os.path.join(HERE, "overnight.sh"), "--interactive", "-p", "hi"], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        check(p.returncode == 0 and p.stdout.strip() == "on unattended --dangerously-skip-permissions -p hi"
              and os.access(os.path.join(HERE, "overnight.sh"), os.X_OK),
              "overnight.sh --interactive exports both variables and runs claude once with the permission flag and its arguments",
              "got %r %r" % (p.stdout, p.stderr))
        with open(os.path.join(d, "claude"), "w") as f:
            f.write('#!/bin/sh\necho "loop=${HOUSE_RULES_LOOP:-unset}"\n')
        loops = {}
        for v in ("off", "unset"):
            e = dict(env)
            e.pop("HOUSE_RULES_LOOP", None)
            if v == "off":
                e["HOUSE_RULES_LOOP"] = "off"
            q = subprocess.run(["sh", os.path.join(HERE, "overnight.sh"), "--interactive"], env=e,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            loops[v] = (q.stdout.strip(), "design loop on" in q.stderr)
        with open(os.path.join(d, "claude"), "w") as f:
            f.write('#!/bin/sh\necho "$*" >> "$CALLS"\n')
        calls = {}
        for v in ("fresh", "resume"):
            cf = os.path.join(d, "calls-" + v)
            e = dict(env, CALLS=cf)
            e.pop("HOUSE_RULES_OVERNIGHT_RESUME", None)
            if v == "resume":
                e["HOUSE_RULES_OVERNIGHT_RESUME"] = "abc-123"
            subprocess.run(["sh", os.path.join(HERE, "overnight.sh"), "task"], env=e, cwd=d, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
            calls[v] = open(cf).read() if os.path.isfile(cf) else ""
        check("--session-id" in calls["fresh"] and calls["resume"] == "",
              "overnight.sh: HOUSE_RULES_OVERNIGHT_RESUME skips the first claude call (the loop then resumes that id)", "got %r" % (calls,))
        check(loops["off"] == ("loop=on", True) and loops["unset"] == ("loop=unset", False),
              "overnight.sh turns a leftover HOUSE_RULES_LOOP=off on and says so; an unset value stays unset", "got %r" % (loops,))
    finally:
        shutil.rmtree(d, True)
_overnight_case()

def _overnight_loop_case():
    sys.path.insert(0, os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts"))
    from house_rules import core
    d = tempfile.mkdtemp()
    try:
        repo = os.path.join(d, "repo")
        os.makedirs(os.path.join(repo, ".claude"))
        subprocess.run(["git", "init", "-q", repo], check=True)
        log = os.path.join(d, "log")
        stub = os.path.join(d, "bin", "claude")
        os.makedirs(os.path.dirname(stub))
        # every call rewrites the stage file: one step for the session id, stuck only on a --resume call unless NEVER_CLOSE is set
        with open(stub, "w") as f:
            f.write("""#!/bin/sh
echo "$CLAUDE_CODE_STOP_HOOK_BLOCK_CAP|$CLAUDE_SESSION_ID|$*" >> "$LOG"
python3 - "$REPO" "$CLAUDE_SESSION_ID" "${NEVER_CLOSE:-}" "$*" <<'PY'
import json, sys
repo, sid, never, argv = sys.argv[1:5]
stuck = "--resume" in argv and not never
rec = {"feature": "feature", "steps": [{"n": 1, "title": "Step 1", "check": "true", "state": "open", "stuck": stuck}]}
json.dump({"feature": "feature", "stage": "build", "skip": False, "approvals": [], "steps": {sid: rec}},
          open(repo + "/.claude/house-rules-loop.json", "w"))
PY
# #648: SF_KIND leaves a stopfailure file like the hook does (every call, or only the first when SF_FIRST is set)
if [ -n "${SF_KIND:-}" ] && { [ -z "${SF_FIRST:-}" ] || [ "${*#*--resume}" = "$*" ]; }; then
  mkdir -p "$CLAUDE_CONFIG_DIR/house-rules-steps"
  printf '{"error":"x","kind":"%s","reset_at":%s,"at":1}' "$SF_KIND" "${SF_RESET:-null}" > "$CLAUDE_CONFIG_DIR/house-rules-steps/stopfailure-$CLAUDE_SESSION_ID.json"
fi
""")
        os.chmod(stub, 0o755)
        script = os.path.join(HERE, "overnight.sh")
        def run(extra=None, cap=None):
            env = dict(os.environ, PATH=os.path.dirname(stub) + os.pathsep + os.environ["PATH"], LOG=log, REPO=repo,
                       CLAUDE_CONFIG_DIR=os.path.join(d, "cfg"))
            env.pop("CLAUDE_SESSION_ID", None)
            if cap:
                env["HOUSE_RULES_OVERNIGHT_NO_PROGRESS"] = cap
            env.update(extra or {})
            if os.path.exists(log):
                os.remove(log)
            p = subprocess.run(["sh", script, "do", "the", "work"], cwd=repo, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, timeout=40)
            return p, open(log).read().splitlines()
        resume = "[Subagent hand-back] Resume: you stopped before every step in the guarded step list was done. Carry on with the next open step. If there is no step list yet, you are still in the design loop: read the reviewer verdict, then the build plan, then build."
        p, lines = run()
        sid = lines[0].split("|")[1] if lines else ""
        check(len(lines) == 3 and sid and lines[0] == "1000|%s|-p do the work --session-id %s --dangerously-skip-permissions" % (sid, sid)
              and lines[1] == "1000|%s|-p %s --resume %s --dangerously-skip-permissions" % (sid, resume, sid)
              and lines[2].startswith("1000|%s|-p [Subagent hand-back] Final pass: the run is ending (all steps closed, but some are stuck: 1 STUCK: Step 1)." % sid)
              and not any("--continue" in l for l in lines),
              "overnight.sh loop: first call --session-id, one --resume with the same id and resume text, cap exported, no --continue",
              "got %r %r" % (lines, p.stderr))
        check(bool(core._RELAYED_PROMPT_RE.search(resume)), "overnight.sh resume text matches core._RELAYED_PROMPT_RE", resume)
        p, lines = run({"NEVER_CLOSE": "1"}, cap="1")
        check(len(lines) == 3 and "loop ended: 5 restarts with no step closed" in p.stdout and "(5 restarts with no step closed)" in lines[2],
              "overnight.sh stops after HOUSE_RULES_OVERNIGHT_NO_PROGRESS no-progress restarts, says so and makes the final call", "got %r %r" % (lines, p.stdout))
        # #648: waits go through HOUSE_RULES_OVERNIGHT_SLEEP (stubbed to log its argument)
        slp = os.path.join(d, "bin", "fakesleep")
        with open(slp, "w") as f:
            f.write('#!/bin/sh\necho "$1" >> "$LOG.sleep"\n')
        os.chmod(slp, 0o755)
        def waits(extra, cap=None):
            if os.path.exists(log + ".sleep"):
                os.remove(log + ".sleep")
            p, lines = run(dict(extra, HOUSE_RULES_OVERNIGHT_SLEEP=slp), cap=cap)
            sl = open(log + ".sleep").read().split() if os.path.exists(log + ".sleep") else []
            return p, lines, sl
        p, lines, sl = waits({})
        check(len(lines) == 3 and sl == [] and "waiting" not in p.stdout, "overnight.sh: no stopfailure file means no wait",
              "got %r %r %r" % (lines, sl, p.stdout))
        p, lines, sl = waits({"SF_KIND": "rate_limit", "SF_FIRST": "1", "NEVER_CLOSE": "1"}, cap="1")
        check(len(lines) == 3 and sl == ["300"] and "rate limit" in p.stdout and "not counted" in p.stdout,
              "overnight.sh: a rate_limit file with no reset time waits HOUSE_RULES_OVERNIGHT_RATE_WAIT (300) and spends no resume",
              "got %r %r %r" % (lines, sl, p.stdout))
        p, lines, sl = waits({"SF_KIND": "rate_limit", "SF_FIRST": "1", "SF_RESET": str(int(time.time()) + 1000), "NEVER_CLOSE": "1"}, cap="1")
        check(len(sl) == 1 and 1000 <= int(sl[0]) <= 1031, "overnight.sh: a rate_limit file with reset_at waits until reset_at plus 30 s", "got %r" % (sl,))
        p, lines, sl = waits({"SF_KIND": "crash", "NEVER_CLOSE": "1"}, cap="2")
        left = [f for f in os.listdir(os.path.join(d, "cfg", "house-rules-steps")) if f.startswith("stopfailure")]
        check(len(lines) == 4 and sl == ["30", "60", "120"] and not left,
              "overnight.sh: crash files back off 30, 60, 120 s, each resume counts (2 no-progress stops after 3 calls plus the final), file deleted",
              "got %r %r %r %r" % (lines, sl, left, p.stdout))
        # #649: limits. Stub clock advances STEP s per read; stub wait advances it by its argument (real time passing).
        clk = os.path.join(d, "bin", "fakeclock")
        with open(clk, "w") as f:
            f.write('#!/bin/sh\nc=$(cat "$LOG.clock"); echo "$c"; echo $((c + ${STEP:-0})) > "$LOG.clock"\n')
        os.chmod(clk, 0o755)
        slp2 = os.path.join(d, "bin", "clockwait")
        with open(slp2, "w") as f:
            f.write('#!/bin/sh\necho "$1" >> "$LOG.sleep"\nc=$(cat "$LOG.clock"); echo $((c + $1)) > "$LOG.clock"\n')
        os.chmod(slp2, 0o755)
        def limits(extra, cap="50"):
            open(log + ".clock", "w").write("1000")
            if os.path.exists(log + ".sleep"):
                os.remove(log + ".sleep")
            return run(dict(extra, HOUSE_RULES_OVERNIGHT_NOW=clk, HOUSE_RULES_OVERNIGHT_SLEEP=slp2, NEVER_CLOSE="1"), cap=cap)
        p, lines = limits({"STEP": "30000"})
        check(len(lines) > 2 and "Final pass: the run is ending (24-hour limit)." in lines[-1] and "loop ended: 24-hour limit" in p.stdout and p.returncode == 0,
              "overnight.sh: 24 hours of work ends the loop with the 24-hour limit final call", "got %r %r" % (lines, p.stdout))
        p, lines = limits({"STEP": "1"}, cap="5")
        check(len(lines) == 7 and "(5 restarts with no step closed)" in lines[-1] and p.returncode == 0,
              "overnight.sh: 5 restarts with no step closed end the loop (first call, 5 resumes, final call)", "got %r %r" % (lines, p.stdout))
        # a resume that closes a step resets the count: status reads OPEN 2, 2, 1, 1, 1, 1, ALL DONE -> count 1, 0, 1, 2, 3 would stop at cap 3 without the reset
        seq = os.path.join(d, "bin", "seqnote.py")
        open(seq, "w").write("import sys, os\nf = sys.argv[0] + '.n'\ni = int(open(f).read()) if os.path.exists(f) else 0\nopen(f, 'w').write(str(i + 1))\n"
                             "v = [2, 2, 1, 1, 1, 0][i]\nprint('OPEN %d' % v if v else 'ALL DONE')\nsys.exit(1 if v else 0)\n")
        script2 = os.path.join(d, "overnight2.sh")
        open(script2, "w").write(open(script).read().replace('python3 "$note"', 'python3 ' + seq).replace('$(dirname "$0")', '.'))
        open(log + ".clock", "w").write("1000")
        env = dict(os.environ, PATH=os.path.dirname(stub) + os.pathsep + os.environ["PATH"], LOG=log, REPO=repo,
                   CLAUDE_CONFIG_DIR=os.path.join(d, "cfg"), HOUSE_RULES_OVERNIGHT_NO_PROGRESS="3", HOUSE_RULES_OVERNIGHT_NOW=clk, NEVER_CLOSE="1")
        env.pop("CLAUDE_SESSION_ID", None)
        os.remove(log)
        p = subprocess.run(["sh", script2, "x"], cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40)
        lines = open(log).read().splitlines()
        check(len(lines) == 7 and "(all steps done)" in lines[-1] and "5 restarts" not in p.stdout,
              "overnight.sh: a resume that closes a step resets the no-progress count (cap 3 not hit)", "got %r %r" % (lines, p.stdout))
        # rate-limit waits are not work: 100000 s of waiting (> 24 h) does not trip the 24-hour limit
        p, lines = limits({"STEP": "0", "SF_KIND": "rate_limit", "SF_FIRST": "1", "HOUSE_RULES_OVERNIGHT_RATE_WAIT": "100000"}, cap="1")
        check("loop ended: 5 restarts" in p.stdout and "24-hour" not in p.stdout and open(log + ".sleep").read().split() == ["100000"],
              "overnight.sh: rate-limit wait seconds are not counted toward the 24 hours", "got %r %r" % (lines, p.stdout))
        fin = "[Subagent hand-back] Final pass: the run is ending (all steps done). Build the QA page now from the ledger, list every open or stuck step first, and do not start new work."
        check(bool(core._RELAYED_PROMPT_RE.search(fin)), "overnight.sh final-pass text matches core._RELAYED_PROMPT_RE", fin)
        note = os.path.join(ROOT, "claude-house-rules", "plugins", "house-rules", "scripts", "ledger_note.py")
        loop = os.path.join(repo, ".claude", "house-rules-loop.json")
        def status(steps):
            json.dump({"feature": "feature", "stage": "build", "skip": False, "approvals": [],
                       "steps": {"S1": {"feature": "feature", "steps": steps}} if steps else {}}, open(loop, "w"))
            r = subprocess.run([sys.executable, note, "steps-status", "feature", "--session", "S1"], cwd=repo,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40)
            return r.returncode, r.stdout.strip()
        st = {"n": 1, "title": "Step 1", "check": "true", "state": "open"}
        got = (status(None), status([st]), status([dict(st, stuck=True)]))
        check(got == ((0, "NO STEP LIST"), (1, "OPEN 1"), (0, "ALL DONE (1 STUCK: Step 1)")),
              "ledger_note.py steps-status prints NO STEP LIST, OPEN n, ALL DONE with the right exit codes", "got %r" % (got,))
        def stage_only(stage):
            json.dump({"feature": "feature", "stage": stage, "skip": False, "approvals": [], "steps": {}}, open(loop, "w"))
            r = subprocess.run([sys.executable, note, "steps-status", "feature", "--session", "S1"], cwd=repo,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=40)
            return r.returncode, r.stdout.strip()
        got = (stage_only("design"), stage_only("plan"), stage_only("build"), stage_only("qa"))
        check(got == ((1, "OPEN 2"), (1, "OPEN 1"), (0, "NO STEP LIST"), (0, "NO STEP LIST")),
              "ledger_note.py steps-status: a feature still in Design or Plan with no step list counts as open (2, 1); Build and QA do not",
              "got %r" % (got,))
    finally:
        shutil.rmtree(d, True)
_overnight_loop_case()

def _time_hooks_case():
    p = subprocess.run([sys.executable, os.path.join(HERE, "time_hooks.py"), "--quick"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
    ms = [l for l in p.stdout.splitlines() if l.startswith("    ") and l.rstrip().endswith(" ms")]
    check(p.returncode == 0 and len(ms) >= 4 and all(l.split()[-2].replace(".", "", 1).isdigit() for l in ms)
          and "Write call:" in p.stdout and "Bash call:" in p.stdout,
          "time_hooks.py --quick prints a millisecond number for every Write and Bash hook (a pre and a post line each since #628)",
          "got %r %r" % (p.stdout, p.stderr))
_time_hooks_case()

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
