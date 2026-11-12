# Issue triage, 2026-11-09

Every issue open on `Ajw2003/AjsClaudeCodeTools` on 2026-11-09 (226), exported with `gh issue list` into
`open-issues-2026-11-09.json`, split into `open-issues-part-a.json` (#41 to #302) and `open-issues-part-b.json`
(#304 to #491), and judged by two read-only scouts that searched the code for each claim. Their verdicts, with
corrections after checking, are in `triage-part-a.md` and `triage-part-b.md`. The roadmap built from them is
`docs/plans/2026-11-09-roadmap.html`.

## Themes

- T1 approvals and design-loop stage moves register reliably
- T2 design loop flow and the code lock
- T3 command guard and safety refusals
- T4 pages and the page builder
- T5 testing on real surfaces (branch installs, desktop app, cloud, clean install, verify.py reliability)
- T6 session handoff and continuity across accounts
- T7 attribution and credit
- T8 visibility of helpers, cloud and background work
- T9 plugin structure and performance
- T10 docs and changelog
- T11 permission prompts and timers
- T12 builder and helper agent behaviour
- T13 other products (art-pipeline, Eldritch goose, Focus Deck, Unity workflow)

## Verdicts

- KEEP: still needed and not built (145)
- UNSURE: the scout could not tell; the phase that carries it checks first (37)
- DONE: built, with the file and line that shows it (21)
- DONE on branch: built on `AjsAgent/session-handoff`, not yet merged (6)
- DUP #M: the same work as #M (10)
- SUPERSEDED #M: replaced by #M (7)

A DONE verdict rests on reading the code, not on running it.
