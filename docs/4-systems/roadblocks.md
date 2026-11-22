# Roadblocks

**Owns:** the rule that the agent checks a roadblock claim before making it, installs missing tools
itself, and tries other routes before stopping, plus the end-of-reply check that enforces it.
Status: built in plugin 2.88.0. Parent issue #569; steps #570 (rule text), #571 (the check), #572
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
2. **Check.** `roadblock_check` (`scripts/house_rules/core.py:3451`), called from `event_handover` in
   `scripts/hook.py:135` right after `handover_evidence_check`; a block is emitted at once and the
   later checks do not run that reply.
   - **Phrases flagged** (`core.py:3390`, case-insensitive, not inside quotes): "I can't", "I cannot",
     "is/isn't/are/aren't/not installed", "not on your machine", "no access to", "you need/have to install".
   - **Probe or install** (`core.py:3395-3399`, `3411-3423`): a `Bash` command this turn containing
     `which`, `ls`, `uname`, `hostname`, `where`, `command -v`, or `apt`, `apt-get`, `pip`, `pip3`,
     `npm`, `brew`, `winget`, `choco`; or a tool named `list_computer_folders` or
     `request_computer_folder`. Any one clears the reply.
   - **Block count** (`core.py:3470-3488`): no probe means block, up to `ROADBLOCK_BLOCKS = 2`
     (`core.py:3400`) per user message; the third time the reply goes out with a visible
     "a roadblock claim (...) went out unchecked" line. The block reason names the rule file and the
     probe to run.
   - **State file** (`core.py:3435-3440`): `house-rules-roadblocks-<sha1 of transcript path, 16
     chars>.json` in the temp directory, holding `{"key": "<transcript path>|<user-message count>",
     "count": n}` (`core.py:3426-3432`, `3472`). A new user message changes the key, so the count restarts.
   - **Fail-open** (`core.py:3459-3464`, `3482-3484`): no `transcript_path`, an unreadable transcript, or a
     state file that cannot be read or written gives a `house-rules: roadblock check could not ...`
     message and never blocks. On the `stop_hook_active` retry it only warns and does not count
     (`core.py:3468`, #256).
   - **Off-switches:** `HOUSE_RULES_ROADBLOCKS=off` (`core.py:3403`) turns the check off;
     `HOUSE_RULES_ROADBLOCKS_STATE=<path>` (`core.py:3436`) moves the state file (the checks use it).
   - **Tests:** cases 101 to 109 in `scripts/checks/core.py:1188-1243`: blocks 1 and 2, warning on
     the third, no block after which/ls/pip, new message resets, unusable state file, retry, off-switch.
   - **Case 91 changed:** its example reason (`checks/core.py:1113`) was a missing editor; it is now a
     four-hour suite, because a missing-tool reason is exactly what this check blocks.
