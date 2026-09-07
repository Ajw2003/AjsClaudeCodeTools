#!/usr/bin/env python3
"""Measure what the installed house-rules plugin actually costs in tokens.

verify.py proves the hooks behave as written. This proves the behaviour is cheap, which is a
different question and the one a version number cannot answer. It runs the INSTALLED copy of
hook.py rather than the repo's, because the installed copy is what a real session executes -
a repo edit that never got registered would pass every check here if we read the repo instead.

Three measurements, in order of how much they matter:

  1. scope gating - the per-prompt cost, which accumulates in context and is never cached away.
     Replays the user's own past prompts through the real gating regex to get a long/short
     split from actual usage rather than a guess.
  2. SessionStart injection - the fixed per-session cost, also re-paid on every subagent spawn.
  3. Failure paths - scope runs on UserPromptSubmit, where a non-zero exit erases the user's
     prompt. A malformed payload must still exit 0.

Usage:
    python tools/measure_footprint.py [--repo]

    --repo  measure this repo's copy instead of the installed one, to see a change's effect
            before installing it.
"""

import argparse
import json
import os
import subprocess
import sys

# Rough and deliberately so: the exact ratio varies by tokenizer, and every number here is a
# comparison against a baseline measured the same way, so a constant factor cancels out.
CHARS_PER_TOKEN = 4

# The pre-2.6.0 scope reminder was a single fixed string emitted on every prompt. Kept here as
# the baseline the saving is measured against; it is not read from anywhere at runtime.
BASELINE_SCOPE_CHARS = 1435

PLUGIN_CACHE = os.path.join(
    os.path.expanduser("~"), ".claude", "plugins", "cache", "aj-house-rules", "house-rules"
)


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_plugin_dir():
    return os.path.join(repo_root(), "claude-house-rules", "plugins", "house-rules")


def installed_plugin_dir():
    """The highest version directory present in the plugin cache.

    Sorted numerically, not lexically: "2.10.0" must beat "2.9.0", which a string sort gets
    backwards. A cache holding only older versions is still reported, so the caller can see
    that the install is behind rather than getting a confusing missing-file error.
    """
    if not os.path.isdir(PLUGIN_CACHE):
        return None
    versions = []
    for name in os.listdir(PLUGIN_CACHE):
        if os.path.isdir(os.path.join(PLUGIN_CACHE, name)):
            try:
                versions.append((tuple(int(p) for p in name.split(".")), name))
            except ValueError:
                continue
    if not versions:
        return None
    return os.path.join(PLUGIN_CACHE, max(versions)[1])


def run_hook(hook_py, event, payload):
    """Invoke a hook handler the way the harness does and return (exit code, stdout)."""
    proc = subprocess.run(
        [sys.executable, hook_py, event],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or ""


def collect_prompts():
    """Every real prompt the user has typed, across all projects.

    Transcript records also carry hook-injected context and system reminders. Those contain the
    very words the gating regex looks for ("command", "shell", "run"), so counting them would
    inflate the long-form rate with the plugin's own output. They are excluded by signature.
    """
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    noise = (
        "Standing house rules",
        "house rules,",
        "<system-reminder>",
        "<command-",
        "Caveat:",
        "SessionStart hook",
        "additional context",
        "[Request interrupted",
    )
    prompts = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, filename)
            try:
                handle = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("type") != "user" or record.get("isMeta"):
                        continue
                    content = record.get("message", {}).get("content")
                    if isinstance(content, str):
                        texts = [content]
                    elif isinstance(content, list):
                        texts = [
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                    else:
                        continue
                    for text in texts:
                        text = text.strip()
                        if not text or text.startswith("<"):
                            continue
                        if any(marker in text for marker in noise):
                            continue
                        prompts.append(text)
    return prompts


def tokens(chars):
    return chars // CHARS_PER_TOKEN


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        action="store_true",
        help="measure this repo's copy instead of the installed one",
    )
    args = parser.parse_args()

    if args.repo:
        plugin_dir, label = repo_plugin_dir(), "repo working tree"
    else:
        plugin_dir = installed_plugin_dir()
        label = "installed copy"
        if plugin_dir is None:
            print("No installed plugin found. Run tools/bootstrap.ps1 first, or pass --repo.")
            return 1

    hook_py = os.path.join(plugin_dir, "scripts", "hook.py")
    if not os.path.isfile(hook_py):
        print(f"No hook.py under {plugin_dir}")
        return 1

    manifest = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
    version = "unknown"
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as f:
            version = json.load(f).get("version", "unknown")

    print("house-rules - token footprint")
    print("=" * 29)
    print(f"\nMeasuring the {label}, version {version}")
    print(f"  {plugin_dir}")

    # --- 1. per-prompt cost ------------------------------------------------------------------
    print("\n1. Per-prompt cost (scope)")
    _, short_out = run_hook(hook_py, "scope", json.dumps({"prompt": "what do you think"}))
    _, long_out = run_hook(hook_py, "scope", json.dumps({"prompt": "run the build script"}))
    short_chars, long_chars = len(short_out), len(long_out)
    print(f"   short form : {short_chars:>6,} chars  (~{tokens(short_chars)} tokens)")
    print(f"   long form  : {long_chars:>6,} chars  (~{tokens(long_chars)} tokens)")
    if short_chars >= long_chars:
        print("   WARNING: the two forms are not distinct - gating is not in effect")

    # --- 2. the split on real prompts --------------------------------------------------------
    print("\n2. Which form your real prompts get")
    prompts = collect_prompts()
    if not prompts:
        print("   no transcripts found - skipping")
    else:
        sys.path.insert(0, os.path.join(plugin_dir, "scripts"))
        import hook as hook_module

        pattern = hook_module._SCOPE_COMMAND_HINT_RE
        long_count = sum(1 for p in prompts if pattern.search(p))
        total = len(prompts)
        short_count = total - long_count
        print(f"   prompts sampled : {total:,}")
        print(f"   long form       : {long_count:,} ({100 * long_count / total:.1f}%)")
        print(f"   short form      : {short_count:,} ({100 * short_count / total:.1f}%)")

        before = total * BASELINE_SCOPE_CHARS
        after = long_count * long_chars + short_count * short_chars
        saved = before - after
        print(f"\n   across that history, reminder text alone:")
        print(f"     before 2.6.0 : {before:>9,} chars  (~{tokens(before):,} tokens)")
        print(f"     now          : {after:>9,} chars  (~{tokens(after):,} tokens)")
        print(f"     saved        : {saved:>9,} chars  (~{tokens(saved):,} tokens, "
              f"{100 * saved / before:.1f}%)")

    # --- 3. per-session cost -----------------------------------------------------------------
    print("\n3. Per-session cost (SessionStart)")
    _, inject_out = run_hook(hook_py, "inject", "{}")
    _, standards_out = run_hook(hook_py, "standards", "{}")
    print(f"   inject     : {len(inject_out):>6,} chars  (~{tokens(len(inject_out)):,} tokens)")
    print(f"   standards  : {len(standards_out):>6,} chars  "
          f"(~{tokens(len(standards_out)):,} tokens)")
    print("   (re-paid on every subagent spawn, not just once per session)")

    # --- 4. the path that must never fail ----------------------------------------------------
    print("\n4. Failure paths (a non-zero exit here erases the user's prompt)")
    failures = 0
    for name, payload in [
        ("missing prompt key", "{}"),
        ("malformed json", "not json at all{{{"),
        ("empty stdin", ""),
    ]:
        code, out = run_hook(hook_py, "scope", payload)
        if code == 0 and out.strip():
            print(f"   PASS  {name}: exit 0, emitted {len(out)} chars")
        else:
            print(f"   FAIL  {name}: exit {code}, emitted {len(out)} chars")
            failures += 1

    print("\n" + "-" * 29)
    if failures:
        print(f"RESULT: FAIL - {failures} failure path(s) did not exit 0 with output.")
        return 1
    print("RESULT: PASS - gating is live and every failure path exits 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
