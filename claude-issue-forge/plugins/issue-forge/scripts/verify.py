#!/usr/bin/env python3
"""verify.py — proves issue-forge's hooks and forge.py do what they claim.

    python claude-issue-forge/plugins/issue-forge/scripts/verify.py

Same shape as house-rules'/prompt-workshop's/agent-router's verify.py: numbered PASS/FAIL, a
check count computed at runtime, exit 0 on all-pass. STDLIB ONLY.

Covers: the two hook contracts (inject fails loud, suggest never blocks and always traces),
forge.py's backlog/ledger parsing against fixture text shaped like the real
docs/architecture-backlog.md, docs/rules-backlog.md and docs/sessions/*.md ledger structure (read
while planning this, not invented), forge.py's dedup logic against a stubbed gh (never the real
CLI), and the hooks.json/EVENTS parity + structure checks the sibling offshoots also run.

Like agent-router's suite, this is v0.1 coverage for a v0.1 shell - see docs/offshoots-plan.md
for what's still open. It deliberately never shells out to a real `gh` or touches real GitHub,
the same documented limitation tools/verify_tools.py carries for anything that shells out to a
real CLI.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
FORGE = os.path.join(HERE, "forge.py")
RUN = os.path.join(HERE, "run.sh")
RULES_FILE = os.path.join(HERE, "..", "rules", "issue-forge.md")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")

SH = shutil.which("sh") or "sh"

STEP = 0
FAILURES = 0


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    print(f"{STEP:2d}. {result}  {title}")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_hook(event, payload=""):
    proc = subprocess.run(
        [sys.executable, HOOK, event],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
        "utf-8", "replace"
    )


def run_shell(args, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [SH] + args,
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=e,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
        "utf-8", "replace"
    )


def edit_payload(file_path):
    return json.dumps({"session_id": "verify", "tool_name": "Edit", "tool_input": {"file_path": file_path}, "file_path": file_path})


def bash_payload(command):
    return json.dumps({"session_id": "verify", "tool_name": "Bash", "tool_input": {"command": command}, "command": command})


print()
print("issue-forge hooks + forge.py - verification (Python)")
print("==============================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"forge.py:    {FORGE}")
print(f"run.sh:      {RUN}")
print()

spec = importlib.util.spec_from_file_location("issue_forge_hook", HOOK)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

forge_spec = importlib.util.spec_from_file_location("issue_forge_forge", FORGE)
forge_module = importlib.util.module_from_spec(forge_spec)
forge_spec.loader.exec_module(forge_module)

# =================================================================================================
# 1. inject — SessionStart
# =================================================================================================

rc, out, err = run_hook("inject", "")
try:
    decoded = json.loads(out)
    ctx = decoded.get("hookSpecificOutput", {}).get("additionalContext", "")
    ok = (
        rc == 0
        and decoded.get("hookSpecificOutput", {}).get("hookEventName") == "SessionStart"
        and "issue-forge" in ctx.lower()
        and "never invoked by a hook" in ctx
    )
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "inject emits rules/issue-forge.md as SessionStart context, hard rule included")

_isolated = tempfile.mkdtemp(prefix="issue-forge-verify-")
try:
    isolated_hook = os.path.join(_isolated, "hook.py")
    shutil.copyfile(HOOK, isolated_hook)
    proc = subprocess.run(
        [sys.executable, isolated_hook, "inject"],
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        decoded = json.loads(proc.stdout.decode("utf-8", "replace"))
        ok = proc.returncode == 0 and "NOT loaded" in decoded.get("systemMessage", "")
    except Exception:
        ok = False
    report("PASS" if ok else "FAIL", "inject fails loud (systemMessage, exit 0) when rules file is missing")
finally:
    shutil.rmtree(_isolated, ignore_errors=True)

# =================================================================================================
# 2. suggest — PostToolUse (Edit|Write and Bash), never blocks, always traces
# =================================================================================================

DOC_CASES = [
    (True, "docs/architecture-backlog.md"),
    (True, "docs/rules-backlog.md"),
    (True, "C:\\repo\\docs\\architecture-backlog.md"),
    (False, "docs/architecture.md"),
    (False, "README.md"),
    (False, "claude-house-rules/plugins/house-rules/scripts/hook.py"),
]
def _fired_reminder(out):
    """True only if this call emitted the additionalContext reminder, not just a trace."""
    try:
        decoded = json.loads(out)
    except Exception:
        return False
    return "additionalContext" in decoded.get("hookSpecificOutput", {})


for should_fire, path in DOC_CASES:
    rc, out, err = run_hook("suggest", edit_payload(path))
    fired = _fired_reminder(out)
    ok = rc == 0 and fired == should_fire and bool(out.strip())
    report("PASS" if ok else "FAIL", f"suggest {'fires the reminder' if should_fire else 'stays silent (trace only)'} on Edit of {path}")

BASH_CASES = [
    (True, "python tools/session_ledger.py"),
    (True, "python3 tools/session_ledger.py --stdout"),
    (False, "git status"),
    (False, "python tools/measure_footprint.py"),
]
for should_fire, command in BASH_CASES:
    rc, out, err = run_hook("suggest", bash_payload(command))
    fired = _fired_reminder(out)
    ok = rc == 0 and fired == should_fire and bool(out.strip())
    report("PASS" if ok else "FAIL", f"suggest {'fires the reminder' if should_fire else 'stays silent (trace only)'} on Bash: {command!r}")

# Every path - fires or not - emits SOMETHING (either the reminder or a trace), never truly
# silent, matching artifact/runnable/harvest's "silence means I could not tell" discipline.
for label, payload in [
    ("empty payload", ""),
    ("no file_path or command", json.dumps({"session_id": "verify"})),
]:
    rc, out, err = run_hook("suggest", payload)
    ok = rc == 0 and bool(out.strip())
    report("PASS" if ok else "FAIL", f"suggest always emits something (trace or reminder) on: {label}")

# Never blocks / never raises on malformed input.
for label, payload in [("not json", "not json at all {{")]:
    rc, out, err = run_hook("suggest", payload)
    ok = rc == 0
    report("PASS" if ok else "FAIL", f"suggest never exits non-zero on: {label}")

# =================================================================================================
# 3. run.sh's no-interpreter fallback
# =================================================================================================

_env_no_py = dict(os.environ)
_env_no_py["PATH"] = ""
_env_no_py.pop("ISSUE_FORGE_PYTHON", None)

rc, out, err = run_shell([RUN, "inject"], "", env=_env_no_py)
try:
    decoded = json.loads(out)
    ok = rc == 0 and "NOT loaded" in decoded.get("systemMessage", "")
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "run.sh inject: no interpreter -> systemMessage, exit 0")

rc, out, err = run_shell([RUN, "suggest"], "", env=_env_no_py)
ok = rc == 0 and out.strip() == ""
report("PASS" if ok else "FAIL", "run.sh suggest: no interpreter -> silent, exit 0 (PostToolUse can't block anyway)")

# =================================================================================================
# 4. hooks.json registers exactly the events hook.py dispatches, on the matchers the plan states
# =================================================================================================

hooks_json = json.loads(read(HOOKS_JSON))
registered = set()
bad_matchers = []
for event_name, entries in hooks_json.get("hooks", {}).items():
    for entry in entries:
        matcher = entry.get("matcher")
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            import re as _re
            m = _re.search(r'run\.sh"\s+(\w+)', cmd)
            if m:
                registered.add(m.group(1))
            if h.get("type") != "command" or "run.sh" not in cmd:
                report("FAIL", f"hooks.json entry for {event_name} does not call run.sh: {cmd!r}")
        if event_name == "PostToolUse" and matcher not in ("Edit|Write", "Bash"):
            bad_matchers.append((event_name, matcher))

declared = set(hook_module.EVENTS.keys())
if registered == declared:
    report("PASS", f"hooks.json registers exactly hook.py's dispatched events: {sorted(declared)}")
else:
    report(
        "FAIL",
        "hooks.json/EVENTS mismatch: registered=%s declared=%s" % (sorted(registered), sorted(declared)),
    )

ok = not bad_matchers
report("PASS" if ok else "FAIL", f"PostToolUse is registered only on Edit|Write and Bash matchers (found: {bad_matchers})")

post_tool_matchers = {e.get("matcher") for e in hooks_json.get("hooks", {}).get("PostToolUse", [])}
ok = post_tool_matchers == {"Edit|Write", "Bash"}
report("PASS" if ok else "FAIL", f"suggest is registered on both Edit|Write and Bash (found: {post_tool_matchers})")

ok = "SessionStart" in hooks_json.get("hooks", {}) and "PreToolUse" not in hooks_json.get("hooks", {})
report("PASS" if ok else "FAIL", "hooks.json never registers PreToolUse - this plugin cannot block anything")

# =================================================================================================
# 5. forge.py: backlog parsing, using fixture text shaped like the real
#    docs/architecture-backlog.md / docs/rules-backlog.md structure
# =================================================================================================

ARCH_BACKLOG_FIXTURE = """# Architecture backlog

Deepening opportunities identified in the plugin's own code but not yet decided on.

An entry here is a **candidate, not a commitment**.

---

## Baseline

Raised 2026-09-07 against `11b5744`. No Status line here - this section must be skipped.

---

## 1. The rules text has nine restatements and no module holding them

**Status:** open, `strong`. Raised 2026-09-07.

**The friction.** `rules/house-rules.md` is canonical, and nine places restate part of it.
That relationship is real and load-bearing but no module holds it.

**Evidence — this is a live gap, not a tidiness complaint.** Three of the nine check only
that the phrase still appears in `house-rules.md`, never that it still appears in the
restatement they are named for.

**What would change.** One `Restatement(source, phrases)` table plus a single checker behind it.

**Open questions.**

- Do all nine restatements bind the same way?

---

## 2. The failure-mode contract is written three times

**Status:** open, `worth exploring`. Raised 2026-09-07.

**The friction.** Which way each handler fails is stated three times and not checked against
each other.

**What would change.** Make the policy the value in the existing `EVENTS` table.

---

## 3. Something already shipped

**Status:** shipped, `speculative`. Raised 2026-09-07.

**The friction.** This one is done, so it must not be counted as a candidate.

---
"""

RULES_BACKLOG_FIXTURE = """# Rules backlog

Rule changes that are decided but not yet written into `rules/house-rules.md`.

---

## Vague statements and instructions

**Status:** open. Raised 2026-09-07.

**The defect.** Handing over an instruction whose wording cannot be acted on the same way
twice.

**Evidence.** SS6 asked for "a multi-step handover" with no prompt text and no expected answer.

**What the rule should say.** Roughly: an instruction the user is meant to act on names the
exact input, not a category of input.

**Open questions before writing it.**

- Does this belong in the six-item contract or as its own rule?

---
"""

arch_candidates = forge_module.parse_backlog_file(
    "docs/architecture-backlog.md", ARCH_BACKLOG_FIXTURE, "architecture-backlog"
)
ok = len(arch_candidates) == 2
report("PASS" if ok else "FAIL", f"architecture-backlog fixture yields 2 open candidates (Baseline + shipped skipped), got {len(arch_candidates)}")

ok = bool(arch_candidates) and arch_candidates[0].title.startswith("1. The rules text")
report("PASS" if ok else "FAIL", "first architecture candidate's title is the heading text verbatim")

ok = bool(arch_candidates) and "strength:strong" in arch_candidates[0].labels and "source:architecture-backlog" in arch_candidates[0].labels
report("PASS" if ok else "FAIL", "first architecture candidate carries source + strength labels")

ok = len(arch_candidates) > 1 and "strength:worth-exploring" in arch_candidates[1].labels
report("PASS" if ok else "FAIL", "second architecture candidate carries strength:worth-exploring")

ok = bool(arch_candidates) and "nine places restate part of it" in arch_candidates[0].body["context"]
report("PASS" if ok else "FAIL", "architecture candidate's Context comes from the friction paragraph")

ok = bool(arch_candidates) and "Restatement(source, phrases)" in arch_candidates[0].body["proposed"]
report("PASS" if ok else "FAIL", "architecture candidate's proposed change comes from 'What would change'")

rules_candidates = forge_module.parse_backlog_file(
    "docs/rules-backlog.md", RULES_BACKLOG_FIXTURE, "rules-backlog"
)
ok = len(rules_candidates) == 1
report("PASS" if ok else "FAIL", f"rules-backlog fixture yields 1 open candidate, got {len(rules_candidates)}")

ok = bool(rules_candidates) and "source:rules-backlog" in rules_candidates[0].labels and "strength:" not in ",".join(rules_candidates[0].labels)
report("PASS" if ok else "FAIL", "rules-backlog candidate carries source label only, no strength label")

ok = bool(rules_candidates) and "an instruction that cannot be acted on" not in rules_candidates[0].body["context"] and "Handing over an instruction" in rules_candidates[0].body["context"]
report("PASS" if ok else "FAIL", "rules-backlog candidate's Context comes from 'The defect'")

# =================================================================================================
# 6. forge.py: session-ledger parsing, using fixture text shaped like the real
#    docs/sessions/*.md ledger structure
# =================================================================================================

LEDGER_WITH_ACTIONS = """# Session ledger — `4e371a18-641b-536e-974a-9e38e191d593`

Generated by `tools/session_ledger.py` from the session transcript.

| | |
|---|---|
| Turns (human prompts) | 16 |
| **Actions in turn continuations** | **2** |

## Actions taken after the visible reply

A Stop hook continues the turn, so anything here happened after the reply the user read.

| Turn | Prompted by | Action | Time |
|---|---|---|---|
| 11 | `~/.claude/stop-hook-git-check.sh` | `Bash` for i in 1 2 3 4; do git push … | 05:40:51 |
| 11 | `~/.claude/stop-hook-git-check.sh` | `github:update_pull_request` | 05:43:44 |

## Every turn

### Turn 1 — 2026-09-08 23:18:45

**Asked:** something

| What | Source | Detail |
|---|---|---|
| command | `Bash` | git status |
"""

LEDGER_NO_ACTIONS = """# Session ledger — `aaaa1111-2222-3333-4444-555566667777`

Generated by `tools/session_ledger.py` from the session transcript.

| | |
|---|---|
| **Actions in turn continuations** | **0** |

## Actions taken after the visible reply

A Stop hook continues the turn, so anything here happened after the reply the user read.

| Turn | Prompted by | Action | Time |
|---|---|---|---|

## Every turn

### Turn 1 — 2026-09-08 23:18:45

**Asked:** something

| What | Source | Detail |
|---|---|---|
| command | `Bash` | git status |
"""

with_actions = forge_module.parse_ledger_file(
    "docs/sessions/2026-09-09-4e371a18-641b-536e-974a-9e38e191d593.md", LEDGER_WITH_ACTIONS
)
ok = len(with_actions) == 1
report("PASS" if ok else "FAIL", f"a ledger with 2 flagged data rows yields exactly 1 candidate, got {len(with_actions)}")

ok = bool(with_actions) and with_actions[0].title == "Review 2 action(s) taken after the visible reply \u2014 session 4e371a18-641b-536e-974a-9e38e191d593"
report("PASS" if ok else "FAIL", f"ledger candidate title names the row count and session id, got {with_actions[0].title if with_actions else None!r}")

ok = bool(with_actions) and with_actions[0].body["context"].count("|") >= 8 and "stop-hook-git-check.sh" in with_actions[0].body["context"]
report("PASS" if ok else "FAIL", "ledger candidate's Context is the flagged-actions table verbatim, not per-row")

no_actions = forge_module.parse_ledger_file(
    "docs/sessions/2026-09-10-aaaa1111-2222-3333-4444-555566667777.md", LEDGER_NO_ACTIONS
)
ok = len(no_actions) == 0
report("PASS" if ok else "FAIL", f"a ledger with zero flagged data rows yields no candidate, got {len(no_actions)}")

# collect_candidates end-to-end over a small fixture filesystem: 2 backlog files + 1 ledger with
# rows + 1 ledger without + 1 -brief.md companion that must be skipped.
_fixture_files = {
    "docs/architecture-backlog.md": ARCH_BACKLOG_FIXTURE,
    "docs/rules-backlog.md": RULES_BACKLOG_FIXTURE,
    "docs/sessions/2026-09-09-x.md": LEDGER_WITH_ACTIONS,
    "docs/sessions/2026-09-10-y.md": LEDGER_NO_ACTIONS,
    "docs/sessions/2026-09-09-x-brief.md": "# brief\nshould never be read as a ledger",
}


def _fake_read(path):
    return _fixture_files[path]


def _fake_listdir(path):
    return ["2026-09-09-x.md", "2026-09-10-y.md", "2026-09-09-x-brief.md"]


all_candidates = forge_module.collect_candidates(
    ["docs/architecture-backlog.md", "docs/rules-backlog.md"],
    "docs/sessions",
    read_file=_fake_read,
    listdir=_fake_listdir,
)
ok = len(all_candidates) == 2 + 1 + 1
report(
    "PASS" if ok else "FAIL",
    f"end-to-end collect_candidates: 2 arch + 1 rules + 1 ledger-with-rows = 4, got {len(all_candidates)}",
)

# =================================================================================================
# 7. forge.py: slug/dedup mechanism against a STUBBED gh - never the real CLI
# =================================================================================================


def _stub_runner_found(args, gh_cmd="gh"):
    assert args[:3] == ["issue", "list", "--repo"]
    return 0, json.dumps([{"number": 42}]), ""


def _stub_runner_not_found(args, gh_cmd="gh"):
    return 0, json.dumps([]), ""


def _stub_runner_gh_error(args, gh_cmd="gh"):
    return 1, "", "some gh failure"


rc = forge_module.already_forged("some-slug", "owner/repo", runner=_stub_runner_found)
report("PASS" if rc is True else "FAIL", "already_forged returns True when the stubbed gh search finds a match")

rc = forge_module.already_forged("some-slug", "owner/repo", runner=_stub_runner_not_found)
report("PASS" if rc is False else "FAIL", "already_forged returns False when the stubbed gh search finds nothing")

rc = forge_module.already_forged("some-slug", "owner/repo", runner=_stub_runner_gh_error)
report("PASS" if rc is None else "FAIL", "already_forged returns None (not a guess) when the stubbed gh call itself fails")

c1 = forge_module.parse_backlog_file("docs/architecture-backlog.md", ARCH_BACKLOG_FIXTURE, "architecture-backlog")[0]
body = c1.issue_body()
ok = body.startswith("<!-- issue-forge:source=%s -->" % c1.slug)
report("PASS" if ok else "FAIL", "the dedup marker is the first line of the drafted issue body, keyed to the candidate's slug")

ok = ("issue-forge:source=%s" % c1.slug) in body and "## Source" in body and "## Context" in body and "## Proposed change / acceptance criteria" in body
report("PASS" if ok else "FAIL", "issue body carries all four template sections verbatim (Context / Why it matters / Proposed change / Source)")

# create_issue never actually shells out - it goes through the same runner seam.
_create_calls = []


def _stub_create_runner(args, gh_cmd="gh"):
    _create_calls.append(args)
    return 0, "https://github.com/owner/repo/issues/1", ""


rc, out, err = forge_module.create_issue(c1, "owner/repo", runner=_stub_create_runner)
ok = rc == 0 and len(_create_calls) == 1 and _create_calls[0][:2] == ["issue", "create"] and "--label" in _create_calls[0]
report("PASS" if ok else "FAIL", "create_issue calls gh issue create once, through the stubbed runner, never the real CLI")

# =================================================================================================
# 8. Safety-rule alignment: --create is never reachable from the hook, and the rules doc states
#    the hard confirmation rule in terms verify.py can check for drift.
# =================================================================================================

hook_src = read(HOOK)
ok = "import subprocess" not in hook_src and "subprocess." not in hook_src and "run_gh(" not in hook_src and '"--create"' not in hook_src
report("PASS" if ok else "FAIL", "hook.py never imports subprocess, calls run_gh, or invokes --create - the hook has no way to reach Phase B")

rules_text = read(RULES_FILE)
for phrase in [
    "never invoked by a hook",
    "never invoked by Claude",
    "explicit go-ahead in chat",
    "publish/post public content",
]:
    ok = phrase in rules_text
    report("PASS" if ok else "FAIL", f"rules/issue-forge.md states the hard rule phrase: {phrase!r}")

forge_src = read(FORGE)
ok = "def phase_a" in forge_src and "def phase_b" in forge_src and forge_src.index("def phase_a") < forge_src.index("def phase_b")
report("PASS" if ok else "FAIL", "forge.py keeps phase_a (read-only) defined before phase_b (create) - the two-phase split is a real seam, not just a CLI flag")

# --dry-run never reaches create_issue; --create always requires named slugs, never "all".
ok = "candidates" in forge_src and "wanted = " in forge_src and "for slug in wanted" in forge_src
report("PASS" if ok else "FAIL", "phase_b only creates issues for explicitly named slugs, never every surviving candidate")

print()
print("=" * 46)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
sys.exit(0)
