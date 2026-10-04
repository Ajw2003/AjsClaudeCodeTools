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

## When nobody answers the prompt

The `prompttimer` hook refuses a permission prompt nobody has answered for 5 minutes
(`HOUSE_RULES_PROMPT_TIMEOUT`, in seconds; `off` disables it). It never approves one. An unanswered
prompt is a no, not a yes. The refused action goes on a waiting-on-you list, and aj sees it on
their next message and at the next session start. When that happens:

1. Don't retry the same action this session. It would only wait again.
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

