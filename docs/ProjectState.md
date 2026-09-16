# Project state

Where things stand right now. There is no dedicated Roadmap document yet (see
[`docs/README.md`#gaps](README.md#gaps)), so this measures against the informal shape the repo
already treats as its milestones — one per plugin, plus the cross-cutting mechanism they share.

## Headline

`house-rules` is mature and enforced daily. `prompt-workshop` and `agent-router` are both real,
runnable v0.1 shells — not stubs — but neither has been tuned against real usage yet, and both
say so themselves in `.claude-plugin/marketplace.json`'s own `STATUS:` prefix.

| Component | Status | Evidence |
|---|---|---|
| `house-rules` | Mature, enforced | `python claude-house-rules/plugins/house-rules/scripts/verify.py` — all checks passed on a run at this commit, 2026-09-16 (the exact count is not repeated here; it drifts, and `verify.py` computes its own) |
| `prompt-workshop` | v0.1 shell | Real hooks, real `verify.py`, heuristic untuned against live traffic — [`docs/offshoots-plan.md`](offshoots-plan.md) §"Open questions" |
| `agent-router` | v0.1 shell | Same shape as above; classifier untuned, and nothing yet confirms a routing suggestion was acted on or that the delegated subagent ran on its declared model |
| Documentation tiers (this repo, on itself) | Landing and State scaffolded this pass; Roadmap still missing | This document and `docs/README.md` |

## The one thing that is not what it looks like

**A green `verify.py` proves the hooks are correct. It does not prove Claude Code loaded them.**
`claude-house-rules/README.md` records this happening for real: the plugin sat three commits
behind for a whole session, injecting four rules while the repo on disk had eleven, and every
file-level check still passed throughout. A fully green suite reads as strong evidence the plugin
works; it is silent on whether the *installed* copy a given session is actually running matches
the one that was checked. `tools/clean_install_test.py` and a live
restart-and-ask session are what actually close that gap, not the test suite.

## Cross-cutting issues that belong to no single component

- **The rules text is restated in nine places, policed by nine hand-copied checks**, most of
  which only verify the restatement still matches the rules text — not the reverse. This is
  `architecture-backlog.md` entry 1: real, `strong`, and open. It's cross-cutting because it
  affects every future rule change, not one plugin's milestone.
- **The failure-mode contract (fail closed / loud / quiet) is written three times** with nothing
  checking the three copies agree — `architecture-backlog.md` entry 2. Same shape: a correctness
  property of the whole mechanism, owned by no single component.
- **Tier 4 of this repo's own documentation is one combined file, not one per system** —
  `docs/architecture.md` rather than `docs/systems/*.md`. Noted as a deliberate bend in
  `docs/README.md` rather than a silent deviation, but it's real drift from the spec this repo
  enforces on everyone else.
- **Neither offshoot has tuning data from real prompts.** Both verify suites are hand-picked
  cases, not samples of actual traffic — `docs/offshoots-plan.md`'s "Open questions" section
  names this for both plugins independently, but the underlying problem (ship a heuristic, then
  have no pipeline to learn whether it's right) is one problem, not two.
