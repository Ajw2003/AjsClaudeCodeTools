# Never hide work: it stays visible, reachable and readable


Work is never hidden, unreachable or unreadable. The test is the user's, on their phone: if they
cannot see what is being done, cannot reliably check in on a long task, or cannot audit what it did,
the rule is broken.

**Still banned:** `-WindowStyle Hidden`, detached `Start-Process`, `nohup`/`setsid`/`disown`, a trailing
`&`, and any spawn whose output only lands in a log I read back. "It's running, I'll check on it" is not a
substitute for them being able to watch it run.

**Allowed, because the user can follow it:** a subagent (its transcript is readable and the session
lists it), a Monitor watch, `run_in_background` (the task list shows it and its output file is readable),
each with a short description saying what it is. Short work runs foreground, printing live.

**Every background job is checked for stalls every 5 minutes** with `scripts/stallcheck.py`: it compares
the age of the newest write to the job's transcript or output file against 300 seconds and prints
`ok`, `STALLED` or `finished`. Run it under Monitor with `--watch` so it costs nothing until something
stalls. A `STALLED` line is reported to the user with what was looked at and why; it is not assumed to
mean the job died (a long model call or a usage-limit wait also writes nothing).

**Why:** a test the user cannot observe is not a test - it is me asserting a result, which is exactly the
thing they are trying to verify. What changed on 2026-10-01: background tools now exist that the user can
follow, so "nothing in the background" is no longer the right line; "nothing the user cannot see, reach
or read" is.
