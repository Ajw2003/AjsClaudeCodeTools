#!/usr/bin/env python3
"""verify.py — proves agent-router's hooks do what they claim.

    python claude-agent-router/plugins/agent-router/scripts/verify.py

Same shape as house-rules'/prompt-workshop's verify.py: numbered PASS/FAIL, computed check
count, exit 0 on all-pass. STDLIB ONLY.

Covers the two fail-open/fail-loud contracts (inject fails loud, route never blocks), the
hooks.json/EVENTS parity check, that each shipped agent declares the model rules/agent-router.md
promises it does, that route's suggestions read that declaration live rather than restating it,
and a representative set of tier classifications. Like prompt-workshop's suite, this is v0.1
coverage for a v0.1 heuristic — see docs/offshoots-plan.md for what's still open.
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
RULES_FILE = os.path.join(HERE, "..", "rules", "agent-router.md")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
AGENTS_DIR = os.path.join(HERE, "..", "agents")

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


def prompt_payload(text):
    return json.dumps({"session_id": "verify", "prompt": text})


def declared_model(agent_name):
    body = read(os.path.join(AGENTS_DIR, agent_name + ".md"))
    m = re.search(r"^model:\s*(\S+)\s*$", body, re.MULTILINE)
    return m.group(1) if m else ""


print()
print("agent-router hooks - verification (Python)")
print("==============================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"run.sh:      {RUN}")
print()

spec = importlib.util.spec_from_file_location("agent_router_hook", HOOK)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# --- 1: inject loads the routing methodology ---------------------------------------------------
rc, out, err = run_hook("inject", "")
try:
    decoded = json.loads(out)
    ctx = decoded.get("hookSpecificOutput", {}).get("additionalContext", "")
    ok = (
        rc == 0
        and decoded.get("hookSpecificOutput", {}).get("hookEventName") == "SessionStart"
        and "Agent Router" in ctx
        and "cannot switch the model the current session is running on" in ctx.lower()
    )
except Exception:
    ok = False
report(
    "PASS" if ok else "FAIL",
    "inject emits the methodology as SessionStart context, honesty clause included",
)

# --- 2: inject fails loud (not closed) when the rules file is unreadable -----------------------
_isolated = tempfile.mkdtemp(prefix="agent-router-verify-")
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

# --- 3: each shipped agent declares the model the rules doc promises ----------------------------
EXPECTED_MODELS = {"scribe": "haiku", "operative": "sonnet", "architect": "opus"}
for agent, expected in EXPECTED_MODELS.items():
    actual = declared_model(agent)
    ok = actual == expected
    report("PASS" if ok else "FAIL", f"agents/{agent}.md declares model: {expected} (found: {actual!r})")

# --- 4: route classifies representative prompts into the right tier -----------------------------
ROUTE_CASES = [
    ("scribe", "update the README with the new install steps"),
    ("scribe", "fix the typo in the changelog"),
    ("scribe", "write a better docstring for parse_config"),
    ("architect", "design the architecture for the new payments service"),
    ("architect", "should we migrate to a new database"),
    ("architect", "make a plan to prioritize the Q3 roadmap"),
    ("operative", "implement the rate limiter in middleware.py"),
    ("operative", "investigate why the login test is flaky"),
    ("operative", "fix the null pointer in the parser"),
    (None, "what time is it"),
    ("operative", "why is the login test flaky?"),
    ("operative", "how does the auth flow work across these services?"),
    ("operative", "what's causing the memory leak in the worker process?"),
    ("architect", "why should we consolidate these two services?"),
    (None, "thanks, that looks right"),
    (None, "please delegate this to @agent-router:operative"),
    (None, "what does this variable represent in the code we just looked at?"),
]

for expect_tier, text in ROUTE_CASES:
    rc, out, err = run_hook("route", prompt_payload(text))
    fired = bool(out.strip())
    if expect_tier is None:
        ok = rc == 0 and not fired
        report("PASS" if ok else "FAIL", f'route stays silent on: "{text[:55]}"')
        continue
    tier_ok = False
    if fired:
        try:
            decoded = json.loads(out)
            ctx = decoded["hookSpecificOutput"]["additionalContext"]
            tier_ok = ("@agent-router:%s" % expect_tier) in ctx
        except Exception:
            tier_ok = False
    ok = rc == 0 and fired and tier_ok
    report("PASS" if ok else "FAIL", f'route suggests @agent-router:{expect_tier} on: "{text[:55]}"')
    if ok:
        expected_model = EXPECTED_MODELS[expect_tier]
        model_ok = ("declared model: %s" % expected_model) in ctx
        report(
            "PASS" if model_ok else "FAIL",
            f"  -> suggestion names {expect_tier}'s declared model ({expected_model})",
        )

# --- 5: route never fails on a malformed or empty payload ---------------------------------------
for label, payload in [
    ("empty stdin", ""),
    ("not json", "not json at all {{"),
    ("json with no prompt field", json.dumps({"session_id": "verify"})),
]:
    rc, out, err = run_hook("route", payload)
    ok = rc == 0
    report("PASS" if ok else "FAIL", f"route never exits non-zero on: {label}")

# --- 6: run.sh's no-interpreter fallback matches each event's failure contract ------------------
_env_no_py = dict(os.environ)
_env_no_py["PATH"] = ""
_env_no_py.pop("AGENT_ROUTER_PYTHON", None)

rc, out, err = run_shell([RUN, "inject"], "", env=_env_no_py)
try:
    decoded = json.loads(out)
    ok = rc == 0 and "NOT loaded" in decoded.get("systemMessage", "")
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "run.sh inject: no interpreter -> systemMessage, exit 0")

rc, out, err = run_shell([RUN, "route"], "", env=_env_no_py)
ok = rc == 0 and out.strip() == ""
report("PASS" if ok else "FAIL", "run.sh route: no interpreter -> silent, exit 0 (never blocks the prompt)")

# --- 7: hooks.json registers exactly the events hook.py dispatches -------------------------------
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

print()
print("=" * 46)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
sys.exit(0)
