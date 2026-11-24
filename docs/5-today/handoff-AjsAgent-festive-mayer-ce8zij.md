# Handoff: AjsAgent/festive-mayer-ce8zij (2026-11-24, proposal for two new skills)

## What the work is for

aj wants two new skills in the house-rules plugin. `visual-docs` turns the tier docs into one
condensed, illustrated, human-worded page in the style of a game design document. `visual-roadmap`
keeps a roadmap current by itself, redrawing two visual views (a racetrack and a burn-up chart are
suggested) whenever an issue opens or closes or a pull request merges into the dev branch or main.

## Where it stands

- 2026-11-24, latest: aj's answers to choices 1 to 8 are recovered and saved (`docs/plans/2026-11-24-visual-docs-and-roadmap-answers.md` and the new artifact's `answers/current`). Choices 9 and 10 were lost and are still open. Cause of the breakage: the content file used the id `share` for all ten choices, so they were one radio group; `make_page.py` has no check for duplicate ids (found by reading it). The answers imply changes to the design (hourglass plus dependency graph, GitHub Pages on, two labelled roadmaps for In dev and Shipped) that are not yet applied to the page.

- 2026-11-24, later: aj's answers on the first published page (artifact `1YozUZzaaPAhnwhwFpnKG8`) could not be copied. Cause: all ten choices used one radio-group name. Fixed in `docs/plans/2026-11-24-visual-docs-and-roadmap.json` (ids c1 to c10). A second artifact (`THgBL8SamiG6HzkfbYpJz2`, file `docs/generated/visual-skills-proposal-with-saved-answers.html`) saves answers to its `answers/current` document. Do NOT republish the first artifact while aj's tab is open: it holds their typed answers. Ask aj for screenshots of that tab, or read `answers/current` from the new artifact with ArtifactData.

- aj's second correction (2026-11-24): the roadmap must not depend on GitHub Actions (their budget may run out, or the Action could exhaust it). It now runs locally only, with GitHub Pages as an optional publish step (a `roadmap-view` branch served by Pages, off by default; whether Pages deploys draw on the Actions allowance is unverified). Refresh triggers: the plugin's session hook (it already matches `issue_write`, `merge_pull_request` and Bash), a new git post-merge hook added after any existing one, session start, `/house-rules:visual-roadmap update`, and, if aj picks it, a prompt-time refresh at most every 5 minutes. The script reads GitHub with `gh api` because `gh issue list` is refused in cloud sessions. The page now has ten picks (the "how views are opened" pick went away because local and Pages views are both HTML; a pick for issues closed without a merge was added).

- aj's correction (2026-11-24): both skills must work in any repo with house rules docs, not only this one. The page now says so: visual-roadmap ships an install command (`/house-rules:visual-roadmap install`) that adds the workflow and a per-repo settings file (dev branch name, label per stage), and repo facts are labelled as examples. A round-3 review and an editor pass were started on that revision.

- Nothing is built. The only output is a proposal page,
  `docs/plans/2026-11-24-visual-docs-and-roadmap.html`, with its content file beside it, and a
  `CHANGELOG.md` line and `docs/5-today/Today.md` entry. Committed and pushed on this branch.
- The page holds ten choices for aj, including: how fresh the views are (a prompt-time refresh every 5 minutes is suggested), which two views, where the views live (local files by default, GitHub Pages optional), how the branch names are set, where an issue closed without a merge goes, grouping by roadmap milestone, how and when the review runs on visual-docs, and the scope and layout of the docs page. It assumes the review command on branch `AjsAgent/jolly-dirac-fvh4cg` (parent issue 617, steps 618 to 621) is merged and built.
- This repo has no dev branch today: `git branch -r` shows only `main` and session branches.
- The page passed `make_page.py`'s own visual check in light and dark with no overflow, and carries ten pictures (not rechecked at 375px since the local-first rework). `@house-rules:reviewer` reviewed the page (22 findings); all are applied, and three design
  findings became new picks (how views are opened, the docs page layout, phase grouping). Later rounds found 15 and then 20 more; the findings that still applied to the local-first design are applied. The page has no review stamp yet.

## The next step

Get aj's answers to choices 9 and 10 on the new artifact (id THgBL8SamiG6HzkfbYpJz2). Then update the proposal page to match all ten answers and send it for the approval line. Ask aj whether to add a duplicate-id check to `make_page.py` with a `verify.py` case.

Older next step:

Wait for aj's picks and the line "Design approved: visual docs and visual roadmap skills". Then log the
decision in `docs/6-decisions/Decisions.md`, create one parent issue and one child issue per step
(labels `AjsAgent created this` plus a category), and build `visual-roadmap`'s data file and racetrack first.

## What is unverified

- Round 3 is applied. Round 4 is applied too. The page is stamped open-risks; the builder caps the stamp at 2 rounds although 4 ran. The final page has had no review after round 4's edits.
- Neither skill has been tried on a second repo; only this repo is reachable from here.
- Whether branch-based GitHub Pages draws on the Actions allowance is unverified; the page says so and keeps Pages off by default.
- Reading issues locally needs `gh` logged in on aj's machine; not checked. In a cloud session, local output vanishes when the session ends unless publishing is on.
- The page was rebuilt after the round-3 review started, so round 3 reviewed an older draft; the local-only rework has had no review yet.
- Both skills depend on the review command, which is planned and not built; whether `.svg` counts as an image for its image mode is undecided.
- The pictures are mock-ups, not output of the real skills.
- Nothing about the GitHub Action design has been run: workflow permissions and whether an Action can
  push to a `roadmap-view` branch in this repo are untested.

## Issue numbers

None yet. They are created after aj approves.
