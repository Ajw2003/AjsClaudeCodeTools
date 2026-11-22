# Handoff: clear-roadblocks plan

## What the work is for
aj wants a house rule that stops the agent claiming a roadblock (a missing tool, the wrong machine) without checking, and makes it install tools and take other routes itself, especially in bypass permission mode.

## Where it stands
Design approved on 2026-11-22 as "Design approved: clear roadblocks 1C 2A" (a rule plus an end-of-reply check that blocks twice, then warns; only licences, logins, purchases and destructive actions stay aj's). Planning is written: `docs/4-systems/roadblocks.md`, a decisions entry, three step issues and a build plan page `docs/plans/2026-11-22-clear-roadblocks-plan.html`. The build plan was approved ("Build plan approved: clear roadblocks") and the stage is Build. Step 1 (#570) is built: the rule text is in rules/house-rules.md and rules/detail/roadblocks.md. To fit the 9700-character injected-rules limit, aj chose to delete the "Plain language and the voice" stub (its pointer lives in rules/clear-writing.md) and the rule section was shortened; verify.py passes all checks, with 9694 characters injected, 6 under the limit. Steps 2 and 3 have not started.

## The next step
Start step 2 (#571, the check), then step 3 (#572, tests, docs, version).

## What is unverified
The injected rules have only 6 characters of room, so any later rule text needs more cut; the shortened rule in house-rules.md no longer says installs happen without asking in bypass mode (only the detail file does). How the block count is kept between replies (the state file) is not designed or tested; step 2 decides it against how `hook.py` reads the transcript.

## Issue numbers
#569 parent; #570, #571, #572 steps.
