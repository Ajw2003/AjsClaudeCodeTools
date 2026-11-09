# Usage handoff (planned)

How a session's work stays saved and handed off, so a usage limit, a closed window or a switch of
Claude account never strands it, and the next session carries on from where the last one stopped.

Issue #406 ("Keep work saved and handed off on every reply, so a usage limit never strands it"),
which replaces #140. Two approved designs make it up (`docs/6-decisions/Decisions.md`, 2026-11-08):
the October design (`docs/plans/2026-10-27-usage-limit-handoff-revised.html` on the branch
`AjsAgent/issue-281-fix`, "Design approved: usage limit handoff 1A 2A 3A"), and the session handoff
design (`docs/plans/2026-11-08-session-handoff-design.html`, 1A 2A 3A), combined by
`docs/plans/2026-11-08-session-handoff-vs-406.html` (1A). Where the two differ, the November picks win.

## What it owns

- **The automatic save.** `event_autosave` (`scripts/house_rules/delegation.py`) today saves only
  subagent branches (`worktree-agent-*`). It is widened to every branch the main session edits on.
- **The facts file.** Written by a hook into each snapshot, never into the working folder.
- **The save check.** A row of the end-of-reply (`Stop`) dispatcher, `event_handover` in
  `scripts/hook.py`, beside the existing commit check.
- **The handoff note.** `docs/5-today/handoff-<branch>.md`, one per branch, `/` replaced by `-`,
  written and committed by the agent.
- **The pickup.** A `SessionStart` block that fetches the snapshots and shows the note and facts.

## Why it doesn't wait for a usage percentage

No hook input carries usage on any surface, and the status line that does is not available to a
plugin (tested 2026-10-27; the table is in the October design). The hooks reference lists a
`StopFailure` event whose matcher includes `rate_limit`, so a turn that ends on the limit can still
be saved after the fact. Whether `Stop` itself runs in that case is not documented. So the design
saves continuously and does not depend on either.

## How it works

**The automatic save (November pick 1A).** After a `Write`, `Edit`, `NotebookEdit` or `Bash` call, at
most once a minute (`AUTOSAVE_PUSH_INTERVAL`, 60 s), the working folder is snapshotted to
`refs/house-rules/autosave/<branch>` through a temporary index and pushed to `origin`. The branch,
its index and its working tree are never changed. What goes into the snapshot follows #477: tracked
changes, plus new files the agent wrote with `Write`, `Edit` or `NotebookEdit`. Other new files stay
out, because one may be a token or a data dump. On the main session's branches the hook makes no
work-in-progress commit; that stays for subagent branches only. The end of a turn (`Stop`) and a turn
ended by an API error (`StopFailure`) force one save and push regardless of the one-minute window.

**The facts file (November pick 2A).** Each snapshot carries `.house-rules/handoff-facts.md`, written
into the temporary index only: the branch, the commit the snapshot sits on, unpushed commits, files
changed but not committed, the design-loop feature and stage, the issues the stage file lists with
their labels, and the time. It lives only in the snapshot, so it never dirties the working folder or
trips the commit check.

**The save check (October design).** It runs only when the turn wrote files or made a commit
(`handover_turn_writes`). It sends the reply back once when a file the turn wrote is uncommitted (the
existing `handover_commit_check`), the branch is not pushed, the handoff note is older than the
branch's newest commit, the note carries a published page link, a session link or Claude credit, or
`docs/5-today/Today.md` was not touched by a turn that changed other files. A git command that fails
is reported as "could not tell". `HOUSE_RULES_HANDOFF=off` turns the check off.

**The note.** Five short sections written by the agent: what the work is for, where it stands, the
next step, what is unverified, and the issue numbers.

**The pickup (November pick 3A).** At session start, with a 5-second timeout, the hook fetches
`refs/house-rules/autosave/*` from `origin`. It shows the current branch's note and the facts from
its newest snapshot. When the snapshot holds changes that the working folder lacks, it lists those
files and the command that restores them, and says to ask aj first; nothing is restored by the hook.
Other branches with a snapshot newer than a day are named in one line. Output is capped so a large
note can't crowd the context.

## Invariants

- Nothing is ever committed on `main` or on aj's branches by this system.
- The hook never restores files on its own.
- Every failure (no `origin`, a push that times out, a fetch that fails) is said in one line.

## Traps that have already cost time

- 2026-11-08: a session opened on `AjsAgent/issue-281-fix`, 367 commits behind `main`, and planned
  from stale files. The pickup's fetch is the guard against that; the facts file names the commit a
  snapshot sits on so a stale folder shows.
