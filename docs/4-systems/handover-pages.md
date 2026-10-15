# Handover pages and checkpoints

Status: **planned, not built.** Design approved 2026-10-15 ("Design approved: handover pages and
checkpoints: 1A 2A 3A 4A 5A 6A 7B 8A"). Design page: `docs/plans/enforced-checkpoints-design.html`. Build plan:
`docs/plans/handover-pages-plan.html`. Decisions: `docs/6-decisions/Decisions.md`, 2026-10-15 entries. Audit that
started it: `docs/handover-page-audit-2026-10-15.md`.

## What it owns

Every plan, design or set of choices reaches aj as a page built the same way. The page carries pictures where the
project needs them, and its look comes from the project. The rules that matter run at fixed points and block
once, so they don't depend on the model choosing to follow them.

## How it will work

| Piece | Where | What it does |
|---|---|---|
| Template | `templates/handover-page.html` | The four parts stay (In short, Changes, Choices, Wrap-up). Each In short step, Changes item and choice option can carry a captioned picture. A Changed item can carry a before-and-after pair: side by side when the screen is wide, and a slider on a phone. |
| Project style | `docs/page-style.json` in each project, optional | Colours, fonts and a `pictures` setting: `required` for art and visual changes, `optional`, or `off`. Without the file the template's own look is used. Orange always means "aj acts" and can't be restyled. |
| Page builder | `scripts/make_page.py` | Takes a page's content and the project's style file, writes the page under `docs/plans/`, copies its pictures beside it, and stamps a builder mark. Refuses an art or visual change with no picture when the project requires pictures. |
| Checkpoint table | `hook.py` | One list: each moment (reply ends, page saved, page published), the rule it runs, and whether a miss blocks or reminds. |
| End-of-reply check | `hook.py`, the `handover` part (Stop) | Blocks once on a miss of the page rule, the editor helper, evidence, commit or plain summary. On the retry (`stop_hook_active`) it only reports, the same safety `subagentcommit` uses. "no page" in aj's own message lets one reply through. |
| Page check | `hook.py`, new PreToolUse entry for `Write` and the Artifact publish tool | Refuses a page under `docs/plans/`, or a published page, that has no builder mark. |
| Rule text | `rules/show-dont-tell.md` | Names the builder's command and the style file, and says the builder overrides the Artifact tool's own page design. |
| Rules after an update | `inject` and `showrule` (SessionStart) | Notice a newer installed version and load its rules, or say they couldn't. |

## Invariants

- A checkpoint blocks at most once per reply. The retry always ends the turn.
- Only aj's own message counts as aj's words. A subagent's hand-back never moves a stage or skips a check.
- `HOUSE_RULES_LOOP=off` turns the whole loop off, these checkpoints included.
