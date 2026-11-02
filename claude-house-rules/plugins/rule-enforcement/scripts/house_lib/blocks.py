"""house_lib.blocks - the repeat-failure counter and lock (#440, choice 6A of the plugin split).

An end-of-reply (Stop) check that fails blocks the reply up to BLOCK_LIMIT (3) times for the same message
of aj's. After the third block the reply goes through and the check is LOCKED: a PreToolUse hook (in the
rule-enforcement plugin) refuses source edits and commits until a later Stop finds the check passing.

Any plugin's Stop check calls `record_stop`; the PreToolUse hook calls `active_locks`. Each check counts
its OWN blocks, keyed by check name, session id and the message it answers; `stop_hook_active` is shared
between plugins and is never used to count (docs/4-systems/plugin-split.md, "Step 1 findings").

State file: `<git common dir>/house-rules/check-blocks.json` (never committed: it is inside .git), else a
session-keyed file in the temp folder outside a repository. STDLIB ONLY.

Failure: `record_stop` and `active_locks` RAISE OSError/ValueError when the state cannot be read or written.
Every caller must say so loudly and fail open; a caller that cannot read the state never refuses a tool.
"""

import hashlib
import json
import os
import re
import tempfile
import time

BLOCK_LIMIT = 3
STATE_FILE = "check-blocks.json"


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _git_dir(start):
    d = os.path.abspath(start or os.getcwd())
    while True:
        cand = os.path.join(d, ".git")
        if os.path.isdir(cand):
            return cand
        if os.path.isfile(cand):
            for line in _read(cand).splitlines():
                if line.startswith("gitdir:"):
                    p = line.split(":", 1)[1].strip()
                    return os.path.abspath(p if os.path.isabs(p) else os.path.join(d, p))
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def common_git_dir(start):
    """The git directory shared by every worktree of `start`'s repository, or None outside one."""
    gd = _git_dir(start)
    if not gd:
        return None
    cd = os.path.join(gd, "commondir")
    if os.path.isfile(cd):
        rel = _read(cd).strip()
        if rel:
            return os.path.abspath(rel if os.path.isabs(rel) else os.path.join(gd, rel))
    return gd


def state_path(cwd, session_id):
    cd = common_git_dir(cwd)
    if cd:
        return os.path.join(cd, "house-rules", STATE_FILE)
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-check-blocks-%s.json" % safe)


def message_mark(user_id, user_text=""):
    """A short key for 'the message this reply answers': the transcript record's uuid when it has one."""
    return hashlib.sha1(("%s|%s" % (user_id or "", user_text or "")).encode("utf-8")).hexdigest()[:16]


def _load(path):
    if not os.path.isfile(path):
        return {}
    data = json.loads(_read(path))
    if not isinstance(data, dict):
        raise ValueError("%s is not a JSON object" % path)
    return data


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _entry(data, session_id):
    e = data.get(session_id)
    e = e if isinstance(e, dict) else {}
    if not isinstance(e.get("counts"), dict):
        e["counts"] = {}
    if not isinstance(e.get("locks"), dict):
        e["locks"] = {}
    return e


def record_stop(cwd, session_id, check, mark, failing, missing="", fix=""):
    """Record one Stop result for `check` and return what the caller must do:

    "pass"    the check passes: its count is reset and any lock on it cleared.
    "block"   the check fails and has blocked fewer than BLOCK_LIMIT times for this message: block the reply.
    "through" the check fails and has already blocked BLOCK_LIMIT times for this message: let the reply go
              through. The check is now locked, with `missing` (what it wants) and `fix` (how to supply it).
    Never returns "block" a fourth time for one message. Raises OSError/ValueError on unreadable state."""
    path = state_path(cwd, session_id)
    data = _load(path)
    entry = _entry(data, session_id)
    counts, locks = entry["counts"], entry["locks"]
    old = counts.get(check) if isinstance(counts.get(check), dict) else {}
    count = old.get("count", 0) if old.get("mark") == mark else 0
    if not failing:
        changed = check in counts or check in locks
        counts.pop(check, None)
        locks.pop(check, None)
        result = "pass"
    elif count < BLOCK_LIMIT:
        counts[check] = {"mark": mark, "count": count + 1}
        changed, result = True, "block"
    else:
        locks[check] = {"missing": missing, "fix": fix, "since": int(time.time())}
        changed, result = True, "through"
    if changed:
        data[session_id] = entry
        _save(path, data)
    return result


def block_count(cwd, session_id, check, mark):
    """Blocks recorded for `check` for this message (0 when none or the message is a new one)."""
    entry = _entry(_load(state_path(cwd, session_id)), session_id)
    old = entry["counts"].get(check)
    return old.get("count", 0) if isinstance(old, dict) and old.get("mark") == mark else 0


def active_locks(cwd, session_id):
    """{check: {"missing", "fix", "since"}} for every locked check of this session. Empty when none.
    Raises OSError/ValueError when the state file exists but cannot be read."""
    return dict(_entry(_load(state_path(cwd, session_id)), session_id)["locks"])


def is_locked(cwd, session_id, check=None):
    locks = active_locks(cwd, session_id)
    return bool(locks) if check is None else check in locks
