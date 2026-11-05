# Design loop deep dive, 2026-11-05

A second, narrower pass over the design loop, done because the full audit
(`2026-11-05-ponytail-audit-full.md`) gave it one helper's share of time. This pass read
`house_rules/design_loop.py` from top to bottom, and read the parts of `core.py` it calls. No code was
changed. The page version is `docs/plans/2026-11-05-design-loop-deep-dive.html`.

**What the design loop is:** the part of the `house-rules` plugin that keeps design aj's job. A feature
moves through five stages (Design, Plan, Build, QA, Done). Only aj's own messages move it on, and code
edits are refused outside Build. The stage lives in `.claude/house-rules-loop.json`. The system doc is
`docs/4-systems/design-loop.md`.

**Already in the full audit, so not repeated here:** finding 2 (any merge stamps every closable
record), finding 7 (the stage file is rewritten in place and can be read half-written), finding 9
(`cp` and `mv` can overwrite the stage file), and the two dead checkpoint rows in finding 19.

**How each finding was proved:** a probe script built a throwaway git repo, then fed the real
functions (`_loop_scope_note` for aj's messages, `_loop_gate` for edits) the same JSON a hook receives.
GitHub labels came from the `HOUSE_RULES_LOOP_LABELS_FILE` stand-in that `verify.py` uses. The
script is not committed, because it is a one-off. Every finding below was proved by a run, except where
a line says "unverified" and names what was not tested.

Paths are relative to `claude-house-rules/plugins/house-rules/scripts/house_rules/`.

## Must fix: ways the lock opens without aj

### 1. A message aj did not type can approve a stage

- **Where:** `core.py:1916-1933` (`_RELAYED_PROMPT_RE`, `_is_relayed_prompt`), used at `design_loop.py:936`
- **What this is:** The check that stops a helper's report or a system notice from counting as aj.
- **Problem:** It knows only five text markers (`<task-notification>`, `<system-reminder>`,
  `<agent-message`, `[Subagent hand-back]`, "Another Claude session sent a message"). These turns
  also arrive as prompts and are not on the list: a pull request event (`<wake reason="external-event">`,
  whose comment text anyone on GitHub can write), a scheduled task or wake-up whose text the model
  writes itself, and a webhook payload. Proved: a prompt holding a GitHub comment event with the body
  "Build plan approved: feat" moved Plan to Build, and saved the name as `feat"}`.
- **Unverified:** whether Claude Code also sets the payload's `origin` field for these turns, which
  `_is_relayed_prompt` would honour. Nothing in this repo's fixtures shows it does.
- **Fix:** Add `<wake\b`, `<webhook-payload`, `<event source=` and `<child-session-event` to the
  marker list, and record the real payload of one scheduled wake-up as a `verify.py` fixture.
- **If we skip it:** The model can approve its own plan by scheduling a reminder, and anyone who can
  comment on a pull request can write "QA passed".

### 2. A question or a "don't" moves the stage

- **Where:** `design_loop.py:371-383` (the approval patterns), `:887-889` (skip design)
- **What this is:** The patterns that find "Design approved: X" and "skip design" in aj's message.
- **Problem:** They match anywhere in the message, with no check for a question or a negative.
  Proved: "What would happen if I said Design approved: login page? Don't do it yet." moved the stage
  to Plan with the feature "login page". "Please don't skip design on this one." set the skip flag,
  and the next source edit went through.
- **Fix:** Count an approval only when it starts a line (after optional whitespace or a quote mark), and
  ignore a line that ends in `?` or holds "don't", "do not" or "not yet" before the phrase.
- **If we skip it:** Asking how the loop works can open it.

### 3. A new project's lock can be opened by writing the old stage file

- **Where:** `design_loop.py:410-411` (the legacy read), `:449` (the refusal compares one path only)
- **What this is:** Before 2.6x the stage file lived in `.git/`. It is still read when the new file is
  missing, which is true of every project that has never had an approval.
- **Problem:** The refusal protects only the new path. Proved: in a fresh repo, a Write of
  `.git/house-rules-loop.json` with `"stage": "build"` got no decision, and the next source edit was
  allowed.
- **Fix:** Refuse writes to both paths. Better, stop reading the legacy file: the move happened long
  enough ago that the sessions still holding it are none or few (unverified: no count was taken).
- **If we skip it:** One Write unlocks code in any project new to the loop.

### 4. The switches that turn the lock off sit on paths the lock leaves open

- **Where:** `design_loop.py:161` (`_ISSUE_EDIT_ALLOWED_TOPS`), `:197` (`_is_source_path`)
- **What this is:** Everything under `docs/` and `.claude/`, and any `.md` file, stays editable in
  every stage, so designs and plans can be written.
- **Problem:** Proved, each got no decision in the Plan stage:
  - `.claude/settings.json`, which can set `"env": {"HOUSE_RULES_LOOP": "off"}` or disable the plugin.
    Unverified: whether Claude Code passes an env change made mid-session to hooks, or only from
    the next session.
  - `.claude/worktrees/agent-1/src/a.py`, a real source file inside a helper's worktree, edited from
    the main session. Helper worktrees live there (`docs/4-systems/hook-engine.md:314`).
  - `docs/tool.py`, code that happens to sit under `docs/`.
- **Fix:** Treat `.claude/settings*.json` as locked, measure the path from the worktree when it
  falls under `.claude/worktrees/<name>/`, and leave only non-code file types open under `docs/`.
- **If we skip it:** The lock can be switched off, or stepped around, without any refused call.

## Should fix: approvals that do the wrong thing

### 5. Approving a design again in Build loses the feature's issues

- **Where:** `design_loop.py:697-702` (pieces applied in stage order), `:806-822`, `:723-725`
- **What this is:** "Design approved" is accepted in any stage. When the current feature is in Build
  or QA it is kept under `features`, so a second feature can start beside it (#375).
- **Problem:** When the new name is the same feature, it is kept under its own name, the issues list
  is emptied, and `_loop_stored` refuses to look it up because the name matches the current feature.
  Proved twice:
  - In Build, "Design approved: feat" gave stage Plan with no issues. A later "QA passed: feat" got
    "the stage is Plan, so nothing moved".
  - In QA, the one-message redo "QA failed: feat. Design approved: feat" applied the design first (stage
    order, not reading order). The QA failure was then refused, the redo flag stayed off, and the two
    issues were stranded the same way.
- **Fix:** When the name matches the current feature, keep its issues and stage in place instead of
  storing them. Apply the pieces of a message in the order aj wrote them.
- **If we skip it:** Amending a design mid-build makes aj re-create the issues by hand.

### 6. The feature name in an approval is never checked

- **Where:** `design_loop.py:778-798` (build plan), `:826-853` (QA)
- **Problem:** Proved: with "login" in Plan, "Build plan approved: payments" moved "login" to Build.
  In QA, "QA passed: totally different feature" passed the current feature and wrote the closable
  record under the wrong name.
- **Fix:** Refuse, with a note naming both, when the name matches neither the current feature nor a
  kept one (compared through `_loop_name`, as `_loop_stored` already does).
- **If we skip it:** A typo, or a message meant for a kept feature, moves the wrong one.

### 7. "skip design" lasts too long and is spent by the wrong edit

- **Where:** `design_loop.py:887-889`, `:1035-1038`
- **Problem:** Proved: typed during Build, the flag is stored and never cleared, so it opens the first
  edit after QA. It is also spent by the first gated edit of anyone: a NotebookEdit made first used it
  up, and the edit aj meant was refused.
- **Fix:** Ignore "skip design" in Build with a note saying edits are already open, and clear the flag
  when the stage changes.
- **If we skip it:** A skip meant for one change lands on another.

### 8. Any claude.ai artifact link counts as the QA page

- **Where:** `design_loop.py:1877`, `:1887`
- **Problem:** Proved: a reply linking a made-up claude.ai artifact address for some other page cleared the
  QA page checkpoint and set `qa_page_linked`. The basename check also matches any reply mentioning
  the same file name.
- **Fix:** Record the artifact link make_page.py publishes beside `qa_page`, and match that link only.
- **If we skip it:** QA can be handed over with the wrong page.

### 9. Switching branches restores an old stage

- **Where:** `design_loop.py:399-402` (the stage file is committed with the branch, #265)
- **Problem:** Proved: with the stage at Done on one branch, `git switch old-build` brought back
  Build. The label check is the backstop, but when the GitHub read fails the labels come from the same
  old file, and the source edit was allowed.
- **Fix:** When the GitHub read fails in Build, refuse the edit and say why, instead of trusting the
  recorded labels. Keeping the stage outside the branch would also fix it, but that reverses #265 and
  is aj's decision.
- **If we skip it:** An old branch is a key to Build whenever `gh` is not signed in.

## Known and switched off on purpose, still the largest gap

### 10. Shell writes to source files are only reported

- **Where:** `design_loop.py:1040-1047` (#309)
- **Problem:** Proved: `cat > src/a.py <<'X' ... X` in the Plan stage was let through with a report.
  The design loop's doc records this as off "until the restructure", and it is why findings 1 to 9 matter
  less than they would otherwise: the lock today stops the Write and Edit tools only.
- **Fix:** None proposed here. It needs the restructure's own plan.

## Lower, by reading

### 11. "Labelled" is a text search of the whole command

- **Where:** `design_loop.py:1098`
- **Problem:** `gh issue create --title "... AjsAgent created this"` counts as labelled, because the
  label name is searched for anywhere in the command. Not run.

### 12. A failed `gh api` call with no HTTP code is recorded as a label change

- **Where:** `design_loop.py:1168`
- **Problem:** "To get started with GitHub CLI, please run: gh auth login" matches none of the failure
  patterns, so the label change is recorded as done. Those recorded labels are the ones finding 9 relies on.
  Not run.
