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
aj's PC session (Castle) let a roadblock claim through. Two bugs reproduced against the merged check: curly apostrophe not matched; `git ls-files` counted as a probe. aj confirmed both sessions ran 2.89.0, so an old build is ruled out; the Castle transcript is not readable from here (aj's PC does not offer its folders to cloud sessions). Proposal page `docs/plans/2026-11-23-roadblock-detection-fix.html` (three questions, editor pass applied to all of it, sent to aj) awaits aj's "Design approved: roadblock detection fix" with three picks (the third covers a second screenshot: an unattended run handed aj a design question in plain text, which the `noask` hook does not catch). Nothing built.

(The proposal page's final editor pass is applied and the page was sent to aj.)

## Detection fix plan (2026-11-23)
aj approved "Design approved: roadblock detection fix 1* 2* 3*" with their own answers. Parent #587; steps #588 (detection and a real block-twice), #589 (evidence rule), #590 (never wait in unattended or bypass mode, docs, version, QA). Build plan page `docs/plans/2026-11-23-roadblock-detection-fix-plan.html` awaits "Build plan approved: roadblock detection fix". aj added during planning (and tightened later the same day: a first try never counts, the first try plus two further attempts by different methods must fail (three attempts in total, corrected from two), and the reply lists every method tried; plus the general inability phrases such as could not and unable to): before saying something can't be done or can't be verified, try up to two different methods; read as two different failed methods, in step 2 (#589). Two readings are mine and are on the page: the stall phrases (not done, I've stopped, next step) fire only in unattended or bypass mode; the approval gate before source edits stays. Verified since: stop_hook_active is True on a continuation and a second block is allowed (test hook; Claude Code caps blocks at 8). Still unverified live: the bypass value of `permission_mode` is `bypassPermissions` from Claude Code's own mode list, never seen in a live bypass run. "I've stopped here" was added to the stall phrases. No code built.

(Plan page final wording applied after the editor pass: nine always-flagged phrases, four stall phrases, sent to aj.)

(Final state of the detection-fix plan page: three attempts in step 2, nine always-flagged phrases, four stall phrases, editor pass applied, sent to aj.)

## Audit (2026-11-23)
aj asked for an audit of the plan's weaknesses. Page `docs/plans/2026-11-23-roadblock-check-audit.html` has eight findings and five picks; waiting on "Design approved: roadblock check audit" with picks. Then update the plan page and issues #588 to #590 to match, and get "Build plan approved: roadblock detection fix". Unverified: the agent-hook option; the judge's cost is from one run; whether aj's PC uses the PowerShell tool; hook time limits.

## The next step
Wait for aj's "Build plan approved: roadblock detection fix", then hand step 1 (#588) to a builder, then #589, then #590. The original work (#569 to #572) is merged. Optional: aj's own test via the QA page ("QA passed: clear roadblocks" or what failed). On a pass, open a pull request with `Refs #569` (never Closes); on a fail, fix on this branch (#571, the check), then step 3 (#572, tests, docs, version).

## What is unverified
The two bugs are reproduced in test runs, not confirmed on the Castle turn itself. The autosave error on aj's PC (a leftover git `index.lock`) was seen in the screenshots and not investigated. The injected rules have only 6 characters of room, so any later rule text needs more cut; the shortened rule in house-rules.md no longer says installs happen without asking in bypass mode (only the detail file does). The new check has only been run against fixture transcripts, not inside a live Claude Code session. The count is kept in a temp-directory file keyed by transcript path and user-message count.

## Issue numbers
#569 parent; #570, #571, #572 steps. All four are closed as completed; pull request #574 is merged.
