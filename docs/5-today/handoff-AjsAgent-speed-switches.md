# Handoff: AjsAgent/speed-switches (2026-11-18)

## What the work is for

Make the design loop stop forcing one page format. aj wants a page to suit what it shows (proposal, build plan, QA, review, art), always with visuals, short blocks, numbered steps, a visible next step and a tick-box checklist when there is something to do.

## Where it stands

- The branch holds all of main and is pushed.
- aj approved the design and the build plan on 2026-11-18 ("Build plan approved: flexible pages 1A 2A"). Stage: Build. The systems doc is `docs/4-systems/flexible-pages.md`.
- Step 1 (#542, `scripts/page_criteria.py`) was handed to a builder helper and is in progress; steps 2 to 4 (#543, #544, #545) wait on it.

## The next step

Check the builder's step 1 against its quoted test output, push, then hand step 2 (the page check reads a page) and step 3 (starters) to builders, then step 4 (rules, docs, version, QA page). When all is built, swap each issue's `in progress` for `needs review`.

## What is unverified

- Phase 3 live headless-session tests were not re-run on this PC (they start paid sessions).
- The seven Windows-only test failures are not fixed or root-caused beyond reading three of them.
- The phase 4 roadmap item has all 15 issues closed; its recorded-day finish test has not been decided on.

## Issue numbers

Flexible pages: #541 (parent), #542, #543, #544, #545 (steps). Related: #535 (feature switches), #539 (version check asks the desktop account copy to update).
