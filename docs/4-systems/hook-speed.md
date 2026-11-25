# Hook speed

**Owns:** the cost of one tool call in hook time, the timing script that measures it, and the
five changes that lower it. Status: design approved 2026-11-24 as "Design approved: speed first
1A 2A 3A 4*" (see `docs/6-decisions/Decisions.md`); build plan not yet approved. Proposal page:
`docs/plans/speed-first-proposal.html`. Source of the numbers: `docs/qa/review-ajsclaudecodetools-2026-11-24/report.md`
(reviewer measurements, not yet repeated by `tools/time_hooks.py`).

## What aj chose

| Question | Choice |
|---|---|
| Scope | A: all five steps (measure, load less, merge processes, faster label reads, append-only log) |
| Label reads | A: run the 5 reads at the same time; GitHub is still read on every call, so the 2026-10-14 decision stands |
| Reply judge | A: leave it as it is; the timing script times it so the next choice has a number |
| Tests | Own answer: speed up the test suite now where the easy wins are feasible, leave the rest for the code-quality phase. aj's aim: routine work is fast, all of it |

## The six steps

1. **Measure.** `tools/time_hooks.py` replays real Write and Bash hook calls and prints milliseconds per call, plus the label reads and the judge call. Also times each `verify.py` part. Saves a baseline.
2. **Load less.** `hook.py` maps each event to its module and imports only that one.
3. **One process per phase.** One process for all checks before a tool call, one for all checks after. Each check keeps its own failure rule.
4. **Faster label reads.** The commit gate's 5 reads run at the same time.
5. **Append-only log.** The hook log gains one line per write and is trimmed under a lock.
6. **Easy test wins.** Chosen from the step 1 timings of each `verify.py` part; nothing is rewritten.

## What does not change

No check is removed or weakened; `verify.py` passes in full after every step. The known guard
holes stay for the later guard phase. The judge is tuned later, not here.
