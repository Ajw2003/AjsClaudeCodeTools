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
- `tools/check_plugin_version_bump.py` still only watches the house-rules folder, so a change to rule-enforcement
  alone is not gated.
- `tools/measure_footprint.py` runs `inject`, `showrule`, `scope` and `subagentrules` through house-rules' `hook.py`; those events now live in the rule-enforcement `hook.py`, so its numbers for them are wrong until it is pointed there (not done here).
- `_rules_root` still reads `~/.claude/plugins/installed_plugins.json`, not `CLAUDE_CONFIG_DIR` (unchanged behaviour).
