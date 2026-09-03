# Desktop verification — the step-card handover format

`verify.py` proves the hooks emit what the docs claim. It cannot see whether the format actually
changes Claude's first draft, whether the fence label really drives the Run button, or whether a
published page renders anywhere. This checklist covers exactly that gap, and its findings are what
the surface table in [`CLAUDE.md`](../CLAUDE.md) should state — that table currently records three
cells as *undocumented*, which is absence of evidence, not evidence.

Run it after a release that touches the handover format. Record the plugin version you ran it at.

**Version run at:** _not yet run_ · **Date:** _—_ · **Result:** _—_

### Findings so far

- **2026-09-03 — `/artifacts` is unavailable in the desktop app**, which answers "isn't available
  in this environment". Now explained by a documented rule rather than treated as a special case:
  built-in commands with no argument form reply exactly that in the Code tab. It is the *listing*
  command, not the publishing capability — publishing is documented for desktop v1.13576.0+, so §1
  tests publishing directly instead of inferring it from this.
- **2026-09-03 — the `Stop` hook was observed correcting a live draft** on 2.3.1: a reply ended
  with "Correction to Step 1 — how you get there and the shell weren't stated properly". Partial
  evidence for §2b, and the reason 2.4.0 changed corrections to reprint the step. It does **not**
  close §2b, which asks what happens with the hook *off*.
- **2026-09-03 — `/output-style` no longer exists on any surface** (deprecated v2.1.73, removed
  v2.1.91), and the desktop app has no style picker. §6 previously told you to run it; that was
  wrong and is rewritten. This is why 2.4.0 forces the style.

## Which section covers which surface

| Surface (as the CLAUDE.md table names it) | Covered by |
|---|---|
| CLI | §2, §3 |
| IDE extension | §7 |
| Desktop **Code** tab | §2, §3, §4 |
| web / cloud session | §7 |
| claude.ai chat — web / desktop | §8 |
| iOS / Android | §4, §8 |
| WSL session | §9 |
| Desktop **Cowork** tab | §9 |

---

## 0 — Get the current plugin onto the machine

Injected context only refreshes at session start, so testing without the restart at the end of this
section tests the *old* rules and will quietly pass for the wrong reason.

**Get to main and update the marketplace and plugin.** Navigate to
`C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools` and open **PowerShell** there.

```powershell
git checkout main
git pull --ff-only
claude plugin marketplace update aj-house-rules
claude plugin update house-rules@aj-house-rules
```

**You should see:** `claude plugin update` reporting a new version number — *not* "already at the
latest version". If it says the latter, the pull did not land and everything below is invalid.

Then **fully quit and restart** every Claude Code session, including any long-running one.

## 1 — Publishing smoke test, before anything depends on it

**Do not use `/artifacts` for this.** That command lists pages you already own, and it is **CLI
only** — the desktop app answers "isn't available in this environment", which says nothing about
whether the app can *publish*. Listing and publishing are separate capabilities; conflating them
would fail this section on a machine where §4 would have worked fine.

Instead ask for a publish directly, in the Desktop **Code** tab: *"publish a one-line test page as
an artifact."*

**You should see:** a link to a published page, or a specific refusal. A refusal naming the plan,
the sign-in method (API key and gateway tokens cannot publish — it needs a `/login` session), or
the surface is the real answer, and §4 and §7 should record it rather than being skipped silently.

To list pages you already own, use `/artifacts` **in the CLI**, not here.


## 2 — Does the format survive without the Stop hook

The highest-information test here, which is why it comes before the cosmetic ones.

- **2a — the baseline.** Fresh session, ask for something that hands back two steps.
  **Pass:** one card, `Step 1 of 2`, and **no published page** — the threshold is four.
- **2b — the real question.** Fresh session with `HOUSE_RULES_HANDOVER=off`, same ask.
  **Pass:** the card still appears.
  **Fail means:** neither `inject` nor the forced output style is doing the work, and the `Stop`
  backstop is carrying the format alone — so every conforming reply costs a correction turn. Since
  2.4.0 both of those are in play, a failure here would mean the format has to move somewhere the
  model cannot skim past, not just be stated in more places.
- **2c — proportionality.** Ask for a handover of exactly one command.
  **Pass:** no numbering, no `*Next:*`, every other field present. Guards against the card
  becoming mandatory ceremony on a one-liner.

## 3 — The fence label and the Run button

**This section is the only source of truth for the claim, and rules wording is waiting on it.**
Item 2 of the handover contract says "the fence label is what the Run button executes". A docs
search found **nothing** — not the button's existence, not how it picks a shell, not whether the
fence language tag has anything to do with it. Anthropic documents shell selection only for the
Bash and PowerShell tools *Claude itself* calls, which is a different mechanism and not evidence
about a button the user clicks. So the rule currently asserts something with nothing behind it,
and it was deliberately left unedited in 2.4.0 rather than reworded twice.

Get a reply containing a `powershell`-labelled fence and click **Run**.

**You should see:** it execute in PowerShell, not the default shell.

- **If it honours the label** — the rule's stated reason is correct. Record it here and nothing
  changes.
- **If it ignores the label** — the rule stays (a mislabelled fence still tells the *reader* the
  wrong shell) but its justification is folklore and `rules/house-rules.md` must be reworded to
  stand on the reader rather than the button.
- **If there is no Run button** on that block — say so; the claim is then vacuous.

Context for interpreting the result: Git for Windows is required for the desktop Code tab, so Git
Bash is always present, and the PowerShell tool is on by default for claude.ai accounts. Both
shells exist on that machine, which is what makes the test meaningful.

## 4 — The published page

Ask for a five-step handover on the Desktop **Code** tab.

**You should see:** the inline card **and** a published page link.

Then, on the page: the pager dots, Next and Back, jumping by clicking a dot, *View all steps*, the
per-command copy button, the `UNTESTED` badge on a step that carries one, light and dark (toggle the
OS theme), a narrow window (there is a breakpoint at 30rem), and reload-restores-position.

Then **open the published URL on the phone** — the Claude app first, then a mobile browser. That is
the cell the table records as undocumented.

Watch for one specific failure: Claude re-authoring the page instead of filling `STEPS` in
`templates/step-card.html`. The template exists so the card is identical every time and cheap to
produce. If it gets rewritten per turn, that has failed and the rules text needs to say so more
plainly than it does.

## 5 — The offline guarantee

Open `claude-house-rules\plugins\house-rules\templates\step-card.html` from disk with wifi off.

**You should see:** a fully working page. `verify.py` asserts this textually — no external `src`,
`href` or `https://` — but the reason for the rule is a machine mid-install with no network, and
that has never actually been tried.

## 6 — The forced output style applies with no selection

**`/output-style` does not exist** — deprecated v2.1.73, removed v2.1.91 — and the desktop app has
no style picker at all. That is precisely why 2.4.0 sets `force-for-plugin: true`: un-forced, the
style was unreachable without hand-editing a settings file.

So the test is that it applies with **nothing selected**. In a fresh Code-tab session, having
selected no style anywhere, ask for a multi-step handover.

**You should see:** the card. And normal coding behaviour intact — `keep-coding-instructions: true`
is what preserves it, so a session that has gone oddly non-technical is that field failing.

To inspect the setting on desktop, `/config` opens Settings → Claude Code; note that arguments
after `/config` are ignored there.

**Worth separating:** this cannot distinguish the style from `inject`, since both produce the card.
If §2b shows the card surviving with the `Stop` hook off, the injection is doing the work and the
style is belt-and-braces. That is the intended reading, not a failure.

## 7 — The other Claude Code surfaces

Same five-step ask in **Claude Code on the web** (a cloud session), and again in the **IDE
extension**. Both resolve table cells: the web row records publishing as undocumented, and the IDE
row says only that it inherits the CLI.

**You should see:** the markdown card in both. Whether either publishes is the finding.

## 8 — The chat surfaces, where no hook runs

Paste the block from [`claude-ai-instructions.md`](claude-ai-instructions.md) into
claude.ai → Settings → Instructions. Then start a new chat on the web, and a new chat on the phone,
and ask each for a multi-step handover.

**You should see:** the same card on both. Note whether the web chat *also* volunteers its own
interactive step widget — that is model discretion, so not a failure either way, but worth
recording, since it is the thing this whole format was built as an alternative to.

## 9 — The two surfaces the plugin does not reach

Neither is a card test. Both are confirmations that a documented limit is real, so the surface
table states a checked fact rather than a repeated claim.

- **WSL session.** Switch the environment dropdown to WSL and check whether house-rules is active
  at all — ask anything that would normally draw the injected rules. **Expected: it is not.**
  Anthropic documents that plugins are unavailable in WSL sessions. If the rules *do* appear,
  the docs are wrong or the limit has changed, and the table needs updating in the other
  direction.
- **Desktop Cowork tab.** Ask for a multi-step handover there. **Expected: no card**, because
  Cowork sources its skills and plugins from the claude.ai account rather than `~/.claude`. If a
  card appears, something is syncing that the docs do not describe — record it.

---

## After the run

Update the surface table in [`CLAUDE.md`](../CLAUDE.md) and the coverage line in
[`../claude-house-rules/README.md`](../claude-house-rules/README.md) so each cell states what was
observed, at which version. A row that stays unverified says so explicitly rather than being left
ambiguous — "not tested" is a fact; "undocumented" is a guess about someone else's docs.
