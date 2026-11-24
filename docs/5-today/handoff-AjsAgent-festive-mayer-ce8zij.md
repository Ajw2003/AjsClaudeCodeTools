# Handoff: AjsAgent/festive-mayer-ce8zij (2026-11-24, proposal for two new skills)

## What the work is for

aj wants two new skills in the house-rules plugin. `visual-docs` turns the tier docs into one
condensed, illustrated, human-worded page in the style of a game design document. `visual-roadmap`
keeps a roadmap current by itself, redrawing two visual views (a racetrack and a burn-up chart are
suggested) whenever an issue opens or closes or a pull request merges into the dev branch or main.

## Where it stands

- Nothing is built. The only output is a proposal page,
  `docs/plans/2026-11-24-visual-docs-and-roadmap.html`, with its content file beside it, and a
  `CHANGELOG.md` line and `docs/5-today/Today.md` entry. Committed and pushed on this branch.
- The page holds five choices for aj: what drives the updates (a GitHub Action is suggested), which
  two views, where the views live (a `roadmap-view` branch is suggested, so main stays
  pull-request-only), how the dev branch is found (a setting), and the scope of the docs page.
- This repo has no dev branch today: `git branch -r` shows only `main` and session branches.
- The page passed `make_page.py`'s own visual check in light and dark with no overflow, and loads
  seven of seven pictures at 375px. A page review by `@house-rules:reviewer` was started; its findings
  are not yet applied.

## The next step

Wait for aj's picks and the line "Design approved: visual docs and visual roadmap skills". Then log the
decision in `docs/6-decisions/Decisions.md`, create one parent issue and one child issue per step
(labels `AjsAgent created this` plus a category), and build `visual-roadmap`'s data file and racetrack first.

## What is unverified

- The reviewer's page findings, and the page's `--reviewed` stamp, are not yet in.
- The pictures are mock-ups, not output of the real skills.
- Nothing about the GitHub Action design has been run: workflow permissions and whether an Action can
  push to a `roadmap-view` branch in this repo are untested.

## Issue numbers

None yet. They are created after aj approves.
