# Hook message log

**Owns:** where the plugin's informational hook messages go (a log file, not the chat), how to read
them, and the autosave scratch-file fix. Status: design approved 2026-11-23 as "Design approved:
quieter hook messages 1* 2A"; aj's own answer to choice 1 was "hide all messages, expandable like tool
output". Claude Code documents no expandable hook message (https://code.claude.com/docs/en/hooks, read
through a helper, so wording unchecked), so aj chose option A: silent by default, plus a log and a command
to read it. Built in plugin 2.90.0 (#583 to #586; the autosave scratch file is `house-rules-autosave-<branch>.index.<pid>`, and `_autosave_error` in `delegation.py` says an error once per session id). The log command is `scripts/hooklog.py`, called with `python`. Page: `docs/plans/2026-11-23-debug-log-spam/proposal.html`.

## What changes

| Message kind | Today | After |
|---|---|---|
| `trace()` and `trace_noop()` (22 `trace()` calls: "looked, nothing to do", "saved", "could not tell") | printed in chat (`core.py:91`) | written to the log, nothing in chat |
| Autosave notes and error (`delegation.py:1548-1567`) | printed in chat on every call; the error is several lines | the notes go to the log; a real error prints once per session as one line |
| Refusals, reminders and instructions to the model (the other `systemMessage` uses) | printed | **unchanged**: they are decisions or instructions, not status |

`HOUSE_RULES_TRACE=chat` restores the old behaviour (everything in chat); `off` still drops everything.

## The log

- One file in the temp folder, `house-rules-hook-log.txt`, one line per message with time and handler,
  capped at 500 lines (oldest dropped).
- `/house-rules:hook-log [N]` prints the last N lines (default 30). It is the expand-on-demand.
- A failure to write the log is itself one chat line, once per session, so nothing fails silently.

## Autosave collision (choice 2A)

`_autosave_state_path` (`delegation.py:1245`) builds the scratch index name from the branch only. Two
overlapping calls share it and collide on git's `.lock`. The name gains the process number. The
error handler (`delegation.py:1565`) sends the first line of the error only, once per session.

## Build plan

| Step | Depends on | Done when |
|---|---|---|
| 1. Log, `trace` routing, `HOUSE_RULES_TRACE=chat`, `/house-rules:hook-log` | nothing | a `verify.py` case shows a trace lands in the log and not in stdout, and `chat` prints it |
| 2. Autosave: unique scratch file, one-line error once per session, notes to the log | 1 | a case runs two autosaves at once with no error; the error case prints once |
| 3. Docs, changelog, version | 1, 2 | `verify.py`, `verify_tools.py`, `docref.py check`, `docs_drift.py` exit 0; version-bump check passes |
