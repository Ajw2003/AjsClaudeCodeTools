"""house_rules.bigfiles - big files go into git only when aj asks, within the LFS allowance (#511, Phase 2 step 4).

Three parts:
  - a commit check, registered on the guard: a file over BIG_FILE_BYTES is refused unless aj approved its path
    ("LFS approved: <path>") and Git LFS tracks it; a file inside a regenerated folder is refused;
  - lfs_apply, called from design_loop._loop_apply: reads aj's "LFS approved: <path>" line, measures the file,
    compares it with the LFS allowance, and records the path in the stage file;
  - event_diskreport, a SessionStart handler: names helper worktrees and regenerated folders over DISK_REPORT_BYTES.

STDLIB ONLY, like hook.py. Nothing here guesses: when a size or a total cannot be read, the note says so.
"""

import json
import os
import re
import subprocess
import time

from house_rules import core
from house_rules.core import emit

# A starting value, not a measured one: GitHub rejects a single file over 100 MB, and 50 MB is where it warns.
BIG_FILE_BYTES = 50 * 1024 * 1024
# From GitHub's billing docs (Git LFS: 10 GiB of free storage per account), read 2026-11-11.
LFS_FREE_BYTES = 10 * 1024**3
# A starting value: a folder under this is not worth a line at session start.
DISK_REPORT_BYTES = 5 * 1024**3
DISK_REPORT_SECONDS = 6.0
BIGFILES_GIT_BUDGET = 2.0
REGENERATED_DIRS = ("Library", "Temp", "obj", "Builds", "node_modules")
_DISK_DEPTH = 4

_LFS_LINE_RE = re.compile(r"^[ \t]*LFS[ \t]+approved[ \t]*:[ \t]*(\S.*?)[ \t]*$", re.IGNORECASE | re.MULTILINE)
_OTHER_REPO_RE = re.compile(r"(^|\s)(--git-dir|--work-tree)")


def _mb(n):
    return "%.1f MB" % (n / (1024.0 * 1024.0))


def _gb(n):
    return "%.1f GB" % (n / 1024.0**3)


def _real_size(path):
    """Size of the file's real content: the working-tree size, or the `size` line when the file on disk is itself an
    LFS pointer. None when it cannot be read."""
    try:
        size = os.stat(path).st_size
        if size < 1024:
            with open(path, "rb") as f:
                head = f.read(1024).decode("utf-8", "replace")
            if head.startswith("version https://git-lfs.github.com/spec"):
                m = re.search(r"^size (\d+)$", head, re.MULTILINE)
                if m:
                    return int(m.group(1))
        return size
    except OSError:
        return None


def _is_lfs(top, rel, deadline):
    """True/False from `git check-attr filter`; None when it could not be asked in time."""
    remaining = deadline - time.time()
    if remaining <= 0:
        return None
    try:
        proc = subprocess.run(["git", "check-attr", "filter", "--", rel], cwd=top, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=remaining)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip().endswith(": filter: lfs")


def _decoded(payload, subject):
    try:
        data = json.loads(payload)
        cmd = data["tool_input"]["command"]
        if isinstance(cmd, str):
            return cmd
    except (TypeError, KeyError, ValueError):
        pass
    return core._decoded_command(subject)


def _bigfile_guard(subject, payload):
    """None when this is not a commit or nothing is wrong; ("deny", reason, None) for a refusal;
    ("note", "", text) when sizes could not be read, said in one line and never refused on a guess."""
    if not core._GIT_COMMIT_RE.search(subject):
        return None
    where, moved_unclear = core._command_dir(payload)
    if _OTHER_REPO_RE.search(subject) or moved_unclear:
        return None  # another repo: the branch and files this command acts on are not the ones in view
    deadline = time.time() + BIGFILES_GIT_BUDGET

    def run_git(args):
        remaining = deadline - time.time()
        if remaining <= 0:
            raise RuntimeError("the big-file check's time budget ran out")
        proc = subprocess.run(["git"] + args, cwd=where, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=remaining)
        if proc.returncode != 0:
            raise RuntimeError("git %s exited %d" % (" ".join(args), proc.returncode))
        return [p for p in proc.stdout.decode("utf-8", "replace").splitlines() if p.strip()]

    try:
        from house_rules import docs
        top = run_git(["rev-parse", "--show-toplevel"])[0]
        files = sorted(docs._commit_effective_files(_decoded(payload, subject), run_git))
    except Exception as exc:
        return ("note", "", "House rules, big files: could not tell what this commit includes (%s), so its file "
                "sizes were not checked." % exc)

    refusals, unread = [], []
    approved = _approved_paths(top)
    for rel in files:
        parts = rel.split("/")
        regen = next((p for p in parts[:-1] if p in REGENERATED_DIRS), None)
        if regen:
            refusals.append("%s is inside `%s/`, a folder the tools regenerate. Add the line `%s/` to .gitignore "
                            "(and `git rm -r --cached %s/` if it is already tracked) instead of committing it."
                            % (rel, regen, regen, regen))
            continue
        path = os.path.join(top, *parts)
        if not os.path.isfile(path):
            continue  # deleted in this commit
        size = _real_size(path)
        if size is None:
            unread.append(rel)
            continue
        if size <= BIG_FILE_BYTES:
            continue
        lfs = _is_lfs(top, rel, deadline)
        if lfs is None:
            unread.append(rel)
            continue
        if rel in approved and lfs:
            continue
        why = []
        if rel not in approved:
            why.append("aj has not approved it")
        if not lfs:
            why.append("Git LFS does not track it")
        refusals.append("%s is %s, over the %s limit for a plain commit, and %s. Keep it out of git with the "
                        ".gitignore line `%s`, or if aj wants it stored, aj can write \"LFS approved: %s\" "
                        "(I then check the LFS allowance and track it)."
                        % (rel, _mb(size), _mb(BIG_FILE_BYTES), " and ".join(why), rel, rel))
    if refusals:
        return ("deny", "House rules, big files go into git only when aj asks:\n  - " + "\n  - ".join(refusals), None)
    if unread:
        return ("note", "", "House rules, big files: could not read the size of %s in time, so it was not checked."
                % ", ".join(unread))
    return None


def _approved_paths(top):
    try:
        from house_rules import design_loop
        _top, git_dir = core._issues_locate(top)
        if not git_dir:
            return set()
        state, _problem = design_loop._loop_read(git_dir)
        return set((state or {}).get("lfs_approved") or [])
    except Exception:
        return set()


core.register_guard_issue(_bigfile_guard)


# --- aj's "LFS approved: <path>" ------------------------------------------------------------------


def _git_out(top, args, timeout=5):
    proc = subprocess.run(["git"] + args, cwd=top, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("git %s exited %d" % (" ".join(args), proc.returncode))
    return proc.stdout.decode("utf-8", "replace")


def _gh(args, timeout=5):
    proc = subprocess.run(["gh"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("gh %s exited %d" % (args[0], proc.returncode))
    return proc.stdout.decode("utf-8", "replace")


def _used_from_api():
    """Bytes of LFS storage the account uses, from the billing usage report. Raises when the call fails or the
    shape is not understood (the caller then falls back to this repo's own LFS objects)."""
    login = _gh(["api", "user", "--jq", ".login"]).strip()
    if not re.match(r"^[\w-]+$", login):
        raise ValueError("no login")
    data = json.loads(_gh(["api", "/users/%s/settings/billing/usage" % login]))
    items = data.get("usageItems") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("no usageItems")
    total, seen = 0.0, False
    for it in items:
        if not isinstance(it, dict):
            continue
        label = ("%s %s" % (it.get("product", ""), it.get("sku", ""))).lower()
        if "lfs" not in label or "storage" not in label:
            continue
        unit = str(it.get("unitType", "")).lower()
        qty = it.get("quantity")
        if not isinstance(qty, (int, float)) or unit not in ("gb", "gigabyte", "gigabytes", "gib"):
            raise ValueError("unit %r not understood" % unit)
        total += qty * 1024**3
        seen = True
    if not seen:
        return 0
    return int(total)


_SIZE_UNITS = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}


def _used_from_repo(top):
    """Bytes of every LFS object this repo tracks. Raises when git-lfs cannot say."""
    try:
        data = json.loads(_git_out(top, ["lfs", "ls-files", "--json"], 10))
        files = data.get("files") or []
        return sum(int(f["size"]) for f in files)
    except (RuntimeError, ValueError, KeyError, TypeError, OSError):
        pass
    total = 0
    for line in _git_out(top, ["lfs", "ls-files", "--size"], 10).splitlines():
        m = re.search(r"\(([\d.]+)\s*([KMGT]?B)\)\s*$", line)
        if not m:
            raise ValueError("could not read %r" % line)
        total += int(float(m.group(1)) * _SIZE_UNITS[m.group(2)])
    return total


def _lfs_used(top):
    """(bytes or None, source "api"|"repo"|"", problem). The stand-ins HOUSE_RULES_LFS_USED_BYTES and
    HOUSE_RULES_LFS_USED_SOURCE replace the lookups in tests."""
    stand = os.environ.get("HOUSE_RULES_LFS_USED_BYTES", "").strip()
    if stand:
        try:
            src = os.environ.get("HOUSE_RULES_LFS_USED_SOURCE", "api").strip().lower()
            return int(stand), ("repo" if src == "repo" else "api"), ""
        except ValueError:
            return None, "", "HOUSE_RULES_LFS_USED_BYTES is not an integer"
    try:
        return _used_from_api(), "api", ""
    except Exception as exc:
        api_problem = "%s: %s" % (type(exc).__name__, exc)
    try:
        return _used_from_repo(top), "repo", ""
    except Exception as exc:
        return None, "", "billing usage (%s) and this repo's LFS objects (%s: %s) were both unreadable" % (
            api_problem, type(exc).__name__, exc)


def _lfs_one(state, top, raw):
    rel = raw.strip().strip("\"'`").replace("\\", "/")
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
        return 'Big files: aj wrote "LFS approved: %s", which is not a path inside this repo, so nothing was recorded.' % raw
    rel = os.path.normpath(rel).replace("\\", "/")
    path = os.path.join(top, *rel.split("/"))
    size = _real_size(path) if os.path.isfile(path) else None
    if size is None:
        return ('Big files: aj wrote "LFS approved: %s", but there is no readable file at %s, so nothing was '
                "recorded." % (rel, path))
    approved = state.setdefault("lfs_approved", [])
    pending = state.setdefault("lfs_pending", [])
    cmds = ('Run `git lfs track "%s"`, then `git add .gitattributes "%s"`, then commit.' % (rel, rel))
    if rel in approved:
        return 'Big files: "%s" is already approved for LFS. %s' % (rel, cmds)
    used, source, problem = _lfs_used(top)
    if used is None:
        return ('Big files: aj wrote "LFS approved: %s" (%s), but I could not read the LFS storage in use (%s), so '
                "nothing was recorded." % (rel, _mb(size), problem))
    scope = "" if source == "api" else " (this repo only; other repos were not counted)"
    if used + size > LFS_FREE_BYTES:
        return ('Big files: aj wrote "LFS approved: %s", but %s of LFS storage is used%s and the file is %s, '
                "together %s, over the free allowance of %s. Nothing was recorded."
                % (rel, _gb(used), scope, _mb(size), _gb(used + size), _gb(LFS_FREE_BYTES)))
    if source == "api":
        approved.append(rel)
        if rel in pending:
            pending.remove(rel)
        return ('Big files: aj wrote "LFS approved: %s". It is %s; LFS storage in use is %s of the free %s. '
                "Recorded it as approved. %s" % (rel, _mb(size), _gb(used), _gb(LFS_FREE_BYTES), cmds))
    if rel in pending:
        pending.remove(rel)
        approved.append(rel)
        return ('Big files: aj confirmed "LFS approved: %s" a second time. Recorded it as approved (%s; this repo\'s '
                "LFS objects total %s of the free %s, other repos not counted). %s"
                % (rel, _mb(size), _gb(used), _gb(LFS_FREE_BYTES), cmds))
    pending.append(rel)
    return ('Big files: aj wrote "LFS approved: %s". It is %s and fits: this repo\'s LFS objects total %s of the '
            "free %s, but I could not read the account's usage, so other repos were not counted. Nothing is approved "
            'yet: aj, send the same line "LFS approved: %s" again to confirm.' % (rel, _mb(size), _gb(used),
                                                                                  _gb(LFS_FREE_BYTES), rel))


def lfs_apply(state, text, top):
    """Note for the model, or "" when the message has no "LFS approved:" line. Mutates state. Quoted (`>`) lines
    do not count; the caller has already thrown out relayed messages."""
    own = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith(">"))
    paths = _LFS_LINE_RE.findall(own)
    if not paths:
        return ""
    return " ".join(_lfs_one(state, top, p) for p in paths)


# --- session-start disk report --------------------------------------------------------------------


class _Deadline(Exception):
    pass


def _tree_size(path, deadline, acc):
    """Sum st_size of every file under `path` with os.scandir. acc[0] holds the running total, so a deadline
    still leaves the partial count behind. Raises _Deadline when time is up."""
    stack = [path]
    while stack:
        if time.time() > deadline:
            raise _Deadline()
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            acc[0] += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue


def _disk_candidates(roots, deadline):
    """Helper worktrees and regenerated folders under each root, depth-limited."""
    found = []
    seen = set()

    def add(p):
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            found.append(p)

    for root in roots:
        wt = os.path.join(root, ".claude", "worktrees")
        try:
            for e in os.scandir(wt):
                if e.is_dir(follow_symlinks=False):
                    add(e.path)
        except OSError:
            pass
        stack = [(root, 0)]
        while stack:
            if time.time() > deadline:
                return found, True
            d, depth = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                try:
                    if not e.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if e.name in REGENERATED_DIRS:
                    add(e.path)
                elif e.name in (".git", "worktrees") or depth + 1 >= _DISK_DEPTH:
                    continue
                else:
                    stack.append((e.path, depth + 1))
    return found, False


def event_diskreport():
    try:
        if os.environ.get("HOUSE_RULES_DISKREPORT", "on").strip().lower() in core._TOGGLE_OFF:
            return 0
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        top, git_dir = core._issues_locate(start)
        if not top:
            return 0
        roots = [top]
        try:
            from house_rules import design_loop
            main = os.path.dirname(design_loop._loop_dir(git_dir))
            if os.path.isdir(main) and os.path.realpath(main) != os.path.realpath(top):
                roots.append(main)
        except Exception:
            pass
        deadline = time.time() + DISK_REPORT_SECONDS
        cands, cut = _disk_candidates(roots, deadline)
        lines, unvisited = [], 0
        for i, c in enumerate(cands):
            acc = [0]
            try:
                _tree_size(c, deadline, acc)
                stopped = False
            except _Deadline:
                stopped = True
            if acc[0] >= DISK_REPORT_BYTES:
                if stopped:
                    lines.append("%s: at least %s (stopped counting at the time limit)" % (c, _gb(acc[0])))
                else:
                    lines.append("%s: %s" % (c, _gb(acc[0])))
            if stopped:
                unvisited = len(cands) - i - 1
                break
        if not lines and not cut and not unvisited:
            return 0  # looked, nothing over the threshold
        text = ("House rules, disk use: " + "; ".join(lines) if lines else "House rules, disk use: nothing counted "
                "over %s so far" % _gb(DISK_REPORT_BYTES))
        if cut or unvisited:
            text += " (the time limit stopped the count before every folder was looked at)"
        if lines:
            text += (". Helper worktrees can be removed once their branch is saved; regenerated folders "
                     "(Library, Temp, obj, Builds, node_modules) belong in .gitignore and can be rebuilt.")
        emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
              "systemMessage": text})
        return 0
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the disk report hit an internal error (%s: %s) and did not run "
              "for this session." % (type(exc).__name__, exc)})
        return 0
