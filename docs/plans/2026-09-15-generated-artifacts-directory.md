# A third non-tier folder: `docs/generated/` for generated and visual artifacts

## Context

The previous change added Tier 6 (`docs/Decisions.md`) and landed clean (`verify.py`: 194/194,
pushed as `da3892b` + `716e649`). The tiered-docs system now has two folders that aren't tiers:
`docs/plans/` (forward intent) and `docs/archive/` (inert docs). The `artifact` hook
(`PostToolUse` on `Write`/`Edit`, `hook.py:event_artifact`) already catches a document written
outside the project (scratchpad, temp dir, `~/.claude/plans`) across `md|txt|html|csv|json|svg|pdf`
and reminds Claude to copy it in — but it sends everything to the same place: "docs/ for
documents, docs/plans/ for plans." An HTML report and a hand-written markdown doc land in the same
folder today.

The user wants a third folder specifically for **generated artifacts** — HTML, exported images,
diagrams, anything a tool produced rather than something authored by hand — so a repo's `docs/`
stays readable as documentation, with generated output backed up separately rather than mixed in.
This repo already has two loose examples proving the gap: `docs/architecture-review-2026-09-07.html`
and `docs/2026-09-09-branch-aware-guard-rollout.html`, sitting directly in `docs/` with no other
document like them.

## Design

**Folder:** `docs/generated/` — tool-produced deliverables: HTML reports, exported diagrams/images,
anything from the Artifact tool or a generated-report script. Not hand-edited once written; if it
needs to change, it gets regenerated. Distinct from `docs/plans/` (forward intent, hand-written)
and `docs/archive/` (formerly-true docs, hand-written) — this is the one non-tier folder for
non-authored content.

**Routing in the `artifact` hook becomes extension-aware**, splitting the existing
`_ARTIFACT_EXT_RE` union into two destination groups:
- `md`, `txt` → `docs/` (hand-authored documents)
- `html`, `csv`, `json`, `svg`, `pdf` → `docs/generated/` (tool output)

`ARTIFACT_NOTE` becomes a template filled with the right destination phrase per extension, the
same way `HARVEST_NOTE` already fills `{n}`/`{s}`/`{where}`. The exact phrase `"artifact custody"`
must stay verbatim — `verify.py`'s `art_case` helper (scripts/verify.py:552-571) asserts on it to
classify a run as "remind".

## Files to change

1. **`claude-house-rules/plugins/house-rules/rules/house-rules.md`** — "## Every artifact lives in
   the project directory" (heading unchanged — `verify.py:433` checks that literal string, don't
   touch it). Body: "docs/ for documents, docs/plans/ for plans" → add ", docs/generated/ for
   generated or visual artifacts (HTML, exported images, diagrams)".

2. **`claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md`** — "Plus two folders
   that are not tiers:" → "three folders"; add a `docs/generated/` bullet (tool-produced, not
   hand-edited, regenerated rather than fixed in place). Update the scaffolding step that creates
   `docs/`, `docs/systems/`, `docs/plans/`, `docs/archive/` to also create `docs/generated/`.

3. **`claude-house-rules/plugins/house-rules/scripts/hook.py`** — `event_artifact()` /
   `ARTIFACT_NOTE` (~lines 862-935): add `_DOC_EXT_RE` (`md|txt`) and `_GENERATED_EXT_RE`
   (`html|csv|json|svg|pdf`); keep `_ARTIFACT_EXT_RE` as the union for the initial "is this a
   document extension" gate; branch to fill the destination clause in `ARTIFACT_NOTE` based on
   which group the matched extension falls in. Keep `"artifact custody"` and the rest of the
   existing wording verbatim.

4. **`claude-house-rules/plugins/house-rules/scripts/verify.py`**
   - Extend the `art_case` test block (~line 574-624): the existing `.html`/`.csv`/`.json`/`.svg`/
     `.pdf` "remind" cases should additionally assert the emitted text names `docs/generated`; the
     `.md` "remind" cases (the `~/.claude/plans` and scratchpad-notes cases) should assert it names
     `docs/` and not `docs/generated`. Extend `art_case` (or add a small variant) with an optional
     substring check on `out` rather than just the remind/trace/silent/malformed bucket.
   - Add a drift check (same pattern as the existing scope/runnable/delegate/harvest drift
     sections) tying `"docs/generated"` across `rules/house-rules.md`, `SKILL.md`, and the emitted
     `ARTIFACT_NOTE` for an `.html` case — this hook had no such check before; adding one holds it
     to the same rigor as the rest of the plugin.

5. **`CLAUDE.md`** (root) — the hook table row for `artifact` (~line 172): update the prose to
   say documents go to `docs/`, generated/visual artifacts go to `docs/generated/`.

## Dogfooding in this repo

- `git mv docs/architecture-review-2026-09-07.html docs/generated/` and same for
  `docs/2026-09-09-branch-aware-guard-rollout.html` (confirmed: nothing in the repo links to
  either file by path, so no pointers need fixing).
- Add `docs/generated/README.md` — one line saying what the folder holds and that its contents are
  regenerated, not hand-edited (mirrors `docs/systems/README.md` indexing the folder it sits in).
- Add a `docs/Decisions.md` entry recording this decision, same shape as the tier-6 entry, citing
  the two loose HTML files as the evidence.

## Verification

`python claude-house-rules/plugins/house-rules/scripts/verify.py` from the repo root — exit 0, no
FAIL lines, including the new art_case destination assertions and the new drift check.

## Commit / push

Branch `claude/house-rules-sixth-tier-9e0oxi` (current branch, already pushed once this session).
One commit covering files 1-5, a second for the dogfooding move + README + Decisions.md entry —
same two-commit split as the tier-6 change. `git push -u origin claude/house-rules-sixth-tier-9e0oxi`.
No PR unless asked.
