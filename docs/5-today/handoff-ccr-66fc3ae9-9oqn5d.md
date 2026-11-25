# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Build stage (aj approved the build plan, "Build plan approved: quiet unattended mode"). No source change is merged yet. Two builders were running in their own worktrees: step 1 (#638, ledger commands) and step 2 (#636, one presence test). The decisions log has this stage's entry. Main has no new commits.

## The next step
When the two builders report: review each diff, merge its worktree branch into this branch, run that step's own verify.py segments (each under 60 seconds), add the CHANGELOG.md line myself, then start the next steps in order (3 after 2, 4 after 1, and so on, at most two builders at once). Keep going until all fifteen steps and the four finish-line steps are done.

## What is unverified
The plan's mechanics are read from code, not run: a check as start and poll calls, a failure hook seeing a failed check, the stop-failure payload's reset time (it has no such field), the block cap at 1000, and whether a ninth consecutive stop block holds. Everything is read from code and the Claude Code binary, not run in a live unattended session. Unconfirmed: whether Stop hooks block in a resumed headless run, whether the web app has /goal, whether a tool call resets Claude Code's consecutive-block count, the pause-goal tool's exact name, and whether settings env reaches a resumed session.

## The issue numbers
Parent #634 (Quiet unattended mode: decide, log, and run to QA without stopping). Steps in build order: #638 (Ledger commands: decide, stricter park, choice rows on the QA page), #636 (One test for who is present, and the guards that use it), #637 (Keep the design loop on when nobody is present), #639 (A guarded step list: the file, its hashes and a check field in build plans), #646 (Start and poll step checks, and mark steps stale by the tree fingerprint), #647 (The four finish-line steps and the step list that moves Build to QA), #640 (A stop check on every stop that blocks while a step is open), #641 (Self-approval by a hook, backed by a stored reviewer verdict), #642 (Restart loop: resume by session id, with an interactive flag), #648 (Restart loop: wait out rate limits and back off after crashes), #649 (Restart loop: limits and the final QA pass), #643 (Show decisions only on the QA page), #635 (Rewrite the rule lines that tell me to ask, wait or hand over), #645 (Reversed decisions, systems docs and version bump), #644 (Live headless unattended run and acceptance).
