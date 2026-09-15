# Plan: prevent concurrent subagent delegations from clobbering a shared checkout

## Incident

Two `Agent` calls delegating implementation work ran against the same working directory at the
same time, neither passing `isolation: "worktree"`. Both edited the same files concurrently,
corrupting the checkout. Separately, a `SubagentStop`/task-completion notification that only
reported a status update ("I've launched...", "I'll report back...") was read as the task being
finished, which is part of how the duplicate dispatch happened in the first place.

Two conversation forks diagnosed this independently. This plan follows the second fork's
diagnosis, which separates the incident into three distinct, separately-fixable causes instead of
two, and lands the fix at the layer each cause actually lives at rather than proposing a new
`PreToolUse` hook whose matcher target (`Task` vs `Agent`) was never resolved.

## The three causes and what fixes each

1. **Concurrent edits to a shared checkout (the actual damage).** Neither delegation passed
   `isolation: "worktree"`. Fixed by making worktree isolation the documented, mandatory default
   for exactly this kind of delegation — in the two places that already govern it — rather than a
   new hook. Mechanical, and closes the actual risk: two isolated worktrees cannot clobber each
   other regardless of any later judgement error.
2. **A hollow "stop" read as real completion.** `verdict` (the `SubagentStop` handler) already
   opens the subagent's own transcript to compare declared vs. observed model. It can cheaply
   extend that same read to flag a completion that looks hollow: zero tool calls across the whole
   transcript, or a final message that reads like a deferral. Like everything else `verdict`
   reports, this can only warn — `SubagentStop` can't block — but a loud, named warning is exactly
   what would have stopped the second delegation from being trusted.
3. **"Is another copy of this already running?"** is inherently cross-invocation state, and this
   plugin has a hard, deliberately tested rule against hooks keeping state between invocations
   (`verify.py` fails the suite if `hook.py` ever does). The host app already tracks live agents
   (`ListAgents` / `TaskOutput`), so this is a house rule telling Claude to consult that live
   registry before relaunching a delegation — not a new stateful file.

## Steps

### 1. Mandate worktree isolation for multi-file/behavior-changing delegations

- **`claude-house-rules/plugins/house-rules/rules/house-rules.md`**, in the "Once the approach is
  decided, delegate the execution" section: add a paragraph stating that any delegation to
  `@house-rules:executor` (or any implementation delegation) that touches more than one file, or
  changes behavior rather than just reading, passes `isolation: "worktree"` on the `Agent` call —
  so two concurrent delegations can never land in the same working directory. Include a `**Why:**`
  line naming the concurrent-edit corruption this incident produced.
- **`claude-house-rules/plugins/house-rules/scripts/hook.py`**, `DELEGATE_NOTE` (around line 1073):
  add a clause instructing that the `Agent` call use `isolation: "worktree"` for a multi-file or
  behavior-changing delegation, worded to match the new house-rules.md paragraph (this repo's
  convention: reworded phrases must be kept in sync between `house-rules.md` and `hook.py`'s
  hardcoded reminder strings, or `verify.py`'s drift checks fail).
- **`claude-house-rules/plugins/house-rules/agents/executor.md`**: add one line to the digest
  noting the executor runs inside an isolated worktree for multi-file work, and that uncommitted
  changes in its working directory it did not make itself mean another delegation's work is
  already there — stop and ask rather than build on top of it.

### 2. Add a completion-sanity check to `verdict`

- In **`hook.py`**, extend the transcript read used by `event_verdict()` (currently
  `_observed_models`, around line 1336) to also return: total count of `tool_use` content blocks
  across all assistant entries, and the concatenated text of the *last* assistant entry's text
  blocks.
- Add a small tuple of deferral phrases (e.g. "i'll report back", "i will report back", "i've
  launched", "i'll get started", "i'm about to start") matched case-insensitively against that
  last-message text.
- In `event_verdict()`, after the existing MATCH/MISMATCH reporting, append one more `bits` entry
  when either signal fires:
  - Zero tool calls across the whole transcript despite one or more assistant turns → e.g.
    `"SUSPICIOUS COMPLETION: 0 tool calls across N assistant turns - this may be a status update, not finished work; verify concrete deliverables before trusting it"`.
  - No zero-tool-call flag, but the last message matches a deferral phrase → a similarly worded
    warning naming the phrase.
  - Zero-tool-calls takes priority over the phrase check when both would fire, so only one
    warning is emitted per finish.
  This only ever appends to the existing `systemMessage` — `SubagentStop` still can't block, same
  as the MISMATCH case today.

### 3. House rule: check the live registry before relaunching

- In **`house-rules.md`**, add a short new rule (or a paragraph in an existing nearby one — use
  judgement on the best fit while writing) stating: a subagent stopping is not the same as its
  task finishing, and a `SubagentStop`/background-task notification reporting only a status update
  is not a report of concrete deliverables. Before treating a delegation as done, or relaunching
  one, check whether a copy of it is already running via `ListAgents`/`TaskOutput` — the plugin
  cannot track this itself (no hook keeps state between invocations, and that constraint is
  intentional), so the live registry the host app already maintains is the source of truth.
  Include a `**Why:**` line naming this incident.

### 4. Tests (`claude-house-rules/plugins/house-rules/scripts/verify.py`)

- A literal-drift check (same shape as the existing `_declared`/announce check around line 2658):
  assert `DELEGATE_NOTE` mentions `isolation` and `worktree`, and assert `house-rules.md`'s
  delegation section also mentions them — catches the two drifting apart.
- Extend the `_assistant()` transcript-fixture helper (verify.py ~line 2618) to accept content
  blocks (text and/or `tool_use`), so fixtures can express "zero tool calls" and "text ending in a
  deferral phrase" transcripts alongside the existing model-only ones.
- A new transcript fixture with assistant turns that carry text content but no `tool_use` blocks
  at all → assert `verdict`'s output contains `SUSPICIOUS COMPLETION` and `0 tool calls`.
- A new transcript fixture with one `tool_use` block (so the zero-tool-calls path does not fire)
  whose last assistant text matches a deferral phrase → assert the output flags it by name.
- A transcript with a normal multi-tool-call turn ending in an ordinary summary (no deferral
  phrase, tool calls present) → assert `SUSPICIOUS COMPLETION` does NOT appear, so the check does
  not false-positive on an ordinary "did the work, then reported back" finish.
- Confirm this new reporting is silenced by `HOUSE_RULES_DELEGATION=off` and NOT by
  `HOUSE_RULES_TRACE=off`, matching the existing test pattern for `verdict`'s MATCH/MISMATCH
  reporting just above it.

### 5. Run the suite and commit

- `python claude-house-rules/plugins/house-rules/scripts/verify.py` — must be 0 failures.
- Commit on this branch (`claude/subagent-checkout-isolation`), scoped to the paths actually
  changed. Do not push or open a PR — report back what ran and what changed.

## What this plan deliberately does not do

- No new `PreToolUse` hook or matcher. Fork 1's proposal hinged on an unresolved question (does
  the harness's subagent-launch tool call match `Task` or `Agent`) that fork 2's approach avoids
  entirely by fixing the problem at the instruction layer instead.
- No new stateful file or hook tracking "which delegations are currently running" — that would
  contradict this plugin's own tested no-state-between-invocations rule. Cause 3 is a behavioral
  rule pointing at the harness's own live registry, not new code.
