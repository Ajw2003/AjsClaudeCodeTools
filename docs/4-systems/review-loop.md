# Review loop

## What it owns

Making a design and a build plan trustworthy before aj sees them, proving a finished feature works before aj is asked to judge it, and keeping routine work moving by parking questions and logging deviations instead of stopping. It sits on top of the design loop (`design-loop.md`). Issue #592; design page `docs/plans/2026-11-24-design-review-loop.html`; build plan page `docs/plans/2026-11-24-design-review-loop-plan.html`.

**Status: planned, nothing built.** Each section below says what will be built and which issue builds it. This page is rewritten as built when each step lands.

## How it will work

| Piece | Built by | What it does |
|---|---|---|
| Reviewer helper | #593 | `agents/reviewer.md` gains page, plan and acceptance modes. Page mode hunts for holes, traps, contradictions, reversals and open questions, then checks wording. A fact it can look up it answers; a real design choice becomes a lettered option with a suggestion. Writes only under `docs/`. |
| Review stamp | #594 | The page builder records a content fingerprint and the verdict. A reply linking an unstamped or stale page is sent back once. At most two rounds; leftovers are shown as open risks. Review and QA pages are exempt. |
| Acceptance run | #595 | Reviewer runs and screenshots the whole feature against the acceptance list the build plan carries, reusing the visual loop (four rounds, never asks aj). A hook records the stamp for the current commit in the stage file. |
| QA gate | #596 | QA mode refuses without a current acceptance stamp, accepts an empty unverified list, and opens with the ledger. |
| Self-judging test | #597 | The fallback when this machine genuinely cannot test something: one test that decides pass or fail itself, handed over as one command. |
| Parked questions | #598 | Reversible questions take the safest default, go in `docs/qa/<feature>/ledger.md` with how to undo them, and work continues. Extends the `noask` hook from 2.90.0. |
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
