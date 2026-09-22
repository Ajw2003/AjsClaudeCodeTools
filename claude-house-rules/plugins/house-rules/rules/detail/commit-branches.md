# Commit constantly on my own branches, never on theirs


Read-only inspection is always fine, anywhere: `git status`, `git log`, `git diff`, `git show`.

**On a branch I created** — one opened for this work, conventionally `claude/<topic>` — I commit
freely and often, without asking. That is the whole point: frequent commits *are* the backup and
the revert checkpoints. A session's work must never sit uncommitted for hours. When I finish a
coherent piece, it gets committed before I start the next one.

**On a branch the user authored** — `main`, `master`, or any branch they named and work on — I
mutate nothing. Not the repo, the index, the working tree, or a remote: `add`, `commit`, `push`,
`reset`, `revert`, `stash`, `rm`, `mv`, `merge`, `rebase`, `clean`, `tag` are all theirs to
authorise, every time. If work needs committing and I am standing on one of theirs, I create my
own branch from it, commit there, and say that I did.

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

