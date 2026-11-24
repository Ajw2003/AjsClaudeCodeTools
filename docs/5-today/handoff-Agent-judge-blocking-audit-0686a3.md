# Handoff: the judge blocking loop and modular-test additions

## What the work is for
A test session was blocked 12 times in a row by the end-of-reply roadblock judge, and the model was never told which reply would pass. This branch holds a proposal page that fixes the judge on both sides, and extends the already approved modular-tests design (issue #575) with a 60-second budget, per-module results and an independence proof.

## Where it stands
Proposal only; no plugin code is changed. `docs/plans/judge-blocking-fix.json` and `docs/plans/judge-blocking-fix.html` are built and were sent to aj. Cause found by reading the code: three Stop-time checks stack on one reply, and the model judge in `hooks.json` has no block counter at all. The page proposes deleting it, one shared cap of two blocks, narrower phrase lists ("next step" is removed because the house rules require it), and block messages that carry a copyable passing reply. Waiting on aj's choices and approval line "Design approved: judge blocking fix and modular tests".

## The next step
aj answers the three choices on the page (the model judge, the shared cap, where the 60-second flag lives) and sends the approval line. Then write the issues (a parent and one child per part), a build plan, and start with the judge fix and its regression case in `verify.py`.

## What is unverified
The 12 blocks were not reproduced: the blocked session's transcript was not found, only synthetic test transcripts and counter files that stop at 2. Whether Claude Code's own limit of 8 consecutive blocks applies to prompt hooks is unconfirmed. A full `verify.py` run was started in the background; the output seen showed the core part taking 68.9 seconds and one failing check (injected rules 9721 characters against a 9700 limit), which predates this work. The other parts' timings were not read.

## The issue numbers
Modular tests: #575 with steps #576 to #582 (design in `docs/4-systems/modular-tests.md`). Roadblock detection: #587 with #588, #589, #591, #590. No issues exist yet for the judge fix.
