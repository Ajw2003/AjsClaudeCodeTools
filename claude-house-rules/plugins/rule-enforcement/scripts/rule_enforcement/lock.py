"""rule_enforcement.lock - the repeat-failure lock gate (#440, step 3 part B, choice 6A of the plugin split).

PreToolUse on Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell. While an end-of-reply check is LOCKED (it
blocked a reply three times for one message and still failed; house_lib.blocks keeps the state) this hook
refuses source-file edits and `git commit` / `git push`, naming the locked check, what it is missing and how
to supply it. It always allows the action that supplies the missing piece:

  - a commit when the commit check is the locked one (a push is still refused),
  - edits to docs/**/*.md and anything under docs/plans/ (pages, state),
  - files outside every git repository and outside the session folder (a page's content.json in a scratch folder),
  - reading, running tests, starting the editor helper: those tools are not matched here at all.

Fail mode: if the lock state cannot be read, the hook says so in a systemMessage and ALLOWS the call. It
never refuses a tool because something is broken (that is how 2.74.0 failed, docs/3-state/ProjectState.md,
2026-10-28).

The lock is decided by the repository of the TARGET: the file an Edit/Write names, each path a shell command
writes (house_lib.shellwrites: redirects, tee, sed -i, python/node writes, cp, mv, dd, truncate; a path that
cannot be read is refused too), and the directory a git commit/push acts on (git -C dir, a leading
"cd dir &&", else the call's cwd). STDLIB ONLY.
"""

import json
import os
import re

from house_lib import blocks, shellwrites
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


def _refusal(locks, what):
    lines = ["House rules, repeat-failure lock: %s is refused because an end-of-reply check failed %d replies in "
             "a row and its reply was let through." % (what, blocks.BLOCK_LIMIT)]
    for name, info in sorted(locks.items()):
        files = info.get("files") or []
        lines.append("- Locked check: %s. Missing: %s%s To supply it: %s." % (
            name, info.get("missing") or "(not recorded)",
            (" Files it named: %s." % ", ".join(files[:8])) if files else "",
            (info.get("fix") or "(not recorded)").rstrip(".")))
    lines.append("The lock clears when a later reply passes the check on what it was locked for. Meanwhile "
                 "docs/*.md and docs/plans/ edits, files outside every repository, reading, running tests and "
                 "starting the editor helper are all allowed%s." % (
                     ", and so is committing" if "commit" in locks else ""))
    return "\n".join(lines)


_CD_RE = re.compile(r"^\s*(?:cd|pushd)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)\s*(?:&&|;)")
_GIT_C_RE = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*-C\s+(\"[^\"]+\"|'[^']+'|\S+)")


def _unq(s):
    return s.strip("\"'")


def _command_dir(cmd, cwd):
    m = _CD_RE.match(cmd)
    if m:
        d = _unq(m.group(1))
        return d if os.path.isabs(d) else os.path.join(cwd, d)
    return cwd


def _target_refusal(path, base, sid, what_prefix):
    """The refusal text when `path` is a source file in a locked repository, else ""."""
    full = path if os.path.isabs(path) else os.path.join(base, path)
    locks, _scope = blocks.locks_for_target(full, base, sid)
    if not locks or _in_docs_allowed(full.replace("\\", "/")):
        return ""
    return _refusal(locks, "%s %s" % (what_prefix, path))


def decide(data):
    """(refusal text or "") for this PreToolUse payload. The lock is looked up by the repository of each
    TARGET file (or of the git command's directory), not only by the payload's cwd. Raises when the state
    cannot be read; the caller allows the call and says so."""
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    sid = str(data.get("session_id") or "")
    if tool in EDIT_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
        if not isinstance(path, str) or not path:
            return ""
        return _target_refusal(path, cwd, sid, "editing the source file")
    if tool in SHELL_TOOLS and isinstance(ti.get("command"), str):
        cmd = shellwrites._apply_assigns(ti["command"])
        base = _command_dir(cmd, cwd)
        t1, u1 = shellwrites.script_write_targets(cmd)
        t2, u2 = shellwrites.copy_targets(cmd)
        for t in t1 + t2:
            r = _target_refusal(t, base, sid, "this shell command writing the source file")
            if r:
                return r
        if u1 or u2:
            locks, _s = blocks.locks_for_target(base, base, sid)
            if locks:
                return _refusal(locks, "this shell command (it writes a file whose path cannot be read from the "
                                       "command text; use the Edit or Write tool, or write the path out)")
        for m in _GIT_RE.finditer(cmd):
            verb = m.group(1)
            gc = _GIT_C_RE.search(cmd)
            gdir = _unq(gc.group(1)) if gc else base
            gdir = gdir if os.path.isabs(gdir) else os.path.join(base, gdir)
            locks, _s = blocks.locks_for_target(gdir, base, sid)
            if not locks or (verb == "commit" and "commit" in locks):
                continue  # the commit check is locked there: committing is how it passes
            return _refusal(locks, "git %s" % verb)
    return ""


def event_lockgate():
    try:
        payload = read_payload()
        data = json.loads(payload) if payload else {}
        if not isinstance(data, dict):
            raise ValueError("the payload is not a JSON object")
    except Exception as exc:
        emit({"systemMessage": "house-rules rule-enforcement: the repeat-failure lock could not read this tool "
                               "call (%s: %s), so it is NOT enforced for this call; the call is allowed."
                               % (type(exc).__name__, exc)})
        return 0
    try:
        reason = decide(data)
    except Exception as exc:
        emit({"systemMessage": "house-rules rule-enforcement: the repeat-failure lock could not decide this call "
                               "(%s: %s), so it is NOT enforced for it; the call is allowed."
                               % (type(exc).__name__, exc)})
        return 0
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    return 0
