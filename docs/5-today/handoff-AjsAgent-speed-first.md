# Handoff: AjsAgent/speed-first (2026-11-24)

## What the work is for
aj wants routine work fast: less hook time on every tool call and a quicker test suite. The review of 2026-11-24 (docs/qa/review-ajsclaudecodetools-2026-11-24/report.md) measured 66 ms of import per hook call, 9 processes per Write and 748 ms of serial label reads.

## Where it stands
Design approved as "Design approved: speed first 1A 2A 3A 4*": all five hook-speed steps, label reads run at the same time, the reply judge left alone and timed, and the test suite sped up now where easy wins exist. Stage is Build (aj sent "Build plan approved: speed first"). Step 1 (#626) is built and pushed (tools/time_hooks.py, baseline in docs/qa/speed-first/baseline.json). Step 2 (#627) is paused (D1 in docs/qa/speed-first/ledger.md): a per-event module load broke 11 core checks because the parts register hooks into core on import; the attempt is on branch AjsAgent/speed-step2-attempt. Step 3 (#628) is with a builder. The build plan page was sent to aj after review round 2. The systems doc is docs/4-systems/hook-speed.md, the build plan page is docs/plans/2026-11-24-speed-first-plan.html, and the decision is in docs/6-decisions/Decisions.md. No code is changed. The branch merged main with `-X ours`, so .claude/house-rules-loop.json lacks the review-command approval entries that were only on main.

## The next step
Read the step 3 builder's report, rerun tools/time_hooks.py --quick and the verify parts myself, commit step 3, then do steps 4 to 6 and finally return to step 2 with a per-event module list. Step 1 was the timing script (tools/time_hooks.py and the saved baseline) on this branch, and steps 2 to 6 follow, each reporting a before and after number.

## What is unverified
verify.py has not been run in full on this branch; tools/verify_tools.py passed 56 checks in the step 1 builder's run, which I did not repeat. Five verify parts timed out at 55 seconds in the baseline, so step 6 has no numbers for them yet. The review's timing figures have not been repeated; step 1 does that. The plan page had two reviewer rounds; round 2's five fixes were applied without a third review, so it is stamped open-risks, and the step 4 picture still shows serial reads. Step 4's premise is already false: the label reads run in a thread pool (design_loop.py:826).

## The issue numbers
Parent #625; steps #626 (timing script), #627 (load less), #628 (one process per phase), #629 (label reads), #630 (append-only log), #631 (easy test wins).

## Update 2026-11-24 (side task)
Commit 09be0861 made `/house-rules:review` default plan, code, codebase, image and style reviews to Sonnet (plugin 2.94.5); page and diff stay Opus, a typed `--model` wins. Unverified: the full `verify.py` run after this change was not seen to finish, and no live review run was made. Speed first is unchanged: the next step is still the build plan approval and step 1 (#626). Issue: the review command is Refs #617.

Follow-up: the first full verify run after 09be0861 failed one check (the review override check expected `default` for code mode); fixed in the test, and a third full run was started and not yet seen to finish.

Benchmark in progress (aj asked for quality, time, cost): a seeded file with six known bugs. Opus run done: all six found, 19,934 tokens, 39.0 s. Sonnet run started, result pending. Next: a real six-file batch on both, then report. Nothing in the repo changed for it.
