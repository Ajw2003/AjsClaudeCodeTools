# Stop permission prompts stalling the main thread and subagents

Date: 2026-10-09. Status: plan, not built. Asked for by aj: find out why sessions and subagents
sit on permission prompts, plan the fix, and list the GitHub issues and pull requests it would
finish.

## What aj wants

- A normal commit or push never raises a permission prompt.
- `main` is never committed on or pushed to directly. Changes reach it only through a pull request.
- The only actions that stop and ask are destructive ones on `main`, and deletion or otherwise
  unrecoverable actions on any other branch.
- An unanswered prompt must never stall the whole workflow. The action is refused, and the work
  goes around it or carries on without it.

## Why it happens

### 1. The `guard` hook asks about ordinary git work on most branches (confirmed)

`guard` (`claude-house-rules/plugins/house-rules/scripts/hook.py`, `event_guard`) lets a plain
commit or push through only when the branch starts `AjsAgent/`, `claude/` or `ccr-`
(`OWNED_BRANCH_PREFIXES`). Everywhere else it returns `ask`. Run directly against throwaway
repos on 2026-10-09 (house-rules at commit `34639ce`):

| Branch | `git commit` | `git push` | `git merge origin/main` | `rm build.log` |
|---|---|---|---|---|
| `worktree-agent-a1b2` (every subagent with `isolation: "worktree"`) | ask | ask | ask | ask |
| `feature/login` | ask | ask | ask | ask |
| `main` | ask | ask | ask | ask |
| `ccr-x` | allow | allow | ask | ask |

So:

- **Every subagent working in a worktree prompts on every commit.** Its branch is named
  `worktree-agent-<id>` by Claude Code and is not on the list. The house rules tell builders to
  commit constantly and to use worktrees, so this fires constantly. A background subagent cannot
  answer, so it waits. Reported as #134 and #136.
- **`main` gets an `ask`, not a refusal.** A commit on `main` is exactly what aj never wants, yet
  it waits on a dialog instead of being refused at once with "branch off and open a PR".
- **Merging the base branch into a PR branch always asks**, on every branch. That is routine
  (keeping a PR up to date) and changes nothing that cannot be undone.
- **`git -C <repo> commit` still asks on an `AjsAgent/` branch.** PR #195 fixed the `cd <repo> &&`
  form of #192; the `-C` form is still treated as "another repo" (`_OTHER_REPO_RE`). Confirmed by
  the same direct run.

### 2. The 5-minute timer cannot be relied on to unstick a prompt (from the record)

`prompttimer` (the `PermissionRequest` hook) refuses a prompt after 5 minutes. The record shows
three ways that still leaves the work stuck:

- **The refusal cascades.** After one timeout, every later prompt in the session is refused at
  once, and Claude is told not to retry "this action, or a variation of it". When the refused
  action was a commit or push, there is no permission-free route around it, so the work stops.
  That is what #173 and #192 describe: ordinary commits, a test script, `gh pr create`, all
  refused, the session idle for an hour.
- **No timer runs if the worker restarts while a dialog is open** (#159). `PermissionRequest`
  never fired; the dialog waited 12 minutes until aj pressed Deny.
- **The dialog stays open after the refusal** (#149), still offering "Allow once" hours later.

None of these can be fixed from inside the timer: the second and third are Claude Code
behaviour. The fix is to stop needing the timer for anything that isn't destructive.

### 3. Some prompts are Claude Code's own, not house-rules'

#173's session ran every command in a sibling worktree outside the session folder, so Claude
Code itself asked about each one. `guard` stays silent on an allowed command, which leaves Claude
Code's own prompt in place. A `PreToolUse` hook that returns `allow` skips that prompt (deny
rules in settings still apply).

## The fix

One branch policy in `guard`, then make the few remaining prompts unable to stall.

### Step 1 - one branch policy for git writes

The protected branch is the repo's default branch: read `refs/remotes/origin/HEAD` from the git
directory (a file read, no subprocess), falling back to `main` and `master`.

| Action | On the default branch | On any other branch |
|---|---|---|
| plain `commit`, `push` (no force), `add` | **deny** with "branch off and open a PR" | **allow** |
| `merge`, `cherry-pick`, `revert`, `am`, `apply`, `rebase` | **deny** | **allow** (history only; nothing is lost) |
| `reset`, `checkout --`, `restore` | ask | allow when the work is saved elsewhere (existing #153 check), else ask |
| force push, `push --delete`, `branch -D`, `clean`, `stash drop/clear`, `rm`, killing a process | ask | ask |

- "Allow" is emitted as `permissionDecision: "allow"`, not silence, so Claude Code's own prompt
  is skipped too (cause 3). Narrow on purpose: only the rows marked allow above.
- The owned-prefix list stops mattering for commit and push. It stays only for the attribution
  and branch-naming nudges that already use it.
- `git -C <dir>` and a leading `cd <dir> &&` both read the branch of `<dir>`. `--git-dir` and
  `--work-tree` still withhold the allow.
- The attribution check reads the git identity from that same `<dir>`. Found while testing: today
  it reads the session folder, so `cd <repo> && git commit` is refused as "authored by Claude"
  when the session folder is not the repo, even though `<repo>` has the right identity.
- GitHub tool calls get the same rule in `guardgithub`: `push_files` and `create_or_update_file`
  aimed at the default branch are denied.
- Belt and braces, aj's side: a GitHub branch protection rule on `main` requiring a pull request.
  That is a GitHub setting only aj can change; the plan hands it over as a step card.

### Step 2 - the remaining prompts never stall

After step 1, only the destructive rows still ask. For those:

- **In a subagent, deny instead of ask.** A subagent cannot usefully wait. `guard` checks the
  payload's subagent marker (`agent_id`; to be confirmed against a live payload before relying on
  it) and refuses with: "leave it, list it under Waiting on you in your report". The parent still
  sees it.
- **When aj is away, deny instead of ask.** `scope` already runs on each of aj's messages; it
  records the time. If `guard` would ask more than 5 minutes after aj last wrote, it refuses at
  once and queues the action on the waiting-on-you list. This is the fallback the original timer
  plan wrote down for when the timer can't see a dialog, and it covers #159: no dialog opens, so
  nothing can outlive a worker restart.
- **The timer stays** for the main-thread case where aj was present and then left. Its refusal
  text and the cascade now apply only to destructive actions, which is what #173 asked for: a
  refused deletion stays refused; nothing ordinary is refused any more because nothing ordinary
  prompts.

### Step 3 - rule text, docs, tests

- `rules/house-rules.md` ("Commit constantly…" and "Never take a destructive action…") and
  `rules/detail/commit-branches.md`, `rules/detail/destructive-action.md` say the table above.
- `verify.py` gets one case per table cell, plus the `-C` case, the attribution-from-`<dir>`
  case, the subagent deny and the away deny.
- `docs/architecture.md` hook table, `docs/4-systems/hook-engine.md`, a dated
  `docs/6-decisions/Decisions.md` entry (this reverses "commit and push only on my own branch
  prefixes"), version bump.
- One live check in a cloud session: a background builder in a worktree commits and pushes with no
  prompt; a commit on `main` is refused at once; an `rm` left unanswered for 5 minutes is refused
  and the session carries on.

## Out of scope

- The "hidden work" prompts (`nohup`, trailing `&`, `Start-Process`) and the issue-workflow
  prompts (`gh issue close`). aj didn't mention them; they stay as they are unless aj says
  otherwise.
- #149's stale dialog. Claude Code owns the dialog; after this change it should only ever appear
  for destructive actions, and a deny-when-away means it rarely appears unattended.

## GitHub issues and pull requests this covers

Close once the work is done and aj has tested it (aj closes; nothing closes automatically):

| # | Title | Why it is covered |
|---|---|---|
| #134 | Helpers on their own branches stop and wait for approval every time they commit | Step 1: commit/push allowed on every non-default branch, `worktree-agent-*` included |
| #136 | Background builders sit blocked for 20+ minutes on approval prompts | Step 2: subagents get a refusal, never a wait |
| #173 | A timed-out permission prompt blocks safe, recoverable work | Steps 1-2: ordinary work no longer prompts; the cascade only reaches destructive actions |
| #192 | Commits on an `AjsAgent/` branch still prompt when the repo isn't the session's main folder | Step 1: `-C` form (the `cd` form was fixed by PR #195) |
| #159 | Prompt timer does not run when the session's worker restarts | Step 2: away-deny means no dialog is left open to outlive a worker |
| #172 | Fix builder cannot recover from failed tasks, timed out prompts or stopped tasks | Partly: the timed-out-prompt part. No body; aj to say if the rest stays open |

Related, not closed by this:

- #142 (parent of the prompt timer) and #149: the timer stays; #149's stale dialog is Claude
  Code's. #142 can close with #159 if aj agrees.
- #144, #145, #146, #151, #152, #153: already built and shipped; still open, waiting on aj's test.
  Not affected.
- PR #190 (draft, "Git rules no longer miss commands with quoted option values"): touches the same
  `guard` patterns. Not a duplicate; merge it first or rebase this work on it to avoid conflicts.
