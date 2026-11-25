# Review command

## What it owns

One command, `/house-rules:review`, that sends the existing reviewer helper at code, an image, a screen's style, or a whole repository, in any project that has the plugin installed. It owns the choice of mode from what the user points at, the saving of the report, and the whole-repo sweep. It does not own the reviewer's judging stance; that stays in `agents/reviewer.md`.

**Status: built (plugin 2.94.0; parent issue #617, steps #618 to #621).** The design was approved on 2026-11-24 as "Design approved: review command 1A 2A 3*". The build plan is `docs/plans/review-command-plan.html`. aj's QA is still to come.

## How it works

| Piece | Step | What it does |
|---|---|---|
| Four new reviewer modes | #618, built | `code`, `codebase`, `image` and `style` join `page`, `plan`, `acceptance` and `diff` in `agents/reviewer.md` and `rules/detail/review-modes.md`. Same stance: findings only, no praise. |
| The command | #619, built | `commands/review.md` picks the mode, takes extra input, saves the report and runs the sweep. |
| Sweep helper | #619, built | `scripts/review_plan.py` (`mode`, `units`, `batches`) picks the mode, lists the units, cuts them into batches and prints the over-12-folders notice, so the counts the user sees come from code. It is a small addition beyond the plan (deviation D1 in `docs/qa/review-command/ledger.md`). |
| Model and effort override | built in 2.94.3 | `/house-rules:review` takes `--model opus\|sonnet\|haiku\|fable` and `--effort low\|medium\|high\|xhigh\|max` anywhere in its text. `review_plan.py mode` reads them and prints `model:` and `effort:` (`default` when not typed; an unknown value exits 2). The command sets the Agent tool's `model` and `effort` only when they are not `default`, so the reviewer's own setting (`opus`, `medium`) applies otherwise, and every reviewer in a sweep gets the same override. The `agentcap` hook stores the typed `model` and `effort` on the launch's record, `announce` shows them ("override typed at spawn"), and `verdict` compares the model the subagent ran on with the typed one, falling back to the agent file when nothing was typed (2.94.4). |
| Checks | #620, built | `verify.py` cases keep the mode lists, the command file and the sweep notice in step. |
| Docs and version | #621, built | This document, a Decisions entry, a CHANGELOG line, the Today note, the version bump. |

## Decisions that shape it

- The reviewer is extended, not duplicated (design review loop, 4A in `docs/6-decisions/Decisions.md`). A second critic agent was dropped for that reason.
- A reviewer has no Agent tool, so it cannot start other reviewers. The command, run by the main session, spawns one reviewer per top-level folder, one at a time.
- Question 1, answer A: a short verdict goes to chat and the main session saves the full report to `docs/qa/review-<target name>-<date>/`. The reviewer itself writes nothing new.
- Question 2, answer A: the sweep goes folder by folder, one reviewer at a time, with a merged list ranked by severity and then file.
- Question 3, aj's own answer: the sweep has **no folder cap**. Over 12 top-level folders the command first tells the user the folder count, an estimated time and an estimated token use, then runs.
- Syntax: `/house-rules:review <path> [style] [criteria text]`. No argument reviews the uncommitted diff in diff mode.

## Report folder and batches

- The report folder is `docs/qa/review-<name>-<date>`. The name is the file stem with any leading date dropped (`2026-11-24-foo.html` gives `foo`), or the folder name.
- A batch is at most 6 files of one top-level folder. `docs/qa/review-command/batch-measurement.md` measured one 10-file markdown batch at 71.3 seconds, about 7.1 seconds a file; 8 files (57 seconds) sat right at the 60-second agent deadline and code files run slower, so 6 files (43 seconds on markdown) leaves headroom (deviation D3).
- That deadline is 60 seconds (`rules/waits.json`). The 900 seconds on the design page and in `skills/visual-loop/SKILL.md` was stale (issue #622).

## Mode detection order

1. The repo root itself (`.`, `./`, or its absolute path): codebase. The target is resolved against `--root`.
2. An image extension: image.
3. A page whose `house-rules-page` tag says `build-plan`: plan. Its design is the page with the same name minus `-plan` or `-build-plan` (dates ignored), or the `proposal.html`/`design.html` beside a folder-style `build-plan.html`; several matches print `design: ambiguous` and one `candidate:` line each.
4. Any other HTML page: page.
5. Any other file or folder: code.
6. The word `style` after the path: style (needs a stated style or a project UI guide; otherwise it stops and says so).

## Invariants it must keep

- The command file uses the braced `${CLAUDE_PLUGIN_ROOT}`; the unbraced form broke `/house-rules:harvest-scan` (Decisions, 2026-09-20).
- One reviewer at a time, at most two, per the delegation rule.
- Every wait has a deadline from `rules/waits.json` (agent: 60 seconds, one segment), checked each minute with `scripts/waitfor.py`. A folder past it is listed as not reviewed, never dropped silently.
- `docs/page-style.json` describes handover pages, not app screens, so style mode does not read it.

## Known unknowns

- The sweep notice counts time at 7.1 seconds a file and tokens at 10,000 per batch plus 3,400 per file. The token rule was fitted to the real 15-batch sweep (203,394 tokens; the old 4,400-a-file figure said 66,000, 3.1 times low, deviation D2). Code files take longer, so both are a floor.
- A sweep of this repo is 9 folders but 96 batches, so the notice (printed over 12 folders, per aj's answer) does not print for it. aj is asked at QA whether it should also print when batches pass 12. The rule is not changed in code.
- Claude Code's own built-in `/review` was named by the reviewer from product knowledge and was not tested here; that is why the command is always written with its `house-rules:` prefix.
