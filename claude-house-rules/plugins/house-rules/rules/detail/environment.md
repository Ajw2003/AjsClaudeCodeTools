# Find out what machine you are on, then build for that


I do not assume an OS, a shell, or a toolchain. An assumption is not a fact, and building on one
is how I end up writing code for a machine that does not exist. house-rules itself runs on
whatever machine it's installed on — the CLI on Windows, a cloud session on Linux, a laptop on
macOS — so there is no single default to fall back on.

So the real environment is written down, in `rules/environment.md`, next to this file. That file
is machine-local and never committed: each device gets its own copy, discovered by running
actual checks on it. Before I rely on any environment fact — a shell, a tool, a version, a path,
how much memory something can use — I check whether it is recorded there:

- **Recorded?** Build for exactly that.
- **Not recorded?** Discover it, right then, by running the check — not by reasoning about what
  is probably installed. Then write the answer into `rules/environment.md` so the next session
  does not have to ask again.

Nothing else gets built for. No portability work, no cross-platform branches, no version
compatibility shims, no "and on Linux…" — none of it unless the user asks. If I think another
environment genuinely matters, I say so in one sentence and ask, rather than quietly building
for it.

The machine I execute tool-calls on and the machine a handed-over command targets are the same
question on a local session — but a **different** one on a remote session (the harness says so
directly: "a managed remote execution environment... in the cloud rather than on the user's
machine", and `CLAUDE_CODE_REMOTE` confirms it). On remote, I answer the second question the same
way as the first: recorded in `rules/handover-target.md`? Build for exactly that. Not recorded?
Find out right then — hard evidence first (a repo's own machine record, something they've told
me), a direct question only if neither exists — then write it down.

**Why:** work spent on environments the user does not have is work not spent on the one they do.
And the facts I do not check are exactly the ones that break the instructions I hand over — a
tool being installed is not the same as it being on PATH.

