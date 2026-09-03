---
name: Handover cards
description: Hands every user-run command over as a step card - one card, the same shape, on every surface
keep-coding-instructions: true
force-for-plugin: true
---

# Hand steps over as cards

This style is **applied automatically** whenever the plugin is enabled, via
`force-for-plugin: true`. That is a reversal of how it shipped in 2.3.0, and the reason is worth
recording rather than quietly flipping:

The original argument was that forcing a style silently displaces whatever style the user selected.
That assumed the user could select one. They cannot — `/output-style` was deprecated in v2.1.73 and
removed in v2.1.91, and the desktop app has no style picker at all: `outputStyle` has to be set in
a settings file by hand. So un-forced meant unreachable on the surface this is actually used on,
and reaching it would have required the manual config editing the rules themselves forbid. What
forcing displaces is a settings-file value, not a live choice.

`verify.py` asserts the field is **present**, and will fail if it is removed. The check exists to
stop the decision being reversed by accident in whichever direction it currently points.

Note that output styles apply to the main conversation only — a subagent runs its own system
prompt. Work delegated to `@house-rules:executor` is governed by the injected rules, not by this
file. Styles are also read once at session start, so a change needs `/clear` or a new session.

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
