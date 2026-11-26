# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Quiet unattended mode (plugin 2.95.0) failed aj's QA on the Canada party trial; four fix rounds are in. New this round: the design lock follows a leading `cd DIR &&` so a shell write of a source file cannot slip past it, and `overnight.sh` takes `HOUSE_RULES_OVERNIGHT_RESUME=<session id>` to continue a killed run. Earlier rounds: pictures check accepts `round-N/` and ignores plan-page pictures, finish checks fall back to local `main`, the launcher turns a leftover `HOUSE_RULES_LOOP=off` on and resumes while the stage is before Build. Suites pass: design_loop 562, tools 72, make_page 124, core 281, safe_git 313, docs 176, writing 24. Trial 4 runs in `/home/user/canada-trial4` (log `/home/user/canada-trial4.log`); trial 3 was killed by a container restart.

## The next step
Read trial 4: stage file, step list, ledger, then run `finish_checks.py docs|pictures|tests|qa throw-power-meter` inside it. If the run was killed, resume it with `HOUSE_RULES_OVERNIGHT_RESUME=<its session id>`. Fix what still fails. aj then retries QA.

## What is unverified
Whether a fresh repo reaches a clean finish (trial 4 had not ended); whether a reviewer's repeated rounds stall the Design gate; core and safe_git after the last edit; the bar on a real phone; Unity cannot be run here. Nothing was pushed to the real Canada repo.

## The issue numbers
Parent #634 (Quiet unattended mode: decide, log, and run to QA without stopping). Steps in build order: #638 (Ledger commands: decide, stricter park, choice rows on the QA page), #636 (One test for who is present, and the guards that use it), #637 (Keep the design loop on when nobody is present), #639 (A guarded step list: the file, its hashes and a check field in build plans), #646 (Start and poll step checks, and mark steps stale by the tree fingerprint), #647 (The four finish-line steps and the step list that moves Build to QA), #640 (A stop check on every stop that blocks while a step is open), #641 (Self-approval by a hook, backed by a stored reviewer verdict), #642 (Restart loop: resume by session id, with an interactive flag), #648 (Restart loop: wait out rate limits and back off after crashes), #649 (Restart loop: limits and the final QA pass), #643 (Show decisions only on the QA page), #635 (Rewrite the rule lines that tell me to ask, wait or hand over), #645 (Reversed decisions, systems docs and version bump), #644 (Live headless unattended run and acceptance).

**Update 2026-11-26 (QA failed):** pictures check and `overnight.sh` fixed (suites: tools 70 pass; design_loop run `/home/user/verify-dl.log`). Second Canada trial running in `/home/user/canada-trial2` (log `/home/user/canada-trial2.log`, started with the loop on). Next: read it back, run the four finish checks there, fix what still fails.
