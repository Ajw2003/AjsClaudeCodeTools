# Today — 2026-09-15

Documentation day: scaffolding the five missing documentation tiers, at the user's request after
an audit surfaced that this repo's own `docs/` never carried them.

## What was done

- Confirmed, by listing `docs/` and reading
  [`docs/archive/2026-09-15-sixth-documentation-tier.md`](archive/2026-09-15-sixth-documentation-tier.md),
  that only Tier 6 (`Decisions.md`) and the three non-tier folders existed; Tiers 1-5 were
  entirely missing and the gap was already named as deliberately out of scope in that plan.
- Read the code directly rather than templating placeholders: `hook.py`, `verify.py`,
  `install.py`, `hooks.json`, both offshoot plugins' `hook.py`/`verify.py`, and every relevant
  existing doc (`CLAUDE.md`, `architecture.md`, `offshoots-plan.md`, both backlog docs, all three
  plugin READMEs).
- **Ran all four verify suites** rather than assuming they pass, since the roadmap tier's own
  rule is that "done" means checked, not that the code exists:
  `claude-house-rules/.../verify.py` (203 PASS), `claude-agent-router/.../verify.py` (41 PASS),
  `claude-prompt-workshop/.../verify.py` (22 PASS), `tools/verify_tools.py` (32 PASS).
- Wrote Tier 4 first, per the skill's own scaffolding order: four system docs
  (`hook-engine.md`, `verify-suites.md`, `plugin-distribution.md`, `offshoot-plugins.md`) plus
  `systems/README.md` indexing them and naming what was deliberately left out.
- Wrote Tier 2 (`Roadmap.md`, four milestones) and Tier 3 (`ProjectState.md`, status against
  each, plus cross-cutting issues that belong to no milestone).
- Wrote Tier 1 (`README.md`) last of those four, so its index describes what now actually exists.
- Wrote this file (Tier 5) last of all six.

## What was deliberately not done

- **No content was invented.** Every percentage and status claim in `Roadmap.md`/`ProjectState.md`
  traces to either a verify-suite run today or an existing doc; nothing was guessed to fill a row.
- **`docs/Decisions.md` was not touched.** Scaffolding tiers 1-5 under an already-decided
  convention isn't itself a new decision worth logging there — see
  [`ProjectState.md`](ProjectState.md) instead for what changed.
- **`architecture-backlog.md` and `rules-backlog.md` were not folded into `Decisions.md`**, even
  though the plan that created Tier 6 names them as the exact ad hoc pattern it was meant to
  replace. They're still open queues, not settled decisions, so migrating their *shape* wasn't
  this session's call to make silently — flagged in `ProjectState.md` instead.
- **Stray root-level items were not cleaned up**: `Modified.md` (an empty directory), the
  `artifact-test.html` smoke test, `skills-lock.json`, and five leftover `.claude/worktrees/`
  directories. Noticed while auditing, not asked about, so left alone and named in
  `ProjectState.md`'s cross-cutting section instead of acted on.
- **CLAUDE.md was left as a pointer**, per the skill's own last scaffolding step — it should point
  at `docs/README.md` rather than duplicate any of this; that edit is the one thing still open
  from today's list, below.

## What got surfaced that is not today's job

- `docs/sessions/` has one ledger entry despite `session_ledger.py` existing since before that
  date — running it isn't yet a habit.
- The offshoot plugins' classifiers are unvalidated against real traffic, by their own authors'
  admission in `offshoots-plan.md` — not something today's audit discovered, but worth carrying
  forward as the actual next milestone-moving work rather than more documentation.

## What to do next, in order

1. **Point `CLAUDE.md` at `docs/README.md`** as the entry point, per the skill's own last
   scaffolding step — the one step from today's list not yet done.
2. **Decide what to do with the two backlog docs** now that Tier 6 exists to hold settled
   decisions — leave them as queues, fold resolved entries into `Decisions.md` as they ship, or
   something else, but as a deliberate call rather than by default.
3. **Give the offshoot plugins real tuning data** — this is what would actually move milestone 3
   in `Roadmap.md`, and no amount of further documentation substitutes for it.
4. **Clear or explain the stray root items** named in `ProjectState.md`'s cross-cutting section.
