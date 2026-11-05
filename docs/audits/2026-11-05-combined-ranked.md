# Combined audit findings, ranked, 2026-11-05

One list of everything found on 2026-11-05, ranked by how much harm each finding does, with an order
for fixing them. It merges three reports and adds a fourth pass:

| Prefix | Source | Findings |
|---|---|---|
| A | Full repo audit, `2026-11-05-ponytail-audit-full.md` | 20 |
| D | Design loop deep dive, `2026-11-05-design-loop-deep-dive.md` | 12 |
| U | Design loop usability audit, `2026-11-05-loop-usability-audit.md` | 9 (1 to 8, plus 2b) |
| H | Hook friction pass, this document (below) | 5 |

That is 46 numbers but 45 separate findings, because U8 is the same as A6. The finding numbers are the ones each report uses, so "A6" is finding 6 of the full audit. No code was
changed. The page version is `docs/plans/2026-11-05-combined-ranked.html`.

## The hook friction pass (H)

**What was tested:** all 17 hooks that run before or after a tool call (`hooks/hooks.json`). Each was run the way
Claude Code runs it, as `hook.py <name>` with the JSON payload on stdin, in a throwaway repo on an
`AjsAgent/` branch with the agent's git identity set. 25 routine shell commands and 6 routine file
writes were tried. The script is not committed, because it is a one-off.

### H1. A commit message or an `echo` that mentions a dangerous command is refused

- **Proved:** `git commit -m "fix: rm -rf no longer deletes docs"` was refused as a delete, and
  `git commit -m "docs: explain git push --force risk"` was refused as a force push.
  `echo 'never run rm -rf /' > notes.txt` was refused as a delete. During this work, three more
  commands were refused for text inside a heredoc or a search pattern (U6).
- **Why it ranks high:** the commit for any fix in this list would describe the command it fixes, and be refused.

### H2. Unstaging a file is refused

- **Proved:** `git restore --staged src/app.py` and `git reset HEAD src/app.py` were both refused as
  throwing away work. Both only take the file out of the next commit, and the edits stay on disk.
- **Cause:** the restore and reset patterns in `house_rules/safe_git.py:113` and `:143` don't tell
  `--staged`, or a reset of named paths, apart from a hard reset.

### H3. The rerun counter blocks `git add`

- **Proved:** after `git restore`, `git reset`, `mv` and `cp` had each named `src/app.py`,
  `git add src/app.py` was refused: "`src/app.py` has run twice since the last commit that changed code".
  This is A6 at its worst, because it blocks the commit that would reset the counter.

### H4. Every call pays for six to nine hook processes

- **Measured:** each shell command started 6 hook processes (2 before it runs, 4 after), which took
  347 to 490 ms in all. Each file write started 9 processes, which took 424 to 636 ms. In Build, every
  edit also reads each issue's labels from GitHub, which took 380 to 576 ms here and is allowed 5 seconds.
- **Effect:** about 40 seconds of waiting per 100 shell commands, measured on this container. It's
  low severity, but it is why "merge the small hooks into one process" belongs on the list.

### H5. Plain text and data files are locked like code

- **Where:** `house_rules/design_loop.py:197` (`_is_source_path`): only `docs/`, `.claude/` and `.md` files are open.
- **Proved:** in the Design stage, writing `notes.txt` from the shell was reported as a code write. A
  `.txt`, `.csv` or `.json` file outside `docs/` would be refused for the Write tool in the same way
  (by reading).

## Severity levels

1. **Critical:** something runs, leaks or is lost with no prompt, or someone other than aj can move the loop.
2. **Blocks work:** routine work stops, or the only way on is a handoff or switching a check off.
3. **Lock bypass:** the model, not an outsider, can step around the code lock.
4. **Wrong result:** a check gives the wrong answer, but nothing is lost.
5. **Minor:** tooling, cost, tidying.

Level 2 sits above level 3 for a reason. When a check blocks routine work, the way out is
`HOUSE_RULES_...=off`, and that turns off every protection the check gives, not just the one that got
in the way.

## The ranked list

### Level 1: Critical

| # | Finding | Why it's critical |
|---|---|---|
| A1 | The guard approves a commit carrying `$(...)`, backticks or `-c core.hooksPath` | Any program runs with no prompt at all |
| A11 | Autosave pushes untracked files to GitHub | A stray token file ends up on the remote |
| D1 | A GitHub comment event or a scheduled reminder can approve a stage | Anyone who can comment on a pull request can write "QA passed" |
| A3 | `/bin/rm -rf`, `find -delete`, `unlink` and `: > file` get past the delete guard | Files lost with no way back |
| A4 | `git checkout HEAD -- FILE` and `git switch -f` discard edits unasked | Uncommitted edits lost |
| U5 | `git worktree remove --force` gets no decision | A helper's uncommitted work lost |
| A8 | The installer can empty `settings.json` if a write fails | Every hand-made setting lost |

### Level 2: Blocks work

| # | Finding | What stops |
|---|---|---|
| A5 | `agent/` branches aren't the agent's own | Cloud sessions can't commit where they must push |
| U4 | Every folder delete is refused, and the suggested `_to_delete/` move frees nothing | A session out of disk must hand off |
| U1 | A new session needs every approval again, and two new issues | Each handoff costs aj two approvals and leaves duplicate issues |
| U2b | Issues made by a script or a one-line loop aren't counted | "Build plan approved" is refused while the issues exist |
| A6 + H3 + U8 | Reading or naming a script counts as running it | `sed`, `cat` and `git add` are refused |
| U6 + H1 | Text in quotes, heredocs and commit messages is read as a command | Commits that describe a fix are refused |
| H2 | Unstaging is refused | Taking a file out of a commit needs a workaround |
| U7 | A cloud session's first commit is refused three times | Three wasted turns per session |
| U2 | An approval is saved only when the model pushes | A session that stops early loses it |

### Level 3: Lock bypass

| # | Finding |
|---|---|
| D10 | Shell writes to source files are only reported (off on purpose since #309) |
| D3 | Writing the old `.git/house-rules-loop.json` opens Build in a new project |
| D4 | `.claude/settings.json`, `.claude/worktrees/` source files and code under `docs/` are open in every stage |
| A9 | `cp`, `mv` or `git checkout REV --` can overwrite the stage file |
| A7 | A half-written stage file turns the lock off |
| D2 | A question or a "don't" that quotes an approval moves the stage |
| D9 | Switching to an old branch brings back its stage |
| A2 | Any merged pull request unlocks closing any QA-passed issue |
| A10 | Three helpers launched together all pass the two-helper cap |

### Level 4: Wrong result

| # | Finding |
|---|---|
| D5 | Re-approving a design in Build strands the feature's issues |
| D6 | Feature names in approvals are never checked |
| D7 | "skip design" outlives its stage and goes to the wrong edit |
| D8 | Any claude.ai artifact link counts as the QA page |
| U3 | `main` carries a merged feature's QA stage |
| A12 | The version check "updates" a newer copy down |
| A16 | `force_update.py` can leave the plugin uninstalled without saying so |
| A13, A14, A15 | Installer diff always differs; page builder's node check can fail wrongly; two commit `-a` checks disagree |
| D11, D12 | "Labelled" is a text search; an unsigned-in `gh` failure is recorded as a label change |
| H5 | `.txt`, `.csv` and `.json` files are locked like code |

### Level 5: Minor

| # | Finding |
|---|---|
| A17 | No test covers the holes (fixed as part of each step below, not on its own) |
| H4 | Six to nine hook processes per call, about 0.35 to 0.65 s each time |
| A18, A19, A20 | `diff_parts.py` miscount, dead code, one-off checks nothing runs |

## What to do first

Each step is one feature with its own issues, and every fix lands with the `verify.py` case that would
have caught it (A17).

1. **Close the critical holes.** A1, A3, A4 and U5 are all patterns in `safe_git.py`. A11 needs
   `git add -u` plus the files the helper wrote, and A8 needs the temp-file-and-`os.replace` write. D1
   needs four more markers in `_RELAYED_PROMPT_RE`. These are the only findings where harm needs no
   mistake by aj. Nearly all of them are small pattern or two-line changes, but that size was estimated, not counted.
2. **Stop the guard blocking routine work.** A5, A6 with H3, U6 with H1, H2 and U7. One condition comes
   with U6 and H1. Strip only single-quoted text and heredocs with a quoted delimiter (`<<'EOF'`),
   because `$(...)` inside double quotes still runs, and that is A1's hole. This step comes second, not
   last, because each of these blocks gets the checks switched off.
3. **Fix the two problems aj named.** U4: allow folder deletes that git or an install can undo. U1,
   U2 and U2b: "Continue from: <branch>", "Issues for <feature>: #N", issue recording that sees loops
   and `gh api`, and a push straight after each approval.
4. **Close the lock's side doors.** D3, D4, A9, A7, D2, then D9 and A2. D10 stays with the restructure
   that switched it off, but it should get its own issue so it isn't forgotten.
5. **Make approvals do what aj said.** D5, D6, D7, D8 and U3.
6. **Tidy up.** Level 4's tooling findings, then level 5.

## Not checked

- A commit failing on a full disk (U2): filling this container's disk would end the session.
- Whether Claude Code sets an `origin` field for scheduled or event-driven prompts (D1).
- When a change to `.claude/settings.json` reaches running hooks (D4).
- The hook timings in H4 are from this container. On aj's own machine they will differ, and they
  weren't measured there.
