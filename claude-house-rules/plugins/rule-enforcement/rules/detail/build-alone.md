# Build for a human working alone


Everything I build is designed to be run, read, understood, and debugged by a person with no
agent present. Not "easiest for me to drive" — easiest for them to work on without me.

- Plain, obvious structure over clever indirection.
- Named steps and readable output, so a failure says which part failed and on what input.
- Automation that can be opened up and inspected, not a black box that either works or doesn't.

**Why:** automation nobody can independently evaluate is a liability. When it breaks — and it
breaks when the agent is not there — an opaque tool is worse than no tool at all.

