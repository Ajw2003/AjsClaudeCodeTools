# Code follows the standards loaded for this project


The coding standards injected at session start are binding for code written in this repo, not
background reading. Where a file's existing style conflicts with them, the file wins — that
carry-over is already stated in `coding-philosophy.md` itself, consistency within a file beats
a global rule.

A repo can be more than one stack, and when several documents load, each governs only its own
languages — the preamble that comes with them says which document applies where. Applying one
stack's conventions to another's files (formatting C# like TypeScript because both loaded) is
the failure this rule exists to prevent.

A repo whose needs differ from what got detected pins its own set in `.claude/standards` rather
than the standards being ignored quietly.

**Why:** injected text with no rule behind it is background reading, easy to skim past. A repo
sitting on two stacks needs the two kept apart, not merged into one undifferentiated wall of
rules.

