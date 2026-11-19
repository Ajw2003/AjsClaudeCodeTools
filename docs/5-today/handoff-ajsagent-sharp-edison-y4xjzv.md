# Handoff: ajsagent/sharp-edison-y4xjzv (2026-11-19, live test run 2 found a checker bug)

## What the work is for

Make the design loop stop forcing one page format. A page may take any format that meets seven basics (summary, next step, a picture per idea, short blocks, numbered steps, a checklist when aj acts, fits 375px), checked by `scripts/page_criteria.py`.

## Where it stands

- All four steps (#542 to #545) are built; plugin 2.82.0. `ajsagent/sharp-edison-y4xjzv` and `AjsAgent/speed-switches` hold the same commits.
- aj typed "QA failed: flexible pages". The cause was the test setup, not the feature: the desktop app runs the claude.ai account's plugin copy, which follows main, so `tools/use_branch.py` switched a copy the app never loads. Stage: Build. Issues #541 to #545 say `in progress`.
- aj asked that the agent test it in its own sessions. `docs/plans/2026-11-19-flexible-pages-live-tests/live_flexible_pages.py` runs three headless sessions with `--plugin-dir` on the branch code (refused once, good page, starter); run 1 passed 3 of 3 (`live_flexible_pages-result.txt`; the sessions reported plugin 2.82.0 from `--plugin-dir`, and both saved pages meet all basics by `page_criteria.py`). Run 2 (`live_flexible_pages-result-2.txt`) failed refused-once: the page had no type and no checklist, and the refusal named only the type, because `page_criteria.check()` returns early when the type is unknown. A builder helper is fixing that on `AjsAgent/fix-pc-type` (#542), with a new verify case.
- aj switched the design loop off and back on; it is on.
- Full verify.py 1294 of 1294, tools/verify_tools.py 54 of 54 (before the QA failure; no code changed since).

## The next step

Check the builder's fix on `AjsAgent/fix-pc-type`, merge it, and run the live test twice more. If all three pass both times, rebuild the QA page as a report of those runs and swap the issues to `needs review`. If one fails, fix it in the step it belongs to and run the test again.

## What is unverified

- The builder's fix was not in when this note was written.
- `tools/use_branch.py` reports "OK" for the CLI copy even when the desktop app will load the account copy; not yet raised as an issue.
- The builder's QA mode fills the "Your next step" box from `wrapup.next` (the agent's step); queued as a suggested task card for aj, not yet an issue.
- A review page made by make_page.py cannot carry a finding marker; an art page passes only because the template's hidden icon sprite counts as a picture.

## Issue numbers

Flexible pages: #541 (parent), #542, #543, #544, #545 (steps). Related: #539 (version check and the desktop account copy).
