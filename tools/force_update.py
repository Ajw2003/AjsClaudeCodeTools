#!/usr/bin/env python3
"""force_update.py — force the installed house-rules plugin to match the marketplace source.

`claude plugin update` is version-gated: if plugin.json still declares the same version, it
reports "already at the latest version" and copies nothing. That is the normal case while
iterating on a branch, so the only reliable way to re-sync is uninstall + reinstall.

This refreshes the marketplace clone, reinstalls the plugin, and verifies the installed cache
matches the source tree file-for-file.

Usage:
    python tools/force_update.py [--plugin name@marketplace] [--skip-marketplace-update]
"""

import argparse
import hashlib
import os
import subprocess
import sys


def invoke_claude(args, activity):
    print(f"==> {activity}")
    proc = subprocess.run(["claude"] + args)
    if proc.returncode != 0:
        raise SystemExit(f"{activity} failed (exit {proc.returncode}).")


def tree_hash(root):
    if not os.path.isdir(root):
        return None
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if os.sep + ".in_use" + os.sep in dirpath + os.sep:
            continue
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as f:
                out[rel] = hashlib.md5(f.read()).hexdigest()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", default="house-rules@aj-house-rules")
    parser.add_argument("--skip-marketplace-update", action="store_true")
    args = parser.parse_args()

    if "@" not in args.plugin:
        raise SystemExit(f"Plugin must be in 'name@marketplace' form. Got: {args.plugin}")
    name, market = args.plugin.split("@", 1)

    from shutil import which

    if which("claude") is None:
        raise SystemExit("'claude' is not on PATH.")

    plugins_root = os.path.join(os.path.expanduser("~"), ".claude", "plugins")
    market_root = os.path.join(plugins_root, "marketplaces", market)

    if not args.skip_marketplace_update:
        invoke_claude(["plugin", "marketplace", "update", market], f"Refreshing marketplace '{market}'")
    else:
        print("==> Skipping marketplace refresh (--skip-marketplace-update)")

    if os.path.isdir(os.path.join(market_root, ".git")):
        head = subprocess.run(
            ["git", "-C", market_root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        subj = subprocess.run(
            ["git", "-C", market_root, "log", "-1", "--format=%s"], capture_output=True, text=True
        ).stdout.strip()
        print(f"    source commit: {head}  {subj}")

        ahead_proc = subprocess.run(
            ["git", "-C", market_root, "rev-list", "--count", "@{upstream}..HEAD"],
            capture_output=True,
            text=True,
        )
        if ahead_proc.returncode == 0:
            ahead = ahead_proc.stdout.strip()
            if ahead and int(ahead) > 0:
                print(f"WARNING: {ahead} local commit(s) are not pushed to the upstream branch.")

        dirty = subprocess.run(
            ["git", "-C", market_root, "status", "--porcelain"], capture_output=True, text=True
        ).stdout
        if dirty.strip():
            print("WARNING: Marketplace clone has uncommitted changes; installing them as-is.")

    invoke_claude(["plugin", "uninstall", args.plugin], f"Uninstalling {args.plugin}")
    invoke_claude(["plugin", "install", args.plugin, "-y"], f"Reinstalling {args.plugin}")

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

    source = None
    if os.path.isdir(market_root):
        for dirpath, dirnames, filenames in os.walk(market_root):
            if os.path.basename(dirpath) == ".claude-plugin" and "plugin.json" in filenames:
                import json

                with open(os.path.join(dirpath, "plugin.json"), "r", encoding="utf-8") as f:
                    if json.load(f).get("name") == name:
                        source = os.path.dirname(dirpath)
                        break

    if not installed or not source:
        print("WARNING: Reinstalled, but could not locate both trees to verify.")
        print("Restart Claude Code to load the new version.")
        return

    diff = []
    src_hash = tree_hash(source)
    dst_hash = tree_hash(installed)
    all_paths = set(src_hash) | set(dst_hash)
    for path in sorted(all_paths):
        if src_hash.get(path) != dst_hash.get(path):
            where = "source only" if path not in dst_hash else ("cache only" if path not in src_hash else "differs")
            diff.append((where, path))

    if diff:
        print()
        print("WARNING: Installed cache does NOT match source:")
        for where, path in diff:
            print(f"  {where:12s} {path}")
        sys.exit(1)

    print()
    print(f"OK: {name} {os.path.basename(installed)} matches source, file-for-file.")
    print("Restart Claude Code to load it - a running session keeps the old hooks and rules.")


if __name__ == "__main__":
    main()
