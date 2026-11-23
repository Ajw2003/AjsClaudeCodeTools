# Handoff: clear-roadblocks plan

## What the work is for
aj wants a house rule that stops the agent claiming a roadblock (a missing tool, the wrong machine) without checking, and makes it install tools and take other routes itself, especially in bypass permission mode.

## Where it stands
Design approved on 2026-11-22 as "Design approved: clear roadblocks 1C 2A" (a rule plus an end-of-reply check that blocks twice, then warns; only licences, logins, purchases and destructive actions stay aj's). Planning is written: `docs/4-systems/roadblocks.md`, a decisions entry, three step issues and a build plan page `docs/plans/2026-11-22-clear-roadblocks-plan.html`. The build plan was approved ("Build plan approved: clear roadblocks") and the stage is Build. Step 1 (#570) is built: the rule text is in rules/house-rules.md and rules/detail/roadblocks.md. To fit the 9700-character injected-rules limit, aj chose to delete the "Plain language and the voice" stub (its pointer lives in rules/clear-writing.md) and the rule section was shortened; verify.py passes all checks, with 9694 characters injected, 6 under the limit. Step 2 (#571) is built: `roadblock_check` in `scripts/house_rules/core.py`, called from `event_handover` in `scripts/hook.py`, with 7 new cases in `scripts/checks/core.py`; verify.py (213 core checks) and verify_tools.py (55) pass. One older case (the #89 'untested' case) had its example reason changed from a missing editor to a four-hour suite, because a missing-tool reason is now exactly what the new check blocks. Step 3 (#572) is built too: docs, changelog and plugin 2.88.0; verify.py 1345 of 1345 and verify_tools.py 55 of 55 pass, docs_drift reports 0 drifted citations. A QA page is written at `docs/plans/2026-11-22-clear-roadblocks-qa.html`; the editor pass is applied and issues #569 to #572 now say `needs review`, so QA has started.

## Update after QA
QA on this machine found main already shipped a different 2.88.0 (#573). Main was merged in with the loop-state file kept as ours, the feature is now 2.89.0, and the rule is folded into the user's-hands section (9691 of 9700 injected characters). verify.py 1443 of 1443 and verify_tools.py 55 of 55 pass.

Live test on the branch build passed (blocked once, then the agent probed and answered with evidence). Pull request #574 is open. The QA page's final editor pass is applied; issue #89 on that page is named from a code comment, not from the issue itself.

CI on #574 failed the inject-size check at the runner's longer path (9717 > 9700); fixed by dropping the roadblocks pointer from house-rules.md (9674 at a runner-like path). Check size at a runner-like path, not only locally: a copy of the repo at `/home/runner/work/AjsClaudeCodeTools/AjsClaudeCodeTools` reproduces CI.

Update: pull request #574 was merged and issues #569 to #572 are closed. Nothing is left to build on this branch.

## New finding after the merge
aj's PC session (Castle) let a roadblock claim through. Two bugs reproduced against the merged check: curly apostrophe not matched; `git ls-files` counted as a probe. Possible third cause: that session loaded an older build, not checkable from here. Proposal page `docs/plans/2026-11-23-roadblock-detection-fix.html` awaits aj's "Design approved: roadblock detection fix" with two picks. Nothing built.

## The next step
Nothing: the work is merged. Optional: aj's own test via the QA page ("QA passed: clear roadblocks" or what failed). On a pass, open a pull request with `Refs #569` (never Closes); on a fail, fix on this branch (#571, the check), then step 3 (#572, tests, docs, version).

## What is unverified
The injected rules have only 6 characters of room, so any later rule text needs more cut; the shortened rule in house-rules.md no longer says installs happen without asking in bypass mode (only the detail file does). The new check has only been run against fixture transcripts, not inside a live Claude Code session. The count is kept in a temp-directory file keyed by transcript path and user-message count.

## Issue numbers
#569 parent; #570, #571, #572 steps. All four are closed as completed; pull request #574 is merged.
