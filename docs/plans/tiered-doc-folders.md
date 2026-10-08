# Plan: give each documentation tier its own labelled folder

Requested 2026-09-24. Decisions made by aj before this plan was written:

- Folders are **numbered**, so they sort in tier order.
- The full tier-1 index **moves into its folder**; a new, short, human-facing `docs/README.md`
  replaces it at the top of `docs/`.
- **This repo migrates too**, with every link fixed, not only new scaffolds.

## The layout

| Tier | Old path | New path |
|---|---|---|
| 1 | `docs/README.md` | `docs/1-landing/README.md` |
| 2 | `docs/Roadmap.md` | `docs/2-roadmap/Roadmap.md` |
| 3 | `docs/ProjectState.md` | `docs/3-state/ProjectState.md` |
| 4 | `docs/systems/*.md` | `docs/4-systems/*.md` (the index stays `README.md` inside it) |
| 5 | `docs/Today.md` | `docs/5-today/Today.md` |
| 6 | `docs/Decisions.md` | `docs/6-decisions/Decisions.md` |

New file: `docs/README.md`: a short plain-English page for people. It says what the project is
in a few sentences, lists the six folders with one line each, and points to
`docs/1-landing/README.md` for the full index. It is not a tier; the `docstiers` check
does not require it, and `plain_docs_check --queue` does not queue it, because it is already the
plain version.

The non-tier folders stay where they are: `docs/plans/`, `docs/archive/`, `docs/generated/`,
`docs/plain/`, `docs/sessions/`. `docs/plain/` keeps mirroring the source layout, so
`docs/plain/systems/hook-engine.md` becomes `docs/plain/4-systems/hook-engine.md`.

Filenames inside the folders are kept, so existing muscle memory and `Decisions.md#anchor` links
only change by their folder prefix.

## What changes

1. **`hook.py` `docstiers`**: the tier list points at the new paths. If a project still has the
   old flat files (`docs/Roadmap.md` etc.) and not the new ones, the message says those tiers
   are in the old flat layout and names each move, rather than telling Claude to scaffold tiers
   that already exist. The other hook texts that name tier paths (the commit nudge around
   `hook.py:1273`, the harvest text around `hook.py:2940`) are updated.
2. **`plain_docs_check.py`**: the queue reads `docs/4-systems/`, the fixed sources become
   `docs/1-landing/README.md`, `docs/3-state/ProjectState.md`, `docs/2-roadmap/Roadmap.md`, and the
   excluded list names `docs/6-decisions/Decisions.md`, `docs/4-systems/README.md` and the new
   `docs/README.md` (why: already the plain version). The unlisted-top-level-`.md` sweep keeps
   working.
3. **`docref.py`**: the legacy-prose-pointer count matches the new folder names.
4. **Plugin text**: `rules/house-rules.md` (stay inside its size budget, which `verify.py`
   enforces), `rules/detail/docs-tiers.md`, `rules/detail/long-form-reasoning.md`,
   `agents/archivist.md`, `skills/project-docs/SKILL.md` (tier table, scaffolding steps
   create the six folders, plus the short human `docs/README.md` as the last scaffolding step
   before tier 5), `skills/plain-docs/SKILL.md`, `commands/harvest-scan.md`.
5. **`verify.py`**: the drift checks and fixtures follow the new paths; add cases for (a) all
   six tiers present in the new layout gives silence, (b) old flat layout is reported as
   "old layout, move X to Y", (c) the new `docs/README.md` is not queued by plain-docs.
6. **This repo's docs**: `git mv` each tier file into its folder; write the new short
   `docs/README.md`; fix every link and `doc-ref` pointer (use `docref.py fix --write` for
   `doc-ref` lines, then a path rewrite for prose links, including relative links inside the
   moved files, which now sit one level deeper). `CLAUDE.md` points at
   `docs/1-landing/README.md` as the entry point for Claude. **Not rewritten:**
   `docs/archive/` and `docs/sessions/`: both are historical records by definition.
   `Decisions.md` entries get their link paths fixed and nothing else; a new dated entry records
   this change.
7. **Version bump**: all three version copies, as `tools/check_plugin_version_bump.py` and
   `versioncheck` require.

## Done when

- `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
- `python tools/verify_tools.py` exits 0.
- `docref.py check` reports no problems outside `verify.py`'s own deliberate fixtures.
- `plain_docs_check.py` exits 0.
- A search for links to the old paths (`docs/Roadmap.md`, `docs/ProjectState.md`,
  `docs/Today.md`, `docs/Decisions.md`, `docs/systems/`, and `docs/README.md` used as the index)
  finds none outside `docs/archive/`, `docs/sessions/`, and deliberate old-layout test fixtures.
- Running the `docstiers` hook against this repo prints nothing (all tiers present), and against
  a scratch copy with the old flat layout it prints the migration message.
