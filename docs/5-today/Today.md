# Today — 2026-09-26

Made `versioncheck` install the plugin update itself, and stopped it asking for an update that
was already installed. See the dated entry in [`Decisions.md`](../6-decisions/Decisions.md).

## What was done

- **Reads the install on disk.** `_installed_on_disk()` in `hook.py` reads
  `~/.claude/plugins/installed_plugins.json`. Newest version already installed but an older copy
  running → a one-line "start a new session" notice, no banner, no marker.
- **Updates itself.** When an update is needed, the hook runs `claude plugin marketplace update`
  (only if that clone is stale) and `claude plugin update`, in a 60 s budget, then re-reads
  `installed_plugins.json`. Success is a one-line notice. The hook's timeout went 10 → 90 s.
- **Failure path.** The banner now names what failed and tells Claude to run the commands
  without asking in chat first; `guard`'s first-command prompt is the user's yes.
  `HOUSE_RULES_AUTO_UPDATE=off` skips the automatic run.
- **Rules.** `rules/detail/handover-command.md` says the plugin's own update is already answered.
- **Tests.** Every `versioncheck` case in `verify.py` now uses a fake `claude`
  (`HOUSE_RULES_VC_CLAUDE`) and its own `installed_plugins.json`. Four new cases: restart-only,
  update works, update exits 0 but nothing installed, auto-update off. They and the reworded
  banner check fail against the previous `hook.py`.
- **Docs.** `docs/architecture.md` (row and new section), `claude-house-rules/README.md`,
  `Decisions.md`.
- **Version bump.** `2.36.0` → `2.37.0` in `plugin.json`.
- **Verified for real.** In a cloud session with 2.30.0 installed and GitHub on 2.36.0, the new
  hook refreshed the marketplace, installed 2.36.0 in about 3 s, and `claude plugin list` showed
  2.36.0. A second run from the same old copy gave the "start a new session" notice.

## What to do next, in order

1. Run `/house-rules:plain-docs` on the remaining system docs (`verify-suites.md`,
   `plugin-distribution.md`, `offshoot-plugins.md`) — still open.
2. Everything still open in [`ProjectState.md`](../3-state/ProjectState.md)'s Cross-cutting
   section.
