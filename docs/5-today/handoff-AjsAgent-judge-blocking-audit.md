# Handoff: the judge blocking loop and modular-test additions

## What the work is for
A test session was blocked 12 times in a row by the end-of-reply roadblock judge, and the model was never told which reply would pass. This branch holds a proposal page that fixes the judge on both sides, and generalises the already approved modular-tests design (issue #575) from tests to every wait-bound job: independent segments of at most 60 seconds, each printing its own result, so failures are caught early.

## Where it stands
Build plan approved 2026-11-24; stage is Build. Builders are running for #606 and #612; their branches are not merged or verified yet.

Design approved by aj on 2026-11-24 (1A 2A 3A). Planning is done: systems doc, parent issue #605 and steps #606 to #613, decisions entry, changelog line, and a build plan page waiting for aj's approval. No code is changed.

Proposal only; no plugin code is changed. `docs/plans/judge-blocking-fix.json` and `docs/plans/judge-blocking-fix.html` are built and were sent to aj. Cause found by reading the code: three Stop-time checks stack on one reply, and the model judge in `hooks.json` has no block counter at all. aj corrected the direction: the judge stays and is tuned. The page proposes four written criteria (shared by the judge, the block message and the rules), a judge that sees the real attempts and shares one cap of two blocks, narrower phrase lists ("next step" is removed because the house rules require it), and block messages that name the failed criterion and carry a copyable passing reply, including an Unverified form. Waiting on aj's choices and approval line "Design approved: judge blocking fix and one-minute segments".

The page checker (scripts/clarity.py) leaked inline picture markup into its findings because its data-URI pattern stops at a space; this page's pictures are fixed (132 findings down to 9). A raw angle bracket had also broken the segments picture; it renders now (checked in the browser pane). The page proposes a fix for both in the checker and the build step. The editor pass on that text is applied.

## The next step
aj answers the three choices on the page (where the judge runs, the shared cap, and how data flows between segments). aj already decided: the guard refuses foreground and background launches over 60 seconds unless the launch gives a Cannot split reason that passes criterion C5 of the judge (a genuine impossibility, shown with the check, its evidence and the logic) and sends the approval line. Then write the issues (a parent and one child per part), a build plan, and start with the judge fix and its regression case in `verify.py`.

## What is unverified
The 12 blocks were not reproduced: the blocked session's transcript was not found, only synthetic test transcripts and counter files that stop at 2. Whether Claude Code's own limit of 8 consecutive blocks applies to prompt hooks is unconfirmed. A full `verify.py` run on this branch took: core 68.9 s, safe_git 127.6 s, design_loop 201.1 s, writing 8.5 s, delegation 142.9 s, docs 46.7 s, make_page 105.5 s. It also had failures (core 1, safe_git 3, delegation 3, make_page 1, design_loop stopped without a result line). This branch changes four docs files and no plugin code, and main's CI run of the same checks passes (1m22s, Linux), so the failures come from running on this Windows machine (git -C, file deletion under /tmp, waitfor, node checks). Fixing them is a separate item.

## The issue numbers
Modular tests: #575 with steps #576 to #582 (design in `docs/4-systems/modular-tests.md`). Roadblock detection: #587 with #588, #589, #591, #590. Judge and segments: #605 with steps #606 to #613.
