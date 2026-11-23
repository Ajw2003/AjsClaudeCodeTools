# Handoff: modular tests and quieter hook messages

## What the work is for
Every test becomes a module that runs alone or chained with others, so a change to one part runs only that part's tests. New tests that are not modules are refused, old ones are listed, and a skill and command convert them.

## Where it stands
BUILD: aj approved both build plans ("Build plan approved: quieter hook messages" and "Build plan approved: modular tests"). Two builders are running in isolated worktrees: quieter messages step 1 (#584) and modular tests step 1 (#576); their reports are not in yet. Issues #583, #584, #585, #586, #575, #576, #577 say `in progress`.

Quieter messages (option A chosen: log plus `/house-rules:hook-log`): systems doc `docs/4-systems/hook-message-log.md`, issues #583 to #586 and build plan page `docs/plans/2026-11-23-debug-log-spam/build-plan.html` are written, waiting on build plan approval. Earlier: design approved ("Design approved: quieter hook messages 1* 2A"), stage Plan. aj's own answer to choice 1: hide all hook messages by default, expandable in chat. The docs lookup found no expandable hook message in Claude Code; aj is asked to choose an alternative. The decisions-log entry is written. No systems doc or issues yet.

Second piece of work: aj asked to fix repeating hook messages (a screenshot of two). A proposal page `docs/plans/2026-11-23-debug-log-spam/proposal.html` is sent; no issues yet, nothing built, waiting on two choices.

Modular tests: Design approved ("Design approved: modular tests 1A 2* 3A"). Planning is done: `docs/4-systems/modular-tests.md`, the issues, and the build plan page `docs/plans/2026-11-23-modular-tests/build-plan.html`. The stage is Plan. Nothing is built.

## The next step
Read both builder reports, verify their claims by running the suites myself, merge their worktree branches into this branch, then start the next steps (#585, #577), two builders at most. Once aj approves the build plan, build step 1 (#584). Earlier note: write `docs/4-systems/` doc and issues for quieter messages (decisions-log entry still owed). For the quieter-messages work: aj picks the two options and approves ("Design approved: quieter hook messages"). For modular tests: aj approves the build plan ("Build plan approved: modular tests"). Then build step 1, the rule text and its detail file (#576). The injected rules sit near the 9700-character limit, so the new section needs room made.

## What is unverified
The hook-log design assumes only `trace()` and the autosave notes move to the log; if aj means every message, step 1 widens. The autosave lock collision is read from code and the Windows error text, not reproduced. Nothing has been run. The gate's file-name patterns and the module header format are untested designs. Plunderspell's repository name is not known, so its tests are not planned.

## The issue numbers
Quieter messages: parent #583, steps #584, #585, #586. Modular tests: parent #575. Steps: #576 rule text, #577 refactor switch, #578 write-time gate, #579 skill, command and audit, #580 convert `tools/verify_tools.py`, #581 offshoot suite issues, #582 docs and version.
