#!/usr/bin/env python3
"""verify.py — proves the house-rules hooks actually do what they claim.

Run it yourself, any time, on any machine:

    python claude-house-rules/plugins/house-rules/scripts/verify.py

It feeds real hook payloads to hook.py's handlers and prints a numbered PASS/FAIL line for
each, then a final verdict. Exit code 0 = all passed, 1 = something failed. Nothing is
hidden: every case tested is printed alongside its result.

A third state, SKIP, exists for the handful of checks that read files the repo ships and the
plugin package does not (docs/, tools/, CLAUDE.md, the README). Run from the installed plugin
cache those used to report FAIL, where the honest answer is "not applicable here" - and a
RESULT line that is always red is one you stop reading. A skip never affects the exit code,
and it is only ever reached from outside a repo checkout: inside one, a missing file is still
a failure.

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
SKIPPED = []

# Why SKIP exists and what it's gated on: docs/systems/verify-suites.md, "How it works"
# (the IN_REPO paragraph) and Invariants ("A repo-only check SKIPs outside a checkout...").
IN_REPO = os.path.isfile(os.path.join(ROOT, ".claude-plugin", "marketplace.json"))


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    elif result == "SKIP":
        SKIPPED.append(title)
    print(f"{STEP:2d}. {result}  {title}")


def absent_repo_files(*rel_paths):
    """Repo-only paths (relative to ROOT) that this copy does not have.

    Returns nothing when this IS the repo working tree - there a missing file is a genuine
    failure and has to stay a FAIL rather than becoming a skip.
    """
    if IN_REPO:
        return []
    return [p for p in rel_paths if not os.path.isfile(os.path.join(ROOT, p))]


def skip_repo_check(title, absent, extra=""):
    report("SKIP", title)
    print(f"          not a repo checkout; {', '.join(absent)} ships in the repo, not the plugin")
    if extra:
        print(f"          {extra}")


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
def art_case(expect, title, file_path, extra="", contains=None, excludes=None):
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
_art_rules_text = read(RULES_FILE)
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

# --- handover-target: a local session (no CLAUDE_CODE_REMOTE) adds nothing -------------------
# house-rules.md's own rule text legitimately says "handover" and names rules/handover-target.md
# unconditionally (it explains the local-vs-remote distinction itself), so checking for the word
# "handover" anywhere in the output would false-fail here. What must be absent on a local session
# is hook.py's *injected block* - checked by its two block-specific openings instead.
env = dict(os.environ)
env.pop("CLAUDE_CODE_REMOTE", None)
code, out, err = run_hook("inject", "", env=env)
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
code, out, err = run_hook("inject", "", env=env)
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
code, out, err = run_hook("inject", "", env=env)
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
_, handover_out, _ = run_hook("inject", "", env=env)
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

# --- the compile-verification reminder for compiled-language (.cs) files ---------------------
def compile_case(expect, title, file_path):
    obj = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    code, out, err = run_hook("runnable", json.dumps(obj))
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

# --- the reminder in hook.py's compile-verification note has not drifted from the rules doc ---
drift = []
for phrase in [
    "should compile",
    "stand-in",
    "real compiler",
    "batch mode",
    "dotnet build",
]:
    if phrase.lower() not in rules_text.lower():
        drift.append(phrase)
if not drift:
    report("PASS", "compile-verification reminder still matches the rules document")
    print("          every key phrase in the reminder appears in rules/house-rules.md")
else:
    report("FAIL", "compile-verification reminder still matches the rules document")
    print(f"          in compile reminder but missing from house-rules.md: {'; '.join(drift)}")

# --- and the reverse: the EMITTED compile note still states the rule -------------------------
code, out, err = run_hook(
    "runnable", json.dumps({"tool_input": {"file_path": r"C:\proj\Assets\Scripts\Enemy.cs"}})
)
drift = []
for phrase in ["Should compile", "stand-in", "real compiler", "UNTESTED"]:
    if phrase not in out:
        drift.append(phrase)
if not drift:
    report("PASS", "the emitted compile note still says a stand-in is not a compiler")
    print("          a trim that gutted the reminder would fail here, not just in the rules doc")
else:
    report("FAIL", "the emitted compile note still says a stand-in is not a compiler")
    print(f"          missing from the emitted reminder: {'; '.join(drift)}")

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
# Why this must be bidirectional: docs/systems/verify-suites.md, Traps ("Most drift checks
# run in one direction only") and docs/architecture.md, "Why the delegation kept not happening".
_, delegate_out, _ = run_hook("delegate", "")
drift = []
for phrase in [
    "@house-rules:executor",
    "plan is settled",
    "proactiv",               # the authorization; its loss is the regression above
    "one file",               # the skip-it exception is a count, not a judgement call
    "three steps or fewer",
    "one delegation per group",
]:
    if phrase.lower() not in rules_text.lower():
        drift.append(f"{phrase!r} missing from rules/house-rules.md")
    if phrase.lower() not in delegate_out.lower():
        drift.append(f"{phrase!r} missing from the emitted delegate reminder")
if not drift:
    report("PASS", "delegate reminder and the rules document state the same thing, both ways")
    print("          every key phrase appears in house-rules.md AND in what delegate emits")
else:
    report("FAIL", "delegate reminder and the rules document state the same thing, both ways")
    for d in drift:
        print(f"          {d}")

# --- the worktree-isolation mandate has not drifted between DELEGATE_NOTE and house-rules.md ---
# Same bidirectional shape as the delegate drift check above: a concurrent-edit corruption
# incident is what this rule exists to prevent, and it only prevents it if both copies say so.
drift = []
for phrase in ("isolation", "worktree"):
    if phrase.lower() not in rules_text.lower():
        drift.append(f"{phrase!r} missing from rules/house-rules.md")
    if phrase.lower() not in delegate_out.lower():
        drift.append(f"{phrase!r} missing from the emitted delegate reminder")
if not drift:
    report("PASS", "worktree-isolation mandate is stated the same way in both places")
    print("          'isolation' and 'worktree' appear in house-rules.md AND in what delegate emits")
else:
    report("FAIL", "worktree-isolation mandate is stated the same way in both places")
    for d in drift:
        print(f"          {d}")

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
    "// A fixed timestep would sidestep the problem, but the game runs its physics on the\n"
    "// render clock, so the integrator has to tolerate a varying dt without drifting.\n"
    "public void Step(float dt) { }\n"
)
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
# Regression for docs/Decisions.md, "Fix the harvest handler treating an Edit fragment's line 1
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
for phrase in ["long-form", "one-line pointer", "@house-rules:archivist", "docs/systems", "docs/Decisions.md", "doc-ref", "docref.py"]:
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
    "doc-ref",
    "docref.py",
    "one-line pointer",
    "@house-rules:archivist",
    "docs/systems",
    "docs/Decisions.md",
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
for phrase in ("not injected", "one-line pointer", "Nothing fails silently", "docs/systems",
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
    if "one file" not in out or "three steps or fewer" not in out:
        bad.append("the skip-it exception is not stated as a count (one file, three steps)")
    if "proactiv" not in out:
        bad.append("it does not say the delegation is authorized for proactive use")
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
_absent = absent_repo_files("docs/desktop-verification.md", "CLAUDE.md")
if _absent:
    skip_repo_check(
        "every surface in the CLAUDE.md table has a check in desktop-verification.md", _absent
    )
elif not os.path.isfile(VERIFYDOC):
    surfdrift.append("docs/desktop-verification.md is missing")
elif not os.path.isfile(root_claude):
    surfdrift.append("CLAUDE.md is missing, so the table it claims cannot be read")
else:
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
if _absent:
    pass  # already reported as skipped above
elif not surfdrift:
    report("PASS", "every surface in the CLAUDE.md table has a check in desktop-verification.md")
    print(f"          {len(surfaces)} surfaces claimed, {len(surfaces)} covered: {', '.join(surfaces)}")
else:
    report("FAIL", "every surface in the CLAUDE.md table has a check in desktop-verification.md")
    print(f"          {'; '.join(surfdrift)}")

# --- nothing publishes a page unasked, and the rule and the table say the same thing ---------
# The threshold used to live in two places that nothing compared: rules/house-rules.md drove the
# behaviour, CLAUDE.md's table described it, and only the surface NAMES above were ever checked.
# So the table could have said one number while the rule said another, and the first symptom
# would have been a page the user did not ask for.
pubdrift = []
for phrase in [
    "I never publish a page unasked",
    "two or more steps",
    "A single-step card is not offered a page at all",
]:
    if phrase.lower() not in rules_text.lower():
        pubdrift.append(f"rules/house-rules.md no longer says {phrase!r}")
# The replaced wording must be GONE from the operative text and PRESENT in the Why - those are
# two different rules ("nothing stale") and ("when a decision reverses, say what it used to say"),
# and a check that greps the whole section can only ever satisfy one of them. Splitting the
# section at its Why is what lets both be enforced at once.
_sec = rules_text.split("#### When a card is worth publishing as a page", 1)
if len(_sec) != 2:
    pubdrift.append("the publishing section is missing from rules/house-rules.md")
else:
    _body = _sec[1].split(chr(10) + "## ", 1)[0]
    _operative, _, _why = _body.partition("**Why:**")
    for stale in ["four or more steps", "below four steps"]:
        if stale in _operative.lower():
            pubdrift.append(f"the operative rule still carries the replaced wording {stale!r}")
    if "four or more steps" not in _why.lower():
        pubdrift.append("the Why does not record the four-step rule this replaced")
_absent = absent_repo_files("CLAUDE.md")
if _absent:
    pass  # the rules half above still ran; only the table half is unavailable here
elif os.path.isfile(root_claude):
    table_text = read(root_claude)
    rows = [ln for ln in table_text.splitlines() if ln.startswith("| Claude Code")]
    offered = [ln for ln in rows if "offered at 2+ steps" in ln]
    if not offered:
        pubdrift.append("no CLAUDE.md surface row states 'offered at 2+ steps'")
    if "4+ steps" in table_text:
        pubdrift.append("CLAUDE.md still advertises the replaced '4+ steps' threshold")
else:
    pubdrift.append("no CLAUDE.md to check")
if pubdrift and _absent:
    report("FAIL", "the page rule and the CLAUDE.md table agree, and nothing publishes unasked")
    for p in pubdrift:
        print(f"          {p}")
elif _absent:
    skip_repo_check(
        "the page rule and the CLAUDE.md table agree, and nothing publishes unasked",
        _absent,
        extra="the rules half was checked here and passed; only the table half is unavailable",
    )
elif not pubdrift:
    report("PASS", "the page rule and the CLAUDE.md table agree, and nothing publishes unasked")
    print("          rule: offer at 2+ steps, publish only on request; table says the same")
else:
    report("FAIL", "the page rule and the CLAUDE.md table agree, and nothing publishes unasked")
    for p in pubdrift:
        print(f"          {p}")

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

# --- the executor description authorizes proactive use ----------------------------------------
if os.path.isfile(AGENT) and "proactiv" in read(AGENT).lower():
    report("PASS", "the executor description authorizes proactive use")
    print('          description contains "proactively", satisfying the Agent tool\'s own gate')
else:
    report("FAIL", "the executor description authorizes proactive use")
    print('          agents/executor.md description has no "proactively" (or similar) wording')

# --- install.py still writes the model setting the README claims ------------------------------
install_path = os.path.join(ROOT, "tools", "install.py")
readme_rel = os.path.join("claude-house-rules", "README.md")
moddrift = []
_absent = absent_repo_files(os.path.join("tools", "install.py"), readme_rel, "CLAUDE.md")
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
readme_path = os.path.join(ROOT, "claude-house-rules", "README.md")
if os.path.isfile(readme_path) and "opusplan" not in read(readme_path):
    moddrift.append("the README does not document opusplan")
for docfile in [readme_path, root_claude]:
    if os.path.isfile(docfile):
        if "cli and the ide" not in read(docfile).lower():
            moddrift.append(
                f"{os.path.basename(docfile)} does not say opusplan covers only the CLI and the IDE"
            )
if _absent:
    pass  # already reported as skipped above
elif not moddrift:
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

# --- the architecture tables in CLAUDE.md and the README match hooks.json ----------------------
# Registered dispatch events, read from hooks.json's run.sh invocations rather than filenames -
# there is only one script (run.sh) now, dispatched by event argument.
registered_events = sorted(set(re.findall(r'run\.sh\\" ([a-z]+)', hooks_json_text)))
docdrift = []
_absent = absent_repo_files("CLAUDE.md", readme_rel)
for doc in ([] if _absent else [root_claude, readme_path]):
    docname = os.path.basename(doc)
    if not os.path.isfile(doc):
        docdrift.append(f"no {docname} to check")
        continue
    doc_text = read(doc)
    table_lines = "\n".join(
        line
        for line in doc_text.splitlines()
        if re.match(r"^\| `(SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop|SubagentStart|SubagentStop)`", line)
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
    report("FAIL", "the architecture tables match hooks.json")
    print(f"          {'; '.join(docdrift)}")
elif _absent:
    skip_repo_check(
        "the architecture tables match hooks.json",
        _absent,
        extra="scripts/ was checked here and holds no stray .sh; only the doc tables are unavailable",
    )
elif not docdrift:
    report("PASS", "the architecture tables match hooks.json")
    print("          every registered hook event is documented and no stray .sh script exists")
else:
    report("FAIL", "the architecture tables match hooks.json")
    print(f"          {'; '.join(docdrift)}")

# --- the "What trips the guard" README table matches GUARD_R3/GUARD_R4's actual git verbs -----
# Why this tokenizes the table instead of hand-copying the verb list, and the incident that
# made it necessary: docs/systems/verify-suites.md, Invariants ("The guarded-verb list is
# never hand-copied into a doc").
GUARDED_GIT_VERBS = [
    "push", "commit", "reset", "revert", "clean", "rebase", "merge",
    "filter-branch", "cherry-pick", "am", "apply", "checkout", "restore", "stash",
]
NAVIGATIONAL_GIT_VERBS = ["add", "switch", "branch", "tag", "remote", "submodule"]

guarddrift = []
_guard_table_absent = absent_repo_files(readme_rel)
if _guard_table_absent:
    skip_repo_check(
        "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs",
        _guard_table_absent,
    )
else:
    readme_text_guard = read(readme_path)
    table_match = re.search(r"### What trips the guard\n\n(?:\|.*\n)+", readme_text_guard)
    if not table_match:
        guarddrift.append("no 'What trips the guard' table found under that heading")
    else:
        table_tokens = set()
        for span in re.findall(r"`([^`]+)`", table_match.group(0)):
            table_tokens.update(re.split(r"[\s/,]+", span.strip()))
        for verb in GUARDED_GIT_VERBS:
            if verb not in table_tokens:
                guarddrift.append(f"the table does not mention `{verb}`, which hook.py actually matches")
        for verb in NAVIGATIONAL_GIT_VERBS:
            if verb in table_tokens:
                guarddrift.append(f"the table claims `{verb}` trips the guard, but hook.py deliberately does not match it")
    if not guarddrift:
        report("PASS", "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs")
        print(f"          all {len(GUARDED_GIT_VERBS)} guarded verbs present, "
              f"all {len(NAVIGATIONAL_GIT_VERBS)} deliberately-dropped verbs absent")
    else:
        report("FAIL", "the 'What trips the guard' table matches GUARD_R3/GUARD_R4's actual git verbs")
        print(f"          {'; '.join(guarddrift)}")

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
if "docs/Decisions.md" not in rules_text:
    docs_drift.append("house-rules.md no longer mentions docs/Decisions.md")
if not os.path.isfile(DOCSKILL):
    docs_drift.append("skills/project-docs/SKILL.md does not exist")
else:
    skill_text = read(DOCSKILL)
    for phrase in ["docs/Roadmap.md", "docs/ProjectState.md", "docs/Today.md", "docs/systems", "docs/Decisions.md"]:
        if phrase not in skill_text:
            docs_drift.append(f"the skill no longer specifies {phrase}")
if not docs_drift:
    report("PASS", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print("          the rule names the skill, the skill exists, and it still specifies all six tiers")
else:
    report("FAIL", "the tiered-docs rule and the project-docs skill it names have not drifted")
    print(f"          {'; '.join(docs_drift)}")

# --- scope's go-ahead clause closes the no-plan-mode delegation gap --------------------------
# delegate only fires on ExitPlanMode. Auto and accept-edits sessions never cross that
# boundary - and house-rules.md says the delegation rule covers them anyway - so a go-ahead
# typed into an ordinary session used to get no delegation reminder at all. The prompt text is
# the only stateless place to notice it.
def scope_text(prompt):
    payload = json.dumps(
        {"session_id": "verify", "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    )
    code, out, err = run_hook("scope", payload)
    try:
        return code, json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return code, ""


goahead = []
for prompt in ("go ahead", "implement it in two groups", "do it", "proceed", "ship it",
               "make the changes", "apply those fixes", "execute the plan"):
    code, text = scope_text(prompt)
    if code != 0:
        goahead.append(f"{prompt!r} exited {code} - scope must never exit non-zero")
    if "@house-rules:executor" not in text:
        goahead.append(f"{prompt!r} is a go-ahead but got no delegation clause")
for prompt in ("what does this function do?", "explain the guard handler",
               "why did the suite fail?"):
    code, text = scope_text(prompt)
    if "@house-rules:executor" in text:
        goahead.append(f"{prompt!r} is a question, not a go-ahead, but got the clause")
if not goahead:
    report("PASS", "scope adds the delegation clause on a go-ahead and not on a question")
    print("          closes the gap where delegate never fires outside plan mode")
else:
    report("FAIL", "scope adds the delegation clause on a go-ahead and not on a question")
    for g in goahead:
        print(f"          {g}")

# The clause restates the rule, so it is drift-checked in both directions like the delegate
# reminder - and it must never be able to take the prompt down with it.
clause_drift = []
_, goahead_text = scope_text("go ahead and implement it")
for phrase in ("@house-rules:executor", "proactiv", "one file", "three steps or fewer"):
    if phrase.lower() not in goahead_text.lower():
        clause_drift.append(f"{phrase!r} missing from the emitted go-ahead clause")
    if phrase.lower() not in rules_text.lower():
        clause_drift.append(f"{phrase!r} missing from rules/house-rules.md")
for label, payload in (
    ("empty payload", ""),
    ("unparseable payload", "not json {{{ go ahead"),
    ("no prompt field", '{"session_id":"v","hook_event_name":"UserPromptSubmit"}'),
    ("prompt field with an escaped quote", '{"prompt":"go ahead \\"now\\" implement it"}'),
):
    code, out, err = run_hook("scope", payload)
    if code != 0:
        clause_drift.append(f"{label} exited {code} - this ERASES the user's prompt")
    if "additionalContext" not in out:
        clause_drift.append(f"{label} emitted no reminder at all: {out[:80]!r}")
if not clause_drift:
    report("PASS", "the go-ahead clause matches the rules and cannot erase a prompt")
    print("          same phrases as house-rules.md; every failure path still exits 0 with a reminder")
else:
    report("FAIL", "the go-ahead clause matches the rules and cannot erase a prompt")
    for c in clause_drift:
        print(f"          {c}")

# --- announce / verdict: a delegation says which agent, which model, which digest -------------
# Judged against hand-written transcript fixtures, not whatever this session happens to have
# produced - the same reasoning as the branch fixtures above. A suite that reads the real
# ~/.claude tree passes or fails on the developer's history rather than on the handler.
_SUB_ROOT = tempfile.mkdtemp(prefix="house-rules-subagent-")
atexit.register(shutil.rmtree, _SUB_ROOT, True)


def _transcript(agent_id, lines):
    d = os.path.join(_SUB_ROOT, "sess1", "subagents")
    if not os.path.isdir(d):
        os.makedirs(d)
    path = os.path.join(d, "agent-%s.jsonl" % agent_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _assistant(model=None, content=None):
    msg = {"role": "assistant", "content": content if content is not None else []}
    if model:
        msg["model"] = model
    return json.dumps({"type": "assistant", "message": msg})


_transcript("sonnet", [json.dumps({"type": "user"}), _assistant("claude-sonnet-4-5-20250929"),
                       _assistant("claude-sonnet-4-5-20250929")])
_transcript("opus", [_assistant("claude-opus-5")])
_transcript("nomodel", [_assistant()])
_transcript("notools", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I've launched the fix."}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I'll report back once it's done."}]),
])
_transcript("deferral", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Edit"}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "text", "text": "I'll report back shortly."}]),
])
_transcript("normal", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Edit"}]),
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "name": "Bash"},
                                               {"type": "text", "text": "Done - ran the tests, all green."}]),
])
_PARENT = os.path.join(_SUB_ROOT, "sess1.jsonl")
with open(_PARENT, "w", encoding="utf-8") as _f:
    _f.write("")


def sub_payload(**kw):
    base = {"session_id": "sess1", "transcript_path": _PARENT}
    base.update(kw)
    return json.dumps(base)


# announce names the agent, what it DECLARES, the plugin version and the digest fingerprint.
code, out, err = run_hook("announce", sub_payload(
    hook_event_name="SubagentStart", agent_type="house-rules:executor", agent_id="x1", effort="low"
))
ann = []
if code != 0:
    ann.append(f"exit {code}, must never be non-zero")
for needle in ("house-rules:executor", "declared model sonnet", "digest ", "house-rules 2."):
    if needle not in out:
        ann.append(f"announce output does not mention {needle!r}")
if not ann:
    report("PASS", "announce reports the agent, its declared model and the digest it carries")
    print(f"          {out[:150]}")
else:
    report("FAIL", "announce reports the agent, its declared model and the digest it carries")
    for a in ann:
        print(f"          {a}")

# The declared model is READ FROM the agent file, not hardcoded in hook.py - otherwise the
# line is hook.py's claim about the agent rather than a report of what actually shipped.
_src = read(HOOK)
_decl = _src[_src.index("def _declared("):_src.index("def _plugin_version(")]
litdrift = []
if "_read_text(path)" not in _decl:
    litdrift.append("_declared does not read the agent file")
if not re.search(r'r"\^model:', _decl):
    litdrift.append("_declared does not parse the frontmatter model field")
for lit in ('"sonnet"', "'sonnet'", '"opus"', '"haiku"'):
    if lit in _decl:
        litdrift.append(f"_declared hardcodes {lit}, so the line is a claim, not a report")
if not litdrift:
    report("PASS", "announce reads the declared model from the agent file, not a literal")
    print("          the value comes from agents/<name>.md frontmatter, so it reports what shipped")
else:
    report("FAIL", "announce reads the declared model from the agent file, not a literal")
    for l in litdrift:
        print(f"          {l}")

# An agent the plugin does not ship is the common case, not an error.
code, out, err = run_hook("announce", sub_payload(agent_type="Explore", agent_id="x2"))
if code == 0 and "Explore" in out and "no declaration" in out:
    report("PASS", "announce still names an agent the plugin does not ship")
    print("          reports the agent and says there is no declaration to compare against")
else:
    report("FAIL", "announce still names an agent the plugin does not ship")
    print(f"          exit {code}, out {out[:160]!r}")

# A set model-override env var is the documented way "model: sonnet" is not what runs.
_ovr = dict(os.environ)
_ovr["CLAUDE_CODE_SUBAGENT_MODEL_FORCE"] = "opus"
code, out, err = run_hook("announce", sub_payload(agent_type="house-rules:executor"), env=_ovr)
if "CLAUDE_CODE_SUBAGENT_MODEL_FORCE" in out and "may not be what runs" in out:
    report("PASS", "announce warns when a model-override env var is set")
    print("          names the variable that can silently override the declared model")
else:
    report("FAIL", "announce warns when a model-override env var is set")
    print(f"          out {out[:200]!r}")

# verdict turns the declaration into evidence: the model that actually served the subagent.
code, out, err = run_hook("verdict", sub_payload(
    hook_event_name="SubagentStop", agent_type="house-rules:executor", agent_id="sonnet"
))
if code == 0 and "claude-sonnet-4-5-20250929" in out and "MATCH" in out and "2 assistant turns" in out:
    report("PASS", "verdict reports the model that actually served the subagent")
    print(f"          {out[:150]}")
else:
    report("FAIL", "verdict reports the model that actually served the subagent")
    print(f"          exit {code}, out {out[:200]!r}")

# The case the whole feature exists for: declared Sonnet, actually ran on something else.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="opus"))
if code == 0 and "MISMATCH" in out and "claude-opus-5" in out:
    report("PASS", "verdict reports MISMATCH when the observed model is not the declared one")
    print("          a delegation that did not run on what it declares is now visible")
else:
    report("FAIL", "verdict reports MISMATCH when the observed model is not the declared one")
    print(f"          exit {code}, out {out[:200]!r}")

# The completion-sanity check: zero tool calls across the whole transcript is exactly the
# hollow "stop" that let a duplicate delegation get dispatched.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="notools"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "0 tool calls" in out:
    report("PASS", "verdict flags a completion with zero tool calls")
    print("          a status-update-only finish is now visible, not read as done work")
else:
    report("FAIL", "verdict flags a completion with zero tool calls")
    print(f"          exit {code}, out {out[:200]!r}")

# One tool call present (so the zero-tool-calls path does not fire), but the last message
# still reads like a deferral - the other half of the same signal.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="deferral"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "i'll report back" in out.lower():
    report("PASS", "verdict flags a last message that matches a deferral phrase")
    print("          names the phrase, does not fire the zero-tool-calls branch instead")
else:
    report("FAIL", "verdict flags a last message that matches a deferral phrase")
    print(f"          exit {code}, out {out[:200]!r}")

# An ordinary finish - tool calls present, last message an ordinary summary - must not
# false-positive as a suspicious completion.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="normal"))
if code == 0 and "SUSPICIOUS COMPLETION" not in out:
    report("PASS", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print("          no false positive on a normal completion")
else:
    report("FAIL", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print(f"          exit {code}, out {out[:200]!r}")

# Nothing fails silently: every "I could not tell" path says so, and says what it tried.
quiet = []
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="ghost"))
if code != 0 or "unverified" not in out or "tried:" not in out:
    quiet.append(f"missing transcript: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="nomodel"))
if code != 0 or "unverified" not in out:
    quiet.append(f"transcript with no model field: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", '{"agent_type":"house-rules:executor"}')
if code != 0 or "unverified" not in out:
    quiet.append(f"not enough fields to locate one: exit {code}, out {out[:120]!r}")
for ev in ("announce", "verdict"):
    code, out, err = run_hook(ev, "")
    if code != 0 or "systemMessage" not in out:
        quiet.append(f"{ev} on an empty payload: exit {code}, out {out[:120]!r}")
    code, out, err = run_hook(ev, "not json at all {{{")
    if code != 0:
        quiet.append(f"{ev} on unparseable input: exit {code}")
if not quiet:
    report("PASS", "announce and verdict never go quiet and never exit non-zero")
    print("          every path meaning 'I could not tell' says so, naming what it tried")
else:
    report("FAIL", "announce and verdict never go quiet and never exit non-zero")
    for q in quiet:
        print(f"          {q}")

# One lever, and it is NOT the trace lever - the report is the feature, not a trace.
_off = dict(os.environ)
_off["HOUSE_RULES_DELEGATION"] = "off"
deloff = []
for ev, pl in (("announce", sub_payload(agent_type="house-rules:executor")),
               ("verdict", sub_payload(agent_type="house-rules:executor", agent_id="sonnet"))):
    code, out, err = run_hook(ev, pl, env=_off)
    if out.strip():
        deloff.append(f"{ev} still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
_tron = dict(os.environ)
_tron["HOUSE_RULES_TRACE"] = "off"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="sonnet"), env=_tron)
if "claude-sonnet" not in out:
    deloff.append("HOUSE_RULES_TRACE=off silenced the verdict, which is not a trace")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="notools"), env=_off)
if out.strip():
    deloff.append(f"suspicious-completion report still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:executor", agent_id="notools"), env=_tron)
if "SUSPICIOUS COMPLETION" not in out:
    deloff.append("HOUSE_RULES_TRACE=off silenced the suspicious-completion report, which is not a trace")
if not deloff:
    report("PASS", "HOUSE_RULES_DELEGATION=off silences both, and the trace lever does not")
    print("          the model report is the deliverable, so it is not trace-gated")
else:
    report("FAIL", "HOUSE_RULES_DELEGATION=off silences both, and the trace lever does not")
    for d in deloff:
        print(f"          {d}")

# announce/verdict are registered on the subagent lifecycle events, with no matcher - the
# complaint was "I could not tell which agent", which covers every subagent, not just ours.
subwire = []
_hj = json.loads(read(HOOKS_JSON))["hooks"]
for ev, handler in (("SubagentStart", "announce"), ("SubagentStop", "verdict")):
    entries = _hj.get(ev)
    if not entries:
        subwire.append(f"hooks.json has no {ev} entry")
        continue
    if any("matcher" in e for e in entries):
        subwire.append(f"{ev} is scoped by a matcher, so it misses other agents")
    if not any(handler in h.get("command", "") for e in entries for h in e.get("hooks", [])):
        subwire.append(f"{ev} does not dispatch run.sh {handler}")
if not subwire:
    report("PASS", "announce and verdict are wired to the subagent lifecycle, unmatched")
    print("          hooks.json reports every subagent, not only the two this plugin ships")
else:
    report("FAIL", "announce and verdict are wired to the subagent lifecycle, unmatched")
    for s in subwire:
        print(f"          {s}")

# run.sh's no-interpreter fallback must speak for these two, or a machine with no Python
# reports a delegation as silently fine.
shfall = []
_rs = read(RUN)
for ev in ("announce", "verdict"):
    if ("    %s)" % ev) not in _rs:
        shfall.append(f"run.sh has no per-event fallback for {ev}")
if not shfall:
    report("PASS", "run.sh names announce and verdict in its no-interpreter fallback")
    print("          no working Python still reports that the delegation went unchecked")
else:
    report("FAIL", "run.sh names announce and verdict in its no-interpreter fallback")
    for s in shfall:
        print(f"          {s}")

# --- the "reported update" rule is present, in its own words -----------------------------------
# Not a drift check - nothing else in hook.py restates this rule's wording, since it's a
# verification habit like its two neighbors, not something mechanically checkable at a hook
# boundary. A straightforward presence check, same shape as the standards/tiered-docs ones above.
if "## A reported update is not a completed one" in rules_text:
    report("PASS", "house-rules.md states the reported-update-is-not-a-completed-one rule")
    print("          the rule heading is present")
else:
    report("FAIL", "house-rules.md states the reported-update-is-not-a-completed-one rule")
    print("          heading missing from rules/house-rules.md")

# --- versioncheck: the three-way plugin freshness check -----------------------------------------
# HOUSE_RULES_VC_MARKETPLACE/_GITHUB are test seams so this never touches real network or disk.
with open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), "r", encoding="utf-8") as f:
    _installed_version = json.load(f).get("version", "")


def vc_payload(session_id):
    return json.dumps({"session_id": session_id, "hook_event_name": "SessionStart"})


def vc_env(**overrides):
    e = dict(os.environ)
    e.update(overrides)
    return e


def vc_marker_path(session_id):
    return os.path.join(tempfile.gettempdir(), f"house-rules-outdated-{session_id}.json")


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
# Why this is its own check, not folded into the mismatch check above: docs/systems/verify-suites.md, "Traps".
vc_banner_out = out
banner_ok = (
    "UNTESTED" in vc_banner_out
    and "step-card" in vc_banner_out
    and "stop and wait" in vc_banner_out
    and "permission" in vc_banner_out
)
if banner_ok:
    report("PASS", "the out-of-date banner tells Claude to ask permission to run the update itself, falling back to the card marked UNTESTED, then stop and wait")
    print("          banner carries the ask-permission/run-it-yourself instruction, the card/UNTESTED fallback, and the stop-and-wait instruction")
else:
    report("FAIL", "the out-of-date banner tells Claude to ask permission to run the update itself, falling back to the card marked UNTESTED, then stop and wait")
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

session_c = "vc-guard-consumes"
run_hook(
    "versioncheck",
    vc_payload(session_c),
    vc_env(HOUSE_RULES_VC_MARKETPLACE="99.0.0", HOUSE_RULES_VC_GITHUB="99.0.0"),
)
marker_c = vc_marker_path(session_c)
guard_payload = json.dumps(
    {"session_id": session_c, "tool_name": "Bash", "tool_input": {"command": "ls"}}
)
rc1, out1, err1 = run_hook("guard", guard_payload)
rc2, out2, err2 = run_hook("guard", guard_payload)
ok = (
    "PLUGIN OUT OF DATE" in out1
    and '"permissionDecision":"ask"' in out1
    and "PLUGIN OUT OF DATE" not in out2
    and '"permissionDecision":"ask"' not in out2
    and not os.path.isfile(marker_c)
)
if ok:
    report("PASS", "guard surfaces versioncheck's marker once, on the first shell call, then stops")
    print("          first `ls` call prompts for the stale plugin alone; the second call is silent")
else:
    report("FAIL", "guard surfaces versioncheck's marker once, on the first shell call, then stops")
    print(
        f"          out1={out1[:200]!r} out2={out2[:200]!r} "
        f"marker exists after: {os.path.isfile(marker_c)}"
    )
if os.path.isfile(marker_c):
    os.remove(marker_c)

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
    {"docs/systems/physics.md": "## T\n", "src/a.c": "// see docs/systems/physics.md, Traps\n"},
    ["check"], 0,
    expect_in=["1 line(s) mention docs/systems/", "legacy prose pointers"],
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
_absent = absent_repo_files("docs/Decisions.md", "docs/README.md")
if _absent:
    skip_repo_check(_dr_live, _absent)
else:
    _rc, _out, _err = docref_run(
        ROOT, "check",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/verify.py",
        "--exclude", "claude-house-rules/plugins/house-rules/scripts/docref.py",
    )
    if _rc == 0:
        report("PASS", _dr_live)
        print("          " + [l for l in _out.splitlines() if "pointers found" in l][0])
    else:
        report("FAIL", _dr_live)
        print("          " + _dr_failure_detail(_rc, _out, _err).replace("\n", "\n          "))

print()
print("-" * 32)
if FAILURES == 0 and not SKIPPED:
    print(f"RESULT: PASS - all {STEP} checks passed. The hooks are behaving as written.")
elif FAILURES == 0:
    print(f"RESULT: PASS - {STEP - len(SKIPPED)} of {STEP} checks passed, {len(SKIPPED)} skipped.")
    print("        The hooks are behaving as written. Skipped checks read files that ship in the")
    print("        repo and not in the plugin package, so from an installed copy they are not")
    print("        applicable rather than failing:")
    for t in SKIPPED:
        print(f"          - {t}")
    print("        Run it from a repo checkout to check those too.")
else:
    print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed. See the FAIL lines above.")
    if SKIPPED:
        print(f"        {len(SKIPPED)} more were skipped as repo-only; see the SKIP lines.")
print()
print("Dependencies used by the hooks: run.sh (POSIX sh) + a probed Python interpreter.")
print("No node, no jq required by hook.py itself - stdlib only.")
print("Matching is textual, so a command that merely mentions a tripwire word will also")
print("prompt. That is deliberate - an extra keypress is cheaper than a missed commit.")
print()

sys.exit(0 if FAILURES == 0 else 1)
