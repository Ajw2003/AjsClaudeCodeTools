"""rule_enforcement.lock - the repeat-failure lock gate (#440, step 3 part B, choice 6A of the plugin split).

PreToolUse on Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell. While an end-of-reply check is LOCKED (it
blocked a reply three times for one message and still failed; house_lib.blocks keeps the state) this hook
refuses source-file edits and `git commit` / `git push`, naming the locked check, what it is missing and how
to supply it. It always allows the action that supplies the missing piece:

  - a commit when the commit check is the locked one (a push is still refused),
  - edits to docs/**/*.md and anything under docs/plans/ (pages, state),
  - files outside the session folder (a page's content.json in a scratch folder),
  - reading, running tests, starting the editor helper: those tools are not matched here at all.

Fail mode: if the lock state cannot be read, the hook says so in a systemMessage and ALLOWS the call. It
never refuses a tool because something is broken (that is how 2.74.0 failed, docs/3-state/ProjectState.md,
2026-10-28). A shell command is only examined for `git commit` and `git push`; a shell redirect that edits a
source file is not caught. STDLIB ONLY.
"""

import json
import os
import re

from house_lib import blocks
from house_lib.plumbing import emit, read_payload

EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")

# `git [options] commit|push`, where options are -c k=v, -C dir, --flag[=v], -x.
_GIT_RE = re.compile(
    r"(?:^|[;&|(`]\s*|\s)git(?:\s+-[cC]\s+\S+|\s+--[\w-]+(?:=\S+)?|\s+-\w+)*\s+(commit|push)\b")


def _in_docs_allowed(path):
    parts = [p for p in re.split(r"[\\/]+", path) if p]
    if any(parts[i] == "docs" and parts[i + 1] == "plans" for i in range(len(parts) - 1)):
        return True
    return path.lower().endswith(".md") and "docs" in parts[:-1]


def _inside(path, root):
    try:
        p, r = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


def _is_source_edit(ti, cwd):
    path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
    if not isinstance(path, str) or not path:
        return False, ""
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    if not _inside(full, cwd) or _in_docs_allowed(full.replace("\\", "/")):
        return False, path
    return True, path


def _refusal(locks, what):
    lines = ["House rules, repeat-failure lock: %s is refused because an end-of-reply check failed %d replies in "
             "a row and its reply was let through." % (what, blocks.BLOCK_LIMIT)]
    for name, info in sorted(locks.items()):
        lines.append("- Locked check: %s. Missing: %s To supply it: %s." % (
            name, info.get("missing") or "(not recorded)", (info.get("fix") or "(not recorded)").rstrip(".")))
    lines.append("The lock clears the moment a later reply passes that check. Meanwhile docs/*.md and docs/plans/ "
                 "edits, reading, running tests and starting the editor helper are all allowed%s." % (
                     ", and so is committing" if "commit" in locks else ""))
    return "\n".join(lines)


def decide(data, locks):
    """(refusal text or "") for this PreToolUse payload given the active locks."""
    if not locks:
        return ""
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if tool in EDIT_TOOLS:
        src, path = _is_source_edit(ti, cwd)
        return _refusal(locks, "editing the source file %s" % path) if src else ""
    if tool in SHELL_TOOLS and isinstance(ti.get("command"), str):
        m = _GIT_RE.search(ti["command"])
        if not m:
            return ""
        verb = m.group(1)
        if verb == "commit" and "commit" in locks:
            return ""  # the commit check is locked: committing is how it passes
        return _refusal(locks, "git %s" % verb)
    return ""


def event_lockgate():
    try:
        payload = read_payload()
        data = json.loads(payload) if payload else {}
        if not isinstance(data, dict):
            raise ValueError("the payload is not a JSON object")
        sid = str(data.get("session_id") or "")
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    except Exception as exc:
        emit({"systemMessage": "house-rules rule-enforcement: the repeat-failure lock could not read this tool "
                               "call (%s: %s), so it is NOT enforced for this call; the call is allowed."
                               % (type(exc).__name__, exc)})
        return 0
    try:
        locks = blocks.active_locks(cwd, sid)
    except Exception as exc:
        emit({"systemMessage": "house-rules rule-enforcement: the repeat-failure lock state could not be read "
                               "(%s: %s), so the lock is NOT enforced for this call; the call is allowed."
                               % (type(exc).__name__, exc)})
        return 0
    try:
        reason = decide(data, locks)
    except Exception as exc:
        emit({"systemMessage": "house-rules rule-enforcement: the repeat-failure lock hit an error (%s: %s) "
                               "deciding this call, so it is NOT enforced for it; the call is allowed."
                               % (type(exc).__name__, exc)})
        return 0
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    return 0
