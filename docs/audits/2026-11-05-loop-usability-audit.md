# Design loop usability audit, 2026-11-05

A look at where the design loop and its guard get in the way of routine work, and how to remove that
friction without weakening what the loop is for. aj asked for it after the design loop deep dive
(`2026-11-05-design-loop-deep-dive.md`), naming two problems: a new session can't pick up from the old
one without every approval again, and a cloud session that runs out of disk can't delete anything to
free space, so it has to hand off. No code was changed. The page version is
`docs/plans/2026-11-05-loop-usability-audit.html`.

**What the loop must keep doing.** Every fix below was checked against these three promises:

1. Only aj's own message moves a stage.
2. Source code can't be edited before aj approves a build plan.
3. Nothing is deleted that can't be brought back.

**How it was tested:** the same probe as the deep dive. Throwaway git repos were fed to the real
functions (`_loop_scope_note`, `_loop_gate`), and real shell commands were piped through `hook.py guard`
on an `AjsAgent/` branch. Four findings also happened to this session while it did the work, and those are
marked "hit in this session". Paths are relative to `claude-house-rules/plugins/house-rules/scripts/`.

## Handoff: a new session starts from nothing

### 1. A new session needs every approval again, and two new issues

- **Where:** `house_rules/design_loop.py:399-402` (the stage file follows the branch), `:1118-1141` (issues are
  recorded only when they are created)
- **Problem:** The stage file lives in `.claude/house-rules-loop.json` and is committed with the
  branch, which works when the next session opens the same branch. A cloud handoff usually doesn't: the
  new session gets a fresh branch made from `main`. Proved: session A reached Build on its branch. Session
  B, on a new branch from the default branch, started in Design with no feature. "Build plan approved:
  login" was refused, then "Design approved: login" moved it to Plan. The build plan approval was then
  refused again: *"the feature has 0 labelled issue(s) made since its design was approved, and needs
  at least 2"*. The issues session A made still exist on GitHub, but nothing can attach them, so aj approves
  twice and the model opens duplicate issues.
- **Why it matters:** the approvals already happened, and they are in session A's stage file and in the
  decisions log. Making aj repeat them adds no safety.

### 2. An approval is not saved anywhere until the model pushes

- **Where:** `house_rules/delegation.py:1322-1325` (autosave pushes only `worktree-agent-` branches)
- **Problem:** aj's approval is written to the stage file on disk. It reaches the remote only when the
  main session commits and pushes. Autosave covers helpers only (by reading). A session that stops
  first loses the approval, and so does one whose disk is full, because `git commit` has to write
  objects. That is the second half of the out-of-disk problem.
- **Unverified:** a commit failing on a full disk was not reproduced, because filling this container's disk
  would end the session.

### 2b. Issues made by a script or a one-line loop are never counted

- **Where:** `house_rules/core.py:2309` (`_GH_PREFIX`), used by `house_rules/design_loop.py:1058` and `:1087`
- **Problem:** Reported by aj from another session: six step issues (#708 to #713) opened from a Python
  loop were not counted, so "Build plan approved" was refused with only #707 recorded. Proved with
  `_created_issue` and an output holding two issue URLs. None of these is recorded: `python3 make_issues.py`,
  `python3 -c` calling `subprocess.run(['gh', 'issue', 'create', ...])`, a one-line
  `for t in a b; do gh issue create ...; done`, or `gh api repos/o/r/issues -f title=...`. The one-line
  loop fails because `gh` has to follow a line start or one of `; & | ( ` $(`, and `do` is none of them. The
  same loop split over lines is recorded.
- **The other session's first option is not safe.** It offered to write #708 to #713 into the stage file by
  hand. That is the model writing its own approval state, which the Write/Edit refusal exists to stop. Its
  "state in .git" is also the legacy file of the deep dive's finding 3.
- **Fix:** Let `gh` follow `do`, `then`, `else` and `xargs`, count `gh api .../issues` POSTs, and give aj the
  "Issues for <feature>: #N" phrase below for issues made any other way.

### 3. `main` carries a finished feature's QA stage

- **Where:** `.claude/house-rules-loop.json` on `origin/main`, last changed by `a48c603`
- **Problem:** On `main` today the stage is QA for "rerun limit", whose pull request has already been merged.
  Every session started from `main` inherits that stage. Merging a pull request records the merge
  for the issue-close guard (`event_closablemerge`), but never moves the stage to Done.
- **Effect:** small, because new work starts with "Design approved" anyway. But the stage file says
  something false, and finding 1's fix would read it.

## Out of disk: nothing can be deleted

### 4. Every folder delete is refused, including ones git or an install can rebuild

- **Where:** `house_rules/safe_git.py:893-900` (`_delete_refusal` returns "recursive" before it checks
  anything), `:174` (the safe way it names)
- **Problem:** Proved through `hook.py guard`, all on an `AjsAgent/` branch:

  | Command | What it holds | Decision |
  |---|---|---|
  | `rm tracked.txt` | one committed, unchanged file | allowed |
  | `git rm tracked.txt` | the same | allowed |
  | `rm -r trackeddir` | committed, unchanged files | refused |
  | `git rm -r trackeddir` | the same | refused |
  | `rm -rf node_modules` | what `npm install` rebuilds | refused |
  | `rm -rf build` | build output | refused |
  | `rm -rf .claude/worktrees/agent-1` | a finished helper's checkout | refused |
  | `rm -rf /tmp/some-cache`, `rm -rf ~/.cache/pip` | temporary files outside the repo | refused |
  | `rm scratch.log` | a file never committed | refused |
  | `git clean -fdX` | ignored files only | refused |

- **The safe way it names doesn't help here.** Every refusal says to move the folder into `_to_delete/`.
  On the same disk, a move frees no space at all. The only other way out is a `no safe way:` citation,
  which turns into a permission prompt for aj.
- **Why it matters:** these are the folders that fill a cloud session's disk, and git or an install
  can bring every one of them back. The single-file rule already allows a committed, unchanged file
  (#291). The folder rule never checks.

### 5. `git worktree remove --force` gets no decision

- **Where:** `house_rules/safe_git.py`, `GUARD_R4` (no pattern names it)
- **Problem:** Proved: both `git worktree remove` and `git worktree remove --force` got no decision. The plain
  form is the right tool for finding 4's helper folders, because git refuses it when the worktree has
  uncommitted changes. The `--force` form throws those changes away and should be refused. This is a
  safety gap more than friction, and it is listed here because finding 4's fix relies on the plain form.

## Routine friction hit in this session

### 6. Text inside a quoted string or a heredoc is read as a command

- **Problem:** Hit twice in this session. A heredoc that wrote a probe script containing `git -C ...`
  was refused as a commit to another repo. A `sed` expression containing the text `rm -r`
  after a `\n` was refused as a delete. A `git commit` chained after a `grep` whose search text was
  `gh issue create` was refused for an issue missing its "Done when" section. None of these commands
  deleted, committed or created anything.
- **Fix:** Strip heredoc bodies and quoted arguments before the destructive patterns run. The design
  loop already does this for its own checks (`_HEREDOC_RE`, `_QUOTED_RE` in `design_loop.py:204-207`).

### 7. The first commit of a cloud session is refused three times

- **Problem:** Hit in this session. The cloud harness asks for a `Co-Authored-By: Claude` footer, and the
  guard refuses it. The `git config` identity command was chained in front of that same refused commit,
  so it never ran, and the retry was refused again for the Claude identity. Fixing a claude.ai link that
  happened to be in the report took a third try.
- **Fix:** Have the SessionStart hook set the repo's `user.name` and `user.email` itself instead of asking
  the model to. Make the attribution refusal say plainly "drop the Co-Authored-By line, end with
  `Committed by AJ's agent`".

### 8. Reading a script counts as running it

- Already the full audit's finding 6. It was hit here on a third read of `design_loop.py` with `sed`, so this
  session switched to the Read tool.

## Proposed fixes, checked against the three promises

| Fix | Findings | Promise 1: only aj | Promise 2: code locked | Promise 3: recoverable |
|---|---|---|---|---|
| **"Continue from: <branch>"**: aj types it and the hook adopts that branch's stage file from the remote | 1 | kept, because aj types it and the approvals it carries were aj's | kept, because the stage is copied, never invented | n/a |
| A start-up note names remote branches whose stage is Plan, Build or QA | 1 | kept, because it only informs | kept | n/a |
| "Issues for <feature>: #12 #13": aj attaches existing issues in Plan | 1, 2b | kept | kept, because a build plan still needs aj | n/a |
| Count `gh issue create` after `do`, `then`, `else` or `xargs`, and `gh api .../issues` POSTs | 2b | kept | kept, because a build plan still needs aj | n/a |
| The approval note tells the model to commit and push the stage file at once | 2 | kept | kept | n/a |
| A merged pull request moves QA to Done when QA passed is recorded | 3 | needs aj's call: a merge is aj's act, but not a message | kept | n/a |
| Allow a folder delete when every file in it is committed, unchanged and pushed | 4 | n/a | n/a | kept, because git restores it |
| Allow deleting git-ignored folders on a fixed list: `node_modules`, `__pycache__`, `.venv`, `.pytest_cache`, `dist`, `build`, `.next`, `target` | 4 | n/a | n/a | kept for the list, because an install or build rebuilds them; `.env`-style files are never on it |
| Allow deletes under `/tmp`, the session scratchpad and `~/.cache` | 4 | n/a | n/a | kept, because they hold temporary files by definition |
| Name `git worktree remove` for helper folders, and refuse `--force` | 4, 5 | n/a | n/a | kept, because git refuses a dirty worktree |
| Replace `_to_delete/` in the refusal with the safe ways above when the target is a folder | 4 | n/a | n/a | kept |
| Strip heredocs and quoted text before the destructive patterns run | 6 | n/a | n/a | kept, because only text that runs is checked |
| SessionStart sets the git identity; a plainer attribution refusal | 7 | n/a | n/a | n/a |

Rejected: adopting a remote branch's stage automatically, without aj's message. A session could then
pick an old branch's Build stage, which is finding 9 of the deep dive. It breaks promise 1.
