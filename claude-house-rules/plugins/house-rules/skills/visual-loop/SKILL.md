---
name: visual-loop
description: Check, critique and fix visual work in a loop with nobody in the middle. Use for any change to
  how something looks or moves (a page, a screen, an animation). Written criteria, screenshots, a separate
  reviewer helper who looks at the images, a builder who fixes what failed, at most 4 rounds. Never asks aj
  mid-loop.
---

# Visual loop

Feature folder: `docs/qa/<feature>/` (pattern and round cap are in `rules/visual.json`, `max_rounds` is 4).
Tools: `scripts/visualcheck.py` (capture), `scripts/ledger.py` (the written record), `scripts/waitfor.py` (every wait).

1. **Criteria first.** From the approved page, write `docs/qa/<feature>/criteria.md` BEFORE building. One line each:
   `C1. <what must be true> | proof: <still|flow|video|frames> | page: <path or url>`.
   `still` = one screenshot, `flow` = screenshots after steps, `video` = a recording, `frames` = a contact sheet of a video (motion).
2. **Build** the change.
3. **Doctor.** Run `python3 scripts/visualcheck.py doctor`. It never installs anything. If something is missing, say what
   (it prints the line) and list it in the final summary as unverified; do not stop to ask.
4. **Capture** into `docs/qa/<feature>/round-N/`: `visualcheck.py shots --steps FILE --out DIR` for still and flow,
   `video` for video, then `frames --video FILE --out DIR` for frames. Each run writes `report.json`.
5. **New round.** `python3 scripts/ledger.py new-round docs/qa/<feature>` writes `round-N.md` with every criterion marked FAIL, not yet judged.
6. **Reviewer.** Spawn ONE helper at a time: `@house-rules:reviewer` (subagent_type `house-rules:reviewer`). Prompt, filled in:

   > You are the reviewer for the visual loop, round N of feature <feature>. Criteria: <path to criteria.md>.
   > Images: <every image path>. Report: <path to report.json>. Use the Read tool to look at EVERY image, one by one.
   > Do not fix anything and do not trust anyone's claim that it looks right; judge with fresh eyes against the criteria only.
   > For EVERY criterion write exactly one line: `C<n>: PASS|FAIL - <what the image actually shows, in plain words> - <image path>`
   > using an image that exists. Then the last line `STATUS: pass` only if all are PASS, else `STATUS: fail`.
   > Put these lines in your reply, with the `# Round N` header, ready to be saved as the round file.

   The reviewer helper has no write tool, so save its reply as `round-N.md` yourself, unchanged, replacing the skeleton.
7. **Check.** `ledger.py check docs/qa/<feature>` (fix the file if it names a problem, never the verdict) then
   `ledger.py status docs/qa/<feature>`:
   - `NEXT: fix`: hand the failing criteria, with the reviewer's own words, to `@house-rules:builder`; recapture; go to step 5.
   - `NEXT: done`: finish.
   - `NEXT: blocked`: write `docs/qa/<feature>/blocked.md` listing what still fails and why; finish WITHOUT asking aj.
8. **Waits.** Every wait (captures, helpers) goes through `scripts/waitfor.py`, with the deadline for its kind from
   `rules/waits.json` (`deadline_seconds`: command 600, agent 900, build 1200). At a deadline or stall, record it and carry on.
9. **Never stop to ask aj.** Only the final summary says what is left: failing criteria, blocked.md, missing tools.

## Whole-feature acceptance
Same loop, widened to a whole feature before QA. Criteria come from the "Acceptance tests" item of the approved build plan page,
one criterion per design item. Add proof type `run` for a feature with no screen: `python3 scripts/acceptance.py run --out
docs/qa/<feature>/round-N -- <command...>` saves output and exit code to `run-N.txt`, a text file the reviewer Reads like an image.
Spawn the reviewer in ACCEPTANCE mode (`@house-rules:reviewer`, see `rules/detail/review-modes.md`); it may write only under
`docs/qa/<feature>/`. On `NEXT: done` run `python3 scripts/acceptance.py stamp docs/qa/<feature>`. On blocked write `blocked.md`
and carry on; never ask aj.

## Limits, plainly
- A model can miss things in its own work; that is why a separate reviewer judges, but the reviewer can miss things too.
- Contact sheets sample frames; motion between two sampled frames is not seen.
- `ledger.py check` proves the record is complete and consistent, not that the verdicts are right.
