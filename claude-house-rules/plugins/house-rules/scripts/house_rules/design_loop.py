"""house_rules.design_loop - the design loop part (#359, step 2c of #340): the issue workflow, the loop stages, labels
and approvals, the issue list, the author and issue guards, the close guard and closablemerge, the end-of-reply
checkpoints and pagecheck. Moved verbatim from hook.py; docs/4-systems/plugin-restructure.md, "Step 2c", says what moved
and why.

Imports only from house_rules.core. It registers itself on the core link lists at the foot of this file."""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

from house_rules import core
from house_rules.core import *  # noqa: F401,F403
from house_rules.writing import _pages_enabled  # noqa: F401  (#537)
from house_rules.core import (  # noqa: F401
    _builders_enabled,
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


def _steps_outside(git_dir, session_id):
    cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(cfg, "house-rules-steps", "%s-%s.json" % (
        hashlib.sha1(os.path.abspath(git_dir).encode("utf-8")).hexdigest(), safe))


def _stopfailure_reset(text, now):
    """Epoch seconds from "retry after 120 seconds" or "resets 8:10pm (UTC)"; None when no time is found.
    shortcut: a clock time is read as UTC unless it names no zone (then local); other zone names are not understood."""
    m = re.search(r"retry[- ]after\D{0,3}(\d+)\s*(second|sec|s\b|minute|min|m\b|hour|h\b)?", text, re.I)
    if m:
        unit = (m.group(2) or "s").lower()
        return int(now + int(m.group(1)) * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1))
    m = re.search(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d\d))?\s*([ap]m)?(?:\s*\((\w+)\))?", text, re.I)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm:
        hour = hour % 12 + (12 if ampm == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    utc = (m.group(4) or "").upper() in ("UTC", "GMT")
    day = time.gmtime(now) if utc else time.localtime(now)
    base = (now - day.tm_hour * 3600 - day.tm_min * 60 - day.tm_sec) + hour * 3600 + minute * 60
    return int(base if base > now else base + 86400)


def event_stopfailure():
    """StopFailure (#648): leave <config>/house-rules-steps/stopfailure-<session>.json for tools/overnight.sh:
    {error, kind: rate_limit|crash, reset_at: epoch or null, at}. Never raises; says so on stderr when it cannot."""
    try:
        raw = read_payload()
        payload = json.loads(raw) if raw else None
        if not isinstance(payload, dict):
            sys.stderr.write("house-rules stopfailure: payload missing or not a JSON object; wrote no file.\n")
            return 0
        err = str(payload.get("error") or "")
        text = " ".join(str(payload.get(k) or "") for k in ("error_details", "last_assistant_message"))
        rate = re.search(r"rate[ _-]?limit|usage[ _-]?limit|\b429\b|resets", err + " " + text, re.I)
        now = time.time()
        rec = {"error": err, "kind": "rate_limit" if rate else "crash",
               "reset_at": _stopfailure_reset(text, now) if rate else None, "at": int(now)}
        cfg = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        safe = re.sub(r"[^0-9A-Za-z_-]", "_", str(payload.get("session_id") or "unknown"))[:100]
        d = os.path.join(cfg, "house-rules-steps")
        os.makedirs(d, exist_ok=True)
        _write_atomic(os.path.join(d, "stopfailure-%s.json" % safe), json.dumps(rec))
    except Exception as exc:
        sys.stderr.write("house-rules stopfailure: could not record the failure: %s\n" % exc)
    return 0


def _steps_hash(steps):
    return hashlib.sha256(json.dumps(steps, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


_FINISH_STEPS = (("docs", "docs written"), ("pictures", "before-and-after pictures"), ("tests", "tests pass"),
                 ("qa", "QA page built and stamped"))


def record_steps(git_dir, feature, plan_json_path, session_id):
    """#639: copy the build plan's Step rows and test_command into the stage file (state["steps"][session_id])
    and an outside copy. Returns a note; a plan with no checks is exempt and writes nothing."""
    try:
        with open(plan_json_path, encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, ValueError) as exc:
        return "steps not recorded: could not read %s (%s)" % (plan_json_path, exc)
    rows = [c for c in plan.get("changes") or [] if isinstance(c, list) and len(c) > 7
            and str(c[1]).startswith("Step ") and isinstance(c[7], str) and c[7].strip()]
    if not rows:
        return "this plan has no step checks, so the feature is exempt from the step list"
    steps = [{"n": i + 1, "title": str(c[1]), "check": c[7], "state": "open"} for i, c in enumerate(rows)]
    fc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "finish_checks.py")
    for which, title in _FINISH_STEPS:  # #647: four required finish-line steps, in the sha, never parked or replaced
        steps.append({"n": len(steps) + 1, "title": "Finish: " + title, "state": "open",
                      "check": "python3 %s %s %s" % (shlex.quote(fc), which, shlex.quote(feature))})
    rec = {"feature": feature, "test_command": plan.get("test_command") or "", "steps": steps,
           "sha256": _steps_hash(steps), "at": time.time()}  # #641: a replace needs a verdict newer than this
    state, problem = _loop_read(git_dir)
    if problem:
        return "steps not recorded: " + problem
    state.setdefault("steps", {})[session_id] = rec
    _loop_write(git_dir, state)
    out = _steps_outside(git_dir, session_id)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    _write_atomic(out, json.dumps(rec))
    return "recorded %d step(s) with checks for this session" % len(steps)


def steps_integrity(git_dir, feature, session_id):
    """A problem string when the stage file's step hash differs from the outside copy (or that copy is gone), else ""."""
    state, _ = _loop_read(git_dir)
    rec = ((state or {}).get("steps") or {}).get(session_id)
    if not rec:
        return ""
    out = _steps_outside(git_dir, session_id)
    try:
        with open(out, encoding="utf-8") as f:
            outer = json.load(f)
    except (OSError, ValueError):
        return "the step list is in the stage file but its outside copy %s is missing or unreadable" % out
    if outer.get("sha256") != rec.get("sha256") or _steps_hash(rec.get("steps")) != rec.get("sha256"):
        return "the step list in the stage file differs from its outside copy (an older stage file was restored?)"
    return ""


def steps_status(git_dir, feature, session_id, current_fp):
    """#646: {n: "done"|"open"|"stale"}. done only when the step is done AND its stored fp equals current_fp;
    stale = was done but the tree changed (or current_fp is "slow"); open = never passed or last run failed."""
    state, _ = _loop_read(git_dir)
    rec = ((state or {}).get("steps") or {}).get(session_id) or {}
    if rec.get("feature") not in (None, feature):
        return {}
    out = {}
    for s in rec.get("steps") or []:
        if s.get("state") != "done":
            out[s["n"]] = "open"
        else:
            out[s["n"]] = "done" if current_fp != "slow" and s.get("fp") == current_fp else "stale"
    return out


def _parked_steps(top, feature, steps):
    """Step numbers named in a Parked-decisions row (P<n>) of the feature's ledger, by title or "step N"."""
    ledger = os.path.join(top, "docs", "qa", feature.lower().replace(" ", "-").replace("/", "-"), "ledger.md")
    if not os.path.isfile(ledger):
        return set()  # no ledger yet: nothing is parked
    try:
        text = _read_text(ledger)
    except OSError as exc:
        sys.stderr.write("house-rules: could not read the ledger to see parked steps (%s), so none count as parked.\n"
                         % type(exc).__name__)
        return set()
    cells = [m.group(1).lower() for m in re.finditer(r"^\| P\d+ \| (.*?) \|", text, re.M)]
    return {s["n"] for s in steps if any(s["title"].lower() in c or re.search(r"\bstep %d\b" % s["n"], c) for c in cells)}


def steps_unfinished(git_dir, payload):
    """#647: titles of the steps still open (not done at the current tree, not parked) for this session;
    None when there is no step list, so the step rule does not apply."""
    try:
        data = json.loads(payload)
        sid = str(data.get("session_id") or "")
    except (ValueError, AttributeError) as exc:
        sys.stderr.write("house-rules: the step check could not read the payload (%s), so no step blocks this stop.\n"
                         % type(exc).__name__)
        return None
    state, _ = _loop_read(git_dir)
    rec = ((state or {}).get("steps") or {}).get(sid)
    if not rec or not rec.get("steps"):
        return None
    try:
        top = subprocess.run(["git", "-C", data.get("cwd") or ".", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "acceptance.py"),
                            "tree", "--root", top], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
        fp = r.stdout.strip() if r.returncode == 0 else "slow"
    except (OSError, subprocess.SubprocessError):
        return ["the tree could not be fingerprinted"]  # could not tell: counts as unfinished
    status = steps_status(git_dir, rec.get("feature"), sid, fp)
    parked = _parked_steps(top, rec.get("feature") or "", rec["steps"])
    return [s["title"] for s in rec["steps"] if status.get(s["n"]) != "done" and s["n"] not in parked
            and not s.get("stuck")]  # #640: a stuck step no longer blocks (steps_stuck lists it for the QA page)


def steps_stuck(git_dir, payload):
    """#640: titles of the steps the stop check marked stuck for this session (not done); [] when none or no list."""
    try:
        sid = str(json.loads(payload).get("session_id") or "")
    except (ValueError, AttributeError) as exc:
        sys.stderr.write("house-rules: steps_stuck could not read the payload (%s), so it lists none.\n" % type(exc).__name__)
        return []
    rec = ((_loop_read(git_dir)[0] or {}).get("steps") or {}).get(sid) or {}
    return [s["title"] for s in rec.get("steps") or [] if s.get("stuck") and s.get("state") != "done"]


def _steps_rec(payload):
    """(git_dir, state, rec, sid, data) for this session's step list, or None when it has none."""
    try:
        data = json.loads(payload)
        sid = str(data.get("session_id") or "")
    except (ValueError, AttributeError) as exc:
        sys.stderr.write("house-rules: the step stop check could not read the payload (%s), so it did not run.\n"
                         % type(exc).__name__)
        return None
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return None
    state, _ = _loop_read(git_dir)
    rec = ((state or {}).get("steps") or {}).get(sid)
    return (git_dir, state, rec, sid, data) if rec and rec.get("steps") else None


def judge_blocked(payload, mark=False):
    """#640: whether the model judge already blocked this step set; mark=True records its first block.
    False (and no write) when the session has no step list."""
    got = _steps_rec(payload)
    if not got:
        return False
    git_dir, state, rec, _, _ = got
    if mark and not rec.get("judge_blocked"):
        rec["judge_blocked"] = True
        _loop_write(git_dir, state)
    return bool(rec.get("judge_blocked"))


def step_stop_check(payload, reply_text):
    """#640: (block reason or None, systemMessage or None). Runs on every stop: blocks while a step of this
    session's list is open, even with no reply text. NEEDS YOU exempts nothing; only a parked step does.
    A `QUESTION FOR YOU:` line passes when somebody is present. After 3 no-progress blocks for one step it
    is marked stuck and stops blocking."""
    got = _steps_rec(payload)
    if not got:
        return None, None
    git_dir, state, rec, sid, data = got
    open_steps = steps_unfinished(git_dir, payload)
    if not open_steps:
        return None, None
    if re.search(r"^QUESTION FOR YOU:", reply_text or "", re.M) and not core.nobody_present(payload):
        return None, None
    msgs = None
    tp = data.get("transcript_path")
    if tp:
        try:
            msgs = core._user_message_count(tp)
        except (OSError, ValueError) as exc:
            sys.stderr.write("house-rules: the step stop check could not count aj's messages (%s), so its counters "
                             "do not reset on a new message.\n" % type(exc).__name__)
    nxt = next(s for s in rec["steps"] if s["title"] == open_steps[0])
    n = str(nxt["n"])
    head = subprocess.run(["git", "-C", data.get("cwd") or ".", "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True).stdout.strip()
    done = sum(1 for s in rec["steps"] if s.get("state") == "done")
    last = rec.get("last_block") or {}
    blocks = rec.setdefault("blocks", {})
    if last.get("msgs") != msgs or last.get("head") != head or last.get("done") != done:
        blocks.clear()  # a new message from aj, a commit or a closed step is progress
    if blocks.get(n, 0) >= 3:
        nxt["stuck"] = True
        blocks.pop(n, None)
        rec["last_block"] = {"msgs": msgs, "head": head, "done": done}
        _loop_write(git_dir, state)
        open_steps = steps_unfinished(git_dir, payload)
        if not open_steps:
            return None, ("house-rules: step %s ('%s') had 3 blocks with no progress, so it is marked stuck and the "
                          "stop is allowed; it counts as not done on the QA page." % (n, nxt["title"]))
        nxt = next(s for s in rec["steps"] if s["title"] == open_steps[0])
        n = str(nxt["n"])
    blocks[n] = blocks.get(n, 0) + 1
    rec["last_block"] = {"msgs": msgs, "head": head, "done": done}
    _loop_write(git_dir, state)
    fc = "python3 %s" % os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ledger_note.py")
    feat = rec.get("feature") or "<feature>"
    return ("House rules, step list: not finished. Next open step: %s. Run `%s check %s --step %s --start`, then "
            "`%s check %s --step %s --poll`, until it passes. NEEDS YOU in a reply does not end the turn. A hard "
            "stop must be parked with `%s park %s --step %s --category ... --tried ...`. Open: %s. (block %d of 3 "
            "for this step before it counts as stuck)"
            % (nxt["title"], fc, feat, n, fc, feat, n, fc, feat, n, "; ".join(open_steps), blocks[n])), None


_STEP_RESULT_RE = re.compile(r"RESULT: (pass|fail) step (\d+) fp=(\S+)")


def _step_run_passed(git_dir, sid, n):
    """True when the run file ledger_note.py check left for step n holds exit code 0 (a typed RESULT line alone is not proof)."""
    out = _steps_outside(git_dir, sid)
    rc = os.path.join(os.path.dirname(out), "runs", os.path.basename(out)[:-5] + "-step%d.rc" % n)
    if not os.path.isfile(rc):
        return False
    try:
        return _read_text(rc).strip() == "0"
    except OSError as exc:
        sys.stderr.write("house-rules: could not read the step run file (%s).\n" % type(exc).__name__)
        return False


def _record_step_result(data):
    """#646, registered under promptran (runs on PostToolUse and PostToolUseFailure): a Bash call of
    `ledger_note.py check` whose output has a RESULT line marks that step done (pass) or open (fail)."""
    ti = data.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else ""
    # the live run showed an agent calls it through a shell variable (python3 "$S" check ...), so match the words
    # of the call, not the script name; a pass is then verified against the run file the poll leaves behind
    if not isinstance(cmd, str) or "check" not in cmd or "--poll" not in cmd:
        return ""
    m = _STEP_RESULT_RE.search(json.dumps([data.get("tool_response"), data.get("error")]).replace("\\n", "\n"))
    if not m:
        sys.stderr.write("house-rules: no RESULT line in the step check output, so the step stays open.\n")
        return ""
    gd = core._git_dir(data.get("cwd") or os.getcwd())
    sid = str(data.get("session_id") or "")
    if not gd:
        return ""
    state, problem = _loop_read(gd)
    rec = ((state or {}).get("steps") or {}).get(sid)
    if problem or not rec:
        sys.stderr.write("house-rules: step result not recorded (%s).\n" % (problem or "no step list for this session"))
        return ""
    for s in rec["steps"]:
        if s.get("n") == int(m.group(2)):
            if m.group(1) == "pass" and not _step_run_passed(gd, sid, s["n"]):
                sys.stderr.write("house-rules: step %s says pass but its run file does not hold exit code 0, so it "
                                 "stays open.\n" % m.group(2))
                return ""
            s.update(state="done" if m.group(1) == "pass" else "open", fp=m.group(3), at=int(time.time()))
            _loop_write(gd, state)
            return ""
    sys.stderr.write("house-rules: step %s is not in the step list.\n" % m.group(2))
    return ""


_VERDICT_RE = re.compile(r"^\W*VERDICT:\s*clean\b", re.I | re.M)
_PAGE_PATH_RE = re.compile(r"docs/plans/[\w./-]+?\.(?:page\.json|html)")
_STAMP_KEYS = ("reviewed", "reviewStamp", "review_stamp", "stamp")  # #641: make_page keeps the stamp in the html; any in the json is not part of the page


def page_hash(path):
    """#641: sha256 of a page's .page.json with any review-stamp key removed; raises OSError/ValueError."""
    with open(path, encoding="utf-8") as f:
        page = json.load(f)
    for k in _STAMP_KEYS:
        page.pop(k, None)
    return hashlib.sha256(json.dumps(page, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _find_page(texts, roots):
    """The newest-mentioned docs/plans page (as its .page.json) that exists under one of roots, else ""."""
    for text in texts:
        for rel in reversed(_PAGE_PATH_RE.findall(text or "")):
            rel = re.sub(r"\.html$", ".page.json", rel)
            for r in roots:
                if os.path.isfile(os.path.join(r, rel)):
                    return os.path.join(r, rel)
    return ""


def record_verdict(payload, agent_type, report, prompt_text, session_id):
    """#641: a reviewer's final report with a `VERDICT: clean` line is stored as state["verdicts"][page_hash]
    = {page, mode, at}; then, when nobody is present, the hook self-approves the stage (see _self_approve).
    Runs even when helpers are off. Returns a note ("" when it is not a clean reviewer verdict); problems go to stderr."""
    if (agent_type or "").split(":")[-1] != "reviewer" or not _VERDICT_RE.search(report or ""):
        return ""
    cwd = (core._field(re.compile(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"'), payload) or os.getcwd()).replace("\\\\", "\\")
    gd = core._git_dir(cwd)
    if not gd:
        sys.stderr.write("house-rules: reviewer verdict not stored: no git directory found from %s.\n" % cwd)
        return ""
    roots = [cwd, os.path.dirname(_loop_dir(gd))]
    page = _find_page([report, prompt_text], roots)
    if not page:
        sys.stderr.write("house-rules: reviewer verdict not stored: could not identify the page (no docs/plans path "
                         "in its report or prompt that exists).\n")
        return ""
    try:
        h = page_hash(page)
        with open(page, encoding="utf-8") as f:
            ptype = json.load(f).get("pageType")
    except (OSError, ValueError, AttributeError) as exc:
        sys.stderr.write("house-rules: reviewer verdict not stored: could not read %s (%s).\n" % (page, exc))
        return ""
    mode = {"proposal": "page", "build-plan": "plan"}.get(ptype)
    if not mode:
        sys.stderr.write("house-rules: reviewer verdict not stored: %s is pageType %r, not a design or build-plan page.\n"
                         % (page, ptype))
        return ""
    state, problem = _loop_read(gd)
    if problem:
        sys.stderr.write(problem + " The verdict was not stored.\n")
        return ""
    state.setdefault("verdicts", {})[h] = {"page": page, "mode": mode, "at": time.time()}
    _loop_write(gd, state)
    note = "verdict stored for %s (%s)" % (os.path.basename(page), h[:12])
    if core.nobody_present(payload):
        note += "; " + _self_approve(gd, state, page, h, ptype, session_id)
    return note


def _self_approve(gd, state, page, h, ptype, session_id):
    """#641: nobody present + a stored clean verdict for this page's current hash: Design -> Plan on a design
    page, Plan -> Build on a build-plan page. Recorded in state["auto_approvals"], never "approvals", so the
    newest-approval marker is untouched. Never QA or Close. Returns a note."""
    if state.get("verdicts", {}).get(h, {}).get("page") != page or page_hash(page) != h:
        return "no self-approval: the stored verdict does not match this page"
    stage = state.get("stage")
    if (stage, ptype) == ("design", "proposal"):
        new = "plan"
    elif (stage, ptype) == ("plan", "build-plan"):
        new = "build"
    else:
        return "no self-approval: stage %s does not take a %s page" % (stage, ptype)
    with open(page, encoding="utf-8") as f:
        title = str(json.load(f).get("title") or "")
    feature = state.get("feature") or _loop_name(title.split(":")[0])
    extra = ""
    if new == "build":
        steps = record_steps(gd, feature, page, session_id)
        state, problem = _loop_read(gd)  # record_steps wrote the stage file; re-read it
        if problem:
            return "no self-approval: " + problem
        extra = "; " + steps
    state["feature"], state["stage"], state["skip"] = feature, new, False
    if new == "plan":
        state["redo"] = False
    state.setdefault("auto_approvals", []).append(
        {"stage": "Design approved" if new == "plan" else "Build plan approved", "page": page, "hash": h,
         "at": int(time.time()), "by": "auto-unattended"})
    _loop_write(gd, state)
    top = os.path.dirname(_loop_dir(gd))
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        import ledger_note
        undo = ("set \"stage\" in .claude/%s back to \"%s\" and delete this entry from auto_approvals"
                % (LOOP_FILE, "design" if new == "plan" else "plan"))
        ledger_note.add_row(top, feature, "S", "Verdict hash", (
            LOOP_STAGE_NAMES[state["stage"]], os.path.relpath(page, top).replace(os.sep, "/"), h,
            time.strftime("%Y-%m-%d %H:%M:%S"), undo))
    except (OSError, ValueError, ImportError) as exc:
        sys.stderr.write("house-rules: self-approval done but the ledger S row was not written (%s).\n" % exc)
    return "self-approved: stage is now %s%s" % (LOOP_STAGE_NAMES[new], extra)


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


def _loop_owe_log(state, top, label, name, owed):
    """Speed switches 6A: a missing decisions log is owed work, not a refusal."""
    if _loop_unlogged(state, top, label, name):
        owed.append("create the decisions log (%s) and log this stage" % LOOP_LOG.replace(os.sep, "/"))


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
                               r"|\s+[-–—]\s|,\s|\s*:\s*\d+[A-Za-z*](?:\s|$)")  # ",\s": #535 QA, aj's "QA failed: X, why"


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


def _steps_to_qa(git_dir, payload):
    """#647: True when nobody is present and the step list has no unfinished step (done at this tree, or parked)."""
    return core.nobody_present(payload) and steps_unfinished(git_dir, payload) == []


def _loop_to_qa(state, labels, steps_done=False):
    """Build becomes QA once every issue says needs review and none says in progress. True if it moved.

    #504: after "QA failed" the stage is Build while every issue still says needs review. That is not a
    finished build, so the move waits (state["reopened"]) until an issue has been seen back at in progress."""
    if state.get("reopened"):
        if state["stage"] != "build" or any(LOOP_WORKING in (l or []) for l in labels.values()):
            state["reopened"] = False
        return False
    # #647: nobody present and every step done or parked moves Build to QA without labels or a pull request
    if state["stage"] == "build" and (steps_done or (labels and not _loop_wrong(labels, LOOP_REVIEW))):
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


_LOOP_CLOSEAPPR_RE = re.compile(r"\bclose\s+approved\s*:[ \t]*([^\n]*)", re.IGNORECASE)


_LOOP_CA_REF_RE = re.compile(r"(?:([\w.-]+/[\w.-]+))?#(\d+)")


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
    m = _LOOP_CLOSEAPPR_RE.search(text)  # #551: "Close approved: #N[, #M]" or "Close approved: milestone N[, M]"
    if m:
        body = m.group(1)
        mm = re.match(r"\s*(?:([\w.-]+/[\w.-]+)\s+)?milestones?\s+#?(\d+(?:[\s,]+(?:and\s+)?#?\d+)*)", body,
                      re.IGNORECASE)
        if mm:
            new = [{"repo": mm.group(1) or "", "milestone": int(n)} for n in re.findall(r"\d+", mm.group(2))]
        else:
            new = [{"repo": r, "number": int(n)} for r, n in _LOOP_CA_REF_RE.findall(body)]
        if not new:
            notes.append('Design loop: aj wrote "Close approved:", but no "#N" issue or "milestone N" was found, '
                         "so nothing was recorded.")
        else:
            if not isinstance(state.get("close_approved"), list):
                state["close_approved"] = []
            state["close_approved"].extend(x for x in new if x not in state["close_approved"])
            notes.append('Design loop: aj wrote "Close approved:". Recorded %d close approval(s): %s. No stage '
                         "moved." % (len(new), ", ".join(("milestone %s" % x["milestone"]) if "milestone" in x
                                                         else "#%s" % x["number"] for x in new)))
    return " ".join(notes)


def _loop_apply(state, text, top):
    carry = _loop_continue_apply(state, text, top)  # #479: first, so "Continue from: x. Build plan approved: y" works
    sweep_note = _loop_sweep_apply(state, text)
    issues_note = _loop_issues_for_apply(state, text, top)
    from house_rules import bigfiles  # #511: "LFS approved: <path>", beside the other phrases
    note = _loop_apply_stage(state, bigfiles.without_lfs_lines(text), top)  # its word "approved" is not a stage approval
    lfs_note = bigfiles.lfs_apply(state, text, top)
    return " ".join(n for n in (carry, sweep_note, issues_note, note, lfs_note) if n)


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


def _plan_unreviewed(top, name):
    """#600, A2: "" when docs/plans holds a build-plan page for this feature with a current review stamp; else
    why the combined approval cannot carry the plan. A page that cannot be read counts as unreviewed."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    plans = os.path.join(top or "", "docs", "plans")
    try:
        names = sorted(n for n in os.listdir(plans) if n.lower().endswith("-plan.html") and slug and slug in n.lower())
    except OSError:
        names = []
    if not names:
        return 'no build plan page for "%s" (a docs/plans file ending -plan.html and naming it) was found' % name
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        import page_criteria
        with open(os.path.join(plans, names[-1]), encoding="utf-8", newline="") as f:
            problem = page_criteria.stamp_problem(f.read())
    except Exception as exc:
        return "the plan page could not be checked (%s: %s)" % (type(exc).__name__, exc)
    return "%s has %s" % (names[-1], problem) if problem else ""


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
    notes = []
    for order, piece in pieces:  # D5: in the order aj wrote them
        if order == 1:  # #600, A2: the combined line carries the plan only when its page was reviewed
            m = _LOOP_PLAN_RE.search(piece)
            why = _plan_unreviewed(top, _loop_name(m.group(1))) if m else ""
            if why:
                notes.append('Design loop: aj wrote "Build plan approved" in the same message as another approval, '
                             "but %s, so the build plan approval was not applied. Run the reviewer on the plan "
                             "page and rebuild it with --reviewed, or aj approves the plan in its own message." % why)
                continue
        notes.append(_loop_apply_one(state, piece, top))
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
    owed = ["these issues should say `needs review`: %s" % "; ".join(wrong)] if wrong else []  # 6A
    _loop_owe_log(state, top, "QA " + verdict, name, owed)
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
    if owed:
        tail += " aj's approval counts as sent, so fix these in this turn without asking aj again: %s." % "; ".join(owed)
    return ('Design loop: aj wrote "QA %s: %s". That feature moved, not the current one.%s The current feature '
            '"%s" is unchanged: stage %s.' % (verdict, name, tail, state.get("feature") or "(none)",
                                              LOOP_STAGE_NAMES[state["stage"]]))


def _loop_apply_one(state, text, top):
    """Move the stage for one approval phrase (or none). Returns a note for the model, or "" when the
    text approves nothing. Mutates state."""
    stage, feature = state["stage"], state.get("feature") or ""
    approval, issues_note = None, ""
    owed = []  # speed switches 6A: what an approval is missing becomes the agent's to-do, never a refusal
    m = _LOOP_PLAN_RE.search(text)
    if m:
        name = _loop_name(m.group(1))
        if stage in ("build", "qa"):
            return ('Design loop: aj wrote "Build plan approved: %s", but the stage is already %s, so there was '
                    "nothing to move." % (name, LOOP_STAGE_NAMES[stage]))
        if stage == "plan" and feature and not _loop_same(name, feature):
            owed.append('aj wrote "%s" but the feature in Plan is "%s", so it was approved as "%s"; say so to aj'
                        % (name, feature, feature))
            name = feature
        elif stage != "plan":
            owed.append("no design was approved first, so log this feature's decisions in the decisions log")
            if feature and stage != "done":
                _loop_keep_feature(state, feature, stage, any_stage=True)
            state["feature"], state["issues"] = name, []
            state.pop("parent", None)
        state["issues"], issues_note = _loop_feature_issues(state, top)
        have = sum(1 for i in state.get("issues", []) if isinstance(i, dict) and i.get("labelled"))
        if have < ISSUES_NEEDED:
            owed.append("the feature has %d labelled issue(s) on record and needs %d (one for the feature and a "
                        "sub-issue per step, labelled `%s` and `%s`): open or label them"
                        % (have, ISSUES_NEEDED, ISSUES_LABEL, LOOP_WORKING))
        labels, src = _loop_labels(state)
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if wrong:
            owed.append("label these `%s`: %s%s" % (LOOP_WORKING, "; ".join(wrong), " (" + src + ")" if src else ""))
        _loop_owe_log(state, top, "Build plan approved", name, owed)
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
                    owed.append("label these `%s`: %s" % (LOOP_WORKING, "; ".join(wrong)))
            _loop_owe_log(state, top, "Design approved", name, owed)
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
                        if wrong:
                            owed.append("these issues should say `needs review`: %s" % "; ".join(wrong))
                elif stage != "qa":
                    return ('Design loop: aj wrote "QA %s: %s", but the stage is %s, so nothing moved. QA '
                            "follows a build." % (verdict, name, LOOP_STAGE_NAMES[stage]))
                _loop_owe_log(state, top, "QA " + verdict, name, owed)
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
        if owed:
            note += (" aj's approval counts as sent, so fix these in this turn without asking aj again: %s."
                     % "; ".join(owed))
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
            hand = ("Hand each approved step to @house-rules:builder (one per issue; at most two running) unless "
                    "aj said to build it yourself; helpers build only approved steps and never design or approve. "
                    if _builders_enabled() else "Builders are off, so build it yourself in this conversation. ")
            note += (" Code edits are open for the approved steps while every issue says `%s`. %sWhen "
                     "the build is ready for aj, swap every issue's `%s` for `%s`: that starts QA."
                     % (LOOP_WORKING, hand, LOOP_WORKING, LOOP_REVIEW))
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
        if _st.get("stage") == "build" and _asks_aj(reply_text) and not core.nobody_present(payload):  # #637
            if "[HARD STOP]" in _MD_FENCED_BLOCK_RE.sub("", reply_text or "").strip().split("\n\n")[-1]:
                if not _st.get("held"):
                    _st["held"] = True
                    changed = True
            else:  # #598: a plain question in Build parks instead of holding
                trace_lines.append("Build stage: record a reversible choice with ledger_note.py decide and end the "
                                   "reply with the next step; park (needs --category and --tried) and [HARD STOP] "
                                   "only for what cannot be undone.")
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
        was = state.get("stage")
        note = _loop_apply(state, text, top)
        if json.dumps(state, sort_keys=True) != before:
            _loop_write(git_dir, state)
        if was != "build" and state.get("stage") == "build" and "Build plan approved" in note:
            try:
                sid = str(json.loads(payload).get("session_id") or "")
            except (ValueError, AttributeError):
                sid = ""
            note += " Steps: " + _record_steps_for(top, git_dir, state.get("feature") or "", sid) + "."
        return note
    except Exception as exc:
        return "house-rules: the design-loop check hit an error (%s: %s), so this message moved nothing." % (
            type(exc).__name__, exc)


def _record_steps_for(top, git_dir, feature, session_id):
    import glob
    plans = []
    for p in glob.glob(os.path.join(top, "docs", "plans", "*.page.json")):
        try:
            with open(p, encoding="utf-8") as f:
                if json.load(f).get("pageType") == "build-plan":
                    plans.append(p)
        except (OSError, ValueError):
            continue
    if not plans:
        return "no build plan .page.json found, so no step list was recorded"
    return record_steps(git_dir, feature, max(plans, key=os.path.getmtime), session_id)


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
        "aj's own message. Record a reversible choice with `ledger_note.py decide` and keep going; `ledger_note.py park` (needs "
        "--category and --tried) is only for a hard stop: a "
        "[HARD STOP] (cannot be undone, or touches money, secrets or other people) is reported back as a "
        "question. Code edits are refused outside Build." % (
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
    if _loop_to_qa(state, labels, _steps_to_qa(git_dir, payload)):
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
    nobody = core.nobody_present(payload)  # #637: no question hold, no GitHub-label refusals
    if state["stage"] == "build" and state.get("held") and not nobody:
        return ("House rules, design loop: the last reply asked aj a question, so code edits wait for their "
                "answer."), None
    if state["stage"] == "build":
        labels, src = _loop_labels(state, record=False)
        if src and not nobody:  # D9: GitHub could not be read, and the record of an old branch is not evidence
            return ("House rules, design loop: code edits in Build need every issue of \"%s\" labelled `%s`, but "
                    "this hook could not read GitHub (%s), so the edit is refused. It will work once gh can read the issues."
                    % (state.get("feature") or "", LOOP_WORKING, src)), None
        reopened = state.get("reopened")
        if _loop_to_qa(state, labels, _steps_to_qa(git_dir, payload)):
            _loop_write(git_dir, state)
            return "House rules, design loop:" + _LOOP_QA_NOTE, None
        if state.get("reopened") != reopened:  # #504: the issues are back at in progress
            _loop_write(git_dir, state)
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if not wrong or nobody:
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
            if any(a.lower() in COMPLETED_LABELS for a in list(add) + list(set_to or [])):
                mine = state.setdefault("self_completed", [])
                if not any(x.get("repo", "").lower() == repo.lower() and x.get("number") == number for x in mine):
                    mine.append({"repo": repo, "number": number})
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


def _pr_open_steps_deny(payload, raw):
    """#647: a plain deny reason while nobody is present and a step is still open (not done, not parked); else None."""
    if not core.nobody_present(raw):
        return None
    _, git_dir = _issues_locate(_payload_cwd(raw))
    open_steps = steps_unfinished(git_dir, raw) if git_dir else None
    if not open_steps:
        return None
    return ("House rules: no pull request yet. These steps of the build plan are not finished: %s. Run their checks "
            "(ledger_note.py check <feature> --step N --start, then --poll) until each passes, or park a real "
            "question with ledger_note.py park; then open the pull request." % "; ".join(open_steps))


def _guardgithub_issue_checks(payload, raw):
    """The two checks event_guardgithub used to run first (the safe git part now loops over this
    through core.GITHUB_WRITE_HOOKS): True when the call was handled and answered."""
    # #248: an issue made with the GitHub tool needs its three sections, like one made with gh.
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if re.match(r"^mcp__(github|GitHub)__(create|update)_pull_request$", str(payload.get("tool_name") or "")):
        why = _pr_open_steps_deny(payload, raw)
        if why:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": why}})
            return True
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
    "evidence (the label that allowed it, or the QA message and the merged pull request link, or the sweep "
    "approval and the replacing issue), add the label `AjsAgent completed this` (`gh api repos/%s/issues/%d/labels -f "
    "\"labels[]=AjsAgent completed this\"`) and remove `in progress` (`gh api -X DELETE "
    "repos/%s/issues/%d/labels/in%%20progress`)."
)


def _close_repo_match(a, b):
    return not a or not b or a.lower() == b.lower()


CLOSE_CACHE_SECONDS = 60  # how long one read of a repo's open issues serves every close
CLOSE_ISSUES_FILE_ENV = "HOUSE_RULES_CLOSE_ISSUES_FILE"  # tests: JSON {"owner/repo#n": {"labels": [...], "milestone": null}}
_CLOSE_FACTS_JQ = "{labels: [.labels[].name], milestone: .milestone.number}"


def _close_gh(args):
    """The stdout of `gh <args>`; raises RuntimeError saying why when it fails."""
    import subprocess
    if not shutil.which("gh"):
        raise RuntimeError("gh is not installed")
    try:
        proc = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh took longer than %d seconds" % LOOP_GH_SECONDS)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(detail[0] if detail else "gh exited %d" % proc.returncode)
    return proc.stdout


def _close_issue_facts(repo, number, git_dir):
    """(facts, problem): facts is {"labels": [names], "milestone": number or None} for issue `number` of `repo`
    (the checkout's own repo when empty); problem is "" on success, else a sentence saying why GitHub could not
    be read (facts None). One REST call lists the repo's open issues and is cached in
    <git_dir>/house-rules-issue-cache.json for CLOSE_CACHE_SECONDS; an issue not in a fresh list is read alone."""
    number = int(number)
    if not repo:
        repo, why = _origin_slug(os.path.dirname(os.path.abspath(git_dir)))
        if not repo:
            return None, why or "House rules could not tell which GitHub repo this is: the checkout has no GitHub origin."
    stand_in = os.environ.get(CLOSE_ISSUES_FILE_ENV)
    if stand_in:
        try:
            with open(stand_in, "r", encoding="utf-8") as f:
                row = json.load(f)["%s#%d" % (repo, number)]
            return {"labels": [str(n) for n in row["labels"]], "milestone": row.get("milestone")}, ""
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return None, "House rules could not read issue %s#%d from %s (%s)." % (repo, number, stand_in, exc)
    path = os.path.join(git_dir, "house-rules-issue-cache.json")
    key = repo.lower()
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if not isinstance(cache, dict):
                cache = {}
        except FileNotFoundError:
            cache = {}
        except ValueError:
            cache = {}  # a damaged cache is replaced by the read below
        entry = cache.get(key)
        fresh = (isinstance(entry, dict) and isinstance(entry.get("issues"), dict)
                 and 0 <= time.time() - float(entry.get("at", 0)) < CLOSE_CACHE_SECONDS)
        if not fresh:
            out = _close_gh(["api", "repos/%s/issues?state=open&per_page=100" % repo, "--paginate", "--jq",
                             ".[] | {number, labels: [.labels[].name], milestone: .milestone.number}"])
            issues = {}
            for line in out.splitlines():
                if line.strip():
                    r = json.loads(line)
                    issues[str(r["number"])] = {"labels": r["labels"], "milestone": r.get("milestone")}
            entry = cache[key] = {"at": time.time(), "issues": issues}
        if str(number) not in entry["issues"]:
            one = json.loads(_close_gh(["api", "repos/%s/issues/%d" % (repo, number), "--jq", _CLOSE_FACTS_JQ]))
            entry["issues"][str(number)] = {"labels": one["labels"], "milestone": one.get("milestone")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        row = entry["issues"][str(number)]
        return {"labels": list(row["labels"]), "milestone": row["milestone"]}, ""
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return None, "House rules could not read issue %s#%d from GitHub (%s)." % (repo, number, exc)


COMPLETED_LABELS = ("ajsagent completed this", "claude completed this")


def _close_check(repo, number, reason, state, git_dir=None):
    ok, why = _close_records(repo, number, reason, state)
    if ok or git_dir is None or (reason or "completed").strip().lower().replace(" ", "_") != "completed":
        return ok, why
    return _close_by_labels(repo, number, state, git_dir, why)


def _close_records(repo, number, reason, state):
    """(allowed, reason_text) for closing issue `number` of `repo` with state reason `reason`
    ("completed", "not_planned" or "" for none), from the design-loop `state` (#363). When the QA and sweep
    records do not allow it and `git_dir` is given, a completed close is also allowed by the issue's own
    GitHub labels (#550): needs review / in review, or a completed label a person set; never in a milestone."""
    reason = (reason or "completed").strip().lower().replace(" ", "_")
    if isinstance(state, dict) and any(isinstance(x, dict) and x.get("number") == number
                                       and _close_repo_match(repo, x.get("repo", ""))
                                       for x in state.get("close_approved") or []):
        return True, "aj wrote \"Close approved: #%d\", so #%d may close whatever its labels or milestone" % (
            number, number)  # #551: before any GitHub lookup
    if not _loop_enabled():  # #515: never demand evidence only a switched-off loop can record
        return True, "the design loop is off, so the QA and sweep records it keeps are not required"
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
        miss = next((e["merge_miss"] for e in holders if e.get("merge_miss")), "")
        return False, "#%d's feature passed QA but no merged pull request is recorded since%s" % (
            number, (" (" + miss + ")") if miss else "")
    if sweep:
        return False, "#%d is on the approved sweep list with a different action than completed" % number
    return False, ("no QA pass is recorded for a feature that holds #%d, and it is on no approved sweep or "
                   "named list" % number)


def _close_by_labels(repo, number, state, git_dir, why):
    """(allowed, text) from the issue's GitHub labels (#550), `why` being the QA/sweep refusal to keep in the text."""
    facts, problem = _close_issue_facts(repo, number, git_dir)
    if problem:
        return False, "%s; and the labels could not be checked: %s" % (why, problem.rstrip("."))
    if facts["milestone"]:
        return False, ("%s; and #%d is in milestone %s, so it needs aj's \"Close approved: #%d\"" % (
            why, number, facts["milestone"], number))
    labels = facts["labels"]
    low = {l.lower() for l in labels}
    for want in ("needs review", "in review"):
        if want in low:
            return True, "#%d has the label `%s` and is in no milestone" % (number, want)
    mine = any(isinstance(x, dict) and x.get("number") == number and _close_repo_match(repo, x.get("repo", ""))
               for x in (state.get("self_completed") if isinstance(state, dict) else None) or [])
    done = [l for l in labels if l.lower() in COMPLETED_LABELS]
    if done and not mine:
        return True, "#%d has the label `%s`, set by a person, and is in no milestone" % (number, done[0])
    note = " (the completed label on it was added by the agent itself, which does not count)" if done else ""
    return False, ("%s; and #%d has the labels %s%s, but a close needs `needs review`, `in review`, or `AjsAgent "
                   "completed this` / `Claude completed this` set by a person, and no milestone. aj can write "
                   "\"Close approved: #%d\"" % (why, number, ", ".join("`%s`" % l for l in labels) or "none",
                                                note, number))


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
    if isinstance(state.get("close_approved"), list):
        n = len(state["close_approved"])
        state["close_approved"] = [x for x in state["close_approved"] if not hit(x)]
        changed = changed or len(state["close_approved"]) != n
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
    ok, why = _close_check(repo, number, reason, state, git_dir)
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


_GH_MILESTONE_CLOSE_RE = re.compile(
    _GH_PREFIX + r"api\b(?=[^\n]*(?:-X|--method)[=\s]+[\"']?PATCH)(?=[^\n]*milestones/\d+)"
    r"(?=[^\n]*state\W{0,4}closed)", re.IGNORECASE)


def _milestone_close_decision(cmd, payload):
    """#551: a milestone close needs aj's "Close approved: milestone N"."""
    m = re.search(r"(?:repos/([\w.-]+/[\w.-]+)/)?milestones/(\d+)", cmd)
    repo, n = m.group(1) or "", int(m.group(2))
    ask = 'Ask aj to write "Close approved: milestone %d".' % n
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return ("deny", "House rules, close guard: could not find the project's stage file, so closing "
                "milestone %d is refused. %s" % (n, ask), None)
    state, problem = _loop_read(git_dir)
    if problem:
        return ("deny", "%s Closing milestone %d is refused. %s" % (problem, n, ask), None)
    for x in (state.get("close_approved") or []) if isinstance(state, dict) else []:
        if isinstance(x, dict) and x.get("milestone") == n and _close_repo_match(repo, x.get("repo", "")):
            note = 'aj wrote "Close approved: milestone %d", so this milestone close is allowed.' % n
            return ("allow", note, note)
    return ("deny", "House rules, close guard: refused to close milestone %d: aj has not approved it. %s" % (n, ask),
            None)


def _issues_guard(subject, payload):
    """None when the issue rules have nothing to say about this command, else
    (kind, reason, context) with kind "deny" or "ask"."""
    if not _issues_enabled():
        return None
    cmd = _decoded_command(subject)
    if _GH_PR_CREATE_RE.search(cmd):
        why = _pr_open_steps_deny(None, payload if isinstance(payload, str) else json.dumps(payload))
        if why:
            return ("deny", why, None)
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
    if _GH_MILESTONE_CLOSE_RE.search(cmd):
        return _milestone_close_decision(cmd, payload)
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


_SEND_TOOL = "SendUserFile"
_PAGE_DOCS_RE = re.compile(r"(^|/)docs/.+\.html$", re.IGNORECASE)
_MADE_PAGE_RE = re.compile(r"make_page: wrote (\S+?\.html)")


def _norm_page(path, cwd):
    return os.path.normcase(os.path.abspath(os.path.join(cwd or "", str(path))))


def _pages_unsent(records, cwd):
    """#559: pages under docs/ written or rebuilt this turn with no file send or Artifact publish after
    their last change. A rebuild is a Bash make_page.py build whose result says `make_page: wrote <page>`."""
    results = {}
    for rec in records:
        c = (rec.get("message") or {}).get("content") if isinstance(rec, dict) else None
        for b in c if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                t = b.get("content")
                results[b.get("tool_use_id")] = t if isinstance(t, str) else " ".join(
                    x.get("text", "") for x in t if isinstance(x, dict)) if isinstance(t, list) else ""
    changed, sent = {}, {}
    for i, b in enumerate(core._turn_tool_uses(records)):
        name, inp = b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {}
        if name in ("Write", "Edit"):
            fp = inp.get("file_path") or ""
            if _PAGE_DOCS_RE.search(fp.replace("\\", "/")):
                changed[_norm_page(fp, cwd)] = i
        elif name == "Bash" and "make_page.py" in (inp.get("command") or "") and " build" in inp["command"]:
            for m in _MADE_PAGE_RE.finditer(results.get(b.get("id"), "")):
                if _PAGE_DOCS_RE.search(m.group(1).replace("\\", "/")):
                    changed[_norm_page(m.group(1), cwd)] = i
        elif name == _SEND_TOOL or name == "Artifact":
            for v in _page_candidates(inp):
                sent[_norm_page(v, cwd)] = i
    return sorted(p for p, i in changed.items() if sent.get(p, -1) < i)


def _check_send(ctx):
    """#559: a page written or rebuilt this turn is sent to aj before the turn ends."""
    pages = ctx.get("pages_unsent") or []
    if not pages or _page_escape(ctx) or not _pages_enabled():
        return ""
    if not ctx.get("can_send") and _reply_links_page(ctx.get("reply") or "", ctx.get("cwd") or ""):
        return ""
    return ("send %s with the file-send tool (display render) as the last action"
            % ", ".join(pages))


def _check_editor(ctx):
    if _page_escape(ctx) or not ctx.get("editor_owed"):
        return ""
    if not ctx["editor_owed"].startswith("this reply is"):  # #594: a page owes a review stamp
        return ("spawn @house-rules:reviewer (Agent tool, subagent_type house-rules:reviewer) in PAGE mode, apply "
                "its findings, rebuild with make_page.py build ... --reviewed clean --rounds N (or open-risks "
                "after round 2), then send the page (%s)" % ctx["editor_owed"])
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
    # #530: the work is uploaded and described. Lazy import: safe_git is loaded after this module.
    from house_rules.safe_git import handover_handoff_check
    return handover_handoff_check(ctx.get("written") or [], ctx.get("committed"), ctx.get("cwd"))


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
_PAGE_DENY_BASICS = (
    "House rules, page check: %s is a hand-written page and it misses these basics:\n%s\n"
    "Fix them in the page, or build it instead: python3 %s build <content.json> and use the page it builds. "
    "HOUSE_RULES_LOOP=off turns this check off."
)


def _page_note(text):
    emit({"systemMessage": "house-rules page check: " + text})


def _page_in_plans(path):
    parts = [p for p in re.split(r"[\\/]+", path) if p]
    return any(parts[i] == "docs" and parts[i + 1] == "plans" for i in range(len(parts) - 1))


def _page_deny(page, fails=None, notes=()):
    script = os.path.join(_plugin_root(), "scripts", "make_page.py")
    why = (_PAGE_DENY_BASICS % (page, "\n".join(fails), script)) if fails else _PAGE_DENY % (page, script)
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": why + "".join(" (" + n + ")" for n in notes)}})


def _page_limit(page, problems):
    """maxBlockWords from the project's docs/page-style.json (None = plugin default); a bad file adds a note."""
    d = os.path.dirname(os.path.abspath(page))
    while not os.path.isdir(os.path.join(d, "docs")):
        if os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)
    f = os.path.join(d, "docs", "page-style.json")
    if not os.path.isfile(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            v = json.load(fh)["basics"]["maxBlockWords"]
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            return v
        raise ValueError("maxBlockWords is not a positive whole number")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append("%s could not be used (%s: %s), so the default block length applies."
                     % (f, type(exc).__name__, exc))
        return None


def _page_read(text, page):
    """(failed basics, notes) for an unmarked page. A checker that cannot load fails open, with a note."""
    notes = []
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        import page_criteria
    except Exception as exc:
        return [], ["the page checker could not load (%s: %s), so %s was not read; the call is allowed."
                    % (type(exc).__name__, exc, page)]
    lim = _page_limit(page, notes)
    return page_criteria.check(text, max_block_words=lim), notes


def _page_verdict(text, page):
    """True when allowed. Denies once when basics fail; otherwise a note (if any) is the only output."""
    fails, notes = _page_read(text, page)
    if fails:
        _page_deny(page, fails, notes)
        return False
    if notes:
        _page_note("; ".join(notes))
    return True


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
            _page_verdict(str(ti.get("content") or ""), fp)
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
                    text = fh.read()
            except OSError as exc:
                _page_note("could not read %s (%s), so the check did not run; the publish is allowed."
                           % (page, type(exc).__name__))
                continue
            if not PAGE_MARK_RE.search(text[:4096]) and not _page_verdict(text, page):
                return 0
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the page check hit an error (%s: %s) and did not "
                               "run for this call; the call is allowed." % (type(exc).__name__, exc)})
    return 0


def _embed_in_place(page, look):
    """#559: embed each relative picture beside `page` as a data: address, nothing else changes. Returns the note."""
    import base64
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import make_page as mp  # the mime table and size limit live there
    with open(page, encoding="utf-8", newline="") as fh:
        html = fh.read()
    done, left = [], []
    for s in mp.static_broken_pictures(html):
        path = re.split(r"[?#]", s)[0]
        ext = os.path.splitext(path)[1].lower()
        full = os.path.join(os.path.dirname(os.path.abspath(page)), path)
        if re.match(r"(?i)^([a-z][a-z0-9+.-]*:|//|/|\\)", s) or os.path.isabs(path):
            left.append("%s (not a relative path)" % s)
        elif not os.path.isfile(full):
            left.append("%s (file not found)" % s)
        elif ext not in mp.PIC_MIME:
            left.append("%s (type %s not supported)" % (s, ext or "none"))
        elif os.path.getsize(full) > mp.MAX_PIC:
            left.append("%s (over %d bytes)" % (s, mp.MAX_PIC))
        else:
            with open(full, "rb") as fh:
                addr = "data:%s;base64,%s" % (mp.PIC_MIME[ext], base64.b64encode(fh.read()).decode("ascii"))
                # not when it is the tail of a longer path (a file list naming docs/plans/<src> is text, not a source)
                html = re.sub(r"(?<![\w./-])" + re.escape(s), lambda _m: addr, html)
            done.append(s)
    if done:
        with open(page, "w", encoding="utf-8", newline="") as fh:
            fh.write(html)
    again, why = look(page)
    if again is None:
        return "%s: embedded %d picture(s) but the re-check did not run (%s); not embedded: %s" % (
            page, len(done), why, ", ".join(left) or "none")
    if not again:
        return "%s was repaired: embedded %s" % (page, ", ".join(done))
    if done:
        return "%s was partly repaired: embedded %s; still broken: %s" % (page, ", ".join(done), "; ".join(left) or ", ".join(again))
    return "%s could not be repaired: %s" % (page, "; ".join(left) or ", ".join(again))


def event_sendcheck():
    """#559: before an .html page is sent, open a copy alone; embed pictures that sit beside it when they are
    broken. Never blocks: every outcome is allow, with a note."""
    import subprocess
    try:
        data = json.loads(read_payload() or "{}")
        ti = data.get("tool_input") if isinstance(data, dict) else None
        pages = [v for v in _page_candidates(ti) if v.lower().endswith(_PAGE_EXT)] if isinstance(ti, dict) else []
        notes = []

        def look(page):
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, "page_criteria.py"), page, "--visual"],
                               capture_output=True, text=True, timeout=240)
            found = list(dict.fromkeys(re.findall(r"broken picture when the page is opened alone: (.+)", r.stdout)))
            if not found and "visual check did not run" in r.stdout:  # the static check reports without a browser
                return None, r.stdout.split("visual check did not run:", 1)[1].strip()[:150]
            return found, ""

        for page in pages:
            broken, why = look(page)
            if broken is None:
                notes.append("the picture check did not run for %s (%s), so its pictures are unchecked" % (page, why))
            elif broken:
                notes.append(_embed_in_place(page, look))
        if notes:
            emit({"systemMessage": "house-rules send check: " + "; ".join(notes) + ". The send goes ahead."})
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the send check hit an error (%s: %s); the send goes ahead."
                               % (type(exc).__name__, exc)})
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
    build = ctx.get("qa_stage") == "build"
    if build and re.search(r"(?i:ledger)|\bP\d+\b", text):  # #598: a parked choice is on the ledger
        return ""
    for line in text.split("\n"):
        if not line.lstrip().startswith(">") and _DECIDED_RE.search(line):
            if build:
                return ("a design point is aj's to review; park the choice in the ledger with "
                        "`python3 %s park ...` instead of only saying \"I went with ...\""
                        % os.path.join(SCRIPTS_DIR, "ledger_note.py"))
            return ("a design point is aj's to decide; put the choice to aj as options with one marked as the "
                    "suggestion instead of saying \"I went with ...\"")
    return ""


def _qa_count_demand(ctx):
    """#643: the QA page is linked and the feature's ledger has K rows: the reply must say how many decisions."""
    reply, folder = ctx.get("reply") or "", ""
    try:
        if SCRIPTS_DIR not in sys.path:
            sys.path.insert(0, SCRIPTS_DIR)
        import make_page
        folder = make_page.qa_folder(ctx.get("qa_feature") or "")
        if not folder:
            return ""
        top = _repo_root_of(os.path.join(ctx.get("cwd") or "", "x"))
        ledger = os.path.join(top, "docs", "qa", folder, "ledger.md")
        if not os.path.isfile(ledger):
            return ""  # no ledger for this feature: nothing to count
        with open(ledger, encoding="utf-8") as fh:
            rows = [ln for ln in fh if re.match(r"\|\s*K\d+\s*\|", ln)]
    except OSError as exc:
        sys.stderr.write("house-rules: the QA decision count could not read the ledger (%s), so it asked for no "
                         "count.\n" % type(exc).__name__)
        return ""
    if not rows or re.search(r"(?i)\bdecisions?\b.{0,20}\d|\d.{0,20}\bdecisions?\b", reply):
        return ""
    return ("the ledger has %d decision(s) for this feature: say in the reply how many decisions were logged "
            "(for example \"%d decisions logged\")" % (len(rows), len(rows)))


def _check_qa_page(ctx):
    """#269: in QA the build is handed over with a make_page.py QA page, linked in a reply. Not
    skipped by "no page": a QA page is mandatory."""
    if ctx.get("qa_stage") != "qa":
        return ""
    page = ctx.get("qa_page") or ""
    if ctx.get("qa_linked"):  # linked on an earlier reply: only the decision count below can still apply
        return _qa_count_demand(ctx) if page and (page in (ctx.get("reply") or "") or os.path.basename(page) in (ctx.get("reply") or "")) else ""
    if _record_qa_link(ctx):
        return _qa_count_demand(ctx)
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


_DEVIATION_RE = re.compile(
    r"\b(deviat\w*|depart(?:s|ed|ure)? from (?:the |this )?(?:build )?plan|(?:differs?|changed?|diverg\w*) from (?:the |this )?(?:build )?plan"
    r"|instead of (?:the )?(?:plan|what the plan)|not as (?:the )?plan(?:ned)?)\b", re.IGNORECASE)


def _check_deviation(ctx):
    """#599: with nobody present (unattended or bypass; an unknown mode counts as attended), a reply that says it
    departed from the build plan, with no `ledger_note.py` call this turn, is sent back once. A phrase heuristic."""
    if not ctx.get("hands_off") or ctx.get("ledger_logged"):
        return ""
    if not _DEVIATION_RE.search(ctx.get("reply") or ""):
        return ""
    return ("log each departure with `python3 %s deviate <feature> --step <n> --plan ... --done ... --why ... "
            "--undo ...`, or `park` for a change to what aj approved, then say so in one line"
            % os.path.join(core.SCRIPTS_DIR, "ledger_note.py"))


CHECKPOINTS = [
    ("reply ends", "page", _check_page, "report"),  # #309: report only until the restructure
    ("reply ends", "editor", _check_editor, "block"),
    ("reply ends", "evidence", _check_evidence, "block"),
    ("reply ends", "commit", _check_commit, "block"),
    ("reply ends", "plain summary", _check_plain, "block"),
    ("reply ends", "qa page", _check_qa_page, "block"),
    ("reply ends", "decided for you", _check_decided, "block"),
    ("reply ends", "deviation", _check_deviation, "block"),
    ("reply ends", "changelog", _check_changelog, "block"),
    ("reply ends", "handoff", _check_handoff, "block"),
    ("reply ends", "send page", _check_send, "block"),
]


NOBODY_CHECKPOINTS = ("evidence", "commit", "deviation", "qa page", "changelog", "decided for you")

CHECKPOINT_RULES = {
    "page": "A reply that offers choices, lays out a plan, or runs to %d words or more links a page." % LONG_REPLY_WORDS,
    "editor": "A page goes past @house-rules:editor before aj reads it; a long reply too when HOUSE_RULES_EDITOR=on.",
    "evidence": "A success claim needs a tool run and its quoted output behind it.",
    "commit": "Files a turn writes are committed on your own branch before it ends.",
    "qa page": "In QA, the build is handed to aj with a QA page built by make_page.py, linked in a reply.",
    "deviation": "With nobody present, every departure from the build plan is logged in the ledger, not only said in the reply.",
    "decided for you": "Design points are aj's to decide; a reply puts them as options, not as \"I went with ...\".",
    "handoff": "A turn that wrote or committed files is pushed, with a fresh clean handoff note.",
    "send page": "A page written or rebuilt this turn is sent to aj with the file-send tool, after its last change.",
    "changelog": "Every change adds a line to the repo's CHANGELOG.md, in the same turn.",
    "plain summary": "A reply reporting finished work opens with a short plain-English summary.",
}


def _missed_checkpoints(ctx):
    """[(rule name, fix)] for every blocking checkpoint at 'reply ends' that the reply misses."""
    if not _loop_enabled():  # light mode: evidence and commit still arrive, as the stop hook's reminders
        return []
    quiet = ctx.get("hands_off") or core.unattended()  # #637: nobody present runs only these six
    return [(name, fix) for moment, name, fn, mode in CHECKPOINTS
            if moment == "reply ends" and mode == "block" and (not quiet or name in NOBODY_CHECKPOINTS)
            for fix in [fn(ctx)] if fix]


def _checkpoint_reason(missed):
    lines = ["House rules, the reply is not done yet. It misses %d checkpoint%s:" % (
        len(missed), "" if len(missed) == 1 else "s")]
    for name, fix in missed:
        lines.append("- %s: %s Fix: %s." % (name, CHECKPOINT_RULES[name], fix))
    lines.append("Fix these and send only what changed, not the whole reply again. A missing page blocks every retry "
                 "until the reply links one; the other checks block once. aj typing \"design loop off\" keeps only the evidence and commit checks.")
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
        # REST, not `gh pr view`: that one uses GraphQL, which cloud sessions refuse (403, seen 2026-11-11).
        proc = subprocess.run(["gh", "api", "repos/%s/pulls/%d" % (repo, number), "--jq", ".body // \"\""],
                              capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
        if proc.returncode != 0:
            raise RuntimeError(((proc.stderr or "").strip().splitlines() or ["gh exited %d" % proc.returncode])[0])
        return _pr_refs(proc.stdout, repo), ""
    except Exception as exc:
        return [], "its body could not be read (%s: %s)" % (type(exc).__name__, exc)


LOOP_ISSUE_BODIES_ENV = "HOUSE_RULES_LOOP_ISSUE_BODIES_FILE"  # tests: {"owner/repo#n": issue body}
_PART_OF_RE = re.compile(r"\bPart of\s+#(\d+)", re.IGNORECASE)


def _issue_parent(repo, number):
    """(parent number or None, problem) from the `Part of #N` line of issue `number`'s body, read through REST
    (not GraphQL, which cloud sessions refuse). problem says why the body could not be read ("" when it could)."""
    stand_in = os.environ.get(LOOP_ISSUE_BODIES_ENV)
    try:
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                body = json.load(f)["%s#%d" % (repo, number)]
        else:
            if not repo or not shutil.which("gh"):
                raise RuntimeError("no repo is named" if not repo else "gh is not installed")
            import subprocess
            proc = subprocess.run(["gh", "api", "repos/%s/issues/%d" % (repo, number), "--jq", ".body // \"\""],
                                  capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
            if proc.returncode != 0:
                raise RuntimeError(((proc.stderr or "").strip().splitlines() or ["gh exited %d" % proc.returncode])[0])
            body = proc.stdout
        m = _PART_OF_RE.search(body or "")
        return (int(m.group(1)) if m else None), ""
    except Exception as exc:
        return None, "#%d's body could not be read (%s: %s)" % (number, type(exc).__name__, exc)


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
        return ""  # switched off by aj; no trace here, so the hook still prints exactly one JSON object
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
        stamp_trace = ""  # #510: said through the one emit below, never as a second JSON object on stdout
        if open_:
            refs, why = _merged_pr_refs(state, repo, number)
            have = {(r.lower(), n) for r, n in refs}
            looked = {}  # (repo, issue) -> parent number or None, for the refusal text
            miss = []

            def _entry_hit(e):
                for i in e.get("issues") or []:
                    if not isinstance(i, dict) or not isinstance(i.get("number"), int):
                        continue
                    irepo = (i.get("repo") or repo or "").lower()
                    if any(n == i["number"] and _close_repo_match(r, i.get("repo", "")) for r, n in refs):
                        return True
                    par, perr = _issue_parent(irepo, i["number"])
                    looked[(irepo, i["number"])] = par
                    if perr:
                        miss.append(perr)
                    if par is not None and (irepo, par) in have:
                        return True
                return False
            hit = [e for e in open_ if _entry_hit(e)]
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
                found = ", ".join("%s#%d" % tuple(r) if isinstance(r, (list, tuple)) else str(r) for r in sorted(have)) or "no refs"
                looked_txt = "; ".join("#%d (parent %s)" % (n, ("#%d" % p) if p is not None else "none")
                                       for (_, n), p in sorted(looked.items()))
                detail = "looked for a Refs/Part of link to %s, found %s%s%s" % (
                    looked_txt or "any QA-passed issue", found, ("; could not tell: " + "; ".join(miss)) if miss else "",
                    ("; " + why) if why else "")
                for e in open_:
                    e["merge_miss"] = "pull request %s#%d: %s" % (repo, number, detail)
                _loop_write(git_dir, state)
                notes.append("house-rules: the merge of %s#%d stamped no closable record, because %s." % (repo, number, detail))
            stamp_trace = "house-rules plugin: merge of %s#%d stamped %d closable record(s)." % (repo, number, len(hit))
        # U3: the merge never moves the stage; aj is asked for the verdict. On the default branch a QA stage file
        # already reads as Done (_loop_read_merged), so asking there would be noise.
        if state.get("stage") == "qa" and _loop_branch(git_dir) not in _loop_default_branches(git_dir):
            notes.append('Design loop: pull request %s#%d merged while "%s" is in QA, so the stage file still '
                         'says QA. Ask aj for "QA passed: %s" or "QA failed: %s"; the stage moves only on their word.'
                         % ((repo, number) + (state.get("feature") or "this feature",) * 3))
        if not notes and stamp_trace:
            trace(stamp_trace)
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
    if _loop_enabled() and _pages_enabled():
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
                         needs_evidence, uncommitted, plain_problems, trace_lines, written=None, committed=False):
    """The blocking checkpoints at "reply ends" (first reply only). True when the reply was blocked (the
    block is emitted here). An error is added to trace_lines and nothing is blocked."""
    try:
        ctx = {
            "reply": reply_text if have_reply else "",
            "long_words": long_words,
            "editor_owed": editor_owed,
            "needs_evidence": needs_evidence,
            "uncommitted": uncommitted, "written": list(written or []), "committed": committed,
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
                           qa_linked=_st.get("qa_page_linked"), qa_git_dir=_gd, qa_feature=_st.get("feature") or "")
        except Exception as exc:
            trace_lines.append("house-rules: the QA page checkpoint could not read the stage file (%s: %s), "
                               "so it is off for this reply." % (type(exc).__name__, exc))
        try:
            recs, _d = core._records_since_last_user_message(transcript_path) if transcript_path else (None, "")
            if recs is not None:
                ctx["pages_unsent"] = _pages_unsent(recs, ctx["cwd"])
                # no send tool in the transcript: a link in the reply counts instead
                ctx["can_send"] = _SEND_TOOL in _read_text(transcript_path)
        except Exception as exc:
            trace_lines.append("house-rules: the send-page checkpoint could not read the turn (%s: %s), "
                               "so it is off for this reply." % (type(exc).__name__, exc))
        try:
            ctx["hands_off"] = core.nobody_present(payload)
            if ctx["hands_off"] and transcript_path:
                recs, _d = core._records_since_last_user_message(transcript_path)
                ctx["ledger_logged"] = any("ledger_note.py" in str((b.get("input") or {}).get("command", ""))
                                           for b in core._turn_tool_uses(recs or []))
        except Exception as exc:
            ctx["hands_off"] = False
            trace_lines.append("house-rules: the deviation checkpoint could not read the turn (%s: %s), "
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


def _noask_stage(payload):
    """#598: (stage, "") for event_noask, or (None, why it could not be read)."""
    if not _loop_enabled():
        return None, "the design loop is off (HOUSE_RULES_LOOP=off)"
    _top, gd = _issues_locate(_payload_cwd(payload))
    if not gd:
        return None, "no git project found from the payload's cwd"
    state, problem = _loop_read_merged(gd)
    if problem:
        return None, problem
    return state["stage"], ""


core.register_noask_stage(_noask_stage)
core.register_guard_issue(_author_guard)
core.register_guard_issue(_issues_guard)
core.register_github_write(_guardgithub_issue_checks)
core.register_prompt(_scope_loop_link)
core.register_delegate_note(_issues_plan_note)
core.register_subagent_note(_loop_helper_note)
core.register_tool_record(_post_tool_records)
core.register_post_tool("promptran", _record_step_result)
core.register_edit_gate(_edit_gates)
