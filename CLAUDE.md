# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What this repo is

A personal Claude Code plugin repo. Its mature plugin is `house-rules`, which turns aj's global
CLAUDE.md-style rules into a Claude Code plugin, delivered via hooks so they follow every device
and project instead of a file that has to be copied around. Published as a GitHub marketplace
(`.claude-plugin/marketplace.json`), installed with `claude plugin install`. Two younger,
not-yet-load-bearing offshoots (`claude-prompt-workshop/`, `claude-agent-router/`) share its
shim-plus-Python-file shape; see [docs/offshoots-plan.md](docs/offshoots-plan.md).

**[docs/README.md](docs/README.md) is the entry point** for everything except running a command
in this repo — what's built, where it stands, how each system works, why past decisions were
made.

**This file is a pointer, not a copy.** The actual rules text lives at
[claude-house-rules/plugins/house-rules/rules/house-rules.md](claude-house-rules/plugins/house-rules/rules/house-rules.md),
injected every session by the plugin's own `SessionStart` hook, and its full detail lives under
`rules/detail/`. **Never paste the rules back into this file** — Claude Code auto-loads every
`CLAUDE.md` it finds, so a copy here loads twice and drifts from the original unnoticed;
`verify.py`'s duplication check fails if it happens. Edit only `house-rules.md` itself; if the
change has a shell signature add a `guard` pattern and a `verify.py` case in the same change.

For the hook-by-hook table, the design constraints `hook.py`/`run.sh` are built on, and which
surfaces the step-card handover format actually reaches, see
[docs/architecture.md](docs/architecture.md). This file stays small on purpose — it is
auto-loaded every session, though (docs/architecture.md, "SessionStart is not re-paid on
subagent spawn") a spawned subagent never sees it.

## Commands

All commands run from the repo root; each is detailed in docs/architecture.md or the doc linked.

- `python claude-house-rules/plugins/house-rules/scripts/verify.py` — proves the hooks match
  what the docs claim; exit 0 means every check passed.
- `python tools/verify_tools.py` — proves the scripts in `tools/` do what they claim.
- `.\tools\bootstrap.ps1` / `tools/bootstrap.sh` — installs or updates the plugin on this device.
- `tools\update.bat` — double-click update; no Python or clone needed.
- `python tools/clean_install_test.py` — proves the *published* plugin installs cleanly from
  GitHub on a fresh machine.
- `python tools/measure_footprint.py` — measures the *installed* plugin's real token cost; see
  [docs/measuring-footprint.md](docs/measuring-footprint.md).
- `python tools/session_ledger.py` — turns a session transcript into an auditable record under
  `docs/sessions/`.
- `python claude-house-rules/plugins/house-rules/scripts/docref.py check` — proves the
  archivist's `doc-ref` pointers still resolve (`fix --write` repairs, `new` prints an unused id).
- `python claude-house-rules/plugins/house-rules/scripts/plain_docs_check.py` — checks the
  plain-English doc copies under `docs/plain/` against the `plain-docs` skill's rules.

[`.github/workflows/verify.yml`](.github/workflows/verify.yml) runs the first two on every push
and pull request.
