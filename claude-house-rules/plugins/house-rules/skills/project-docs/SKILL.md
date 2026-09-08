---
name: project-docs
description: The five-tier documentation structure every repo uses - the tier spec, the per-tier templates, the conventions that keep it honest, and scaffolding for a repo that has none of it yet. Use when creating a repo's documentation, restructuring docs that grew without a shape, auditing docs against the code, or when the house rule "Documentation goes in tiers" needs its detail. Not for an ordinary edit to a document that already exists and already sits in the right tier.
---

# Project documentation: the five tiers

The short version is a house rule and always loaded. This is the detail behind it.

**Read the repo before writing anything.** If `docs/` already exists, the job is almost never
"create a structure" — it is finding which tier each existing document belongs to and whether it
still tells the truth. A repo with fifteen unstructured markdown files does not need fifteen new
ones; it needs those fifteen sorted, merged, and the dead ones moved to `archive/`.

## The tiers

| Tier | File | Answers | Rewritten when |
|---|---|---|---|
| 1 | `docs/README.md` | What is this, where is everything | The shape of the project changes |
| 2 | `docs/Roadmap.md` | What 0–100% means. What "done" looks like | The **definition** of done changes — rare |
| 3 | `docs/ProjectState.md` | Where it stands *right now* against tier 2 | A milestone's status changes |
| 4 | `docs/systems/*.md` | How each runtime-critical system works | That system changes |
| 5 | `docs/Today.md` | What is being worked on today, and why that | Every working session |

Plus two folders that are not tiers:

- **`docs/plans/`** — a plan for a specific piece of work, live until executed. Named for the
  work, not the date: `presentation-and-ui.md`, not `2026-09-08-notes.md`. A plan that has been
  executed and is now only of historical interest moves to `archive/`.
- **`docs/archive/`** — documents that were correct when written and are now inert. **Nothing in
  `archive/` describes current behaviour**, by definition, and it carries a `README.md` saying
  why each item is inert. Things move here; they do not get deleted.

### Every project gets all five

A project too small for ten milestones still has a roadmap — it just has three milestones. A
project with two runtime-critical systems still has `systems/`, with two files in it. **Scale
the contents; never drop a tier.** A missing tier is a question nobody can answer; a small tier
is just a small project honestly described.

The judgement call is what counts as a *system*. The test: **if this is wrong, does the product
stop working?** Not "is it a folder" — an event bus that four scenes depend on is a system, a
utilities folder is not. Somewhere between three and eight is normal. More than that usually
means the test is being applied too loosely.

## What each tier contains

### Tier 1 — `docs/README.md`

The entry point, and the promise it makes is that **nobody should ever have to search the
folder.** It carries: what the project is in a paragraph; the moving parts as a table with one
line each; the tier table above with links; a table of the tier-4 systems and what each owns;
everything else worth reaching (live reference docs, runbooks, archive); and the conventions
section below.

### Tier 2 — `docs/Roadmap.md`

Milestones, each with a percentage, a one-line statement of what it is, a **Contains** list and
an **Acceptance** criterion. The acceptance criterion is the whole point: it is what makes
"done" checkable by someone who was not there.

A milestone is done when its acceptance criterion **has actually been checked**, not when the
code exists. "Written but never run" is not done.

When an acceptance criterion changes, say so in the milestone itself — what it used to say, what
it says now, and what decision moved it. A roadmap that quietly rewrites its own targets is
worthless, because it can never be failed.

### Tier 3 — `docs/ProjectState.md`

Where things actually stand. A headline percentage, a status table with one row per milestone,
and a section per milestone saying what is built and what is not.

Two sections that make this tier earn its keep:

- **"The one thing that is not what it looks like"** — the item whose status most misleads a
  reader. Usually something that reads as nearly finished and is not, or the reverse. If nothing
  qualifies, say so; do not invent one.
- **Cross-cutting issues that belong to no milestone** — the things that fall between the
  milestones and therefore never get owned.

### Tier 4 — `docs/systems/*.md`

One document per runtime-critical system, each covering the same four things in this order:

1. **What it owns** — the single responsibility, stated so overlaps between systems are visible
2. **How it works** — the design, at the depth needed to change it safely
3. **Invariants** — what must stay true. Breaking one of these is how the expensive bugs happen
4. **Traps** — specific things that have already cost someone a day

**These do not restate the code.** They give the shape that the code's comments assume you
already have. A system doc that reads like a paraphrase of the source is a doc that will rot,
because nothing forces it to change when the source does.

`docs/systems/README.md` indexes them, and says which systems were considered and deliberately
left out, with the reason. That list is as useful as the docs themselves.

### Tier 5 — `docs/Today.md`

What is being worked on today and why that rather than something else. Rewritten each working
session — **at the start, not the end**, because the point is planning from where you actually
stand rather than from what felt urgent.

It carries: what was done; what was deliberately *not* done; what got surfaced that is not
today's job; and "what to do next, in order" — ranked by what unblocks what, not by size.

A day whose plan is "routine audit, check for drift" is a legitimate plan and should be written
down as one. If today's work maps to no milestone, say so explicitly and say why.

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
  fix the pointers.
- **Update the tier that changed, not every tier.** Tier 3 moving is routine. Tier 2 moving means
  the definition of done moved, and that is worth announcing rather than slipping in.

## Scaffolding a repo that has none of this

Only when `docs/` is absent or genuinely unstructured. Order matters — tiers 1 to 4 first, tier 5
**last**, because today's plan should follow from knowing where you stand rather than the
reverse.

1. **Read the code first.** The milestone list, the system list and the state section all come
   from the repo, not from a template. A scaffold filled with placeholders is worse than no
   scaffold: it looks like documentation and answers nothing.
2. Create `docs/`, `docs/systems/`, `docs/plans/`, `docs/archive/`.
3. Write tier 4 first — one document per system, derived by reading the code. This is the
   expensive part and everything else references it.
4. Write tier 2, then tier 3. The roadmap defines done; the state measures against it.
5. Write tier 1 last of the four, so its index describes what actually exists.
6. Write tier 5, and say in it that today was a documentation day.
7. Move anything inert into `docs/archive/` with a `README.md` saying why each item is there.
   Fix every pointer into the moved documents — do not leave the link graph broken.
8. If the repo has a `CLAUDE.md`, point it at `docs/README.md` as the entry point rather than
   duplicating any of this into it. Two copies drift.

**Never invent content to fill a tier.** A row that says `TODO` is honest; a row with a plausible
guess in it is a lie that will be cited as evidence later. If the knowledge is not available,
write the placeholder and say in the document that it is one.
