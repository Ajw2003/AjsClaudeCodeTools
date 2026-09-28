# Re-creating existing behaviour starts from an inventory of the original

Any change after which the only features left are the ones somebody re-created — a replacement,
port, rebuild, rewrite, restructure or migration — starts from an inventory of what the original
does. Ordinary small edits are out of scope; their diff already shows what changed.

1. **Inventory from the code, not from memory.** Every user-visible feature and behaviour, with
   the original's `file:line`. For a restructure, every trigger, input, output and side effect.
   For a migration, every column and every reader of it.
2. **Mark each one keep, change or drop**, with the reason for every drop, and show the table to
   the user before building. A delegation for this work carries the table, or tells the subagent
   to read the original first — a spec written from memory is how a regression gets *specified*
   rather than improvised.
3. **Verify against the original, with the same inputs** — not only the new version against
   itself. At least one like-for-like old-vs-new comparison goes in the report. For a UI, diffing
   the element IDs of the two pages is one line and catches lost controls; for a workflow, diff
   the triggers, outputs and side effects.
4. **Name every drop in the final report, prominently** — not only the ones forced by the new
   platform. A dropped feature the user was not shown is a regression, even if the new version
   works.
5. **A feature to be re-added later gets its own GitHub issue**, and a roadmap entry, so the user
   can track it and the next session can find it.

The hooks: `scope` adds an inventory reminder to a prompt that reads like this kind of change,
`delegate` adds one to an approved plan that reads like it and carries no keep/change/drop
table, and `handover` (Stop) reminds a turn that did this kind of work and wrote files, but whose
reply names nothing kept or dropped.

**Why:** a stock page moved from a desktop app to a static GitHub Pages site dropped 10 features a
static site could have kept, changed 2 for the worse and added 2 bugs; searching "pre-roll" went
from 232 results to 7. The spec was written from memory and handed to a subagent, only the
server-only losses were disclosed, and every check compared the new page with itself. The same
day, a workflow split into per-province workflows plus an orchestrator dropped three smaller
behaviours, all in logic that was re-written rather than carried over — and git showed it as a
delete plus an add, so nothing flagged it.
