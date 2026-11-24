# Roadblock judge friction seen on 2026-11-24

aj noted that the roadblock judge looks over-zealous: it flags things it should not, and the repeated calls may be using up usage for no gain. The judge is the model-judged Stop check described in `docs/4-systems/roadblocks.md`. This file records what was seen in one session so a later session can measure it and decide. Nothing here is fixed or decided; the cost in tokens was not measured.

## What was seen (branch `ccr-1839130d-clohr1`, finishing the design review loop, #592)

1. **It fired on replies that only reported a wait.** About seven times in a row it flagged replies saying a background test run was still going. None claimed something could not be done. Each retry listed "three methods" that only showed the run was in progress, and the judge kept firing because those were not three different ways of getting a result that does not exist yet. A wait is not a roadblock, and the judge has no way to tell the two apart.
2. **It flagged an honest report of a refusal.** "The safety check denied this, so I did not stamp it" was read as a claim of inability and sent back, although it named the attempt and what the refusal said.
3. **It did not pass on the retry.** The retry (`stop_hook_active`) is meant to pass once three different methods are listed, but a wait has no such methods to list, so it blocked again and again.

## What it costs, as far as known

- The judge is a model call on every Stop. The 2026-11-23 test put one call at about $0.002 and 4 to 5 seconds (`docs/5-today/Today.md`); this session's total was not counted. Each block also forces a full extra reply.
- All three cases above are repeats on the same state, not new findings.

## Questions for whoever picks this up

- Should the judge pass a reply whose only claim is that a background task or timer is still running?
- Should repeated blocks stop after the first retry that adds no new information, instead of the fixed two?
- Should a report of an automatic refusal count as naming the attempt?

## Seen in the same session, not part of this note

The editor, commit, changelog, handoff and page checkpoints also fired repeatedly on small replies. aj said the judge was the subject, so they are listed here only so they are not lost.
