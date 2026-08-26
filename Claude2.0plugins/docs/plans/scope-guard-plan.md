# Plugin: `scope-guard` — behavioral guardrails, not just prompted rules

## Context

Fixes five recurring behaviors when working with Claude:

1. Rambling/over-reasoning on problems that don't need it
2. Deciding instead of asking when a requirement is ambiguous
3. Doing more work than needed instead of the simplest path
4. Handing over deliverables that need manual setup (manual `cmd` run, manual server start)
5. Building for hypothetical scenarios ("what if X/Y/Z") beyond what was asked

Hooks fire only at fixed, mechanical checkpoints (prompt submitted, tool about to run, tool finished, response finished) — they cannot see inside reasoning. That splits the five issues:

- **Issue 4 is mechanically checkable**: "was a script/config file written, and did a Bash/PowerShell command run afterward" is observable via tool-call names, with zero NLP.
- **Issues 1, 2, 3, 5 are judgment calls inside the reasoning itself.** No hook can detect "this was rambling" or "this was ambiguous." The lever used is the same one the existing `house-rules` plugin already uses: a `UserPromptSubmit` hook that force-injects rule text into *every single turn* as `additionalContext`, so enforcement never depends on a skill being semantically matched. A skill (`scope-check`) supplements this with a fuller, on-demand checklist — it is not the primary enforcement.

## What was built

```
ClaudePlugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── scope-check/
│       └── SKILL.md               # on-demand full checklist for issues 1,2,3,5
├── hooks/
│   ├── hooks.json
│   └── scripts/
│       ├── inject-rules.js        # UserPromptSubmit — force-injects the 4-bullet rule text every turn
│       ├── track-write.js         # PostToolUse(Write) — records newly-written "runnable" files
│       ├── clear-pending.js       # PostToolUse(Bash|PowerShell) — clears the record once something is actually run
│       └── check-deliverable.js   # Stop — blocks once with a reason if a runnable file was written but never run
└── docs/plans/scope-guard-plan.md # this file
```

Scripts are Node (v22.19.0, confirmed installed) instead of PowerShell 5.1/batch, for reliable JSON in/out.

### Issue 4 mechanism — Stop hook + per-session state file

No reliance on the undocumented `transcript_path` JSONL format. Instead:

- `track-write.js` (`PostToolUse`, matcher `Write`): if the written file looks runnable (`.py .js .mjs .cjs .ts .sh .ps1 .bat .cmd`, `Dockerfile`, `docker-compose.yml`), appends its path to `hooks/state/<session_id>.json`.
- `clear-pending.js` (`PostToolUse`, matcher `Bash|PowerShell`): clears that session's state file — something was actually executed.
- `check-deliverable.js` (`Stop`): if `stop_hook_active` is true, allows silently (no nag loop). Otherwise, if the state file is non-empty, returns `decision: block` naming the unrun file(s), then clears the file so it only nags once.

### Issues 1/2/3/5 mechanism — always-on `UserPromptSubmit` injection

`inject-rules.js` prints a fixed `additionalContext` block on every prompt:

```
Standing behavior rules (scope-guard):
- Match response depth to task complexity — don't reason at length about simple problems.
- If a requirement is ambiguous, ask; do not guess and proceed.
- Take the simplest, most direct path that satisfies exactly what was asked.
- Do not build for hypotheticals ("what if X/Y/Z") beyond what was actually requested.
```

### `skills/scope-check/SKILL.md`

Fuller version of the same 4 rules plus a self-audit checklist, invocable as `/scope-check` and loadable by Claude before finalizing a plan or large change — a supplement, not a replacement, for the hook.

## Verification performed

1. `hooks.json` / `plugin.json` — valid JSON (checked with `node -e "JSON.parse(...)"`).
2. Each script tested standalone with crafted stdin, all branches:
   - `inject-rules.js` → correct `additionalContext` JSON.
   - `track-write.js` → records `.py`/`.js` files, ignores `.md`.
   - `clear-pending.js` → removes the session's state file.
   - `check-deliverable.js` → silent when `stop_hook_active:true`; silent when nothing pending; blocks with the right file list and reason when something is pending, then clears state.
3. `claude --plugin-dir "C:\Users\aj\Desktop\ClaudePlugin" plugin list` → plugin loads cleanly as `scope-guard@inline`, no errors.

## Install (decision pending with user)

Two supported routes, not yet chosen:

- **`~/.claude/skills/scope-guard/`** — copy the plugin there; auto-loads every session with zero ongoing action. This changes the user's persistent global Claude Code config, so it needs their explicit go-ahead before doing it.
- **`/plugin marketplace add` + `/plugin install`** — REPL-only slash commands the user must run themselves; requires adding a `marketplace.json` (schema not independently verified/tested here).
