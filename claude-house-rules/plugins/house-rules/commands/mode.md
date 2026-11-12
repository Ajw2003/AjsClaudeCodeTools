---
description: Switch the design loop or the builder helpers on or off for this repo, or show which are off
argument-hint: "[design loop on|off] [builders on|off]"
---

The speed switches (docs/4-systems/speed-switches.md in the house-rules repo) are saved by the
plugin's prompt hook as soon as aj's message contains `design loop off`, `design loop on`,
`builders off` or `builders on`. This command's own text is that message, so by the time you read
this the switch in `$ARGUMENTS` is already saved, and the hook's note above says so.

Reply in two or three plain sentences:

- What is on and what is off now, and why. Read `.claude/house-rules-mode.json` in the main checkout
  for what aj typed. A switch with no entry there follows the default: light (both off) when this
  session's model is Fable, full for every other model, and off when `HOUSE_RULES_LOOP` or
  `HOUSE_RULES_DELEGATION` is `off` in settings.json.
- What that means for this session: with the design loop off there are no design or build plan
  pages, no wait for approvals and no issues before code, while the destructive and main-branch
  guards and the evidence and commit checks still apply. With builders off, you build the work
  yourself rather than handing it to helpers.
- If `$ARGUMENTS` was empty or held no switch, say which lines to type to change it.

Commit `.claude/house-rules-mode.json` with the next commit, so the switch reaches aj's other
devices.
