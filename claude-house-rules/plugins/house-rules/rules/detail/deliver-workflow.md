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

