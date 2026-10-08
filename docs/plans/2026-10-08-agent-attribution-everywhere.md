# Plan: "aj's agent" attribution and `AjsAgent/` branches, in every repo, going forward and backward

STATUS: decisions D1-D4 answered by aj 2026-10-08 (see bottom); D5 defaulted. Nothing built yet;
next is the parent issue plus one child per step.
Builds on [attribution-build-plan.md](attribution-build-plan.md) (issue #133, shipped in 2.51.0).

## What exists today, checked 2026-10-08 in a cloud session on this repo

- The `guard` hook refuses a `git commit` / `gh pr|issue create|edit|comment` whose text carries a
  Claude credit (`hook.py`, `_attribution_guard`, about line 4573). It is wired to
  `PreToolUse` `Bash|PowerShell` only (`hooks/hooks.json:70`).
- `tools/install.py` writes the Claude Code `attribution` setting on machines that run the
  installer.
- Branch ownership is a single constant: `OWNED_BRANCH_PREFIX = "claude/"` (`hook.py:1894`),
  used by the guard, `branchnudge` and the `Stop` check, and named in the rules text.

## The gaps, found by looking, not assumed

1. **Cloud sessions have no `attribution` setting.** This container's `~/.claude/settings.json`
   enables the plugin but has no `attribution` key, so the harness hands the agent the
   `Co-Authored-By: Claude` / `Claude-Session` trailers every session; only the guard stops them.
2. **The commit author itself is Claude.** Cloud `~/.gitconfig` sets
   `user.name=Claude`, `user.email=noreply@anthropic.com`. On this repo's `main`, 103 of 227
   commits are authored `Claude <noreply@anthropic.com>`. The guard reads message text, never
   the author, so this passes untouched.
3. **GitHub MCP tools bypass the guard.** `create_pull_request`, `update_pull_request`,
   `add_issue_comment`, `push_files`, `create_or_update_file` all write titles, bodies and commit
   messages without going through Bash, so no `PreToolUse Bash` check sees them.
4. **Branch names.** The cloud harness assigns `claude/<name>` and tells the agent to push only
   there. The plugin treats only `claude/` as the agent's own. This repo alone has 56 `claude/`
   branches on GitHub (plus 3 `ccr-*`).
5. **"All repos" is ~70 repositories** reachable from this account (list_repos), including forks
   and other people's repos (`busch-owen/*`, `IamNomadic/*`, `indikman/*`, `pe-gg/*`,
   `theseanzo/*`). Only repos where the plugin loads get the guard.

## Going forward (plugin work, this repo)

Step 1. **Ownership prefix becomes a list: `AjsAgent/` first, `claude/` still recognised.**
`OWNED_BRANCH_PREFIX` → a tuple; every "branch off" message names `AjsAgent/<topic>`; rules text
and `commit-branches.md` say `AjsAgent/`. `claude/` stays recognised because the cloud harness
will keep creating it and old branches exist; dropping it would make the guard treat the agent's
own cloud branch as aj's. verify.py cases for both prefixes and for a non-owned branch.

Step 2. **Cloud sessions branch to `AjsAgent/` at the start.** The `SessionStart` hook, when it
sees the checkout on a fresh `claude/<name>` branch with no commits beyond its base, tells the
agent to run `git switch -c AjsAgent/<name>` and push there. Depends on decision D3 (it overrides
the harness's "push only to the designated branch" instruction).

Step 3. **Commit author is "AJ's agent".** The guard refuses a `git commit` when the effective
author (`git config user.name` / `user.email`, or `--author`, or `GIT_AUTHOR_*`) is Claude or an
`anthropic.com` address, naming the fix. The `SessionStart` hook sets the repo-local identity in
cloud checkouts so the refusal rarely fires. Email per decision D2.

Step 4. **Extend the guard to GitHub MCP write tools.** New `PreToolUse` matcher for
`mcp__github__*|mcp__GitHub__*` write tools (create/update PR, issue write/comment, push_files,
create_or_update_file, review replies): same text patterns, plus refuse a `create_branch` /
`create_pull_request` head starting `claude/` when an `AjsAgent/` one is possible. Same kill
switch. Cases through each tool shape in verify.py.

Step 5. **Cloud settings carry `attribution` too.** The plugin cannot set it (only `agent` and
`subagentStatusLine` are allowed in a plugin's settings), so: document the one line to add to
the cloud environment's setup script, and have `SessionStart` write it into the container's
`~/.claude/settings.json` when missing (takes effect next session, so the guard still covers the
first). Unverified whether the harness re-reads it mid-session; the 2.51.0 notes say the desktop
app did.

Step 6. **Reach every repo.** The plugin is user-scoped, so it already loads in every repo on a
machine that installed it and in any cloud environment whose setup installs it. The remaining
gap is cloud environments set up without it: list them (`list_environments`) and make the setup
script install the plugin in each. Optionally add a tiny reusable GitHub Actions check
(`AjsAgent` attribution lint) that each repo can call, so a commit made outside Claude Code is
caught on push. GitHub's own branch-name / commit-message rulesets are a paid-plan feature for
personal repos as far as I know (unverified, checked from memory, not the API).

Version bump, docs tiers, Decisions entry, one PR `Refs #<parent>`, per house rules.

## Retroactively (one-off tool, `tools/retro_attribution.py`, dry-run by default)

R1. **Inventory first, change nothing.** Per repo in scope: `claude/` and `ccr-*` branches
(merged or not, open PR or not), commits on each branch with a Claude author or trailer, open and
closed PR bodies with Claude footers. Writes `docs/reports/retro-attribution-<date>.md`. aj reads
it before anything moves.

R2. **Rename branches** `claude/x` → `AjsAgent/x` with GitHub's rename-branch API. It is not a
delete: open PRs follow the rename and GitHub redirects the old name. Branch protection and local
clones still pointing at the old name need `git fetch --prune` (the report lists them).

R3. **Edit PR and issue text** to replace the footer with `Opened by AJ's agent`. Non-destructive
(GitHub keeps edit history).

R4. **Rewrite commit history** (author and trailers) — the only destructive part. Every SHA
changes; on `main` it needs a force-push, breaks every clone, every open PR, every tag and every
link to an old commit. See D1. If done, per repo: mirror backup first (`git clone --mirror` into a
dated folder), `git filter-repo --mailmap --message-callback`, force-push with lease, one repo at
a time with aj's yes for each.

## Decisions

Answered by aj, 2026-10-08:

- **D1: branches + PR/issue text only.** R4 (history rewrite) is dropped; no commit is rewritten.
- **D2: `AJ's agent <79066376+Ajw2003@users.noreply.github.com>`.**
- **D3: always switch** cloud sessions to `AjsAgent/<name>` at session start (Step 2 is in).
  Whether the app's "Create PR" button follows the new branch gets tested in the first cloud run.
- **D4: own non-fork `Ajw2003/*` repos only.**
- **D5 (not asked, defaulted): rename merged `claude/` branches too**, since a rename is not a
  delete and keeps the naming uniform. Say so if you'd rather leave merged ones alone.

The questions as asked:

- D1. History rewrite: none / unmerged branches only / everything including `main`.
- D2. Commit identity: name `AJ's agent` with which email — your GitHub noreply
  (`79066376+Ajw2003@users.noreply.github.com`, commits count as yours on your profile), or a
  dummy like `agent@ajs.invalid` (shows as an unlinked author).
- D3. Override the cloud harness's assigned `claude/` branch (Step 2), or keep `claude/` for
  cloud sessions and use `AjsAgent/` only where the agent names the branch itself.
- D4. Which repos: your own non-fork `Ajw2003/*` only, or also forks and the other owners' repos
  you can push to.
- D5. Old branches already merged: rename, or leave as-is (renaming merged branches has little
  benefit; deleting is a separate ask under house rules).
