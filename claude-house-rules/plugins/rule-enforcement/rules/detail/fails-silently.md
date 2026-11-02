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

## Verify a wait, then leave it

I never set a timer, start a wait loop, or leave a background task running until two things are
verified:

1. **The name it waits on is real.** I read the exact identifier it waits on — test class full
   name, process, file, log marker — from the source, and check the watcher's matcher actually
   accepts it.
2. **It is working.** One direct status check shows the task started and the watcher reads that
   status correctly — for example, the verdict script run once against the current status gives
   a sensible answer.

A wait's output streams live. I never pipe a wait loop through `tail` or `head`, which hides
everything until it exits; `guard` prompts when a command does.

**Why:** a test-runner wrapper was called with a bare class name, `CarryFeelTests`, while its
verdict script matched results by full-name prefix, `Plunderspell.Tests.CarryFeelTests…`. It
reported "running" for its whole 10-minute timeout on a run that had finished in 62 seconds, and
the wait was piped through `tail`, so nothing showed until it ended. A wait that can never see its
own completion is a silent failure.
