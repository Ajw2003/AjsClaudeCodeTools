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
| Stage tracker | `.claude/house-rules-loop.json` in the main checkout (shared by every worktree) | Holds the feature, its stage (Design, Plan, Build, QA, Done), aj's approvals, the issues made during Plan, and a fingerprint of the decisions log. Committed with the branch, so a fresh clone or new cloud session keeps the stage. A legacy `.git/house-rules-loop.json` is still read when the new file is missing; the next write moves it. A Write, Edit, NotebookEdit or shell redirect to the file is refused in every stage: only aj's approval messages move the stage (`HOUSE_RULES_LOOP=off` turns the loop off). |
| Approvals | `scope` (UserPromptSubmit), `_loop_scope_note`, `_loop_apply` | Reads aj's message before the model does. "Design approved: <feature>" → Plan; "Build plan approved: <feature>" → Build; "QA passed: <feature>" → Done and "QA failed: <feature>" → Design, both only from QA; "skip design" → one code edit. A bare "approved" moves nothing and tells the model to ask which. Since 2.68.1 (#307) every approval phrase in one message is applied, in stage order (design, build plan, QA), each with its own note; and a redo after "QA failed" matches the feature QA named even when the stored name is stale. |
| Logged first | `_loop_unlogged` | An approval needs `docs/6-decisions/Decisions.md` to exist (#230). If the log is unchanged since the last approval, the approval still counts and its note asks the model to add the stage's entry before the turn ends; the log mark is not updated, so the next approval checks again (#327). |
| Feature home | `_loop_record_issues`, `autosave` (PostToolUse) | Issues made during Plan, by `gh issue create` or the GitHub tool, are recorded; "Build plan approved" needs two labelled `AjsAgent created this` (#231). Since 2.68.1 (#308) only issues made in the repo named by the checkout's GitHub `origin` count; one made elsewhere gets a note instead. A checkout with no GitHub origin counts every issue, as before. |
| Issue labels | `_loop_labels`, `_loop_wrong` | An issue's label says whose move it is: `in progress` is mine, `needs review` is aj's. Read from GitHub every time (`gh api`, in parallel, 5-second limit); if that fails, from the changes `autosave` recorded (`_loop_record_labels`), and the note says why (#235, #236). Design `docs/plans/label-check.html`, plan `docs/plans/label-check-plan.html`. |
| Label checks | `scope`, `commitgate`, `handover` | "Build plan approved" needs every issue `in progress`. Swapping every issue to `needs review` moves Build to QA and closes code; so does a pull request opening during Build (#267). A QA answer counts only in QA. "QA failed" keeps the issues, and the redo's "Design approved" needs them back to `in progress`. In Build an edit is refused while any label is wrong. The end-of-reply check names wrong labels (#237, #238). |
| QA start and page | `autosave`, `make_page.py` QA mode, `handover` (`qa page` row) | A pull request opening during Build moves the stage to QA (#267); the QA page is built by the page builder and its path stored as `qa_page` (#268); a reply in QA is sent back once until that page is linked (#269). See below. |
| Code lock | `commitgate` (PreToolUse), `_loop_gate` | Refuses Write/Edit/NotebookEdit of source files outside Build. `docs/`, `.claude/` and `.md` files stay open. Holds helpers' edits too. Since 2.68.1 (#309) a shell command that writes files is reported, never refused: the note names the stage and the file, or says the file couldn't be named. |
| Helpers | `subagentrules` (SubagentStart), `_loop_helper_note` | A helper starts knowing the feature, stage and issues, and that it only builds approved steps. The "reads like a go-ahead" guess is off while the loop is on (#232). |
| Long replies | `handover` (Stop), `_long_reply_words`, `_check_page` | A reply of 160 words or more (code blocks not counted), or one offering choices, with no page or picture link gets the page report. Since 2.68.1 the page row reports instead of blocking (#309), and a flagged page stays owed for every later reply to the same message of aj's until one links a page, counted in the page-blocks file (#310). aj's own "no page" lifts it. Before 2.68.1 it blocked up to three times (#226, #282, #283). |
| Page template | `templates/handover-page.html` | The approved four-part page, filled from one PAGE block; an empty part is left out (#233). A New item carries three labelled boxes (What exists today, What this creates, How it impacts you), and any item can carry a file list shown on open, each file once with its parts and line counts (#240, v2). |

"I review" happens inside Build, because fixing what my own review finds is code. aj's review and
test are one QA step with a pass/fail answer.

### Enforced QA stage (built, #264)

Designed in `docs/plans/qa-stage-design.html`, plan `docs/plans/qa-stage-plan.html`, both approved 2026-10-15.

- **QA starts** when a pull request is opened for the feature (`gh pr create` or the GitHub tool's
  `create_pull_request`, seen by `autosave`, #267) or when every issue says `needs review`, whichever comes first.
  Code is closed from that moment.
- **The QA page** is built by `make_page.py build` in QA mode (`qa` block: feature, base, unverified, files). It
  counts each file's added and removed lines from `git diff --numstat <base>...HEAD`, refuses an empty
  unverified list, fixes the reply to "QA passed: <feature>" and records the path as `qa_page` in the stage file (#268).
- **The checkpoint** is a sixth "reply ends" row, `qa page`: in QA a reply is sent back once until `qa_page` is
  set and the page is linked (#269).
- **The stage survives a new session**: the stage file is committed with the branch (#265).

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
