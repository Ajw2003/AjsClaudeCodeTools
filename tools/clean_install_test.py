#!/usr/bin/env python3
"""clean_install_test.py — strips the house-rules plugin off this machine and reinstalls it
from GitHub the way the README tells a new device to, then proves the fresh copy works.

This exists because "it works on my machine" is not evidence: the working repo on disk is not
what a new device gets. A new device gets whatever is on GitHub, installed through the two
documented CLI commands. This script tests exactly that path.

SAFETY: settings.json, installed_plugins.json and known_marketplaces.json are copied to a
timestamped backup folder BEFORE anything is removed, and the path is printed. Unrelated config
in those files (theme, enableWorkflows, the claude-plugins-official marketplace) is preserved,
not clobbered. Everything plugin-side is recoverable from GitHub regardless.

Usage:
    python tools/clean_install_test.py [--force] [--skip-strip]
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

# The full git URL, not the Ajw2003/AjsClaudeCodeTools shorthand. The shorthand resolves to
# marketplace kind "github"; a settings file that already declares this name as kind "git"
# with a .git URL is a mismatch, and the CLI refuses the add rather than reconciling them.
REPO = "https://github.com/Ajw2003/AjsClaudeCodeTools.git"
MARKETPLACE = "aj-house-rules"
PLUGIN_ID = f"house-rules@{MARKETPLACE}"

step_no = 0
failures = 0


def step(title):
    global step_no
    step_no += 1
    print()
    print(f"{step_no:2d}. {title}")


def ok(msg):
    print(f"     PASS  {msg}")


def bad(msg):
    global failures
    failures += 1
    print(f"     FAIL  {msg}")


def info(msg):
    print(f"     {msg}")


def run_claude(args):
    # encoding is explicit: the claude CLI writes UTF-8, and text=True alone decodes with the
    # locale codec (cp1252 on Windows), which renders its output as mojibake.
    proc = subprocess.run(
        ["claude"] + args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    for line in (proc.stdout + proc.stderr).splitlines():
        info(line)
    return proc.returncode


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-strip", action="store_true")
    args = parser.parse_args()

    claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
    plugins_dir = os.path.join(claude_dir, "plugins")
    settings_path = os.path.join(claude_dir, "settings.json")
    installed_path = os.path.join(plugins_dir, "installed_plugins.json")
    known_path = os.path.join(plugins_dir, "known_marketplaces.json")
    clone_path = os.path.join(plugins_dir, "marketplaces", MARKETPLACE)
    cache_path = os.path.join(plugins_dir, "cache", MARKETPLACE)
    install_path = None

    print()
    print("house-rules - clean install test")
    print("================================")
    print(f"Source repo : {REPO}")
    print(f"Plugin      : {PLUGIN_ID}")
    print(f"Claude dir  : {claude_dir}")

    step("Preflight: the tools this test needs")
    from shutil import which

    claude_bin = which("claude")
    git_bin = which("git")
    sh_bin = None
    for cand in (r"C:\Program Files\Git\bin\sh.exe", r"C:\Program Files\Git\usr\bin\sh.exe"):
        if os.path.exists(cand):
            sh_bin = cand
            break
    if sys.platform != "win32":
        sh_bin = which("sh") or sh_bin

    if claude_bin:
        ok(f"claude  {claude_bin}")
    else:
        bad("claude is not on PATH - cannot install anything")
    if git_bin:
        ok(f"git     {git_bin}")
    else:
        bad("git is not on PATH - cannot clone the marketplace")
    if sh_bin:
        ok(f"sh      {sh_bin}")
    else:
        bad("no sh found - install Git for Windows (or ensure sh is on PATH)")
    if failures:
        print()
        print("Stopping: the environment cannot run this test.")
        sys.exit(1)

    step("What a new device would actually get")
    remote = None
    remote_proc = subprocess.run(
        ["git", "ls-remote", REPO, "refs/heads/main"],
        capture_output=True,
        text=True,
    )
    if remote_proc.stdout.strip():
        remote = remote_proc.stdout.split()[0]
    if remote:
        ok(f"remote main is {remote[:7]}")
    else:
        bad("could not reach the remote")

    step("What is installed right now, before touching anything")
    if os.path.isfile(installed_path):
        inst = load_json(installed_path)
        entry = inst.get("plugins", {}).get(PLUGIN_ID)
        if entry:
            sha = entry[0]["gitCommitSha"]
            info(f"version   {entry[0]['version']}")
            info(f"commit    {sha[:7]}")
            info(f"path      {entry[0]['installPath']}")
            if remote and sha == remote:
                info("this is already current")
            elif remote:
                info(f"STALE - behind remote {remote[:7]}")
        else:
            info("not currently installed")
    else:
        info("no installed_plugins.json yet")

    if args.skip_strip:
        print()
        print("--skip-strip given: skipping the strip and install, verifying what is here now.")

    if not args.skip_strip:
        step("Back up the config files that are about to be edited")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(claude_dir, "backups", f"house-rules-clean-install-{stamp}")
        os.makedirs(backup_dir, exist_ok=True)
        for f in (settings_path, installed_path, known_path):
            if os.path.isfile(f):
                shutil.copy2(f, backup_dir)
                ok(f"saved {os.path.basename(f)}")
            else:
                info(f"{os.path.basename(f)} does not exist, nothing to save")
        info(f"backup folder: {backup_dir}")

        step("Confirm the strip-down")
        print("     This will remove:")
        print(f"       - the installed plugin {PLUGIN_ID}")
        print(f"       - the marketplace clone at {clone_path}")
        print(f"       - the extracted copy at   {cache_path}")
        print(f"       - the {PLUGIN_ID} entry from enabledPlugins in settings.json")
        print(f"       - the {MARKETPLACE} entry from extraKnownMarketplaces in settings.json")
        print(f"       - the {MARKETPLACE} entry from known_marketplaces.json")
        print("     It will NOT touch your theme, enableWorkflows, autoUpdatesChannel, any")
        print("     OTHER plugin or marketplace you have installed, or any CLAUDE.md file.")
        if not args.force:
            answer = input("     Type STRIP to continue, anything else to abort: ")
            if answer != "STRIP":
                print("     Aborted. Nothing was changed.")
                sys.exit(2)
        else:
            info("--force given, not asking")

        step("Uninstall through the CLI")
        run_claude(["plugin", "uninstall", PLUGIN_ID])
        run_claude(["plugin", "marketplace", "remove", MARKETPLACE])

        step("Strip the declarative keys out of settings.json, keeping everything else")
        if os.path.isfile(settings_path):
            # Remove OUR entries only. Popping the whole enabledPlugins and
            # extraKnownMarketplaces keys also deregistered every unrelated plugin and
            # marketplace on the machine - which the header above promises not to do, and
            # which the reinstall at the end does not put back.
            s = load_json(settings_path)
            removed = []
            if isinstance(s.get("enabledPlugins"), dict):
                if s["enabledPlugins"].pop(PLUGIN_ID, None) is not None:
                    removed.append(f"enabledPlugins[{PLUGIN_ID}]")
            if isinstance(s.get("extraKnownMarketplaces"), dict):
                if s["extraKnownMarketplaces"].pop(MARKETPLACE, None) is not None:
                    removed.append(f"extraKnownMarketplaces[{MARKETPLACE}]")
            save_json(settings_path, s)
            survivors = sorted(s.get("enabledPlugins", {}))
            ok(f"removed {', '.join(removed) if removed else 'nothing (already absent)'}")
            info(f"other plugins left registered: {', '.join(survivors) if survivors else 'none'}")
        else:
            info("no settings.json")

        step("Remove any leftover files on disk")
        for d in (clone_path, cache_path):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
                ok(f"removed {d}")
            else:
                info(f"already gone: {d}")
        if os.path.isfile(known_path):
            k = load_json(known_path)
            if MARKETPLACE in k:
                del k[MARKETPLACE]
                save_json(known_path, k)
                ok(f"removed {MARKETPLACE} from known_marketplaces.json")
            else:
                info(f"{MARKETPLACE} was not in known_marketplaces.json")

        step("Prove the machine is actually clean")
        dirty = []
        if os.path.isdir(clone_path):
            dirty.append("marketplace clone still present")
        if os.path.isdir(cache_path):
            dirty.append("plugin cache still present")
        if os.path.isfile(settings_path):
            s2 = load_json(settings_path)
            if "enabledPlugins" in s2:
                dirty.append("enabledPlugins still in settings.json")
        if not dirty:
            ok("nothing left behind - this is now a fresh machine")
        else:
            for d in dirty:
                bad(d)

        step("Install using the two commands the README gives a new device")
        info(f"claude plugin marketplace add {REPO}")
        run_claude(["plugin", "marketplace", "add", REPO])
        info(f"claude plugin install {PLUGIN_ID} -y")
        run_claude(["plugin", "install", PLUGIN_ID, "-y"])

    step("Did the install land on the commit that is actually on GitHub?")
    if os.path.isfile(installed_path):
        inst2 = load_json(installed_path)
        e2 = inst2.get("plugins", {}).get(PLUGIN_ID)
        if e2:
            sha2 = e2[0]["gitCommitSha"]
            if remote and sha2 == remote:
                ok(f"installed at {sha2[:7]}, matching remote")
            elif remote:
                bad(f"installed at {sha2[:7]} but remote is {remote[:7]}")
            install_path = e2[0]["installPath"]
            info(f"installed to {install_path}")
        else:
            bad("the plugin is not registered as installed")
    else:
        bad("no installed_plugins.json after install")

    step("Does the installed copy contain every file the hooks need?")
    expected = [
        os.path.join("hooks", "hooks.json"),
        os.path.join("rules", "house-rules.md"),
        os.path.join("scripts", "run.sh"),
        os.path.join("scripts", "hook.py"),
        os.path.join("scripts", "verify.py"),
        os.path.join("commands", "doctor.md"),
    ]
    if install_path and os.path.isdir(install_path):
        for f in expected:
            if os.path.isfile(os.path.join(install_path, f)):
                ok(f)
            else:
                bad(f"{f} is MISSING from the installed copy")
    else:
        bad("cannot find the installed copy on disk")

    step("Are all five hook events wired in the installed hooks.json?")
    hooks_json_path = install_path and os.path.join(install_path, "hooks", "hooks.json")
    if hooks_json_path and os.path.isfile(hooks_json_path):
        h = load_json(hooks_json_path)
        for evt in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
            if evt in h.get("hooks", {}):
                ok(evt)
            else:
                bad(f"{evt} is not wired")
    else:
        bad("no hooks.json in the installed copy")

    step("Run the full verify suite against the freshly cloned copy")
    fresh_verify = os.path.join(
        clone_path, "claude-house-rules", "plugins", "house-rules", "scripts", "verify.py"
    )
    if os.path.isfile(fresh_verify):
        info(f"running: {fresh_verify}")
        print()
        proc = subprocess.run([sys.executable, fresh_verify])
        print()
        if proc.returncode == 0:
            ok("all checks passed against the fresh clone")
        else:
            bad(f"the suite exited {proc.returncode} - read the FAIL lines above")
    else:
        bad(f"verify.py not found in the fresh clone at {fresh_verify}")

    step("Run each hook directly out of the installed copy")
    if install_path and os.path.isfile(os.path.join(install_path, "scripts", "hook.py")):
        hook_path = os.path.join(install_path, "scripts", "hook.py")
        out = subprocess.run(
            [sys.executable, hook_path, "inject"], input=b"", capture_output=True
        ).stdout.decode("utf-8", "replace")
        if "Never commit without asking" in out:
            ok("inject emits the rules")
        else:
            bad("inject did not emit the rules")
        if "This machine" in out:
            ok("inject emits the machine profile")
        else:
            bad("inject did not emit the machine profile")

        out2 = subprocess.run(
            [sys.executable, hook_path, "scope"], input=b"", capture_output=True
        ).stdout.decode("utf-8", "replace")
        if "UserPromptSubmit" in out2:
            ok("scope emits the per-prompt reminder")
        else:
            bad("scope produced nothing usable")
    else:
        bad("hook.py missing from the installed copy")

    print()
    print("--------------------------------")
    if failures == 0:
        print(f"RESULT: PASS - all {step_no} steps passed. The published plugin installs and runs.")
    else:
        print(f"RESULT: FAIL - {failures} check(s) failed across {step_no} steps.")

    print()
    print("ONE STEP IS LEFT, AND ONLY YOU CAN DO IT:")
    print()
    print("  Everything above tests files on disk. It cannot test that Claude Code loads them,")
    print("  because hooks are read at startup. So:")
    print()
    print("    1. Fully quit Claude Code - close every window.")
    print("    2. Start it again, in any project.")
    print("    3. Ask it:  what are my house rules, and what machine am I on?")
    print()
    print("       If SessionStart fired it answers both without opening a file. If it starts")
    print("       searching for files instead, the injection did not happen.")
    print()
    print("    4. Ask it to run:  git status")
    print("       That must run with NO permission prompt.")
    print()
    print("    5. The guard test needs an uncommitted change to be meaningful.")
    print("       On a clean worktree, git add -A stages nothing whether the guard")
    print("       intercepted it or not, so the result looks the same either way and")
    print("       proves nothing. Give it something real to stage first:")
    print()
    print("         echo scratch > guard-test.txt")
    print()
    print("       Then ask Claude to run:  git add -A")
    print('       That MUST raise a prompt naming "Never commit without asking".')
    print("       Deny it, then clean up:")
    print()
    print("         del guard-test.txt")
    print()

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
