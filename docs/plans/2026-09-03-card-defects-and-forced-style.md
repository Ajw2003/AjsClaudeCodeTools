# Fix the first real card's defects, and reverse the un-forced style decision

## Context

Plugin 2.3.1 is live on the desktop app and the format is reaching real replies — the RockSkipping
screenshot shows `### Step 1 of 2`, `**You should see:**`, the `---` rules and `UNTESTED:` all
landing. The container works. Four things inside it do not, and separately, desktop research
invalidated a decision already shipped.

### The four defects

| Observed | Rule that failed |
|---|---|
| ``In `C:\Users\aj\Desktop\GameDev\RockSkipping\relay`, Git Bash:`` | **Item 1 regressed** — the directory named as an aside, the exact thing PR #11 fixed. The card template shows only the *right* sentence, never the wrong one |
| Prose says `C:\Users\aj\...`; the command says `cd /c/Users/aj/... && npm test` | **No rule covers it.** Root cause is visible in the transcript: the tool call ran as **Bash**, so Claude pasted *its own* shell's path notation into a handover meant for the user's |
| Two *alternative* suites numbered `Step 1 of 2` / `Step 2 of 2` under "do them in order" | **No rule covers it.** Choices are not a sequence; the header asserts something false |
| "Correction to Step 1 — how you get there and the shell weren't stated properly" | **`HANDOVER_NOTE` working as written** — "append one short corrected block" yields a broken card followed by a prose patch, worse than either alone |

### What desktop research changed

- **`/output-style` was deprecated in v2.1.73 and removed in v2.1.91.** It exists on no surface.
  `docs/desktop-verification.md` §6 currently tells you to run it — a factual error already committed.
- **The desktop app has no style picker at all.** `outputStyle` must be set in a settings file.
  The un-forced style therefore cannot be selected on the surface aj actually uses without
  hand-editing config, which the repo's own "no manual config editing" rule forbids. The decision
  to ship it un-forced rested on a picker that does not exist.
- **Plugins are entirely unavailable in WSL sessions**, and the **Cowork tab** sources skills and
  plugins from the claude.ai account rather than `~/.claude`. Neither is in the surface table.
- **The Run button is undocumented** — its existence, its shell selection, and whether the fence
  label drives it. Zero Anthropic documentation. `house-rules.md` asserts the mechanism as fact.
- Windows shell selection **is** documented: with Git for Windows present, the Bash tool uses Git
  Bash; the PowerShell tool is on by default for claude.ai accounts. Git for Windows is *required*
  for the desktop Code tab. That corroborates the notation defect above.
- `/artifacts` being unavailable on desktop follows a documented rule — argument-less picker
  commands reply `isn't available in this environment` — not a special case.

Outcome wanted: the next real handover needs no correction block, the format applies on desktop
without config surgery, and the surface table stops omitting two surfaces and asserting one
unverified mechanism.

## Changes

### 1. Rules — `rules/house-rules.md`, under `#### The card`

**a. Show the anti-pattern.** Beneath the correct location sentence, the wrong form quoted as
wrong: ``Not `In C:\...\relay, Git Bash:` — that is a label on a command, not a step.`` The failure
was a shortcut back to a familiar shorthand, so a negative example sitting next to the positive one
is the fix most likely to stick.

**b. One folder, in the reader's notation.** The folder is written **once per step, in the notation
the named shell uses** — Git Bash `/c/Users/aj/...`, PowerShell `C:\Users\aj\...` — and the notation
follows **the shell the user will run it in, never the shell I ran it in**. That last clause is the
actual root cause and must be stated explicitly. And if the step says to open a prompt *in* that
folder, the command does not `cd` there again: a `cd` means either the navigation line or the
command is decoration, and the reader cannot tell which.

There is no default shell to assume — aj uses PowerShell or Git Bash depending on the repo — so the
rule says the shell is chosen per handover and named every time, deferring to
`rules/environment.md` (which exists on that machine) for per-device facts.

**c. Sequence versus choice.** The card means "do these in order". So: steps in order → the card;
alternatives the user acts on themselves → a plain list or headings, no numbering, no "do them in
order" header; a choice that must be made before work continues → the `AskUserQuestion` picker.

Record why the picker cannot replace the card generally, so it is not re-litigated: it **blocks**
the turn, it **cannot hold a fenced command** (so the commands would still need the card), it caps
at four options, and it **does not exist in claude.ai chat**. Its rendering in the desktop Code tab
is undocumented — noted as such, not asserted.

**d. Not touching the fence-label sentence.** `house-rules.md` says "the fence label is what the
Run button executes" and nothing documents that. Per your call, that wording waits until §3 of the
verification checklist is actually run, so it is written once against an observed fact rather than
revised twice.

### 2. `hook.py` — corrections replace, not annotate

`HANDOVER_NOTE`: replace *"append one short corrected block covering only what was missing"* with —
reprint **the corrected step in full card shape**, introduced by `Replacing step N:`. One step, not
the whole handover. The reader ends on something followable rather than a note about what was wrong
above it. Everything else in the note stands.

### 3. Force the output style — reversing 2.3.0's decision

`output-styles/handover-cards.md` gains `force-for-plugin: true`.

The original argument was that forcing displaces a style the user selected. On the desktop app there
is no picker to select one with, and `/output-style` no longer exists anywhere — so what forcing
displaces is a settings-file value, not a live choice, and *not* forcing means the style is
unreachable on the surface in question. The evidence the decision was made on turned out to be
wrong.

This inverts a test: `verify.py` currently asserts `force-for-plugin` is **absent**, with a failure
message saying the decision was deliberately not taken. That check flips to asserting it is
**present**, and its message must carry the new reasoning — the check exists to stop the decision
being reversed by accident, in whichever direction it currently points.

`CLAUDE.md`'s "Why the output style is shipped un-forced" section is rewritten to "Why the output
style is forced", stating the evidence that changed and the fact that it still does not reach
subagents.

### 4. Surface table — two missing surfaces, one corrected cell

Add to the `CLAUDE.md` table: **WSL sessions** (plugins unavailable entirely — a hard kill worth
naming) and the **Desktop Cowork tab** (config comes from the claude.ai account, so the plugin
covers the Code tab only). Note on the desktop rows that there is no style picker.

Because `verify.py` reads surface names out of that table and requires each to appear in
`docs/desktop-verification.md`, both new rows need coverage in the checklist — which is the check
working as intended.

### 5. `docs/desktop-verification.md` — fix the error, sharpen §3

- §6 rewritten: `/output-style` does not exist. The test becomes confirming the forced style is
  active **without any selection** (that is what forcing means) and that coding behaviour is
  retained by `keep-coding-instructions`. On desktop, `/config` opens Settings → Claude Code.
- §3 promoted and marked as the sole source of truth for the Run button, explicitly noting that
  rules wording is deliberately waiting on its result.
- New sections for the two added surfaces.
- **Findings so far** gains: `/artifacts` is explained by the documented argument-less-picker rule,
  not a special case; and the `Stop` hook was observed correcting a live draft on 2.3.1 — partial
  evidence for §2b, which it does not close, since §2b asks what happens with the hook *off*.

### 6. Version

`plugin.json` 2.3.1 → **2.4.0**. Forcing an output style changes installed behaviour on every
device; that is a minor bump, not a patch.

## Critical files

- `claude-house-rules/plugins/house-rules/rules/house-rules.md` — change 1
- `claude-house-rules/plugins/house-rules/scripts/hook.py` — `HANDOVER_NOTE` only
- `claude-house-rules/plugins/house-rules/output-styles/handover-cards.md` — add the frontmatter field
- `claude-house-rules/plugins/house-rules/scripts/verify.py` — flip the force check, extend the
  handover drift list, assert the anti-pattern and the sequence-versus-choice rule are present, and
  assert `inject` actually delivers them
- `CLAUDE.md`, `docs/desktop-verification.md`, `.claude-plugin/plugin.json`

## Verification

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Exit 0, including the flipped force check and the new assertions. Then on the desktop app, after
updating and restarting: a reply that hands over commands should need **no** "Correction to step N"
block. One appearing means the anti-pattern example did not take and it needs to move into
`HANDOVER_NOTE` as well. §3 stays open until you run it.

## Not doing

- Rewording the fence-label rule before §3 is run.
- Replacing the card with `AskUserQuestion` generally — it blocks, cannot carry a command, caps at
  four options, and does not exist in claude.ai chat.
- A second card template for alternatives; a list needs no definition or drift check.
