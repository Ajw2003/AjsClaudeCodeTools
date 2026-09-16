#!/usr/bin/env python3
"""_plugin_sync.py — shared tree-hashing used to prove an installed plugin cache actually
matches the marketplace source, instead of trusting a tool's own "already up to date" message.

Factored out of tools/force_update.py so install.py and force_update.py both import ONE
implementation instead of risking two copies drifting apart — this repo already treats that kind
of drift as a tested failure mode elsewhere (verify.py's literal-drift checks).

Not a script on its own; nothing here shells out or mutates anything.
"""

import hashlib
import os


def tree_hash(root):
    """Return {relative_path: md5} for every file under root, or None if root does not exist.
    Skips any path segment named `.in_use` (an in-flight cache copy, not comparable)."""
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


def diff_trees(src_hash, dst_hash):
    """Compare two tree_hash() outputs. Returns a list of (where, path) for every mismatch,
    where `where` is "source only", "cache only", or "differs". Empty list means they match.
    """
    src_hash = src_hash or {}
    dst_hash = dst_hash or {}
    diff = []
    all_paths = set(src_hash) | set(dst_hash)
    for path in sorted(all_paths):
        if src_hash.get(path) != dst_hash.get(path):
            where = (
                "source only" if path not in dst_hash
                else ("cache only" if path not in src_hash else "differs")
            )
            diff.append((where, path))
    return diff
