---
name: Handover cards
description: Hands every user-run command over as a step card - one card, the same shape, on every surface
keep-coding-instructions: true
---

# Hand steps over as cards

This style is **opt-in and deliberately not forced.** It restates the step-card half of
`rules/house-rules.md`, which the plugin's `SessionStart` hook already injects into every session
and its `UserPromptSubmit` hook already restates on every prompt. Select it with
`/output-style` when running with `HOUSE_RULES_HANDOVER=off`, or in a session where you want the
format without the `Stop` check blocking a turn to correct it.

It does **not** set `force-for-plugin`, and that omission is load-bearing enough that `verify.py`
fails if someone adds it. Only one output style is active at a time, so a forced style silently
displaces whatever style the user selected — and this plugin is installed globally on every
device by design, which would make that override permanent, in every repo, with no way to keep
the rules while dropping the style. The plugin already owns the system-prompt region at
`SessionStart` and every prompt thereafter; forcing the slot would buy very little and cost the
user a setting that is theirs.

Note that output styles apply to the main conversation only — a subagent runs its own system
prompt. Work delegated to `@house-rules:executor` is governed by the injected rules, not by this
file.

## The format

Every command handed to the user to run goes in this shape:

````markdown
**<What this accomplishes>: <N> steps.** Do them in order; each step's output tells you it worked.

---

### Step 1 of <N> — <short title, what this step accomplishes>

Navigate to `<absolute path>` and open **<shell>** there (<how — right-click the folder →
*Open in Terminal*, etc.>).

```<fence label: powershell | bash | sh | cmd | zsh>
<the exact command, copy-pasteable, no placeholders>
```

**You should see:** <the literal output, or its first line>, and <what that means>.

*Next: step 2 <one clause saying what it does>.*

---
````

A single command drops the numbering and the `*Next:*` line and keeps every other field.

- The field order is fixed: title, `UNTESTED:` if it applies, location and shell, the fenced
  command, `**You should see:**`, `*Next:*`.
- `UNTESTED:` is the first line of the step, **above the fence** — never inside it, where it
  would break copy-paste.
- Nothing sits between the `---` pair but card content.
- The vocabulary is `---`, `###`, `**bold**`, plain paragraphs and top-level fenced blocks. No
  box-drawing borders, no fence inside a blockquote, no command in a table, no fence nested in a
  list item — each of those breaks in at least one renderer this reaches.
