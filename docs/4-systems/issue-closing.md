# Issue closing

How the agent closes GitHub issues itself, under a guard that checks the evidence first. Designed
2026-10-20 (`docs/6-decisions/Decisions.md`, "Design approved: issue closing"); proposal page
`docs/plans/2026-10-20-issue-closing.html`.

## What it owns

- The rule for when the agent may close an issue, in `rules/detail/issue-workflow.md` (rule 6).
- The closable record: the evidence that lets an issue close, kept in the design loop's stage file,
  `.claude/house-rules-loop.json`.
- The close guard: the part of `guard` (for `gh`) and `guardgithub` (for the GitHub MCP tools) that
  lets a close through or refuses it.
- The sweep: a one-time page that lists the open agent-created issues for aj to approve.

## How it works

**What existed before 2.70.0.** Rule 6 said closing always asked aj, and the guard turned three `gh`
closing commands into a prompt. A close through the GitHub MCP tool (`issue_write` with `state:
closed`) was not checked at all. The design loop records the current feature's issues in
`state["issues"]` and aj's approvals in `state["approvals"]`, but a new "Design approved" clears
`state["issues"]` (then hook.py line 5533; today `_loop_apply_one` in `house_rules/design_loop.py`), so nothing about a finished feature survives the next one.

**The closable record.** When aj's "QA passed: <feature>" moves the loop on, the hook copies that
feature's recorded issues into a new list in the stage file, `closable`, as one entry: the feature
name, its issue numbers, the time and the QA message. The entry survives later design approvals. When
a pull request merges into the default branch (a `PostToolUse` record of the MCP
`merge_pull_request` tool or `gh pr merge`), the hook stamps every `closable` entry that has a QA pass
and no merge yet with that pull request's number. An entry with both a QA pass and a merge is ready.

**The close guard (question 1, answer A).** A close of issue N goes through when N is in a ready
`closable` entry. Any other close is refused, and the refusal names what is missing: no QA pass for
the feature that holds N, no merged pull request since that pass, or N not recorded under any
feature. The `gh` routes and the MCP route are both checked. The allowed close carries an
instruction for the agent: comment on the issue with the QA message and the merged pull request's
link, add the label "AjsAgent completed this" (its name comes from the settings once #341, Restructure
step 3: settings and identity, ships) and remove "in progress". The guard itself removes nothing.
After the close, the `closablemerge` hook (`PostToolUse`) removes the issue from its entry, or from
`sweep`, only on proof the close succeeded: the GitHub tool's result with no error, or for `gh` an
exit code of 0 or gh's own "Closed issue" line. A close that fails keeps its evidence, so a retry is
still allowed. An empty entry is dropped. An approval that names no repo matches this project's own
repo, because the stage file belongs to one repo.

**The sweep (question 2, answer A; question 3, answer A).** The sweep page lists every open issue
labelled "AjsAgent created this", grouped as: QA passed and merged, built and waiting for aj's QA,
never started, replaced by #306 (the restructure). Each row shows its evidence and a suggested action:
close as completed, close as not planned (naming the issue that replaces it), or keep. aj's reply
"Sweep approved: issues" plus any changes records the approved list in the stage file as `sweep`.
The guard lets through exactly those closes, with exactly the approved state reason, and a not-planned
close must comment naming its replacement. aj can also name issues in a message, "Close as not planned:
#N replaced by #M", which records the same kind of approval for those issues alone. Issues opened by anyone other than the agent are never in
the sweep. A not-planned close never comes from a QA pass.

## Invariants

- Since 2.83.0 (free issue closing): an issue closes on its own only when it is in no GitHub milestone
  and carries `needs review`, `in review` or a completed label someone other than the agent set. Every
  other close, any milestone issue and any milestone need aj's "Close approved", a sweep approval or a
  QA pass plus a merge.
- Every close comments with its evidence.
- The guard reads the stage file first; only when no record allows the close does it read GitHub, once
  per repo per 60 seconds, and a failed read refuses the close.

## Traps that have already cost time

- A new design approval clears `state["issues"]`; the closable record exists because of it.

## Planned: the proof check fix (#367)

Approved 2026-10-21 ("Design approved: proof check fix 1A 2A"). Two gaps, both found live:

- **Wrapped replies (#374).** The GitHub tool returns every result as a list holding one text block,
  `[{"type": "text", "text": "{\"merged\": true, ...}"}]`, recorded on all 74 successful merge and issue-update
  calls in the 2026-10-21 session transcript. `_closable_merge_of` and `_closed_issue_of`
  (`scripts/house_rules/design_loop.py`) read the reply as a plain object, so neither ever found its proof. A
  helper unwraps the text block first; an error reply stays text and proves nothing.
- **One issue list per feature (#375).** `state["issues"]` holds only the current feature's issues, so a build
  plan approved for a second feature before the first passed QA made the first feature's "QA passed" record
  nothing. Issues are kept per feature name instead, and an older stage file is converted on first read.

Built: #374 (wrapped replies), branch `AjsAgent/issue-374-unwrap`; a helper `_unwrap_tool_response` now runs first in both proof checks.

Built: #375 (one issue list per feature), branch `AjsAgent/issue-375-features`. `state["issues"]` is still the current
feature's list. When a new "Design approved" replaces a feature whose stage is build or qa and that has recorded issues,
`_loop_keep_feature` copies them to `state["features"][<name lowercased>] = {"name", "issues", "stage"}`; a feature in
design, plan or done, or with no issues, has nothing to keep. "QA passed: X" or "QA failed: X" naming a kept feature
other than the current one (`_loop_stored_qa`) checks that feature's own issues for `needs review`, never changes the
current feature's stage or issues, and says so in the hook's note. A pass appends the `closable` entry as the current
path does and removes the feature from the map; a failure leaves it there, stage "build" with `redo` true, so a later QA
message works once its issues are back to `needs review`. A stage file with no `features` key reads as an empty map, so
no conversion is needed. Checks: "per-feature issues" in `scripts/checks/design_loop.py`.

Step 2's issues (#340, #357 to #360) close through the next sweep page (answer 2A).


## Free issue closing (2.83.0)

Approved 2026-11-20 ("Design approved: free issue closing 1* 2A"; `docs/6-decisions/Decisions.md`).
Proposal page `docs/plans/2026-11-20-free-issue-closing.html`.

**The new close rule.** `_close_check` (`scripts/house_rules/design_loop.py`) allows a close when
the issue is in no GitHub milestone and carries `needs review`, `in review`, `AjsAgent completed
this` or `Claude completed this`. A completed label the agent added in this repo (recorded by the
existing label-change hook into the stage file as `self_completed`) does not count. Anything else is
refused unless aj wrote "Close approved: #N" for it, recorded in the stage file as `close_approved`.
The QA-and-merge and sweep records still allow a close when present; they are no longer required.

**One lookup per group (aj's answer to choice 1).** The guard reads the repo's open issues with one
`gh api repos/O/R/issues?state=open --paginate` call (5 second limit) and keeps the labels and
milestone of each in `.git/house-rules-issue-cache.json` for 60 seconds. Every close in that window
reads the cache, so a mass close makes one call. An issue missing from the list is read alone. When
GitHub cannot be read, the close is refused and the refusal says why. Tests point
`HOUSE_RULES_CLOSE_ISSUES_FILE` at a JSON file standing in for GitHub.

**Milestones.** A close of a milestone (`gh api -X PATCH repos/O/R/milestones/N` with state closed)
is refused unless aj wrote "Close approved: milestone N".

**After a close.** The allowed close tells the agent to add `AjsAgent completed this` and remove
`in progress`, as today.

**As built (#549 to #552).** `_close_issue_facts` does the cached lookup; `_close_records` holds the old
record checks, now preceded by `close_approved`; `_close_by_labels` applies the label rule;
`_close_check(..., git_dir)` runs records first and the lookup only when they refuse. `self_completed`
is written by `_loop_record_labels`. `_GH_MILESTONE_CLOSE_RE` and `_milestone_close_decision` guard
milestone closes. "Close approved:" is parsed in `_loop_sweep_apply`. One difference from the plan:
the label rule applies to completed closes only; a not-planned close still needs a sweep approval,
"Close as not planned" or "Close approved", so a `needs review` label never closes work as not planned.
An MCP `issue_write` that sets a full label list containing a completed label is recorded as
self-added even if a person set the label first; that errs toward asking. Checks: "close facts (#549)",
"close by labels (#550)" and "close approved:" in `scripts/checks/design_loop.py`.
