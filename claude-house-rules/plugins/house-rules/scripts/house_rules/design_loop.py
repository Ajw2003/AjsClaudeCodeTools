"""house_rules.design_loop - the design loop part (#359, step 2c of #340): the issue workflow, the loop stages, labels
and approvals, the issue list, the author and issue guards, the close guard and closablemerge, the end-of-reply
checkpoints and pagecheck. Moved verbatim from hook.py; docs/4-systems/plugin-restructure.md, "Step 2c", says what moved
and why.

Imports only from house_rules.core. It registers itself on the core link lists at the foot of this file."""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse

from house_rules import core
from house_rules.core import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _GATED_TOOLS,
    _GH_PREFIX,
    _GIT_COMMIT_RE,
    _MD_FENCED_BLOCK_RE,
    _PLAN_VALUE_RE,
    _PROMPT_VALUE_RE,
    _PR_BODY_FILE_RE,
    _write_atomic,
    _SESSION_ID_RE,
    _ag,  # #479 (U1): adaptation - the plan's code calls _ag but design_loop.py didn't import it
    _apply_assigns,
    _attribution_enabled,
    _clear_writing_enabled,
    _command_dir,
    _common_git_dir,
    _git_dir,
    _decoded_command,
    _effective_author,
    _field,
    _inside,
    _is_claude_identity,
    _is_relayed_prompt,
    _issues_enabled,
    _issues_locate,
    _last_user_text,
    _loop_enabled,
    _outside_page_links,
    _own_words,
    _payload_cwd,
    _plugin_root,
    _read_text,
    _reply_links_page,
    _waiting_session_note,
)


# ---------------------------------------------------------------------------------------
# Issue workflow (2.49.0): plans over three steps become issues, source edits wait for them,
# PRs link with Refs and never close, and an issue closes only on recorded evidence (#361). The hooks FORCE Claude
# to do these things; none of them runs `gh issue create` or `gh issue close` itself. No new
# hook process on Write/Edit/Bash: delegate writes the state, the Bash PostToolUse entry that
# autosave uses records creations, commitgate gates, handover nags, guard checks the gh commands.
# Plan: docs/plans/issue-workflow-build-plan.md. HOUSE_RULES_ISSUES=off disables all of it.
# ---------------------------------------------------------------------------------------

ISSUES_FILE = "house-rules-issues.json"


ISSUES_LABEL = "AjsAgent created this"


ISSUES_LABEL_OLD = "Claude created this"  # still counts: plans already in flight


ISSUES_STEP_THRESHOLD = 3


ISSUES_NEEDED = 2  # one parent plus at least one child


ISSUE_NOTE = (
    " Issue workflow: this plan has {n} steps, which is more than three, so before any code is "
    "written create one parent issue for the plan and one child issue per step with `gh issue "
    "create`. Each child says `Part of #<parent>` in its body. Titles are plain language a "
    "non-programmer can follow. Every issue carries at least one category label and the label "
    "`AjsAgent created this`; if the repo lacks that label, create it first with `gh label "
    "create`. Show the user the issue numbers. Mark a step `in progress` (`gh api repos/<owner>/<repo>/issues/N/labels "
    "-f \"labels[]=in progress\"`; the `gh issue edit` form fails in cloud sessions) when work on it starts and remove it when the issue closes. "
    "Until a parent and at least one child exist, a hook blocks edits to source files "
    "(docs/ pages, .claude/ files other than settings, and .md, .txt and .csv files stay open). Do not close any issue yourself: closing always "
    "asks the user."
)


def _issues_read(git_dir):
    """(state dict or None, problem or None). A missing file is the normal no-gate state; an
    unreadable or corrupt one is reported and treated as no gate (fail open, loud)."""
    path = os.path.join(git_dir, ISSUES_FILE)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as exc:
        return None, ("house-rules: could not read %s (%s), so the issue gate is off for this call."
                      % (ISSUES_FILE, exc))
    return data, None


def _issues_write(git_dir, state):
    _write_atomic(os.path.join(git_dir, ISSUES_FILE), json.dumps(state))


def _labelled_count(state):
    return sum(1 for c in state.get("created", []) if isinstance(c, dict) and c.get("labelled"))


_STEP_LINE_RES = (
    re.compile(r"^\s*\d+[.)]\s", re.MULTILINE),
    re.compile(r"^\s*[-*]\s+\[ \]", re.MULTILINE),
    re.compile(r"^#{3,}\s+(?:Step|Change)", re.MULTILINE | re.IGNORECASE),
)


def _plan_step_count(plan):
    return sum(len(r.findall(plan)) for r in _STEP_LINE_RES)


def _issues_plan_note(payload):
    """Delegate's issue half: count the plan's steps, write the gate state when it is over the
    threshold, and return the text to append to the delegate note (always at least one sentence)."""
    if not _issues_enabled():
        return ""
    raw = _field(_PLAN_VALUE_RE, payload or "")
    if raw is None:
        return " Issue workflow: could not read the plan text from the payload, so the issue gate is off for this plan."
    try:
        plan = json.loads('"%s"' % raw)
    except ValueError:
        plan = raw
    n = _plan_step_count(plan)
    if n <= ISSUES_STEP_THRESHOLD:
        return " Issue workflow: this plan counts %d step(s), 3 or fewer, so no issues are required." % n
    top, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return (" Issue workflow: this plan counts %d steps but the directory is not in a git repo, "
                "so no gate was set." % n)
    import datetime
    state = {"plan_steps": n, "approved_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "needs_issues": True, "created": []}
    try:
        _issues_write(git_dir, state)
    except OSError as exc:
        return (" Issue workflow: this plan counts %d steps but the gate state could not be written "
                "(%s), so edits are not blocked. Create the issues anyway." % (n, exc)) + ISSUE_NOTE.format(n=n)
    # #276: no label setup here. This runs on a tool call, and tool calls never reach the network;
    # the labels are created when aj's "Design approved" arrives, before any issue is made.
    return ISSUE_NOTE.format(n=n)


# D4: under docs/ only code is locked; H5: notes and data files are open everywhere, like .md.
_CODE_EXTS = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".ps1", ".rb", ".bat",
              ".cmd", ".cs", ".go", ".rs", ".java", ".c", ".cpp", ".h")
_OPEN_EXTS = (".md", ".txt", ".csv")  # aj chose 8A: notes and csv data open; .json stays locked


def _gated_edit(payload, who):
    """(git_dir or None, problem or None) for a Write/Edit/NotebookEdit of a source file inside a
    repo. None for anything the edit blocks never cover: another tool, a path outside the
    project, docs/, .claude/, any .md file. `who` names the block in the problem message."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None, "house-rules: the %s could not parse the hook payload, so it is off for this call." % who
    if not isinstance(data, dict) or data.get("tool_name") not in _GATED_TOOLS:
        return None, None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp:
        return None, None
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None, None
    if not _is_source_path(fp, cwd, top):
        return None, None
    return git_dir, None


def _is_source_path(fp, cwd, top):
    """The commitgate test: is `fp` a source file of the checkout at `top`? False for a path outside it,
    any .md, .txt or .csv file, the tracker files, and docs/ or .claude/ files that are not code.
    .claude/settings*.json is locked (it can switch the loop off), and a path inside
    .claude/worktrees/<name>/ is judged as if from that worktree, which is a whole checkout (D4, H5)."""
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(fp)), os.path.normcase(top))
    except ValueError:
        rel = ".."  # another drive: outside the project
    parts = rel.replace("\\", "/").split("/")
    if parts[:2] == [".claude", "worktrees"] and len(parts) > 3:
        parts = parts[3:]
    name, low = parts[-1], "/".join(parts).lower()
    if parts[0] == ".." or low.endswith(_OPEN_EXTS) or name in (ISSUES_FILE, LOOP_FILE):
        return False
    if parts[0] == ".claude":
        return name.lower().startswith("settings") and low.endswith(".json")
    if parts[0] == "docs":
        return low.endswith(_CODE_EXTS)
    return True


_SHELL_TOOLS = ("Bash", "PowerShell")


_HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)


_QUOTED_RE = re.compile(r"(>>?[ \t]*)?(\"[^\"\n]*\"|'[^'\n]*')")


_REDIRECT_RE = re.compile(r"(?<![<>&|])(?:\d|&)?>>?(?![&(>])[ \t]*(\"[^\"\n]+\"|'[^'\n]+'|[^\s;&|<>()\"']+)")


_PY_OPEN_RE = re.compile(r"\bopen\(\s*([^,()]+?)\s*,\s*(?:mode\s*=\s*)?['\"][wax]")


_PY_WRITE_TEXT_RE = re.compile(r"\.write_text\(")


_PY_WRITE_TEXT_LIT_RE = re.compile(r"Path\(\s*(['\"])([^'\"]+)\1\s*\)\s*\.write_text\(")


_NODE_WRITE_RE = re.compile(r"\bwriteFileSync\(")


_NODE_WRITE_LIT_RE = re.compile(r"\bwriteFileSync\(\s*(['\"])([^'\"]+)\1")


_SCRIPT_RUNNER_RE = re.compile(r"(?:^|[\s;&|(/])(?:python3?|py|node)(?:\.exe)?(?=\s|$)")


_LITERAL_RE = re.compile(r"^(['\"])(.+)\1$")


def _script_write_targets(cmd):
    """(targets, unreadable): file paths a shell command writes through a python/node script
    (open w/a, write_text, writeFileSync), sed -i / perl -pi, tee, or a > / >> redirect, and
    whether some write's path could not be read from the command text (#262)."""
    import shlex
    targets, unreadable = [], False
    body = _HEREDOC_RE.sub("", cmd)
    if _SCRIPT_RUNNER_RE.search(cmd):
        for m in _PY_OPEN_RE.finditer(cmd):
            lit = _LITERAL_RE.match(m.group(1))
            if lit and "$" not in lit.group(2):
                targets.append(lit.group(2))
            else:
                unreadable = True
        lits = _PY_WRITE_TEXT_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_PY_WRITE_TEXT_RE.findall(cmd)) > len(lits):
            unreadable = True
        lits = _NODE_WRITE_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_NODE_WRITE_RE.findall(cmd)) > len(lits):
            unreadable = True
    for stmt in re.split(r"&&|\|\||;|\n|\|", body):
        try:
            words = shlex.split(stmt)
        except ValueError:
            sys.stderr.write("house-rules design-loop lock: could not split a statement (unbalanced quotes) "
                             "to look for sed -i / tee; skipping that statement.\n")
            continue
        for i, w in enumerate(words):
            if w not in ("sed", "perl", "tee"):
                continue
            if any(p not in ("sudo", "env", "time", "nohup") and "=" not in p for p in words[:i]):
                continue  # not in command position (e.g. `echo sed -i`, `grep tee f`)
            rest = words[i + 1:]
            files, has_script, skip = [], False, False
            in_place = w == "tee"
            for a in rest:
                if skip:
                    skip = False
                elif a in ("-e", "-f", "--expression", "--file"):
                    has_script, skip = True, True
                elif re.match(r"^-[A-Za-z]+$", a) and a.endswith("e") and not re.match(r"^-[A-Za-z]*i", a):
                    has_script, skip = True, True  # -ne / -pe: the next word is the script
                elif a.startswith("-"):
                    if a == "--in-place" or a.startswith("--in-place=") or re.match(r"^-[A-Za-z]*i", a):
                        in_place = True
                else:
                    files.append(a)
            if not in_place:
                continue
            if w == "sed" and not has_script and files:
                files = files[1:]
            if not files:
                unreadable = True
            for f in files:
                if re.search(r"[$`~*?]", f):
                    unreadable = True
                else:
                    targets.append(f)
            break
    plain = _QUOTED_RE.sub(lambda m: m.group(0) if m.group(1) else " ", body)
    for m in _REDIRECT_RE.finditer(plain):
        t = m.group(1).strip("'\"")
        if t.startswith("/dev/"):
            continue
        if re.search(r"[$`~*?]", t):
            unreadable = True
        else:
            targets.append(t)
    return targets, unreadable


def _gated_script_write(payload):
    """(git_dir, problem, paths, unreadable) for a Bash/PowerShell command that writes a source
    file through a script, sed -i, tee or a redirect. git_dir None when nothing is gated."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None, "house-rules: the design-loop lock could not parse the hook payload, so it is off for this call.", [], False
    if not isinstance(data, dict) or data.get("tool_name") not in _SHELL_TOOLS:
        return None, None, [], False
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cmd = ti.get("command")
    if not isinstance(cmd, str) or not cmd:
        return None, None, [], False
    cmd = _apply_assigns(cmd)
    targets, unreadable = _script_write_targets(cmd)
    if not targets and not unreadable:
        return None, None, [], False
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None, None, [], False
    src = [t for t in targets if _is_source_path(t, cwd, top)]
    if not src and not unreadable:
        return None, None, [], False
    return git_dir, None, src, unreadable


def _issues_gate(payload):
    """(deny reason or None, problem or None) for a Write/Edit/NotebookEdit payload."""
    git_dir, problem = _gated_edit(payload, "issue gate")
    if not git_dir:
        return None, problem
    state, problem = _issues_read(git_dir)
    if problem:
        return None, problem
    if not state or not state.get("needs_issues"):
        return None, None
    have = _labelled_count(state)
    return (
        "House rules, plans become issues: the approved plan has %s steps, so source edits are "
        "blocked until its issues exist. Two pieces are missing: (1) a parent issue for the plan, "
        "(2) at least one child issue per step saying `Part of #<parent>`, each carrying the label "
        "`%s` (%d of %d recorded). Create them with `gh issue create --label \"%s\"`, show the user "
        "the numbers, then repeat this edit. docs/, .md files and .claude/ are editable meanwhile. "
        "To switch this off: HOUSE_RULES_ISSUES=off." % (state.get("plan_steps", "more than 3"),
                                                          ISSUES_LABEL, have, ISSUES_NEEDED, ISSUES_LABEL),
        None,
    )


# ---------------------------------------------------------------------------------------
# The design loop (#223, #225): each project has a stage - design, plan, build, done - kept in
# LOOP_FILE in .claude/ of the main checkout and carried across sessions. Only aj's own message moves it
# (scope reads it before the model does), and code edits are refused outside build. "I review"
# happens inside build, because fixing what the review finds is code. Design:
# docs/plans/loop-design.html. HOUSE_RULES_LOOP=off disables it.
# ---------------------------------------------------------------------------------------

LOOP_FILE = "house-rules-loop.json"


LOOP_STAGE_NAMES = {"design": "Design", "plan": "Plan", "build": "Build", "qa": "QA", "done": "Done"}


# D2: an approval counts only where aj's sentence starts with it (a line start, or after . ! , ; or a tag such as
# <message>, with optional quote marks or a bullet), and not when it runs into a question mark.
_LOOP_LEAD = r"(?:^|[.!,;][ \t]+)(?:<[\w/]+>)?[ \t>\"'*\-]*"
_LOOP_NOT_ASKED = r"(?![^\n.!]*\?)"


_LOOP_DESIGN_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"(?<!don't )(?<!dont )(?<!do not )(?<!not )design\s+approved" + _LOOP_NOT_ASKED
                             + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_PLAN_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"(?<!don't )(?<!dont )(?<!do not )(?<!not )build\s+plan\s+approved" + _LOOP_NOT_ASKED
                           + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_QA_RE = re.compile(r"(?m)" + _LOOP_LEAD + r"(?<!don't )(?<!dont )(?<!do not )(?<!not )qa\s+(passed|failed)" + _LOOP_NOT_ASKED
                         + r"\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)


_LOOP_SKIP_RE = re.compile(r"(?<!don't )(?<!dont )(?<!do not )(?<!not )\bskip\s+design\b" + _LOOP_NOT_ASKED,
                           re.IGNORECASE)


# #409: an approval that is only quoted (a `>` line, or a quote opened after "said ...:") is another
# thread's message passed along, not aj approving here.
_LOOP_PHRASE = r"(?:design\s+approved|build\s+plan\s+approved|qa\s+(?:passed|failed))\b"
_LOOP_QUOTED_RE = re.compile(r"(?mi)(?:^[ \t]*>[ \t>\"'*\-]*|:[ \t]*[\"'“])" + _LOOP_PHRASE)


_LOOP_BARE_RE = re.compile(r"\b(approved|qa\s+passed|qa\s+failed)\b", re.IGNORECASE)


# #501: a line that names something and ends in answer picks ("1A 2A", "3*"), the shape of an approval
# missing its stage words. A pick is a digit run plus one letter A-H or a star, so "3D printer" never fits.
_LOOP_PICKS_ONLY_RE = re.compile(r"(?m)^[ \t]*[A-Za-z][^\n?]*?(?:[ \t]+\d+[A-Ha-h*])+[ \t]*[.!]?[ \t]*$")


# #491: the stage words may follow the feature name, never after a negation or inside a question
_LOOP_STAGE_WORDS = r"(design\s+approved|build\s+plan\s+approved|qa\s+passed|qa\s+failed)"
_LOOP_AFTER_RE = re.compile(r"(?mi)(" + _LOOP_LEAD + r")((?!" + _LOOP_STAGE_WORDS
                            + r")(?=\w)(?:(?!\bnot\b|n't\b)[^\n.?!:])+?)\s+"
                            + _LOOP_STAGE_WORDS + _LOOP_NOT_ASKED + r"[ \t]*:?[ \t]*([^\n]*)")
_LOOP_STAGE_TEXT = {"design": "Design approved", "build": "Build plan approved", "qa passed": "QA passed",
                    "qa failed": "QA failed"}


def _loop_normalise(text):
    """'Phase 1 design approved 1A' -> 'Design approved: Phase 1 1A', then the old patterns run."""
    def fix(m):
        words = re.sub(r"\s+", " ", m.group(4).lower())
        key = words if words.startswith("qa") else words.split()[0]
        return "%s%s: %s %s" % (m.group(1), _LOOP_STAGE_TEXT[key], m.group(2).strip(), m.group(5))
    return _LOOP_AFTER_RE.sub(fix, text)


def _loop_any_phrase(text):
    """True when the text holds an approval phrase in either word order (for the not-a-repo note)."""
    return bool(_LOOP_BARE_RE.search(text) or _LOOP_AFTER_RE.search(text))


def _loop_dir(git_dir):
    """#262: where the stage file lives - the COMMON git directory (what `git rev-parse
    --git-common-dir` prints, read from the worktree's `commondir` file so no git process is
    spawned on every edit), so every worktree of a repo shares one stage. A git directory with no
    readable commondir is its own common directory (a plain checkout, or git unreadable)."""
    cd = os.path.join(git_dir, "commondir")
    if os.path.isfile(cd):
        rel = _read_text(cd).strip()
        if rel:
            return os.path.abspath(rel if os.path.isabs(rel) else os.path.join(git_dir, rel))
    return git_dir


def _loop_path(git_dir):
    """#265: the stage file lives in .claude/ of the MAIN checkout (the parent of the common git
    directory), so it is committed with the branch and a fresh clone keeps the stage."""
    return os.path.join(os.path.dirname(_loop_dir(git_dir)), ".claude", LOOP_FILE)


def _loop_read(git_dir):
    """(state, problem). No file means a project that has not started a feature: Design. D3: the old
    place, LOOP_FILE in the git directory, is no longer read, so a file written there opens nothing."""
    fresh = {"feature": "", "stage": "design", "skip": False, "approvals": []}
    path = _loop_path(git_dir)
    if not os.path.isfile(path):
        return fresh, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("stage") not in LOOP_STAGE_NAMES:
            raise ValueError("no valid stage")
    except (OSError, ValueError) as exc:
        return None, ("house-rules: could not read %s (%s), so the design-loop lock is off for this call."
                      % (LOOP_FILE, exc))
    state = dict(fresh, **data)
    _loop_note_seen(git_dir, state)
    return state, None


def _loop_write(git_dir, state):
    _write_atomic(_loop_path(git_dir), json.dumps(state))
    _loop_note_seen(git_dir, state)


SEEN_FILE = "house-rules-loop-seen.json"


def _loop_ref_text(path):
    """The text of a small git file, or "" when it is absent (a missing ref is an answer, not an error)."""
    return _read_text(path).strip() if os.path.isfile(path) else ""


def _loop_branch(git_dir):
    """D9/U3: the branch this git directory has checked out, read from its HEAD file (no git process on
    every edit). "" for a detached HEAD or an unreadable file."""
    m = re.match(r"ref:\s*refs/heads/(\S+)", _loop_ref_text(os.path.join(git_dir, "HEAD")))
    return m.group(1) if m else ""


def _loop_newest(state):
    """The `at` of the newest approval a stage file records (0 when there is none)."""
    return max([a["at"] for a in state.get("approvals") or []
                if isinstance(a, dict) and isinstance(a.get("at"), int)] or [0])


def _loop_seen(git_dir):
    """D9: the clone-wide record of the newest approval seen, in the common git directory: {} when none."""
    path = os.path.join(_loop_dir(git_dir), SEEN_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        sys.stderr.write("house-rules: could not read %s (%s), so no newer-branch hold applies.\n" % (SEEN_FILE, exc))
        return {}
    return data if isinstance(data, dict) and isinstance(data.get("at"), int) else {}


def _loop_note_seen(git_dir, state):
    """D9: record this branch's newest approval when it is newer than the one on record. A failed write
    is reported on stderr, never silent."""
    at = _loop_newest(state)
    if at and at > (_loop_seen(git_dir).get("at") or 0):
        try:
            _write_atomic(os.path.join(_loop_dir(git_dir), SEEN_FILE), json.dumps(
                {"at": at, "branch": _loop_branch(git_dir), "feature": state.get("feature") or ""}))
        except OSError as exc:
            sys.stderr.write("house-rules: could not record the newest approval seen (%s).\n" % exc)


def _loop_stale_hold(git_dir, state):
    """D9: a refusal when this branch's newest approval is OLDER than the newest recorded from a different
    branch (an old branch checked out brings back its older stage), else None."""
    seen, here = _loop_seen(git_dir), _loop_branch(git_dir)
    if seen and seen.get("branch") and seen["branch"] != here and _loop_newest(state) < seen["at"]:
        return ("House rules, design loop: this branch's stage (%s, branch \"%s\") is older than the newest "
                "approval in this clone, which was given on branch \"%s\", so code edits stay closed. Write "
                "\"Continue from: %s\" to take that branch's stage, or approve anew on this branch."
                % (LOOP_STAGE_NAMES[state["stage"]], here or "detached HEAD", seen["branch"], seen["branch"]))
    return None


def _loop_default_branches(git_dir):
    """U3: the default branch names: origin/HEAD's target when the common git directory has it (a loose ref;
    packed-refs cannot hold a symbolic ref), else main and master."""
    m = re.match(r"ref:\s*refs/remotes/origin/(\S+)",
                 _loop_ref_text(os.path.join(_loop_dir(git_dir), "refs", "remotes", "origin", "HEAD")))
    return {m.group(1)} if m else {"main", "master"}


def _loop_read_merged(git_dir):
    """U3: _loop_read, except that on the default branch a feature in QA reads as Done (its pull request
    merged and main carries the branch's stage file). Nothing is written. Used by the gate, the stop line
    and the approvals; a write after it saves "done" only when an approval moved the state."""
    state, problem = _loop_read(git_dir)
    if state and state["stage"] == "qa" and _loop_branch(git_dir) in _loop_default_branches(git_dir):
        state = dict(state, stage="done")
    return state, problem


# A9: commands that only read a file, and the git steps that save it. Anything else naming the stage file is refused.
# sed, awk, echo and printf are here because their writes (sed -i, a > redirect) are caught by _script_write_targets.
_LOOP_READERS = {"cat", "head", "tail", "less", "more", "grep", "rg", "jq", "wc", "ls", "stat", "file", "diff",
                 "sed", "awk", "echo", "printf"}
_LOOP_GIT_READS = {"add", "commit", "diff", "log", "show", "status", "blame"}
_LOOP_JSON_READ_RE = re.compile(r"json\.load\(\s*open\(")
_LOOP_PY_WRITE_RE = re.compile(r"shutil|os\.(?:replace|rename|remove)|\.write|json\.dump\b|copy", re.IGNORECASE)


def _loop_file_shell_write(cmd):
    """A9: True when a shell statement names the stage file and is not a read-only command, `git add` or
    `git commit`. Python or node count as a read only when they json.load the file and write nothing."""
    import shlex
    text = _HEREDOC_RE.sub("", cmd)
    if LOOP_FILE not in text:
        return False
    try:  # quote-aware, so `python3 -c "import json; print(...)"` stays one statement
        lex = shlex.shlex(text.replace("\n", ";"), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = None
    if tokens is None:  # unbalanced quotes around the stage file's name: refuse rather than guess
        return True
    stmts, cur = [], []
    for t in tokens:
        if t in (";", "&&", "||", "|", "&"):
            stmts.append(cur)
            cur = []
        else:
            cur.append(t)
    stmts.append(cur)
    for toks in stmts:
        stmt = " ".join(toks)
        if LOOP_FILE not in stmt:
            continue
        words = [w for w in toks if "=" not in w.split("/")[0] and w not in ("sudo", "env", "time")]
        first = os.path.basename(words[0]) if words else ""
        if first in _LOOP_READERS:
            continue
        if first == "git":
            rest = words[1:]
            while rest and rest[0].startswith("-"):  # git's own options, such as -C <path>
                rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
            if rest and rest[0] in _LOOP_GIT_READS:
                continue
        if re.match(r"(?:python3?|py|node)(?:\.exe)?$", first) and _LOOP_JSON_READ_RE.search(stmt) \
                and not _LOOP_PY_WRITE_RE.search(stmt):
            continue
        return True
    return False


def _loop_file_refusal(payload):
    """Deny reason when a Write/Edit/NotebookEdit or a shell redirect/script names the stage file:
    only aj's approval messages move the stage. None otherwise."""
    data = json.loads(payload)  # _loop_gate calls this only after _gated_edit parsed the same payload
    if not isinstance(data, dict):
        return None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if data.get("tool_name") in _GATED_TOOLS:
        paths = [ti.get("file_path") or ti.get("notebook_path")]
    elif data.get("tool_name") in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        if _loop_file_shell_write(ti["command"]):
            return ("House rules, design loop: this command names %s and isn't a read, `git add` or `git commit`, "
                    "so it could overwrite the stage. Only aj's approval messages move the stage. To switch the "
                    "loop off: HOUSE_RULES_LOOP=off." % LOOP_FILE)
        paths = _script_write_targets(_apply_assigns(ti["command"]))[0]
    else:
        return None
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None
    # D3: the old place in the git directory is still read when .claude/ has no stage file, so it is the stage file too.
    want = {os.path.normcase(os.path.abspath(x)) for x in (_loop_path(git_dir), os.path.join(_loop_dir(git_dir), LOOP_FILE))}
    for p in paths:
        if isinstance(p, str) and p:
            p = p if os.path.isabs(p) else os.path.join(cwd, p)
            if os.path.normcase(os.path.abspath(p)) in want:
                return ("House rules, design loop: %s is the stage tracker and only aj's approval messages "
                        "move the stage, so it cannot be edited by hand. To switch the loop off: "
                        "HOUSE_RULES_LOOP=off." % LOOP_FILE)
    return None


LOOP_LOG = os.path.join("docs", "6-decisions", "Decisions.md")


def _loop_log_mark(top):
    """A fingerprint of the decisions log, or None when the project has none. Any other read error
    propagates to _loop_scope_note, which reports it."""
    path = os.path.join(top, LOOP_LOG)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _loop_unlogged(state, top, label, name):
    """#230: an approval counts only once the stage being closed is in the decisions log - the log
    must exist and have changed since the last approval. A refusal note, or "" when it may count."""
    mark = _loop_log_mark(top)
    if mark is None:
        return ('Design loop: aj wrote "%s: %s", but this project has no decisions log (%s), so nothing '
                "moved. Create it, log this stage's decisions, then ask aj to approve again."
                % (label, name, LOOP_LOG.replace(os.sep, "/")))
    if mark == state.get("log_mark"):
        # #327: the model can only log the entry after the approval, so refusing made aj type it twice.
        # The approval counts; the note asks for the entry. log_mark stays, so the next approval still
        # detects whether this one got logged.
        state["log_ask"] = True
        return ""
    state["log_mark"] = mark
    return ""


# A feature name ends at the end of its sentence, or where a pasted reply such as "Build plan: 1A 2A"
# starts on the same line - found in the real run, where the whole line became the name. A spaced
# dash ends it too: "QA failed: label check - it should say hi" (found in the label check's real run). So
# does a pasted page reply's answer codes: "New item visual: 1C", "Label check plan: 1A 2A" (#243).
# A capitalised header before a colon ends it only when an answer code does not follow (#266): "enforced QA
# stage: 1A" is a name and its codes, but a pasted "Build plan: 1A" header is cut whole.
_LOOP_NAME_END_RE = re.compile(r"[.!?](?:\s|$)|\s+(?:Build|Design) plan:|\s+[A-Z][A-Za-z ]{0,30}:\s(?!\d+[A-Za-z*](?:\s|$))"
                               r"|\s+[-–—]\s|\s*:\s*\d+[A-Za-z*](?:\s|$)")


# #403: a name also ends at the first `<` that starts a tag ("</message>" pasted from a reply), and
# a trailing run of answer codes ("1A 2A", "1*") is cut. "3D printer" stays whole: a code is only a
# space-separated trailing token shaped digit + letter/star.
_LOOP_TAG_RE = re.compile(r"<[/A-Za-z!?]")
_LOOP_TRAIL_CODES_RE = re.compile(r"(?:\s+\d+[A-Za-z*])+$")


def _loop_name(raw):
    tag = _LOOP_TAG_RE.search(raw)
    text = raw[:tag.start()] if tag else raw
    m = _LOOP_NAME_END_RE.search(text)
    cut = (text[:m.start()] if m else text).strip()
    cut = _LOOP_TRAIL_CODES_RE.sub("", cut).strip()
    return cut or raw.strip()


def _loop_same(a, b):
    """D6: True when two feature names agree, ignoring case and _loop_name's clean-up, or when one starts with the
    other as whole words ("background work tracking" and "background work tracking 1A except ...")."""
    x, y = _loop_name(a or "").lower(), _loop_name(b or "").lower()
    if not x or not y:
        return False
    short, longer = sorted((x, y), key=len)
    return longer == short or longer.startswith(short + " ")


# #235: an issue's label says whose move it is - `in progress` is mine, `needs review` is aj's - and
# every stage move checks it. Labels are read from GitHub every time (#236); when that read fails,
# from the label changes this hook recorded, and the note says why.
LOOP_WORKING, LOOP_REVIEW = "in progress", "needs review"


LOOP_GH_SECONDS = 5  # the reads run in parallel, well inside hooks.json's 10s per hook


# Tests point this at a JSON file of {"owner/repo#n": [labels]} standing in for GitHub; a missing
# file reads as a failed GitHub read.
LOOP_LABELS_FILE_ENV = "HOUSE_RULES_LOOP_LABELS_FILE"


def _loop_key(repo, number):
    return "%s#%d" % (repo, int(number))


def _loop_gh_labels(repo, number):
    import subprocess
    proc = subprocess.run(["gh", "api", "repos/%s/issues/%d" % (repo, number), "--jq", "[.labels[].name]"],
                          capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(detail[0] if detail else "gh exited %d" % proc.returncode)
    return json.loads(proc.stdout)


LOOP_ISSUES_FILE_ENV = "HOUSE_RULES_LOOP_ISSUES_FILE"  # tests: a JSON list of {number, body, labels} rows


def _loop_feature_issues(state, top):
    """(issues, note): the feature's issues read from GitHub at "Build plan approved" - the parent plus every
    open issue whose body says "Part of #<parent>" - merged with what was recorded (hand-recorded
    "Issues for" included). On a missing parent or a failed read, the recorded issues and a note saying why."""
    import subprocess
    recorded = [i for i in state.get("issues", []) if isinstance(i, dict)]
    parent = state.get("parent")
    if parent is None:
        return recorded, ('No step issue named "Part of #N" was seen in Plan, so the feature\'s issues were not '
                          "read from GitHub; the %d recorded issue(s) were used." % len(recorded))
    own, _problem = _origin_slug(top)
    try:
        stand_in = os.environ.get(LOOP_ISSUES_FILE_ENV)
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                rows = json.load(f)
        else:
            if not shutil.which("gh"):
                raise RuntimeError("gh is not installed")
            if not own:
                raise RuntimeError("this checkout has no GitHub origin")
            # The REST list, not `gh issue list`: that one uses GraphQL, which cloud sessions refuse (403), and
            # GitHub's search index lags behind issues made a moment ago. Pull requests are dropped below.
            proc = subprocess.run(["gh", "api", "repos/%s/issues?state=open&per_page=100" % own, "--paginate",
                                   "--jq", ".[] | select(.pull_request == null) | {number, body, labels}"],
                                  capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout).strip().splitlines()
                raise RuntimeError(detail[0] if detail else "gh exited %d" % proc.returncode)
            rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        if not isinstance(rows, list):
            raise ValueError("the issue list was not a JSON list")
        mark = {ISSUES_LABEL.lower(), ISSUES_LABEL_OLD.lower()}
        repo = own or next((i.get("repo") for i in recorded if i.get("repo")), "")
        merged = [{"repo": repo, "number": int(parent), "labelled": True}]
        for r in rows:  # the GitHub search is loose, so each body is re-checked for the exact number
            if any(int(n) == int(parent) for n in _PART_OF_RE.findall(r.get("body") or "")):
                names = {(l.get("name") if isinstance(l, dict) else str(l)).lower() for l in r.get("labels") or []}
                merged.append({"repo": repo, "number": int(r["number"]), "labelled": bool(names & mark)})
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return recorded, ("The feature's issues could not be read from GitHub (%s), so the %d recorded issue(s) "
                          "were used." % (exc, len(recorded)))
    have = {(str(i["repo"]).lower(), i["number"]) for i in merged}
    for i in recorded:  # hand-recorded ones still count
        key = (str(i.get("repo")).lower(), i.get("number"))
        if key not in have:
            merged.append(i)
            have.add(key)
    return merged, ""


def _loop_labels(state, issues=None, record=True):
    """({key: [labels] or None}, note) for the feature's issues (or, #375, the given list: a stored
    feature's). The note is "" when GitHub answered, else it says the labels came from the record and why."""
    import subprocess
    issues = [i for i in (state.get("issues", []) if issues is None else issues)
              if isinstance(i, dict) and i.get("repo") and "number" in i]
    if not issues:
        return {}, ""
    keys = [_loop_key(i["repo"], i["number"]) for i in issues]
    stand_in = os.environ.get(LOOP_LABELS_FILE_ENV)
    try:
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                found = json.load(f)
            return {k: found.get(k) for k in keys}, ""
        if not shutil.which("gh"):
            raise RuntimeError("gh is not installed")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            got = list(pool.map(lambda i: _loop_gh_labels(i["repo"], i["number"]), issues))
        return dict(zip(keys, got)), ""
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        why = "Labels were taken from the changes this hook recorded, because the GitHub read failed (%s)." % exc
        failed = str(exc)
    if not record:  # D9 (aj chose 6B): the Build edit gate never falls back to the stage file's labels
        return {k: None for k in keys}, failed
    recorded = state.get("labels") if isinstance(state.get("labels"), dict) else {}
    return {k: recorded.get(k) for k in keys}, why


def _loop_wrong(labels, want):
    """The issues whose labels don't fit `want` (LOOP_WORKING or LOOP_REVIEW), named with what they have."""
    wrong = []
    for key, have in labels.items():
        low = [str(l).lower() for l in have] if isinstance(have, list) else None
        ok = low is not None and (LOOP_WORKING in low if want == LOOP_WORKING
                                  else LOOP_REVIEW in low and LOOP_WORKING not in low)
        if not ok:
            wrong.append("#%s (%s)" % (key.split("#")[1], ", ".join(have) if low else "no labels known"))
    return wrong


def _loop_to_qa(state, labels):
    """Build becomes QA once every issue says needs review and none says in progress. True if it moved.

    #504: after "QA failed" the stage is Build while every issue still says needs review. That is not a
    finished build, so the move waits (state["reopened"]) until an issue has been seen back at in progress."""
    if state.get("reopened"):
        if state["stage"] != "build" or any(LOOP_WORKING in (l or []) for l in labels.values()):
            state["reopened"] = False
        return False
    if state["stage"] == "build" and labels and not _loop_wrong(labels, LOOP_REVIEW):
        state["stage"] = "qa"
        return True
    return False


_PR_URL_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")


_GITHUB_PR_CREATE_RE = re.compile(r"^mcp__(github|GitHub)__create_pull_request$")


_LOOP_PR_NOTE = (" QA started because a pull request was opened: code edits are now closed. Swap every issue to "
                 "`needs review` and build the QA page with make_page.py; aj answers \"QA passed: <feature>\" "
                 "or \"QA failed: <feature>\".")


_LOOP_QA_NOTE = (" Every issue of the feature says `needs review`, so the stage is QA: code edits are closed, "
                 "and aj answers \"QA passed: <feature>\" or \"QA failed: <feature>\" with the changes.")


def _house_labels_note(top):
    """#276: create any house label this repo's GitHub copy is missing (scripts/labels.py), and say
    what it created or could not. "" when the repo has every label or no GitHub remote. Never raises."""
    try:
        import labels as _labels  # scripts/labels.py, beside this file (sys.path is set above)
        git_dir = _common_git_dir(top) if top else None
        if not git_dir:
            return ""
        repo, _why = _labels.repo_from_git(git_dir)
        if not repo:
            return ""  # no GitHub remote: there is nowhere to create labels
        return _labels.summary_note(_labels.ensure_labels(repo), repo)
    except Exception as exc:
        return ("house-rules: label setup hit an error (%s: %s), so missing house labels were not created."
                % (type(exc).__name__, exc))


def _loop_label_refusal(said, want, wrong, note, top=None):
    made = _house_labels_note(top)
    return ('Design loop: aj wrote "%s", but these issues are not labelled `%s`: %s. Nothing moved. Fix the '
            "labels, then ask aj to approve again.%s%s" % (said, want, "; ".join(wrong), " " + note if note else "",
                                                          " " + made if made else ""))


_LOOP_STAGE_ORDER = ((_LOOP_DESIGN_RE, 0), (_LOOP_PLAN_RE, 1), (_LOOP_QA_RE, 2))


_LOOP_SWEEP_RE = re.compile(r"\bsweep\s+approved\s*:\s*issues\b([^\n]*)", re.IGNORECASE)


_LOOP_NOTPLANNED_RE = re.compile(r"\bclose\s+as\s+not\s+planned\s*:[ \t]*([^\n]*)", re.IGNORECASE)


_LOOP_NP_PAIR_RE = re.compile(r"(?:([\w.-]+/[\w.-]+))?#(\d+)\s+replaced\s+by\s+(?:[\w.-]+/[\w.-]+)?#(\d+)",
                              re.IGNORECASE)


def _loop_sweep_apply(state, text):
    """#364: aj's sweep approvals. "Sweep approved: issues [keep #N ...]" moves sweep_proposed into sweep;
    "Close as not planned: #N replaced by #M[, ...]" appends not_planned entries. Returns notes ("" if none)."""
    notes = []
    m = _LOOP_SWEEP_RE.search(text)
    if m:
        proposed = [x for x in (state.get("sweep_proposed") or []) if isinstance(x, dict)]
        if not proposed:
            notes.append('Design loop: aj wrote "Sweep approved: issues", but no sweep page has recorded '
                         "proposed rows, so there is nothing to approve and nothing moved.")
        else:
            k = re.search(r"\bkeep\b(.*)", m.group(1), re.IGNORECASE)
            kept = {int(n) for n in re.findall(r"#(\d+)", k.group(1))} if k else set()
            moved = [x for x in proposed if x.get("number") not in kept]
            left_out = [x for x in proposed if x.get("number") in kept]
            if not isinstance(state.get("sweep"), list):
                state["sweep"] = []
            state["sweep"].extend(moved)
            state.pop("sweep_proposed", None)
            notes.append('Design loop: aj wrote "Sweep approved: issues". Recorded %d sweep row(s) for the close '
                         "guard%s." % (len(moved), ("; kept open at aj's word: " + ", ".join(
                             "#%s" % x.get("number") for x in left_out)) if left_out else ""))
    m = _LOOP_NOTPLANNED_RE.search(text)
    if m:
        pairs = _LOOP_NP_PAIR_RE.findall(m.group(1))
        if not pairs:
            notes.append('Design loop: aj wrote "Close as not planned:", but no "#N replaced by #M" pair '
                         "was found, so nothing was recorded.")
        else:
            if not isinstance(state.get("sweep"), list):
                state["sweep"] = []
            for repo, n, by in pairs:
                state["sweep"].append({"repo": repo, "number": int(n), "action": "not_planned",
                                       "replaced_by": int(by)})
            notes.append('Design loop: aj wrote "Close as not planned:". Recorded %d not-planned close(s) for the '
                         "close guard: %s." % (len(pairs), ", ".join("#%s replaced by #%s" % (n, b)
                                                                      for _r, n, b in pairs)))
    return " ".join(notes)


def _loop_apply(state, text, top):
    carry = _loop_continue_apply(state, text, top)  # #479: first, so "Continue from: x. Build plan approved: y" works
    sweep_note = _loop_sweep_apply(state, text)
    issues_note = _loop_issues_for_apply(state, text, top)
    note = _loop_apply_stage(state, text, top)
    return " ".join(n for n in (carry, sweep_note, issues_note, note) if n)


_LOOP_CONTINUE_RE = re.compile(r"\bcontinue\s+from\s*:\s*([\w./-]+)", re.IGNORECASE)


_LOOP_ISSUES_FOR_RE = re.compile(
    r"\bissues\s+for\s+([^:\n]+?)\s*:\s*((?:[\w.-]+/[\w.-]+)?#\d+(?:[\s,]+(?:and\s+)?(?:[\w.-]+/[\w.-]+)?#\d+)*)",
    re.IGNORECASE)


def _loop_continue_apply(state, text, top):
    """#479 (U1): "Continue from: <branch>" in aj's own message copies that branch's stage file from origin, so
    a handoff keeps the approvals aj already gave. It never invents a stage: a branch with no valid stage file
    moves nothing. Returns a note, or "" when the phrase is absent."""
    m = _LOOP_CONTINUE_RE.search(text)
    if not m:
        return ""
    branch = m.group(1).rstrip(".,")
    if branch.startswith("-") or ".." in branch:
        return 'Design loop: aj wrote "Continue from: %s", which is not a branch name, so nothing moved.' % branch
    rc, _o, err = _ag(top, ["fetch", "--quiet", "origin", branch], check=False, timeout=20)
    if rc != 0:
        return ('Design loop: aj wrote "Continue from: %s", but `git fetch origin %s` failed (%s), so nothing '
                "moved." % (branch, branch, err[:120] or "exit %d" % rc))
    rc, out, _e = _ag(top, ["show", "FETCH_HEAD:.claude/" + LOOP_FILE], check=False)
    try:
        other = json.loads(out) if rc == 0 else None
    except ValueError:
        other = None
    if not isinstance(other, dict) or other.get("stage") not in LOOP_STAGE_NAMES:
        return ('Design loop: aj wrote "Continue from: %s", but that branch has no readable stage file '
                "(.claude/%s), so nothing moved." % (branch, LOOP_FILE))
    state.clear()
    state.update(other)
    state.setdefault("approvals", []).append({"stage": "Continue from", "name": branch, "at": int(time.time())})
    return ('Design loop: aj wrote "Continue from: %s". This branch now has that branch\'s stage: "%s" in %s, with '
            "%d recorded issue(s). Commit and push .claude/%s now, so the next session has it too."
            % (branch, state.get("feature") or "(none)", LOOP_STAGE_NAMES[state["stage"]],
               len(state.get("issues") or []), LOOP_FILE))


def _loop_issues_for_apply(state, text, top):
    """#479 (U1, U2b): "Issues for <feature>: #N #M" in aj's own message records issues that already exist for
    the feature in Plan - made by a script, in another session, or any way the hook didn't see. The feature
    must be the one in Plan. "Build plan approved" still checks each issue's labels on GitHub."""
    m = _LOOP_ISSUES_FOR_RE.search(text)
    if not m:
        return ""
    name, feature = _loop_name(m.group(1)), state.get("feature") or ""
    if state["stage"] != "plan" or not _loop_same(name, feature):  # D6: same name matching as the approvals
        return ('Design loop: aj wrote "Issues for %s:", but %s, so nothing was recorded. Issues attach only to '
                "the feature being planned." % (name, 'the feature in Plan is "%s"' % feature
                                                 if state["stage"] == "plan" else "no feature is in Plan"))
    own, _problem = _origin_slug(top)
    have = {(str(i.get("repo")).lower(), i.get("number")) for i in state.get("issues", []) if isinstance(i, dict)}
    added = []
    for repo, n in re.findall(r"(?:([\w.-]+/[\w.-]+))?#(\d+)", m.group(2)):
        repo = repo or own
        if not repo:
            return ('Design loop: aj wrote "Issues for %s:", but this checkout has no GitHub origin to say which '
                    "repo #%s is in, so nothing was recorded. Write them as owner/repo#N." % (name, n))
        if (repo.lower(), int(n)) not in have:
            state.setdefault("issues", []).append({"repo": repo, "number": int(n), "labelled": True})
            have.add((repo.lower(), int(n)))
            added.append("%s#%s" % (repo, n))
    return ('Design loop: aj wrote "Issues for %s:". Recorded %s for it. "Build plan approved" still checks every '
            "issue's labels on GitHub." % (name, ", ".join(added) or "nothing new"))


def _loop_apply_stage(state, text, top):
    """Move the stage for one message of aj's. Returns a note for the model, or "" when the
    message approves nothing. Mutates state.

    #307: a message can hold more than one approval ("Design approved: X.  Build plan approved: X").
    Each phrase is cut out up to where the next one starts, and the pieces are applied in the order aj
    wrote them (D5), so one refusal no longer hides the approvals beside it."""
    found = sorted((m.start(), order) for rx, order in _LOOP_STAGE_ORDER for m in rx.finditer(text))
    if len(found) < 2:
        return _loop_apply_one(state, text, top)
    pieces = [(order, text[start:found[i + 1][0] if i + 1 < len(found) else len(text)])
              for i, (start, order) in enumerate(found)]
    notes = [_loop_apply_one(state, piece, top) for _order, piece in pieces]  # D5: in the order aj wrote them
    return " ".join(n for n in notes if n)


def _loop_keep_feature(state, feature, stage, any_stage=False):
    """#375: a new design approval replaces `feature`. If it is in build or QA and has recorded issues,
    keep them under state["features"][name.lower()] so its own "QA passed" still has them. A feature in
    design, plan or done, or one with no issues, has nothing to keep. D6: any_stage keeps it in design or
    plan too (a different design name starts a new feature on purpose); a done one is still not kept."""
    issues = [dict(i) for i in state.get("issues", []) if isinstance(i, dict)]
    if feature and (stage in ("build", "qa") or (any_stage and stage != "done")) and issues:
        if not isinstance(state.get("features"), dict):
            state["features"] = {}
        state["features"][feature.lower()] = {"name": feature, "issues": issues, "stage": stage}
        if any_stage and state.get("parent"):  # D6: the kept feature keeps its "Part of #N"
            state["features"][feature.lower()]["parent"] = state["parent"]


def _loop_stored(state, name):
    """The stored feature (#375) a QA message names, or None when it names the current feature,
    nothing stored, or the stage file has no "features" key (an older file)."""
    stash = state.get("features")
    # #403: stored names from before the cleanup may carry junk ("... 1*"), so compare them
    # through _loop_name as well as raw.
    if not isinstance(stash, dict) or name.lower() in {
            (state.get("feature") or "").lower(), _loop_name(state.get("feature") or "").lower()}:
        return None
    entry = stash.get(name.lower())
    if not isinstance(entry, dict):
        entry = next((e for k, e in stash.items()
                      if isinstance(e, dict) and _loop_name(str(k)).lower() == name.lower()), None)
    return entry if isinstance(entry, dict) else None


def _loop_stored_qa(state, entry, verdict, name, top):
    """#375: "QA passed/failed: X" for a feature kept in state["features"]. Uses that feature's own issues
    for the `needs review` check, never touches the current feature's stage or issues. Pass: the entry
    goes to `closable` and out of the map. Fail: it stays, stage "build" with redo true, so a later QA
    message works again once its issues are back to `needs review`."""
    issues = [i for i in entry.get("issues", []) if isinstance(i, dict)]
    labels, src = _loop_labels(state, issues)
    wrong = _loop_wrong(labels, LOOP_REVIEW)
    if wrong or not labels:
        return ('Design loop: aj wrote "QA %s: %s", but that feature is still being built beside the current '
                "one, and QA needs every one of its issues to say `needs review`; these don't: %s. Nothing "
                "moved. Swap their labels when its build is ready for aj, then ask again.%s"
                % (verdict, name, "; ".join(wrong) or "no issues are recorded", " " + src if src else ""))
    unlogged = _loop_unlogged(state, top, "QA " + verdict, name)
    if unlogged:
        return unlogged
    key = (entry.get("name") or name).lower()
    if verdict == "passed":
        if not isinstance(state.get("closable"), list):
            state["closable"] = []
        state["closable"].append({
            "feature": name,
            "issues": [{"repo": i["repo"], "number": i["number"]} for i in issues
                       if i.get("repo") and "number" in i],
            "qa_at": int(time.time()), "qa": "QA passed: " + name, "merged_pr": None})
        state["features"].pop(key, None)
        if not state["features"]:
            state.pop("features")
        tail = (" It is recorded as closable and removed from the kept features. The issues keep `%s` until "
                "aj closes them; never close one." % LOOP_REVIEW)
    else:
        entry["stage"], entry["redo"] = "build", True
        tail = (" It stays in the kept features, back in build: move its issues back to `%s`, fix the changes "
                "aj listed, then swap them to `%s` again for a new QA message." % (LOOP_WORKING, LOOP_REVIEW))
    state.setdefault("approvals", []).append({"stage": "QA " + verdict, "name": name, "at": int(time.time())})
    return ('Design loop: aj wrote "QA %s: %s". That feature moved, not the current one.%s The current feature '
            '"%s" is unchanged: stage %s.' % (verdict, name, tail, state.get("feature") or "(none)",
                                              LOOP_STAGE_NAMES[state["stage"]]))


def _loop_apply_one(state, text, top):
    """Move the stage for one approval phrase (or none). Returns a note for the model, or "" when the
    text approves nothing. Mutates state."""
    stage, feature = state["stage"], state.get("feature") or ""
    approval, issues_note = None, ""
    m = _LOOP_PLAN_RE.search(text)
    if m:
        name = _loop_name(m.group(1))
        if stage == "plan" and not _loop_same(name, feature):
            return ('Design loop: aj wrote "Build plan approved: %s", but the feature in Plan is "%s", so nothing '
                    "moved. Ask aj to approve it by that name, or to approve a design for \"%s\" first."
                    % (name, feature, name))
        if stage != "plan":
            return ('Design loop: aj wrote "Build plan approved: %s", but the stage is %s, not Plan, so '
                    "nothing moved. A build plan is approved after its design." % (name, LOOP_STAGE_NAMES[stage]))
        state["issues"], issues_note = _loop_feature_issues(state, top)
        have = sum(1 for i in state.get("issues", []) if isinstance(i, dict) and i.get("labelled"))
        if have < ISSUES_NEEDED:
            return (issues_note + " " if issues_note else "") + ('Design loop: aj wrote "Build plan approved: %s", but the feature has %d labelled issue(s) '
                    "made since its design was approved, and needs at least %d: one issue for the feature "
                    "and a sub-issue per step, each naming what it depends on, what depends on it and when "
                    "it counts as done, labelled `%s`. Nothing moved. Create them, then ask aj to approve again."
                    % (name, have, ISSUES_NEEDED, ISSUES_LABEL))
        labels, src = _loop_labels(state)
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if wrong:
            return _loop_label_refusal("Build plan approved: %s" % name, LOOP_WORKING, wrong, src, top)
        unlogged = _loop_unlogged(state, top, "Build plan approved", name)
        if unlogged:
            return unlogged
        state["stage"], approval = "build", ("Build plan approved", name)
    else:
        m = _LOOP_DESIGN_RE.search(text)
        if m:
            name = _loop_name(m.group(1))
            # #307: the redo is for the feature QA failed, even when the stored name went stale.
            failed = [a.get("name") or "" for a in state.get("approvals", [])
                      if isinstance(a, dict) and a.get("stage") == "QA failed"]
            redo = state.get("redo") and name.lower() in {feature.lower(), _loop_name(feature).lower(),
                                                       (failed[-1] if failed else "").lower(),
                                                       _loop_name(failed[-1] if failed else "").lower()}
            if redo:
                labels, src = _loop_labels(state)
                wrong = _loop_wrong(labels, LOOP_WORKING)
                if wrong:
                    return _loop_label_refusal("Design approved: %s" % name, LOOP_WORKING, wrong, src, top)
            unlogged = _loop_unlogged(state, top, "Design approved", name)
            if unlogged:
                return unlogged
            same = stage in ("build", "qa") and _loop_same(name, feature)  # D5: an amended design, not a new feature
            state["feature"], state["stage"], approval = name, "plan", ("Design approved", name)
            state["redo"] = False
            if same:
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # the amended build gets a new QA page
            elif not redo:
                _loop_keep_feature(state, feature, stage)  # #375: a feature in build or QA keeps its issues
                if feature and not _loop_same(name, feature) and stage != "done":
                    # D6: a different name starts a new feature on purpose; the old one is kept in any stage
                    _loop_keep_feature(state, feature, stage, any_stage=True)
                    issues_note = ' This starts a new feature; "%s" is kept with its issues.' % feature
                state["issues"] = []
                state.pop("parent", None)  # a new feature's issues name a new "Part of #N"
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: not the next feature's
        else:
            m = _LOOP_QA_RE.search(text)
            if m:
                verdict, name = m.group(1).lower(), _loop_name(m.group(2))
                stored = _loop_stored(state, name)
                if stored is not None:
                    return _loop_stored_qa(state, stored, verdict, name, top)
                if stage in ("build", "qa") and not _loop_same(name, feature):
                    return ('Design loop: aj wrote "QA %s: %s", but the feature in %s is "%s" and no kept feature has '
                            "that name, so nothing moved. Ask aj which feature they meant."
                            % (verdict, name, LOOP_STAGE_NAMES[stage], feature))
                if stage == "build":
                    labels, src = _loop_labels(state)
                    if not _loop_to_qa(state, labels):
                        wrong = _loop_wrong(labels, LOOP_REVIEW)
                        return ('Design loop: aj wrote "QA %s: %s", but QA starts only once every issue of the '
                                "feature says `needs review`, and these don't: %s. Nothing moved. Swap their "
                                "labels when the build is ready for aj, then ask again.%s"
                                % (verdict, name, "; ".join(wrong) or "no issues are recorded",
                                   " " + src if src else ""))
                elif stage != "qa":
                    return ('Design loop: aj wrote "QA %s: %s", but the stage is %s, so nothing moved. QA '
                            "follows a build." % (verdict, name, LOOP_STAGE_NAMES[stage]))
                unlogged = _loop_unlogged(state, top, "QA " + verdict, name)
                if unlogged:
                    return unlogged
                state["stage"] = "done" if verdict == "passed" else "build"  # #504: one message sends a QA fault back
                state["reopened"] = verdict == "failed"
                if verdict == "passed":  # #362: the closable record; "Design approved" never touches it
                    if not isinstance(state.get("closable"), list):
                        state["closable"] = []
                    state["closable"].append({
                        "feature": name,
                        "issues": [{"repo": i["repo"], "number": i["number"]} for i in state.get("issues", [])
                                   if isinstance(i, dict) and i.get("repo") and "number" in i],
                        "qa_at": int(time.time()), "qa": "QA passed: " + name, "merged_pr": None})
                state["redo"] = verdict == "failed"
                if state["redo"]:
                    state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: the redo gets a new page
                approval = ("QA " + verdict, name)
    if approval:
        state["skip"] = False  # D7: a skip belongs to the stage it was typed in
        state.setdefault("approvals", []).append(
            {"stage": approval[0], "name": approval[1], "at": int(time.time())})
        note = 'Design loop: aj wrote "%s: %s". The stage is now %s.' % (
            approval[0], approval[1], LOOP_STAGE_NAMES[state["stage"]])
        if issues_note:
            note += " " + issues_note
        # #479 (U2): the approval is only on this disk until it is pushed, and a session that stops loses it.
        note += (" Save it now, before anything else: `git add .claude/%s && git commit -m \"chore: record %s\" "
                 "&& git push`." % (LOOP_FILE, approval[0].lower()))
        if state.pop("log_ask", False):  # #327
            note += (" The decisions log (%s) has nothing new since the last approval: add this stage's "
                     "entry to it before the turn ends." % LOOP_LOG.replace(os.sep, "/"))
        if state["stage"] == "plan":
            note += (" Code edits stay closed. Planning owes: a systems doc in docs/4-systems/, a GitHub issue "
                     "for the feature and a sub-issue per step, each naming dependencies, dependants and "
                     "done-criteria, labelled `%s` and `%s`." % (ISSUES_LABEL, LOOP_WORKING))
            made = _house_labels_note(top)  # #276: planning is when the labels are first needed
            return note + (" " + made if made else "")
        if state["stage"] == "build":
            note += (" Code edits are open for the approved steps while every issue says `%s`. Hand each "
                     "approved step to @house-rules:builder (one per issue; at most two running) unless aj said "
                     "to build it yourself; helpers build only approved steps and never design or approve. When "
                     "the build is ready for aj, swap every issue's `%s` for `%s`: that starts QA."
                     % (LOOP_WORKING, LOOP_WORKING, LOOP_REVIEW))
        elif approval[0] == "QA failed":
            note += (" aj's words after the feature name are the fix list; the issues and the build plan are kept. "
                     "Move every issue back to `%s` now: code edits open once they are. A changed design still "
                     "needs \"Design approved\"." % LOOP_WORKING)
        elif approval[0] == "QA passed":
            note += (" Code edits stay closed. The issues keep `%s` until aj closes them; never close one. "
                     "The close line (\"Close as completed: #N\") is offered to aj after the feature's pull "
                     "request merges." % LOOP_REVIEW)
        else:
            note += " Code edits stay closed."
        return note
    if _LOOP_SKIP_RE.search(text):
        if stage == "build":
            return ('Design loop: aj wrote "skip design", but the stage is Build, so code edits are already open '
                    "and nothing was stored.")
        state["skip"] = True
        return 'Design loop: aj wrote "skip design", so the next code edit goes through, then the lock is back.'
    if _LOOP_BARE_RE.search(text):
        return ('Design loop: aj\'s message says "approved" but names no stage and feature, so nothing moved. '
                'Ask which they mean; an approval reads like "Design approved: <feature>", '
                '"Build plan approved: <feature>", "QA passed: <feature>" or "QA failed: <feature>".')
    if _LOOP_PICKS_ONLY_RE.search(text):  # #501: picks with no stage words ("Handoff overwrite 1A 2A")
        return ('Design loop: aj\'s message ends in picks but has no stage words ("design approved", "build plan '
                'approved", "QA passed" or "QA failed"), so nothing moved. Ask whether they meant to approve; an '
                'approval reads like "Design approved: <feature> 1A" or "<feature> design approved 1A".')
    return ""


def _loop_locate_prompt(start):
    """(top, git_dir, note) for aj's message. A cloud session's folder often holds the cloned repos
    without being one, so when `start` is outside a repo the folders directly inside it are tried:
    exactly one with a stage file gets the message. None found, or more than one, gives no git_dir and
    a note saying why, so an approval never moves nothing in silence or moves two repos at once."""
    top, git_dir = _issues_locate(start)
    if git_dir:
        return top, git_dir, ""
    found = []
    try:
        names = sorted(os.listdir(start))
    except OSError:
        names = []
    for name in names:
        sub = os.path.join(start, name)
        if os.path.isdir(sub) and os.path.exists(os.path.join(sub, ".git")):
            sub_git = _git_dir(sub)
            if sub_git and os.path.isfile(_loop_path(sub_git)):
                found.append((sub, sub_git))
    if len(found) == 1:
        return found[0][0], found[0][1], ""
    if found:
        return None, None, ("Design loop: this message was sent from %s, which is not a repo, and %d repos "
                            "inside it have a design-loop stage file (%s), so nothing moved: one approval "
                            "must not move two repos. Run the session inside the repo the approval is for."
                            % (start, len(found), ", ".join(os.path.basename(t) for t, _ in found)))
    return None, None, ("Design loop: this message was sent from %s, which is not a repo, and no repo "
                        "directly inside it has a design-loop stage file, so nothing moved." % start)


# #502: a reply button sends only its label ("Approve", or "Approve 1A 2B" when it carries picks).
_LOOP_BUTTON_RE = re.compile(r"(?i)^\s*approve((?:\s+\d+[a-z*])*)\s*$")


def _offered_lines(reply):
    """#502: the clean approval lines a reply offers ("Design approved: X"), without picks or trailing text."""
    out = set()
    for rx, _ in _LOOP_STAGE_ORDER:
        for m in rx.finditer(reply or ""):
            head = m.group(0)[:m.start(1) - m.start(0)]
            name = _loop_name(m.group(1))
            out.add((head + name).strip())
    return sorted(out)


def _asks_aj(reply):
    """#459: True when a reply asks aj something. Conservative: the last paragraph, outside code fences, ends
    with a question mark."""
    text = _MD_FENCED_BLOCK_RE.sub("", reply or "").strip()
    if not text:
        return False
    return text.split("\n\n")[-1].rstrip().endswith("?")


def handover_record_offers(payload, have_reply, reply_text, trace_lines):
    """#502: remember which approval lines this reply offered, so a bare "Approve" button can be matched to one.
    Only a real reply is recorded; the stage file is written only when the list changed."""
    if not have_reply or not _loop_enabled():
        return
    try:
        _top, _gd = _issues_locate(_payload_cwd(payload))
        if not _gd or not os.path.isfile(_loop_path(_gd)):
            return
        _st, _pr = _loop_read(_gd)
        if _pr:
            raise OSError(_pr)
        offered = _offered_lines(reply_text)
        changed = _st.get("offered", []) != offered
        if changed:
            _st["offered"] = offered
        # #459: a reply in Build that asks aj something holds code edits until aj's next message
        if _st.get("stage") == "build" and _asks_aj(reply_text) and not _st.get("held"):
            _st["held"] = True
            changed = True
        if changed:
            _loop_write(_gd, _st)
    except Exception as exc:
        trace_lines.append("house-rules: the offered approval lines could not be recorded (%s: %s), so an "
                           "Approve button may not be matched." % (type(exc).__name__, exc))


def _loop_scope_note(payload):
    """scope's half: read aj's message, move the stage, say what happened. Never raises."""
    if not _loop_enabled():
        return ""
    try:
        m = _PROMPT_VALUE_RE.search(payload or "")
        if not m:
            return ""
        text = json.loads('"%s"' % m.group(1))
        text = _own_words(text)
        if text is None or _is_relayed_prompt(text, payload):
            return ("Design loop: this message is a helper's report or a notification, not aj, "
                    "so it moved nothing.")
        text = _loop_normalise(text)
        if _LOOP_QUOTED_RE.search(text):
            own = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith(">"))
            if not any(rx.search(own) for rx, _ in _LOOP_STAGE_ORDER):
                return ("Design loop: this message only quotes an approval (a `>` line or a quoted message "
                        "from another thread), not aj approving here, so it moved nothing.")
        top, git_dir, missed = _loop_locate_prompt(_payload_cwd(payload))
        if not git_dir:
            return missed if _loop_any_phrase(text) else ""
        state, problem = _loop_read_merged(git_dir)
        if problem:
            return problem
        before = json.dumps(state, sort_keys=True)
        if state.get("held"):
            state["held"] = False  # #459: aj's next real message answers the held question
        b = _LOOP_BUTTON_RE.match(text)
        if b:
            # #502: an Approve button sends only its label; the line it stands for is the one the last reply offered.
            offered = state.get("offered") or []
            if len(offered) != 1:
                return ('Design loop: aj tapped "Approve", but the last reply offered %d approval lines (%s), so '
                        "it is not clear which one, and nothing moved. Ask aj to type the line they mean."
                        % (len(offered), "; ".join(offered) or "none"))
            text = offered[0] + b.group(1)
        note = _loop_apply(state, text, top)
        if json.dumps(state, sort_keys=True) != before:
            _loop_write(git_dir, state)
        return note
    except Exception as exc:
        return "house-rules: the design-loop check hit an error (%s: %s), so this message moved nothing." % (
            type(exc).__name__, exc)


def _loop_helper_note(payload):
    """#232: what a helper is told at start-up about the feature it works inside. "" when the loop
    is off or the helper is not in a repo."""
    if not _loop_enabled():
        return ""
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return ""
    state, problem = _loop_read(git_dir)
    if problem:
        return problem
    issues = ", ".join("#%d" % i["number"] for i in state.get("issues", []) if isinstance(i, dict) and "number" in i)
    return (
        "Design loop: the feature is %s and its stage is %s%s. You build only the steps aj approved in its "
        "build plan; you never design, change the plan, or approve anything - an approval only counts from "
        "aj's own message. Anything unexpected is a question for aj: the main session puts it on a page and "
        "does not answer it. Code edits are refused outside Build." % (
            '"%s"' % state["feature"] if state.get("feature") else "not started",
            LOOP_STAGE_NAMES[state["stage"]],
            "; its issues are %s" % issues if issues else ""))


def _loop_stop_line(payload):
    """#238, handover: (line or None, problem or None) - name every issue whose label doesn't fit the
    stage. Quiet when there is no feature with issues, or every label fits."""
    if not _loop_enabled():
        return None, None
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return None, None
    state, problem = _loop_read_merged(git_dir)
    if problem:
        return None, problem
    stage = state["stage"]
    if stage == "done" or (stage == "design" and not state.get("redo")) or not state.get("issues"):
        return None, None
    labels, src = _loop_labels(state)
    reopened = state.get("reopened")
    if _loop_to_qa(state, labels):
        _loop_write(git_dir, state)
        return "House rules, design loop:" + _LOOP_QA_NOTE, src or None
    if state.get("reopened") != reopened:  # #504: the issues are back at in progress
        _loop_write(git_dir, state)
    want = LOOP_REVIEW if stage == "qa" else LOOP_WORKING
    wrong = _loop_wrong(labels, want)
    if not wrong:
        if state.pop("label_said", None) is not None:
            _loop_write(git_dir, state)
        return None, src or None
    said = hashlib.sha1("; ".join(wrong).encode()).hexdigest()[:12]
    if state.get("label_said") == said:  # #273: said once per set of wrong labels
        return None, src or None
    state["label_said"] = said
    _loop_write(git_dir, state)
    return ("House rules, design loop: \"%s\" is in %s, so every issue should be labelled `%s`, and these "
            "are not: %s. Fix the labels before this turn ends.%s"
            % (state.get("feature") or "", LOOP_STAGE_NAMES[stage], want, "; ".join(wrong),
               " Code edits are refused until they are." if stage == "build" else "")), src or None


def _loop_gate(payload):
    """(deny reason or None, problem or None): code edits only in Build, or once after skip design."""
    git_dir, problem = _gated_edit(payload, "design-loop lock")
    if not problem:
        refusal = _loop_file_refusal(payload)
        if refusal:
            return refusal, None
    script_paths, script_unreadable, script = [], False, False
    if not git_dir and not problem:
        # #262: a Bash/PowerShell script write of a source file is held to the same lock.
        git_dir, problem, script_paths, script_unreadable = _gated_script_write(payload)
        script = bool(git_dir)
    if not git_dir:
        return None, problem
    state, problem = _loop_read_merged(git_dir)
    if problem:
        return None, problem
    if state["stage"] == "build" or state.get("skip"):
        hold = _loop_stale_hold(git_dir, state)  # D9: an older branch's stage never reopens code on its own
        if hold:
            return hold, None
    if script and state["stage"] == "build":
        return None, None  # Build: nothing changes for shell commands
    if state["stage"] == "build" and state.get("held"):
        return ("House rules, design loop: the last reply asked aj a question, so code edits wait for their "
                "answer."), None
    if state["stage"] == "build":
        labels, src = _loop_labels(state, record=False)
        if src:  # D9: GitHub could not be read, and the record of an old branch is not evidence
            return ("House rules, design loop: code edits in Build need every issue of \"%s\" labelled `%s`, but "
                    "this hook could not read GitHub (%s), so the edit is refused. It will work once gh can read the issues."
                    % (state.get("feature") or "", LOOP_WORKING, src)), None
        reopened = state.get("reopened")
        if _loop_to_qa(state, labels):
            _loop_write(git_dir, state)
            return "House rules, design loop:" + _LOOP_QA_NOTE, None
        if state.get("reopened") != reopened:  # #504: the issues are back at in progress
            _loop_write(git_dir, state)
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if not wrong:
            return None, src or None
        return ("House rules, design loop: code edits in Build need every issue of \"%s\" labelled `%s`, and "
                "these are not: %s. Fix the labels, then edit again.%s"
                % (state.get("feature") or "", LOOP_WORKING, "; ".join(wrong), " " + src if src else "")), None
    if state.get("skip"):
        state["skip"] = False
        _loop_write(git_dir, state)
        return None, None
    feature = state.get("feature") or ""
    if script:
        # #309 (incident 4 of #303): a shell command is reported, never refused, until the restructure. The
        # refusal stopped docs and .claude/ writes made from the shell, which are meant to stay open.
        what = ("a file it can't name" if script_unreadable and not script_paths
                else ", ".join(script_paths) or "a source file")
        return None, ("house-rules design loop (report only, #309): code is locked in the %s stage, and this "
                      "shell command writes %s. It was let through; the shell-write refusal is switched off "
                      "until the restructure." % (LOOP_STAGE_NAMES[state["stage"]], what))
    return (
        "House rules, design loop: code edits are closed in the %s stage%s. They open when aj types "
        "\"Build plan approved: <feature>\" after approving a design, or \"skip design\" for one small "
        "change. docs/ pages, .claude/ files other than settings, and .md, .txt and .csv files stay open, so write the design or plan as a page "
        "now. To switch this off: HOUSE_RULES_LOOP=off." % (
            LOOP_STAGE_NAMES[state["stage"]], ' of "%s"' % feature if feature else ""),
        None,
    )


_GH_ISSUE_CREATE_RE = re.compile(_GH_PREFIX + r"issue\s+create\b")
# #479 (U2b): the REST form, `gh api repos/O/R/issues -f title=...`, and Python's ['gh', 'issue', 'create'].
_GH_API_ISSUE_CREATE_RE = re.compile(
    _GH_PREFIX + r"api\b(?=[^\n]*\brepos/[\w.-]+/[\w.-]+/issues(?![/\w]))(?=[^\n]*(?:-f|-F|--field|--raw-field)"
    r"[=\s]+[\"']?title=)", re.IGNORECASE)
_PY_GH_ISSUE_CREATE_RE = re.compile(r"""['"]gh['"]\s*,\s*['"]issue['"]\s*,\s*['"]create['"]""")


_GH_PR_CREATE_RE = re.compile(_GH_PREFIX + r"pr\s+create\b")


_GH_ISSUE_CLOSE_RES = (
    re.compile(_GH_PREFIX + r"issue\s+close\b"),
    re.compile(_GH_PREFIX + r"issue\s+edit\b[^\n;&|]*--state[=\s]+[\"']?closed", re.IGNORECASE),
    re.compile(_GH_PREFIX + r"api\b(?=[^\n]*(?:-X|--method)[=\s]+[\"']?PATCH)(?=[^\n]*issues/\d+)"
               r"(?=[^\n]*state\W{0,4}closed)", re.IGNORECASE),
)


_ISSUE_URL_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


_GITHUB_ISSUE_WRITE_RE = re.compile(r"^mcp__(github|GitHub)__issue_write$")


def _created_issue(data):
    """(found, labelled, how) for a tool call that created a GitHub issue - a terminal
    `gh issue create` or the GitHub tool's issue_write with method create (#231) - or None for any
    other call. `found` lists (repo, number) pairs from the response; `labelled` says whether the
    project label was set."""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    tool = data.get("tool_name") or ""
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if not (_GH_ISSUE_CREATE_RE.search(cmd) or _GH_API_ISSUE_CREATE_RE.search(cmd)
                or _PY_GH_ISSUE_CREATE_RE.search(cmd)):
            return None
        how = "`gh issue create`"
        if _GH_ISSUE_CREATE_RE.search(cmd):
            labels = _gh_label_flags(cmd)["add"]  # D11: the label flags, not the title
        else:  # adapted: the gh api and python forms (step 5) carry no --label flag, so they keep the text search
            labels = [l for l in (ISSUES_LABEL, ISSUES_LABEL_OLD) if l.lower() in cmd.lower()]
    elif _GITHUB_ISSUE_WRITE_RE.match(tool) and str(ti.get("method", "")).lower() == "create":
        labels = [str(l) for l in ti["labels"]] if isinstance(ti.get("labels"), list) else []
        how = "GitHub tool issue_write"
    else:
        return None
    resp = data.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp)
    found = list(dict.fromkeys(_ISSUE_URL_RE.findall(text)))
    labelled = bool({l.lower() for l in labels} & {ISSUES_LABEL.lower(), ISSUES_LABEL_OLD.lower()})
    return found, labelled, how


_BODY_FILE_RE = re.compile(r"--body-file(?:=|\s+)(\"[^\"]*\"|'[^']*'|[^\s\"']+)|-F\s+(\"[^\"]*\"|'[^']*'|[^\s\"']+)")


def _issue_body(data):
    """The text an issue-creating call carries as its body: the GitHub tool's `body`, or the whole Bash command
    (which holds --body / a heredoc / -f body=...) plus the contents of a --body-file it names, when readable."""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if data.get("tool_name") != "Bash":
        return str(ti.get("body") or "")
    cmd = ti.get("command") or ""
    text = cmd
    for m in _BODY_FILE_RE.finditer(cmd):
        path = (m.group(1) or m.group(2)).strip("\"'")
        try:
            base = data.get("cwd") or os.getcwd()
            with open(os.path.join(base, path), "r", encoding="utf-8") as f:
                text += "\n" + f.read()
        except OSError:
            pass  # unreadable: the command text alone is searched, so a missing "Part of" shows in the note
    return text


_GITHUB_SLUG_RE = re.compile(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?\s*$", re.IGNORECASE)


def _origin_slug(top):
    """(slug, problem): the "owner/repo" of the checkout's GitHub origin remote, or "" when it has none,
    and why it couldn't be read ("" when it could)."""
    import subprocess
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=top, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=3).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return "", "house-rules: could not read this checkout's git remote (%s)" % exc
    m = _GITHUB_SLUG_RE.search(url.strip())
    return (m.group(1) if m else ""), ""


_PART_OF_RE = re.compile(r"(?i)\bpart of #(\d+)\b")


def _loop_record_issues(git_dir, found, labelled, top=None, body=""):
    """#231: issues made while a feature is in Plan count toward its build-plan approval.

    #308: only issues made in the repo that owns the stage file count. In an Unblocked session, two issues
    opened in another repo were counted as Unblocked's, and the label check then blocked the turn seven
    times. A checkout with no GitHub origin can't say which repo it is, so its issues count as before."""
    if not _loop_enabled() or not found:
        return []
    state, problem = _loop_read(git_dir)
    if problem:
        return [problem]
    if state["stage"] != "plan":
        return []
    own, slug_problem = _origin_slug(top) if top else ("", "")
    own = own.lower()
    notes = [slug_problem + ", so every new issue counts toward this feature."] if slug_problem else []
    part = _PART_OF_RE.search(body or "")
    parent = state.get("parent")
    if not part or (parent is not None and int(part.group(1)) != int(parent)):
        # #475: an issue for a separate feature is not this feature's. The feature issue itself is made
        # first, with no "Part of" line; it enters the list as `parent` once a step issue names it.
        why = 'names no "Part of #N"' if not part else 'names "Part of #%s", not #%s' % (part.group(1), parent)
        expected = "" if parent is not None else " If this is the feature issue itself, that is expected."
        return notes + ['Design loop: issue #%s %s, so it is not counted as a step of "%s".%s'
                        % (found[0][1], why, state.get("feature") or "this feature", expected)]
    if parent is None:
        state["parent"] = int(part.group(1))
    for repo, number in found:
        if own and str(repo).lower() != own:
            notes.append("Design loop: issue %s#%s was made in another repo, so it doesn't count toward \"%s\" "
                         "here (this checkout is %s)." % (repo, number, state.get("feature") or "this feature", own))
            continue
        state.setdefault("issues", []).append({"repo": repo, "number": int(number), "labelled": labelled})
    _loop_write(git_dir, state)
    return notes


_GH_ISSUE_EDIT_RE = re.compile(_GH_PREFIX + r"issue\s+edit\s+(\d+)\b([^\n;&|]*)")


_GH_LABEL_FLAG_RE = re.compile(r"(?:--(add-label|remove-label|label)|-(l))(?:=|\s+)(\"[^\"]*\"|'[^']*'|[^\s\"']+)")


def _gh_label_flags(cmd):
    """{"add": [...], "remove": [...]} from a gh command's label flags (--label and -l count as add)."""
    out = {"add": [], "remove": []}
    for long_flag, _short, value in _GH_LABEL_FLAG_RE.findall(cmd):
        names = [v.strip() for v in value.strip("\"'").split(",") if v.strip()]
        out["remove" if long_flag == "remove-label" else "add"].extend(names)
    return out


_GH_API_LABELS_RE = re.compile(_GH_PREFIX + r"api\s+([^\n;&|]*?)\brepos/([\w.-]+/[\w.-]+)/issues/(\d+)/labels(?:/([^\s\"']+))?([^\n;&|]*)")


_GH_API_METHOD_RE = re.compile(r"(?:-X|--method)(?:=|\s+)[\"']?(\w+)", re.I)


_GH_API_LABEL_FIELD_RE = re.compile(r"(?:-f|-F|--raw-field|--field)(?:=|\s+)(?:\"labels\[\]=([^\"]*)\"|'labels\[\]=([^']*)'|labels\[\]=(\S+))")


_GH_API_FAILED_RE = re.compile(r"\(HTTP [45]\d\d\)|^gh: |\"status\":\s*\"[45]\d\d\"", re.M)


def _gh_api_worked(resp):
    """D12: proof a `gh api` labels call worked: exit code 0, or, where none is reported, the JSON list of labels
    the endpoint answers with. A sign-in prompt or any other text is not proof."""
    if isinstance(resp, list):
        return True
    if isinstance(resp, str):
        resp = {"stdout": resp}
    if not isinstance(resp, dict):
        return False
    code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
    if code is not None:
        return code == 0
    try:
        parsed = json.loads(resp.get("stdout") or "")
    except ValueError:
        parsed = None  # not JSON (a sign-in prompt or an error): proves nothing, so the call is not recorded
    return isinstance(parsed, list)


def _gh_api_label_change(cmd, text, resp=None):
    """#278: (repo, number, None, add, remove) for a succeeded `gh api repos/O/R/issues/N/labels` call (the REST
    form that works in cloud sessions), else None. Repo and number come from the path, not the response."""
    m = _GH_API_LABELS_RE.search(cmd)
    if not m or _GH_API_FAILED_RE.search(text) or not _gh_api_worked(resp):
        return None
    pre, repo, number, name, post = m.groups()
    method = (_GH_API_METHOD_RE.search(pre + " " + post) or [None, "POST" if "-f" in post or "-F" in post or "field" in post else "GET"])[1].upper()
    if method == "DELETE" and name:
        return (repo, int(number), None, [], [urllib.parse.unquote(name)])
    if method == "POST" and not name:
        adds = [(x or y or z).strip("\"'") for x, y, z in _GH_API_LABEL_FIELD_RE.findall(pre + " " + post)]
        if adds:
            return (repo, int(number), None, adds, [])
    return None


def _label_changes(data):
    """#236: [(repo, number, set_to or None, add, remove)] for a tool call that set issue labels and
    succeeded - the GitHub tool's issue_write, or `gh issue create` / `gh issue edit`."""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    tool = data.get("tool_name") or ""
    resp = data.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp)
    urls = list(dict.fromkeys(_ISSUE_URL_RE.findall(text)))
    if _GITHUB_ISSUE_WRITE_RE.match(tool) and isinstance(ti.get("labels"), list):
        labels = [str(l) for l in ti["labels"]]
        if str(ti.get("method", "")).lower() == "create":
            return [(repo, int(n), labels, [], []) for repo, n in urls]
        number = ti.get("issue_number")
        repo = "%s/%s" % (ti.get("owner"), ti.get("repo"))
        if number and any(r.lower() == repo.lower() and int(n) == int(number) for r, n in urls):
            return [(repo, int(number), labels, [], [])]
        return []
    if tool != "Bash":
        return []
    cmd = ti.get("command") or ""
    if _GH_ISSUE_CREATE_RE.search(cmd):
        flags = _gh_label_flags(cmd)
        return [(repo, int(n), flags["add"], [], []) for repo, n in urls]
    api = _gh_api_label_change(cmd, text, resp)
    if api:
        return [api]
    m = _GH_ISSUE_EDIT_RE.search(cmd)
    if m:
        flags = _gh_label_flags(m.group(2))
        if flags["add"] or flags["remove"]:
            return [(repo, int(n), None, flags["add"], flags["remove"]) for repo, n in urls if int(n) == int(m.group(1))]
    return []


def _pr_opened(data):
    """True for a successful pull request creation: the GitHub tool or `gh pr create`, with a PR URL in the response."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if not (_GITHUB_PR_CREATE_RE.match(tool) or (tool == "Bash" and _GH_PR_CREATE_RE.search(ti.get("command") or ""))):
        return False
    resp = data.get("tool_response")
    return bool(_PR_URL_RE.search(resp if isinstance(resp, str) else json.dumps(resp)))


def _loop_record_labels(payload):
    """PostToolUse: record label changes for the GitHub-read fallback, and move Build to QA once every
    issue says needs review. Returns notes. Never raises."""
    if not _loop_enabled():
        return []
    try:
        data = json.loads(payload)
        changes = _label_changes(data) if isinstance(data, dict) else []
        pr = isinstance(data, dict) and _pr_opened(data)
        if not changes and not pr:
            return []
        _, git_dir = _issues_locate(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return []
        state, problem = _loop_read(git_dir)
        if problem:
            return [problem]
        recorded = state.setdefault("labels", {})
        for repo, number, set_to, add, remove in changes:
            key = _loop_key(repo, number)
            now = list(set_to) if set_to is not None else list(recorded.get(key) or [])
            now = [l for l in now if l.lower() not in {r.lower() for r in remove}]
            now += [a for a in add if a.lower() not in {l.lower() for l in now}]
            recorded[key] = now
        if pr:  # A2: what this pull request links, so its merge stamps only those issues
            resp = data.get("tool_response")
            url = re.search(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)", resp if isinstance(resp, str) else json.dumps(resp))
            ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
            body = ti.get("body") if isinstance(ti.get("body"), str) else ti.get("command") or ""
            fm = _PR_BODY_FILE_RE.search(body) if "command" in ti else None
            if fm and fm.group(1).strip("\"'") != "-":
                try:
                    body = _read_text(os.path.join(_payload_cwd(payload), fm.group(1).strip("\"'")))
                except OSError:
                    pass  # the guard already read this file before the command ran; refs from the command text stand
            if url:
                state.setdefault("pr_refs", {})["%s#%s" % (url.group(1).lower(), url.group(2))] = _pr_refs(body, url.group(1))
        notes = []
        if pr and state["stage"] == "build":
            state["stage"] = "qa"
            notes.append("Design loop:" + _LOOP_PR_NOTE)
        elif state["stage"] == "build" and changes:
            labels, src = _loop_labels(state)
            if _loop_to_qa(state, labels):
                notes.append("Design loop:" + _LOOP_QA_NOTE + (" " + src if src else ""))
        _loop_write(git_dir, state)
        return notes
    except Exception as exc:
        return ["house-rules: could not record an issue label change for the design loop (%s: %s)."
                % (type(exc).__name__, exc)]


def _issues_record(payload):
    """PostToolUse Bash or GitHub tool: record a created issue in the issue-gate and design-loop
    state. Returns a list of note strings (empty when nothing applies). Never raises."""
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            return []
        hit = _created_issue(data)
        if hit is None:
            return []
        found, labelled, how = hit
        top, git_dir = _issues_locate(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return []
        loop_notes = _loop_record_issues(git_dir, found, labelled, top, _issue_body(data))
        if not _issues_enabled():
            return loop_notes
        state, problem = _issues_read(git_dir)
        if problem:
            return loop_notes + [problem]
        if not state or not state.get("needs_issues"):
            return loop_notes
        if not found:
            return loop_notes + ["house-rules: a %s ran but no issue URL was in its output, so it "
                                 "was not counted toward the issue gate." % how]
        created = state.setdefault("created", [])
        for repo, number in found:
            created.append({"repo": repo, "number": int(number), "labelled": labelled})
        notes = []
        if not labelled:
            notes.append("house-rules: issue #%s was created without the `%s` label, so it does not "
                         "count toward the issue gate and Focus Deck will ignore it. Add it with `gh "
                         "api repos/%s/issues/%s/labels -f \"labels[]=%s\"` and create the next issues with it."
                         % (found[0][1], ISSUES_LABEL, found[0][0], found[0][1], ISSUES_LABEL))
        have = _labelled_count(state)
        if have >= ISSUES_NEEDED:
            state["needs_issues"] = False
            notes.append("house-rules: %d labelled issues recorded, so source edits are unblocked." % have)
        _issues_write(git_dir, state)
        return loop_notes + notes
    except Exception as exc:
        return ["house-rules: could not record a created issue in the issue gate (%s: %s)."
                % (type(exc).__name__, exc)]


def _issues_stop_line(payload):
    """Handover: (line or None, problem or None) - the gate is still closed at Stop."""
    if not _issues_enabled():
        return None, None
    top, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return None, None
    state, problem = _issues_read(git_dir)
    if problem:
        return None, problem
    if state and state.get("needs_issues"):
        return ("House rules, plans become issues: the approved %s-step plan still has no parent and "
                "child issues recorded (%d of %d), so source edits stay blocked. Create them with `gh "
                "issue create` and the `%s` label, or tell the user why not."
                % (state.get("plan_steps", "multi"), _labelled_count(state), ISSUES_NEEDED, ISSUES_LABEL)), None
    return None, None


# gh pr create / gh issue close, checked in guard. Both work from the decoded command text.
_PR_BODY_FLAG_RE = re.compile(r"(?:--body|(?<![\w-])-b)(?:=|\s+|(?=[\"']))")


_PR_LINK_RE = re.compile(r"\b(?:Refs|Part of)\s+(?:[\w.-]+/[\w.-]+)?#\d+", re.IGNORECASE)


_PR_NO_ISSUE_RE = re.compile(r"(?:^|\n|[\"']|\\n)\s*No-issue:\s*\S", re.IGNORECASE)


_PR_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?:[\w.-]+/[\w.-]+)?#\d+|https?://github\.com/[\w.-]+/[\w.-]+/issues/\d+)",
    re.IGNORECASE,
)


PR_ASK_NOTE = (
    "House rules, pull requests link issues without closing them: say `Refs #N` (or `Part of #N`, "
    "or a line `No-issue: <reason>`) in the body, and never a closing word, because GitHub would "
    "close the issue at merge, before the user has tested."
)


def _author_guard(subject, payload):
    """None unless a git commit would be authored as Claude, else ("deny", reason, None)."""
    if not _attribution_enabled():
        return None
    cmd = _decoded_command(subject)
    if not _GIT_COMMIT_RE.search(cmd):
        return None
    try:
        who = _effective_author(cmd, _command_dir(payload)[0])  # the repo a cd / -C moves to
    except Exception: return None  # unreadable identity: let the commit through, as for an unreadable body file
    if who is None or not _is_claude_identity(*who):
        return None
    return ("deny", "House rules, credit Edens Agent: this commit would be authored as `%s <%s>`, "
            "which signs it as Claude. Set the agent's identity in this repo and retry: `%s`. "
            "HOUSE_RULES_ATTRIBUTION=off disables this check."
            % (who[0] or "?", who[1] or "?", AGENT_IDENTITY_FIX), None)


def _guardgithub_issue_checks(payload, raw):
    """The two checks event_guardgithub used to run first (the safe git part now loops over this
    through core.GITHUB_WRITE_HOOKS): True when the call was handled and answered."""
    # #248: an issue made with the GitHub tool needs its three sections, like one made with gh.
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if (_GITHUB_ISSUE_WRITE_RE.match(str(payload.get("tool_name") or ""))
            and str(ti.get("method", "")).lower() == "create" and _issues_enabled() and _clear_writing_enabled()):
        if clarity is None:
            emit({"systemMessage": CLARITY_ERROR + " The issue was NOT checked for its sections."})
        else:
            missing = clarity.missing_issue_sections(str(ti.get("body") or ""))
            if missing:
                emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                      "permissionDecisionReason": ISSUE_SECTIONS_DENY % ", ".join("\"%s\"" % m for m in missing)}})
                return True
    # #363: a close through the GitHub tool goes through the same close guard as gh.
    if (_GITHUB_ISSUE_WRITE_RE.match(str(payload.get("tool_name") or "")) and _issues_enabled()
            and str(ti.get("method", "")).lower() == "update" and str(ti.get("state", "")).lower() == "closed"):
        num = ti.get("issue_number")
        try:
            num = int(num)
        except (TypeError, ValueError):
            num = None
        repo = "%s/%s" % (ti.get("owner"), ti.get("repo")) if ti.get("owner") and ti.get("repo") else ""
        ok, text, ctx = _close_decide(repo, num, str(ti.get("state_reason") or "").lower(), _payload_cwd(raw))
        if ok:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                         "additionalContext": ctx}})
        else:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": text}})
        return True
    return False


# --- #363: the close guard. A close goes through only on recorded evidence or an approved list. ---
CLOSE_COMMENT_NOTE = (
    "House rules, this close is allowed: %s. Before or right after it, comment on issue #%d with that "
    "evidence (the QA message and the merged pull request link, or the sweep approval and the replacing "
    "issue), add the label `AjsAgent completed this` (`gh api repos/%s/issues/%d/labels -f "
    "\"labels[]=AjsAgent completed this\"`) and remove `in progress` (`gh api -X DELETE "
    "repos/%s/issues/%d/labels/in%%20progress`)."
)


def _close_repo_match(a, b):
    return not a or not b or a.lower() == b.lower()


def _close_check(repo, number, reason, state):
    """(allowed, reason_text) for closing issue `number` of `repo` with state reason `reason`
    ("completed", "not_planned" or "" for none), from the design-loop `state` (#363)."""
    reason = (reason or "completed").strip().lower().replace(" ", "_")
    if not isinstance(state, dict):
        state = {}
    sweep = [x for x in (state.get("sweep") or []) if isinstance(x, dict) and x.get("number") == number
             and _close_repo_match(repo, x.get("repo", ""))]
    for x in sweep:
        if x.get("action") == reason:
            if reason == "not_planned" and x.get("replaced_by"):
                return True, "#%d is on the approved sweep list as not planned, replaced by #%s" % (number, x["replaced_by"])
            return True, "#%d is on the approved sweep list as %s" % (number, reason.replace("_", " "))
    holders = []
    for e in state.get("closable") or []:
        if isinstance(e, dict) and any(isinstance(i, dict) and i.get("number") == number
                                       and _close_repo_match(repo, i.get("repo", "")) for i in e.get("issues") or []):
            holders.append(e)
    ready = [e for e in holders if e.get("merged_pr")]
    if ready and reason == "completed":
        e = ready[0]
        pr = e["merged_pr"]
        return True, "%s, and pull request %s#%s was merged since" % (
            e.get("qa") or "QA passed", pr.get("repo") or repo or "?", pr.get("number"))
    if reason != "completed":
        return False, ("a not-planned close needs an approved sweep or a named list, and #%d is not on one "
                       "with the action not_planned" % number)
    if holders:
        return False, "#%d's feature passed QA but no merged pull request is recorded since" % number
    if sweep:
        return False, "#%d is on the approved sweep list with a different action than completed" % number
    return False, ("no QA pass is recorded for a feature that holds #%d, and it is on no approved sweep or "
                   "named list" % number)


def _close_forget(git_dir, repo, number):
    """Take `number` out of its closable entry (the entry goes once empty) and out of sweep."""
    state, problem = _loop_read(git_dir)
    if problem or not isinstance(state, dict):
        return
    hit = lambda i: isinstance(i, dict) and i.get("number") == number and _close_repo_match(repo, i.get("repo", ""))
    changed = False
    if isinstance(state.get("closable"), list):
        keep = []
        for e in state["closable"]:
            if isinstance(e, dict) and any(hit(i) for i in e.get("issues") or []):
                e["issues"] = [i for i in e["issues"] if not hit(i)]
                changed = True
                if not e["issues"]:
                    continue
            keep.append(e)
        state["closable"] = keep
    if isinstance(state.get("sweep"), list):
        n = len(state["sweep"])
        state["sweep"] = [x for x in state["sweep"] if not hit(x)]
        changed = changed or len(state["sweep"]) != n
    if changed:
        _loop_write(git_dir, state)


def _close_decide(repo, number, reason, cwd):
    """(allowed, text, context). Reads the stage file and changes nothing; the evidence is
    removed after a successful close, in event_closablemerge."""
    if number is None:
        return False, ("House rules, close guard: I could not tell which issue this close is for (no issue "
                       "number found), so it is refused. Name the issue number."), None
    _, git_dir = _issues_locate(cwd)
    if not git_dir:
        return False, ("House rules, close guard: could not find the project's stage file from %s, so the "
                       "close of #%d is refused." % (cwd, number)), None
    state, problem = _loop_read(git_dir)
    if problem:
        return False, "%s The close of #%d is refused." % (problem, number), None
    ok, why = _close_check(repo, number, reason, state)
    if not ok:
        return False, "House rules, close guard: refused to close #%d: %s." % (number, why), None
    slug = repo or "<owner>/<repo>"
    return True, why, CLOSE_COMMENT_NOTE % (why, number, slug, number, slug, number)


def _close_gh_parse(cmd):
    """(repo, number, reason) from a gh close command; number None when it cannot be read."""
    repo = ""
    m = re.search(r"(?:-R|--repo)[ =]+[\"']?([\w.-]+/[\w.-]+)", cmd)
    if m:
        repo = m.group(1)
    um = _ISSUE_URL_RE.search(cmd)
    number = None
    if um:
        repo, number = um.group(1), int(um.group(2))
    else:
        am = re.search(r"issues/(\d+)", cmd)
        if am:
            number = int(am.group(1))
            rm = re.search(r"repos/([\w.-]+/[\w.-]+)/issues", cmd)
            if rm:
                repo = rm.group(1)
        else:
            im = re.search(r"issue\s+(?:close|edit)\s+(?:(?:-R|--repo)[ =]+\S+\s+)?#?(\d+)(?![\w/-])", cmd)
            if im:
                number = int(im.group(1))
    reason = ""
    rm = re.search(r"(?:--reason|-r)[ =]+[\"']?(not[ _]planned|completed|duplicate)", cmd, re.IGNORECASE)
    if not rm:
        rm = re.search(r"state_reason[=\s:\"']+(not[ _]planned|completed|duplicate)", cmd, re.IGNORECASE)
    if rm:
        reason = rm.group(1).lower().replace(" ", "_")
    return repo, number, reason


def _close_gh_decision(cmd, payload):
    repo, number, reason = _close_gh_parse(cmd)
    ok, text, ctx = _close_decide(repo, number, reason, _payload_cwd(payload))
    return ("allow", text, ctx) if ok else ("deny", text, None)


def _issues_guard(subject, payload):
    """None when the issue rules have nothing to say about this command, else
    (kind, reason, context) with kind "deny" or "ask"."""
    if not _issues_enabled():
        return None
    cmd = _decoded_command(subject)
    if _GH_PR_CREATE_RE.search(cmd):
        body = cmd
        fm = _PR_BODY_FILE_RE.search(cmd)
        if fm:
            name = fm.group(1).strip("\"'")
            if name == "-":
                return ("ask", "House rules: `gh pr create --body-file -` reads the body from stdin, so I "
                        "could not check it for `Refs #N` and closing words. " + PR_ASK_NOTE, PR_ASK_NOTE)
            path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError as exc:
                return ("ask", "House rules: could not read the PR body file %s (%s), so I could not check "
                        "it for `Refs #N` and closing words. %s" % (name, exc, PR_ASK_NOTE), PR_ASK_NOTE)
        elif not _PR_BODY_FLAG_RE.search(cmd):
            return ("ask", "House rules: this `gh pr create` has no --body or --body-file (--web, --fill "
                    "or interactive), so I cannot check it for `Refs #N` and closing words. " + PR_ASK_NOTE,
                    PR_ASK_NOTE)
        closing = _PR_CLOSING_RE.search(body)
        if closing:
            return ("deny", "House rules, pull requests link issues without closing them: the body says "
                    "`%s`, and GitHub would close that issue when the PR merges, before the user has "
                    "tested. Reword it as `Refs #N` (the user closes the issue after testing)."
                    % closing.group(0), None)
        if not (_PR_LINK_RE.search(body) or _PR_NO_ISSUE_RE.search(body)):
            return ("deny", "House rules, pull requests link issues without closing them: the body needs "
                    "`Refs #N`, `Refs owner/repo#N` or `Part of #N`, or a line `No-issue: <reason>`. "
                    "Add it and run the command again.", None)
        bm = re.search(r"(?:--base|(?<![\w-])-B)(?:=|\s+)[\"']?([^\s\"']+)", cmd)
        note = core.pr_changelog_note(_command_dir(payload)[0], bm.group(1) if bm else "")
        return ("note", "", note) if note else None  # #509: a reminder, never a decision
    if _GH_ISSUE_CREATE_RE.search(cmd) and _clear_writing_enabled() and clarity is not None:
        body = cmd
        fm = _PR_BODY_FILE_RE.search(cmd)
        if fm and fm.group(1).strip("\"'") != "-":
            name = fm.group(1).strip("\"'")
            path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError as exc:
                return ("ask", "House rules: could not read the issue body file %s (%s), so I could not "
                        "check it for its three sections." % (name, exc), None)
        missing = clarity.missing_issue_sections(body)
        if missing:
            return ("deny", ISSUE_SECTIONS_DENY % ", ".join("\"%s\"" % m for m in missing), None)
    if any(r.search(cmd) for r in _GH_ISSUE_CLOSE_RES):
        return _close_gh_decision(cmd, payload)
    return None


# #248: an issue says what it depends on, what depends on it, and when it's done.
ISSUE_SECTIONS_DENY = (
    "House rules, write it so nothing is left to guess: this issue is missing %s. Every issue needs "
    "\"Depends on\", \"Depended on by\" and \"Done when\" sections (\"Nothing\" is a fine answer), so "
    "a blocker shows up as an unfinished dependency and done means something. Add them and create it "
    "again. HOUSE_RULES_CLEAR_WRITING=off turns this off."
)


def _open_issues_text(cwd):
    """(text or "", problem or None) for the SessionStart open-issue list. Silent ("", None)
    when there is nothing to list against: no gh, or no GitHub remote."""
    import subprocess
    import time
    gh = shutil.which("gh")
    if not gh:
        return "", None
    top, git_dir = _issues_locate(cwd)
    if not top or not git_dir:
        return "", None
    try:
        remote = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=top,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=3).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return "", "git remote lookup failed: %s" % exc
    if "github.com" not in remote:
        return "", None
    cache = os.path.join(git_dir, "house-rules-issues-cache.json")
    try:
        with open(cache, "r", encoding="utf-8") as f:
            c = json.load(f)
        if time.time() - float(c["ts"]) < 60:
            return c["text"], None
    except (OSError, ValueError, KeyError, TypeError):
        pass  # no usable cache: fetch fresh below
    try:
        proc = subprocess.run([gh, "issue", "list", "--state", "open", "--limit", "10", "--json",
                               "number,title"], cwd=top, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=5)
    except subprocess.TimeoutExpired:
        return "", "timed out after 5 s"
    except OSError as exc:
        return "", "could not run gh: %s" % exc
    if proc.returncode != 0:
        first = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or ["exit %d" % proc.returncode])[0]
        return "", first[:120]
    try:
        items = json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError as exc:
        return "", "unreadable gh output: %s" % exc
    if not items:
        text = "Open issues: none."
    else:
        text = "Open issues (newest first):\n" + "\n".join(
            "- #%s %s" % (i.get("number"), str(i.get("title", ""))[:80]) for i in items[:10])
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "text": text}, f)
    except OSError as exc:
        return text, "cache not written (%s)" % exc
    return text, None


def event_issuelist():
    """SessionStart: the open issues, so the session starts knowing what work is tracked. Its own
    entry (like profile) because inject is already near the 10,000-char per-hook limit."""
    try:
        payload = read_payload()
        waiting = _waiting_session_note(payload)
        text, problem = "", ""
        if _issues_enabled():
            text, problem = _open_issues_text(_payload_cwd(payload or ""))
        out = {}
        context = [t for t in (text, waiting) if t]
        if context:
            out["hookSpecificOutput"] = {"hookEventName": "SessionStart",
                                         "additionalContext": "\n\n".join(context)}
        notes = []
        if _issues_enabled():
            if problem and not text:
                notes.append("house-rules: could not list open issues (%s)" % problem)
            elif text:
                n = sum(1 for l in text.splitlines() if l.startswith("- #"))
                notes.append("house-rules: %d open issue%s loaded" % (n, "" if n == 1 else "s")
                             if n else "house-rules: no open issues")
                if problem:
                    notes.append("house-rules: open issue list: %s" % problem)
        if waiting:
            notes.append("house-rules: " + waiting)
        if notes:
            out["systemMessage"] = " | ".join(notes)
        if out:
            emit(out)
    except Exception as exc:
        emit({"systemMessage": "house-rules: could not list open issues (%s: %s)" % (type(exc).__name__, exc)})
    return 0


# #256: the checkpoint table. Each row is (moment, rule name, check function, "block" or "remind").
# A check takes the context dict event_handover builds and returns the exact fix when the rule is
# missed, else "". A "block" row at "reply ends" stops the reply once; on the retry
# (stop_hook_active) it only reports, the same safety event_subagentcommit uses.
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.MULTILINE)


_OPTION_LABEL_RE = re.compile(r"\boption\s+(?:[A-Za-z]|\d+)\b|\(\s*[A-Ca-c1-3]\s*\)", re.IGNORECASE)


_PICK_QUESTION_RE = re.compile(r"\b(approve|approval|pick|choose|which|sign off|go ahead)\b", re.IGNORECASE)


_NO_PAGE_RE = re.compile(r"\bno\s+page\b", re.IGNORECASE)


def _offers_choices(reply):
    """True when a reply offers named options or lays out a plan for aj to approve. Conservative:
    it needs a closing question, plus either two labelled options in it or a list of 3+ items
    earlier with a question asking aj to pick or approve."""
    text = _MD_FENCED_BLOCK_RE.sub("", reply or "").strip()
    if not text.endswith("?"):
        return False
    final = text.split("\n\n")[-1] if "\n\n" in text else text.splitlines()[-1]
    if len({m.group(0).lower() for m in _OPTION_LABEL_RE.finditer(text)}) >= 2:
        return True
    items = _LIST_ITEM_RE.findall(text[:len(text) - len(final)] if final else text)
    return len(items) >= 3 and bool(_PICK_QUESTION_RE.search(final))


def _page_escape(ctx):
    """True when aj's own genuine message says "no page". A helper's hand-back never counts."""
    text = ctx.get("user_text") or ""
    return bool(_NO_PAGE_RE.search(text)) and not _is_relayed_prompt(text)


def _check_page(ctx):
    if _page_escape(ctx):
        return ""
    reply = ctx.get("reply") or ""
    cwd = ctx.get("cwd") or ""
    if _reply_links_page(reply, cwd):
        return ""
    out = _outside_page_links(reply, cwd)
    if out:
        return ("%s is outside this session's folder %s, so the app cannot open it: copy it into "
                "%s/docs/plans/ and link the copy" % (out[0], cwd, cwd))
    if ctx.get("long_words") or _offers_choices(reply):
        return ("put the detail on a page: write a content.json, run `python3 %s build <content.json>` "
                "and link the page it makes in the reply"
                % os.path.join(SCRIPTS_DIR, "make_page.py"))
    return ""


def _check_editor(ctx):
    if _page_escape(ctx) or not ctx.get("editor_owed"):
        return ""
    return ("hand the text to @house-rules:editor (Agent tool, subagent_type house-rules:editor), "
            "apply its rewrites, then send the reply (%s)" % ctx["editor_owed"])


def _check_evidence(ctx):
    if not ctx.get("needs_evidence"):
        return ""
    return "run the check and quote its real output, or restate the claim as untested and say why"


def _check_commit(ctx):
    if not ctx.get("uncommitted"):
        return ""
    return "commit %s on your own branch" % ", ".join(ctx["uncommitted"][:8])


def _check_handoff(ctx):
    return ctx.get("handoff") or ""


def _check_plain(ctx):
    if not ctx.get("plain_problems"):
        return ""
    return "open with a short plain-English summary (%s)" % "; ".join(ctx["plain_problems"])


# --- pagecheck (#257): a handover page must come from make_page.py -------------------------
# PreToolUse on Write and Artifact.
PAGE_MARK_RE = re.compile(r"<!--\s*house-rules make_page\b")


_PAGE_EXT = (".html", ".htm")


_PAGE_SKIP_ACTIONS = {"read", "list", "open", "delete", "view", "get", "ls", "remove"}


_PAGE_DENY = (
    "House rules, page check: %s is a hand-written page - it has no house-rules make_page mark. "
    "Pages are built, not typed. Write the content file, then run: python3 %s build <content.json> "
    "and use the page it builds. HOUSE_RULES_LOOP=off turns this check off."
)


def _page_note(text):
    emit({"systemMessage": "house-rules page check: " + text})


def _page_in_plans(path):
    parts = [p for p in re.split(r"[\\/]+", path) if p]
    return any(parts[i] == "docs" and parts[i + 1] == "plans" for i in range(len(parts) - 1))


def _page_deny(page):
    script = os.path.join(_plugin_root(), "scripts", "make_page.py")
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": _PAGE_DENY % (page, script)}})


def _page_candidates(ti):
    out = []
    fp = ti.get("file_path")
    if isinstance(fp, str) and fp:
        out.append(fp)
    files = ti.get("files")
    vals = list(files.values()) if isinstance(files, dict) else (files if isinstance(files, list) else [])
    out.extend(v for v in vals if isinstance(v, str) and v and v not in out)
    return out


def event_pagecheck():
    try:
        if not _loop_enabled():
            return 0
        payload = read_payload()
        data = json.loads(payload) if payload else {}
        ti = data.get("tool_input") if isinstance(data, dict) else None
        if not isinstance(ti, dict):
            _page_note("the call carried no tool_input, so the check could not run; the call is allowed.")
            return 0
        tool = str(data.get("tool_name") or "")
        if tool == "Write":
            fp = ti.get("file_path")
            if not (isinstance(fp, str) and fp.lower().endswith(_PAGE_EXT) and _page_in_plans(fp)):
                return 0  # not a docs/plans page: nothing to check, nothing to say
            if PAGE_MARK_RE.search(str(ti.get("content") or "")):
                return 0
            _page_deny(fp)
            return 0
        # Artifact (or any other tool the matcher routes here)
        action = str(ti.get("action") or ti.get("command") or ti.get("operation") or "").lower()
        if action in _PAGE_SKIP_ACTIONS:
            _page_note("skipped, the Artifact call is a %s action, not a page save." % action)
            return 0
        if ti.get("asset") is True:
            _page_note("skipped, the Artifact call is an asset upload, not a page.")
            return 0
        cands = _page_candidates(ti)
        pages = [c for c in cands if c.lower().endswith(_PAGE_EXT)]
        if not pages:
            if ti.get("type") or ti.get("artifact_type"):
                _page_note("skipped, the Artifact input is the data file of a typed artifact, not an HTML page.")
            else:
                _page_note("skipped, the Artifact input names no HTML file (%s)."
                           % (", ".join(cands) or "no file path"))
            return 0
        for page in pages:
            try:
                with open(page, encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4096)
            except OSError as exc:
                _page_note("could not read %s (%s), so the check did not run; the publish is allowed."
                           % (page, type(exc).__name__))
                continue
            if not PAGE_MARK_RE.search(head):
                _page_deny(page)
                return 0
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the page check hit an error (%s: %s) and did not "
                               "run for this call; the call is allowed." % (type(exc).__name__, exc)})
    return 0


def _record_qa_link(ctx):
    """True (and qa_page_linked recorded) when the reply links the QA page. Also used on a retry."""
    page, reply = ctx.get("qa_page") or "", ctx.get("reply") or ""
    cwd = ctx.get("cwd") or ""
    in_reply = page in reply or os.path.basename(page) in reply
    if page and cwd and in_reply:  # #329: the page counts only when its path opens inside the folder
        in_reply = _inside(os.path.normcase(os.path.abspath(os.path.join(cwd, page))), cwd)
    if not (page and in_reply):  # D8: the reply names this feature's QA page; a bare artifact link proves nothing
        return False
    state, problem = _loop_read(ctx["qa_git_dir"])
    if problem:
        raise OSError(problem)
    state["qa_page_linked"] = True
    _loop_write(ctx["qa_git_dir"], state)
    return True


_DECIDED_RE = re.compile(r"(?i)\bI (?:went with|chose|picked|decided on|settled on)\b")


def _check_decided(ctx):
    """#460: a reply that settles a design point on its own is sent back once."""
    text = _MD_FENCED_BLOCK_RE.sub("", ctx.get("reply") or "")
    for line in text.split("\n"):
        if not line.lstrip().startswith(">") and _DECIDED_RE.search(line):
            return ("a design point is aj's to decide; put the choice to aj as options with one marked as the "
                    "suggestion instead of saying \"I went with ...\"")
    return ""


def _check_qa_page(ctx):
    """#269: in QA the build is handed over with a make_page.py QA page, linked in a reply. Not
    skipped by "no page": a QA page is mandatory."""
    if ctx.get("qa_stage") != "qa" or ctx.get("qa_linked"):
        return ""
    page = ctx.get("qa_page") or ""
    if _record_qa_link(ctx):
        return ""
    missing = "the QA page is built but not linked in the reply" if page else "no QA page is built yet"
    return ("%s: build it with `python3 %s build docs/plans/<name>-qa.page.json`, where the content file has a "
            "`qa` block (feature, base, unverified, files), then name the page's file in the reply, beside any link"
            % (missing, os.path.join(SCRIPTS_DIR, "make_page.py")))


def _repo_root_of(path):
    """The nearest folder at or above `path` holding .git (a folder or a worktree file), else ""."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return ""
        d = up


def _check_changelog(ctx):
    """#387/#244: a turn that wrote files in a repo whose root has a CHANGELOG.md, and left it alone, is sent back."""
    touched = {}
    for fp in ctx.get("written") or []:
        if "/.claude/" in str(fp).replace("\\", "/"):
            continue
        root = _repo_root_of(fp)
        if root and os.path.isfile(os.path.join(root, "CHANGELOG.md")):
            touched.setdefault(root, False)
            if os.path.abspath(fp) == os.path.join(root, "CHANGELOG.md"):
                touched[root] = True
    stale = sorted(r for r, done in touched.items() if not done)
    if not stale:
        return ""
    return ("add one line under Unreleased in %s (plain words first, exact detail after)"
            % ", ".join(os.path.join(r, "CHANGELOG.md") for r in stale))


CHECKPOINTS = [
    ("reply ends", "page", _check_page, "report"),  # #309: report only until the restructure
    ("reply ends", "editor", _check_editor, "block"),
    ("reply ends", "evidence", _check_evidence, "block"),
    ("reply ends", "commit", _check_commit, "block"),
    ("reply ends", "handoff", _check_handoff, "block"),
    ("reply ends", "plain summary", _check_plain, "block"),
    ("reply ends", "qa page", _check_qa_page, "block"),
    ("reply ends", "decided for you", _check_decided, "block"),
    ("reply ends", "changelog", _check_changelog, "block"),
]


CHECKPOINT_RULES = {
    "page": "A reply that offers choices, lays out a plan, or runs to %d words or more links a page." % LONG_REPLY_WORDS,
    "editor": "A page goes past @house-rules:editor before aj reads it; a long reply too when HOUSE_RULES_EDITOR=on.",
    "evidence": "A success claim needs a tool run and its quoted output behind it.",
    "commit": "Files a turn writes are committed on your own branch before it ends.",
    "handoff": "A turn that wrote files is pushed, with a fresh clean handoff note and Today.md updated.",
    "qa page": "In QA, the build is handed to aj with a QA page built by make_page.py, linked in a reply.",
    "decided for you": "Design points are aj's to decide; a reply puts them as options, not as \"I went with ...\".",
    "changelog": "Every change adds a line to the repo's CHANGELOG.md, in the same turn.",
    "plain summary": "A reply reporting finished work opens with a short plain-English summary.",
}


def _missed_checkpoints(ctx):
    """[(rule name, fix)] for every blocking checkpoint at 'reply ends' that the reply misses."""
    if not _loop_enabled():
        return []
    return [(name, fix) for moment, name, fn, mode in CHECKPOINTS
            if moment == "reply ends" and mode == "block" for fix in [fn(ctx)] if fix]


def _checkpoint_reason(missed):
    lines = ["House rules, the reply is not done yet. It misses %d checkpoint%s:" % (
        len(missed), "" if len(missed) == 1 else "s")]
    for name, fix in missed:
        lines.append("- %s: %s Fix: %s." % (name, CHECKPOINT_RULES[name], fix))
    lines.append("Fix these and send only what changed, not the whole reply again. A missing page blocks every retry "
                 "until the reply links one; the other checks block once. HOUSE_RULES_LOOP=off turns it off.")
    return "\n".join(lines)


# #283: the page checkpoint keeps blocking on the retry until the reply links a page. aj's pick on the
# automatic-pages build plan: after PAGE_BLOCK_LIMIT blocks in a row the reply goes through with a note,
# so a broken page builder can't loop a session with nobody watching.
PAGE_BLOCK_LIMIT = 3


PAGE_BLOCKS_FILE = "page-blocks.json"


def _page_blocks_path(cwd, session_id):
    """In the common git directory, so worktrees share it; outside a repository, a session-keyed temp file."""
    cd = _common_git_dir(cwd)
    if cd:
        return os.path.join(cd, "house-rules", PAGE_BLOCKS_FILE)
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-page-blocks-%s.json" % safe)


def _page_blocks(path, session_id, mark, change=None):
    """Page blocks in a row for this session since aj's message `mark` (a new message starts again at 0).
    change "bump" adds one block, "clear" resets the count; either saves the file. Raises OSError or
    ValueError when the file can't be read or written, and the caller reports it."""
    data = json.loads(_read_text(path)) if os.path.isfile(path) else {}
    if not isinstance(data, dict):
        raise ValueError("%s is not a JSON object" % path)
    entry = data.get(session_id) if isinstance(data.get(session_id), dict) else {}
    count = entry.get("count", 0) if entry.get("mark") == mark else 0
    if change:
        count = count + 1 if change == "bump" else 0
        data[session_id] = {"mark": mark, "count": count}
        _write_atomic(path, json.dumps(data))
    return count


# closablemerge - PostToolUse on Bash|merge_pull_request (#362). A merged pull request stamps every
# closable entry (state["closable"], saved by a QA pass) that has no merge yet. Never raises.
_GH_PR_MERGE_RE = re.compile(r"(?:^|[;&|(\s])gh\s+pr\s+merge\b([^;&|\n]*)")


def _unwrap_tool_response(resp):
    """#374: the GitHub tool returns a list of text blocks, [{"type": "text", "text": "<json>"}]. Join the
    texts and parse them: the object when it is a dict, else the joined text. Anything else is returned as is."""
    if isinstance(resp, list) and resp and all(isinstance(i, dict) and i.get("type") == "text" for i in resp):
        text = "".join(str(i.get("text", "")) for i in resp)
        parsed = text  # not JSON (an error message): kept as the joined text, which proves nothing
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = text
        return parsed if isinstance(parsed, dict) else text
    return resp


def _closable_merge_of(data):
    """(repo, number) of a merge this payload reports, else None."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    resp = _unwrap_tool_response(data.get("tool_response"))
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except ValueError:
            resp = None
    if tool.lower().startswith("mcp__github__") and tool.endswith("merge_pull_request"):
        if isinstance(resp, dict) and resp.get("merged") is True and ti.get("pullNumber") is not None:
            return "%s/%s" % (ti.get("owner"), ti.get("repo")), int(ti["pullNumber"])
        return None
    if tool in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        m = _GH_PR_MERGE_RE.search(ti["command"])
        if not m:
            return None
        code, out = None, ""
        if isinstance(resp, dict):
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if code is None and resp.get("interrupted"):
                code = 1
            out = "%s\n%s" % (resp.get("stdout") or "", resp.get("stderr") or "")
        # Stamp only on proof: exit code 0, or, where no code is reported, gh's own success line
        # ("Merged pull request", "Squashed and merged pull request", "Rebased and merged pull request").
        # "will be automatically merged" is not a merge yet.
        if code is None and not re.search(r"merged pull request", out, re.IGNORECASE):
            return None
        if code not in (None, 0):
            return None
        num = re.search(r"(?<![\w-])(\d+)(?![\w-])", m.group(1))
        url = re.search(r"github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)", m.group(1))
        repo = re.search(r"(?:-R|--repo)[ =]+(\S+)", m.group(1))
        if url:
            return url.group(1), int(url.group(2))
        if num:
            return (repo.group(1) if repo else ""), int(num.group(1))
    return None


def _closed_issue_of(data):
    """(repo, number) of a close this PostToolUse payload proves succeeded, else None (#363)."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    resp = _unwrap_tool_response(data.get("tool_response"))
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except ValueError:
            resp = {"raw": resp}  # not JSON: kept as text, which proves nothing for the tool route
    if _GITHUB_ISSUE_WRITE_RE.match(tool):
        if str(ti.get("method", "")).lower() != "update" or str(ti.get("state", "")).lower() != "closed":
            return None
        try:
            num = int(ti.get("issue_number"))
        except (TypeError, ValueError):
            num = None  # no usable issue number: nothing to remove
        if num is None:
            return None
        text = json.dumps(resp) if resp is not None else ""
        if isinstance(resp, dict) and (resp.get("error") or resp.get("isError")):
            return None
        ok = (isinstance(resp, dict) and (str(resp.get("state", "")).lower() == "closed" or resp.get("url")))
        if not ok and not re.search(r'"state"\s*:\s*"closed"', text, re.IGNORECASE):
            return None
        return ("%s/%s" % (ti.get("owner"), ti.get("repo")) if ti.get("owner") and ti.get("repo") else ""), num
    if tool in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        cmd = ti["command"]
        if not any(r.search(cmd) for r in _GH_ISSUE_CLOSE_RES):
            return None
        repo, num, _ = _close_gh_parse(cmd)
        if num is None:
            return None
        code, out = None, ""
        if isinstance(resp, dict):
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if code is None and resp.get("interrupted"):
                code = 1
            out = "%s\n%s" % (resp.get("stdout") or "", resp.get("stderr") or "")
        if code is None and not re.search(r"(closed issue|\"state\"\s*:\s*\"closed\")", out, re.IGNORECASE):
            return None
        if code not in (None, 0):
            return None
        return repo, num
    return None


_PR_REF_RE = re.compile(r"\b(?:Refs|Part of)\s+([\w.-]+/[\w.-]+)?#(\d+)", re.IGNORECASE)
LOOP_PR_BODIES_ENV = "HOUSE_RULES_LOOP_PR_BODIES_FILE"  # tests: {"owner/repo#n": body}; a missing file is a failed read


def _pr_refs(body, repo):
    """A2: [[repo, number]] that a pull request body links with `Refs #N` or `Part of #N`; a bare #N is in `repo`."""
    return [[(r or repo).lower(), int(n)] for r, n in _PR_REF_RE.findall(body or "")]


def _merged_pr_refs(state, repo, number):
    """(refs, problem) for the merged pull request: the links recorded when it was opened in a session, else
    its body read once from GitHub. problem says why nothing could be read ("" when it could)."""
    rec = state.get("pr_refs") if isinstance(state.get("pr_refs"), dict) else {}
    hit = rec.get("%s#%d" % (repo.lower(), number)) if repo else next(
        (v for k, v in rec.items() if k.endswith("#%d" % number)), None)
    if isinstance(hit, list):
        return hit, ""
    stand_in = os.environ.get(LOOP_PR_BODIES_ENV)
    try:
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                return _pr_refs(json.load(f)["%s#%d" % (repo, number)], repo), ""
        if not repo or not shutil.which("gh"):
            raise RuntimeError("no repo is named" if not repo else "gh is not installed")
        import subprocess
        proc = subprocess.run(["gh", "pr", "view", str(number), "--repo", repo, "--json", "body", "--jq", ".body"],
                              capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
        if proc.returncode != 0:
            raise RuntimeError(((proc.stderr or "").strip().splitlines() or ["gh exited %d" % proc.returncode])[0])
        return _pr_refs(proc.stdout, repo), ""
    except Exception as exc:
        return [], "its body could not be read (%s: %s)" % (type(exc).__name__, exc)


# #510: after a merge, the local branch of the merged pull request and the finished helper worktrees are deleted
# when nothing unsaved goes with them. Runs inside the hook (not through Bash, so the guard is not involved).
CLEANUP_ENV = "HOUSE_RULES_CLEANUP"  # "off" turns the cleanup off
PR_FILE_ENV = "HOUSE_RULES_PR_FILE"  # tests: JSON {"ref", "sha", "merged"} that replaces the gh api read
CLEANUP_SECONDS = 6  # inside hooks.json's 10s for closablemerge
CLEANUP_IDLE_SECONDS = 30 * 60  # a helper copy touched more recently may still be in use, so it is kept


def _worktree_recent(git, path):
    """True when the worktree's index or HEAD changed in the last CLEANUP_IDLE_SECONDS: a helper may still be
    working in it. A brand-new helper copy has no commits of its own, so "merged and pushed" alone can't tell."""
    rc, gd, _e = git(path, ["rev-parse", "--absolute-git-dir"])
    if rc != 0:
        return True  # can't tell: keep it
    newest = 0
    for name in ("index", "HEAD", "logs/HEAD"):
        p = os.path.join(gd.strip(), name)
        if os.path.exists(p):
            newest = max(newest, os.path.getmtime(p))
    return time.time() - newest < CLEANUP_IDLE_SECONDS
_HELPER_WT = ".claude/worktrees/"


class _CleanupBudget(Exception):
    pass


def _cleanup_pr(repo, number, left):
    """(ref, sha, merged) of the pull request's head, from the stand-in file or `gh api`. Raises on a failed read."""
    stand_in = os.environ.get(PR_FILE_ENV)
    if stand_in:
        with open(stand_in, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d["ref"], d["sha"], d["merged"] is True
    if not shutil.which("gh"):
        raise RuntimeError("gh is not installed")
    import subprocess
    proc = subprocess.run(["gh", "api", "repos/%s/pulls/%d" % (repo or "{owner}/{repo}", number), "--jq",
                           "{ref: .head.ref, sha: .head.sha, merged: .merged}"],
                          capture_output=True, text=True, timeout=min(LOOP_GH_SECONDS, left()))
    if proc.returncode != 0:
        raise RuntimeError(((proc.stderr or "").strip().splitlines() or ["gh exited %d" % proc.returncode])[0])
    d = json.loads(proc.stdout)
    return d["ref"], d["sha"], d["merged"] is True


def _merge_cleanup(cwd, repo, number):
    """The note for the cleanup after the merge of repo#number ("" when it is off). Never raises."""
    if os.environ.get(CLEANUP_ENV, "").strip().lower() == "off":
        trace("house-rules plugin: cleanup after a merge is off (%s=off), so it did nothing." % CLEANUP_ENV)
        return ""
    name = "%s#%d" % (repo or "this repo", number)
    deadline = time.time() + CLEANUP_SECONDS

    def left():
        rest = deadline - time.time()
        if rest <= 0.3:
            raise _CleanupBudget()
        return rest

    def git(top, args):
        return _ag(top, args, timeout=left(), check=False)

    deleted, kept = [], []
    try:
        try:
            ref, sha, merged = _cleanup_pr(repo, number, left)
        except _CleanupBudget:
            raise
        except Exception as exc:
            return "Cleanup after the merge of %s did not run: GitHub could not be read (%s: %s). Nothing was deleted." % (
                name, type(exc).__name__, exc)
        if not merged:
            return "Cleanup after the merge of %s did not run: GitHub does not say it is merged. Nothing was deleted." % name
        rc, out, _e = git(cwd, ["worktree", "list", "--porcelain"])
        if rc != 0:
            return "Cleanup after the merge of %s did not run: %s is not a git repository. Nothing was deleted." % (name, cwd)
        wts, cur = [], None
        for line in out.splitlines():
            if line.startswith("worktree "):
                cur = {"path": line[9:], "branch": "", "head": ""}
                wts.append(cur)
            elif cur is not None and line.startswith("branch refs/heads/"):
                cur["branch"] = line[18:]
            elif cur is not None and line.startswith("HEAD "):
                cur["head"] = line[5:]
        main = wts[0]["path"]
        here = git(cwd, ["rev-parse", "--show-toplevel"])[1].strip()
        norm = os.path.realpath
        rel = lambda p: os.path.relpath(p, main).replace(os.sep, "/")
        default = ""
        rc, out, _e = git(main, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
        if rc == 0 and out.strip():
            default = out.strip()
        else:
            for cand in ("origin/main", "origin/master"):
                if git(main, ["rev-parse", "--verify", "-q", "refs/remotes/" + cand])[0] == 0:
                    default = cand
                    break
        fetched = None
        # Helper worktrees: on the merged branch, or finished on their own (merged into the default and pushed).
        for w in wts[1:]:
            if not w["branch"] or _HELPER_WT not in w["path"].replace(os.sep, "/") or norm(w["path"]) == norm(here):
                continue
            tip = w["head"]
            why = ""
            if w["branch"] == ref:
                if tip != sha:
                    why = "its branch has commits not in the merged pull request"
            elif not default:
                why = "the default branch could not be found, so whether it is merged is unknown"
            else:
                if fetched is None:
                    frc, _o, ferr = git(main, ["fetch", "-q", "origin", default.split("/", 1)[1]])
                    fetched = "" if frc == 0 else (ferr or "git fetch failed")
                if fetched:
                    why = "the default branch could not be fetched (%s)" % fetched
                elif git(main, ["merge-base", "--is-ancestor", tip, default])[0] != 0:
                    continue  # not merged: still somebody's work, not named
                elif not git(main, ["branch", "-r", "--contains", tip])[1].strip():
                    why = "its commits are not on any remote branch"
            # Recency first: `git status` below can rewrite the index and make an idle copy look just used.
            if not why and w["branch"] != ref and _worktree_recent(git, w["path"]):
                why = "it was used in the last %d minutes, so a helper may still be working in it" % (
                    CLEANUP_IDLE_SECONDS // 60)
            if not why and git(w["path"], ["status", "--porcelain"])[1].strip():
                why = "it has uncommitted changes"
            if not why:
                rc, _o, err = git(main, ["worktree", "remove", w["path"]])
                if rc == 0:
                    deleted.append("worktree " + rel(w["path"]))
                    w["gone"] = True
                    continue
                why = "git refused to remove it (%s)" % ((err.splitlines() or ["?"])[0])
            kept.append("worktree %s (%s)" % (rel(w["path"]), why))
        # The local branch of the merged pull request. The default branch is never deleted, whatever was merged.
        if ref in ("main", "master") or (default and ref == default.split("/", 1)[1]):
            kept.append("branch %s (the default branch is never deleted)" % ref)
        elif git(main, ["rev-parse", "--verify", "-q", "refs/heads/" + ref])[0] != 0:
            kept.append("branch %s (there is no local branch of that name)" % ref)
        else:
            tip = git(main, ["rev-parse", "refs/heads/" + ref])[1].strip()
            holders = [w for w in wts if w["branch"] == ref and not w.get("gone")]
            if holders:
                where = "the main checkout" if holders[0]["path"] == main else (
                    "this checkout" if norm(holders[0]["path"]) == norm(here) else rel(holders[0]["path"]))
                kept.append("branch %s (checked out in %s)" % (ref, where))
            elif tip != sha:
                rc, out, _e = git(main, ["rev-list", "--count", "%s..%s" % (sha, tip)])
                n = out.strip() if rc == 0 and out.strip().isdigit() else ""
                kept.append("branch %s (%s)" % (ref, ("has %s commit%s not in the merged pull request" % (n, "" if n == "1" else "s"))
                                                if n and n != "0" else "its tip is not the merged pull request's head"))
            else:
                rc, _o, err = git(main, ["branch", "-d", ref])
                if rc != 0:  # squash- or rebase-merged: git does not see it as merged; the tip equals the PR head, so -D loses nothing
                    rc, _o, err = git(main, ["branch", "-D", ref])
                if rc == 0:
                    deleted.append("branch " + ref)
                else:
                    kept.append("branch %s (git refused to delete it: %s)" % (ref, (err.splitlines() or ["?"])[0]))
    except _CleanupBudget:
        kept.append("the rest was not checked (the %d s cleanup budget ran out)" % CLEANUP_SECONDS)
    except Exception as exc:
        kept.append("the rest was not checked (%s: %s)" % (type(exc).__name__, exc))
    return "Deleted after the merge of %s: %s. Kept: %s." % (
        name, "; ".join(deleted) or "nothing", "; ".join(kept) or "nothing")


def event_closablemerge():
    try:
        if not _loop_enabled():
            trace("house-rules plugin: closable-merge stamping is off (HOUSE_RULES_LOOP=off), so it did nothing.")
            return 0
        payload = read_payload()
        if not payload:
            return 0
        data = json.loads(payload)
        if not isinstance(data, dict):
            return 0
        closed = _closed_issue_of(data)
        if closed:  # #363: the evidence goes only once the close is proven to have worked
            _, git_dir = _issues_locate(_payload_cwd(payload))
            if git_dir:
                _close_forget(git_dir, closed[0], closed[1])
                trace("house-rules plugin: close of %s#%d succeeded, its closable/sweep record was removed." % closed)
            return 0
        merged = _closable_merge_of(data)
        if not merged:
            return 0
        cleanup = _merge_cleanup(_payload_cwd(payload), merged[0], merged[1])
        _, git_dir = _issues_locate(_payload_cwd(payload))
        if not git_dir:
            if cleanup:
                emit({"systemMessage": cleanup,
                      "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": cleanup}})
            return 0
        state, problem = _loop_read(git_dir)
        if problem:
            emit({"systemMessage": " ".join([problem, cleanup]).strip()})
            return 0
        open_ = [e for e in state.get("closable", []) if isinstance(e, dict) and e.get("merged_pr") is None]
        repo, number = merged
        notes = [cleanup] if cleanup else []
        if open_:
            refs, why = _merged_pr_refs(state, repo, number)
            hit = [e for e in open_ if any(isinstance(i, dict) and i.get("number") == n
                                           and _close_repo_match(r, i.get("repo", ""))
                                           for i in e.get("issues") or [] for r, n in refs)]
            for e in hit:
                e["merged_pr"] = {"repo": repo, "number": number, "at": int(time.time())}
            if hit:
                _loop_write(git_dir, state)
                nums = sorted({("#%d" % i["number"]) if _close_repo_match(repo, i.get("repo", ""))
                               else "%s#%d" % (i.get("repo"), i["number"])
                               for e in hit for i in e.get("issues") or []
                               if isinstance(i, dict) and "number" in i})
                notes.append('Design loop: the merge of %s#%d is stamped on the QA-passed record, so the close '
                             'guard allows those closes once aj says yes. Offer aj: "Close as completed: %s". '
                             "Never close without aj's word." % (repo, number, ", ".join(nums)))
            else:
                notes.append("house-rules: the merge of %s#%d stamped no closable record, because %s." % (
                    repo, number, why or "it links none of the QA-passed issues with `Refs #N`"))
            trace("house-rules plugin: merge of %s#%d stamped %d closable record(s)." % (repo, number, len(hit)))
        if state.get("stage") == "qa":  # U3: the merge never moves the stage; aj is asked for the verdict
            notes.append('Design loop: pull request %s#%d merged while "%s" is in QA, so the stage file still '
                         'says QA. Ask aj for "QA passed: %s" or "QA failed: %s"; the stage moves only on their word.'
                         % ((repo, number) + (state.get("feature") or "this feature",) * 3))
        if notes:
            emit({"systemMessage": " ".join(notes),
                  "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": " ".join(notes)}})
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the closable-merge check hit an error (%s: %s) and "
                               "stamped nothing for this call." % (type(exc).__name__, exc)})
    return 0


def _scope_loop_link(payload, field):
    return "", _loop_scope_note(payload)


# What the delegation part used to call directly (#359, step 2c). It loops over core lists; these are the entries.
def _post_tool_records(payload):
    """The issue and label recording event_autosave used to run first (core.TOOL_RECORD_HOOKS)."""
    issue_notes = _issues_record(payload) if (_issues_enabled() or _loop_enabled()) else []
    issue_notes += _loop_record_labels(payload)
    return issue_notes


def _edit_gates(payload):
    """The loop and issue gates event_commitgate used to run first (core.EDIT_GATE_HOOKS). True when the call
    was answered."""
    if _loop_enabled():
        deny, problem = _loop_gate(payload)
        if deny:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": deny}})
            return True
        if problem:
            emit({"systemMessage": problem})
    if _issues_enabled():
        deny, problem = _issues_gate(payload)
        if deny:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": deny}})
            return True
        if problem:
            emit({"systemMessage": problem})
            return True
    return False


# The design loop's pieces of the end-of-reply dispatcher (event_handover in hook.py), moved out of it verbatim.
def handover_stop_lines(payload):
    """(issue line, issue problem, label line, label problem)."""
    issue_line, issue_problem = _issues_stop_line(payload)
    try:
        label_line, label_problem = _loop_stop_line(payload)
    except Exception as exc:
        label_line, label_problem = None, "house-rules: the design-loop label check hit an error (%s: %s)." % (
            type(exc).__name__, exc)
    return issue_line, issue_problem, label_line, label_problem


def handover_page_row(payload, transcript_path, have_reply, reply_text, long_words, trace_lines):
    """The page row of the checkpoint table (#283, #309, #310, #326): the report-only page note, or "". An error
    is added to trace_lines."""
    # #256: the checkpoint table. A miss blocks once, except the page row (#283), which blocks every
    # retry up to PAGE_BLOCK_LIMIT in a row. Any error here fails open with a message.
    def _page_count(ctx, change=None):
        mark = hashlib.sha1((ctx.get("user_text") or "").encode("utf-8")).hexdigest()[:16]
        return _page_blocks(_page_blocks_path(_payload_cwd(payload), _field(_SESSION_ID_RE, payload) or ""),
                            _field(_SESSION_ID_RE, payload) or "", mark, change)

    # #309 (incident 6 of #303): the page row reports instead of blocking, on the first reply and the retry
    # alike, until the restructure. It pushed another repo's work into a session as a proposal page.
    page_note = ""
    if _loop_enabled():
        try:
            pctx = {"reply": reply_text if have_reply else "", "long_words": long_words,
                    "cwd": _payload_cwd(payload),
                    "user_text": _last_user_text(transcript_path) if transcript_path else ""}
            fix = _check_page(pctx)
            # #310: once a reply to aj's message is flagged, the page stays owed for every later reply to the
            # same message until one links a page - a shorter retry no longer clears it. The page-blocks file
            # keeps a count per message; above zero means owed.
            if _page_escape(pctx) or _reply_links_page(pctx["reply"], pctx["cwd"]):
                _page_count(pctx, "clear")
            elif fix or _page_count(pctx) > 0:
                # #326: the note is said once per message of aj's, on the first flag (count 0). The bump still
                # records that a page is owed; later replies to the same message, flagged or owed, stay quiet.
                first = _page_count(pctx) == 0
                _page_count(pctx, "bump")
                if first:
                    page_note = ("House rules, page checkpoint (report only, #309): %s. Nothing is blocked; if this "
                                 "reply belongs to another repo's work, the issue for that repo is enough." % fix)
        except Exception as exc:
            trace_lines.append("house-rules: the page checkpoint could not run (%s: %s), so this reply got no "
                               "page reminder." % (type(exc).__name__, exc))
    return page_note


def handover_checkpoints(payload, transcript_path, have_reply, reply_text, long_words, editor_owed,
                         needs_evidence, uncommitted, plain_problems, trace_lines, handoff="", written=None):
    """The blocking checkpoints at "reply ends" (first reply only). True when the reply was blocked (the
    block is emitted here). An error is added to trace_lines and nothing is blocked."""
    try:
        ctx = {
            "reply": reply_text if have_reply else "",
            "long_words": long_words,
            "editor_owed": editor_owed,
            "needs_evidence": needs_evidence,
            "uncommitted": uncommitted, "handoff": handoff, "written": list(written or []),
            "plain_problems": plain_problems, "cwd": _payload_cwd(payload),
            "user_text": _last_user_text(transcript_path) if transcript_path else "",
        }
        try:
            _top, _gd = _issues_locate(_payload_cwd(payload))
            if _gd:
                _st, _pr = _loop_read(_gd)
                if _pr:
                    raise OSError(_pr)
                ctx.update(qa_stage=_st.get("stage"), qa_page=_st.get("qa_page"),
                           qa_linked=_st.get("qa_page_linked"), qa_git_dir=_gd)
        except Exception as exc:
            trace_lines.append("house-rules: the QA page checkpoint could not read the stage file (%s: %s), "
                               "so it is off for this reply." % (type(exc).__name__, exc))
        missed = _missed_checkpoints(ctx)
        if missed:
            emit({"decision": "block", "reason": _checkpoint_reason(missed)})
            return True
    except Exception as exc:
        trace_lines.append("house-rules: the checkpoint table hit an error (%s: %s), so this reply was "
                           "not blocked." % (type(exc).__name__, exc))
    return False


def handover_qa_retry(payload, have_reply, reply_text, trace_lines):
    # #269: a QA page linked only in the retry reply is still recorded; the retry never blocks.
    try:
        _top, _gd = _issues_locate(_payload_cwd(payload))
        if _gd:
            _st, _pr = _loop_read(_gd)
            if _pr:
                raise OSError(_pr)
            if _st.get("stage") == "qa" and _st.get("qa_page") and not _st.get("qa_page_linked"):
                _record_qa_link({"reply": reply_text if have_reply else "",
                                 "qa_page": _st.get("qa_page"), "qa_git_dir": _gd,
                                 "cwd": _payload_cwd(payload)})
    except Exception as exc:
        trace_lines.append("house-rules: the QA page link could not be recorded on the retry (%s: %s)."
                           % (type(exc).__name__, exc))


core.register_guard_issue(_author_guard)
core.register_guard_issue(_issues_guard)
core.register_github_write(_guardgithub_issue_checks)
core.register_prompt(_scope_loop_link)
core.register_delegate_note(_issues_plan_note)
core.register_subagent_note(_loop_helper_note)
core.register_tool_record(_post_tool_records)
core.register_edit_gate(_edit_gates)
