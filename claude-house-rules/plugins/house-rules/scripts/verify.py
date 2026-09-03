#!/usr/bin/env python3
"""verify.py — proves the house-rules hooks actually do what they claim.

Run it yourself, any time, on any machine:

    python claude-house-rules/plugins/house-rules/scripts/verify.py

It feeds real hook payloads to hook.py's handlers and prints a numbered PASS/FAIL line for
each, then a final verdict. Exit code 0 = all passed, 1 = something failed. Nothing is
hidden: every case tested is printed alongside its result.

STDLIB ONLY. No third-party imports — the same constraint hook.py is built on.

The check count is never hardcoded anywhere that references it (here or in any doc) — it is
computed at runtime, so it cannot drift out from under an added case.
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RULES_FILE = os.path.join(HERE, "..", "rules", "house-rules.md")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
AGENT = os.path.join(HERE, "..", "agents", "executor.md")

SH = (
    r"C:\Program Files\Git\bin\sh.exe"
    if os.path.exists(r"C:\Program Files\Git\bin\sh.exe")
    else "sh"
)

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


def payload_for(cmd):
    return json.dumps(
        {"session_id": "verify", "tool_name": "Bash", "tool_input": {"command": cmd}}
    )


print()
print("house-rules hooks - verification (Python)")
print("===========================================")
print(f"Interpreter: {sys.executable}")
print(f"hook.py:     {HOOK}")
print(f"run.sh:      {RUN}")
print()
print("The guard cases feed one shell command each to the guard and check the decision:")
print('  "ask"  = Claude Code will show you a permission prompt naming the rule.')
print('  "pass" = the command runs with no extra prompt.')
print("Later checks prove the hooks cannot fail silently, that the guard matches the")
print("command field rather than the whole payload, and that the scope, artifact and")
print("runnable reminders, the machine profile, and the rules-vs-docs drift checks hold.")
print()

# --- guard cases: 28 commands ---------------------------------------------------------------
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
    ("ask", "Never hide work in a background window or a silent process", "nohup ./long-task.sh"),
    (
        "ask",
        "Never hide work in a background window or a silent process",
        "Start-Job -ScriptBlock { ./build.ps1 }",
    ),
    ("ask", "Never take a destructive action without checking first", "rm -rf node_modules"),
    (
        "ask",
        "Never take a destructive action without checking first",
        "Remove-Item -Recurse -Force ./dist",
    ),
    ("ask", "Never take a destructive action without checking first", "taskkill /IM node.exe /F"),
    (
        "ask",
        "Never take a destructive action without checking first",
        "git checkout -- src/app.js",
    ),
    ("ask", "Never take a destructive action without checking first", "git restore src/app.js"),
    ("ask", "Never take a destructive action without checking first", "git stash drop"),
    ("ask", "Never take a destructive action without checking first", "git stash clear"),
    ("ask", "Never commit without asking", 'echo "starting" && git commit -m "wip"'),
]

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

# --- fail-closed: an internal error in guard must BLOCK, not shrug --------------------------
crash_snippet = (
    "import sys, hook\n"
    "def boom():\n"
    "    raise OSError('simulated stdin failure')\n"
    "hook.read_payload = boom\n"
    "sys.exit(hook.main(['hook.py', 'guard']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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

# --- the guard matches the command field, not the whole payload -----------------------------
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

# --- the fallback tier: no command field must never mean "wave it through" ------------------
nocmd_payload = json.dumps(
    {"session_id": "verify", "tool_name": "PowerShell", "tool_input": {"script": "git commit -m wip"}}
)
code, out, err = run_hook("guard", nocmd_payload)
if '"permissionDecision":"ask"' in out and "Never commit without asking" in out:
    report("PASS", "a payload with no command field still gets checked (whole-payload fallback)")
    print("          fell back to the old behaviour rather than passing it unchecked")
else:
    report("FAIL", "a payload with no command field still gets checked (whole-payload fallback)")
    print(f"          got: {out}")

# --- the rules actually reach the session ----------------------------------------------------
code, out, err = run_hook("inject", "")
missing = []
for h in [
    "The machine is fixed",
    "Match response depth to the task",
    "Build only what was asked",
    "Read the docs first, then check them against the code",
    "Build for a human working alone",
    "hands are for decisions, not labour",
    "Deliver a whole workflow, not a starting point",
    "Never hand over a command I have not run",
    "Every artifact lives in the project directory",
    "Never hide work in a background window or a silent process",
    "Never commit without asking",
    "Never take a destructive action without checking first",
]:
    if h not in out:
        missing.append(h)
if not missing:
    report("PASS", "SessionStart injects every rule heading into context")
    print(f"          {len(out)} characters injected")
else:
    report("FAIL", "SessionStart injects every rule heading into context")
    print(f"          missing: {'; '.join(missing)}")

# --- inject fail-loud: an internal error must still say something ---------------------------
crash_snippet2 = (
    "import sys, hook\n"
    "orig = hook._read_text\n"
    "def boom(path):\n"
    "    if 'house-rules.md' in path:\n"
    "        raise OSError('simulated read failure')\n"
    "    return orig(path)\n"
    "hook._read_text = boom\n"
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

# --- the scope reminder reaches every prompt --------------------------------------------------
def check_scope(title, empty_path):
    env = dict(os.environ)
    if empty_path:
        env["PATH"] = ""
    code, out, err = run_hook("scope", "", env=env)
    bad = []
    if '"hookEventName":"UserPromptSubmit"' not in out:
        bad.append("wrong or missing hookEventName")
    if "response depth" not in out:
        bad.append("response-depth line missing")
    if "only what was asked" not in out:
        bad.append("scope line missing")
    if "machine you are on" not in out:
        bad.append("environment line missing")
    if not bad:
        report("PASS", title)
        print(f"          {len(out)} characters of reminder injected")
    else:
        report("FAIL", title)
        print(f"          {'; '.join(bad)}")


check_scope("scope reminder is emitted ahead of every prompt", False)
check_scope("scope reminder still works with PATH empty (it depends on nothing)", True)

# --- the artifact reminder fires on documents written outside a project ---------------------
def art_case(expect, title, file_path, extra=""):
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    )
    if extra:
        obj = json.loads(payload)
        obj["tool_input"].update(extra)
        payload = json.dumps(obj)
    code, out, err = run_hook("artifact", payload)
    if "artifact custody" in out:
        got = "remind"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    report("PASS" if got == expect else "FAIL", title)
    print(f"          expected {expect}, got {got}")


art_case(
    "remind",
    "plan written to ~/.claude/plans is flagged for copying into the project",
    r"C:\Users\aj\.claude\plans\some-plan.md",
)
art_case(
    "remind",
    "document written to the session scratchpad is flagged",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\notes.md",
)
art_case(
    "silent",
    "document written inside the project is left alone",
    r"C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\docs\plans\x.md",
)
art_case(
    "silent",
    "file whose CONTENTS mention a temp path is left alone",
    r"C:\Users\aj\Desktop\proj\README.md",
    extra={"content": "put it in /tmp/ or scratchpad"},
)
art_case(
    "silent",
    "script in a temp directory is scratch work, not an artifact",
    r"C:\Users\aj\AppData\Local\Temp\build.sh",
)

# --- the reminder in hook.py's scope handler has not drifted from the rules document --------
rules_text = read(RULES_FILE)
drift = []
for phrase in [
    "response depth",
    "portability work",
    "only what was asked",
    "ask instead of assuming",
    "project directory",
    "hand over a command",
]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "scope reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "scope reminder still matches the rules document")
    print(f"          in scope reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- the rules have not been re-duplicated into CLAUDE.md ------------------------------------
root_claude = os.path.join(ROOT, "CLAUDE.md")
if not os.path.isfile(root_claude):
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

# --- the recorded machine profile actually reaches the session -------------------------------
code, out, err = run_hook("inject", "")
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
code, out, err = run_hook("inject", "", env=env)
if "NOT RECORDED YET" in out:
    report("PASS", "a missing machine profile becomes an instruction to discover it")
    print("          the session is told to go and find the facts, not to assume them")
else:
    report("FAIL", "a missing machine profile becomes an instruction to discover it")
    print("          the injection said nothing about the profile being absent")

# --- the run-what-you-wrote reminder ----------------------------------------------------------
def run_case(expect, title, file_path, extra=""):
    obj = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    if extra:
        obj["tool_input"].update(extra)
    code, out, err = run_hook("runnable", json.dumps(obj))
    if "whole workflows" in out:
        got = "remind"
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
run_case("silent", "a document is not a runnable file", r"C:\proj\notes.md")
run_case(
    "silent",
    "a script written to a temp directory is scratch work, not a delivery",
    r"C:\Users\aj\AppData\Local\Temp\build.sh",
)
run_case(
    "silent",
    "a script written to the session scratchpad is scratch work",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\run.py",
)
run_case(
    "silent",
    "a file whose CONTENTS mention a temp path is judged on where it actually is",
    r"C:\proj\notes.md",
    extra={"content": "write it to /tmp/build.sh first"},
)

# --- the reminder in hook.py's runnable handler has not drifted from the rules document -----
drift = []
for phrase in ["whole workflow", "starting point", "hand over a command"]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "runnable reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "runnable reminder still matches the rules document")
    print(f"          in runnable reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- the delegate reminder fires after ExitPlanMode -------------------------------------------
code, out, err = run_hook("delegate", "")
if '"hookEventName":"PostToolUse"' in out and "@house-rules:executor" in out:
    report("PASS", "delegate reminds Claude to hand the plan to the executor subagent")
    print("          names @house-rules:executor and carries the right hookEventName")
else:
    report("FAIL", "delegate reminds Claude to hand the plan to the executor subagent")
    print(f"          got: {out}")

# --- delegate is wired to ExitPlanMode, not just present in hook.py ---------------------------
hooks_json_text = read(HOOKS_JSON)
if '"matcher": "ExitPlanMode"' in hooks_json_text and 'run.sh\\" delegate' in hooks_json_text:
    report("PASS", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json wires ExitPlanMode to run.sh delegate")
else:
    report("FAIL", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json does not wire ExitPlanMode to run.sh delegate")

# --- the reminder in hook.py's delegate handler has not drifted from the rules document -----
drift = []
for phrase in ["@house-rules:executor", "plan is settled"]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "delegate reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "delegate reminder still matches the rules document")
    print(f"          in delegate reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- the command-handover check at Stop --------------------------------------------------------
def hand_case(expect, title, payload, mode=""):
    env = dict(os.environ)
    if mode == "toggle":
        env["HOUSE_RULES_HANDOVER"] = "off"
    elif mode == "nopath":
        env["PATH"] = ""
    code, out, err = run_hook("handover", payload, env=env)
    if '"decision":"block"' in out:
        got = "block"
    elif "systemMessage" in out:
        got = "offline"
    elif not out.strip():
        got = "silent"
    else:
        got = "malformed"
    if code != 0:
        got = f"{got} (exit {code})"
    report("PASS" if got == expect else "FAIL", title)
    print(f"          expected {expect}, got {got}")


hand_case(
    "block",
    "a turn about to end gets the handover checklist",
    json.dumps({"session_id": "verify", "hook_event_name": "Stop", "stop_hook_active": False}),
)
hand_case(
    "silent",
    "the retry after a block is allowed to finish - it cannot loop",
    json.dumps({"session_id": "verify", "hook_event_name": "Stop", "stop_hook_active": True}),
)
hand_case(
    "silent",
    "the toggle switches the check off without touching any file",
    json.dumps({"session_id": "verify", "hook_event_name": "Stop", "stop_hook_active": False}),
    mode="toggle",
)
hand_case("silent", "an empty payload is nothing to check, not a failed check", "")

# --- the checklist in hook.py's handover handler has not drifted from the rules document ----
drift = []
for phrase in ["fence label", "working directory", "UNTESTED", "Run button", "hand over a command"]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "handover checklist still matches the rules document")
    print("          every key phrase in the checklist appears in rules/house-rules.md")
else:
    report("FAIL", "handover checklist still matches the rules document")
    print(f"          in handover checklist but missing from house-rules.md: {'; '.join(drift)}")

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
if "house-rules-deliverable" in read(HOOK):
    gone.append("hook.py still writes deliverable state")
if not gone:
    report("PASS", "the stateful deliverable machinery and the old .sh hooks are gone")
    print("          every hook is stateless; hooks.json calls only run.sh")
else:
    report("FAIL", "the stateful deliverable machinery and the old .sh hooks are gone")
    print(f"          {'; '.join(gone)}")

# --- the delegation nudge fires when a plan is approved ----------------------------------------
def check_delegate(title, empty_path):
    env = dict(os.environ)
    if empty_path:
        env["PATH"] = ""
    code, out, err = run_hook("delegate", "", env=env)
    bad = []
    if '"hookEventName":"PostToolUse"' not in out:
        bad.append("wrong or missing hookEventName")
    if "@house-rules:executor" not in out:
        bad.append("it does not name the executor subagent")
    if "trivial" not in out:
        bad.append("the trivial-work exception is missing")
    if not bad:
        report("PASS", title)
        print(f"          {len(out)} characters of delegation nudge injected")
    else:
        report("FAIL", title)
        print(f"          {'; '.join(bad)}")


check_delegate("the delegation nudge is emitted when plan mode is exited", False)
check_delegate("the delegation nudge still works with PATH empty (it depends on nothing)", True)

# --- delegate is registered on ExitPlanMode, and nowhere else ---------------------------------
deldrift = []
if '"matcher": "ExitPlanMode"' not in hooks_json_text:
    deldrift.append("hooks.json has no ExitPlanMode matcher")
if "@house-rules:executor" not in rules_text:
    deldrift.append("house-rules.md no longer states the delegation rule")
if not deldrift:
    report("PASS", "delegate runs on ExitPlanMode and matches the rules document")
    print("          the nudge fires at the plan boundary and names the agent the rules name")
else:
    report("FAIL", "delegate runs on ExitPlanMode and matches the rules document")
    print(f"          {'; '.join(deldrift)}")

import re

# NOTE: the "exactly one delegation heading" check belongs to the F6 merge (rules-doc dedup),
# which is Step 4 of the port plan - added there, not here, since house-rules.md still has the
# pre-existing duplicate at this point in the port.

# --- the executor subagent is pinned to Sonnet ---------------------------------------------
agentdrift = []
if not os.path.isfile(AGENT):
    agentdrift.append("agents/executor.md is missing")
else:
    agent_text = read(AGENT)
    if not re.search(r"^model: sonnet$", agent_text, re.MULTILINE):
        agentdrift.append("executor.md does not pin model: sonnet")
    if not re.search(r"^name: executor$", agent_text, re.MULTILINE):
        agentdrift.append("executor.md has no name: executor")
    for dead in ["hooks", "mcpServers", "permissionMode"]:
        if re.search(rf"^{dead}:", agent_text, re.MULTILINE):
            agentdrift.append(f"executor.md sets {dead}, which plugin subagents ignore")
if not agentdrift:
    report("PASS", "the executor subagent exists and is pinned to Sonnet")
    print("          execution delegated to @house-rules:executor runs on sonnet, not opus")
else:
    report("FAIL", "the executor subagent exists and is pinned to Sonnet")
    print(f"          {'; '.join(agentdrift)}")

# --- the executor description authorizes proactive use ----------------------------------------
if os.path.isfile(AGENT) and "proactiv" in read(AGENT).lower():
    report("PASS", "the executor description authorizes proactive use")
    print('          description contains "proactively", satisfying the Agent tool\'s own gate')
else:
    report("FAIL", "the executor description authorizes proactive use")
    print('          agents/executor.md description has no "proactively" (or similar) wording')

# --- install.ps1 still writes the model setting the README claims ------------------------------
install_path = os.path.join(ROOT, "tools", "install.ps1")
moddrift = []
if not os.path.isfile(install_path):
    moddrift.append("tools/install.ps1 is missing")
else:
    install_text = read(install_path)
    if "Name = 'model'" not in install_text:
        moddrift.append("install.ps1 no longer writes a model setting")
    if "opusplan" not in install_text:
        moddrift.append("install.ps1 no longer sets opusplan")
readme_path = os.path.join(ROOT, "claude-house-rules", "README.md")
if os.path.isfile(readme_path) and "opusplan" not in read(readme_path):
    moddrift.append("the README does not document opusplan")
for docfile in [readme_path, root_claude]:
    if os.path.isfile(docfile):
        if "cli and the ide" not in read(docfile).lower():
            moddrift.append(
                f"{os.path.basename(docfile)} does not say opusplan covers only the CLI and the IDE"
            )
if not moddrift:
    report("PASS", "install.ps1 sets model = opusplan and the docs scope it correctly")
    print("          opusplan on the CLI and IDE; every other surface via @house-rules:executor")
else:
    report("FAIL", "install.ps1 sets model = opusplan and the docs scope it correctly")
    print(f"          {'; '.join(moddrift)}")

# --- the architecture tables in CLAUDE.md and the README match hooks.json ----------------------
# Registered dispatch events, read from hooks.json's run.sh invocations rather than filenames -
# there is only one script (run.sh) now, dispatched by event argument.
registered_events = sorted(set(re.findall(r'run\.sh\\" ([a-z]+)', hooks_json_text)))
docdrift = []
for doc in [root_claude, readme_path]:
    docname = os.path.basename(doc)
    if not os.path.isfile(doc):
        docdrift.append(f"no {docname} to check")
        continue
    doc_text = read(doc)
    table_lines = "\n".join(
        line
        for line in doc_text.splitlines()
        if re.match(r"^\| `(SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop)`", line)
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
if not docdrift:
    report("PASS", "the architecture tables match hooks.json")
    print("          every registered hook event is documented and no stray .sh script exists")
else:
    report("FAIL", "the architecture tables match hooks.json")
    print(f"          {'; '.join(docdrift)}")

print()
print("-" * 32)
if FAILURES == 0:
    print(f"RESULT: PASS - all {STEP} checks passed. The hooks are behaving as written.")
else:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed. See the FAIL lines above.")
print()
print("Dependencies used by the hooks: run.sh (POSIX sh) + a probed Python interpreter.")
print("No node, no jq required by hook.py itself - stdlib only.")
print("Matching is textual, so a command that merely mentions a tripwire word will also")
print("prompt. That is deliberate - an extra keypress is cheaper than a missed commit.")
print()

sys.exit(0 if FAILURES == 0 else 1)
