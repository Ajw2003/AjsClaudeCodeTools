# Handoff: AjsAgent/speed-switches (2026-11-18)

## What the work is for

Make the design loop stop forcing one page format. aj wants a page to suit what it shows (proposal, build plan, QA, review, art), always with visuals, short blocks, numbered steps, a visible next step and a tick-box checklist when there is something to do.

## Where it stands

- The branch now contains all of main (merged 2026-11-18; one CHANGELOG.md conflict, both sides kept).
- A design proposal page for flexible formats is built and committed: `docs/plans/2026-11-18-flexible-pages-design.html`. It is a proposal only; no code is written.
- Phase 3 was retested on aj's Windows PC: `verify.py` 1246 of 1252, `tools/verify_tools.py` 53 of 54. The failures are tests that assume Linux paths. CI on main passes.

## The next step

aj answers the three choices on the proposal page (how a page is checked, whether starters exist, where the basics live) with "Design approved: flexible pages" plus the picks. After that: a build plan page, step issues, then build `page_criteria.py` and relax the page check in `design_loop.py`.

## What is unverified

- Phase 3 live headless-session tests were not re-run on this PC (they start paid sessions).
- The seven Windows-only test failures are not fixed or root-caused beyond reading three of them.
- The phase 4 roadmap item has all 15 issues closed; its recorded-day finish test has not been decided on.

## Issue numbers

None yet for flexible pages. Related: #535 (feature switches), #539 (version check asks the desktop account copy to update).
