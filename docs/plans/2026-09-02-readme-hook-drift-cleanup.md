# Docs drift cleanup

## Context
Commit 154aff1 added a seventh hook (delegate.sh on PostToolUse/ExitPlanMode). CLAUDE.md and verify.sh were updated; claude-house-rules/README.md only partly. Fix the README and widen the existing drift check so it cannot recur.

## Changes

### 1. claude-house-rules/README.md
- Line 8: currently "Six hooks on five events, all defined in [plugins/house-rules/hooks/hooks.json](...)". Drop the spelled-out count entirely rather than correcting it to "Seven" — same reasoning the README already applies to the verify check count. Reword to e.g. "Every hook, defined in [plugins/house-rules/hooks/hooks.json](plugins/house-rules/hooks/hooks.json):". The seven-row table below is already correct; leave it.
- Lines ~100-103: the paragraph listing rules with no shell signature ("match response depth to the task, the fixed environment, build only what was asked, docs-before-research, build for a human working alone, the user's hands are for decisions not labour"). Add the delegation rule ("once the approach is decided, delegate the execution") into the exceptions, and change "Two are exceptions" (line ~105) to three, adding a third bullet alongside the existing two ("Deliver a whole workflow" / "Never hand over a command I have not run"): the delegation rule is enforced at PostToolUse on ExitPlanMode, where delegate.sh names @house-rules:executor the moment a plan is approved. Match the surrounding prose voice.
- Table at line ~178 ("Testing that the hooks are actually live"): add a row for `PostToolUse` on `ExitPlanMode` — how to see it: approve any plan out of plan mode; what proves it: a delegation nudge naming @house-rules:executor comes back to Claude, you are not prompted.

### 2. CLAUDE.md (repo root)
Heading "### The plugin is seven hooks on five events, nothing else" — reword to drop the number, e.g. "### The plugin is hooks on five events, nothing else". Keep the rest of that section. Required by change 3.

### 3. claude-house-rules/plugins/house-rules/scripts/verify.sh
Widen the EXISTING check at ~line 552 ("the architecture table in CLAUDE.md matches hooks.json"). Do not add a new numbered check.
- It currently sets DOC="$ROOT/CLAUDE.md". Make the per-doc part loop over "$ROOT/CLAUDE.md" and "$ROOT/claude-house-rules/README.md", keeping the existing row-only TABLE extraction regex (verify it matches the README's table rows, whose first cell is like `| `PreToolUse` on `Bash` / `PowerShell` |` — it starts with the backticked event name, so the existing regex should match; check by running it).
- The "exists but hooks.json does not register it" direction is repo-wide: run it once, not per doc.
- Keep the existing 'four hooks, nothing else' guard, and add next to it: fail if either doc matches -iE '(four|five|six|seven|eight|nine) hooks' — a spelled-out hook count is exactly what went stale.
- Make the drift messages and the PASS/FAIL report line name which doc (report line doc-agnostic, e.g. 'the architecture tables match hooks.json').
- Keep the suite's self-computed check count; do not hardcode numbers.

## Verification (run it, report real output)
PowerShell 5.1, from the worktree root:
& "C:\Program Files\Git\bin\sh.exe" claude-house-rules/plugins/house-rules/scripts/verify.sh
Expect RESULT: PASS - all N checks passed, exit 0.
Then prove the widened check has teeth: temporarily put the words "Six hooks" back into the README, re-run, confirm that check FAILs and names the README, then revert the README to the fixed text and re-run to PASS again.

### 4. Copy the plan into the project
Write the plan above (the full text of this PLAN section, formatted as the original markdown document) to docs/plans/2026-09-02-readme-hook-drift-cleanup.md — house rules require artifacts live in the project as real files.

Report back: files changed, the final verify.sh output, and the FAIL output from the teeth test.
