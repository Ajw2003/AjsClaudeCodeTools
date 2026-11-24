# Review loop

## What it owns

Making a design and a build plan trustworthy before aj sees them, proving a finished feature works before aj is asked to judge it, and keeping routine work moving by parking questions and logging deviations instead of stopping. It sits on top of the design loop (`design-loop.md`). Issue #592; design page `docs/plans/2026-11-24-design-review-loop.html`; build plan page `docs/plans/2026-11-24-design-review-loop-plan.html`.

**Status: built (plugin 2.92.0).** Steps #593 to #600 are built and #601 closes the docs. The acceptance run of the whole feature and aj's QA are the remaining checks.

## How it works

| Piece | Built by | What it does |
|---|---|---|
| Reviewer helper | #593 | `agents/reviewer.md` has eight modes: page, plan, acceptance and diff, plus code (a named file or folder), codebase (one batch of files from a repo), image (a picture judged against stated criteria) and style (a picture or page compared with a stated style). The last four are reached through the `/house-rules:review` command (`review-command.md`). Page mode hunts for holes, traps, contradictions, reversals and open questions, then checks wording. A fact it can look up it answers; a real design choice becomes a lettered option with a suggestion. Writes only under `docs/`. |
| Review stamp | #594 | The page builder records a content fingerprint and the verdict. A reply linking an unstamped or stale page is sent back once. At most two rounds; leftovers are shown as open risks. Review and QA pages are exempt. |
| Acceptance run | #595 | Reviewer runs and screenshots the whole feature against the acceptance list the build plan carries, reusing the visual loop (four rounds, never asks aj). `scripts/acceptance.py stamp` writes `docs/qa/<feature>/acceptance-stamp.json`, tied to a fingerprint of the source tree (not the commit), and `check` says current or stale (deviations D3 and D5, parked decisions P3 and P4). |
| QA gate | #596 | QA mode refuses without a current acceptance stamp, accepts an empty unverified list, and opens with the ledger. |
| Self-judging test | #597 | The fallback when this machine genuinely cannot test something: one test that decides pass or fail itself, handed over as one command. |
| Parked questions | #598 | Built. In Build with someone present, a plain question is refused and parked with `ledger_note.py park`; only a `[HARD STOP]` question is asked and held. See "Parked questions" below. |
| Deviations ledger | #599 | Built. `ledger_note.py deviate` logs what the plan said, what was done, why and how to undo it; a change to what aj approved is parked instead. With nobody present (unattended or bypass mode), a reply that admits a departure with no `ledger_note.py` call that turn is sent back once by the `deviation` checkpoint in `design_loop.py` (`_check_deviation`). The phrase list is a heuristic; an unknown permission mode counts as attended. |
| Combined approval | #600 | One message holding "Design approved" and "Build plan approved" moves Design to Build, but only when a `-plan.html` page naming the feature in `docs/plans/` carries a current review stamp (`_plan_unreviewed` in `design_loop.py`). Otherwise the design half applies, the plan half is refused with the reason, and the plan is approved in its own message. A plan approval on its own is not held to the stamp (speed switches 6A). |

## Invariants it must keep

- Only aj's message moves a stage. Stamps and the ledger are written by hooks or by the agent, never by aj's words being guessed.
- Irreversible steps, and anything touching money, secrets, other people, outward posts or deleted data, never run on a guess in any mode.
- A session whose permission mode is unknown is treated as attended.
- The injected rules text has a size limit; any new rule line must make room (see `docs/5-today/Today.md`, 2026-11-22).

## Known unknowns

- The `bypassPermissions` value was read from Claude Code's mode list, not seen live (`roadblocks.md`, 2.90.0 notes).
- Opus review cost per page is unmeasured. The two-round cap is an estimate.

## Parked questions (design review loop, #598)

`scripts/ledger_note.py park <feature> --step S --question Q --default D --affects A [--answer HOW]` appends row P<n> (one more than the highest P in the file) to the Parked decisions table of `docs/qa/<folder>/ledger.md`, creating the file with its two tables if absent; the folder rule is `make_page.qa_folder`. `|` and newlines in a cell are escaped (the QA page parser, `make_page.py`, splits cells only on an unescaped `|` and shows `\|` as `|`). The rule in `rules/show-dont-tell.md` and the helper start note (`_loop_helper_note`) tell the agent to park a reversible question and carry on; a [HARD STOP] (cannot be undone, or touches money, secrets or other people) is still asked. Built (#598): in Build with someone present, `event_noask` (`core.py`, reading the stage through `design_loop._noask_stage`) denies an `AskUserQuestion` unless a question or header contains `[HARD STOP]`, and the deny reason names `ledger_note.py park`; unattended and bypassPermissions runs are still denied, and the reason now names it too. `ExitPlanMode` and every other stage are untouched. The Build question hold (`held`) now sets only for a last paragraph containing `[HARD STOP]`; a plain question adds a non-blocking park note, and the `decided for you` row stays quiet in Build when the reply mentions the ledger.
