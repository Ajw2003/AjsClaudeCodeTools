# After every pull request: how to test it, and what's next

aj, 2026-10-16, after pull request #295 merged: "How can I verifiably test these fixes in a new
session? And what's next? That should be a question we ask and answer from now on after every pull
request." So every pull request answers both, in three places: the pull request body, its QA page,
and the reply that reports it opened or merged.

## How do I verifiably test this in a new session?

A new session is the honest test: it installs whatever is on GitHub, not what is on my disk.

1. **First step, always: the installed version.** The exact command that lists the installed
   plugin's version, and the version it should show. A wrong version means the rest tests the old
   build, so the step says what to run to update it.
2. **One step per fix.** Each names the literal prompt to send, or the command to run, in the new
   session, and the exact output or behaviour that proves the fix works. "Check that X works" is
   not a step.
3. **What proves it failed.** Each step also says what a failure looks like, so a pass is not
   judged by its absence.
4. **What I already ran.** The steps I ran myself say so, with the real output quoted. A step only
   a live session can run is marked `UNTESTED:` with the reason, as the rule "Never hand over a command I have not run where
   they will run it" requires (`rules/detail/handover-command.md`).

## What's next?

Every open item the pull request leaves, nothing dropped:

- aj's decisions: the QA verdict, any held issue, any choice the build raised.
- Issues still open, by number and title, and which ones aj can close once tested.
- Follow-ups the build found, and cleanup it left: files in `_to_delete/`, stale worktrees, stale
  waiting-on-you entries.
- Older open pull requests and branches this one did not touch.

Each item says what it waits on and gives my suggested next step, with one marked as the one to do
first.

**Why:** a merged pull request was being reported as done with no way for aj to prove it in a fresh
session, and with the open threads scattered across issues and replies.
