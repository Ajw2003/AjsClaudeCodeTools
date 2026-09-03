# Desktop verification — the step-card handover format

`verify.py` proves the hooks emit what the docs claim. It cannot see whether the format actually
changes Claude's first draft, whether the fence label really drives the Run button, or whether a
published page renders anywhere. This checklist covers exactly that gap, and its findings are what
the surface table in [`CLAUDE.md`](../CLAUDE.md) should state — that table currently records three
cells as *undocumented*, which is absence of evidence, not evidence.

Run it after a release that touches the handover format. Record the plugin version you ran it at.

**Version run at:** _not yet run_ · **Date:** _—_ · **Result:** _—_

## Which section covers which surface

| Surface (as the CLAUDE.md table names it) | Covered by |
|---|---|
| CLI | §2, §3 |
| IDE extension | §7 |
| Desktop **Code** tab | §2, §3, §4 |
| web / cloud session | §7 |
| claude.ai chat — web / desktop | §8 |
| iOS / Android | §4, §8 |

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

Run `/artifacts` in the Desktop **Code** tab.

**You should see:** either a list (publishing is available) or a message that it is not. §4 and §7
branch on this answer, and finding out here beats discovering it four tests later.

## 2 — Does the format survive without the Stop hook

The highest-information test here, which is why it comes before the cosmetic ones.

- **2a — the baseline.** Fresh session, ask for something that hands back two steps.
  **Pass:** one card, `Step 1 of 2`, and **no published page** — the threshold is four.
- **2b — the real question.** Fresh session with `HOUSE_RULES_HANDOVER=off`, same ask.
  **Pass:** the card still appears.
  **Fail means:** the injection is not doing the work and the `Stop` backstop is carrying the
  format alone — so every conforming reply costs a correction turn. That would make the decision to
  ship the output style un-forced worth revisiting, since "inject + scope already own this ground"
  was the argument for it.
- **2c — proportionality.** Ask for a handover of exactly one command.
  **Pass:** no numbering, no `*Next:*`, every other field present. Guards against the card
  becoming mandatory ceremony on a one-liner.

## 3 — The fence label and the Run button

Item 2 of the handover contract exists because "the fence label is what the Run button executes".
That has never been observed on this machine; it is inherited belief.

Get a reply containing a `powershell`-labelled fence and click **Run**.

**You should see:** it execute in PowerShell, not the default shell. If the button ignores the
label, the rule is still right — a mislabelled fence is still wrong — but its stated *reason* is
wrong, and `rules/house-rules.md` needs correcting rather than left as folklore.

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

## 6 — The output style is opt-in

Run `/output-style`.

**You should see:** `handover-cards` **listed but not active.** That is the un-forced decision
holding. If it is already active, `force-for-plugin` has leaked in somehow and `verify.py`'s
negative check has a gap worth finding.

Then select it and confirm normal coding behaviour is retained — that is `keep-coding-instructions`
doing its job. Switch back afterwards.

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

---

## After the run

Update the surface table in [`CLAUDE.md`](../CLAUDE.md) and the coverage line in
[`../claude-house-rules/README.md`](../claude-house-rules/README.md) so each cell states what was
observed, at which version. A row that stays unverified says so explicitly rather than being left
ambiguous — "not tested" is a fact; "undocumented" is a guess about someone else's docs.
