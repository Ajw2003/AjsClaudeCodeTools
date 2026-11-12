# Design loop

## What it owns

Keeping design aj's job. Every feature moves through stages, and only aj's own message moves it on.
Code can only change once aj has approved a design and the plan to build it. Designs:
`docs/plans/loop-design.html` (the loop), `docs/plans/handover-format.html` (the pages it hands over).
Rule: `rules/show-dont-tell.md`, detail in `rules/detail/show-dont-tell.md`. Issue #223.

**Changed in 2.80.0 (speed switches, #525):** aj's approval always moves the stage. What a refusal
below used to send back to aj (too few issues, wrong labels, no log entry, a different feature name)
is now a to-do for the agent in the same turn; only an unknown feature name and a QA verdict before
any build still move nothing. The loop can be switched off per repo by typing "design loop off"
on its own line. See `speed-switches.md`.

## How it works

| Piece | Where | What it does |
|---|---|---|
| Rule | `showrule` (SessionStart), `rules/show-dont-tell.md` | Loads the rule every session in its own slot: `house-rules.md` had 47 characters of room left. |
| Stage tracker | `.claude/house-rules-loop.json` in the main checkout (shared by every worktree) | Holds the feature, its stage (Design, Plan, Build, QA, Done), aj's approvals, the issues made during Plan, and a fingerprint of the decisions log. Committed with the branch, so a fresh clone or new cloud session keeps the stage. The old `.git/house-rules-loop.json` is no longer read, so writing it opens nothing (D3, #505). The newest approval this clone has seen is kept in `house-rules-loop-seen.json` in the common git folder: on a branch whose own newest approval is older, code edits wait for "Continue from: <branch>" or a new approval (D9, #505). On the default branch a stage file in QA reads as Done, without being written, because the feature's pull request merged (U3, #505). A Write, Edit, NotebookEdit or shell redirect to the file is refused in every stage: only aj's approval messages move the stage (`HOUSE_RULES_LOOP=off` turns the loop off). |
| Approvals | `scope` (UserPromptSubmit), `_loop_scope_note`, `_loop_apply` | Reads aj's message before the model does. "Design approved: <feature>" → Plan; "Build plan approved: <feature>" → Build; "QA passed: <feature>" → Done and "QA failed: <feature> <what's wrong>" → Build with the issues kept (#504), both only from QA; "skip design" → one code edit. A bare "approved" moves nothing and tells the model to ask which. Since 2.68.1 (#307) every approval phrase in one message is applied, in stage order (design, build plan, QA), each with its own note; and a redo after "QA failed" matches the feature QA named even when the stored name is stale. Two more phrases, also only from aj's own message and never from a relayed one (#479): "Continue from: <branch>" copies that branch's stage file from origin (stage, approvals, issues), so a handoff keeps what aj already approved, and moves nothing when the branch has no readable stage file; "Issues for <feature>: #N #M" records issues that already exist (made by a script or another session) for the feature in Plan, and cannot move a stage. Each approval note also tells the model to commit and push the stage file straight away, because the approval is only on this disk until then; the hook itself does not push. Since phase 1 (#501, #502): the stage words may follow the feature name ("Phase 1 design approved 1A", `_loop_normalise`); a leading cloud `<system-reminder>` block is set aside unless it carries a relayed message (`_own_words` in `core.py`); a "don't" or "not" before any approval stops it; picks with no stage words get a note; an approval sent from outside a repo is never silent; and a bare "Approve" plus picks is read as the one approval line the last reply offered (`offered`, recorded at the end of each reply), or moves nothing and says why. A design approval with a different name starts a new feature and keeps the old one with its issues, in any stage (D6, #505). |
| Logged first | `_loop_unlogged` | An approval needs `docs/6-decisions/Decisions.md` to exist (#230). If the log is unchanged since the last approval, the approval still counts and its note asks the model to add the stage's entry before the turn ends; the log mark is not updated, so the next approval checks again (#327). |
| Feature home | `_loop_record_issues`, `autosave` (PostToolUse) | Issues made during Plan, by `gh issue create` or the GitHub tool, are recorded; "Build plan approved" needs two labelled `AjsAgent created this` (#231). Since 2.68.1 (#308) only issues made in the repo named by the checkout's GitHub `origin` count; one made elsewhere gets a note instead. A checkout with no GitHub origin counts every issue, as before. Since #503 a step issue counts only when its body says "Part of #N"; the first one sets the feature issue (`parent`). "Build plan approved" reads the feature issue and every open issue naming it from GitHub's REST issue list (`_loop_feature_issues`; not `gh issue list`, whose GraphQL calls cloud sessions refuse), merged with the recorded ones, and falls back to the recorded issues with a note when GitHub can't be read. |
| Issue labels | `_loop_labels`, `_loop_wrong` | An issue's label says whose move it is: `in progress` is mine, `needs review` is aj's. Read from GitHub every time (`gh api`, in parallel, 5-second limit); if that fails, from the changes `autosave` recorded (`_loop_record_labels`), and the note says why (#235, #236). Design `docs/plans/label-check.html`, plan `docs/plans/label-check-plan.html`. |
| Label checks | `scope`, `commitgate`, `handover` | "Build plan approved" needs every issue `in progress`. Swapping every issue to `needs review` moves Build to QA and closes code; so does a pull request opening during Build (#267). A QA answer counts only in QA. "QA failed" sends the feature back to Build with its issues kept; code opens once they are back to `in progress`, and the stage does not bounce straight back to QA while they still say `needs review` (`reopened`, #504). A changed design still needs "Design approved", which also needs them back to `in progress`. In Build an edit is refused while any label is wrong. The end-of-reply check names wrong labels (#237, #238). |
| QA start and page | `autosave`, `make_page.py` QA mode, `handover` (`qa page` row) | A pull request opening during Build moves the stage to QA (#267); the QA page is built by the page builder and its path stored as `qa_page` (#268); a reply in QA is sent back once until that page is linked (#269). See below. |
| Code lock | `commitgate` (PreToolUse), `_loop_gate` | Refuses Write/Edit/NotebookEdit of source files outside Build. `docs/`, `.claude/` and `.md` files stay open. Holds helpers' edits too. In Build, a reply whose last paragraph asks aj a question holds code edits until aj's next real message (`held`, #506). Since 2.68.1 (#309) a shell command that writes files is reported, never refused: the note names the stage and the file, or says the file couldn't be named. |
| Helpers | `subagentrules` (SubagentStart), `_loop_helper_note` | A helper starts knowing the feature, stage and issues, and that it only builds approved steps; anything unexpected is a question for aj, which the main session puts on a page and does not answer (#506). The "reads like a go-ahead" guess is off while the loop is on (#232). |
| Long replies | `handover` (Stop), `_long_reply_words`, `_check_page` | A reply of 160 words or more (code blocks not counted), or one offering choices, with no page or picture link gets the page report. Since 2.68.1 the page row reports instead of blocking (#309), and a flagged page stays owed for every later reply to the same message of aj's until one links a page, counted in the page-blocks file (#310). aj's own "no page" lifts it. Before 2.68.1 it blocked up to three times (#226, #282, #283). The `decided for you` row sends a reply back once when it settles a design point itself ("I went with", "I chose"; #506). |
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

- **An approval sent from the folder above the repo moved nothing, silently.** A cloud session sits in
  the folder that holds its cloned repos, which is not a repo, so `_loop_scope_note` found no stage
  file and returned nothing while the edit lock (which works from the edited file's path) still refused.
  aj's two approvals for QA evidence by change type (#389) were lost this way on 2026-10-27.
  `_loop_locate_prompt` now tries the folders directly inside: exactly one with a stage file gets the
  message, two or more get a note naming them, and none gets a note naming the folder searched
  (approved as "Design approved: missed approvals fix 1A").
- **A feature name ran on past a dash.** "QA failed: label check - it should say hi" saved the
  whole line as the name; a spaced dash now ends it (found in the label check's real run).
- **The end-of-reply check goes quiet when nothing else fires.** A new reminder added only to the
  list of notes never appears; it has to be counted before the quiet exit (found building #226).
- **Issues made in cloud sessions were invisible.** The issue record only matched a terminal
  `gh issue create`; cloud sessions use the GitHub tool (aj chose to record both, #231).
- **Writing the tracker on every message** gave a fresh project a file on a bare "approved"; the
  write now happens only on a real change.

## Approvals in natural word order (2026-11-09, "Handoff overwrite" 3A; built in phase 1 step 1, #501)

The loop accepted only the stage words first ("Design approved: <feature>"). It also accepts them after the
feature name ("<feature> design approved <picks>", "<feature> build plan approved", "<feature> QA passed"), with
the same rules as before: not inside a question, not quoted from another message. aj's three approvals of
2026-11-09 that moved nothing ("Handoff overwrite design approved 1A" among them) become `verify.py` cases.

## Phase 1, approvals just work (2026-11-10, "Phase 1" 1A 2A 3A; built 2026-11-11, plugin 2.78.0)

Issue #493; page `docs/plans/2026-11-10-phase-1-approvals.html`. Seven build steps, one sub-issue each, all in
`scripts/house_rules/design_loop.py` unless named, built one after another because they share that file:

1. **Matching.** The stage words may follow the feature name ("Phase 1 design approved 1A"). A leading
   `<system-reminder>` block is stripped before matching, unless it carries a relayed-message marker (cloud
   sessions, #429). A "don't" or "not" before any approval stops it (D2). Outside a repo the note names the folder
   searched and says to open the repo (#296).
2. **Lines and buttons.** `make_page.py check_approval` refuses a design or build plan page whose copy-box line the
   loop would reject. The end-of-reply check records the approval lines a reply offered; aj's next message, when it
   is exactly "Approve" plus optional picks and that reply offered exactly one line, is read as that line (2A).
3. **The feature's issues.** The feature issue is the one the others name in "Part of #N". "Build plan approved"
   reads open issues with "Part of #N" in their body from GitHub, plus #N itself; an issue that names no part of
   the feature no longer counts (1A, #475).
4. **One-message QA fix.** "QA failed: <feature> <what's wrong>" moves the stage to Build with the issues kept, not
   to Design; the agent moves the labels back to `in progress`.
5. **Lock gaps.** D3 (the old `.git` stage file is not read), D6 (a new design name is checked first), D9 (a branch
   switch does not bring back that branch's stage), U3 (a merged feature leaves no QA stage on `main`).
6. **Decisions only from aj** (#458, #459, #460): no judgement-call exception in the rules, helper questions go to
   aj, a question asked in Build holds code edits until aj answers, and a reply that settles a design point alone
   is sent back once.
7. **Issues follow the work, and proof.** After "QA passed" and a merge the reply offers the close line (#132,
   #141); the label line is said once per set of labels (#273). `verify.py` cases for the eight findings already
   fixed, for #107, #110 and #128, and for #102, #129 and #130 (3A); then this doc's "How it works" is updated and
   the QA page is built.
