# Repo audit, 2026-11-05 (full)

A one-shot quality audit of the whole repo, run with the ponytail-audit skill. No code was changed;
every finding below is a proposal. Every finding was proved by running the real code, except where a
finding says "by reading". The page version is `docs/plans/2026-11-05-ponytail-audit.html`. This
replaces the first pass, `2026-11-05-ponytail-audit.md`, which read only part of the code.

**What this repo does:** It is aj's personal Claude Code plugin repo. Its main plugin, `house-rules`,
is a set of hooks (small programs Claude Code runs before and after each tool call) that load aj's
rules into every session, refuse risky commands such as deleting files or pushing to `main`, and
lock code edits until aj approves a design. Two younger plugins, `prompt-workshop` and
`agent-router`, share its shape.

**Load assumed:** one person, one session at a time, with at most two helper agents running beside
it. The guard hook runs once per shell command and took 95 ms per call when measured here, which is
fine at this load.

**Starting state:** `verify.py`, `tools/verify_tools.py`, `docref.py check` and
`plain_docs_check.py` all pass on this branch.

**How it was read:** the main session read `tools/`, the standalone scripts, the two offshoot
plugins, CI and the guard path of `safe_git.py`. Two forked helpers read `design_loop.py` with
`delegation.py`, and `core.py`, `docs.py`, `writing.py`, `hook.py` with the rest of `safe_git.py`.
The main session re-ran each helper's probe scripts and got the same results before listing them.

Paths below are relative to `claude-house-rules/plugins/house-rules/scripts/` unless they start with
`tools/`.

## Must fix

### 1. The guard approves a commit that runs any program inside it

- **Where:** `house_rules/safe_git.py:744-745`, `_only_git_statements` at `:384-387`
- **What this is:** On the agent's own branch, a routine commit gets an explicit "allow", which also
  skips Claude Code's own permission prompt.
- **Problem:** The check only looks at whether each statement starts with `git`. These three all got
  `allow`: `git commit -m "$(python3 /tmp/anything.py)"`, the same with backticks around a `curl`
  download, and `git -c core.hooksPath=/tmp/evil commit -m x`, which runs any script in that folder.
- **Fix:** Approve only when there is no `$(` or backtick outside the `$(cat <<'EOF'` message form,
  and no `-c core.hooksPath`. Otherwise give no decision, so Claude Code still asks.
- **If we skip it:** Anything wrapped in a commit command runs with no prompt at all.

### 2. Any merged pull request unlocks closing any QA-passed issue

- **Where:** `house_rules/design_loop.py:2123-2129`, `_close_repo_match` at `:1421`
- **What this is:** `gh issue close` is allowed only after "QA passed" and a merged pull request.
- **Problem:** A merge stamps every open closable record, whatever repo it is in and whether or not
  the pull request touches the issue. Closing `own/repo#5` was refused; after merging the unrelated
  `other/repo#99` it was allowed.
- **Fix:** Stamp only records in the merged pull request's repo whose issues it names with
  `Refs #N`. `_issues_guard` already parses that text.
- **If we skip it:** Issues close before aj has tested the work.

### 3. `/bin/rm -rf` and other delete forms get past the delete guard

- **Where:** `house_rules/safe_git.py:133`
- **What this is:** The guard spots a delete by finding the word `rm` with a space or line start
  before it.
- **Problem:** `/bin/rm -rf docs` is allowed, because a `/` before `rm` is excluded.
  `find docs -delete`, `unlink FILE` and `: > FILE` (which empties a file) are also allowed, because
  no pattern names them. `rm -rf docs` is refused, as it should be.
- **Fix:** Allow a `/bin/` or `/usr/bin/` path before `rm`, and add patterns for `find … -delete`,
  `unlink` and a bare `>` redirect onto an existing file.
- **If we skip it:** Files can be lost with no way back, just by writing the full path.

### 4. `git checkout HEAD -- FILE` and `git switch -f` throw away edits unasked

- **Where:** `house_rules/safe_git.py:143`
- **What this is:** The rule that refuses throwing away uncommitted edits, unless they are saved
  elsewhere.
- **Problem:** The pattern needs `--` straight after `checkout`. `checkout HEAD -- FILE`,
  `checkout HEAD FILE`, `checkout -f BRANCH` and `switch -f` / `--discard-changes` all got no decision.
- **Fix:** Widen it to `checkout\b.*(\s--(\s|$)|\s-f\b|--force)` and
  `switch\b.*(\s-f\b|--force|--discard-changes)`, keeping the saved-work exemption.
- **If we skip it:** Uncommitted edits are lost without a prompt.

### 5. Cloud sessions cannot commit to their own branch

- **Where:** `house_rules/core.py:2089` (`OWNED_BRANCH_PREFIXES`), note at `house_rules/safe_git.py:265-301`
- **What this is:** The branch prefixes the guard treats as the agent's own: `AjsAgent/`,
  `claude/`, `ccr-`.
- **Problem:** Cloud sessions are now given `agent/<name>` branches and told to push only there. The
  guard refused this session's commit on `agent/optimistic-planck-1h64c9`, so work can be committed
  only on a branch the session may not push.
- **Fix:** Add `"agent/"` to the prefixes, and treat it like `claude/` in `_agent_branch_block`.
- **If we skip it:** Cloud work stays unpushed, and is lost when the container is cleaned up.

### 6. The "ran twice" check counts reading or committing a script as running it

- **Where:** `house_rules/safe_git.py:464-478`
- **What this is:** It refuses the third run of a project script when no code commit happened in
  between.
- **Problem:** Any existing file word ending in `.py`, `.sh` and so on counts, so `cat`, `grep`,
  `sed`, `git add` and `git commit` naming the file all count. A second `sed -n` read of
  `safe_git.py` was refused during this audit.
- **Fix:** Count a file only when it is the first word, or the first argument of an interpreter such
  as `python`, `sh`, `bash`, `node` or `pwsh`.
- **If we skip it:** Normal reading and committing gets blocked, which pushes the agent to switch the
  check off.

## Should fix

### 7. A half-written stage file switches the code lock off

- **Where:** `house_rules/design_loop.py:109-111`, `:425-429`, `:1983`; `house_rules/delegation.py:908`,
  `:1215`; `house_rules/safe_git.py:550`, `:571`; `make_page.py:410`
- **What this is:** `.claude/house-rules-loop.json` holds the design stage that gates code edits;
  other state files hold the helper count and the rerun counts.
- **Problem:** Each is rewritten by emptying the file and writing it again, and the rerun file's temp
  name is shared by every process. A reader mid-write sees an empty file: an empty stage file gave
  "the design-loop lock is off for this call". Two hooks at once can also lose each other's update
  (by reading). The stage file is committed (18 KB, 51 commits), so a merge conflict in it leaves
  the lock off until someone repairs it by hand.
- **Fix:** In each writer, write to a temp file named with the process id, then `os.replace` it
  over the real file. About two lines each.
- **If we skip it:** The lock fails open now and then, and stays open after a conflicted merge.

### 8. The installer can wipe the user's `settings.json`

- **Where:** `tools/install.py:253`
- **What this is:** It adds three settings to `~/.claude/settings.json` and keeps every other key.
- **Problem:** It empties the real file and then writes the new content. If that stops half way (disk
  full, Ctrl-C, a crash), the user's own settings are gone, with no backup (by reading).
- **Fix:** Temp file plus `os.replace`, the same two lines as finding 7.
- **If we skip it:** A rare failure loses every setting made by hand.

### 9. The stage file can be overwritten from the shell

- **Where:** `house_rules/design_loop.py:432-457`
- **What this is:** Only aj's messages may move the stage, so writes to the file are refused.
- **Problem:** The refusal spots Write, Edit, `>`, `sed -i`, `tee` and Python or Node writes, but
  `cp FILE .claude/house-rules-loop.json` got no decision. `mv` and `git checkout REV -- FILE` get
  through the same way (by reading).
- **Fix:** Refuse any shell command naming `house-rules-loop.json`, except read-only ones and
  `git add` / `git commit`.
- **If we skip it:** The model can move itself into Build with one `cp`.

### 10. The two-helper cap lets a third helper through

- **Where:** `house_rules/delegation.py:940-981`, count added at `:369`
- **What this is:** `agentcap` refuses a third running helper.
- **Problem:** It reads the count, but the count only goes up later, when the helper starts. Three
  launch checks in a row on an empty state file were all allowed.
- **Fix:** Add a placeholder record in `agentcap`, keyed by the tool call's id, which `announce` then
  replaces. The stale-record timeout already cleans up leftovers.
- **If we skip it:** "At most two" holds only when helpers are started one at a time.

### 11. Autosave can push untracked files, secrets included, to GitHub

- **Where:** `house_rules/delegation.py:1252`, `:1259-1290`
- **What this is:** On helper worktree branches, autosave snapshots the work to a hidden ref and
  force-pushes it about once a minute.
- **Problem:** The snapshot uses `git add -A`, so every untracked file that is not gitignored goes
  to origin, such as a token file or a data dump a helper wrote. Anyone who can read the repo can
  fetch hidden refs. Found by reading: a run would push to the real remote.
- **Fix:** Snapshot tracked changes only (`git add -u`), plus files the helper wrote with the Write
  or Edit tools.
- **If we skip it:** A secret a helper wrote could leak within a minute.

### 12. The version check "updates" a newer copy back down

- **Where:** `house_rules/core.py:1327`, `:1338`
- **What this is:** At session start it compares the running version with the marketplace and
  GitHub, and updates on a difference.
- **Problem:** It compares with `!=`, not "older than". A running 2.75.0 against a published 1.0.0
  ran `claude plugin update` (a stand-in command in the test) and told the model it was out of date.
- **Fix:** Compare with the existing `_version_tuple` (`core.py:479`): update only when installed is
  older.
- **If we skip it:** A branch build that is ahead of `main` gets nagged or downgraded at every
  session start.

### 13. The installer's file-for-file check always finds a difference

- **Where:** `tools/_plugin_sync.py:22-29`
- **What this is:** `install.py` and `force_update.py` hash every installed file against the source.
- **Problem:** After the first hook runs, the installed copy holds `scripts/.python-cache` and
  `__pycache__` folders that the source never has. Both exist in this session's installed copy. So
  every re-run of `install.py` uninstalls and reinstalls for nothing.
- **Fix:** Skip `__pycache__` folders, `.pyc` files and `.python-cache` in `tree_hash`, as
  `tools/clean_install_test.py:302-305` already does.
- **If we skip it:** Every update does a needless uninstall, which leaves no guard for a moment.

### 14. The page builder's node check can fail a page wrongly

- **Where:** `make_page.py:569-578`
- **What this is:** After building a page, it screenshots it with Playwright, through Python or node.
- **Problem:** The node probe looks for `playwright` from the current folder, but the check runs
  from a temp file in `/tmp`, which looks elsewhere. With `playwright` only in a project's
  `node_modules`, the probe found it and the real run failed with `Cannot find module 'playwright'`,
  which the builder reports as "visual check found problems". The temp file is also never deleted.
- **Fix:** Run the script with `node -e` (or write it inside the project), and delete the temp file
  afterwards.
- **If we skip it:** On a machine with no Python Playwright, page builds exit 2 for no reason.

### 15. "Does this commit include every file?" is answered two ways

- **Where:** `house_rules/docs.py:208` and `house_rules/safe_git.py:1539`
- **What this is:** Two patterns, both named `_COMMIT_ALL_RE`, decide whether a commit uses `-a`.
- **Problem:** For `git commit -sam x` and `git commit -qa -m x`, the docs check says no and the
  link check says yes, so the "code changed but no docs" reminder is skipped for those forms.
- **Fix:** Keep the `safe_git.py` pattern, move it to `core.py`, and import it in both places.
- **If we skip it:** Some commits skip the docs reminder for no reason.

### 16. `force_update.py` can leave the plugin uninstalled

- **Where:** `tools/force_update.py:82-83`
- **What this is:** It uninstalls the plugin, then installs it again.
- **Problem:** If the install fails (network down, for example), it stops with "Reinstalling failed",
  and doesn't say the plugin and its guard are now gone (by reading).
- **Fix:** On that failure, print that the plugin is uninstalled and the exact command to install it.
- **If we skip it:** A failed update quietly leaves the machine with no guard.

### 17. No test covers findings 1 to 7 or 10

- **Where:** `checks/safe_git.py`, `checks/design_loop.py`, `checks/delegation.py`
- **What this is:** The hook test cases.
- **Problem:** No case covers a `$(…)` commit, `/bin/rm`, `find -delete`, `checkout HEAD --`,
  `switch -f`, an `agent/` branch, `cat x.py` against the rerun count, a two-repo merge stamp, an
  empty stage file, or helpers launched together. That is why every suite passes with these holes.
- **Fix:** One case each, added in the same change as each fix.
- **If we skip it:** The holes come back after the next pattern edit.

## Nice to have

### 18. `diff_parts.py` miscounts lines that start with `--` or `++`

- **Where:** `tools/diff_parts.py:68-75`
- **What this is:** It splits a file's diff into the functions or headings it touched, and promises
  totals that match `git diff --numstat`.
- **Problem:** It skips any line starting `+++` or `---`, not just the two header lines. Removing a
  Markdown `---` rule counted 1 removed line where `numstat` says 2.
- **Fix:** Skip `---`/`+++` only before the first `@@` line.
- **If we skip it:** Pages built from it show wrong line counts.

### 19. Dead code

- **Where:** `clarity.py:196`, `hook.py:191` (with its uses at `:202` and `:219`),
  `house_rules/design_loop.py:1873-1874` and `:1912-1913`, and about 55 blank lines in
  `house_rules/safe_git.py` (255-260, 328-332, 1196-1205, 1508-1516, 1816-1830, 1836-1846).
- **What this is:** Lines left over from earlier moves.
- **Problem:** `clarity.py:196` is overwritten by the next line. The `writing` list in `hook.py` is
  never filled. The two checkpoint rows use `_check_page_saved`, which always returns `""`; the
  2026-10-16 audit already flagged them.
- **Fix:** Delete them. Check the other callers of `_writing_note` before deleting its `if writing:`
  branch.
- **If we skip it:** Readers keep tracing code that does nothing.

### 20. One-off checks that nothing runs, and small copies

- **Where:** `tools/check_verify_inventory.py` (304 lines), `plain_docs_check.py:136-153`,
  `tools/install.py:351-352`
- **What this is:** A checker for the finished split of `verify.py` into parts, a second Markdown
  fence parser, and the installer's failure count.
- **Problem:** Nothing runs `check_verify_inventory.py`, neither CI nor `tools/verify_tools.py`, so it
  guards nothing. The fence parser in `plain_docs_check.py` closes a fence on any fence line, where
  `docref.py`'s `_fence_step` gets it right. `install.py` counts a failed self-heal twice.
- **Fix:** Delete the checker (or add it to CI if the table must stay true), reuse `_fence_step`, and
  drop the extra `failures += 1`.
- **If we skip it:** About 320 lines that cost reading and pass no judgement.

## Verdict

The guard has real holes. Fix 1 first (it skips the user's own prompt), then 3 and 4 (data lost with
no prompt), then 2 and 5.

**Lean:** about −380 lines possible (304 of them `check_verify_inventory.py`, 55 blank lines, the
rest dead code; the figure is approximate because reusing `_fence_step` adds a few lines back), and
no dependencies to remove.

## Not checked

- Not read in full: the test files under `checks/` (about 11,000 lines), which were searched to see
  what is covered; `tools/verify_tools.py`, which is a test file; and the Markdown rules, agents and
  HTML templates, which are not code.
- Not run: the autosave push (finding 11), because it would push to the real remote; the
  `handover_links_owed` and `rclink` paths, which only run in project threads this session doesn't
  have; and the Windows `del` / `Remove-Item` forms, because no PowerShell is installed here.
- Left behind by the probes: `/tmp/house-rules-outdated-vcprobe.json` and
  `/tmp/msg-with-claude-credit.txt`. The guard refused deleting them. The marker matches only the
  made-up session id `vcprobe`, so no real session reads it.
