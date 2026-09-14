---
description: Run the prompt workshop on the user's last request, or on a request they paste in
---

The user has asked to workshop a prompt explicitly — either their previous message in this
conversation, or new text they give you along with this command. This is the same flow the
`workshop` hook (`UserPromptSubmit`) nudges you toward automatically when a prompt looks
under-specified, run here on demand instead of by heuristic.

Read `rules/prompt-workshop.md` in this plugin (loaded into context at session start by the
`inject` hook — reread the file directly if it's no longer visible) and follow **The flow**
section on the prompt in question:

1. Restate the literal prompt back in one plain sentence.
2. Ask only about whichever of goal / constraints / success criteria / gating is missing or
   ambiguous — use `AskUserQuestion` for this rather than a wall of text, and ask about the
   gaps only, not all four dimensions on every prompt.
3. Propose the refined prompt back as a short structured summary and confirm it.
4. Once confirmed, proceed under the refined version — or, if the user invoked this mid-plan,
   hand the refined prompt back to them as the thing to run next rather than acting on it
   yourself, whichever matches how they asked.

If the prompt already reads as fully specified, say so in one line and ask whether they want to
proceed as written rather than manufacturing questions to justify running the command.
