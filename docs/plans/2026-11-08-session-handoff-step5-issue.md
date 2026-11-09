# Draft: usage handoff step 5 issue (not opened yet)

Title: Usage handoff step 5: save the working folder automatically on every branch
Labels: AjsAgent created this, Feature, in progress. Sub-issue of #406.

---

Part of #406 (Keep work saved and handed off on every reply, so a usage limit never strands it).

## What this is

The existing autosave (`event_autosave` in `scripts/house_rules/delegation.py`) saves only subagent branches today. This step widens it to every branch the main session edits on:

- After a `Write`, `Edit`, `NotebookEdit` or `Bash` call, at most once a minute, the working folder is snapshotted to `refs/house-rules/autosave/<branch>` through a temporary index and pushed to `origin`. The branch, its index and its working tree are never changed.
- What is saved follows #477: tracked changes, plus new files the agent wrote with `Write`, `Edit` or `NotebookEdit`.
- Each snapshot carries `.house-rules/handoff-facts.md`, written only into the temporary index: branch, base commit, unpushed commits, uncommitted files, design-loop feature and stage, the stage file's issues with labels, and the time.
- The end of a turn (`Stop`) and a turn ended by an API error (`StopFailure`, which includes `rate_limit`) force one save and push.
- No work-in-progress commits on the main session's branches; those stay for subagent branches.
- No `origin`, a push timeout, or any git failure is said in one line. `HOUSE_RULES_AUTOSAVE=off` still turns it off.

## Depends on

Nothing.

## Depended on by

Step 1 (#407, the save check runs after the forced save), step 2 (#408, the pickup reads these snapshots), and step 4 (#410).

## Done when

`verify.py` replays an edit on an `AjsAgent/` branch and on `main` and finds the snapshot ref with the facts file and the edited file, with the branch, index and working tree unchanged; a second edit within a minute does not push; a `Stop` and a `StopFailure` push. A real edit in a live session puts the ref on `origin`, seen with `git ls-remote`. `verify.py` passes twice with no new failures.

Opened by AJ's agent
