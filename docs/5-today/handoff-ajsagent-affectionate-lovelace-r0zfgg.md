# Handoff: clear-roadblocks plan

## What the work is for
aj wants a house rule that stops the agent claiming a roadblock (a missing tool, the wrong machine) without checking, and makes it install tools and take other routes itself, especially in bypass permission mode.

## Where it stands
Design approved on 2026-11-22 as "Design approved: clear roadblocks 1C 2A" (a rule plus an end-of-reply check that blocks twice, then warns; only licences, logins, purchases and destructive actions stay aj's). Planning is written: `docs/4-systems/roadblocks.md`, a decisions entry, three step issues and a build plan page `docs/plans/2026-11-22-clear-roadblocks-plan.html`. No code is built.

## The next step
Wait for aj's "Build plan approved: clear roadblocks". Then a builder does step 1 (#570, the rule text), then step 2 (#571, the check), then step 3 (#572, tests, docs, version).

## What is unverified
How the block count is kept between replies (the state file) is not designed or tested; step 2 decides it against how `hook.py` reads the transcript.

## Issue numbers
#569 parent; #570, #571, #572 steps.
