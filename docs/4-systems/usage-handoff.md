# Usage handoff (built on `AjsAgent/session-handoff`; being brought to `main` in phase 3)

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

## What was built, where it differs from the plan

Built as #486 (autosave), #487 (save at once on `Stop`/`StopFailure`), #407 (the handoff check),
#408 (the pickup) and #409 (quoted approvals move nothing), merged into `AjsAgent/session-handoff`.
Plugin 2.77.0. The differences:

- The end-of-turn save (`event_autosave_final`) saves only when the folder has changes (tracked, or
  files the agent wrote) or the autosave ref is older than `HEAD`; otherwise it skips, so a turn that
  changed nothing pushes nothing. It never makes a work-in-progress commit.
- The pickup keeps fetched snapshots under `refs/house-rules/remote-autosave/` (`PICKUP_REMOTE_PREFIX`),
  not in the local `autosave` namespace.
- The pickup output is capped at 6000 characters (`PICKUP_CAP`), the note alone at 3500, with a line
  saying where it was cut. The fetch times out at 5 seconds.
- The rule text is one sentence in "Commit constantly on my own branches".

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
its index and its working tree are never changed. What goes into the snapshot: tracked changes and every new file git does not ignore
(aj, 2026-11-17, reversing #477's file-tool-only rule after a shell-made file was never saved). A new file over
the 50 MB big-file limit is left out and named. On the main session's branches the hook makes no
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
- 2026-11-08: the end-of-turn save must not push when nothing changed, or every read-only reply would
  move the autosave ref; the skip-when-unchanged rule above is what prevents it.
- The pickup cap cuts a long note at 3500 characters; keep the note's first lines the next step.

## Planned: a save per folder (2026-11-09, "Handoff overwrite" 1A)

Every folder on a branch saved to one ref, so the newest save replaced another folder's unrestored work; the
desktop QA lost session A's snapshot e724bf2 this way. Each folder now gets a random id, written once to
`.git/house-rules-folder-id`, and saves to `refs/house-rules/autosave/<branch>/<folder id>`. A save only ever
replaces its own folder's ref. The pickup fetches `refs/house-rules/autosave/*`, and for the current branch lists
each other folder's snapshot that holds files this folder lacks, newest first, each with its own restore command
(`git diff <snap>^ <snap> -- <files> | git apply`, which the guard allows and which stops rather than overwrite).
The folder's own snapshot is skipped, since its work is already in the folder. Old single-ref snapshots
(`refs/house-rules/autosave/<branch>`) are still read, so work saved before the change is not stranded.

## Phase 3 plan (2026-11-16, "Design approved: Phase 3 1A 2A 3B 4A")

The code above lives on `AjsAgent/session-handoff` and was left out of `main` by pull request #519. Phase 3 (#495)
copies it onto `AjsAgent/phase-3-handoff`, cut from `main`, with these changes. The keep, change and drop list is on the
build plan page, `docs/plans/2026-11-16-phase-3-build-plan.html`.

- **`main` today.** `event_autosave` (`scripts/house_rules/delegation.py:1361`) runs only on `worktree-agent-*` branches
  (`_autosave_target`, `delegation.py:1176`). There is no facts file, no `event_autosave_final`, no pickup, no
  handoff check and no rule sentence. The quoted-approval guard from #409 is already on `main` (`_LOOP_QUOTED_RE`,
  `scripts/house_rules/design_loop.py:412`).
- **A save per folder (#489, built in #527).** As planned in the section above, but under `refs/house-rules/saves/<branch>/<folder id>`, not `autosave/<branch>/<folder id>`: git cannot hold a ref and refs nested under the same name, and old single saves under `autosave/<branch>` exist on GitHub (a verify case covers it). Old saves stay readable for the pickup. Saves run on every branch, `main` included; a save is a ref only and never a commit there. Work-in-progress commits stay for `worktree-agent-*` branches.
- **Cloud sessions (1A).** When `CLAUDE_CODE_REMOTE=true`, the save skips the hidden ref, which a cloud session cannot
  push (Research.md, 2026-11-12 and its 2026-11-16 note). Instead it commits the tracked changes and the files the
  agent wrote as `wip: autosave` on the session's own branch and pushes the branch, on the same one-minute window and
  at the end of a turn. It does this only on a branch `branch_ownership` says is the agent's. A cloud session's branch
  starts with lowercase `ajsagent/`, which the guard does not count as the agent's today, so the guard learns that
  prefix in the same change. The pickup needs nothing extra for these saves: they are on the branch itself.
- **The handoff check** takes the `written` argument `handover_checkpoints` has on `main`
  (`scripts/house_rules/design_loop.py:3040`), not the `handoff` argument it had on the old branch.
- **A command for branch builds.** `claude plugin marketplace add Ajw2003/AjsClaudeCodeTools#<branch>` records
  `"ref": "<branch>"` and checks that branch out (run 2026-11-16 in a throwaway `CLAUDE_CONFIG_DIR`). The command wraps
  that, plus the plugin update, and a matching command goes back to `main`.
