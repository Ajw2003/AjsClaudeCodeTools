# Today — 2026-09-24 (session 2)

Executed [`docs/plans/tiered-doc-folders.md`](../plans/tiered-doc-folders.md): gave each of the
six documentation tiers its own numbered folder, so they sort in tier order in any file browser,
and migrated this repo's own docs onto the new layout rather than leaving them flat.

## What was done

- **The layout.** Each tier moved into its own folder: `docs/1-landing/README.md`,
  `docs/2-roadmap/Roadmap.md`, `docs/3-state/ProjectState.md`, `docs/4-systems/*.md`,
  `docs/5-today/Today.md`, `docs/6-decisions/Decisions.md`. `docs/plain/` mirrors the same
  layout (`docs/plain/4-systems/hook-engine.md`). A new, short, human-facing `docs/README.md`
  now sits at the top of `docs/`, pointing at the full index.
- **`hook.py`'s `docstiers`.** Checks the new paths; a project still on the old flat layout is
  told which file moves to which new path, rather than being told to scaffold tiers it already
  has. The commit-time reminder and the harvest long-form-reasoning text were updated to the new
  paths too.
- **`plain_docs_check.py`.** The queue reads `docs/4-systems/`; the fixed sources are
  `docs/1-landing/README.md`, `docs/3-state/ProjectState.md`, `docs/2-roadmap/Roadmap.md`; the
  excluded list names `docs/6-decisions/Decisions.md`, `docs/4-systems/README.md`, and the new
  `docs/README.md` (already the plain version).
- **`docref.py`.** The legacy-prose-pointer pattern matches the new folder names; `fix --write`
  repaired every stale `doc-ref` pointer across the repo mechanically.
- **Plugin text.** `rules/house-rules.md`, `rules/detail/docs-tiers.md`,
  `rules/detail/long-form-reasoning.md`, `agents/archivist.md`,
  `skills/project-docs/SKILL.md` (tier table, scaffolding steps now create the six folders plus
  the short `docs/README.md` as its own step before tier 5), `skills/plain-docs/SKILL.md`, and
  `commands/harvest-scan.md` all point at the new paths.
- **Version bump.** `2.33.0` → `2.34.0` in `plugin.json`.
- **Verified.** `verify.py` 366/366 PASS, `verify_tools.py` 39/39 PASS, `docref.py check` clean
  outside `verify.py`'s own fixtures, `plain_docs_check.py` OK. The `docstiers` hook prints
  nothing against this repo and the move message against a scratch old-flat-layout copy.

## What was deliberately not done

- **`docs/archive/` and `docs/sessions/`** were left untouched, as historical record.
- **Old `docs/6-decisions/Decisions.md` entries** had only their link paths repaired, not their
  prose — they describe what was true when they were written; a new dated entry at the top
  records this change.

## What to do next, in order

1. Run `/house-rules:plain-docs` on the remaining system docs (`verify-suites.md`,
   `plugin-distribution.md`, `offshoot-plugins.md`) — unchanged from before this session, still
   open.
2. Everything still open in [`ProjectState.md`](../3-state/ProjectState.md)'s Cross-cutting
   section — none of it was touched by this plan.
