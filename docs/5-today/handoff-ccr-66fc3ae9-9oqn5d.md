# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Plan stage, nothing built. The proposal page `docs/plans/2026-11-25-quiet-unattended-mode.html` (content file beside it) has eleven changes and twelve reversed decisions. It has had three review rounds (45 holes, then 38 more); every finding is applied or decided on the page. Review stamp: open risks, round 2.

## The next step
Wait for aj's line "Design approved: quiet unattended mode". Then write the build plan page (a test command per step), have it reviewed, and build in small steps, running `verify.py` after each.

## What is unverified
Everything is read from code and the Claude Code binary, not run in a live unattended session. Unconfirmed: whether Stop hooks block in a resumed headless run, whether the web app has /goal, whether a tool call resets Claude Code's consecutive-block count, the pause-goal tool's exact name, and whether settings env reaches a resumed session.

## The issue numbers
None yet, because the plan is not approved. Related earlier work: #587 to #591.
