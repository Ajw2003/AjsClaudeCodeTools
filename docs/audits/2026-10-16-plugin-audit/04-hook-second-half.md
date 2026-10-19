# Audit 4 of the house-rules plugin: hook.py, lines 4200 to the end

Raw findings from a read-only scout pass on 2026-10-16 (Read tool only). All line numbers refer to
`claude-house-rules/plugins/house-rules/scripts/hook.py` at plugin version 2.68.0. Items checked
by hand afterwards are marked **confirmed**. The scout inferred hook events from docstrings rather
than reading `hooks/hooks.json`; audit 2 confirms that all 30 entry points are wired.

## Inventory of hook entry points and subsystems in this range

| Subsystem (lines) | Event | What it does | State and external calls | Off switch |
|---|---|---|---|---|
| Prompt timer, `event_prompttimer` (4410-4531) | PermissionRequest | Times a guard's question; after the timeout it refuses and records the action as refused | Waiting list; asked-key file `tempdir/house-rules-asked-<session>` (4338-4351) | `HOUSE_RULES_PROMPT_TIMEOUT=off` |
| `_ask_or_refuse` (4360-4400) | (inside guards) | Turns a guard question into a refusal inside helpers | Waiting list | `HOUSE_RULES_PROMPT_TIMEOUT` |
| `event_promptran` (4534-4576) | PostToolUse, PostToolUseFailure | Marks a waiting entry as run and reports late approvals | Waiting list | None of its own |
| Waiting-on-you notes (4209-4287) | UserPromptSubmit, SessionStart | Reports refused actions | Waiting list | `HOUSE_RULES_PROMPT_TIMEOUT` |
| `event_subagentcommit` (4642-4719) | SubagentStop | Blocks a helper that leaves files uncommitted, once; on retry commits its autosave branches with a force-push | Transcript; git; push | `HOUSE_RULES_COMMIT_CHECK` (4644); `HOUSE_RULES_AUTOSAVE` |
| `event_autosave` (6344-6387) | PostToolUse | Commits after 10 minutes idle on `worktree-agent-*` branches, snapshots to `refs/house-rules/autosave/<branch>`, force-pushes to origin at most once per 60 seconds; also records issue creation and labels | `.git/house-rules-autosave-*.{index,pushed,noorigin,denied}` (4804-4806); git push | `HOUSE_RULES_AUTOSAVE` (the issues and loop switches also keep it running) |
| `event_commitgate` (6390-6454) | PreToolUse on Write, Edit, NotebookEdit (and Bash, per audit 2) | Blocks edits at 3 or more uncommitted files, then commits for the agent on the second try; also runs the loop gate and the issue gate | git | `HOUSE_RULES_AUTOSAVE`, `HOUSE_RULES_ISSUES`, `HOUSE_RULES_LOOP`, each for its own gate |
| `event_worktreesweep` (6494-6544) | UserPromptSubmit | Commits any helper worktree idle for 10 minutes, with a force-push | git; push | `HOUSE_RULES_AUTOSAVE` |
| Issue workflow (4925-5222, 5713-5931, 6254-6341) | Several | Counts plan steps (5012-5045), records issue creation (5871-5913), gates code on issues (5201-5221), adds a stop line (5916-5931); `event_issuelist` (6309-6341) lists open issues at session start | `.git/house-rules-issues.json` (4934, per worktree); cache `.git/house-rules-issues-cache.json` (6273); `gh issue list` (6282) | `HOUSE_RULES_ISSUES` |
| Design loop (5224-5695, 5713-5868) | Several | Stage file, edit gate (5649-5695), approval parser (5467-5568), scope reader (5571-5596), helper note (5599-5618), stop line (5621-5646) | `.claude/house-rules-loop.json` in the main checkout (5258-5261), falling back to the git common dir (5270); `gh api repos/<repo>/issues/N` (5379) | `HOUSE_RULES_LOOP` |
| Pull request and issue text checks (5934-6242) | PreToolUse | Checks `gh pr create`, `gh issue create/edit/close` and label changes | Reads pull request body files | `HOUSE_RULES_ISSUES`; `HOUSE_RULES_CLEAR_WRITING` for issue sections |
| Attribution, author and branch checks (5971-6186) | PreToolUse | Commit author, credit text, branch names | git | `HOUSE_RULES_ATTRIBUTION` |
| `event_guardgithub` (6031-6094) | PreToolUse on GitHub tools | The same credit and issue-section checks for GitHub tool writes | None | `HOUSE_RULES_ATTRIBUTION`, `HOUSE_RULES_CLEAR_WRITING` |
| `event_audit` (6550-6623), `event_userpromptaudit` (6629-6696) | PostToolUse on Agent/Task; UserPromptSubmit | Audit a finished helper's transcript | Transcript | `_delegation_enabled` |
| `event_handover` (7592-7865) | Stop | Runs the checkpoint table (7518-7537) and the card, evidence, commit, plain-summary, parity, visual, editor and writing checks; blocks once per check, and the page row up to 3 times (7561-7562, 7758-7776) | `<git common dir>/house-rules/page-blocks.json` or temp dir (7567-7571); transcript; `docs/plans/*.html` (7202-7234); git status and log | `HOUSE_RULES_HANDOVER`; sub-switches `HOUSE_RULES_LOOP`, `_COMMIT_CHECK`, `_PLAIN_SUMMARY`, `_PARITY`, `_VISUAL_CHECK`, `_CLEAR_WRITING`; the evidence check has none |
| `event_pagecheck` (7431-7481) | PreToolUse on Write and Artifact | Refuses pages in `docs/plans` that lack the page builder's mark | None | `HOUSE_RULES_LOOP` |
| `event_harvest` (8146-8283) | PostToolUse on Write, Edit | Finds essay-length comments in source files and asks for them to move to docs | None | `HOUSE_RULES_HARVEST` (off or quiet), `HOUSE_RULES_HARVEST_MIN_CHARS` |

## Logic against logic
- Autosave writes "Co-Authored-By: Claude" and a Claude-Session trailer (4896-4898), commits as `house-rules@localhost` (4912-4915), and runs git directly, so the guard never sees it; the guard refuses the same trailers (5979, 5983) and demands a personal identity (6100-6101). **Confirmed.**
- The design-loop comment says only aj's message moves the stage (5226); opening a pull request (5857) and label changes (5425-5430) move it automatically. **Confirmed for 5857.**
- The QA path can change the stage and then refuse with "nothing moved" (5517-5527).
- An edit attempt in PreToolUse can move the stage from build to QA and save it (5670-5671), so a check changes state as a side effect.
- The issue gate's state is per worktree (4982), but the loop state is shared (5245-5261), so the two gates disagree inside worktrees.
- Issues are counted twice, as the loop's "issues" (5478, 5747) and the issue file's "created" (5898).
- The issue-section check skips silently when the writing checker isn't available (6225), while the GitHub-tool path reports it (6049-6050).
- The commit gate stops early and only reports the problem when the issues file has one, so the autosave step after it never runs (6416-6420). **Confirmed.**
- The plan step count adds numbered lines and "### Step" headings, so one step can count twice (5006-5013; unverified).
- Any fenced block counts as evidence (6787-6789), so quoting code silences the claim check.
- One label text says "Claude completed this" (5952) while the house credit is "AjsAgent created this" (4935).

## Silent failures
- 6135 (git author lookup), 6180 (author guard), 6012-6013 (an unreadable `-F` body; the comment says the pull request check covers it, but that check covers only `gh pr create`), 6920-6923 (corrupt transcript lines skipped), 6279-6280 (issues cache read), 6225 (issue-section check).

## Structure
- Over 150 lines: `event_handover` (7592-7865, about 270). Close behind: `event_prompttimer` (about 120), `_loop_apply` (about 100), `event_harvest` (about 137).
- Dead code: `_check_page_saved` (7485) always returns an empty string, yet backs two checkpoint rows (7519-7520) **(confirmed)**. `_records_since_last_user_message` (6878-6882) is a thin wrapper. `_loop_record_issues` returns an empty list except on a problem (5749).
- Duplicated: `_dirty_files` (4822) and `_dirty_paths` (7007); `_repo_top` and `_issues_locate`; the same working-folder fallback at 5065, 5191, 5304, 5843, 5882 and 6508; issue-body reads at 6203-6209 and 6230-6236; the audit and userpromptaudit flows (6576-6623 and 6663-6696).
- Only the newest message is judged by the card (6764), plain summary (7696), writing (7747), long-reply (7746) and choices (7360) checks. Evidence and commit cover the whole turn.
- The page-block key is a hash of the user's text (7754), so the count resets on each new message.

## Hardcoded personal values
- 6101 the Ajw2003 noreply email; 6100 "AJ's agent"; 6183 and 5993 "Committed by AJ's agent".
- 5902 "Focus Deck".
- 4935 the label "AjsAgent created this"; 5952-5954 "Claude completed this".
- The branch prefixes `AjsAgent/` and `claude/` (6025-6027) and `worktree-agent-` (4727).
- Fixed doc paths: `docs/6-decisions/Decisions.md` (5319), `docs/4-systems` (5541), `docs/plans` (7210).
- claude.ai URLs (4898, 5984) and `house-rules@localhost` (4888).

## Natural split lines
- **Harvest** (7868-8283): independent; it needs only the emit and trace helpers.
- **Worktree autosave**, commitgate, worktreesweep and subagentcommit (4642-4924, 6344-6454, 6494-6544): one module on top of the git helpers at 4747-4924.
- **Issue workflow** (4925-5222, 5713-5931, 6254-6341): depends on `_issues_locate` and `_git_dir`.
- **Design loop** (5224-5695, 5832-5868): depends on the issue module for labels and the issue record.
- **Guards** for pull request, issue and credit text (5934-6242, 6022-6094): depend on the issue module for issue sections.
- **Waiting list and prompt timer** (4209-4576): independent, apart from a shared temp folder.
- **Stop handover** (6703-7865): the largest seam; it reads the loop, issues, writing, commit and transcript helpers.
