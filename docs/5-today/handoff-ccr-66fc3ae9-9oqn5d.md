# Handoff: quiet unattended mode

## What the work is for
aj wants unattended mode to keep the design loop on and run it without them: decide, log decisions, work numbered steps to the end, and never stop part-way in any mode. Anything that truly needs aj is left for the QA page. aj is asked about look or function choices only when present; in unattended those are decided too, with a stated assumption shown on the QA page. Bypass counts as unattended. Auto stays attended (the loop still gates every step) but gets every other decision-cutting change. Every step list in every mode ends with four required steps (tests, docs, before-and-after pictures, QA page) that cannot be parked or skipped.

## Where it stands
Quiet unattended mode (plugin 2.95.0) failed aj's QA on the Canada party trial; five fix rounds are in and pushed. Latest: `steps-status` counts a feature as open (Design) when a QA ledger exists even with no stage file, because a fresh repo has no stage file until a reviewer verdict is stored and the launcher had read the run as finished. Earlier: the design lock follows a leading `cd`; `overnight.sh` resumes a killed run by `HOUSE_RULES_OVERNIGHT_RESUME`; pictures check accepts `round-N/`; finish checks fall back to local `main`. Suites: tools 73, design_loop 562, make_page 124, core 281, safe_git 313, docs 176, writing 24. Trial 4 (`/home/user/canada-trial4`) is resumed by session id; log `/home/user/canada-trial4b.log`.

## The next step
Read trial 4: stage file, step list, ledger, then run `finish_checks.py docs|pictures|tests|qa power-meter` inside it. If it was killed again, resume with `HOUSE_RULES_OVERNIGHT_RESUME=<session id>`. Fix what still fails. aj then retries QA.

## What is unverified
Whether a fresh repo reaches a clean finish (trial 4 was still running); whether a reviewer's repeated rounds stall the Design gate; the bar on a real phone; Unity cannot be run here. Nothing was pushed to the real Canada repo.

## The issue numbers
Parent #634 (Quiet unattended mode: decide, log, and run to QA without stopping). Steps in build order: #638 (Ledger commands: decide, stricter park, choice rows on the QA page), #636 (One test for who is present, and the guards that use it), #637 (Keep the design loop on when nobody is present), #639 (A guarded step list: the file, its hashes and a check field in build plans), #646 (Start and poll step checks, and mark steps stale by the tree fingerprint), #647 (The four finish-line steps and the step list that moves Build to QA), #640 (A stop check on every stop that blocks while a step is open), #641 (Self-approval by a hook, backed by a stored reviewer verdict), #642 (Restart loop: resume by session id, with an interactive flag), #648 (Restart loop: wait out rate limits and back off after crashes), #649 (Restart loop: limits and the final QA pass), #643 (Show decisions only on the QA page), #635 (Rewrite the rule lines that tell me to ask, wait or hand over), #645 (Reversed decisions, systems docs and version bump), #644 (Live headless unattended run and acceptance).

**Update 2026-11-26 (QA failed):** pictures check and `overnight.sh` fixed (suites: tools 70 pass; design_loop run `/home/user/verify-dl.log`). Second Canada trial running in `/home/user/canada-trial2` (log `/home/user/canada-trial2.log`, started with the loop on). Next: read it back, run the four finish checks there, fix what still fails.
