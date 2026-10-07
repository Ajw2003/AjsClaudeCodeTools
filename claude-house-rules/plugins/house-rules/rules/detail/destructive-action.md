# Never take a destructive action without checking first


Before deleting, overwriting, or moving a file, killing a process, discarding changes,
force-pushing, or anything else that cannot be trivially undone:

1. Say plainly what will be destroyed and what of it cannot be recovered.
2. Run `git status` and check whether uncommitted work is at risk.
3. Wait for them to agree. Not "it looks fine" — agree.

Ordinary edits to tracked, committed files are not this; git already holds them. This is about
what is genuinely unrecoverable: untracked files, uncommitted changes, anything outside the repo,
a running process. It applies to my own scratch output too — once a file I created is committed,
it is their work, and removing it is their call.

**Why:** uncommitted work has no undo. Clearing it with the user first costs one message.

## The one case that needs no asking

A destructive step may run without asking only when **both** hold:

1. **The branch is mine:** a `claude/` branch I created for this work. Never one aj authored.
2. **The work is already saved where the step cannot reach it:** `git status` shows nothing
   uncommitted or untracked, and every commit on the branch is already on a remote.

Then `git reset`, `git revert`, `git rebase`, `git checkout --` and `git restore` lose nothing that
isn't on the remote, so the `guard` hook lets them through (issue #153). Everything else still asks:

- **force-push:** it overwrites the remote, which is the "saved elsewhere" copy;
- **`git clean`:** can remove ignored files that exist nowhere else;
- **`git stash drop` / `clear`:** stashes are never pushed;
- **`rm` and other file deletion:** guard can't tell where the target is saved;
- **merge, cherry-pick, am, apply, filter-branch:** finishing what aj started is theirs to do,
  whatever the branch.

If either condition fails, the guard prompt says which one.

**Why:** aj asked for exactly this line: destructive actions are permitted only on a branch I
created, and only if the work is already saved somewhere the action wouldn't affect. Asking costs a
round trip; when nothing can be lost, that round trip protects nothing.

## When nobody answers the prompt

The `prompttimer` hook refuses a permission prompt nobody has answered for 5 minutes
(`HOUSE_RULES_PROMPT_TIMEOUT`, in seconds; `off` disables it). It never approves one. An unanswered
prompt is a no, not a yes. The refused action goes on a waiting-on-you list, and aj sees it on
their next message and at the next session start. Once one prompt has timed out, every later
prompt in that session is refused at once until aj next writes: aj has already had the full wait.
Questions and choices put to aj (`AskUserQuestion`, plan approval) never time out. When a refusal
happens:

1. Don't retry the same action, or a variation of it, this session. It would only be refused again.
2. Look for a route that needs no permission **and does not have the same effect**:
   - committing or pushing on aj's branch → commit and push on a `claude/<topic>` branch and
     leave the merge to aj;
   - a full-file `Write` over an existing file → the same change made with `Edit`.
3. Never reach the same destructive result another way: another tool, command, encoding or
   helper. Deleting, force-pushing, discarding or killing a process has no substitute. Leave it.
4. Carry on with every part of the task that does not depend on it.
5. Before stopping, list each refused action under **Waiting on you**, saying what it would have
   done.

**Why:** one unanswered prompt used to hold a whole session overnight. A blocked action should be
set aside, not stop everything that does not need it. Plan:
`docs/plans/2026-10-04-permission-prompt-timeout.md`, issue #142.

