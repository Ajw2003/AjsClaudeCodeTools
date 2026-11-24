# Handoff: the judge blocking loop and modular-test additions

## What the work is for
A test session was blocked 12 times in a row by the end-of-reply roadblock judge, and the model was never told which reply would pass. This branch holds a proposal page that fixes the judge on both sides, and extends the already approved modular-tests design (issue #575) with a 60-second budget, per-module results and an independence proof.

## Where it stands
Proposal only; no plugin code is changed. `docs/plans/judge-blocking-fix.json` and `docs/plans/judge-blocking-fix.html` are built and were sent to aj. Cause found by reading the code: three Stop-time checks stack on one reply, and the model judge in `hooks.json` has no block counter at all. aj corrected the direction: the judge stays and is tuned. The page proposes four written criteria (shared by the judge, the block message and the rules), a judge that sees the real attempts and shares one cap of two blocks, narrower phrase lists ("next step" is removed because the house rules require it), and block messages that name the failed criterion and carry a copyable passing reply, including an Unverified form. Waiting on aj's choices and approval line "Design approved: judge blocking fix and modular tests".

## The next step
aj answers the three choices on the page (where the judge runs, the shared cap, where the 60-second flag lives) and sends the approval line. Then write the issues (a parent and one child per part), a build plan, and start with the judge fix and its regression case in `verify.py`.

## What is unverified
The 12 blocks were not reproduced: the blocked session's transcript was not found, only synthetic test transcripts and counter files that stop at 2. Whether Claude Code's own limit of 8 consecutive blocks applies to prompt hooks is unconfirmed. A full `verify.py` run on this branch took: core 68.9 s, safe_git 127.6 s, design_loop 201.1 s, writing 8.5 s, delegation 142.9 s, docs 46.7 s, make_page 105.5 s. It also had failures (core 1, safe_git 3, delegation 3, make_page 1, design_loop stopped without a result line). This branch changes four docs files and no plugin code, and main's CI run of the same checks passes (1m22s, Linux), so the failures come from running on this Windows machine (git -C, file deletion under /tmp, waitfor, node checks). Fixing them is a separate item.

## The issue numbers
Modular tests: #575 with steps #576 to #582 (design in `docs/4-systems/modular-tests.md`). Roadblock detection: #587 with #588, #589, #591, #590. No issues exist yet for the judge fix.
