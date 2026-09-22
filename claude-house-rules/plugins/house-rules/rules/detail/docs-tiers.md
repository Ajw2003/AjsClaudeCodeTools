# Documentation goes in tiers, and I update the tier that changed


Every repo's `docs/` is the same six tiers: **landing** (what this is, where everything is),
**roadmap** (what done means), **state** (where it stands right now), **systems** (how each
runtime-critical piece works, one document each), **today** (what is being worked on and why),
**decisions** (why a decision was made, and what it replaced). Every project gets all six — a
project too small for milestones still has milestones, it just has fewer of them. Scale the
contents, never drop a tier.

Three habits, and they matter more than the layout:

- **Write to the tier that changed.** State moved, not the definition of done — so update state
  and leave the roadmap alone. Changing the roadmap means the *definition* moved, which is rare
  and worth saying out loud.
- **When a decision reverses, fix the body and leave a pointer.** Add a dated entry to
  `docs/Decisions.md` recording what changed and why, then fix the tier document's body to state
  the new truth and leave a one-line pointer into that entry — never stack a "superseded" note on
  top of text that still says the old thing, and never silently overwrite.
- **Cite claims to `file:line`.** It is what makes an audit mechanical instead of a matter of
  opinion.

`house-rules:project-docs` carries the full tier spec, the per-tier templates, and the
scaffolding for a repo that has none of this yet. I load it before creating or restructuring a
repo's documentation — not for an ordinary edit to a doc that already exists.

**Why:** docs rot at the tier boundary. Mixing "what we're doing today" into "what done means"
is what produces a roadmap nobody trusts, and a reversal written as a stacked note on top of
stale text is how four documents end up describing something that no longer exists.

