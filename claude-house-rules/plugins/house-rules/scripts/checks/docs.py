#!/usr/bin/env python3
"""checks/docs.py - the docs part: docstiers, harvest, docref and plain_docs_check (#370).

Run it alone:  python3 claude-house-rules/plugins/house-rules/scripts/checks/docs.py
It prints its own numbered results and a RESULT line, and exits non-zero if any check fails. verify.py runs
every part at the same time; see docs/4-systems/verify-suites.md, "The split layout (#370)".

STDLIB ONLY, like hook.py.

docref: skip-file - this file's docref cases hold deliberately broken pointers, so docref.py check skips it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa: F401,F403 - common.py sets __all__ to everything it defines

print()
print("house-rules hooks - verification (Python) - part: docs")
print("=" * 43)
print()

for _event, _margin, _env in _size_cases[4:]:  # docstiers
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

# --- docstiers: complete/missing, owned/not-owned, ssh, no .git, unreadable/garbage config ----
_docstiers_cases = [
    (
        "all six tiers present - silent",
        DOCSTIERS_COMPLETE,
        {"empty": True},
    ),
    (
        "missing tiers, https remote owned by the configured account - no exclude instruction",
        DOCSTIERS_OWNED,
        {"missing": True, "exclude": False, "owned": True},
    ),
    (
        "missing tiers, https remote NOT owned - exclude instruction present",
        DOCSTIERS_NOT_OWNED,
        {"missing": True, "exclude": True, "owned": False},
    ),
    (
        "missing tiers, ssh-form remote owned by the configured account",
        DOCSTIERS_SSH_OWNED,
        {"missing": True, "exclude": False, "owned": True},
    ),
    (
        "missing tiers, not a git repository at all - no exclude instruction",
        DOCSTIERS_NO_GIT,
        {"missing": True, "exclude": False, "not_git": True},
    ),
    (
        "missing tiers, garbage .git/config - falls to not-owned and says so",
        DOCSTIERS_GARBAGE_CONFIG,
        {"missing": True, "exclude": True, "owned": False},
    ),
    (
        "missing tiers, unreadable .git/config - falls to not-owned and says so",
        DOCSTIERS_UNREADABLE_CONFIG,
        {"missing": True, "exclude": True, "owned": False},
    ),
    (
        "old flat layout, all tiers present under it - reported as moves, not missing",
        DOCSTIERS_OLD_LAYOUT,
        {"old_layout": True},
    ),
]
for _title, _path, _expect in _docstiers_cases:
    _code, _out, _err = run_hook("docstiers", "", env=env_in(_path))
    _problems = []
    if _code != 0:
        _problems.append(f"exited {_code}, expected 0")
    if _expect.get("empty"):
        if _out.strip():
            _problems.append(f"expected a fully silent stdout, got: {_out[:200]!r}")
    elif _expect.get("old_layout"):
        if "old flat layout" not in _out:
            _problems.append("expected the old-flat-layout move message, not present")
        if "docs/Roadmap.md to docs/2-roadmap/Roadmap.md" not in _out:
            _problems.append("expected a named move for docs/Roadmap.md")
        if "docs/systems/*.md to docs/4-systems/*.md" not in _out:
            _problems.append("expected a named move for docs/systems/*.md")
        if "missing" in _out.lower() and "outright" in _out.lower():
            _problems.append("an all-present old layout should not also claim tiers are missing")
    else:
        if "house-rules:project-docs" not in _out:
            _problems.append("missing the load-and-scaffold instruction")
        _exclude_instruction = "add every scaffolded path to .git/info/exclude" in _out
        if _expect.get("exclude") and not _exclude_instruction:
            _problems.append("expected the .git/info/exclude instruction, not present")
        if not _expect.get("exclude") and _exclude_instruction:
            _problems.append("the .git/info/exclude instruction leaked into an owned/no-git case")
        if _expect.get("not_git") and "not a git repository" not in _out.lower():
            _problems.append("expected a not-a-git-repository note")
    if not _problems:
        report("PASS", f"docstiers: {_title}")
        print(f"          {len(_out)} chars emitted")
    else:
        report("FAIL", f"docstiers: {_title}")
        print(f"          {'; '.join(_problems)}")

# docstiers's fail-loud path (systemMessage on an internal error, like inject) is covered by
# main()'s generic exception net, proven generically further down this file rather than with a
# docstiers-specific fixture - every input docstiers actually reads already degrades gracefully
# by design (a garbage/unreadable .git/config falls to not-owned, not a crash - proven above).

_skill_drift = []
if not os.path.isfile(DOCSKILL):
    _skill_drift.append("skills/project-docs/SKILL.md is missing")
else:
    _skill_text = read(DOCSKILL)
    for _tier_phrase in [
        "docs/1-landing/README.md", "docs/2-roadmap/Roadmap.md", "docs/3-state/ProjectState.md",
        "docs/4-systems/*.md", "docs/5-today/Today.md", "docs/6-decisions/Decisions.md",
    ]:
        if _tier_phrase not in _skill_text:
            _skill_drift.append(f"{_tier_phrase!r} is not named in SKILL.md - docstiers may be inventing tier names")
if not _skill_drift:
    report("PASS", "docstiers's hardcoded tier list matches skills/project-docs/SKILL.md")
    print("          all six tier paths docstiers checks are the ones SKILL.md names")
else:
    report("FAIL", "docstiers's hardcoded tier list matches skills/project-docs/SKILL.md")
    print(f"          {'; '.join(_skill_drift)}")
SHORT_CS = CS_HEAD + "// Must run after Init(). Order matters here.\nvoid A() { }\n"
COMMENTED_CODE = CS_HEAD + "".join(
    "// var x%d = Compute(y, z);\n" % i for i in range(30)
) + "void B() { }\n"
LICENSE_CS = CS_HEAD + (
    "// Copyright 2026 Someone. All rights reserved. Licensed under the Apache License,\n"
    "// Version 2.0 (the \"License\"); you may not use this file except in compliance with it.\n"
    "// You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.\n"
    "// Unless required by applicable law, software distributed under the License is\n"
    "// distributed on an \"AS IS\" BASIS, without warranties or conditions of any kind.\n"
    "// See the License for the specific language governing permissions and limitations.\n"
    "// Unless required by applicable law or agreed to in writing, this file is provided as is.\n"
    "class C { }\n"
)
ESSAY_PY = (
    'import time\n'
    '\n'
    'def f():\n'
    '    """Retries are capped at three because the upstream service rate-limits per minute.\n'
    '\n'
    '    A fourth attempt inside the same window is always rejected, so retrying it converts a\n'
    '    slow failure into a slower one. The backoff is deliberately not jittered: the caller\n'
    '    is a single cron job, so there is no thundering herd to spread out, and a fixed delay\n'
    '    makes the failure timeline reproducible when reading logs after the fact. Raising the\n'
    '    cap needs the upstream owner to raise the limit first, otherwise the extra attempts are\n'
    '    simply wasted requests that count against the same per-minute budget.\n'
    '    """\n'
    '    return 1\n'
)


def harv_case(expect, title, file_path, content, tool="Write", env=None, expect_in=()):
    field = "content" if tool == "Write" else "new_string"
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path, field: content}})
    e = dict(os.environ)
    e.pop("HOUSE_RULES_HARVEST", None)
    e.pop("HOUSE_RULES_HARVEST_MIN_CHARS", None)
    e.pop("HOUSE_RULES_DEBUG", None)
    e["HOUSE_RULES_TRACE"] = "verbose"  # the no-blocks trace is verbose-only; env= may override
    if env:
        e.update(env)
    code, out, err = run_hook("harvest", payload, env=e)
    if '"additionalContext"' in out and "systemMessage" in out:
        got = "remind+trace"
    elif '"additionalContext"' in out:
        got = "remind"
    elif "systemMessage" in out:
        got = "trace"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    if code != 0:
        got = f"{got} (exit {code})"
    missing = [p for p in expect_in if p not in out]
    ok = got == expect and not missing
    report("PASS" if ok else "FAIL", title)
    detail = f"expected {expect}, got {got}"
    if missing:
        detail += f"; missing from output: {'; '.join(missing)}"
    print(f"          {detail}")


harv_case(
    "remind+trace",
    "a design essay in a .cs file is flagged for porting into docs/4-systems/",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    expect_in=["@house-rules:archivist", "one-line pointer", "Orbit.cs:5-12"],
)
harv_case(
    "remind+trace",
    "a long Python docstring is flagged the same way as a // block",
    "/proj/svc/retry.py",
    ESSAY_PY,
)
harv_case(
    "trace",
    "a short why-comment is left alone",
    r"C:\proj\A.cs",
    SHORT_CS,
)
harv_case(
    "trace",
    "many short comment lines are not an essay - characters decide, not line count",
    r"C:\proj\A.cs",
    CS_HEAD + "".join("// Order matters %d.\n" % i for i in range(12)) + "void A() { }\n",
    expect_in=["none met 500 chars"],
)
harv_case(
    "trace",
    "thirty lines of commented-out code is not an essay",
    r"C:\proj\B.cs",
    COMMENTED_CODE,
    expect_in=["rejected: looks like commented-out code"],
)
harv_case(
    "trace",
    "a license header is not an essay",
    r"C:\proj\C.cs",
    LICENSE_CS,
    expect_in=["rejected: license header"],
)
harv_case(
    "silent",
    "a markdown file is out of jurisdiction - the one fully silent path",
    r"C:\proj\docs\systems\physics.md",
    "Sentence one. Sentence two. " * 60,
)

# --- harvest: the trace never claims "none met the threshold" for a run that did meet it -------
# The bug this guards: a run long enough to clear the threshold but rejected for cause (a file
# header, commented-out code, a license block) was reported as "none met N lines / M chars" -
# self-contradictory once the run's own size was printed right next to that claim.
for label, payload_content in (("commented-out code", COMMENTED_CODE), ("license header", LICENSE_CS)):
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": r"C:\proj\D.cs", "content": payload_content}}
    )
    code, out, err = run_hook("harvest", payload)
    if "none met" not in out:
        report("PASS", f"a run that met the size threshold but was rejected ({label}) is not reported as 'none met'")
        print(f"          {label}: no self-contradictory 'none met' phrasing in the trace")
    else:
        report("FAIL", f"a run that met the size threshold but was rejected ({label}) is not reported as 'none met'")
        print(f"          got: {out[:300]}")

# --- harvest: the trace is on by DEFAULT, and says what it measured ----------------------------
# A diagnostic that ships switched off is never enabled until someone is already lost, so the
# default output has to answer "did this run, on what, and what did it decide" with no flags set.
harv_case(
    "trace",
    "the default trace names the measured longest run and the active threshold",
    r"C:\proj\A.cs",
    SHORT_CS,
    expect_in=["A.cs", "500 chars", "longest was 1 line"],
)
harv_case(
    "remind+trace",
    "HOUSE_RULES_DEBUG=1 adds the per-run rejection reasons on top of the default trace",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS + "\n" + SHORT_CS,
    env={"HOUSE_RULES_DEBUG": "1"},
    expect_in=["runs considered:"],
)

# --- harvest: the thresholds are tunable, and a bad value is announced not ignored -------------
harv_case(
    "trace",
    "raising HOUSE_RULES_HARVEST_MIN_CHARS stops the essay qualifying",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST_MIN_CHARS": "9000"},
)
harv_case(
    "remind+trace",
    "a bad threshold override is named out loud and the default is used anyway",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST_MIN_CHARS": "banana"},
    expect_in=["banana", "using the defaults"],
)

# --- harvest: toggles --------------------------------------------------------------------------
harv_case(
    "remind",
    "HOUSE_RULES_HARVEST=quiet keeps the reminder and drops the trace",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST": "quiet"},
)
harv_case(
    "silent",
    "HOUSE_RULES_HARVEST=off disables the reminder and the trace together",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST": "off"},
)

# --- harvest: an Edit carries a fragment, so its line numbers are withheld ---------------------
# Reporting new_string offsets as file lines would put a confidently wrong file:line into a
# document whose own convention is to cite file:line. Better to say the ranges are unavailable.
harv_case(
    "remind+trace",
    "an Edit is flagged but reports no line range, because the fragment's offsets are not the file's",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    tool="Edit",
    expect_in=["find the blocks by reading the file"],
)
edit_payload = json.dumps(
    {"tool_name": "Edit", "tool_input": {"file_path": r"C:\proj\Assets\Orbit.cs", "new_string": ESSAY_CS}}
)
code, out, err = run_hook("harvest", edit_payload)
if "Orbit.cs:5-12" not in out and "Blocks:" not in out:
    report("PASS", "an Edit's reminder carries no file:line range at all")
    print("          no fabricated line numbers in the Edit reminder")
else:
    report("FAIL", "an Edit's reminder carries no file:line range at all")
    print(f"          got: {out[:300]}")

# --- harvest: an Edit fragment's own line 1 is not the file's line 1 ---------------------------
# Regression for docs/6-decisions/Decisions.md, "Fix the harvest handler treating an Edit fragment's line 1
# as the file's header".
EDIT_ESSAY_AT_FRAGMENT_START = (
    "// The orbit integrator uses Verlet rather than Euler. Euler was tried first and lost\n"
    "// energy visibly over about four minutes of play, which showed up as satellites slowly\n"
    "// spiralling into the planet with no force acting on them. Verlet is symplectic, so the\n"
    "// energy error is bounded rather than cumulative, and the artefact goes away entirely.\n"
    "// The cost is that velocity is not directly available at the current step; where a caller\n"
    "// needs it, it is reconstructed from the two most recent positions instead.\n"
    "// A fixed timestep would sidestep the problem, but the game runs its physics on the\n"
    "// render clock, so the integrator has to tolerate a varying dt without drifting.\n"
    "public void Step(float dt) { }\n"
)
harv_case(
    "remind+trace",
    "an essay at the very start of an Edit's new_string is still flagged, not exempted as a file header",
    r"C:\proj\Assets\Orbit.cs",
    EDIT_ESSAY_AT_FRAGMENT_START,
    tool="Edit",
    expect_in=["@house-rules:archivist"],
)
edit_head_payload = json.dumps(
    {
        "tool_name": "Edit",
        "tool_input": {"file_path": r"C:\proj\Assets\Orbit.cs", "new_string": EDIT_ESSAY_AT_FRAGMENT_START},
    }
)
code, out, err = run_hook("harvest", edit_head_payload)
if "file header" not in out:
    report("PASS", "an Edit fragment starting on a comment is not classified as a file header")
    print("          the fragment's line 1 was not mistaken for the file's line 1")
else:
    report("FAIL", "an Edit fragment starting on a comment is not classified as a file header")
    print(f"          got: {out[:300]}")

# --- harvest: a genuine file header (Write, real line 1) is still exempted ---------------------
# The other half of the same fix: full_file=True must still exempt a real module docstring when
# the content really is the whole file, so the fix narrows the bug rather than removing the
# exemption outright.
PY_MODULE_DOCSTRING = (
    '"""Orbit decay is modelled with an inverse-square drag term rather than a constant one.\n'
    '\n'
    'A constant term made outer satellites decay at the same rate as inner ones, which reads as\n'
    'wrong to anyone who has watched a real orbit - drag falls off with altitude, and the model\n'
    'should too. The inverse-square term was chosen over inverse-cube because it matches the\n'
    'reference atmosphere table closely enough over the altitudes this game actually uses.\n'
    'Above the model ceiling the drag term is simply zero, since the table stops there and\n'
    'extrapolating past it would invent numbers nobody has measured.\n'
    '"""\n'
    'import time\n'
)
harv_case(
    "trace",
    "a real module docstring at the file's actual line 1 is still exempted as a file header",
    "/proj/svc/decay.py",
    PY_MODULE_DOCSTRING,
    expect_in=["file header"],
)

# --- harvest: every "could not tell" path is loud, and none of them obstruct -------------------
for payload, label in (
    ("", "an empty payload"),
    ('{"tool_input": ', "a payload that will not parse"),
    ('{"tool_name":"Write","tool_input":{}}', "a payload with no file_path"),
    (
        '{"tool_name":"Write","tool_input":{"file_path":"/proj/A.cs"}}',
        "a payload with a source path but no body",
    ),
):
    code, out, err = run_hook("harvest", payload)
    if code == 0 and "systemMessage" in out and "did not run" in out:
        report("PASS", f"harvest given {label} says so out loud and still exits 0")
        print("          never obstructs, never goes quiet")
    else:
        report("FAIL", f"harvest given {label} says so out loud and still exits 0")
        print(f"          exit {code}, got: {out[:200]!r}")
_hd = dict(_dflt)
_hd["HOUSE_RULES_HARVEST_MIN_CHARS"] = "banana"
_short_payload = json.dumps(
    {"tool_name": "Write", "tool_input": {"file_path": "/p/a.cs", "content": SHORT_CS}}
)
code, out, err = run_hook("harvest", _short_payload, env=_dflt)
if code == 0 and not out.strip():
    report("PASS", "harvest is silent by default when no comment block qualifies")
else:
    report("FAIL", "harvest is silent by default when no comment block qualifies")
    print(f"          exit {code}, got: {out[:160]!r}")
code, out, err = run_hook("harvest", _short_payload, env=_hd)
if code == 0 and "banana" in out and "systemMessage" in out:
    report("PASS", "harvest still speaks by default when an override is bad")
else:
    report("FAIL", "harvest still speaks by default when an override is bad")
    print(f"          exit {code}, got: {out[:160]!r}")
code, out, err = run_hook(
    "harvest",
    json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/p/a.cs", "content": ESSAY_CS}}),
    env=_dflt,
)
if code == 0 and "additionalContext" in out and "systemMessage" in out:
    report("PASS", "harvest still speaks by default when blocks are found")
else:
    report("FAIL", "harvest still speaks by default when blocks are found")
    print(f"          exit {code}, got: {out[:160]!r}")

# --- harvest scans a big file rather than skipping it, and does it in linear time -------------
# Regression: the run accumulator rebuilt its line list per line, which is O(n^2). A 4.8MB file
# took 22 seconds - past hooks.json's 10s timeout, so in practice the harness killed the hook
# instead of it reporting anything. Hand-testing caught this; the suite had not.
big = "using UnityEngine;\n" + ("// Filler line of ordinary prose here. And another sentence.\n" * 60000)
big_payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/proj/Big.cs", "content": big}})
started = time.time()
code, out, err = run_hook("harvest", big_payload)
elapsed = time.time() - started
if code == 0 and '"additionalContext"' in out and elapsed < 8:
    report("PASS", "a multi-megabyte file is scanned, not skipped, and well inside the hook timeout")
    print(f"          {len(big)} bytes scanned in {elapsed:.2f}s (hooks.json allows 10s)")
else:
    report("FAIL", "a multi-megabyte file is scanned, not skipped, and well inside the hook timeout")
    print(f"          exit {code} after {elapsed:.2f}s, got: {out[:160]!r}")

# --- and when the scan genuinely does run long, it says so by name ----------------------------
budget_snippet = (
    "import sys, hook\n"
    "hook.docs.HARVEST_BUDGET_SECONDS = -1.0\n"  # #358: harvest lives in the docs part now
    "sys.exit(hook.main(['hook.py', 'harvest']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", budget_snippet],
    cwd=HERE,
    input=big_payload.encode("utf-8"),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    timeout=30,
)
out = proc.stdout.decode("utf-8", "replace")
if proc.returncode == 0 and "exceeded its" in out and "was not checked" in out and "Big.cs" in out:
    report("PASS", "a scan that runs out of budget names the file and says it was not checked")
    print("          loud and specific, rather than a silent skip or a harness timeout")
else:
    report("FAIL", "a scan that runs out of budget names the file and says it was not checked")
    print(f"          exit {proc.returncode}, got: {out[:200]!r}")

# --- harvest is wired to Write|Edit, not just present in hook.py -------------------------------
if 'run.sh\\" harvest' in hooks_json_text and hooks_json_text.count('"matcher": "Write|Edit"') >= 2:
    report("PASS", "harvest is registered on PostToolUse with matcher Write|Edit")
    print("          hooks.json wires Write|Edit to run.sh harvest")
else:
    report("FAIL", "harvest is registered on PostToolUse with matcher Write|Edit")
    print("          hooks.json does not wire Write|Edit to run.sh harvest")

# --- run.sh's no-interpreter fallback for harvest is loud, not silent --------------------------
code, out, err = run_shell([RUN, "harvest"], env={**os.environ, "PATH": ""})
if code == 0 and "systemMessage" in out and "did not run" in out:
    report("PASS", "harvest with no working Python says so rather than falling through silently")
    print("          run.sh's per-event fallback covers harvest by name")
else:
    report("FAIL", "harvest with no working Python says so rather than falling through silently")
    print(f"          exit {code}, got: {out[:200]!r}")
for ev, needle in (
    ("harvest", "harvest"),
    ("docstiers", "docstiers"),
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

# --- the archivist subagent is shaped so the delegation can actually happen --------------------
archivist = read(ARCHIVIST)
problems = []
if not re.search(r"^name: archivist$", archivist, re.MULTILINE):
    problems.append("name: archivist is missing from the frontmatter")
if not re.search(r"^model: sonnet$", archivist, re.MULTILINE):
    problems.append("model: sonnet is missing - the whole point is not running this on Opus")
for forbidden in ("hooks:", "mcpServers:", "permissionMode:"):
    if re.search(r"^%s" % re.escape(forbidden), archivist, re.MULTILINE):
        problems.append(f"{forbidden} is set, and plugin subagents silently ignore it")
desc = ""
for line in archivist.split("\n"):
    if line.startswith("description:"):
        desc = line
        break
if "proactiv" not in desc.lower():
    problems.append("the description does not say to use it proactively, so the Agent gate wins")
for phrase in ("not injected", "one-line pointer", "Nothing fails silently", "docs/4-systems",
               "doc-ref", "<!-- ref:", "${CLAUDE_PLUGIN_ROOT}/scripts/docref.py", "fix --write"):
    if phrase.lower() not in archivist.lower():
        problems.append(f"the digest no longer states {phrase!r}")
if not problems:
    report("PASS", "the archivist subagent is shaped so the harvest delegation can happen")
    print("          pinned to sonnet, marked proactive, and carries the digest it needs")
else:
    report("FAIL", "the archivist subagent is shaped so the harvest delegation can happen")
    for p in problems:
        print(f"          {p}")
for _restatement in [RESTATEMENTS[_i] for _i in (6,)]:  # docs
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

# --- /house-rules:harvest-scan exists and actually invokes harvest_scan.py ---------------------
HARVEST_SCAN_CMD = os.path.join(HERE, "..", "commands", "harvest-scan.md")
HARVEST_SCAN_PY = os.path.join(HERE, "harvest_scan.py")
hsdrift = []
if not os.path.isfile(HARVEST_SCAN_CMD):
    hsdrift.append("commands/harvest-scan.md is missing")
if not os.path.isfile(HARVEST_SCAN_PY):
    hsdrift.append("scripts/harvest_scan.py is missing")
if not hsdrift:
    cmd_text = read(HARVEST_SCAN_CMD)
    for needle in ["harvest_scan.py", "${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS",
                   "the plugin root did not resolve"]:
        if needle not in cmd_text:
            hsdrift.append(f"harvest-scan.md is missing {needle!r}")
    # The bare form is never substituted and is not exported to the Bash tool's shell.
    CMDS_DIR = os.path.dirname(HARVEST_SCAN_CMD)
    for name in sorted(os.listdir(CMDS_DIR)):
        path = os.path.join(CMDS_DIR, name)
        if os.path.isfile(path) and re.search(r"\$CLAUDE_PLUGIN_ROOT", read(path)):
            hsdrift.append(f"commands/{name} uses bare $CLAUDE_PLUGIN_ROOT (must be braced)")
if not hsdrift:
    report("PASS", "/house-rules:harvest-scan exists and runs the installed harvest_scan.py")
    print("          resolves via ${CLAUDE_PLUGIN_ROOT}, never a hand-built cache path")
else:
    report("FAIL", "/house-rules:harvest-scan exists and runs the installed harvest_scan.py")
    print(f"          {'; '.join(hsdrift)}")

# Drift: the tiered-docs rule names a skill by id, so that skill has to exist. A rule that
# points at a skill nobody shipped is worse than no rule - it reads as though the detail is
# somewhere findable. Same class of check as the standards one above.
docs_drift = []
if "## Documentation goes in tiers" not in rules_text:
    docs_drift.append("house-rules.md is missing the tiered-docs rule heading")
if "house-rules:project-docs" not in rules_text:
    docs_drift.append("the tiered-docs rule no longer names the project-docs skill")
if "docs/6-decisions/Decisions.md" not in rules_text:
    docs_drift.append("house-rules.md no longer mentions docs/6-decisions/Decisions.md")
if not os.path.isfile(DOCSKILL):
    docs_drift.append("skills/project-docs/SKILL.md does not exist")
else:
    skill_text = read(DOCSKILL)
    for phrase in [
        "docs/2-roadmap/Roadmap.md", "docs/3-state/ProjectState.md", "docs/5-today/Today.md",
        "docs/4-systems", "docs/6-decisions/Decisions.md",
    ]:
        if phrase not in skill_text:
            docs_drift.append(f"the skill no longer specifies {phrase}")
if not docs_drift:
    report("PASS", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print("          the rule names the skill, the skill exists, and it still specifies all six tiers")
else:
    report("FAIL", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print(f"          {'; '.join(docs_drift)}")

# --- docref.py: the doc-ref pointer checker ----------------------------------------------------
# Design: docs/superpowers/specs/2026-09-20-pointer-integrity-design.md
DOCREF = os.path.join(HERE, "docref.py")
FENCE = "`" * 3


def docref_run(root, *args):
    cmd = [sys.executable, DOCREF, args[0], "--root", root] + list(args[1:])
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def docref_case(title, files, args, expect_rc, expect_in=(), expect_out=(), after=None, setup=None):
    d = make_fixture(files)
    try:
        if setup is not None:
            try:
                setup(d)
            except Exception as e:
                report("FAIL", title)
                stderr = getattr(e, "stderr", b"") or b""
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", "replace")
                print(f"          setup raised {type(e).__name__}: {e} {stderr.strip()[:200]}")
                return
        rc, out, err = docref_run(d, *args)
        problems = []
        if rc != expect_rc:
            problems.append(f"exit {rc}, expected {expect_rc}")
        for needle in expect_in:
            if needle not in out:
                problems.append(f"output is missing {needle!r}")
        for needle in expect_out:
            if needle in out:
                problems.append(f"output should not contain {needle!r}")
        if after is not None:
            ok, detail = after(d)
            if not ok:
                problems.append(detail)
        if not problems:
            report("PASS", title)
            print("          " + (out.strip().splitlines() or ["(no output)"])[-1][:100])
        else:
            report("FAIL", title)
            for p in problems:
                print(f"          {p}")
            print(f"          stdout: {out[:400]!r} stderr: {err[:200]!r}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


import importlib.util as _dr_importlib_util

_dr_spec = _dr_importlib_util.spec_from_file_location("docref_mod", DOCREF)
docref_mod = _dr_importlib_util.module_from_spec(_dr_spec)
DR_MOD_OK = os.path.isfile(DOCREF)
if DR_MOD_OK:
    _dr_spec.loader.exec_module(docref_mod)
else:
    report("FAIL", "docref.py is missing")
    print(f"          expected {DOCREF}; the docref tests that import it are skipped")

DR_DOC = "## Traps\n<!-- ref:a3f9 -->\nBody.\n"

docref_case(
    "docref check: a pointer whose id is in exactly one doc, at the recorded path, is ok",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "int x;\n// doc-ref a3f9 docs/systems/physics.md\n"},
    ["check"], 0,
    expect_in=["1 ok, 0 stale, 0 dangling", "docref: OK"],
)

docref_case(
    "docref check: a code file that opts out with 'docref: skip-file' is skipped and named, not scanned",
    {"docs/a.md": DR_DOC, "src/fixtures.py": "# docref: skip-file\n# doc-ref beef docs/none.md\n",
     "src/a.c": "// doc-ref a3f9 docs/a.md\n"},
    ["check"], 0,
    expect_in=["docref: skipped src/fixtures.py", "1 ok, 0 stale, 0 dangling", "docref: OK"],
)

docref_case(
    "docref check: the opt-out only counts in a file's first lines, so a later mention changes nothing",
    {"docs/a.md": DR_DOC, "src/a.c": "\n" * 12 + "// docref: skip-file\n// doc-ref beef docs/none.md\n"},
    ["check"], 1,
    expect_in=["DANGLING", "docref: PROBLEMS"],
)

docref_case(
    "docref check: a pointer whose doc moved is reported stale, naming the doc it moved to",
    {"docs/systems/new.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/old.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:1  STALE", "docs/systems/new.md", "1 stale"],
)

docref_case(
    "docref check: a pointer whose id no doc carries is dangling, with file and line",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "int x;\n// doc-ref beef docs/systems/physics.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:2  DANGLING", "1 dangling", "docref: PROBLEMS"],
)

docref_case(
    "docref check: one id claimed by two markers is a duplicate, and pointers to it are ambiguous",
    {"docs/a.md": DR_DOC, "docs/b.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["DUPLICATE", "a3f9", "1 ambiguous"],
)

docref_case(
    "docref check: an uppercase pointer id is malformed, not silently ignored",
    {"docs/a.md": DR_DOC, "src/a.c": "// doc-ref A3F9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["src/a.c:1  MALFORMED", "not 4 lowercase hex"],
)

docref_case(
    "docref check: a marker with a 3-character id is malformed",
    {"docs/a.md": "## T\n<!-- ref:abc -->\n"},
    ["check"], 1,
    expect_in=["docs/a.md:2  MALFORMED"],
)

docref_case(
    "docref check: a marker inside a fenced code block is ignored",
    {
        "docs/a.md": "Example:\n" + FENCE + "\n<!-- ref:a3f9 -->\n" + FENCE + "\n",
        "src/a.c": "// doc-ref a3f9 docs/a.md\n",
    },
    ["check"], 1,
    expect_in=["DANGLING"],
)

docref_case(
    "docref check: a marker quoted inline in prose is not a marker",
    {"docs/a.md": "Put `<!-- ref:a3f9 -->` under the heading.\n", "src/a.c": "// doc-ref a3f9 docs/a.md\n"},
    ["check"], 1,
    expect_in=["DANGLING"],
)

docref_case(
    "docref check: a marker nobody points at is information, not a failure",
    {"docs/a.md": DR_DOC},
    ["check"], 0,
    expect_in=["docs/a.md:2  INFO", "unreferenced", "docref: OK"],
)

docref_case(
    "docref check: a project with no docs and no pointers says so and passes",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["0 pointers found", "no docs/**/*.md", "docref: OK"],
)

docref_case(
    "docref check: prose pointers are counted as legacy, not judged",
    {"docs/4-systems/physics.md": "## T\n", "src/a.c": "// see docs/4-systems/physics.md, Traps\n"},
    ["check"], 0,
    expect_in=["1 line(s) mention docs/4-systems/", "legacy prose pointers"],
)

docref_case(
    "docref check: the words doc-ref in ordinary prose are not a pointer",
    {"src/a.c": "// the doc-ref token is what carries the id\n"},
    ["check"], 0,
    expect_in=["0 pointers found"],
)

docref_case(
    "docref check: --exclude skips a matching file",
    {"src/bad.c": "// doc-ref beef docs/none.md\n"},
    ["check", "--exclude", "src/bad.c"], 0,
    expect_in=["0 pointers found"],
)


def _dr_write_binary(d):
    with open(os.path.join(d, "blob.bin"), "wb") as f:
        f.write(b"\xff\xfe\x00\x01")


docref_case(
    "docref check: a binary file is counted as skipped, not read and not an error",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["1 binary skipped", "via directory walk"],
    setup=_dr_write_binary,
)


def _dr_git_setup(d):
    for args in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", "-C", d] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    with open(os.path.join(d, "src", "untracked.c"), "w", encoding="utf-8") as f:
        f.write("// doc-ref beef docs/none.md\n")


if shutil.which("git"):
    docref_case(
        "docref check: in a git work tree it reads tracked and untracked files and skips ignored ones",
        {
            ".gitignore": "ignored/\n",
            "docs/x.md": "## T\n<!-- ref:a3f9 -->\n",
            "src/tracked.c": "// doc-ref a3f9 docs/x.md\n",
            "ignored/bad.c": "// doc-ref beef docs/none.md\n",
        },
        ["check"], 1,
        expect_in=["src/untracked.c:1  DANGLING", "via git"],
        expect_out=["ignored/bad.c"],
        setup=_dr_git_setup,
    )
else:
    report("FAIL", "docref check: in a git work tree it reads tracked and untracked files")
    print("          git is not on PATH; this machine's environment says it should be")


def _dr_unreadable_dir_case():
    import contextlib
    import io

    title = "docref check: a directory the walk cannot list is named UNREADABLE and forces exit 1"
    d = make_fixture({"src/a.c": "int x;\n"})
    real_walk = docref_mod._walk_names

    def failing_walk(root):
        return [], [("src", "denied on purpose")]

    buf = io.StringIO()
    try:
        docref_mod._walk_names = failing_walk
        try:
            with contextlib.redirect_stdout(buf):
                rc = docref_mod.main(["check", "--root", d])
        finally:
            docref_mod._walk_names = real_walk
        out = buf.getvalue()
        if rc == 1 and "UNREADABLE" in out and "denied on purpose" in out:
            report("PASS", title)
        else:
            report("FAIL", title)
            print(f"          exit {rc}, expected 1; stdout: {out[:400]!r}")
    except Exception as e:
        report("FAIL", title)
        print(f"          raised {type(e).__name__}: {e}")
    finally:
        docref_mod._walk_names = real_walk
        shutil.rmtree(d, ignore_errors=True)


if DR_MOD_OK:
    _dr_unreadable_dir_case()

DR_STALE = {"docs/systems/new.md": DR_DOC, "src/a.c": "int x;\n// doc-ref a3f9 docs/old.md\n"}


def _dr_file_has(rel, needle, absent=None):
    def _check(d):
        with open(os.path.join(d, rel), "rb") as f:
            data = f.read().decode("utf-8")
        if needle not in data:
            return False, f"{rel} does not contain {needle!r}"
        if absent is not None and absent in data:
            return False, f"{rel} still contains {absent!r}"
        return True, ""
    return _check


docref_case(
    "docref fix: without --write it reports what it would change and writes nothing",
    DR_STALE, ["fix"], 0,
    expect_in=["would rewrite", "docs/old.md -> docs/systems/new.md", "nothing written"],
    after=_dr_file_has("src/a.c", "docs/old.md"),
)


def _dr_fixed_then_clean(d):
    ok, detail = _dr_file_has("src/a.c", "docs/systems/new.md", absent="docs/old.md")(d)
    if not ok:
        return ok, detail
    rc, out, err = docref_run(d, "check")
    return (rc == 0, f"check still exits {rc} after fix: {out[-200:]!r}")


docref_case(
    "docref fix --write: repairs a stale path by id, and check is clean afterwards",
    DR_STALE, ["fix", "--write"], 0,
    expect_in=["rewrote", "docs/old.md -> docs/systems/new.md"],
    after=_dr_fixed_then_clean,
)


def _dr_write_crlf(d):
    with open(os.path.join(d, "src", "a.c"), "wb") as f:
        f.write(b"int x;\r\n// doc-ref a3f9 docs/old.md\r\n")


def _dr_crlf_kept(d):
    with open(os.path.join(d, "src", "a.c"), "rb") as f:
        got = f.read()
    want = b"int x;\r\n// doc-ref a3f9 docs/systems/new.md\r\n"
    return got == want, f"bytes after fix were {got!r}, wanted {want!r}"


docref_case(
    "docref fix --write: keeps CRLF line endings byte-for-byte",
    DR_STALE, ["fix", "--write"], 0,
    after=_dr_crlf_kept, setup=_dr_write_crlf,
)

docref_case(
    "docref fix --write: keeps a trailing comment closer on the same line",
    {"docs/systems/new.md": DR_DOC, "src/a.c": "/* doc-ref a3f9 docs/old.md */\n"},
    ["fix", "--write"], 0,
    after=_dr_file_has("src/a.c", "/* doc-ref a3f9 docs/systems/new.md */"),
)

docref_case(
    "docref fix --write: leaves a dangling pointer alone and says it is unresolved",
    {
        "docs/systems/new.md": DR_DOC,
        "src/a.c": "// doc-ref a3f9 docs/old.md\n// doc-ref beef docs/gone.md\n",
    },
    ["fix", "--write"], 0,
    expect_in=["still unresolved: 1 dangling"],
    after=_dr_file_has("src/a.c", "doc-ref beef docs/gone.md"),
)

docref_case(
    "docref fix --write: refuses to touch pointers to a duplicated id",
    {"docs/a.md": DR_DOC, "docs/b.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/zzz.md\n"},
    ["fix", "--write"], 0,
    expect_in=["still unresolved", "1 ambiguous"],
    after=_dr_file_has("src/a.c", "docs/zzz.md"),
)

docref_case(
    "docref fix: with nothing stale it says so and exits 0",
    {"docs/systems/physics.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/systems/physics.md\n"},
    ["fix", "--write"], 0,
    expect_in=["0 pointer(s)"],
)

_d = make_fixture({"docs/a.md": DR_DOC, "src/a.c": "// doc-ref beef docs/none.md\n"})
try:
    _rc, _out, _err = docref_run(_d, "new")
    _id = _out.strip()
    if _rc == 0 and re.fullmatch(r"[0-9a-f]{4}", _id) and _id not in ("a3f9", "beef"):
        report("PASS", "docref new: prints a 4-hex id not used by any marker or pointer")
        print(f"          printed {_id}")
    else:
        report("FAIL", "docref new: prints a 4-hex id not used by any marker or pointer")
        print(f"          rc={_rc} stdout={_out[:80]!r} stderr={_err[:120]!r}")
finally:
    shutil.rmtree(_d, ignore_errors=True)


class _SeqRng:
    def __init__(self, seq):
        self.seq = list(seq)

    def randrange(self, n):
        return self.seq.pop(0)


if DR_MOD_OK:
    if docref_mod.new_id({"a3f9"}, _SeqRng([0xA3F9, 0xA3F9, 0x0001])) == "0001":
        report("PASS", "docref new_id: skips ids that are already used and returns the first free one")
    else:
        report("FAIL", "docref new_id: skips ids that are already used and returns the first free one")

    try:
        docref_mod.new_id({"%04x" % i for i in range(0x10000)})
        report("FAIL", "docref new_id: says so when all 65536 ids are used")
    except RuntimeError as _e:
        report("PASS", "docref new_id: says so when all 65536 ids are used")
        print(f"          {_e}")

# An unreadable file must be named and must fail the check - not be skipped quietly.
import contextlib
import io

if DR_MOD_OK:
    _d = make_fixture({"docs/a.md": DR_DOC, "src/a.c": "// doc-ref a3f9 docs/a.md\n"})
    _orig_read = docref_mod._read_bytes


    def _boom(path):
        if path.endswith("a.c"):
            raise PermissionError("denied on purpose")
        return _orig_read(path)


    docref_mod._read_bytes = _boom
    _buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(_buf):
            _rc = docref_mod.main(["check", "--root", _d])
    finally:
        docref_mod._read_bytes = _orig_read
        shutil.rmtree(_d, ignore_errors=True)
    if _rc == 1 and "src/a.c  UNREADABLE  denied on purpose" in _buf.getvalue():
        report("PASS", "docref check: an unreadable file is named and fails the check")
    else:
        report("FAIL", "docref check: an unreadable file is named and fails the check")
        print(f"          rc={_rc} stdout={_buf.getvalue()[:300]!r}")

_proc = subprocess.run(
    [sys.executable, DOCREF, "check", "--root", os.path.join(ROOT, "no", "such", "dir")],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
if _proc.returncode == 2 and b"is not a directory" in _proc.stderr:
    report("PASS", "docref check: a --root that is not a directory exits 2 and says why on stderr")
else:
    report("FAIL", "docref check: a --root that is not a directory exits 2 and says why on stderr")
    print(f"          rc={_proc.returncode} stderr={_proc.stderr[:160]!r}")


def _dr_run_patched(argv, files, fail_for):
    """Run docref_mod.main with _read_bytes patched; return (rc, stdout, stderr, dir)."""
    d = make_fixture(files)
    orig = docref_mod._read_bytes
    seen = {}

    def patched(path):
        seen[path] = seen.get(path, 0) + 1
        if fail_for(path, seen[path]):
            raise PermissionError("denied on purpose")
        return orig(path)

    out, err = io.StringIO(), io.StringIO()
    docref_mod._read_bytes = patched
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = docref_mod.main(argv(d))
    finally:
        docref_mod._read_bytes = orig
    return rc, out.getvalue(), err.getvalue(), d


_DR_TWO = {
    "docs/systems/new.md": DR_DOC,
    "src/a.c": "// doc-ref a3f9 docs/old.md\n",
    "src/b.c": "// doc-ref a3f9 docs/old.md\n",
}

if DR_MOD_OK:
    _title = "docref fix: an unreadable file is named, the readable one is still repaired, exit stays 0"
    _rc, _o, _e, _d = _dr_run_patched(
        lambda d: ["fix", "--write", "--root", d], _DR_TWO, lambda p, n: p.endswith("b.c"))
    try:
        _ok, _detail = _dr_file_has("src/a.c", "docs/systems/new.md", absent="docs/old.md")(_d)
        if _rc == 0 and "src/b.c  UNREADABLE  denied on purpose" in _o and "still unresolved" in _o and _ok:
            report("PASS", _title)
        else:
            report("FAIL", _title)
            print(f"          rc={_rc} {_detail} stdout={_o[:300]!r}")
    finally:
        shutil.rmtree(_d, ignore_errors=True)

    _title = "docref new: an unreadable file is warned about on stderr and stdout stays one bare id"
    _rc, _o, _e, _d = _dr_run_patched(
        lambda d: ["new", "--root", d], _DR_TWO, lambda p, n: p.endswith("b.c"))
    shutil.rmtree(_d, ignore_errors=True)
    if _rc == 0 and re.fullmatch(r"[0-9a-f]{4}\n", _o) and "src/b.c" in _e and "collide" in _e:
        report("PASS", _title)
    else:
        report("FAIL", _title)
        print(f"          rc={_rc} stdout={_o[:80]!r} stderr={_e[:200]!r}")

    _title = "docref fix: a file that fails on re-read is named, others are processed, exit 2, count reported"
    _rc, _o, _e, _d = _dr_run_patched(
        lambda d: ["fix", "--write", "--root", d], _DR_TWO, lambda p, n: p.endswith("a.c") and n >= 2)
    try:
        _ok, _detail = _dr_file_has("src/b.c", "docs/systems/new.md", absent="docs/old.md")(_d)
        if _rc == 2 and "src/a.c  UNREADABLE  denied on purpose" in _o and "1 file(s) failed" in _o and _ok:
            report("PASS", _title)
        else:
            report("FAIL", _title)
            print(f"          rc={_rc} {_detail} stdout={_o[:300]!r}")
    finally:
        shutil.rmtree(_d, ignore_errors=True)

# --- docref.py final-review fixes: fences, atomic write, punctuation, --exclude, git entries ---
FENCE4 = "`" * 4
TILDES = "~" * 3

docref_case(
    "docref check: a four-backtick block holding an unclosed three-backtick line ends at the four, so the marker after it is seen",
    {
        "docs/a.md": FENCE4 + "\n" + FENCE + "md\nx\n" + FENCE4 + "\n<!-- ref:a3f9 -->\n",
        "src/a.c": "// doc-ref a3f9 docs/a.md\n",
    },
    ["check"], 0,
    expect_in=["1 ok, 0 stale, 0 dangling", "docref: OK"],
)

docref_case(
    "docref check: a marker inside a four-backtick block, after a nested three-backtick line, is not a marker",
    {
        "docs/a.md": FENCE4 + "\n" + FENCE + "\n<!-- ref:a3f9 -->\n" + FENCE4 + "\n",
        "src/a.c": "// doc-ref a3f9 docs/a.md\n",
    },
    ["check"], 1,
    expect_in=["src/a.c:1  DANGLING"],
)

docref_case(
    "docref check: a tilde fence is not closed by a backtick fence line inside it",
    {
        "docs/a.md": (TILDES + "\n" + FENCE + "\n<!-- ref:a3f9 -->\n" + FENCE + "\n" + TILDES
                      + "\n<!-- ref:b4b4 -->\n"),
        "src/a.c": "// doc-ref a3f9 docs/a.md\n// doc-ref b4b4 docs/a.md\n",
    },
    ["check"], 1,
    expect_in=["src/a.c:1  DANGLING", "1 ok, 0 stale, 1 dangling"],
    expect_out=["src/a.c:2"],
)

docref_case(
    "docref check: a fence indented four spaces is not a fence, so the marker after it is seen",
    {
        "docs/a.md": "    " + FENCE + "\n<!-- ref:a3f9 -->\n",
        "src/a.c": "// doc-ref a3f9 docs/a.md\n",
    },
    ["check"], 0,
    expect_in=["1 ok"],
)

docref_case(
    "docref check: a doc that ends inside a fence is MALFORMED on the opening fence line",
    {"docs/a.md": "Text\n" + FENCE + "\ncode\n"},
    ["check"], 1,
    expect_in=["docs/a.md:2  MALFORMED", "never closed"],
)

docref_case(
    "docref fix --write: leaves no temp file behind after a successful write",
    DR_STALE, ["fix", "--write"], 0,
    after=lambda d: (
        not any(n.endswith(".docref.tmp") for _r, _ds, fs in os.walk(d) for n in fs),
        "a *.docref.tmp file was left behind",
    ),
)

docref_case(
    "docref check: a pointer path followed by a sentence period is a valid pointer",
    {
        "docs/systems/physics.md": DR_DOC,
        "src/a.c": "// See doc-ref a3f9 docs/systems/physics.md.\n// (doc-ref a3f9 docs/systems/physics.md)\n",
    },
    ["check"], 0,
    expect_in=["2 ok, 0 stale, 0 dangling", "0 malformed"],
)

docref_case(
    "docref fix --write: keeps the sentence period it did not use",
    {"docs/systems/new.md": DR_DOC, "src/a.c": "// See doc-ref a3f9 docs/old.md.\n"},
    ["fix", "--write"], 0,
    after=_dr_file_has("src/a.c", "doc-ref a3f9 docs/systems/new.md.", absent="docs/old.md"),
)

docref_case(
    "docref check: --exclude that matches a file prints no note",
    {"src/bad.c": "// doc-ref beef docs/none.md\n"},
    ["check", "--exclude", "src/bad.c"], 0,
    expect_out=["matched no file"],
)

docref_case(
    "docref check: --exclude that matches nothing is noted and does not change the exit code",
    {"src/a.c": "int x;\n"},
    ["check", "--exclude", "nope/*.c"], 0,
    expect_in=["docref: note: --exclude 'nope/*.c' matched no file", "docref: OK"],
)

docref_case(
    "docref check: --exclude is case-sensitive on every OS",
    {"src/bad.c": "// doc-ref beef docs/none.md\n"},
    ["check", "--exclude", "SRC/BAD.C"], 1,
    expect_in=["src/bad.c:1  DANGLING", "--exclude 'SRC/BAD.C' matched no file"],
)


def _dr_git_deleted_setup(d):
    for args in (["init", "-q"], ["add", "-A"]):
        subprocess.run(["git", "-C", d] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    os.remove(os.path.join(d, "src", "gone.c"))


def _dr_git_nested_setup(d):
    subprocess.run(["git", "-C", d, "init", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    os.makedirs(os.path.join(d, "inner"))
    subprocess.run(["git", "-C", os.path.join(d, "inner"), "init", "-q"],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    with open(os.path.join(d, "inner", "f.c"), "w", encoding="utf-8") as f:
        f.write("int y;\n")


if shutil.which("git"):
    docref_case(
        "docref check: a file git lists but that is deleted is counted in a note, not silent",
        {"src/a.c": "int x;\n", "src/gone.c": "int z;\n"},
        ["check"], 0,
        expect_in=["1 path(s) listed by git are not readable files", "via git"],
        setup=_dr_git_deleted_setup,
    )
    docref_case(
        "docref check: a nested repo git lists as a directory is counted in a note, not silent",
        {"src/a.c": "int x;\n"},
        ["check"], 0,
        expect_in=["path(s) listed by git are not readable files"],
        setup=_dr_git_nested_setup,
    )


def _dr_write_utf16_doc(d):
    with open(os.path.join(d, "docs", "x.md"), "wb") as f:
        f.write("## T\n<!-- ref:a3f9 -->\n".encode("utf-16"))


docref_case(
    "docref check: an undecodable doc under docs/ is named UNDECODABLE and fails, not just counted",
    {"docs/y.md": "## T\n", "src/a.c": "// doc-ref a3f9 docs/x.md\n"},
    ["check"], 1,
    expect_in=["docs/x.md  UNDECODABLE  not valid UTF-8; its markers cannot be read"],
    setup=_dr_write_utf16_doc,
)

docref_case(
    "docref check: an undecodable non-doc file is still only counted as binary skipped",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["1 binary skipped"],
    expect_out=["UNDECODABLE"],
    setup=_dr_write_binary,
)

docref_case(
    "docref check: the fallback line says git did not list files, not that git is unavailable",
    {"src/a.c": "int x;\n"},
    ["check"], 0,
    expect_in=["via directory walk (git did not list files:"],
    expect_out=["git unavailable"],
)

# --- /house-rules:docref exists and runs the installed docref.py -------------------------------
DOCREF_CMD = os.path.join(HERE, "..", "commands", "docref.md")
drdrift = []
if not os.path.isfile(DOCREF_CMD):
    drdrift.append("commands/docref.md is missing")
else:
    _dr_cmd_text = read(DOCREF_CMD)
    for needle in ["docref.py", "${CLAUDE_PLUGIN_ROOT}", "$ARGUMENTS",
                   "the plugin root did not resolve", "fix --write"]:
        if needle not in _dr_cmd_text:
            drdrift.append(f"docref.md is missing {needle!r}")
    if re.search(r"\$CLAUDE_PLUGIN_ROOT", _dr_cmd_text):
        drdrift.append("docref.md uses bare $CLAUDE_PLUGIN_ROOT (must be braced)")
if not drdrift:
    report("PASS", "/house-rules:docref exists and runs the installed docref.py")
    print("          resolves via ${CLAUDE_PLUGIN_ROOT}, never a hand-built cache path")
else:
    report("FAIL", "/house-rules:docref exists and runs the installed docref.py")
    print(f"          {'; '.join(drdrift)}")

def _dr_failure_detail(rc, out, err):
    """FAIL detail for the live check: the finding lines themselves (everything that is not a
    'docref:' summary line, capped), then the verdict line, so the flagged file:line survives."""
    lines = out.splitlines()
    findings = chr(10).join(l for l in lines if not l.startswith("docref:"))[:1500]
    verdicts = [l for l in lines if l.startswith("docref:")]
    verdict = verdicts[-1] if verdicts else "(no docref: line)"
    return "\n".join([f"exit {rc}", findings, verdict, repr(err[:200])])


# --- the live check's failure output names the flagged line, not just a tail of the summary ----
_title = "docref live check: failure detail names the flagged file:line and the exit code"
_d = make_fixture({"src/a.c": "// doc-ref beef docs/none.md\n"})
try:
    _rc, _o, _e = docref_run(_d, "check")
    _detail = _dr_failure_detail(_rc, _o, _e)
    if _rc == 1 and "src/a.c:1  DANGLING" in _detail and "exit 1" in _detail:
        report("PASS", _title)
    else:
        report("FAIL", _title)
        print(f"          rc={_rc} detail={_detail[:300]!r}")
finally:
    shutil.rmtree(_d, ignore_errors=True)

# --- the repo's own docs and code pass docref check ----------------------------------------------
# verify.py and docref.py are excluded: they hold well-formed example pointers on purpose.
_dr_live = "docref check passes on this repo's own docs and code"
_absent = absent_repo_files("docs/6-decisions/Decisions.md", "docs/README.md")
if _absent:
    skip_repo_check(_dr_live, _absent)
else:
    _rc, _out, _err = docref_run(
        ROOT, "check",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/verify.py",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/checks/*.py",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/docref.py",
    )
    if _rc == 0:
        report("PASS", _dr_live)
        print("          " + [l for l in _out.splitlines() if "pointers found" in l][0])
    else:
        report("FAIL", _dr_live)
        print("          " + _dr_failure_detail(_rc, _out, _err).replace("\n", "\n          "))

# --- plain_docs_check.py: the plain-English doc copy checker -----------------------------------
# Design: docs/plans/2026-09-24-plain-docs-skill.md
PLAIN_CHECK = os.path.join(HERE, "plain_docs_check.py")

PD_HASH_RE = re.compile(r"@HASHOF:([\w./-]+)@")


def _pd_prepare(d):
    """git init the fixture, then resolve every @HASHOF:<relpath>@ token in every file to that
    file's real git blob hash, so header lines can reference a source's actual current hash
    without the test data hardcoding one."""
    subprocess.run(["git", "init", "-q"], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    for dirpath, _dirnames, filenames in os.walk(d):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in filenames:
            full = os.path.join(dirpath, name)
            with open(full, "r", encoding="utf-8") as f:
                text = f.read()
            if "@HASHOF:" not in text:
                continue

            def repl(m, d=d):
                target = os.path.join(d, m.group(1))
                proc = subprocess.run(
                    ["git", "hash-object", target], cwd=d,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                )
                return proc.stdout.decode("utf-8", "replace").strip()

            new_text = PD_HASH_RE.sub(repl, text)
            if new_text != text:
                with open(full, "w", encoding="utf-8") as f:
                    f.write(new_text)


def pd_run(root, *args):
    cmd = [sys.executable, PLAIN_CHECK, "--root", root] + list(args)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def pd_case(title, files, args=(), expect_rc=0, expect_in=(), expect_out=()):
    d = make_fixture(files)
    try:
        _pd_prepare(d)
        resolved_args = [a.replace("{ROOT}", d) if isinstance(a, str) else a for a in args]
        rc, out, err = pd_run(d, *resolved_args)
        problems = []
        if rc != expect_rc:
            problems.append(f"exit {rc}, expected {expect_rc}")
        for needle in expect_in:
            if needle not in out:
                problems.append(f"output is missing {needle!r}")
        for needle in expect_out:
            if needle in out:
                problems.append(f"output should not contain {needle!r}")
        if not problems:
            report("PASS", title)
            print("          " + (out.strip().splitlines() or ["(no output)"])[-1][:100])
        else:
            report("FAIL", title)
            for p in problems:
                print(f"          {p}")
            print(f"          stdout: {out[:500]!r} stderr: {err[:200]!r}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


PD_OK_HEADER = "<!-- plain copy of: docs/4-systems/x.md @ @HASHOF:docs/4-systems/x.md@ -->\n"
PD_SOURCE = (
    "# X\n\nA source doc with a decent number of words in it so the ratio math has room to work. "
    + " ".join(f"word{i}" for i in range(1, 300))
    + "\n"
)
PD_OK_BODY = (
    "\n# X, in plain English\n\n"
    "Full technical doc: [x.md](../../4-systems/x.md)\n\n"
    "**What it is.** A short, clean plain copy.\n\n"
    "**Why it matters.** Nothing breaks if this one is missing.\n\n"
    "**How it works.**\n\n1. Step one.\n\n"
    "**Risks and safeguards.**\n\n- **Nothing.** No known risk.\n\n"
    "**Related.**\n\n- **Nothing.** No related systems.\n\n"
    "**Left out**, see the full doc: nothing.\n"
)

CHECK_NO_PLUGIN_FILE = "plain_docs_check.py is missing"
if not os.path.isfile(PLAIN_CHECK):
    report("FAIL", CHECK_NO_PLUGIN_FILE)
    print(f"          expected {PLAIN_CHECK}; the plain-docs tests that run it are skipped")
else:
    pd_case(
        "plain_docs_check: a well-formed plain copy passes clean",
        {"docs/4-systems/x.md": PD_SOURCE, "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY},
        expect_rc=0,
        expect_in=["0 fail", "plain_docs_check: OK"],
    )

    pd_case(
        "plain_docs_check: no docs/plain/ folder is reported plainly and still exits 0",
        {"docs/4-systems/x.md": PD_SOURCE},
        expect_rc=0,
        expect_in=["no docs/plain/ folder", "nothing to check"],
    )

    pd_case(
        "plain_docs_check: an em dash fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "A short, clean plain copy.", "A short plain copy — written badly."
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "em dash or en dash"],
    )

    pd_case(
        "plain_docs_check: a banned word fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "A short, clean plain copy.", "A short plain copy, built from the payload."
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "banned word 'payload'"],
    )

    pd_case(
        "plain_docs_check: a code block fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY + "\n```\ncode here\n```\n",
        },
        expect_rc=1,
        expect_in=["FAIL", "fenced code block"],
    )

    pd_case(
        "plain_docs_check: a file path in prose fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "A short, clean plain copy.", "See scripts/hook.py for the real code."
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "a file path in prose"],
    )

    pd_case(
        "plain_docs_check: a file:line reference fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "A short, clean plain copy.", "See hook.py:71 for the real code."
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "file:line reference"],
    )

    pd_case(
        "plain_docs_check: a missing header fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_BODY.lstrip("\n"),
        },
        expect_rc=1,
        expect_in=["FAIL", "missing or malformed header"],
    )

    pd_case(
        "plain_docs_check: a missing full-doc link fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "Full technical doc: [x.md](../../4-systems/x.md)\n\n", ""
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "missing the 'Full technical doc:"],
    )

    pd_case(
        "plain_docs_check: a source file that no longer exists fails",
        {"docs/plain/4-systems/x.md": PD_OK_HEADER.replace("@HASHOF:docs/4-systems/x.md@", "0" * 40) + PD_OK_BODY},
        expect_rc=1,
        expect_in=["FAIL", "does not exist"],
    )

    pd_case(
        "plain_docs_check: a word count over a third of the source's fails",
        {
            "docs/4-systems/x.md": "# X\n\n" + " ".join(f"w{i}" for i in range(1, 13)) + "\n",
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY,
        },
        expect_rc=1,
        expect_in=["FAIL", "over a third of the source's"],
    )

    pd_case(
        "plain_docs_check: a word count over a quarter (but not a third) only warns",
        {
            # source has 183 words, plain body has 55 -> 30%, between a quarter and a third
            "docs/4-systems/x.md": "# X\n\n" + " ".join(f"w{i}" for i in range(1, 183)) + "\n",
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY,
        },
        expect_rc=0,
        expect_in=["WARN", "over a quarter of the source's", "plain_docs_check: OK"],
    )

    pd_case(
        "plain_docs_check: a broken relative link fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "- **Nothing.** No related systems.\n",
                "- **Missing.** [missing.md](../../4-systems/missing.md)\n",
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "broken relative link"],
    )

    pd_case(
        "plain_docs_check: a stale source blob hash warns, not fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER.replace("@HASHOF:docs/4-systems/x.md@", "f" * 40) + PD_OK_BODY,
        },
        expect_rc=0,
        expect_in=["WARN", "stale: source", "plain_docs_check: OK"],
    )

    pd_case(
        "plain_docs_check: a related link to a doc that already has a plain copy fails",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/4-systems/y.md": "# Y\n\nStub.\n",
            "docs/plain/4-systems/y.md": (
                "<!-- plain copy of: docs/4-systems/y.md @ @HASHOF:docs/4-systems/y.md@ -->\n\n"
                "# Y, in plain English\n\nFull technical doc: [y.md](../../4-systems/y.md)\n\n"
                "**What it is.** Stub.\n"
            ),
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "- **Nothing.** No related systems.\n",
                "- **Y.** The y system.\n  [y.md](../../4-systems/y.md)\n",
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "already has a plain copy", "link to the plain copy instead"],
    )

    pd_case(
        "plain_docs_check: an unupgraded '(no plain copy yet)' pointer fails once the plain copy exists",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/4-systems/y.md": "# Y\n\nStub.\n",
            "docs/plain/4-systems/y.md": (
                "<!-- plain copy of: docs/4-systems/y.md @ @HASHOF:docs/4-systems/y.md@ -->\n\n"
                "# Y, in plain English\n\nFull technical doc: [y.md](../../4-systems/y.md)\n\n"
                "**What it is.** Stub.\n"
            ),
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "- **Nothing.** No related systems.\n",
                "- **Y.** The y system.\n  [y.md](../../4-systems/y.md) *(no plain copy yet)*\n",
            ),
        },
        expect_rc=1,
        expect_in=["FAIL", "upgrade the pointer"],
    )

    pd_case(
        "plain_docs_check: '(no plain copy yet)' and '(needs a doc)' lines are listed as to-do items",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/4-systems/y.md": "# Y\n\nStub.\n",
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "- **Nothing.** No related systems.\n",
                "- **Y.** The y system.\n  [y.md](../../4-systems/y.md) *(no plain copy yet)*\n"
                "- **Z.** No doc yet.\n  Z *(needs a doc)*\n",
            ),
        },
        expect_rc=0,
        expect_in=[
            "to-do, plain copies not yet written",
            "docs/4-systems/y.md",
            "to-do, systems that need a technical doc first",
            "(needs a doc)",
        ],
    )

    QUEUE_SYSTEM_A = "# A\n\nStub source.\n"
    QUEUE_SYSTEM_B = "# B\n\nStub source, different content.\n"
    QUEUE_ROOT_README = "# Project\n\nStub root README.\n"
    QUEUE_STALE_HEADER = "<!-- plain copy of: docs/4-systems/a.md @ " + "f" * 40 + " -->\n\nStale.\n"
    QUEUE_CURRENT_BODY = "<!-- plain copy of: docs/4-systems/a.md @ @HASHOF:docs/4-systems/a.md@ -->\n\nCurrent.\n"

    pd_case(
        "plain_docs_check --queue: ordering, MISSING/STALE/CURRENT, and the summary line",
        {
            "docs/4-systems/README.md": "# Systems\n\nIndex, not a system.\n",
            "docs/4-systems/b.md": QUEUE_SYSTEM_B,  # MISSING, but alphabetically after a.md
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,  # CURRENT
            "docs/plain/4-systems/a.md": QUEUE_CURRENT_BODY,
            "docs/1-landing/README.md": QUEUE_ROOT_README,  # MISSING
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=[
            "docs/4-systems/a.md  CURRENT  docs/plain/4-systems/a.md",
            "docs/4-systems/b.md  MISSING  docs/plain/4-systems/b.md",
            "docs/1-landing/README.md  MISSING  docs/plain/1-landing/README.md",
            "plain_docs_check: queue: 2 missing, 0 stale, 1 current, 0 deferred",
        ],
    )

    pd_case(
        "plain_docs_check --queue: a plain copy with a stale header is STALE, not CURRENT",
        {
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,
            "docs/plain/4-systems/a.md": QUEUE_STALE_HEADER,
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=[
            "docs/4-systems/a.md  STALE  docs/plain/4-systems/a.md",
            "plain_docs_check: queue: 0 missing, 1 stale, 0 current, 0 deferred",
        ],
    )

    pd_case(
        "plain_docs_check --queue: docs/4-systems/README.md is never queued, itself an index",
        {
            "docs/4-systems/README.md": "# Systems\n\nIndex, not a system.\n",
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=["docs/4-systems/a.md  MISSING"],
        expect_out=["docs/4-systems/README.md  MISSING", "docs/4-systems/README.md  CURRENT",
                    "docs/4-systems/README.md  STALE"],
    )

    pd_case(
        "plain_docs_check --queue: docs/architecture.md is shown as DEFERRED, never queued",
        {
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,
            "docs/architecture.md": "# Architecture\n\nStub.\n",
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=[
            "docs/architecture.md  DEFERRED  done only once the others have proven useful",
            "plain_docs_check: queue: 1 missing, 0 stale, 0 current, 1 deferred",
        ],
        expect_out=["docs/architecture.md  MISSING", "docs/architecture.md  CURRENT"],
    )

    pd_case(
        "plain_docs_check --queue: excluded folders are named, not queued",
        {
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,
            "docs/6-decisions/Decisions.md": "# Decisions\n\nStub.\n",
            "docs/plans/2026-01-01-x.md": "# X\n\nStub.\n",
            "docs/archive/old.md": "# Old\n\nStub.\n",
            "docs/sessions/2026-01-01.md": "# Session\n\nStub.\n",
            "docs/generated/gen.md": "# Gen\n\nStub.\n",
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=[
            "EXCLUDED: docs/6-decisions/Decisions.md, docs/plans/, docs/archive/, docs/sessions/, "
            "docs/generated/, docs/plain/, docs/4-systems/README.md",
        ],
        expect_out=["docs/6-decisions/Decisions.md  MISSING", "docs/plans/2026-01-01-x.md",
                    "docs/archive/old.md", "docs/sessions/2026-01-01.md", "docs/generated/gen.md"],
    )

    pd_case(
        "plain_docs_check --queue: an unlisted docs/*.md is named in the EXCLUDED summary",
        {
            "docs/4-systems/a.md": QUEUE_SYSTEM_A,
            "docs/some-other-note.md": "# Note\n\nStub.\n",
        },
        args=("--queue",),
        expect_rc=0,
        expect_in=[
            "any other docs/*.md not in the eligible list: docs/some-other-note.md",
        ],
    )

    pd_case(
        "plain_docs_check --queue: honours --root",
        {
            "sub/docs/4-systems/a.md": QUEUE_SYSTEM_A,
        },
        args=("--queue", "--root", "{ROOT}/sub"),
        expect_rc=0,
        expect_in=["docs/4-systems/a.md  MISSING  docs/plain/4-systems/a.md"],
    )

    pd_case(
        "plain_docs_check --queue: no docs/ folder is reported plainly and still exits 0",
        {"README.md": "# Not docs\n"},
        args=("--queue",),
        expect_rc=0,
        expect_in=["no docs/ folder", "nothing to queue"],
    )

    pd_case(
        "plain_docs_check: a single file path argument checks only that file",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/4-systems/y.md": "# Y\n\nStub.\n",
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY,
            "docs/plain/4-systems/y.md": "not a header at all\n",
        },
        args=("{ROOT}/docs/plain/4-systems/x.md",),
        expect_rc=0,
        expect_in=["checked 1 file(s)", "plain_docs_check: OK"],
        expect_out=["docs/plain/4-systems/y.md"],
    )

    def pd_closed_reader_case(title, files, args, expect_rc):
        """Run the checker with stdout already closed at the reading end, the way `| head` leaves
        it, and check the exit code is still the real result with no internal error."""
        d = make_fixture(files)
        read_end, write_end = os.pipe()
        os.close(read_end)
        try:
            _pd_prepare(d)
            proc = subprocess.run(
                [sys.executable, PLAIN_CHECK, "--root", d] + list(args),
                stdout=write_end, stderr=subprocess.PIPE,
            )
            err = proc.stderr.decode("utf-8", "replace")
            if proc.returncode == expect_rc and "internal error" not in err:
                report("PASS", title)
            else:
                report("FAIL", title)
                print(f"          exit {proc.returncode}, expected {expect_rc}; stderr: {err[:300]!r}")
        finally:
            os.close(write_end)
            shutil.rmtree(d, ignore_errors=True)

    pd_closed_reader_case(
        "plain_docs_check --queue: a reader that stops early (| head) is not an internal error",
        {"docs/4-systems/x.md": PD_SOURCE, "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY},
        args=("--queue",),
        expect_rc=0,
    )

    pd_closed_reader_case(
        "plain_docs_check: a reader that stops early still gets the real failing exit code",
        {
            "docs/4-systems/x.md": PD_SOURCE,
            "docs/plain/4-systems/x.md": PD_OK_HEADER + PD_OK_BODY.replace(
                "A short, clean plain copy.", "A short plain copy, built from the payload."
            ),
        },
        args=(),
        expect_rc=1,
    )


finish()
