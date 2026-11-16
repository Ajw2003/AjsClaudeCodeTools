#!/usr/bin/env python3
"""use_branch.py - switch the installed house-rules plugin to a branch build, and back.

Usage:
    python tools/use_branch.py <branch>     e.g. AjsAgent/phase-3-handoff
    python tools/use_branch.py main         back to the normal build (no ref)

Re-adds the aj-house-rules marketplace as Ajw2003/AjsClaudeCodeTools#<branch>, reinstalls the
plugin, then PRINTS what is really installed: marketplace ref, plugin version, checkout commit.
Exits non-zero if a claude call fails or the installed ref/commit is not the one asked for.
Honours CLAUDE_CONFIG_DIR (the claude CLI does too), so it can be tried in a throwaway folder.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from install import MARKETPLACE, PLUGIN_ID, run_claude  # noqa: E402

SLUG = "Ajw2003/AjsClaudeCodeTools"


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def read_json(name):
    with open(os.path.join(config_dir(), "plugins", name), encoding="utf-8") as f:
        return json.load(f)


def switch(branch):
    """Returns (ref, version, commit) as installed; raises SystemExit with a plain line on failure."""
    source = SLUG if branch == "main" else f"{SLUG}#{branch}"
    # remove/uninstall may legitimately find nothing to remove on a fresh config, so not fatal.
    run_claude(["plugin", "uninstall", PLUGIN_ID])
    run_claude(["plugin", "marketplace", "remove", MARKETPLACE])
    for argv in (["plugin", "marketplace", "add", source],
                 ["plugin", "install", PLUGIN_ID, "-y"],
                 ["plugin", "update", PLUGIN_ID]):
        if run_claude(argv) != 0:
            # the old install is already gone, so never leave the machine without the plugin
            if branch != "main":
                run_claude(["plugin", "marketplace", "remove", MARKETPLACE])
                ok = run_claude(["plugin", "marketplace", "add", SLUG]) == 0 and \
                    run_claude(["plugin", "install", PLUGIN_ID, "-y"]) == 0
                back = "the normal build was put back" if ok else "putting the normal build back ALSO failed"
            else:
                back = "nothing else to fall back to"
            raise SystemExit(f"FAILED: claude {' '.join(argv)} - the lines above say why; {back}.")
    entry = read_json("known_marketplaces.json").get(MARKETPLACE)
    if not entry:
        raise SystemExit(f"FAILED: {MARKETPLACE} is not in known_marketplaces.json after the add.")
    ref = entry.get("source", {}).get("ref") or entry.get("ref")
    commit = subprocess.run(["git", "-C", entry["installLocation"], "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    plugin = (read_json("installed_plugins.json").get("plugins", {}).get(PLUGIN_ID) or [{}])[0]
    return ref, plugin.get("version"), commit


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        raise SystemExit("usage: python tools/use_branch.py <branch|main>")
    branch = sys.argv[1]
    ref, version, commit = switch(branch)
    print()
    print(f"marketplace ref : {ref or '(none - default branch)'}")
    print(f"plugin version  : {version}")
    print(f"checkout commit : {commit}")
    want = None if branch == "main" else branch
    if ref != want or not commit or not version:
        raise SystemExit(f"MISMATCH: asked for {branch!r} but the install has ref {ref!r}, "
                         f"version {version!r}, commit {commit!r}.")
    print("OK: installed build matches the request. Restart Claude Code to load it.")


if __name__ == "__main__":
    main()
