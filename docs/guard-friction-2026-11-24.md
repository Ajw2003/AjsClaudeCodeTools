# Guard friction seen on 2026-11-24

aj noted that the guards look over-zealous: they flag things they should not, and the repeated checks may be using up usage for no gain. This file records what was seen in one session so a later session can measure it and decide. Nothing here is fixed or decided; the cost in tokens was not measured.

## What was seen (branch `ccr-1839130d-clohr1`, finishing the design review loop, #592)

1. **The roadblock judge fired on a reply that only reported a wait.** The model-judged Stop check (`roadblocks.md`, 2.90.0) fired about seven times in a row on replies that said a background test run was still going. None claimed something could not be done. Each retry listed "three methods" that only showed the run was in progress, and the check kept firing because those were not three different ways of getting a result that does not exist yet. A wait is not a roadblock; the check has no way to tell the two apart.
2. **The roadblock check flagged an honest report.** "The safety check denied this, so I did not stamp it" was read as a claim of inability and sent back, although it named the attempt and the refusal.
3. **The editor checkpoint asked for a helper the design replaces.** After the reviewer helper had read and word-checked a plan page, the installed 2.91.0 hook still demanded `@house-rules:editor` before the reply could end.
4. **The commit, changelog and handoff checkpoints re-fire on every small reply.** A one-line status reply after a pushed commit was blocked again for a changelog line and a new handoff note, each time the turn wrote a file.
5. **The page checkpoint flagged short decision questions.** Replies of 234 and 249 words were reported as needing a page although each was a single question with options.
6. **Auto-mode refusals stacked on top.** Hand-writing a round file and running the acceptance runner on saved output were both denied. That was right once, but the second attempt was a reasonable-looking route that cost another turn to learn the same thing.

## What it costs, as far as known

- The judge is a model call on every Stop. The 2026-11-23 test put one call at about $0.002 and 4 to 5 seconds (`docs/5-today/Today.md`); this session's total was not counted. Repeated blocks also add a full extra reply each time.
- Five of the six cases above are repeats of an earlier flag on the same state, not new findings.

## Questions for whoever picks this up

- Should the roadblock judge skip a reply whose only claim is that a background task or timer is still running?
- Should a block count stop after the first retry that adds no new information, instead of the fixed two?
- Should the changelog and handoff checkpoints fire once per task and not once per reply?
- Should the page checkpoint skip a reply that is one question with options?

Related: `docs/guard-friction-audit-2026-10-15.md`, `docs/4-systems/roadblocks.md`.
