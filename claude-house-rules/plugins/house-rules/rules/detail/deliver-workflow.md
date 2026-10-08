# Deliver a whole workflow, not a starting point


A finished deliverable runs end to end with zero manual config editing and no tokens spent, and
comes with literal instructions: the exact commands to run, what they will see, what it means.
"Just test it" is not a delivery.

The difference, on "how do I set this up on a new device":

> **Not this:** install Claude Code and Git for Windows, then paste these two keys into
> `~/.claude/settings.json`. Restart.
>
> **This:** install Claude Code and Git for Windows, then run:
> `claude plugin marketplace add https://github.com/Ajw2003/AjsClaudeCodeTools.git`
> `claude plugin install house-rules@aj-house-rules`
> Restart to apply.

Same outcome. The second needs no hand-editing, no guessing at file contents, and cannot be
mistyped into a broken state.

**Why:** a deliverable that still needs assembly is a to-do list handed back to the user.

## An instruction names its exact input

An instruction the user is meant to act on names the exact input, not a category of input: the
literal prompt, the literal file, the literal value. Where the point is comparing two runs, the
expected result is recorded too, so a later run can disagree with an earlier one. "Ask for
something like X" is a description of a test, not a test.

This is the bare-command-block failure one level up. A command with no shell and no folder cannot
be run; an instruction with no fixed input cannot be *compared*, because every run produces
something different and no two runs can disagree.

**Why:** `docs/desktop-verification.md` shipped six verification steps whose entire input was
"ask for a multi-step handover" or "same five-step ask". §6 was unrunnable as written, caught by
the user rather than by any check, and fixed only by defining `PROMPT-MULTI`, `PROMPT-ONE` and
`PROMPT-LONG` verbatim, with a recorded baseline card to compare later runs against.

