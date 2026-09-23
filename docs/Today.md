# Today — 2026-09-23

Executed [`docs/plans/2026-09-22-rules-that-actually-load.md`](plans/2026-09-22-rules-that-actually-load.md)
end to end, all 8 steps, across 11 commits (`9e7e780`..`555129c`; this file's own update is the
closing one). See that plan's own `## Result` section for the full before/after footprint numbers.

## What was done

- **Size fix (steps 1-3).** Split `inject` from `profile` (separate `SessionStart` entries, each
  under its own per-hook budget), moved the hook table from `CLAUDE.md` to
  [`docs/architecture.md`](architecture.md) and shrank `CLAUDE.md` to a 3,151-byte pointer (from
  33,083), and added `docstiers`, a stateless `SessionStart` check for the six documentation
  tiers.
- **Subagent visibility (step 4).** A `SubagentStart` handler (`subagentrules`) re-injects a
  subagent-scoped core of the rules — `SessionStart`'s own `additionalContext` never reaches a
  spawned subagent, probed with `claude -p`. `verdict` (`SubagentStop`) gained an audit summary
  built from the subagent's own transcript, and two more handlers (`audit` on `PostToolUse`,
  `userpromptaudit` on `UserPromptSubmit`) carry that summary to the parent MODEL, not just the
  user, since `SubagentStop`'s own output was found not to reach it in-turn.
- **Commit-time docs check (step 5).** `guard` now recognizes a `git commit` and computes the
  EFFECTIVE set of files it will include — not just what's staged right now, since `guard` fires
  before the command it judges runs — covering `-a`/`-am`, an earlier `git add` in the same
  command (`shlex`-tokenized), and `git add .`/`-A`/`-u`. A staged source file with nothing under
  `docs/` gets a reminder; the one place `guard` shells out, under a shared 2-second budget that
  never changes its own decision on failure.
- **`handover` narrowed and extended (step 6).** Its card check now fires only on a
  shell-labelled fence, not any fence. An independent evidence check fires when a reply claims
  success with no tool run since the last genuine user message and no quoted evidence.
- **`scope` rebalanced (step 7).** Traded its step-card line (now enforced live by `handover`
  itself) for a docs-tier line and an evidence line, in both forms, within 10% of each form's
  prior size.
- **Version bump and this file (step 8).** Plugin version 2.30.0 → 2.31.0;
  [`docs/ProjectState.md`](ProjectState.md) updated with the new check counts and what changed.

## What was deliberately not done

- **The repo-wide `/house-rules:harvest-scan` and archivist pass** the plan names as a follow-up
  is explicitly a separate PR, not part of this one.
- **No new offshoot-plugin work.** This plan touched only `house-rules`.

## What to do next, in order

1. The separate PR: `/house-rules:harvest-scan` across the repo, then an archivist pass on
   anything it flags.
2. Everything still open in [`ProjectState.md`](ProjectState.md)'s Cross-cutting section — none
   of it was touched by this plan.
