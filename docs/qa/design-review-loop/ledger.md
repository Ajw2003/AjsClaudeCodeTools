# Design review loop: deviations and parked decisions

Every change from the approved build plan, and every question parked instead of asked. Each row says what the plan said, what was done, why, and how to undo it. aj reviews this on the QA page.

## Deviations

| # | Step | The plan said | What was done | Why | How to undo |
|---|---|---|---|---|---|
| D1 | 1 (#593) | The editor's wording rules "move into the reviewer file". | The reviewer's page mode points to the editor's rules in `agents/editor.md` instead of copying them. | The editor stays for long replies (design page, "What stays the same"), so a copy would drift. The test limits an agent body to 15 lines. | Copy the five wording bullets from `agents/editor.md` into `agents/reviewer.md` and trim other lines to fit. |
| D2 | all | Multi-file work uses an isolated worktree (house rule). | Steps are built one at a time on this branch, with no worktree. | Only one builder runs at once, so nothing edits the same files at the same time, and a worktree would add a merge per step. | Rebuild a step in a worktree from its commit. |

## Parked decisions

None yet.
