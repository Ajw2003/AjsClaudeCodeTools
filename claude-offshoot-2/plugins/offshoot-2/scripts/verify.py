#!/usr/bin/env python3
"""verify.py — proves offshoot-2's placeholder hook does what a placeholder should: says it's a
placeholder, on every path, and never fails.

    python claude-offshoot-2/plugins/offshoot-2/scripts/verify.py

Same shape as house-rules'/prompt-workshop's verify.py: numbered PASS/FAIL, computed check
count, exit 0 on all-pass. Grows alongside hook.py — when this plugin gets a real purpose, add
cases the same way prompt-workshop's suite was grown from this one.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
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


print()
print("offshoot-2 hooks - verification (Python)")
print("============================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"run.sh:      {RUN}")
print()

spec = importlib.util.spec_from_file_location("offshoot_2_hook", HOOK)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# --- 1: inject states the placeholder status, never silently ----------------------------------
rc, out, err = run_hook("inject", "")
try:
    decoded = json.loads(out)
    ok = rc == 0 and "placeholder" in decoded.get("systemMessage", "").lower()
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "inject states the placeholder status via systemMessage, exit 0")

# --- 2: inject never fails regardless of stdin content -----------------------------------------
for label, payload in [("empty stdin", ""), ("garbage stdin", "not json {{")]:
    rc, out, err = run_hook("inject", payload)
    ok = rc == 0 and out.strip() != ""
    report("PASS" if ok else "FAIL", f"inject still reports its status on: {label}")

# --- 3: run.sh's no-interpreter fallback matches inject's fail-loud contract -------------------
_env_no_py = dict(os.environ)
_env_no_py["PATH"] = ""
_env_no_py.pop("OFFSHOOT2_PYTHON", None)

rc, out, err = run_shell([RUN, "inject"], "", env=_env_no_py)
try:
    decoded = json.loads(out)
    ok = rc == 0 and "systemMessage" in decoded
except Exception:
    ok = False
report("PASS" if ok else "FAIL", "run.sh inject: no interpreter -> systemMessage, exit 0")

# --- 4: hooks.json registers exactly the events hook.py dispatches -----------------------------
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
print("=" * 44)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
sys.exit(0)
