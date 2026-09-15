# Decisions

The paper trail: what was decided, when, why, what alternatives were rejected, and what it
superseded. Append-mostly — newest entry at the top. An entry is never rewritten or deleted; the
one allowed edit to an existing entry is flipping its `Status` line to `Superseded`, with a
pointer, when a later entry replaces it.

---

## 2026-09-15 — A third non-tier folder, `docs/generated/`, for generated artifacts

**Context.** The tiered-docs system had two non-tier folders: `docs/plans/` (forward intent) and
`docs/archive/` (inert docs) — both hand-written. The `artifact` hook already caught a document
written outside the project and reminded Claude to copy it in, but it sent every extension to the
same place: "docs/ for documents, docs/plans/ for plans." Nothing distinguished a hand-written
markdown doc from an HTML report or other tool output, so both landed in `docs/`. This repo had
two loose examples proving the gap: `docs/architecture-review-2026-09-07.html` and
`docs/2026-09-09-branch-aware-guard-rollout.html`, sitting directly in `docs/` with no other
document like them. Full design and exact wording constraints are in the plan this decision
executed: [`docs/plans/2026-09-15-generated-artifacts-directory.md`](plans/2026-09-15-generated-artifacts-directory.md).

**Decision.** Add `docs/generated/` — a third non-tier folder for tool-produced deliverables:
HTML reports, exported diagrams/images, anything from the Artifact tool or a generated-report
script. Made the `artifact` hook's routing extension-aware: hand-authored `md`/`txt` still go to
`docs/` (or `docs/plans/` for a plan), while tool-produced `html`/`csv`/`json`/`svg`/`pdf` now go
to `docs/generated/` instead. Updated `rules/house-rules.md`, the `project-docs` skill, and
`CLAUDE.md`'s hook table to match, and moved this repo's two loose HTML files into the new
folder with a `README.md` explaining it.

**Why.** `docs/plans/` and `docs/archive/` are both hand-written; a generated HTML report is
neither forward-looking intent nor a formerly-true document — it's tool output that gets
regenerated, not edited, when it needs to change. Mixing it into `docs/` made `docs/` unreliable
as "documentation" versus "whatever a tool happened to produce." Giving generated artifacts their
own folder keeps `docs/` readable as hand-authored documentation while still backing up generated
output as a tracked, committable file instead of leaving it in a scratchpad or temp directory.

**Status.** Standing.

---

## 2026-09-15 — Add a sixth documentation tier, `docs/Decisions.md`

**Context.** `house-rules:project-docs` defined five tiers (`README.md`, `Roadmap.md`,
`ProjectState.md`, `systems/*.md`, `Today.md`) plus two non-tier folders (`plans/`, `archive/`).
None of the five was *why*: tier 3 says where things stand, tier 4 says how a system works
*today*, but nothing durable recorded why a choice was made, what was tried and rejected, or what
an earlier decision used to say before it was reversed. That gap was already visible as ad hoc
workarounds in this repo — [`docs/rules-backlog.md`](rules-backlog.md) and
[`docs/architecture-backlog.md`](architecture-backlog.md) are hand-rolled decision logs (Status /
Defect / Evidence / "what the rule should say" per entry) that exist only because nothing in the
shipped tier system covered this. The `harvest` hook and `archivist` subagent also misfiled this
material — design rationale or a bug post-mortem got routed into a tier-4 system doc's *How it
works*/*Traps*, which is supposed to describe current truth, not carry historical narrative. Full
design and the exact wording constraints are in the plan this decision executed:
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](archive/2026-09-15-sixth-documentation-tier.md).

**Decision.** Add Tier 6 — `docs/Decisions.md` — to the house-rules tiered-docs system: one
running, dated, append-mostly log (Context/Decision/Why/Status per entry), as designed in the
plan above. Updated `rules/house-rules.md`, the `project-docs` skill, the `archivist` subagent's
routing, and `hook.py`'s `HARVEST_NOTE` so rationale, rejected approaches, and post-mortems route
here instead of into tier-4 system docs; ongoing mechanisms, invariants, and operational traps
still go to tier-4, unchanged. Bumped the plugin version 2.20.0 → 2.21.0.

**Why.** `docs/plans/` is forward-looking intent that goes inert once executed and moves to
`docs/archive/`; `docs/archive/` holds documents that are no longer true. Neither is the right
home for a decision's reasoning, which stays true history even after the decision it describes is
superseded — it isn't inert, and it isn't forward-looking. A single append-mostly file (matching
the shape of tiers 2/3/5, not tier 4's per-system folder, since entries are short and
chronological rather than one-per-topic) gives `harvest`/`archivist` a real destination instead of
stuffing rationale into a system doc, and lets tiers 1–5 stop carrying their own change history
inline — they rewrite cleanly to state current truth and leave a one-line pointer into this log.
The alternative of folding decisions into tier-4 `Traps`/`How it works` was rejected because it
conflates "what is true now" with "what we chose and why," which is exactly the misfiling this
tier fixes.

**Status.** Standing.
