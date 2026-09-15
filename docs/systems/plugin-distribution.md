# Plugin distribution

## What it owns

Getting all three plugins (`house-rules`, `agent-router`, `prompt-workshop`) declared in
[`.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json) onto a machine,
upgrading them there later, and writing the two harness-level settings a plugin cannot ship
itself. If this is wrong, a machine either never gets the hooks in the first place, or silently
keeps running a stale version while believing it's current — which is what actually happened
once (see Traps).

It does not own whether the hooks themselves behave correctly once installed (that's
[`hook-engine.md`](hook-engine.md) and [`verify-suites.md`](verify-suites.md)) — this system's
job ends at "the right version is registered and the machine-level settings are set."

## How it works

**The four-command install/upgrade sequence**, held as a value rather than four inline calls in
[`tools/install.py`](../../tools/install.py)'s `install_steps()` (`install.py:88-124`), because
the *order* is the load-bearing part and was wrong once:

1. `plugin marketplace add <repo>` — declares the marketplace (a no-op once declared)
2. `plugin marketplace update aj-house-rules` — **re-fetches** the clone
3. `plugin install <id> -y` — registers the plugin (a no-op once registered)
4. `plugin update <id>` — re-points the registration at what's now on disk

All four always run, because each is a no-op on the path where the other three matter. Step 2 is
the fix: `marketplace add` answers "already on disk" for a marketplace the device has already
seen and does **not** re-fetch, so on a machine that already had the plugin, the cached clone
stayed on the old commit, `plugin update` found nothing newer, and `install` alone would have
left the registration silently pointed at the stale copy.

**Three ways this sequence reaches a machine:**

- [`tools/bootstrap.ps1`](../../tools/bootstrap.ps1) / [`bootstrap.sh`](../../tools/bootstrap.sh)
  probe for a working Python (the same probe `run.sh` uses) and hand off to `install.py`, which
  also writes `verbose: true` and `model: opusplan` into `~/.claude/settings.json` — settings the
  harness reads at startup that no plugin can ship (`--no-verbose` / `--no-model` skip either).
  `model: opusplan` is read by the CLI and IDE only; it does nothing in the desktop Code tab
  (session-level model picker outranks a settings file) or a cloud session (managed VM, never
  receives a device settings file).
- [`tools/update.bat`](../../tools/update.bat) restates the same four `claude` commands directly,
  needing no Python and no clone — double-click it. It does not touch the two settings above.
- A hand-run `/plugin` menu, or the four `claude plugin` commands typed manually.

**Proving the published plugin installs cleanly**:
[`tools/clean_install_test.py`](../../tools/clean_install_test.py) strips the local install,
backs up `~/.claude/settings.json`, reinstalls from GitHub using the same two documented CLI
commands a user would run, and re-runs `verify.py` against the fresh clone —
proof against what a stranger's machine would actually get, not just the working tree.

**Proving the tools' own decision logic**:
[`tools/verify_tools.py`](../../tools/verify_tools.py) (480 lines, 32 checks, last run
2026-09-15: all PASS) covers the logic inside `session_ledger.py`, `clean_install_test.py`, and
`measure_footprint.py` — deliberately *not* anything that shells out to the real `claude` CLI or
mutates a real machine's config, which is what `clean_install_test.py` itself is for.

## Invariants

- **The four-command order is fixed**: add, update, install, update. Collapsing or reordering it
  silently strands any machine that already has an old version installed — the failure is
  invisible on a fresh machine, which is exactly the case that doesn't expose it.
- **`update.bat` needs no Python and no repo clone** — it must keep restating the four commands
  literally rather than calling into `install.py`, or it stops being double-click-portable.
- **Every `claude` line in `update.bat` uses `call`** — the CLI is `claude.cmd`, and running one
  `.cmd` from a `.bat` without `call` ends the script after the first command.
- **`update.bat` is CRLF throughout and ends in `pause`** — `cmd.exe` mis-parses an LF-only batch
  file with `goto` labels, and a double-clicked window closes before output can be read without
  the trailing `pause`. `.gitattributes` pins `*.bat text eol=crlf` so a checkout can't silently
  lose this. `tools/verify_tools.py` checks both.
- **The `verbose`/`model` settings cover the CLI and IDE only** — never claim they affect the
  desktop Code tab or a cloud session; both read the model from elsewhere entirely.

## Traps

- **Running only `marketplace add` + `plugin install` on a machine that already has the plugin
  keeps the old version, and looks like success.** No error, no warning — `plugin update`
  afterward would report "already at the latest version" and name the **stale** one. The
  temptation to treat `add` + `install` as "the two commands that matter" is exactly what
  `install_steps()`'s ordering exists to prevent.
- **A stale install passes every file-level `verify.py` check while the running session executes
  the old on-disk copy from before the last update.** Hooks and agents are read at Claude Code
  startup, so an update is never live in a window that's already open. This has already happened
  once: the plugin sat three commits behind for a whole session, injecting four rules while the
  repo on disk had eleven. `verify.py` proves the *code* is correct; it cannot prove Claude Code
  *loaded* it.
- **`.ps1` files aren't double-click-runnable on Windows by default** — this is the actual reason
  `update.bat` exists as a `.bat` rather than a thinner `.ps1` wrapper.
- **`clean_install_test.py`'s cleanliness check can contradict its own strip step** if the strip
  doesn't fully clear the cache before reinstalling — this class of bug is exactly why
  `tools/verify_tools.py` exists: `tools/` had no coverage at all before 2.15.0.
