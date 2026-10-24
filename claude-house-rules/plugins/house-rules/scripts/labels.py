#!/usr/bin/env python3
"""Create only the missing house labels on a GitHub repo (#275). Python stdlib only.

Creating is the only write: no overwrite flag, no edit, no delete. A label that exists with a
different colour or description is left alone. ensure_labels never raises; every failure is
reported in its result. Tests set HOUSE_RULES_REPO_LABELS_FILE to a JSON file
{"owner/repo": ["label", ...]} that stands in for GitHub.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_rules import settings  # noqa: E402

HOUSE_LABELS = tuple(settings.HOUSE_LABELS)  # the names stay literal: existing labels carry them

REPO_LABELS_FILE_ENV = "HOUSE_RULES_REPO_LABELS_FILE"
GH_SECONDS = 5


def _first_line(text, fallback):
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else fallback


def _gh(args):
    proc = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=GH_SECONDS)
    if proc.returncode != 0:
        raise RuntimeError(_first_line(proc.stderr or proc.stdout, "gh exited %d" % proc.returncode))
    return proc.stdout


def _create_one(repo, label):
    """'created', 'present', or 'failed:<reason>'."""
    name, colour, desc = label
    try:
        _gh(["label", "create", name, "--repo", repo, "--color", colour, "--description", desc])
        return "created"
    except subprocess.TimeoutExpired:
        return "failed:timed out after %d seconds" % GH_SECONDS
    except (OSError, RuntimeError) as exc:
        if "already exists" in str(exc).lower():
            return "present"
        return "failed:%s" % exc


def ensure_labels(repo):
    result = {"created": [], "present": [], "failed": [], "error": ""}
    try:
        stand_in = os.environ.get(REPO_LABELS_FILE_ENV)
        data = None
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                data = json.load(f)
            have = [str(x) for x in data.get(repo, [])]
        else:
            if not shutil.which("gh"):
                result["error"] = "gh is not installed"
                return result
            out = _gh(["api", "repos/%s/labels" % repo, "--paginate", "--jq", ".[].name"])
            have = [l.strip() for l in out.splitlines() if l.strip()]
        low = {h.lower() for h in have}
        missing = []
        for label in HOUSE_LABELS:
            if label[0].lower() in low:
                result["present"].append(label[0])
            else:
                missing.append(label)
        if data is not None:
            for label in missing:
                data.setdefault(repo, []).append(label[0])
                result["created"].append(label[0])
            if missing:
                with open(stand_in, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        elif missing:
            with ThreadPoolExecutor(max_workers=len(missing)) as pool:
                outcomes = list(pool.map(lambda l: _create_one(repo, l), missing))
            for label, outcome in zip(missing, outcomes):
                if outcome == "created":
                    result["created"].append(label[0])
                elif outcome == "present":
                    result["present"].append(label[0])
                else:
                    result["failed"].append([label[0], outcome[len("failed:"):]])
    except subprocess.TimeoutExpired:
        result["error"] = "gh timed out after %d seconds" % GH_SECONDS
    except (OSError, ValueError, RuntimeError, AttributeError, TypeError) as exc:
        result["error"] = _first_line(str(exc), exc.__class__.__name__)
    return result


def repo_from_git(git_dir):
    """(owner/repo or None, note) from <git_dir>/config's remote url(s), no subprocess."""
    try:
        with open(os.path.join(git_dir, "config"), "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return None, "could not read .git/config (%s)" % exc
    urls = re.findall(r"(?m)^\s*url\s*=\s*(\S+)", text)
    if not urls:
        return None, ".git/config has no remote url"
    for url in urls:
        m = (re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
             or re.match(r"^(?:ssh://)?git@github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
             or re.match(r"^https?://[^/]+/(?:.*/)?git/([^/]+)/([^/]+?)(?:\.git)?/?$", url))
        if m:
            return "%s/%s" % (m.group(1), m.group(2)), None
    return None, "no remote url is a GitHub owner/repo form (%s)" % urls[0]


def _names(names):
    quoted = ["`%s`" % n for n in names]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " and " + quoted[-1]


def summary_note(result, repo="this repo"):
    """One plain-English sentence; "" when nothing was created and nothing failed."""
    if result.get("error"):
        return ("house-rules: could not check %s's labels (%s), so missing house labels were not created."
                % (repo, result["error"]))
    parts = []
    if result.get("created"):
        parts.append("created the missing labels %s on %s" % (_names(result["created"]), repo))
    if result.get("failed"):
        parts.append("could not create %s on %s (%s)" % (
            _names([f[0] for f in result["failed"]]), repo,
            "; ".join("%s: %s" % (f[0], f[1]) for f in result["failed"])))
    return "house-rules: " + ", and ".join(parts) + "." if parts else ""


def _git_dir_of(start):
    """The common git directory above `start` (a worktree's .git file is followed), or None."""
    d = os.path.abspath(start)
    while True:
        dot = os.path.join(d, ".git")
        if os.path.isdir(dot):
            return dot
        if os.path.isfile(dot):
            with open(dot, "r", encoding="utf-8") as f:
                line = f.read().strip()
            if line.startswith("gitdir:"):
                gd = os.path.normpath(os.path.join(d, line[len("gitdir:"):].strip()))
                common = os.path.join(gd, "commondir")
                if os.path.isfile(common):
                    with open(common, "r", encoding="utf-8") as f:
                        return os.path.normpath(os.path.join(gd, f.read().strip()))
                return gd
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main(argv):
    """`labels.py [owner/repo]` (#277): set up the house labels on the named repo, or on this folder's
    GitHub remote. Prints what it created, what was already there and what failed. Exit 0 when every
    house label is now present, 1 when some could not be created, 2 when the repo could not be checked."""
    if len(argv) > 1:
        print("usage: labels.py [owner/repo]")
        return 2
    if argv:
        repo = argv[0]
        if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", repo):
            print("labels: %r is not an owner/repo name, such as owner/repo" % repo)
            return 2
    else:
        git_dir = _git_dir_of(os.getcwd())
        if not git_dir:
            print("labels: this folder is not inside a git repository; name the repo, such as labels.py owner/repo")
            return 2
        repo, why = repo_from_git(git_dir)
        if not repo:
            print("labels: could not tell this folder's GitHub repo (%s); name it, such as labels.py owner/repo" % why)
            return 2
    result = ensure_labels(repo)
    if result["error"]:
        print("labels: could not check %s's labels: %s" % (repo, result["error"]))
        return 2
    print("labels on %s:" % repo)
    for name in result["created"]:
        print("  created         %s" % name)
    for name in result["present"]:
        print("  already there   %s" % name)
    for name, why in result["failed"]:
        print("  FAILED          %s (%s)" % (name, why))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
