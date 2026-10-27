#!/usr/bin/env python3
"""checks/common.py - the test setup every per-part check file shares (#370).

Not run on its own. Each part file (core.py, safe_git.py, design_loop.py, writing.py, delegation.py, docs.py,
make_page.py) starts with `from common import *`, which gives it: `report` and the counters, the paths, the
temp-repo and fixture helpers, the stub gh, the payload builders, and the other helpers more than one part uses.
Everything here was moved out of verify.py unchanged, except HERE (one level up now) and the temp-folder name.

STDLIB ONLY, like hook.py.
"""


import atexit
from collections import namedtuple
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import tempfile
import time

# #229: every run gets its own temp folder. The hooks keep small state files in the temp folder
# (when aj last wrote, the waiting-on-you list), and these tests reuse session names, so a file
# left by an earlier run made the guard believe aj was away and turn its asks into refusals.
# TMPDIR reaches every hook these tests start; tempfile.tempdir covers this process.
# Each part is its own process with its own temp folder, named for the part, so parts running at the same
# time never share a session file, a scratchpad or a stage file.
PART = os.path.splitext(os.path.basename(sys.argv[0]))[0] or "part"
_RUN_TMP = tempfile.mkdtemp(prefix="house-rules-verify-%s-" % PART)
os.environ["TMPDIR"] = _RUN_TMP
tempfile.tempdir = _RUN_TMP
atexit.register(shutil.rmtree, _RUN_TMP, True)

# checks/ sits one level below scripts/, which is where hook.py, run.sh and the helper scripts are.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)  # so `import clarity`, `import labels`, `import make_page` resolve as they did from verify.py
HOOK = os.path.join(HERE, "hook.py")
# The core module (#357): hook.py imports it, so source-reading checks read both.
CORE = os.path.join(HERE, "house_rules", "core.py")
# The safe git and docs parts (#358): the guards and the docs check live here now, so source-reading checks read them.
SAFE_GIT = os.path.join(HERE, "house_rules", "safe_git.py")
DOCS = os.path.join(HERE, "house_rules", "docs.py")
# The delegation, design loop and writing parts (#359): the rest of what hook.py held, so source-reading checks read them.
DELEGATION = os.path.join(HERE, "house_rules", "delegation.py")
DESIGN_LOOP = os.path.join(HERE, "house_rules", "design_loop.py")
WRITING = os.path.join(HERE, "house_rules", "writing.py")
RUN = os.path.join(HERE, "run.sh")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RULES_FILE = os.path.join(HERE, "..", "rules", "house-rules.md")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
AGENTS_DIR = os.path.join(HERE, "..", "agents")
# The three tier agents and the model each must declare (and, at SubagentStop, actually run on).
TIERS = {"scout": "haiku", "builder": "sonnet", "reviewer": "opus", "editor": "sonnet"}
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
    # The show-don't-tell rule is injected by its own handler (showrule), not inside house-rules.md.
    corpus += "\n\n" + read(os.path.join(HERE, "..", "rules", "show-dont-tell.md"))
    corpus += "\n\n" + read(os.path.join(HERE, "..", "rules", "clear-writing.md"))
    if os.path.isdir(DETAIL_DIR):
        for name in sorted(os.listdir(DETAIL_DIR)):
            if name.endswith(".md"):
                corpus += "\n\n" + read(os.path.join(DETAIL_DIR, name))
    return corpus


def run_hook(event, payload="", env=None):
    e = dict(os.environ) if env is None else env
    # #397: a sandbox that is itself a project thread would otherwise write test work trails into
    # the real shared project folder.
    e.setdefault("HOUSE_RULES_WORKTRAIL_DIR", os.path.join(tempfile.gettempdir(), "house-rules-verify-worktrail"))
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

RULE_COMMIT = "Commit constantly on my own branches, never on theirs"
RULE_DESTRUCTIVE = "Never take a destructive action without checking first"
DEFAULT = "is the default branch"  # in every refusal of a default-branch git write (#197)

# --- branch fixtures -------------------------------------------------------------------------
# Why fixtures instead of the developer's branch: docs/architecture.md, "Fixture repos, not the developer's branch".
_FIXTURE_ROOT = tempfile.mkdtemp(prefix="house-rules-verify-")
# The design-loop lock (#225) refuses code edits outside Build in any repo, which would turn every
# fixture edit below into a refusal. It is off for the suite and switched on by its own cases.
os.environ["HOUSE_RULES_LOOP"] = "off"
# Simulated spawns in this file must never leave records in the real repository's agent list.
os.environ["HOUSE_RULES_AGENTS_STATE"] = os.path.join(_FIXTURE_ROOT, "default-agents.json")
atexit.register(shutil.rmtree, _FIXTURE_ROOT, True)
# The author guard (#177) reads the git identity, and a cloud container's ~/.gitconfig is Claude. Point
# git at a fixture global config with the agent identity so these cases do not depend on the machine.
_GIT_GLOBAL = os.path.join(_FIXTURE_ROOT, "gitconfig-global")
with open(_GIT_GLOBAL, "w", encoding="utf-8") as _gf:
    _gf.write("[user]\n\tname = AJ's agent\n\temail = 79066376+Ajw2003@users.noreply.github.com\n")
os.environ["GIT_CONFIG_GLOBAL"] = _GIT_GLOBAL


def _repo_on(name, head_line):
    path = os.path.join(_FIXTURE_ROOT, name)
    os.makedirs(os.path.join(path, ".git"))
    with open(os.path.join(path, ".git", "HEAD"), "w", encoding="utf-8") as f:
        f.write(head_line)
    return path


REPO_THEIRS = _repo_on("theirs", "ref: refs/heads/main\n")
REPO_MINE = _repo_on("mine", "ref: refs/heads/claude/some-topic\n")
REPO_DETACHED = _repo_on("detached", "9f1c0de0000000000000000000000000000000ab\n")
REPO_THEIRS_FEATURE = _repo_on("theirs-feature", "ref: refs/heads/feature/theirs\n")
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
    ("showrule", 9_500, env_in(ROOT)),
    ("standards", 9_500, env_in(ROOT)),
    ("profile", 9_500, env_in(ROOT, HOUSE_RULES_ENV_FILE=EXAMPLE_ENV)),
    ("docstiers", 9_500, env_in(DOCSTIERS_NOT_OWNED)),
]

rules_text = rules_corpus()

# --- delegate is wired to ExitPlanMode, not just present in hook.py ---------------------------
hooks_json_text = read(HOOKS_JSON)

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

# --- the default is silent on "looked, nothing to do"; verbose restores it; "could not tell" stays loud
_dflt = dict(os.environ)
_dflt.pop("HOUSE_RULES_TRACE", None)


def stop_payload(**extra):
    base = {"session_id": "verify", "hook_event_name": "Stop", "stop_hook_active": False}
    base.update(extra)
    return json.dumps(base)

# --- the evidence check: an independent trigger from the fence gate above ----------------------
_HAND_ROOT = os.path.join(_FIXTURE_ROOT, "handover-transcripts")
os.makedirs(_HAND_ROOT, exist_ok=True)


def _hand_transcript(name, lines):
    path = os.path.join(_HAND_ROOT, "%s.jsonl" % name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path

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
_par, _vis, _pv_ctx = _stop_notes(_pv_port, "Done, the page is ported.")

# --- plain summary first (#98) ------------------------------------------------------------
_PS_PLAIN = ("The commit hooks are done and pushed. Claude now gets reminded to save its work, and "
             "nothing is waiting on you.\n\n" + "More detail follows here. " * 30)  # under 160 words, so the page rule (#282) stays out of it
_PS_TECH = ("`hook.py`: added `_dirty_paths`, `_uncommitted_among`, `branch_ownership` and "
            "`event_branchnudge`.\n\n" + "More detail follows here. " * 30)

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


def _nudge(root, rel, **extra):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": os.path.join(root, rel)}})
    return run_hook("branchnudge", payload, env=_project_env(root, **extra))[1]

# -- #318: creditcheck reads the body back after a pull request / issue write (fetch stubbed) --------
import importlib.util as _cc_util
import io as _cc_io
_cc_spec = _cc_util.spec_from_file_location("hook_creditcheck", HOOK)
_cc_mod = _cc_util.module_from_spec(_cc_spec)
_cc_spec.loader.exec_module(_cc_mod)


def _creditcheck(cmd, stdout, fetch, off=False):
    _cc_mod.safe_git._read_back_body = fetch  # #358: event_creditcheck lives in house_rules/safe_git.py now
    _saved = (sys.stdin, sys.stdout, os.environ.get("HOUSE_RULES_ATTRIBUTION"))
    sys.stdin = type("S", (), {"buffer": _cc_io.BytesIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}, "tool_response": {"stdout": stdout}}).encode())})()
    sys.stdout = _cc_io.StringIO()
    if off:
        os.environ["HOUSE_RULES_ATTRIBUTION"] = "off"
    try:
        _cc_mod.event_creditcheck()
        return sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = _saved[0], _saved[1]
        os.environ.pop("HOUSE_RULES_ATTRIBUTION", None)
        if _saved[2] is not None:
            os.environ["HOUSE_RULES_ATTRIBUTION"] = _saved[2]
# autosave / commitgate / worktreesweep (2.47.0): a subagent killed mid-run never reaches
# SubagentStop, so its work is protected while it runs. Each fixture repo has a local bare repo
# as `origin`, standing in for GitHub.
def _as_git(d, *args, env=None):
    return subprocess.run(["git", "-c", "user.name=verify", "-c", "user.email=verify@example.invalid",
                           "-C", d] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, check=False).stdout.decode("utf-8", "replace").strip()


def _as_write(d, rel, text="x\n"):
    p = os.path.join(d, rel)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p
_ISS_STUBDIR = tempfile.mkdtemp(prefix="house-rules-ghstub-", dir=_FIXTURE_ROOT)


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

# -- #108: gh pr create ------------------------------------------------------------------------
_dp = _iss_repo()


def _iss_guard(cmd, d=None, **envx):
    d = d or _dp
    return _iss_call("guard", _iss_payload("PreToolUse", "Bash", d, command=cmd), d, **envx)[1]


def _au_repo(name, email):
    d = _iss_repo()
    subprocess.run(["git", "config", "user.name", name], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", email], cwd=d, check=True)
    subprocess.run(["git", "switch", "-q", "-c", "AjsAgent/author"], cwd=d, check=True)
    return d


_AU_GOOD = ("AJ's agent", "79066376+Ajw2003@users.noreply.github.com")
_au_bad, _au_good = _au_repo("Claude", "noreply@anthropic.com"), _au_repo(*_AU_GOOD)
# No gh on PATH is tested in-process, with shutil.which patched and then restored. A PATH built
# from dirname(SH) does not work: on a Linux runner gh lives in /usr/bin beside sh and git.
import importlib.util as _ig_util

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
            "show, don't tell", "nothing unasked is built",
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
         "not a checkpoint", "AjsAgent/<topic>"),
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
            "whole workflow", "starting point", "hand over a command", "touched twice",
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
readme_rel = os.path.join("claude-house-rules", "README.md")
readme_path = os.path.join(ROOT, "claude-house-rules", "README.md")

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

# --- announce / verdict: a delegation says which agent, which model, which digest -------------
# Judged against hand-written transcript fixtures, not whatever this session happens to have
# produced - the same reasoning as the branch fixtures above. A suite that reads the real
# ~/.claude tree passes or fails on the developer's history rather than on the handler.
_SUB_ROOT = tempfile.mkdtemp(prefix="house-rules-subagent-")
atexit.register(shutil.rmtree, _SUB_ROOT, True)
_PARENT = os.path.join(_SUB_ROOT, "sess1.jsonl")
with open(_PARENT, "w", encoding="utf-8") as _f:
    _f.write("")

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


def _pt_run(payload=_pt_payload, guarded=True, **extra):
    if guarded:  # #290: only a prompt a guard raised is timed; record its key as the guard would
        try:
            _d = json.loads(payload)
            _k = hashlib.sha256((_d["tool_name"] + json.dumps(_d["tool_input"], sort_keys=True, separators=(",", ":"),
                                                              default=str)).encode("utf-8")).hexdigest()[:16]
            with open(os.path.join(tempfile.gettempdir(), "house-rules-asked-%s" % re.sub(
                    r"[^0-9A-Za-z_-]", "_", _d["session_id"])), "a", encoding="utf-8") as _af:
                _af.write(_k + "\n")
        except (ValueError, KeyError, TypeError):
            pass  # a malformed payload case: nothing to record
    t0 = time.time()
    code, out, err = run_hook("prompttimer", payload, env=_pt_env(**extra))
    return code, out, err, time.time() - t0

# --- #145: the waiting-on-you list is locked, shown by scope and issuelist, and named in the guard prompts
import threading

# --- #142 follow-ups: questions exempt, away fast-fail, an action that ran is never "timed out" (#149)
def _pt_tool(tool, tool_input, sid="pt-sess", event="PermissionRequest"):
    return json.dumps({"hook_event_name": event, "session_id": sid, "tool_name": tool, "tool_input": tool_input})


def _pt_state_now():
    try:
        return json.load(open(_pt_state, encoding="utf-8"))
    except Exception:
        return []

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

# A backgrounded call's PostToolUse fires immediately with status "async_launched" - nothing
# has happened yet, so audit reports no audit. Since 2.47.0 it asks the parent for a check-in
# instead (so worktreesweep runs while the subagent works); with autosave off it says nothing.
_async_payload = post_agent_payload(
    tool_response={"isAsync": True, "status": "async_launched", "agentId": "audit1"}
)
code_off, out_off, _e = run_hook("audit", _async_payload, env=dict(os.environ, HOUSE_RULES_AUTOSAVE="off"))


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


_nb_r = _commit_repo("AjsAgent/topic", committed=["a.py"])
# #293: each enforced workflow check refuses and names its exact fix (the page, credit-line and
# helper-cap texts are checked where those checks are tested).
_e293 = dict(os.environ, HOUSE_RULES_ATTRIBUTION="on", HOUSE_RULES_ISSUES="on", HOUSE_RULES_CLEAR_WRITING="on",
             HOUSE_RULES_AGENTS="on")


def finish():
    """Print this part's verdict and exit. The same RESULT lines verify.py always printed."""
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
    sys.exit(0 if FAILURES == 0 else 1)


# Every name above, underscore names included, so `from common import *` hands a part file all of it.
__all__ = [_n for _n in dir() if not _n.startswith("__")]
