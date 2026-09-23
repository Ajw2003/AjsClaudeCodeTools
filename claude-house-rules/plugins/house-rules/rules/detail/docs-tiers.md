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

**Enforcement.** A `SessionStart` handler, `docstiers`, checks the project root every session
for `docs/README.md`, `docs/Roadmap.md`, `docs/ProjectState.md`, at least one file under
`docs/systems/`, `docs/Today.md` and `docs/Decisions.md`. All six present: it emits nothing at
all — this is the one other deliberate silent exception besides `handover`, because it runs every
session and a trace here would cost something on every single one for a fact that is true almost
always. Any missing: it names exactly which tiers are missing and instructs loading
`house-rules:project-docs` and scaffolding them before any other work, in every repo — including
one that is not a git repository at all. When the repo *is* a git repository, it also checks
whether the remote's owner (read from `.git/config`, both the `https://` and `git@host:` URL
forms, and a worktree's `.git` file redirect) matches `HOUSE_RULES_GITHUB_OWNER` (default
`Ajw2003`, case-insensitive). Not owned — or the remote can't be read at all, which is treated the
same as not owned, since scaffolding into a repo whose ownership is unknown is the riskier
default — and the instruction adds one more step: add every scaffolded path to
`.git/info/exclude`, so the new docs never leave the machine and never enter that repo's history.

A second, commit-time check closes the gap between sessions: `guard` (`PreToolUse`) recognizes a
`git commit` command and, only then, checks the staged files (`git diff --cached --name-only`,
under a hard timeout - the one place in `guard` that shells out). A staged source file with
nothing staged under `docs/` gets a reminder naming the tier to update - on my own branch the
commit still runs, with the reminder attached as `additionalContext`; anywhere else it is folded
into the prompt `guard` already shows. It can never block on its own and never changes `guard`'s
underlying decision - a missing `git`, a timeout, or a command naming another repo all say "could
not tell" rather than guessing.

