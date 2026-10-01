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
stalls. Scope it to the job: `python scripts/stallcheck.py --watch --threshold 300 --session <session_id>
--agent <agentId>` (the PostToolUse hook prints this command filled in). Without `--session` it watches
every session's subagents on the machine and says so in a header line; that is noise, not a check of
your own work. A stalled row is re-printed every threshold period with its age growing. On a `STALLED` line:
find the agent's last tool call or blocking child process (newest transcript record, process list);
tell the user how long it has been stuck and what it is blocked on; ask before stopping a command that
cannot finish. Do not assume it died, and do not assume it is fine: "no STALLED line since" is not
evidence of progress, and SendMessage (delivered only at the agent's next tool round) cannot reach an
agent blocked inside a tool call.

**Every wait has a time limit and says why it gave up** (`timeout 900 bash -c '...'`, or a loop with a
counter that prints why it stopped). Never `until`/`while ... sleep` without one. The harness's
completion notice beats polling.

**Why:** a test the user cannot observe is not a test - it is me asserting a result, which is exactly the
thing they are trying to verify. What changed on 2026-10-01: background tools now exist that the user can
follow, so "nothing in the background" is no longer the right line; "nothing the user cannot see, reach
or read" is.
