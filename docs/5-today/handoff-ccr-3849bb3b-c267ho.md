# Handoff: ccr-3849bb3b-c267ho (2026-11-25)

## What the work is for
Finish the speed-first work that branch AjsAgent/speed-first started: less hook time on every tool call, and a measured before and after.

## Where it stands
That branch is merged in (step 3, one hook process per tool phase). Step 5 is done: the hook log in core.py `_log_line` appends and trims only past 128 KB, with two checks. Step 4 needs no change, since the label reads already run at the same time. Measured results, old main against this branch, are in docs/qa/speed-first/results.md: Write hooks 649 to 145 ms, Bash 458 to 163 ms. The failing verify checks are the same on main and here.

Pull request #633 is open into main. Its first CI run failed on one stale check (verify_tools.py expected 6 time_hooks lines, now 4); fixed in 0a17a8ca, and verify_tools passes 56 of 56 here. The second CI run passed verify_tools but failed the version-bump gate; plugin.json is now 2.94.7. The third run is not yet seen.

Update: #633 is merged. Next target measured: the reply judge (core.py `_judge_check`) is 5,519 ms per reply; the proposal page has options A, B and C and waits on aj's choice.

## The next step
Wait for CI on #633 and merge on aj's word (main takes pull requests only); then profile the make_page verify part (100 s, the longest) for step 6, then return to step 2 with a per-event module list. aj chooses the order.

## What is unverified
CI on the fix commit is unseen. The full verify.py was not run end to end, only the seven parts separately. Timings come from a cloud sandbox, not aj's PC. The 128 KB trim threshold is parked in the ledger for aj to confirm.

## The issue numbers
Parent #625; steps #626 (timing script), #627 (load less), #628 (one process per phase), #629 (label reads), #630 (append-only log), #631 (easy test wins).
