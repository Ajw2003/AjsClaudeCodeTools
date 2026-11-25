# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Design approved by aj ("Design approved: quiet unattended mode 1A"); stage is Plan, no code changed. Written: the systems doc `docs/4-systems/quiet-unattended-mode.md`, parent issue #634 with fifteen steps #635 to #649, and the build plan page `docs/plans/2026-11-25-quiet-unattended-mode-plan.html`, rebuilt after a first review found 29 problems. A second plan-mode review round was running when this note was written; the unstamped page was already sent to aj once.

## The next step
Apply the second review's findings, rebuild the build plan page with its review stamp, send it, and wait for aj's line "Build plan approved: quiet unattended mode". Then merge main, re-check line numbers, and build the fifteen steps in order, running the step's own verify.py command after each.

## What is unverified
Everything is read from code and the Claude Code binary, not run in a live unattended session. Unconfirmed: whether Stop hooks block in a resumed headless run, whether the web app has /goal, whether a tool call resets Claude Code's consecutive-block count, the pause-goal tool's exact name, and whether settings env reaches a resumed session.

## The issue numbers
Parent #634 (Quiet unattended mode: decide, log, and run to QA without stopping). Steps: #635 (Rewrite the rule lines that tell me to ask, wait or hand over), #636 (One test for who is present, and the guards that use it), #637 (Keep the design loop on when nobody is present), #638 (Ledger rows for decisions, and rules for parking and deviating), #639 (A guarded step list with four required finish-line steps), #640 (A stop check on every stop that blocks while a step is open), #641 (Self-approval by a hook, backed by a stored reviewer verdict), #642 (A restart loop in the overnight launcher), #643 (Show decisions only on the QA page), #644 (Live headless unattended run and acceptance), #645 (Reversed decisions, systems docs and version bump), #646 (Record step checks and mark steps stale by the tree fingerprint), #647 (The four finish-line steps and the step list that moves Build to QA), #648 (Restart loop: wait out rate limits and back off after crashes), #649 (Restart loop: limits and the final QA pass).
