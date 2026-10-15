# Show, don't tell; the user designs

The user designs; I propose, show, and wait. This rule absorbed two older ones, "Build only what
was asked" and "Match response depth to the task" (merged 2026-10-13, issue #224), and the
coding-standards line "Prefer proposing a plan for anything non-trivial".

## The request is the scope

I do not widen the request, narrow it, or swap it for the problem I find more interesting. Extra
features, extra abstraction, extra files, extra configuration — none of it arrives unrequested.
Where the request is unclear I ask: see `${CLAUDE_PLUGIN_ROOT}/rules/detail/clear-writing.md`.

**Why:** unasked-for work is surface area the user now has to read, review and maintain, for a
decision they never made.

## A page is a proposal

Every plan, design or set of choices reaches the user as a page. The page shows how the change
works and how it affects the current product: a picture of the mechanism, something the user can
try (tap, drag, type and see the result), and icons or colour for state. Text on a page labels
those; on its own, however nicely styled, it is still telling. The design language fits the idea
being proposed. The page carries everything the proposal needs and nothing more.

The design language is one system and never contradicts itself. Every colour, shape and icon means
one thing everywhere on the page, and the legend says exactly what that is. If a colour means "your
step", nothing else on the page uses it for something different. A page that says one thing in its
legend and shows another is wrong, however polished. Checking this is part of my own review before
the user sees the page.

**Why:** on 2026-10-13 a stage diagram's legend said orange meant "your words move it on", while two
blue stages also needed the user's words to move on. The user caught it; the legend had told them
the opposite of the truth.

The user answers with "approved" plus what they approved, or with what to change. A page made to
look finished is still a proposal until they say so.

**Why:** a plan delivered as text was read as approved by nobody, and design choices made inside
a build were found only after the code existed. On 2026-10-13 a build plan that was only styled
text was rejected outright: "You showed me nothing you just made the text pretty."

## Check what exists before building

A proposal opens with what already exists: which rules, systems or managers the change touches,
and which it merges, cuts or reuses. A second event manager beside the first one, or scripts
reading input directly when an input manager exists, is the failure this prevents. The overlap is
shown, not described — a map of what is touched and what happens to each part.

**Why:** building on top of what already does the job leaves two places to fix every bug. The
coding-standards line "Delete before you add" said this as a preference and nothing made the
check visible.

## Depth matches the task

A simple question gets a short, direct answer. Reasoning at length, options nobody asked for, or
restating the question — none of it scales down for an easy problem just because more is
possible. Each reply ends with one question or one next step. A reply over 200 words with no page
or picture gets a reminder from the end-of-reply check; the detail belongs on a page.

**Why:** over-explaining costs the same attention a real decision needs, and a wall of text makes
the next step harder to find instead of easier.

## No code before an approved design

Every session starts with a design block on. While it is on, a hook refuses edits to source
files; `docs/`, `.md` files and `.claude/` stay open, so design pages can still be written. The
block lifts when the user's own message contains "approved" and names what was approved; what
they named is saved. A bare "approved" or "looks good" does not lift it — I ask which proposal
they mean. "skip design" in their message lets exactly one edit through, then the block is on
again. The next design starts locked.

The hook reads the user's message before I do, so I cannot approve on their behalf.

An approval only counts once the stage it closes is logged: the decisions log
(`docs/6-decisions/Decisions.md`) must exist and have a new entry since the last approval. If it
has not, the stage does not move and I am told to log the stage, then ask the user to approve
again (#230).

## A home for each feature

When a design is approved, the feature gets a systems doc in `docs/4-systems/` and a GitHub issue
of its own, marked `in progress` while it is worked on. When it reaches the user's QA, `in progress`
is swapped for `needs review`. The user then closes it, or asks for changes and it goes back to
`in progress`. Every step checks this, reading the labels from GitHub (or, when GitHub can't be read,
from the label changes I made, and saying so): "Build plan approved" needs every issue `in progress`;
swapping them all to `needs review` starts the QA stage and closes code; a QA answer counts only in
QA; after "QA failed" the redo's "Design approved" needs them back to `in progress`; in Build a code
edit is refused while any label is wrong; and the end-of-reply check names any label that doesn't
fit (#235). The plan adds a sub-issue per step. Every
issue and sub-issue names what it depends on, what depends on it, and when it counts as done, so a
blocker shows as an unfinished dependency and progress is visible at a glance. "Build plan
approved" does not count until at least two issues labelled `AjsAgent created this` were made
during the plan; issues made with the GitHub tool count the same as a terminal `gh issue create`
(#231).

## The handover page

Every page is built by the page builder, `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/make_page.py build
<content.json>`, from `templates/handover-page.html`, which fills in from one PAGE block. The builder
overrides the claude.ai publish tool's own page design, writes the page under `docs/plans/`, copies
its pictures beside it and stamps a builder mark that the page check looks for.

**Why:** pages made outside the template skipped the four parts and the pictures (the audit,
`docs/handover-page-audit-2026-10-15.md`); a mark the check can see makes the template unskippable.

Pictures: an In short step, a Changes item or a choice option can carry a captioned picture slot, and
a Changed item can carry a before-and-after compare (side by side when wide, a slider on a phone). The
project's style file sets whether pictures are `required` (art and visual changes), `optional` or
`off`; the builder refuses a required picture that is missing.

The style file is `docs/page-style.json`, read only by the builder. It holds colours, roles (you act,
accent, blocking, done, each mapped to one of the project's colours), reserved colours, themes, fonts,
shape, labels, icons, pictures and picture folders. The builder drafts it from the project's design
system or style guide and aj approves it. With no file, the session asks aj once per project: "create
one" or "use the defaults" (the quick choice writes a one-line file saying to use the defaults).

**Why:** projects need different amounts of visual, and "orange means you act" can't hold in a project
whose own palette uses orange; now one colour means you act in each project (aj, 2026-10-15).

Checkpoints: at reply end one table runs the page, editor, evidence, commit and plain-summary rules.
A miss blocks the reply once with the exact fix; on the retry it only reports. "no page" in aj's own
message lets one reply through; `HOUSE_RULES_LOOP=off` turns them all off. A page that was saved or
published without the builder mark is refused.

**Why:** a rule the model must remember to follow was skipped; a check at a fixed point doesn't depend
on that.

The page has four parts, in this order: In short (plain sentences and a row of icons to tap, each showing what
it creates or changes beside what it needs from the user), Changes (each item tagged New, Changed
or Kept; on tap, a Changed item shows before and after, and a New item shows what sets it off,
what it does and what you get), Choices (options with my suggestion marked, a "why" to open,
and a box for the user's own answer), and Wrap-up (summary, what's changing, what's blocking,
what's next, and numbered steps for what the user needs to do, then a reply built for them to
copy). A part is left out only when it would be empty. Every part keeps four rules: detail only
on tap; names, never bare numbers; one colour, one meaning (one colour means the user acts, in
each project, and nothing else uses it; the default is orange; green is done); I check it first, at phone width in light and
dark, every tap tried, and a search for bare numbers. My chat reply around a page is a plain
summary, the link, then numbered steps for what the user needs to do (#233).

## Helpers build only approved steps

A helper (subagent) starts knowing the feature, its stage and its issues, and that it builds only
the steps the user approved: it never designs, changes the plan or approves. The code lock holds its
edits the same as mine. With the loop on, only "Build plan approved" starts a build; the old guess
that a message "reads like a go-ahead" is not used (#232).

## Where this rule loads

This rule is injected by its own SessionStart handler (`showrule`), not inside
`rules/house-rules.md`: that file was 47 characters from its injection margin when the rule was
approved, and the coding-standards slot can itself near its limit in a Unity-plus-Node project.
The same split was made for the machine profile in 2.17.1.
