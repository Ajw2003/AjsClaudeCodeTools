# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked only about choices that change how something looks or what it does.

## Where it stands
Plan stage, nothing built. The proposal page `docs/plans/2026-11-25-quiet-unattended-mode.html` (content file beside it) lists six changes and six reversed earlier decisions. A page reviewer ran once; its findings are applied, but the later loop and no-stopping changes were not re-reviewed (stamped open-risks, round 1).

## The next step
Wait for aj's line "Design approved: quiet unattended mode". Then write the systems doc, create the issues, and build in small steps, running `verify.py` after each.

## What is unverified
All of it is read from the code, not run. No live unattended or bypass session was tried. The limit of 8 blocked stops before Claude Code overrides a hook comes from a comment in `docs/4-systems/roadblocks.md`. Whether a web-app scheduled task can resume a session is unconfirmed.

## The issue numbers
None yet, because the plan is not approved. Related earlier work: #587 to #591.
