# Flexible pages

Status: **design approved 2026-11-18 ("Design approved: flexible pages 1A 2A 3A"), not built.** Design page:
`docs/plans/2026-11-18-flexible-pages-design.html`.

## What it owns

A page may take any format as long as it meets seven basics. Until now every page was poured into one template by
`scripts/make_page.py`, and the page check (`event_pagecheck` in `scripts/house_rules/design_loop.py`, the `PAGE_MARK_RE`
test) refused any page under `docs/plans/` without the builder's mark, however good the page was.

## The seven basics (every page)

1. A one-sentence summary at the top.
2. A "Your next step" box that stays on screen.
3. A picture or diagram for every idea.
4. No block over 60 words (aj's number to change); long detail folds away.
5. Steps numbered, one action each.
6. A tick-box checklist whenever aj has something to do.
7. Fits a phone (375 pixels wide), in light and dark.

## What each type adds

| Type | Adds |
|---|---|
| Proposal | what exists first; options with one marked as the suggestion; the approval phrase |
| Build plan | steps in order; a "done when" line per step; the code each step touches |
| QA | tick-box steps for aj; the expected result per step; what was not verified |
| Review | findings ranked; where, why and the fix for each |
| Art | the picture first; variants side by side; almost no words |

## Decisions (aj, 2026-11-18)

- **1A** The checker refuses once on a miss and names the failed basic; the corrected page then goes through.
- **2A** Five optional starters, one per type, built on the basics. Using one is a shortcut, never a requirement.
- **3A** The basics live in the plugin, so every project gets them; a project's `docs/page-style.json` can add stricter limits.

## What stays the same

Stages, approval phrases, issue labels, the QA page's measured line counts, and the builder's mark (a page with the mark
still passes without being read).

## How it will work

| Piece | Where | What it does |
|---|---|---|
| Checker | `scripts/page_criteria.py` (new) | Reads a page's HTML and lists each failed basic in plain words |
| Page check | `event_pagecheck` | A page with no mark is read by the checker instead of refused; a pass is allowed |
| Starters | `templates/starters/` (new) | One content skeleton per type for `make_page.py` |
| Rules | `rules/show-dont-tell.md`, `rules/detail/show-dont-tell.md` | Name the basics and the types |

Steps and issues are tracked under the parent issue for flexible pages.
