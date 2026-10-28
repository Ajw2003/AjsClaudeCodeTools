# Handoff — 2026-10-28: re-check the restructure before any of it returns to `main`

Start a fresh session from this file. Everything it needs is here or linked by repo path. Nothing below comes from
memory: each fact names where it was checked.

## Where things stand

- **`main` runs 2.73.3's code, numbered 2.74.1.** Pull request #428 reverted the restructure (pull request #427,
  version 2.74.0) and merged as `bc5a1b3`. The only plugin differences from 2.73.3 (`2b30052`) are the version in
  `.claude-plugin/plugin.json` and the check in `scripts/checks/design_loop.py` that pins it. Checked with
  `git diff --stat 2b30052 origin/main -- claude-house-rules`: 2 files, 3 lines. `verify.py` on that code: exit 0,
  965 PASS, 0 FAIL. CI `verify` on the pull request: success.
- **Nothing was lost.** The restructure commits stay in `main`'s history and on the branch `AjsAgent/issue-281-fix`.
- **A partial fix for 2.74.0 exists but is not on `main`.** Branch `ajsagent/affectionate-turing-y4ypfg`, commit
  `d3c7da3`: while a setting is unset, the settings gate refuses only commits, pushes, merges, tags, `gh` commands
  and GitHub tool writes, not every tool; `run.sh settingsgate` without Python warns instead of blocking. A second
  one-line fix (the environment variables win over an unreadable settings file) was never committed, because aj
  had not cleared it past the design lock; it sat in a `git stash` of a temporary cloud container, so it is written
  out here instead. In `settings.refusal` in `scripts/house_rules/settings.py` on that branch, the line
  `if not gone and not problem:` becomes `if not gone:`. Treat both as input to the re-check, not as done.
- **QA failed on "restructure steps 3 to 7"**, so issues #381 (restructure steps 3 to 7) and #382 (version 2.74.0,
  docs and release) are labelled `in progress` and the design loop is back at the Design stage.
- **Open check on aj's PC:** a read-only session titled "Read-only check: which house-rules version loads on this PC"
  was started on DESKTOP-ENFEPDQ (GameDev folder) to report which plugin version loads after the merge. It was
  waiting on aj to approve a PowerShell prompt. Its answer is still unknown; read it or re-run it first.

## What broke, with evidence

1. **2.74.0 refused every tool while `agent_name` was unset, replies included.** `settings.refusal` in
   `scripts/house_rules/settings.py` (2.74.0) returned a refusal for any tool but the settings script, and
   `settingsgate` is registered on every tool with no matcher in `hooks/hooks.json`.
2. **aj's environment variables never reached the PC.** A read-only session on aj's PC (Windows, PowerShell 5.1,
   Python 3.13.7) found `HOUSE_RULES_AGENT_NAME`, `HOUSE_RULES_OWNED_BRANCHES` and `CLAUDE_CONFIG_DIR` all unset.
   aj's projects run as Remote Control (bridge) sessions on that PC, so variables set in the cloud environment do
   not reach them, and no `env` block exists in `%USERPROFILE%\.claude\settings.json` or the GameDev folder's
   settings files. aj then approved saving `agent_name = ajw2003sAgent` and `extra_owned_prefixes = ""` to
   `C:\Users\aj\.claude\house-rules\settings.json`, after which the tools ran.
3. **The refusal's fix command fails on Windows.** It prints `python3 ...`; on aj's PC `python3` is only the
   Microsoft Store alias, and `python` is the real interpreter.
4. **An unreadable settings file refused every tool even with both variables set** (reproduced with the shipped
   2.74.0 hook and an empty settings file).
5. **The checks asserted the broken behaviour.** `scripts/checks/core.py` (2.74.0) had a case titled "an unset
   setting refuses a non-settings tool (Bash, Write, a GitHub tool, Read)". 1007 checks passed; no real session ran.
6. **I claimed from memory how updates reach aj's PC, and was wrong.** I said devices update through the plugin
   update; the PC loads a copy synced from the claude.ai account (under `AppData\Local\Claude-Data`), and
   `docs/3-state/ProjectState.md` already said such a copy runs no `claude plugin` update. The end-of-reply
   evidence check missed it: it looks only for ten success words (`scripts/house_rules/core.py:2603-2606` on
   `main`) and counts any tool call as evidence (`core.py:3017-3021`).
7. **The design lock counts single edits, not changes.** "skip design" let one Edit through; a two-line version
   change needed it twice, and the push in between left the pull request's checks red. The lock is on `main` too.
8. **I went quiet** for minutes during long tool runs, with no visible reasoning. aj: "never ever ever do you go
   quiet and hide work or reasoning from the user".
9. **The branch guard does not treat `ajsagent/` (lowercase) as owned**; `extra_owned_prefixes` held `AjsAgent/`,
   and the comparison is case-sensitive (`branch.startswith(owned_branch_prefixes())`,
   `scripts/house_rules/safe_git.py:252` on `main`), so every commit on this session's assigned branch needed the
   "no safe way" route.

## The standing rule this work must follow

`docs/6-decisions/Decisions.md`, "2026-10-28 - Nothing reaches staging or main on an unchecked assumption". In
short: every assumption a change rests on is listed and checked against code, docs and a real run; a real run is
the plugin as it ships, in a real Claude Code session on aj's PC (Remote Control) and in a cloud session, with real
data; every guard that can refuse work is run there in both its allowed and refused paths; memory and chat are
never evidence on their own; cost is not a reason to skip any of it.

## The task, in order

Each step is a proposal for aj first, as a page built with `make_page.py`, per the house rules. Nothing is built
before aj approves it by name.

1. **Read the PC check's result** (above) and record which version loaded and from where.
2. **Catalogue 2.73.3's behaviour** (what `main` runs now): every hook in `hooks/hooks.json`, what it allows,
   refuses and says, read from the code and confirmed in a real session on aj's PC. This is the known working
   baseline.
3. **Compare the restructure against it, step by step** (#341 settings and identity, #349, #343, #344, #345 under
   #381): for each step, what it keeps, changes and drops, then a real-session run of both versions on the same
   real task. A step returns to `main` only when its real-session run matches or improves on the baseline and aj
   passes its QA.
4. **Fix the design lock** so one approval covers one change, not one edit (item 7), tested in a real session.
5. **Fix going quiet** (item 8): find what can stop long silent stretches and propose it.
6. **Plan how the standing rule is enforced** (item 6 shows the evidence check cannot catch claims about
   behaviour), so a release cannot reach `main` without the real-session runs on record.
7. Fold in items 3, 4 and 9 where the steps above touch them.

## Branches

- `main` at `bc5a1b3`: the revert, 2.74.1.
- `AjsAgent/after-revert`: this handoff, the Decisions entry and a design-loop state commit, made from `main`
  after the merge. Not yet in a pull request.
- `ajsagent/affectionate-turing-y4ypfg`: the partial 2.74.0 fix (`d3c7da3`) and state docs for it.
- `AjsAgent/issue-281-fix`: the full restructure, as merged in pull request #427.
