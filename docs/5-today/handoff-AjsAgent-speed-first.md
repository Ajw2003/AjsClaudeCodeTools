# Handoff: AjsAgent/speed-first (2026-11-24)

## What the work is for
aj wants routine work fast: less hook time on every tool call and a quicker test suite. The review of 2026-11-24 (docs/qa/review-ajsclaudecodetools-2026-11-24/report.md) measured 66 ms of import per hook call, 9 processes per Write and 748 ms of serial label reads.

## Where it stands
Design approved as "Design approved: speed first 1A 2A 3A 4*": all five hook-speed steps, label reads run at the same time, the reply judge left alone and timed, and the test suite sped up now where easy wins exist. Stage is Build (aj sent "Build plan approved: speed first"). Step 1 (#626) is with a builder. The build plan page was sent to aj after review round 2. The systems doc is docs/4-systems/hook-speed.md, the build plan page is docs/plans/2026-11-24-speed-first-plan.html, and the decision is in docs/6-decisions/Decisions.md. No code is changed. The branch merged main with `-X ours`, so .claude/house-rules-loop.json lacks the review-command approval entries that were only on main.

## The next step
Read the step 1 builder's report and run tools/time_hooks.py and tools/verify_tools.py myself. Then merge step 1 and start step 2. Step 1 is the timing script (tools/time_hooks.py and the saved baseline) on this branch, and steps 2 to 6 follow, each reporting a before and after number.

## What is unverified
verify.py has not been run on this branch. The review's timing figures have not been repeated; step 1 does that. The plan page had two reviewer rounds; round 2's five fixes were applied without a third review, so it is stamped open-risks, and the step 4 picture still shows serial reads. Step 4's premise is already false: the label reads run in a thread pool (design_loop.py:826).

## The issue numbers
Parent #625; steps #626 (timing script), #627 (load less), #628 (one process per phase), #629 (label reads), #630 (append-only log), #631 (easy test wins).

## Update 2026-11-24 (side task)
Commit 09be0861 made `/house-rules:review` default plan, code, codebase, image and style reviews to Sonnet (plugin 2.94.5); page and diff stay Opus, a typed `--model` wins. Unverified: the full `verify.py` run after this change was not seen to finish, and no live review run was made. Speed first is unchanged: the next step is still the build plan approval and step 1 (#626). Issue: the review command is Refs #617.
