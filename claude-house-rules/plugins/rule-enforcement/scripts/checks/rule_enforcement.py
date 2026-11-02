#!/usr/bin/env python3
"""checks/rule_enforcement.py - the rule-enforcement plugin's checks (#440): inject, showrule, scope, subagentrules, and the
repeat-failure lock (lockgate, step 3 part B).

Run it alone:  python3 claude-house-rules/plugins/rule-enforcement/scripts/checks/rule_enforcement.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails.
scripts/verify.py runs it; CI runs scripts/verify.py. The cases were moved, with their text, out of
house-rules' checks/core.py and checks/delegation.py when the four handlers moved (docs/4-systems/plugin-split.md,
"Step 3 part A").

STDLIB ONLY, like hook.py.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("rule-enforcement hooks - verification (Python) - part: rule_enforcement")
print("=" * 43)
print()

# --- inject and showrule each stay under the per-hook additionalContext limit ------------------
# Margins per docs/6-decisions/Decisions.md, 2026-09-22 (second entry), measured on the REAL emitted output.
for _event, _margin, _env in (("inject", 9_700, env_in(ROOT)), ("showrule", 9_500, env_in(ROOT))):
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
    "import rule_enforcement.core as core\n"
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

# --- the voice is always loaded, and the rules around it are intact -------------------------------
# Nothing turns the voice off any more: it is a preference, but no rule is optional. Since #245 the voice
# lives in rules/clear-writing.md, loaded by showrule.
code, on_out, err = run_hook("showrule", "")
voice_problems = []
if "### The voice" not in on_out:
    voice_problems.append("the voice is missing from what showrule loads")
for kept in [
    "Write it so nothing is left to guess",
    "Explicit context",
    "Define before use",
    "Named references",
    "Show, don't tell; the user designs",
]:
    if kept not in on_out:
        voice_problems.append(f"the rules lost {kept!r}")
if code != 0:
    voice_problems.append(f"showrule exited {code}")
if not voice_problems:
    report("PASS", "showrule loads the voice and every rule around it")
    print(f"          {len(on_out)} chars loaded")
else:
    report("FAIL", "showrule loads the voice and every rule around it")
    for v in voice_problems:
        print(f"          {v}")

# --- no switch turns a check off (#440 part C) ---------------------------------------------------
# The removed switches are written in pieces so this file does not contain them. A name counts only when
# it ends there: the path, URL and number switches that start with the same letters are kept.
import re as _sw_re
_SW_REMOVED = ("AGENTS", "AGENT_BRANCH", "ATTRIBUTION", "AUTOSAVE", "AUTO_UPDATE", "CLEAR_WRITING", "COMMIT_CHECK",
               "DELEGATION", "EDITOR", "HANDOVER", "HARVEST", "ISSUES", "LOOP", "PARITY", "PLAIN_SUMMARY",
               "VERSION_CHECK", "VISUAL_CHECK", "VOICE", "WORKTRACKING")
_SW_RE = _sw_re.compile("HOUSE_" + "RULES_(?:" + "|".join(_SW_REMOVED) + ")(?![A-Za-z0-9_])|"
                        "HOUSE_" + "RULES_PROMPT_TIMEOUT=.?off", _sw_re.IGNORECASE)
_sw_hits = []
for _sw_dir, _sw_dirs, _sw_files in os.walk(PLUGIN):
    _sw_dirs[:] = [d for d in _sw_dirs if d != "__pycache__"]
    for _sw_f in _sw_files:
        if _sw_f.endswith(".pyc"):
            continue
        _sw_path = os.path.join(_sw_dir, _sw_f)
        try:
            _sw_text = open(_sw_path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as _sw_exc:
            _sw_hits.append("%s: could not be read (%s), so it was not checked" % (_sw_path, _sw_exc))
            continue
        for _sw_m in _SW_RE.finditer(_sw_text):
            _sw_hits.append("%s: %s" % (os.path.relpath(_sw_path, PLUGIN), _sw_m.group(0)))
if not _sw_hits:
    report("PASS", "no removed off switch is named anywhere in this plugin's code or rules")
    print("          %d names searched in every file under the plugin folder" % (len(_SW_REMOVED) + 1))
else:
    report("FAIL", "no removed off switch is named anywhere in this plugin's code or rules")
    for _h in _sw_hits[:20]:
        print(f"          {_h}")

# --- SessionStart loads the newest installed rules after an update (issue #252) -----------
# An older folder runs SessionStart; installed_plugins.json names a newer folder. inject and
# showrule must load the newer folder's rule text and say so in one line, and must say it in one
# line when installed_plugins.json cannot be read (never silent).
_nr_dir = tempfile.mkdtemp(prefix="rule-enforcement-newest-rules-")


def _nr_make(name, version, tag, with_showrule):
    root = os.path.join(_nr_dir, name)
    os.makedirs(os.path.join(root, "scripts"))
    os.makedirs(os.path.join(root, "rules"))
    os.makedirs(os.path.join(root, ".claude-plugin"))
    shutil.copy(HOOK, os.path.join(root, "scripts", "hook.py"))
    shutil.copytree(os.path.join(HERE, "rule_enforcement"), os.path.join(root, "scripts", "rule_enforcement"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(HERE, "house_lib"), os.path.join(root, "scripts", "house_lib"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "rule-enforcement", "version": version}, f)
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
    json.dump({"version": 2, "plugins": {"rule-enforcement@aj-house-rules": [
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


# --- subagentrules: a subagent core, generated from house-rules.md, injected at SubagentStart --
# Judged against the real rules file, since a hand-copied fixture core would only prove the
# handler can read a fixture, not that it stays in sync with the rules a human session sees.
code, out, err = run_hook("subagentrules", json.dumps(
    {"hook_event_name": "SubagentStart", "agent_type": "house-rules:builder", "agent_id": "x1", "session_id": "sess1"}
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

# Never blocks a spawn: empty payload and unparseable input both still exit 0.
sarq = []
code, out, err = run_hook("subagentrules", "")
if code != 0 or "additionalContext" not in out:
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

# Registered on SubagentStart, unmatched.
hooks_json_text = read(HOOKS_JSON)
_hj2 = json.loads(hooks_json_text)["hooks"]
sarwire = []
starts = _hj2.get("SubagentStart") or []
if not any("subagentrules" in h.get("command", "") for e in starts for h in e.get("hooks", [])):
    sarwire.append("hooks.json's SubagentStart has no subagentrules dispatch")
if any("matcher" in e for e in starts):
    sarwire.append("SubagentStart is scoped by a matcher, so it misses other agents")
if not sarwire:
    report("PASS", "subagentrules is wired on SubagentStart, unmatched")
    print("          fires, unmatched, on every subagent spawn")
else:
    report("FAIL", "subagentrules is wired on SubagentStart, unmatched")
    for s in sarwire:
        print(f"          {s}")

if ("    subagentrules)" in read(RUN)):
    report("PASS", "run.sh names subagentrules in its no-interpreter fallback")
    print("          no working Python still reports the subagent got no rules")
else:
    report("FAIL", "run.sh names subagentrules in its no-interpreter fallback")


# --- the plugin is wired as the split says (#440) -----------------------------------------------
_wire = []
_hjw = json.loads(hooks_json_text)["hooks"]
_want = {"SessionStart": ["inject", "showrule"], "SubagentStart": ["subagentrules"], "UserPromptSubmit": ["scope"],
         "PreToolUse": ["lockgate"]}
for _evn, _names in _want.items():
    _cmds = [h.get("command", "") for e in _hjw.get(_evn, []) for h in e.get("hooks", [])]
    for _n in _names:
        if not any(c.endswith('run.sh" %s' % _n) for c in _cmds):
            _wire.append(f"{_evn} has no {_n} dispatch")
if sorted(_hjw) != sorted(_want):
    _wire.append(f"hooks.json events are {sorted(_hjw)}, expected {sorted(_want)}")
_pj = json.loads(read(PLUGIN_JSON))
if _pj.get("name") != "rule-enforcement":
    _wire.append("plugin.json name is not rule-enforcement")
if _pj.get("dependencies") != ["house-lib"]:
    _wire.append(f"plugin.json dependencies are {_pj.get('dependencies')!r}, expected ['house-lib']")
report("FAIL" if _wire else "PASS", "hooks.json wires inject, showrule, subagentrules, scope and lockgate; plugin.json depends on house-lib")
for _w in _wire:
    print(f"          {_w}")

# --- run.sh: no interpreter -> each moved event fails loud (or, for scope, quiet and exit 0) ----
_rs = read(RUN)
_fall = [ev for ev in ("inject", "showrule", "subagentrules") if ("    %s)" % ev) not in _rs]
report("FAIL" if _fall else "PASS", "run.sh names inject, showrule and subagentrules in its no-interpreter fallback")
if _fall:
    print(f"          no per-event fallback for {', '.join(_fall)}")
_npath = dict(os.environ)
_npath["PATH"] = ""
_npath.pop("HOUSE_RULES_PYTHON", None)
_sh_bad = []
for _ev, _needle in (("inject", "NOT loaded"), ("showrule", "NOT loaded"), ("subagentrules", "did NOT receive")):
    _c, _o, _e = run_shell([RUN, _ev], env=_npath)
    if _c != 0 or _needle not in _o:
        _sh_bad.append(f"{_ev}: exit {_c}, out {_o[:100]!r}")
_c, _o, _e = run_shell([RUN, "scope"], env=_npath)
if _c != 0:
    _sh_bad.append(f"scope: exit {_c}, must never erase the prompt")
report("FAIL" if _sh_bad else "PASS", "with no working Python the moved events still exit 0 and the rules events say so")
for _b in _sh_bad:
    print(f"          {_b}")

# --- the last-resort net in main() speaks for scope, showrule and subagentrules too ---------------
for _ev in ("scope", "showrule", "subagentrules"):
    _snip = (
        "import sys, hook\n"
        "import rule_enforcement.core as core\n"
        "real_emit = hook.emit\n"
        "state = {'first': True}\n"
        "def one_shot_boom(obj):\n"
        "    if state['first']:\n"
        "        state['first'] = False\n"
        "        raise OSError('simulated internal failure')\n"
        "    real_emit(obj)\n"
        "hook.emit = core.emit = one_shot_boom\n"
        f"sys.exit(hook.main(['hook.py', '{_ev}']))\n"
    )
    _p = subprocess.run([sys.executable, "-c", _snip], cwd=HERE, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    _o = _p.stdout.decode("utf-8", "replace")
    _spoke = bool(_o.strip()) if _ev == "scope" else ("systemMessage" in _o)
    if _p.returncode == 0 and _spoke:
        report("PASS", f"an internal crash in {_ev} is announced rather than swallowed")
        print("          exits 0 without obstructing, but does not go quiet")
    else:
        report("FAIL", f"an internal crash in {_ev} is announced rather than swallowed")
        print(f"          exit {_p.returncode}, stdout {_o[:120]!r}, stderr {_p.stderr.decode('utf-8', 'replace')[:120]!r}")

# --- the Unity tools-first rule is not in the always-injected core (the inject half) ----------------
_, _inject_out, _ = run_hook("inject", "", env=env_in(ROOT))
if "Unity work starts" not in _inject_out and "unity-tools-first" not in _inject_out:
    report("PASS", "the inject output does not carry the Unity tools-first rule")
    print("          it loads only through house-rules' standards hook for Unity projects")
else:
    report("FAIL", "the inject output does not carry the Unity tools-first rule")

# --- the rules text is injected exactly once, by this plugin alone (#440) ------------------------------
_hr_hooks = os.path.join(PLUGIN, "..", "house-rules", "hooks", "hooks.json")
if os.path.isfile(_hr_hooks):
    _hr_cmds = " ".join(h.get("command", "") for evs in json.loads(read(_hr_hooks))["hooks"].values()
                        for e in evs for h in e.get("hooks", []))
    _dup = [n for n in ("inject", "showrule", "scope", "subagentrules") if re.search(r'run\.sh" %s\b' % n, _hr_cmds)]
    _hr_rules = [n for n in ("house-rules.md", "show-dont-tell.md", "clear-writing.md")
                 if os.path.isfile(os.path.join(PLUGIN, "..", "house-rules", "rules", n))]
    _hr_detail = os.path.isdir(os.path.join(PLUGIN, "..", "house-rules", "rules", "detail"))
    report("FAIL" if (_dup or _hr_rules or _hr_detail) else "PASS",
           "house-rules no longer dispatches inject, showrule, scope or subagentrules, and holds none of the moved rules files")
    if _dup or _hr_rules or _hr_detail:
        print(f"          still dispatched: {_dup}; rules files still in house-rules: {_hr_rules}; detail dir: {_hr_detail}")
else:
    report("SKIP", "house-rules no longer dispatches the four moved events (house-rules is not beside this plugin)")

# --- the repeat-failure lock (#440, step 3 part B, choice 6A) ---------------------------------------------
from house_lib import blocks as _bl  # noqa: E402 - the vendored library, importable because common.py put scripts/ on sys.path

_lk_repo = tempfile.mkdtemp(prefix="lock-repo-")
subprocess.run(["git", "init", "-q", _lk_repo], check=True)
os.makedirs(os.path.join(_lk_repo, "docs", "plans"))
_LK_SID = "lock-verify"
_LK_SRC = os.path.join(_lk_repo, "src", "app.py")


def _lk_gate(tool, ti, sid=_LK_SID, cwd=None):
    payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": cwd or _lk_repo,
                          "tool_name": tool, "tool_input": ti})
    _c, _o, _e = run_hook("lockgate", payload, env=env_in(_lk_repo))
    try:
        d = json.loads(_o) if _o.strip() else {}
    except ValueError:
        d = {"unparsable": _o}
    hso = d.get("hookSpecificOutput", {})
    return _c, hso.get("permissionDecision") == "deny", hso.get("permissionDecisionReason", ""), d.get("systemMessage", ""), _o


def _lk_stop(check, mark, failing, fix="commit a.py on your own branch", sid=_LK_SID):
    return _bl.record_stop(_lk_repo, sid, check, mark, failing, "Files a turn writes are committed.", fix)


# block 1, 2, 3 then pass-through on the 4th, and never a fourth block
_lk_seq = [_lk_stop("commit", "m1", True) for _ in range(6)]
_lk_want = ["block", "block", "block", "through", "through", "through"]
report("PASS" if _lk_seq == _lk_want else "FAIL",
       "a failing check blocks three times for one message, then the reply goes through, and it never blocks a fourth time")
if _lk_seq != _lk_want:
    print(f"          got {_lk_seq}")
_lk_state = _bl.state_path(_lk_repo, _LK_SID)
_lk_porc = subprocess.run(["git", "-C", _lk_repo, "status", "--porcelain"], stdout=subprocess.PIPE).stdout.strip()
report("PASS" if (os.path.join(".git", "house-rules") in _lk_state and os.path.isfile(_lk_state) and not _lk_porc) else "FAIL",
       "the counter file lives inside the git directory, so git never sees it (never committed)")
_lk_other = [_lk_stop("evidence", "m1", True, sid="other-session") for _ in range(2)]
report("PASS" if (_lk_other == ["block", "block"] and _bl.block_count(_lk_repo, "other-session", "evidence", "m1") == 2
                  and not _bl.is_locked(_lk_repo, "other-session")) else "FAIL",
       "counts are per check and per session: another session's evidence check starts at its own count")
report("PASS" if _lk_stop("commit", "m2", True) == "block" else "FAIL",
       "a new message from aj starts the count again at block 1 (the lock stays until the check passes)")

# the lock refuses a source edit and a commit, naming the check, what it misses and how to supply it
_c, _ref, _why, _sm, _o = _lk_gate("Edit", {"file_path": _LK_SRC})
report("PASS" if (_c == 0 and _ref and "commit" in _why and "Missing:" in _why and "To supply it: commit a.py" in _why) else "FAIL",
       "while the commit check is locked a source-file edit is refused, naming the check, what it misses and the fix")
if not _ref:
    print(f"          out {_o[:200]!r}")
_lk_stop("commit", "m2", False)  # clear commit, lock evidence instead
for _ in range(4):
    _lk_stop("evidence", "m3", True, fix="run the check and quote its real output")
_c, _ref, _why, _sm, _o = _lk_gate("Bash", {"command": "git commit -am 'x'"})
report("PASS" if (_ref and "evidence" in _why and "git commit" in _why) else "FAIL",
       "while another check (evidence) is locked, a commit is refused, naming that check")
_c, _ref2, _why2, _, _ = _lk_gate("Bash", {"command": "git -C %s push origin main" % _lk_repo})
report("PASS" if _ref2 else "FAIL", "while a check is locked, a push is refused too, even behind -C")
_c, _ref3, _, _, _ = _lk_gate("Bash", {"command": "git log --grep commit && python3 -m pytest -q && ls"})
report("PASS" if not _ref3 else "FAIL", "running tests, reading history and listing files are never refused by the lock")
_lk_scratch = os.path.join(tempfile.gettempdir(), "content.json")
for _tool, _fp in (("Write", os.path.join(_lk_repo, "docs", "plans", "x.page.json")),
                   ("Edit", os.path.join(_lk_repo, "docs", "3-state", "ProjectState.md")),
                   ("Write", "docs/notes.md"),
                   ("Write", _lk_scratch)):
    _c, _r, _, _, _o = _lk_gate(_tool, {"file_path": _fp, "content": "x"})
    report("PASS" if (not _r and _c == 0) else "FAIL",
           f"locked: {_tool} of {os.path.basename(_fp)} is allowed (docs, docs/plans, or outside the folder)")
for _tool, _key in (("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path"), ("Write", "file_path")):
    _c, _r, _, _, _ = _lk_gate(_tool, {_key: "src/code.py"})
    report("PASS" if _r else "FAIL", f"locked: a relative source path through {_tool} is refused")

# the lock allows the commit when the commit check is the locked one
for _ in range(4):
    _lk_stop("commit", "m4", True, fix="commit a.py on your own branch")
_lk_stop("evidence", "m3", False)
_c, _r, _, _, _o = _lk_gate("Bash", {"command": "git add a.py && git commit -m 'x'"})
report("PASS" if not _r else "FAIL", "when the commit check is the locked one, a commit is allowed (it is how the check passes)")
_c, _r, _why, _, _ = _lk_gate("Bash", {"command": "git push origin HEAD"})
report("PASS" if (_r and "commit" in _why) else "FAIL", "...but a push is still refused while the commit check is locked")
_c, _r, _, _, _ = _lk_gate("Edit", {"file_path": _LK_SRC})
report("PASS" if _r else "FAIL", "...and a source edit is still refused")

# the lock clears the moment a later Stop finds the check passing
_lk_stop("commit", "m5", False)
_c, _r, _, _sm, _o = _lk_gate("Edit", {"file_path": _LK_SRC})
_c2, _r2, _, _, _ = _lk_gate("Bash", {"command": "git push origin HEAD"})
report("PASS" if (not _r and not _r2 and not _bl.is_locked(_lk_repo, _LK_SID)) else "FAIL",
       "a later Stop that finds the check passing clears the lock at once: edits and pushes are allowed again")
_lk_after = [_lk_stop("commit", "m6", True) for _ in range(2)]
report("PASS" if _lk_after == ["block", "block"] else "FAIL", "after a pass the count is back to zero for the same check")

# no lock at all: an ordinary session gets no refusal and no noise
_c, _r, _, _sm, _o = _lk_gate("Edit", {"file_path": _LK_SRC}, sid="never-failed")
report("PASS" if (_c == 0 and not _r and _o == "") else "FAIL", "with no locked check the hook allows everything and says nothing")

# unreadable state: loud and open, never a refusal
with open(_bl.state_path(_lk_repo, "broken"), "w", encoding="utf-8") as _f:
    _f.write("{not json")
for _tool, _ti in (("Edit", {"file_path": _LK_SRC}), ("Bash", {"command": "git commit -m x"})):
    _c, _r, _, _sm, _o = _lk_gate(_tool, _ti, sid="broken")
    report("PASS" if (_c == 0 and not _r and "NOT enforced" in _sm and "allowed" in _sm) else "FAIL",
           f"unreadable lock state: a {_tool} call is allowed and the hook says loudly that the lock is not enforced")
os.remove(_bl.state_path(_lk_repo, "broken"))  # the state file is per repository: later cases need it readable
_p = run_hook("lockgate", "not json at all", env=env_in(_lk_repo))
report("PASS" if (_p[0] == 0 and "NOT enforced" in _p[1] and "deny" not in _p[1]) else "FAIL",
       "an unreadable payload is allowed with a loud message, never a refusal")
_p = run_shell([RUN, "lockgate"], env=dict(os.environ, PATH="/nonexistent", HOUSE_RULES_PYTHON=""))
report("PASS" if (_p[0] == 0 and "NOT enforced" in _p[1] and "deny" not in _p[1]) else "FAIL",
       "with no working Python the lockgate shim exits 0 and says the lock is not enforced")
# --- shell writes, the target's repository, and scratch paths (#440 part B follow-up) ---------------------
_lk_other_repo = tempfile.mkdtemp(prefix="lock-other-")
subprocess.run(["git", "init", "-q", _lk_other_repo], check=True)
_lk_scratch_dir = tempfile.mkdtemp(prefix="lock-scratch-")  # inside no repository
_XS = "xs-session"
for _ in range(4):
    _lk_stop("evidence", "x1", True, fix="run the check and quote its real output", sid=_XS)
for _tool in ("Bash", "PowerShell"):
    for _cmd in ("sed -i s/a/b/ src/app.py", "echo x > src/app.py", "echo x | tee src/app.py", "printf x >> src/app.py",
                 "cp /etc/hostname src/app.py", "mv src/app.py src/old.py", "dd if=/dev/zero of=src/app.py",
                 "python3 -c \"open('src/app.py','w').write('x')\"", "perl -pi -e s/a/b/ src/app.py"):
        _c, _r, _why, _, _ = _lk_gate(_tool, {"command": _cmd}, sid=_XS)
        report("PASS" if (_r and "evidence" in _why and "src/app.py" in _why) else "FAIL",
               f"locked: {_tool} `{_cmd}` is refused like an Edit, naming the check")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": "echo x > $TARGET"}, sid=_XS)
report("PASS" if _r else "FAIL", "locked: a shell write whose path cannot be read is refused, not waved through")
for _cmd in ("echo x > docs/notes.md", "echo x > docs/plans/p.page.json", "sed -i s/a/b/ docs/3-state/ProjectState.md",
             "echo x > %s/content.json" % _lk_scratch_dir, "echo hi | cat", "python3 -m pytest -q 2>&1 | tee /dev/null"):
    _c, _r, _, _, _ = _lk_gate("Bash", {"command": _cmd}, sid=_XS)
    report("PASS" if not _r else "FAIL", f"locked: `{_cmd}` is allowed (docs, docs/plans, a path in no repository, reading, tests)")
# quote-aware statement splitting (replay finding, #452)
_c, _r, _, _, _ = _lk_gate("Bash", {"command": 'echo "a && b" > src/app.py'}, sid=_XS)
report("PASS" if _r else "FAIL", 'locked: `echo "a && b" > src/app.py` is still refused as a write to src/app.py')
_c, _r, _why, _, _ = _lk_gate("Bash", {"command": 'echo "x\ny" && sed -i s/a/b/ src/app.py'}, sid=_XS)
report("PASS" if (_r and "src/app.py" in _why) else "FAIL", "locked: a sed -i after a quoted multi-line argument is refused")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": 'echo "unclosed > docs/notes.md'}, sid=_XS)
report("PASS" if _r else "FAIL", "locked: a statement with truly unbalanced quotes counts as unreadable and is refused")
_c, _o, _e = run_hook("lockgate", json.dumps({"hook_event_name": "PreToolUse", "session_id": "nolock", "cwd": _lk_repo,
                      "tool_name": "Bash", "tool_input": {"command": 'ls && echo "line one\nline two" | cat'}}),
                      env=env_in(_lk_repo))
report("PASS" if (_e == "" and not _o.strip()) else "FAIL", "a multi-line quoted argument prints nothing to stderr and is not refused")
# the target's repository decides, not the payload cwd
_c, _r, _why, _, _ = _lk_gate("Edit", {"file_path": _LK_SRC}, sid=_XS, cwd=_lk_other_repo)
report("PASS" if (_r and "evidence" in _why) else "FAIL", "a call whose cwd is another repo, editing the locked repo's file by its path, is refused")
_c, _r, _, _, _ = _lk_gate("Edit", {"file_path": os.path.join(_lk_other_repo, "x.py")}, sid=_XS)
report("PASS" if not _r else "FAIL", "a call from the locked repo editing a file in another (unlocked) repo is allowed")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": "echo x > %s" % _LK_SRC}, sid=_XS, cwd=_lk_other_repo)
report("PASS" if _r else "FAIL", "a shell write by absolute path into the locked repo from another cwd is refused")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": "cd %s && echo x > src/app.py" % _lk_repo}, sid=_XS, cwd=_lk_other_repo)
report("PASS" if _r else "FAIL", "`cd <locked repo> && echo x > file` from another cwd is refused")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": "git -C %s commit -m x" % _lk_repo}, sid=_XS, cwd=_lk_other_repo)
report("PASS" if _r else "FAIL", "`git -C <locked repo> commit` from another cwd is refused")
_c, _r, _, _, _ = _lk_gate("Bash", {"command": "git -C %s commit -m x" % _lk_other_repo}, sid=_XS)
report("PASS" if not _r else "FAIL", "`git -C <other repo> commit` from the locked repo is allowed (that repo is not locked)")
_c, _r, _, _, _ = _lk_gate("Write", {"file_path": os.path.join(_lk_scratch_dir, "c.json"), "content": "{}"}, sid=_XS)
report("PASS" if not _r else "FAIL", "a scratch file in no repository is allowed")
# a non-git session folder: the session-keyed temp file holds the lock, and the folder's files are covered
_lk_plain = tempfile.mkdtemp(prefix="lock-plain-")
for _ in range(4):
    _bl.record_stop(_lk_plain, "plain-sid", "evidence", "p1", True, "needs evidence", "quote output")
_c, _r, _, _, _ = _lk_gate("Edit", {"file_path": os.path.join(_lk_plain, "app.py")}, sid="plain-sid", cwd=_lk_plain)
_c2, _r2, _, _, _ = _lk_gate("Edit", {"file_path": os.path.join(_lk_scratch_dir, "z.py")}, sid="plain-sid", cwd=_lk_plain)
report("PASS" if (_r and not _r2) else "FAIL", "outside a repository the session folder's files are locked and a path outside it is not")
# the lock record carries the files it named
for _ in range(4):
    _bl.record_stop(_lk_repo, "files-sid", "commit", "f1", True, "needs commit", "commit it", ["src/app.py"])
_c, _r, _why, _, _ = _lk_gate("Edit", {"file_path": _LK_SRC}, sid="files-sid")
report("PASS" if (_r and "Files it named: src/app.py" in _why) else "FAIL", "the refusal names the files a commit lock was recorded with")
for _d in (_lk_other_repo, _lk_scratch_dir, _lk_plain):
    shutil.rmtree(_d, True)
shutil.rmtree(_lk_repo, True)


# --- every ${CLAUDE_PLUGIN_ROOT}/... or <plugin>/... path the rules name exists in this plugin (#440) ----
import re as _re
_rp_missing = []
for _dp, _dn, _fn in os.walk(os.path.join(PLUGIN, "rules")):
    for _f in _fn:
        _txt = open(os.path.join(_dp, _f), encoding="utf-8").read()
        for _m in _re.findall(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}|<plugin>)/[A-Za-z0-9_./*-]+", _txt):
            _rel = _re.sub(r"^(?:\$\{CLAUDE_PLUGIN_ROOT\}|<plugin>)/", "", _m).rstrip(".,;:)")
            if not os.path.exists(os.path.join(PLUGIN, _rel)):
                _rp_missing.append("%s -> %s" % (_f, _rel))
report("FAIL" if _rp_missing else "PASS", "every plugin-root path in rules/ exists inside rule-enforcement" +
       ("".join("\n          missing " + x for x in _rp_missing)))

finish()
