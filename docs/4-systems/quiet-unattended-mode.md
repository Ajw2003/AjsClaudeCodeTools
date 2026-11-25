# Quiet unattended mode

## What it owns

Making a run with nobody present (unattended, bypass) carry the design loop from goal to QA by itself: it decides, logs every decision, works a guarded list of steps, and cannot stop part-way. Also the shared parts that cut aj's decisions in every mode, auto included.

**Status: built (plugin 2.95.0), live headless run pending (#644).** Steps #638, #636, #637, #639, #646, #647, #640, #641, #642, #648, #649, #643, #635 and #645 are merged and their suites pass; what is built is listed in "What was built" below. The design status line that follows is the original, kept for the record.

**Original status: designed, not built.** aj approved the design on 2026-11-25 as "Design approved: quiet unattended mode 1A" on `docs/plans/2026-11-25-quiet-unattended-mode.html`. The page had three review rounds (45 holes, then 38 more); the stamp reads open risks, round 2, and the last four edits (look or function decided when nobody is present, auto stays attended, bypass counts as unattended, the finish line) were not re-reviewed.

## Who counts as present

| Mode | Loop gates | Look or function choices | Self-approval |
|---|---|---|---|
| Unattended, bypass | Run alone to QA | Decided with a stated assumption | Yes, by a hook |
| Auto | Still gate every step | Asked | No |
| Normal | Gate every step | Asked | No |

In every mode: ask only about look or function; decide and log the rest; the step check blocks a stop while a step is open; decisions are shown only on the QA page; a hard stop (licence, login, purchase, deletion, money, secrets, other people, outward posts) marks its own step and the rest carries on.

## How it will work

1. **Rule text.** Every line that tells me to ask, wait or hand over is rewritten (`rules/show-dont-tell.md:5,11,12`, `rules/house-rules.md:91`, `rules/detail/clear-writing.md:59-62`, `rules/detail/handover-command.md`, `rules/detail/commit-branches.md:50`, `rules/standards/coding-philosophy.md:58`, `agents/builder.md`, and the scope reminder `scripts/house_rules/core.py:1610`).
2. **One presence test.** A single helper in `core.py` replaces the separate unattended and bypass tests (`core.py:1487, 2794, 3840`, `safe_git.py:1375, 1638, 1935`, `bigfiles.py:150`, `design_loop.py:3555`). When nobody is present a permission prompt is denied at once, a plan-exit prompt is allowed, pause-goal is denied, and agent writes to `.claude/house-rules-mode.json` or to `HOUSE_RULES_` keys in `.claude/settings*.json` are refused.
3. **Loop stays on.** `unattended on` no longer turns the design loop off (`core.py:2723, 2850`). The end-of-reply check returns for evidence, commit, deviation, QA page, changelog and decision log only. The holds, label and GitHub gates are skipped when nobody is present (`design_loop.py:1401, 1524-1567`).
4. **Ledger.** `ledger_note.py` gains `decide` (row type K, choice, with an Assumption column; self-approvals are S rows; C stays for acceptance criteria) and `check <step> --start|--poll`, and `park` needs a hard-stop `--category` and `--tried`. `deviate` may add or replace a step, never delete one or touch the finish line. `make_page.py` shows C rows and auto-approvals first with why and how to undo; the ledger folder for a branch name replaces `/` with `-`.
5. **Step list and finish line.** On approval a hook copies the steps from the reviewed build plan into the stage file, with a hash kept inside the repo and a second copy outside it, under the hook payload's `session_id`, in any mode. A step is done when its `ledger_note.py check` (a start call, then polls that each return inside 60 seconds and end with a `RESULT:` line, because the wait guard refuses longer calls) reports a pass in a normal Bash call and a hook records the exit code and the `acceptance.py tree` fingerprint (stale only when that fingerprint changes, so autosave commits do not undo it). Every list ends with four required steps, in this order so the fingerprint stays fresh: docs written (changed docs tier and `CHANGELOG.md`), before-and-after pictures under `docs/qa` or a check that no visual file changed, the plan's test command passes (`verify.py && python tools/verify_tools.py` in this repo), QA page built and stamped. The plan carries the test command and a check per step, and `make_page.py build` refuses a plan without them.
6. **Stop check.** (overnight.sh sets `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` to 1000, not 0, because what 0 means is unverified; this changes one line of the approved design and the live run must prove a ninth consecutive block holds. Pending approval of the build plan.) The shared block counter (`core.py:3655`) is reused. On every stop, even with no reply text, an open step blocks. After 3 blocks with no step closed and no commit the step is marked stuck, shown on QA, and the check moves on. "NEEDS YOU" text no longer exempts anything; only a parked step does. The model judge blocks at most once per step set. Sessions with no step list keep the current goal check. The dead `GOALCHECK_BLOCKS` is deleted.
7. **Self-approval.** A hook, not a command I can run, moves Design to Plan and Plan to Build when nobody is present, needs a stored `VERDICT: clean` from a house-rules reviewer in page or plan mode, for the page hash (a verdict hook for reviewer helpers stays on when helpers are off, `delegation.py:740`), and never updates the newest-approval marker (`design_loop.py:482-509, 526-536`; self-approvals are stored under their own key). QA passed and Close approved stay aj's.
8. **Restart loop.** `tools/overnight.sh` starts `claude -p` with `--session-id`, resumes with `--resume <id> -p` after any stop, waits for a rate-limit reset without spending a restart, backs off after crashes, and runs a last short pass that builds the QA page. The resume text is marked relayed (`core.py:2040`). A stop-failure script parses `error_details` for a reset time and falls back to a fixed wait, because the stop-failure payload has no reset-time field. `--interactive` keeps today's behaviour. Limits: 24 hours of work, 5 restarts with no step closed; they end the run into QA with open steps listed first. This is the one exception to never stopping.
9. **QA-only reporting.** The messages that tell me to list refusals or report in the reply (`safe_git.py:1584, 1620`, `core.py:2800, 2958`, `tools/overnight.sh:4`) change to: write to the ledger and carry on.

## Speed first

The branch's stage file lacks the speed-first feature that main holds in Build; step 1 restores it under `features` so merging main does not overwrite its Build state. This reverses the design page's "wait for speed first to leave Build".

## Invariants it must keep

- QA passed and Close approved are aj's only, in every mode.
- The destructive-command guard and the main-branch guard have no switch and stay as they are.
- A session whose permission mode is unknown is treated as attended.
- A pull request to main may be opened by the run, never merged.
- The injected rules text has a size limit; new rule lines make room for themselves.

## Reversals (each gets a dated entry in `docs/6-decisions/Decisions.md`)

Lines 22, 54 (#460), 87, 92, 101, 121, 126 (the relaxed credit check stays relaxed, and a final check strips credit lines before a pull request opens), 133, 141 and 143, plus "approval only from aj's own message" and "nothing fails silently" (decisions are not said until QA).

## Known unknowns

Read from code and the Claude Code binary, never run live: whether Stop hooks block in a resumed headless run, whether the web app has `/goal`, whether a tool call resets Claude Code's consecutive-block count, the pause-goal tool's exact name, whether settings `env` reaches a resumed session, and whether a web-app scheduled task can resume a session. The web app has no outer loop and keeps Claude Code's cap of 8 blocks. Auto mode has a safety check I cannot rewrite, so overnight runs use the launcher.

## What was built (plugin 2.95.0)

- **#638 ledger commands:** `ledger_note.py decide` (K rows), `park` needs `--category` and `--tried`, K rows first on the QA page, slash-safe ledger folder.
- **#636 one presence test:** `core.nobody_present` (unattended switch or bypass); prompts denied at once, plan-exit allowed, pause-goal denied, agent writes to the mode file and to `HOUSE_RULES_` settings keys refused.
- **#637 loop stays on:** unattended keeps the design loop and handover on with six checkpoints (evidence, commit, deviation, QA page, changelog, decided-for-you); the question hold and the two issue refusals are skipped when nobody is present.
- **#639 step file:** `record_steps`, inside and outside hashes, `steps_integrity`, a `check` field and `test_command` in build plans, deviate rules (never delete, replace keeps the id).
- **#646 checks:** `ledger_note.py check --start|--poll`, a hook that records RESULT lines (PostToolUse and PostToolUseFailure), staleness by tree fingerprint.
- **#647 finish line:** four `Finish:` steps, `scripts/finish_checks.py`, Build to QA from the step list when nobody is present, a pull request denied while a step is open.
- **#640 stop check:** `step_stop_check` on every stop, stuck rule, judge once per step set, `QUESTION FOR YOU:` allowed when aj is present.
- **#641 self-approval:** verdict store for reviewer helpers (works with helpers off), `_self_approve`, `auto_approvals`, S rows first on the QA page, replace needs a fresh verdict.
- **#642, #648, #649 restart loop:** `tools/overnight.sh` resumes by session id (`--interactive` keeps the old behaviour), `ledger_note.py steps-status`, a `stopfailure` hook writing the error and any reset time, waits for rate limits without spending a restart, backs off after crashes, 24 hours of work and 5 restarts with no step closed, then one final QA pass.
- **#643 QA-only reporting:** refusals and denied questions point at the ledger, the QA reply counts the decisions, a pull request with a credit line is denied.
- **#635 rules:** the lines that told the agent to ask or wait are rewritten; `show-dont-tell.md` may be 3600 characters.

**Deviations (ledger `docs/qa/quiet-unattended-mode/ledger.md`):** the speed-first entry was not restored under `features` (the stage-file guard refuses hand edits; merging conflicts visibly instead); `park` stores its category and attempt inside the Question cell; the unattended noask text was updated in step 12, not step 1. Builder deviations that stand: `steps-status` reads the stage file, not the outside copy (the outside copy never records "done"); stuck steps are tracked in the stage record; a pull request is denied but `gh pr edit` is not.

**Not yet verified live:** Stop hooks in a resumed headless run, the block cap at 1000 and a ninth consecutive block, the real stop-failure payload shape, and whether the web app has `/goal`. Step 15 (#644) runs these.

