# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command plan)

## What the work is for

aj wants one `/house-rules:review` command that sends the existing reviewer at code, an image, a screen's style or a whole repo, in any project that has the plugin installed. The reviewer is extended with four modes, not duplicated.

## Where it stands

- Design approved by aj: "Design approved: review command 1A 2A 3*". 3* means the sweep has no folder cap; over 12 top-level folders the command first states the folder count, estimated time and usage.
- Stage: Plan. Parent issue #617; steps #618 (modes), #619 (command), #620 (verify.py checks), #621 (docs and version).
- Written so far, docs only: `docs/plans/2026-11-24-review-command.html` (design), `docs/plans/review-command-plan.html` (build plan), `docs/4-systems/review-command.md`.
- The plan was reviewed twice (15 findings, then 13, all applied) and is stamped open-risks. It carries three questions for aj: how a sweep handles the 60-second agent deadline, whether repo-root files are reviewed, and where the mode lists live.

## The next step

Wait for "Build plan approved: review command" with answers to the three questions. Build nothing before that line.

## What is unverified

- The per-folder time and token figures in the sweep notice are placeholders until step 2 measures a real folder.
- `rules/waits.json` says the agent deadline is 60 seconds; `skills/visual-loop/SKILL.md` and the design page say 900. The file was read, not tested with a real sweep.
- Claude Code's own built-in `/review` was named from product knowledge and not tested.
- Nothing has been run, because nothing is built.

## Issue numbers

#617 (parent), #618, #619, #620, #621. Related: #610 (the 60-second segments), #622 (visual-loop skill quotes old deadlines).
