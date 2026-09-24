#!/usr/bin/env python3
"""install.py — installs the house-rules plugin on this device and applies the settings it
expects.

The two `claude plugin` commands in the README install the plugin, but a plugin can only ship
hooks, rules and agents — it cannot set anything the Claude Code harness reads from
~/.claude/settings.json. Two of those matter here:

  verbose  the verbose transcript view, rendered by the harness, so no rule text can turn it on.
  model    'opusplan' - Opus while planning, automatically switching to Sonnet to execute.
           Hooks cannot set a model at all (a SessionStart hook may be told which model is
           running; none can change it), so this is the only place a DEFAULT model can be set -
           but it is read by the CLI and the IDE only. In the desktop app's Code tab the model
           comes from the picker beside the send button, a session-level selection that
           outranks the model field in any settings file, and 'opusplan' is an alias rather
           than a model so it is not in that picker at all. Cloud sessions run on managed VMs
           that never see a settings file written to this device. On all of those, the
           Opus/Sonnet split comes from the @house-rules:executor subagent the plugin ships,
           not from this key.

This script does both halves, so a new device is configured in one command instead of two
commands plus a hand edit.

Idempotent. Re-running it on a machine that already has the plugin re-adds the marketplace
(a no-op), re-installs at the current remote commit, and leaves a setting alone when it already
holds the wanted value. Every other key in settings.json is preserved.

Usage:
    python tools/install.py [--no-verbose] [--no-model]
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _plugin_sync import tree_hash, diff_trees  # noqa: E402

# The full git URL, not the Ajw2003/AjsClaudeCodeTools shorthand. The shorthand resolves to
# marketplace kind "github"; a settings file that already declares this name as kind "git"
# with a .git URL is a mismatch, and the CLI refuses the add rather than reconciling them.
REPO = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
MARKETPLACE = "aj-house-rules"
PLUGIN_ID = f"house-rules@{MARKETPLACE}"


# The claude CLI writes UTF-8 including check marks. When this script's stdout is a pipe or a
# file rather than a console, Python picks the locale codec (cp1252 here) and printing that
# output raised UnicodeEncodeError, crashing the installer mid-run. Degrade the character
# instead of the install.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def repo_plugin_version():
    """The version this repo ships, read from the plugin manifest next to this script."""
    here = os.path.dirname(os.path.abspath(__file__))
    manifest = os.path.join(
        here, "..", "claude-house-rules", "plugins", "house-rules",
        ".claude-plugin", "plugin.json",
    )
    with open(manifest, "r", encoding="utf-8") as f:
        return json.load(f).get("version")


def home_claude_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def which(cmd):
    from shutil import which as _which

    return _which(cmd)


def locate_source_and_installed(plugins_root, market, name):
    """Find the marketplace's source tree and the newest matching installed cache dir.

    Same lookup force_update.py already does. Returns (source_root, installed_root), either
    of which may be None if it could not be found.
    """
    market_root = os.path.join(plugins_root, "marketplaces", market)
    source = None
    if os.path.isdir(market_root):
        for dirpath, dirnames, filenames in os.walk(market_root):
            if os.path.basename(dirpath) == ".claude-plugin" and "plugin.json" in filenames:
                with open(os.path.join(dirpath, "plugin.json"), "r", encoding="utf-8") as f:
                    if json.load(f).get("name") == name:
                        source = os.path.dirname(dirpath)
                        break

    cache_root = os.path.join(plugins_root, "cache", market, name)
    installed = None
    if os.path.isdir(cache_root):
        candidates = [
            os.path.join(cache_root, d)
            for d in os.listdir(cache_root)
            if os.path.isdir(os.path.join(cache_root, d))
        ]
        if candidates:
            installed = max(candidates, key=os.path.getmtime)

    return source, installed


def verify_and_self_heal(source_root, installed_root, reinstall_fn, ok, bad, info):
    """Hash-compare the installed cache against source. On mismatch, run `reinstall_fn()` (the
    uninstall+reinstall sequence force_update.py already uses) and re-verify once.

    Returns True if the cache matches source by the end (whether or not a reinstall ran),
    False if it still mismatches after the self-heal attempt.
    """
    src_hash = tree_hash(source_root)
    dst_hash = tree_hash(installed_root)
    diff = diff_trees(src_hash, dst_hash)

    if not diff:
        ok("installed cache matches source, file-for-file - no reinstall needed")
        return True

    info(f"installed cache does not match source ({len(diff)} path(s) differ) - self-healing")
    reinstall_fn()

    dst_hash2 = tree_hash(installed_root)
    diff2 = diff_trees(src_hash, dst_hash2)
    if not diff2:
        ok("self-heal reinstall brought the installed cache back in sync with source")
        return True

    bad("installed cache still does not match source after the self-heal reinstall")
    for where, path in diff2:
        info(f"  {where:12s} {path}")
    info("run tools/force_update.py for manual investigation")
    return False


def run_claude(args):
    # encoding is explicit: the claude CLI writes UTF-8, and text=True alone decodes with the
    # locale codec (cp1252 on this box), which turned its output into mojibake.
    print(f"        claude {' '.join(args)}")
    proc = subprocess.run(
        ["claude"] + args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    for line in (proc.stdout + proc.stderr).splitlines():
        print(f"        {line}")
    return proc.returncode


def install_steps():
    """The claude CLI commands that install or upgrade the plugin, in the order they must run.

    `marketplace add` answers "already on disk" for a marketplace this device has seen before
    and does NOT re-fetch it, which is why `marketplace update` must run too. Full rationale and
    why this is a value rather than four inline calls:
    doc-ref db64 docs/4-systems/plugin-distribution.md (How it works).
    """
    return [
        (["plugin", "marketplace", "add", REPO],
         "marketplace add failed - the lines above say why"),
        # The fix. Loud on failure rather than warned-about: if the refresh did not happen you
        # do not know which version you have, and the version check below cannot tell you -
        # it compares against this repo's plugin.json, which may itself be stale.
        (["plugin", "marketplace", "update", MARKETPLACE],
         "marketplace update failed - the cached clone may be stale, so the version "
         "installed below may not be the current one"),
        (["plugin", "install", PLUGIN_ID, "-y"],
         "plugin install failed - the lines above say why"),
        # install is a no-op when the plugin is already registered - it fetches the new version
        # into the cache and then leaves the registration pointing at the OLD one. That is a
        # silent downgrade: the bumped version sits on disk unused while the stale copy keeps
        # running. update is the verb that re-points the registration, so it always runs.
        (["plugin", "update", PLUGIN_ID],
         "plugin update failed - the lines above say why"),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-verbose", action="store_true")
    parser.add_argument("--no-model", action="store_true")
    args = parser.parse_args()

    failures = 0

    def ok(msg):
        print(f"  PASS  {msg}")

    def bad(msg):
        nonlocal failures
        failures += 1
        print(f"  FAIL  {msg}")

    def info(msg):
        print(f"        {msg}")

    print()
    print("house-rules - install")
    print("=====================")

    print()
    print("1. Preflight")
    claude_path = which("claude")
    if claude_path:
        ok(f"claude  {claude_path}")
    else:
        bad("claude is not on PATH - nothing can be installed")
    if failures:
        sys.exit(1)

    print()
    print("2. Install the plugin")
    # Every return code is checked. They used to be discarded, so a marketplace add that
    # failed outright still reported PASS as long as a PREVIOUS install had left the plugin
    # registered - a failure reported as a pass, which is the one thing this repo does not do.
    # run_claude already echoes the command it is about to run, so nothing echoes it twice.
    for argv, failure in install_steps():
        if run_claude(argv) != 0:
            bad(failure)

    claude_dir = home_claude_dir()
    installed_path = os.path.join(claude_dir, "plugins", "installed_plugins.json")
    if os.path.isfile(installed_path):
        with open(installed_path, "r", encoding="utf-8") as f:
            inst = json.load(f)
        entries = inst.get("plugins", {}).get(PLUGIN_ID)
        if not entries:
            bad(f"{PLUGIN_ID} did not register - read the lines above")
        else:
            # Registered is not the same as current. Asserting the registered version equals
            # the version this repo ships is what catches a bump that silently did not take.
            registered = entries[0].get("version")
            if registered == repo_plugin_version():
                ok(f"{PLUGIN_ID} is registered at {registered}, matching this repo")
            else:
                bad(
                    f"{PLUGIN_ID} is registered at {registered} but this repo ships "
                    f"{repo_plugin_version()} - the update did not take"
                )
    else:
        bad("no installed_plugins.json after install")

    print()
    print("3. Verify the installed cache actually matches source")
    # "Registered at the right version" (above) is not "holds the right content" - that's the
    # exact gap this step closes: a reported update is not a completed one. Hash-compare the
    # installed cache against the marketplace source tree, the same check force_update.py makes,
    # and self-heal automatically on a mismatch instead of leaving it to a human to notice.
    plugins_root = os.path.join(claude_dir, "plugins")
    source_root, installed_root = locate_source_and_installed(plugins_root, MARKETPLACE, "house-rules")
    if not source_root or not installed_root:
        bad(
            "could not locate both the source tree and the installed cache to verify - "
            f"source={source_root!r}, installed={installed_root!r}"
        )
    else:
        def reinstall():
            run_claude(["plugin", "uninstall", PLUGIN_ID])
            run_claude(["plugin", "install", PLUGIN_ID, "-y"])

        if not verify_and_self_heal(source_root, installed_root, reinstall, ok, bad, info):
            failures += 1

    print()
    print("4. Settings the plugin cannot set itself")

    wanted = [
        {
            "name": "verbose",
            "value": True,
            "skip": args.no_verbose,
            "skip_note": "--no-verbose given, leaving the transcript view setting alone",
            "why": "default to the verbose transcript view",
        },
        {
            "name": "model",
            "value": "opusplan",
            "skip": args.no_model,
            "skip_note": "--no-model given, leaving the model setting alone",
            "why": "Opus while planning, Sonnet to execute",
        },
    ]

    to_apply = [w for w in wanted if not w["skip"]]
    for w in wanted:
        if w["skip"]:
            info(w["skip_note"])

    if to_apply:
        settings_path = os.path.join(claude_dir, "settings.json")
        if os.path.isfile(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            os.makedirs(claude_dir, exist_ok=True)
            settings = {}

        changed = False
        for w in to_apply:
            if settings.get(w["name"]) == w["value"]:
                ok(f"{w['name']} is already {w['value']} - nothing to change")
                continue
            settings[w["name"]] = w["value"]
            changed = True
            ok(f"set {w['name']} = {w['value']} ({w['why']})")

        if changed:
            kept = [k for k in settings if k not in [w["name"] for w in to_apply]]
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            if kept:
                info(f"kept: {', '.join(kept)}")

        with open(settings_path, "r", encoding="utf-8") as f:
            check = json.load(f)
        for w in to_apply:
            if check.get(w["name"]) == w["value"]:
                ok(f"settings.json still parses and reads back {w['name']} = {w['value']}")
            else:
                bad(f"settings.json does not read back {w['name']} = {w['value']}")

    print()
    print("---------------------")
    if failures == 0:
        print("RESULT: PASS - plugin installed and settings applied.")
    else:
        print(f"RESULT: FAIL - {failures} check(s) failed.")
    print()
    print("Fully quit Claude Code and start it again. Hooks, agents, the transcript view and")
    print("the model setting are all read at startup, so none takes effect in a running session.")
    print()
    if not args.no_model:
        print("Note: model = opusplan applies to the CLI and the IDE extensions. The desktop Code")
        print("tab takes its model from the picker beside the send button, and cloud sessions never")
        print("read this file at all. There, the Opus/Sonnet split comes from the plugin delegating")
        print("execution to @house-rules:executor, which is pinned to Sonnet.")
        print()

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
