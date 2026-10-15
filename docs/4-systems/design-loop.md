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
| Stage tracker | `.git/house-rules-loop.json` | Holds the feature, its stage (Design, Plan, Build, QA, Done), aj's approvals, the issues made during Plan, and a fingerprint of the decisions log. Never committed. Carries across sessions. |
| Approvals | `scope` (UserPromptSubmit), `_loop_scope_note` | Reads aj's message before the model does. "Design approved: <feature>" → Plan; "Build plan approved: <feature>" → Build; "QA passed: <feature>" → Done and "QA failed: <feature>" → Design, both only from QA; "skip design" → one code edit. A bare "approved" moves nothing and tells the model to ask which. |
| Logged first | `_loop_unlogged` | An approval only counts when `docs/6-decisions/Decisions.md` exists and changed since the last approval (#230). |
| Feature home | `_loop_record_issues`, `autosave` (PostToolUse) | Issues made during Plan, by `gh issue create` or the GitHub tool, are recorded; "Build plan approved" needs two labelled `AjsAgent created this` (#231). |
| Issue labels | `_loop_labels`, `_loop_wrong` | An issue's label says whose move it is: `in progress` is mine, `needs review` is aj's. Read from GitHub every time (`gh api`, in parallel, 5-second limit); if that fails, from the changes `autosave` recorded (`_loop_record_labels`), and the note says why (#235, #236). Design `docs/plans/label-check.html`, plan `docs/plans/label-check-plan.html`. |
| Label checks | `scope`, `commitgate`, `handover` | "Build plan approved" needs every issue `in progress`. Swapping every issue to `needs review` moves Build to QA and closes code. A QA answer counts only in QA. "QA failed" keeps the issues, and the redo's "Design approved" needs them back to `in progress`. In Build an edit is refused while any label is wrong. The end-of-reply check names wrong labels (#237, #238). |
| Code lock | `commitgate` (PreToolUse), `_loop_gate` | Refuses Write/Edit/NotebookEdit of source files outside Build. `docs/`, `.claude/` and `.md` files stay open. Holds helpers' edits too. |
| Helpers | `subagentrules` (SubagentStart), `_loop_helper_note` | A helper starts knowing the feature, stage and issues, and that it only builds approved steps. The "reads like a go-ahead" guess is off while the loop is on (#232). |
| Long replies | `handover` (Stop), `_long_reply_words` | A reply over 200 words (code blocks not counted) with no page or picture link gets a reminder (#226). |
| Page template | `templates/handover-page.html` | The approved four-part page, filled from one PAGE block; an empty part is left out (#233). A New item carries three labelled boxes (What exists today, What this creates, How it impacts you), and any item can carry a file list shown on open, each file once with its parts and line counts (#240, v2). |

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

- **A feature name ran on past a dash.** "QA failed: label check - it should say hi" saved the
  whole line as the name; a spaced dash now ends it (found in the label check's real run).
- **The end-of-reply check goes quiet when nothing else fires.** A new reminder added only to the
  list of notes never appears; it has to be counted before the quiet exit (found building #226).
- **Issues made in cloud sessions were invisible.** The issue record only matched a terminal
  `gh issue create`; cloud sessions use the GitHub tool (aj chose to record both, #231).
- **Writing the tracker on every message** gave a fresh project a file on a bare "approved"; the
  write now happens only on a real change.
