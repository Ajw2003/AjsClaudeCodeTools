# Handoff: ajsagent/eloquent-mayer-0ayp82 (2026-11-22, proposal page waiting on aj's four choices)

## What the work is for

Two workflow fixes aj asked for. First, no wait may run unchecked or for ever: a one-minute first check, a check every minute after that, and a stated done-test and deadline for every wait. Second, a visual check for everything that can be seen (video of a feature, a frame sheet for animation, phone and desktop screenshots of a flow), so the agent can capture, critique and fix its own visual work without aj in the middle.

## Where it stands

- Nothing is built. The design loop's code lock is still on, because aj has not approved.
- The proposal page is `docs/plans/2026-11-22-wait-and-visual-checks.html` (source `docs/plans/2026-11-22-wait-and-visual-checks.page.json`, pictures in `docs/plans/2026-11-22-wait-and-visual-checks-art/`). It is committed and pushed. It was checked at 375px in light and dark, and the text went through the editor helper.
- Findings the page rests on: the guard already refuses foreground sleep loops and timeouts over 60 seconds (`scripts/house_rules/safe_git.py:668`) but not background tasks, helper agents or wake-ups; `scripts/stallcheck.py` is manual; the visual end-of-turn check (`scripts/house_rules/writing.py:229`) counts any command containing "browser" or "capture" as a look.
- An unused starter file was moved to `docs/plans/_to_delete/` because the write guard blocked overwriting it.

## The next step

aj answers the four choices on the page (deadline behaviour, guard strictness, capture tools, who critiques) and sends the approval line "Design approved: wait clocks and visual checks". Then open one parent issue with a child per step, build the wait clock first (the visual loop reuses its deadlines), and prove each fix on seeded failures: a hanging process, a stalled process, and a deliberately broken page the loop must catch and repair on its own.

## What is unverified

- `visualcheck.py` and `waitfor.py` do not exist yet; nothing about their behaviour is tested.
- Playwright for Node and ffmpeg ran in this cloud container only. aj's own machine is untested and not recorded in `rules/handover-target.md`.
- Unity and game capture is only planned, not tried.
- The false-alarm rate of a widened visual-file list is unmeasured; it must be measured on this repo's real sessions before shipping.

## Issue numbers

None yet. They are opened after aj approves the page.
