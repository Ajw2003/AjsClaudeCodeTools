# Handoff: the judge blocking loop and modular-test additions

## What the work is for
A test session was blocked 12 times in a row by the end-of-reply roadblock judge, and the model was never told which reply would pass. This branch holds a proposal page that fixes the judge on both sides, and generalises the already approved modular-tests design (issue #575) from tests to every wait-bound job: independent segments of at most 60 seconds, each printing its own result, so failures are caught early.

## Where it stands
Design and build plan approved by aj on 2026-11-24; stage is Build. Done and merged into this branch: #606 (criteria C1 to C5 and the six reply forms, in `rules/detail/roadblocks.md`, commit af2867e8) #612 (page check ignores picture markup, page build refuses a malformed inline svg, commit e1fab14e) and #607 (judge moved into the scripted Stop hook, prompt-type entry removed; core verify 1 of 269 failed, the existing failure). Builders are running for #608 (shared cap) and #611 (tests print as they finish); neither is merged or verified yet. #609, #610 and #613 are not started.

Cause found by reading the code: three Stop-time checks stack on one reply, and the model judge in `hooks.json` has no block counter at all. aj decided the judge stays and is tuned: written criteria, a shared cap of two blocks, narrower phrase lists, block messages that name the failed criterion and show the allowed reply forms. The design is in `docs/4-systems/roadblock-judge-and-segments.md`; the build plan page is `docs/plans/2026-11-24-judge-and-segments/build-plan.page.html`.

## The next step
Wait for the #608 and #611 builders' reports, run verify on each branch (core baseline: 1 of 269 failed, "inject stays under the per-hook additionalContext limit"; writing and make_page baseline: 1 of 110, case A14), and merge if each matches. Then build #609 and #610, then #613. The #607 builder noted that `docs/4-systems/roadblocks.md` and the new systems doc cite the changed files; #613 covers that. At most two builders run at once. When the build is ready, swap each issue's `in progress` label for `needs review` and build the QA page.

## What is unverified
The 12 blocks were not reproduced: the blocked session's transcript was not found, only synthetic test transcripts and counter files that stop at 2. Whether Claude Code's own limit of 8 consecutive blocks applies to prompt hooks is unconfirmed. A full `verify.py` run on this branch took: core 68.9 s, safe_git 127.6 s, design_loop 201.1 s, writing 8.5 s, delegation 142.9 s, docs 46.7 s, make_page 105.5 s. It also had failures (core 1, safe_git 3, delegation 3, make_page 1, design_loop stopped without a result line). This branch changes four docs files and no plugin code, and main's CI run of the same checks passes (1m22s, Linux), so the failures come from running on this Windows machine (git -C, file deletion under /tmp, waitfor, node checks). Fixing them is a separate item.

## The issue numbers
Modular tests: #575 with steps #576 to #582 (design in `docs/4-systems/modular-tests.md`). Roadblock detection: #587 with #588, #589, #591, #590. Judge and segments: #605 with steps #606 to #613.
