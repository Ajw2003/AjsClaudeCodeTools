Part of #406 (Keep work saved and handed off on every reply, so a usage limit never strands it). Design: `docs/plans/2026-11-08-session-handoff-mechanism.html`, step 5, "Also saves".

## What this is

Two new hook entries that save at once, skipping the 60-second wait of the automatic save:

- `Stop`: when a turn ends, the snapshot is rebuilt and pushed, so the last minute of work is never left only on this machine.
- `StopFailure`: when a turn ends on an API error, which the hooks reference lists as including `rate_limit`, the same save runs. This covers a session cut off by a usage limit.
- Both reuse the snapshot code from the automatic save issue; neither commits on any branch. A failure is said in one line.

## Depends on

#486 (Usage handoff step 5: save the working folder automatically on every branch).

## Depended on by

Step 4 (#410), whose real run stops a session mid-turn.

## Done when

`verify.py` replays a `Stop` and a `StopFailure` payload within the 60-second window and finds a fresh snapshot pushed each time. `verify.py` passes twice with no new failures.

Opened by AJ's agent
