---
name: project-docs
description: The six-tier documentation structure every repo uses - the tier spec, the per-tier templates, the conventions that keep it honest, and scaffolding for a repo that has none of it yet. Use when creating a repo's documentation, restructuring docs that grew without a shape, auditing docs against the code, or when the house rule "Documentation goes in tiers" needs its detail. Not for an ordinary edit to a document that already exists and already sits in the right tier.
---

# Project documentation: the six tiers

The short version is a house rule and always loaded. This is the detail behind it.

**Read the repo before writing anything.** If `docs/` already exists, the job is almost never
"create a structure" — it is finding which tier each existing document belongs to and whether it
still tells the truth. A repo with fifteen unstructured markdown files does not need fifteen new
ones; it needs those fifteen sorted, merged, and the dead ones moved to `archive/`.

## The tiers

Each tier lives in its own numbered folder, so the folders sort in tier order.

| Tier | File | Answers | Rewritten when |
|---|---|---|---|
| 1 | `docs/1-landing/README.md` | What is this, where is everything | The shape of the project changes |
| 2 | `docs/2-roadmap/Roadmap.md` | What 0–100% means. What "done" looks like | The **definition** of done changes — rare |
| 3 | `docs/3-state/ProjectState.md` | Where it stands *right now* against tier 2 | A milestone's status changes |
| 4 | `docs/4-systems/*.md` | How each runtime-critical system works | That system changes |
| 5 | `docs/5-today/Today.md` | What is being worked on today, and why that | Every working session |
| 6 | `docs/6-decisions/Decisions.md` | Why a decision was made, and what it replaced | Never rewritten — only appended to |

`docs/README.md` itself is not a tier: it is a short, plain-English page for people, pointing at
`docs/1-landing/README.md` for the full index.

Plus four folders that are not tiers:

- **`docs/plans/`** — a plan for a specific piece of work, live until executed. Named for the
  work, not the date: `presentation-and-ui.md`, not `2026-09-08-notes.md`. A plan that has been
  executed and is now only of historical interest moves to `archive/`.
- **`docs/archive/`** — documents that were correct when written and are now inert. **Nothing in
  `archive/` describes current behaviour**, by definition, and it carries a `README.md` saying
  why each item is inert. Things move here; they do not get deleted.
- **`docs/generated/`** — tool-produced deliverables: HTML reports, exported diagrams/images,
  anything from the Artifact tool or a generated-report script. Not hand-edited once written; if
  it needs to change, it gets regenerated.
- **`docs/plain/`** — plain-English copies of eligible docs, mirroring the layout of the doc each
  is drawn from (`docs/plain/4-systems/x.md` is the plain copy of `docs/4-systems/x.md`). Written
  by the `house-rules:plain-docs` skill, checked by `plain_docs_check.py`. The original tier doc
  is never rewritten to produce one.

### Every project gets all six

A project too small for ten milestones still has a roadmap — it just has three milestones. A
project with two runtime-critical systems still has `systems/`, with two files in it. A brand-new
project still gets `docs/6-decisions/Decisions.md` — an empty log with just a header is honest for a project
with no history yet, not a placeholder problem, since there is no rule that history must be
non-empty. **Scale the contents; never drop a tier.** A missing tier is a question nobody can
answer; a small tier is just a small project honestly described.

The judgement call is what counts as a *system*. The test: **if this is wrong, does the product
stop working?** Not "is it a folder" — an event bus that four scenes depend on is a system, a
utilities folder is not. Somewhere between three and eight is normal. More than that usually
means the test is being applied too loosely.

## What each tier contains

### Tier 1 — `docs/1-landing/README.md`

The entry point, and the promise it makes is that **nobody should ever have to search the
folder.** It carries: what the project is in a paragraph; the moving parts as a table with one
line each; the tier table above with links; a table of the tier-4 systems and what each owns;
everything else worth reaching (live reference docs, runbooks, archive); and the conventions
section below.

### Tier 2 — `docs/2-roadmap/Roadmap.md`

Milestones, each with a percentage, a one-line statement of what it is, a **Contains** list and
an **Acceptance** criterion. The acceptance criterion is the whole point: it is what makes
"done" checkable by someone who was not there.

A milestone is done when its acceptance criterion **has actually been checked**, not when the
code exists. "Written but never run" is not done.

When an acceptance criterion changes, say so in the milestone itself — what it used to say, what
it says now, and what decision moved it. A roadmap that quietly rewrites its own targets is
worthless, because it can never be failed.

### Tier 3 — `docs/3-state/ProjectState.md`

Where things actually stand. A headline percentage, a status table with one row per milestone,
and a section per milestone saying what is built and what is not.

Two sections that make this tier earn its keep:

- **"The one thing that is not what it looks like"** — the item whose status most misleads a
  reader. Usually something that reads as nearly finished and is not, or the reverse. If nothing
  qualifies, say so; do not invent one.
- **Cross-cutting issues that belong to no milestone** — the things that fall between the
  milestones and therefore never get owned.

### Tier 4 — `docs/4-systems/*.md`

One document per runtime-critical system, each covering the same four things in this order:

1. **What it owns** — the single responsibility, stated so overlaps between systems are visible
2. **How it works** — the design, at the depth needed to change it safely
3. **Invariants** — what must stay true. Breaking one of these is how the expensive bugs happen
4. **Traps** — specific things that have already cost someone a day

**These do not restate the code.** They give the shape that the code's comments assume you
already have. A system doc that reads like a paraphrase of the source is a doc that will rot,
because nothing forces it to change when the source does.

`docs/4-systems/README.md` indexes them, and says which systems were considered and deliberately
left out, with the reason. That list is as useful as the docs themselves.

### Tier 5 — `docs/5-today/Today.md`

What is being worked on today and why that rather than something else. Rewritten each working
session — **at the start, not the end**, because the point is planning from where you actually
stand rather than from what felt urgent.

It carries: what was done; what was deliberately *not* done; what got surfaced that is not
today's job; and "what to do next, in order" — ranked by what unblocks what, not by size.

A day whose plan is "routine audit, check for drift" is a legitimate plan and should be written
down as one. If today's work maps to no milestone, say so explicitly and say why.

### Tier 6 — `docs/6-decisions/Decisions.md`

The paper trail: one running, dated, append-mostly log of what was decided, when, why, what
alternatives were rejected, and what it superseded. It is the one tier that is **not** rewritten
to stay current — it only grows. An entry is never rewritten or deleted; the one allowed edit to
an existing entry is flipping its `Status` line to `Superseded`, with a pointer, when a later
entry replaces it — the *new* reasoning goes in the new entry, not by editing the old one.
Newest entry at the top.

Entry shape:

```
## <date> — <short decision title>

**Context.** What prompted this — the observation, the problem, the plan or session it came out of.

**Decision.** What was actually decided or chosen.

**Why.** The reasoning, the alternatives considered, and why they were rejected.

**Status.** Standing. / Superseded by [<date> — <title>](#anchor) on <date>.
```

**Boundaries with what already exists**, so this tier doesn't get reinvented:

- `docs/plans/` stays forward-looking intent, live until executed, then archived — unchanged. A
  Decisions.md entry may point back at the plan that produced it.
- `docs/archive/` stays "no longer true" — unchanged. A superseded decision is **not** moved
  there; it stays in Decisions.md with its Status flipped, because the fact that it was once
  decided (and why it changed) remains true history, unlike an inert doc.
- Tier 4 system docs keep *How it works* / *Invariants* / *Traps* — current, operational,
  rewritten in place. They stop being where rationale and post-mortems live; those go here
  instead.

## The conventions that keep it honest

These are the part that actually works. The folder layout is the easy half.

- **Cite claims to `file:line`.** Most assertions should link to the code they describe. This is
  what makes an audit mechanical instead of a matter of opinion.
- **Say what a measurement cannot show.** A findings document that states its own limits is what
  stops a dead end being reopened on a hunch six months later.
- **When a decision reverses, fix the body and leave a pointer.** Do not stack a "superseded —
  see X" box on top of a table that still says the old thing. Rewrite the body, and record what
  it used to say and why it changed. Both halves: a silent overwrite loses the reasoning, and a
  stacked note leaves two answers in one document.
- **A doc that has gone inert moves to `archive/`. It does not get deleted.** Deleting documents
  that other documents point at is how a link graph breaks in twenty places at once. Move, then
  fix the pointers — `/house-rules:docref fix --write` does it for code pointers in the
  `doc-ref` form.
- **Update the tier that changed, not every tier.** Tier 3 moving is routine. Tier 2 moving means
  the definition of done moved, and that is worth announcing rather than slipping in.

## Scaffolding a repo that has none of this

Only when `docs/` is absent or genuinely unstructured. Order matters — tiers 1 to 4 first, tier 5
**last**, because today's plan should follow from knowing where you stand rather than the
reverse.

1. **Read the code first.** The milestone list, the system list and the state section all come
   from the repo, not from a template. A scaffold filled with placeholders is worse than no
   scaffold: it looks like documentation and answers nothing.
2. Create `docs/`, its six numbered tier folders (`docs/1-landing/`, `docs/2-roadmap/`,
   `docs/3-state/`, `docs/4-systems/`, `docs/5-today/`, `docs/6-decisions/`), plus
   `docs/plans/`, `docs/archive/`, `docs/generated/`, and `docs/6-decisions/Decisions.md`. If
   the repo already has ad hoc decision records — a backlog doc, a CHANGELOG with rationale —
   transcribe the real decisions in it as dated entries; never invent placeholders, same rule as
   every other tier. Otherwise start it with just a header; an empty log is honest for a project
   with no recorded history yet.
3. Write tier 4 first — one document per system, derived by reading the code. This is the
   expensive part and everything else references it.
4. Write tier 2, then tier 3. The roadmap defines done; the state measures against it.
5. Write tier 1 last of the four, so its index describes what actually exists.
6. Write the short, plain-English `docs/README.md` that sits at the top of `docs/` — what the
   project is in a few sentences, one line per folder, and a pointer to
   `docs/1-landing/README.md` for the full index. It is not a tier and is not scaffolded until
   the real tier 1 index exists to point at.
7. Write tier 5, and say in it that today was a documentation day.
8. Move anything inert into `docs/archive/` with a `README.md` saying why each item is there.
   Fix every pointer into the moved documents — do not leave the link graph broken. Code
   pointers in the `doc-ref` form are repaired mechanically by `/house-rules:docref fix --write`.
9. If the repo has a `CLAUDE.md`, point it at `docs/1-landing/README.md` as the entry point
   rather than duplicating any of this into it. Two copies drift.

**Never invent content to fill a tier.** A row that says `TODO` is honest; a row with a plausible
guess in it is a lie that will be cited as evidence later. If the knowledge is not available,
write the placeholder and say in the document that it is one.
