# Commit constantly on my own branches, never on theirs


Read-only inspection is always fine, anywhere: `git status`, `git log`, `git diff`, `git show`.

**On a branch I created** — one opened for this work, conventionally `AjsAgent/<topic>` — I commit
freely and often, without asking. That is the whole point: frequent commits *are* the backup and
the revert checkpoints. A session's work must never sit uncommitted for hours. When I finish a
coherent piece, it gets committed before I start the next one.

`claude/` is still treated as mine too, because the cloud app names its branches that way.

**On a branch the user authored** — `main`, `master`, or any branch they named and work on — I
mutate nothing. Not the repo, the index, the working tree, or a remote: `add`, `commit`, `push`,
`reset`, `revert`, `stash`, `rm`, `mv`, `merge`, `rebase`, `clean`, `tag` are all theirs to
authorise, every time. If work needs committing and I am standing on one of theirs, I create my
own branch from it, commit there, and say that I did.

**"If needed" arrives at the first edit, not at the first commit.** Standing on a branch that is
not mine, I branch off before changing a file, so the work never sits uncommitted on theirs. The
`branchnudge` hook says so on the first uncommitted change, and the `Stop` hook names any file this
turn wrote that is still uncommitted at the end of the turn — committing is an obligation, not
only something the guard permits.

**Destructive steps on my own branch** (reset, rebase, restore and the like) run unasked only when
the work is already saved where they can't reach it: a clean tree and every commit pushed. The
full line, and what still asks, is in `destructive-action.md`, "The one case that needs no asking".

**I never delete a branch**, mine or theirs, unless asked. Deleting is the one mutation that is
not a checkpoint.

Three things hold even on my own branches:

- **I commit my work, scoped to the paths I changed.** I never sweep up unrelated dirty files, a
  half-finished merge, or edits the user made. Those are theirs, and a commit that buries them
  inside my change is not a checkpoint, it is a mess. `git commit -- <paths>` over `git add -A`.
- **I do not finish what the user started.** An in-progress merge, rebase or cherry-pick is theirs
  to complete or abandon, even on a branch named after me. I stop and say so.
- **I say what I committed and where**, in the same message. A silent commit is not a backup the
  user can find.

**Why:** the rule this replaces said "never commit without asking", and its purpose was to stop
work being lost. It achieved the opposite, twice, in ways worth recording rather than quietly
rewording. Every commit needed a round trip, so none happened, and a full day of work accumulated
uncommitted until a machine change nearly took all of it. Separately, an ephemeral container
reclaimed work that had never been committed because the round trip had not come back yet. A rule
written to protect the user's history was instead the thing destroying work — the precise outcome
it exists to prevent, and a rule that produces its own failure case is mis-drawn.

The line it actually needs to draw is ownership, not permission. Frequent commits on a branch that
is mine risk nothing; that history is disposable. The user's is not.

## Credit "aj's agent", never Claude

Commits end with `Committed by AJ's agent`; pull requests end with `Opened by AJ's agent`. The
user wants the distinction that an agent did the work, but not the Claude branding, and no email
shown, so there is no `Co-Authored-By:` trailer (a trailer needs an email) and no
`Generated with [Claude Code]` line, `Claude-Session` trailer or `claude.ai/code/` link.

Two mechanisms, because a plugin cannot carry the Claude Code `attribution` setting (a plugin's
`settings.json` may only hold `agent` and `subagentStatusLine`): `tools/install.py` writes
`attribution` (`commit`, `pr`, `sessionUrl: false`) into `~/.claude/settings.json` on each machine,
and the `guard` hook refuses a `git commit`, `gh pr create/edit` or `gh issue create/comment` whose
text carries the old forms, naming the replacement wording. The guard is the backstop for sessions
that never read the settings file (cloud sessions). `HOUSE_RULES_ATTRIBUTION=off` disables it.

