#!/usr/bin/env python3
"""replay_hooks.py - replays recorded hook payloads through two plugin sets and diffs the combined output.

    python tools/replay_hooks.py [--old-ref origin/main] [--report PATH] [--keep DIR]

Merge-gate item 2 for the plugin split (docs/4-systems/plugin-split.md, "The gate before a merge to main"):
the behaviour of the branch's plugins together must equal house-rules as `main` has it, except for the
changes aj approved. OLD is house-rules from `git archive <old-ref>`; NEW is every plugin under
claude-house-rules/plugins/ in the working tree that has a hooks.json (house-rules, rule-enforcement).

For each scenario (an event, a tool, a payload and a fresh throwaway git repo on an AjsAgent/ branch) it feeds
the payload, the way Claude Code does, to every hook registered for that event whose matcher fits the tool:
each plugin's scripts/run.sh with that plugin's own CLAUDE_PLUGIN_ROOT. HOME and CLAUDE_CONFIG_DIR are a temp
folder and a failing fake `gh` is first on PATH, so GitHub is never called. The outputs of all hooks for the
event are combined (decisions, block reasons, additionalContext blocks, systemMessage blocks, stderr), then
OLD and NEW are diffed line by line and every difference is classified against the approved changes. A
difference no rule explains is UNEXPLAINED: it is reported, never hidden, and the exit code is 1.

The diff and classify functions take plain data (compare, classify) so verify_tools.py can test them on a
tiny fake pair of plugins without git or Claude Code.
"""

import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGINS_REL = "claude-house-rules/plugins"

# --- approved changes: a difference is explained only by one of these ----------------------------------------

CLASSES = [
    "rule loading moved",
    "block boundary (link clause is its own block)",
    "three blocks then lock",
    "off switches removed",
    "go-ahead delegation clause removed",
    "house-rules files line",
    "text no longer mentions removed switches",
    "UNEXPLAINED",
]

_SWITCH_RE = re.compile(r"HOUSE_RULES_(AGENTS|AGENT_BRANCH|ATTRIBUTION|AUTOSAVE|AUTO_UPDATE|CLEAR_WRITING|COMMIT_CHECK|"
                        r"DELEGATION|HANDOVER|HARVEST|ISSUES|LOOP|PARITY|PLAIN_SUMMARY|VERSION_CHECK|VISUAL_CHECK|"
                        r"VOICE|WORKTRACKING|EDITOR|PROMPT_TIMEOUT)\b")
_LOCK_RE = re.compile(r"block \d of 3|\bLOCKED\b|repeat-failure lock|locked check|still fails after 3 blocks|"
                      r"up to (3|three) (times|blocks)|after the last block|blocks every retry|the other checks block once|"
                      r"\bblocks? (the reply )?once\b", re.I)
_BLOCK_N_RE = re.compile(r" \(block \d of 3\)")
_FILES_LINE_RE = re.compile(r"^house-rules files the rules name:")
_FILES_OLD_RE = re.compile(r"<plugin>/(output-styles/handover-cards\.md|scripts/make_page\.py)")
_FILES_NEW_RE = re.compile(r"whose path house-rules gives at session start")
_GOAHEAD_RE = re.compile(r"go-ahead|go ahead", re.I)
_ROOT_TOKEN_RE = re.compile(r"<RE>")
_OFF_RE = re.compile(r"HOUSE_RULES_\w+=off|switch (it|this) off|turns? (it|this) off|disables? (it|this)", re.I)


def fold_roots(text):
    """Rule loading moved: the plugin root the rules text names is rule-enforcement's, not house-rules'."""
    return _ROOT_TOKEN_RE.sub("<HR>", text)


def classify(field, side, line, other_lines):
    """Class of one unit of text that is only on `side` ('old' or 'new') of a field.
    other_lines: the units only on the other side. Returns one of CLASSES."""
    if side == "new" and _FILES_LINE_RE.match(line):
        return "house-rules files line"
    if (side == "old" and _FILES_OLD_RE.search(line)) or (side == "new" and _FILES_NEW_RE.search(line)):
        return "house-rules files line"
    if "<RE>" in line + "".join(other_lines) and any(fold_roots(line) == fold_roots(o) for o in other_lines):
        return "rule loading moved"
    if _LOCK_RE.search(line) or any(_BLOCK_N_RE.sub("", line) == _BLOCK_N_RE.sub("", o) for o in other_lines):
        return "three blocks then lock"
    if side == "old" and _SWITCH_RE.search(line) or side == "old" and _OFF_RE.search(line):
        return "text no longer mentions removed switches"
    if side == "old" and _GOAHEAD_RE.search(line):
        return "go-ahead delegation clause removed"
    return "UNEXPLAINED"


# --- normalising and combining outputs ------------------------------------------------------------------------

def parse_output(rc, out, err):
    """One hook's output as a dict of lists: decisions, blocks, context, system, stderr, misc."""
    r = {"decisions": [], "blocks": [], "context": [], "system": [], "stderr": [], "misc": []}
    out = out.strip()
    if rc not in (0,):
        r["misc"].append("exit code %d" % rc)
    if err.strip():
        r["stderr"].append(err.strip())
    if not out:
        return r
    try:
        data = json.loads(out)
    except ValueError:
        r["misc"].append("stdout not JSON: " + out)
        return r
    if not isinstance(data, dict):
        r["misc"].append("stdout JSON not an object: " + out)
        return r
    hso = data.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        r["decisions"].append("%s: %s" % (hso["permissionDecision"], hso.get("permissionDecisionReason", "")))
    if "decision" in data:
        r["blocks"].append("%s: %s" % (data["decision"], data.get("reason", "")))
    if hso.get("additionalContext"):
        r["context"].append(hso["additionalContext"])
    if data.get("systemMessage"):
        r["system"].append(data["systemMessage"])
    known = {"hookSpecificOutput", "decision", "reason", "systemMessage"}
    extra = {k: v for k, v in data.items() if k not in known}
    hso_extra = {k: v for k, v in hso.items() if k not in ("permissionDecision", "permissionDecisionReason",
                                                           "additionalContext", "hookEventName")}
    if hso.get("hookEventName") is None and hso:
        extra["hookSpecificOutput.hookEventName"] = None
    if extra or hso_extra:
        r["misc"].append(json.dumps({**extra, **hso_extra}, sort_keys=True))
    return r


def combine(outputs):
    """Combine several parse_output() dicts (one per hook) into one per-event dict."""
    c = {"decisions": [], "blocks": [], "context": [], "system": [], "stderr": [], "misc": []}
    for o in outputs:
        for k in c:
            c[k].extend(o[k])
    return c


FIELDS = ["decisions", "blocks", "context", "system", "stderr", "misc"]


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\"(<-])")
_STRUCT_RE = re.compile(r"^\s*(#|-|\*|\d+[.)]|\||`{3})")


def _lines(blocks):
    """The comparison units of some blocks: one per heading or bullet line, and one per sentence of a
    wrapped paragraph (so re-wrapping a changed sentence does not look like a change of its neighbours)."""
    out = []
    for b in blocks:
        para = []

        def flush():
            if para:
                text = " ".join(" ".join(para).split())
                out.extend(x for x in _SENT_SPLIT_RE.split(text) if x.strip())
                del para[:]
        for l in b.split("\n"):
            if not l.strip():
                flush()
            elif _STRUCT_RE.match(l):
                flush()
                out.append(" ".join(l.split()))
            else:
                para.append(l.strip())
        flush()
    return out


def compare(old, new):
    """Differences between two combined dicts: [{field, side, line, cls}] plus block-boundary notes.
    Hooks of one event run in parallel, so block order is not compared; blocks identical on both sides cancel,
    then the remaining lines are compared as multisets."""
    diffs = []
    for f in FIELDS:
        ob, nb = collections.Counter(old[f]), collections.Counter(new[f])
        o_rest = list((ob - nb).elements())
        n_rest = list((nb - ob).elements())
        if not o_rest and not n_rest:
            continue
        ol, nl = collections.Counter(_lines(o_rest)), collections.Counter(_lines(n_rest))
        only_old = list((ol - nl).elements())
        only_new = list((nl - ol).elements())
        if not only_old and not only_new:
            diffs.append({"field": f, "side": "both", "line": "same lines, split into %d block(s) now, was %d"
                          % (len(n_rest), len(o_rest)), "cls": "block boundary (link clause is its own block)",
                          "old": o_rest, "new": n_rest})
            continue
        # line order of the original text
        order_old = [l for l in _lines(o_rest) if l in set(only_old)]
        order_new = [l for l in _lines(n_rest) if l in set(only_new)]
        for l in order_old:
            diffs.append({"field": f, "side": "old", "line": l, "cls": classify(f, "old", l, order_new)})
        for l in order_new:
            diffs.append({"field": f, "side": "new", "line": l, "cls": classify(f, "new", l, order_old)})
    return diffs


# --- plugins and hook entries ---------------------------------------------------------------------------------

def load_plugins(plugins_dir, only=None):
    """[{name, dir, version, entries:[{event, matcher, name, timeout}]}] for each plugin folder with a hooks.json."""
    out = []
    for name in sorted(os.listdir(plugins_dir)):
        d = os.path.join(plugins_dir, name)
        hj = os.path.join(d, "hooks", "hooks.json")
        if not os.path.isfile(hj) or (only and name not in only):
            continue
        with open(hj, encoding="utf-8") as f:
            data = json.load(f)
        version = ""
        pj = os.path.join(d, ".claude-plugin", "plugin.json")
        if os.path.isfile(pj):
            with open(pj, encoding="utf-8") as f:
                version = json.load(f).get("version", "")
        entries = []
        for event, groups in data["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    m = re.search(r'run\.sh"?\s+(\S+)', h["command"])
                    entries.append({"event": event, "matcher": g.get("matcher", ""),
                                    "name": m.group(1) if m else h["command"], "command": h["command"],
                                    "timeout": h.get("timeout", 60)})
        out.append({"name": name, "dir": d, "version": version, "entries": entries})
    return out


def matches(entry, tool):
    """Claude Code matchers are regexes anchored to the whole tool name; an empty matcher matches all."""
    if not entry["matcher"]:
        return True
    return bool(tool) and re.fullmatch(entry["matcher"], tool) is not None


def extract_old(ref, dest):
    """house-rules (and its vendored library) at `ref`, from git archive, into dest."""
    p1 = subprocess.Popen(["git", "-C", ROOT, "archive", ref, PLUGINS_REL + "/house-rules"], stdout=subprocess.PIPE)
    p2 = subprocess.run(["tar", "-x", "-C", dest], stdin=p1.stdout)
    p1.stdout.close()
    if p1.wait() != 0 or p2.returncode != 0:
        raise SystemExit("could not extract %s from git archive" % ref)
    return os.path.join(dest, PLUGINS_REL)


# --- scenarios ------------------------------------------------------------------------------------------------

def _scn(name, event, tool="", tool_input=None, prompt=None, branch="AjsAgent/replay", stage="build",
         committed=None, dirty=None, staged=None, reply=None, written=None, user="please do the thing",
         extra=None, response=None):
    return {"name": name, "event": event, "tool": tool, "tool_input": tool_input or {}, "prompt": prompt,
            "branch": branch, "stage": stage, "committed": committed or {}, "dirty": dirty or {},
            "staged": staged or {}, "reply": reply, "written": written or [], "user": user,
            "extra": extra or {}, "response": response}


def scenarios():
    S = []
    S.append(_scn("SessionStart on an AjsAgent branch", "SessionStart", extra={"source": "startup"}))
    S.append(_scn("SessionStart on main (not aj's branch)", "SessionStart", branch="main", extra={"source": "startup"}))
    S.append(_scn("UserPromptSubmit ordinary prompt", "UserPromptSubmit", prompt="please read notes.txt and tell me what it says"))
    S.append(_scn("UserPromptSubmit 'Design approved: x'", "UserPromptSubmit", prompt="Design approved: x", stage="design"))
    S.append(_scn("UserPromptSubmit long prompt with a parity ask", "UserPromptSubmit",
                  prompt="port the importer to python and show the parity report"))
    # PreToolUse
    S.append(_scn("guard: harmless ls", "PreToolUse", "Bash", {"command": "ls"}))
    S.append(_scn("guard: git commit on an owned branch", "PreToolUse", "Bash",
                  {"command": "git commit -m 'add a note\n\nCommitted by AJ'\"'\"'s agent'"}, staged={"a.txt": "a\n"}))
    S.append(_scn("guard: git commit crediting Claude", "PreToolUse", "Bash",
                  {"command": "git commit -m 'x\n\nCo-Authored-By: Claude <noreply@anthropic.com>'"}, staged={"a.txt": "a\n"}))
    S.append(_scn("guard: rm -rf", "PreToolUse", "Bash", {"command": "rm -rf build"}, committed={"build/x.txt": "x\n"}))
    S.append(_scn("guard: git push to main", "PreToolUse", "Bash", {"command": "git push origin main"}))
    S.append(_scn("guard: git reset --hard", "PreToolUse", "Bash", {"command": "git reset --hard HEAD~1"}))
    S.append(_scn("guard: commit on main", "PreToolUse", "Bash", {"command": "git commit -m x"}, branch="main",
                  staged={"a.txt": "a\n"}))
    S.append(_scn("guard: PowerShell Remove-Item", "PreToolUse", "PowerShell", {"command": "Remove-Item -Recurse -Force build"}))
    S.append(_scn("guard: gh pr merge", "PreToolUse", "Bash", {"command": "gh pr merge 5 --squash"}))
    S.append(_scn("Write a doc (build)", "PreToolUse", "Write", {"file_path": "{REPO}/docs/note.md", "content": "# Note\n\nA short note.\n"}))
    S.append(_scn("Write a source file (build)", "PreToolUse", "Write", {"file_path": "{REPO}/app.py", "content": "print(1)\n"}))
    S.append(_scn("Write a source file (design stage)", "PreToolUse", "Write", {"file_path": "{REPO}/app.py", "content": "print(1)\n"}, stage="design"))
    S.append(_scn("Write over a committed file", "PreToolUse", "Write", {"file_path": "{REPO}/app.py", "content": "print(2)\n"},
                  committed={"app.py": "print(1)\n"}))
    S.append(_scn("Write over an uncommitted file", "PreToolUse", "Write", {"file_path": "{REPO}/app.py", "content": "print(2)\n"},
                  dirty={"app.py": "print(1)\n"}))
    S.append(_scn("Write a page (html)", "PreToolUse", "Write", {"file_path": "{REPO}/docs/page.html", "content": "<html><body><h1>x</h1></body></html>\n"}))
    S.append(_scn("Edit a doc", "PreToolUse", "Edit", {"file_path": "{REPO}/docs/note.md", "old_string": "a", "new_string": "b"},
                  committed={"docs/note.md": "a\n"}))
    S.append(_scn("Edit a source file (build)", "PreToolUse", "Edit", {"file_path": "{REPO}/app.py", "old_string": "1", "new_string": "2"},
                  committed={"app.py": "print(1)\n"}))
    S.append(_scn("Edit a source file (design stage)", "PreToolUse", "Edit", {"file_path": "{REPO}/app.py", "old_string": "1", "new_string": "2"},
                  committed={"app.py": "print(1)\n"}, stage="design"))
    S.append(_scn("MultiEdit a source file (build)", "PreToolUse", "MultiEdit",
                  {"file_path": "{REPO}/app.py", "edits": [{"old_string": "1", "new_string": "2"}]}, committed={"app.py": "print(1)\n"}))
    S.append(_scn("NotebookEdit", "PreToolUse", "NotebookEdit", {"notebook_path": "{REPO}/n.ipynb", "new_source": "x"}))
    S.append(_scn("Bash sed -i on a source file", "PreToolUse", "Bash", {"command": "sed -i s/1/2/ app.py"}, committed={"app.py": "print(1)\n"}))
    S.append(_scn("Bash redirect into a source file (design)", "PreToolUse", "Bash", {"command": "echo 'x=1' > app.py"}, stage="design"))
    S.append(_scn("Agent spawn: general-purpose", "PreToolUse", "Agent",
                  {"subagent_type": "general-purpose", "description": "read a file", "prompt": "read notes.txt"}))
    S.append(_scn("Task spawn: Explore", "PreToolUse", "Task", {"subagent_type": "Explore", "description": "look", "prompt": "look around"}))
    S.append(_scn("github create_pull_request (guardgithub)", "PreToolUse", "mcp__github__create_pull_request",
                  {"owner": "Ajw2003", "repo": "r", "title": "t", "head": "AjsAgent/x", "base": "main",
                   "body": "A change.\n\n🤖 Generated with Claude Code"}))
    S.append(_scn("github issue_write (guardgithub)", "PreToolUse", "mcp__github__issue_write",
                  {"method": "create", "owner": "Ajw2003", "repo": "r", "title": "t", "body": "body text"}))
    S.append(_scn("github add_issue_comment ordinary", "PreToolUse", "mcp__github__add_issue_comment",
                  {"owner": "Ajw2003", "repo": "r", "issue_number": 1, "body": "done\n\nCommitted by AJ's agent"}))
    S.append(_scn("github create_branch", "PreToolUse", "mcp__github__create_branch", {"owner": "Ajw2003", "repo": "r", "branch": "AjsAgent/x"}))
    S.append(_scn("Read (no PreToolUse hook should fire)", "PreToolUse", "Read", {"file_path": "{REPO}/notes.txt"}, committed={"notes.txt": "n\n"}))
    # PostToolUse
    S.append(_scn("PostToolUse Write a doc", "PostToolUse", "Write", {"file_path": "{REPO}/docs/note.md", "content": "# Note\n"},
                  dirty={"docs/note.md": "# Note\n"}, response={"success": True}))
    S.append(_scn("PostToolUse Write a source file", "PostToolUse", "Write", {"file_path": "{REPO}/app.py", "content": "print(1)\n"},
                  dirty={"app.py": "print(1)\n"}, response={"success": True}))
    S.append(_scn("PostToolUse Write a runnable script", "PostToolUse", "Write", {"file_path": "{REPO}/run.sh", "content": "#!/bin/sh\necho hi\n"},
                  dirty={"run.sh": "#!/bin/sh\necho hi\n"}, response={"success": True}))
    S.append(_scn("PostToolUse Edit a source file", "PostToolUse", "Edit", {"file_path": "{REPO}/app.py", "old_string": "1", "new_string": "2"},
                  committed={"app.py": "print(1)\n"}, dirty={"app.py": "print(2)\n"}, response={"success": True}))
    S.append(_scn("PostToolUse Write a long source file with comments", "PostToolUse", "Write",
                  {"file_path": "{REPO}/lib.py", "content": "# helper\n" + "def f():\n    # why\n    return 1\n" * 12},
                  dirty={"lib.py": "# helper\n" + "def f():\n    # why\n    return 1\n" * 12}, response={"success": True}))
    S.append(_scn("PostToolUse Bash git commit", "PostToolUse", "Bash",
                  {"command": "git commit -m 'x\n\nCommitted by AJ'\"'\"'s agent'"}, response={"stdout": "[AjsAgent/replay abc1234] x\n", "stderr": ""}))
    S.append(_scn("PostToolUse Bash git commit crediting Claude", "PostToolUse", "Bash",
                  {"command": "git commit -m 'x\n\nCo-Authored-By: Claude <n@a.com>'"}, response={"stdout": "[AjsAgent/replay abc1234] x\n", "stderr": ""}))
    S.append(_scn("PostToolUse Bash ls", "PostToolUse", "Bash", {"command": "ls"}, response={"stdout": "a.txt\n", "stderr": ""}))
    S.append(_scn("PostToolUse github merge_pull_request", "PostToolUse", "mcp__github__merge_pull_request",
                  {"owner": "Ajw2003", "repo": "r", "pullNumber": 5}, response={"merged": True}))
    S.append(_scn("PostToolUse ExitPlanMode", "PostToolUse", "ExitPlanMode", {"plan": "1. read\n2. edit"}, response={"ok": True}))
    S.append(_scn("PostToolUse Agent", "PostToolUse", "Agent", {"subagent_type": "general-purpose", "description": "d", "prompt": "p"},
                  response={"content": [{"type": "text", "text": "done"}]}))
    S.append(_scn("PostToolUse hearthbot remote control", "PostToolUse", "mcp__hearthbot__start_remote_control", {},
                  response={"url": "https://example.invalid/r"}))
    S.append(_scn("PostToolUse github issue_write", "PostToolUse", "mcp__github__issue_write",
                  {"method": "create", "owner": "Ajw2003", "repo": "r", "title": "t", "body": "b"}, response={"number": 7}))
    S.append(_scn("PostToolUse mcp tool (promptran)", "PostToolUse", "mcp__other__thing", {"x": 1}, response={"ok": True}))
    S.append(_scn("PostToolUse WebFetch (promptran)", "PostToolUse", "WebFetch", {"url": "https://example.invalid"}, response={"ok": True}))
    S.append(_scn("PostToolUse NotebookEdit (autosave)", "PostToolUse", "NotebookEdit", {"notebook_path": "{REPO}/n.ipynb"},
                  dirty={"n.ipynb": "{}\n"}, response={"ok": True}))
    S.append(_scn("PostToolUseFailure Bash", "PostToolUseFailure", "Bash", {"command": "false"}, extra={"error": "exit 1"}))
    S.append(_scn("PostToolUseFailure Edit", "PostToolUseFailure", "Edit", {"file_path": "{REPO}/x.py"}, extra={"error": "no match"}))
    # Stop
    S.append(_scn("Stop: ordinary short reply", "Stop", reply="The file says hello.", user="what does notes.txt say?",
                  committed={"notes.txt": "hello\n"}))
    S.append(_scn("Stop: reply after writing an uncommitted source file", "Stop", reply="I wrote app.py.", user="add app.py",
                  written=["app.py"], dirty={"app.py": "print(1)\n"}))
    S.append(_scn("Stop: committed work with a plain summary", "Stop",
                  reply="Done. I added app.py and committed it on AjsAgent/replay.\n\nFiles: app.py\nChecked by running python app.py, which printed 1.",
                  user="add app.py", written=["app.py"], committed={"app.py": "print(1)\n"}))
    S.append(_scn("Stop: success claim without evidence", "Stop", reply="All tests pass and the feature works correctly.",
                  user="did the fix work?"))
    S.append(_scn("Stop: says it cannot be done", "Stop", reply="That cannot be done: the API does not exist.",
                  user="call the API"))
    S.append(_scn("Stop: long reply of 200 words", "Stop", reply=" ".join(["word"] * 200), user="explain"))
    S.append(_scn("Stop: reply on main", "Stop", reply="Looked at it.", user="look", branch="main"))
    # Subagents
    S.append(_scn("SubagentStart general-purpose", "SubagentStart", extra={"agent_id": "a1", "agent_type": "general-purpose"}))
    S.append(_scn("SubagentStart Explore", "SubagentStart", extra={"agent_id": "a2", "agent_type": "Explore"}))
    S.append(_scn("SubagentStop that left a file uncommitted", "SubagentStop", reply="I wrote b.py.", written=["b.py"],
                  dirty={"b.py": "x=1\n"}, extra={"agent_id": "a3", "agent_type": "general-purpose"}))
    S.append(_scn("SubagentStop that only read a file", "SubagentStop", reply="notes.txt says hello.",
                  committed={"notes.txt": "hello\n"}, extra={"agent_id": "a4", "agent_type": "general-purpose"}))
    S.append(_scn("PermissionRequest Bash", "PermissionRequest", "Bash", {"command": "ls"}))
    return S


# --- running --------------------------------------------------------------------------------------------------

def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", repo, *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def _write(repo, rel, content):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def make_repo(repo, scn, env):
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", scn["branch"], env=env)
    _write(repo, "README.md", "readme\n")
    _write(repo, "docs/.gitkeep", "")
    for rel, c in scn["committed"].items():
        _write(repo, rel, c)
    _git(repo, "add", "-A", env=env)
    _git(repo, "commit", "-q", "-m", "init", env=env)
    for rel, c in scn["dirty"].items():
        _write(repo, rel, c)
    for rel, c in scn["staged"].items():
        _write(repo, rel, c)
        _git(repo, "add", rel, env=env)
    if scn["stage"]:
        with open(os.path.join(repo, ".git", "house-rules-loop.json"), "w", encoding="utf-8") as f:
            json.dump({"feature": "replay", "stage": scn["stage"], "skip": False, "approvals": []}, f)


def make_transcript(path, scn):
    ts = "2026-11-02T01:00:0%dZ"
    lines = [json.dumps({"type": "user", "origin": {"kind": "human"}, "timestamp": ts % 0, "uuid": "u-1",
                         "message": {"role": "user", "content": scn["user"]}})]
    for i, rel in enumerate(scn["written"]):
        lines.append(json.dumps({"type": "assistant", "timestamp": ts % (1 + i), "uuid": "a-%d" % i, "message": {
            "role": "assistant", "content": [{"type": "tool_use", "id": "t%d" % i, "name": "Write",
                                              "input": {"file_path": os.path.join(os.path.dirname(path), "repo", rel),
                                                        "content": "x"}}]}}))
    lines.append(json.dumps({"type": "assistant", "timestamp": ts % 9, "uuid": "a-final", "message": {
        "role": "assistant", "content": [{"type": "text", "text": scn["reply"] or ""}]}}))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def build_payload(scn, repo, transcript):
    p = {"session_id": "replay-" + re.sub(r"\W+", "-", scn["name"]).lower()[:40], "cwd": repo,
         "hook_event_name": scn["event"], "transcript_path": transcript, "permission_mode": "default"}
    if scn["tool"]:
        p["tool_name"] = scn["tool"]
        p["tool_input"] = json.loads(json.dumps(scn["tool_input"]).replace("{REPO}", repo.replace("\\", "/")))
        p["tool_use_id"] = "toolu_replay"
    if scn["prompt"] is not None:
        p["prompt"] = scn["prompt"]
    if scn["event"] == "PostToolUse":
        p["tool_response"] = scn["response"]
    if scn["event"] in ("Stop", "SubagentStop"):
        p["stop_hook_active"] = False
        p["last_assistant_message"] = scn["reply"] or ""
    if scn["event"] == "SubagentStop":
        p["agent_transcript_path"] = transcript
    p.update(scn["extra"])
    return p


def base_env(home, fakebin, version):
    env = {"PATH": fakebin + os.pathsep + os.environ.get("PATH", ""), "HOME": home,
           "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude"), "LANG": "C.UTF-8",
           "GIT_CONFIG_GLOBAL": os.path.join(home, "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
           "HOUSE_RULES_PYTHON": sys.executable, "HOUSE_RULES_WORKTRAIL_DIR": os.path.join(home, "worktrail"),
           "HOUSE_RULES_VC_MARKETPLACE": version, "HOUSE_RULES_VC_GITHUB": version,
           "HOUSE_RULES_VC_CLAUDE": '["false"]', "HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON": os.path.join(home, "no-installed.json"),
           "HOUSE_RULES_MEMORY_DIR": os.path.join(home, "memory"), "HOUSE_RULES_LOOP_LABELS_FILE": os.path.join(home, "no-labels.json"),
           "HOUSE_RULES_AGENTS_STATE": os.path.join(home, "agents-state.json"), "TMPDIR": os.path.join(home, "tmp")}
    os.makedirs(env["TMPDIR"], exist_ok=True)
    return env


def setup_home(home):
    os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
    fb = os.path.join(home, "fakebin")
    os.makedirs(fb, exist_ok=True)
    with open(os.path.join(fb, "gh"), "w") as f:
        f.write("#!/bin/sh\necho 'gh: fake failing gh, GitHub is never called by the replay' >&2\nexit 1\n")
    os.chmod(os.path.join(fb, "gh"), 0o755)
    with open(os.path.join(home, "gitconfig"), "w") as f:
        f.write("[user]\n\tname = replay\n\temail = replay@example.invalid\n[init]\n\tdefaultBranch = main\n")
    return fb


def run_one_hook(plugin, entry, payload, env):
    e = dict(env)
    e["CLAUDE_PLUGIN_ROOT"] = plugin["dir"]
    e["HOUSE_RULES_VC_MARKETPLACE"] = e["HOUSE_RULES_VC_GITHUB"] = plugin["version"] or "0"
    cmd = entry["command"].replace("${CLAUDE_PLUGIN_ROOT}", plugin["dir"])
    try:
        pr = subprocess.run(["sh", "-c", cmd], input=json.dumps(payload).encode(), capture_output=True, env=e,
                            cwd=payload["cwd"], timeout=min(entry["timeout"], 90))
    except subprocess.TimeoutExpired:
        return {"decisions": [], "blocks": [], "context": [], "system": [], "stderr": [], "misc": ["TIMEOUT in " + entry["name"]]}
    return parse_output(pr.returncode, pr.stdout.decode("utf-8", "replace"), pr.stderr.decode("utf-8", "replace"))


def normalise(text, subs):
    for pat, rep in subs:
        text = text.replace(pat, rep)
    return text


def run_side(label, plugins, scn_list, workdir, root_tokens):
    versions = [p["version"] for p in plugins if p["version"]]
    """{scenario name: {combined fields, per-hook list}} for one plugin set."""
    results = {}
    for scn in scn_list:
        home = os.path.join(workdir, label, re.sub(r"\W+", "_", scn["name"])[:50])
        shutil.rmtree(home, ignore_errors=True)
        fakebin = setup_home(home)
        env = base_env(home, fakebin, "0")
        repo = os.path.join(home, "repo")
        make_repo(repo, scn, env)
        transcript = os.path.join(home, "transcript.jsonl")
        make_transcript(transcript, scn)
        payload = build_payload(scn, repo, transcript)
        outs, ran = [], []
        for pl in plugins:
            for entry in pl["entries"]:
                if entry["event"] == scn["event"] and matches(entry, scn["tool"]):
                    outs.append(run_one_hook(pl, entry, payload, env))
                    ran.append("%s:%s" % (pl["name"], entry["name"]))
        comb = combine(outs)
        subs = [(repo, "<REPO>"), (home, "<HOME>")] + root_tokens + [(v, "<VERSION>") for v in versions]
        for f in FIELDS:
            comb[f] = [normalise(t, subs) for t in comb[f]]
        comb["ran"] = ran
        results[scn["name"]] = comb
    return results


def coverage(plugins, scn_list, label):
    """Hook entries no scenario reaches."""
    missed = []
    for pl in plugins:
        for e in pl["entries"]:
            if not any(s["event"] == e["event"] and matches(e, s["tool"]) for s in scn_list):
                missed.append("%s %s %s:%s" % (label, e["event"], pl["name"], e["name"]))
    return missed


def replay(old_plugins, new_plugins, scn_list, workdir):
    def tokens(pls, is_new):
        t = []
        for pl in pls:
            tok = "<RE>" if (is_new and pl["name"] == "rule-enforcement") else "<HR>"
            t.append((pl["dir"], tok))
        return sorted(t, key=lambda x: -len(x[0]))
    old = run_side("old", old_plugins, scn_list, workdir, tokens(old_plugins, False))
    new = run_side("new", new_plugins, scn_list, workdir, tokens(new_plugins, True))
    return old, new


def full_report(old, new, scn_list):
    rows, counts = [], collections.Counter()
    ident = 0
    for s in scn_list:
        d = compare(old[s["name"]], new[s["name"]])
        if not d:
            ident += 1
        rows.append((s, d))
        for x in d:
            counts[x["cls"]] += 1
    return rows, counts, ident


def render(rows, counts, ident, old, new, missed, old_ref, versions):
    L = ["# Plugin split: hook replay, OLD against NEW", "",
         "Generated by `tools/replay_hooks.py`. OLD = house-rules from `git archive %s` (%s). NEW = %s." % (old_ref, versions[0], versions[1]),
         "Each scenario is one recorded payload fed to every hook registered for its event, in a fresh throwaway repo on an",
         "`AjsAgent/` branch (HOME and CLAUDE_CONFIG_DIR in a temp folder, a failing fake `gh` first on PATH). Differences are",
         "line level, after the outputs of all hooks for the event are combined.", "",
         "## Counts", "", "| Class | Differences |", "|---|---|"]
    for c in CLASSES:
        L.append("| %s | %d |" % (c, counts.get(c, 0)))
    L += ["", "Scenarios: %d. Identical in OLD and NEW: %d. With at least one difference: %d." % (len(rows), ident, len(rows) - ident), ""]
    if missed:
        L += ["## Hook entries no scenario reaches", ""] + ["- " + m for m in missed] + [""]
    else:
        L += ["Every hook entry in OLD's and NEW's hooks.json is reached by at least one scenario.", ""]
    unexpl = [(s, x) for s, d in rows for x in d if x["cls"] == "UNEXPLAINED"]
    L += ["## UNEXPLAINED differences (%d)" % len(unexpl), ""]
    if not unexpl:
        L += ["None.", ""]
    for s, x in unexpl:
        L += ["- **%s** (%s %s), `%s`, only in %s:" % (s["name"], s["event"], s["tool"], x["field"], x["side"]), "", "  > " + x["line"], ""]
    L += ["## Every difference, by scenario", ""]
    for s, d in rows:
        if not d:
            continue
        L += ["### %s (%s %s)" % (s["name"], s["event"], s["tool"]), "",
              "Hooks run: OLD %s ; NEW %s" % (", ".join(old[s["name"]]["ran"]) or "none", ", ".join(new[s["name"]]["ran"]) or "none"), ""]
        for x in d:
            L.append("- [%s] `%s` only in %s: %s" % (x["cls"], x["field"], x["side"], x["line"] if len(x["line"]) < 600 else x["line"][:600] + " ..."))
        L.append("")
    L += ["## Scenarios with no difference", ""]
    for s in [s for s, d in rows if not d]:
        o = old[s["name"]]
        gave = ", ".join("%s %d" % (f, len(o[f])) for f in FIELDS if o[f]) or "nothing"
        first = (o["decisions"] or o["blocks"] or [""])[0][:60].replace("\n", " ")
        L.append("- %s (%s %s): hooks run %s; both gave %s%s" % (s["name"], s["event"], s["tool"],
                 ", ".join(o["ran"]) or "none", gave, (" [" + first + "...]") if first else ""))
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-ref", default="origin/main")
    ap.add_argument("--report", default="")
    ap.add_argument("--keep", default="")
    a = ap.parse_args(argv)
    work = a.keep or tempfile.mkdtemp(prefix="replay-hooks-")
    os.makedirs(work, exist_ok=True)
    try:
        old_dir = os.path.join(work, "old-src")
        os.makedirs(old_dir, exist_ok=True)
        old_plugins = load_plugins(extract_old(a.old_ref, old_dir), only=["house-rules"])
        new_plugins = load_plugins(os.path.join(ROOT, PLUGINS_REL))
        scn_list = scenarios()
        missed = coverage(old_plugins, scn_list, "OLD") + coverage(new_plugins, scn_list, "NEW")
        old, new = replay(old_plugins, new_plugins, scn_list, work)
        rows, counts, ident = full_report(old, new, scn_list)
        versions = ("house-rules %s" % old_plugins[0]["version"],
                    ", ".join("%s %s" % (p["name"], p["version"]) for p in new_plugins))
        text = render(rows, counts, ident, old, new, missed, a.old_ref, versions)
        if a.report:
            with open(a.report, "w", encoding="utf-8") as f:
                f.write(text)
        print(text if not a.report else "\n".join(text.split("\n")[:25]))
        return 1 if counts.get("UNEXPLAINED") or missed else 0
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
