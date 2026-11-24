# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | 1 (#593) | The editor's wording rules "move into the reviewer file". | The reviewer's page mode points to the editor's rules in `agents/editor.md` instead of copying them. | The editor stays for long replies (design page, "What stays the same"), so a copy would drift. The test limits an agent body to 15 lines. | Copy the five wording bullets from `agents/editor.md` into `agents/reviewer.md` and trim other lines to fit. |
| D2 | all | Multi-file work uses an isolated worktree (house rule). | Steps are built one at a time on this branch, with no worktree. | Only one builder runs at once, so nothing edits the same files at the same time, and a worktree would add a merge per step. | Rebuild a step in a worktree from its commit. |
| D3 | 3 (#595) | The acceptance stamp is "for the current commit". | The stamp is tied to a fingerprint of the source tree with `docs/qa/` left out. | The reviewer's own report is committed under `docs/qa/<feature>/`, which would make a stamp bound to the commit stale at once and block the QA page. Found by the reviewer's first real run (finding 3). | Bind the stamp to the commit and write the report outside the committed tree. |
| D4 | 1 (#593) | The reviewer may write "under docs/". | It may write only under `docs/qa/<feature>/`. This is a written rule: the agent also has Bash, so nothing technical stops a write elsewhere. | Narrower is safer, and the mode file already said so (finding 4). | Widen the sentence in `agents/reviewer.md` and `rules/detail/review-modes.md`. |
| D5 | 3 (#595) | A hook records the acceptance stamp in the stage file. | A script, `scripts/acceptance.py stamp <feature>`, writes `docs/qa/<feature>/acceptance-stamp.json` after checking the report has no FAIL. | The stage file refuses every hand write or shell write by design (only aj's messages move a stage), and routing around that for a stamp would add plumbing, not safety. | Add a hook that writes the stamp into the stage file, and have the QA gate read it from there. |
| D6 | 2 (#594) | The stamp is checked for pages "written or changed this turn" (existing detection). | Same. A page that was reviewed but not rebuilt with `--reviewed` is flagged. The page `2026-11-24-design-review-loop-plan.html` and the design page were built before the stamp existed and carry none. | The check only looks at pages changed in the turn, so old pages are not flagged until edited. | Stamp them by rebuilding with `--reviewed` after a reviewer run. |

## Parked decisions

| # | Step | Question | Default taken for now | What it affects | How to answer |
|---|---|---|---|---|---|
| P1 | 8 (#600) | The design says one reply approves design and plan, but the approval reader already accepts two phrases in one message (design-loop.md, Approvals row, since 2.68.1). Add a new single phrase (a fifth reversal), or reuse the two-phrase rule? | Reuse the two-phrase rule: no stage-machine change, no fifth reversal (the reviewer's suggestion A). Step 8 is not started, so nothing depends on this yet. | Step 8 only. | Reply "P1: B" to get a single new phrase instead. |
| P2 | 2 and 3 | Round caps: two review rounds apply to design and plan pages (choice 3A); four apply to the acceptance run (the visual loop's existing limit). The page left it unclear whether 3A also changes the four. | Two for pages, four for the acceptance run. | The wording of the systems doc only. | Reply "P2: two everywhere" or similar. |
