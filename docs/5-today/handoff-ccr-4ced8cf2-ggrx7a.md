# Handoff: modular tests and quieter hook messages

## What the work is for
Every test becomes a module that runs alone or chained with others, so a change to one part runs only that part's tests. New tests that are not modules are refused, old ones are listed, and a skill and command convert them.

## Where it stands
Quieter messages: design approved ("Design approved: quieter hook messages 1* 2A"), stage Plan. aj's own answer to choice 1: hide all hook messages by default, expandable in chat. A docs lookup on whether hooks can do that is pending; no systems doc or issues yet.

Second piece of work: aj asked to fix repeating hook messages (a screenshot of two). A proposal page `docs/plans/2026-11-23-debug-log-spam/proposal.html` is sent; no issues yet, nothing built, waiting on two choices.

Modular tests: Design approved ("Design approved: modular tests 1A 2* 3A"). Planning is done: `docs/4-systems/modular-tests.md`, the issues, and the build plan page `docs/plans/2026-11-23-modular-tests/build-plan.html`. The stage is Plan. Nothing is built.

## The next step
Read the docs lookup result, then write `docs/4-systems/` doc and issues for quieter messages (decisions-log entry still owed). For the quieter-messages work: aj picks the two options and approves ("Design approved: quieter hook messages"). For modular tests: aj approves the build plan ("Build plan approved: modular tests"). Then build step 1, the rule text and its detail file (#576). The injected rules sit near the 9700-character limit, so the new section needs room made.

## What is unverified
The autosave lock collision is read from code and the Windows error text, not reproduced. Nothing has been run. The gate's file-name patterns and the module header format are untested designs. Plunderspell's repository name is not known, so its tests are not planned.

## The issue numbers
Parent #575. Steps: #576 rule text, #577 refactor switch, #578 write-time gate, #579 skill, command and audit, #580 convert `tools/verify_tools.py`, #581 offshoot suite issues, #582 docs and version.
