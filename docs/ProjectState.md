# Project state

Where things actually stand against [`Roadmap.md`](Roadmap.md), as of 2026-09-23.

**Headline: ~85%.** Three of four milestones are done against their acceptance criterion; the
fourth (offshoot plugins) ships and verifies but its actual judgment quality is unmeasured.

| Milestone | Status |
|---|---|
| 1. Hook engine | 100% — `verify.py` 336/336 PASS (2026-09-23) |
| 2. Six-tier docs convention | 100% as a mechanism; this repo's own adoption tracked below |
| 3. Offshoot plugins | 50% — mechanism verified, classifiers unvalidated |
| 4. Distribution & install tooling | 100% — `verify_tools.py` 39/39 PASS (2026-09-23) |

## 1. Hook engine — built and verified

What's built: nineteen handlers, dispatched statelessly, each with the fail-mode its rule
requires (`guard`/`guardwrite` closed, `inject`/`standards`/`docstiers`/`versioncheck` loud,
`scope`/`userpromptaudit` unable to erase the prompt, the `PostToolUse` handlers never
obstructing, `handover`/`announce`/`subagentrules`/`verdict`/`audit` open and loud). The
2026-09-22 "rules that actually load" plan (`docs/plans/2026-09-22-rules-that-actually-load.md`,
see its own `## Result`) closed the gap where `inject` emitted 44,506 chars against a proven
10,000-char per-hook limit ([`claude-house-rules/plugins/house-rules/scripts/hook.py:71`](../claude-house-rules/plugins/house-rules/scripts/hook.py#L71),
`INJECT_CHAR_LIMIT`), added a `SubagentStart` handler that re-injects a subagent-scoped core of
the rules (`hook.py:1886`, `_subagent_core`) since `SessionStart`'s own `additionalContext` never
reaches a spawned subagent, and added a commit-time docs-tier reminder to `guard` itself
(`hook.py:1174`, `_staged_docs_status`) rather than only once per session. What's not built:
nothing against the current rule set — the seven candidate refactors in
[`docs/architecture-backlog.md`](architecture-backlog.md) are real friction (see Cross-cutting,
below) but none blocks this milestone's own acceptance criterion, which is about behavior, not
code shape.

## 2. Six-tier docs convention — mechanism done, this repo's adoption just started

The plugin-side mechanism (skill, routing, drift checks) has been verified since before this
document existed. This repo's own `docs/` did **not** carry tiers 1, 2, 3, 4, or 5 until today —
only tier 6 (`Decisions.md`, added 2026-09-15) and the three non-tier folders (`plans/`,
`archive/`, `generated/`) existed. Today's session scaffolded the other five
(`README.md`, `Roadmap.md`, this file, `systems/*.md`, `Today.md`) by reading the code directly,
per the skill's own scaffolding order (tier 4 first, tier 5 last). That scaffolding is what
this document is part of.

## 3. Offshoot plugins — real but unvalidated

Both `prompt-workshop` and `agent-router` are fully wired, not stub code, and both verify
suites pass. What's missing is everything that would turn "the mechanism works" into "the
mechanism is worth trusting": no tuning against real prompt traffic, no
`SubagentStart`/`SubagentStop` visibility parity with `house-rules`, no handling for a prompt
that spans two of `agent-router`'s tiers. These are stated as open by
[`docs/offshoots-plan.md`](offshoots-plan.md), not discovered here.

## 4. Distribution & install tooling — built and verified

`install_steps()`'s four-command order, `bootstrap.ps1`/`.sh`, `update.bat`, and both
verification scripts (`clean_install_test.py`'s logic, `verify_tools.py` itself) are all in
place and `verify_tools.py` passes. The one thing this document does *not* claim: that the real
`claude` CLI sequence was re-run today. It wasn't — see "the one thing that is not what it looks
like," below.

## The one thing that is not what it looks like

**This document, and the four other tiers scaffolded alongside it today, will read as a mature,
long-standing documentation practice — tables, percentages, `file:line` citations — when they
are in fact a same-day first draft, assembled by reading the code once.** None of them has yet
been through the cycle that's supposed to keep them honest: `Today.md` rewritten at the start of
a session, `ProjectState.md` updated when a milestone's status actually changes, a tier-4 doc
revised because its system changed. A reader six months from now should weigh today's dates
(2026-09-15, on every file created in this pass) accordingly — freshly written is not the same
claim as battle-tested, even when the content is accurate.

A second, smaller instance of the same thing: milestone 4's acceptance criterion leans partly on
"per prior recorded verification on this machine, the real command sequence has been run" —
that's a claim inherited from an earlier session, not re-checked today. The suite that *was*
re-run today (`verify_tools.py`) tests the tools' decision logic, not a live `claude` CLI
invocation.

## Cross-cutting issues that belong to no milestone

- **[`docs/architecture-backlog.md`](architecture-backlog.md)** — seven open refactor candidates
  against `hook.py`/`verify.py` (deduplicating nine restatement checks, unifying the three
  places the failure-mode contract is stated, one open item about agent frontmatter fields
  `verify.py` currently forbids). None are commitments; none block any milestone above.
- **[`docs/rules-backlog.md`](rules-backlog.md)** — one open item (vague, unrunnable handover
  instructions caught once in `docs/desktop-verification.md`), not yet written into
  `rules/house-rules.md`.
- **Both backlog docs are the exact kind of ad hoc decision log that Tier 6
  (`docs/Decisions.md`) was built to replace**, per
  [`docs/archive/2026-09-15-sixth-documentation-tier.md`](archive/2026-09-15-sixth-documentation-tier.md#context) —
  but their entries haven't been transcribed into `Decisions.md` yet. They still function as
  backlogs (open items awaiting a decision), which is a different thing from `Decisions.md`'s
  append-only *record* of decisions already made — so this isn't necessarily a migration to do,
  but it's worth a deliberate call rather than leaving both patterns live indefinitely.
- **Stray root-level items with no documented purpose**: `Modified.md` (an empty directory,
  despite the `.md` name), `artifact-test.html` (a committed artifact-publishing smoke test, per
  its own commit message — not part of `docs/`), `skills-lock.json`, and five leftover
  directories under `.claude/worktrees/` from past delegated sessions
  (`auto-mode-subagent-delegation-bfb401`, `changelog-planning-7a4c3f`,
  `house-rules-version-check-3b7798`, `opus-sonnet-fix-plan-349283`,
  `plugin-version-bump-guard`). None were investigated further or touched as part of this
  scaffolding pass — flagged here because they're the kind of thing a documentation audit is
  supposed to surface, not because their disposition was decided.
- **`docs/sessions/` has exactly one recorded ledger** (2026-09-09), despite
  `tools/session_ledger.py` existing to produce one per session. The tool works; running it
  isn't yet a habit.
