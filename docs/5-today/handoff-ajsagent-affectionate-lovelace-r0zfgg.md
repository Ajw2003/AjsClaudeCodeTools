# Handoff: clear-roadblocks plan

## What the work is for
aj wants a house rule that stops the agent claiming a roadblock (a missing tool, the wrong machine) without checking, and makes it install tools and take other routes itself, especially in bypass permission mode.

## Where it stands
Design approved on 2026-11-22 as "Design approved: clear roadblocks 1C 2A" (a rule plus an end-of-reply check that blocks twice, then warns; only licences, logins, purchases and destructive actions stay aj's). Planning is written: `docs/4-systems/roadblocks.md`, a decisions entry, three step issues and a build plan page `docs/plans/2026-11-22-clear-roadblocks-plan.html`. The build plan was approved ("Build plan approved: clear roadblocks") and the stage is Build. Step 1 (#570) is built but blocked: the rule text is in rules/house-rules.md and rules/detail/roadblocks.md, but verify.py fails one check because the injected rules are 9962 characters against a 9700 limit. Steps 2 and 3 have not started.

## The next step
Check the step 1 builder's report (verify.py before and after), then start step 2 (#571, the check), then step 3 (#572, tests, docs, version).

## What is unverified
verify.py fails 1 check (inject size, 9962 > 9700) until aj picks how to make room; every other check passes. How the block count is kept between replies (the state file) is not designed or tested; step 2 decides it against how `hook.py` reads the transcript.

## Issue numbers
#569 parent; #570, #571, #572 steps.
