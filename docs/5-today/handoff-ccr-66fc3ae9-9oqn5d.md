# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Design approved by aj ("Design approved: quiet unattended mode 1A"); stage is Plan, no code changed. The fifteen-step build plan page `docs/plans/2026-11-25-quiet-unattended-mode-plan.html` has had two plan-mode review rounds (29 findings, then 30); every finding is applied or decided on the page, and the page is stamped open risks, round 2. The systems doc and issues #634 to #649 match it.

## The next step
Wait for aj's line "Build plan approved: quiet unattended mode". Then merge main, re-check the line numbers, and build the fifteen steps in order, running each step's own verify.py command as segments under 60 seconds.

## What is unverified
The plan's mechanics are read from code, not run: a check as start and poll calls, a failure hook seeing a failed check, the stop-failure payload's reset time (it has no such field), the block cap at 1000, and whether a ninth consecutive stop block holds. Everything is read from code and the Claude Code binary, not run in a live unattended session. Unconfirmed: whether Stop hooks block in a resumed headless run, whether the web app has /goal, whether a tool call resets Claude Code's consecutive-block count, the pause-goal tool's exact name, and whether settings env reaches a resumed session.

## The issue numbers
Parent #634 (Quiet unattended mode: decide, log, and run to QA without stopping). Steps in build order: #638 (Ledger commands: decide, stricter park, choice rows on the QA page), #636 (One test for who is present, and the guards that use it), #637 (Keep the design loop on when nobody is present), #639 (A guarded step list: the file, its hashes and a check field in build plans), #646 (Start and poll step checks, and mark steps stale by the tree fingerprint), #647 (The four finish-line steps and the step list that moves Build to QA), #640 (A stop check on every stop that blocks while a step is open), #641 (Self-approval by a hook, backed by a stored reviewer verdict), #642 (Restart loop: resume by session id, with an interactive flag), #648 (Restart loop: wait out rate limits and back off after crashes), #649 (Restart loop: limits and the final QA pass), #643 (Show decisions only on the QA page), #635 (Rewrite the rule lines that tell me to ask, wait or hand over), #645 (Reversed decisions, systems docs and version bump), #644 (Live headless unattended run and acceptance).
