---
description: Switch a feature group on or off for this folder or everywhere, or show which are off
argument-hint: "[design loop|pages|builders|issues|writing checks|autosave|house rules] on|off [everywhere]"
---

The feature switches (docs/4-systems/speed-switches.md in the house-rules repo) are saved by the
plugin's prompt hook as soon as aj's message holds a line such as `pages off` or `builders on everywhere`.
The groups are design loop, pages, builders, issues, writing checks, autosave and house rules. This command's own text is that message, so by the time you read
this the switch in `$ARGUMENTS` is already saved, and the hook's note above says so.

Reply in two or three plain sentences:

- Every group, with its state and where that came from: "this folder" (`.claude/house-rules-mode.json`
  in the main checkout), "everywhere" (`house-rules-mode.json` in the Claude config folder, usually
  `~/.claude/`) or "settings.json" (a `HOUSE_RULES_` value set to `off` with nothing typed). The folder
  file wins over the everywhere file. A group with no entry is on. Also list the typed lines in both
  files, "everywhere" ones included.
- What that means for this session: with the design loop off there are no design or build plan
  pages, no wait for approvals and no issues before code, while the destructive and main-branch
  guards and the evidence and commit checks still apply. With builders off, you build the work
  yourself rather than handing it to helpers. With pages off there is no page, no 160-word page rule
  and no page editor pass, though approvals still count. "house rules off" turns off everything
  except the destructive-command guard, the main-branch guard and the credit check.
- If `$ARGUMENTS` was empty or held no switch, say which lines to type to change it (add `everywhere` for all folders).

Commit `.claude/house-rules-mode.json` with the next commit, so the switch reaches aj's other
devices.
