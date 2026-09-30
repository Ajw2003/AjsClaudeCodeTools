# house-rules efficiency review: findings and proposed changes

## Context

The user sees four or five "Claude Code notice" lines after every Write or Edit (guardwrite, artifact, harvest, branchnudge, and so on), and suspects the hooks overlap and the rule base is heavier than it needs to be. Three read-only audits (hooks, rule base, repo tooling) were run and their key claims spot-checked against the code. This is a report with ranked suggestions; nothing has been changed. Paths are relative to `claude-house-rules/plugins/house-rules/` unless stated.

Evidence status: file sizes, line counts and hook wiring were read from the code. Timings (293 ms via `run.sh` vs 80 ms direct) were measured by one audit agent on this machine. Process counts per tool call, the `verify.py` runtime and the 12-git-process figure for autosave are inferred from code, not measured. The trace behaviour (`scripts/hook.py:91-110`, `:2146`) was re-read by me and confirmed.

## APPROVED SCOPE (user approved; scope chosen: findings 1, 2, 3 only)

Findings 4-8 are out of scope for this run. Hand to `@house-rules:executor` with `isolation: "worktree"` (multi-file behaviour work).

### Change A: silence no-op traces (finding 1)
- `scripts/hook.py:91-110`: keep `trace()` for "could not tell" and "acted" messages. Add `trace_noop(message)` that emits only when `HOUSE_RULES_TRACE` is `verbose`. Default `on` therefore stops printing "looked, nothing to do". `off` still silences everything.
- Switch to `trace_noop` (success/no-op decisions): `:2146` (guardwrite new file), `:2262`, `:2265` (artifact), `:2326` (branchnudge own branch), `:2354` (not first change), `:2425`, `:2437`, `:2440` (runnable), guard allow at `:2021` (and the `allow_trace` systemMessage at `:2016-2017`), and the no-blocks case of the harvest trace (`:4782` `_harvest_trace` / `:4957`: emit by default only when blocks were found or overrides were bad; otherwise `trace_noop`).
- Keep as `trace()`: empty-payload / no-file_path / "could not tell" traces (`:1962`, `:2019`, `:2127`, `:2132`, `:2329`), `subagentcommit` (`:3295`) and `autosave ... saved` (`:3564`) since they record an action.
- Update `docs/architecture.md` (~`:452-460`) and `docs/4-systems/hook-engine.md` trace description; add the `verbose` value to wherever `HOUSE_RULES_TRACE` is documented.
- `scripts/verify.py`: update cases asserting the silenced text (e.g. `:1938`, `:2691` and any others found by grepping the messages above); add a case per behaviour: default run is silent on the no-op path, `HOUSE_RULES_TRACE=verbose` restores the message, "could not tell" still prints under default.

### Change B: cache the interpreter in `scripts/run.sh` (finding 2a)
- Cache file: `$HERE/.python-cache` if writable, else skip caching (never fail because the cache can't be written). It holds only a command that already passed `probe` (so the Windows Store stub can never be cached). Because the plugin directory is replaced on update, the cache resets on update.
- Flow: if `HOUSE_RULES_PYTHON` unset and cache exists, read it, and check the first word resolves (`command -v`); if it does, exec it with no probe. If the check fails or the file is unreadable, delete the cache and fall through to the existing probe order, then write the cache on success. `HOUSE_RULES_PYTHON` still wins and is still probed, unchanged. The no-interpreter fallback table stays as is.
- Keep `set -u`, sh-only dependencies, `py -3` handled as two words.
- `verify.py`: add cases for cache written on first run, cache used (second run skips probing), stale cache (points at a missing binary) recovers, stub interpreter never cached, read-only dir still works.
- Measure before/after: median of 5 runs of `sh run.sh nosuchevent`.

### Change C: `.git/HEAD` fast path in `_autosave_target` (finding 3)
- `scripts/hook.py:3386`: after resolving `path`, call existing `_git_dir(...)` (`:1872`, already handles worktree `.git` files) and read `HEAD` (as `branch_ownership()` does at `:1892`). If HEAD is not `refs/heads/worktree-agent-*` return `None` without any git subprocess. Only then fall through to the current `_repo_top` / `_repo_branch` calls (or derive the top from the git dir found) for matching branches. Keep the "could not tell" loudness: an unreadable HEAD raises, as the current code does.
- `commitgate` shares `_autosave_target`, so it benefits automatically; confirm by reading its call site (`:3571`).
- `verify.py`: add cases for non-subagent branch (no git subprocess spawned; assert via a PATH with a `git` stub that records calls), subagent branch (unchanged behaviour), detached HEAD, worktree `.git` file.

### Housekeeping for this run
- Bump plugin version (CI `check_plugin_version_bump.py` enforces it) and note the change in `docs/3-state/ProjectState.md`, `docs/5-today/Today.md`, and `docs/4-systems/hook-engine.md`.
- Commit on this branch (`claude/hooks-efficiency-review-32732b`), scoped to changed paths. Copy this plan to `docs/plans/hooks-efficiency-review.md` (artifact rule).
- Do not touch findings 4-8; list them in `docs/2-roadmap/Roadmap.md` as follow-ups.

### Verification (must be quoted from real runs)
- `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
- `python tools/verify_tools.py` exits 0.
- `python tools/measure_footprint.py --repo` before/after.
- Real run: pipe a sample Write and Edit PostToolUse payload through `sh run.sh <handler>` for artifact, branchnudge, harvest and runnable, and show default output is empty on the no-op path and non-empty under `HOUSE_RULES_TRACE=verbose`.
- Timing: median of 5 runs of `sh scripts/run.sh nosuchevent` before and after (baseline 293 ms).
- Screenshot check is not possible from the CLI; the user confirms the transcript noise is gone in a fresh session.

## Findings, ranked by payoff

### 1. Every no-op hook path prints a transcript notice (the screenshot)
- `trace()` (`scripts/hook.py:101`) is on by default and emits one `systemMessage` per handler, even when the handler decided nothing. Examples: "does not exist yet - a new file" (`:2146`), "not a document extension - not checked" (`:2262`), "not the first change, no nudge" (`:2354`), "no comment runs found".
- A Write of a source file gives four to five notices; an Edit gives three. On `worktree-agent-*` branches `autosave` adds another per call, including Bash.
- Each is a separate transcript entry, so the cost is tokens plus scroll noise. The design comment defends it under "nothing fails silently", but that rule is about *couldn't tell*, not *looked, nothing to do*, which the house rules themselves define as legitimately silent.
- Fix: trace only when a handler acted, blocked, or could not decide. Keep `HOUSE_RULES_TRACE=on` as a full-verbosity debug mode.

### 2. Too many processes per tool call, and the shim is slow
- Every hook entry is `sh run.sh <handler>`. `run.sh` probes `python3` first (a Windows Store stub here, about 65 ms, prints nothing), then `python`, then execs `hook.py`. Measured: about 293 ms per call via the shim against about 80 ms for `hook.py` directly.
- A Write fires seven entries, an Edit five, a Bash two. SessionStart fires seven (five house-rules plus one each from agent-router and prompt-workshop); UserPromptSubmit fires five.
- `hook.py` is 219 KB and 5,053 lines and is re-parsed on every call.
- Fix, in order of ease: (a) cache the resolved interpreter next to the plugin, or try `python` first on Windows; (b) merge same-event handlers into one dispatcher per event/matcher: PostToolUse `Write|Edit|...` (artifact, runnable, branchnudge, harvest, autosave) and PreToolUse (guardwrite, commitgate), with one payload parse and one combined JSON message; (c) later, split `hook.py` into per-event modules behind a thin dispatcher.

### 3. Git subprocesses run before cheap checks
- `autosave` and `commitgate` both call `_autosave_target` (`scripts/hook.py:3386`), which runs `git rev-parse` and `git symbolic-ref` before checking for a `worktree-agent-` branch, on every Write, Edit and Bash call in every repo. `branch_ownership()` (`:1892`) already reads `.git/HEAD` for free.
- Inside a subagent worktree, each call also does a snapshot (`read-tree`, `add -A`, `write-tree`, `commit-tree`, `update-ref`, throttled push).
- Fix: check the branch from `.git/HEAD` first; snapshot only when dirty and the last snapshot is over 60 s old; share one git wrapper (there are three: `:1799`, `:3363`, `:4189`).

### 4. Duplicated logic inside `hook.py`
- File-path extraction exists in two forms (regex on raw JSON, `json.loads`); base-name splitting and empty-payload handling repeat per handler; repo and branch resolution exists in four forms. A merged dispatcher (finding 2) removes most of this for free.

### 5. Rule-base weight and repetition
- Injected once per session: about 5.5k tokens (rules 2.2k, profile 0.4k, standards 0.9k, plus `CLAUDE.md` and the forced output style). Every prompt: 65 or 227 tokens. Every subagent spawn: about 700 hook tokens plus 0.8k (executor) or 2k (archivist). Every ExitPlanMode: about 460 tokens.
- Repeated in several places (savings in tokens are approximate):
  - Handover six-field list: `rules/house-rules.md:114-124`, `output-styles/handover-cards.md:44-63`, `HANDOVER_NOTE` (`scripts/hook.py:3872`), `agents/executor.md`. Keep the output style as the single carrier; drop it from `house-rules.md` (about 250 tokens) and trim the style's history prose (about 300 tokens).
  - Evidence/verification: `house-rules.md:61-67` and `:90-106`, both scope reminders, `RUNNABLE_NOTE`, `COMPILE_NOTE`. Fold green-suite, shim-compiles and reported-update into the evidence section or move them to on-demand detail.
  - "See `<plugin>/rules/detail/x.md`" on all 26 sections (about 425 tokens): state the naming convention once.
  - Delegation exception "one file AND ≤3 steps" appears in four places.
- Rules that duplicate hooks and can be shortened to one line: hidden/background processes (guard patterns), git commit rules (`commitgate`, `branchnudge`), machine profile (`profile` hook). Rarely-needed rules (open-source-first, build-alone, voice) can move to on-demand detail.
- Stale: `docs/architecture.md:460` says `inject` is about 6,200 tokens; measured is about 2,243.

### 6. Rules that conflict or over-fire
- "Commit constantly" vs the guard: only `claude/` branches are exempt, so on any other branch every commit prompts.
- Autosave uses `git add -A`, against the rule "commit scoped to changed paths".
- `SUBAGENT_MANDATE` (`scripts/hook.py:2570`) tells every subagent to report every command verbatim, including read-only Explore agents, and fights short-report requests. Skip it for read-only agent types.
- Delegation costs about 1.5k tokens of spawn overhead, and the trigger regex matches loose words ("proceed", "implement"). A 2-file, 4-step change pays full price.
- Handover check fires on any bash fence missing the card markers (about 556 tokens each), including illustrative fences.
- "A non-blocking check still announces it ran" (`house-rules.md:57`) contradicts deliberately silent `docstiers` and `handover`; finding 1 resolves this in favour of the silence definition already in the rules.

### 7. Docs tiers: mandatory, so leave the enforcement alone
- Correction from the user: docs are not optional. The six tiers are a mandatory, continuously maintained database in every repo, and that is the only way docs are useful. An earlier draft of this finding proposed a once-per-project offer and dropping the per-prompt docs line. **That is withdrawn.**
- Keep as is: the every-session `docstiers` nag (`scripts/hook.py:934-1030`, about 112 tokens, and only while tiers are missing, so it stops on its own once fixed), the docs line in both per-prompt reminders, and the commit-time `DOCS_COMMIT_REMINDER` (`:1856`).
- The only efficiency work worth doing here: (a) make the nag cheaper to *resolve* rather than rarer, e.g. name the exact scaffold command or skill (`house-rules:project-docs`) so one step clears it; (b) resolve the wording conflict with "build only what was asked" in `rules/house-rules.md` by stating that keeping the tiers current is part of every request, not scope creep; (c) dedupe the *text* of the rule where it repeats (`house-rules.md:28-34`, both reminders, the hook note), keeping one short imperative per surface and cutting only the repeated rationale.

### 8. Repo-level maintenance
- `verify.py` is 298 KB, about 173 hook invocations each going through `run.sh` (add about 290 ms each; total runtime unmeasured but likely a minute or more). Test hook logic by calling `hook.py` directly, keeping a small set of shim tests.
- `run.sh` is copied into three plugins (64-131 lines each), with `read_payload`, `emit` and `report()` also duplicated in each `hook.py` and `verify.py`. Extract one shared shim.
- Offshoot overlap on UserPromptSubmit: `route` (agent-router) and `scope`'s delegate clause both nudge toward delegation; `route` ends in `except Exception: pass` (about `:214`), which breaks the "nothing fails silently" rule.
- issue-forge (in commit `54594fc`, unmerged) registers two PostToolUse entries with the same `suggest` command; merge into one matcher before it lands.
- `worktreesweep` runs `git worktree list` on every prompt and made a `--no-verify` "wip: parent checkpoint" commit (`54594fc`) that swept a whole plugin. WIP commits are never squashed. Add a squash step at merge time and skip the walk when no `worktree-agent-*` exists.
- Docs: `docs/architecture.md` (81 KB) predates the tiers and overlaps `docs/4-systems/hook-engine.md`; `docs/plans/` has 28 mostly-implemented files (333 KB) never archived; loose files outside the tiers (`desktop-verification.md`, `architecture-backlog.md`, and others); `artifact-test.html` at the repo root and `.claude/skills/grill-me` (duplicated by the `grilling` skill) look dead. Confirm before deleting.

## Suggested order of work (each a separate, small change)

1. Silence no-op traces (finding 1). Smallest change, removes the visible noise. Files: `scripts/hook.py` (the `trace()` call sites), `scripts/verify.py` cases that assert trace text.
2. Interpreter caching in `scripts/run.sh`, or `python`-first on Windows (finding 2a).
3. `.git/HEAD` fast path in `_autosave_target` (finding 3).
4. Merge PostToolUse and PreToolUse handlers into one dispatcher each; update `hooks/hooks.json`, `verify.py`, `docs/architecture.md` and `docs/4-systems/hook-engine.md` (finding 2b).
5. Rule-text dedup and stale-doc fixes (findings 5, 6, and 7a-c; docs enforcement itself unchanged).
6. Repo hygiene and `verify.py` speed-up (finding 8).

Each change that touches `hook.py`, hooks or rules needs a `verify.py` case in the same change (repo rule) and a plugin version bump (CI-enforced).

## Verification for any change made from this list
- `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
- `python tools/verify_tools.py` exits 0.
- `python tools/measure_footprint.py --repo` before and after, to show the token change.
- Time a Write hook chain before and after (per-call wall time) and screenshot the transcript notices for the same Write/Edit flow.

## Decisions needed from the user
- Is the always-on trace worth keeping at all, or should it become a debug mode?
- Which items to implement now (recommended: 1, 2 and 3 first).
