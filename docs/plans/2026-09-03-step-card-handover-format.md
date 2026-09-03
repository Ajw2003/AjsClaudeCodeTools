# A step card for user-run steps, on every surface

## Context

PR #11 shipped a six-item handover contract. It fixed the *content* of a handover
(navigate-and-open-a-shell, one numbered step per action) but not the *shape*. The comparison
drawn was claude.ai's step card: bordered, one step at a time, bold title, numbered pager, Next.

Research settled what is actually reachable, and it is not that widget:

- The card is claude.ai's **custom visuals** feature — model-discretion, beta, **web and desktop
  chat only; it explicitly does not render on iOS/Android**. No documented emission format, so it
  cannot be requested deterministically anywhere.
- **Claude Code hooks run on every Claude Code surface** — terminal, IDE, Desktop Code tab, and
  Claude Code on the web. Not in claude.ai chat, mobile chat, or the Desktop chat tab.
- **Artifact publishing from Claude Code is documented for the CLI (v2.1.183+) and desktop app
  (v1.13576.0+) only.** Claude Code on the web is unnamed; mobile-app rendering of a published
  artifact is undocumented; API-key and gateway-authenticated sessions cannot publish at all.

So the load-bearing deliverable is a **markdown card that renders identically everywhere**. The
artifact is an escalation. No new hook event is needed — `Stop`/`handover` already fires at the
end of every turn, and `inject` + `scope` already carry the rules text.

Outcome wanted: any turn handing the user steps to run ends with something that reads as a
deliberate card on a bare terminal, in the IDE, on web, on desktop, and in mobile chat.

## Surface coverage, stated honestly

| Surface | Interactive card | Markdown card | Mechanism |
|---|---|---|---|
| Claude Code — CLI | Artifact (4+ steps or on request) | Yes | inject + scope + handover |
| Claude Code — IDE extension | Inherits the CLI; not separately documented | Yes | inject + scope + handover |
| Claude Code — Desktop Code tab | Artifact (4+ steps or on request) | Yes | inject + scope + handover |
| Claude Code — web / cloud | Publishing undocumented; treat as unavailable | Yes | ships with the repo install; cloud never reads `~/.claude/settings.json` |
| claude.ai chat — web / desktop | Sometimes, model's discretion, unrequestable | Yes | claude.ai Instructions block |
| claude.ai chat — iOS / Android | **Never** | Yes | claude.ai Instructions block |

No surface gets the real widget deterministically. Every surface gets the markdown card.

## The format

Vocabulary restricted to what survives every renderer: `---`, `###`, `**bold**`, plain
paragraphs, top-level fenced blocks. **Excluded and why:** box-drawing borders (wrap-break below
~80 cols, render as literal junk outside a fence), blockquote-wrapped cards (fence-in-blockquote
makes Run-button and copy-button attachment flaky), commands in tables, fences nested in list
items (per-renderer indent differences).

````markdown
**<What this accomplishes>: <N> steps.** Do them in order; each step's output tells you it worked.

---

### Step 1 of <N> — <short title, what this step accomplishes>

Navigate to `<absolute path>` and open **<shell>** there (<how: right-click the folder →
*Open in Terminal*>).

```<fence label: powershell | bash | sh | cmd | zsh>
<the exact command, copy-pasteable, no placeholders>
```

**You should see:** <the literal output or its first line>, and <what that means>.

*Next: step 2 <one clause saying what it does>.*

---
````

A single command drops the numbering and the `*Next:*` line but keeps every other field.

### How the card maps to the six items

| Card slot | Item |
|---|---|
| `### Step k of N — <title>` | 6 |
| `**UNTESTED:** <why>` — first line under the title | 5 |
| `Navigate to <abs path> and open **<shell>** there (<how>)` | 1, and the prose half of 2 |
| The fence label | the fence half of 2 |
| Fence body | 3 |
| `**You should see:**` | 4 |
| `*Next: …*` | the pager/Next analogue; omitted on the last step |

Three rules that make it checkable rather than aspirational:

1. **Fixed field order.** Title → UNTESTED → location+shell → fence → You should see → Next.
2. **`UNTESTED:` goes above the fence, never inside it.** Item 5 currently says "the first word
   of the block", which reads as *inside the fence* — where it breaks the copy-paste item 3
   requires. Fix the wording in the same change.
3. **Nothing between the `---` pair but card content.** Commentary goes outside the rules.

## Changes

### 1. `rules/house-rules.md` — the source of truth, edited first

New `#### The card` subsection under `### The handover format is not optional`: the literal
template, the fixed field order, the `UNTESTED:` placement clarification, the excluded
vocabulary, and the artifact trigger + degradation rule. The six numbered items stay exactly as
they are — the card is the shape they pour into, not a seventh item.

Every drift check reads against this file, so nothing else can pass until the phrases exist here.

### 2. `scripts/hook.py` — two strings, phrase-matched to step 1

- `HANDOVER_NOTE`: one added sentence naming the card's structural markers (`---` delimiters,
  `### Step k of N — title`, location and shell in prose, one fenced block per step labelled with
  the shell, `**You should see:**`). **No mention of artifacts** — this fires every turn, and a
  mention here becomes a per-turn nudge to publish.
- `SCOPE_REMINDER`: at most one added clause ("…handed over in the step-card format"). Still a
  fixed string, no file read — the `UserPromptSubmit` contract is intact.

### 3. `output-styles/handover-cards.md` — new, deliberately un-forced

Frontmatter: `name`, `description`, `keep-coding-instructions: true`. **No `force-for-plugin`.**

Rationale, recorded in the file and in `CLAUDE.md`: only one output style is active at a time, so
forcing one silently displaces whatever style the user selects — and this plugin is installed
globally by design, making that override permanent across every repo and machine. The gain would
be system-prompt persistence, which `inject` + `scope` already provide (`scope` exists precisely
to keep the rules live deep into a session). A style also does not reach subagents, so
`@house-rules:executor` would need the template duplicated regardless. Un-forced, it is the
opt-in for a session running with `HOUSE_RULES_HANDOVER=off`.

### 4. `templates/step-card.html` — new, self-contained

Reproduces image one: one step visible at a time, bold title, `Step 2 of 4` pager, Back/Next,
copy button per command, `UNTESTED` badge, prefers-color-scheme light/dark, progress in
`localStorage`. No external `<script src>`, no CDN CSS, no webfont, no network fetch.

Claude edits exactly one thing — a `const STEPS = [...]` array whose field names are the card's
fields (`title`, `location`, `how`, `shell`, `lang`, `command`, `expect`, `untested`), so filling
it is mechanical and the two representations cannot disagree.

Neither `runnable` nor `artifact` fires on `.html`, so no hook behaviour changes.

**Trigger: 4 or more steps, or an explicit request.** Below that the inline card is enough.
Degradation is a hard rule: the inline markdown card is written first and in full, always — the
artifact is never a replacement, never "see the page for steps 3–6". If publishing fails or is
unavailable, say so in one line and stop; no retry, no re-authoring inline. Do **not** try to
detect publishing support from a hook — there is no reliable signal for CLI version, auth mode,
or surface. Attempt, catch, degrade.

### 5. `docs/claude-ai-instructions.md` — new

Preamble saying what it is and where it goes (claude.ai → Settings → Instructions; account-wide,
so it reaches iOS/Android), then **one fenced block** holding the paste-able text and nothing
else. Self-contained and short — the field is length-bounded: the six items compressed to one
line each, the card template, and one line saying mobile gets the markdown card only.
Deliberately excluded: hooks, `@house-rules:executor`, `verify.py`, coding standards, artifacts.

### 6. Docs and version

`CLAUDE.md` — `output-styles/` and `templates/` under *Where things live*, the surface table, and
the un-forced decision with its reasoning. No new row in the hook table; no new event.
`claude-house-rules/README.md` — the surface table and the opt-in style.
`plugin.json` — 2.2.0 → 2.3.0.

Caution: `verify.py`'s doc check fails text matching `[0-9]+-check|all [0-9]+ checks`, so don't
write a step count in that shape.

### 7. `scripts/verify.py` — new checks, existing conventions

Format checks next to the handover block, component checks next to the executor block.

1. Extend the **existing** handover drift list with every new `HANDOVER_NOTE` phrase (`Step 1 of`,
   `You should see`, `step-card`) — the required pin for new hardcoded strings.
2. Extend the scope drift list with any added `SCOPE_REMINDER` clause.
3. **The template actually reaches the session**: `run_hook("inject", "")` and assert the card
   markers appear in the output — asserting the file contains it is not asserting it arrives.
4. `house-rules.md` still has `#### The card` exactly once, and item 6 is still intact, so the
   card subsection cannot quietly displace it.
5. The output style exists, has `name`/`description`/`keep-coding-instructions: true`, and
   **`force-for-plugin` is absent** — mirroring the `executor.md` dead-field check, so the
   decision cannot be reversed by accident.
6. `templates/step-card.html` exists, contains `const STEPS`, and has no `<script src=`,
   `<link rel="stylesheet"`, or `https://` in a `src=`/`href=` attribute.
7. Every card field name appears in the HTML — the specific drift this template exists to prevent.
8. `docs/claude-ai-instructions.md` exists, has exactly one fenced block, and its key phrases all
   appear in `house-rules.md`.
9. `CLAUDE.md` does not contain the literal template — extends the existing duplication check.

## Sequencing

1. `house-rules.md` (every drift check reads against it).
2. `hook.py` strings, phrase-matched to step 1.
3. verify checks 1–4; run the suite — proves the injection path before any new component exists.
4. `output-styles/` and `templates/`; verify checks 5–7; run the suite.
5. `docs/claude-ai-instructions.md`; check 8; run the suite.
6. `CLAUDE.md`, `README.md`, `plugin.json`; check 9; run the suite.

## Verification

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Exit 0, every check passing. Then by hand on aj's machine, since the suite cannot see rendering:

1. `/clear` or a new session — injected context only refreshes at session start.
2. A 2-step handover → inline card, no artifact.
3. A 5-step handover → inline card **and** a published artifact link.
4. Confirm the fence label drives the Run button, not just the prose.
5. Open `templates/step-card.html` in a browser, offline, with a filled `STEPS` array.
6. `HOUSE_RULES_HANDOVER=off` → the Stop backstop is silent, the injected format still applies.

## Explicitly not doing

- Chasing claude.ai's custom-visuals widget. No documented format, model-discretion, and it does
  not render on mobile at all — building on it would be building on an assumption.
- `force-for-plugin: true`, for the reasons in §3.
- A second `SessionStart` entry for a separate template file. The `standards` precedent exists
  because that handler does detection that can fail; a static template does not, and a second
  copy of the text is what the repo's single-source convention forbids.
- Any mention of artifacts in `HANDOVER_NOTE`, or a hook that tries to detect publishing support.
