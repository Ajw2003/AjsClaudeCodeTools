#!/usr/bin/env python3
"""verify.py — proves prompt-workshop's hooks do what they claim.

Run it yourself, any time, on any machine:

    python claude-prompt-workshop/plugins/prompt-workshop/scripts/verify.py

Same shape as house-rules' verify.py, deliberately: numbered PASS/FAIL lines, a computed check
count, exit 0 on all-pass / 1 on any failure. STDLIB ONLY.

This is a v0.1 suite for a v0.1 shell — it covers the two fail-open/fail-loud contracts that
must never regress (inject fails loud, workshop never blocks), the hooks.json/EVENTS parity
check, and a handful of representative trigger/non-trigger prompts. It does not attempt the
scale of house-rules' guard suite; the heuristics it tests are explicitly approximate (see
rules/prompt-workshop.md and docs/offshoots-plan.md at the repo root).
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
RULES_FILE = os.path.join(HERE, "..", "rules", "prompt-workshop.md")
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


def run_hook(event, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [sys.executable, HOOK, event],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=e,
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


def prompt_payload(text):
    return json.dumps({"session_id": "verify", "prompt": text})


print()
print("prompt-workshop hooks - verification (Python)")
print("===============================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"run.sh:      {RUN}")
print()

# --- module import, for the EVENTS/hooks.json parity check -----------------------------------
spec = importlib.util.spec_from_file_location("prompt_workshop_hook", HOOK)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# --- 1: inject loads the methodology file -----------------------------------------------------
rc, out, err = run_hook("inject", "")
try:
    decoded = json.loads(out)
    ok = (
        rc == 0
        and decoded.get("hookSpecificOutput", {}).get("hookEventName") == "SessionStart"
        and "Prompt Workshop" in decoded.get("hookSpecificOutput", {}).get("additionalContext", "")
    )
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "inject emits the methodology file as SessionStart context")

# --- 2: inject fails loud (not closed) when the rules file is unreadable ---------------------
# Copy just hook.py into an isolated temp dir with no sibling rules/ directory, so
# _RULES_PATH resolves to a path that does not exist.
_isolated = tempfile.mkdtemp(prefix="prompt-workshop-verify-")
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

# --- 3: workshop fires on a short, bare task prompt -------------------------------------------
WORKSHOP_CASES = [
    ("fire", "fix the bug"),
    ("fire", "add authentication"),
    ("fire", "refactor this module"),
    ("fire", "make the dashboard better"),
    (
        "silent",
        "Add a rate limiter to the API, only touching middleware/, must pass the existing "
        "tests, and check with me before merging.",
    ),
    ("silent", "What does the calculateTotal function do?"),
    ("silent", "git status"),
    ("silent", "Thanks, that looks right."),
]

for expect, text in WORKSHOP_CASES:
    rc, out, err = run_hook("workshop", prompt_payload(text))
    fired = bool(out.strip())
    ok = rc == 0 and (fired == (expect == "fire"))
    label = "fires" if expect == "fire" else "stays silent"
    report("PASS" if ok else "FAIL", f'workshop {label} on: "{text[:60]}"')
    if fired:
        try:
            decoded = json.loads(out)
            ctx = decoded["hookSpecificOutput"]["additionalContext"]
            ok2 = "prompt-workshop" in ctx and "AskUserQuestion" in ctx
        except Exception:
            ok2 = False
        report("PASS" if ok2 else "FAIL", f'  -> fired output names the workshop flow: "{text[:40]}"')

# --- 4: workshop never fails on a malformed or empty payload -----------------------------------
for label, payload in [
    ("empty stdin", ""),
    ("not json", "not json at all {{"),
    ("json with no prompt field", json.dumps({"session_id": "verify"})),
    ("prompt field is not a string in a way that still parses", json.dumps({"prompt": ""})),
]:
    rc, out, err = run_hook("workshop", payload)
    ok = rc == 0
    report("PASS" if ok else "FAIL", f"workshop never exits non-zero on: {label}")

# --- 5: run.sh's no-interpreter fallback matches each event's failure contract ------------------
_env_no_py = dict(os.environ)
_env_no_py["PATH"] = ""
_env_no_py.pop("PROMPT_WORKSHOP_PYTHON", None)

rc, out, err = run_shell([RUN, "inject"], "", env=_env_no_py)
try:
    decoded = json.loads(out)
    ok = rc == 0 and "NOT loaded" in decoded.get("systemMessage", "")
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "run.sh inject: no interpreter -> systemMessage, exit 0")

rc, out, err = run_shell([RUN, "workshop"], "", env=_env_no_py)
ok = rc == 0 and out.strip() == ""
report("PASS" if ok else "FAIL", "run.sh workshop: no interpreter -> silent, exit 0 (never blocks the prompt)")

# --- 6: hooks.json registers exactly the events hook.py dispatches -----------------------------
hooks_json = json.loads(read(HOOKS_JSON))
registered = set()
for event_name, entries in hooks_json.get("hooks", {}).items():
    for entry in entries:
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            m = re.search(r'run\.sh"\s+(\w+)', cmd)
            if m:
                registered.add(m.group(1))
            if h.get("type") != "command" or "run.sh" not in cmd:
                report("FAIL", f"hooks.json entry for {event_name} does not call run.sh: {cmd!r}")

declared = set(hook_module.EVENTS.keys())
if registered == declared:
    report("PASS", f"hooks.json registers exactly hook.py's dispatched events: {sorted(declared)}")
else:
    report(
        "FAIL",
        "hooks.json/EVENTS mismatch: registered=%s declared=%s" % (sorted(registered), sorted(declared)),
    )

# --- 7: rules/prompt-workshop.md exists and covers the four dimensions -------------------------
rules_text = read(RULES_FILE)
required_terms = ["Goal", "Constraints", "Success criteria", "Loops & gating"]
missing = [t for t in required_terms if t not in rules_text]
report(
    "PASS" if not missing else "FAIL",
    "rules/prompt-workshop.md names all four dimensions" + ("" if not missing else f" (missing: {missing})"),
)

print()
print("=" * 47)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
sys.exit(0)
