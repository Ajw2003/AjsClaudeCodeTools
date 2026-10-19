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
| Replies | `handover` (Stop), `_writing_findings`, `_writing_note` | One note listing every finding, with the not-checked and long-reply notes folded in. Since 2.68.1 (#309) the kinds in `_WRITING_REPORT_ONLY` (bare references) are left out of the note and reported to aj in one line instead (`_writing_report_line`), because the bare-reference check misread "the option I suggested". |
| Pages | `artifact` (PostToolUse), `_page_writing_note` | A write to `docs/plans/*.html` runs the checker on what a reader sees: the visible text and a template page's PAGE strings. The report-only kinds are skipped here too. |
| Issues | `guard` (`gh issue create`), `guardgithub` (`issue_write` create) | Refused without "Depends on", "Depended on by" and "Done when". |
| Editor helper | `agents/editor.md` (Sonnet), `_editor_owed` | Rewrites a page or a long reply. The end-of-reply check reminds me when a page was written, or a reply ran to 160 words or more, and no editor ran. |

`HOUSE_RULES_CLEAR_WRITING=off` turns off the reply note, the page check, the issue check and the
editor reminder. The not-checked disclosure stays on: it belongs to Evidence before claims.

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
