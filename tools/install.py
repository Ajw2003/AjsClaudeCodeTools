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

# The full git URL, not the Ajw2003/AjsClaudeCodeTools shorthand. The shorthand resolves to
# marketplace kind "github"; a settings file that already declares this name as kind "git"
# with a .git URL is a mismatch, and the CLI refuses the add rather than reconciling them.
REPO = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
MARKETPLACE = "aj-house-rules"
PLUGIN_ID = f"house-rules@{MARKETPLACE}"


def home_claude_dir():
    return os.path.join(os.path.expanduser("~"), ".claude")


def which(cmd):
    from shutil import which as _which

    return _which(cmd)


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
    # Both return codes are checked. They used to be discarded, so a marketplace add that
    # failed outright still reported PASS as long as a PREVIOUS install had left the plugin
    # registered - a failure reported as a pass, which is the one thing this repo does not do.
    info(f"claude plugin marketplace add {REPO}")
    if run_claude(["plugin", "marketplace", "add", REPO]) != 0:
        bad("marketplace add failed - the lines above say why")
    info(f"claude plugin install {PLUGIN_ID} -y")
    if run_claude(["plugin", "install", PLUGIN_ID, "-y"]) != 0:
        bad("plugin install failed - the lines above say why")

    claude_dir = home_claude_dir()
    installed_path = os.path.join(claude_dir, "plugins", "installed_plugins.json")
    if os.path.isfile(installed_path):
        with open(installed_path, "r", encoding="utf-8") as f:
            inst = json.load(f)
        if inst.get("plugins", {}).get(PLUGIN_ID):
            ok(f"{PLUGIN_ID} is registered as installed")
        else:
            bad(f"{PLUGIN_ID} did not register - read the lines above")
    else:
        bad("no installed_plugins.json after install")

    print()
    print("3. Settings the plugin cannot set itself")

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
