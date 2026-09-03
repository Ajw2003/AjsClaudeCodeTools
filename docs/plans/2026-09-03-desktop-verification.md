# Desktop verification for the step-card format

## Context

PR #11 is merged; `main` carries plugin 2.3.0 with the six-item handover contract, the step-card
format, the un-forced output style, `templates/step-card.html`, and the claude.ai Instructions
block. `verify.py` passes 89 checks.

But `verify.py` only proves the hooks emit what the docs claim. Three classes of thing it
structurally cannot reach, and all three are load-bearing:

1. **Whether the injected format actually changes Claude's first draft.** If the card only appears
   because the `Stop` hook blocked the turn and asked for it, every conforming reply costs a
   correction turn — the exact cost the injection was meant to avoid.
2. **Whether the fence label really drives the Run button.** That is the entire justification for
   item 2 of the contract, and it has never been observed — it is inherited belief.
3. **Three rows this repo committed to `CLAUDE.md` as "undocumented"**: publishing from the
   Desktop Code tab, publishing from Claude Code on the web, and whether a published page renders
   in the Claude mobile app. Those currently rest on absence of documentation, not observation.

The artifact path in particular has never been exercised end to end — Claude must read
`templates/step-card.html` out of the plugin directory and fill its `STEPS` array. That is the
single most likely thing to be broken.

Outcome wanted: a checklist the repo keeps, run once now, with its findings folded back into the
surface table so the table states what was observed rather than what was not documented.

## Deliverable 1 — `docs/desktop-verification.md`

A committed checklist, in the step-card format itself (dogfooding: if the format is bad to follow,
that shows up while writing it). Each item states what to do, what a pass looks like, and what a
failure means — not just "check X works".

### Section 0 — get 2.3.0 onto the machine

`main` is merged, so: `git checkout main`, `git pull --ff-only`, `claude plugin marketplace update
aj-house-rules`, `claude plugin update house-rules@aj-house-rules`, then **fully quit and restart**
every Claude Code session. Injected context only refreshes at session start; testing without the
restart tests the old rules. Pass: `claude plugin update` reports 2.3.0, not "already at the latest
version".

### Section 1 — publishing smoke test, first

`/artifacts` in the Desktop **Code** tab, before anything that depends on publishing. Everything in
section 3 branches on this answer, and finding out here beats discovering it four tests later.

### Section 2 — does the format survive without the Stop hook

The highest-information test in the list, so it comes before the cosmetic ones.

- **2a** Fresh session, ask for something that hands back 2 steps. Pass: one card, `Step 1 of 2`,
  no published page (the threshold is 4).
- **2b** Fresh session with `HOUSE_RULES_HANDOVER=off`, same ask. Pass: **the card still appears.**
  Fail means the injection is not doing the work and the `Stop` backstop is carrying the format
  alone — which would make the un-forced output-style decision worth revisiting, since that was
  the argument for it.
- **2c** Ask for a handover of exactly one command. Pass: no numbering, no `*Next:*`, every other
  field present. Guards against the card becoming mandatory ceremony on a one-liner.

### Section 3 — the fence label and the Run button

Item 2's whole justification, never observed. Click **Run** on a `powershell`-labelled fence in the
Desktop Code tab and confirm it executes in PowerShell rather than the default shell. If the button
ignores the label, item 2's stated reason is wrong and the rule text needs correcting — the rule
would still be right, but for a different reason.

### Section 4 — the published page

Ask for a 5-step handover on the Desktop Code tab. Pass: the inline card **and** a published page.

Then on the page: pager dots, Next/Back, dot-jump, *View all steps*, per-command copy button,
`UNTESTED` badge on a step that has one, light and dark (OS theme toggle), a narrow window (the
30rem breakpoint), and reload-restores-position (`localStorage`). Then **open the published URL on
the phone** — Claude app first, then mobile browser. That resolves the mobile row.

Watch specifically for Claude re-authoring the page instead of filling `STEPS`. The template exists
so the card is identical every time and cheap; if it gets rewritten per turn, that has failed and
the rules text needs to say so more plainly.

### Section 5 — the offline guarantee

Open `templates/step-card.html` from disk with wifi off. Pass: fully functional. This is asserted
by `verify.py` textually (no external `src`/`href`/`https://`) but never actually observed, and the
reason for the rule is a machine mid-install with no network.

### Section 6 — the output style is opt-in

`/output-style`. Pass: `handover-cards` is **listed but not active** — that is the un-forced
decision holding. If it is already active, `force-for-plugin` leaked in and `verify.py`'s negative
check has a gap. Then select it and confirm coding behaviour is retained
(`keep-coding-instructions`).

### Section 7 — Claude Code on the web

Same 5-step ask in a cloud session. Resolves the "publishing undocumented; treat as unavailable"
row either way.

### Section 8 — chat surfaces

Paste the block from `docs/claude-ai-instructions.md` into claude.ai → Settings → Instructions, then
a new chat on web and a new chat on the phone. Pass: the same card. Note whether the web chat also
volunteers its own interactive widget — model discretion, so not a failure either way, but worth
recording.

## Deliverable 2 — fold the results back

Update the surface table in `CLAUDE.md` (and the coverage line in `claude-house-rules/README.md`)
to state what was observed, with the plugin version it was observed at. Replace each
"undocumented" / "treat as unavailable" cell with a verified yes or no. A row that stays unverified
gets said so explicitly rather than left ambiguous.

## Deliverable 3 — one `verify.py` check

`docs/desktop-verification.md` exists and names every surface the `CLAUDE.md` table lists. The table
is a claim; this checklist is what substantiates it, and a surface added to the table without a way
to check it is the drift this repo already guards against everywhere else. Follows the existing
`report()` convention; no hardcoded totals.

## Critical files

- `docs/desktop-verification.md` — new
- `CLAUDE.md` — the surface table, after the run
- `claude-house-rules/README.md` — the coverage line, after the run
- `claude-house-rules/plugins/house-rules/scripts/verify.py` — one check, near the chat-block check
- `claude-house-rules/plugins/house-rules/templates/step-card.html` — only if section 4 finds a bug

## Verification

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Exit 0 with the new check passing. The suite cannot confirm the manual results — that is the point
of the checklist — so the run itself is the verification, and section 2b is the one whose failure
would send the design back for rework rather than a fix.
