# Never take a destructive action without checking first


An action that could lose data with no way back, or change work that may not be mine, is refused
outright (#291). The refusal names the safe way to do the same job, and I do it that way:

| Refused | The safe way it names |
|---|---|
| Pushing or committing to `main` | open a pull request |
| A commit, merge, rebase, cherry-pick, revert, `am` or `apply` on a branch not confirmed mine | `git switch -c AjsAgent/<topic>` and commit there |
| A force-push, or `push --all` / `--mirror` | push a new branch |
| Deleting a branch (`branch -D`, `push --delete`) | leave it for aj to delete |
| `git clean` | move the files into a `_to_delete/` folder |
| `filter-branch` | rewrite on a copy branch |
| `reset`, `checkout --` or `restore` over uncommitted work | commit it on a new branch first |
| `stash drop` / `stash clear` | keep the stash |
| Truncating a file | write a new file beside it |
| A recursive delete, or deleting a file with uncommitted changes or never committed | move it into `_to_delete/` |

Deleting a committed, unchanged file goes through: git can bring it back. aj is asked only when no
safe way exists, and only when I cite the source that proves it by putting `no safe way: <source>`
(for example the git manual page) in the command's description. The prompt shows the citation.

**Why:** aj, 2026-10-15 (#285): the guards caused more problems than they prevented. A prompt nobody
answers stalls the work; a refusal that names the safe way lets me carry on without losing anything.

## The one case that needs no asking

A destructive step may run without asking only when **both** hold:

1. **The branch is not the default branch** (`main`, `master`, or what `origin/HEAD` names).
2. **The work is already saved where the step cannot reach it:** `git status` shows nothing
   uncommitted or untracked, and every commit on the branch is already on a remote.

Then `git reset`, `git checkout --` and `git restore` lose nothing that isn't on the remote, so
the `guard` hook lets them through (issue #153). Merge, rebase, revert and cherry-pick are not
destructive at all off the default branch (the old commits stay in the reflog and on the remote)
and run unasked on a branch confirmed mine (#197, #291). Everything in the table above is refused
on every branch: a force-push or `--all`/`--mirror` overwrites the remote, the "saved elsewhere"
copy; a deleted branch's unmerged work may exist nowhere else; `git clean` can remove ignored files
that exist nowhere else; stashes are never pushed; `filter-branch` rewrites every commit.

If either condition fails, the refusal says which one.

**Why:** aj asked for exactly this line: destructive actions are permitted only off `main`, and
only if the work is already saved somewhere the action wouldn't affect. Asking costs a round trip;
when nothing can be lost, that round trip protects nothing.

## When nobody can answer

A prompt inside a subagent (the hook input carries `agent_id`) is refused at once instead of
opened, because a subagent cannot answer a prompt (#198). How long ago aj last wrote no longer
matters (#290).

Each refusal goes on the waiting-on-you list, like a timed-out prompt. `HOUSE_RULES_PROMPT_TIMEOUT=off`
turns these refusals off with the timer.

## When nobody answers the prompt

The `prompttimer` hook refuses a permission prompt nobody has answered for 5 minutes
(`HOUSE_RULES_PROMPT_TIMEOUT`, in seconds; `off` disables it). It never approves one. An unanswered
prompt is a no, not a yes. The refused action goes on a waiting-on-you list, and aj sees it on
their next message and at the next session start. Each prompt waits on its own timer: an earlier
unanswered prompt never causes a later one to be refused (#290). The timer applies only to the
prompts the guards raise, never to anything else, such as publishing a page. Questions and choices put to aj (`AskUserQuestion`, plan approval) never time out. When a refusal
happens:

1. Don't retry the same action, or a variation of it, this session. It would only be refused again.
2. Look for a route that needs no permission **and does not have the same effect**:
   - committing or pushing on aj's branch → commit and push on an `AjsAgent/<topic>` branch and
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

