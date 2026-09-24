#!/usr/bin/env python3
"""check_plugin_version_bump.py — refuses a PR that changes plugin-relevant files without
bumping the plugin's version.

Two merged PRs changed files under claude-house-rules/plugins/house-rules/ without bumping
.claude-plugin/plugin.json's `version`. Nothing enforced the convention, so it silently lapsed,
and claude plugin update (version-gated) reported "already at the latest version" while the
installed cache held stale content. See docs/6-decisions/Decisions.md for the full incident.

"Plugin-relevant" is wider than "ships inside the installed plugin package": root CLAUDE.md is
auto-loaded into every live session working in this repo, and docs/ is what a session reads (and,
per house-rules' own artifact rule, writes) while following the rules — both are as directly used
by the plugin, live, as the files under PLUGIN_ROOT itself, even though neither is packaged into
the install. A PR that only touches one of these still needs the same version bump this check
exists to enforce; see docs/6-decisions/Decisions.md for that decision too.

Usage:
    python tools/check_plugin_version_bump.py [--base origin/main] [--head HEAD]

Exits 0 and prints a message when no bump was required or a real bump was made; exits 1 and
prints why otherwise. Every branch prints something - there is no silent path.
"""

import argparse
import json
import subprocess
import sys

PLUGIN_ROOT = "claude-house-rules/plugins/house-rules/"
PLUGIN_JSON_PATH = "claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json"

# Directory prefixes and exact root files that count as plugin-relevant beyond PLUGIN_ROOT
# itself. "docs/" is a prefix (everything under it); "CLAUDE.md" is the root file only — not a
# prefix, so a hypothetical CLAUDE.md.bak or similar doesn't accidentally match.
PLUGIN_RELEVANT_PREFIXES = (PLUGIN_ROOT, "docs/")
PLUGIN_RELEVANT_EXACT = ("CLAUDE.md",)


def _is_plugin_relevant(path):
    return path in PLUGIN_RELEVANT_EXACT or any(
        path.startswith(prefix) for prefix in PLUGIN_RELEVANT_PREFIXES
    )


class VersionBumpCheckError(Exception):
    """Raised when changed_paths()/plugin_version_at() cannot answer the question at all -
    a bad ref, a missing path, or unparseable JSON. Distinct from `decide()` saying no, which
    is a normal (False) result, not an error."""


def changed_paths(base, head="HEAD"):
    """Files that differ between base and head, via `git diff --name-only base...head`."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VersionBumpCheckError(
            f"git diff --name-only {base}...{head} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip()}"
        )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def plugin_version_at(ref, path=PLUGIN_JSON_PATH):
    """The `version` field of plugin.json as it existed at `ref`. Raises VersionBumpCheckError
    (never returns None) if the ref, path, or JSON is bad - a caller must not be able to treat
    a failure to read as "no plugin files existed at that ref"."""
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VersionBumpCheckError(
            f"git show {ref}:{path} failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise VersionBumpCheckError(f"{ref}:{path} is not valid JSON: {e}")
    version = data.get("version")
    if not version:
        raise VersionBumpCheckError(f"{ref}:{path} has no 'version' field")
    return version


def _parse_semver(version):
    parts = version.split(".")
    if len(parts) != 3:
        raise VersionBumpCheckError(f"{version!r} is not a MAJOR.MINOR.PATCH version string")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise VersionBumpCheckError(f"{version!r} is not a MAJOR.MINOR.PATCH version string")


def decide(changed, old_version, new_version):
    """The policy, with zero I/O, so it can be tested directly without touching git.

    Returns (ok: bool, message: str).
    """
    plugin_changed = [p for p in changed if _is_plugin_relevant(p)]
    if not plugin_changed:
        return True, "no plugin-relevant files changed, no bump required"

    changed_list = ", ".join(sorted(plugin_changed))

    if old_version == new_version:
        return False, (
            f"{changed_list} changed, but plugin.json's version is still "
            f"{old_version} - bump it"
        )

    old_tuple = _parse_semver(old_version)
    new_tuple = _parse_semver(new_version)
    if not (new_tuple > old_tuple):
        return False, (
            f"{changed_list} changed, and plugin.json's version moved from "
            f"{old_version} to {new_version}, which is not an increase"
        )

    return True, f"{changed_list} changed, and the version bumped from {old_version} to {new_version}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    try:
        changed = changed_paths(args.base, args.head)
        old_version = plugin_version_at(args.base)
        new_version = plugin_version_at(args.head)
        ok, message = decide(changed, old_version, new_version)
    except VersionBumpCheckError as e:
        print(f"check_plugin_version_bump: FAIL - {e}")
        sys.exit(1)

    status = "PASS" if ok else "FAIL"
    print(f"check_plugin_version_bump: {status} - {message}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
