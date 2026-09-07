#!/usr/bin/env python3
"""Move a branch onto a new base without losing commits only that branch held.

    python tools/rebase_branch.py <branch> <base>

The operation this replaces is `git checkout -B <branch> <base>`, which moves a ref and orphans
anything only that ref pointed at. Nothing warns you: the working tree is clean, `git status` is
empty, and a merged pull request makes the branch look finished. A commit pushed *after* that
merge is invisible to that reasoning and is discarded silently.

So this refuses to move the pointer while the branch holds work the base does not, and cherry-picks
that work onto the new base instead.

Comparison is by **patch-id**, via `git cherry`, not by commit sha. A commit that reached the base
through a squash or a rebase has a different sha but the same patch, and reporting it as
about-to-be-lost would train the reader to ignore this tool - which is the only way it can fail.

Exit codes: 0 the branch is on the new base, 1 refused or failed. Nothing is deleted, ever: the
branch's old tip is printed so `git reset --hard <sha>` can put it back.
"""

import subprocess
import sys


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"FAILED: git {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    branch, base = argv

    for ref in (branch, base):
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                          capture_output=True).returncode != 0:
            sys.exit(f"REFUSED: {ref!r} is not a ref this repo knows. Nothing was changed.")

    if git("status", "--porcelain"):
        sys.exit("REFUSED: the working tree is dirty. Commit or stash first - a checkout here "
                 "would carry those edits onto the new base. Nothing was changed.")

    old_tip = git("rev-parse", branch)
    print(f"{branch} is at {old_tip[:7]}")
    print(f"{base} is at {git('rev-parse', base)[:7]}")

    # `git cherry <base> <branch>` lists <branch>'s commits with a leading '+' when the base has
    # no equivalent patch, '-' when it does. The '+' lines are exactly what a ref move would lose.
    unmerged = [ln[2:] for ln in git("cherry", base, branch).splitlines() if ln.startswith("+")]

    if not unmerged:
        print(f"\nNothing on {branch} is missing from {base}. Safe to move.")
        git("checkout", "-B", branch, base)
        print(f"{branch} now points at {base}. Old tip was {old_tip[:7]} if you need it back.")
        return 0

    print(f"\n{len(unmerged)} commit(s) on {branch} are NOT in {base} - a ref move would lose these:")
    for sha in unmerged:
        print(f"  {sha[:7]}  {git('log', '-1', '--format=%s', sha)}")

    print(f"\nRebuilding {branch} from {base} and cherry-picking them instead.")
    git("checkout", "-B", branch, base)
    for sha in unmerged:
        r = subprocess.run(["git", "cherry-pick", sha], capture_output=True, text=True)
        if r.returncode != 0:
            subprocess.run(["git", "cherry-pick", "--abort"], capture_output=True)
            git("checkout", "-B", branch, old_tip)
            sys.exit(f"REFUSED: {sha[:7]} does not cherry-pick cleanly onto {base}.\n"
                     f"{branch} has been put back at {old_tip[:7]} - resolve it by hand.\n"
                     f"{r.stderr.strip()}")
        print(f"  picked {sha[:7]}")

    print(f"\n{branch} is on {base} with all {len(unmerged)} commit(s) kept. "
          f"Old tip was {old_tip[:7]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
