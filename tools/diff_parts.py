"""Split a file's changes between two commits into the parts they belong to (issue #242).

    python tools/diff_parts.py BASE HEAD PATH

prints JSON: {"path", "added", "removed", "parts": [[name, added, removed], ...]}, biggest part first.
A part is the top-level Python function, class or constant around a changed line, or the Markdown
heading above it; any other file is one part. Added lines are placed by the new file and removed
lines by the old one. A comment, decorator or blank run just above a definition belongs to that
definition, not the one before it. The totals always equal `git diff --numstat` for the file.
"""
import json
import re
import subprocess
import sys

_PY_TOP = re.compile(r"^(?:def |class |async def )([A-Za-z_]\w*)|^([A-Za-z_]\w*)\s*[:=]")
_MD_TOP = re.compile(r"^#{1,4}\s+(.+?)\s*$")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, check=True).stdout


def _show(repo, rev, path):
    proc = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (rev, path)], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""  # a file that doesn't exist on that side is empty


def owners(text, path):
    """The part each line of text belongs to, one entry per line."""
    lines = text.splitlines()
    if path.endswith(".py"):
        top = _PY_TOP
    elif path.endswith(".md"):
        top = _MD_TOP
    else:
        return ["(whole file)"] * len(lines)
    out, cur = [], "(top of file)"
    for line in lines:
        m = top.match(line)
        if m:
            cur = next(g for g in m.groups() if g)
        out.append(cur)
    if top is _PY_TOP:
        # A comment, decorator or blank run directly above a definition belongs to it.
        nxt = None
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if top.match(line):
                nxt = out[i]
            elif nxt and (not line.strip() or line.startswith(("#", "@"))):
                out[i] = nxt
            else:
                nxt = None
    return out


def parts(repo, base, head, path):
    old, new = _show(repo, base, path), _show(repo, head, path)
    old_own, new_own = owners(old, path), owners(new, path)
    diff = _git(repo, "diff", "-U0", "--no-color", base, head, "--", path)
    added, removed, o, n = {}, {}, 0, 0
    for line in diff.splitlines():
        hunk = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            o, n = int(hunk.group(1)), int(hunk.group(2))
        elif line.startswith("+") and not line.startswith("+++"):
            key = new_own[n - 1] if 0 < n <= len(new_own) else "(top of file)"
            added[key] = added.get(key, 0) + 1
            n += 1
        elif line.startswith("-") and not line.startswith("---"):
            key = old_own[o - 1] if 0 < o <= len(old_own) else "(top of file)"
            removed[key] = removed.get(key, 0) + 1
            o += 1
    names = sorted(set(added) | set(removed), key=lambda k: -(added.get(k, 0) + removed.get(k, 0)))
    return {"path": path, "added": sum(added.values()), "removed": sum(removed.values()),
            "parts": [[k, added.get(k, 0), removed.get(k, 0)] for k in names]}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python tools/diff_parts.py BASE HEAD PATH")
    repo = _git(".", "rev-parse", "--show-toplevel").strip()
    print(json.dumps(parts(repo, sys.argv[1], sys.argv[2], sys.argv[3]), indent=1))
