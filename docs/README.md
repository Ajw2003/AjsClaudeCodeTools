# Documentation index

Nobody should have to search this folder — everything worth finding is linked from here.

This repo ships a personal Claude Code plugin marketplace. Its mature plugin is `house-rules`,
which turns aj's global CLAUDE.md-style rules into hooks so they follow every device and project
without a file to copy around. Two younger sibling plugins, `prompt-workshop` and `agent-router`,
copy the same shim-plus-hook.py-plus-verify.py formula toward a different problem each. `tools/`
holds the scripts that get all three onto a machine and prove they still work once there.

## The moving parts

| Part | What it is |
|---|---|
| [`claude-house-rules/`](../claude-house-rules) | The `house-rules` plugin — hooks, rules, agents, output style |
| [`claude-prompt-workshop/`](../claude-prompt-workshop) | The `prompt-workshop` plugin — v0.1 |
| [`claude-agent-router/`](../claude-agent-router) | The `agent-router` plugin — v0.1 |
| [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | Declares all three plugins to `claude plugin marketplace add` |
| [`tools/`](../tools) | Install, upgrade, verify, and measure scripts — not shipped to installed copies |
| [`CLAUDE.md`](../CLAUDE.md) | Session-loaded guidance for working *in* this repo — commands, editing rules |

## The six tiers

| Tier | File | Answers |
|---|---|---|
| 1 | [README.md](README.md) (this file) | What is this, where is everything |
| 2 | [Roadmap.md](Roadmap.md) | What 0-100% means, what "done" looks like |
| 3 | [ProjectState.md](ProjectState.md) | Where it stands right now |
| 4 | [systems/](systems/README.md) | How each runtime-critical system works |
| 5 | [Today.md](Today.md) | What's being worked on today, and why |
| 6 | [Decisions.md](Decisions.md) | Why a decision was made, and what it replaced |

Plus four non-tier folders: [`plans/`](plans) (live intent until executed), [`archive/`](archive)
(inert docs, moved not deleted), [`generated/`](generated) (tool-produced output, regenerated not
hand-edited), and [`plain/`](plain) (plain-English copies of eligible docs, written by the
`house-rules:plain-docs` skill and checked by `plain_docs_check.py`; mirrors the layout of the
doc each copy is drawn from).

## Systems (tier 4)

| System | Owns |
|---|---|
| [hook-engine](systems/hook-engine.md) | Dispatching every `house-rules` hook event to the handler that enforces it |
| [verify-suites](systems/verify-suites.md) | Proving the three plugins' hook payloads produce the decisions the docs claim |
| [plugin-distribution](systems/plugin-distribution.md) | Getting the plugins onto a machine and upgrading them |
| [offshoot-plugins](systems/offshoot-plugins.md) | `prompt-workshop` and `agent-router` |

## Everything else worth reaching

- [`architecture.md`](architecture.md) — long-form rationale behind `CLAUDE.md`'s design
  constraints: why the shim, why the model split works the way it does, why `guard` reads
  `.git/HEAD` instead of shelling out, why the output style is forced.
- [`architecture-backlog.md`](architecture-backlog.md) / [`rules-backlog.md`](rules-backlog.md) —
  open, undecided refactor candidates and rule changes. Not commitments; see
  [`ProjectState.md`](ProjectState.md#cross-cutting-issues-that-belong-to-no-milestone).
- [`desktop-verification.md`](desktop-verification.md) — which surfaces actually receive the
  step-card handover format, and how each row was checked.
- [`claude-ai-instructions.md`](claude-ai-instructions.md) — the text to paste into claude.ai's
  own Settings → Instructions, the one surface the plugin's hooks cannot reach.
- [`measuring-footprint.md`](measuring-footprint.md) — how to read `tools/measure_footprint.py`'s
  output honestly.
- [`comment-harvest-calibration.md`](comment-harvest-calibration.md) — what the `harvest` hook's
  size thresholds catch in this repo, and why.
- [`example-environment.md`](example-environment.md) — a worked, committed example of a
  machine-local `rules/environment.md`, kept for the traps it already caught.
- [`offshoots-plan.md`](offshoots-plan.md) — the plan `prompt-workshop` and `agent-router` were
  built against, including what's still open.
- [`sessions/`](sessions) — per-session audit ledgers from `tools/session_ledger.py`. Sparse —
  see [`ProjectState.md`](ProjectState.md#cross-cutting-issues-that-belong-to-no-milestone).

## Conventions

The full conventions live in the `house-rules:project-docs` skill (load it for the detail,
scaffolding steps, and per-tier templates) — restated here only to the depth this index needs:

- **Cite claims to `file:line`.** Most assertions in a tier-4 doc should link to the code they
  describe, so an audit is mechanical rather than a matter of opinion.
- **Say what a measurement cannot show.** A doc that states its own limits stops a dead end being
  reopened on a hunch later.
- **Update the tier that changed, not every tier.** `ProjectState.md` moving is routine;
  `Roadmap.md` moving means the definition of done moved, and that's worth announcing.
- **A doc that's gone inert moves to `archive/` with a note in its `README.md`; it never gets
  deleted.**
- **Never invent content to fill a tier.** A row that says the answer isn't known yet is honest;
  a plausible guess is a lie that gets cited as evidence later.
