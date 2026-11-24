# Handoff: AjsAgent/festive-mayer-ce8zij (2026-11-24, proposal for two new skills)

## What the work is for

aj wants two new skills in the house-rules plugin. `visual-docs` turns the tier docs into one
condensed, illustrated, human-worded page in the style of a game design document. `visual-roadmap`
keeps a roadmap current by itself, redrawing two visual views (a racetrack and a burn-up chart are
suggested) whenever an issue opens or closes or a pull request merges into the dev branch or main.

## Where it stands

- aj's second correction (2026-11-24): the roadmap must not depend on GitHub Actions (their budget may run out, or the Action could exhaust it). It now runs locally only, with GitHub Pages as an optional publish step (a `roadmap-view` branch served by Pages, off by default). Refresh triggers: the plugin's session hook (it already matches `issue_write`, `merge_pull_request` and Bash), a new git post-merge hook, session start, and `/house-rules:visual-roadmap update`. The page now has ten picks (the "how views are opened" pick went away because local and Pages views are both HTML; a pick for issues closed without a merge was added).

- aj's correction (2026-11-24): both skills must work in any repo with house rules docs, not only this one. The page now says so: visual-roadmap ships an install command (`/house-rules:visual-roadmap install`) that adds the workflow and a per-repo settings file (dev branch name, label per stage), and repo facts are labelled as examples. A round-3 review and an editor pass were started on that revision.

- Nothing is built. The only output is a proposal page,
  `docs/plans/2026-11-24-visual-docs-and-roadmap.html`, with its content file beside it, and a
  `CHANGELOG.md` line and `docs/5-today/Today.md` entry. Committed and pushed on this branch.
- The page holds ten choices for aj, including: what refreshes the roadmap (local triggers only are suggested), which two views, where the views live (local files by default, GitHub Pages optional), how the branch names are set, where an issue closed without a merge goes, grouping by roadmap milestone, how and when the review runs on visual-docs, and the scope and layout of the docs page. It assumes the review command on branch `AjsAgent/jolly-dirac-fvh4cg` (parent issue 617, steps 618 to 621) is merged and built.
- This repo has no dev branch today: `git branch -r` shows only `main` and session branches.
- The page passed `make_page.py`'s own visual check in light and dark with no overflow, and carries ten pictures (not rechecked at 375px since the local-first rework). `@house-rules:reviewer` reviewed the page (22 findings); all are applied, and three design
  findings became new picks (how views are opened, the docs page layout, phase grouping). Later rounds found 15 and then 20 more; the findings that still applied to the local-first design are applied. The page has no review stamp yet.

## The next step

Wait for aj's picks and the line "Design approved: visual docs and visual roadmap skills". Then log the
decision in `docs/6-decisions/Decisions.md`, create one parent issue and one child issue per step
(labels `AjsAgent created this` plus a category), and build `visual-roadmap`'s data file and racetrack first.

## What is unverified

- Round 3 and the editor pass on the any-repo wording: results not yet applied when this note was written.
- Neither skill has been tried on a second repo; only this repo is reachable from here.
- Whether branch-based GitHub Pages draws on the Actions allowance is unverified; the page says so and keeps Pages off by default.
- Reading issues locally needs `gh` logged in on aj's machine; not checked.
- The page was rebuilt after the round-3 review started, so round 3 reviewed an older draft; the local-only rework has had no review yet.
- Both skills depend on the review command, which is planned and not built; whether `.svg` counts as an image for its image mode is undecided.
- The pictures are mock-ups, not output of the real skills.
- Nothing about the GitHub Action design has been run: workflow permissions and whether an Action can
  push to a `roadmap-view` branch in this repo are untested.

## Issue numbers

None yet. They are created after aj approves.
