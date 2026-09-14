---
description: Classify the user's last request (or pasted text) into a routing tier and offer to delegate to the matching subagent
---

The user asked to run the router explicitly — either on their previous message, or on new text
given alongside this command. This is the same classification the `route` hook (`UserPromptSubmit`)
runs automatically; here it's on demand.

Read `rules/agent-router.md` in this plugin (loaded into context at session start by the `inject`
hook — reread the file directly if it's no longer visible) and:

1. **State which of the three tiers the request fits** — doc/comms, recon/implementation, or
   planning/architecture/management — and why, in one sentence.
2. **Name the matching subagent** (`@agent-router:scribe`, `@agent-router:operative`, or
   `@agent-router:architect`) and read that agent's frontmatter to confirm its declared `model:`
   before naming it, rather than assuming — the same "read the declaration, don't restate it
   from memory" rule the `route` hook itself follows.
3. **If the current session is already running on the tier's model**, say so and offer to just
   do the work directly instead of delegating — a same-tier handoff is pure overhead.
4. **Otherwise, ask whether to delegate** rather than delegating unasked — this command is an
   explicit query about routing, not itself a go-ahead to spawn a subagent.

If the request doesn't cleanly fit one tier (it has doc, recon, and planning pieces), say so and
suggest splitting it rather than forcing a single tier.
