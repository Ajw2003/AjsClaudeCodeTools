# AjsClaudeCodeTools

A personal Claude Code plugin repo. Its original and mature plugin is **house-rules**, which
turns aj's standing CLAUDE.md-style rules into hooks so they follow every device and project
automatically instead of living in a file that has to be copied around. Two younger, smaller
plugins built on the same formula — **prompt-workshop** and **agent-router** — sit alongside it,
both still v0.1 shells rather than load-bearing tools yet.

This file is the map. Nobody should have to search this folder to find something that's in it.

## The moving parts

| Part | What it is | Entry point |
|---|---|---|
| `house-rules` | The mature plugin: hooks that inject aj's global rules and enforce the ones with a shell signature (destructive commands, unasked git mutations, hidden background work, untested handovers). | [`claude-house-rules/README.md`](../claude-house-rules/README.md) |
| `prompt-workshop` | v0.1 shell. Notices an under-specified prompt and walks the user through goal, constraints, success criteria and gating before Claude runs on an inferred reading. | [`claude-prompt-workshop/README.md`](../claude-prompt-workshop/README.md) |
| `agent-router` | v0.1 shell. Classifies a prompt's complexity and nudges Claude to delegate to a model-pinned subagent; cannot switch the live session's own model — no hook can. | [`claude-agent-router/README.md`](../claude-agent-router/README.md) |
| `tools/` | Cross-cutting scripts: install/bootstrap, the clean-install test, footprint measurement, the session ledger, standards sync. Shared by all three plugins above rather than owned by one. | [`tools/`](../tools/) (no dedicated system doc yet — see Gaps below) |
| `.claude-plugin/marketplace.json` | The marketplace manifest `claude plugin marketplace add` reads. Must stay at the repo root. | [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) |

## The documentation tiers

This repo follows the same six-tier structure its own `house-rules` plugin requires of every
project it's installed in (`rules/house-rules.md`, "Documentation goes in tiers"). Until this
pass, it didn't apply that rule to itself — see [Gaps](#gaps) below.

| Tier | Answers | Where |
|---|---|---|
| 1 — Landing | What is this, where is everything | This file |
| 2 — Roadmap | What "done" means | Not written as a dedicated document yet — see [Gaps](#gaps) |
| 3 — State | Where things stand right now | [`docs/ProjectState.md`](ProjectState.md) |
| 4 — Systems | How each runtime-critical piece works | [`docs/architecture.md`](architecture.md) (see note below) |
| 5 — Today | What's being worked on right now, and why | [`docs/plans/`](plans/) — one file per piece of work, not one rewritten file; see note below |
| 6 — Decisions | Why a decision was made, and what it replaced | [`docs/Decisions.md`](Decisions.md) |

Two notes on where this repo bends the standard shape, both worth knowing before you go looking
for something that isn't where the spec says it should be:

- **Tier 4 is one combined document, not one file per system.** `docs/architecture.md` covers
  the whole hook-dispatch mechanism (`run.sh` + `hook.py` + `verify.py`) as a single system,
  rather than a `docs/systems/` folder with a file per handler. The repo is small enough that
  this hasn't caused confusion yet; splitting it out is exactly the kind of change that belongs
  in `docs/architecture-backlog.md` before it's made, not silently.
- **Tier 5 is a folder of dated, named plans, not one rewritten `Today.md`.** Each file in
  [`docs/plans/`](plans/) is named for the work it covers, not the date it was written, and stays
  in place after the work ships rather than being overwritten by the next task. A plan that's
  been executed and is now only historically interesting moves to `docs/archive/`.

Plus two folders that are not tiers, same as the spec describes:

- [`docs/plans/`](plans/) — a plan for one piece of work, live until it's carried out.
- [`docs/archive/`](archive/) — documents that were correct when written and are now inert.
  Nothing in here describes current behaviour; its own `README.md` says why each item is there.

## Everything else worth reaching

| Document | What it's for |
|---|---|
| [`docs/rules-backlog.md`](rules-backlog.md) | Rule changes that are decided but not yet written into `rules/house-rules.md`. |
| [`docs/architecture-backlog.md`](architecture-backlog.md) | Candidate (not yet approved) deepening work against `hook.py` / `verify.py`. |
| [`docs/offshoots-plan.md`](offshoots-plan.md) | What `prompt-workshop` and `agent-router` are for, decisions already made, and what's still open. |
| [`docs/measuring-footprint.md`](measuring-footprint.md) | How to read `tools/measure_footprint.py`'s output honestly. |
| [`docs/desktop-verification.md`](desktop-verification.md) | Which surfaces (CLI, IDE, desktop tabs, web, mobile) actually receive the step-card handover format. |
| [`docs/claude-ai-instructions.md`](claude-ai-instructions.md) | The claude.ai-chat-specific instructions, separate from the plugin. |
| [`docs/comment-harvest-calibration.md`](comment-harvest-calibration.md) | How the `harvest` hook's thresholds were tuned. |
| [`docs/example-environment.md`](example-environment.md) | A worked example of a machine profile, kept for the traps it already caught. |
| [`docs/sessions/`](sessions/) | Session ledgers — a generated, auditable record of what a session actually did, per `tools/session_ledger.py`. |
| [`docs/generated/`](generated/) | Tool-produced artifacts (HTML, exported images, diagrams) — as opposed to hand-authored documents, which go in `docs/` directly. |

## Conventions that keep this honest

- **Update the tier that changed, not every tier.** State moving is routine; the roadmap moving
  means the *definition* of done moved, which is rare and worth saying out loud.
- **Cite claims to `file:line`** wherever the claim is about code, not prose.
- **When a decision reverses,** add a dated entry to `Decisions.md`, then fix the tier document's
  body to state the new truth with a one-line pointer into that entry — never a "superseded" note
  stacked on top of text that still says the old thing.
- **A document that's gone inert moves to `docs/archive/`.** It does not get deleted, and every
  pointer into it gets fixed rather than left broken.

## Gaps

Named rather than quietly worked around, per the rule above:

- **No Roadmap tier document.** `docs/rules-backlog.md`, `docs/architecture-backlog.md` and
  `docs/offshoots-plan.md` between them cover what's queued and why, but nothing states a single
  definition of "done" with acceptance criteria per milestone the way the tier spec asks for.
- **Landing and State were both missing until this pass**, in a repo whose own rules require
  every project — including itself — to carry all six tiers. Nothing in `Decisions.md` records a
  deliberate exception; it was a plain gap, not a reasoned one.
