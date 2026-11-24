# Handoff: AjsAgent/jolly-dirac-fvh4cg (2026-11-24, review command proposal)

## What the work is for

aj wants a command that sends the reviewer at any target: part of a codebase, images, visual style, or a whole repo, usable in any project the plugin is installed in. aj also asked whether the existing reviewer should grow or a new general critic agent should be made.

## Where it stands

- Design only; no code written. The proposal page is `docs/plans/2026-11-24-review-command.html`, built with `make_page.py`.
- Suggestion on the page: one `/house-rules:review` command, four new reviewer modes (code, codebase, image, style), no new agent.
- Round one of the page review found 16 problems, all applied. The biggest: a "new critic agent" option would have reversed the 4A decision (`docs/6-decisions/Decisions.md:42`), and a reviewer cannot start other reviewers, so the whole-repo sweep belongs in the command.
- Round two of the review was started and its result was not read when this note was written.

## The next step

Read the round-two result. If it says clean, rebuild the page with `--reviewed clean --rounds 2`, send it, and wait for aj's approval line naming the two choices (report location, sweep method). Do not build before "Design approved: review command" arrives.

## What is unverified

- The page is not stamped as reviewed.
- The claim that Claude Code has its own built-in `/review` came from the reviewer's product knowledge and was not tested.
- Nothing about the command or the new modes has been run, because none of it exists yet.

## Issue numbers

None opened yet. After approval the plan is over three steps, so a parent issue and one child per step are needed.
