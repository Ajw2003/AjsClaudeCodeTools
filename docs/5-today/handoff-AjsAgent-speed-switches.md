# Handoff: AjsAgent/speed-switches (2026-11-18)

## What the work is for

Make the design loop stop forcing one page format. aj wants a page to suit what it shows (proposal, build plan, QA, review, art), always with visuals, short blocks, numbered steps, a visible next step and a tick-box checklist when there is something to do.

## Where it stands

- The branch holds all of main and is pushed.
- aj approved the design on 2026-11-18 ("Design approved: flexible pages 1A 2A 3A"). The systems doc is `docs/4-systems/flexible-pages.md`.
- The parent issue and four step issues exist. The build plan page `docs/plans/2026-11-18-flexible-pages-build-plan.html` is built and waits on aj's approval and two choices. No code is written.

## The next step

aj answers the build plan page's two choices and says "Build plan approved: flexible pages". Then build step 1 (the checker `scripts/page_criteria.py`), then the page check, the starters, and the rules, docs and QA page.

## What is unverified

- Phase 3 live headless-session tests were not re-run on this PC (they start paid sessions).
- The seven Windows-only test failures are not fixed or root-caused beyond reading three of them.
- The phase 4 roadmap item has all 15 issues closed; its recorded-day finish test has not been decided on.

## Issue numbers

Flexible pages: #541 (parent), #542, #543, #544, #545 (steps). Related: #535 (feature switches), #539 (version check asks the desktop account copy to update).
