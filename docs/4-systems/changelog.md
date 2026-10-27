# Changelog pages

**Status: planned, not built** (issue #384, design approved 2026-10-27 as "Design approved: changelog page
rule 1A 2A 3A"). This document describes the mechanism as planned; each section is updated as its step
lands.

Every repo keeps a changelog page. It comes from the Changes section of the PlunderSpell visual roadmap
(`Ajw2003/PlunderSpell`, `docs/roadmap-visual/`), which aj asked to keep as the template.

## Where it lives (1A)

`docs/changelog/` in each repo, next to the six tiers rather than as a seventh:

- `changelog.json`: the page content, in the page builder's shape.
- `changelog.html`: the page `make_page.py` builds from it.
- `changelog-pics/`: the pictures the builder copies next to the page.

## The rows

Each row is a tagged, tap-to-open entry built by `make_page.py`'s Changes part, unchanged:

| Tag | Shown as | Meaning |
|---|---|---|
| `keep` | Kept | Built and checked. |
| `chg` | Changed | Works differently now; carries a before-and-after picture. |
| `new` | New | Being built now, or next. |

A row marked `{"visual": true}` must carry a real, existing picture (3A); the builder already refuses one
without when the project's `docs/page-style.json` says `"pictures": "required"`.

## The template (#385)

`templates/changelog.page.json` in the plugin. The `house-rules:project-docs` skill says how to make
`docs/changelog/changelog.json` from it.

## When it is checked (2A)

- **Session start (#386).** `docstiers` also looks for `docs/changelog/changelog.json` and names it when
  missing, in the same message as any missing tier.
- **Pull request (#387).** Creating a pull request whose branch changes nothing under `docs/changelog/`
  gets a reminder to add a row. It never blocks.

## Rule text (#388)

One sentence in `rules/house-rules.md`, "Documentation goes in tiers"; the detail in
`rules/detail/docs-tiers.md`.
