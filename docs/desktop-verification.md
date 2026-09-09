# Desktop verification — the step-card handover format

`verify.py` proves the hooks emit what the docs claim. It cannot see whether the format actually
changes Claude's first draft, or whether a published page renders anywhere. This checklist covers
exactly that gap, and its findings are what
the surface table in [`CLAUDE.md`](../CLAUDE.md) should state — that table currently records three
cells as *undocumented*, which is absence of evidence, not evidence.

Run it after a release that touches the handover format. Record the plugin version you ran it at.

**Version run at:** 2.4.0 → 2.10.0 · **Date:** 2026-09-07 · **Result:** §0, §2a, §2b and §3 all
answered, and 2.9.0's location-independence fix verified working on the desktop app (see
Findings). 2.10.0's handover gate is verified on the app both ways — silent on a conforming card
(test A), still firing on a card missing fields (test B). §1 and §4–§9 are not yet run.

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
- **2026-09-03 — a second real handover on 2.3.1 came out correct in every field**: item 1 as a
  navigate-and-open instruction, no redundant `cd`, PowerShell notation matching the shell that
  was actually used, `UNTESTED:` above the fence, header and `*Next:*` lines present. None of the
  four defects from the first observation recurred, and this was *before* 2.4.0's rule changes —
  so the format wording is working and the remaining problem was hook noise, not the format.
  Further partial evidence for §2a, which it does not close.
- **2026-09-03 — the check announced itself on a conforming reply**: the same turn ended with
  "Both steps already carry all six fields in card shape", and an unrelated turn that handed over
  no commands had to answer the check in the user's view. Both are why the check now reads
  `last_assistant_message` and stays silent when the reply has no fenced block.
- **2026-09-03 — `/output-style` no longer exists on any surface** (deprecated v2.1.73, removed
  v2.1.91), and the desktop app has no style picker. §6 previously told you to run it; that was
  wrong and is rewritten. This is why 2.4.0 forces the style.
- **2026-09-07 — PRs #12 and #13 both shipped under version 2.4.0.** #13 deliberately skipped the
  version bump on the reasoning that 2.4.0 was unreleased — true when it was written, false once
  #12 merged first, so #13's `Stop`-hook change landed as a second, different code state under the
  same version number. The plugin cache is version-keyed
  (`~/.claude/plugins/cache/aj-house-rules/house-rules/<version>/`) while `installed_plugins.json`
  separately records a `gitCommitSha`, so whether a same-version change like #13's actually reaches
  an already-installed copy is UNVERIFIED. 2.5.0 makes the immediate collision moot, and the new
  byte-for-byte content comparison added to `tools/clean_install_test.py` makes a future repeat
  detectable rather than silent.
- **2026-09-07 — the byte-for-byte install check was proven in both directions.** Run with
  `--skip-strip` against a stale install it correctly reported FAIL lines for the files that had
  changed, alongside differing installed and repo versions; run again after
  `claude plugin marketplace update` + `claude plugin update` + a restart, it reported clean. That
  is the before-fail/after-pass pair PR #14 named as outstanding — a check that has only ever
  passed has not been tested, and this one now has been.
  Still unexercised: the branch that fires on **equal versions with differing content**, which is
  the exact collision the check was built for. Both runs had differing versions, so that path has
  never executed. It would need a deliberate same-version change to reach.
- **2026-09-07 — updating across a version change works on the desktop app.** 2.4.0 → 2.5.0 landed
  and the content check confirmed it by content, not by the reported version alone. This says
  nothing about the same-version case, which remains UNVERIFIED.
- **2026-09-07 — on the Windows desktop Code tab, a card step said "Navigate to
  `C:\Users\aj\Desktop\GameDev\RockSkipping\relay` and open **Git Bash** there" with a fenced
  `npm test`. Clicking Run produced:**

  ```
  PS C:\Users\aj\Desktop\GameDev\RockSkipping\Assets> npm test
  > echo "Error: no test specified" && exit 1
  ```

  Two facts, now observed rather than assumed: (1) **the Run button does not select the shell
  from the fence label** — the reply named Git Bash, it ran PowerShell; (2) **the Run button
  executes in the session's working directory, not the folder the step names** — it ran in
  `\Assets`, not `\relay`, and therefore hit the wrong `package.json` and failed. §3 is answered
  by fact (1). Fact (2) exposed a conflict between the card's navigate-and-open line (item 1,
  true for whoever pastes) and the no-`cd` rule (which assumed the reader was already in the
  named folder): resolved by requiring commands that do not depend on where the prompt is —
  location-independent forms such as `npm --prefix "<absolute path>" test` or
  `git -C "<absolute path>" status`. `rules/house-rules.md`, `hook.py`'s `scope` and `handover`
  reminders, and `docs/claude-ai-instructions.md` were corrected in response.

- **2026-09-07 — §2b PASSES.** With `HOUSE_RULES_HANDOVER=off` and a fresh session, a two-step
  handover still came back as a full card: header line, `---` rules, `### Step 1 of 2`, the
  navigate-and-open line with the how, `**You should see:**`, the `*Next:*` line, `UNTESTED:` above
  step 2, and no correction block. So `inject` and the forced output style carry the format on
  their own — the `Stop` check is a backstop, not the mechanism. This was the result that would
  have sent the design back, and it did not. The reply also volunteered "PowerShell works too — the
  command is identical", which is the corrected item 2 landing.
- **2026-09-07 — but the Run-button failure recurred verbatim in that same reply**, with 2.8.0
  installed and the rule loaded (confirmed by `Select-String` finding
  `does not depend on where the prompt is` at `house-rules.md:201` in the installed copy). The
  command was a bare `npm test`, which ran from `Assets` and failed again. So the rule was **loaded
  and ignored** — a stale install was ruled out, not assumed. Three reasons it did not bite, all
  fixed in 2.9.0:
  1. It sat as the *second clause* of a bullet titled "No redundant `cd`" — the bullet leads with
     a prohibition, so the actual requirement read as subordinate.
  2. It was not in the six-item contract. Item 3 said only "copy-pasteable as written, no
     placeholder to fill in" — nothing about location. It now says the command **runs from
     anywhere**, because a command that only works in one folder is not copy-pasteable.
  3. `output-styles/handover-cards.md` contained none of it, and with the `Stop` check off that
     style is one of only two carriers — so during this very test the rule's entire presence was
     the one buried sub-bullet. The style now restates all six items, and `verify.py` gained a
     drift check (proven to fail before being trusted) so it cannot fall behind again.
- **2026-09-07 — 2.9.0's location-independence fix is VERIFIED WORKING.** The same RockSkipping
  question that failed twice returned
  `npm --prefix "C:\Users\aj\Desktop\GameDev\RockSkipping\relay" test`, and clicking **Run**
  executed it from `Assets` — the directory that broke it both previous times — reaching
  `tests 46 / pass 46 / fail 0`. The reply also volunteered "the command below runs from anywhere,
  so the session's current folder is fine too", which is item 3's new wording landing verbatim.

  **The lesson is about placement, not wording.** This rule failed twice while it lived as a
  sub-bullet under `#### The card` — restating it more forcefully changed nothing. It started
  working the moment it moved into the **six-item contract** (item 3) and into
  `output-styles/handover-cards.md`. A rule that must change the draft belongs in the six; a rule
  in a sub-bullet is documentation.
- **2026-09-07 — the compliance announcement, and the gate that fixed it (2.10.0).** That same
  reply ended "Both cards carry all six fields — nothing to correct", which `HANDOVER_NOTE` calls
  "itself the failure this is guarding against" and `house-rules.md` forbids as "A card never
  announces its own compliance". Wording failed twice (2.4.0 strengthened it; 2.9.0 states it
  outright), and it cannot succeed by wording at all: the continued turn **cannot be made
  silent** — `suppressOutput` is documented as having no effect — so once the check fires on a
  reply needing nothing, something is always emitted. The repo was shipping a rule that its own
  hook broke on every correct handover.

  2.10.0 fixes it structurally instead: `handover` now stays silent when the reply already
  carries the card markers (`---`, `###`, `You should see:`), so a conforming reply never fires
  it and there is nothing to announce. This was considered and declined once, on the grounds that
  a reply carrying the markers but botching a field would slip through unchecked. That cost is
  real and still stands — but it is a **silent miss on some turns**, traded against a **visible
  defect on every good one**, and the drafting-path carriers (`inject`, `scope`, and the output
  style) all still state the six before the reply is written. The `Stop` check was always the
  backstop, not the primary carrier.

- **2026-09-07 — the 2.10.0 gate VERIFIED on the desktop app (test A of two).** On Windows 11,
  plugin 2.10.0 installed and byte-matching source, a three-step handover came back as a card
  ending at its closing `---`. What followed it was new information — the marketplace clone
  reporting 38 commits unpushed to its own upstream, and the restart reminder — not a report on
  the card's own fields. The "both cards carry all six fields" sentence that 2.9.0 produced on
  every conforming reply is gone. Note that this result cannot distinguish "the check fired and
  said nothing" from "the check did not fire"; it does not need to, because the announcement is
  the only observable either way.

  Recorded incidentally from the same run: `claude plugin update` is **version-gated** and copies
  nothing while the version string is unchanged, which is why `tools/force_update.py` (uninstall
  then reinstall) exists rather than being redundant with the CLI verb. It reported
  `OK: house-rules 2.10.0 matches source, file-for-file`, and `verify.py` on the freshly installed
  copy reported 101/101.

- **2026-09-07 — the 2.10.0 gate VERIFIED on the desktop app (test B of two).** The first attempt
  was **inconclusive by test design, not by defect**: the prompt said *"in one line, no card"*, and
  the reply ended on a bare fence with *"You asked for one line, no card - that's it above"*.
  Replaying that exact reply text through the hook shows it **does** fire, so what followed was
  Claude obeying an explicit user instruction over a Stop-hook reminder. A fired check and an
  unfired check are indistinguishable under a prompt that forbids the card — do not write a test
  that way again.

  The retry (*"quick - what do I type to see which house-rules version is installed?"*, no
  instruction about format) passed. The first draft was card-**shaped** but missing two of the
  six: no location line (it said "Open PowerShell anywhere" rather than navigate-to-a-path) and no
  `UNTESTED:`. The checklist fired and the reply appended `Replacing the step above:` with both
  fields restored.

  That is the risk named when the gate went in — a reply carrying the markers but botching a field
  slipping through unchecked — and it did **not** materialise, because the draft that skipped
  fields also skipped a marker (a bold title instead of `###`). Not a guarantee, but evidence the
  gate is narrower than the failure mode feared. Worth watching: the correction was introduced by
  `Replacing the step above:` where `house-rules.md` specifies `Replacing step N:`.

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

## The canonical prompts, and the baseline to compare against

Every section below that needs a handover uses **one of these three prompts, pasted verbatim**.
They are not examples to paraphrase. "Ask for a multi-step handover" is what this section replaces:
it produces a different card every run, so no two runs can disagree and nothing is actually being
tested. A fixed prompt with a recorded answer is the only thing that makes a later run comparable.

| Name | Paste this verbatim |
|---|---|
| **PROMPT-MULTI** | `give me the steps to update the house-rules plugin from source and re-verify it` |
| **PROMPT-ONE** | `what do I type to see which house-rules version is installed?` |
| **PROMPT-LONG** | `give me the steps to set this repo up from scratch on a new Windows machine: clone it, install Python if missing, install the plugin, set verbose and the model, and prove it works` |
| **PROMPT-DOCS** | `where does documentation go in this repo, and which file do I update when a milestone's status changes but the definition of done has not?` |
| **PROMPT-SKILL** | `how do I decide what counts as a system worth its own doc?` |
| **PROMPT-NOOP** | `in docs/architecture.md, in the section about the shim in front of the Python file, add a sentence saying that py is the Windows launcher` |

`PROMPT-MULTI` is chosen because its answer is **determined by the repo**, not by Claude's
invention: the three commands are the ones `CLAUDE.md` documents. If a run returns different
commands, that is a finding about the rules, not prompt variance.

### The recorded baseline for PROMPT-MULTI

Observed 2026-09-07, Windows 11 desktop **Code** tab, plugin 2.10.0 byte-matching source. This is
the data point later runs are compared against:

- **Three steps**, headed `Step 1 of 3` … `Step 3 of 3`.
- Step 1 — pull: `git -C "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools" pull --ff-only`
- Step 2 — force-reinstall: `python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\tools\force_update.py"`
- Step 3 — verify: `python "C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\claude-house-rules\plugins\house-rules\scripts\verify.py"`
- Every step: navigate-to-an-absolute-path plus the shell in prose, one ```` ```powershell ```` fence,
  and a `**You should see:**` line.
- **No published page, but a one-line offer of one** — three steps is at or over the two-step
  offer threshold, and a page is published only if the offer is taken.
- The reply ends at the card's closing `---`; the only prose after it was new information (the
  clone's unpushed commits, the restart reminder), never a report on the card's own fields.

**A later run matches the baseline if** the step count, the three commands, and the per-step fields
are the same. Wording differences in titles and prose are not failures. Different *commands*, a
missing field, a page published without being asked for, a missing offer at two or more steps, or
a trailing compliance sentence are.

`PROMPT-LONG` exists only for the sections that need a longer card than PROMPT-MULTI produces
(§4, §7). It has **no recorded baseline yet** — the first run of §4 establishes one. Note that
since 2.17.0 no prompt publishes a page on its own: §4 takes the offer, it does not clear a
threshold.


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

Do not stop at the version number alone — trust content, not the label. Grep the installed copy
directly for a marker from the newest change:

UNTESTED:
```powershell
Select-String -Path "$env:USERPROFILE\.claude\plugins\cache\aj-house-rules\house-rules\*\scripts\hook.py" -Pattern "_reply_needs_the_handover_check"
```

**You should see:** at least one match. No match means the installed copy predates the change even
if the reported version number looks current.

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

- **2a — the baseline.** Fresh session, **PROMPT-MULTI**.
  **Pass:** the recorded baseline above, and **no published page** — three steps earns an offer,
  and nothing publishes until the offer is accepted.
- **2b — the real question.** Fresh session with `HOUSE_RULES_HANDOVER=off`, **PROMPT-MULTI** again.
  **Pass:** the card still appears.
  **Fail means:** neither `inject` nor the forced output style is doing the work, and the `Stop`
  backstop is carrying the format alone — so every conforming reply costs a correction turn. Since
  2.4.0 both of those are in play, a failure here would mean the format has to move somewhere the
  model cannot skim past, not just be stated in more places.
- **2c — proportionality.** **PROMPT-ONE**, whose answer is a single command.
  **Pass:** no numbering, no `*Next:*`, every other field present. Guards against the card
  becoming mandatory ceremony on a one-liner.

## 3 — ANSWERED: the fence label does not drive the Run button

On 2026-09-07, on the Windows desktop Code tab, a card step said "Navigate to
`C:\Users\aj\Desktop\GameDev\RockSkipping\relay` and open **Git Bash** there" with a fenced
`npm test`. Clicking **Run** produced:

```
PS C:\Users\aj\Desktop\GameDev\RockSkipping\Assets> npm test
> echo "Error: no test specified" && exit 1
```

**Result: the Run button does not select the shell from the fence label.** The reply named Git
Bash; the button ran PowerShell. The same observation also showed the Run button executing in the
session's working directory (`\Assets`) rather than the folder the step named (`\relay`), hitting
the wrong `package.json` and failing — a second, separate fact, tracked in the Findings list
above rather than here since it is not about the fence label.

Item 2 of the handover contract previously said "the fence label is what the Run button
executes" — that justification is now known false and has been reworded to stand on the reader:
the label tells the reader which shell the command's syntax is for, and a mislabelled fence is
broken the moment they paste it into the shell the prose named, regardless of what any Run button
does. `rules/house-rules.md`, `hook.py`'s `scope` and `handover` reminders, and
`docs/claude-ai-instructions.md` were all updated to match.

Context that shaped the observation: Git for Windows is required for the desktop Code tab, so Git
Bash is always present, and the PowerShell tool is on by default for claude.ai accounts — both
shells existed on that machine, which is what made the mismatch detectable.

## 4 — The published page

**PROMPT-LONG** on the Desktop **Code** tab, then **accept the offer** — since 2.17.0 nothing
publishes unasked, so taking the offer is what produces the page.

**You should see:** the inline card, then a one-line offer; and after accepting, a published page
link. A page appearing before the offer is accepted is a failure, not a convenience.

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
selected no style anywhere, **PROMPT-MULTI**.

**You should see:** the card. And normal coding behaviour intact — `keep-coding-instructions: true`
is what preserves it, so a session that has gone oddly non-technical is that field failing.

To inspect the setting on desktop, `/config` opens Settings → Claude Code; note that arguments
after `/config` are ignored there.

**Worth separating:** this cannot distinguish the style from `inject`, since both produce the card.
If §2b shows the card surviving with the `Stop` hook off, the injection is doing the work and the
style is belt-and-braces. That is the intended reading, not a failure.

## 7 — The other Claude Code surfaces

**PROMPT-LONG** again in **Claude Code on the web** (a cloud session), and again in the **IDE
extension**. Both resolve table cells: the web row records publishing as undocumented, and the IDE
row says only that it inherits the CLI.

**You should see:** the markdown card in both. Whether either publishes is the finding.

## 8 — The chat surfaces, where no hook runs

Paste the block from [`claude-ai-instructions.md`](claude-ai-instructions.md) into
claude.ai → Settings → Instructions. Then start a new chat on the web, and a new chat on the phone,
and give each **PROMPT-MULTI**.

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
- **Desktop Cowork tab.** **PROMPT-MULTI** there. **Expected: no card**, because
  Cowork sources its skills and plugins from the claude.ai account rather than `~/.claude`. If a
  card appears, something is syncing that the docs do not describe — record it.

## 10 — The tiered-documentation rule and the project-docs skill

Added 2.12.0. Three checks, and they are separable on purpose: the rule reaching the session, the
skill loading on demand, and the pair **not** firing when they should stay quiet. A run that only
does the first proves the text arrived, not that anything uses it.

Run all three in a **fresh Code-tab session** after §0's restart — injected context refreshes at
session start, so testing before that tests 2.11.0 and passes for the wrong reason.

### 10a — The rule reached the session

**PROMPT-DOCS**, in any repo.

**You should see:** the five tiers named with their filenames — `docs/README.md`,
`docs/Roadmap.md`, `docs/ProjectState.md`, `docs/systems/`, `docs/Today.md` — and the direct
answer that a milestone's *status* moving is a tier-3 change, so `docs/ProjectState.md` is updated
and `docs/Roadmap.md` is left alone.

**Why this prompt and not a friendlier one:** the answer is only available from the rule. A session
without it gives generic documentation advice and cannot produce those five filenames or that
tier-2/tier-3 distinction, because nothing else in the plugin mentions them. That is what makes
this falsifiable rather than agreeable — a wrong answer looks obviously different, not just
worse-worded.

**Fails if** the reply gives sensible generic advice with no filenames, or names the tiers but says
to update the roadmap.

### 10b — The skill loads, and is not just the rule talking

**PROMPT-SKILL**, same session.

**You should see:** the transcript showing `SKILL.md` actually being **read**, and the answer
citing it by line (`SKILL.md:82`, `SKILL.md:95`, or similar). The substance should turn on
**runtime-critical** as the filter, and on the four sections a tier-4 doc has to fill.

**Why this discriminates:** `rules/house-rules.md` names the four sections nowhere — it says only
that systems get a document each. An answer that reasons from those sections, and cites the file
by line, cannot have come from the rule alone. The tool call is the strongest single signal: the
skill either got read or it did not, and that is visible in the transcript rather than inferred
from wording.

**This criterion was rewritten after the first run**, and the reason is worth keeping. It
originally demanded two verbatim phrases from the skill — *"if this is wrong, does the product
stop working?"* and *"three and eight"* — on the reasoning that neither appears in the rule. The
2.12.0 run **passed the underlying claim and failed that wording**: the transcript showed
`Read SKILL.md` and two accurate line citations, but the answer synthesised from the tier-4
section at `SKILL.md:82` rather than reciting the sentence at `SKILL.md:42`. The check assumed
recitation where the model summarises, so it would have reported a false failure on a working
plugin. **Do not test for a sentence the model has no reason to quote**; test for the file being
read and the reasoning being traceable to it.

**Fails if** nothing in the transcript reads `SKILL.md`, or the answer is generic enough to have
come from the rule alone, or if the skill has to be invoked by name
(`/house-rules:project-docs`) before either appears — the skill's description is
supposed to earn the load on its own.

### 10c — The negative control

**PROMPT-NOOP**, same session, in this repo.

**You should see:** the sentence added to the existing section. Nothing about tiers, no
`project-docs` load, no proposal to restructure `docs/`.

The prompt names an edit that is always available — a sentence added to a section that exists —
rather than a defect that has to be present for the test to run at all. An earlier draft said
"fix the typo in the second paragraph", and there is no typo there; the step would have been
unrunnable, which is the failure `rules-backlog.md` records under *Vague statements and
instructions*.

**The 2.12.0 run's edit was kept, so `PROMPT-NOOP` is now spent.** `docs/architecture.md:9`
already carries the `py` sentence, and a later run of this prompt would find the work done and
have nothing to do — which tests nothing. **A later run needs a fresh one-line edit to a section
that already exists**, anywhere in `docs/`, phrased as concretely as this one was. Record the
replacement in the prompts table when you use it; do not reuse a prompt whose edit is already in
the file.

**Why this is a required check, not padding:** the skill's own frontmatter excludes "an ordinary
edit to a document that already exists", and an always-injected rule about documentation is exactly
the shape that starts firing on every file with an `.md` extension. Over-triggering here is more
likely than under-triggering and would be far more annoying, because it turns a one-line fix into a
restructuring proposal.

**Fails if** the reply reaches for the skill, lectures about tiers, or offers to reorganise the
folder before doing what was asked.

### Recorded baseline

Observed 2026-09-08, Windows 11 desktop **Code** tab, plugin **2.12.0**. All three passed. This is
the data point later runs are compared against.

**10a — `PROMPT-DOCS`.** Run twice, in two different repos, and both passed:

- In `RockSkipping/Assets` (a repo that *has* the five tiers): rendered the tier table with all
  five filenames, answered `../docs/ProjectState.md`, and quoted `docs/README.md:52` as the source
  of the tier-3/tier-2 split.
- In `AjsClaudeCodeTools` (a repo that does **not** have them yet): same table, same answer —
  update `docs/ProjectState.md`, leave `docs/Roadmap.md` alone — and then noted unprompted that
  this repo's `docs/` is `architecture.md` / `desktop-verification.md` / `rules-backlog.md`, that
  there is no `ProjectState.md` here to edit, and that scaffolding one is a **restructure** the
  skill covers rather than an ordinary doc edit. That last part is the rule correctly
  distinguishing its own trigger conditions without being asked, and is a stronger pass than the
  criterion required.

**10b — `PROMPT-SKILL`.** Passed, and rewrote the criterion — see the note above. The transcript
showed `Read SKILL.md`, and the answer cited `SKILL.md:82` and `SKILL.md:95`, both real lines
(the tier-4 heading and the `systems/README.md` line). It reasoned from **runtime-critical** and
the four sections, and added a judgement the skill does not state — that a doc which can only fill
sections 1 and 2 is a paraphrase of the source and should not exist. Neither nominated phrase
appeared.

**10c — `PROMPT-NOOP`.** Passed cleanly. Added the sentence to `docs/architecture.md:9`, placed so
`py` is explained before the paragraph reaches the `python3` stub problem. No tier talk, no skill
load, no restructuring offer.

**A later run matches this baseline if** 10a produces the five filenames and the
`ProjectState.md`-not-`Roadmap.md` answer, 10b shows `SKILL.md` being read and cited, and 10c
makes the edit and nothing else. Different wording is not a failure. A missing file read in 10b,
a roadmap answer in 10a, or any tier commentary in 10c is.

---

## After the run

Update the surface table in [`CLAUDE.md`](../CLAUDE.md) and the coverage line in
[`../claude-house-rules/README.md`](../claude-house-rules/README.md) so each cell states what was
observed, at which version. A row that stays unverified says so explicitly rather than being left
ambiguous — "not tested" is a fact; "undocumented" is a guess about someone else's docs.
