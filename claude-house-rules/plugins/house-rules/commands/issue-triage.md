---
description: Triage a repo's open GitHub issues into done, duplicate and burst groups, as a proposal page
argument-hint: [owner/name]
---

Load the `house-rules:issue-triage` skill and follow it for `$ARGUMENTS` (a repo as
`owner/name`; if empty, this project's own repo).

The output is one proposal page built with `scripts/make_page.py`, and nothing else until aj
approves it. Do not close, relabel or create any issue before that approval.

If the skill cannot load, STOP and say so. Do not triage from memory.
