# Review loop

## What it owns

Making a design and a build plan trustworthy before aj sees them, proving a finished feature works before aj is asked to judge it, and keeping routine work moving by parking questions and logging deviations instead of stopping. It sits on top of the design loop (`design-loop.md`). Issue #592; design page `docs/plans/2026-11-24-design-review-loop.html`; build plan page `docs/plans/2026-11-24-design-review-loop-plan.html`.

**Status: planned, nothing built.** Each section below says what will be built and which issue builds it. This page is rewritten as built when each step lands.

## How it will work

| Piece | Built by | What it does |
|---|---|---|
| Reviewer helper | #593 | `agents/reviewer.md` gains page, plan and acceptance modes. Page mode hunts for holes, traps, contradictions, reversals and open questions, then checks wording. A fact it can look up it answers; a real design choice becomes a lettered option with a suggestion. Writes only under `docs/`. |
| Review stamp | #594 | The page builder records a content fingerprint and the verdict. A reply linking an unstamped or stale page is sent back once. At most two rounds; leftovers are shown as open risks. Review and QA pages are exempt. |
| Acceptance run | #595 | Reviewer runs and screenshots the whole feature against the acceptance list the build plan carries, reusing the visual loop (four rounds, never asks aj). `scripts/acceptance.py stamp` writes `docs/qa/<feature>/acceptance-stamp.json`, tied to a fingerprint of the source tree (not the commit), and `check` says current or stale (deviations D3 and D5, parked decisions P3 and P4). |
| QA gate | #596 | QA mode refuses without a current acceptance stamp, accepts an empty unverified list, and opens with the ledger. |
| Self-judging test | #597 | The fallback when this machine genuinely cannot test something: one test that decides pass or fail itself, handed over as one command. |
| Parked questions | #598 | First half built (see "Parked questions" below): the script, the rule text and the helper note. The hooks that stop asking in Build are not built yet. |
| Deviations ledger | #599 | In unattended or bypass mode, every departure from the plan is logged in the same ledger file. Intent changes park that piece only. |
| Combined approval | #600 | One approval line moves Design to Build when the reviewed plan is present. |

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
