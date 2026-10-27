# Usage handoff (planned)

How work stays saved and handed off, so a usage limit never strands it and a session on another
Claude account can pick it up at once. Designed 2026-10-27 ("Design approved: usage limit handoff 1A
2A 3A", `docs/6-decisions/Decisions.md`); proposal page `docs/plans/2026-10-27-usage-limit-handoff-revised.html`.
It replaces issue #140 ("auto create a handoff document at 95% usage and commit all current changes").

## What it owns

- The save check: a row of the end-of-reply (`Stop`) dispatcher, `event_handover` in `scripts/hook.py`,
  that sends a reply back once when the turn's work is not committed, not pushed, or not described.
- The handoff note: `docs/5-today/handoff-<branch>.md` in the repo being worked on, one per branch,
  rewritten in place, where `<branch>` is the branch name with each `/` replaced by `-`.
- The pickup: a `SessionStart` block that loads the note for the branch the session opens on.

## Why it doesn't wait for 90%

The original ask was a trigger at 90% of the five-hour or weekly usage limit. Tested 2026-10-27:

| Surface | Can a hook learn the usage percentage? | Evidence |
|---|---|---|
| Terminal | Only through the status line, which a plugin can't set | `rate_limits.five_hour.used_percentage` and `seven_day` in code.claude.com/docs/en/statusline.md; plugin settings accept only `agent` and `subagentStatusLine` (`docs/3-state/ProjectState.md` line 106) |
| Cloud, including the phone | No | A status line set in a cloud project thread, refreshing every 5 seconds, never ran over about 15 replies |
| Desktop app | Not documented; untested | The desktop docs mention a usage ring, never a status line |
| Every surface | No hook input carries usage | The hooks reference's common input fields; `StopFailure` with `rate_limit` fires only after the limit is hit |

The end-of-reply hook does run on every surface: seen blocking a reply in a cloud project thread on
2026-10-27, and on the Windows desktop app on 2026-09-07 (`docs/desktop-verification.md`). So the design
saves on every reply that changes files instead of predicting the limit.

## How it works

**The save check.** It runs only when the turn wrote files or made a commit (`handover_turn_writes`). It
checks, in order:

1. No file this turn wrote is left uncommitted. This is the existing commit check
   (`handover_commit_check`, `safe_git.py`), unchanged.
2. The branch is pushed: it has an upstream and `git rev-list @{u}..HEAD` is empty. On `main`, the advice
   is to branch off to an `AjsAgent/` branch first, as `rules/detail/commit-branches.md` requires.
3. The handoff note is current: no commit on the branch is newer than the note's last commit
   (`git rev-list <note's last commit>..HEAD` is empty), so a commit that carries both the work and the
   note passes.
4. The note carries no published page link, no session link and no Claude credit (aj's standing rule,
   2026-10-27).

Any failure sends the reply back once with the reason, through the existing one-block checkpoint
mechanism. A turn that changed nothing is never checked. `HOUSE_RULES_HANDOFF=off` turns the check off.

**The note.** Five short sections: what the work is for, where it stands, the next step, what is
unverified, and the issue numbers. Its shape is cut down from `docs/handoff-2026-10-15.md` so updating it
costs little usage.

**The pickup.** At session start, if the current branch has a note, its text is added to the session
context with a first line saying it was loaded and from which file. It is capped so a large note can't
crowd the context.

## Invariants

- The hook only checks; the commit, push and note are written by the model, so commit messages stay
  meaningful.
- Nothing is committed on `main` or on aj's own branch; the rules for that are unchanged.
- A git command that fails is reported as "could not tell", never treated as a pass.

## Traps that have already cost time

None yet; this system is planned.
