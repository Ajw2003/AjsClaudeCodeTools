# Handoff: AjsAgent/speed-switches (2026-11-19, run 3 passed; #546 merged)

## What the work is for

Make the design loop stop forcing one page format. A page may take any format that meets seven basics (summary, next step, a picture per idea, short blocks, numbered steps, a checklist when aj acts, fits 375px), checked by `scripts/page_criteria.py`.

## Where it stands

- All four steps (#542 to #545) are built; plugin 2.82.0. Stage: Build. Issues #541 to #546 say `needs review` (2026-11-19).
- aj's desktop QA failed because the desktop app loads the claude.ai account's plugin copy (follows main). QA now runs as headless sessions on the branch code: `docs/plans/2026-11-19-flexible-pages-live-tests/live_flexible_pages.py`.
- Run 1 passed 3 of 3, run 2 failed refused-once (checker stopped at a missing type; fixed, 1608f64), run 3 passed 3 of 3 (`live_flexible_pages-result-3.txt`).
- #546 (verify.py ignores the repo's typed switches) is merged here (adb5ec4). Its check (g) set the ignore list on `os.environ`, but the hook runs with the `_fs_env` copy, so it failed everywhere; corrected in the commit after the merge.
- On aj's Windows PC, from the repo with `.claude/house-rules-mode.json` present: verify.py 1289 of 1295, verify_tools 53 of 54. Every failure is on #523's Windows-only list (safe_git 81, 84, 206; design_loop 266, 344; make_page A14; tools A16).
- `ajsagent/sharp-edison-y4xjzv` (the cloud session's branch) is now behind this one; its handoff note is superseded by this file.

## The next step

aj chose to skip a fourth live run. QA page: `docs/qa/flexible-pages-qa.html`, published on aj's account as "Flexible pages: your QA". Waiting on aj to read run 3's result and reply "QA passed: flexible pages"; then open the pull request to main (`Refs #541`, never Closes).

## What is unverified

- The corrected check (g) has not run on Linux CI yet; it passed twice on aj's PC.
- `tools/use_branch.py` reports "OK" for the CLI copy even when the desktop app will load the account copy; not yet an issue.
- The builder's QA mode fills the "Your next step" box from `wrapup.next` (the agent's step); not yet an issue.
- A make_page.py review page cannot carry a finding marker; an art page passes only because the template's hidden icon sprite counts as a picture.

## Issue numbers

Flexible pages: #541 (parent), #542 to #545 (steps), #546 (verify.py switch leak). Related: #523 (Windows-only test failures), #539 (version check and the desktop account copy).
