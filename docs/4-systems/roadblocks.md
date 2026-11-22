# Roadblocks

**Owns:** the rule that the agent checks a roadblock claim before making it, installs missing tools
itself, and tries other routes before stopping, plus the end-of-reply check that enforces it.
Status: designed, not built. Parent issue #569; steps #570 (rule text), #571 (the check), #572
(tests, docs, version). aj approved the design on 2026-11-22 as "Design approved: clear roadblocks
1C 2A" on `docs/plans/2026-11-22-clear-roadblocks.html`.

## Why it exists

A session on aj's PC said it could not go further because Unity was missing and it was on the wrong
machine. Both claims were false, and the session was in bypass permission mode. The existing rules
already say a "can't be done" claim needs a test (`rules/detail/evidence-before-claims.md`) and that
aj's hands are not for labour (`rules/detail/users-hands.md`), but text alone was read and ignored.

## What aj chose

| Question | Choice | Meaning |
|---|---|---|
| How firmly is it enforced? | 1C | A rule plus an end-of-reply check that blocks a roadblock claim twice, then lets the reply through with a visible warning line. |
| What stays aj's? | 2A | Licences, logins, purchases and destructive actions only. |

Dropped from the proposal: a line at session start telling every bypass-mode session that installs
are pre-approved.

## How it will work

1. **Rule.** Probe before claiming (`which`, `ls`, `uname`, `hostname`, `list_computer_folders`);
   install what is missing (without asking in bypass mode, through the normal prompt otherwise);
   try the next route and list every attempt before stopping.
2. **Check.** `handover_evidence_check` in `scripts/house_rules/core.py` already flags impossibility
   claims made with no tool run. The new check also flags roadblock phrases when the only tool run
   was unrelated, and "you need to install" hand-offs. It blocks twice per user message, then
   warns. The count lives in a small state file reset by each new user message; if it cannot be
   read, the check says so in words and does not block. The existing `stop_hook_active` retry
   behaviour (`hook.py`, "#256") is the model: no check may block without end.

## Open design detail

Where the state file lives and how the block count is keyed (session id plus message count) is
decided in step 2 (#571), against how `hook.py` already reads the transcript.
