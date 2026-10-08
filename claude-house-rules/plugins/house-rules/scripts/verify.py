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
from collections import namedtuple
import json
import os
import pathlib
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
AGENTS_DIR = os.path.join(HERE, "..", "agents")
# The three tier agents and the model each must declare (and, at SubagentStop, actually run on).
TIERS = {"scout": "haiku", "builder": "sonnet", "reviewer": "opus"}
ARCHIVIST = os.path.join(HERE, "..", "agents", "archivist.md")
STYLE = os.path.join(HERE, "..", "output-styles", "handover-cards.md")
TEMPLATE = os.path.join(HERE, "..", "templates", "step-card.html")
DOCSKILL = os.path.join(HERE, "..", "skills", "project-docs", "SKILL.md")
CHATDOC = os.path.join(ROOT, "docs", "claude-ai-instructions.md")
VERIFYDOC = os.path.join(ROOT, "docs", "desktop-verification.md")
ARCHDOC = os.path.join(ROOT, "docs", "architecture.md")

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

# Why SKIP exists and what it's gated on: docs/4-systems/verify-suites.md, "How it works"
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


DETAIL_DIR = os.path.join(HERE, "..", "rules", "detail")
STANDARDS_DIR = os.path.join(HERE, "..", "rules", "standards")


def rules_corpus():
    """house-rules.md (the injected core) plus every rules/detail/*.md file it points to.
    See docs/6-decisions/Decisions.md, 2026-09-22, for why drift checks read this instead of the core alone.
    """
    corpus = read(RULES_FILE)
    if os.path.isdir(DETAIL_DIR):
        for name in sorted(os.listdir(DETAIL_DIR)):
            if name.endswith(".md"):
                corpus += "\n\n" + read(os.path.join(DETAIL_DIR, name))
    return corpus


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
# Simulated spawns in this file must never leave records in the real repository's agent list.
os.environ["HOUSE_RULES_AGENTS_STATE"] = os.path.join(_FIXTURE_ROOT, "default-agents.json")
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


def verbose_env(base=None):
    """The no-op traces ("looked, nothing to do") print only under HOUSE_RULES_TRACE=verbose.
    Cases that assert the decision text run under this env; the default-silent cases do not."""
    e = dict(os.environ if base is None else base)
    e["HOUSE_RULES_TRACE"] = "verbose"
    return e


def env_in(project_dir, **extra):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = project_dir
    e.update(extra)
    return e


# --- docstiers fixtures ------------------------------------------------------------------
_DOCS_TIER_FOLDER_FILES = [
    "1-landing/README.md", "2-roadmap/Roadmap.md", "3-state/ProjectState.md",
    "5-today/Today.md", "6-decisions/Decisions.md",
]
_DOCS_OLD_TIER_FILE_NAMES = ["README.md", "Roadmap.md", "ProjectState.md", "Today.md", "Decisions.md"]


def _docstiers_repo(name, all_tiers, git_config_text=None, config_is_dir=False, no_git=False, old_layout=False):
    path = os.path.join(_FIXTURE_ROOT, name)
    docs = os.path.join(path, "docs")
    if old_layout:
        os.makedirs(os.path.join(docs, "systems"), exist_ok=True)
        if all_tiers:
            for fname in _DOCS_OLD_TIER_FILE_NAMES:
                with open(os.path.join(docs, fname), "w", encoding="utf-8") as f:
                    f.write("x\n")
            with open(os.path.join(docs, "systems", "core.md"), "w", encoding="utf-8") as f:
                f.write("x\n")
    else:
        os.makedirs(os.path.join(docs, "4-systems"), exist_ok=True)
        if all_tiers:
            for rel in _DOCS_TIER_FOLDER_FILES:
                full = os.path.join(docs, *rel.split("/"))
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write("x\n")
            with open(os.path.join(docs, "4-systems", "core.md"), "w", encoding="utf-8") as f:
                f.write("x\n")
    if not no_git:
        git_dir = os.path.join(path, ".git")
        os.makedirs(git_dir, exist_ok=True)
        if config_is_dir:
            os.makedirs(os.path.join(git_dir, "config"), exist_ok=True)
        elif git_config_text is not None:
            with open(os.path.join(git_dir, "config"), "w", encoding="utf-8") as f:
                f.write(git_config_text)
    return path


DOCSTIERS_COMPLETE = _docstiers_repo(
    "docstiers-complete", True, '[remote "origin"]\n\turl = https://github.com/Ajw2003/repo.git\n'
)
DOCSTIERS_OWNED = _docstiers_repo(
    "docstiers-owned", False, '[remote "origin"]\n\turl = https://github.com/Ajw2003/repo.git\n'
)
DOCSTIERS_NOT_OWNED = _docstiers_repo(
    "docstiers-not-owned", False, '[remote "origin"]\n\turl = https://github.com/SomeoneElse/repo.git\n'
)
DOCSTIERS_SSH_OWNED = _docstiers_repo(
    "docstiers-ssh-owned", False, '[remote "origin"]\n\turl = git@github.com:Ajw2003/repo.git\n'
)
DOCSTIERS_NO_GIT = _docstiers_repo("docstiers-no-git", False, no_git=True)
DOCSTIERS_GARBAGE_CONFIG = _docstiers_repo(
    "docstiers-garbage-config", False, "not an ini file\njust some random text\n"
)
DOCSTIERS_UNREADABLE_CONFIG = _docstiers_repo("docstiers-unreadable-config", False, config_is_dir=True)
DOCSTIERS_OLD_LAYOUT = _docstiers_repo(
    "docstiers-old-layout", True, '[remote "origin"]\n\turl = https://github.com/Ajw2003/repo.git\n',
    old_layout=True,
)


# --- inject, profile and standards each stay under the per-hook additionalContext limit ------
# Margins per docs/6-decisions/Decisions.md, 2026-09-22 (second entry): inject 9,000, profile/standards 9,500,
# each measured on the REAL emitted output, not source file size. profile is measured with
# docs/example-environment.md standing in for a recorded profile.
EXAMPLE_ENV = os.path.join(ROOT, "docs", "example-environment.md")


def _additional_context(event, payload="", env=None):
    code, out, err = run_hook(event, payload, env=env)
    try:
        parsed = json.loads(out)
        return code, parsed["hookSpecificOutput"]["additionalContext"], err
    except Exception as exc:
        return code, None, f"{err}\ncould not parse {event} output as JSON: {exc}"


_size_cases = [
    ("inject", 9_700, env_in(ROOT)),
    ("standards", 9_500, env_in(ROOT)),
    ("profile", 9_500, env_in(ROOT, HOUSE_RULES_ENV_FILE=EXAMPLE_ENV)),
    ("docstiers", 9_500, env_in(DOCSTIERS_NOT_OWNED)),
]
for _event, _margin, _env in _size_cases:
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


# --- guard cases: 29 commands ---------------------------------------------------------------
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
        "Never hide work: it stays visible, reachable and readable",
        'Start-Process powershell -WindowStyle Hidden -ArgumentList "-File build.ps1"',
    ),
    (
        "ask",
        "Never hide work: it stays visible, reachable and readable",
        "npm run dev > dev.log 2>&1 &",
    ),
    ("ask", "Never hide work: it stays visible, reachable and readable", "nohup ./long-task.sh"),
    # #85: a wait piped through tail/head shows nothing until it exits.
    (
        "ask",
        "Never hide work: it stays visible, reachable and readable",
        "until grep -q done status.txt; do sleep 5; done | tail -5",
    ),
    ("ask", "Never hide work: it stays visible, reachable and readable", "timeout 600 ./run_tests.sh | head -40"),
    ("pass", None, "git log | head -5"),
    ("pass", None, "cat build.log | tail -50"),
    ("pass", None, "python sleepy.py | tail"),
    (
        "ask",
        "Never hide work: it stays visible, reachable and readable",
        "Start-Job -ScriptBlock { ./build.ps1 }",
    ),
    ("ask", "Never take a destructive action without checking first", "rm -rf node_modules"),
    (
        "ask",
        "Never take a destructive action without checking first",
        "rm styles.css",
    ),
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

# --- #153: destructive git steps run unasked only on my branch with the work saved elsewhere ---
_sv_root = os.path.join(_FIXTURE_ROOT, "saved")
_sv_remote, _sv_repo = os.path.join(_sv_root, "remote.git"), os.path.join(_sv_root, "work")
os.makedirs(_sv_repo, exist_ok=True)


def _sv_git(*args, cwd=_sv_repo):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


_sv_git("init", "-q", "--bare", _sv_remote, cwd=_sv_root)
_sv_git("init", "-q")
_sv_git("switch", "-q", "-c", "claude/saved-topic")
with open(os.path.join(_sv_repo, "f.txt"), "w") as _f:
    _f.write("one\n")
_sv_git("add", "f.txt")
_sv_git("commit", "-q", "-m", "one")
_sv_git("remote", "add", "origin", _sv_remote)
_sv_git("push", "-q", "-u", "origin", "claude/saved-topic")


def _sv_guard(cmd):
    code, out, err = run_hook("guard", payload_for(cmd), env=verbose_env(env_in(_sv_repo)))
    return ("ask" if '"permissionDecision":"ask"' in out else "pass"), out


def _sv_case(title, ok, detail):  # commit_case is defined further down this file
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


_sv_fail = []
for _cmd in ("git reset --hard HEAD", "git rebase -i HEAD", "git revert --no-edit HEAD", "git restore f.txt",
             "git checkout -- f.txt"):
    _got, _out = _sv_guard(_cmd)
    if _got != "pass" or "every commit on a remote" not in _out:
        _sv_fail.append("%s: %s %r" % (_cmd, _got, _out[:120]))
_sv_case(
    "guard: on a claude/ branch with a clean tree and every commit pushed, reset/rebase/revert/restore run unasked",
    not _sv_fail, "; ".join(_sv_fail) or "5 commands passed, each trace names the saved-elsewhere check",
)
_sv_fail = []
for _cmd in ("git push --force-with-lease", "git clean -fdx", "git stash drop", "git merge main", "rm f.txt"):
    if _sv_guard(_cmd)[0] != "ask":
        _sv_fail.append(_cmd)
_sv_case(
    "guard: even with the work saved, force-push, clean, stash drop, merge and rm still ask",
    not _sv_fail, "did not ask: %s" % ", ".join(_sv_fail) if _sv_fail else "all 5 asked",
)
with open(os.path.join(_sv_repo, "f.txt"), "a") as _f:
    _f.write("uncommitted\n")
_sv_dirty = _sv_guard("git reset --hard HEAD")
_sv_git("checkout", "--", "f.txt")
with open(os.path.join(_sv_repo, "f.txt"), "a") as _f:
    _f.write("two\n")
_sv_git("commit", "-q", "-am", "two")
_sv_unpushed = _sv_guard("git reset --hard HEAD~1")
_sv_case(
    "guard: an uncommitted change or an unpushed commit makes reset ask, and the prompt says which",
    _sv_dirty[0] == "ask" and "1 uncommitted or untracked file would be lost" in _sv_dirty[1]
    and _sv_unpushed[0] == "ask" and "1 commit on this branch is not on any remote" in _sv_unpushed[1],
    "dirty %r | unpushed %r" % (_sv_dirty[1][-160:], _sv_unpushed[1][-160:]),
)
_sv_git("push", "-q")
_sv_git("switch", "-q", "-c", "main")
_sv_git("push", "-q", "-u", "origin", "main")
_sv_theirs = _sv_guard("git reset --hard HEAD")
_sv_case(
    "guard: on aj's branch, reset asks even with a clean tree and everything pushed",
    _sv_theirs[0] == "ask" and "not a `claude/` branch" in _sv_theirs[1], "out %r" % (_sv_theirs[1][-160:],),
)

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

# --- guard's commit-time docs-tier reminder: real git fixtures, since this path itself uses -----
# git diff --cached, unlike the rest of guard which stays subprocess-free.
if shutil.which("git"):
    def _git(d, *args):
        subprocess.run(
            ["git", "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )

    def _docs_guard_repo(name, branch, files, staged):
        d = os.path.join(_FIXTURE_ROOT, name)
        os.makedirs(d)
        _git(d, "init", "-q")
        _git(d, "config", "user.email", "t@t.com")
        _git(d, "config", "user.name", "t")
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(d, "add", "README.md")
        _git(d, "commit", "-q", "-m", "init")
        if branch != "main" and branch != "master":
            _git(d, "checkout", "-q", "-b", branch)
        for path, content in files.items():
            full = os.path.join(d, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        if staged:
            _git(d, "add", *staged)
        return d

    DOCSGUARD_CLAUDE_SOURCE_ONLY = _docs_guard_repo(
        "docsguard-claude-source-only", "claude/topic", {"a.py": "print(1)\n"}, ["a.py"]
    )
    DOCSGUARD_CLAUDE_SOURCE_AND_DOCS = _docs_guard_repo(
        "docsguard-claude-source-and-docs", "claude/topic",
        {"a.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, ["a.py", "docs/ProjectState.md"],
    )
    DOCSGUARD_CLAUDE_CONFIG_ONLY = _docs_guard_repo(
        "docsguard-claude-config-only", "claude/topic", {"config.json": "{}\n"}, ["config.json"]
    )
    DOCSGUARD_MAIN_SOURCE_ONLY = _docs_guard_repo(
        "docsguard-main-source-only", "main", {"a.py": "print(1)\n"}, ["a.py"]
    )

    docsguard_cases = [
        (
            "a claude/ branch commit with a staged source file and nothing under docs/ gets a "
            "docs reminder, still allowed",
            DOCSGUARD_CLAUDE_SOURCE_ONLY, "allow", True,
        ),
        (
            "a claude/ branch commit with a staged source file AND a staged docs/ file gets no "
            "reminder",
            DOCSGUARD_CLAUDE_SOURCE_AND_DOCS, "allow", False,
        ),
        (
            "a claude/ branch commit with no staged source file (config only) gets no reminder",
            DOCSGUARD_CLAUDE_CONFIG_ONLY, "allow", False,
        ),
        (
            "a non-owned branch commit with a staged source file gets the docs reason appended "
            "to guard's existing prompt",
            DOCSGUARD_MAIN_SOURCE_ONLY, "ask", True,
        ),
    ]
    for title, repo, expect_decision, expect_reminder in docsguard_cases:
        code, out, err = run_hook("guard", payload_for('git commit -m "wip"'), env=env_in(repo))
        problems = []
        if code != 0:
            problems.append(f"exit {code}, must never be non-zero")
        if expect_decision == "allow":
            if '"permissionDecision":"ask"' in out:
                problems.append("guard asked, expected a silent/allow decision")
        else:
            if '"permissionDecision":"ask"' not in out:
                problems.append("guard did not ask, expected it to (non-owned branch always asks on a commit)")
        has_reminder = "documentation goes in tiers" in out.lower() or "Documentation goes in tiers" in out
        if expect_reminder and not has_reminder:
            problems.append("no docs-tier reminder in the output, expected one")
        if not expect_reminder and has_reminder:
            problems.append("a docs-tier reminder fired, expected none")
        if not problems:
            report("PASS", title)
            print(f"          {out[:200]}")
        else:
            report("FAIL", title)
            for p in problems:
                print(f"          {p}")

    # git missing/unusable: guard's decision must be UNCHANGED (still exempted-allow on a
    # claude/ branch commit), with a "could not tell" note replacing the reminder, not silence.
    _no_git_env = env_in(DOCSGUARD_CLAUDE_SOURCE_ONLY)
    _no_git_env["PATH"] = _FIXTURE_ROOT  # a directory with no git binary in it
    code, out, err = run_hook("guard", payload_for('git commit -m "wip"'), env=_no_git_env)
    if (
        code == 0
        and '"permissionDecision":"ask"' not in out
        and "mine to commit on" in out
        and "could not tell" in out
    ):
        report("PASS", "a missing git binary leaves guard's own decision unchanged, and says so")
        print(f"          {out[:200]}")
    else:
        report("FAIL", "a missing git binary leaves guard's own decision unchanged, and says so")
        print(f"          exit {code}, out {out[:200]!r}")

    # A command naming another repo: guard already prompts (RULE_COMMIT); the docs check must
    # not try to resolve that other repo's staged files, and says it could not tell rather than
    # silently assuming either answer.
    code, out, err = run_hook(
        "guard",
        payload_for('git -C /some/other/repo commit -m "wip"'),
        env=env_in(DOCSGUARD_CLAUDE_SOURCE_ONLY),
    )
    if '"permissionDecision":"ask"' in out and "could not tell" in out.lower() and "another repo" in out:
        report("PASS", "a -C/--git-dir commit says the docs check could not tell, not another repo's answer")
        print(f"          {out[:250]}")
    else:
        report("FAIL", "a -C/--git-dir commit says the docs check could not tell, not another repo's answer")
        print(f"          out {out[:250]!r}")

    # --- what a commit will ACTUALLY include, not just what is already staged -----------------
    # doc-ref c79f docs/6-decisions/Decisions.md: guard fires before the command it judges runs, so a
    # docs-only-staged-right-now check misses an add-then-commit or an -a/-am commit entirely.
    DOCSGUARD_ADD_THEN_COMMIT_SOURCE = _docs_guard_repo(
        "docsguard-add-then-commit-source", "claude/topic", {"f.py": "print(1)\n"}, staged=[]
    )
    DOCSGUARD_ADD_THEN_COMMIT_WITH_DOCS = _docs_guard_repo(
        "docsguard-add-then-commit-with-docs", "claude/topic",
        {"f.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, staged=[],
    )
    DOCSGUARD_ADD_DOT_WITH_DOCS = _docs_guard_repo(
        "docsguard-add-dot-with-docs", "claude/topic",
        {"f.py": "print(1)\n", "docs/ProjectState.md": "state\n"}, staged=[],
    )

    def _docs_guard_repo_with_tracked_change(name):
        # -am needs a file that is TRACKED and modified, not staged - a plain new file (never
        # committed) is not what -a stages.
        d = os.path.join(_FIXTURE_ROOT, name)
        os.makedirs(d)
        _git(d, "init", "-q")
        _git(d, "config", "user.email", "t@t.com")
        _git(d, "config", "user.name", "t")
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("x\n")
        _git(d, "add", "README.md")
        _git(d, "commit", "-q", "-m", "init")
        _git(d, "checkout", "-q", "-b", "claude/topic")
        with open(os.path.join(d, "tracked.py"), "w", encoding="utf-8") as f:
            f.write("print(1)\n")
        _git(d, "add", "tracked.py")
        _git(d, "commit", "-q", "-m", "add tracked")
        with open(os.path.join(d, "tracked.py"), "w", encoding="utf-8") as f:
            f.write("print(2)\n")
        return d

    DOCSGUARD_AM_SOURCE_ONLY = _docs_guard_repo_with_tracked_change("docsguard-am-source-only")
    DOCSGUARD_QUOTED_PATH = _docs_guard_repo(
        "docsguard-quoted-path", "claude/topic", {"my file.py": "print(1)\n"}, staged=[]
    )

    effective_cases = [
        (
            "git add f.py && git commit -m f",
            "add-then-commit of a new source file, nothing under docs/, gets the reminder",
            DOCSGUARD_ADD_THEN_COMMIT_SOURCE, True,
        ),
        (
            "git add f.py docs/ProjectState.md && git commit -m f",
            "add-then-commit that also adds a docs/ path gets no reminder",
            DOCSGUARD_ADD_THEN_COMMIT_WITH_DOCS, False,
        ),
        (
            "git add . && git commit -m f",
            "git add . with an untracked docs/ change present gets no reminder",
            DOCSGUARD_ADD_DOT_WITH_DOCS, False,
        ),
        (
            "git commit -am f",
            "-am against a tracked, modified source file with nothing under docs/ gets the reminder",
            DOCSGUARD_AM_SOURCE_ONLY, True,
        ),
        (
            'git add "my file.py" && git commit -m x',
            "a quoted add path with a space is tokenized as one argument (shlex), and gets the reminder",
            DOCSGUARD_QUOTED_PATH, True,
        ),
    ]
    for cmd, title, repo, expect_reminder in effective_cases:
        code, out, err = run_hook("guard", payload_for(cmd), env=env_in(repo))
        has_reminder = "documentation goes in tiers" in out.lower()
        if code == 0 and has_reminder == expect_reminder:
            report("PASS", title)
            print(f"          {out[:200]}")
        else:
            report("FAIL", title)
            print(f"          exit {code}, expected reminder={expect_reminder}, out {out[:250]!r}")

    # Unbalanced quotes in an add statement: shlex.split raises ValueError, which must read as
    # "could not tell" - never a guess, and never a change to guard's own decision.
    code, out, err = run_hook(
        "guard", payload_for('git add "unbalanced.py && git commit -m x'), env=env_in(DOCSGUARD_QUOTED_PATH)
    )
    if code == 0 and '"permissionDecision":"ask"' not in out and "mine to commit on" in out and "could not tell" in out.lower():
        report("PASS", "an add statement with unbalanced quotes is a could-not-tell, not a guess")
        print(f"          {out[:200]}")
    else:
        report("FAIL", "an add statement with unbalanced quotes is a could-not-tell, not a guess")
        print(f"          exit {code}, out {out[:250]!r}")
else:
    report("SKIP", "guard's commit-time docs-tier reminder (real git fixtures)")
    print("          no git binary on PATH")

print()

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
code, out, err = run_hook("guard", desc_payload, env=verbose_env())
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

print()

# --- guardwrite: a Write that would replace an existing file's entire contents asks first ----
RULE_EDIT_IN_PLACE = "Edit in place; a full rewrite is a delete, not an edit"


def guardwrite_payload(file_path, content="new content\n"):
    return json.dumps(
        {
            "session_id": "verify",
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


_gw_dir = tempfile.mkdtemp(prefix="house-rules-guardwrite-")
atexit.register(shutil.rmtree, _gw_dir, True)
_gw_existing = os.path.join(_gw_dir, "styles.css")
with open(_gw_existing, "w", encoding="utf-8") as f:
    f.write("body { color: red; }\n.header { margin: 0; }\n")
_gw_new = os.path.join(_gw_dir, "new-file.css")

code, out, err = run_hook("guardwrite", guardwrite_payload(_gw_existing))
if (
    '"permissionDecision":"ask"' in out
    and RULE_EDIT_IN_PLACE in out
    and os.path.basename(_gw_existing) in out
    and "2 existing line(s)" in out
):
    report("PASS", "Write to a file that already exists asks before replacing it")
    print("          names the file, cites the rule, and counts the discarded lines")
else:
    report("FAIL", "Write to a file that already exists asks before replacing it")
    print(f"          got: {out}")

code, out, err = run_hook("guardwrite", guardwrite_payload(_gw_new))
if '"permissionDecision"' not in out:
    report("PASS", "Write to a brand-new path does not ask - there is nothing to discard yet")
    print("          no prompt for a file that does not already exist")
else:
    report("FAIL", "Write to a brand-new path does not ask - there is nothing to discard yet")
    print(f"          got: {out}")

code, out, err = run_hook("guardwrite", "")
if code == 0 and '"permissionDecision"' not in out:
    report("PASS", "guardwrite with an empty payload does not crash or silently allow-by-default")
    print("          exits 0 with no permission decision, same contract as guard's empty case")
else:
    report("FAIL", "guardwrite with an empty payload does not crash or silently allow-by-default")
    print(f"          exit code {code}, got: {out}")

nofile_payload = json.dumps({"session_id": "verify", "tool_name": "Write", "tool_input": {"content": "x"}})
code, out, err = run_hook("guardwrite", nofile_payload)
if code == 0 and '"permissionDecision"' not in out:
    report("PASS", "guardwrite with no file_path field does not ask")
    print("          nothing to resolve on disk, so nothing to check")
else:
    report("FAIL", "guardwrite with no file_path field does not ask")
    print(f"          exit code {code}, got: {out}")

# fail-closed: an internal error in guardwrite must BLOCK, not shrug - same contract as guard,
# since this is also a PreToolUse hook that can stop a tool call from running.
crash_snippet_gw = (
    "import sys, hook\n"
    "def boom():\n"
    "    raise OSError('simulated stdin failure')\n"
    "hook.read_payload = boom\n"
    "sys.exit(hook.main(['hook.py', 'guardwrite']))\n"
)
proc = subprocess.run(
    [sys.executable, "-c", crash_snippet_gw], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
code, out, err = proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode(
    "utf-8", "replace"
)
if code == 2 and err.strip() and not out.strip():
    report("PASS", "guardwrite that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          said: {err.strip().splitlines()[0]}")
else:
    report("FAIL", "guardwrite that hits an internal error exits 2 (blocking) and explains itself on stderr")
    print(f"          exit code was {code}; stdout={out!r} stderr={err!r}")

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
    "Never hide work: it stays visible, reachable and readable",
    "Commit constantly on my own branches, never on theirs",
    "Never take a destructive action without checking first",
    "Edit in place; a full rewrite is a delete, not an edit",
]:
    if h not in out:
        missing.append(h)
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

# --- the artifact reminder fires on documents written outside a project ---------------------
def art_case(expect, title, file_path, extra="", contains=None, excludes=None):
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    )
    if extra:
        obj = json.loads(payload)
        obj["tool_input"].update(extra)
        payload = json.dumps(obj)
    code, out, err = run_hook("artifact", payload, env=verbose_env())
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
_art_rules_text = rules_corpus()
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

rules_text = rules_corpus()
# The scope reminder's own drift check now lives in the RESTATEMENTS table below (see
# "the restatement table" further down this file), which checks it - and every other
# restatement - both ways: rules corpus and emitted text, not the rules corpus alone.

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

# --- CLAUDE.md stays a real pointer, not a growing document ----------------------------------
CLAUDE_MD_BYTE_LIMIT = 4_000
_absent = absent_repo_files("CLAUDE.md")
if _absent:
    skip_repo_check(f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes", _absent)
elif not os.path.isfile(root_claude):
    report("PASS", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
    print("          no CLAUDE.md at the repo root")
else:
    _claude_bytes = len(read(root_claude).encode("utf-8"))
    if _claude_bytes <= CLAUDE_MD_BYTE_LIMIT:
        report("PASS", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
        print(f"          {_claude_bytes} bytes <= {CLAUDE_MD_BYTE_LIMIT}")
    else:
        report("FAIL", f"CLAUDE.md stays at or under {CLAUDE_MD_BYTE_LIMIT} bytes")
        print(f"          {_claude_bytes} bytes > {CLAUDE_MD_BYTE_LIMIT} - it has grown past a pointer again")

# --- the recorded machine profile actually reaches the session -------------------------------
# A real rules/environment.md fixture, not a coincidental phrase in the rules body - the rules
# split (docs/6-decisions/Decisions.md, 2026-09-22) moved the PowerShell/Git-Bash path-notation example this
# used to piggyback on out of the injected text on purpose, so this now supplies its own fixture.
_envfixture = os.path.join(_FIXTURE_ROOT, "environment.md")
with open(_envfixture, "w", encoding="utf-8") as _f:
    _f.write("# This machine (hand-verified)\n\nShell: PowerShell\nsh: NOT on PATH\n")
code, out, err = run_hook("profile", "", env=env_in(ROOT, HOUSE_RULES_ENV_FILE=_envfixture))
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
code, out, err = run_hook("profile", "", env=env)
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
code, out, err = run_hook("profile", "", env=env)
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
code, out, err = run_hook("profile", "", env=env)
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
code, out, err = run_hook("profile", "", env=env)
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
_, handover_out, _ = run_hook("profile", "", env=env)
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
    code, out, err = run_hook("runnable", json.dumps(obj), env=verbose_env())
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
    code, out, err = run_hook("runnable", json.dumps(obj), env=verbose_env())
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

# The compile-verification note's drift check is a row in the RESTATEMENTS table below.

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

# The runnable note's drift check is a row in the RESTATEMENTS table below.

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
if '"hookEventName":"PostToolUse"' in out and "@house-rules:builder" in out:
    report("PASS", "delegate reminds Claude to hand the plan to the builder subagent")
    print("          names @house-rules:builder and carries the right hookEventName")
else:
    report("FAIL", "delegate reminds Claude to hand the plan to the builder subagent")
    print(f"          got: {out}")

# --- delegate is wired to ExitPlanMode, not just present in hook.py ---------------------------
hooks_json_text = read(HOOKS_JSON)
if '"matcher": "ExitPlanMode"' in hooks_json_text and 'run.sh\\" delegate' in hooks_json_text:
    report("PASS", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json wires ExitPlanMode to run.sh delegate")
else:
    report("FAIL", "delegate is registered on PostToolUse with matcher ExitPlanMode")
    print("          hooks.json does not wire ExitPlanMode to run.sh delegate")

# The delegate reminder's drift check (including the worktree-isolation mandate it carries) is
# a row in the RESTATEMENTS table below. Why this must be bidirectional: docs/4-systems/
# verify-suites.md, Traps ("Most drift checks run in one direction only") and
# docs/architecture.md, "Why the delegation kept not happening".

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
    code, out, err = run_hook(event, payload, env=verbose_env())
    if code == 0 and '"systemMessage"' in out and needle in out:
        report("PASS", f"{event} traces its decision on {why}")
        print(f"          says what it looked at and what it concluded; names {needle!r}")
    else:
        report("FAIL", f"{event} traces its decision on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")

# --- the default is silent on "looked, nothing to do"; verbose restores it; "could not tell" stays loud
_dflt = dict(os.environ)
_dflt.pop("HOUSE_RULES_TRACE", None)
for event, payload, needle, why in trace_cases:
    code, out, err = run_hook(event, payload, env=_dflt)
    if code == 0 and not out.strip():
        report("PASS", f"{event} is silent by default on {why}")
        print("          no-op decision, nothing emitted (HOUSE_RULES_TRACE unset)")
    else:
        report("FAIL", f"{event} is silent by default on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
    code, out, err = run_hook(event, payload, env=verbose_env())
    if code == 0 and needle in out and '"systemMessage"' in out:
        report("PASS", f"HOUSE_RULES_TRACE=verbose restores the {event} trace on {why}")
    else:
        report("FAIL", f"HOUSE_RULES_TRACE=verbose restores the {event} trace on {why}")
        print(f"          exit {code}, got: {out[:160]!r}")
for event, payload, needle in (
    ("guard", "", "guard: empty payload"),
    ("guardwrite", "", "guardwrite: empty payload"),
    ("guardwrite", json.dumps({"tool_input": {}}), "no file_path field"),
):
    code, out, err = run_hook(event, payload, env=_dflt)
    if code == 0 and needle in out and '"systemMessage"' in out:
        report("PASS", f"{event} still prints its 'could not tell' trace by default ({needle})")
    else:
        report("FAIL", f"{event} still prints its 'could not tell' trace by default ({needle})")
        print(f"          exit {code}, got: {out[:160]!r}")
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
if not out.strip() and "never announces its own compliance" in rules_corpus():
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

# --- run.sh's interpreter cache (2.48.0) -------------------------------------------------------
# A copy of run.sh sits next to a stub hook.py that just prints "ran", so the cache file lands in
# a throwaway directory and never in the real plugin.
def _cache_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


def _cache_dir():
    d = tempfile.mkdtemp(prefix="house-rules-cache-", dir=_FIXTURE_ROOT)
    shutil.copy(RUN, os.path.join(d, "run.sh"))
    with open(os.path.join(d, "hook.py"), "w", encoding="utf-8") as f:
        f.write("print('ran')\n")
    return d


def _cache_run(d, **env_extra):
    e = dict(os.environ)
    e.pop("HOUSE_RULES_PYTHON", None)
    e["HOUSE_RULES_DEBUG"] = "1"
    e.update(env_extra)
    # forward slashes: run.sh derives HERE from $0 and splits only on "/"
    return run_shell([os.path.join(d, "run.sh").replace("\\", "/"), "anyevent"], env=e)


def _cache_text(d):
    try:
        with open(os.path.join(d, ".python-cache"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


_cd = _cache_dir()
_c1, _o1, _e1 = _cache_run(_cd)
_first = _cache_text(_cd)
_cache_case(
    "run.sh: the first run probes and writes the cache",
    _c1 == 0 and "ran" in _o1 and "cache=yes" not in _e1 and bool(_first),
    "exit %d, out %r, cache %r" % (_c1, _o1.strip(), _first),
)
_c2, _o2, _e2 = _cache_run(_cd)
_cache_case(
    "run.sh: the second run uses the cache and skips probing",
    _c2 == 0 and "ran" in _o2 and "cache=yes" in _e2 and _cache_text(_cd) == _first,
    "exit %d, out %r, stderr %r" % (_c2, _o2.strip(), _e2.strip()[:100]),
)
with open(os.path.join(_cd, ".python-cache"), "w", encoding="utf-8") as f:
    f.write("no-such-interpreter-xyz\n")
_c3, _o3, _e3 = _cache_run(_cd)
_cache_case(
    "run.sh: a stale cache (missing binary) is dropped, the probe order runs, and the cache is rewritten",
    _c3 == 0 and "ran" in _o3 and "cache=yes" not in _e3 and _cache_text(_cd) == _first,
    "exit %d, out %r, cache now %r" % (_c3, _o3.strip(), _cache_text(_cd)),
)
_cd = _cache_dir()
_stubdir = tempfile.mkdtemp(prefix="house-rules-stub-", dir=_FIXTURE_ROOT)
with open(os.path.join(_stubdir, "python3"), "w", encoding="utf-8", newline="\n") as f:
    f.write('#!/bin/sh\necho "Python was not found; run without arguments to install from the Microsoft Store."\nexit 0\n')
os.chmod(os.path.join(_stubdir, "python3"), 0o755)  # POSIX skips a non-executable file on PATH
_c4, _o4, _e4 = _cache_run(_cd, PATH=_stubdir + os.pathsep + os.environ.get("PATH", ""))
_cached4 = _cache_text(_cd)
_cache_case(
    "run.sh: an interpreter stub that prints a nag instead of running code is never cached",
    _c4 == 0 and "ran" in _o4 and _cached4 is not None and _cached4.split()[0] != "python3",
    "exit %d, out %r, cache %r" % (_c4, _o4.strip(), _cached4),
)
_cd = _cache_dir()
os.mkdir(os.path.join(_cd, ".python-cache"))  # a directory where the file should go: not writable as a file
_c5, _o5, _e5 = _cache_run(_cd)
_cache_case(
    "run.sh: a cache that cannot be written is skipped, never a failure",
    _c5 == 0 and "ran" in _o5 and "Permission denied" not in _e5 and "Is a directory" not in _e5,
    "exit %d, out %r, stderr %r" % (_c5, _o5.strip(), _e5.strip()[:100]),
)
_cd = _cache_dir()
with open(os.path.join(_cd, ".python-cache"), "w", encoding="utf-8") as f:
    f.write("no-such-interpreter-xyz\n")
_c6, _o6, _e6 = _cache_run(_cd, HOUSE_RULES_PYTHON=sys.executable)
_cache_case(
    "run.sh: HOUSE_RULES_PYTHON still wins over the cache and is still probed",
    _c6 == 0 and "ran" in _o6 and "cache=override" in _e6 and _cache_text(_cd) == "no-such-interpreter-xyz",
    "exit %d, out %r, stderr %r" % (_c6, _o6.strip(), _e6.strip()[:100]),
)
_cd = _cache_dir()
_c7, _o7, _e7 = _cache_run(_cd, HOUSE_RULES_PYTHON="no-such-interpreter-xyz")
_cache_case(
    "run.sh: a bad HOUSE_RULES_PYTHON is still rejected by the probe and falls through to the normal order",
    _c7 == 0 and "ran" in _o7,
    "exit %d, out %r" % (_c7, _o7.strip()),
)

# The harvest reminder's drift check is a row in the RESTATEMENTS table below.

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
    ("docstiers", "docstiers"),
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

# --- fence gating narrows to a SHELL-labelled fence, not any fence -----------------------------
hand_case(
    "feedback",
    "a shell-labelled fence (bash) still fires the card check",
    stop_payload(last_assistant_message="Run this:\n\n```bash\nls -la\n```\n"),
)
hand_case(
    "silent",
    "a python-labelled fence is not a command handover, so the card check stays quiet",
    stop_payload(last_assistant_message="```python\nprint('hi')\n```\n"),
)
hand_case(
    "silent",
    "an unlabelled fence is not a command handover, so the card check stays quiet",
    stop_payload(last_assistant_message="```\nsome output\n```\n"),
)

# --- the evidence check: an independent trigger from the fence gate above ----------------------
_HAND_ROOT = os.path.join(_FIXTURE_ROOT, "handover-transcripts")
os.makedirs(_HAND_ROOT, exist_ok=True)


def _hand_transcript(name, lines):
    path = os.path.join(_HAND_ROOT, "%s.jsonl" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


_HAND_NO_TOOL = _hand_transcript("no-tool", [
    json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "please fix the bug"}}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Looking into it."}]}}),
])
_HAND_WITH_TOOL = _hand_transcript("with-tool", [
    json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "please fix the bug"}}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}]}}),
    json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "5 passed"}]}}),
])

hand_case(
    "feedback",
    "a success claim with no tool run since the last real message gets the evidence reminder",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Fixed the bug, it works now.",
    ),
)
hand_case(
    "silent",
    "a success claim backed by a tool call since the last real message stays quiet",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="Fixed the bug, it works now.",
    ),
)
hand_case(
    "silent",
    "a success claim that quotes real RESULT: output stays quiet, even with no tool this turn",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="It works now.\n\nRESULT: PASS",
    ),
)
# #89 reversed this one: it used to expect silence, because "untested" is not a success word.
# But a bare "untested" with no reason is exactly the disclosure-instead-of-checking #89 is about.
hand_case(
    "feedback",
    "a bare 'untested' with no reason the check could not run gets told to run it (#89)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="This is untested; I have not run it.",
    ),
)
hand_case(
    "silent",
    "an 'untested' that says in the same sentence why the check cannot run stays quiet (#89)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="This is untested because the Unity editor is not installed here.",
    ),
)
hand_case(
    "feedback",
    "a 'not checked' with no reason fires even when tools ran this turn (#89)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="I ran the tests. I haven't checked the CI logs.",
    ),
)
hand_case(
    "silent",
    "a handover card's own UNTESTED: marker is not what the not-checked check trips on (#89)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="UNTESTED: this runs on your machine.\n\nNothing else to report.",
    ),
)
hand_case(
    "feedback",
    "'that can't be done' with no tool run this turn gets the evidence reminder (#92)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="That can't be done in Claude Code; there is no setting for it.",
    ),
)
hand_case(
    "silent",
    "'that can't be done' after a tool ran this turn stays quiet (#92)",
    stop_payload(
        transcript_path=_HAND_WITH_TOOL,
        last_assistant_message="That can't be done in Claude Code; there is no setting for it.",
    ),
)
hand_case(
    "silent",
    "'it is possible' is not an impossibility claim (#92)",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Yes, it is possible to configure that.",
    ),
)
hand_case(
    "silent",
    "a phrase in quotation marks is being talked about, not asserted, so neither check fires",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message='Adding checks for "can\'t be done" claims and for a bare "untested".',
    ),
)
_, _out92, _ = run_hook("handover", stop_payload(
    transcript_path=_HAND_NO_TOOL,
    last_assistant_message="That setting doesn't exist.",
))
report("PASS" if "cannot be done or does not exist" in _out92 and "doesn't exist" in _out92 else "FAIL",
       "the #92 note names the impossibility phrase it caught")
print(f"          {_out92[:160]!r}")
hand_case(
    "silent",
    "a reply naming no claim word at all is untouched by the evidence check",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="I opened the pull request; nothing for you to run.",
    ),
)
hand_case(
    "trace",
    "a success claim whose transcript cannot be read fails open with a systemMessage, never a block",
    stop_payload(
        transcript_path=os.path.join(_HAND_ROOT, "does-not-exist.jsonl"),
        last_assistant_message="Fixed the bug, it works now.",
    ),
)

# A shell fence always satisfies the evidence check's own "quotes evidence" exemption, so the
# two checks can never both fire live on one reply - see doc-ref 6534 docs/6-decisions/Decisions.md.
code, out, err = run_hook(
    "handover",
    stop_payload(
        transcript_path=_HAND_NO_TOOL,
        last_assistant_message="Fixed the bug, it works now:\n\n```bash\ndeploy.sh\n```\n",
    ),
)
if '"hookEventName":"Stop"' in out and '"additionalContext"' in out and out.count('"hookSpecificOutput"') == 1:
    report("PASS", "a reply with both a shell fence and a claim still emits exactly one valid JSON object")
    print("          the fence's own evidence-quote exemption means only the card note fires here")
else:
    report("FAIL", "a reply with both a shell fence and a claim still emits exactly one valid JSON object")
    print(f"          out {out[:200]!r}")

# --- parity (#90/#87) and visual (#88/#96) checks ------------------------------------------
def _turn_transcript(name, prompt, uses):
    lines = [json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": prompt}})]
    for i, (tool, arg) in enumerate(uses):
        inp = {"command": arg} if tool == "Bash" else {"file_path": arg}
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "p%d" % i, "name": tool, "input": inp}]}}))
    return _hand_transcript(name, lines)


def _stop_notes(transcript, reply, **env_extra):
    env = dict(os.environ)
    env["HOUSE_RULES_COMMIT_CHECK"] = "off"
    env.update(env_extra)
    _, out, _ = run_hook("handover", stop_payload(transcript_path=transcript, last_assistant_message=reply), env=env)
    try:
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        ctx = ""
    return ("re-creating existing behaviour" in ctx, "checked by looking at it" in ctx, ctx)


def pv_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


_pv_port = _turn_transcript("pv-port", "port the stock page to GitHub Pages", [("Write", "/proj/site/index.html")])
_par, _vis, _ = _stop_notes(_pv_port, "Done, the page is ported.")
pv_case("Stop: a port that wrote files but names nothing kept or dropped gets the parity report note (#90)",
        _par, "parity=%s" % _par)
pv_case("Stop: the same turn changed an .html file and looked at nothing, so it gets the visual note (#88)",
        _vis, "visual=%s" % _vis)
_par, _, _ = _stop_notes(_pv_port, "Kept search and sorting; dropped the server sync, which needs a server.")
pv_case("Stop: a port whose reply names what was kept and dropped gets no parity note", not _par, "parity=%s" % _par)
_par, _, _ = _stop_notes(_pv_port, "Done.", HOUSE_RULES_PARITY="off")
pv_case("Stop: HOUSE_RULES_PARITY=off switches the parity check off", not _par, "parity=%s" % _par)
_pv_edit = _turn_transcript("pv-edit", "replace the colour in the header", [("Edit", "/proj/src/app.py")])
_par, _vis, _ = _stop_notes(_pv_edit, "Changed the colour.")
pv_case("Stop: an everyday 'replace' edit to a non-visual file trips neither check", not _par and not _vis,
        "parity=%s visual=%s" % (_par, _vis))
_pv_shot = _turn_transcript("pv-shot", "make the header blue",
                            [("Edit", "/proj/site.css"), ("Bash", "npx playwright screenshot http://localhost:3000 after.png")])
_, _vis, _ = _stop_notes(_pv_shot, "The header is blue.")
pv_case("Stop: a visual edit with a Playwright screenshot in the turn gets no visual note", not _vis, "visual=%s" % _vis)
_pv_read = _turn_transcript("pv-read", "make the header blue", [("Edit", "/proj/site.css"), ("Read", "/proj/after.png")])
_, _vis, _ = _stop_notes(_pv_read, "The header is blue.")
pv_case("Stop: a visual edit whose turn read a captured image gets no visual note", not _vis, "visual=%s" % _vis)
_, _vis, _ = _stop_notes(_turn_transcript("pv-off", "make the header blue", [("Edit", "/proj/site.css")]),
                         "Done.", HOUSE_RULES_VISUAL_CHECK="off")
pv_case("Stop: HOUSE_RULES_VISUAL_CHECK=off switches the visual check off", not _vis, "visual=%s" % _vis)

_, out, _ = run_hook("scope", json.dumps({"prompt": "rewrite the scraper workflow from scratch"}))
pv_case("scope: a prompt that reads like a rewrite gets the inventory-first clause", "re-creating existing behaviour" in out,
        "clause=%s" % ("re-creating existing behaviour" in out))
_, out, _ = run_hook("scope", json.dumps({"prompt": "replace the colour in header.css"}))
pv_case("scope: an everyday 'replace' prompt does not", "re-creating existing behaviour" not in out,
        "clause=%s" % ("re-creating existing behaviour" in out))
_, out, _ = run_hook("delegate", json.dumps({"tool_name": "ExitPlanMode", "tool_input": {
    "plan": "Port the stock page to GitHub Pages as a static site."}}))
pv_case("delegate: an approved port plan with no keep/change/drop inventory gets the parity note",
        "carries no keep/change/drop" in out, "note=%s" % ("carries no keep/change/drop" in out))
_, out, _ = run_hook("delegate", json.dumps({"tool_name": "ExitPlanMode", "tool_input": {
    "plan": "Port the page. Parity: keep search, drop server sync."}}))
pv_case("delegate: a port plan that carries its inventory does not", "carries no keep/change/drop" not in out,
        "note=%s" % ("carries no keep/change/drop" in out))

# --- plain summary first (#98) ------------------------------------------------------------
_PS_PLAIN = ("The commit hooks are done and pushed. Claude now gets reminded to save its work, and "
             "nothing is waiting on you.\n\n" + "More detail follows here. " * 40)
_PS_TECH = ("`hook.py`: added `_dirty_paths`, `_uncommitted_among`, `branch_ownership` and "
            "`event_branchnudge`.\n\n" + "More detail follows here. " * 40)
_PS_WIDE = _PS_PLAIN + "\n\n| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n"
_ps_wrote = _turn_transcript("ps-wrote", "add the commit hooks", [("Edit", "/proj/src/app.py")])
_ps_read = _turn_transcript("ps-read", "what does this do?", [("Bash", "cat app.py")])
_ps_commit = _turn_transcript("ps-commit", "commit it", [("Bash", "git commit -m x -- a.py && git push")])


def _ps(transcript, reply, **env_extra):
    return "plain summary first" in _stop_notes(transcript, reply, **env_extra)[2]


pv_case("Stop: a work report opening with a pile of code names is sent back to lead with a plain summary (#98)",
        _ps(_ps_wrote, _PS_TECH), "fired=%s" % _ps(_ps_wrote, _PS_TECH))
pv_case("Stop: a work report that opens plainly is left alone", not _ps(_ps_wrote, _PS_PLAIN),
        "fired=%s" % _ps(_ps_wrote, _PS_PLAIN))
pv_case("Stop: a plain opening with a 4-column table still fires - too wide for a phone", _ps(_ps_wrote, _PS_WIDE),
        "fired=%s" % _ps(_ps_wrote, _PS_WIDE))
pv_case("Stop: a turn that only committed counts as reporting work", _ps(_ps_commit, _PS_TECH),
        "fired=%s" % _ps(_ps_commit, _PS_TECH))
pv_case("Stop: a turn that changed nothing is not a work report, so a technical answer is fine",
        not _ps(_ps_read, _PS_TECH), "fired=%s" % _ps(_ps_read, _PS_TECH))
pv_case("Stop: HOUSE_RULES_PLAIN_SUMMARY=off switches it off",
        not _ps(_ps_wrote, _PS_TECH, HOUSE_RULES_PLAIN_SUMMARY="off"), "")

# --- the commit rule's obligation half (#97): Stop, branchnudge, audit, stale memories -------
# Each case gets its own throwaway repo, so the branch and the dirty set are exactly what the
# case says they are. The hook is pointed at it through CLAUDE_PROJECT_DIR, the same variable
# Claude Code sets.
def _commit_repo(branch, committed=(), dirty=()):
    d = tempfile.mkdtemp(prefix="house-rules-commit-", dir=_FIXTURE_ROOT)
    git = ["git", "-c", "user.name=verify", "-c", "user.email=verify@example.invalid", "-C", d]
    subprocess.run(git + ["init", "-q", "-b", branch], check=True)
    for rel in committed:
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write("original\n")
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "base"], check=True)
    for rel in dirty:
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write("changed\n")
    return d


def _wrote_transcript(name, paths):
    lines = [json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "change it"}})]
    for i, p in enumerate(paths):
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "w%d" % i, "name": "Edit", "input": {"file_path": p}}]}}))
    return _hand_transcript(name, lines)


def _project_env(root, **extra):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = root
    e.pop("HOUSE_RULES_COMMIT_CHECK", None)
    e.update(extra)
    return e


def _stop_context(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def commit_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print(f"          {detail}")


_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-own", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
_ctx = _stop_context(out)
commit_case(
    "Stop: a file this turn wrote, still uncommitted on a claude/ branch, gets 'commit it now, scoped'",
    "commit on your own branch" in _ctx and "a.py" in _ctx and "`claude/topic`" in _ctx and "git commit -- <paths>" in _ctx,
    "context: %r" % _ctx[:160],
)

_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-main", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
_ctx = _stop_context(out)
commit_case(
    "Stop: the same on the user's main says to branch off to claude/<topic> first",
    "not a claude/ branch" in _ctx and "branch off first" in _ctx and "git switch -c claude/<topic>" in _ctx,
    "context: %r" % _ctx[:160],
)

_r = _commit_repo("main", committed=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-committed", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed and committed a.py."),
    env=_project_env(_r),
)
commit_case(
    "Stop: a file this turn wrote that is already committed stays silent",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_r = _commit_repo("main", committed=["a.py", "theirs.py"], dirty=["theirs.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-not-theirs", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r),
)
commit_case(
    "Stop: the user's own uncommitted edit, which this turn never wrote, never trips the check",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-toggle", [os.path.join(_r, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_r, HOUSE_RULES_COMMIT_CHECK="off"),
)
commit_case(
    "Stop: HOUSE_RULES_COMMIT_CHECK=off switches the commit check off",
    out.strip() == "",
    "stdout: %r" % out[:120],
)

_nogit = tempfile.mkdtemp(prefix="house-rules-nogit-", dir=_FIXTURE_ROOT)
_, out, _ = run_hook(
    "handover",
    stop_payload(transcript_path=_wrote_transcript("wrote-nogit", [os.path.join(_nogit, "a.py")]),
                 last_assistant_message="Changed a.py."),
    env=_project_env(_nogit),
)
commit_case(
    "Stop: outside a git repo the commit check says it could not tell, and never blocks",
    "commit check could not tell" in out and '"decision"' not in out and '"additionalContext"' not in out,
    "stdout: %r" % out[:160],
)


def _nudge(root, rel, **extra):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(root, rel)}})
    return run_hook("branchnudge", payload, env=_project_env(root, **extra))[1]


_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py")
commit_case(
    "branchnudge: the first uncommitted change on a non-claude/ branch says to branch off now",
    "branch off now" in out and "`main`" in out and '"PostToolUse"' in out and '"permissionDecision"' not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("main", committed=["a.py", "b.py"], dirty=["a.py", "b.py"])
out = _nudge(_r, "b.py")
commit_case(
    "branchnudge: a second uncommitted change is not the first, so it stays quiet",
    "branch off now" not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py")
commit_case(
    "branchnudge: on a claude/ branch there is nothing to nudge",
    "branch off now" not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("main", committed=["a.py"], dirty=["a.py"])
out = _nudge(_r, "a.py", HOUSE_RULES_COMMIT_CHECK="off")
commit_case(
    "branchnudge: HOUSE_RULES_COMMIT_CHECK=off switches it off",
    out.strip() == "",
    "stdout: %r" % out[:160],
)
commit_case(
    "branchnudge is wired to PostToolUse Write|Edit in hooks.json",
    bool(re.search(r'"matcher": "Write\|Edit",\s*"hooks": \[\s*\{\s*"type": "command",\s*"command": "sh \\"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/run\.sh\\" branchnudge"', hooks_json_text)),
    "hooks.json PostToolUse entry",
)

# audit: a subagent's uncommitted files are named, because the parent owns that commit.
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
_sub = _hand_transcript("subagent-wrote", [
    json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "w1", "name": "Write", "input": {"file_path": os.path.join(_r, "a.py")}}]}}),
])
_audit_snippet = "import sys, hook\nprint(hook._audit_report(sys.argv[1]))\n"
_p = subprocess.run([sys.executable, "-c", _audit_snippet, _sub], cwd=HERE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, env=_project_env(_r))
_aout = _p.stdout.decode("utf-8", "replace")
commit_case(
    "audit: a file the subagent wrote that is still uncommitted is named, and the commit is the parent's",
    "uncommitted: a.py" in _aout and "The commit is yours now" in _aout,
    "audit: %r" % _aout[-200:],
)

# subagentcommit: a subagent cannot finish with files it wrote still uncommitted - it is sent
# back once (decision "block", probed on CLI 2.1.284), and the retry is let through.
def _subagent_stop(paths, active=False, **env_extra):
    tr = _hand_transcript("subcommit-%d" % len(os.listdir(_HAND_ROOT)), [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "s%d" % i, "name": "Write", "input": {"file_path": p}}]}})
        for i, p in enumerate(paths)
    ])
    payload = json.dumps({"hook_event_name": "SubagentStop", "agent_type": "house-rules:builder",
                          "agent_transcript_path": tr, "stop_hook_active": active})
    return run_hook("subagentcommit", payload, env=_project_env(_FIXTURE_ROOT, **env_extra))[1]


_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")])
commit_case(
    "subagentcommit: a subagent finishing with a file it wrote still uncommitted is sent back to commit it",
    '"decision": "block"' in out.replace('":"', '": "') and "a.py" in out and "commit on your own branch" in out,
    "stdout: %r" % out[:160],
)
commit_case(
    "subagentcommit: its instruction respects a 'do not run git' delegation",
    "told you not to run git" in out,
    "stdout: %r" % out[:160],
)
out = _subagent_stop([os.path.join(_r, "a.py")], active=True)
commit_case(
    "subagentcommit: the retry (stop_hook_active) is never blocked again - it only reports",
    '"decision"' not in out and "still uncommitted after being asked once" in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")])
commit_case(
    "subagentcommit: a subagent that committed what it wrote finishes without being held",
    '"decision"' not in out,
    "stdout: %r" % out[:160],
)
_r = _commit_repo("claude/topic", committed=["a.py"], dirty=["a.py"])
out = _subagent_stop([os.path.join(_r, "a.py")], HOUSE_RULES_COMMIT_CHECK="off")
commit_case(
    "subagentcommit: HOUSE_RULES_COMMIT_CHECK=off switches it off",
    out.strip() == "",
    "stdout: %r" % out[:160],
)
# The project dir is _FIXTURE_ROOT (not a repo); the file lives in its own repo, like a worktree.
_wt = _commit_repo("worktree-agent-1", committed=["w.py"], dirty=["w.py"])
out = _subagent_stop([os.path.join(_wt, "w.py")])
commit_case(
    "subagentcommit: a file in a separate worktree is judged in that worktree's repo, not the project dir",
    '"decision"' in out and "w.py" in out and "worktree-agent-1" in out,
    "stdout: %r" % out[:200],
)
commit_case(
    "subagentcommit is wired to SubagentStop in hooks.json",
    'run.sh\\" subagentcommit' in hooks_json_text,
    "hooks.json SubagentStop entry",
)
# autosave / commitgate / worktreesweep (2.47.0): a subagent killed mid-run never reaches
# SubagentStop, so its work is protected while it runs. Each fixture repo has a local bare repo
# as `origin`, standing in for GitHub.
def _as_git(d, *args, env=None):
    return subprocess.run(["git", "-c", "user.name=verify", "-c", "user.email=verify@example.invalid",
                           "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, check=False).stdout.decode("utf-8", "replace").strip()


def _as_repo(branch, backdate_minutes=0):
    bare = tempfile.mkdtemp(prefix="house-rules-origin-", dir=_FIXTURE_ROOT)
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
    d = tempfile.mkdtemp(prefix="house-rules-autosave-", dir=_FIXTURE_ROOT)
    _as_git(d, "init", "-q", "-b", branch)
    with open(os.path.join(d, "base.py"), "w", encoding="utf-8") as f:
        f.write("base\n")
    _as_git(d, "add", "-A")
    env = dict(os.environ)
    if backdate_minutes:
        when = "@%d +0000" % int(time.time() - backdate_minutes * 60)
        env.update(GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when)
    _as_git(d, "commit", "-q", "-m", "base", env=env)
    _as_git(d, "remote", "add", "origin", bare)
    return d, bare


def _as_write(d, rel, text="x\n"):
    p = os.path.join(d, rel)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _as_payload(event, tool, path, cwd):
    return json.dumps({"hook_event_name": event, "tool_name": tool, "session_id": "s1", "cwd": cwd,
                       "tool_input": {"file_path": path} if tool != "Bash" else {"command": "true"}})


def _as_env(**extra):
    e = _project_env(_FIXTURE_ROOT, **extra)
    e.pop("HOUSE_RULES_AUTOSAVE", None)
    e.update(extra)
    return e


def _as_ref(d, branch):
    return _as_git(d, "rev-parse", "--verify", "-q", "refs/house-rules/autosave/" + branch)


def _as_remote_ref(bare, branch):
    return _as_git(bare, "rev-parse", "--verify", "-q", "refs/house-rules/autosave/" + branch)


_d, _bare = _as_repo("worktree-agent-x")
_head0 = _as_git(_d, "rev-parse", "HEAD")
_p = _as_write(_d, "new.py")
_t0 = time.time()
_, out, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _p, _d), env=_as_env())
out_first_autosave = out
_elapsed = time.time() - _t0
_local = _as_ref(_d, "worktree-agent-x")
commit_case(
    "autosave: an edit on a worktree-agent- branch saves an untracked file to the autosave ref and pushes it",
    bool(_local) and "new.py" in _as_git(_d, "ls-tree", "--name-only", _local)
    and _as_remote_ref(_bare, "worktree-agent-x") == _local,
    "local %s, origin %s, out %r" % (_local[:9], _as_remote_ref(_bare, "worktree-agent-x")[:9], out[:120]),
)
commit_case(
    "autosave: the branch, the real index and the working tree are left exactly as they were",
    _as_git(_d, "rev-parse", "HEAD") == _head0 and _as_git(_d, "diff", "--cached", "--name-only") == ""
    and _as_git(_d, "status", "--porcelain") == "?? new.py",
    "status %r" % _as_git(_d, "status", "--porcelain"),
)
commit_case("autosave: one edit stays well inside the 10 s hook budget", _elapsed < 5, "took %.2fs" % _elapsed)
_p = _as_write(_d, "new.py", "y\n")
run_hook("autosave", _as_payload("PostToolUse", "Edit", _p, _d), env=_as_env())
_local2 = _as_ref(_d, "worktree-agent-x")
_rate_ok = _local2 != _local and _as_remote_ref(_bare, "worktree-agent-x") == _local
_stamp = os.path.join(_as_git(_d, "rev-parse", "--absolute-git-dir"), "house-rules-autosave-worktree-agent-x.pushed")
with open(_stamp, "w", encoding="utf-8") as f:
    f.write("%s %s" % (time.time() - 120, _local))
_p = _as_write(_d, "new.py", "z\n")
run_hook("autosave", _as_payload("PostToolUse", "Edit", _p, _d), env=_as_env())
commit_case(
    "autosave: pushes at most once a minute; the local ref still moves, and the next push after the window catches up",
    _rate_ok and _as_remote_ref(_bare, "worktree-agent-x") == _as_ref(_d, "worktree-agent-x"),
    "second edit local-only: %s; after the window origin matches: %s"
    % (_rate_ok, _as_remote_ref(_bare, "worktree-agent-x") == _as_ref(_d, "worktree-agent-x")),
)
_quiet = []
for _br in ("main", "claude/x"):
    _dq, _ = _as_repo(_br)
    _pq = _as_write(_dq, "new.py")
    _, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
    if _as_ref(_dq, _br) or oq.strip():
        _quiet.append("%s: ref %r, out %r" % (_br, _as_ref(_dq, _br), oq[:80]))
_dq, _ = _as_repo("worktree-agent-off")
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env(HOUSE_RULES_AUTOSAVE="off"))
if _as_ref(_dq, "worktree-agent-off") or oq.strip():
    _quiet.append("HOUSE_RULES_AUTOSAVE=off still acted: out %r" % oq[:80])
commit_case(
    "autosave: does nothing on main, on a claude/ branch, or with HOUSE_RULES_AUTOSAVE=off",
    not _quiet, "; ".join(_quiet) or "no ref and no output in all three",
)
# .git/HEAD fast path (2.48.0): a branch that is not worktree-agent-* is ruled out by reading
# .git/HEAD, so no git subprocess is spawned. The probe counts subprocess.Popen constructions
# (subprocess.run goes through Popen) while running hook.py unmodified.
_SPAWN_PROBE = (
    "import sys, subprocess, runpy\n"
    "n = [0]\n"
    "orig = subprocess.Popen.__init__\n"
    "def counting(self, *a, **k):\n"
    "    n[0] += 1\n"
    "    orig(self, *a, **k)\n"
    "subprocess.Popen.__init__ = counting\n"
    "hook, event = sys.argv[1], sys.argv[2]\n"
    "sys.argv = [hook, event]\n"
    "try:\n"
    "    runpy.run_path(hook, run_name='__main__')\n"
    "finally:\n"
    "    sys.stderr.write('SPAWNS=%d' % n[0])\n"
)


def _as_spawns(event, payload, env):
    proc = subprocess.run([sys.executable, "-c", _SPAWN_PROBE, HOOK, event], input=payload.encode("utf-8"),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    m = re.search(r"SPAWNS=(\d+)", proc.stderr.decode("utf-8", "replace"))
    return (int(m.group(1)) if m else -1), proc.stdout.decode("utf-8", "replace")


_fast = []
for _ev in ("autosave", "commitgate"):
    _dq, _ = _as_repo("main")
    _pq = _as_write(_dq, "new.py")
    _n, _o = _as_spawns(_ev, _as_payload("PostToolUse" if _ev == "autosave" else "PreToolUse", "Write", _pq, _dq), _as_env())
    if _n != 0 or _o.strip():
        _fast.append("%s on main: %d spawns, out %r" % (_ev, _n, _o[:60]))
commit_case(
    "autosave/commitgate: a non-subagent branch is ruled out from .git/HEAD with zero git subprocesses",
    not _fast, "; ".join(_fast) or "0 spawns and no output on main for both handlers",
)
_dq, _ = _as_repo("worktree-agent-fast")
_pq = _as_write(_dq, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), _as_env())
commit_case(
    "autosave: a worktree-agent- branch still takes the full path after the fast check (unchanged behaviour)",
    _n > 0 and bool(_as_ref(_dq, "worktree-agent-fast")),
    "%d spawns, autosave ref %r" % (_n, _as_ref(_dq, "worktree-agent-fast")[:9]),
)
_dq, _ = _as_repo("worktree-agent-det")
_as_git(_dq, "checkout", "-q", "--detach")
_pq = _as_write(_dq, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), _as_env())
commit_case(
    "autosave: a detached HEAD spawns no git subprocess and saves nothing",
    _n == 0 and not _o.strip() and not _as_ref(_dq, "worktree-agent-det"),
    "%d spawns, out %r" % (_n, _o[:60]),
)
_dq, _ = _as_repo("main")
_wt = os.path.join(_FIXTURE_ROOT, "wt-agent-%d" % int(time.time() * 1000))
_as_git(_dq, "worktree", "add", "-q", "-b", "worktree-agent-wt", _wt)
_wf_is_file = os.path.isfile(os.path.join(_wt, ".git"))
_pq = _as_write(_wt, "new.py")
_n, _o = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq, _wt), _as_env())
_wt2 = os.path.join(_FIXTURE_ROOT, "wt-plain-%d" % int(time.time() * 1000))
_as_git(_dq, "worktree", "add", "-q", "-b", "feature-plain", _wt2)
_pq2 = _as_write(_wt2, "new.py")
_n2, _o2 = _as_spawns("autosave", _as_payload("PostToolUse", "Write", _pq2, _wt2), _as_env())
commit_case(
    "autosave: a linked worktree (.git is a file) is resolved for both branch kinds",
    _wf_is_file and _n > 0 and bool(_as_ref(_wt, "worktree-agent-wt")) and _n2 == 0 and not _o2.strip(),
    ".git file %s; agent branch: %d spawns, ref %r; plain branch: %d spawns" % (_wf_is_file, _n, _as_ref(_wt, "worktree-agent-wt")[:9], _n2),
)
_dq, _ = _as_repo("worktree-agent-noreach")
_as_git(_dq, "remote", "set-url", "origin", os.path.join(_FIXTURE_ROOT, "no-such-origin.git"))
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
oq_unreach = oq
commit_case(
    "autosave: an unreachable origin is said out loud, and the save is still kept locally",
    "could not push refs/house-rules/autosave/worktree-agent-noreach" in oq and bool(_as_ref(_dq, "worktree-agent-noreach")),
    "out %r" % oq[:160],
)
_dq, _ = _as_repo("worktree-agent-old", backdate_minutes=20)
_pq = _as_write(_dq, "new.py")
_, oq, _ = run_hook("autosave", _as_payload("PostToolUse", "Write", _pq, _dq), env=_as_env())
oq_checkpoint = oq
_dfresh, _ = _as_repo("worktree-agent-fresh")
_pf = _as_write(_dfresh, "new.py")
run_hook("autosave", _as_payload("PostToolUse", "Write", _pf, _dfresh), env=_as_env())
commit_case(
    "autosave: 10 minutes without a commit makes the hook commit for the subagent; a fresh commit does not",
    _as_git(_dq, "log", "-1", "--format=%s") == "wip: checkpoint - 10 min without a commit"
    and _as_git(_dq, "status", "--porcelain") == "" and "committed 1 file(s)" in oq
    and _as_git(_dfresh, "log", "-1", "--format=%s") == "base",
    "old: %r, status %r; fresh: %r" % (_as_git(_dq, "log", "-1", "--format=%s"),
                                       _as_git(_dq, "status", "--porcelain"), _as_git(_dfresh, "log", "-1", "--format=%s")),
)

_dg, _ = _as_repo("worktree-agent-gate")
_as_write(_dg, "a.py")
_pg = _as_write(_dg, "b.py")
_, o2, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
_as_write(_dg, "c.py")
_, o3, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
commit_case(
    "commitgate: 2 uncommitted files pass; 3 block the edit, naming the files, with nothing committed",
    o2.strip() == "" and '"permissionDecision":"deny"' in o3 and "a.py" in o3 and "c.py" in o3
    and _as_git(_dg, "log", "-1", "--format=%s") == "base",
    "2 files: %r; 3 files: %r" % (o2[:60], o3[:140]),
)
_, o4, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pg, _dg), env=_as_env())
commit_case(
    "commitgate: asked once and ignored, the hook commits everything itself and lets the edit through",
    _as_git(_dg, "log", "-1", "--format=%s") == "wip: autosave - subagent did not commit when asked"
    and _as_git(_dg, "status", "--porcelain") == "" and "deny" not in o4 and "committed 3 file(s)" in o4,
    "last commit %r, out %r" % (_as_git(_dg, "log", "-1", "--format=%s"), o4[:140]),
)
_gq = []
_dm, _ = _as_repo("main")
for _n in ("a.py", "b.py", "c.py", "d.py"):
    _pm = _as_write(_dm, _n)
_, om, _ = run_hook("commitgate", _as_payload("PreToolUse", "Edit", _pm, _dm), env=_as_env())
if om.strip():
    _gq.append("main: %r" % om[:80])
_db, _ = _as_repo("worktree-agent-bash")
for _n in ("a.py", "b.py", "c.py"):
    _as_write(_db, _n)
_, ob, _ = run_hook("commitgate", _as_payload("PreToolUse", "Bash", _db, _db), env=_as_env())
if ob.strip():
    _gq.append("Bash: %r" % ob[:80])
commit_case(
    "commitgate: never gates main, and never gates Bash (the subagent needs it to commit)",
    not _gq, "; ".join(_gq) or "both passed with no output",
)

_ds, _bs = _as_repo("worktree-agent-done")
_ps = _as_write(_ds, "s.py")
run_hook("autosave", _as_payload("PostToolUse", "Write", _ps, _ds), env=_as_env())
_had = bool(_as_remote_ref(_bs, "worktree-agent-done"))
_as_git(_ds, "add", "-A")
_as_git(_ds, "commit", "-q", "-m", "feat: s")
out = run_hook("subagentcommit", json.dumps({
    "hook_event_name": "SubagentStop", "agent_type": "house-rules:builder", "stop_hook_active": False,
    "agent_transcript_path": _hand_transcript("autosave-done", [json.dumps({"type": "assistant", "message": {
        "content": [{"type": "tool_use", "id": "d1", "name": "Write", "input": {"file_path": _ps}}]}})])}),
    env=_project_env(_FIXTURE_ROOT))[1]
commit_case(
    "subagentcommit: a clean finish deletes the autosave ref locally and on origin",
    _had and not _as_ref(_ds, "worktree-agent-done") and not _as_remote_ref(_bs, "worktree-agent-done"),
    "on origin before: %s; after: local %r origin %r; out %r"
    % (_had, _as_ref(_ds, "worktree-agent-done"), _as_remote_ref(_bs, "worktree-agent-done"), out[:80]),
)
_dr, _ = _as_repo("worktree-agent-retry")
_pr = _as_write(_dr, "r.py")
out = _subagent_stop([_pr], active=True)
_dc, _ = _as_repo("claude/retry")
_pc = _as_write(_dc, "r.py")
out_c = _subagent_stop([_pc], active=True)
commit_case(
    "subagentcommit: a retry still uncommitted is committed by the hook on a worktree-agent- branch, never on claude/",
    _as_git(_dr, "log", "-1", "--format=%s") == "wip: autosave - subagent did not commit when asked"
    and _as_git(_dr, "status", "--porcelain") == "" and "committed 1 file(s)" in out
    and _as_git(_dc, "log", "-1", "--format=%s") == "base" and _as_git(_dc, "status", "--porcelain") == "?? r.py",
    "worktree-agent: %r; claude/: %r" % (_as_git(_dr, "log", "-1", "--format=%s"), _as_git(_dc, "log", "-1", "--format=%s")),
)

_dmain, _ = _as_repo("main")
_sweep_old = os.path.join(_FIXTURE_ROOT, "wt-sweep-old")
_sweep_new = os.path.join(_FIXTURE_ROOT, "wt-sweep-new")
_sweep_mine = os.path.join(_FIXTURE_ROOT, "wt-sweep-claude")
_as_git(_dmain, "worktree", "add", "-q", "-b", "worktree-agent-old", _sweep_old)
_as_git(_dmain, "worktree", "add", "-q", "-b", "worktree-agent-new", _sweep_new)
_as_git(_dmain, "worktree", "add", "-q", "-b", "claude/sweep", _sweep_mine)
_long_ago = time.time() - 20 * 60
for _wt in (_sweep_old, _sweep_mine):
    os.utime(_as_write(_wt, "left.py"), (_long_ago, _long_ago))
_as_write(_sweep_new, "live.py")
_, osw, _ = run_hook("worktreesweep", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi",
                                                  "cwd": _dmain, "session_id": "s1"}),
                     env=_project_env(_dmain))
commit_case(
    "worktreesweep: the parent commits a subagent worktree left untouched 10+ min, and leaves a live one and claude/ alone",
    _as_git(_sweep_old, "log", "-1", "--format=%s") == "wip: parent checkpoint of subagent work"
    and _as_git(_sweep_old, "status", "--porcelain") == "" and "worktree-agent-old" in osw
    and _as_git(_sweep_new, "status", "--porcelain") == "?? live.py"
    and _as_git(_sweep_mine, "status", "--porcelain") == "?? left.py",
    "old: %r; live: %r; claude/: %r; out %r" % (_as_git(_sweep_old, "log", "-1", "--format=%s"),
                                                _as_git(_sweep_new, "status", "--porcelain"),
                                                _as_git(_sweep_mine, "status", "--porcelain"), osw[:100]),
)
_, osw2, _ = run_hook("worktreesweep", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi",
                                                   "cwd": _dmain}), env=_project_env(_dmain))
commit_case(
    "worktreesweep: says nothing when there is nothing to commit",
    osw2.strip() == "", "out %r" % osw2[:100],
)
_multi = []
for _name, _o in (("autosave", out_first_autosave), ("autosave unreachable origin", oq_unreach),
                  ("autosave checkpoint", oq_checkpoint), ("commitgate deny", o3),
                  ("commitgate fallback", o4), ("worktreesweep", osw)):
    try:
        json.loads(_o)
    except ValueError:
        _multi.append("%s: %r" % (_name, _o[:100]))
commit_case(
    "autosave, commitgate and worktreesweep each print exactly one JSON object per call",
    not _multi, "; ".join(_multi) or "all six outputs parse as one object",
)
commit_case(
    "autosave, commitgate and worktreesweep are wired in hooks.json",
    all('run.sh\\" %s' % e in hooks_json_text for e in ("autosave", "commitgate", "worktreesweep")),
    "hooks.json PostToolUse / PreToolUse / UserPromptSubmit entries",
)

# --- issue workflow (2.49.0): #108 PR Refs rule, #109 issue close asks, #110 plan -> issues gate ---
# Every case runs against a throwaway repo in _FIXTURE_ROOT. A stub `gh` on PATH writes a marker
# file when it is run, so "the hooks never run gh on a tool call" is asserted, not assumed.
# Plan: docs/plans/issue-workflow-build-plan.md.
_ISS_PLAN5 = "# Plan\n\n1. one\n2. two\n3. three\n4. four\n5. five\n"
_ISS_PLAN3 = "# Plan\n\n1. one\n2. two\n3. three\n"
_ISS_MARK = os.path.join(_FIXTURE_ROOT, "gh-was-run.marker")
_ISS_STUBDIR = tempfile.mkdtemp(prefix="house-rules-ghstub-", dir=_FIXTURE_ROOT)


def _iss_stub(body_ok=True):
    """Write a stub gh into _ISS_STUBDIR. It records that it ran, then prints two issues (or fails)."""
    if os.name == "nt":
        path = os.path.join(_ISS_STUBDIR, "gh.cmd")
        lines = ["@echo off", "echo ran> \"%s\"" % _ISS_MARK]
        if body_ok == "empty":
            lines.append("echo []")
        elif body_ok:
            lines.append("echo [{\"number\":7,\"title\":\"Fix the login screen\"},{\"number\":3,\"title\":\"Add sound\"}]")
        else:
            lines += ["echo HTTP 401: bad credentials 1>&2", "exit /b 1"]
        open(path, "w", encoding="utf-8", newline="\r\n").write("\r\n".join(lines) + "\r\n")
    else:
        path = os.path.join(_ISS_STUBDIR, "gh")
        lines = ["#!/bin/sh", "echo ran > '%s'" % _ISS_MARK]
        if body_ok == "empty":
            lines.append("echo '[]'")
        elif body_ok:
            lines.append("echo '[{\"number\":7,\"title\":\"Fix the login screen\"},{\"number\":3,\"title\":\"Add sound\"}]'")
        else:
            lines += ["echo 'HTTP 401: bad credentials' >&2", "exit 1"]
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        os.chmod(path, 0o755)


def _iss_env(**extra):
    e = _project_env(_FIXTURE_ROOT)
    e.pop("HOUSE_RULES_ISSUES", None)
    e["PATH"] = _ISS_STUBDIR + os.pathsep + e.get("PATH", "")
    e.update(extra)
    return e


def _iss_repo(remote=None):
    d = tempfile.mkdtemp(prefix="house-rules-issues-", dir=_FIXTURE_ROOT)
    _as_git(d, "init", "-q", "-b", "main")
    _as_write(d, "base.py", "base\n")
    _as_git(d, "add", "-A")
    _as_git(d, "commit", "-q", "-m", "base")
    if remote:
        _as_git(d, "remote", "add", "origin", remote)
    return d


def _iss_state_path(d):
    return os.path.join(_as_git(d, "rev-parse", "--absolute-git-dir"), "house-rules-issues.json")


def _iss_state(d):
    try:
        return json.load(open(_iss_state_path(d), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _iss_payload(event, tool, d, **ti):
    p = {"hook_event_name": event, "tool_name": tool, "session_id": "iss", "cwd": d, "tool_input": ti}
    return p


def _iss_call(event, payload, d, **envx):
    return run_hook(event, json.dumps(payload), env=_iss_env(**envx))


def _iss_decision(out):
    try:
        return json.loads(out)["hookSpecificOutput"].get("permissionDecision")
    except Exception:
        return None


def _iss_reason(out):
    try:
        return json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason", "")
    except Exception:
        return ""


_iss_stub(True)
_issues_outputs = []

# -- #110: delegate counts steps and writes the state -----------------------------------------
_d = _iss_repo()
_, _o, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _d, plan=_ISS_PLAN5), _d)
_issues_outputs.append(("delegate 5 steps", _o))
_st = _iss_state(_d)
_ctx = _stop_context(_o)
commit_case(
    "issues: a 5-step plan writes the gate state and the delegate note says to create the issues",
    bool(_st) and _st.get("needs_issues") is True and _st.get("plan_steps") == 5 and "5 steps" in _ctx
    and "parent issue" in _ctx and "Claude created this" in _ctx and "in progress" in _ctx
    and "Claude completed this" not in _ctx,
    "state %r" % _st,
)
_d3 = _iss_repo()
_, _o3, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _d3, plan=_ISS_PLAN3), _d3)
_issues_outputs.append(("delegate 3 steps", _o3))
commit_case(
    "issues: a 3-step plan writes nothing and the note names the count",
    _iss_state(_d3) is None and "counts 3 step(s)" in _stop_context(_o3),
    "state %r" % _iss_state(_d3),
)
_dh = _iss_repo()
_, _oh, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dh,
                      plan="## Steps\n\n### Step 1 - a\n### Step 2 - b\n### Change 3 - c\n- [ ] d\n"), _dh)
commit_case(
    "issues: '### Step', '### Change' headings and '- [ ]' items count as steps",
    (_iss_state(_dh) or {}).get("plan_steps") == 4, "state %r" % _iss_state(_dh),
)

# -- #110: the gate in commitgate --------------------------------------------------------------
_fp = lambda rel: os.path.join(_d, rel)
_, _og, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp("Assets/Foo.cs"), content="x"), _d)
_issues_outputs.append(("gate deny", _og))
commit_case(
    "issues: with the gate closed, a Write to a source file is denied naming both missing pieces",
    _iss_decision(_og) == "deny" and "parent issue" in _iss_reason(_og) and "child issue" in _iss_reason(_og),
    "out %r" % _og[:160],
)
_, _oe, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Edit", _d, file_path=_fp("src/a.py")), _d)
_, _on, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "NotebookEdit", _d, notebook_path=_fp("n.ipynb")), _d)
commit_case(
    "issues: Edit and NotebookEdit on source files are denied too",
    _iss_decision(_oe) == "deny" and _iss_decision(_on) == "deny", "edit %r notebook %r" % (_oe[:60], _on[:60]),
)
_allowed = []
for _rel in ("docs/x.md", "docs/sub/y.json", "README.md", "src/notes.md", ".claude/settings.json"):
    _, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp(_rel)), _d)
    if _oa.strip():
        _allowed.append((_rel, _oa[:60]))
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=os.path.join(_FIXTURE_ROOT, "elsewhere.cs")), _d)
if _oa.strip():
    _allowed.append(("outside project", _oa[:60]))
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_iss_state_path(_d)), _d)
if _oa.strip():
    _allowed.append(("state file", _oa[:60]))
commit_case(
    "issues: docs/, .md files, .claude/, files outside the project and the state file stay editable",
    not _allowed, "denied: %r" % _allowed,
)
_, _ob, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Bash", _d, command="true"), _d)
commit_case("issues: Bash is never gated", _ob.strip() == "", "out %r" % _ob[:80])

# -- #110: recording creations clears the gate --------------------------------------------------
_label_cmd = 'gh issue create --title "t" --body "b" --label "Claude created this" --label bug'
_bare_cmd = 'gh issue create --title "t" --body "b" --label bug'


def _iss_created(d, cmd, n):
    return _iss_call("autosave", dict(_iss_payload("PostToolUse", "Bash", d, command=cmd),
                                      tool_response={"stdout": "https://github.com/o/r/issues/%d\n" % n}), d)


_, _ou, _ = _iss_created(_d, _bare_cmd, 50)
_issues_outputs.append(("unlabelled create", _ou))
_st = _iss_state(_d)
commit_case(
    "issues: an unlabelled `gh issue create` gets a correction note and does not count",
    "without the `Claude created this` label" in _ou and _st["needs_issues"] is True
    and _st["created"] and _st["created"][0]["labelled"] is False,
    "state %r out %r" % (_st, _ou[:100]),
)
_, _o1, _ = _iss_created(_d, _label_cmd, 51)
_st1 = _iss_state(_d)
_, _o2, _ = _iss_created(_d, _label_cmd, 52)
_issues_outputs.append(("labelled create 2", _o2))
_st2 = _iss_state(_d)
commit_case(
    "issues: the gate clears after two labelled issues (parent plus one child), not after one",
    _st1["needs_issues"] is True and _st2["needs_issues"] is False and "unblocked" in _o2
    and _st2["created"][-1] == {"repo": "o/r", "number": 52, "labelled": True},
    "after one %r, after two %r" % (_st1["needs_issues"], _st2["needs_issues"]),
)
_, _oa, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _d, file_path=_fp("Assets/Foo.cs")), _d)
commit_case("issues: once cleared the same source Write is allowed", _oa.strip() == "", "out %r" % _oa[:80])
_dn = _iss_repo()
_, _onone, _ = _iss_created(_dn, _label_cmd, 60)
commit_case(
    "issues: a `gh issue create` with no plan state is not recorded and says nothing",
    _onone.strip() == "" and _iss_state(_dn) is None, "out %r" % _onone[:80],
)
_dm = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dm, plan=_ISS_PLAN5), _dm)
_, _omiss, _ = _iss_call("autosave", dict(_iss_payload("PostToolUse", "Bash", _dm, command=_label_cmd),
                                          tool_response={"stdout": "error: network down"}), _dm)
commit_case(
    "issues: a `gh issue create` whose output has no issue URL is said out loud and not counted",
    "no issue URL" in _omiss and _iss_state(_dm)["created"] == [], "out %r" % _omiss[:120],
)

# -- #110: stop line, corrupt state, kill switch, subagent worktree -----------------------------
_ds = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _ds, plan=_ISS_PLAN5), _ds)
_, _ostop, _ = run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_ds), env=_iss_env())
_issues_outputs.append(("stop", _ostop))
commit_case(
    "issues: Stop adds one line while the gate is still closed and does not block",
    "plans become issues" in _stop_context(_ostop) and '"decision"' not in _ostop,
    "out %r" % _ostop[:160],
)
_, _ostop2, _ = run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_d), env=_iss_env())
commit_case("issues: Stop stays silent once the gate is cleared", "plans become issues" not in _ostop2, "out %r" % _ostop2[:100])

_dc = _iss_repo()
open(_iss_state_path(_dc), "w", encoding="utf-8").write("{not json")
_, _oc, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dc, file_path=os.path.join(_dc, "a.cs")), _dc)
_issues_outputs.append(("corrupt state", _oc))
commit_case(
    "issues: a corrupt state file is reported in one line and treated as no gate",
    "could not read house-rules-issues.json" in _oc and _iss_decision(_oc) is None,
    "out %r" % _oc[:160],
)

_dk = _iss_repo()
_, _ok, _ = _iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk, plan=_ISS_PLAN5), _dk,
                      HOUSE_RULES_ISSUES="off")
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk, plan=_ISS_PLAN5), _dk)  # state now exists
_, _ogk, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dk, file_path=os.path.join(_dk, "a.cs")), _dk,
                       HOUSE_RULES_ISSUES="off")
_, _opk, _ = _iss_call("guard", _iss_payload("PreToolUse", "Bash", _dk, command='gh pr create --title T --body "Closes #5"'), _dk,
                       HOUSE_RULES_ISSUES="off")
_, _ock, _ = _iss_call("guard", _iss_payload("PreToolUse", "Bash", _dk, command="gh issue close 5"), _dk,
                       HOUSE_RULES_ISSUES="off")
_dk2 = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dk2, plan=_ISS_PLAN5), _dk2, HOUSE_RULES_ISSUES="off")
commit_case(
    "issues: HOUSE_RULES_ISSUES=off writes no state and disables the gate, the PR rule and the close prompt",
    _iss_state(_dk2) is None and _ogk.strip() == "" and _opk.strip() == "" and _ock.strip() == "",
    "gate %r pr %r close %r" % (_ogk[:40], _opk[:40], _ock[:40]),
)

_dw = _iss_repo()
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dw, plan=_ISS_PLAN5), _dw)
_wt = os.path.join(_FIXTURE_ROOT, "iss-subagent-wt")
_as_git(_dw, "worktree", "add", "-q", "-b", "worktree-agent-iss", _wt)
_, _osub, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _wt, file_path=os.path.join(_wt, "a.cs")), _wt)
_, _omain, _ = _iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dw, file_path=os.path.join(_dw, "a.cs")), _dw)
commit_case(
    "issues: the main session's gate does not apply inside a subagent worktree (its own git directory)",
    _iss_decision(_omain) == "deny" and _osub.strip() == "", "main %r subagent %r" % (_iss_decision(_omain), _osub[:60]),
)

# -- #108: gh pr create ------------------------------------------------------------------------
_dp = _iss_repo()


def _iss_guard(cmd, d=None, **envx):
    d = d or _dp
    return _iss_call("guard", _iss_payload("PreToolUse", "Bash", d, command=cmd), d, **envx)[1]


_pr = lambda body: 'gh pr create --title "T" --body "%s"' % body
_ocl = _iss_guard(_pr("Closes #5"))
_issues_outputs.append(("pr closes", _ocl))
commit_case(
    "pr: a body with 'Closes #5' is denied and the reason explains the merge-time close",
    _iss_decision(_ocl) == "deny" and "before the user has tested" in _iss_reason(_ocl), "out %r" % _ocl[:140],
)
_bad = []
for _b in ("Fixes #5", "resolved #5", "FIXED owner/repo#7", "Close: #9", "closes https://github.com/o/r/issues/4"):
    if _iss_decision(_iss_guard(_pr(_b))) != "deny":
        _bad.append(_b)
commit_case("pr: every closing word in any tense, any case, with #N, owner/repo#N or a URL is denied", not _bad, "not denied: %r" % _bad)
_onr = _iss_guard(_pr("Just a change"))
commit_case(
    "pr: a body with no Refs / Part of / No-issue is denied",
    _iss_decision(_onr) == "deny" and "Refs #N" in _iss_reason(_onr), "out %r" % _onr[:140],
)
_bad = []
for _b in ("Refs #5", "Refs owner/repo#5", "Part of #12", "Summary\\n\\nNo-issue: typo fix"):
    if _iss_guard(_pr(_b)).strip():
        _bad.append(_b)
commit_case("pr: Refs #N, Refs owner/repo#N, Part of #N and a No-issue line are allowed", not _bad, "not allowed: %r" % _bad)
_heredoc = "gh pr create --title T --body \"$(cat <<'EOF'\n## Summary\nthings\n\nRefs #108, #109\nEOF\n)\""
commit_case("pr: a heredoc body carrying Refs is allowed", _iss_guard(_heredoc).strip() == "", "out %r" % _iss_guard(_heredoc)[:100])
_bf = os.path.join(_dp, "body.md")
open(_bf, "w", encoding="utf-8").write("Summary\n\nRefs #5\n")
_bfc = os.path.join(_dp, "bodyc.md")
open(_bfc, "w", encoding="utf-8").write("Summary\n\nFixes #5\n")
_bfn = os.path.join(_dp, "bodyn.md")
open(_bfn, "w", encoding="utf-8").write("Summary only\n")
commit_case(
    "pr: --body-file / -F is read: Refs allowed, closing word denied, no link denied",
    _iss_guard("gh pr create --title T --body-file body.md").strip() == ""
    and _iss_decision(_iss_guard("gh pr create -t T -F bodyc.md")) == "deny"
    and _iss_decision(_iss_guard("gh pr create --title T --body-file bodyn.md")) == "deny",
    "three file cases",
)
_ou = _iss_guard("gh pr create --title T --body-file missing.md")
_ow = _iss_guard("gh pr create --web")
_os = _iss_guard("gh pr create --title T --body-file -")
commit_case(
    "pr: an unreadable body file, stdin, and --web / no body all ask instead of allowing",
    _iss_decision(_ou) == "ask" and "could not read" in _iss_reason(_ou)
    and _iss_decision(_ow) == "ask" and _iss_decision(_os) == "ask",
    "missing %r web %r stdin %r" % (_iss_decision(_ou), _iss_decision(_ow), _iss_decision(_os)),
)
commit_case(
    "pr: commands that only mention gh pr create (a commit message, an echo) are not checked",
    all(_iss_guard(c).strip() == "" for c in ('echo "gh pr create is checked"', 'grep -r "gh pr create" docs')),
    "two commands that only mention it",
)

# -- #133: credit aj's agent, never Claude -------------------------------------------------------------
_att_trailer = "git commit -m \"$(cat <<'EOF'\nfix: thing\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nEOF\n)\""
_att_gen = "git commit -m \"feat: x\n\nGenerated with [Claude Code](https://claude.com/claude-code)\""
_att_ok = "git commit -m \"$(cat <<'EOF'\nfix: thing\n\nCommitted by AJ's agent\nEOF\n)\""
_att_word = "git commit -m \"docs: rename the Claude setting\""
_oa1, _oa2, _oa3, _oa4 = _iss_guard(_att_trailer), _iss_guard(_att_gen), _iss_guard(_att_ok), _iss_guard(_att_word)
commit_case(
    "attribution: a commit crediting Claude (co-author trailer or Generated-with line) is refused, naming the replacement",
    _iss_decision(_oa1) == "deny" and _iss_decision(_oa2) == "deny"
    and "Committed by AJ's agent" in _iss_reason(_oa1) and "no email" in _iss_reason(_oa1),
    "out %r | %r" % (_oa1[:140], _oa2[:100]),
)
_ota3 = _iss_decision(_oa3) != "deny" or "credit aj's agent" not in _iss_reason(_oa3)
commit_case(
    "attribution: crediting aj's agent with no email passes, and a subject that merely mentions Claude passes",
    "credit aj's agent" not in _oa3 and "credit aj's agent" not in _oa4,
    "out %r | %r" % (_oa3[:100], _oa4[:100]),
)
_opr1 = _iss_guard('gh pr create --title T --body "Refs #5\n\nGenerated with [Claude Code](https://claude.com/claude-code)"')
_opr2 = _iss_guard('gh pr create --title T --body "Refs #5\n\nOpened by AJ\'s agent"')
_opr3 = _iss_guard('gh pr create --title T --body "Refs #5\n\nhttps://claude.ai/code/session_abc"')
commit_case(
    "attribution: a pull request body crediting Claude or linking a Claude session is refused; crediting aj's agent passes",
    _iss_decision(_opr1) == "deny" and "credit aj's agent" in _iss_reason(_opr1)
    and _iss_decision(_opr3) == "deny" and "credit aj's agent" not in _opr2 and _opr2.strip() == "",
    "out %r | %r | %r" % (_opr1[:90], _opr2[:60], _opr3[:90]),
)
_oc1 = _iss_guard('gh issue comment 5 --body "Co-Authored-By: Claude <x>"')
_off = _iss_guard(_att_trailer, HOUSE_RULES_ATTRIBUTION="off")
commit_case(
    "attribution: an issue comment crediting Claude is refused, and HOUSE_RULES_ATTRIBUTION=off disables the check",
    _iss_decision(_oc1) == "deny" and "credit aj's agent" not in _off,
    "out %r | off %r" % (_oc1[:90], _off[:80]),
)
_opw = _iss_call("guard", _iss_payload("PreToolUse", "PowerShell", _dp, command=_att_trailer), _dp)[1]
commit_case(
    "attribution: the same refusal applies through the PowerShell tool",
    _iss_decision(_opw) == "deny" and "credit aj's agent" in _iss_reason(_opw),
    "out %r" % _opw[:140],
)

# -- #109: gh issue close ---------------------------------------------------------------------------
_occ = _iss_guard("gh issue close 5")
_issues_outputs.append(("issue close", _occ))
commit_case(
    "close: `gh issue close` asks, says the user must have tested, and tells Claude the label follow-up",
    _iss_decision(_occ) == "ask" and "tested" in _iss_reason(_occ) and "Claude completed this" in _iss_reason(_occ)
    and "Claude completed this" in json.loads(_occ)["hookSpecificOutput"].get("additionalContext", ""),
    "out %r" % _occ[:160],
)
_bad = []
for _c in ("gh issue close 5 --comment done", "gh issue edit 5 --state closed", "cd x && gh issue close 5",
           "gh api -X PATCH repos/o/r/issues/5 -f state=closed", "gh api repos/o/r/issues/5 --method PATCH -f state=closed"):
    if _iss_decision(_iss_guard(_c)) != "ask":
        _bad.append(_c)
commit_case("close: edit --state closed, a chained close and gh api PATCH to closed also ask", not _bad, "not asked: %r" % _bad)
_bad = []
for _c in ("gh issue comment 5 --body hi", 'gh issue create --title t --body b', "gh issue edit 5 --add-label bug",
           "gh api repos/o/r/issues/5", 'git commit -m "gh issue close 5 is gated"'):
    if _iss_decision(_iss_guard(_c)) == "ask" and "closing an issue" in _iss_reason(_iss_guard(_c)):
        _bad.append(_c)
commit_case("close: comment, create, label edits, reads and a commit message mentioning it are not affected", not _bad, "affected: %r" % _bad)
_ocm = _iss_guard("git add -A && git commit -m x && gh issue close 5")
commit_case(
    "close: a chained command asks once with both reasons in the prompt",
    _iss_decision(_ocm) == "ask" and "closing an issue" in _iss_reason(_ocm) and "writes history" in _iss_reason(_ocm),
    "out %r" % _ocm[:120],
)

# -- SessionStart open-issue list (issuelist) ---------------------------------------------------------
_dl = _iss_repo(remote="https://github.com/o/r.git")
if os.path.exists(_ISS_MARK):
    os.remove(_ISS_MARK)
_, _ol, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
_issues_outputs.append(("issuelist", _ol))
_lctx = _stop_context(_ol)
commit_case(
    "issuelist: a GitHub repo gets the open issue titles as SessionStart context",
    "#7 Fix the login screen" in _lctx and "#3 Add sound" in _lctx and "SessionStart" in _ol and len(_lctx) < 1200,
    "out %r" % _ol[:160],
)
_cachef = os.path.join(_as_git(_dl, "rev-parse", "--absolute-git-dir"), "house-rules-issues-cache.json")
try:
    _lmsg = json.loads(_ol).get("systemMessage", "")
except ValueError:
    _lmsg = "unparseable"
commit_case(
    "issuelist: the user sees `house-rules: 2 open issues loaded` in the same single JSON object as the context",
    _lmsg == "house-rules: 2 open issues loaded" and _lctx != "" and _ol.strip().count("\n") == 0,
    "systemMessage %r" % _lmsg,
)
_iss_stub(False)
_, _ol2, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
commit_case(
    "issuelist: a second start within 60 s uses the cache and does not call gh again",
    os.path.isfile(_cachef) and "#7 Fix the login screen" in _stop_context(_ol2), "out %r" % _ol2[:100],
)
os.remove(_cachef)
_, _ol3, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
commit_case(
    "issuelist: a gh failure prints `could not list open issues (<reason>)` and no context",
    "could not list open issues (HTTP 401: bad credentials" in _ol3 and _stop_context(_ol3) == "", "out %r" % _ol3[:160],
)
commit_case(
    "issuelist: a gh failure shows no 'loaded' note, only the could-not-list message",
    "loaded" not in _ol3 and "open issues" in _ol3, "out %r" % _ol3[:100],
)
os.remove(_cachef) if os.path.exists(_cachef) else None
_iss_stub("empty")
_, _ol3b, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl)
try:
    _emsg = json.loads(_ol3b).get("systemMessage", "")
except ValueError:
    _emsg = "unparseable"
commit_case(
    "issuelist: an empty list shows `house-rules: no open issues`",
    _emsg == "house-rules: no open issues", "systemMessage %r" % _emsg,
)
os.remove(_cachef) if os.path.exists(_cachef) else None
_iss_stub(True)
_dnr = _iss_repo(remote="git@example.com:o/r.git")
_, _ol4, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dnr}, _dnr)
_dnr2 = _iss_repo()
_, _ol5, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dnr2}, _dnr2)
# No gh on PATH is tested in-process, with shutil.which patched and then restored. A PATH built
# from dirname(SH) does not work: on a Linux runner gh lives in /usr/bin beside sh and git.
import importlib.util as _ig_util
_ig_spec = _ig_util.spec_from_file_location("hook_nogh", HOOK)
_ig_mod = _ig_util.module_from_spec(_ig_spec)
_ig_spec.loader.exec_module(_ig_mod)
_ig_which = shutil.which
shutil.which = lambda *_a, **_k: None
try:
    _ig_res = _ig_mod._open_issues_text(_dl)
finally:
    shutil.which = _ig_which
_ol6 = "" if _ig_res == ("", None) else "unexpected result %r" % (_ig_res,)
commit_case(
    "issuelist: no GitHub remote, no remote at all, or no gh on PATH is silent (nothing to list)",
    _ol4.strip() == "" and _ol5.strip() == "" and _ol6.strip() == "", "out %r %r %r" % (_ol4[:40], _ol5[:40], _ol6[:40]),
)
_, _ol7, _ = _iss_call("issuelist", {"hook_event_name": "SessionStart", "cwd": _dl}, _dl, HOUSE_RULES_ISSUES="off")
commit_case("issuelist: HOUSE_RULES_ISSUES=off prints nothing", _ol7.strip() == "", "out %r" % _ol7[:60])

# -- constraints the plan sets --------------------------------------------------------------------------
if os.path.exists(_ISS_MARK):
    os.remove(_ISS_MARK)
_iss_stub(True)
_dq = _iss_repo(remote="https://github.com/o/r.git")
_iss_call("delegate", _iss_payload("PostToolUse", "ExitPlanMode", _dq, plan=_ISS_PLAN5), _dq)
_iss_call("commitgate", _iss_payload("PreToolUse", "Write", _dq, file_path=os.path.join(_dq, "a.cs")), _dq)
_iss_created(_dq, _label_cmd, 1)
_iss_guard("gh issue close 5", _dq)
_iss_guard('gh pr create --title T --body "Refs #1"', _dq)
run_hook("handover", stop_payload(last_assistant_message="Done.", cwd=_dq), env=_iss_env())
commit_case(
    "issues: delegate, commitgate, the Bash PostToolUse entry, guard and handover never run gh (no network on a tool call)",
    not os.path.exists(_ISS_MARK), "gh stub marker present: %s" % os.path.exists(_ISS_MARK),
)
_multi = []
for _name, _o in _issues_outputs:
    if not _o.strip():
        continue
    try:
        json.loads(_o)
    except ValueError:
        _multi.append("%s: %r" % (_name, _o[:80]))
commit_case("issues: every new output parses as exactly one JSON object", not _multi, "; ".join(_multi) or "%d outputs checked" % len(_issues_outputs))

_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"]
# The agentcap entry runs only on an Agent spawn (plan: allowed), so it is exempt from this count.
# 11, not 10, since promptran (#149): one process per prompt-capable tool call, measured at about
# the same cost as artifact's, and the only way to tell the timer an action actually ran.
_non_agent = [g for g in _hj.get("PreToolUse", []) + _hj.get("PostToolUse", []) if not any("agentcap" in h["command"] for h in g["hooks"])]
_tool_cmds = [h["command"] for g in _non_agent for h in g["hooks"]]
_count_entries = sum(len(g["hooks"]) for g in _non_agent)
commit_case(
    "issues: no new hook process on Write/Edit/Bash - Pre/PostToolUse entries carry no issue-specific command",
    not any("issue" in c for c in _tool_cmds) and _count_entries == 11 and any('run.sh\\" issuelist' in json.dumps(g) for g in _hj["SessionStart"]),
    "%d Pre/PostToolUse entries; issuelist is on SessionStart" % _count_entries,
)
_rules_text = read(RULES_FILE)
_detail = os.path.join(DETAIL_DIR, "issue-workflow.md")
commit_case(
    "issues: the rules section and its detail file exist, and the plugin is 2.54.0",
    "becomes issues" in _rules_text and "rules/detail/issue-workflow.md" in _rules_text and os.path.isfile(_detail)
    and "HOUSE_RULES_ISSUES=off" in read(_detail)
    and json.load(open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"] == "2.54.0",
    "rules section + detail file + version",
)

commit_case(
    "the builder and archivist commit as they go, not only if asked",
    all(
        phrase in read(os.path.join(HERE, "..", "agents", n))
        and "only if asked to commit" not in read(os.path.join(HERE, "..", "agents", n))
        for n, phrase in (("builder.md", "Commit as you go"), ("archivist.md", "Commit each finished piece as you go"))
    ),
    "agents/builder.md, agents/archivist.md",
)

# profile: a saved memory restating the replaced commit rule is flagged at session start.
_mem = tempfile.mkdtemp(prefix="house-rules-memory-", dir=_FIXTURE_ROOT)
with open(os.path.join(_mem, "MEMORY.md"), "w", encoding="utf-8") as f:
    f.write("# Memory\n\n- Never run git actions; commit before destructive changes\n")
with open(os.path.join(_mem, "other.md"), "w", encoding="utf-8") as f:
    f.write("- prefers tabs over spaces\n")
_, out, _ = run_hook("profile", "", env=_project_env(_FIXTURE_ROOT, HOUSE_RULES_MEMORY_DIR=_mem))
commit_case(
    "profile: a memory restating the old commit rule is flagged by file and line at session start",
    "restates the old commit rule" in out and "MEMORY.md:3" in out and "other.md" not in out,
    "found: %s" % ("yes" if "restates the old commit rule" in out else "no"),
)
_clean_mem = tempfile.mkdtemp(prefix="house-rules-memory-clean-", dir=_FIXTURE_ROOT)
with open(os.path.join(_clean_mem, "MEMORY.md"), "w", encoding="utf-8") as f:
    f.write("- Commit freely on claude/ branches\n")
_, out, _ = run_hook("profile", "", env=_project_env(_FIXTURE_ROOT, HOUSE_RULES_MEMORY_DIR=_clean_mem))
commit_case(
    "profile: a memory that agrees with the commit rule adds nothing",
    "restates the old commit rule" not in out,
    "flagged: %s" % ("yes" if "restates the old commit rule" in out else "no"),
)

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

# --- the restatement table --------------------------------------------------------------------
# Each restatement of a house rule is one row, checked both directions at once (rules corpus and
# its own emitted source) - adding a restatement to check is a row here, not a new drift block.
# emitted_only holds phrases about the note's own behaviour that the rules never state, so they
# can only be checked one way - but deleting one from the emitted note must still fail.
Restatement = namedtuple("Restatement", "name source phrases case_sensitive emitted_only")
Restatement.__new__.__defaults__ = ((),)

RESTATEMENTS = [
    Restatement(
        "the scope reminder (long form)",
        lambda: run_hook("scope", json.dumps({"prompt": "run the build script"}))[1],
        [
            "response depth", "only what was asked", "ask instead of assuming",
            "project directory", "hand over a command", "tier that changed",
            "success claim", "whole workflow", "have not run", "own branch", "branch off first",
        ],
        False,
    ),
    Restatement(
        "the Stop commit note (#97), on the user's branch",
        lambda: (lambda r: run_hook(
            "handover",
            stop_payload(transcript_path=_wrote_transcript("restate-commit", [os.path.join(r, "a.py")]),
                         last_assistant_message="Changed a.py."),
            env=_project_env(r),
        )[1])(_commit_repo("main", committed=["a.py"], dirty=["a.py"])),
        ["own branch", "branch off first", "scoped to"],
        False,
        ("commit on your own branch", "scoped to those paths", "say what you committed and where",
         "not a checkpoint", "claude/<topic>"),
    ),
    Restatement(
        "the branch nudge (#97)",
        lambda: (lambda r: _nudge(r, "a.py"))(_commit_repo("main", committed=["a.py"], dirty=["a.py"])),
        ["own branch", "branch off", "scoped to"],
        False,
        ("commit on your own branch", "scoped to the paths you changed", "only uncommitted change"),
    ),
    Restatement(
        "the compile-verification note (runnable handler, .cs files)",
        lambda: run_hook(
            "runnable", json.dumps({"tool_input": {"file_path": r"C:\proj\Assets\Scripts\Enemy.cs"}})
        )[1],
        ["should compile", "stand-in", "real compiler", "batch mode", "dotnet build"],
        False,
    ),
    Restatement(
        "the runnable note (runnable handler, scripts)",
        lambda: run_hook("runnable", json.dumps({"tool_input": {"file_path": r"C:\proj\deploy.sh"}}))[1],
        [
            "whole workflow", "starting point", "hand over a command", "run it twice",
            "realistic", "not proof it works",
        ],
        False,
        ("someone thought to write",),
    ),
    Restatement(
        "the delegate reminder (ExitPlanMode, including the worktree-isolation mandate)",
        lambda: run_hook("delegate", "")[1],
        [
            "@house-rules:builder", "plan is settled", "proactiv", "one file",
            "three steps or fewer", "one delegation per group", "isolation", "worktree",
        ],
        False,
    ),
    Restatement(
        "the harvest reminder (long-form comments)",
        lambda: run_hook(
            "harvest",
            json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/proj/Orbit.cs", "content": ESSAY_CS}}),
        )[1],
        [
            "long-form", "one-line pointer", "@house-rules:archivist", "docs/4-systems",
            "docs/6-decisions/Decisions.md", "doc-ref", "docref.py", "<!-- ref:",
            "How it works", "Traps", "Invariants",
        ],
        False,
        ("Do not change how you write", "the user was not prompted"),
    ),
    Restatement(
        "the command-handover checklist (Stop hook)",
        lambda: run_hook(
            "handover",
            json.dumps(
                {
                    "session_id": "verify",
                    "hook_event_name": "Stop",
                    "stop_hook_active": False,
                    "last_assistant_message": "```powershell\nGet-ChildItem\n```",
                }
            ),
        )[1],
        [
            "fence label", "working directory", "UNTESTED", "Run button",
            "not depend on where the prompt is", "open a terminal or PowerShell there",
            "One numbered step per action", "step-card format", "Step 1 of",
            "You should see:", "above the fence", "Replacing step",
            "never announces its own compliance",
        ],
        False,
    ),
]

for _restatement in RESTATEMENTS:
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
    if "@house-rules:builder" not in out:
        bad.append("it does not name the builder subagent")
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
if "@house-rules:builder" not in rules_text:
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


# --- the tier agents exist, each pinned to its model, with the tool allowlist the plan set -------
TIER_TOOLS = {
    "scout": ["Read", "Grep", "Glob"],
    "builder": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "reviewer": ["Read", "Grep", "Glob", "Bash"],
}
agentdrift = []
for _name, _model in TIERS.items():
    _f = os.path.join(AGENTS_DIR, _name + ".md")
    if not os.path.isfile(_f):
        agentdrift.append(f"agents/{_name}.md is missing")
        continue
    _t = read(_f)
    if not re.search(rf"^model: {_model}$", _t, re.MULTILINE):
        agentdrift.append(f"{_name}.md does not pin model: {_model}")
    if not re.search(rf"^name: {_name}$", _t, re.MULTILINE):
        agentdrift.append(f"{_name}.md has no name: {_name}")
    _tm = re.search(r"^tools:\s*(.+)$", _t, re.MULTILINE)
    _got = [x.strip() for x in _tm.group(1).split(",")] if _tm else []
    if _got != TIER_TOOLS[_name]:
        agentdrift.append(f"{_name}.md tools are {_got}, expected {TIER_TOOLS[_name]}")
    if "Agent" in _got:
        agentdrift.append(f"{_name}.md allows the Agent tool, so it could start subagents")
    _body = _t.split("---", 2)[-1].strip().splitlines()
    if len(_body) > 15:
        agentdrift.append(f"{_name}.md body is {len(_body)} lines, the limit is 15")
    for dead in ["hooks", "mcpServers", "permissionMode"]:
        if re.search(rf"^{dead}:", _t, re.MULTILINE):
            agentdrift.append(f"{_name}.md sets {dead}, which plugin subagents ignore")
if os.path.isfile(os.path.join(AGENTS_DIR, "executor.md")):
    agentdrift.append("agents/executor.md still exists, it was retired")
if not agentdrift:
    report("PASS", "the scout, builder and reviewer agents exist, pinned to haiku, sonnet and opus")
    print("          short tool allowlists, no Agent tool, bodies of 15 lines or fewer, executor.md gone")
else:
    report("FAIL", "the scout, builder and reviewer agents exist, pinned to haiku, sonnet and opus")
    print(f"          {'; '.join(agentdrift)}")

# --- no live file still names the retired executor agent ----------------------------------------
_stale = []
_skip_dirs = {".git", "node_modules", "__pycache__", "sessions", "archive", "plans", "generated", "worktrees"}
for _dp, _dns, _fns in os.walk(ROOT):
    _dns[:] = [d for d in _dns if d not in _skip_dirs and d != "6-decisions"]
    for _fn in _fns:
        if not _fn.endswith((".md", ".py", ".json", ".sh", ".bat", ".ps1", ".yml", ".html")):
            continue
        _fp = os.path.join(_dp, _fn)
        if os.path.abspath(_fp) == os.path.abspath(__file__):
            continue
        try:
            if "house-rules:executor" in read(_fp):
                _stale.append(os.path.relpath(_fp, ROOT))
        except OSError:
            pass
if not _stale:
    report("PASS", "no live file still names house-rules:executor")
    print("          docs/sessions, docs/archive, docs/plans and past Decisions entries are history and not scanned")
else:
    report("FAIL", "no live file still names house-rules:executor")
    print(f"          still named in: {', '.join(_stale)}")

# --- archivist.md does not claim the rules are already in its context, and carries a digest ----
# A clean spawn was asked directly and answered no: SessionStart additionalContext does not
# reach subagents. The tier files carry no digest (the subagentrules hook injects the core);
# archivist.md keeps its own, so only it is checked here.
digestdrift = []
if not os.path.isfile(ARCHIVIST):
    digestdrift.append("agents/archivist.md is missing")
else:
    agent_text = read(ARCHIVIST)
    if "already in this session" in agent_text.lower():
        digestdrift.append("archivist.md still claims the rules are already in its context")
    for phrase in [
        "not injected",
        "hand over a command you have not run",
        "step-card format",
        "commit messages",
    ]:
        if phrase.lower() not in agent_text.lower():
            digestdrift.append(f"archivist.md digest is missing: {phrase!r}")
if not digestdrift:
    report("PASS", "archivist.md carries its own rules digest instead of assuming inherited context")
    print("          no 'already in this session' claim; the digest covers the load-bearing rules")
else:
    report("FAIL", "archivist.md carries its own rules digest instead of assuming inherited context")
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
    # The style is now the single copy of the six-field checklist (docs/6-decisions/Decisions.md,
    # 2026-09-22); the check below this one proves the core points here instead of restating it.
    for phrase in ["runs from anywhere", "One numbered step per action", "UNTESTED:"]:
        if phrase not in style_text:
            styledrift.append(f"the style no longer restates {phrase!r} from the six items")
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

# --- the core's card section points at the output style instead of restating it --------------
# Moved out of house-rules.md 2.17.0 to stay under the per-hook context limit (docs/6-decisions/Decisions.md,
# 2026-09-22): the core keeps a one-line pointer, the output style keeps the actual checklist.
cardptr = []
_core_text = read(RULES_FILE)
_card_sec = _core_text.split("#### The card", 1)
if len(_card_sec) != 2:
    cardptr.append("'#### The card' heading is missing from house-rules.md")
else:
    _pointer_body = _card_sec[1].split("\n## ", 1)[0]
    if "handover-cards" not in _pointer_body:
        cardptr.append("the core's card section does not name the handover-cards output style")
    for phrase in ["runs from anywhere", "One numbered step per action", "UNTESTED:"]:
        if phrase in _pointer_body:
            cardptr.append(f"{phrase!r} is restated in the core instead of pointed at")
if not cardptr:
    report("PASS", "the core's card section points at the output style instead of restating it")
    print("          house-rules.md names handover-cards.md; the six-field text lives there only")
else:
    report("FAIL", "the core's card section points at the output style instead of restating it")
    print(f"          {'; '.join(cardptr)}")

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

# --- every surface the architecture.md table claims has a way to be checked ------------------
# The table moved from CLAUDE.md to docs/architecture.md (docs/6-decisions/Decisions.md, 2026-09-22, step 2);
# surface names are read out of the table itself rather than hardcoded here.
surfdrift = []
surfaces = []
_absent = absent_repo_files("docs/desktop-verification.md", "docs/architecture.md")
if _absent:
    skip_repo_check(
        "every surface in the architecture.md table has a check in desktop-verification.md", _absent
    )
elif not os.path.isfile(VERIFYDOC):
    surfdrift.append("docs/desktop-verification.md is missing")
elif not os.path.isfile(ARCHDOC):
    surfdrift.append("docs/architecture.md is missing, so the table it claims cannot be read")
else:
    verify_doc = read(VERIFYDOC)
    for line in read(ARCHDOC).splitlines():
        m = re.match(r"^\| (?:Claude Code|claude\.ai chat) [-\u2014 ]+([^|]+?) \|", line)
        if m:
            surfaces.append(m.group(1).strip())
    if not surfaces:
        surfdrift.append("no surface rows found in docs/architecture.md - has the table been renamed?")
    for s in surfaces:
        if s not in verify_doc:
            surfdrift.append(f"{s!r} is in the architecture.md table but has no check in desktop-verification.md")
if _absent:
    pass  # already reported as skipped above
elif not surfdrift:
    report("PASS", "every surface in the architecture.md table has a check in desktop-verification.md")
    print(f"          {len(surfaces)} surfaces claimed, {len(surfaces)} covered: {', '.join(surfaces)}")
else:
    report("FAIL", "every surface in the architecture.md table has a check in desktop-verification.md")
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
_absent = absent_repo_files("docs/architecture.md")
if _absent:
    pass  # the rules half above still ran; only the table half is unavailable here
elif os.path.isfile(ARCHDOC):
    table_text = read(ARCHDOC)
    rows = [ln for ln in table_text.splitlines() if ln.startswith("| Claude Code")]
    offered = [ln for ln in rows if "offered at 2+ steps" in ln]
    if not offered:
        pubdrift.append("no architecture.md surface row states 'offered at 2+ steps'")
    if "4+ steps" in table_text:
        pubdrift.append("docs/architecture.md still advertises the replaced '4+ steps' threshold")
else:
    pubdrift.append("no docs/architecture.md to check")
if pubdrift and _absent:
    report("FAIL", "the page rule and the architecture.md table agree, and nothing publishes unasked")
    for p in pubdrift:
        print(f"          {p}")
elif _absent:
    skip_repo_check(
        "the page rule and the architecture.md table agree, and nothing publishes unasked",
        _absent,
        extra="the rules half was checked here and passed; only the table half is unavailable",
    )
elif not pubdrift:
    report("PASS", "the page rule and the architecture.md table agree, and nothing publishes unasked")
    print("          rule: offer at 2+ steps, publish only on request; table says the same")
else:
    report("FAIL", "the page rule and the architecture.md table agree, and nothing publishes unasked")
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

# --- the scout and builder descriptions authorize proactive use ----------------------------------------
_proactive = [n for n in ("scout", "builder")
              if "proactiv" not in read(os.path.join(AGENTS_DIR, n + ".md")).lower()]
if not _proactive:
    report("PASS", "the scout and builder descriptions authorize proactive use")
    print('          description contains "proactively", satisfying the Agent tool\'s own gate')
else:
    report("FAIL", "the scout and builder descriptions authorize proactive use")
    print(f'          {", ".join(_proactive)}: description has no "proactively" (or similar) wording')

# --- install.py still writes the model setting the README claims ------------------------------
install_path = os.path.join(ROOT, "tools", "install.py")
readme_rel = os.path.join("claude-house-rules", "README.md")
moddrift = []
_absent = absent_repo_files(os.path.join("tools", "install.py"), readme_rel, "docs/architecture.md")
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
for docfile in [readme_path, ARCHDOC]:
    if os.path.isfile(docfile):
        if "cli and the ide" not in read(docfile).lower():
            moddrift.append(
                f"{os.path.basename(docfile)} does not say opusplan covers only the CLI and the IDE"
            )
if _absent:
    pass  # already reported as skipped above
elif not moddrift:
    report("PASS", "install.py sets model = opusplan and the docs scope it correctly")
    print("          opusplan on the CLI and IDE; every other surface via @house-rules:builder")
else:
    report("FAIL", "install.py sets model = opusplan and the docs scope it correctly")
    print(f"          {'; '.join(moddrift)}")

# --- preflight warns about a missing dependency, and points at /house-rules:doctor -----------
env = dict(os.environ)
env["PATH"] = ""
code, out, err = run_hook("profile", "", env=env)
if "Preflight gaps found" in out and "git is not on PATH" in out and "/house-rules:doctor" in out:
    report("PASS", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print("          a broken PATH produces a visible, actionable preflight warning")
else:
    report("FAIL", "SessionStart preflight warns when git is missing and points at /house-rules:doctor")
    print(f"          got: {out[-400:]!r}")

code, out, err = run_hook("profile", "")
if "Preflight gaps found" not in out:
    report("PASS", "SessionStart preflight is silent when there is nothing to warn about")
    print("          a clean machine adds nothing to the injection")
else:
    report("FAIL", "SessionStart preflight is silent when there is nothing to warn about")
    print(f"          got: {out[-400:]!r}")

# --- profile truncates only the environment body, never preflight or the handover block -------
# Coordinator review of 9e7e780: the first cut truncated the WHOLE assembled profile text, which
# could in principle have cut into preflight warnings or the remote handover-target block instead
# of just the oversized profile. Fixed to truncate envbody alone; this proves it.
_oversized_env = os.path.join(_FIXTURE_ROOT, "oversized-environment.md")
with open(_oversized_env, "w", encoding="utf-8") as _f:
    _f.write("# Huge profile\n\n" + ("filler line about this machine\n" * 2000))
_handover_fixture2 = os.path.join(_FIXTURE_ROOT, "handover-target-2.md")
with open(_handover_fixture2, "w", encoding="utf-8") as _f:
    _f.write("# The human's machine\n\nWindows 11, PowerShell, Git Bash for POSIX.\n")
_env = env_in(
    ROOT,
    PATH="",  # also forces a preflight warning, so both survivors are exercised at once
    HOUSE_RULES_ENV_FILE=_oversized_env,
    CLAUDE_CODE_REMOTE="true",
    HOUSE_RULES_HANDOVER_TARGET_FILE=_handover_fixture2,
)
_code, _trunc_out, _err = run_hook("profile", "", env=_env)
_trunc_problems = []
if "Git Bash for POSIX" not in _trunc_out:
    _trunc_problems.append("the handover-target block did not survive truncation intact")
if "Preflight gaps found" not in _trunc_out:
    _trunc_problems.append("preflight warnings did not survive truncation intact")
if os.path.basename(_oversized_env) not in _trunc_out and _oversized_env not in _trunc_out:
    _trunc_problems.append("the truncation notice does not name the oversized file")
if not _trunc_problems:
    report("PASS", "profile truncates only the environment body, never preflight or the handover block")
    print(f"          {len(_trunc_out)} chars total; handover block and preflight both intact")
else:
    report("FAIL", "profile truncates only the environment body, never preflight or the handover block")
    print(f"          {'; '.join(_trunc_problems)}")

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

# --- the architecture tables in docs/architecture.md and the README match hooks.json ----------
# Registered dispatch events, read from hooks.json's run.sh invocations rather than filenames -
# there is only one script (run.sh) now, dispatched by event argument. The table moved from
# CLAUDE.md to docs/architecture.md (docs/6-decisions/Decisions.md, 2026-09-22, step 2).
registered_events = sorted(set(re.findall(r'run\.sh\\" ([a-z]+)', hooks_json_text)))
docdrift = []
_absent = absent_repo_files("docs/architecture.md", readme_rel)
for doc in ([] if _absent else [ARCHDOC, readme_path]):
    docname = os.path.basename(doc)
    if not os.path.isfile(doc):
        docdrift.append(f"no {docname} to check")
        continue
    doc_text = read(doc)
    table_lines = "\n".join(
        line
        for line in doc_text.splitlines()
        if re.match(r"^\| `(SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|PermissionRequest|Stop|SubagentStart|SubagentStop)`", line)
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
    report("FAIL", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print(f"          {'; '.join(docdrift)}")
elif _absent:
    skip_repo_check(
        "the architecture tables in docs/architecture.md and the README match hooks.json",
        _absent,
        extra="scripts/ was checked here and holds no stray .sh; only the doc tables are unavailable",
    )
elif not docdrift:
    report("PASS", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print("          every registered hook event is documented and no stray .sh script exists")
else:
    report("FAIL", "the architecture tables in docs/architecture.md and the README match hooks.json")
    print(f"          {'; '.join(docdrift)}")

# --- the "What trips the guard" README table matches GUARD_R3/GUARD_R4's actual git verbs -----
# Why this tokenizes the table instead of hand-copying the verb list, and the incident that
# made it necessary: docs/4-systems/verify-suites.md, Invariants ("The guarded-verb list is
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

# --- standards stays under budget in Unity projects, where the Unity rule now lives ----------
# The standards budget was only ever measured in this repo, which has no Unity markers, so a
# Unity project sailed past the 10,000-char hard limit unseen (docs/6-decisions/Decisions.md,
# 2026-09-29). These two fixtures are the check that was missing.
STANDARDS_BUDGET = 9_500


def _standards_len(out):
    try:
        return len(json.loads(out)["hookSpecificOutput"]["additionalContext"])
    except Exception as exc:
        return f"unparseable ({exc}): {out[:120]!r}"


for _title, _files in [
    ("a Unity-only project", {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"}),
    ("a Unity + Node project", {"Assets/Scripts/a.cs": "", "package.json": "{}"}),
]:
    def _within_budget(out):
        n = _standards_len(out)
        return isinstance(n, int) and n <= STANDARDS_BUDGET, f"{n} chars (budget {STANDARDS_BUDGET}, hard limit 10,000)"

    std_case(f"standards stays under its {STANDARDS_BUDGET:,}-char budget in {_title}", _files, _within_budget)

_UNITY_RULE_HEADING = "## Unity work starts with the Unity plugin and the Unity CLI"
std_case(
    "the Unity tools-first rule reaches a Unity project through standards, with both pointers",
    {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.1f1\n"},
    lambda out: (
        _UNITY_RULE_HEADING in out
        and "rules/detail/unity-tools-first.md" in out
        and "rules/standards/csharp-unity-detail.md" in out
        and "${CLAUDE_PLUGIN_ROOT}" not in out,
        f"got: {_standards_len(out)} chars; heading={_UNITY_RULE_HEADING in out}",
    ),
)
std_case(
    "the Unity tools-first rule does not reach a project with no Unity markers",
    {},
    lambda out: (_UNITY_RULE_HEADING not in out, "a bare directory got the Unity rule" if _UNITY_RULE_HEADING in out else "absent, as intended"),
)
_, _inject_out, _ = run_hook("inject", "", env=env_in(ROOT))
_core_text = read(RULES_FILE)
if (
    "Unity work starts" not in _inject_out
    and "unity-tools-first" not in _inject_out
    and "Unity work starts" not in _core_text
):
    report("PASS", "the Unity tools-first rule is not in the always-injected core")
    print("          neither house-rules.md nor the inject output carries it")
else:
    report("FAIL", "the Unity tools-first rule is not in the always-injected core")
    print("          the Unity rule is still in house-rules.md or the inject output")
_unity_detail = os.path.join(STANDARDS_DIR, "csharp-unity-detail.md")
if os.path.isfile(_unity_detail) and all(
    h in read(_unity_detail)
    for h in ("## Unity-specific patterns", "## Performance", "## Testing", "## Verifying compilation", "## Tooling (Rider)")
):
    report("PASS", "rules/standards/csharp-unity-detail.md holds the Unity sections moved out of the core")
    print("          all five named sections are present")
else:
    report("FAIL", "rules/standards/csharp-unity-detail.md holds the Unity sections moved out of the core")
    print(f"          {_unity_detail} is missing or lacks a moved section")

# --- the profile reports hardware and the Claude plan, and says so when it cannot -----------
# PATH is replaced by a directory holding only the fakes each case wants, so the result does not
# depend on whether this machine has nvidia-smi or a logged-in claude. POSIX shell fakes.
def _fake_bin(**scripts):
    d = tempfile.mkdtemp(prefix="house-rules-fakebin-")
    for name, body in scripts.items():
        path = os.path.join(d, name.replace("_", "-"))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(path, 0o755)
    return d


def _profile_out(path_dir, remote=False, **extra):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_REMOTE", None)
    env["PATH"] = path_dir
    env["HOUSE_RULES_ENV_FILE"] = "/nonexistent-on-purpose-env"
    env["HOUSE_RULES_HANDOVER_TARGET_FILE"] = "/nonexistent-on-purpose-handover"
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "1"
    env.update(extra)
    _, out, _ = run_hook("profile", "", env=env)
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return out


if os.name == "nt":
    for _t in ("the profile names CPU, RAM, GPU, free disk and Claude plan",
               "a missing nvidia-smi is reported as 'GPU: not detected (...)'",
               "a claude that reports no plan field is 'Claude plan: not detected (...)'",
               "a claude that reports a plan field has it shown",
               "nvidia-smi output is reported as GPU name and VRAM"):
        report("SKIP", _t + " (the fakes are POSIX shell scripts)")
else:
    _no_plan = _fake_bin(claude='echo \'{"loggedIn":true,"authMethod":"oauth_token","apiProvider":"firstParty"}\'')
    _with_plan = _fake_bin(claude='echo \'{"loggedIn":true,"subscriptionType":"max"}\'',
                           nvidia_smi='echo "NVIDIA Test GPU, 8192 MiB"')
    _empty = tempfile.mkdtemp(prefix="house-rules-emptybin-")
    try:
        _p = _profile_out(_no_plan)
        _missing = [f for f in ("CPU:", "RAM:", "GPU:", "Free disk:", "Claude plan:") if f not in _p]
        report("PASS" if not _missing else "FAIL", "the profile names CPU, RAM, GPU, free disk and Claude plan")
        print(f"          missing fields: {_missing}" if _missing else "          all five field names present")

        _gpu_line = next((l for l in _p.splitlines() if l.startswith("GPU:")), "")
        report("PASS" if _gpu_line.startswith("GPU: not detected (") and "nvidia-smi" in _gpu_line else "FAIL",
               "a missing nvidia-smi is reported as 'GPU: not detected (...)'")
        print(f"          {_gpu_line!r}")

        _plan_line = next((l for l in _p.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan_line.startswith("Claude plan: not detected (") and "no plan field" in _plan_line else "FAIL",
               "a claude that reports no plan field is 'Claude plan: not detected (...)'")
        print(f"          {_plan_line!r}")

        _p2 = _profile_out(_with_plan)
        _plan2 = next((l for l in _p2.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan2.startswith("Claude plan: max") else "FAIL",
               "a claude that reports a plan field has it shown")
        print(f"          {_plan2!r}")

        _gpu2 = next((l for l in _p2.splitlines() if l.startswith("GPU:")), "")
        report("PASS" if "NVIDIA Test GPU" in _gpu2 and "8192 MiB" in _gpu2 else "FAIL",
               "nvidia-smi output is reported as GPU name and VRAM")
        print(f"          {_gpu2!r}")

        _p3 = _profile_out(_empty)
        _plan3 = next((l for l in _p3.splitlines() if l.startswith("Claude plan:")), "")
        report("PASS" if _plan3.startswith("Claude plan: not detected (claude not on PATH)") else "FAIL",
               "no claude on PATH is 'Claude plan: not detected (claude not on PATH)'")
        print(f"          {_plan3!r}")
    finally:
        for _d in (_no_plan, _with_plan, _empty):
            shutil.rmtree(_d, ignore_errors=True)

# --- a remote profile never presents the sandbox's hardware as the local build budget --------
_remote_empty = tempfile.mkdtemp(prefix="house-rules-emptybin-")
try:
    _r = _profile_out(_remote_empty, remote=True)
    _r_ok = (
        "NOT the user's local build budget" in _r
        and "rules/handover-target.md" in _r
        and "## Hardware (the local build budget)" not in _r
        and "Ask for their hardware" in _r
    )
    report("PASS" if _r_ok else "FAIL",
           "a remote profile labels detected hardware as the sandbox's and asks for the user's")
    print("          sandbox label, handover-target pointer and hardware question present" if _r_ok
          else f"          got: {_r[-900:]!r}")
    _l = _profile_out(_remote_empty, remote=False)
    report("PASS" if "## Hardware (the local build budget)" in _l and "NOT the user's" not in _l else "FAIL",
           "a local profile calls the detected hardware the local build budget")
    print("          local label present, no sandbox caveat")
finally:
    shutil.rmtree(_remote_empty, ignore_errors=True)

# --- the open-source-first rule and its detail file agree ------------------------------------
_free_detail = os.path.join(DETAIL_DIR, "free-first.md")
_core = read(RULES_FILE)
_free_problems = []
if not os.path.isfile(_free_detail):
    _free_problems.append("rules/detail/free-first.md does not exist")
else:
    _fd = read(_free_detail)
    _core_rungs = ["Local OSS", "cloud OSS", "local free closed", "cloud free closed", "→ paid"]
    _detail_rungs = ["Local open source", "Cloud open source", "Local free closed source",
                     "Cloud free closed source", "Any paid option"]
    _core_rule = _core[_core.find("## Open source first"):].split("\n## ")[0]
    for label, text, rungs in (("house-rules.md", _core_rule, _core_rungs), ("free-first.md", _fd, _detail_rungs)):
        pos = [text.find(r) for r in rungs]
        if min(pos) < 0:
            _free_problems.append(f"{label} lacks ladder rung(s): {[r for r, p in zip(rungs, pos) if p < 0]}")
        elif pos != sorted(pos):
            _free_problems.append(f"{label} names the ladder rungs out of order")
    for phrase in ("OSI-approved", "Pro or Max", "Break-even", "guess"):
        if phrase not in _fd:
            _free_problems.append(f"free-first.md lacks {phrase!r}")
if "## Open source first; paid is the last resort" not in _core:
    _free_problems.append("house-rules.md lacks the rule heading")
if "${CLAUDE_PLUGIN_ROOT}/rules/detail/free-first.md" not in _core:
    _free_problems.append("house-rules.md does not point at rules/detail/free-first.md")
if "## Open source first; paid is the last resort" in _core and "## Match response depth" in _core and \
        _core.index("## Open source first") > _core.index("## Match response depth"):
    _free_problems.append("the rule is not placed before 'Match response depth'")
if "free-first.md" not in read(os.path.join(DETAIL_DIR, "environment.md")):
    _free_problems.append("environment.md does not link free-first.md")
report("FAIL" if _free_problems else "PASS", "the open-source-first rule and rules/detail/free-first.md exist and agree")
print(f"          {'; '.join(_free_problems)}" if _free_problems else "          heading, pointer, ladder order in both files, estimate table terms all present")

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
    if "@house-rules:builder" not in text:
        goahead.append(f"{prompt!r} is a go-ahead but got no delegation clause")
for prompt in ("what does this function do?", "explain the guard handler",
               "why did the suite fail?"):
    code, text = scope_text(prompt)
    if "@house-rules:builder" in text:
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
for phrase in ("@house-rules:builder", "proactiv", "one file", "three steps or fewer"):
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
def _user_result(tool_use_id, is_error=False):
    return json.dumps({
        "type": "user",
        "message": {"content": [{"type": "tool_result", "tool_use_id": tool_use_id, "is_error": is_error}]},
    })


# audit1: the case the audit summary exists for - one ok command, one failing command, one
# write, seen from the transcript itself, never from what the subagent says about itself.
_transcript("audit1", [
    _assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                "input": {"command": "pytest -q"}}]),
    _user_result("t1", is_error=False),
    _assistant("claude-sonnet-4-5-20250929", [
        {"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": "/proj/a.py"}},
        {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "false"}},
    ]),
    _user_result("t3", is_error=True),
])
# auditbig: 45 commands, to prove the 40-command cap and the "N more" line.
_transcript("auditbig", sum((
    [_assistant("claude-sonnet-4-5-20250929", [{"type": "tool_use", "id": "b%d" % i, "name": "Bash",
                                                 "input": {"command": "echo %d" % i}}]),
     _user_result("b%d" % i)]
    for i in range(45)
), []))
_PARENT = os.path.join(_SUB_ROOT, "sess1.jsonl")
with open(_PARENT, "w", encoding="utf-8") as _f:
    _f.write("")


def sub_payload(**kw):
    base = {"session_id": "sess1", "transcript_path": _PARENT}
    base.update(kw)
    return json.dumps(base)


# announce names the agent, what it DECLARES, the plugin version and the digest fingerprint.
code, out, err = run_hook("announce", sub_payload(
    hook_event_name="SubagentStart", agent_type="house-rules:builder", agent_id="x1", effort="low"
))
ann = []
if code != 0:
    ann.append(f"exit {code}, must never be non-zero")
for needle in ("house-rules:builder", "declared model sonnet", "digest ", "house-rules 2."):
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
code, out, err = run_hook("announce", sub_payload(agent_type="house-rules:builder"), env=_ovr)
if "CLAUDE_CODE_SUBAGENT_MODEL_FORCE" in out and "may not be what runs" in out:
    report("PASS", "announce warns when a model-override env var is set")
    print("          names the variable that can silently override the declared model")
else:
    report("FAIL", "announce warns when a model-override env var is set")
    print(f"          out {out[:200]!r}")

# verdict turns the declaration into evidence: the model that actually served the subagent.
code, out, err = run_hook("verdict", sub_payload(
    hook_event_name="SubagentStop", agent_type="house-rules:builder", agent_id="sonnet"
))
if code == 0 and "claude-sonnet-4-5-20250929" in out and "MATCH" in out and "2 assistant turns" in out:
    report("PASS", "verdict reports the model that actually served the subagent")
    print(f"          {out[:150]}")
else:
    report("FAIL", "verdict reports the model that actually served the subagent")
    print(f"          exit {code}, out {out[:200]!r}")

# The case the whole feature exists for: declared Sonnet, actually ran on something else.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="opus"))
if code == 0 and "MISMATCH" in out and "claude-opus-5" in out:
    report("PASS", "verdict reports MISMATCH when the observed model is not the declared one")
    print("          a delegation that did not run on what it declares is now visible")
else:
    report("FAIL", "verdict reports MISMATCH when the observed model is not the declared one")
    print(f"          exit {code}, out {out[:200]!r}")

# The completion-sanity check: zero tool calls across the whole transcript is exactly the
# hollow "stop" that let a duplicate delegation get dispatched.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "0 tool calls" in out:
    report("PASS", "verdict flags a completion with zero tool calls")
    print("          a status-update-only finish is now visible, not read as done work")
else:
    report("FAIL", "verdict flags a completion with zero tool calls")
    print(f"          exit {code}, out {out[:200]!r}")

# One tool call present (so the zero-tool-calls path does not fire), but the last message
# still reads like a deferral - the other half of the same signal.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="deferral"))
if code == 0 and "SUSPICIOUS COMPLETION" in out and "i'll report back" in out.lower():
    report("PASS", "verdict flags a last message that matches a deferral phrase")
    print("          names the phrase, does not fire the zero-tool-calls branch instead")
else:
    report("FAIL", "verdict flags a last message that matches a deferral phrase")
    print(f"          exit {code}, out {out[:200]!r}")

# An ordinary finish - tool calls present, last message an ordinary summary - must not
# false-positive as a suspicious completion.
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="normal"))
if code == 0 and "SUSPICIOUS COMPLETION" not in out:
    report("PASS", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print("          no false positive on a normal completion")
else:
    report("FAIL", "verdict does not flag an ordinary did-the-work-then-reported-back finish")
    print(f"          exit {code}, out {out[:200]!r}")

# Nothing fails silently: every "I could not tell" path says so, and says what it tried.
quiet = []
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="ghost"))
if code != 0 or "unverified" not in out or "tried:" not in out:
    quiet.append(f"missing transcript: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="nomodel"))
if code != 0 or "unverified" not in out:
    quiet.append(f"transcript with no model field: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("verdict", '{"agent_type":"house-rules:builder"}')
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
for ev, pl in (("announce", sub_payload(agent_type="house-rules:builder")),
               ("verdict", sub_payload(agent_type="house-rules:builder", agent_id="sonnet"))):
    code, out, err = run_hook(ev, pl, env=_off)
    if out.strip():
        deloff.append(f"{ev} still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
_tron = dict(os.environ)
_tron["HOUSE_RULES_TRACE"] = "off"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="sonnet"), env=_tron)
if "claude-sonnet" not in out:
    deloff.append("HOUSE_RULES_TRACE=off silenced the verdict, which is not a trace")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"), env=_off)
if out.strip():
    deloff.append(f"suspicious-completion report still emitted with HOUSE_RULES_DELEGATION=off: {out[:80]}")
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="notools"), env=_tron)
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

# --- subagentrules: a subagent core, generated from house-rules.md, injected at SubagentStart --
# Judged against the real rules file, since a hand-copied fixture core would only prove the
# handler can read a fixture, not that it stays in sync with the rules a human session sees.
code, out, err = run_hook("subagentrules", sub_payload(
    hook_event_name="SubagentStart", agent_type="house-rules:builder", agent_id="x1"
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

# A section NOT marked <!-- subagent --> (e.g. "Match response depth to the task") must not
# appear as its own heading in the core - otherwise "marked sections only" is not what ships.
if "## Match response depth to the task" in core:
    report("FAIL", "subagentrules includes only the sections marked <!-- subagent -->")
    print("          an unmarked heading leaked into the subagent core")
else:
    report("PASS", "subagentrules includes only the sections marked <!-- subagent -->")
    print("          an unmarked rule (response depth) is absent from the subagent core")

# SubagentStart also tells the user the transcript's EXPECTED path, before it exists.
if code == 0 and "systemMessage" in parsed and "transcript expected at" in parsed["systemMessage"] \
        and os.path.join("sess1", "subagents", "agent-x1.jsonl") in parsed["systemMessage"]:
    report("PASS", "subagentrules tells the user the expected transcript path at SubagentStart")
    print(f"          {parsed['systemMessage'][:150]}")
else:
    report("FAIL", "subagentrules tells the user the expected transcript path at SubagentStart")
    print(f"          out {out[:200]!r}")

# Never blocks a spawn: empty payload and unparseable input both still exit 0.
sarq = []
code, out, err = run_hook("subagentrules", "")
if code != 0 or "systemMessage" not in out:
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

# Registered as its OWN SubagentStart entry, unmatched, separate from announce.
_hj2 = json.loads(read(HOOKS_JSON))["hooks"]
sarwire = []
starts = _hj2.get("SubagentStart") or []
if not any("subagentrules" in h.get("command", "") for e in starts for h in e.get("hooks", [])):
    sarwire.append("hooks.json's SubagentStart has no subagentrules dispatch")
announce_entries = [e for e in starts if any("announce" in h.get("command", "") for h in e.get("hooks", []))]
subagentrules_entries = [e for e in starts if any("subagentrules" in h.get("command", "") for h in e.get("hooks", []))]
if announce_entries and subagentrules_entries and announce_entries[0] is subagentrules_entries[0]:
    sarwire.append("announce and subagentrules share one hook entry instead of two separate ones")
if any("matcher" in e for e in starts):
    sarwire.append("SubagentStart is scoped by a matcher, so it misses other agents")
if not sarwire:
    report("PASS", "subagentrules is its own SubagentStart entry, separate from announce")
    print("          both fire, unmatched, on every subagent spawn")
else:
    report("FAIL", "subagentrules is its own SubagentStart entry, separate from announce")
    for s in sarwire:
        print(f"          {s}")

if ("    subagentrules)" in read(RUN)):
    report("PASS", "run.sh names subagentrules in its no-interpreter fallback")
    print("          no working Python still reports the subagent got no rules")
else:
    report("FAIL", "run.sh names subagentrules in its no-interpreter fallback")

# --- agentcap (2.50.0, #112): at most two running subagents, none started by a subagent -------
_cap_state = os.path.join(_FIXTURE_ROOT, "cap-agents.json")


def _cap_env(**extra):
    e = dict(os.environ)
    e["HOUSE_RULES_AGENTS_STATE"] = _cap_state
    e.pop("HOUSE_RULES_AGENTS", None)
    e.update(extra)
    return e


def _cap_spawn(agent_id="", **extra):
    pl = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"prompt": "x"}}
    if agent_id:
        pl["agent_id"] = agent_id
    return run_hook("agentcap", json.dumps(pl), env=_cap_env(**extra))


def _cap_denied(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        return False


def _cap_start(aid, atype="house-rules:builder"):
    return run_hook("announce", sub_payload(hook_event_name="SubagentStart", agent_type=atype, agent_id=aid), env=_cap_env())


def _cap_stop(aid, atype="house-rules:builder"):
    return run_hook("verdict", sub_payload(hook_event_name="SubagentStop", agent_type=atype, agent_id=aid), env=_cap_env())


if os.path.exists(_cap_state):
    os.remove(_cap_state)
_c0 = _cap_spawn()
_cap_start("capA")
_c1 = _cap_spawn()
_cap_start("capB")
_c2 = _cap_spawn()
commit_case(
    "agentcap: the first and second spawn are allowed, the third is denied naming both running agents",
    not _cap_denied(_c0[1]) and not _cap_denied(_c1[1]) and _cap_denied(_c2[1])
    and "capA" in _c2[1] and "capB" in _c2[1] and "Wait for one to finish" in _c2[1],
    "out %r" % _c2[1][:200],
)
_cap_stop("capA")
_c3 = _cap_spawn()
commit_case(
    "agentcap: a record is cleared by SubagentStop, so a spawn is allowed again",
    not _cap_denied(_c3[1]) and "capA" not in open(_cap_state, encoding="utf-8").read(),
    "after stop: %r" % open(_cap_state, encoding="utf-8").read()[:120],
)
_stale = time.time() - 46 * 60
with open(_cap_state, "w", encoding="utf-8") as _f:
    json.dump({"agents": [{"id": "old1", "type": "x", "start": _stale}, {"id": "old2", "type": "x", "start": _stale}]}, _f)
_c4 = _cap_spawn()
commit_case(
    "agentcap: records older than 45 minutes are ignored",
    not _cap_denied(_c4[1]), "out %r" % _c4[1][:120],
)
with open(_cap_state, "w", encoding="utf-8") as _f:
    json.dump({"agents": [{"id": "k1", "type": "x", "start": time.time()}, {"id": "k2", "type": "x", "start": time.time()}]}, _f)
_c5 = _cap_spawn(HOUSE_RULES_AGENTS="off")
_c5b = _cap_spawn()
commit_case(
    "agentcap: HOUSE_RULES_AGENTS=off disables the cap (and the same state denies without it)",
    _c5[1].strip() == "" and _cap_denied(_c5b[1]), "off: %r; on: %r" % (_c5[1][:60], _c5b[1][:60]),
)
with open(_cap_state, "w", encoding="utf-8") as _f:
    _f.write("{not json")
_c6 = _cap_spawn()
try:
    _c6msg = json.loads(_c6[1]).get("systemMessage", "")
except ValueError:
    _c6msg = "unparseable"
commit_case(
    "agentcap: a corrupt state file fails open and says so in one line",
    _c6[0] == 0 and not _cap_denied(_c6[1]) and "could not read" in _c6msg and "allowed" in _c6msg,
    "systemMessage %r" % _c6msg[:160],
)
os.remove(_cap_state)
_c7 = _cap_spawn(agent_id="sub9")
commit_case(
    "agentcap: a spawn made by a subagent (payload carries agent_id) is denied",
    _cap_denied(_c7[1]) and "sub9" in _c7[1], "out %r" % _c7[1][:160],
)

# --- prompttimer (#144): an unanswered permission prompt is refused after a timeout, never approved
_pt_repo = os.path.join(_FIXTURE_ROOT, "pt-repo")
os.makedirs(_pt_repo, exist_ok=True)
subprocess.run(["git", "init", "-q"], cwd=_pt_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
_pt_state = os.path.join(_pt_repo, ".git", "house-rules", "waiting-on-you.json")
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)


def _pt_env(**extra):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = _pt_repo
    e["HOUSE_RULES_PROMPT_TIMEOUT"] = "1"
    e.update(extra)
    return e


_pt_payload = json.dumps({"hook_event_name": "PermissionRequest", "session_id": "pt-sess", "tool_name": "Bash",
                          "tool_input": {"command": "rm -rf /tmp/pt-victim"}})


def _pt_run(payload=_pt_payload, **extra):
    t0 = time.time()
    code, out, err = run_hook("prompttimer", payload, env=_pt_env(**extra))
    return code, out, err, time.time() - t0


def _pt_decision(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["decision"]
    except Exception:
        return {}


_p1 = _pt_run()
_d1 = _pt_decision(_p1[1])
try:
    _pt_entries = json.load(open(_pt_state, encoding="utf-8"))
except Exception:
    _pt_entries = []
commit_case(
    "prompttimer: an unanswered prompt is denied after the timeout, message == reason, state holds one timed-out entry",
    _p1[0] == 0 and _d1.get("behavior") == "deny" and _d1.get("message") == _d1.get("reason")
    and "refused" in _d1.get("message", "") and "rm -rf /tmp/pt-victim" in _d1.get("message", "")
    and len(_pt_entries) == 1 and _pt_entries[0]["status"] == "timed-out"
    and _pt_entries[0]["session_id"] == "pt-sess" and len(_pt_entries[0]["key"]) == 16
    and _pt_entries[0]["summary"] == "rm -rf /tmp/pt-victim",
    "out %r entries %r" % (_p1[1][:120], _pt_entries),
)
commit_case(
    "prompttimer: the 1-second timeout waits about 1 second (not 0, not 10)",
    0.9 <= _p1[3] <= 5, "elapsed %.2fs" % _p1[3],
)
_p2 = _pt_run()
commit_case(
    "prompttimer: the same action again in the same session is denied at once",
    _p2[3] < 0.5 and _pt_decision(_p2[1]).get("behavior") == "deny" and "already timed out" in _pt_decision(_p2[1]).get("message", ""),
    "elapsed %.2fs out %r" % (_p2[3], _p2[1][:100]),
)
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_p3 = _pt_run(HOUSE_RULES_PROMPT_TIMEOUT="OFF")
commit_case(
    "prompttimer: HOUSE_RULES_PROMPT_TIMEOUT=off makes no decision and writes no state",
    _p3[0] == 0 and _p3[1] == "" and not os.path.exists(_pt_state) and _p3[3] < 0.9,
    "out %r state exists %s" % (_p3[1], os.path.exists(_pt_state)),
)
os.makedirs(os.path.dirname(_pt_state), exist_ok=True)
with open(_pt_state, "w", encoding="utf-8") as _f:
    _f.write("{not json")
_p4 = _pt_run()
commit_case(
    "prompttimer: a corrupt state file is reported loudly and the prompt is still denied after the timeout",
    _p4[0] == 0 and _pt_decision(_p4[1]).get("behavior") == "deny" and _p4[3] >= 0.9
    and "could not read" in _p4[2] and _pt_state in _p4[2] and "Traceback" not in _p4[2],
    "elapsed %.2fs stderr %r" % (_p4[3], _p4[2][:200]),
)
_p5 = _pt_run("{not json")
_p5b = _pt_run(json.dumps({"session_id": "x"}))
commit_case(
    "prompttimer: a malformed payload makes no decision, says so on stderr and exits 0",
    _p5[0] == 0 and _p5[1] == "" and "could not read" in _p5[2] and _p5[3] < 0.9
    and _p5b[0] == 0 and _p5b[1] == "" and "could not read" in _p5b[2],
    "stderr %r / %r" % (_p5[2][:100], _p5b[2][:100]),
)
_pt_src = read(HOOK)
_pt_block = _pt_src[_pt_src.index("# prompttimer - PermissionRequest"):_pt_src.index("# subagentcommit")]
commit_case(
    "prompttimer: the handler source has no route to an allow decision",
    "allow" not in _pt_block.lower() and 'behavior": "deny"' in _pt_block,
    "%d characters of handler source scanned" % len(_pt_block),
)
_pt_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"].get("PermissionRequest", [])
commit_case(
    "prompttimer: hooks.json wires PermissionRequest to prompttimer with a 330 second timeout",
    len(_pt_hj) == 1 and "matcher" not in _pt_hj[0] and len(_pt_hj[0]["hooks"]) == 1
    and _pt_hj[0]["hooks"][0]["command"].endswith('run.sh" prompttimer') and _pt_hj[0]["hooks"][0]["timeout"] == 330,
    "entry %r" % (_pt_hj,),
)

# --- #145: the waiting-on-you list is locked, shown by scope and issuelist, and named in the guard prompts
import threading

shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_pt_pl = lambda cmd, sid="pt-sess": json.dumps({"hook_event_name": "PermissionRequest", "session_id": sid,
                                                "tool_name": "Bash", "tool_input": {"command": cmd}})
_pt_res = {}


def _pt_thread(name, cmd):
    _pt_res[name] = _pt_run(_pt_pl(cmd))


_ths = [threading.Thread(target=_pt_thread, args=("a", "echo concurrent-a")),
        threading.Thread(target=_pt_thread, args=("b", "echo concurrent-b"))]
for _t in _ths:
    _t.start()
for _t in _ths:
    _t.join()
try:
    _pt_c = json.load(open(_pt_state, encoding="utf-8"))
except Exception:
    _pt_c = []
commit_case(
    "prompttimer: two concurrent runs on different actions leave 2 entries (the lock keeps both)",
    len(_pt_c) == 2 and {e["summary"] for e in _pt_c} == {"echo concurrent-a", "echo concurrent-b"}
    and not os.path.exists(_pt_state + ".lock"),
    "entries %r" % (_pt_c,),
)

# a stale lock is removed and reported
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
os.makedirs(os.path.dirname(_pt_state), exist_ok=True)
with open(_pt_state + ".lock", "w") as _f:
    _f.write("")
os.utime(_pt_state + ".lock", (time.time() - 60, time.time() - 60))
_s1 = _pt_run(_pt_pl("echo stale-lock"))
commit_case(
    "prompttimer: a lock older than 15 s is removed, reported on stderr, and the entry is still written",
    "stale lock" in _s1[2] and not os.path.exists(_pt_state + ".lock")
    and _pt_decision(_s1[1]).get("behavior") == "deny"
    and any(e["summary"] == "echo stale-lock" for e in json.load(open(_pt_state, encoding="utf-8"))),
    "stderr %r" % (_s1[2][:200],),
)

# scope: a real prompt lists the entry, marks it reported; a retry then waits
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_pt_run()  # times out: one timed-out entry for rm -rf /tmp/pt-victim in pt-sess
_pt_scope_env = _pt_env()


def _pt_scope(prompt, sid="pt-sess"):
    return run_hook("scope", json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": sid,
                                         "prompt": prompt}), env=_pt_scope_env)


_n1 = _pt_scope("<task-notification><task-id>abc</task-id><status>completed</status></task-notification>")
_state_n1 = json.load(open(_pt_state, encoding="utf-8"))
commit_case(
    "scope: a background task-notification prompt changes nothing and lists nothing",
    _n1[0] == 0 and "waiting on you" not in _n1[1] and _state_n1[0]["status"] == "timed-out",
    "out %r state %r" % (_n1[1][:150], _state_n1),
)
_r1 = _pt_scope("hello, back now")
_state_r1 = json.load(open(_pt_state, encoding="utf-8"))
try:
    _r1ctx = json.loads(_r1[1])["hookSpecificOutput"]["additionalContext"]
except Exception:
    _r1ctx = ""
commit_case(
    "scope: a real prompt lists the session's timed-out action, marks it reported, one JSON object on stdout",
    _r1[0] == 0 and "1 action waiting on you since" in _r1ctx and "(local time)" in _r1ctx
    and "- Bash: rm -rf /tmp/pt-victim" in _r1ctx and "aj is here now" in _r1ctx
    and len(_state_r1) == 1 and _state_r1[0]["status"] == "reported",
    "out %r state %r" % (_r1[1][:200], _state_r1),
)
_r2 = _pt_run()
commit_case(
    "prompttimer: after scope reported it, the same action waits instead of being re-denied at once",
    _r2[3] >= 0.9 and "already timed out" not in _pt_decision(_r2[1]).get("message", ""),
    "elapsed %.2fs out %r" % (_r2[3], _r2[1][:100]),
)
_r3 = _pt_scope("again", sid="quiet-sess")
commit_case(
    "scope: a session with nothing waiting gets nothing extra",
    "action waiting on you" not in _r3[1] and "actions waiting on you" not in _r3[1],
    "out %r" % (_r3[1][:150],),
)

# issuelist: other sessions' entries are shown and dropped; >7-day entries pruned; empty says nothing
_now = time.time()
with open(_pt_state, "w", encoding="utf-8") as _f:
    json.dump([
        {"session_id": "old-sess", "key": "k1", "tool": "Bash", "summary": "git push origin main",
         "started": _now - 3600, "status": "timed-out"},
        {"session_id": "old-sess2", "key": "k2", "tool": "Write", "summary": "ancient.txt",
         "started": _now - 8 * 86400, "status": "timed-out"},
        {"session_id": "new-sess", "key": "k3", "tool": "Bash", "summary": "mine stays",
         "started": _now - 5, "status": "waiting"},
    ] + [{"session_id": "filler%d" % _k, "key": "f%d" % _k, "tool": "Bash", "summary": "filler %d" % _k,
          "started": _now - 100 - _k, "status": "timed-out"} for _k in range(9)], _f)
_il_env = _pt_env(HOUSE_RULES_ISSUES="off")
_i1 = run_hook("issuelist", json.dumps({"hook_event_name": "SessionStart", "session_id": "new-sess",
                                        "cwd": _pt_repo}), env=_il_env)
try:
    _io = json.loads(_i1[1])
except Exception:
    _io = {}
_left = json.load(open(_pt_state, encoding="utf-8"))
commit_case(
    "issuelist: another session's entry is shown to Claude and aj in one JSON object, then dropped; >7-day entries pruned",
    _i1[0] == 0 and "Left waiting on you by an earlier session" in _io.get("hookSpecificOutput", {}).get("additionalContext", "")
    and "git push origin main" in _io["hookSpecificOutput"]["additionalContext"]
    and "ancient.txt" not in _io["hookSpecificOutput"]["additionalContext"]
    and _io["hookSpecificOutput"]["additionalContext"].count("\n- ") == 10
    and "git push origin main" in _io.get("systemMessage", "")
    and [e["summary"] for e in _left] == ["mine stays"],
    "out %r left %r" % (_i1[1][:200], _left),
)
_i2 = run_hook("issuelist", json.dumps({"hook_event_name": "SessionStart", "session_id": "new-sess",
                                        "cwd": _pt_repo}), env=_il_env)
commit_case(
    "issuelist: with nothing left by other sessions it says nothing",
    _i2[0] == 0 and _i2[1] == "", "out %r" % (_i2[1][:100],),
)

# guard: the timeout line, omitted when off
_g_payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "g", "tool_name": "Bash",
                         "tool_input": {"command": "rm -rf /tmp/pt-victim"}, "cwd": _pt_repo})
_gw_payload = json.dumps({"hook_event_name": "PreToolUse", "session_id": "g", "tool_name": "Write",
                          "tool_input": {"file_path": os.path.join(_pt_repo, "existing.txt"), "content": "x\n"},
                          "cwd": _pt_repo})
with open(os.path.join(_pt_repo, "existing.txt"), "w") as _f:
    _f.write("a\nb\n")
_gline = "refused (never approved) and added to the waiting-on-you list."
_ge = _pt_env(HOUSE_RULES_PROMPT_TIMEOUT="300")
_geoff = _pt_env(HOUSE_RULES_PROMPT_TIMEOUT="off")
_g1, _g2 = run_hook("guard", _g_payload, env=_ge), run_hook("guardwrite", _gw_payload, env=_ge)
_g3, _g4 = run_hook("guard", _g_payload, env=_geoff), run_hook("guardwrite", _gw_payload, env=_geoff)
commit_case(
    "guard and guardwrite: the prompt says 'If nobody answers within 5 minutes...' before the Approve line; off omits it",
    all("If nobody answers within 5 minutes, this is " + _gline in x[1] for x in (_g1, _g2))
    and all(x[1].index("If nobody answers") < x[1].index("Approve to let it run") for x in (_g1, _g2))
    and all(_gline not in x[1] and "Approve to let it run" in x[1] for x in (_g3, _g4)),
    "guard %r | guardwrite %r | off %r" % (_g1[1][-250:], _g2[1][-250:], _g3[1][-150:]),
)

# --- #142 follow-ups: questions exempt, away fast-fail, an action that ran is never "timed out" (#149)
def _pt_tool(tool, tool_input, sid="pt-sess", event="PermissionRequest"):
    return json.dumps({"hook_event_name": event, "session_id": sid, "tool_name": tool, "tool_input": tool_input})


def _pt_state_now():
    try:
        return json.load(open(_pt_state, encoding="utf-8"))
    except Exception:
        return []


shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_q1 = _pt_run(_pt_tool("AskUserQuestion", {"questions": [{"question": "Which one?"}]}))
_q2 = _pt_run(_pt_tool("ExitPlanMode", {"plan": "1. do it"}))
commit_case(
    "prompttimer: AskUserQuestion and ExitPlanMode get no timer - no decision, no state, said on stderr",
    all(x[0] == 0 and x[1] == "" and x[3] < 0.9 and "question for aj" in x[2] for x in (_q1, _q2))
    and not os.path.exists(_pt_state),
    "q1 %r q2 %r state %s" % (_q1[2][:120], _q2[2][:120], os.path.exists(_pt_state)),
)

_a1 = _pt_run()  # rm -rf /tmp/pt-victim times out: aj is away
_a2 = _pt_run(_pt_pl("git push -q origin claude/x"))
_a2d = _pt_decision(_a2[1])
_a2s = _pt_state_now()
commit_case(
    "prompttimer: after one timeout, a DIFFERENT action in the same session is refused at once and queued",
    _a1[3] >= 0.9 and _a2[3] < 0.5 and _a2d.get("behavior") == "deny" and _a2d.get("message") == _a2d.get("reason")
    and "already went unanswered" in _a2d.get("message", "") and "rm -rf /tmp/pt-victim" in _a2d.get("message", "")
    and sorted(e["status"] for e in _a2s) == ["timed-out", "timed-out"],
    "elapsed %.2fs out %r state %r" % (_a2[3], _a2[1][:120], _a2s),
)
_a3 = _pt_run(_pt_pl("git push -q origin claude/x", sid="other-sess"))
commit_case(
    "prompttimer: another session's timeout does not refuse this session's prompt at once",
    _a3[3] >= 0.9 and "already went unanswered" not in _pt_decision(_a3[1]).get("message", ""),
    "elapsed %.2fs" % _a3[3],
)
_pt_scope("I'm back")
_a4 = _pt_run(_pt_pl("echo after-aj-wrote"))
commit_case(
    "prompttimer: once aj writes (scope), a new prompt waits normally again",
    _a4[3] >= 0.9 and "already went unanswered" not in _pt_decision(_a4[1]).get("message", ""),
    "elapsed %.2fs out %r" % (_a4[3], _a4[1][:100]),
)

# an action approved some other way runs: promptran marks it, the waiting timer stops without a decision
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_ran_input = {"command": "git push -q"}
_ran_res = {}
_ran_t = threading.Thread(target=lambda: _ran_res.update(
    r=_pt_run(_pt_tool("Bash", _ran_input), HOUSE_RULES_PROMPT_TIMEOUT="4")))
_ran_t.start()
for _w in range(50):
    if any(e.get("status") == "waiting" for e in _pt_state_now()):
        break
    time.sleep(0.1)
_rr = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUse"), env=_pt_env())
_ran_t.join()
_ran = _ran_res.get("r", (None, "?", "", 99))
commit_case(
    "promptran: an action that ran while its prompt was waiting stops the timer with no decision and no entry",
    _rr[0] == 0 and _rr[1] == "" and _ran[0] == 0 and _ran[1] == "" and _ran[3] < 3.5
    and "the action ran" in _ran[2] and _pt_state_now() == [],
    "timer elapsed %.2fs out %r stderr %r state %r" % (_ran[3], _ran[1][:80], _ran[2][:150], _pt_state_now()),
)

# an action that ran AFTER being refused as timed out is removed and reported out loud
_pt_run(_pt_tool("Bash", _ran_input))
_late = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUseFailure"), env=_pt_env())
try:
    _late_o = json.loads(_late[1])
except Exception:
    _late_o = {}
commit_case(
    "promptran: a timed-out action that ran anyway is removed from the list and reported to aj and Claude",
    _late[0] == 0 and "ran although its permission prompt was refused" in _late_o.get("systemMessage", "")
    and "git push -q" in _late_o.get("systemMessage", "")
    and _late_o.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUseFailure"
    and _pt_state_now() == [],
    "out %r state %r" % (_late[1][:200], _pt_state_now()),
)
shutil.rmtree(os.path.dirname(_pt_state), ignore_errors=True)
_quiet = run_hook("promptran", _pt_tool("Bash", _ran_input, event="PostToolUse"), env=_pt_env())
_bad = run_hook("promptran", "{not json", env=_pt_env())
commit_case(
    "promptran: with no waiting-on-you list, or a bad payload, it says nothing and exits 0",
    _quiet[0] == 0 and _quiet[1] == "" and _bad[0] == 0 and _bad[1] == "",
    "quiet %r bad %r" % (_quiet[1][:80], _bad[1][:80]),
)
_pr_hj = json.load(open(HOOKS_JSON, encoding="utf-8"))["hooks"]
_pr_entries = [g for ev in ("PostToolUse", "PostToolUseFailure") for g in _pr_hj.get(ev, [])
               if any(h["command"].endswith('run.sh" promptran') for h in g["hooks"])]
commit_case(
    "promptran: wired on PostToolUse and PostToolUseFailure, matched to the tools that raise permission prompts",
    len(_pr_entries) == 2 and all(len(g["hooks"]) == 1 and "Bash" in g.get("matcher", "")
                                  and "Read" not in g.get("matcher", "") for g in _pr_entries),
    "entries %r" % (_pr_entries,),
)

# --- verdict's audit summary: built from the transcript, not the subagent's own report --------
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"))
audit = []
if code != 0:
    audit.append(f"exit {code}, must never be non-zero")
for needle in (
    "transcript found at", "tool uses:", "FAILED commands", "cmd: Bash [ERROR]: false",
    "wrote: Write /proj/a.py", "other commands: 1 ok (not listed)",
    "Reconcile the subagent's report against this record",
):
    if needle not in out:
        audit.append(f"audit summary is missing {needle!r}")
if not audit:
    report("PASS", "verdict's audit summary reports commands with exit status and files written")
    print("          built from the transcript itself: counts, the failed command in full, the written file, the ok count")
else:
    report("FAIL", "verdict's audit summary reports commands with exit status and files written")
    for a in audit:
        print(f"          {a}")

# The cap: 45 commands in the fixture, at most 40 shown plus an explicit "N more".
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="auditbig"))
if code == 0 and "cmd: Bash [ok]" not in out and "other commands: 45 ok (not listed)" in out and "Bash x45" in out and len(out) < 1500:
    report("PASS", "verdict's audit summary counts ok commands instead of listing them, and stays small")
    print(f"          45 ok commands -> one count line, {len(out)} chars (< 1500)")
else:
    report("FAIL", "verdict's audit summary counts ok commands instead of listing them, and stays small")
    print(f"          exit {code}, len={len(out)}, out[-200:]={out[-200:]!r}")

# --- HOUSE_RULES_SUBAGENT_LEDGER: off by default, renders docs/sessions/<...> when on ---------
_ledger_root = tempfile.mkdtemp(prefix="house-rules-ledger-")
atexit.register(shutil.rmtree, _ledger_root, True)
_ledger_off = dict(os.environ)
_ledger_off["CLAUDE_PROJECT_DIR"] = _ledger_root
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"), env=_ledger_off)
_ledger_dir = os.path.join(_ledger_root, "docs", "sessions")
if "LEDGER" not in out and not os.path.isdir(_ledger_dir):
    report("PASS", "HOUSE_RULES_SUBAGENT_LEDGER is off by default - no docs/sessions/ write")
    print("          no LEDGER line, no docs/sessions/ directory created")
else:
    report("FAIL", "HOUSE_RULES_SUBAGENT_LEDGER is off by default - no docs/sessions/ write")
    print(f"          out {out[:150]!r}, ledger dir exists={os.path.isdir(_ledger_dir)}")

_ledger_on = dict(_ledger_off)
_ledger_on["HOUSE_RULES_SUBAGENT_LEDGER"] = "on"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="audit1"), env=_ledger_on)
_written = [f for f in os.listdir(_ledger_dir)] if os.path.isdir(_ledger_dir) else []
if code == 0 and "LEDGER: rendered" in out and any(f.endswith(".md") for f in _written):
    report("PASS", "HOUSE_RULES_SUBAGENT_LEDGER=on renders the subagent transcript into docs/sessions/")
    print(f"          wrote {_written}")
else:
    report("FAIL", "HOUSE_RULES_SUBAGENT_LEDGER=on renders the subagent transcript into docs/sessions/")
    print(f"          exit {code}, out {out[:200]!r}, dir listing {_written}")

# A failure rendering the ledger (unreadable transcript) says so and never crashes verdict.
_ledger_bad_root = tempfile.mkdtemp(prefix="house-rules-ledger-bad-")
atexit.register(shutil.rmtree, _ledger_bad_root, True)
_ledger_bad = dict(os.environ)
_ledger_bad["CLAUDE_PROJECT_DIR"] = _ledger_bad_root
_ledger_bad["HOUSE_RULES_SUBAGENT_LEDGER"] = "on"
code, out, err = run_hook("verdict", sub_payload(agent_type="house-rules:builder", agent_id="ghost"), env=_ledger_bad)
# "ghost" has no transcript file at all, so verdict returns before ever reaching the ledger
# step - this proves that early return, not the ledger call, never crashes.
if code == 0 and "unverified" in out:
    report("PASS", "an unreadable/missing subagent transcript never crashes verdict, ledger or not")
    print("          missing-transcript path returns before the ledger step, exit 0")
else:
    report("FAIL", "an unreadable/missing subagent transcript never crashes verdict, ledger or not")
    print(f"          exit {code}, out {out[:150]!r}")

# --- audit: the foreground half of the audit summary, PostToolUse on Agent|Task ---------------
def post_agent_payload(**kw):
    base = {
        "session_id": "sess1",
        "transcript_path": _PARENT,
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "general-purpose"},
        "tool_response": {"status": "completed", "agentId": "audit1", "agentType": "general-purpose"},
    }
    base.update(kw)
    return json.dumps(base)


code, out, err = run_hook("audit", post_agent_payload())
aud = []
if code != 0:
    aud.append(f"exit {code}, must never be non-zero")
try:
    core_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    aud.append(f"could not parse audit output: {exc}")
    core_ctx = ""
for needle in (
    "finished (foreground)", "FAILED commands", "cmd: Bash [ERROR]: false", "wrote: Write /proj/a.py",
    "Reconcile the subagent's report against this record",
):
    if needle not in core_ctx:
        aud.append(f"audit's additionalContext is missing {needle!r}")
if not aud:
    report("PASS", "audit hands the subagent's audit summary to the parent MODEL after a foreground return")
    print(f"          {core_ctx[:150]}")
else:
    report("FAIL", "audit hands the subagent's audit summary to the parent MODEL after a foreground return")
    for a in aud:
        print(f"          {a}")

# A backgrounded call's PostToolUse fires immediately with status "async_launched" - nothing
# has happened yet, so audit reports no audit. Since 2.47.0 it asks the parent for a check-in
# instead (so worktreesweep runs while the subagent works); with autosave off it says nothing.
_async_payload = post_agent_payload(
    tool_response={"isAsync": True, "status": "async_launched", "agentId": "audit1"}
)
code, out, err = run_hook("audit", _async_payload)
code_off, out_off, _e = run_hook("audit", _async_payload, env=dict(os.environ, HOUSE_RULES_AUTOSAVE="off"))
if (code == 0 and "checked for stalls every 5 minutes" in out and "stallcheck.py" in out and "AUDIT" not in out
        and code_off == 0 and not out_off.strip()):
    report("PASS", "audit asks for a check-in, not an audit, on a backgrounded call's async_launched PostToolUse")
    print("          nothing to audit yet; the check-in nudge appears, and not with HOUSE_RULES_AUTOSAVE=off")
else:
    report("FAIL", "audit asks for a check-in, not an audit, on a backgrounded call's async_launched PostToolUse")
    print(f"          exit {code}, out {out[:150]!r}; autosave off: exit {code_off}, out {out_off[:80]!r}")


# --- stallcheck.py (issue 120). The agentcap cases live with the spawn-cap tests above.
import tempfile as _cap_tf
def _cap_case(title, ok, detail):
    report("PASS" if ok else "FAIL", title)
    print("          " + detail)

_sc = os.path.join(HERE, "stallcheck.py")
_home = _cap_tf.mkdtemp(prefix="house-rules-home-", dir=_FIXTURE_ROOT)
_sd = os.path.join(_home, ".claude", "projects", "p", "s", "subagents")
os.makedirs(_sd)
_henv = dict(os.environ, HOME=_home, USERPROFILE=_home)


def _sc_file(name, text, age_s):
    path = os.path.join(_sd, "agent-%s.jsonl" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.utime(path, (time.time() - age_s, time.time() - age_s))


def _sc_run(*extra):
    pr = subprocess.run([sys.executable, _sc] + list(extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_henv)
    return pr.returncode, pr.stdout.decode("utf-8", "replace")


_sc_file("fresh", '{"type":"assistant"}\n', 20)
_c, _o = _sc_run()
_cap_case("stallcheck: a transcript written 20 s ago is ok, exit 0", _c == 0 and "ok" in _o and "fresh" in _o, "exit %d out %r" % (_c, _o[:100]))
_sc_file("quiet", '{"type":"assistant"}\n', 600)
_c, _o = _sc_run()
_cap_case("stallcheck: a transcript silent for 10 minutes is STALLED, exit 1",
          _c == 1 and "STALLED" in _o and "quiet" in _o, "exit %d out %r" % (_c, _o[:160]))
_sc_file("done", '{"type":"attachment","attachment":{"hookEvent":"SubagentStop"}}\n', 3000)
_c, _o = _sc_run("--threshold", "9999")
_cap_case("stallcheck: a transcript holding SubagentStop is finished, never STALLED",
          "finished  subagent done" in _o, "out %r" % _o[:200])
_c, _o = _sc_run("--file", os.path.join(_home, "no-such.out"))
_cap_case("stallcheck: a watched file that does not exist is STALLED, not skipped", _c == 1 and "no-such.out" in _o, "exit %d out %r" % (_c, _o[:160]))
for _n in os.listdir(_sd):
    os.remove(os.path.join(_sd, _n))
_c, _o = _sc_run()
_cap_case("stallcheck: with nothing to check it says so and exits 2, never silent",
          _c == 2 and "nothing was checked" in _o, "exit %d out %r" % (_c, _o[:160]))

audq = []
code, out, err = run_hook("audit", "")
if code != 0 or "systemMessage" not in out:
    audq.append(f"empty payload: exit {code}, out {out[:120]!r}")
code, out, err = run_hook("audit", "not json at all {{{")
if code != 0:
    audq.append(f"unparseable payload: exit {code}")
if not audq:
    report("PASS", "audit never blocks a PostToolUse call, even on a bad payload")
    print("          empty and unparseable payloads both still exit 0")
else:
    report("FAIL", "audit never blocks a PostToolUse call, even on a bad payload")
    for a in audq:
        print(f"          {a}")

_hj3 = json.loads(read(HOOKS_JSON))["hooks"]
audwire = []
posts = _hj3.get("PostToolUse") or []
audit_entries = [e for e in posts if any("audit" in h.get("command", "") and "\" audit" in h.get("command", "") for h in e.get("hooks", []))]
if not any(e.get("matcher") == "Agent|Task" for e in posts):
    audwire.append("hooks.json's PostToolUse has no Agent|Task matcher for audit")
if not any("\" audit" in h.get("command", "") for e in posts for h in e.get("hooks", [])):
    audwire.append("hooks.json's PostToolUse has no audit dispatch")
if not audwire:
    report("PASS", "audit is its own PostToolUse entry matched on Agent|Task")
    print("          separate from artifact/runnable/harvest/delegate")
else:
    report("FAIL", "audit is its own PostToolUse entry matched on Agent|Task")
    for a in audwire:
        print(f"          {a}")

if ("    audit)" in read(RUN)):
    report("PASS", "run.sh names audit in its no-interpreter fallback")
else:
    report("FAIL", "run.sh names audit in its no-interpreter fallback")

# --- userpromptaudit: the background half, UserPromptSubmit --------------------------------
def _task_notification(task_id, status="completed"):
    return (
        "<task-notification>\n<task-id>%s</task-id>\n<tool-use-id>toolu_x</tool-use-id>\n"
        "<output-file>/x</output-file>\n<status>%s</status>\n<summary>Agent finished</summary>\n"
        "<result>done</result>\n</task-notification>" % (task_id, status)
    )


def userprompt_payload(prompt, **kw):
    base = {"session_id": "sess1", "transcript_path": _PARENT, "hook_event_name": "UserPromptSubmit", "prompt": prompt}
    base.update(kw)
    return json.dumps(base)


code, out, err = run_hook("userpromptaudit", userprompt_payload(_task_notification("audit1")))
upa = []
if code != 0:
    upa.append(f"exit {code}, must never be non-zero")
try:
    up_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    upa.append(f"could not parse userpromptaudit output: {exc}")
    up_ctx = ""
for needle in (
    "finished (background)", "FAILED commands", "cmd: Bash [ERROR]: false",
    "Reconcile the subagent's report against this record",
):
    if needle not in up_ctx:
        upa.append(f"userpromptaudit's additionalContext is missing {needle!r}")
if not upa:
    report("PASS", "userpromptaudit hands the audit summary to the parent model on a background hand-back")
    print(f"          {up_ctx[:150]}")
else:
    report("FAIL", "userpromptaudit hands the audit summary to the parent model on a background hand-back")
    for a in upa:
        print(f"          {a}")

# The ordinary case: a ordinary prompt must never be touched, and never even emit anything -
# a non-zero exit or a wrong additionalContext here would corrupt or erase the user's prompt.
code, out, err = run_hook("userpromptaudit", userprompt_payload("please fix the failing test"))
if code == 0 and not out.strip():
    report("PASS", "userpromptaudit is silent on an ordinary prompt")
    print("          no additionalContext, no systemMessage - nothing to say")
else:
    report("FAIL", "userpromptaudit is silent on an ordinary prompt")
    print(f"          exit {code}, out {out[:150]!r}")

# A notification for a still-running task carries nothing finished to audit yet.
code, out, err = run_hook("userpromptaudit", userprompt_payload(_task_notification("audit1", status="running")))
if code == 0 and not out.strip():
    report("PASS", "userpromptaudit is silent on a not-yet-completed task notification")
else:
    report("FAIL", "userpromptaudit is silent on a not-yet-completed task notification")
    print(f"          exit {code}, out {out[:150]!r}")

upq = []
code, out, err = run_hook("userpromptaudit", "")
if code != 0 or out.strip():
    upq.append(f"empty payload: exit {code}, out {out[:120]!r} (must be silent, exit 0)")
code, out, err = run_hook("userpromptaudit", "not json at all {{{")
if code != 0 or out.strip():
    upq.append(f"unparseable payload: exit {code}, out {out[:120]!r}")
if not upq:
    report("PASS", "userpromptaudit never erases the prompt - exit 0 and silent on bad payloads")
else:
    report("FAIL", "userpromptaudit never erases the prompt - exit 0 and silent on bad payloads")
    for u in upq:
        print(f"          {u}")

upwire = []
prompts = _hj3.get("UserPromptSubmit") or []
if not any("\" userpromptaudit" in h.get("command", "") for e in prompts for h in e.get("hooks", [])):
    upwire.append("hooks.json's UserPromptSubmit has no userpromptaudit dispatch")
scope_entries = [e for e in prompts if any("\" scope" in h.get("command", "") for h in e.get("hooks", []))]
upa_entries = [e for e in prompts if any("\" userpromptaudit" in h.get("command", "") for h in e.get("hooks", []))]
if scope_entries and upa_entries and scope_entries[0] is upa_entries[0]:
    upwire.append("scope and userpromptaudit share one hook entry instead of two separate ones")
if not upwire:
    report("PASS", "userpromptaudit is its own UserPromptSubmit entry, separate from scope")
else:
    report("FAIL", "userpromptaudit is its own UserPromptSubmit entry, separate from scope")
    for u in upwire:
        print(f"          {u}")

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


# Every case gets a fake `claude` and its own installed_plugins.json, so no case can run a real
# update or read this machine's real install. The fake logs each call and, when told to, writes
# the "updated" version into that JSON the way a real `claude plugin update` would.
_vc_fake_dir = tempfile.mkdtemp(prefix="house-rules-vc-fake-")
_vc_fake_claude = os.path.join(_vc_fake_dir, "fake_claude.py")
with open(_vc_fake_claude, "w", encoding="utf-8") as f:
    f.write(
        "import json, os, sys\n"
        "with open(os.environ['VC_FAKE_LOG'], 'a', encoding='utf-8') as log:\n"
        "    log.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "target = os.environ.get('VC_FAKE_INSTALLS', '')\n"
        "if sys.argv[1:3] == ['plugin', 'update'] and target:\n"
        "    with open(os.environ['HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON'], 'w', encoding='utf-8') as out:\n"
        "        json.dump({'version': 2, 'plugins': {sys.argv[3]: [{'version': target}]}}, out)\n"
        "print('fake claude: ' + ' '.join(sys.argv[1:]))\n"
        "sys.exit(int(os.environ.get('VC_FAKE_EXIT', '1')))\n"
    )


def vc_installed_json(case, version=None):
    path = os.path.join(_vc_fake_dir, f"installed-{case}.json")
    if version is not None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"version": 2, "plugins": {"house-rules@aj-house-rules": [{"version": version}]}}, f
            )
    return path


def vc_clear(case):
    """Remove what an earlier run left for this case, so a stale marker or log cannot pass or
    fail it."""
    for path in (vc_marker_path(case), os.path.join(_vc_fake_dir, f"calls-{case}.log")):
        if os.path.isfile(path):
            os.remove(path)


def vc_fake_calls(case):
    path = os.path.join(_vc_fake_dir, f"calls-{case}.log")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def vc_env(case="default", **overrides):
    e = dict(os.environ)
    e["HOUSE_RULES_VC_CLAUDE"] = json.dumps([sys.executable, _vc_fake_claude])
    e["HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON"] = vc_installed_json(case)
    e["VC_FAKE_LOG"] = os.path.join(_vc_fake_dir, f"calls-{case}.log")
    e.pop("HOUSE_RULES_AUTO_UPDATE", None)
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
# Why this is its own check, not folded into the mismatch check above: docs/4-systems/verify-suites.md, "Traps".
vc_banner_out = out
banner_ok = (
    "UNTESTED" in vc_banner_out
    and "step-card" in vc_banner_out
    and "stop and wait" in vc_banner_out
    and "permission" in vc_banner_out
    and "run the command(s) below yourself" in vc_banner_out
    and "Do not ask in chat" in vc_banner_out
    and "could not finish" in vc_banner_out
)
if banner_ok:
    report("PASS", "when the automatic update fails, the banner says why and tells Claude to run it itself without asking, falling back to the card marked UNTESTED, then stop and wait")
    print("          banner names the failure, the run-it-yourself-now instruction, the card/UNTESTED fallback, and the stop-and-wait instruction")
else:
    report("FAIL", "when the automatic update fails, the banner says why and tells Claude to run it itself without asking, falling back to the card marked UNTESTED, then stop and wait")
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

# --- versioncheck: the GitHub fetch falls back to the API, and a failure reaches the model ------
# 2026-09-24: raw.githubusercontent.com was reset by a sandbox while api.github.com worked, and the
# "couldn't verify" result went only to a systemMessage the model never sees. file:// URLs stand in
# for both routes, so these cases never touch the network: a missing file is a failed fetch.
_vc_dir = tempfile.mkdtemp(prefix="house-rules-vc-")
_vc_dead_url = pathlib.Path(_vc_dir, "missing.json").as_uri()
_vc_api_json = pathlib.Path(_vc_dir, "api-plugin.json")
_vc_api_json.write_text(json.dumps({"version": "99.0.0"}), encoding="utf-8")

session_d = "vc-raw-fails-api-works"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_d),
    vc_env(
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB_URL=_vc_dead_url,
        HOUSE_RULES_VC_GITHUB_API_URL=_vc_api_json.as_uri(),
    ),
)
marker_d = vc_marker_path(session_d)
ok = (
    rc == 0
    and "OUT OF DATE" in out
    and "GitHub's default branch has 99.0.0" in out
    and os.path.isfile(marker_d)
)
if ok:
    report("PASS", "versioncheck falls back to the GitHub API when the raw URL fails, and still flags a stale copy")
    print("          raw route dead, API route reports 99.0.0 - banner fires and the marker is armed")
else:
    report("FAIL", "versioncheck falls back to the GitHub API when the raw URL fails, and still flags a stale copy")
    print(f"          rc={rc} out={out[:300]!r} err={err[:200]!r}")
if os.path.isfile(marker_d):
    os.remove(marker_d)

session_e = "vc-both-routes-fail"
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(session_e),
    vc_env(
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB_URL=_vc_dead_url,
        HOUSE_RULES_VC_GITHUB_API_URL=_vc_dead_url,
    ),
)
marker_e = vc_marker_path(session_e)
try:
    _vc_ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
except Exception:
    _vc_ctx = ""
ok = (
    rc == 0
    and "could not confirm the plugin is current" in _vc_ctx
    and "raw.githubusercontent.com (URLError" in _vc_ctx
    and "api.github.com (URLError" in _vc_ctx
    and _installed_version in _vc_ctx
    and "OUT OF DATE" not in out
    and not os.path.isfile(marker_e)
)
if ok:
    report("PASS", "versioncheck tells the model, not just the UI, when neither GitHub route could be reached")
    print("          additionalContext names both failed routes and the installed version; no banner, no marker")
else:
    report("FAIL", "versioncheck tells the model, not just the UI, when neither GitHub route could be reached")
    print(f"          rc={rc} out={out[:400]!r} marker exists: {os.path.isfile(marker_e)}")
if os.path.isfile(marker_e):
    os.remove(marker_e)

rc, out, err = run_hook(
    "versioncheck",
    vc_payload("vc-agree-no-context"),
    vc_env(HOUSE_RULES_VC_MARKETPLACE=_installed_version, HOUSE_RULES_VC_GITHUB=_installed_version),
)
if rc == 0 and "additionalContext" not in out:
    report("PASS", "versioncheck adds nothing to the model's context when all three copies agree")
    print("          a verified-current plugin stays a UI-only trace line")
else:
    report("FAIL", "versioncheck adds nothing to the model's context when all three copies agree")
    print(f"          rc={rc} out={out[:200]!r}")
shutil.rmtree(_vc_dir, ignore_errors=True)

# --- versioncheck updates the plugin itself, and reads what is installed, not only what runs -----
# 2026-09-26: a session ran 2.29.0 while 2.36.0 was already installed on disk, and the banner asked
# for an update that would have done nothing; the fix is a restart. And the update is now run by
# the hook itself, confirmed by re-reading installed_plugins.json rather than trusting exit 0.
case = "vc-restart-needed"
vc_clear(case)
vc_installed_json(case, "99.0.0")
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(case, HOUSE_RULES_VC_MARKETPLACE="99.0.0", HOUSE_RULES_VC_GITHUB="99.0.0"),
)
ok = (
    rc == 0
    and "OUT OF DATE" not in out
    and "start a new session" in out
    and "Do not run any update command" in out
    and vc_fake_calls(case) == []
    and not os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck says 'start a new session', not 'update', when the newer version is already installed on disk")
    print("          running copy is old, installed_plugins.json has 99.0.0: no banner, no marker, no update run")
else:
    report("FAIL", "versioncheck says 'start a new session', not 'update', when the newer version is already installed on disk")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")

case = "vc-auto-update-works"
vc_clear(case)
vc_installed_json(case, _installed_version)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE=_installed_version,
        HOUSE_RULES_VC_GITHUB="99.0.0",
        VC_FAKE_EXIT="0",
        VC_FAKE_INSTALLS="99.0.0",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case)
    == ["plugin marketplace update aj-house-rules", "plugin update house-rules@aj-house-rules"]
    and "updated automatically at session start" in out
    and "99.0.0" in out
    and "OUT OF DATE" not in out
    and not os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck refreshes the stale marketplace, runs the update itself, and confirms it on disk")
    print("          both commands ran in order; installed_plugins.json then read 99.0.0, so no banner and no marker")
else:
    report("FAIL", "versioncheck refreshes the stale marketplace, runs the update itself, and confirms it on disk")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")

case = "vc-update-exits-0-but-nothing-installed"
vc_clear(case)
vc_installed_json(case, _installed_version)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE="99.0.0",
        HOUSE_RULES_VC_GITHUB="99.0.0",
        VC_FAKE_EXIT="0",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case) == ["plugin update house-rules@aj-house-rules"]
    and "OUT OF DATE" in out
    and "exited 0, but installed_plugins.json lists" in out
    and os.path.isfile(vc_marker_path(case))
)
if ok:
    report("PASS", "versioncheck does not trust an update's exit code: nothing new on disk still means out of date")
    print("          only `plugin update` ran (marketplace already current); exit 0 with no new install -> banner and marker")
else:
    report("FAIL", "versioncheck does not trust an update's exit code: nothing new on disk still means out of date")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")
if os.path.isfile(vc_marker_path(case)):
    os.remove(vc_marker_path(case))

case = "vc-auto-update-off"
vc_clear(case)
rc, out, err = run_hook(
    "versioncheck",
    vc_payload(case),
    vc_env(
        case,
        HOUSE_RULES_VC_MARKETPLACE="99.0.0",
        HOUSE_RULES_VC_GITHUB="99.0.0",
        HOUSE_RULES_AUTO_UPDATE="off",
    ),
)
ok = (
    rc == 0
    and vc_fake_calls(case) == []
    and "OUT OF DATE" in out
    and "HOUSE_RULES_AUTO_UPDATE=off" in out
)
if ok:
    report("PASS", "HOUSE_RULES_AUTO_UPDATE=off keeps the check but never runs the update")
    print("          no `claude` call; the banner says automatic updating is off")
else:
    report("FAIL", "HOUSE_RULES_AUTO_UPDATE=off keeps the check but never runs the update")
    print(f"          rc={rc} calls={vc_fake_calls(case)} out={out[:300]!r}")
if os.path.isfile(vc_marker_path(case)):
    os.remove(vc_marker_path(case))
shutil.rmtree(_vc_fake_dir, ignore_errors=True)

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
