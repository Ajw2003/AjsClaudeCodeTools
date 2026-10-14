# Design loop

## What it owns

Keeping design aj's job. Every feature moves through stages, and only aj's own message moves it on.
Code can only change once aj has approved a design and the plan to build it. Designs:
`docs/plans/loop-design.html` (the loop), `docs/plans/handover-format.html` (the pages it hands over).
Rule: `rules/show-dont-tell.md`, detail in `rules/detail/show-dont-tell.md`. Issue #223.

## How it works

| Piece | Where | What it does |
|---|---|---|
| Rule | `showrule` (SessionStart), `rules/show-dont-tell.md` | Loads the rule every session in its own slot: `house-rules.md` had 47 characters of room left. |
| Stage tracker | `.git/house-rules-loop.json` | Holds the feature, its stage (Design, Plan, Build, Done), aj's approvals, the issues made during Plan, and a fingerprint of the decisions log. Never committed. Carries across sessions. |
| Approvals | `scope` (UserPromptSubmit), `_loop_scope_note` | Reads aj's message before the model does. "Design approved: <feature>" → Plan; "Build plan approved: <feature>" → Build; "QA passed: <feature>" → Done; "QA failed: <feature>" → Design; "skip design" → one code edit. A bare "approved" moves nothing and tells the model to ask which. |
| Logged first | `_loop_unlogged` | An approval only counts when `docs/6-decisions/Decisions.md` exists and changed since the last approval (#230). |
| Feature home | `_loop_record_issues`, `autosave` (PostToolUse) | Issues made during Plan, by `gh issue create` or the GitHub tool, are recorded; "Build plan approved" needs two labelled `AjsAgent created this` (#231). |
| Issue labels | by hand, on GitHub | `in progress` while worked on; swapped for `needs review` at aj's QA. aj closes it, or asks for changes and it goes back to `in progress`. No hook checks this yet; the label check (#235, design `docs/plans/label-check.html`, plan `docs/plans/label-check-plan.html`) is being built to check it at every step. |
| Code lock | `commitgate` (PreToolUse), `_loop_gate` | Refuses Write/Edit/NotebookEdit of source files outside Build. `docs/`, `.claude/` and `.md` files stay open. Holds helpers' edits too. |
| Helpers | `subagentrules` (SubagentStart), `_loop_helper_note` | A helper starts knowing the feature, stage and issues, and that it only builds approved steps. The "reads like a go-ahead" guess is off while the loop is on (#232). |
| Long replies | `handover` (Stop), `_long_reply_words` | A reply over 200 words (code blocks not counted) with no page or picture link gets a reminder (#226). |
| Page template | `templates/handover-page.html` | The approved four-part page, filled from one PAGE block; an empty part is left out (#233). |

"I review" happens inside Build, because fixing what my own review finds is code. aj's review and
test are one QA step with a pass/fail answer.

## Invariants

- Only aj's message moves the stage. `scope` reads the prompt itself, so the model cannot approve
  on aj's behalf.
- The tracker file is written only when the stage, approvals, issues or skip flag actually change.
- Every failure is loud: an unreadable tracker turns the lock off for that call and says so.
- `HOUSE_RULES_LOOP=off` turns off the lock, the approvals, the helper note and the long-reply
  reminder together, and restores the go-ahead guess.
- `verify.py` runs with the loop off (its fixtures edit files freely) and switches it on for its own
  "design loop:" cases.

## Traps that have already cost time

- **The end-of-reply check goes quiet when nothing else fires.** A new reminder added only to the
  list of notes never appears; it has to be counted before the quiet exit (found building #226).
- **Issues made in cloud sessions were invisible.** The issue record only matched a terminal
  `gh issue create`; cloud sessions use the GitHub tool (aj chose to record both, #231).
- **Writing the tracker on every message** gave a fresh project a file on a bare "approved"; the
  write now happens only on a real change.
