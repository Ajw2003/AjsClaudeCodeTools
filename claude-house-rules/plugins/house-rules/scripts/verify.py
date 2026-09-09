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

import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RULES_FILE = os.path.join(HERE, "..", "rules", "house-rules.md")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
AGENT = os.path.join(HERE, "..", "agents", "executor.md")
ARCHIVIST = os.path.join(HERE, "..", "agents", "archivist.md")
STYLE = os.path.join(HERE, "..", "output-styles", "handover-cards.md")
TEMPLATE = os.path.join(HERE, "..", "templates", "step-card.html")
DOCSKILL = os.path.join(HERE, "..", "skills", "project-docs", "SKILL.md")
CHATDOC = os.path.join(ROOT, "docs", "claude-ai-instructions.md")
VERIFYDOC = os.path.join(ROOT, "docs", "desktop-verification.md")

# Absolute, so the PATH-emptied cases below still find the shell they are testing run.sh with —
# with a bare "sh" those cases fail to launch at all instead of exercising the fallback.
SH = (
    r"C:\Program Files\Git\bin\sh.exe"
    if os.path.exists(r"C:\Program Files\Git\bin\sh.exe")
    else (shutil.which("sh") or "sh")
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

RULE_COMMIT = "Commit constantly on my own branches, never on theirs"
RULE_DESTRUCTIVE = "Never take a destructive action without checking first"

# --- branch fixtures -------------------------------------------------------------------------
# Why fixtures instead of the developer's branch: docs/architecture.md, "Fixture repos, not the developer's branch".
_FIXTURE_ROOT = tempfile.mkdtemp(prefix="house-rules-verify-")
atexit.register(shutil.rmtree, _FIXTURE_ROOT, True)


def _repo_on(name, head_line):
    path = os.path.join(_FIXTURE_ROOT, name)
    os.makedirs(os.path.join(path, ".git"))
    with open(os.path.join(path, ".git", "HEAD"), "w", encoding="utf-8") as f:
        f.write(head_line)
    return path


REPO_THEIRS = _repo_on("theirs", "ref: refs/heads/main\n")
REPO_MINE = _repo_on("mine", "ref: refs/heads/claude/some-topic\n")
REPO_DETACHED = _repo_on("detached", "9f1c0de0000000000000000000000000000000ab\n")
REPO_NONE = os.path.join(_FIXTURE_ROOT, "not-a-repo")
os.makedirs(REPO_NONE)


def env_in(project_dir, **extra):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = project_dir
    e.update(extra)
    return e


# --- guard cases: 28 commands ---------------------------------------------------------------
# All judged from REPO_THEIRS, so these pin the behaviour on a branch that is not mine - the
# conservative baseline the plugin had before branch-awareness. BRANCH_CASES below covers the
# ownership axis.
GUARD_CASES = [
    ("pass", None, "git status"),
    ("pass", None, "git log --oneline -n 20"),
    ("pass", None, "git diff HEAD~1"),
    ("pass", None, "npm test"),
    ("pass", None, "ls -la src"),
    ("pass", None, r"Get-ChildItem C:\Users"),
    ("pass", None, "npm run build && npm test"),
    ("ask", "Commit constantly on my own branches, never on theirs", 'git commit -m "wip"'),
    ("pass", None, "git add -A"),
    ("ask", "Commit constantly on my own branches, never on theirs", "git push origin main"),
    ("ask", "Commit constantly on my own branches, never on theirs", "git push --force-with-lease"),
    ("pass", None, "git checkout -b feature/x"),
    ("pass", None, "git switch main"),
    ("pass", None, "git branch -d old-feature"),
    ("pass", None, "git tag v1.2.0"),
    ("ask", "Commit constantly on my own branches, never on theirs", "git reset --hard origin/main"),
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
    ("ask", "Commit constantly on my own branches, never on theirs", 'echo "starting" && git commit -m "wip"'),
]

for expect, rule, cmd in GUARD_CASES:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(REPO_THEIRS))
    if '"permissionDecision":"ask"' in out:
        got = "ask"
    elif not out.strip() or "no house rule matched" in out:
        # Not prompting is the decision; the allow path now says so out loud rather than
        # being indistinguishable from the hook never having run.
        got = "pass"
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

# --- branch-aware guard: the same command, judged by whose branch the checkout is on ---------
BRANCH_CASES = [
    # On a branch I created, a commit and an ordinary push are checkpoints, not mutations of
    # the user's history. These are the only two the exemption covers.
    (REPO_MINE, "claude/some-topic", "pass", None, 'git commit -m "checkpoint"'),
    (REPO_MINE, "claude/some-topic", "pass", None, "git push origin HEAD"),
    (REPO_MINE, "claude/some-topic", "pass", None, "git -c user.name=x commit -m y"),
    # Force-pushing rewrites history that was already safe, so it is not a checkpoint and the
    # exemption does not reach it - on any branch.
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git push --force-with-lease"),
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git push -f origin HEAD"),
    # Discarding work, or finishing something the user started, stays a prompt on my branch too.
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git reset --hard origin/main"),
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git rebase -i HEAD~3"),
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git merge main"),
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git cherry-pick abc123"),
    # A command naming another repo is not talking about the branch we just read.
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, 'git -C /other/repo commit -m "x"'),
    (REPO_MINE, "claude/some-topic", "ask", RULE_COMMIT, "git --git-dir=/other/.git push"),
    # Ownership buys nothing outside the commit rule.
    (REPO_MINE, "claude/some-topic", "ask", RULE_DESTRUCTIVE, "rm -rf build"),
    # Every branch that is not mine, and every branch I could not read, still prompts.
    (REPO_THEIRS, "main", "ask", RULE_COMMIT, 'git commit -m "wip"'),
    (REPO_THEIRS, "main", "ask", RULE_COMMIT, "git push origin main"),
    (REPO_DETACHED, "a detached HEAD", "ask", RULE_COMMIT, 'git commit -m "wip"'),
    (REPO_NONE, "a directory that is not a repo", "ask", RULE_COMMIT, 'git commit -m "wip"'),
]

for project_dir, label, expect, rule, cmd in BRANCH_CASES:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(project_dir))
    if '"permissionDecision":"ask"' in out:
        got = "ask"
    elif not out.strip() or "no house rule matched" in out or "mine to commit on" in out:
        got = "pass"
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
    report(result, f"{cmd}   [on {label}]")
    print(f"          expected {expect}, got {got}{cited}")

# The prompt has to say why the exemption did not apply, or the user is left reading a rule
# about branch ownership with no way to tell which branch they are on. Each of the three ways
# it can fail to apply names itself.
prompt_problems = []
for project_dir, cmd, wanted in [
    (REPO_THEIRS, 'git commit -m "wip"', "You are on `main`, which is yours"),
    (REPO_DETACHED, 'git commit -m "wip"', "HEAD is detached"),
    (REPO_NONE, 'git commit -m "wip"', "not inside a git repository"),
    (REPO_MINE, 'git -C /other/repo commit -m "x"', "names another repo"),
]:
    code, out, err = run_hook("guard", payload_for(cmd), env=env_in(project_dir))
    if wanted not in out:
        prompt_problems.append(f"{cmd} in {os.path.basename(project_dir)}: no {wanted!r}")
if not prompt_problems:
    report("PASS", "a prompt the branch exemption could have silenced says why it did not")
    print("          names the branch, the detached HEAD, the missing repo, or the other repo")
else:
    report("FAIL", "a prompt the branch exemption could have silenced says why it did not")
    for p in prompt_problems:
        print(f"          {p}")

# The exemption is a silent success path, and guard's silent paths trace by contract.
code, out, err = run_hook("guard", payload_for("git commit -m x"), env=env_in(REPO_MINE))
if '"systemMessage"' in out and "claude/some-topic" in out and "mine to commit on" in out:
    report("PASS", "an exempted command traces the branch it was exempted on")
    print(f"          said: {json.loads(out)['systemMessage']}")
else:
    report("FAIL", "an exempted command traces the branch it was exempted on")
    print(f"          got: {out!r}")

# A worktree's .git is a file, not a directory. Getting this wrong would silently downgrade
# every worktree to "not a repo" - which prompts, so it would never have been noticed.
_wt = os.path.join(_FIXTURE_ROOT, "worktree")
os.makedirs(_wt)
with open(os.path.join(_wt, ".git"), "w", encoding="utf-8") as f:
    f.write("gitdir: %s\n" % os.path.join(REPO_MINE, ".git"))
code, out, err = run_hook("guard", payload_for("git commit -m x"), env=env_in(_wt))
if "mine to commit on" in out:
    report("PASS", "a linked worktree resolves its branch through the gitdir: pointer")
    print("          .git as a file is followed, not mistaken for an unreadable repo")
else:
    report("FAIL", "a linked worktree resolves its branch through the gitdir: pointer")
    print(f"          got: {out!r}")

# The branch is read from a file, never by running git. A subprocess here would sit on the
# critical path of every shell command, in the one handler that blocks when it fails.
_hook_src = read(HOOK)
_own = _hook_src[_hook_src.index("def branch_ownership") :]
_own = _own[: _own.index("\ndef ", 1)]
# Call syntax only, not prose. Why the docstring names rev-parse: docs/architecture.md, "Why `.git/HEAD` and not `git rev-parse --abbrev-ref HEAD`".
_shelling = [c for c in ("subprocess.", "os.popen(", "os.system(", "check_output") if c in _own]
if not _shelling:
    report("PASS", "branch ownership is read from .git/HEAD, never by shelling out to git")
    print("          guard blocks on failure, so it must not depend on a process that can hang")
else:
    report("FAIL", "branch ownership is read from .git/HEAD, never by shelling out to git")
    print(f"          branch_ownership() reached for: {', '.join(_shelling)}")

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
if '"permissionDecision"' not in out and "`npm test`" in out:
    report("PASS", "a harmless command with a git-mentioning description does not prompt")
    print("          no prompt, and the trace names `npm test` - the command, not the description")
else:
    report("FAIL", "a harmless command with a git-mentioning description does not prompt")
    print(f"          got: {out}")

# --- the fallback tier: no command field must never mean "wave it through" ------------------
nocmd_payload = json.dumps(
    {"session_id": "verify", "tool_name": "PowerShell", "tool_input": {"script": "git commit -m wip"}}
)
code, out, err = run_hook("guard", nocmd_payload, env=env_in(REPO_THEIRS))
if '"permissionDecision":"ask"' in out and "Commit constantly on my own branches, never on theirs" in out:
    report("PASS", "a payload with no command field still gets checked (whole-payload fallback)")
    print("          fell back to the old behaviour rather than passing it unchecked")
else:
    report("FAIL", "a payload with no command field still gets checked (whole-payload fallback)")
    print(f"          got: {out}")

# --- the rules actually reach the session ----------------------------------------------------
code, out, err = run_hook("inject", "")
missing = []
for h in [
    "Find out what machine you are on",
    "Match response depth to the task",
    "Build only what was asked",
    "Read the docs first, then check them against the code",
    "Documentation goes in tiers",
    "Build for a human working alone",
    "hands are for decisions, not labour",
    "Deliver a whole workflow, not a starting point",
    "Never hand over a command I have not run",
    "Every artifact lives in the project directory",
    "Never hide work in a background window or a silent process",
    "Commit constantly on my own branches, never on theirs",
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

# --- the step-card template actually REACHES the session, not just the file ------------------
# Asserting rules/house-rules.md contains the card is not asserting Claude ever sees it - the
# same distinction the model-split checks exist for. Feed inject and read the injected text.
cardmissing = []
for marker in [
    "#### The card",
    "### Step 1 of",
    "**You should see:**",
    "UNTESTED:",
    "is a label on a command, not a step",
    "A card is a sequence, not a menu",
    "Replacing step N:",
    "does not depend on where the prompt is",
]:
    if marker not in out:
        cardmissing.append(marker)
if not cardmissing:
    report("PASS", "SessionStart injects the step-card template into context")
    print("          the card markers arrive in additionalContext, not just in the file")
else:
    report("FAIL", "SessionStart injects the step-card template into context")
    print(f"          missing from the injected text: {'; '.join(cardmissing)}")

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
        if "response depth" not in out or "machine you are on" not in out:
            bad.append("expected the long form, did not see its content")
    elif expect == "short":
        if "response depth" in out or "machine you are on" in out:
            bad.append("expected the short form, but the long form's content is present")
        if "step-card format" not in out:
            bad.append("short form missing the step-card-format line")
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
    elif '"systemMessage"' in out:
        got = "trace"
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
    )
art_case(
    "trace",
    "a .ps1 in the scratchpad is still scratch work - runnables stay out of the artifact list",
    r"C:\Users\aj\AppData\Local\Temp\claude\scratchpad\build.ps1",
)

# --- the reminder in hook.py's scope handler has not drifted from the rules document --------
# Covers both forms - the short one is what fires on most prompts now, so its phrases need the
# same drift protection the long form always had.
rules_text = read(RULES_FILE)
drift = []
for phrase in [
    "response depth",
    "portability work",
    "only what was asked",
    "ask instead of assuming",
    "project directory",
    "hand over a command",
    "step-card format",
    "You should see:",
]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
# The check above reads the rules document only, so it cannot notice a reminder that has been
# trimmed until it no longer states a rule. The long form was cut from 1,435 to ~915 chars for
# cost; these are the rules it must still carry after any further trim, since the long form is
# the only place they are restated once the SessionStart copy has faded from attention.
long_reminder = run_hook("scope", json.dumps({"prompt": "run the build script"}))[1]
gutted = []
for phrase in [
    "only what was asked",
    "ask instead of assuming",
    "whole workflow",
    "project directory",
    "have not run",
    "step-card format",
    "You should see:",
    "UNTESTED:",
]:
    if phrase.lower() not in long_reminder.lower():
        gutted.append(phrase)
if not gutted:
    report("PASS", "the trimmed long-form reminder still carries every operative rule")
    print(f"          {len(long_reminder)} chars, all 8 operative phrases present")
else:
    report("FAIL", "the trimmed long-form reminder still carries every operative rule")
    print(f"          trimmed away: {'; '.join(gutted)}")

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

# --- the reminder in hook.py's runnable handler has not drifted from the rules document -----
drift = []
for phrase in [
    "whole workflow",
    "starting point",
    "hand over a command",
    "run it twice",
    "realistic",
    "not proof it works",
]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "runnable reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "runnable reminder still matches the rules document")
    print(f"          in runnable reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- and the reverse: the EMITTED runnable note still states the rule ---------------------------
# The check above reads the rules document only, so on its own it cannot notice a reminder that
# has been trimmed until it no longer states a rule. This reads what the hook actually emits.
code, out, err = run_hook(
    "runnable", json.dumps({"tool_input": {"file_path": r"C:\proj\deploy.sh"}})
)
drift = []
for phrase in ["run it twice", "realistic input", "not a whole workflow", "someone thought to write"]:
    if phrase not in out:
        drift.append(phrase)
if not drift:
    report("PASS", "the emitted runnable note still says one clean run is not proof")
    print("          a trim that gutted the reminder would fail here, not just in the rules doc")
else:
    report("FAIL", "the emitted runnable note still says one clean run is not proof")
    print(f"          missing from the emitted reminder: {'; '.join(drift)}")

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

missing = [
    ph
    for ph in [
        "Plain language on the surfaces a human reads",
        "### The voice",
        "gloss",
        "never buys warmth with accuracy",
        "HOUSE_RULES_VOICE=off",
    ]
    if ph.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the plain-language rule carries the voice and its hard constraint")
    print("          tone is a preference; not softening a failure is not")
else:
    report("FAIL", "the plain-language rule carries the voice and its hard constraint")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# --- HOUSE_RULES_VOICE=off removes the voice and nothing else -------------------------------
# The section is cut by locating the next "## " heading. If that boundary is wrong the toggle
# eats the rule after it, silently, and nobody notices until a rule stops being enforced.
code, on_out, err = run_hook("inject", "")
env_off = dict(os.environ)
env_off["HOUSE_RULES_VOICE"] = "off"
code_off, off_out, err_off = run_hook("inject", "", env=env_off)
voice_problems = []
if "### The voice" not in on_out:
    voice_problems.append("the voice is missing by default, but it ships on")
if "### The voice" in off_out:
    voice_problems.append("HOUSE_RULES_VOICE=off did not remove the voice section")
for kept in [
    "Plain language on the surfaces a human reads",
    "Deliver a whole workflow",
    "Never hand over a command",
    "A green test suite is not proof it works",
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

# --- the commit rule draws the line at branch ownership, and records both reversals ----------
# It has now been rewritten twice for the same reason, so what is pinned here is the shape that
# survived: who owns the branch, not whether permission was granted for this change. The earlier
# "open pull request" wording gated on a state only reachable *after* the first commit, which is
# exactly the commit that protects a day's work.
missing = [
    ph
    for ph in [
        "On a branch I created",
        "On a branch the user authored",
        "I do not finish what the user started",
        "ephemeral container",
        "mis-drawn",
    ]
    if ph.lower() not in rules_text.lower()
]
if not missing:
    report("PASS", "the commit rule draws the line at branch ownership and records both reversals")
    print("          my branches: commit freely; theirs: mutate nothing; both losses written down")
else:
    report("FAIL", "the commit rule draws the line at branch ownership and records both reversals")
    print(f"          missing from house-rules.md: {'; '.join(missing)}")

# --- the guard cites rules that actually exist in the rules document -------------------------
# It cites a rule by its heading, and nothing checked that the heading was still there. Renaming
# "Never commit without asking" to "Never commit to `main` without asking" would have left the
# permission prompt naming a rule the user could not find - a silent drift in the one place the
# plugin speaks directly to them.
bucket_titles = re.findall(r'^\s*\("([^"]+)", GUARD_R\d+\),', read(HOOK), re.MULTILINE)
headings = [ln.lstrip("# ").strip() for ln in rules_text.split("\n") if ln.startswith("## ")]
orphans = [t for t in bucket_titles if t not in headings]
if bucket_titles and not orphans:
    report("PASS", "every rule the guard cites is a real heading in the rules document")
    print(f"          {len(bucket_titles)} bucket titles, all found in house-rules.md")
else:
    report("FAIL", "every rule the guard cites is a real heading in the rules document")
    for o in orphans:
        print(f"          guard cites {o!r}, which is not a heading in house-rules.md")
    if not bucket_titles:
        print("          no GUARD_BUCKETS titles were found at all - the pattern has drifted")

# --- harvest: long-form comments are documentation in the wrong file ---------------------------
CS_HEAD = "using UnityEngine;\n\npublic class Orbit : MonoBehaviour\n{\n"
ESSAY_CS = CS_HEAD + (
    "// The orbit integrator uses Verlet rather than Euler. Euler was tried first and lost\n"
    "// energy visibly over about four minutes of play, which showed up as satellites slowly\n"
    "// spiralling into the planet with no force acting on them. Verlet is symplectic, so the\n"
    "// energy error is bounded rather than cumulative, and the artefact goes away entirely.\n"
    "// The cost is that velocity is not directly available at the current step; where a caller\n"
    "// needs it, it is reconstructed from the two most recent positions instead.\n"
    "public void Step(float dt) { }\n"
)
SHORT_CS = CS_HEAD + "// Must run after Init(). Order matters here.\nvoid A() { }\n"
COMMENTED_CODE = CS_HEAD + "".join(
    "// var x%d = Compute(y, z);\n" % i for i in range(20)
) + "void B() { }\n"
LICENSE_CS = CS_HEAD + (
    "// Copyright 2026 Someone. All rights reserved. Licensed under the Apache License,\n"
    "// Version 2.0 (the \"License\"); you may not use this file except in compliance with it.\n"
    "// You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.\n"
    "// Unless required by applicable law, software distributed under the License is\n"
    "// distributed on an \"AS IS\" BASIS, without warranties or conditions of any kind.\n"
    "// See the License for the specific language governing permissions and limitations.\n"
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
    '    makes the failure timeline reproducible when reading logs after the fact.\n'
    '    """\n'
    '    return 1\n'
)


def harv_case(expect, title, file_path, content, tool="Write", env=None, expect_in=()):
    field = "content" if tool == "Write" else "new_string"
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": file_path, field: content}})
    e = dict(os.environ)
    e.pop("HOUSE_RULES_HARVEST", None)
    e.pop("HOUSE_RULES_HARVEST_MIN_LINES", None)
    e.pop("HOUSE_RULES_HARVEST_MIN_CHARS", None)
    e.pop("HOUSE_RULES_DEBUG", None)
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
    "a design essay in a .cs file is flagged for porting into docs/systems/",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    expect_in=["@house-rules:archivist", "one-line pointer", "Orbit.cs:5-10"],
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
    "twenty lines of commented-out code is not an essay",
    r"C:\proj\B.cs",
    COMMENTED_CODE,
    expect_in=["commented-out code"],
)
harv_case(
    "trace",
    "a license header is not an essay",
    r"C:\proj\C.cs",
    LICENSE_CS,
    expect_in=["license header"],
)
harv_case(
    "silent",
    "a markdown file is out of jurisdiction - the one fully silent path",
    r"C:\proj\docs\systems\physics.md",
    "Sentence one. Sentence two. " * 60,
)

# --- harvest: the trace is on by DEFAULT, and says what it measured ----------------------------
# A diagnostic that ships switched off is never enabled until someone is already lost, so the
# default output has to answer "did this run, on what, and what did it decide" with no flags set.
harv_case(
    "trace",
    "the default trace names the measured longest run and the active threshold",
    r"C:\proj\A.cs",
    SHORT_CS,
    expect_in=["A.cs", "5 lines / 300 chars", "longest was 1 line"],
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
    "raising HOUSE_RULES_HARVEST_MIN_LINES stops the essay qualifying",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST_MIN_LINES": "40", "HOUSE_RULES_HARVEST_MIN_CHARS": "9000"},
)
harv_case(
    "remind+trace",
    "a bad threshold override is named out loud and the default is used anyway",
    r"C:\proj\Assets\Orbit.cs",
    ESSAY_CS,
    env={"HOUSE_RULES_HARVEST_MIN_LINES": "banana"},
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
if "Orbit.cs:5-10" not in out and "Blocks:" not in out:
    report("PASS", "an Edit's reminder carries no file:line range at all")
    print("          no fabricated line numbers in the Edit reminder")
else:
    report("FAIL", "an Edit's reminder carries no file:line range at all")
    print(f"          got: {out[:300]}")

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

# --- every handler with a silent success path now says what it decided --------------------------
# "Nothing fails silently" asks the default output to answer: did this run, on what, and what did
# it decide. stderr cannot answer it - a hook that exits 0 has its stderr sent to the debug log
# only, never the transcript - so these are systemMessages or they are nothing.
trace_cases = [
    ("guard", json.dumps({"tool_input": {"command": "git status"}}),
     "`git status`", "the allow path, the plugin's highest-frequency silent decision"),
    ("artifact", json.dumps({"tool_input": {"file_path": r"C:\proj\a.cs"}}),
     "a.cs", "a file that is not a document extension"),
    ("artifact", json.dumps({"tool_input": {"file_path": r"C:\proj\notes.md"}}),
     "inside the project", "a document that is already in the project"),
    ("runnable", json.dumps({"tool_input": {"file_path": r"C:\proj\notes.md"}}),
     "not a runnable file", "a file that cannot be run"),
]
for event, payload, needle, why in trace_cases:
    code, out, err = run_hook(event, payload)
    if code == 0 and '"systemMessage"' in out and needle in out:
        report("PASS", f"{event} traces its decision on {why}")
        print(f"          says what it looked at and what it concluded; names {needle!r}")
    else:
        report("FAIL", f"{event} traces its decision on {why}")
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
    "guard", json.dumps({"tool_input": {"command": "git commit -m wip"}}), env=off
)
if '"permissionDecision":"ask"' not in out:
    quiet_failures.append("HOUSE_RULES_TRACE=off also silenced guard's prompt, which it must not")
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
if not out.strip() and "never announces its own compliance" in read(RULES_FILE):
    report("PASS", "handover stays silent on its stand-down, and the rule that requires it still stands")
    print("          the one handler where tracing would break a rule rather than cost tokens")
else:
    report("FAIL", "handover stays silent on its stand-down, and the rule that requires it still stands")
    print(f"          got: {out[:160]!r}")

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
    "hook.HARVEST_BUDGET_SECONDS = -1.0\n"
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

# --- the harvest reminder has not drifted from the rules document ------------------------------
drift = []
for phrase in ["long-form", "one-line pointer", "@house-rules:archivist", "docs/systems"]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "harvest reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "harvest reminder still matches the rules document")
    print(f"          in harvest reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- and the reverse: the EMITTED reminder still states the rule -------------------------------
# The check above reads the rules document only, so on its own it cannot notice a reminder that
# has been trimmed until it no longer states a rule. This reads what the hook actually emits.
payload = json.dumps(
    {"tool_name": "Write", "tool_input": {"file_path": "/proj/Orbit.cs", "content": ESSAY_CS}}
)
code, out, err = run_hook("harvest", payload)
drift = []
for phrase in [
    "one-line pointer",
    "@house-rules:archivist",
    "docs/systems",
    "How it works",
    "Traps",
    "Invariants",
    "Do not change how you write",
    "the user was not prompted",
]:
    if phrase not in out:
        drift.append(phrase)
if not drift:
    report("PASS", "the emitted harvest reminder still carries every operative phrase")
    print("          a trim that gutted the reminder would fail here, not just in the rules doc")
else:
    report("FAIL", "the emitted harvest reminder still carries every operative phrase")
    print(f"          missing from the emitted reminder: {'; '.join(drift)}")

# --- the "nothing fails silently" rule, enforced structurally over hook.py source --------------
# The rule is worthless if the plugin's own hooks break it, so this reads hook.py and fails any
# except block that returns without first emitting or writing to stderr.
hook_src = read(HOOK)
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
    ("delegate", "delegate"),
    ("handover", "handover"),
    ("harvest", "harvest"),
):
    snippet = (
        "import sys, hook\n"
        "real_emit = hook.emit\n"
        "state = {'first': True}\n"
        "def one_shot_boom(obj):\n"
        "    if state['first']:\n"
        "        state['first'] = False\n"
        "        raise OSError('simulated internal failure')\n"
        "    real_emit(obj)\n"
        "hook.emit = one_shot_boom\n"
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
for phrase in ("not injected", "one-line pointer", "Nothing fails silently", "docs/systems"):
    if phrase.lower() not in archivist.lower():
        problems.append(f"the digest no longer states {phrase!r}")
if not problems:
    report("PASS", "the archivist subagent is shaped so the harvest delegation can happen")
    print("          pinned to sonnet, marked proactive, and carries the digest it needs")
else:
    report("FAIL", "the archivist subagent is shaped so the harvest delegation can happen")
    for p in problems:
        print(f"          {p}")

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


def stop_payload(**extra):
    base = {"session_id": "verify", "hook_event_name": "Stop", "stop_hook_active": False}
    base.update(extra)
    return json.dumps(base)


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

# --- the checklist in hook.py's handover handler has not drifted from the rules document ----
drift = []
for phrase in [
    "fence label",
    "working directory",
    "UNTESTED",
    "Run button",
    "does not depend on where the prompt is",
    "hand over a command",
    "open a terminal or PowerShell there",
    "One numbered step per action",
    "step-card format",
    "Step 1 of",
    "You should see:",
    "above the fence",
    "Replacing step",
    "never announces its own compliance",
]:
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

# --- house-rules.md states the delegation rule exactly once (F6 merge) -----------------------
heading_hits = [m for m in re.finditer(r"^## .*delegat.*$", rules_text, re.IGNORECASE | re.MULTILINE)]
if len(heading_hits) == 1:
    report("PASS", "house-rules.md states the delegation rule exactly once")
    print(f"          one heading: {heading_hits[0].group(0)}")
else:
    report("FAIL", "house-rules.md states the delegation rule exactly once")
    print(f"          found {len(heading_hits)} delegation headings: {[m.group(0) for m in heading_hits]}")

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

# --- executor.md does not claim the rules are already in its context, and carries a digest ----
# A clean @house-rules:executor spawn was asked directly and answered no: SessionStart
# additionalContext does not reach subagents. executor.md used to assert the opposite ("The
# house rules are already in this session's context"), which is the bug this check catches.
digestdrift = []
if not os.path.isfile(AGENT):
    digestdrift.append("agents/executor.md is missing")
else:
    agent_text = read(AGENT)
    if "already in this session" in agent_text.lower():
        digestdrift.append("executor.md still claims the rules are already in its context")
    for phrase in [
        "not injected",
        "hand over a command you have not run",
        "step-card format",
        "commit messages",
    ]:
        if phrase.lower() not in agent_text.lower():
            digestdrift.append(f"executor.md digest is missing: {phrase!r}")
if not digestdrift:
    report("PASS", "executor.md carries its own rules digest instead of assuming inherited context")
    print("          no 'already in this session' claim; the digest covers the load-bearing rules")
else:
    report("FAIL", "executor.md carries its own rules digest instead of assuming inherited context")
    print(f"          {'; '.join(digestdrift)}")

# --- the output style exists and IS forced ---------------------------------------------------
# Reversed in 2.4.0. 2.3.0 asserted this field was ABSENT, on the argument that forcing displaces
# a style the user selected - which assumed a picker that does not exist: /output-style was
# removed in v2.1.91 and the desktop app has no style picker, so un-forced meant unreachable
# without hand-editing a settings file. Same shape as the executor dead-field check either way:
# assert the decision, not just the file, so it cannot flip back by accident.
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
    # The style is a live carrier whenever the Stop check is off, so a restatement that has
    # fallen behind the rules is a real gap, not cosmetic. It fell behind once already:
    # location-independence shipped in the rules and never reached this file.
    for phrase in ["runs from anywhere", "One numbered step per action", "UNTESTED:"]:
        if phrase not in style_text:
            styledrift.append(f"the style no longer restates {phrase!r} from the six items")
        elif phrase not in rules_text:
            styledrift.append(f"{phrase!r} is in the style but not in house-rules.md")
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

# --- every surface the CLAUDE.md table claims has a way to be checked ------------------------
# The table is a claim about six surfaces; docs/desktop-verification.md is what substantiates it.
# A row added to the table with no way to check it is exactly the drift guarded against elsewhere,
# so the surface names are read out of the table itself rather than hardcoded here.
surfdrift = []
surfaces = []
if not os.path.isfile(VERIFYDOC):
    surfdrift.append("docs/desktop-verification.md is missing")
elif os.path.isfile(root_claude):
    verify_doc = read(VERIFYDOC)
    for line in read(root_claude).splitlines():
        m = re.match(r"^\| (?:Claude Code|claude\.ai chat) [-\u2014 ]+([^|]+?) \|", line)
        if m:
            surfaces.append(m.group(1).strip())
    if not surfaces:
        surfdrift.append("no surface rows found in CLAUDE.md - has the table been renamed?")
    for s in surfaces:
        if s not in verify_doc:
            surfdrift.append(f"{s!r} is in the CLAUDE.md table but has no check in desktop-verification.md")
if not surfdrift:
    report("PASS", "every surface in the CLAUDE.md table has a check in desktop-verification.md")
    print(f"          {len(surfaces)} surfaces claimed, {len(surfaces)} covered: {', '.join(surfaces)}")
else:
    report("FAIL", "every surface in the CLAUDE.md table has a check in desktop-verification.md")
    print(f"          {'; '.join(surfdrift)}")

# --- the card template was not duplicated into CLAUDE.md -------------------------------------
# Same reasoning as the rules-duplication check above: CLAUDE.md is a pointer. A second copy of
# the template would load twice and drift from the real one unnoticed.
dupe = []
if os.path.isfile(root_claude):
    claude_text = read(root_claude)
    for marker in ["### Step 1 of", "**You should see:**", "*Next: step 2"]:
        if marker in claude_text:
            dupe.append(f"CLAUDE.md contains {marker!r} - the template belongs only in house-rules.md")
if not dupe:
    report("PASS", "the card template was not duplicated into CLAUDE.md")
    print("          CLAUDE.md describes the format and points at rules/house-rules.md for it")
else:
    report("FAIL", "the card template was not duplicated into CLAUDE.md")
    print(f"          {'; '.join(dupe)}")

# --- the claude.ai chat block exists and has not drifted from the rules document -------------
# Hooks do not run in claude.ai chat, so this file is the only thing covering that surface (and
# the phone). It is a restatement, so it gets the same drift treatment as hook.py's strings.
chatdrift = []
if not os.path.isfile(CHATDOC):
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
if not chatdrift:
    report("PASS", "the claude.ai chat block exists and matches the rules document")
    print("          one paste-able block; every phrase in it also appears in house-rules.md")
else:
    report("FAIL", "the claude.ai chat block exists and matches the rules document")
    print(f"          {'; '.join(chatdrift)}")

# --- the executor description authorizes proactive use ----------------------------------------
if os.path.isfile(AGENT) and "proactiv" in read(AGENT).lower():
    report("PASS", "the executor description authorizes proactive use")
    print('          description contains "proactively", satisfying the Agent tool\'s own gate')
else:
    report("FAIL", "the executor description authorizes proactive use")
    print('          agents/executor.md description has no "proactively" (or similar) wording')

# --- install.py still writes the model setting the README claims ------------------------------
install_path = os.path.join(ROOT, "tools", "install.py")
moddrift = []
if not os.path.isfile(install_path):
    moddrift.append("tools/install.py is missing")
else:
    install_text = read(install_path)
    if '"name": "model"' not in install_text:
        moddrift.append("install.py no longer writes a model setting")
    if "opusplan" not in install_text:
        moddrift.append("install.py no longer sets opusplan")
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
    report("PASS", "install.py sets model = opusplan and the docs scope it correctly")
    print("          opusplan on the CLI and IDE; every other surface via @house-rules:executor")
else:
    report("FAIL", "install.py sets model = opusplan and the docs scope it correctly")
    print(f"          {'; '.join(moddrift)}")

# --- preflight warns about a missing dependency, and points at /house-rules:doctor -----------
env = dict(os.environ)
env["PATH"] = ""
code, out, err = run_hook("inject", "", env=env)
if "Preflight gaps found" in out and "git is not on PATH" in out and "/house-rules:doctor" in out:
    report("PASS", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print("          a broken PATH produces a visible, actionable preflight warning")
else:
    report("FAIL", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print(f"          got: {out[-400:]!r}")

code, out, err = run_hook("inject", "")
if "Preflight gaps found" not in out:
    report("PASS", "SessionStart preflight is silent when there is nothing to warn about")
    print("          a clean machine adds nothing to the injection")
else:
    report("FAIL", "SessionStart preflight is silent when there is nothing to warn about")
    print(f"          got: {out[-400:]!r}")

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

# --- the standards handler: selection, detection, override, and the fallbacks around it ------
def make_fixture(files):
    d = tempfile.mkdtemp(prefix="house-rules-standards-")
    for relpath, content in files.items():
        full = os.path.join(d, relpath)
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    return d


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

# Drift: the tiered-docs rule names a skill by id, so that skill has to exist. A rule that
# points at a skill nobody shipped is worse than no rule - it reads as though the detail is
# somewhere findable. Same class of check as the standards one above.
docs_drift = []
if "## Documentation goes in tiers" not in rules_text:
    docs_drift.append("house-rules.md is missing the tiered-docs rule heading")
if "house-rules:project-docs" not in rules_text:
    docs_drift.append("the tiered-docs rule no longer names the project-docs skill")
if not os.path.isfile(DOCSKILL):
    docs_drift.append("skills/project-docs/SKILL.md does not exist")
else:
    skill_text = read(DOCSKILL)
    for phrase in ["docs/Roadmap.md", "docs/ProjectState.md", "docs/Today.md", "docs/systems"]:
        if phrase not in skill_text:
            docs_drift.append(f"the skill no longer specifies {phrase}")
if not docs_drift:
    report("PASS", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print("          the rule names the skill, the skill exists, and it still specifies all five tiers")
else:
    report("FAIL", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print(f"          {'; '.join(docs_drift)}")

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
