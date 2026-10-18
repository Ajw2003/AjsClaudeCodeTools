# Clear writing check

## What it owns

Making everything aj reads (replies, pages, issues, plans) read as proper English in a human
voice, with nothing left to work out. Rule: `rules/clear-writing.md`, "Write it so nothing is left
to guess", with its detail in `rules/detail/clear-writing.md`. Design `docs/plans/clear-writing-check.html`,
plan `docs/plans/clear-writing-plan.html`. Issue #245. It merged the plain-language rule, the
exact-input and ask-when-unclear lines, and the plain-docs writing limits.

## How it works

| Piece | Where | What it does |
|---|---|---|
| Rule | `showrule` (SessionStart), `rules/clear-writing.md` | Loads after Show, don't tell, in the same slot. The voice section is last, so `HOUSE_RULES_VOICE=off` cuts only it. |
| Shared checker | `scripts/clarity.py` | Vague claims with no reason, bare references, repetition, jargon, long sentences, and the not-checked disclosure. One module for the hook and `plain_docs_check.py`; `python clarity.py [--page] < file` runs it by hand. |
| Replies | `handover` (Stop), `_writing_note` | Chat replies are no longer checked for writing (since #324); the old reply note and the bare-reference report line are gone. Only the not-checked and long-reply notes still go through `_writing_note`. |
| Pages | `artifact` (PostToolUse), `_page_writing_note` | A write to `docs/plans/*.html` runs the checker on what a reader sees: the visible text and a template page's PAGE strings. The report-only kinds are skipped here too. |
| Issues | `guard` (`gh issue create`), `guardgithub` (`issue_write` create) | Refused without "Depends on", "Depended on by" and "Done when". |
| Editor helper | `agents/editor.md` (Sonnet), `_editor_owed` | Rewrites a page or a long reply. The end-of-reply check reminds me when a page was written and no editor ran. A reply of 160 words or more counts too only with `HOUSE_RULES_EDITOR=on` (default off, #325). |

`HOUSE_RULES_CLEAR_WRITING=off` turns off the page check, the issue check and the
editor reminder. The not-checked disclosure stays on: it belongs to Evidence before claims.

## Stop the end-of-reply loop (#322)

Design approved 2026-10-18 ("Design approved: #322 writing check loop"). Built in plugin 2.68.4
(#323 to #326, plus #327 for the design loop); waiting for aj's QA.

**Why.** A Stop hook's `additionalContext` continues the turn, and `handover` emits it on the retry
(`stop_hook_active` true) as well as the first stop. Every report-only note (the page checkpoint, the
label line, the long-reply note) therefore woke the model for another reply, which tripped the same note
again. On 2026-10-18 a cloud session ran until Claude Code's own cap of 9 consecutive blocks ended it,
and the editor checkpoint added a whole subagent run for one 386-word chat reply.

**The four steps, one sub-issue each:**

1. **The retry only reports to aj.** When `stop_hook_active` is true, `event_handover` puts every note
   in `systemMessage` and emits no `additionalContext`, so a retry can never continue the turn.
2. **The writing check leaves chat replies alone.** `_writing_findings` and `_writing_report_line` stop
   running on replies. The page check (`_page_writing_note`) and the issue check stay on, and the
   not-checked disclosure stays, because it belongs to Evidence before claims.
3. **The editor checkpoint is pages-only by default.** `_editor_owed` asks for the editor only when a
   page under `docs/plans/` was written. `HOUSE_RULES_EDITOR=on` brings back the 160-word reply trigger.
4. **The page checkpoint is said once (#326).** The #310 "still owed" note is delivered once per message of
   aj's, not after every later reply to it. The page-blocks count still records that a page is owed.

Each step adds its own `verify.py` case. Step 1's case proves that two Stop runs about the same reply
give no second `additionalContext`.

## Invariants

- A finding names the phrase it found and why; the note never just says "unclear".
- Code blocks, code spans, links and quoted text are never read as prose: a quoted example ("see
  #229" alone) is talked about, not asserted.
- A hedge with a reason in the same sentence passes: "estimated 25 lines, because it isn't written
  yet".
- A missing `clarity.py` is reported by each check that needs it; it never takes the other hooks
  down (`CLARITY_ERROR`).

## Traps that have already cost time

- **A list label read as a confession.** "**Not checked:** vague claims, by any hook" set off the
  not-checked check on 2026-10-15. A phrase followed by a colon is now a label.
- **False alarms on real replies.** Calibrated on this session's 93 long replies. Before tuning:
  quoted titles after a number (`#228, "Audit…"`), step cards ("Step 1 of 3") and parallel list
  items were flagged. After: the hits left (vague numbers that could have been counted, bare
  "choice 5") are the failures the rule exists for.
- **Test fixtures sit in a temp folder**, which the page hook treats as outside the project; the
  page check now runs before the location check.
