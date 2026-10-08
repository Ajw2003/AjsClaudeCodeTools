# Add a `whats-next` skill: suggest what to work on today

## Context

The house-rules plugin's six-tier docs structure (`house-rules:project-docs`) ends with tier 5,
`docs/5-today/Today.md` — "what to do next, in order" — but the tier spec only says the file gets
rewritten every session; it doesn't help a user who is staring at a blank or stale `Today.md` and
genuinely doesn't know what to fill in. The user wants a mechanism that reads across the tiers a
repo actually has and suggests what to work on.

Two mechanisms exist in this plugin for "automatic behavior": hooks (fire every session,
unconditionally, priced by `tools/measure_footprint.py`) and skills (invoked on demand, by the
model matching a description). The user chose **on-demand skill**, matching how the plugin's only
other skill (`project-docs`) already works, and avoiding token cost on the many sessions where
nobody is stuck. This also sidesteps a real problem a hook would have to solve: most repos —
including this one — only adopt some of the six tiers (this repo has only `docs/6-decisions/Decisions.md`,
`docs/plans/`, `docs/archive/`, `docs/generated/`; no `README.md`/`Roadmap.md`/`ProjectState.md`/
`systems/`/`Today.md`), so any automatic per-session firing would need to stay silent on most
repos most of the time — exactly the shape a hook in this plugin is designed to avoid.

## Approach

### 1. New file: `claude-house-rules/plugins/house-rules/skills/whats-next/SKILL.md`

Matches the one-file, two-field-frontmatter convention of the plugin's only existing skill
([project-docs/SKILL.md](../../claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md)) —
no `scripts/`/`references/` subfolder; this is pure reasoning over whatever `docs/` a repo has,
not a script.

**Frontmatter:**

```yaml
---
name: whats-next
description: Reads whatever docs tiers, plans, and git history a repo actually has and synthesizes a ranked suggestion for what to work on this session — surfacing docs/5-today/Today.md as-is when it's current, or reconstructing the same "what to do next, in order" ranking from ProjectState/Roadmap/plans/Decisions when Today.md is missing, stale, or every item in it is blocked. Falls back to git log/status, README, and TODO/FIXME grep when a repo has none of the docs tiers at all, and says so plainly rather than fabricating structure. Use when the user seems stuck, asks what to work on, or opens a session with no stated task. Not for creating, restructuring, or auditing the docs/ tiers themselves — use house-rules:project-docs for that — and not for an ordinary question about what a specific file or function does.
---
```

**Body**, section by section (content to write, not final prose — mirror project-docs' dense
reference style, tables + bullets, no numbered tutorial except where a procedure is genuinely
sequential):

- **When this fires** — restate the four trigger scenarios; one line that this skill reads/ranks
  and never restructures `docs/` (point to `project-docs` once, not per-section).
- **Step 0 — read the repo's actual adoption level.** Check each of the six tier files plus
  `docs/plans/`/`archive/`/`systems/` individually (a repo can have some tiers and not others —
  this repo has 6/`plans`/`archive`/`generated` but not 1/2/3/4/5, so "all or nothing" checks are
  wrong). Classify full / partial / zero — gates which later steps run.
- **Step 1 — `docs/5-today/Today.md` first, if it exists.** Extract its "what to do next, in order" list
  verbatim. Sanity-check each item against current reality (does a referenced `docs/plans/*.md`
  still exist there rather than having moved to `archive/`? does `git log` already show the work
  done? does `ProjectState.md` still agree?) before trusting it, citing file:line. If ≥1 item is
  unblocked and accurate, **restate it — do not re-derive from scratch.** Only fall through to
  Step 2 when every item is blocked, contradicted, or the file is empty/missing — and say which.
- **Step 2 — re-derive candidates** (only on fallthrough), reading whichever of these exist, each
  cited to file:line, in priority order: `docs/plans/*.md` (designed-but-unexecuted work — verify
  each plan is actually still unexecuted by checking `git log` for its filename/title, since a
  plan whose work already shipped but wasn't archived is a real failure mode — see Verification
  step 2 below for a live example already sitting in this repo); `docs/3-state/ProjectState.md`'s "the one
  thing that is not what it looks like" and cross-cutting issues; `docs/2-roadmap/Roadmap.md`'s current
  (not-100%) milestone's unmet Acceptance criterion, cross-referenced against ProjectState; recent
  `docs/6-decisions/Decisions.md` entries (newest few) for implied follow-up work; `docs/4-systems/*.md` Traps
  sections as the lowest-priority signal.
- **Step 3 — rank, don't just list.** State the rule explicitly (unblocking power, not size — same
  principle `Today.md` itself states). Tie-breakers: nothing blocks it right now > a `docs/plans/`
  entry outranks equivalent unplanned work (thinking already paid for) > a cross-cutting issue
  outranks a single-milestone gap > size is explicitly not a factor. Present 3-5 ranked candidates
  max, one line of why + citation each — not a dump of every signal found.
- **Step 4 — zero/thin-adoption fallback.** Trigger: no `docs/` at all, or none of tiers 1-5
  populated. Open by naming the absent tiers plainly — never silently substitute. Fall back, in
  order, to `git log --oneline -20`, `git status` (uncommitted work is the strongest single
  signal), the repo-root README, a bounded TODO/FIXME/XXX grep excluding vendor/build dirs; still
  apply Step 2a's plan-freshness check if `docs/plans/` exists even when other tiers don't (this
  repo's real case). Close with exactly one pointer to `house-rules:project-docs` to scaffold real
  tiers — stated once, not repeated.
- **Step 5 — offer to write `docs/5-today/Today.md`.** Only after the user has picked a direction. One
  line, never auto-write ("ask instead of assuming"). If accepted, draft per tier 5's required
  contents (what's being worked on and why; what's deliberately not; what got surfaced that isn't
  today's job — e.g. a stale-plan finding from Step 2a; what to do next after this). Decline means
  stop; the verbal answer already stands as the session's output.
- **Citing claims** — every status/percentage/acceptance claim: file:line. Every git-derived claim:
  command + commit hash/line. A tier that says nothing on a point: "not stated," never guessed.

### 2. Fix `docs/architecture.md:350-358`

The skills-directory paragraph is already stale independent of this change — it says "Currently
one: `project-docs/`" and "five-tier"/"all five tiers" (tier 6, `Decisions.md`, shipped
2026-09-15). While touching this paragraph: list `whats-next/` alongside `project-docs/` with one
sentence on what it does and that — unlike everything else that paragraph's surroundings describe
— it's on-demand, not hook-driven; fix "five" → "six" in both places.

### 3. `plugin.json` version bump

`2.21.0` → `2.22.0`, matching the precedent of the tier-6 addition bumping the version
([docs/6-decisions/Decisions.md:62](../6-decisions/Decisions.md)).

### 4. New `docs/6-decisions/Decisions.md` entry (newest-first, top of file)

Record: Context (tier 5 says what `Today.md` should contain but nothing helps reconstruct or
sanity-check it when stale/absent/blocked), Decision (added the on-demand `whats-next` skill),
Why (kept as a skill, not a `SessionStart` hook, to avoid token cost on sessions where nobody's
stuck, and because most repos — including this one — only partially adopt the six tiers, which a
hook would have to silently no-op around on every session), Status: Standing.

### Explicitly not changing

- **`house-rules.md`** — no pointer added. It only names a skill by id where a *rule* defers its
  detail to that skill (as "Documentation goes in tiers" does for `project-docs`). No rule requires
  invoking `whats-next`; adding a pointer would misleadingly read as though one does, contradicting
  the on-demand decision.
- **`verify.py`** — no new check. Its two `project-docs`-tied checks exist because `house-rules.md`
  names that skill by id (dangling-pointer risk) and because `hook.py`'s emitted text must agree
  with the rule and skill text on `docs/generated` (cross-file drift risk). Neither applies here:
  nothing names `whats-next` by id, and no hook emits paraphrased text about it (pure reasoning
  skill, no shell signature, so no `guard` pattern either).
- **`CLAUDE.md`**, **`tools/measure_footprint.py`** — no change. CLAUDE.md documents hooks/commands
  and stays short by design; `measure_footprint.py` doesn't price skills at all (confirmed: zero
  mentions of "skill" in the file), so a new skill adds nothing for it to measure.

## Critical files

- `claude-house-rules/plugins/house-rules/skills/whats-next/SKILL.md` — new, the entire deliverable
- [claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md](../../claude-house-rules/plugins/house-rules/skills/project-docs/SKILL.md) — pattern to match (frontmatter shape, tier semantics, negative-trigger convention)
- [docs/architecture.md:350-358](../architecture.md) — skills-directory paragraph, needs the new skill added and "five"→"six" fixed
- [claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json](../../claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json) — version bump
- [docs/6-decisions/Decisions.md](../6-decisions/Decisions.md) — new entry

## Verification

No code runs here — verification is the suite (to prove nothing broke) plus manual dry-runs.

1. **Run the existing suite, unchanged expectations:**
   `python claude-house-rules/plugins/house-rules/scripts/verify.py` — must still pass at the same
   count with zero new failures, since this touches no hook, no rule text, and no shell-signature
   pattern. Confirms the new file didn't trip the `docs/generated` three-way drift check or the
   CLAUDE.md-duplication check (both scan nearby files).
2. **Manual dry-run against this repo's own partial adoption (the real, checkable case):** invoke
   the skill here. `docs/plans/2026-09-15-subagent-checkout-isolation.md` is a live example of
   exactly the failure mode Step 2a is designed to catch — that plan's work already landed in
   commit `20738b4` (which names the plan file in its own commit body) but the plan file was never
   moved to `docs/archive/`. Pass/fail signal: does the skill surface that specific plan as stale
   (already-shipped, mis-filed) rather than presenting it as live unexecuted work? Does it cite
   `docs/6-decisions/Decisions.md:<line>` and the commit hash rather than paraphrasing without citation?
3. **Manual dry-run, zero-adoption repo:** point the skill at a throwaway scratch repo with no
   `docs/` at all (outside this project, per the artifact-custody rule). Expect: plain statement of
   which tiers are absent, fallback to git log/status/README/TODO-grep, exactly one
   `project-docs` pointer at the end — not fabricated tier-shaped content.
4. **Manual dry-run, `Today.md` present and current:** hand-construct a minimal scratch
   `docs/5-today/Today.md` fixture (outside the project) with one unblocked ranked item. Confirm the skill
   restates/confirms it rather than re-deriving from scratch — the cheap-path behavior that's easy
   to skip past accidentally.
5. **Confirm offer-not-write:** in at least one dry-run, confirm the skill ends with a one-line
   offer to draft/update `docs/5-today/Today.md` and stops there without writing anything unprompted.
