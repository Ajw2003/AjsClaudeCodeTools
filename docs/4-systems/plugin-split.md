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
