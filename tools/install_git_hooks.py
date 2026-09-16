#!/usr/bin/env python3
"""install_git_hooks.py — points git's global core.hooksPath at tools/git-hooks, so the
pre-push merged-PR check (tools/git-hooks/pre_push_check.py) runs on every repo on this
machine, not just this one.

Why a global hooksPath rather than copying a hook into each repo's .git/hooks: this plugin's
whole premise is rules that follow the device, not files that have to be copied around per
project (see the top of CLAUDE.md) - a per-repo .git/hooks/pre-push would have to be
re-installed by hand in every clone and would silently stop covering a repo cloned later.

Idempotent: re-running it when core.hooksPath already points here is a no-op. Refuses to
clobber a core.hooksPath that points somewhere else, since that means either this ran before
with a different checkout path, or the user (or some other tool) set up their own hooks
directory - overwriting it would silently disable whatever hook lived there.

Usage:
    python tools/install_git_hooks.py
    python tools/install_git_hooks.py --uninstall
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.join(HERE, "git-hooks")


def _run_git_config(args):
    return subprocess.run(["git", "config", "--global"] + args, capture_output=True, text=True)


def current_hooks_path():
    result = _run_git_config(["--get", "core.hooksPath"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def install():
    if not os.path.isdir(HOOKS_DIR):
        print(f"install_git_hooks: {HOOKS_DIR} does not exist - nothing to install.", file=sys.stderr)
        return 1

    existing = current_hooks_path()
    if existing and os.path.abspath(existing) == os.path.abspath(HOOKS_DIR):
        print(f"core.hooksPath already set to {HOOKS_DIR} - nothing to do.")
        return 0
    if existing:
        print(
            f"core.hooksPath is already set to {existing!r}, which is not {HOOKS_DIR}.\n"
            "Not overwriting it - merge the pre-push check into that directory by hand, or "
            "unset core.hooksPath first if that value is stale:\n"
            "  git config --global --unset core.hooksPath",
            file=sys.stderr,
        )
        return 1

    result = _run_git_config(["core.hooksPath", HOOKS_DIR])
    if result.returncode != 0:
        print(f"install_git_hooks: `git config --global core.hooksPath` failed:\n{result.stderr}", file=sys.stderr)
        return 1

    print(f"core.hooksPath set to {HOOKS_DIR}.")
    print("Every git push on this machine now runs the merged-PR check first.")
    return 0


def uninstall():
    existing = current_hooks_path()
    if not existing or os.path.abspath(existing) != os.path.abspath(HOOKS_DIR):
        print("core.hooksPath does not point here - nothing to uninstall.")
        return 0
    result = _run_git_config(["--unset", "core.hooksPath"])
    if result.returncode != 0:
        print(f"install_git_hooks: `git config --global --unset core.hooksPath` failed:\n{result.stderr}", file=sys.stderr)
        return 1
    print("core.hooksPath unset. The merged-PR pre-push check no longer runs.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true", help="unset core.hooksPath if it points here")
    args = parser.parse_args()
    return uninstall() if args.uninstall else install()


if __name__ == "__main__":
    sys.exit(main())
