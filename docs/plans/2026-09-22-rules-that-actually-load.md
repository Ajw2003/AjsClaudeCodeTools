# Make the rules actually load, enforce the docs tiers, and cut the fixed footprint

## Context

A grilling session on 2026-09-22 reviewed the plugin's architecture, costs and downsides. The
headline finding: **the rules mostly do not reach the model.** `inject` emits 44,506 chars; Claude
Code saves any single hook's `additionalContext` over 10,000 chars to a file and puts only a ~2KB
preview in context. Everything past the first section of `house-rules.md` — including the docs-tier
rule — was invisible in that session. `house-rules.md` has doubled since the 2026-09-07 footprint
plan (20.8KB → 43KB), and the repo `CLAUDE.md` is 32KB despite claiming to "stay short on purpose".

### Facts established by experiment (CLI 2.1.280, `claude -p` with a probe SessionStart hook)

| Question | Result |
|---|---|
| Size at which hook context is saved to a file | `additionalContext` of **10,000 chars arrives in full; 10,001 is persisted** (preview only) |
| Is the limit per hook or combined? | **Per hook.** Two hooks of 7,000 chars each both arrived in full |
| Is SessionStart output re-paid on each subagent spawn? | **No.** A spawned `general-purpose` subagent could not see a word planted by a SessionStart hook. The "re-paid on every subagent spawn" claim in `CLAUDE.md`/`measure_footprint.py` is wrong for SessionStart output — and it means subagents never see the injected rules at all |

## Priorities (user-ranked)

1. Guards (`guard`, `guardwrite`) — never weakened.
2. The docs tier structure followed in every project, **and** handovers that are actionable and
   grounded in evidence — never asserted from chat, docs, reasoning or memory alone.
3. The step-card format.
4. Visibility (traces, `announce`/`verdict`).

## Decisions

- **Rules split.** `inject` emits an imperative-only core that stays under the per-hook limit. Detail
  goes to what already owns a topic (the `project-docs` skill, the output style, the executor and
  archivist agents), and the rest to `rules/detail/<topic>.md`, which the core names by path. The
  "Why:" rationale leaves the injected text for `docs/` (reverses the 2026-09-07 decision to keep
  every Why: block injected — record it in `docs/Decisions.md`).
- **One size constant** (`INJECT_CHAR_LIMIT = 10_000` in `hook.py`, with a safety margin applied by
  the check) enforced by `verify.py` on the actual `inject` and `standards` output, each checked
  separately, since the limit is per hook. The same suite caps the root `CLAUDE.md` (~4KB).
- **Card format:** the output style is the single copy the model reads; the rules file keeps a
  one-line pointer. `verify.py`'s six-field drift check is moved accordingly.
- **Root `CLAUDE.md` becomes a real pointer:** commands and links. The hook table moves to
  `docs/architecture.md`, and `verify.py`'s table-vs-hooks.json check follows it.
- **SessionStart docs check** (stateless file test): a project missing `docs/README.md` or any of
  the six tiers gets a loud instruction to load `house-rules:project-docs` and scaffold before other
  work, **in every repo**. In a repo not owned by the configured GitHub account (read from the git
  remote), the scaffolded paths are also added to `.git/info/exclude`, so they never leave the
  machine.
- **Commit-time docs check:** a `git commit` whose staged files include a source file (the
  `harvest` extension list) with nothing staged under `docs/`:
  on a `claude/` branch → reminder to Claude (context), no prompt; on any other branch → the
  prompt `guard` already shows gains the docs reason. Read from the index, no state.
- **`Stop` (`handover`) narrowed and extended:** fires only on shell-labelled fences
  (`bash`, `sh`, `powershell`, `pwsh`, `cmd`, `zsh`, …), not any fence. Adds an evidence check: a
  reply claiming success (works / fixed / passes / verified / tested) needs a tool call since the
  last user message (read from the transcript) **or** quoted evidence in the reply. Stays
  fail-open, keeps `stop_hook_active`.
- **`scope`:** the card line is replaced by a docs-tier line and an evidence line, same size.
- **Unchanged:** traces; offshoots stay separate and uninstalled.
- **Subagents get the rules (added 2026-09-22, after a tested finding).** SessionStart context never
  reaches a subagent; `SubagentStart` context does, and `PreToolUse` guards already fire on
  subagent tool calls (both probed with `claude -p`). A `SubagentStart` handler injects a
  *subagent core*: the sections of `house-rules.md` marked as applying to subagents (docs tiers,
  evidence before claims, edit in place, commit only on own branches, artifacts in the project,
  nothing fails silently), generated from that one file, with its own size limit. It mandates that
  the final report lists every command run and its result verbatim.
- **Subagent work is checkable.** At `SubagentStart` the user is told the transcript's path. At
  `SubagentStop`, `verdict` also emits an audit summary built from the transcript itself - commands
  with exit status, files written/edited, tools used - shown to the user, plus an instruction to the
  main session to reconcile the subagent's report against it and flag every mismatch before relaying.
  `HOUSE_RULES_SUBAGENT_LEDGER=on` additionally renders the full transcript into `docs/sessions/`
  with `tools/session_ledger.py`'s renderer; off by default.

## Steps — one commit each, one PR, one version bump at the end

1. Size constant + `verify.py` limit check (fails now), then split `house-rules.md` into the core and
   its detail files, move the rationale into docs, and add the `Decisions.md` entry. Check passes.
2. Root `CLAUDE.md` → pointer; hook table to `docs/architecture.md`; move its verify check; cap it.
   Correct the "re-paid per subagent spawn" claim wherever it appears.
3. SessionStart docs-tier check, including the `.git/info/exclude` handling for repos you don't own; verify cases.
4. Subagents: `SubagentStart` subagent core + report mandate + transcript path; `verdict` audit
   summary + reconcile instruction; ledger toggle; verify cases.
5. Commit-time docs reminder in `guard`; verify cases on fixture repos (`claude/` branch and `main`).
6. `handover`: shell-fence gating + evidence check; verify cases.
7. `scope` rebalance; update its drift checks.
8. Version bump, `docs/ProjectState.md` / `Today.md` updated, `measure_footprint.py --repo` re-run
   and the before/after recorded.

Afterwards, as a separate PR: repo-wide `/house-rules:harvest-scan` and archivist pass.

## Done means

`python claude-house-rules/plugins/house-rules/scripts/verify.py` and
`python tools/verify_tools.py` exit 0; `inject` output ≤ the limit; a fresh `claude -p` probe
confirms the injected core arrives in full (no "Output too large").

## Result

All 8 steps landed, `45a2bc8`..`555129c` (12 commits, one a plan update: the size-constant split that started this
plan, through `scope`'s rebalance), plugin version bumped 2.30.0 → 2.31.0 in the commit that
closes this plan out. `python
claude-house-rules/plugins/house-rules/scripts/verify.py` and `python tools/verify_tools.py`
both exit 0 (336 and 39 checks respectively as of the closing commit).

`python tools/measure_footprint.py --repo`, before this plan (2026-09-22) vs. now:

| | Before | Now |
|---|---|---|
| `inject` (SessionStart) | 44,507 chars, combined with `profile` | 8,917 chars, `profile` split into its own hook (1,316 chars) - 10,233 combined, still under the two hooks' separate 9,000/9,500-char margins |
| `standards` (SessionStart) | 3,765 chars | 3,765 chars (unchanged - this hook was never part of the size problem) |
| root `CLAUDE.md` | 33,083 bytes | 3,151 bytes - a real pointer, not a second copy of the rules |
| `scope` short form | 260 chars | 222 chars (step-card line traded for a docs-tier line + an evidence line, doc-ref in `docs/Decisions.md`, 2026-09-23) |
| `scope` long form | 909 chars | 795 chars |

New per-hook costs this plan added, none of which existed on 2026-09-22:

| Handler | Event | Cost | Notes |
|---|---|---|---|
| `subagentrules` | `SubagentStart` | 2,324 chars (~581 tok) | The ONLY `additionalContext` a subagent ever sees - `inject`/`profile`/`standards` never reach it. Own budget, 4,500-char limit. |
| `announce` | `SubagentStart` | 168 chars (~42 tok) trace | Unchanged from before this plan. |
| `verdict` | `SubagentStop` | 175 chars (~43 tok) trace (no-transcript case; the audit summary is larger when one is found) | |
| `audit` | `PostToolUse` (`Agent`\|`Task`) | 126 chars (~31 tok) trace (no-transcript case) | Foreground half of the audit summary - reaches the parent MODEL, not just the user. |
| `userpromptaudit` | `UserPromptSubmit` | 136 chars (~34 tok) trace (no-transcript case) | Background half - a `run_in_background` call's hand-back turn. |

The headline finding this plan started from - `inject` emitting 44,506 chars against a proven
10,000-char per-hook limit, and `house-rules.md` doubling since the 2026-09-07 footprint plan -
is fixed: every `SessionStart` hook now measures well under its margin, verified by `verify.py`
on the real emitted output, not source file size, on every run.

`docs/ProjectState.md` and `docs/Today.md` updated to describe what this branch built, citing
`file:line` per the docs-tiers convention (`rules/detail/docs-tiers.md`: "Cite claims to
`file:line`. It is what makes an audit mechanical instead of a matter of opinion.").
