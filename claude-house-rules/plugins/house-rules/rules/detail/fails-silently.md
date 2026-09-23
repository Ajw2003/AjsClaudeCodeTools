# Nothing fails silently


Silence means one thing only: **I looked, and there was nothing to do.** Anything that means *I
could not tell* says so out loud, naming what it could not do and why.

- A caught exception that produces no output is a bug, not a safeguard. `except: pass` is never
  the answer; if there is genuinely nothing to say, there was nothing to catch.
- Failing loudly is not the same as failing closed. A check that must not obstruct still
  announces that it did not run.
- A diagnostic channel that ships switched off does not count. Nobody enables it until they are
  already lost, so the **default** output has to answer "did this run, on what, and what did it
  decide". A verbose flag sits on top of that, not in place of it.
- Degrading quietly is something a shipped system can earn deliberately, once, and write down.
  It is never the default, and never in something still being built — the phase where a silent
  failure costs the most is exactly the phase where it is cheapest to add one.

**Why:** whoever debugs this next — a person or an agent — has only the output to go on. A path
that produces nothing is indistinguishable from a path that was never reached, and telling those
two apart is the difference between a five-minute fix and an afternoon.

