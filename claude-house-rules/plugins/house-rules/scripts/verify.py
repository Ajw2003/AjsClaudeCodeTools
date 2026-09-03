#!/usr/bin/env python3
"""verify.py — proves hook.py (and run.sh's interpreter fallback) behave as claimed.

Run it yourself, any time, on any machine:

    python claude-house-rules/plugins/house-rules/scripts/verify.py

STDLIB ONLY — the same constraint hook.py itself is built on.

This is the Step 2 suite: it covers only the files the Python port adds (hook.py, run.sh),
not the full plugin. verify.sh (the shell suite) still covers the pre-existing scripts until
Step 3 retires them and this suite is promoted to the full one.

The check count is never hardcoded here or anywhere referencing it — it is computed at
runtime, the same discipline verify.sh follows.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
SH = r"C:\Program Files\Git\bin\sh.exe" if os.path.exists(
    r"C:\Program Files\Git\bin\sh.exe"
) else "sh"

STEP = 0
FAILURES = 0


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    print(f"{STEP:2d}. {result}  {title}")


def run_hook(event, payload="", env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
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


def payload_for(cmd):
    return json.dumps(
        {"session_id": "verify", "tool_name": "Bash", "tool_input": {"command": cmd}}
    )


print()
print("house-rules hooks (Python port) - verification")
print("================================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"run.sh:      {RUN}")
print()

# --- guard cases: 28 commands, expect | rule-title | command ------------------------------
GUARD_CASES = [
    ("pass", None, "git status"),
    ("pass", None, "git log --oneline -n 20"),
    ("pass", None, "git diff HEAD~1"),
    ("pass", None, "npm test"),
    ("pass", None, "ls -la src"),
    ("pass", None, r"Get-ChildItem C:\Users"),
    ("pass", None, "npm run build && npm test"),
    ("ask", "Never commit without asking", 'git commit -m "wip"'),
    ("pass", None, "git add -A"),
    ("ask", "Never commit without asking", "git push origin main"),
    ("ask", "Never commit without asking", "git push --force-with-lease"),
    ("pass", None, "git checkout -b feature/x"),
    ("pass", None, "git switch main"),
    ("pass", None, "git branch -d old-feature"),
    ("pass", None, "git tag v1.2.0"),
    ("ask", "Never commit without asking", "git reset --hard origin/main"),
    (
        "ask",
        "Never hide work in a background window or a silent process",
        'Start-Process powershell -WindowStyle Hidden -ArgumentList "-File build.ps1"',
    ),
    (
        "ask",
        "Never hide work in a background window or a silent process",
        "npm run dev > dev.log 2>&1 &",
    ),
    (
        "ask",
        "Never hide work in a background window or a silent process",
        "nohup ./long-task.sh",
    ),
    (
        "ask",
        "Never hide work in a background window or a silent process",
        "Start-Job -ScriptBlock { ./build.ps1 }",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "rm -rf node_modules",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "Remove-Item -Recurse -Force ./dist",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "taskkill /IM node.exe /F",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "git checkout -- src/app.js",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "git restore src/app.js",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "git stash drop",
    ),
    (
        "ask",
        "Never take a destructive action without checking first",
        "git stash clear",
    ),
    (
        "ask",
        "Never commit without asking",
        'echo "starting" && git commit -m "wip"',
    ),
]

print("Guard cases feed one shell command each and check the decision:")
print('  "ask"  = a permission prompt naming the rule.')
print('  "pass" = the command runs with no extra prompt.')
print()

for expect, rule, cmd in GUARD_CASES:
    code, out, err = run_hook("guard", payload_for(cmd))
    if not out.strip():
        got = "pass"
    elif '"permissionDecision":"ask"' in out:
        got = "ask"
    else:
        got = "malformed"
    result = "PASS" if got == expect else "FAIL"
    cited = ""
    if rule:
        if rule in out:
            cited = "; rule cited correctly"
        else:
            cited = f"; RULE NOT CITED (wanted: {rule})"
            result = "FAIL"
    report(result, cmd)
    print(f"          expected {expect}, got {got}{cited}")

print()

# --- fail-closed: guard that hits an internal error must BLOCK, not shrug ------------------
# hook.py has no external dependency to go missing (no grep to be absent) - the equivalent
# failure mode is an unhandled exception inside the handler, caught by main()'s last-resort
# net. Simulated here by making stdin unreadable from inside the interpreter.
crash_snippet = (
    "import sys, hook\n"
    "def boom():\n"
    "    raise OSError('simulated stdin failure')\n"
    "hook.read_payload = boom\n"
    "sys.exit(hook.main(['hook.py', 'guard']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet],
    cwd=HERE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
code, out, err = proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
    "utf-8", "replace"
)
if code == 2 and err.strip() and not out.strip():
    report("PASS", "guard that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          said: {err.strip().splitlines()[0]}")
else:
    report("FAIL", "guard that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          exit code was {code}; stdout={out!r} stderr={err!r}")

# --- the guard matches the command field, not the whole payload ----------------------------
desc_payload = json.dumps(
    {
        "session_id": "verify",
        "tool_name": "Bash",
        "tool_input": {
            "command": "npm test",
            "description": "check for uncommitted changes before we commit and push",
        },
    }
)
code, out, err = run_hook("guard", desc_payload)
if not out.strip():
    report("PASS", "a harmless command with a git-mentioning description does not prompt")
    print("          matched the command field only, not the description")
else:
    report("FAIL", "a harmless command with a git-mentioning description does not prompt")
    print(f"          got: {out}")

# --- the fallback tier: no command field must never mean "wave it through" -----------------
nocmd_payload = json.dumps(
    {"session_id": "verify", "tool_name": "PowerShell", "tool_input": {"script": "git commit -m wip"}}
)
code, out, err = run_hook("guard", nocmd_payload)
if '"permissionDecision":"ask"' in out and "Never commit without asking" in out:
    report(
        "PASS",
        "a payload with no command field still gets checked (whole-payload fallback)",
    )
    print("          fell back to the old behaviour rather than passing it unchecked")
else:
    report(
        "FAIL",
        "a payload with no command field still gets checked (whole-payload fallback)",
    )
    print(f"          got: {out}")

print()

# --- the missing-interpreter fallback, exercised through run.sh directly -------------------
print("run.sh interpreter-fallback checks (PATH broken -> no candidate probes):")


def run_shell(args, payload="", env=None):
    e = dict(os.environ)
    if env is not None:
        e = env
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


code, out, err = run_shell([RUN, "guard"], payload_for("git commit -m x"), env={"PATH": ""})
if code == 2 and err.strip() and not out.strip():
    report("PASS", "run.sh with no working interpreter blocks guard (exit 2, stderr, no stdout)")
    print(f"          said: {err.strip().splitlines()[0]}")
else:
    report("FAIL", "run.sh with no working interpreter blocks guard (exit 2, stderr, no stdout)")
    print(f"          exit={code} stdout={out!r} stderr={err!r}")

code, out, err = run_shell([RUN, "inject"], "", env={"PATH": ""})
if code == 0 and "systemMessage" in out and "NOT loaded" in out:
    report("PASS", "run.sh with no working interpreter fails loud on inject (systemMessage, exit 0)")
    print(f"          said: {out.strip()}")
else:
    report("FAIL", "run.sh with no working interpreter fails loud on inject (systemMessage, exit 0)")
    print(f"          exit={code} stdout={out!r}")

code, out, err = run_shell([RUN, "scope"], "", env={"PATH": ""})
if code == 0 and not out.strip():
    report("PASS", "run.sh with no working interpreter is silent and exits 0 on every other event")
    print("          UserPromptSubmit/PostToolUse/Stop must never fail closed")
else:
    report("FAIL", "run.sh with no working interpreter is silent and exits 0 on every other event")
    print(f"          exit={code} stdout={out!r}")

code, out, err = run_shell(
    [RUN, "scope"], "", env={"PATH": os.environ.get("PATH", ""), "HOUSE_RULES_PYTHON": sys.executable}
)
if code == 0 and '"hookEventName":"UserPromptSubmit"' in out:
    report("PASS", "HOUSE_RULES_PYTHON override is probed and used when set")
    print(f"          used {sys.executable} via the override, not PATH resolution")
else:
    report("FAIL", "HOUSE_RULES_PYTHON override is probed and used when set")
    print(f"          exit={code} stdout={out!r}")

print()
print("-" * 32)
if FAILURES == 0:
    print(f"RESULT: PASS - all {STEP} checks passed.")
else:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed. See the FAIL lines above.")
print()

sys.exit(0 if FAILURES == 0 else 1)
