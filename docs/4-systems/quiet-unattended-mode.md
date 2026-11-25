# Quiet unattended mode

## What it owns

Making a run with nobody present (unattended, bypass) carry the design loop from goal to QA by itself: it decides, logs every decision, works a guarded list of steps, and cannot stop part-way. Also the shared parts that cut aj's decisions in every mode, auto included.

**Status: designed, not built.** aj approved the design on 2026-11-25 as "Design approved: quiet unattended mode 1A" on `docs/plans/2026-11-25-quiet-unattended-mode.html`. The page had three review rounds (45 holes, then 38 more); the stamp reads open risks, round 2, and the last four edits (look or function decided when nobody is present, auto stays attended, bypass counts as unattended, the finish line) were not re-reviewed.

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
4. **Ledger.** `ledger_note.py` gains `decide` (row type C with an Assumption column) and `check`, and `park` needs a hard-stop `--category` and `--tried`. `deviate` may add or replace a step, never delete one or touch the finish line. `make_page.py` shows C rows and auto-approvals first with why and how to undo; the ledger folder for a branch name replaces `/` with `-`.
5. **Step list and finish line.** On approval a hook copies the steps from the reviewed build plan into the stage file, with a hash kept inside the repo and a second copy outside it, under the launcher's session id. A step is done when `ledger_note.py check` exits 0 in a normal Bash call and a hook records the exit code and commit (stale once HEAD moves). Every list ends with four required steps: tests pass (`verify.py` exits 0), docs written (changed docs tier and `CHANGELOG.md`), before-and-after pictures under `docs/qa` or a check that no visual file changed, QA page built and stamped.
6. **Stop check.** The shared block counter (`core.py:3655`) is reused. On every stop, even with no reply text, an open step blocks. After 3 blocks with no step closed and no commit the step is marked stuck, shown on QA, and the check moves on. "NEEDS YOU" text no longer exempts anything; only a parked step does. The model judge blocks at most once per step set. Sessions with no step list keep the current goal check. The dead `GOALCHECK_BLOCKS` is deleted.
7. **Self-approval.** A hook, not a command I can run, moves Design to Plan and Plan to Build when nobody is present, needs a stored reviewer verdict for the page hash (a verdict hook for reviewer helpers stays on when helpers are off, `delegation.py:740`), and never updates the newest-approval marker (`design_loop.py:525`). QA passed and Close approved stay aj's.
8. **Restart loop.** `tools/overnight.sh` starts `claude -p` with `--session-id`, resumes with `--resume <id> -p` after any stop, waits for a rate-limit reset without spending a restart, backs off after crashes, and runs a last short pass that builds the QA page. The resume text is marked relayed (`core.py:2040`). `--interactive` keeps today's behaviour. Limits: 24 hours of work, 5 restarts with no step closed; they end the run into QA with open steps listed first. This is the one exception to never stopping.
9. **QA-only reporting.** The messages that tell me to list refusals or report in the reply (`safe_git.py:1584, 1620`, `core.py:2800, 2958`, `tools/overnight.sh:4`) change to: write to the ledger and carry on.

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
