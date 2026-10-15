# Audit: guards that stopped approved, routine work (2026-10-15)

Status: **fixed** in 2.66.0 (#261 `26a4b34`, #262 `f15fbd8`), from the proposal `docs/plans/guard-fixes.html`; each entry's real command is replayed in `scripts/verify.py`. This lists each time a guard or hook stopped an action this session that was already
approved and routine. Every entry is quoted from the session. The fixes come to aj as a proposal page before the
#251 pull request (decision logged 2026-10-15, "Before the pull request: guards must not stall an approved,
autonomous build").

| # | What was stopped | Where | Message (quoted) | Why it was wrong |
|---|---|---|---|---|
| 1 | Committing and pushing finished, tested work on this session's own branch | main session | "This command names another repo (--git-dir, or a cd / -C I could not follow)… Refused, not asked: aj has not written for 8 minutes… Do not retry this action, or reach the same result another way." | `git -C $G`, where `$G` was the repo itself. A guard that can't resolve a path refuses outright instead of resolving it. The "do not retry" rule then stopped the build until aj returned. |
| 2 | A builder helper committing its own finished step | subagent, main checkout | Helper's report: the guard refuses `git -C <path> commit` from a subagent ("names another repo", no one to ask). | Same cause as 1. A helper can never be asked, so this always stalls. |
| 3 | A builder helper's commit preceded by `cd` | subagent | Helper's report: the guard "refused a command starting with `cd`". | `cd <repo> && git commit` into the same repo is routine. |
| 4 | Every code edit by two builder helpers in their own git worktrees, during an approved Build stage | subagents, worktrees | "design loop: code edits are closed in the Design stage" | The loop state lives in each worktree's own git folder, so a worktree reads Design. Filed as a suggested task, "Fix design loop lock inside git worktrees". |
| 5 | Stopping my own stalled screenshot script while aj was away | main session | "pipes a wait or loop through tail/head… Refused, not asked: aj has not written for 7 minutes… Do not retry this action" | Not the `kill`: the same command had `sleep 1` and a later `\| head`, so the wait-pipe rule matched across unrelated parts of the command. Harmless here, since the script ended on its own. |
| 6 | A builder helper editing its own new file with a Bash Python script | subagent | Waiting-on-you entry for "python3 - <<'E' p='make_page.py'…" | Partly right: code edits through Bash do bypass the code lock (see 4). The helper should have used the Edit tool. |
| 7 | A builder helper running the test suite with its output piped through `tail` | subagent | "pipes a wait or loop through tail/head, which hides its output until it exits" (refused, not asked, inside a subagent) | Partly right: the rule is real. But a foreground run that ends on its own isn't a hidden wait. The helper re-ran it without the pipe. |
| 8 | Clearing a scratch folder of my own (`rm -rf` under the session scratchpad) before a check | main session | "deletes one or more files… Refused, not asked: aj has not written for 12 minutes… Do not retry this action" | The scratchpad is session-private and holds nothing of aj's. Deleting there is never destructive to aj's work. |
| 9 | A builder helper's commit preceded by `cd` (same as 3, hit again by the page-check helper) | subagent | "This command names another repo (--git-dir, or a cd / -C I could not follow)… Refused, not asked: this runs inside a helper (subagent)" | Repeats 3 even though the helper was told not to use `cd`, which shows that instructions alone don't prevent it. The helper re-ran it as plain `git commit`. |

## Not friction: these worked as intended

- The commit hook refusing a `Co-Authored-By: Claude` trailer and an author of `Claude <noreply@anthropic.com>`. That's aj's attribution rule.
- The design loop ignoring helper reports. This was the #253 fix, built today.

## Still to add

Refusals that the remaining #251 steps hit will be appended here, as each builder reports them.
