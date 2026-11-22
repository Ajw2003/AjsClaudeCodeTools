# Handoff: ajsagent/eloquent-mayer-0ayp82 (2026-11-22, proposal page, four fixes, waiting on aj's six choices)

## What the work is for

Four workflow fixes aj asked for. First, no wait may run unchecked or for ever: a one-minute first check, a check every minute after that, and a stated done-test and deadline for every wait. Second, a visual check for everything that can be seen (video of a feature, a frame sheet for animation, phone and desktop screenshots of a flow), so the agent can capture, critique and fix its own visual work without aj in the middle. Third, pages always reach aj: any page made or updated in a turn is sent (and sent again after a change) before the turn ends, so aj never has to ask. Today's end-of-turn page check (`scripts/house_rules/core.py:3261`, `design_loop.py:2466`) only wants a link in the reply, so a page can be linked but never sent. Fourth, pictures on pages must always show: `make_page.py:156` copies each picture into a `<page>-pics/` folder and links it by relative path, so a page sent on its own loses its pictures. Measured on a lone copy of the proposal page: 5 of 5 pictures broken, against 0 of 5 in the repo; six other pages in `docs/plans/` use the same folder pattern.

## Where it stands

- Nothing is built. The design loop's code lock is still on, because aj has not approved.
- The proposal page is `docs/plans/2026-11-22-wait-and-visual-checks.html` (source `docs/plans/2026-11-22-wait-and-visual-checks.page.json`, pictures in `docs/plans/2026-11-22-wait-and-visual-checks-art/`). It is committed and pushed, and has been sent to aj four times (after Fix 3 was added, after the editor's wording fixes, and after Fix 4 was added with the pictures built into the page file). It was checked at 375px in light and dark (steps In short, Changes and Choices; the Wrap-up step was checked before Fix 3 was added), and the text went through the editor helper three times.
- Findings the page rests on: the guard already refuses foreground sleep loops and timeouts over 60 seconds (`scripts/house_rules/safe_git.py:668`) but not background tasks, helper agents or wake-ups; `scripts/stallcheck.py` is manual; the visual end-of-turn check (`scripts/house_rules/writing.py:229`) counts any command containing "browser" or "capture" as a look.
- An unused starter file was moved to `docs/plans/_to_delete/` because the write guard blocked overwriting it.

## The next step

aj answers the six choices on the page (deadline behaviour, guard strictness, capture tools, who critiques, how firm the page-sending check is, how the six old pages with folder pictures are fixed) and sends the approval line "Design approved: wait clocks, visual checks, page sending and pictures". Then open one parent issue with a child per step, build page sending and the picture fix first (smallest, answer the most repeated complaints), then the wait clock (the visual loop reuses its deadlines), and prove each fix on seeded failures: a hanging process, a stalled process, and a deliberately broken page the loop must catch and repair on its own.

## What is unverified

- `visualcheck.py`, `waitfor.py`, the page-sending check and the picture embedding do not exist yet; nothing about their behaviour is tested.
- Playwright for Node and ffmpeg ran in this cloud container only. aj's own machine is untested and not recorded in `rules/handover-target.md`.
- Unity and game capture is only planned, not tried.
- The proposal page's own pictures were put into its source as inline data by hand, as an interim fix; after that a lone copy showed 0 of 6 broken pictures. I did not capture a clean image of them drawn in the lone copy (a sticky box covered it); the pictures loaded with a real width. I have not seen how aj's side panel renders the page.
- The false-alarm rate of a widened visual-file list is unmeasured; it must be measured on this repo's real sessions before shipping.

## Issue numbers

None yet. They are opened after aj approves the page.
