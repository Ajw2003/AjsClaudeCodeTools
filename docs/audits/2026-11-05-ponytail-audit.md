# Repo audit, 2026-11-05 (first pass)

**Superseded:** this first pass read only part of the code. The full audit, with every file read,
is [2026-11-05-ponytail-audit-full.md](2026-11-05-ponytail-audit-full.md).

A one-shot quality audit of the whole repo, run with the ponytail-audit skill. Nothing was changed
by it; every finding below is a proposal.

**What this repo does:** It is aj's personal Claude Code plugin repo. Its main plugin,
`house-rules`, is a set of hooks (small programs Claude Code runs before and after each tool call)
that load aj's rules into every session and refuse risky commands, such as deleting files or
pushing to `main`. Two younger plugins, `prompt-workshop` and `agent-router`, share its shape.

**Load assumed:** one person, one session at a time, with at most two helper agents running
beside it. The guard hook runs once per shell command; it measured about 95 ms per call here,
which is fine at this load.

**Starting state:** `verify.py` and `tools/verify_tools.py` both exit 0 on this branch.

## Must fix

### 1. `/bin/rm -rf` gets past the delete guard

- **Where:** `claude-house-rules/plugins/house-rules/scripts/house_rules/safe_git.py:133`
- **What this is:** The guard spots a delete by looking for the word `rm` with a space or a line
  start in front of it.
- **Problem:** The character in front may not be `/`, so `/bin/rm -rf docs` is allowed with no
  prompt at all. `rm -rf docs` is refused, as it should be. The same gap lets `find docs -delete`,
  `unlink FILE` and `: > FILE` (which empties a file) through, because no pattern names them.
- **Fix:** Allow a `/` path in front of `rm` (for example `(^|...|[^0-9A-Za-z_.-]|/(usr/)?bin/)rm`),
  and add `find\b.*\s-delete\b`, `\bunlink\s` and a `:?\s*>\s*\S` redirect pattern to the delete
  bucket. Add one `verify.py` case per pattern.
- **If we skip it:** The safety net the plugin promises has a hole that a model can fall into
  just by writing the full path, and the files go with no way back.

### 2. `git checkout HEAD -- FILE` and `git switch -f` throw away edits unasked

- **Where:** `claude-house-rules/plugins/house-rules/scripts/house_rules/safe_git.py:143`
- **What this is:** The "throws away uncommitted edits" rule catches `git checkout -- FILE` and
  `git restore`, and lets them run only when the work is saved elsewhere.
- **Problem:** The pattern needs `--` straight after `checkout`. `git checkout HEAD -- FILE`,
  `git checkout HEAD FILE`, `git checkout -f BRANCH` and `git switch -f` (or
  `--discard-changes`) do the same damage, and the guard returns no decision for any of them.
- **Fix:** Widen the pattern to `checkout\b.*(\s--(\s|$)|\s-f\b|--force)` plus
  `switch\b.*(\s-f\b|--force|--discard-changes)`, keeping the existing saved-work exemption.
- **If we skip it:** Uncommitted edits are lost without a prompt, which is the exact case this
  rule exists for.

### 3. The "ran twice" check counts reading or committing a script as running it

- **Where:** `claude-house-rules/plugins/house-rules/scripts/house_rules/safe_git.py:464-478`
- **What this is:** The rerun check refuses the third run of a project script when no code
  commit happened in between, to stop retry loops.
- **Problem:** It counts any word in the command that ends in `.py`, `.sh` and so on and names
  an existing file. So `cat x.py`, `grep foo x.py`, `git add x.py` and `git commit ... x.py` all
  count as runs. During this audit, a second `sed -n` read of `safe_git.py` was refused with
  "has run twice". The third `git add` or `git commit` naming the same file would be refused too.
- **Fix:** Count a script only when it is the command itself (the first word) or the first
  argument of an interpreter (`python`, `python3`, `py`, `sh`, `bash`, `node`, `pwsh`). That is a
  small check on `words[0]` inside the existing loop.
- **If we skip it:** Normal reading and committing gets blocked, which teaches the agent to work
  around the guard or to switch it off.

## Should fix

### 4. The installer can wipe the user's `settings.json`

- **Where:** `tools/install.py:253`
- **What this is:** `apply_settings` adds the plugin's settings to `~/.claude/settings.json` and
  keeps every other key.
- **Problem:** It opens the real file for writing, which empties it first, then writes the new
  JSON. If the write stops half way (disk full, Ctrl-C, a crash), the user is left with an empty
  or broken settings file and no copy of the old one.
- **Fix:** Write to `settings_path + ".tmp"` and then `os.replace` it over the real file, the
  same pattern `safe_git.py:550` already uses. Two lines.
- **If we skip it:** A rare failure loses every setting the user made by hand.

### 5. Two hooks at once can corrupt the rerun state file

- **Where:** `claude-house-rules/plugins/house-rules/scripts/house_rules/safe_git.py:550` and `:571`
- **What this is:** The rerun check saves its counts to one JSON file in the git folder, through
  a temp file.
- **Problem:** The temp file always has the same name, `<state>.tmp`. When two agents run a
  command at the same moment (the rules allow two helpers), both write that one temp file, and
  the result can be mixed JSON. After that, every guard call fails to read it and adds a
  "could not be checked" note, until someone deletes the file.
- **Fix:** Name the temp file per process, for example `"%s.%d.tmp" % (path, os.getpid())`.
- **If we skip it:** The rerun check quietly stops working for that repo, and every command
  carries a warning.

### 6. No test covers findings 1 to 3

- **Where:** `claude-house-rules/plugins/house-rules/scripts/checks/safe_git.py`
- **What this is:** The guard's test cases.
- **Problem:** No case checks `/bin/rm`, `find -delete`, `git checkout HEAD --`, `git switch -f`,
  or that `cat x.py` does not count as a run. That is why `verify.py` passes with all three holes.
- **Fix:** Add one case per command above to the existing table, in the same change as each fix.
- **If we skip it:** The holes come back unnoticed after the next pattern edit.

## Verdict

The guard has real holes. Fix 1 and 2 first, since they let data be lost with no prompt, then 3,
because it blocks normal work.

## Not checked

- Read in full: `run.sh`, the guard path in `safe_git.py` (patterns, guard, delete and rerun
  checks), the settings write in `tools/install.py`.
- Probed by running: 23 commands through the real guard hook, using a scratch copy of the
  payload format.
- Not read: `design_loop.py`, `delegation.py`, `docs.py`, `writing.py`, `make_page.py`,
  `docref.py`, `plain_docs_check.py`, the session-ledger tools, and both offshoot plugins beyond
  a diff. The near-copy code between the two offshoots is deliberate (they install separately),
  so it is not listed.
- Not tested: the Windows commands (`del`, `Remove-Item`) on real PowerShell, since no PowerShell
  is installed here.
