#!/usr/bin/env python3
"""pre_push_check.py — the mechanical backstop for "pushed to a branch whose PR already merged".

Why this exists: guard (the PreToolUse hook in the house-rules plugin) deliberately never shells
out or hits the network on a Bash call — a hang there would wedge the whole session, and it reads
`.git/HEAD` directly for exactly that reason (see docs/architecture.md). That means guard can
prompt on "this pushes to a remote" but it cannot know whether the PR that branch is tied to was
already merged since I last looked — that fact lives on GitHub, not in the local checkout, and
depending on me to re-check it in chat before every push is the habit failure this script exists
to replace with a mechanical one (see the CLAUDE.md entry this ships with).

A real git `pre-push` hook is the right place for that network call: a push already talks to the
network, so a slow or failed lookup here costs nothing guard's callers don't already accept, and
it runs only on the one command that matters instead of every shell call.

Protocol: git feeds this script one line per ref being pushed on stdin, each
`<local ref> <local sha1> <remote ref> <remote sha1>`. Exit non-zero to reject the push (git
prints stderr and aborts before contacting the remote); exit 0 to allow it.

FAILS OPEN on anything that isn't a clear "yes, this PR is merged": no remote, not a GitHub
remote, the API unreachable or rate-limited, a malformed response. The one thing that blocks is
an unambiguous merged-PR match for a branch being pushed. Silence on any skip reason would defeat
the point of a mechanical backstop nobody can see working, so every skip says why on stderr.
"""

import json
import re
import subprocess
import sys
import urllib.request
import urllib.error

TIMEOUT_SECONDS = 5

_GITHUB_REMOTE_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def _run_git(args):
    return subprocess.run(
        ["git"] + args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
    )


def owner_repo_from_remote(remote_name="origin"):
    """(owner, repo) for a github.com remote, or None if it can't be determined."""
    try:
        result = _run_git(["remote", "get-url", remote_name])
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"pre-push check: could not read remote {remote_name!r} ({exc}) - skipping.\n")
        return None
    if result.returncode != 0:
        sys.stderr.write(
            f"pre-push check: `git remote get-url {remote_name}` failed - skipping.\n"
        )
        return None
    m = _GITHUB_REMOTE_RE.match(result.stdout.strip())
    if not m:
        sys.stderr.write("pre-push check: remote is not github.com - skipping (nothing to check).\n")
        return None
    return m.group("owner"), m.group("repo")


def merged_pr_for_branch(owner, repo, branch):
    """Return the merged PR's html_url for `branch`, or None if there isn't one / can't tell."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/pulls"
        f"?head={owner}:{branch}&state=closed&per_page=10"
    )
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"pre-push check: GitHub API returned {exc.code} - skipping (fail open).\n")
        return None
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        sys.stderr.write(f"pre-push check: GitHub API unreachable ({exc}) - skipping (fail open).\n")
        return None

    if not isinstance(data, list):
        sys.stderr.write("pre-push check: unexpected API response shape - skipping (fail open).\n")
        return None

    for pr in data:
        if isinstance(pr, dict) and pr.get("merged_at"):
            return pr.get("html_url")
    return None


ZERO_SHA_RE = re.compile(r"^0+$")


def branches_to_check(lines):
    """Local branch names being pushed (deletes and non-branch refs excluded)."""
    branches = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, _remote_sha = parts
        if ZERO_SHA_RE.match(local_sha):
            continue  # a delete - nothing new is being pushed
        prefix = "refs/heads/"
        if remote_ref.startswith(prefix):
            branches.append(remote_ref[len(prefix):])
        elif local_ref.startswith(prefix):
            branches.append(local_ref[len(prefix):])
    return branches


def main(argv, stdin_lines):
    owner_repo = owner_repo_from_remote()
    if owner_repo is None:
        return 0
    owner, repo = owner_repo

    blocked = []
    for branch in branches_to_check(stdin_lines):
        pr_url = merged_pr_for_branch(owner, repo, branch)
        if pr_url:
            blocked.append((branch, pr_url))

    if not blocked:
        return 0

    sys.stderr.write(
        "\npre-push check: REFUSING - the PR for this branch is already merged.\n\n"
    )
    for branch, pr_url in blocked:
        sys.stderr.write(f"  branch {branch!r} -> already merged: {pr_url}\n")
    sys.stderr.write(
        "\nA merged PR can't track new commits. Restart the branch from the base branch's\n"
        "current tip (`git fetch origin <base> && git checkout -B <branch> origin/<base>`),\n"
        "carry over any unmerged commits, and push that - it will open as a new PR.\n"
        "\nTo push anyway (force-recreating a branch you know is intentionally reused),\n"
        "delete or rename it on GitHub first, or override this check once with:\n"
        "  git -c core.hooksPath=/dev/null push ...\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin.readlines()))
