# Can my work always be split into short visible steps? (measured 2026-10-28)

Question from aj: is there any reason work can't always be split and shown? I had answered "almost
all of it can" from judgement. This file is the measurement behind a corrected answer.

## Sources and what each can measure

| Source | Per-call timings? | Used for |
|---|---|---|
| This session's transcript (38 tool calls) | Yes, tool_use to tool_result timestamps | Exact call lengths, via `2026-10-28-call_durations.py` |
| `docs/sessions/2026-09-09-4e371a18-...md` (169 commands) | No: only turn start times | Nothing; it cannot answer this |
| Timings recorded in the docs | Per job, not per call | Which long jobs exist, and whether they split |

Only this session's transcript exists in this container, so there is no wider sample of my calls.

## Results

This session (planning and pages): 0 of 38 calls ran over 30 seconds; the longest were the two
editor helpers, 22.2 s and 19.3 s.

Long jobs on record, and whether each splits:

| Job | Recorded length | Splits into short steps? |
|---|---|---|
| Full `verify.py`, serial | 130 to 197 s (`docs/4-systems/verify-suites.md:125`, `:651`) | Yes: `--parts` runs one part at a time; the longest part is about 32 s (`verify-suites.md:227`) |
| Full `verify.py`, parallel | 35 to 41 s (`docs/3-state/ProjectState.md:226`) | Already short; but its output file is quiet until a part ends (seen in this session), so a check must also count its processes |
| A builder helper | 32 minutes (`docs/6-decisions/Decisions.md`, entry 2026-10-01) | Into issues, yes (a builder takes at most three steps); but the helper's own steps never show in the thread while it runs |
| Unity builds and wait loops (#138, #139) | Not recorded here; those projects are not in this container | Unknown. A single compile cannot be cut up; it can only run in the background with short checks |

## Answer

Not proven as "almost all". What the record shows: the long jobs here are a full test run, which
does split, and helper agents, which split into issues but stay unseen inside each one. A single
compile or install cannot split; it can only be watched in short checks. The ratio across real
building sessions is unmeasured, because no such transcript with per-call timings exists here.
