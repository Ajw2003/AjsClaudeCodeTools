# Handoff: ajsagent/eloquent-mayer-0ayp82 (2026-11-22, build plan approved, phase 1 building)

## What the work is for

Four workflow fixes aj asked for. First, no wait may run unchecked or for ever: a one-minute first check, a check every minute after that, and a stated done-test and deadline for every wait. Second, a visual check for everything that can be seen (video of a feature, a frame sheet for animation, phone and desktop screenshots of a flow), so the agent can capture, critique and fix its own visual work without aj in the middle. Third, pages always reach aj: any page made or updated in a turn is sent (and sent again after a change) before the turn ends, so aj never has to ask. Today's end-of-turn page check (`scripts/house_rules/core.py:3261`, `design_loop.py:2466`) only wants a link in the reply, so a page can be linked but never sent. Fourth, pictures on pages must always show: `make_page.py:156` copies each picture into a `<page>-pics/` folder and links it by relative path, so a page sent on its own loses its pictures. Measured on a lone copy of the proposal page: 5 of 5 pictures broken, against 0 of 5 in the repo; six other pages in `docs/plans/` use the same folder pattern.

## Where it stands

- aj approved the design on 2026-11-22: "Design approved: wait clocks, visual checks, page sending and pictures 1A 2A 3B 4B 5A 6A". Choices 3B (Python Playwright and Pillow) and 4B (a separate reviewer helper critiques each round) differ from the suggested options. The stage file `.claude/house-rules-loop.json` says stage `plan`, feature `wait clocks`; the approval is committed. Code edits are still locked.
- aj approved the build plan on 2026-11-22 as "Build plan approved: wait clocks 1B" (an early check after phase 1, while phases 2 to 4 keep building). The stage is Build; the approval is committed (`8d71568`). Phase 1 is under way: two builders, each in its own worktree, are building #556 (pictures into the page file) and #558 (the send rule and the builder's send line). #556 is built and merged into this branch (`056e0f6`, builder commit `b48e9e3`): `embed_pictures` in `make_page.py` replaces `copy_pictures`, with five new verify cases. I read its code and it is right, but I have not yet confirmed the full test totals myself. #558's first report was wrong: its commit had no verify cases and its new rule section sat mid-file in `rules/detail/show-dont-tell.md`; that builder (`a8ab3c5`, branch `worktree-agent-a8ab3c5bda9055049`, commit `6b8a0b5`) was sent back to fix both and is not merged. #557 and #559 wait on #558.
- Planning is done: systems doc `docs/4-systems/wait-and-visual-checks.md`, a decisions entry, indexes updated, parent issue #555 and step issues #556 to #568 (labelled `Feature`, `AjsAgent created this`, `in progress`, each naming dependencies, dependants and done-criteria).
- The build plan page `docs/plans/2026-11-22-wait-and-visual-checks-build-plan.html` (source `.page.json` beside it) has four phases and one choice (when aj checks: once at the end, or early after phase 1). It meets all basics by `page_criteria.py`, shows no sideways scroll at 375px, and its picture loads in a copy opened alone. aj approved it.
- The proposal page `docs/plans/2026-11-22-wait-and-visual-checks.html` had its pictures put into its source as inline data by hand, so they show when the page is sent alone.
- Findings the design rests on: the guard refuses foreground sleep loops and timeouts over 60 seconds (`scripts/house_rules/safe_git.py:669,678`) but not background tasks; `scripts/stallcheck.py` is manual; the visual check (`scripts/house_rules/writing.py:227`) counts any command containing "browser" or "capture"; the page checks (`core.py:3261`, `design_loop.py:2461`) accept a link, not a send; `make_page.py:156` links pictures in a `-pics/` folder that does not travel with the page.
- An unused starter file was moved to `docs/plans/_to_delete/` because the write guard blocked overwriting it.

## The next step

When the #558 builder reports, merge its branch (it touches the end of `make_page.py`; #556 touched `copy_pictures`), then, with no builder running (a builder's `pkill -f verify.py` or its own run can kill or confuse mine), run the full `verify.py` and `tools/verify_tools.py` once each and quote the totals; then build #557 (depends on #556) and #559 (depends on #557 and #558). Then send aj the early-check page for phase 1 (choice 1B) while building phase 2 (#560 to #563, the wait clock), phase 3 (#564 to #567, the visual loop), phase 4 (#568, docs, tests, version, QA page). Prove each fix by planting the failure it should catch: a hanging and a stalled process, a broken picture, an unsent page, and a page with seeded sideways scroll the loop must repair alone.

## What is unverified

- Builder #556 reported `verify.py` passing "205 of 205" while builder #558 reported 1337 checks for the same suite; the difference is unexplained until my own full run completes. My first full run was lost (no totals line; a builder was running `verify.py` at the same time).
- Nothing is built: `waitfor.py`, `visualcheck.py`, the `visual-loop` skill, the page-sending check and the picture embedding do not exist.
- Python Playwright and Pillow worked in a scratch virtual environment here only; `visualcheck.py` must install nothing by itself and `doctor` must print the install commands. aj's own machine is untested and not recorded in `rules/handover-target.md`.
- Unity and game capture is only planned. The false-alarm rate of a widened visual-file list is unmeasured until #567.
- I have not seen how aj's side panel renders either page.
- ProjectState was not updated: nothing about the product changed yet.

## Issue numbers

Parent #555. Steps: #556, #557 (pictures); #558, #559 (page sending); #560, #561, #562, #563 (wait clock); #564, #565, #566, #567 (visual loop); #568 (docs, tests, version).
