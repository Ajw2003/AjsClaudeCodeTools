# Handoff: ajsagent/sharp-edison-y4xjzv (2026-11-19)

## What the work is for

Make the design loop stop forcing one page format. A page may take any format that meets seven basics (summary, next step, a picture per idea, short blocks, numbered steps, a checklist when aj acts, fits 375px), checked by `scripts/page_criteria.py`.

## Where it stands

- This branch continues `AjsAgent/speed-switches`, whose Windows session was cut off by a usage limit. Its uncommitted step 4 (#545) came from the save ref `refs/house-rules/saves/AjsAgent/speed-switches/437b9f62`; the stray `grep.exe.stackdump` was left out.
- All four steps (#542 to #545) are built. Plugin 2.82.0.
- Full verify.py passes 1294 of 1294, tools/verify_tools.py 54 of 54, docs drift 0.
- QA page: `docs/plans/flexible-pages-qa.html`. Issues #541 to #545 say `needs review`.

## The next step

aj runs the three tests on the QA page and replies "QA passed: flexible pages" or says what failed. On a pass, open a pull request into main (`Refs #541`).

## What is unverified

- Nothing has run on aj's Windows PC or in the desktop app since the pickup.
- A review page made by make_page.py cannot carry a finding marker; an art page passes only because the template's hidden icon sprite counts as a picture.
- The page check does not test that the next-step box stays on screen; only `--visual` or a look does.
- `AjsAgent/speed-switches` on GitHub still stops at step 3; the finished work is only on this branch.

## Issue numbers

Flexible pages: #541 (parent), #542, #543, #544, #545 (steps).
