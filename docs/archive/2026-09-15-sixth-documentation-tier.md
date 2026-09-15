# A sixth documentation tier: decisions, reasoning, and the paper trail

## Context

`house-rules:project-docs` currently defines five tiers (`README.md`, `Roadmap.md`,
`ProjectState.md`, `systems/*.md`, `Today.md`), plus two non-tier folders (`plans/`, `archive/`).
None of the five is *why*. Tier 3 (state) says where things stand; tier 4 (systems) says how a
system works *today*; nothing durable records why a choice was made, what was tried and rejected,
or what an earlier decision used to say before it was reversed.

That gap is already visible as ad hoc workarounds in this very repo: `docs/rules-backlog.md` and
`docs/architecture-backlog.md` are hand-rolled decision logs (Status / Defect / Evidence / "what
the rule should say" per entry) that exist only because nothing in the shipped tier system covers
this. The `harvest` hook and `archivist` subagent also currently misfile this material — a design
rationale or a bug post-mortem is routed into a tier-4 system doc's *How it works*/*Traps*, which
is supposed to describe current truth, not carry historical narrative. And the existing convention
("when a decision reverses, fix the body and leave a pointer... say what it used to say and why")
asks every tier doc to carry its own change history inline, with nowhere central to point to.

This plan adds **Tier 6 — `docs/Decisions.md`**: one running, dated, append-mostly log that is the
paper trail — what was decided, when, why, what alternatives were rejected, and what it superseded.
It is the one tier that is *not* rewritten to stay current; it only grows. Once it ships, tiers 1–5
stop needing to carry their own history inline — they rewrite cleanly to state current truth and
leave a one-line pointer into the log — and `harvest`/`archivist` get a real destination for
rationale and post-mortems instead of stuffing them into a system doc.

A second phase — making this tier structure apply automatically, and recursively, across every
project — is deliberately **out of scope for this plan**. It gets planned as a follow-up once this
phase ships and `verify.py` is green.

## Tier 6 design

**File:** `docs/Decisions.md`, single file (matches the shape of tiers 2/3/5, not tier 4's
per-system folder — entries are short and chronological, not one-per-topic).

**Discipline:** append-mostly, newest entry at the top. An entry is never rewritten or deleted.
The one allowed edit to an existing entry is flipping its `Status` line to `Superseded` with a
pointer, when a later entry replaces it — the *new* reasoning goes in the new entry, not by
editing the old one.

**Entry shape:**
```
## <date> — <short decision title>

**Context.** What prompted this — the observation, the problem, the plan or session it came out of.

**Decision.** What was actually decided or chosen.

**Why.** The reasoning, the alternatives considered, and why they were rejected.

**Status.** Standing. / Superseded by [<date> — <title>](#anchor) on <date>.
```

**Boundaries with what already exists** (spelled out in the skill so it doesn't get reinvented):
- `docs/plans/` stays forward-looking intent, live until executed, then archived — unchanged.
  A Decisions.md entry may point back at the plan that produced it.
- `docs/archive/` stays "no longer true" — unchanged. A superseded decision is *not* moved there;
  it stays in Decisions.md with its Status flipped, because the fact that it was once decided
  (and why it changed) remains true history, unlike an inert doc.
- Tier 4 system docs keep *How it works* / *Invariants* / *Traps* — current, operational,
  rewritten in place. They stop being where rationale and post-mortems live.

## Files to change

1. **`claude-house-rules/plugins/house-rules/rules/house-rules.md`**
   - "## Documentation goes in tiers" section: five → six tiers; add **decisions** (why a
     decision was made, and what it replaced) to the tier list; "all five" → "all six".
   - Refine the "when a decision reverses" bullet: the old text's reasoning now goes into a
     `docs/Decisions.md` entry, and the tier doc leaves a one-line pointer instead of inlining it.
   - "## Long-form reasoning goes in a document, not in a comment": split the routing so an
     ongoing mechanism/invariant/operational gotcha still goes to the tier-4 doc (`How it works`
     / `Invariants` / `Traps`, all phrases preserved verbatim — `verify.py` drift-checks them),
     while rationale, a rejected approach, or a post-mortem — "a record of a choice, not current
     truth about the system" — becomes a dated `docs/Decisions.md` entry instead.

2. **`claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md`**
   - Add the Tier 6 row to the table and a "### Tier 6 — `docs/Decisions.md`" section (entry
     shape, append-only discipline, the boundaries paragraph above).
   - "Every project gets all five" → "all six" (with the same "scale the contents, never drop a
     tier" framing — an empty log with just a header is honest for a brand-new project, not a
     placeholder problem, since there's no rule that history must be non-empty yet).
   - Scaffolding steps: create `docs/Decisions.md` alongside the other tiers in step 2; if the
     repo already has ad hoc decision records (a backlog doc, a CHANGELOG with rationale), their
     real decisions get transcribed as dated entries — never invented placeholders, same rule as
     the other tiers.

3. **`claude-house-rules/plugins/house-rules/agents/archivist.md`**
   - Update the routing bullet: rationale/derivation/rejected-approach and post-mortems →
     append a `docs/Decisions.md` entry (new file with a header if none exists) instead of tier-4
     *How it works*/*Traps*; an ongoing invariant and an operational/platform-quirk trap still go
     to tier-4, unchanged.
   - Update the "Find the tier-4 document" bullet to add the parallel Decisions.md path.
   - Update the un-injected digest list at the bottom to mention the new routing split.

4. **`claude-house-rules/plugins/house-rules/scripts/hook.py`** — `HARVEST_NOTE`
   - Rewrite the routing sentence only, keeping the untouched tail (the `{where}` single-block
     clause, the archivist hand-off, "the user was not prompted") verbatim. New routing sentence
     preserves the phrases `How it works`, `Traps`, `Invariants`, `docs/systems` (still checked by
     `verify.py`) and adds `docs/Decisions.md`: an ongoing mechanism/invariant/gotcha still goes to
     the tier-4 doc; rationale, a rejected approach, or a post-mortem is "a record of a choice, not
     current truth about the system" and becomes a dated `docs/Decisions.md` entry instead.

5. **`claude-house-rules/plugins/house-rules/scripts/verify.py`**
   - Harvest drift checks (~line 1397 and ~line 1415): add `"docs/Decisions.md"` to both phrase
     lists (the rules-text check and the emitted-reminder check) so the new routing text can't
     silently regress.
   - Tiered-docs drift check (~line 2404–2424): add `"docs/Decisions.md"` to the SKILL.md phrase
     list; add a check that `rules/house-rules.md` itself mentions `docs/Decisions.md` (same
     pattern as the existing `house-rules:project-docs` name check); update the PASS print message
     from "all five tiers" to "all six tiers".

6. **`.claude-plugin/plugin.json`** — bump `version` 2.20.0 → 2.21.0 (additive feature, no
   removal/break — matches the existing pattern of version bumps per shipped feature).

## Dogfooding in this repo

This repo's own `docs/` doesn't carry the other five tiers today (no `README.md`/`Roadmap.md`/
etc.) — retrofitting that is out of scope and not asked for. But validating the new tier costs
little and proves the shape works:

- After implementing, create `docs/Decisions.md` in this repo with its first real entry recording
  *this* decision (context: the gap above; decision: add tier 6 as designed; why: the routing
  split and the existing backlog docs as evidence).
- Move this plan doc to `docs/archive/` once executed, per the existing plans-lifecycle rule, with
  an `archive/README.md` note — and have the Decisions.md entry point at the archived plan.

## Verification

Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` from the repo root and
confirm exit 0 with no FAIL lines — this is what actually proves the drift checks (house-rules.md
↔ SKILL.md ↔ hook.py ↔ the emitted reminder) all agree, not a read-through.

## Commit / push

Per this session's branch instructions: commit on `claude/house-rules-sixth-tier-9e0oxi` and push.
Two commits — the plugin change (files 1–6 above), then the dogfooding docs in this repo — no PR
unless asked.

## Deferred: applying this everywhere, recursively

Once this ships and verifies, come back with a design for propagating the six-tier structure to
every project automatically. Current thinking, to be designed properly as its own plan: a third
`SessionStart` hook (alongside `inject`/`standards`, same non-blocking, detect-and-nudge pattern —
never auto-write a repo's `docs/` uninvited) that checks the current project root, and one level of
subdirectories the same way `standards` already does for ecosystem markers, for which tiers exist
and which are missing, and points at `house-rules:project-docs` to scaffold the gap. "Recursively"
would mean that same nested-project detection, not blindly stamping a full doc tree into every
subfolder of a monorepo.
