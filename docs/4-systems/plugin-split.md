# Plugin split

How house-rules becomes nine plugins plus a shared library. Approved 2026-11-02
(`docs/6-decisions/Decisions.md`, "Design approved: plugin split"); proposal
`docs/plans/2026-11-02-plugin-split.html`. Nothing is built yet: this doc is the target.

## The principle

No rule is optional. Every rule is enforced by code, not left to the agent. A check that causes
friction is reworked, never removed or switched off (`docs/6-decisions/Decisions.md`, "The plugin
split: no rule is optional"). The 21 `HOUSE_RULES_*` switches that turn a check off are removed;
the 17 that set a path, URL or number stay.

## Target structure

| Plugin | Takes from house-rules today |
|---|---|
| Shared library (no hooks) | `core.py` plumbing: `read_payload`, `emit`, trace, the `register_*` links, transcript and git helpers; `run.sh`; `make_page.py` and its templates |
| Rule enforcement | `inject`, `showrule`, `subagentrules`, `scope`; the repeat-failure lock (choice 6A) |
| Safe work | `safe_git.py` (guard, guardwrite, guardgithub, creditcheck, branchnudge, prompttimer/promptran); autosave, commitgate, worktreesweep, subagentcommit from `delegation.py`; no local paths; the planned secret scrub (`session_triage.py`) |
| Design loop | `design_loop.py`: approval lock, stages, pages, QA, issue workflow, close guard, issuelist, closablemerge, labels |
| No hiding | artifact location, fails silently, what prompted me; announce, audit, userpromptaudit, verdict, subagent ledger, rclink from `delegation.py`; `session_ledger.py`, `stallcheck.py`; new research-citation check |
| Living docs | `docs.py`: docstiers, harvest, commit-time docs reminder; archivist, docref, project-docs skill; plain-docs |
| Code standards | `standards` hook, `rules/standards/`, build-alone, open source first; new code checks |
| Check your work | green suite, shim compiles, reported update, visual check, runnable, parity, reviewer; handover rule, step cards, `handover-cards` output style; new screenshot and video tools |
| No trust memory | read docs first, evidence check (`handover_evidence_check`), stale-memory warning, `profile`; new docs-freshness check |
| Accessible AI | `clarity.py`, `writing.py`, editor, voice, plain summary, the 160-word page rule |
| `claude-agent-router` (existing) | delegation rule, scout/builder/reviewer, agentcap |

## Known risks

- The 2.74.0 restructure was reverted because a shared settings gate refused every tool
  (`docs/3-state/ProjectState.md`, 2026-10-28). The library has no hooks, so it cannot do that.
- Today one Stop hook gathers every part's end-of-reply checks. After the split each plugin has its
  own, so several could block the same reply; the repeat-failure lock has to count across plugins.
- `guard` calls the docs reminder (`register_docs_status`) at commit time: 17 `register_*` calls link
  the parts today and each needs a cross-plugin route.
- Plugin `dependencies` installing the library: verified, see "Step 1 findings (#438)" below.

## Step 1 findings (#438)

Throwaway plugins (`spike-lib`, `spike-a`, `spike-b`) in a local marketplace, installed into a
throwaway `CLAUDE_CONFIG_DIR`, Claude Code CLI 2.1.316. The real `~/.claude` was not touched.

### 1. Dependencies install the library: yes

Schema (official plugins-reference, `dependencies`): array of `"name"`, `"name@marketplace"` or
`{"name","marketplace","version"}`; bare names resolve against the plugin's own marketplace.
`spike-a/.claude-plugin/plugin.json` had `"dependencies":["spike-lib"]`.

```
$ claude plugin marketplace add .../dep-spike/mkt
√ Successfully added marketplace: spike-mkt (declared in user settings)
$ claude plugin install spike-a@spike-mkt
√ Successfully installed plugin: spike-a@spike-mkt (scope: user) (+ 1 dependency: spike-lib)
$ claude plugin list
  > spike-a@spike-mkt  Status: √ enabled
  > spike-b@spike-mkt  Status: √ enabled
  > spike-lib@spike-mkt  Status: √ enabled
```

Installing `spike-a` alone also installed and enabled `spike-lib`. (`claude plugin prune` removes
auto-installed dependencies no longer needed.)

### 2. Two blocking Stop hooks: both reasons reach the model, one retry

Both `spike-a` and `spike-b` had a Stop hook that returns `{"decision":"block","reason":"REASON-FROM-<X>..."}`
unless `stop_hook_active` is true, and logs the payload. Run: `CLAUDE_CONFIG_DIR=.../cfg claude -p "say hi" --output-format stream-json --verbose`
(auth worked with the custom config dir; exit 0).

Hook log (order of execution):

```
a stop_hook_active=False   (.717)
b stop_hook_active=False   (.720)   - started 3 ms apart: run in parallel, not sequentially
b stop_hook_active=True    (.969)
a stop_hook_active=True    (.972)
```

- Order: on the first stop a ran first and b 3 ms later (parallel; do not rely on order). On the retry b was logged before a.
- Both reasons reached the model: the transcript holds two separate user messages,
  `Stop hook feedback:\nREASON-FROM-A...` and `Stop hook feedback:\nREASON-FROM-B...`; the model's reply said both words (AZZ, BZZ).
- `stop_hook_active` read `True` on the retry, for both hooks.
- Retries: exactly 1 (each hook ran twice).

Consequence for the split: several plugins' Stop hooks can block one reply and all reasons are
delivered together. `stop_hook_active` is shared, so it cannot tell a plugin whether its own earlier
block was the one repeated; a cross-plugin repeat-failure counter needs its own shared state.

Not verified: more than one retry (hooks here stop blocking after the first); behaviour on the
interactive path (only headless `-p` was run); hook ordering in other CLI versions.

## Step 2: the library (#439)

The library source lives once, in `claude-house-rules/plugins/house-lib/house_lib/` (a plugin with
no hooks, version 0.1.0, listed in `.claude-plugin/marketplace.json`). Two modules moved verbatim
out of `house_rules/core.py`, which now imports them back and re-exports every name:

- `plumbing.py`: `read_payload`, `emit`, `_TRACE_OFF`, `_truncate_with_notice`, `trace_enabled`,
  `trace`, `trace_verbose`, `trace_noop`, `_read_text`.
- `links.py`: `_register`, the six registries (`SESSION_START_HOOKS`, `PROMPT_HOOKS`,
  `POST_TOOL_HOOKS`, `GUARD_ISSUE_HOOKS`, `GITHUB_WRITE_HOOKS`, `DOCS_STATUS_HOOKS`) and the
  `register_*` / `_session_start_hooks` / `_post_tool_hooks` functions.

`python tools/sync_library.py` copies the source into each plugin listed in `TARGETS` (today
`house-rules/scripts/house_lib/`); `--check` changes nothing and exits 1 naming each file that
differs or is missing. CI runs the check (`.github/workflows/verify.yml`) and
`tools/verify_tools.py` proves it on a temp folder. Edit the source, never a copy.
Transcript and git helpers stay in `core.py` for now: they depend on core's other functions.

## The gate before a merge to main

aj, 2026-11-02: open the pull request after step 3 (#440), "but ensure it will break nothing before we
consider merging to main. i dont want to repeat the first restructure attempt". The 2.74.0 restructure
was reverted because its settings gate refused every tool, replies included (`docs/3-state/ProjectState.md`,
2026-10-28). Nothing merges until every item below has run, with its output quoted on the QA page:

1. **Every suite passes**, locally and in CI on the pull request: each plugin's `verify` run,
   `tools/verify_tools.py`, `tools/sync_library.py --check`, `tools/check_plugin_version_bump.py`.
2. **Same behaviour as 2.74.1.** One recorded payload per hook handler is replayed through `main`'s
   house-rules 2.74.1 and through the branch's installed plugins together; the combined outputs are
   diffed, and every difference is listed and traced to an approved change.
3. **No tool refused that 2.74.1 allows.** Headless sessions on a clean config with the branch's plugins
   installed read a file, edit a doc, run a shell command, spawn a helper and reply; the transcript shows
   no refusal that the same session under 2.74.1 does not also give.
4. **A clean install from GitHub** of the pull request's branch on a fresh config.
5. **Rollback is one step:** the revert command for the merge is written on the QA page and tested on a
   throwaway branch.
6. **aj's QA pass** on the QA page, before the merge.

## Step 3 part A: rule loading moved (#440)

Part A of step 3 only moves the four rule-loading handlers. The repeat-failure lock and removing the
off switches are later parts and are not started: `HOUSE_RULES_VOICE` and `HOUSE_RULES_DELEGATION`
still work, in the new plugin, exactly as before.

### What moved

New plugin `claude-house-rules/plugins/rule-enforcement/` (version 0.1.0, `"dependencies": ["house-lib"]`,
listed in `.claude-plugin/marketplace.json`). It has its own `scripts/run.sh` (same probe and the same
fail-loud text as house-rules' for these events), `scripts/hook.py`, `hooks/hooks.json` and a
vendored `scripts/house_lib/` (`tools/sync_library.py` now has two targets).

| Handler | Event | From | To |
|---|---|---|---|
| `inject` (`event_inject`) | SessionStart | `house_rules/core.py` | `rule_enforcement/core.py` |
| `showrule` (`event_showrule`) | SessionStart | `house_rules/core.py` | `rule_enforcement/core.py` |
| `scope` (`event_scope`, `SCOPE_REMINDER*`) | UserPromptSubmit | `house_rules/core.py` | `rule_enforcement/core.py` |
| `subagentrules` (`event_subagentrules`, `_subagent_core`) | SubagentStart | `house_rules/delegation.py` | `rule_enforcement/core.py` |

Used only by them, moved too: `_apply_voice_toggle`, `_rules_root`, `_version_tuple`, `_plugin_version_of`,
`_strip_subagent_markers`, `SUBAGENT_*`, `TIER_AGENTS`/`_is_tier_agent` (unused anywhere), and small copies of
`_installed_plugins_path`, `_plugin_version` and `_delegation_enabled` (the last is one line; it goes with the off switches).
`_expand_detail_paths` and `_plugin_root` stay in house-rules too (the `standards` hook uses them).
Files moved with `git mv`: `rules/house-rules.md`, `rules/show-dont-tell.md`, `rules/clear-writing.md`,
`rules/detail/` (28 files). `rules/standards/` stays in house-rules (its own later plugin).

`<plugin>` expansion: inject, showrule and the subagent core expand `${CLAUDE_PLUGIN_ROOT}` to the root
of the plugin that holds `rules/`, which is now rule-enforcement. `_rules_root` looks up
`rule-enforcement` (not `house-rules`) in `installed_plugins.json` when an update lands mid-start.
The headless run below shows `<plugin> ... is the plugin root: .../plugins/rule-enforcement`, once.

### Every link, and where it went

house-rules removed the four handlers and their hooks.json entries and gained three small hooks, one per
event, each emitting just the text the staying parts contribute:

| Link (registered by) | Was gathered by | Now emitted by | Change a reader could see |
|---|---|---|---|
| `register_session_start("inject", _strip_subagent_markers)` (delegation) | `inject` | moved into `inject` itself (it is about the rules text) | none |
| `register_session_start("inject", _append_thread_link)` (delegation, #400) | appended to the `inject` text | house-rules `threadlink` (SessionStart, `delegation.py`) | the thread-link sentence is its own `additionalContext` block, not the tail of the rules block; a failure says so in its own `systemMessage` |
| `register_session_start("profile", ...)` x2 (safe_git: branch block, identity block) | `profile` | unchanged: `profile` stays in house-rules | none |
| `register_prompt(_scope_waiting_link)` (safe_git) | `scope` | house-rules `scopelinks` (UserPromptSubmit, `hook.py`) | its note is its own `additionalContext` block after the reminder |
| `register_prompt(_scope_loop_link)` (design_loop) | `scope` | `scopelinks` | its clause is a separate block of bullet lines, not appended to the reminder's list |
| `register_prompt(_scope_delegate_link)` (delegation) | `scope` | `scopelinks` | same |
| `register_prompt(_scope_parity_link)` (hook.py) | `scope` | `scopelinks` | same |
| `register_subagent_note(_loop_helper_note)` (design_loop) | `subagentrules` appended it to the core | house-rules `subagentlinks` (SubagentStart, `delegation.py`) | the design-loop note is its own `additionalContext` block, not the tail of the rules core |
| transcript line "subagent transcript expected at ..." and its `COULD NOT TELL` | `subagentrules` `systemMessage` | `subagentlinks` | its `systemMessage` is separate from the one `subagentrules` emits; the prefix reads `subagentlinks COULD NOT TELL` |

Clause order inside `scopelinks` is the order the parts registered in before (waiting, design loop, delegate, parity).
`scopelinks` says nothing when no link has text, and reports a failing link in a `systemMessage` (it used to
fall back silently to the short reminder). Not changed: `register_post_tool`, `register_guard_issue`,
`register_github_write`, `register_docs_status` (their handlers all stay in house-rules).

What a reader sees differently is only the block boundaries listed above. No sentence changed. If these should
be one block again, the rule-enforcement hooks would have to call back into house-rules code, which the split
rules out; that is a design call for aj, not made here.

### Tests

- house-rules `checks/` lost the cases that tested the four handlers (inject/showrule content and size, the
  `${CLAUDE_PLUGIN_ROOT}` expansion, the fail-loud read, the scope forms and their size baselines, the voice
  toggle, the newest-installed-rules cases, the subagent core) and gained cases for `threadlink`, `scopelinks`
  and `subagentlinks` (the thread-link, go-ahead, parity, waiting and loop cases now call them). The
  restatement table's scope row and every rules-text drift check read the moved files from the sibling
  plugin (`checks/common.py` `RE_PLUGIN`), so they need a repo checkout.
- The moved cases live in `rule-enforcement/scripts/checks/rule_enforcement.py` (run by
  `rule-enforcement/scripts/verify.py`, a step in `.github/workflows/verify.yml`), plus new cases for the
  wiring, the no-interpreter fallback, the crash net on each moved event, and "house-rules dispatches none of
  the four and holds none of the moved files".
- house-rules went to 2.75.0 (`plugin.json`, and the one version pin in `checks/design_loop.py`).

### Known gaps

- Fixed after part A: `unity-tools-first.md` moved to house-rules `rules/standards/` beside the Unity standards that
  point at it, and the plain-doc limits moved from `rules/detail/clear-writing.md` into `skills/plain-docs/SKILL.md`,
  the skill that applies them. Neither pointer crosses a plugin now.
- Fixed after part A: `tools/check_plugin_version_bump.py` now checks every plugin folder under
  `claude-house-rules/plugins/` that has a `.claude-plugin/plugin.json` (a plugin not on the base passes as new);
  `docs/` and the root `CLAUDE.md` still count for house-rules only. Its output names each plugin and its verdict.
- Fixed after part A: `tools/measure_footprint.py` reads each plugin's `hooks.json` to find which plugin declares
  an event, runs it through that plugin's `hook.py`, adds a `showrule` row, and reports the fixed per-session cost
  per plugin plus a total (`--repo`, or the installed cache for both plugins).
- `_rules_root` still reads `~/.claude/plugins/installed_plugins.json`, not `CLAUDE_CONFIG_DIR` (unchanged behaviour).

## Step 3 part B: the repeat-failure lock (#440)

Choice 6A of the approved design: an end-of-reply (Stop) check that fails blocks the reply up to three
times for the same message of aj's; after the third block the reply goes through, loudly, and from then on
source edits and commits are refused until that check passes. Nothing passes silently. Not touched: the
report-only checks marked #309 (the page row) and the `HOUSE_RULES_*` switches (part C).

### How it works

- **Library.** `house_lib/blocks.py` (library source in `house-lib`, vendored into house-rules and
  rule-enforcement by `tools/sync_library.py`) holds the counter, the lock and the "is a lock active" query.
  `record_stop(cwd, session_id, check, mark, failing, missing, fix)` returns `"pass"` (count reset, lock
  cleared), `"block"` (fewer than three blocks so far for this message) or `"through"` (three blocks done:
  the check is locked, with what it misses and how to supply it). It never returns `"block"` a fourth time
  for one message. `active_locks(cwd, session_id)` is what the PreToolUse hook reads.
- **State.** `<git common dir>/house-rules/check-blocks.json` (inside `.git`, so never committed; shared
  by worktrees), else `house-rules-check-blocks-<session>.json` in the temp folder outside a repository.
  Keyed by session id, then check name; a count remembers the message it answers (the transcript record's
  uuid plus its text), so a new message from aj starts again at block 1. A lock outlives messages: only a
  Stop that finds the check passing clears it. `stop_hook_active` is never used to count (it is shared
  between plugins, see "Step 1 findings").
- **The four checks.** house-rules `handover_checkpoints` (`design_loop.py`) records editor, evidence, commit
  and plain summary through the library, on the first reply and on every retry. Block text says
  "(block N of 3)". The `through` reply says the check is LOCKED, as a `systemMessage`, and the notes that
  would have woken the model go to aj only (no `additionalContext`, so no loop). qa page still blocks once.
  A check whose result is unknown this time (commit or evidence "could not tell", an unreadable transcript)
  neither blocks nor clears a lock. A counter that cannot be read or written says so and does not block.
- **Enforcement.** rule-enforcement `lockgate` (PreToolUse on `Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell`,
  `rule_enforcement/lock.py`) refuses, while a check is locked: edits to source files, shell commands that
  write a source file, and `git commit` / `git push`. The refusal names each locked check, what it misses, the
  files a commit lock named and how to supply it. Shell writes use the detector that used to live in the
  design loop (`house_lib/shellwrites.py`: redirects, tee, `sed -i`, `perl -pi`, python/node writes), plus
  cp, mv, install, dd of=, truncate and ln; a write whose path cannot be read from the command text is
  refused too (use Edit/Write). **The target's repository decides**, not the call's cwd: the lock is looked
  up in the repo of the file an Edit/Write names, of each shell write target, and of the directory a git
  command acts on (`git -C dir`, a leading `cd dir &&`, else cwd). Always allowed: `docs/**/*.md`, anything
  under `docs/plans/`, paths in no git repository and outside the session folder (a page's content file in
  a scratch folder; never another repo's source), reading, tests, and the editor helper (not matched). When
  the commit check is the locked one a commit is allowed (a push is not). In a session folder that is not a
  repository the temp-file state holds the lock and the folder's own files are covered.
- **Clearing.** A lock clears only when the check passes on what it was locked for. The commit lock records
  the repo-relative files it named and clears only when none of them is still uncommitted (a later turn that
  writes nothing does not clear it, and blocks again while they stay dirty). The evidence, editor and plain-
  summary locks clear only on a reply that carries the missing piece: a success claim with a tool run or
  quoted output, an editor run, a finished-work reply with a plain opening. A reply that cannot be judged
  against a lock keeps it and says so ("the X lock is kept"); an unreadable lock state keeps every lock and
  says so.
- **Fail mode.** If the state cannot be read, or the payload cannot be parsed, or the shim finds no Python,
  `lockgate` says "NOT enforced for this call" in a `systemMessage` and allows the call. It never refuses
  because something is broken (the 2.74.0 failure, `docs/3-state/ProjectState.md`, 2026-10-28).

### Limits, said plainly

- A shell command can still write a source file in a way the detector cannot read (a program that writes a
  path it computes at run time). Paths that cannot be read from the command text are refused; a path computed
  inside a script is not seen.
- The evidence lock needs a reply that makes a success claim to clear it: saying nothing never clears it.
  That is intended, and the refusal says what to do.
- Paths in no git repository and outside the session folder are always allowed while locked, so a page's
  content file can be written. A repository's own files never are.

### Live proof (headless, CLI 2.1.316, throwaway config and repo)

house-rules and rule-enforcement installed from the local marketplace into a throwaway `CLAUDE_CONFIG_DIR`;
the session ran in a throwaway git repo. The prompts began "skip design" (the design loop's own gate, in the
throwaway session) and told the model not to commit, so the commit check kept failing. Turn A wrote `a.py`
and never committed it:

```
Stop: "- commit (block 1 of 3): Files a turn writes are committed on your own branch before it ends."
Stop: "- commit (block 2 of 3): ..."   Stop: "- commit (block 3 of 3): ..."
Stop: {"systemMessage":"house-rules: the commit check still fails after 3 blocks for this message, so the reply goes through and the check is LOCKED: source edits and commits are refused until it passes. ..."}
state: {"counts": {"commit": {"count": 3}}, "locks": {"commit": {"missing": "Files a turn writes are committed ...", "fix": "commit a.py on your own branch"}}}
```

Turn B asked for an Edit of `a.py`: `PreToolUse:Edit` came back `permissionDecision: deny`, "House rules,
repeat-failure lock: editing the source file .../a.py is refused ... Locked check: commit. Missing: Files a
turn writes are committed on your own branch before it ends. To supply it: commit a.py on your own branch."
Turn C wrote `docs/3-state/ProjectState.md` (allowed) and ran `git add a.py docs/... && git commit` (allowed,
`[AjsAgent/live-test cd8f5c9]`); that reply's Stop printed nothing and the state became
`{"counts": {}, "locks": {}}`. Turn D's Edit of `a.py` then went through ("updated successfully"), and the
cycle started again at block 1. An ordinary session (echo, Read, a docs Write, a docs commit, a reply with
nothing failing) had zero lock mentions in its transcript and wrote no state file.

Not proven live: the unreadable-state and no-Python paths (covered by the verify cases only).
Finding for aj: the commit check only looks at files the current turn wrote, so a later message that writes
nothing passes and clears the lock even though an earlier file is still uncommitted (seen once, a turn that
only ran a refused command). That is the approved "clears when a later Stop finds it passing"; whether the
commit check should also look at files left uncommitted by earlier turns is a design call, not made here.

### Live proof of the follow-up (same setup)

With the commit lock on (`"files": ["a.py"]` in the state), a shell `sed -i s/print\(1\)/print\(2\)/ a.py` came
back `permissionDecision: deny`: "repeat-failure lock: this shell command writing the source file a.py is
refused ... Locked check: commit. ... Files it named: a.py. To supply it: commit a.py on your own branch."
(`a.py` stayed `print(1)`). A following turn that wrote nothing ("hello") did not clear the lock: its Stop
blocked "commit (block 1 of 3)", "(block 2 of 3)", "(block 3 of 3)", then went through with the lock still in
the state file. A last turn wrote `docs/3-state/ProjectState.md` and committed `a.py` with it
(`1706866 add a.py and note it`); its Stop printed nothing and the state became `{"counts": {}, "locks": {}}`.

## Step 3 part C: the off switches removed (#440)

Principle: no rule is optional, so no switch may turn a check off (`docs/6-decisions/Decisions.md`, "Off switches
answered: part C of step 3"). Every check below now runs exactly as it did with its switch unset.

### Removed (19 switches, plus one value)

| Switch | What it used to turn off | Code that went |
|---|---|---|
| `HOUSE_RULES_AGENTS` | the two-subagent cap | `_agentcap_enabled` |
| `HOUSE_RULES_AGENT_BRANCH` | the move-to-`AjsAgent/` advice at session start | `_agent_branch_enabled` |
| `HOUSE_RULES_ATTRIBUTION` | the credit-aj's-agent guards, `creditcheck`, the author guard | `_attribution_enabled` |
| `HOUSE_RULES_AUTOSAVE` | autosave, `commitgate`, `worktreesweep` | `_autosave_enabled` |
| `HOUSE_RULES_AUTO_UPDATE` | the automatic `claude plugin update` at session start | `_auto_update_enabled`; the "switched off" banner text |
| `HOUSE_RULES_CLEAR_WRITING` | the page, issue and editor checks | `_clear_writing_enabled` |
| `HOUSE_RULES_COMMIT_CHECK` | the Stop commit check, `branchnudge`, `subagentcommit`, the audit line | `_commit_check_enabled` |
| `HOUSE_RULES_DELEGATION` | `announce`, `verdict`, `audit`, `userpromptaudit`, `subagentlinks`, `subagentrules` | `_delegation_enabled` (both plugins) |
| `HOUSE_RULES_HANDOVER` | the whole end-of-reply dispatcher | the check at the top of `event_handover` |
| `HOUSE_RULES_HARVEST` | the comment-harvest reminder (`quiet` also dropped its trace) | the toggle; `HOUSE_RULES_TRACE` still covers the trace |
| `HOUSE_RULES_ISSUES` | the issue workflow: gate, PR rule, close guard, issue list | `_issues_enabled` |
| `HOUSE_RULES_LOOP` | the design loop: lock, approvals, page check, checkpoints, closable merge | `_loop_enabled` |
| `HOUSE_RULES_PARITY` | the parity report | `_parity_enabled` |
| `HOUSE_RULES_PLAIN_SUMMARY` | the plain-summary check | `_plain_summary_enabled` |
| `HOUSE_RULES_VERSION_CHECK` | the version check | `_version_check_enabled` (the check stays until step 13, #450) |
| `HOUSE_RULES_VISUAL_CHECK` | the visual check | `_visual_check_enabled` |
| `HOUSE_RULES_VOICE` | the voice section of the clear-writing rule | `_apply_voice_toggle` |
| `HOUSE_RULES_WORKTRACKING` | `rclink` and the thread link | `_worktracking_enabled` |
| `HOUSE_RULES_EDITOR` | the long-reply editor trigger (it was off by default) | `_editor_enabled` and the long-reply branch of `_editor_owed`: the editor pass is required for pages only |
| `HOUSE_RULES_PROMPT_TIMEOUT=off` (and `0`) | the permission timer | the value only: the number of seconds stays, and `off` or `0` is now named on stderr and the 300 second default applies |

Two things went with them because they could only run when a switch was off: the go-ahead delegation clause
(`scope` added it only when `HOUSE_RULES_LOOP=off`, so with the loop always on it never fired), and the
"HOUSE_RULES_X=off disables it" sentences in the refusal and Stop messages, the rules text, the editor agent
description, `docs/architecture.md`, `docs/4-systems/*.md`, the README table and `tools/measure_footprint.py`.
`tools/measure_footprint.py` no longer sets the auto-update switch: it already points `HOUSE_RULES_VC_CLAUDE` at
`false`, so no update can run during a measurement.

### Kept

| Switch | Why it stays |
|---|---|
| `HOUSE_RULES_SUBAGENT_LEDGER` | aj's own answer: "keep it for now as i need a way to view their work even if it is less secure"; redone in Safe work (#441) and No hiding (#446) |
| `HOUSE_RULES_ENV_FILE`, `HOUSE_RULES_HANDOVER_TARGET_FILE`, `HOUSE_RULES_LOOP_LABELS_FILE`, `HOUSE_RULES_AGENTS_STATE`, `HOUSE_RULES_WORKTRAIL_DIR`, `HOUSE_RULES_MEMORY_DIR` | each only points at a path; none turns a check off |
| `HOUSE_RULES_GITHUB_OWNER`, `HOUSE_RULES_OWNED_BRANCHES`, the `HOUSE_RULES_VC_*` URLs and paths | each only sets a name, a URL or a path |
| `HOUSE_RULES_HARVEST_MIN_CHARS`, `HOUSE_RULES_PROMPT_TIMEOUT` (a number) | each only sets a number |
| `HOUSE_RULES_TRACE`, `HOUSE_RULES_DEBUG` | how much a hook says, never whether a check runs; no reminder or refusal depends on them |

### How the suites isolate now

No test turns a check off, and there is no test-only switch. A fixture repo that edits source starts at the Build
stage (`build_stage` in `checks/common.py` writes a stage file into the repo's git directory, where the loop still
reads one, so the tree stays clean); the cases that test the lock write their own stage file. Each Stop case runs in
a repo of its own, so the repeat-failure count of one case never reaches another. Because the checkpoints now always
run, the evidence, commit and plain-summary checks block the first replies with their short reason; the cases that
need the full note read the reply that goes through after three blocks (`_stop_through`). The 160-word editor case
now asserts the reminder is not given. One check per plugin (`checks/core.py` in house-rules, `checks/rule_enforcement.py`
in rule-enforcement) fails if a removed switch name, or `HOUSE_RULES_PROMPT_TIMEOUT=off`, appears anywhere under the
plugin folder; a second case proves the pattern matches the removed names and ignores the kept ones.

### Live proof

Throwaway `CLAUDE_CONFIG_DIR` under the session scratchpad (`switch-live/cfg`), `house-rules` 2.75.0 and
`rule-enforcement` 0.1.0 (plus `house-lib` as a dependency) installed from the local marketplace, Claude Code 2.1.316,
headless (`claude -p`). Same five steps in two fresh repos: read `notes.txt`, write `docs/live-note.md`, run
`echo live-ok`, write `app.py`, reply. The repos are on `AjsAgent/live` with no stage file (Design).

| Step | Environment without `HOUSE_RULES_LOOP` | Environment with `HOUSE_RULES_LOOP=off` |
|---|---|---|
| Read `notes.txt` | allowed | allowed |
| Write `docs/live-note.md` | allowed | allowed |
| `echo live-ok` | allowed, printed `live-ok` | allowed, printed `live-ok` |
| Write `app.py` | denied: "House rules, design loop: code edits are closed in the Design stage ..." | denied, same words |
| End of reply | blocked once: "commit (block 1 of 3)"; the model committed the note | the same block; the model committed the note |

The refusal text has no "switch this off" sentence in either run. Nothing was refused that 2.74.1 would allow:
the one refusal is the design-loop code lock, which 2.74.1 also applies in Design. An earlier run, before the
version overrides were set, had the first shell command held once by the out-of-date notice (the throwaway
install reads 2.75.0 and GitHub's default branch says otherwise); that is the version check, not a removed switch.
