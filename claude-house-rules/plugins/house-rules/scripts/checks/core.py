#!/usr/bin/env python3
"""checks/core.py - the core part: the rules injection, the reminders, the Stop-time handover checks, the version check (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/core.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: core")
print("=" * 43)
print()

for _event, _margin, _env in _size_cases[:4]:  # inject, showrule, standards, profile
    _code, _ctx, _err = _additional_context(_event, "", env=_env)
    if _ctx is None:
        report("FAIL", f"{_event} stays under the per-hook additionalContext limit")
        print(f"          could not read additionalContext: {_err.strip()}")
    elif len(_ctx) <= _margin:
        report("PASS", f"{_event} stays under the per-hook additionalContext limit")
        print(f"          {len(_ctx)} chars <= {_margin} margin (hard limit 10,000)")
    else:
        report("FAIL", f"{_event} stays under the per-hook additionalContext limit")
        print(f"          {len(_ctx)} chars > {_margin} margin - Claude Code will truncate this")

# --- the show-don't-tell rule reaches the session through its own slot (issue #224) ----------
_code, _ctx, _err = _additional_context("showrule", "", env=env_in(ROOT))
_sdt_missing = [p for p in (
    "## Show, don't tell; the user designs",
    "The request is the scope",
    "Every page is a proposal",
    "what the change merges, cuts or reuses",
    "one marked as my suggestion",
    "160 words or more needs a page",
    "A bare\n\"approved\" does not count",
    "rules/detail/show-dont-tell.md",
) if p not in (_ctx or "")]
if not os.path.isfile(os.path.join(DETAIL_DIR, "show-dont-tell.md")):
    _sdt_missing.append("rules/detail/show-dont-tell.md does not exist")
if "## Show, don't tell" in read(RULES_FILE):
    _sdt_missing.append("house-rules.md also carries the rule - it would load twice")
if _sdt_missing:
    report("FAIL", "showrule injects the show-don't-tell rule, once, with a live detail pointer")
    print(f"          missing or wrong: {'; '.join(_sdt_missing)}")
else:
    report("PASS", "showrule injects the show-don't-tell rule, once, with a live detail pointer")
    print(f"          {len(_ctx)} chars; every approved clause present")

# --- the clear-writing rule loads in the same slot, once (#246) -------------------------------
_cw_missing = [p for p in (
    "## Write it so nothing is left to guess",
    "Proper sentences", "Said once", "Explicit context", "Define before use", "Measured, not guessed",
    "Named references", "Exact inputs", "Done-criteria", "Ask when unclear", "Plain words", "### The voice",
    "rules/detail/clear-writing.md",
) if p not in (_ctx or "")]
if _ctx.count("## Write it so nothing is left to guess") > 1:
    _cw_missing.append("the rule loads twice")
if not os.path.isfile(os.path.join(DETAIL_DIR, "clear-writing.md")):
    _cw_missing.append("rules/detail/clear-writing.md does not exist")
if os.path.isfile(os.path.join(DETAIL_DIR, "plain-language.md")):
    _cw_missing.append("rules/detail/plain-language.md still exists beside its replacement")
if "Never softens a failure" in read(RULES_FILE):
    _cw_missing.append("house-rules.md still carries the voice - it would load twice")
report("FAIL" if _cw_missing else "PASS",
       "showrule injects the clear-writing rule, once, and the old plain-language homes point to it")
if _cw_missing:
    print(f"          missing or wrong: {'; '.join(_cw_missing)}")

# --- the rules actually reach the session ----------------------------------------------------
code, out, err = run_hook("inject", "")
missing = []
for h in [
    "Find out what machine you are on",
    "Read the docs first, then check them against the code",
    "Documentation goes in tiers",
    "Build for a human working alone",
    "hands are for decisions, not labour",
    "Deliver a whole workflow, not a starting point",
    "Never hand over a command I have not run",
    "Every artifact lives in the project directory",
    "Commit constantly on my own branches, never on theirs",
    "Never take a destructive action without checking first",
    "Edit in place; a full rewrite is a delete, not an edit",
]:
    if h not in out:
        missing.append(h)
if "Never hide work" in out:  # #292: the rule was removed
    missing.append("the removed 'Never hide work' rule is still injected")
if not missing:
    report("PASS", "SessionStart injects every rule heading into context")
    print(f"          {len(out)} characters injected")
else:
    report("FAIL", "SessionStart injects every rule heading into context")
    print(f"          missing: {'; '.join(missing)}")

# --- ${CLAUDE_PLUGIN_ROOT} is expanded to a real, openable path before injection --------------
_root = None
_ctx_text = ""
# additionalContext is plain text nothing expands - only hooks.json's own command strings get
# ${CLAUDE_PLUGIN_ROOT} substituted by the harness. A literal ${CLAUDE_PLUGIN_ROOT} left in the
# injected text is a path Claude cannot open.
_detail_marker = "/rules/detail/edit-place.md"
if "${CLAUDE_PLUGIN_ROOT}" in out:
    report("FAIL", "inject expands ${CLAUDE_PLUGIN_ROOT} to a real path")
    print("          the literal placeholder reached additionalContext unexpanded")
elif _detail_marker.lstrip("/") not in out:
    report("FAIL", "inject expands ${CLAUDE_PLUGIN_ROOT} to a real path")
    print(f"          no detail pointer {_detail_marker.lstrip('/')!r} found in the injection")
else:
    try:
        _ctx_text = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        _ctx_text = ""
    _root_line = re.search(r"is the plugin root: ([^\n]+)", _ctx_text)
    _root = _root_line.group(1) if _root_line else None
    _expanded_path = os.path.join(_root, *_detail_marker.lstrip("/").split("/")) if _root else None
    if _expanded_path and os.path.isfile(_expanded_path):
        report("PASS", "inject expands ${CLAUDE_PLUGIN_ROOT} to a real path")
        print(f"          {_expanded_path} exists on disk")
    else:
        report("FAIL", "inject expands ${CLAUDE_PLUGIN_ROOT} to a real path")
        print(f"          plugin root {_root!r} + detail pointer does not exist on disk")
# The install path's length must not scale the injection: stated once, never per pointer.
_root_count = _ctx_text.count(_root) if _root else 0
if _root_count == 1:
    report("PASS", "inject states the plugin root once, so its size is independent of the install path")
    print(f"          root appears once; {len(_ctx_text)} chars total")
else:
    report("FAIL", "inject states the plugin root once, so its size is independent of the install path")
    print(f"          root appears {_root_count} times - each copy grows with the install path")

# --- the step-card POINTER actually REACHES the session, not just the file --------------------
# Since 2.17.0 ("rules that actually load") the full card template is deliberately NOT injected -
# it lives once in the forced handover-cards output style, which is what stays under the per-hook
# context limit. So this no longer asserts the template's own markers arrive in additionalContext
# (they intentionally do not); it asserts the POINTER to where the template lives does.
cardmissing = []
for marker in [
    "#### The card",
    "handover-cards",
    "UNTESTED:",
]:
    if marker not in out:
        cardmissing.append(marker)
if not cardmissing:
    report("PASS", "SessionStart injects the step-card pointer into context")
    print("          the card heading and a pointer to handover-cards.md arrive in additionalContext")
else:
    report("FAIL", "SessionStart injects the step-card pointer into context")
    print(f"          missing from the injected text: {'; '.join(cardmissing)}")

# --- inject fail-loud: an internal error must still say something ---------------------------
crash_snippet2 = (
    "import sys, hook\n"
    "import house_rules.core as core\n"
    "orig = core._read_text\n"
    "def boom(path):\n"
    "    if 'house-rules.md' in path:\n"
    "        raise OSError('simulated read failure')\n"
    "    return orig(path)\n"
    "core._read_text = boom\n"
    "sys.exit(hook.main(['hook.py', 'inject']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet2], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out2 = proc.stdout.decode("utf-8", "replace")
if "systemMessage" in out2 and "NOT loaded" in out2:
    report("PASS", "inject that cannot read the rules file still prints a visible warning")
    print(f"          said: {out2}")
else:
    report("FAIL", "inject that cannot read the rules file still prints a visible warning")
    print(f"          got: {out2}")

# --- the scope reminder reaches every prompt, gated stateless on the prompt's own content ----
# scope runs on UserPromptSubmit, where a non-zero exit ERASES THE USER'S PROMPT - every case
# below asserts exit 0 alongside the expected form, and the no-"prompt"-key case is the one
# that would catch a regression toward raising instead of falling back.
def scope_payload(prompt=None):
    obj = {"session_id": "verify", "hook_event_name": "UserPromptSubmit"}
    if prompt is not None:
        obj["prompt"] = prompt
    return json.dumps(obj)


def check_scope(title, payload, expect, empty_path=False):
    env = dict(os.environ)
    if empty_path:
        env["PATH"] = ""
    code, out, err = run_hook("scope", payload, env=env)
    bad = []
    if code != 0:
        bad.append(f"exited {code}, not 0 - this would erase the user's prompt")
    if '"hookEventName":"UserPromptSubmit"' not in out:
        bad.append("wrong or missing hookEventName")
    if expect == "long":
        if "Show, don't tell" not in out or "machine you are on" not in out:
            bad.append("expected the long form, did not see its content")
    elif expect == "short":
        if "Show, don't tell" in out or "machine you are on" in out:
            bad.append("expected the short form, but the long form's content is present")
        if "docs tier that changed" not in out:
            bad.append("short form missing the docs-tier line")
        if "run you can quote" not in out:
            bad.append("short form missing the evidence line")
    if not bad:
        report("PASS", title)
        print(f"          {len(out)} characters of reminder injected ({expect} form)")
    else:
        report("FAIL", title)
        print(f"          {'; '.join(bad)}")


check_scope(
    "a command-shaped prompt gets the full reminder",
    scope_payload("run the install script and build the project"),
    "long",
)
check_scope(
    "a plain prompt gets the short reminder",
    scope_payload("what does this function do?"),
    "short",
)
check_scope(
    "a payload with no prompt field at all still exits 0 with the short reminder - the "
    "path that would erase the user's prompt if it regressed",
    scope_payload(),
    "short",
)
check_scope(
    "the short reminder still works with PATH empty (it depends on nothing)",
    scope_payload("what does this function do?"),
    "short",
    empty_path=True,
)

# --- both scope forms stay within +10% of their 2026-09-23 baseline size --------------------
# Baselines recorded the day the step-card line was swapped for a docs-tier line and an
# evidence line (docs/6-decisions/Decisions.md): long form was 909 chars, short form 260. +10% margin, not
# a floor - shrinking is fine, growing past it is the thing this catches.
_SCOPE_SIZE_BASELINES = {"long": (909, 1.10), "short": (260, 1.10)}
for form, payload_prompt in (("long", "run the build script"), ("short", "what does this function do?")):
    _, out, _ = run_hook("scope", scope_payload(payload_prompt))
    try:
        actual = len(json.loads(out)["hookSpecificOutput"]["additionalContext"])
    except Exception as exc:
        actual = -1
    base, margin = _SCOPE_SIZE_BASELINES[form]
    cap = int(base * margin)
    if 0 <= actual <= cap:
        report("PASS", f"scope's {form} form stays within +10% of its baseline size")
        print(f"          {actual} chars <= {cap} (baseline {base})")
    else:
        report("FAIL", f"scope's {form} form stays within +10% of its baseline size")
        print(f"          {actual} chars > {cap} (baseline {base}) or output unparseable")

# --- the artifact reminder fires on documents written outside a project ---------------------
def art_case(expect, title, file_path, extra="", contains=None, excludes=None):
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    )
    if extra:
        obj = json.loads(payload)
        obj["tool_input"].update(extra)
        payload = json.dumps(obj)
    code, out, err = run_hook("artifact", payload, env=verbose_env())
    if "artifact custody" in out:
        got = "remind"
    elif '"systemMessage"' in out:
        got = "trace"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    ok = got == expect
    if ok and contains is not None and contains not in out:
        ok = False
    if ok and excludes is not None and excludes in out:
        ok = False
    report("PASS" if ok else "FAIL", title)
    print(f"          expected {expect}, got {got}")


art_case(
    "remind",
    "plan written to ~/.claude/plans is flagged for copying into the project",
    r"C:\Users\aj\.claude\plans\some-plan.md",
    contains="docs/",
    excludes="docs/generated",
)
art_case(
    "remind",
    "document written to the session scratchpad is flagged",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\notes.md",
    contains="docs/",
    excludes="docs/generated",
)
art_case(
    "trace",
    "document written inside the project is left alone",
    r"C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\docs\plans\x.md",
)
art_case(
    "trace",
    "file whose CONTENTS mention a temp path is left alone",
    r"C:\Users\aj\Desktop\proj\README.md",
    extra={"content": "put it in /tmp/ or scratchpad"},
)
art_case(
    "trace",
    "script in a temp directory is scratch work, not an artifact",
    r"C:\Users\aj\AppData\Local\Temp\build.sh",
)
# The extension list shipped as md|txt, so an .html report written to the scratchpad was invisible
# to the one backstop that exists to catch it - the rule says "every artifact", the pattern said
# two extensions. It happened for real: an architecture review was left in the scratchpad and the
# hook never fired. One case per extension, so widening cannot silently narrow again.
art_case(
    "remind",
    "an .html report written to the scratchpad is flagged - the case that shipped unguarded",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\architecture-review.html",
    contains="docs/generated",
)
art_case(
    "trace",
    "an .html report written inside the project is left alone",
    r"C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\docs\architecture-review.html",
)
for _ext in ("csv", "json", "svg", "pdf"):
    art_case(
        "remind",
        f"a .{_ext} deliverable written outside the project is flagged",
        rf"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\report.{_ext}",
        contains="docs/generated",
    )
art_case(
    "trace",
    "a .ps1 in the scratchpad is still scratch work - runnables stay out of the artifact list",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\build.ps1",
)

# --- docs/generated/ has not drifted between the rules, the project-docs skill, and the -----
# --- text hook.py actually emits for a generated-extension artifact -------------------------
gendrift = []
_art_rules_text = rules_corpus()
if "docs/generated" not in _art_rules_text:
    gendrift.append("house-rules.md no longer mentions docs/generated/")
if not os.path.isfile(DOCSKILL):
    gendrift.append("skills/project-docs/SKILL.md does not exist")
else:
    _art_skill_text = read(DOCSKILL)
    if "docs/generated" not in _art_skill_text:
        gendrift.append("skills/project-docs/SKILL.md no longer mentions docs/generated/")
_gen_code, _gen_out, _gen_err = run_hook(
    "artifact",
    json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\report.html"
            },
        }
    ),
)
if "docs/generated" not in _gen_out:
    gendrift.append("hook.py's emitted ARTIFACT_NOTE no longer names docs/generated/ for an .html case")
if not gendrift:
    report("PASS", "docs/generated has not drifted across house-rules.md, SKILL.md, and the emitted ARTIFACT_NOTE")
    print("          all three name docs/generated/ for generated artifacts")
else:
    report("FAIL", "docs/generated has not drifted across house-rules.md, SKILL.md, and the emitted ARTIFACT_NOTE")
    print(f"          {'; '.join(gendrift)}")
# The scope reminder's own drift check now lives in the RESTATEMENTS table below (see
# "the restatement table" further down this file), which checks it - and every other
# restatement - both ways: rules corpus and emitted text, not the rules corpus alone.

# --- a repo checkout and an installed copy can be told apart ---------------------------------
# Everything below that skips instead of failing rests on IN_REPO. If that marker ever disagreed
# with reality, the skips would either hide real drift (in the repo) or come back as noise (in the
# cache), so it is checked against a second repo-only file that has nothing to do with the marker.
_independent = os.path.isfile(os.path.join(ROOT, "tools", "verify_tools.py"))
if IN_REPO == _independent:
    report("PASS", "the repo-only checks can tell a repo checkout from an installed copy")
    print(f"          running from {'the repo working tree' if IN_REPO else 'an installed copy'}; "
          "marketplace.json and tools/verify_tools.py agree")
else:
    report("FAIL", "the repo-only checks can tell a repo checkout from an installed copy")
    print(f"          .claude-plugin/marketplace.json says {IN_REPO}, tools/verify_tools.py says "
          f"{_independent} - the skip decisions below cannot be trusted")

# --- the rules have not been re-duplicated into CLAUDE.md ------------------------------------
root_claude = os.path.join(ROOT, "CLAUDE.md")
_absent = absent_repo_files("CLAUDE.md")
if _absent:
    skip_repo_check("repo CLAUDE.md is not a second copy of the rules", _absent)
elif not os.path.isfile(root_claude):
    report("PASS", "repo CLAUDE.md is not a second copy of the rules")
    print("          no CLAUDE.md at the repo root; the plugin is the only source")
else:
    claude_text = read(root_claude)
    if "Never take a destructive action without checking first" in claude_text:
        report("FAIL", "repo CLAUDE.md is not a second copy of the rules")
        print("          it holds a full copy of the rules; it should be a pointer")
    else:
        report("PASS", "repo CLAUDE.md is not a second copy of the rules")
        print(f"          it is a pointer ({len(claude_text.encode('utf-8'))} bytes), not a copy")

# --- CLAUDE.md stays a real pointer, not a growing document ----------------------------------
CLAUDE_MD_BYTE_LIMIT = 4_000
_absent = absent_repo_files("CLAUDE.md")
if _absent:
    skip_repo_check(f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes", _absent)
elif not os.path.isfile(root_claude):
    report("PASS", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
    print("          no CLAUDE.md at the repo root")
else:
    _claude_bytes = len(read(root_claude).encode("utf-8"))
    if _claude_bytes <= CLAUDE_MD_BYTE_LIMIT:
        report("PASS", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
        print(f"          {_claude_bytes} bytes <= {CLAUDE_MD_BYTE_LIMIT}")
    else:
        report("FAIL", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
        print(f"          {_claude_bytes} bytes > {CLAUDE_MD_BYTE_LIMIT} - it has grown past a pointer again")

# --- the recorded machine profile actually reaches the session -------------------------------
# A real rules/environment.md fixture, not a coincidental phrase in the rules body - the rules
# split (docs/6-decisions/Decisions.md, 2026-09-22) moved the PowerShell/Git-Bash path-notation example this
# used to piggyback on out of the injected text on purpose, so this now supplies its own fixture.
_envfixture = os.path.join(_FIXTURE_ROOT, "environment.md")
with open(_envfixture, "w", encoding="utf-8") as _f:
    _f.write("# This machine (hand-verified)\n\nShell: PowerShell\nsh: NOT on PATH\n")
code, out, err = run_hook("profile", "", env=env_in(ROOT, HOUSE_RULES_ENV_FILE=_envfixture))
missing_env = []
if "This machine" not in out:
    missing_env.append("no machine profile in the injection")
if "PowerShell" not in out:
    missing_env.append("no shell recorded")
if "NOT on PATH" not in out:
    missing_env.append("the sh-not-on-PATH trap is not recorded")
if not missing_env:
    report("PASS", "SessionStart injects the recorded machine profile")
    print(f"          rules + machine profile = {len(out)} characters")
else:
    report("FAIL", "SessionStart injects the recorded machine profile")
    print(f"          {'; '.join(missing_env)}")

# --- an unrecorded machine reads as "go and find out", never as "assume" ---------------------
env = dict(os.environ)
env["HOUSE_RULES_ENV_FILE"] = "/nonexistent-on-purpose"
code, out, err = run_hook("profile", "", env=env)
if "NOT RECORDED YET" in out:
    report("PASS", "a missing machine profile becomes an instruction to discover it")
    print("          the session is told to go and find the facts, not to assume them")
else:
    report("FAIL", "a missing machine profile becomes an instruction to discover it")
    print("          the injection said nothing about the profile being absent")

# --- handover-target: a local session (no CLAUDE_CODE_REMOTE) adds nothing -------------------
# house-rules.md's own rule text legitimately says "handover" and names rules/handover-target.md
# unconditionally (it explains the local-vs-remote distinction itself), so checking for the word
# "handover" anywhere in the output would false-fail here. What must be absent on a local session
# is hook.py's *injected block* - checked by its two block-specific openings instead.
env = dict(os.environ)
env.pop("CLAUDE_CODE_REMOTE", None)
code, out, err = run_hook("profile", "", env=env)
if "for anything I hand over to them" not in out.lower() and "this session is remote:" not in out.lower():
    report("PASS", "a local session's injection carries no handover-target block")
    print("          no CLAUDE_CODE_REMOTE in the test env, no handover block emitted")
else:
    report("FAIL", "a local session's injection carries no handover-target block")
    print("          handover-target block leaked into a non-remote injection")

# --- handover-target: remote + no file recorded -> told to find out and record ---------------
env = dict(os.environ)
env["CLAUDE_CODE_REMOTE"] = "true"
env["HOUSE_RULES_HANDOVER_TARGET_FILE"] = "/nonexistent-on-purpose-handover"
code, out, err = run_hook("profile", "", env=env)
if "rules/handover-target.md" in out and "find out" in out.lower():
    report("PASS", "a remote session with no recorded handover target is told to find one out")
    print("          the injection points at docs/example-environment.md / asking, then recording")
else:
    report("FAIL", "a remote session with no recorded handover target is told to find one out")
    print("          the injection did not carry the find-out-and-record instruction")

# --- handover-target: remote + a recorded file -> that content is injected -------------------
handover_fixture = os.path.join(_FIXTURE_ROOT, "handover-target.md")
with open(handover_fixture, "w", encoding="utf-8") as f:
    f.write("# The human's machine\n\nWindows 11, PowerShell, Git Bash for POSIX.\n")
env = dict(os.environ)
env["CLAUDE_CODE_REMOTE"] = "true"
env["HOUSE_RULES_HANDOVER_TARGET_FILE"] = handover_fixture
code, out, err = run_hook("profile", "", env=env)
if "Git Bash for POSIX" in out:
    report("PASS", "a remote session injects a recorded handover-target file's content")
    print("          fixture content reached additionalContext")
else:
    report("FAIL", "a remote session injects a recorded handover-target file's content")
    print("          fixture content did not appear in the injection")

# --- the handover-target clause has not drifted between house-rules.md and hook.py -----------
handover_drift = []
for phrase in [
    "handed-over command targets",
    "rules/handover-target.md",
]:
    if phrase.lower() not in rules_text.lower():
        handover_drift.append(f"missing from house-rules.md: {phrase}")
env = dict(os.environ)
env["CLAUDE_CODE_REMOTE"] = "true"
env["HOUSE_RULES_HANDOVER_TARGET_FILE"] = "/nonexistent-on-purpose-handover"
_, handover_out, _ = run_hook("profile", "", env=env)
if "rules/handover-target.md" not in handover_out:
    handover_drift.append("hook.py's find-out instruction no longer names rules/handover-target.md")
if not handover_drift:
    report("PASS", "the handover-target clause has not drifted between house-rules.md and hook.py")
    print("          both name rules/handover-target.md and the handed-over-command distinction")
else:
    report("FAIL", "the handover-target clause has not drifted between house-rules.md and hook.py")
    print(f"          {'; '.join(handover_drift)}")

# --- the run-what-you-wrote reminder ----------------------------------------------------------
def run_case(expect, title, file_path, extra=""):
    obj = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    if extra:
        obj["tool_input"].update(extra)
    code, out, err = run_hook("runnable", json.dumps(obj), env=verbose_env())
    if "whole workflows" in out:
        got = "remind"
    elif '"systemMessage"' in out:
        got = "trace"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    report("PASS" if got == expect else "FAIL", title)
    print(f"          expected {expect}, got {got}")


run_case("remind", "a runnable .sh created in the project is flagged to be run", r"C:\proj\build.sh")
run_case(
    "remind", "a runnable .ps1 created in the project is flagged to be run", r"C:\proj\tools\install.ps1"
)
run_case("remind", "a bare Dockerfile counts as runnable", r"C:\proj\Dockerfile")
run_case("trace", "a document is not a runnable file", r"C:\proj\notes.md")
run_case(
    "trace",
    "a script written to a temp directory is scratch work, not a delivery",
    r"C:\Users\aj\AppData\Local\Temp\build.sh",
)
run_case(
    "trace",
    "a script written to the session scratchpad is scratch work",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\run.py",
)
run_case(
    "trace",
    "a file whose CONTENTS mention a temp path is judged on where it actually is",
    r"C:\proj\notes.md",
    extra={"content": "write it to /tmp/build.sh first"},
)

# --- the compile-verification reminder for compiled-language (.cs) files ---------------------
def compile_case(expect, title, file_path):
    obj = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    code, out, err = run_hook("runnable", json.dumps(obj), env=verbose_env())
    if "should compile" in out.lower():
        got = "remind"
    elif '"systemMessage"' in out:
        got = "trace"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    report("PASS" if got == expect else "FAIL", title)
    print(f"          expected {expect}, got {got}")


compile_case(
    "remind",
    "a .cs file created in the project is flagged to compile against the real toolchain",
    r"C:\proj\Assets\Scripts\Player.cs",
)
compile_case(
    "trace",
    "a .cs file written to a temp directory is scratch work, not compiled",
    r"C:\Users\aj\AppData\Local\Temp\Player.cs",
)

# The compile-verification note's drift check is a row in the RESTATEMENTS table below.

# --- the shim-is-not-a-compiler rule is stated in full, not just as scattered phrases ---------
missing = [
    p
    for p in [
        "A shim that compiles is not proof the real code does",
        "hand-rolled stand-in",
        "batch mode",
        "dotnet build",
        "UNTESTED",
    ]
    if p.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the shim-is-not-a-compiler rule states the check, the fallback, and the honest-gap case")
    print("          real toolchain, dotnet build fallback, and the UNTESTED label are all named")
else:
    report("FAIL", "the shim-is-not-a-compiler rule states the check, the fallback, and the honest-gap case")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# The runnable note's drift check is a row in the RESTATEMENTS table below.

# --- the green-suite rule is stated, and states the conditions that actually found the bugs ----
missing = [
    p
    for p in [
        "A green test suite is not proof it works",
        "realistic scale",
        "Twice",
        "As the thing that ships",
        "the run wins",
    ]
    if p.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the green-suite rule names the conditions each real defect was found under")
    print("          scale, repetition, the shipped artifact, and run-beats-test")
else:
    report("FAIL", "the green-suite rule names the conditions each real defect was found under")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# The delegate reminder's drift check (including the worktree-isolation mandate it carries) is
# a row in the RESTATEMENTS table below. Why this must be bidirectional: docs/4-systems/
# verify-suites.md, Traps ("Most drift checks run in one direction only") and
# docs/architecture.md, "Why the delegation kept not happening".

# --- the disclosure rule, and the voice toggle it sits next to ------------------------------
missing = [
    ph
    for ph in [
        "I say what prompted me",
        "continue past a visible reply",
        "from memory when a record exists",
        "docs/sessions/",
    ]
    if ph.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the disclosure rule states attribution, continuations, and check-the-record")
    print("          all three failures it was written for are named")
else:
    report("FAIL", "the disclosure rule states attribution, continuations, and check-the-record")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# --- HOUSE_RULES_VOICE=off removes the voice and nothing else -------------------------------
# The section is cut by locating the next "## " heading. If that boundary is wrong the toggle
# eats the rule after it, silently, and nobody notices until a rule stops being enforced.
# Since #245 the voice lives in rules/clear-writing.md, loaded by showrule.
code, on_out, err = run_hook("showrule", "")
env_off = dict(os.environ)
env_off["HOUSE_RULES_VOICE"] = "off"
code_off, off_out, err_off = run_hook("showrule", "", env=env_off)
voice_problems = []
if "### The voice" not in on_out:
    voice_problems.append("the voice is missing by default, but it ships on")
if "### The voice" in off_out:
    voice_problems.append("HOUSE_RULES_VOICE=off did not remove the voice section")
for kept in [
    "Write it so nothing is left to guess",
    "Explicit context",
    "Define before use",
    "Named references",
    "Show, don't tell; the user designs",
]:
    if kept not in off_out:
        voice_problems.append(f"turning the voice off also removed {kept!r}")
if code_off != 0:
    voice_problems.append(f"exited {code_off} with the voice off")
if not voice_problems:
    report("PASS", "HOUSE_RULES_VOICE=off removes the voice and no rule around it")
    print(f"          on: {len(on_out)} chars, off: {len(off_out)} chars; every neighbouring rule survives")
else:
    report("FAIL", "HOUSE_RULES_VOICE=off removes the voice and no rule around it")
    for v in voice_problems:
        print(f"          {v}")
for event, payload, needle, why in trace_cases[1:]:  # artifact, runnable
    code, out, err = run_hook(event, payload, env=verbose_env())
    if code == 0 and '"systemMessage"' in out and needle in out:
        report("PASS", f"{event} traces its decision on {why}")
        print(f"          says what it looked at and what it concluded; names {needle!r}")
    else:
        report("FAIL", f"{event} traces its decision on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
for event, payload, needle, why in trace_cases[1:]:  # artifact, runnable
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

# --- one lever turns every trace off, and no reminder goes with it -----------------------------
off = env_in(REPO_THEIRS)
off["HOUSE_RULES_TRACE"] = "off"
quiet_failures = []
for event, payload, _, why in trace_cases:
    code, out, err = run_hook(event, payload, env=off)
    if out.strip():
        quiet_failures.append(f"{event} still emitted with HOUSE_RULES_TRACE=off: {out[:80]}")
code, out, err = run_hook(
    "guard", json.dumps({"tool_input": {"command": "rm -rf build"}}), env=off
)
if '"permissionDecision":"deny"' not in out:  # #291: rm -rf is refused, naming the safe way
    quiet_failures.append("HOUSE_RULES_TRACE=off also silenced guard's refusal, which it must not")
code, out, err = run_hook(
    "harvest",
    json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/p/a.cs", "content": ESSAY_CS}}),
    env=off,
)
if '"additionalContext"' not in out:
    quiet_failures.append("HOUSE_RULES_TRACE=off also silenced the harvest reminder")
if '"systemMessage"' in out:
    quiet_failures.append("HOUSE_RULES_TRACE=off did not cover harvest's own trace")
if not quiet_failures:
    report("PASS", "HOUSE_RULES_TRACE=off silences every trace and no reminder")
    print("          one lever for the diagnostic; the decisions themselves still speak")
else:
    report("FAIL", "HOUSE_RULES_TRACE=off silences every trace and no reminder")
    for q in quiet_failures:
        print(f"          {q}")

# --- handover is the deliberate exception, and it is not an oversight --------------------------
# Tracing its stand-down would announce a compliant card's own compliance, which the rules
# forbid, and would put a line on the end of every ordinary turn. Silence there already means
# "I looked and there was nothing to do".
code, out, err = run_hook(
    "handover",
    json.dumps(
        {
            "session_id": "verify",
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "a reply with no fenced block",
        }
    ),
)
if not out.strip() and "never announces its own compliance" in rules_corpus():
    report("PASS", "handover stays silent on its stand-down, and the rule that requires it still stands")
    print("          the one handler where tracing would break a rule rather than cost tokens")
else:
    report("FAIL", "handover stays silent on its stand-down, and the rule that requires it still stands")
    print(f"          got: {out[:160]!r}")

# --- run.sh's interpreter cache (2.48.0) -------------------------------------------------------
# A copy of run.sh sits next to a stub hook.py that just prints "ran", so the cache file lands in
# a throwaway directory and never in the real plugin.
def _cache_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


def _cache_dir():
    d = tempfile.mkdtemp(prefix="house-rules-cache-", dir=_FIXTURE_ROOT)
    shutil.copy(RUN, os.path.join(d, "run.sh"))
    with open(os.path.join(d, "hook.py"), "w", encoding="utf-8") as f:
        f.write("print('ran')\n")
    return d


def _cache_run(d, **env_extra):
    e = dict(os.environ)
    e.pop("HOUSE_RULES_PYTHON", None)
    e["HOUSE_RULES_DEBUG"] = "1"
    e.update(env_extra)
    # forward slashes: run.sh derives HERE from $0 and splits only on "/"
    return run_shell([os.path.join(d, "run.sh").replace("\\", "/"), "anyevent"], env=e)


def _cache_text(d):
    try:
        with open(os.path.join(d, ".python-cache"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


_cd = _cache_dir()
_c1, _o1, _e1 = _cache_run(_cd)
_first = _cache_text(_cd)
_cache_case(
    "run.sh: the first run probes and writes the cache",
    _c1 == 0 and "ran" in _o1 and "cache=yes" not in _e1 and bool(_first),
    "exit %d, out %r, cache %r" % (_c1, _o1.strip(), _first),
)
_c2, _o2, _e2 = _cache_run(_cd)
_cache_case(
    "run.sh: the second run uses the cache and skips probing",
    _c2 == 0 and "ran" in _o2 and "cache=yes" in _e2 and _cache_text(_cd) == _first,
    "exit %d, out %r, stderr %r" % (_c2, _o2.strip(), _e2.strip()[:100]),
)
with open(os.path.join(_cd, ".python-cache"), "w", encoding="utf-8") as f:
    f.write("no-such-interpreter-xyz\n")
_c3, _o3, _e3 = _cache_run(_cd)
_cache_case(
    "run.sh: a stale cache (missing binary) is dropped, the probe order runs, and the cache is rewritten",
    _c3 == 0 and "ran" in _o3 and "cache=yes" not in _e3 and _cache_text(_cd) == _first,
    "exit %d, out %r, cache now %r" % (_c3, _o3.strip(), _cache_text(_cd)),
)
_cd = _cache_dir()
_stubdir = tempfile.mkdtemp(prefix="house-rules-stub-", dir=_FIXTURE_ROOT)
with open(os.path.join(_stubdir, "python3"), "w", encoding="utf-8", newline="\n") as f:
    f.write('#!/bin/sh\necho "Python was not found; run without arguments to install from the Microsoft Store."\nexit 0\n')
os.chmod(os.path.join(_stubdir, "python3"), 0o755)  # POSIX skips a non-executable file on PATH
_c4, _o4, _e4 = _cache_run(_cd, PATH=_stubdir + os.pathsep + os.environ.get("PATH", ""))
_cached4 = _cache_text(_cd)
_cache_case(
    "run.sh: an interpreter stub that prints a nag instead of running code is never cached",
    _c4 == 0 and "ran" in _o4 and _cached4 is not None and _cached4.split()[0] != "python3",
    "exit %d, out %r, cache %r" % (_c4, _o4.strip(), _cached4),
)
_cd = _cache_dir()
os.mkdir(os.path.join(_cd, ".python-cache"))  # a directory where the file should go: not writable as a file
_c5, _o5, _e5 = _cache_run(_cd)
_cache_case(
    "run.sh: a cache that cannot be written is skipped, never a failure",
    _c5 == 0 and "ran" in _o5 and "Permission denied" not in _e5 and "Is a directory" not in _e5,
    "exit %d, out %r, stderr %r" % (_c5, _o5.strip(), _e5.strip()[:100]),
)
_cd = _cache_dir()
with open(os.path.join(_cd, ".python-cache"), "w", encoding="utf-8") as f:
    f.write("no-such-interpreter-xyz\n")
_c6, _o6, _e6 = _cache_run(_cd, HOUSE_RULES_PYTHON=sys.executable)
_cache_case(
    "run.sh: HOUSE_RULES_PYTHON still wins over the cache and is still probed",
    _c6 == 0 and "ran" in _o6 and "cache=override" in _e6 and _cache_text(_cd) == "no-such-interpreter-xyz",
    "exit %d, out %r, stderr %r" % (_c6, _o6.strip(), _e6.strip()[:100]),
)
_cd = _cache_dir()
_c7, _o7, _e7 = _cache_run(_cd, HOUSE_RULES_PYTHON="no-such-interpreter-xyz")
_cache_case(
    "run.sh: a bad HOUSE_RULES_PYTHON is still rejected by the probe and falls through to the normal order",
    _c7 == 0 and "ran" in _o7,
    "exit %d, out %r" % (_c7, _o7.strip()),
)

# The harvest reminder's drift check is a row in the RESTATEMENTS table below.

# --- the "nothing fails silently" rule, enforced structurally over hook.py source --------------
# The rule is worthless if the plugin's own hooks break it, so this reads hook.py and fails any
# except block that returns without first emitting or writing to stderr.
hook_src = "\n".join(read(p) for p in (HOOK, CORE, SAFE_GIT, DOCS, DELEGATION, DESIGN_LOOP, WRITING))  # #359: all seven files
hook_lines = hook_src.split("\n")
silent_handlers = []
for i, line in enumerate(hook_lines):
    stripped = line.strip()
    if not (stripped.startswith("except ") or stripped == "except:"):
        continue
    indent = len(line) - len(line.lstrip())
    spoke = False
    bails = False
    for j in range(i + 1, len(hook_lines)):
        nxt = hook_lines[j]
        if not nxt.strip():
            continue
        if len(nxt) - len(nxt.lstrip()) <= indent:
            break
        body = nxt.strip()
        if "emit(" in nxt or "stderr.write" in nxt or "problems.append(" in nxt:
            spoke = True
        # Handing the caller something to say is the third shape the rule allows, alongside
        # emitting and writing to stderr - CLAUDE.md names it "recording the problem for its
        # caller to report". branch_ownership() is the case: it cannot emit, because guard has
        # to decide whether to prompt before it knows what to print. A return carrying a
        # non-empty string literal is that shape; a bare `return`, `return None` or `return ""`
        # is not, and still counts as giving up silently.
        if body.startswith("return") and re.search(r'"[^"]+"|\'[^\']+\'', body):
            spoke = True
        # An except that recovers - assigns a fallback and carries on - is not the defect;
        # the rule is about a handler that GIVES UP without saying so. Only a body that
        # returns or passes straight out is one of those.
        if body == "pass" or body.startswith("return"):
            bails = True
    if bails and not spoke:
        silent_handlers.append(f"hook.py:{i + 1}: {stripped}")
if not silent_handlers:
    report("PASS", "no except block in hook.py swallows a failure without saying so")
    print("          every handler announces a failure it caught; nothing fails silently")
else:
    report("FAIL", "no except block in hook.py swallows a failure without saying so")
    for h in silent_handlers:
        print(f"          {h}")

# --- and the last-resort net in main() speaks for EVERY event, not just guard and inject -------
for ev, needle in (
    ("scope", "scope"),
    ("artifact", "artifact"),
    ("runnable", "runnable"),
    ("handover", "handover"),
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

# --- the command-handover check at Stop --------------------------------------------------------
def hand_case(expect, title, payload, mode=""):
    env = dict(os.environ)
    if mode == "toggle":
        env["HOUSE_RULES_HANDOVER"] = "off"
    elif mode == "nopath":
        env["PATH"] = ""
    code, out, err = run_hook("handover", payload, env=env)
    if '"hookEventName":"Stop"' in out and '"additionalContext"' in out:
        got = "feedback"
    elif '"decision":"block"' in out:
        got = "block (the old shape - additionalContext is what it should emit now)"
    elif "systemMessage" in out and "house-rules plugin:" in out:
        got = "offline"
    elif "systemMessage" in out:
        got = "trace"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    if code != 0:
        got = f"{got} (exit {code})"
    report("PASS" if got == expect else "FAIL", title)
    print(f"          expected {expect}, got {got}")


# The firing condition IS the behaviour under test: this check used to fire on every turn,
# including turns that handed over nothing, which forced Claude to answer it in the user's
# view. It now reads last_assistant_message - the documented field for the just-written reply.
hand_case(
    "feedback",
    "a reply containing a fenced block gets the handover checklist",
    stop_payload(
        last_assistant_message="Run this:\n\n```powershell\nGet-ChildItem\n```\n"
    ),
)
hand_case(
    "silent",
    "a reply with no fenced block handed over nothing, so the check stays quiet",
    stop_payload(
        last_assistant_message="I opened the pull request; nothing for you to run."
    ),
)
# 2.9.0 shipped "a card never announces its own compliance" as a rule and then violated it on
# every conforming handover: the check fired, the turn continued, and the only thing left to say
# was that nothing needed saying. Wording could not fix that - it was tried twice - because a
# continued turn cannot be silent. Not firing can.
hand_case(
    "silent",
    "a reply already in card shape is not re-checked - firing there can only produce the "
    "compliance announcement the rules forbid",
    stop_payload(
        last_assistant_message=(
            "**Update the plugin: 1 step.**\n\n---\n\n### Step 1 of 1 - Update\n\n"
            "Navigate to `C:\\repo` and open **PowerShell** there.\n\n"
            "```powershell\nclaude plugin update house-rules@aj-house-rules\n```\n\n"
            "**You should see:** house-rules reported as updated.\n\n---\n"
        )
    ),
)
hand_case(
    "feedback",
    "a fenced command that is not in card shape is still checked - the gate is card markers, "
    "not the mere presence of a fence",
    stop_payload(
        last_assistant_message="Run `claude plugin update` from the repo:\n\n```powershell\nclaude plugin update\n```\n"
    ),
)
hand_case(
    "feedback",
    "a payload with no last_assistant_message still fires - a CLI without it must not "
    "silently disable the check",
    stop_payload(),
)
hand_case(
    "silent",
    "the retry after the check is allowed to finish - it cannot loop",
    stop_payload(stop_hook_active=True, last_assistant_message="```sh\nls\n```"),
)
hand_case(
    "silent",
    "the toggle switches the check off without touching any file",
    stop_payload(last_assistant_message="```sh\nls\n```"),
    mode="toggle",
)
# This used to expect silence, on the reasoning that an empty payload is "nothing to check".
# The "nothing fails silently" rule reverses that: an empty payload is not a turn with no
# command in it, it is a check that never got its input, and the two must not look the same.
hand_case("offline", "an empty payload is a check that could not run, and says so", "")

# --- fence gating narrows to a SHELL-labelled fence, not any fence -----------------------------
hand_case(
    "feedback",
    "a shell-labelled fence (bash) still fires the card check",
    stop_payload(last_assistant_message="Run this:\n\n```bash\nls -la\n```\n"),
)
hand_case(
    "silent",
    "a python-labelled fence is not a command handover, so the card check stays quiet",
    stop_payload(last_assistant_message="```python\nprint('hi')\n```\n"),
)
hand_case(
    "silent",
    "an unlabelled fence is not a command handover, so the card check stays quiet",
    stop_payload(last_assistant_message="```\nsome output\n```\n"),
)


_HAND_NO_TOOL = _hand_transcript("no-tool", [
    json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "please fix the bug"}}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Looking into it."}]}}),
])
_HAND_WITH_TOOL = _hand_transcript("with-tool", [
    json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "please fix the bug"}}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}]}}),
    json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "5 passed"}]}}),
])

hand_case(
    "feedback",
    "a success claim with no tool run since the last real message gets the evidence reminder",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Fixed the bug, it works now.",
    ),
)
hand_case(
    "silent",
    "a success claim backed by a tool call since the last real message stays quiet",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="Fixed the bug, it works now.",
    ),
)
hand_case(
    "silent",
    "a success claim that quotes real RESULT: output stays quiet, even with no tool this turn",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="It works now.\n\nRESULT: PASS",
    ),
)
# #89 reversed this one: it used to expect silence, because "untested" is not a success word.
# But a bare "untested" with no reason is exactly the disclosure-instead-of-checking #89 is about.
hand_case(
    "feedback",
    "a bare 'untested' with no reason the check could not run gets told to run it (#89)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="This is untested; I have not run it.",
    ),
)
hand_case(
    "silent",
    "an 'untested' that says in the same sentence why the check cannot run stays quiet (#89)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="This is untested because the Unity editor is not installed here.",
    ),
)
hand_case(
    "feedback",
    "a 'not checked' with no reason fires even when tools ran this turn (#89)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="I ran the tests. I haven't checked the CI logs.",
    ),
)
hand_case(
    "silent",
    "a handover card's own UNTESTED: marker is not what the not-checked check trips on (#89)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="UNTESTED: this runs on your machine.\n\nNothing else to report.",
    ),
)
hand_case(
    "feedback",
    "'that can't be done' with no tool run this turn gets the evidence reminder (#92)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="That can't be done in Claude Code; there is no setting for it.",
    ),
)
hand_case(
    "silent",
    "'that can't be done' after a tool ran this turn stays quiet (#92)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="That can't be done in Claude Code; there is no setting for it.",
    ),
)
hand_case(
    "silent",
    "'it is possible' is not an impossibility claim (#92)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Yes, it is possible to configure that.",
    ),
)
hand_case(
    "silent",
    "a phrase in quotation marks is being talked about, not asserted, so neither check fires",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message='Adding checks for "can\'t be done" claims and for a bare "untested".',
    ),
)
_, _out92, _ = run_hook("handover", stop_payload(
    transcript_path=_HAND_NO_TOOL,
    last_assistant_message="That setting doesn't exist.",
))
report("PASS" if "cannot be done or does not exist" in _out92 and "doesn't exist" in _out92 else "FAIL",
       "the #92 note names the impossibility phrase it caught")
print(f"          {_out92[:160]!r}")
hand_case(
    "silent",
    "a reply naming no claim word at all is untouched by the evidence check",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="I opened the pull request; nothing for you to run.",
    ),
)
hand_case(
    "trace",
    "a success claim whose transcript cannot be read fails open with a systemMessage, never a block",
    stop_payload(
        transcript_path=os.path.join(_HAND_ROOT, "does-not-exist.jsonl"),
        last_assistant_message="Fixed the bug, it works now.",
    ),
)

# A shell fence always satisfies the evidence check's own "quotes evidence" exemption, so the
# two checks can never both fire live on one reply - see doc-ref 6534 docs/6-decisions/Decisions.md.
code, out, err = run_hook(
    "handover",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Fixed the bug, it works now:\n\n```bash\ndeploy.sh\n```\n",
    ),
)
if '"hookEventName":"Stop"' in out and '"additionalContext"' in out and out.count('"hookSpecificOutput"') == 1:
    report("PASS", "a reply with both a shell fence and a claim still emits exactly one valid JSON object")
    print("          the fence's own evidence-quote exemption means only the card note fires here")
else:
    report("FAIL", "a reply with both a shell fence and a claim still emits exactly one valid JSON object")
    print(f"          out {out[:200]!r}")
pv_case("Stop: a port that wrote files but names nothing kept or dropped gets the parity report note (#90)",
        _par, "parity=%s" % _par)
pv_case("Stop (#309): the parity note is report-only - it demands no inventory or issues before the turn ends",
        "report only, #309" in _pv_ctx and "Nothing is required this turn" in _pv_ctx
        and "keep/change/drop inventory with" not in _pv_ctx,
        "note=%r" % _pv_ctx[_pv_ctx.find("re-creating"):][:200])
_par, _, _ = _stop_notes(_pv_port, "Kept search and sorting; dropped the server sync, which needs a server.")
pv_case("Stop: a port whose reply names what was kept and dropped gets no parity note", not _par, "parity=%s" % _par)
_par, _, _ = _stop_notes(_pv_port, "Done.", HOUSE_RULES_PARITY="off")
pv_case("Stop: HOUSE_RULES_PARITY=off switches the parity check off", not _par, "parity=%s" % _par)
_pv_edit = _turn_transcript("pv-edit", "replace the colour in the header", [("Edit", "/proj/src/app.py")])
_par, _vis, _ = _stop_notes(_pv_edit, "Changed the colour.")
pv_case("Stop: an everyday 'replace' edit to a non-visual file trips neither check", not _par and not _vis,
        "parity=%s visual=%s" % (_par, _vis))

_, out, _ = run_hook("scope", json.dumps({"prompt": "rewrite the scraper workflow from scratch"}))
pv_case("scope: a prompt that reads like a rewrite gets the inventory-first clause", "re-creating existing behaviour" in out,
        "clause=%s" % ("re-creating existing behaviour" in out))
_, out, _ = run_hook("scope", json.dumps({"prompt": "replace the colour in header.css"}))
pv_case("scope: an everyday 'replace' prompt does not", "re-creating existing behaviour" not in out,
        "clause=%s" % ("re-creating existing behaviour" in out))

_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"]
# The agentcap entry runs only on an Agent spawn (plan: allowed), so it is exempt from this count;
# so is guardgithub (#178), which runs only on a GitHub MCP write; and pagecheck (#257), which
# exits at once unless the call is an .html page Write or an Artifact call; and closablemerge (#362), which
# exits at once unless the call is a merge.
# 11, not 10, since promptran (#149): one process per prompt-capable tool call, measured at about
# the same cost as artifact's, and the only way to tell the timer an action actually ran.
# 13 since settingsgate (#341): one process on every tool call, the cost of refusing every tool while a setting is unset.
_non_agent = [g for g in _hj.get("PreToolUse", []) + _hj.get("PostToolUse", []) if not any("agentcap" in h["command"] or "guardgithub" in h["command"] or "pagecheck" in h["command"] or "closablemerge" in h["command"] for h in g["hooks"])]
_tool_cmds = [h["command"] for g in _non_agent for h in g["hooks"]]
_count_entries = sum(len(g["hooks"]) for g in _non_agent)
commit_case(
    "issues: no new hook process on Write/Edit/Bash - Pre/PostToolUse entries carry no issue-specific command",
    not any("issue" in c for c in _tool_cmds) and _count_entries == 13 and any('run.sh\\" issuelist' in json.dumps(g) for g in _hj["SessionStart"]),
    "%d Pre/PostToolUse entries; issuelist is on SessionStart" % _count_entries,
)

# profile: a saved memory restating the replaced commit rule is flagged at session start.
_mem = tempfile.mkdtemp(prefix="house-rules-memory-", dir=_FIXTURE_ROOT)
with open(os.path.join(_mem, "MEMORY.md"), "w", encoding="utf-8") as f:
    f.write("# Memory\n\n- Never run git actions; commit before destructive changes\n")
with open(os.path.join(_mem, "other.md"), "w", encoding="utf-8") as f:
    f.write("- prefers tabs over spaces\n")
_, out, _ = run_hook("profile", "", env=_project_env(_FIXTURE_ROOT, HOUSE_RULES_MEMORY_DIR=_mem))
commit_case(
    "profile: a memory restating the old commit rule is flagged by file and line at session start",
    "restates the old commit rule" in out and "MEMORY.md:3" in out and "other.md" not in out,
    "found: %s" % ("yes" if "restates the old commit rule" in out else "no"),
)
_clean_mem = tempfile.mkdtemp(prefix="house-rules-memory-clean-", dir=_FIXTURE_ROOT)
with open(os.path.join(_clean_mem, "MEMORY.md"), "w", encoding="utf-8") as f:
    f.write("- Commit freely on claude/ branches\n")
_, out, _ = run_hook("profile", "", env=_project_env(_FIXTURE_ROOT, HOUSE_RULES_MEMORY_DIR=_clean_mem))
commit_case(
    "profile: a memory that agrees with the commit rule adds nothing",
    "restates the old commit rule" not in out,
    "flagged: %s" % ("yes" if "restates the old commit rule" in out else "no"),
)

# --- the check gives guidance, not a hook error ----------------------------------------------
code, out, err = run_hook(
    "handover", stop_payload(last_assistant_message="```powershell\nGet-ChildItem\n```")
)
if '"hookEventName":"Stop"' in out and '"decision"' not in out:
    report("PASS", "the handover check emits Stop feedback, not a blocking hook error")
    print("          additionalContext on hookEventName Stop; no decision field")
else:
    report("FAIL", "the handover check emits Stop feedback, not a blocking hook error")
    print(f"          got: {out[:200]!r}")

for _restatement in [RESTATEMENTS[_i] for _i in (0, 3, 4, 7)]:  # core
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

# --- the state machine this replaced is really gone, and no *.sh hook script survives --------
gone = []
for dead in ["track-write.sh", "clear-pending.sh", "deliverable.sh"] + [
    "inject.sh",
    "scope.sh",
    "guard.sh",
    "artifact.sh",
    "runnable.sh",
    "handover.sh",
    "delegate.sh",
]:
    if os.path.exists(os.path.join(HERE, dead)):
        gone.append(f"{dead} still exists")
if ".sh\"" in hooks_json_text:
    gone.append("hooks.json still references a .sh hook script directly")
if "house-rules-deliverable" in "".join(read(p) for p in (HOOK, CORE, SAFE_GIT, DOCS, DELEGATION, DESIGN_LOOP, WRITING)):
    gone.append("hook.py still writes deliverable state")
if not gone:
    report("PASS", "the stateful deliverable machinery and the old .sh hooks are gone")
    print("          every hook is stateless; hooks.json calls only run.sh")
else:
    report("FAIL", "the stateful deliverable machinery and the old .sh hooks are gone")
    print(f"          {'; '.join(gone)}")

# --- house-rules.md states the card format once, and it has not displaced item 6 -------------
carddrift = []
card_hits = [m for m in re.finditer(r"^#### The card$", rules_text, re.MULTILINE)]
if len(card_hits) != 1:
    carddrift.append(f"found {len(card_hits)} '#### The card' headings, expected exactly 1")
if not re.search(r"^6\. \*\*One numbered step per action\*\*", rules_text, re.MULTILINE):
    carddrift.append("item 6 of the handover format is gone - the card must not displace it")
if "never inside it" not in rules_text:
    carddrift.append("item 5 no longer says UNTESTED: goes above the fence, not inside it")
if not carddrift:
    report("PASS", "house-rules.md states the card format once, alongside the six items")
    print("          one '#### The card' heading; item 6 and the UNTESTED: placement intact")
else:
    report("FAIL", "house-rules.md states the card format once, alongside the six items")
    print(f"          {'; '.join(carddrift)}")

# --- the output style exists and IS forced ---------------------------------------------------
# Why this was reversed in 2.4.0: docs/architecture.md, "Why the output style is forced".
styledrift = []
if not os.path.isfile(STYLE):
    styledrift.append("output-styles/handover-cards.md is missing")
else:
    style_text = read(STYLE)
    if not re.search(r"^name: ", style_text, re.MULTILINE):
        styledrift.append("the style has no name: field")
    if not re.search(r"^description: ", style_text, re.MULTILINE):
        styledrift.append("the style has no description: field")
    if not re.search(r"^keep-coding-instructions: true$", style_text, re.MULTILINE):
        styledrift.append("the style does not keep-coding-instructions, so it would replace them")
    # The style is now the single copy of the six-field checklist (docs/6-decisions/Decisions.md,
    # 2026-09-22); the check below this one proves the core points here instead of restating it.
    for phrase in ["runs from anywhere", "One numbered step per action", "UNTESTED:"]:
        if phrase not in style_text:
            styledrift.append(f"the style no longer restates {phrase!r} from the six items")
    if not re.search(r"^force-for-plugin: true$", style_text, re.MULTILINE):
        styledrift.append(
            "the style does not set force-for-plugin: true - without it the style is "
            "unreachable on the desktop app, which has no picker and no /output-style command"
        )
if not styledrift:
    report("PASS", "the handover-cards output style is forced, so it applies without a picker")
    print("          keeps the coding instructions; applies on surfaces with no way to select one")
else:
    report("FAIL", "the handover-cards output style is forced, so it applies without a picker")
    print(f"          {'; '.join(styledrift)}")

# --- the core's card section points at the output style instead of restating it --------------
# Moved out of house-rules.md 2.17.0 to stay under the per-hook context limit (docs/6-decisions/Decisions.md,
# 2026-09-22): the core keeps a one-line pointer, the output style keeps the actual checklist.
cardptr = []
_core_text = read(RULES_FILE)
_card_sec = _core_text.split("#### The card", 1)
if len(_card_sec) != 2:
    cardptr.append("'#### The card' heading is missing from house-rules.md")
else:
    _pointer_body = _card_sec[1].split("\n## ", 1)[0]
    if "handover-cards" not in _pointer_body:
        cardptr.append("the core's card section does not name the handover-cards output style")
    for phrase in ["runs from anywhere", "One numbered step per action", "UNTESTED:"]:
        if phrase in _pointer_body:
            cardptr.append(f"{phrase!r} is restated in the core instead of pointed at")
if not cardptr:
    report("PASS", "the core's card section points at the output style instead of restating it")
    print("          house-rules.md names handover-cards.md; the six-field text lives there only")
else:
    report("FAIL", "the core's card section points at the output style instead of restating it")
    print(f"          {'; '.join(cardptr)}")

# --- the step-card page template exists, is self-contained, and matches the card's fields ----
tpldrift = []
if not os.path.isfile(TEMPLATE):
    tpldrift.append("templates/step-card.html is missing")
else:
    tpl = read(TEMPLATE)
    if "const STEPS" not in tpl:
        tpldrift.append("no `const STEPS` array for Claude to fill")
    for external in ["<script src=", '<link rel="stylesheet"', "https://"]:
        if external in tpl:
            tpldrift.append(f"contains {external!r} - the page must work offline, with no network")
    for field in ["title:", "location:", "how:", "shell:", "command:", "expect:", "untested:"]:
        if field not in tpl:
            tpldrift.append(f"the STEPS array has no {field} field, so it cannot carry the card")
if not tpldrift:
    report("PASS", "the step-card page template is self-contained and carries every card field")
    print("          no external script, stylesheet or fetch; STEPS mirrors the markdown card")
else:
    report("FAIL", "the step-card page template is self-contained and carries every card field")
    print(f"          {'; '.join(tpldrift)}")

# --- the rules teach the anti-patterns, not only the patterns --------------------------------
# 2.3.0 shipped a template showing only the CORRECT location sentence, and the next real handover
# reverted to the old shorthand anyway. A positive-only example is what failed, so the negative
# form and the sequence-vs-menu rule are pinned here rather than trusted to stay.
teachdrift = []
for phrase, why in [
    ("is a label on a command, not a step", "the item-1 anti-pattern example is gone"),
    ("never the shell I ran it in", "the path-notation rule is gone"),
    ("does not `cd` there again", "the redundant-cd rule is gone"),
    ("A card is a sequence, not a menu", "the sequence-vs-menu heading is gone"),
    ("AskUserQuestion", "the rules no longer say a blocking choice is a question, not a menu"),
]:
    if phrase not in rules_text:
        teachdrift.append(why)
if not teachdrift:
    report("PASS", "the rules show the anti-patterns, not only the correct forms")
    print("          item-1 counter-example, path notation, redundant cd, sequence vs menu")
else:
    report("FAIL", "the rules show the anti-patterns, not only the correct forms")
    print(f"          {'; '.join(teachdrift)}")

# --- every surface the architecture.md table claims has a way to be checked ------------------
# The table moved from CLAUDE.md to docs/architecture.md (docs/6-decisions/Decisions.md, 2026-09-22, step 2);
# surface names are read out of the table itself rather than hardcoded here.
surfdrift = []
surfaces = []
_absent = absent_repo_files("docs/desktop-verification.md", "docs/architecture.md")
if _absent:
    skip_repo_check(
        "every surface in the architecture.md table has a check in desktop-verification.md", _absent
    )
elif not os.path.isfile(VERIFYDOC):
    surfdrift.append("docs/desktop-verification.md is missing")
elif not os.path.isfile(ARCHDOC):
    surfdrift.append("docs/architecture.md is missing, so the table it claims cannot be read")
else:
    verify_doc = read(VERIFYDOC)
    for line in read(ARCHDOC).splitlines():
        m = re.match(r"^\| (?:Claude Code|claude\.ai chat) [-\u2014 ]+([^|]+?) \|", line)
        if m:
            surfaces.append(m.group(1).strip())
    if not surfaces:
        surfdrift.append("no surface rows found in docs/architecture.md - has the table been renamed?")
    for s in surfaces:
        if s not in verify_doc:
            surfdrift.append(f"{s!r} is in the architecture.md table but has no check in desktop-verification.md")
if _absent:
    pass  # already reported as skipped above
elif not surfdrift:
    report("PASS", "every surface in the architecture.md table has a check in desktop-verification.md")
    print(f"          {len(surfaces)} surfaces claimed, {len(surfaces)} covered: {', '.join(surfaces)}")
else:
    report("FAIL", "every surface in the architecture.md table has a check in desktop-verification.md")
    print(f"          {'; '.join(surfdrift)}")

# --- the card template was not duplicated into CLAUDE.md -------------------------------------
# Same reasoning as the rules-duplication check above: CLAUDE.md is a pointer. A second copy of
# the template would load twice and drift from the real one unnoticed.
dupe = []
_absent = absent_repo_files("CLAUDE.md")
if _absent:
    skip_repo_check("the card template was not duplicated into CLAUDE.md", _absent)
elif os.path.isfile(root_claude):
    claude_text = read(root_claude)
    for marker in ["### Step 1 of", "**You should see:**", "*Next: step 2"]:
        if marker in claude_text:
            dupe.append(f"CLAUDE.md contains {marker!r} - the template belongs only in house-rules.md")
if _absent:
    pass  # already reported as skipped above
elif not dupe:
    report("PASS", "the card template was not duplicated into CLAUDE.md")
    print("          CLAUDE.md describes the format and points at rules/house-rules.md for it")
else:
    report("FAIL", "the card template was not duplicated into CLAUDE.md")
    print(f"          {'; '.join(dupe)}")

# --- the claude.ai chat block exists and has not drifted from the rules document -------------
# Hooks do not run in claude.ai chat, so this file is the only thing covering that surface (and
# the phone). It is a restatement, so it gets the same drift treatment as hook.py's strings.
chatdrift = []
_absent = absent_repo_files("docs/claude-ai-instructions.md")
if _absent:
    skip_repo_check("the claude.ai chat block exists and matches the rules document", _absent)
elif not os.path.isfile(CHATDOC):
    chatdrift.append("docs/claude-ai-instructions.md is missing")
else:
    chat_text = read(CHATDOC)
    if chat_text.count("````") != 2:
        chatdrift.append(
            f"expected exactly one paste-able block delimited by ````, found "
            f"{chat_text.count('````')} markers"
        )
    for phrase in ["fence label", "UNTESTED:", "You should see:", "Step 1 of", "above the fence"]:
        if phrase not in chat_text:
            chatdrift.append(f"the block does not state {phrase!r}")
        elif phrase not in rules_text:
            chatdrift.append(f"{phrase!r} is in the chat block but not in house-rules.md")
if _absent:
    pass  # already reported as skipped above
elif not chatdrift:
    report("PASS", "the claude.ai chat block exists and matches the rules document")
    print("          one paste-able block; every phrase in it also appears in house-rules.md")
else:
    report("FAIL", "the claude.ai chat block exists and matches the rules document")
    print(f"          {'; '.join(chatdrift)}")

# --- install.py still writes the model setting the README claims ------------------------------
install_path = os.path.join(ROOT, "tools", "install.py")
moddrift = []
_absent = absent_repo_files(os.path.join("tools", "install.py"), readme_rel, "docs/architecture.md")
if _absent:
    skip_repo_check("install.py sets model = opusplan and the docs scope it correctly", _absent)
elif not os.path.isfile(install_path):
    moddrift.append("tools/install.py is missing")
else:
    install_text = read(install_path)
    if '"name": "model"' not in install_text:
        moddrift.append("install.py no longer writes a model setting")
    if "opusplan" not in install_text:
        moddrift.append("install.py no longer sets opusplan")
if os.path.isfile(readme_path) and "opusplan" not in read(readme_path):
    moddrift.append("the README does not document opusplan")
for docfile in [readme_path, ARCHDOC]:
    if os.path.isfile(docfile):
        if "cli and the ide" not in read(docfile).lower():
            moddrift.append(
                f"{os.path.basename(docfile)} does not say opusplan covers only the CLI and the IDE"
            )
if _absent:
    pass  # already reported as skipped above
elif not moddrift:
    report("PASS", "install.py sets model = opusplan and the docs scope it correctly")
    print("          opusplan on the CLI and IDE; every other surface via @house-rules:builder")
else:
    report("FAIL", "install.py sets model = opusplan and the docs scope it correctly")
    print(f"          {'; '.join(moddrift)}")

# --- preflight warns about a missing dependency, and points at /house-rules:doctor -----------
env = dict(os.environ)
env["PATH"] = ""
code, out, err = run_hook("profile", "", env=env)
if "Preflight gaps found" in out and "git is not on PATH" in out and "/house-rules:doctor" in out:
    report("PASS", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print("          a broken PATH produces a visible, actionable preflight warning")
else:
    report("FAIL", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print(f"          got: {out[-400:]!r}")

code, out, err = run_hook("profile", "")
if "Preflight gaps found" not in out:
    report("PASS", "SessionStart preflight is silent when there is nothing to warn about")
    print("          a clean machine adds nothing to the injection")
else:
    report("FAIL", "SessionStart preflight is silent when there is nothing to warn about")
    print(f"          got: {out[-400:]!r}")

# --- profile truncates only the environment body, never preflight or the handover block -------
# Coordinator review of 9e7e780: the first cut truncated the WHOLE assembled profile text, which
# could in principle have cut into preflight warnings or the remote handover-target block instead
# of just the oversized profile. Fixed to truncate envbody alone; this proves it.
_oversized_env = os.path.join(_FIXTURE_ROOT, "oversized-environment.md")
with open(_oversized_env, "w", encoding="utf-8") as _f:
    _f.write("# Huge profile\n\n" + ("filler line about this machine\n" * 2000))
_handover_fixture2 = os.path.join(_FIXTURE_ROOT, "handover-target-2.md")
with open(_handover_fixture2, "w", encoding="utf-8") as _f:
    _f.write("# The human's machine\n\nWindows 11, PowerShell, Git Bash for POSIX.\n")
_env = env_in(
    ROOT,
    PATH="",  # also forces a preflight warning, so both survivors are exercised at once
    HOUSE_RULES_ENV_FILE=_oversized_env,
    CLAUDE_CODE_REMOTE="true",
    HOUSE_RULES_HANDOVER_TARGET_FILE=_handover_fixture2,
)
_code, _trunc_out, _err = run_hook("profile", "", env=_env)
_trunc_problems = []
if "Git Bash for POSIX" not in _trunc_out:
    _trunc_problems.append("the handover-target block did not survive truncation intact")
if "Preflight gaps found" not in _trunc_out:
    _trunc_problems.append("preflight warnings did not survive truncation intact")
if os.path.basename(_oversized_env) not in _trunc_out and _oversized_env not in _trunc_out:
    _trunc_problems.append("the truncation notice does not name the oversized file")
if not _trunc_problems:
    report("PASS", "profile truncates only the environment body, never preflight or the handover block")
    print(f"          {len(_trunc_out)} chars total; handover block and preflight both intact")
else:
    report("FAIL", "profile truncates only the environment body, never preflight or the handover block")
    print(f"          {'; '.join(_trunc_problems)}")

# --- /house-rules:doctor exists and maps gaps to an install command per OS --------------------
DOCTOR = os.path.join(HERE, "..", "commands", "doctor.md")
doctordrift = []
if not os.path.isfile(DOCTOR):
    doctordrift.append("commands/doctor.md is missing")
else:
    doctor_text = read(DOCTOR)
    for needle in ["winget install Python", "brew install python", "apt install python3", "dnf install python3"]:
        if needle not in doctor_text:
            doctordrift.append(f"doctor.md is missing the install command: {needle}")
if not doctordrift:
    report("PASS", "/house-rules:doctor maps every interpreter gap to an OS-specific install command")
    print("          winget/brew/apt/dnf all covered")
else:
    report("FAIL", "/house-rules:doctor maps every interpreter gap to an OS-specific install command")
    print(f"          {'; '.join(doctordrift)}")

# --- the architecture tables in docs/architecture.md and the README match hooks.json ----------
# Registered dispatch events, read from hooks.json's run.sh invocations rather than filenames -
# there is only one script (run.sh) now, dispatched by event argument. The table moved from
# CLAUDE.md to docs/architecture.md (docs/6-decisions/Decisions.md, 2026-09-22, step 2).
registered_events = sorted(set(re.findall(r'run\.sh\\" ([a-z]+)', hooks_json_text)))
docdrift = []
_absent = absent_repo_files("docs/architecture.md", readme_rel)
for doc in ([] if _absent else [ARCHDOC, readme_path]):
    docname = os.path.basename(doc)
    if not os.path.isfile(doc):
        docdrift.append(f"no {docname} to check")
        continue
    doc_text = read(doc)
    table_lines = "\n".join(
        line
        for line in doc_text.splitlines()
        if re.match(r"^\| `(SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|PermissionRequest|Stop|SubagentStart|SubagentStop)`", line)
    )
    for event in registered_events:
        if event not in table_lines:
            docdrift.append(f"{event} is a registered hook event but has no row in the {docname} table")
    if "four hooks, nothing else" in doc_text:
        docdrift.append(f"{docname} still says four hooks")
    if re.search(r"[0-9]+-check|all [0-9]+ checks", doc_text):
        docdrift.append(f"{docname} hardcodes a check count, which drifts")
    if re.search(r"(four|five|six|seven|eight|nine) hooks", doc_text, re.IGNORECASE):
        docdrift.append(f"{docname} spells out a hook count, which drifts")
# The reverse direction: every *.sh in scripts/ (other than verify.py itself has no .sh
# counterpart) must be registered - there should be none left except run.sh.
for fname in os.listdir(HERE):
    if fname.endswith(".sh") and fname != "run.sh":
        docdrift.append(f"{fname} exists but is not run.sh - a leftover hook script")
if docdrift and _absent:
    report("FAIL", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print(f"          {'; '.join(docdrift)}")
elif _absent:
    skip_repo_check(
        "the architecture tables in docs/architecture.md and the README match hooks.json",
        _absent,
        extra="scripts/ was checked here and holds no stray .sh; only the doc tables are unavailable",
    )
elif not docdrift:
    report("PASS", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print("          every registered hook event is documented and no stray .sh script exists")
else:
    report("FAIL", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print(f"          {'; '.join(docdrift)}")


def std_case(title, files, check):
    """Build a fixture dir under the scratchpad-style temp dir, run the standards handler
    with CLAUDE_PROJECT_DIR pointed at it, check the output, then remove the fixture."""
    d = make_fixture(files)
    try:
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = d
        code, out, err = run_hook("standards", "", env=env)
        ok, detail = check(out)
        report("PASS" if ok else "FAIL", title)
        print(f"          {detail}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


std_case(
    "a bare directory injects coding-philosophy and neither ecosystem document",
    {},
    lambda out: (
        "### coding-philosophy.md" in out
        and "### csharp-unity-standards.md" not in out
        and "### web-js-ts-node-standards.md" not in out,
        f"philosophy-only preamble: {out[:160]!r}",
    ),
)

std_case(
    "ProjectSettings/ProjectVersion.txt injects the C#/Unity document",
    {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"},
    lambda out: (
        "### csharp-unity-standards.md" in out and "### web-js-ts-node-standards.md" not in out,
        f"got: {out[:160]!r}",
    ),
)

std_case(
    "package.json injects the web document",
    {"package.json": "{}"},
    lambda out: (
        "### web-js-ts-node-standards.md" in out and "### csharp-unity-standards.md" not in out,
        f"got: {out[:160]!r}",
    ),
)

std_case(
    "both markers at the root injects all three documents",
    {"package.json": "{}", "ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"},
    lambda out: (
        "### coding-philosophy.md" in out
        and "### csharp-unity-standards.md" in out
        and "### web-js-ts-node-standards.md" in out,
        f"got: {out[:160]!r}",
    ),
)

std_case(
    "the mixed-repo case (Node at root, Unity one level down) injects all three and names Game/",
    {"package.json": "{}", "Game/ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"},
    lambda out: (
        "### coding-philosophy.md" in out
        and "### csharp-unity-standards.md" in out
        and "### web-js-ts-node-standards.md" in out
        and "in `Game/`" in out,
        f"got: {out[:400]!r}",
    ),
)

std_case(
    "node_modules/package.json in an otherwise bare directory does not select the web document",
    {"node_modules/package.json": "{}"},
    lambda out: (
        "### web-js-ts-node-standards.md" not in out and "### coding-philosophy.md" in out,
        f"got: {out[:160]!r}",
    ),
)

std_case(
    ".claude/standards naming only the web document in a Unity-shaped directory overrides detection",
    {
        "ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n",
        ".claude/standards": "web-js-ts-node-standards\n",
    },
    lambda out: (
        "### web-js-ts-node-standards.md" in out and "### csharp-unity-standards.md" not in out,
        f"got: {out[:160]!r}",
    ),
)

std_case(
    ".claude/standards naming a nonexistent document produces a systemMessage, not silence",
    {".claude/standards": "nonexistent-doc\n"},
    lambda out: (
        '"systemMessage"' in out and out.strip() != "",
        f"got: {out[:200]!r}",
    ),
)

# opening a Unity project at its Assets/ folder (a normal workflow) rather than the project
# root one level up - the sibling ProjectSettings/*.csproj never show up in the depth-1 scan
# because they live above project_dir, not inside it. See _unity_markers_in_parent. A sibling
# Node service (e.g. RockSkipping's controller/) must also be found - it's a depth-1 dir of the
# real project root, not of project_dir, so detection has to rescan from up there too.
assets_fixture = make_fixture(
    {
        "ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n",
        "controller/package.json": "{}",
    }
)
try:
    env_assets = dict(os.environ)
    env_assets["CLAUDE_PROJECT_DIR"] = os.path.join(assets_fixture, "Assets")
    os.makedirs(env_assets["CLAUDE_PROJECT_DIR"], exist_ok=True)
    code, out, err = run_hook("standards", "", env=env_assets)
    ok = (
        "### csharp-unity-standards.md" in out
        and "### web-js-ts-node-standards.md" in out
        and "Assets/` folder" in out
        and "in `controller/`" in out
    )
    report(
        "PASS" if ok else "FAIL",
        "a project rooted at a Unity project's Assets/ folder injects both Unity and a "
        "sibling Node service's standards",
    )
    print(f"          got: {out[:300]!r}")
finally:
    shutil.rmtree(assets_fixture, ignore_errors=True)

# --- standards stays under budget in Unity projects, where the Unity rule now lives ----------
# The standards budget was only ever measured in this repo, which has no Unity markers, so a
# Unity project sailed past the 10,000-char hard limit unseen (docs/6-decisions/Decisions.md,
# 2026-09-29). These two fixtures are the check that was missing.
STANDARDS_BUDGET = 9_500


def _standards_len(out):
    try:
        return len(json.loads(out)["hookSpecificOutput"]["additionalContext"])
    except Exception as exc:
        return f"unparseable ({exc}): {out[:120]!r}"


for _title, _files in [
    ("a Unity-only project", {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"}),
    ("a Unity + Node project", {"Assets/Scripts/a.cs": "", "package.json": "{}"}),
]:
    def _within_budget(out):
        n = _standards_len(out)
        return isinstance(n, int) and n <= STANDARDS_BUDGET, f"{n} chars (budget {STANDARDS_BUDGET}, hard limit 10,000)"

    std_case(f"standards stays under its {STANDARDS_BUDGET:,}-char budget in {_title}", _files, _within_budget)

_UNITY_RULE_HEADING = "## Unity work starts with the Unity plugin and the Unity CLI"
std_case(
    "the Unity tools-first rule reaches a Unity project through standards, with both pointers",
    {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"},
    lambda out: (
        _UNITY_RULE_HEADING in out
        and "rules/detail/unity-tools-first.md" in out
        and "rules/standards/csharp-unity-detail.md" in out
        and "${CLAUDE_PLUGIN_ROOT}" not in out,
        f"got: {_standards_len(out)} chars; heading={_UNITY_RULE_HEADING in out}",
    ),
)
std_case(
    "the Unity tools-first rule does not reach a project with no Unity markers",
    {},
    lambda out: (_UNITY_RULE_HEADING not in out, "a bare directory got the Unity rule" if _UNITY_RULE_HEADING in out else "absent, as intended"),
)
_, _inject_out, _ = run_hook("inject", "", env=env_in(ROOT))
_core_text = read(RULES_FILE)
if (
    "Unity work starts" not in _inject_out
    and "unity-tools-first" not in _inject_out
    and "Unity work starts" not in _core_text
):
    report("PASS", "the Unity tools-first rule is not in the always-injected core")
    print("          neither house-rules.md nor the inject output carries it")
else:
    report("FAIL", "the Unity tools-first rule is not in the always-injected core")
    print("          the Unity rule is still in house-rules.md or the inject output")
_unity_detail = os.path.join(STANDARDS_DIR, "csharp-unity-detail.md")
if os.path.isfile(_unity_detail) and all(
    h in read(_unity_detail)
    for h in ("## Unity-specific patterns", "## Performance", "## Testing", "## Verifying compilation", "## Tooling (Rider)")
):
    report("PASS", "rules/standards/csharp-unity-detail.md holds the Unity sections moved out of the core")
    print("          all five named sections are present")
else:
    report("FAIL", "rules/standards/csharp-unity-detail.md holds the Unity sections moved out of the core")
    print(f"          {_unity_detail} is missing or lacks a moved section")

# --- the profile reports hardware and the Claude plan, and says so when it cannot -----------
# PATH is replaced by a directory holding only the fakes each case wants, so the result does not
# depend on whether this machine has nvidia-smi or a logged-in claude. POSIX shell fakes.
def _fake_bin(**scripts):
    d = tempfile.mkdtemp(prefix="house-rules-fakebin-")
    for name, body in scripts.items():
        path = os.path.join(d, name.replace("_", "-"))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(path, 0o755)
    return d


def _profile_out(path_dir, remote=False, **extra):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_REMOTE", None)
    env["PATH"] = path_dir
    env["HOUSE_RULES_ENV_FILE"] = "/nonexistent-on-purpose-env"
    env["HOUSE_RULES_HANDOVER_TARGET_FILE"] = "/nonexistent-on-purpose-handover"
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "1"
    env.update(extra)
    _, out, _ = run_hook("profile", "", env=env)
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return out


if os.name == "nt":
    for _t in ("the profile names CPU, RAM, GPU, free disk and Claude plan",
               "a missing nvidia-smi is reported as 'GPU: not detected (...)'",
               "a claude that reports no plan field is 'Claude plan: not detected (...)'",
               "a claude that reports a plan field has it shown",
               "nvidia-smi output is reported as GPU name and VRAM"):
        report("SKIP", _t + " (the fakes are POSIX shell scripts)")
else:
    _no_plan = _fake_bin(claude='echo \'{"loggedIn":true,"authMethod":"oauth_token","apiProvider":"firstParty"}\'')
    _with_plan = _fake_bin(claude='echo \'{"loggedIn":true,"subscriptionType":"max"}\'',
                           nvidia_smi='echo "NVIDIA Test GPU, 8192 MiB"')
    _empty = tempfile.mkdtemp(prefix="house-rules-emptybin-")
    try:
        _p = _profile_out(_no_plan)
        _missing = [f for f in ("CPU:", "RAM:", "GPU:", "Free disk:", "Claude plan:") if f not in _p]
        report("PASS" if not _missing else "FAIL", "the profile names CPU, RAM, GPU, free disk and Claude plan")
        print(f"          missing fields: {_missing}" if _missing else "          all five field names present")

        _gpu_line = next((l for l in _p.splitlines() if l.startswith("GPU:")), "")
        report("PASS" if _gpu_line.startswith("GPU: not detected (") and "nvidia-smi" in _gpu_line else "FAIL",
               "a missing nvidia-smi is reported as 'GPU: not detected (...)'")
        print(f"          {_gpu_line!r}")

        _plan_line = next((l for l in _p.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan_line.startswith("Claude plan: not detected (") and "no plan field" in _plan_line else "FAIL",
               "a claude that reports no plan field is 'Claude plan: not detected (...)'")
        print(f"          {_plan_line!r}")

        _p2 = _profile_out(_with_plan)
        _plan2 = next((l for l in _p2.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan2.startswith("Claude plan: max") else "FAIL",
               "a claude that reports a plan field has it shown")
        print(f"          {_plan2!r}")

        _gpu2 = next((l for l in _p2.splitlines() if l.startswith("GPU:")), "")
        report("PASS" if "NVIDIA Test GPU" in _gpu2 and "8192 MiB" in _gpu2 else "FAIL",
               "nvidia-smi output is reported as GPU name and VRAM")
        print(f"          {_gpu2!r}")

        _p3 = _profile_out(_empty)
        _plan3 = next((l for l in _p3.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan3.startswith("Claude plan: not detected (claude not on PATH)") else "FAIL",
               "no claude on PATH is 'Claude plan: not detected (claude not on PATH)'")
        print(f"          {_plan3!r}")
    finally:
        for _d in (_no_plan, _with_plan, _empty):
            shutil.rmtree(_d, ignore_errors=True)

# --- a remote profile never presents the sandbox's hardware as the local build budget --------
_remote_empty = tempfile.mkdtemp(prefix="house-rules-emptybin-")
try:
    _r = _profile_out(_remote_empty, remote=True)
    _r_ok = (
        "NOT the user's local build budget" in _r
        and "rules/handover-target.md" in _r
        and "## Hardware (the local build budget)" not in _r
        and "Ask for their hardware" in _r
    )
    report("PASS" if _r_ok else "FAIL",
           "a remote profile labels detected hardware as the sandbox's and asks for the user's")
    print("          sandbox label, handover-target pointer and hardware question present" if _r_ok
          else f"          got: {_r[-900:]!r}")
    _l = _profile_out(_remote_empty, remote=False)
    report("PASS" if "## Hardware (the local build budget)" in _l and "NOT the user's" not in _l else "FAIL",
           "a local profile calls the detected hardware the local build budget")
    print("          local label present, no sandbox caveat")
finally:
    shutil.rmtree(_remote_empty, ignore_errors=True)

# --- the open-source-first rule and its detail file agree ------------------------------------
_free_detail = os.path.join(DETAIL_DIR, "free-first.md")
_core = read(RULES_FILE)
_free_problems = []
if not os.path.isfile(_free_detail):
    _free_problems.append("rules/detail/free-first.md does not exist")
else:
    _fd = read(_free_detail)
    _core_rungs = ["Local OSS", "cloud OSS", "local free closed", "cloud free closed", "→ paid"]
    _detail_rungs = ["Local open source", "Cloud open source", "Local free closed source",
                     "Cloud free closed source", "Any paid option"]
    _core_rule = _core[_core.find("## Open source first"):].split("\n## ")[0]
    for label, text, rungs in (("house-rules.md", _core_rule, _core_rungs), ("free-first.md", _fd, _detail_rungs)):
        pos = [text.find(r) for r in rungs]
        if min(pos) < 0:
            _free_problems.append(f"{label} lacks ladder rung(s): {[r for r, p in zip(rungs, pos) if p < 0]}")
        elif pos != sorted(pos):
            _free_problems.append(f"{label} names the ladder rungs out of order")
    for phrase in ("OSI-approved", "Pro or Max", "Break-even", "guess"):
        if phrase not in _fd:
            _free_problems.append(f"free-first.md lacks {phrase!r}")
if "## Open source first; paid is the last resort" not in _core:
    _free_problems.append("house-rules.md lacks the rule heading")
if "${CLAUDE_PLUGIN_ROOT}/rules/detail/free-first.md" not in _core:
    _free_problems.append("house-rules.md does not point at rules/detail/free-first.md")
if "## Open source first; paid is the last resort" in _core and "## Read the docs first" in _core and \
        _core.index("## Open source first") > _core.index("## Read the docs first"):
    _free_problems.append("the rule is not placed before 'Read the docs first'")
if "free-first.md" not in read(os.path.join(DETAIL_DIR, "environment.md")):
    _free_problems.append("environment.md does not link free-first.md")
report("FAIL" if _free_problems else "PASS", "the open-source-first rule and rules/detail/free-first.md exist and agree")
print(f"          {'; '.join(_free_problems)}" if _free_problems else "          heading, pointer, ladder order in both files, estimate table terms all present")

# run.sh standards with no working interpreter still prints a visible warning and exits 0
env_nopath = dict(os.environ)
env_nopath.pop("HOUSE_RULES_PYTHON", None)
env_nopath["PATH"] = ""
code, out, err = run_shell([RUN, "standards"], env=env_nopath)
if code == 0 and '"systemMessage"' in out and "No coding standards were loaded" in out:
    report("PASS", "run.sh standards with no working interpreter still warns visibly and exits 0")
    print(f"          said: {out}")
else:
    report("FAIL", "run.sh standards with no working interpreter still warns visibly and exits 0")
    print(f"          exit code was {code}; stdout={out!r} stderr={err!r}")

# CLAUDE_PROJECT_DIR unset falls back to os.getcwd() and still detects correctly
cwd_fixture = make_fixture({"package.json": "{}"})
try:
    env_nocwd = dict(os.environ)
    env_nocwd.pop("CLAUDE_PROJECT_DIR", None)
    proc = subprocess.run(
        [sys.executable, HOOK, "standards"],
        cwd=cwd_fixture,
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env_nocwd,
    )
    out_cwd = proc.stdout.decode("utf-8", "replace")
    if "### web-js-ts-node-standards.md" in out_cwd:
        report("PASS", "CLAUDE_PROJECT_DIR unset falls back to the current directory and still detects")
        print("          detected the web document from os.getcwd() alone")
    else:
        report("FAIL", "CLAUDE_PROJECT_DIR unset falls back to the current directory and still detects")
        print(f"          got: {out_cwd[:200]!r}")
finally:
    shutil.rmtree(cwd_fixture, ignore_errors=True)

# Drift: the standards rule heading and the matching SCOPE_REMINDER phrase
std_drift = []
if "## Code follows the standards loaded for this project" not in rules_text:
    std_drift.append("house-rules.md is missing the standards rule heading")
for phrase in ["standards loaded for this project", "governs only its own"]:
    if phrase.lower() not in rules_text.lower():
        std_drift.append(f"scope reminder phrase missing from house-rules.md: {phrase}")
if not std_drift:
    report("PASS", "the standards rule heading and its SCOPE_REMINDER phrasing have not drifted")
    print("          house-rules.md states the rule and the scope reminder echoes it")
else:
    report("FAIL", "the standards rule heading and its SCOPE_REMINDER phrasing have not drifted")
    print(f"          {'; '.join(std_drift)}")

# an action approved some other way runs: promptran marks it, the waiting timer stops without a decision
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_ran_input = {"command": "git push -q"}
_ran_res = {}
_ran_t = threading.Thread(target=lambda: _ran_res.update(
    r=_pt_run(_pt_tool("Bash", _ran_input), HOUSE_RULES_PROMPT_TIMEOUT="4")))
_ran_t.start()
for _w in range(50):
    if any(e.get("status") == "waiting" for e in _pt_state_now()):
        break
    time.sleep(0.1)
_rr = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUse"), env=_pt_env())
_ran_t.join()
_ran = _ran_res.get("r", (None, "?", "", 99))
commit_case(
    "promptran: an action that ran while its prompt was waiting stops the timer with no decision and no entry",
    _rr[0] == 0 and _rr[1] == "" and _ran[0] == 0 and _ran[1] == "" and _ran[3] < 3.5
    and "the action ran" in _ran[2] and _pt_state_now() == [],
    "timer elapsed %.2fs out %r stderr %r state %r" % (_ran[3], _ran[1][:80], _ran[2][:150], _pt_state_now()),
)

# an action that ran AFTER being refused as timed out is removed and reported out loud
_pt_run(_pt_tool("Bash", _ran_input))
_late = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUseFailure"), env=_pt_env())
try:
    _late_o = json.loads(_late[1])
except Exception:
    _late_o = {}
commit_case(
    "promptran: a timed-out action that ran anyway is removed from the list and reported to aj and Claude",
    _late[0] == 0 and "ran although its permission prompt was refused" in _late_o.get("systemMessage", "")
    and "git push -q" in _late_o.get("systemMessage", "")
    and _late_o.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUseFailure"
    and _pt_state_now() == [],
    "out %r state %r" % (_late[1][:200], _pt_state_now()),
)
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_quiet = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUse"), env=_pt_env())
_bad = run_hook("promptran", "{not json", env=_pt_env())
commit_case(
    "promptran: with no waiting-on-you list, or a bad payload, it says nothing and exits 0",
    _quiet[0] == 0 and _quiet[1] == "" and _bad[0] == 0 and _bad[1] == "",
    "quiet %r bad %r" % (_quiet[1][:80], _bad[1][:80]),
)
_pr_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"]
_pr_entries = [g for ev in ("PostToolUse", "PostToolUseFailure") for g in _pr_hj.get(ev, [])
               if any(h["command"].endswith('run.sh" promptran') for h in g["hooks"])]
commit_case(
    "promptran: wired on PostToolUse and PostToolUseFailure, matched to the tools that raise permission prompts",
    len(_pr_entries) == 2 and all(len(g["hooks"]) == 1 and "Bash" in g.get("matcher", "")
                                  and "Read" not in g.get("matcher", "") for g in _pr_entries),
    "entries %r" % (_pr_entries,),
)

# --- versioncheck: the three-way plugin freshness check -----------------------------------------
# HOUSE_RULES_VC_MARKETPLACE/_GITHUB are test seams so this never touches real network or disk.
with open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), "r", encoding="utf-8") as f:
    _installed_version = json.load(f).get("version", "")


def vc_clear(case):
    """Remove what an earlier run left for this case, so a stale marker or log cannot pass or
    fail it."""
    for path in (vc_marker_path(case), os.path.join(_vc_fake_dir, f"calls-{case}.log")):
        if os.path.isfile(path):
            os.remove(path)


def vc_fake_calls(case):
    path = os.path.join(_vc_fake_dir, f"calls-{case}.log")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


rc, out, err = run_hook(
    "versioncheck",
    vc_payload("vc-clean"),
    vc_env(HOUSE_RULES_VC_MARKETPLACE=_installed_version, HOUSE_RULES_VC_GITHUB=_installed_version),
)
if rc == 0 and "OUT OF DATE" not in out and not os.path.isfile(vc_marker_path("vc-clean")):
    report("PASS", "versioncheck is quiet when installed, marketplace and GitHub all agree")
    print("          no banner, no marker file - matching versions leave nothing to say")
else:
    report("FAIL", "versioncheck is quiet when installed, marketplace and GitHub all agree")
    print(f"          rc={rc} out={out[:200]!r}")

# --- SessionStart loads the newest installed rules after an update (issue #252) -----------
# An older folder runs SessionStart; installed_plugins.json names a newer folder. inject and
# showrule must load the newer folder's rule text and say so in one line, and must say it in one
# line when installed_plugins.json cannot be read (never silent).
_nr_dir = tempfile.mkdtemp(prefix="house-rules-newest-rules-")


def _nr_make(name, version, tag, with_showrule):
    root = os.path.join(_nr_dir, name)
    os.makedirs(os.path.join(root, "scripts"))
    os.makedirs(os.path.join(root, "rules"))
    os.makedirs(os.path.join(root, ".claude-plugin"))
    shutil.copy(HOOK, os.path.join(root, "scripts", "hook.py"))
    shutil.copytree(os.path.join(HERE, "house_rules"), os.path.join(root, "scripts", "house_rules"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "house-rules", "version": version}, f)
    with open(os.path.join(root, "rules", "house-rules.md"), "w", encoding="utf-8") as f:
        f.write(f"{tag} CORE RULES, see ${{CLAUDE_PLUGIN_ROOT}}/rules/detail/x.md\n")
    if with_showrule:
        for fname in ("show-dont-tell.md", "clear-writing.md"):
            with open(os.path.join(root, "rules", fname), "w", encoding="utf-8") as f:
                f.write(f"{tag} {fname} ${{CLAUDE_PLUGIN_ROOT}}/rules/detail/x.md\n")
    return root


def _nr_run(event, root, installed_json):
    e = dict(os.environ)
    e["HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON"] = installed_json
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "hook.py"), event],
        input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e,
    )
    out = proc.stdout.decode("utf-8", "replace")
    try:
        parsed = json.loads(out)
    except Exception:
        return proc.returncode, "", "", out
    ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
    return proc.returncode, ctx, parsed.get("systemMessage", ""), out


_nr_old = _nr_make("old", "1.0.0", "OLDTAG", False)
_nr_new = _nr_make("new", "2.0.0", "NEWTAG", True)
_nr_json = os.path.join(_nr_dir, "installed.json")
with open(_nr_json, "w", encoding="utf-8") as f:
    json.dump({"version": 2, "plugins": {"house-rules@aj-house-rules": [
        {"installPath": _nr_new, "version": "2.0.0"}]}}, f)

for _ev, _want in (("inject", "NEWTAG CORE RULES"), ("showrule", "NEWTAG show-dont-tell.md")):
    rc, ctx, msg, raw = _nr_run(_ev, _nr_old, _nr_json)
    ok = (rc == 0 and _want in ctx and "OLDTAG" not in ctx and f"plugin root: {_nr_new}" in ctx
          and "2.0.0" in msg and "\n" not in msg)
    report("PASS" if ok else "FAIL",
           f"{_ev} from an older folder loads the newer installed folder's rules and says so in one line")
    if not ok:
        print(f"          rc={rc} ctx={ctx[:200]!r} msg={msg!r}")

for _label, _jpath in (("missing", os.path.join(_nr_dir, "absent.json")), ("unreadable", None)):
    if _jpath is None:
        _jpath = os.path.join(_nr_dir, "broken.json")
        with open(_jpath, "w", encoding="utf-8") as f:
            f.write("{not json")
    for _ev, _want in (("inject", "OLDTAG CORE RULES"), ("showrule", None)):
        rc, ctx, msg, raw = _nr_run(_ev, _nr_new if _ev == "showrule" else _nr_old, _jpath)
        if _ev == "showrule":
            _want = "NEWTAG show-dont-tell.md"
        ok = (rc == 0 and _want in ctx and "could not check for newer rules" in msg and "\n" not in msg)
        report("PASS" if ok else "FAIL",
               f"{_ev} with installed_plugins.json {_label} loads its own rules and says why in one line")
        if not ok:
            print(f"          rc={rc} ctx={ctx[:200]!r} msg={msg!r}")

session_a = "vc-installed-stale"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_a),
    vc_env(HOUSE_RULES_VC_MARKETPLACE="99.0.0", HOUSE_RULES_VC_GITHUB="99.0.0"),
)
marker_a = vc_marker_path(session_a)
ok = (
    rc == 0
    and "OUT OF DATE" in out
    and "claude plugin update house-rules@aj-house-rules" in out
    and os.path.isfile(marker_a)
)
if ok:
    report("PASS", "versioncheck flags installed lagging the marketplace clone, and arms a marker")
    print("          banner names the update command; marker written for guard's first-call prompt")
else:
    report("FAIL", "versioncheck flags installed lagging the marketplace clone, and arms a marker")
    print(f"          rc={rc} out={out[:300]!r}")

# --- the out-of-date banner tells Claude to hand the command over properly and then stop -----
# Why this is its own check, not folded into the mismatch check above: docs/4-systems/verify-suites.md, "Traps".
vc_banner_out = out
banner_ok = (
    "UNTESTED" in vc_banner_out
    and "step-card" in vc_banner_out
    and "stop and wait" in vc_banner_out
    and "permission" in vc_banner_out
    and "run the command(s) below yourself" in vc_banner_out
    and "Do not ask in chat" in vc_banner_out
    and "could not finish" in vc_banner_out
)
if banner_ok:
    report("PASS", "when the automatic update fails, the banner says why and tells Claude to run it itself without asking, falling back to the card marked UNTESTED, then stop and wait")
    print("          banner names the failure, the run-it-yourself-now instruction, the card/UNTESTED fallback, and the stop-and-wait instruction")
else:
    report("FAIL", "when the automatic update fails, the banner says why and tells Claude to run it itself without asking, falling back to the card marked UNTESTED, then stop and wait")
    print(f"          out={vc_banner_out[:400]!r}")

# --- that same instruction has not drifted from the rules document, bidirectionally ----------
# Same shape as the delegate/harvest drift checks: the phrase must appear in BOTH house-rules.md
# and what versioncheck actually emits, or a reword on one side silently stops matching the other.
drift = []
for phrase in ("relayed", "step-card", "UNTESTED", "stop and wait", "permission"):
    if phrase.lower() not in rules_text.lower():
        drift.append(f"{phrase!r} missing from rules/house-rules.md")
    if phrase.lower() not in vc_banner_out.lower():
        drift.append(f"{phrase!r} missing from the emitted versioncheck banner")
if not drift:
    report("PASS", "the versioncheck banner and the rules document state the relay/stop rule the same way, both ways")
else:
    report("FAIL", "the versioncheck banner and the rules document state the relay/stop rule the same way, both ways")
    for d in drift:
        print(f"          {d}")

if os.path.isfile(marker_a):
    os.remove(marker_a)

session_b = "vc-marketplace-stale"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_b),
    vc_env(HOUSE_RULES_VC_MARKETPLACE=_installed_version, HOUSE_RULES_VC_GITHUB="99.0.0"),
)
marker_b = vc_marker_path(session_b)
ok = (
    rc == 0
    and "marketplace clone itself has not synced" in out
    and "claude plugin marketplace update aj-house-rules" in out
    and os.path.isfile(marker_b)
)
if ok:
    report(
        "PASS",
        "versioncheck catches a marketplace clone stale against GitHub even when installed matches it",
    )
    print("          the exact gap `plugin update` alone would miss - the marketplace never re-fetched")
else:
    report(
        "FAIL",
        "versioncheck catches a marketplace clone stale against GitHub even when installed matches it",
    )
    print(f"          rc={rc} out={out[:300]!r}")
if os.path.isfile(marker_b):
    os.remove(marker_b)

rc, out, err = run_hook(
    "versioncheck",
    vc_payload("vc-off"),
    vc_env(
        HOUSE_RULES_VERSION_CHECK="off",
        HOUSE_RULES_VC_MARKETPLACE="99.0.0",
        HOUSE_RULES_VC_GITHUB="99.0.0",
    ),
)
if rc == 0 and out == "":
    report("PASS", "HOUSE_RULES_VERSION_CHECK=off disables the freshness check entirely")
    print("          exits 0 with nothing emitted, even with a manufactured mismatch")
else:
    report("FAIL", "HOUSE_RULES_VERSION_CHECK=off disables the freshness check entirely")
    print(f"          rc={rc} out={out[:200]!r}")

# --- versioncheck: the GitHub fetch falls back to the API, and a failure reaches the model ------
# 2026-09-24: raw.githubusercontent.com was reset by a sandbox while api.github.com worked, and the
# "couldn't verify" result went only to a systemMessage the model never sees. file:// URLs stand in
# for both routes, so these cases never touch the network: a missing file is a failed fetch.
_vc_dir = tempfile.mkdtemp(prefix="house-rules-vc-")
_vc_dead_url = pathlib.Path(_vc_dir, "missing.json").as_uri()
_vc_api_json = pathlib.Path(_vc_dir, "api-plugin.json")
_vc_api_json.write_text(json.dumps({"version": "99.0.0"}), encoding="utf-8")

session_d = "vc-raw-fails-api-works"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_d),
    vc_env(
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB_URL=_vc_dead_url,
        HOUSE_RULES_VC_GITHUB_API_URL=_vc_api_json.as_uri(),
    ),
)
marker_d = vc_marker_path(session_d)
ok = (
    rc == 0
    and "OUT OF DATE" in out
    and "GitHub's default branch has 99.0.0" in out
    and os.path.isfile(marker_d)
)
if ok:
    report("PASS", "versioncheck falls back to the GitHub API when the raw URL fails, and still flags a stale copy")
    print("          raw route dead, API route reports 99.0.0 - banner fires and the marker is armed")
else:
    report("FAIL", "versioncheck falls back to the GitHub API when the raw URL fails, and still flags a stale copy")
    print(f"          rc={rc} out={out[:300]!r} err={err[:200]!r}")
if os.path.isfile(marker_d):
    os.remove(marker_d)

session_e = "vc-both-routes-fail"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_e),
    vc_env(
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB_URL=_vc_dead_url,
        HOUSE_RULES_VC_GITHUB_API_URL=_vc_dead_url,
    ),
)
marker_e = vc_marker_path(session_e)
try:
    _vc_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception:
    _vc_ctx = ""
ok = (
    rc == 0
    and "could not confirm the plugin is current" in _vc_ctx
    and "raw.githubusercontent.com (URLError" in _vc_ctx
    and "api.github.com (URLError" in _vc_ctx
    and _installed_version in _vc_ctx
    and "OUT OF DATE" not in out
    and not os.path.isfile(marker_e)
)
if ok:
    report("PASS", "versioncheck tells the model, not just the UI, when neither GitHub route could be reached")
    print("          additionalContext names both failed routes and the installed version; no banner, no marker")
else:
    report("FAIL", "versioncheck tells the model, not just the UI, when neither GitHub route could be reached")
    print(f"          rc={rc} out={out[:400]!r} marker exists: {os.path.isfile(marker_e)}")
if os.path.isfile(marker_e):
    os.remove(marker_e)

rc, out, err = run_hook(
    "versioncheck",
    vc_payload("vc-agree-no-context"),
    vc_env(HOUSE_RULES_VC_MARKETPLACE=_installed_version, HOUSE_RULES_VC_GITHUB=_installed_version),
)
if rc == 0 and "additionalContext" not in out:
    report("PASS", "versioncheck adds nothing to the model's context when all three copies agree")
    print("          a verified-current plugin stays a UI-only trace line")
else:
    report("FAIL", "versioncheck adds nothing to the model's context when all three copies agree")
    print(f"          rc={rc} out={out[:200]!r}")
shutil.rmtree(_vc_dir, ignore_errors=True)

# --- versioncheck updates the plugin itself, and reads what is installed, not only what runs -----
# 2026-09-26: a session ran 2.29.0 while 2.36.0 was already installed on disk, and the banner asked
# for an update that would have done nothing; the fix is a restart. And the update is now run by
# the hook itself, confirmed by re-reading installed_plugins.json rather than trusting exit 0.
case = "vc-restart-needed"
vc_clear(case)
vc_installed_json(case, "99.0.0")
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(case, HOUSE_RULES_VC_MARKETPLACE="99.0.0", HOUSE_RULES_VC_GITHUB="99.0.0"),
)
ok = (
    rc == 0
    and "OUT OF DATE" not in out
    and "start a new session" in out
    and "Do not run any update command" in out
    and vc_fake_calls(case) == []
    and not os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck says 'start a new session', not 'update', when the newer version is already installed on disk")
    print("          running copy is old, installed_plugins.json has 99.0.0: no banner, no marker, no update run")
else:
    report("FAIL", "versioncheck says 'start a new session', not 'update', when the newer version is already installed on disk")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")

case = "vc-auto-update-works"
vc_clear(case)
vc_installed_json(case, _installed_version)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB="99.0.0",
        VC_FAKE_EXIT="0",
        VC_FAKE_INSTALLS="99.0.0",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case)
    == ["plugin marketplace update aj-house-rules", "plugin update house-rules@aj-house-rules"]
    and "updated automatically at session start" in out
    and "99.0.0" in out
    and "OUT OF DATE" not in out
    and not os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck refreshes the stale marketplace, runs the update itself, and confirms it on disk")
    print("          both commands ran in order; installed_plugins.json then read 99.0.0, so no banner and no marker")
else:
    report("FAIL", "versioncheck refreshes the stale marketplace, runs the update itself, and confirms it on disk")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")

case = "vc-update-exits-0-but-nothing-installed"
vc_clear(case)
vc_installed_json(case, _installed_version)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE="99.0.0",
        HOUSE_RULES_VC_GITHUB="99.0.0",
        VC_FAKE_EXIT="0",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case) == ["plugin update house-rules@aj-house-rules"]
    and "OUT OF DATE" in out
    and "exited 0, but installed_plugins.json lists" in out
    and os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck does not trust an update's exit code: nothing new on disk still means out of date")
    print("          only `plugin update` ran (marketplace already current); exit 0 with no new install -> banner and marker")
else:
    report("FAIL", "versioncheck does not trust an update's exit code: nothing new on disk still means out of date")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")
if os.path.isfile(vc_marker_path(case)):
    os.remove(vc_marker_path(case))

case = "vc-auto-update-off"
vc_clear(case)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE="99.0.0",
        HOUSE_RULES_VC_GITHUB="99.0.0",
        HOUSE_RULES_AUTO_UPDATE="off",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case) == []
    and "OUT OF DATE" in out
    and "HOUSE_RULES_AUTO_UPDATE=off" in out
)
if ok:
    report("PASS", "HOUSE_RULES_AUTO_UPDATE=off keeps the check but never runs the update")
    print("          no `claude` call; the banner says automatic updating is off")
else:
    report("FAIL", "HOUSE_RULES_AUTO_UPDATE=off keeps the check but never runs the update")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")
if os.path.isfile(vc_marker_path(case)):
    os.remove(vc_marker_path(case))
shutil.rmtree(_vc_fake_dir, ignore_errors=True)


# -- #341: settings and identity. Every setting blocks until it is set; identity strings come from settings. -----
import importlib.util as _st_util
_st_spec = _st_util.spec_from_file_location("hr_settings_mod", os.path.join(HERE, "house_rules", "settings.py"))
_st = _st_util.module_from_spec(_st_spec)
_st_spec.loader.exec_module(_st)
_ST_SCRIPT = os.path.join(HERE, "settings.py")
_ST_DIR = tempfile.mkdtemp(prefix="hr-settings-", dir=_FIXTURE_ROOT)


def _st_env(file_name="settings.json", **extra):
    """The suite's environment with both settings variables removed, so nothing is set unless a case sets it."""
    e = dict(os.environ)
    e.pop("HOUSE_RULES_AGENT_NAME", None)
    e.pop("HOUSE_RULES_OWNED_BRANCHES", None)
    e["HOUSE_RULES_SETTINGS_FILE"] = os.path.join(_ST_DIR, file_name)
    e.update(extra)
    return e


def _st_call(event, tool, tool_input, env):
    pl = json.dumps({"session_id": "verify", "tool_name": tool, "tool_input": tool_input})
    return run_hook(event, pl, env=env)[1]


def _st_cli(args, env):
    p = subprocess.run([sys.executable, _ST_SCRIPT] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _st_py(code, env):
    return subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); from house_rules import settings; %s" % (HERE, code)],
                          stdout=subprocess.PIPE, env=env).stdout.decode().strip()


# (a) an unset setting refuses a non-settings tool, naming the setting and the command
_sa = [_st_call("guard", "Bash", {"command": "echo hi"}, _st_env("a.json")),
       _st_call("settingsgate", "Write", {"file_path": "/x/a.txt", "content": "x"}, _st_env("a.json")),
       _st_call("settingsgate", "mcp__github__issue_write", {"method": "create"}, _st_env("a.json")),
       _st_call("settingsgate", "Read", {"file_path": "/x/a.txt"}, _st_env("a.json"))]
commit_case(
    "settings: an unset setting refuses a non-settings tool (Bash, Write, a GitHub tool, Read), naming the setting and the command (#341)",
    all('"permissionDecision":"deny"' in o and "agent_name" in o and "extra_owned_prefixes" in o
        and "settings.py set agent_name" in o and "settings.py set extra_owned_prefixes" in o for o in _sa),
    "out %r" % [o[:90] for o in _sa],
)
_sa_set = _st_env("a.json", HOUSE_RULES_AGENT_NAME=TEST_AGENT_NAME, HOUSE_RULES_OWNED_BRANCHES="")
commit_case(
    "settings: with both settings set (an empty extra_owned_prefixes counts as set) the settings gate lets every tool through (#341)",
    "settings not set" not in _st_call("guard", "Bash", {"command": "echo hi"}, _sa_set)
    and _st_call("settingsgate", "Read", {"file_path": "/x"}, _sa_set) == "",
    "set env: agent_name + empty extra_owned_prefixes",
)

# (b) the one allowed settings command passes the guard while unset; chained and look-alike commands do not
_sb_ok = [_st_call("guard", "Bash", {"command": c}, _st_env("b.json")) for c in (
    "python3 %s set agent_name %s" % (_ST_SCRIPT, TEST_AGENT_NAME),
    "python3 \"%s\" set extra_owned_prefixes \"AjsAgent/,claude/\"" % _ST_SCRIPT,
    "python3 %s set extra_owned_prefixes \"\"" % _ST_SCRIPT,
    "python3 %s show" % _ST_SCRIPT)]
_sb_ok += [_st_call("settingsgate", "Bash", {"command": "python3 %s get agent_name" % _ST_SCRIPT}, _st_env("b.json"))]
_sb_bad = [_st_call("guard", "Bash", {"command": c}, _st_env("b.json")) for c in (
    "python3 %s set agent_name x; echo hi" % _ST_SCRIPT,
    "python3 %s set agent_name $(whoami)" % _ST_SCRIPT,
    "python3 %s set agent_name x && echo hi" % _ST_SCRIPT,
    "python3 /tmp/elsewhere/settings.py set agent_name x",
    "python3 %s set agent_name x > /tmp/x" % _ST_SCRIPT)]
commit_case(
    "settings: the one settings command passes the guard and the settings gate while unset; chained, substituted and look-alike commands do not (#341)",
    all("settings not set" not in o for o in _sb_ok) and all("settings not set" in o for o in _sb_bad),
    "ok %r | bad %r" % ([o[:60] for o in _sb_ok], [o[:40] for o in _sb_bad]),
)

# (c) the environment variable is read before the settings file; the file is read when the variable is absent
_sc_file = os.path.join(_ST_DIR, "c.json")
_sc_env = _st_env("c.json")
_sc_set = _st_cli(["set", "agent_name", "fileAgent"], _sc_env)
_sc_get_file = _st_cli(["get", "agent_name"], _sc_env)
_sc_get_env = _st_cli(["get", "agent_name"], dict(_sc_env, HOUSE_RULES_AGENT_NAME="envAgent"))
_sc_none = _st_cli(["set", "extra_owned_prefixes", ""], _sc_env)
_sc_show = _st_cli(["show"], _sc_env)
_sc_bad = _st_cli(["set", "agent_name", "bad name/x"], _sc_env)
_sc_missing_after = _st_py("print(settings.missing())", _sc_env)
commit_case(
    "settings: the environment variable is read before the settings file; set writes the file and says where; an empty extra_owned_prefixes counts as set (#341)",
    _sc_set[0] == 0 and _sc_file in _sc_set[1] and _sc_get_file[1].strip() == "fileAgent"
    and _sc_get_env[1].strip() == "envAgent" and _sc_none[0] == 0 and _sc_missing_after == "[]"
    and "fileAgent" in _sc_show[1] and _sc_file in _sc_show[1] and _sc_bad[0] == 1 and "not saved" in _sc_bad[2],
    "set %r | file %r | env %r | missing %r | bad %r" % (_sc_set[1][:80], _sc_get_file[1], _sc_get_env[1], _sc_missing_after, _sc_bad[2][:60]),
)

# the settings file sits outside the repo: under the Claude config dir, which follows the machine
_sc_home = _st_env()
_sc_home.pop("HOUSE_RULES_SETTINGS_FILE")
_sc_home["CLAUDE_CONFIG_DIR"] = os.path.join(_ST_DIR, "cfg")
_sc_loc = _st_py("print(settings.settings_path())", _sc_home)
commit_case(
    "settings: the settings file defaults to <config dir>/house-rules/settings.json, outside any repo (#341)",
    _sc_loc == os.path.join(_ST_DIR, "cfg", "house-rules", "settings.json") and not _sc_loc.startswith(ROOT),
    "path %r" % _sc_loc,
)

# the derived identity strings (this process has the suite's test settings)
commit_case(
    "settings: the credit lines, branch prefix and owned prefixes derive from agent_name and the extras (#341)",
    _st.commit_credit() == "Committed by " + TEST_AGENT_NAME and _st.pr_credit() == "Opened by " + TEST_AGENT_NAME
    and _st.agent_prefix() == TEST_AGENT_PREFIX
    and _st.owned_prefixes() == (TEST_AGENT_PREFIX, "AjsAgent/", "claude/", "ccr-")
    and _st.identity_fix().startswith("git config user.name \"%s\"" % TEST_AGENT_NAME),
    "owned %r" % (_st.owned_prefixes(),),
)

# (d) no identity string is left in shipped code outside the defaults file
_sd_rx = re.compile(r"AjsAgent|aj'?s agent|ajw2003", re.IGNORECASE)
_sd_files = [os.path.join(HERE, n) for n in os.listdir(HERE) if n.endswith((".py", ".sh"))]
_sd_files += [os.path.join(HERE, "house_rules", n) for n in os.listdir(os.path.join(HERE, "house_rules")) if n.endswith(".py")]
_sd_files.append(HOOKS_JSON)
_sd_defaults = os.path.join(HERE, "house_rules", "settings.py")
_sd_hits = []
for _f in _sd_files:
    if _f == _sd_defaults:
        continue
    for _n, _line in enumerate(read(_f).splitlines(), 1):
        if _sd_rx.search(_line):
            _sd_hits.append("%s:%d" % (os.path.relpath(_f, HERE), _n))
commit_case(
    "settings: no identity string (AjsAgent, aj's agent, ajw2003) is left in the shipped scripts outside house_rules/settings.py (#341)",
    bool(_sd_files) and not _sd_hits and _sd_rx.search(read(_sd_defaults)) is not None,
    "scanned %d files (scripts/, scripts/house_rules/, hooks.json; not scripts/checks/); left: %s" % (len(_sd_files), _sd_hits[:8]),
)

# (e) the session-start note suggests <login lowercased>sAgent when unset, and is absent when set
_se_bin = tempfile.mkdtemp(prefix="hr-gh-", dir=_FIXTURE_ROOT)
_se_gh = os.path.join(_se_bin, "gh")
with open(_se_gh, "w", encoding="utf-8") as _f:
    _f.write("#!/bin/sh\nif [ \"$1\" = api ] && [ \"$2\" = user ]; then echo MixedCaseUser; exit 0; fi\nexit 1\n")
os.chmod(_se_gh, 0o755)
_se_path = _se_bin + os.pathsep + os.environ.get("PATH", "")
_se_unset = run_hook("profile", "", env=_st_env("e.json", PATH=_se_path))[1]
_se_set = run_hook("profile", "", env=_st_env("e.json", PATH=_se_path, HOUSE_RULES_AGENT_NAME=TEST_AGENT_NAME, HOUSE_RULES_OWNED_BRANCHES=""))[1]
commit_case(
    "settings: the session-start note suggests <GitHub login lowercased>sAgent, naming gh as the source, when unset; absent when set (#341)",
    "mixedcaseusersAgent" in _se_unset and "gh api user" in _se_unset and "only once the user confirms" in _se_unset
    and "settings are not set" in _se_unset and "settings are not set" not in _se_set and "mixedcaseusersAgent" not in _se_set,
    "unset tail %r | set-has-note %s" % (_se_unset[-300:], "settings are not set" in _se_set),
)
_se_real = _st.subprocess.run


def _se_fake(cmd, **kw):
    if cmd[0] == "gh":
        raise FileNotFoundError("gh")
    return subprocess.CompletedProcess(cmd, 0, stdout="git@github.com:SomeOwner/repo.git\n", stderr="")


_st.subprocess.run = _se_fake
try:
    _se_fb = _st.suggestion()
finally:
    _st.subprocess.run = _se_real
commit_case(
    "settings: when gh fails the suggestion falls back to the git remote's owner and says so (#341)",
    _se_fb[0] == "someownersAgent" and "git remote" in _se_fb[1],
    "suggestion %r" % (_se_fb,),
)


finish()
