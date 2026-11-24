# Codebase review: AjsClaudeCodeTools (2026-11-24)

Criteria from aj: be critical of actual flaws, contradictions, over-engineering, and above all bad, slow, sloppy, inefficient or very large (hundreds of lines) spaghetti code that could be modular and extensible.

Mode: codebase. Eight reviewer runs, one at a time, each run with real commands where it could (timings, hook calls, test runs). Where a finding comes from reading code and not from a run, the reviewer said so and it is marked *(read, not run)*.

## What was and was not reviewed

| Reviewed | Batches |
|---|---|
| `claude-house-rules` scripts | 11, 12, 13, 14, 15, and 16+17+18 together |
| `tools/` plus `verify.yml` and `marketplace.json` | tools 1+2+3 together |

| Not reviewed | Why |
|---|---|
| `docs` batches 1-98 (583 prose files) | Prose, not code. Skipped to keep the review on what aj asked about. |
| `claude-house-rules` batches 1-10 and 19 (agent/command/rules/skill `.md`, templates) | Prose and templates. Only checked where a script's claim could be tested against them. |
| `.claude`, `.claude-plugin` (checked only for contradictions), `_to_delete`, root files | Config and notes. |
| `claude-agent-router` 1-2, `claude-prompt-workshop` 1-2 | aj said they are not in production. |

Batches 16, 17 and 18 were merged into one reviewer, and tools 1, 2 and 3 into one. This is a deviation from "one reviewer per batch".

## Verdict

**The biggest problem is size and shape, not any one bug.** About 39,000 lines of Python hold the plugin. Nine files are 2,000 to 4,000 lines each. Every one is a flat module with no seams the code itself respects.

| File | Lines | What it is |
|---|---|---|
| `scripts/checks/design_loop.py` | 3,980 | Test script, one global namespace |
| `scripts/house_rules/core.py` | 3,892 | Engine, 175 functions, 66 regexes |
| `scripts/house_rules/design_loop.py` | 3,612 | Engine, 140 functions |
| `scripts/checks/core.py` | 3,054 | Test script |
| `scripts/checks/delegation.py` | 2,484 | Test script |
| `scripts/house_rules/delegation.py` | 2,333 | Engine |
| `scripts/house_rules/safe_git.py` | 2,332 | Engine, only about 40% is git |
| `scripts/checks/docs.py` | 2,317 | Test script |
| `scripts/checks/safe_git.py` | 2,229 | Test script |

The `checks/` and `house_rules/` files share names and sizes but do **not** duplicate each other: `checks/` are verify.py's test parts and `house_rules/` is the hook engine.

**The safety guard has real holes**, proven by running commands through the real hook (finding 1, 2).

**Every tool call pays for the size.** The hook engine imports about 14,000 lines before it looks at the event name (66 ms against 14 ms for bare Python), starts up to 9 hook processes for one Write, and one hook makes 5 serial network calls (finding 4, 5).

## Counts

The seven reviewer runs each reported between about 15 and 25 findings. I did not tally them exactly or by severity, so no total is given. The top 12 are written out in full; the rest are grouped by area below, with every high and medium finding included and the minor lows summarised.

## Top findings, worst first

### 1. [high] The destructive-command guard is regex over text and is bypassed by ordinary quoting
`house_rules/safe_git.py:85-168`, `:93-104`, `:471-486`, `:154`, `:351-362`. Each result below was run through the real hook. `allow*` means the hook printed nothing, so no house rule fired.

| Command | Result | Why it matters |
|---|---|---|
| `git push origin +HEAD:someone-else` | `allow` (explicit) | Force-overwrites another branch; the guard approves it, skipping Claude Code's own prompt too |
| `git reset --hard HEAD --` | `allow*` | Real git ran it and lost a dirty edit |
| `git checkout keep.txt` | `allow*` | Discards uncommitted edits |
| `'rm' -f keep.txt`, `$(which rm) -f ...` | `allow*` | Quotes and substitution defeat the pattern |
| `git cl''ean -fdx`, `git -c alias.x=clean x -fdx` | `allow*` | Same |
| `git branch -d -f other`, `-Df`, `-f other HEAD~1`, `update-ref -d`, `reflog expire` | `allow*` | Not in the lists |
| `echo 'rm -rf docs' \| sh`, heredoc into `sh` | `allow*` | Text "treated as harmless" is not harmless when piped to a shell |
| `grep rm notes.txt` | `deny` | False block: the word `rm` anywhere counts as a delete |

Fix: one tokenizer (`shlex` with punctuation) that strips quotes and splits statements, then rules written as data, `(command, subcommand, flags) -> reason`, matched on argument lists.

### 2. [high] The design-loop lock on `.claude/house-rules-loop.json` only catches the literal file name
`house_rules/design_loop.py:577-651`. `cp /tmp/x .claude/house-rules-loop.json` is denied, but `.claude/house-rules-l*.json`, `...loop.js?n`, and a Python one-liner building the name from two strings all give `allow*`. That file is what opens code edits, so the gate can be opened by hand. Also `:1605`: `gh api -XPATCH repos/o/r/issues/5 -f state=closed` (no space after `-X`) is allowed; `-X PATCH` is denied. Fix: refuse any shell write to `.claude/` whose target is a glob or unreadable, or keep an approvals hash in the file.

### 3. [high] A test case that throws kills every case after it, and the suite hides it
`checks/design_loop.py`, `core.py`, `delegation.py`, `docs.py`: each is one flat module-level script. If `design_loop.py:763` raises (it slices a phrase out of the engine's own source), about 3,200 lines of later cases never run. `tools/verify_tools.py:101-828` has the same shape (840 lines, no functions). Fix: wrap each section in `def case_<topic>()` and add a runner in `common.py` that turns an exception into one FAIL with its traceback.

### 4. [high] Every hook call imports all 7 parts (about 14,000 lines) before it reads the event name
`hook.py:52-59, 340-348`. Measured: 66 ms for an unknown event against 14 ms bare Python; 170 ms with no bytecode cache. One Write tool call starts 9 hook processes (about 630 ms of interpreter time); one Bash call starts 6 (about 330 ms). Adding one event takes 6 edits in 3 files. Fix: map each event to `(module, function)` and load it with `importlib`; run all Pre-hooks for a tool in one process.

### 5. [high] `commitgate` makes 5 serial network calls on every Write, Edit and Bash
`delegation.py:1661-1663` calling `design_loop.py:745`. Measured 748 ms for 5 `gh api repos/.../issues/N` reads. The comment at `design_loop.py:733` says "the reads run in parallel"; the timing says they do not. Fix: cache labels per issue for about 60 seconds, or at least use a thread pool.

### 6. [high] A paid model call (`claude -p --model haiku`) runs on nearly every Stop
`core.py:3837-3854`. `roadblock_check` runs the judge whenever the reply has no roadblock phrase and no "NEEDS YOU", which is nearly every reply. Each turn pays for a model call and up to 22 seconds. Fix: run it only when a cheap phrase screen finds a candidate, or put it behind an opt-in switch. *(Not timed; a live call costs money.)*

### 7. [high] The hook log drops entries under parallel hooks
`core.py:100-118`. `_log_line` reads the whole file and rewrites it with no lock, and Claude Code starts hooks in parallel. Measured: 320 concurrent writes left 5 lines. This is the log behind the "nothing fails silently" rule. Fix: open in append mode, one write per line, trim occasionally.

### 8. [high] `make_page.py` never checks its own output
`make_page.py:543-630`, `page_criteria.py:143`. An unedited starter with 16 to 21 `<replace:` placeholders builds with exit 0, passes the criteria check and prints "SEND THIS PAGE NOW". `page_criteria.check()` skips any file whose first 4,096 characters contain the builder's comment, so a two-line forged file passes `--type review`. With the mark removed, the built review page fails its own rule ("no finding"). Fix: refuse to build while any `<replace:` remains, write the finding marker, and run `page_criteria.check()` on the output. Also `:822-826`: `style --quick` overwrites an approved `docs/page-style.json` with defaults without asking.

### 9. [high] `waitfor.py` cannot do what the wait rule says
`waitfor.py:90-100` against `rules/waits.json`. First check and deadline are both 60 s, so exactly one check runs and it gets a 1-second cap. Reproduced at 3 s scale: a check that takes 1.5 s reports "timed out", exit 3. Stall detection (3 quiet checks) can never fire. Fix: reject a config where `first + (stalled_after-1)*interval > deadline`, and give each check `min(interval, left)`.

### 10. [high] `run.sh` fails open where its header says it fails closed
`run.sh:68-77`: a cached `python3` is trusted without re-probing. With the Windows Store stub first on PATH, `guard` returned exit 0 and the install message, so the guard passed everything. With no Python at all, `noask`, `agentcap`, `sendcheck`, `pagecheck` and `handover` exit 0 with no output (`run.sh:105-162`).

### 11. [high] `tools/`: five scripts do one install job, and two disagree about the source string
`install.py`, `force_update.py`, `use_branch.py`, `clean_install_test.py` and `update.bat` each restate the `claude` CLI sequence. Constants and `run_claude` are copied word for word. `use_branch.py:24,38,49` adds the marketplace as `Ajw2003/AjsClaudeCodeTools`; `install.py:49-52` and `clean_install_test.py:26-29` say that form conflicts with the `.git` URL and the CLI refuses it *(read, not run)*. `install.py:116-144` ignores both return codes in its self-heal, so a failed install after a successful uninstall leaves the machine with no guard hooks. Fix: one `_plugin_cli.py` with the constants, `run_claude`, `reinstall`, `locate_installed`.

### 12. [high] `verify_tools.py` reports a broken `use_branch` as a skip
`verify_tools.py:793-797`: `SystemExit` becomes `SKIP`, and the final line says "all 55 checks passed" without counting skips. CI has no `claude`, so it skips there every time. Also `:14-16` says nothing shells out to the `claude` CLI, but `:794` runs the real `claude plugin uninstall/install/update` against GitHub (most of the 7.5 s run).

## Other findings by area

Paths are under `claude-house-rules/plugins/house-rules/scripts/` unless noted.

### Hook engine (`house_rules/`, `hook.py`)
- [medium] `core.py:1629-1642`: `event_scope` has no per-hook try, so one failing hook drops every clause; the comment at `:1627` claims the opposite. The comments at `core.py:1569` and `hook.py:29` say scope "cannot fail" and "reads no file"; it reads and writes the mode files.
- [medium] `hook.py:118-283`: `event_handover` is 166 lines with 20 local flags and a 15-term `not ... and not ...` test that must mirror the parts list by hand.
- [medium] `hook.py:340-383` and `run.sh`: failure rule per event lives in three places (run.sh case list, an if-chain, the docstring).
- [medium] `core.py:3710-3818`: `_goal_check` and `_judge_check` are copy-paste twins (about 25 lines each).
- [medium] `bigfiles.py:30, 119-124`: `Library`, `Temp`, `obj` match any path segment, so `src/Library/util.py` is refused as "regenerated".
- [medium] `bigfiles.py:161-170`: an unreadable stage file produces "aj has not approved it", which is false.
- [medium] `safe_git.py:815-1101`: `_event_guard_main` is 287 lines; the "append to additionalContext" block is copied 6 times.
- [medium] `safe_git.py:140, 148`: `: > newfile.log` is denied although no file exists; guardwrite refused to rewrite the reviewer's own scratchpad file.
- [medium] `design_loop.py:1174`: `_loop_apply_one` is 155 lines with three approval branches inline; a regex-to-handler table would do.
- [medium] Two shell-write parsers exist, `design_loop.py:251` and `safe_git.py`, and `_HEREDOC_RE` exists twice with different patterns.
- [medium] `core.py:2742-2872`: both mode files are read 3 times per hook call.
- [low] `bigfiles.py:402-408` bare `except: pass`; `core.py:159-162` duplicate imports; `hook.py:186` rebuilds a regex that `core._SESSION_ID_RE` already holds; `core.py:1708` reads JSON fields with a regex (wrong for Windows paths); `design_loop.py:3550` reads the whole transcript on every Stop; `session_triage.py` is an empty placeholder nothing imports; `writing.py:158` matches plan pages by base name only.

**Where the big files should split** (seams already marked by the code's own section headers):

| File | Split into |
|---|---|
| `core.py` 3,892 | io, session_start, versioncheck (about 535 lines run once per session but compiled into every call), registry (10 `register_*` lists to one table), gitutil and switches, transcript and evidence, roadblocks |
| `design_loop.py` 3,612 | shell_writes (shared with safe_git), loop_state, loop_approvals, loop_gate, issue_records, issue_guards, checkpoints, closable_merge |
| `safe_git.py` 2,332 | guard_rules, rerun_wait, delete_safety, prompt_timer (nothing to do with git), attribution, handover_checks |

### Test parts (`checks/`)
- [high] `common.py:425-837`: importing `common` takes 1.1 s and runs hooks, builds about 5 fixture repos and execs `hook.py` for every part, whether it needs them or not. Fix: lazy `lru_cache` functions.
- [high] `checks/safe_git.py:2054`: checks 254-256 run the noask hook against the live checkout's design-loop stage. Reproduced: "3 of 282 checks failed" while this repo is in Build. `checks/writing.py` alone gave 3 false FAILs because isolation from the mode file exists only in `verify.py`.
- [high] `checks/safe_git.py:1253`: `_ggd` returns "allow" for empty or non-JSON output, so a guard that crashes passes every allow case.
- [medium] `docs.py:2028-2047`: the "every section has a check" test passes if a name appears anywhere in any `checks/*.py`, comments included.
- [medium] The same "send a prompt, parse `additionalContext`, return empty on any exception" helper is written about 9 times; the parse appears 27 times; `json.load(open(...))` 27 times in `design_loop.py` alone. About 74 if/else PASS/FAIL pairs in `core.py` and 52 in `delegation.py` write each title twice. Eleven different "what did the guard decide" helpers exist with disagreeing defaults.
- [medium] `_ma_say` is defined twice with different signatures (`checks/design_loop.py:1783`, `:2946`).
- [medium] Git fixture helpers are written once per file with different identity flags; only one turns off `commit.gpgsign`. *(Reasoned, not reproduced.)*
- [medium] `checks/make_page.py`, `checks/design_loop.py`: results are collected as `(title, bool)` with no detail line, and are lost if anything raises first.
- [medium] `verify.py:106-118`: the `--changed` map is hand-kept and has drifted (editing `make_page.py` skips design_loop's sweep cases). `--only` still runs every case. Three parts each run longer than 50 s; the full suite cannot finish under the plugin's own 60-second rule.
- [low] Unclosed `open()` in many files, stale "three tier agents" comment (there are four), `docs.py:2` docstring covers a third of the file, `checks/common.py:494-509` never restores a stub it installs, `selftest.py` template passes unedited (false green).

### Page and ledger scripts
- [medium] `make_page.py`, `page_criteria.py`: page types are code, not data. A new type means edits in `PAGE_TYPES`, `TYPES`, `STAMP_EXEMPT`, `EXTRA` and the build-plan item. Fix: one `templates/page-types.json`.
- [medium] `make_page.py:646-724`: the browser check is written twice (Node and Python, about 75 lines each).
- [medium] `make_page.py:513-540, 288-367`: no shape check on content; a dict Changes item gives `KeyError: 0`, exit 1, a code the docstring does not list.
- [medium] `make_page.py:625-630`: a visual-check failure exits 2 after the page is written and skips recording it.
- [medium] `plain_docs_check.py:207-208`: git missing means the stale check is silently skipped and the queue reports CURRENT. `check_file` is 149 lines in six passes.
- [medium] `ledger.py:19`: `ledger_dir` is loaded, documented, and read by nothing.
- [medium] `labels.py:105-113`: takes the first GitHub remote in config order, which can be `upstream` in a fork.
- [medium] `session_ledger_render.py:17-19`: misses `git -C /repo push` and `mcp__GitHub__...`; `:197` does not escape `|` in the table that is the ledger's reason for existing.
- [medium] `waitfor.py:112-120`: a typo in `--agent` finds nothing and the wait can never stall, with the message shown only at the end.
- [low] `visualcheck.py` step handling copied twice and all frames held in memory; `review_plan.py:26` regex requires `name=` before `content=`; `ledger.py:180` the skeleton it writes fails its own check; several `hooks.json` timeouts (90, 300, 330 s) exceed the 60 s foreground limit in `waits.json`.

### Docs and drift tools
- [medium] `docs_drift.py:121`: an unreadable living doc is skipped and the run exits 0, against its docstring. `:59` uses `git ls-files` without `-z`, so non-ASCII paths read as gone. `:95` is citations x files (757k `endswith` calls, 0.24 of 0.32 s).
- [medium] `docs_drift.py:70`: any line with "deleted" or "removed" is not checked.
- [high] `docref.py:324`: `fix --write` replaces the file through a temp file and loses its exec bit. *(Read, not run.)*
- [medium] `clarity.py:91`: one detector skips the code-fence stripper the others use. `:259` can delete visible words from HTML.

### `tools/`
- [medium] Three different rules pick "the installed plugin" (newest mtime, highest version, registered `installPath`).
- [medium] Only `use_branch.py` honours `CLAUDE_CONFIG_DIR`; five other scripts hard-code `~/.claude`.
- [medium] `force_update.py:113-116` exits 0 after an uninstall when it cannot find the trees. `install.py` and `clean_install_test.py` run bare `claude`, which `force_update.py` documents as unreliable on Windows.
- [medium] `use_branch.py:59-62,78` prints "OK" after checking only the clone, not the installed cache.
- [medium] `clean_install_test.py` ignores four CLI return codes and compares the local working tree, not GitHub.
- [medium] `check_plugin_version_bump.py:29-30` gates one plugin though `marketplace.json` publishes three.
- [medium] `sync_standards.py:89-102` never deletes files removed upstream; prints PASS for an unknown commit.
- [medium] Several `verify_tools.py` checks test wording (the word "errorlevel" anywhere, a docstring).
- [low] `verify.yml` runs on pushes to `main` only, but `CLAUDE.md` says every push; `install.py` leaves `settings.json.<pid>.tmp` behind (confirmed in `/tmp`); `bootstrap.sh` re-splits `$ORIG_ARGS`; `session_ledger.py:65` filter is dead.

## Not done, and what could not be checked

- Full `verify.py` run: not timed. `delegation`, `design_loop` and `make_page` each hit the 50 s cap. Other parts took 18 to 46 s.
- Reviewers read most large files by pattern and structure, not line by line.
- Not run, because they change the real install: `install.py`, `force_update.py`, `use_branch.py`, `clean_install_test.py`, `bootstrap.*`, `update.bat`, `sync_standards.py`.
- Windows behaviour (PowerShell `ri`, `rd`, `py -3`, `claude.cmd`) was reasoned from code, not run.
- The Stop-time model judge was not timed.

## Suggested order of work (aj chooses)

1. Close the guard holes (finding 1, 2): a small tokenizer, the biggest real risk.
2. Make test failures visible (3, 12): per-case runner; fixes silent skips and kills most duplication.
3. Cut per-call cost (4, 5, 6, 7): lazy event loading, label cache, judge only on a hit, append-only log.
4. Split `core.py`, `design_loop.py` and `safe_git.py` along the seams above.
5. One shared install module for `tools/` (11).
