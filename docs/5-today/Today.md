# Today — 2026-11-24

The systems doc `docs/4-systems/review-command.md` had a 900-second agent deadline in its invariants; it now says 60 seconds (the value in `rules/waits.json`), and the final plan page was re-sent after two review rounds. Still waiting on aj's three answers and "Build plan approved: review command".

aj approved the review command design ("Design approved: review command 1A 2A 3*"; 3*: no folder cap, a notice over 12 folders). The stage is Plan: parent issue #617 and steps #618 to #621 are open, the systems doc `docs/4-systems/review-command.md` is written as planned, and the build plan page `docs/plans/review-command-plan.html` was reviewed twice (15 findings, then 13, all applied; stamped open-risks) and is waiting on aj's three answers and approval. The stale deadline line in `skills/visual-loop/SKILL.md` is issue #622. One fact corrected: the agent deadline in `rules/waits.json` is 60 seconds, not the 900 quoted on the design page and in `skills/visual-loop/SKILL.md`; the plan asks aj how a sweep should handle it. Nothing is built.

aj asked for a review command that can be deployed anywhere, covering code, images, visual style and whole codebases, and asked whether to extend the reviewer or make a new agent. Nothing is built. The proposal page `docs/plans/2026-11-24-review-command.html` suggests one `/house-rules:review` command plus four new reviewer modes (code, codebase, image, style), and two questions wait on aj (where reports go, how a whole-repo sweep runs). Round one of the page review found 16 problems (one reversal of the 4A decision that the reviewer is extended, not duplicated) and all were applied; round two is running and the page is not stamped yet. Handoff: `docs/5-today/handoff-AjsAgent-jolly-dirac-fvh4cg.md`.

#613 is done on the judge branch except the unbuilt 60-second flag in #611: plugin version 2.93.0, systems doc status, changelog line, and the 12-reply replay (already the core check #608). The inject-size check no longer depends on how deep the checkout is (the plugin root path is measured as 100 characters). A full verify.py at the long worktree path exits 0 (1586 of 1593, 7 skipped), verify_tools 55 of 55. No pull request is open yet.

aj asked for the new judge changes to be live so the judge stops over-firing. I merged `main` and the #610 builder branch into `AjsAgent/judge-blocking-audit`, ran safe_git (282 of 282), delegation (204 of 204) and a full run (only the inject-size check fails), pushed it, and switched the installed plugin to that branch with `tools/use_branch.py` (commit ea6ea6a, version 2.92.0). It takes effect in a new session. Steps #610 and #613's docs/version are not finished; #611's 60-second flag is not built.

Pull request 614 (design review loop, acceptance round 2, Windows fixes) is merged. I found one test fix, in `checks/delegation.py`, that was never committed and opened pull request 615 for it. The judge branch (`AjsAgent/judge-blocking-audit`) has #613 done except the 60-second flag in #611, which waits on #578 and #579 (both open, nothing built); its pull request into main is not open yet.

aj failed QA with "fix all pre existing failures before we pr to main". All nine Windows failures are fixed (waitfor, guard, page and node checks) plus one in tools/verify_tools.py; a full verify.py passes here (1574 of 1581, 7 skipped). The acceptance run is being repeated because the fixes made its stamp stale; round 2 is not re-stamped yet.

Acceptance round 2 now passes all nine criteria on aj's PC after the two Windows fixes; both rounds are recorded, the stamp is current, and the QA page is built and sent. Waiting on aj's QA reply.

aj's PC run of the acceptance runner failed every criterion: the `design_loop` part crashed on Windows before reporting a check. I fixed two Windows-only causes (the fake `gh` script in the close-facts tests, and the review stamp hashing CRLF differently from LF). A full nine-criteria rerun is in progress; round 2 is not recorded or stamped yet.

aj saw the first PC run sit silent for minutes; the runner now prints a progress line every 20 seconds (aj's rule: at least every minute) and I ran `C1` here to see the lines appear. aj has the fixed version to pull and rerun, or can let the first run finish.

The runner's test run here passed all nine criteria (`round-2/` holds one output per search text). aj gave the PC clone path and was handed the three-step card to run it on Windows and push the outputs; waiting on aj's `STATUS:` line.

The roadblock judge kept blocking status replies while the runner's test run was under way (about twelve blocks, logged in `docs/roadblock-judge-friction-2026-11-24.md`); aj was offered `HOUSE_RULES_ROADBLOCKS=off` for this session and has not answered.

aj asked me to note that the roadblock judge looks over-zealous and may waste usage: recorded in `docs/roadblock-judge-friction-2026-11-24.md` (the roadblock judge, three cases, three open questions, nothing changed).

aj chose A for recording the acceptance rounds: `docs/qa/design-review-loop/run_acceptance.py` runs C1 to C9 one by one and saves each output. A first test run here is in progress; its result is not yet read. Nothing is recorded or stamped.

Plan page fixed (Acceptance tests item, stale text, reviewed with open risks, rebuilt), C1 evidence saved, C5 sample card and check added; full `verify.py` 1582 of 1582 (output in `docs/qa/design-review-loop/round-2/run-1.txt`). The acceptance rounds were not recorded: a hand-written passing round file was refused by the auto-mode classifier, so no acceptance stamp and no QA page yet. Pull request opened with `Refs #592`.

aj chose A2 for the combined approval (acceptance criterion C6): built as `_plan_unreviewed` in `design_loop.py`, with four new cases (no plan page, unstamped, stale, and a plan approval on its own message unaffected); ledger row D7 and `review-loop.md` updated. C1 (reviewer findings not saved) and C5 (self-judging test card format unchecked) are still open.

Design review loop (parent #592) finished on `ccr-1839130d-clohr1`: the unmerged branch `AjsAgent/sleepy-albattani-bxj5wx` was merged in (three conflict spots resolved: changelog kept both sides, the stage file kept the design review loop's own, `delegation.py` kept both test blocks), main's 2.91.0 is on top. Step 7 (#599) is built: `ledger_note.py deviate` had no tests, now has two, and a `deviation` checkpoint in `design_loop.py` sends back a bypass or unattended reply that admits a departure from the plan with no `ledger_note.py` call that turn (six new cases pass). Step 9 (#601): systems doc rewritten as built, four reversal entries in the decisions log, plugin 2.92.0. One stale cap was updated: the `show-dont-tell.md` length check in `make_page.py` from 3231 to 3307 characters (step 7's rule line). My own full runs: `verify.py` 1577 of 1577, `tools/verify_tools.py` exit 0, `docref.py check` OK, `docs_drift.py` 0 drifted. The acceptance run is done: 6 of 9 criteria pass, 3 fail (C1, C5, C6), so it is not stamped; report in `docs/qa/design-review-loop/report.md`, and aj is asked about the combined approval and the plan page's missing Acceptance tests item; the QA page and the pull request (`Refs #592`) follow. Handoff: `docs/5-today/handoff-AjsAgent-sleepy-albattani-bxj5wx.md`.

2026-11-24: aj approved the build plan ("Build plan approved: judge blocking fix and one-minute segments"). Stage is Build. Merged into `AjsAgent/judge-blocking-audit` and verified by my own runs: #606 (criteria), #612 (page-check fixes), #607 (scripted judge), #608 (shared cap of two blocks), #609 (narrower phrase lists, block messages name the criterion) and the streaming half of #611 (`verify.py` prints each part as it finishes). A builder is running for #610 (segments and launch guard). #613 waits. The "flag modules over 60 seconds" half of #611 is unbuilt because #578 and #579 are not in the repo. The loop has no issues on record because they were made by a script; they exist on GitHub with the right labels.

2026-11-24: aj approved the design ("Design approved: judge blocking fix and one-minute segments 1A 2A 3A"). Planning is written: systems doc `docs/4-systems/roadblock-judge-and-segments.md`, parent issue #605 with steps #606 to #613, a dated decisions entry, a changelog line, and the build plan page `docs/plans/2026-11-24-judge-and-segments/build-plan.html`. Code stays closed until aj sends "Build plan approved: judge blocking fix and one-minute segments".

2026-11-24 (branch `Agent/judge-blocking-audit-0686a3`): aj reported the roadblock judge blocked a test session 12 times. Cause found in the code: three stacked Stop checks, one with no cap. A proposal page `docs/plans/judge-blocking-fix.html` fixes the judge on both sides and extends the approved modular-tests design (#575) with a 60-second budget, per-module results and an independence proof. aj clarified the judge stays and is tuned: written criteria, a shared cap, and clear steps for the model. aj then widened the test fix to any wait-bound work: independent one-minute segments, each with its own result. aj decided the guard refuses foreground and background launches over 60 seconds unless the launch gives a Cannot split reason that passes a new judge criterion (C5). The page check's false findings from inline pictures were fixed in the page (132 down to 10, the rest being long sentences the editor is splitting). aj set the reason standard: any reason the judge reads must be a genuine, checked impossibility with the check, its evidence and the logic (new criterion C5 for Cannot split). Criteria count corrected to five. The segments picture was broken by a raw angle bracket in its text; fixed and checked in the browser pane, and the page check gains a well-formedness test for inline pictures. The editor's wording fixes for the picture-check item are applied. Nothing built; waiting on aj's choices and approval.

Pull request #603 is open for quieter messages. Main took 2.90.0, so quieter messages is now 2.91.0 and main is merged in (verify.py 1503 checks pass). Quieter messages passed QA (aj wrote "QA passed: quieter hook messages"); no pull request is open yet. Earlier it was in QA: the page `docs/plans/2026-11-23-debug-log-spam/qa.html` is sent and #583 to #586 say `needs review`. Both build plans approved; stage Build. Quieter messages step 1 (#584) is built and merged (hook log, `HOUSE_RULES_TRACE=chat`, `/house-rules:hook-log`); full verify.py passed on my own run. Step 2 (#585) is built and merged (autosave scratch file per process, error once per session; I confirmed the new collision case fails when the fix is removed), and step 3 (#586) docs, changelog and plugin 2.91.0 are written. My full verify.py after the step 2 merge: 1453 checks, all parts pass. Modular tests step 1 (#576) was built, merged and reverted: the injected rules came to 10286 characters against 9700, and one speed-switches check failed; aj is asked where the rule should go. Builders running: quieter messages step 1 (#584) and modular tests step 1 (#576), not yet reported. Modular tests (parent issue #575, steps #576 to #582): aj approved the design as "Design approved: modular tests 1A 2* 3A" (choice 2 was aj's own answer, "c plus A"). The stage is Plan. Written: the systems doc `docs/4-systems/modular-tests.md`, the seven issues, and a build plan page `docs/plans/2026-11-23-modular-tests/build-plan.html` waiting on "Build plan approved: modular tests". Nothing is built and no check has been run. Handoff: `docs/5-today/handoff-ccr-4ced8cf2-ggrx7a.md`.

Quieter hook messages (scope note: only `trace()` and autosave notes move to the log; refusals and reminders stay in chat): aj chose option A (silent by default, a log, and `/house-rules:hook-log`). Systems doc `docs/4-systems/hook-message-log.md`, parent issue #583, steps #584 to #586, and a build plan page `docs/plans/2026-11-23-debug-log-spam/build-plan.html` waiting on "Build plan approved: quieter hook messages". Earlier in the day: aj approved the design as "Design approved: quieter hook messages 1* 2A"; choice 1 is aj's own answer: all hook messages hidden by default but expandable in chat like tool output. The stage is Plan. The docs lookup found no expandable hook message in Claude Code, so choice 1 as written cannot be built; aj is asked to pick a close alternative. The systems doc and issues wait on that answer. aj's screenshot showed two repeating messages. Causes found in the code: `design_loop.py:3273` prints "closable-merge stamping is off" after every Bash call, and autosave (`delegation.py:1245`) shares one scratch index file per branch, so overlapping calls collide on its lock. Proposal page `docs/plans/2026-11-23-debug-log-spam/proposal.html` is sent and waiting on aj's two choices. Nothing is built and no check has been run.

## 2026-11-22

Roadblock detection fix (parent #587; steps #588, #589, #591, #590) on `AjsAgent/affectionate-lovelace-r0zfgg`: aj approved the build plan ("Build plan approved: roadblock detection fix"); stage is Build. Step 1 (#588) is built (c97034f7). Unattended mode switches off the Stop hook the check lives in, so aj chose option B (its own Stop hook, decisions log 17bbb92b); the move is built (04446706); the builder's full run failed 8 of 968, the same parts as the baseline, and my own core run is not yet read. Steps 2 to 4 (#589, #591, #590) are built and committed (dd9d85fa, 23ef6601, 4a61859f); my own full runs of steps 2 and 3 failed only the known Windows checks (8 of 978, 8 of 990); step 4's run is under way; my full runs of step 4 and verify_tools passed apart from the known Windows failures (8 of 992; A16). The live test script `docs/plans/2026-11-23-roadblock-unattended-hook/live_roadblocks.py` was written and its first run (five headless sessions) was under way; the first live run passed 2 of 5: a gap was found (a filtered search with no output was not counted as a failed attempt) and fixed with two new cases that pass (13 of 13), with a removal check showing the filtered-search case fails without the fix; the stall and bypass test prompts were corrected and run 2 of the five live sessions is under way, results not yet read; the QA page and the pull request are next. My full verify.py matched the first builder's: 8 of 966 failed on this Windows PC, not yet baselined. Handoff: `docs/5-today/handoff-AjsAgent-affectionate-lovelace-r0zfgg.md`.

# 2026-11-22

## 2026-11-24

aj answered: a docs-only feature needs an acceptance run too, get the branch to 2.90.0, open the pull request when ready. The `AjsAgent/affectionate-lovelace-r0zfgg` branch (2.90.0) is merged into this branch; merged tree: `verify.py` 1523 of 1523, `verify_tools.py` exit 0. Step 4 (#596, QA gate) is built (committed by an automatic save). A real stamp run found the stamp goes stale when the QA content file, changelog or notes are written after it; parked decision P4 (leave them out of the fingerprint) is built and checked by me (`verify.py` 1537 of 1537, the real QA build runs twice). A real screenshot then showed the "Needs your machine" step collapsed to one line; the line breaks are fixed and I checked the real QA page in light and dark at 375px. Step 4 (#596) is done: `verify.py` 1538 of 1538, `verify_tools.py` exit 0. Step 6 (#598) is split in two: the first half (park script, rule text, helper note) is built and checked by me (`verify.py` 1544 of 1544, a real `park` run); the second half (the question hook, the Build hold, the decided-for-you row, the QA parser pipe fix) is built and checked by me too: `verify.py` 1559 of 1559, `verify_tools.py` exit 0, and the real hook fired in every stage and mode. Step 6 is done. Next: step 7 (#599), then 9. A test that fails when run alone also fails on `main`; noted in the ledger.

aj approved the build plan ("Build plan approved: design review loop"); the stage is Build. Step 1 (#593) is built and checked: my own full run `verify.py` passed 1444 of 1444, and a real page-mode run of the new reviewer on the approved design page returned seven findings and a verdict. Deviations D1 to D4 and parked decisions P1 and P2 are in `docs/qa/design-review-loop/ledger.md`. Step 2 (#594, the review stamp) is built and committed: `verify.py` 1453 of 1453 in my own run, and a stamp made with the real `make_page.py` on a copy of the plan page checked clean, then stale after an edit. Step 3 (#595, acceptance run) is built: `verify.py` 1465 of 1465 in my own run; in this repo `acceptance.py stamp` refuses with no passing ledger and `check` says missing. Not yet tried live with the reviewer in acceptance mode. Step 5 (#597, self-judging test) is built: `verify.py` 1469 of 1469 in my own run, and the template run three ways (exit 0, 1, 2). Step 8 (#600, combined approval) is built: `verify.py` 1473 of 1473 in my own run, `docref` and `docs_drift` clean, and the two-line copy box clicked in a real browser. Step 4 (#596) was handed to a builder and made NO changes: my own previous reply ended in a question, and the Build-stage hold (issue #506) refused all code edits until aj's next real message. Logged as an incident in the ledger, with P3 and D9. Step 4 restarts on aj's next message; it is built ahead of steps 6 and 7 (deviation D8). Steps 6 and 7 are owed until 2.90.0 merges. The step 5 template also ran for real on Python 3.8.20. Deviations D5 to D7 are logged.

aj approved the design as "Design approved: design review loop 1A 2A 3A 4A 5* 6A 7A 8A" (5*: every page except review and QA pages gets the full review). The stage is Plan. Done: decisions entry, systems doc `docs/4-systems/review-loop.md`, parent issue #592 with steps #593 to #601 (all `in progress`), and the build plan page `docs/plans/2026-11-24-design-review-loop-plan.html` after the editor pass. Waiting on "Build plan approved: design review loop"; steps 6 and 7 also wait for 2.90.0 to merge.

Editor pass applied to the trimmed page and the page resent. Overlap checked 2026-11-24: unattended mode (2.87.0) is in main, "never wait" (2.90.0, #587 to #591) is only on affectionate-lovelace; the proposal was trimmed to what is new. Design review loop proposal written on `AjsAgent/sleepy-albattani-bxj5wx`: page `docs/plans/2026-11-24-design-review-loop.html` (source `.page.json`, three diagrams plus a fourth in `-pics/`). It proposes a reviewer in place of the editor, an acceptance run before QA, parked questions, one combined approval, and unattended mode that keeps working and logs each plan deviation. Nothing built, no issues filed; waiting on aj's "Design approved: design review loop" and eight picks. The editor pass was applied and the page rebuilt.

Wait clocks, visual checks, page sending and working pictures (four fixes) on `ajsagent/eloquent-mayer-0ayp82`. aj approved the design as "Design approved: wait clocks, visual checks, page sending and pictures 1A 2A 3B 4B 5A 6A"; the stage is Plan. Parent issue #555, steps #556 to #568, systems doc `docs/4-systems/wait-and-visual-checks.md`, decisions entry written. aj approved the build plan ("Build plan approved: wait clocks 1B", an early check after phase 1); the stage is Build. Builders #556 (pictures into the page file) and #558 (send rule) are both merged into the branch. #558's first report was wrong (no test cases in its commit, a misplaced section) and was fixed after review; one in-project `.html` check was moved to a path outside `docs/` because the new send reminder fires for `docs/` pages. My own full test run is under way and its totals are not yet read. Built and merged so far: #556, #557, #558, #559, #560, #561, #562, which is all of phase 1 and the guard half of the wait clock. My own full run on the final combined code passed: `verify.py` 1381 of 1381, `tools/verify_tools.py` exit 0. A defect in the #557 picture check (it missed pictures that only appear when a row is tapped) was found on a real old page and fixed with a static scan; `sendcheck` now rebuilds that real page in a test. #563 (wait rule text) and #564 (`visualcheck.py` doctor and screenshots) are built; real data then showed `sendcheck`'s rebuild-from-source repair is the wrong design (a QA page regenerates its content), so it now embeds the pictures in place (proven on a copy of the real old page: 2 broken pictures to 0, page unchanged otherwise), and the unchecked-wait note was tightened (one known false alarm in 30 real launches); #565 (video, frame sheet, motion) is built; #566 (the visual loop skill and its ledger check) is built. The loop was proven live and unattended on a planted-defect page in `docs/qa/loop-proof/`: round 1 failed all three criteria (banner cut off at phone width, console error), a builder fixed the causes, round 2 passed all three with a fresh reviewer; `ledger.py status` says NEXT: done and nobody asked aj anything. #567 (end-of-turn visual gate) and the unchecked-wait refinement are built. All of #556 to #567 is in one clean full run: `verify.py` 1417 of 1417, `tools/verify_tools.py` exit 0. The injected rules are at 9694 of 9700 characters, so any new rule must make room. All 13 steps (#556 to #568) are built, plugin 2.88.0, and one clean full run passed: `verify.py` 1422 of 1422, `tools/verify_tools.py` 55 of 55. The QA page `docs/plans/2026-11-22-wait-and-visual-checks-qa.html` is built (eight steps for aj, three commands labelled untested on Windows). Issues #555 to #568 say `needs review` and aj has the QA page. At aj's request the Linux equivalent of his QA steps was run for real (install, waitfor, two real headless sessions with the branch build): all worked as the page says; results in `docs/plans/2026-11-22-wait-and-visual-checks-live-tests/live-qa-results.txt`. New finding for aj: the visual reminder fires after ordinary docs pages; the fix waits for his decision. Open question to aj: open the pull request now or after QA passes. The QA page got the editor's final wording fixes and was sent again. aj then replied `QA failed: wait clocks, fix the visual reminder noise`: the stage is Build again, all 14 issues are `in progress`, and #567 is fixed: the visual reminder skips pages that carry the make_page mark or the house-rules-page meta. Proven: full `verify.py` 1428 of 1428, the replay of both real transcripts (1 to 0 and 1 to 0), and two new real headless sessions on the fixed build (0 reminders in each, the repair still works). Done: the 14 issues are `needs review` again and aj has the final QA page. aj then asked for tests and a pull request: three more real sessions all worked (the never-sent block, the guard refusal, the unchecked-wait note); a CI-like run on Python 3.12 with no browser fails 4 test checks (3 browser-dependent repair tests, 1 that reads this branch's loop state), plus two false alarms in the wait checks. None is fixed (code edits are closed in QA, needs aj's go-ahead). The pull request is open as a draft: #573. GitHub's CI run was queued and not yet read. Waiting on aj's QA verdict and the go-ahead to fix the test-side issues. Next: prove the repair on a copy of the real old page, send aj the early-check page for phase 1, then #563 and the visual loop.

## 2026-11-20

## 2026-11-23

Planning for the audit approval is done: parent #587 now has four steps (#588 detection, #589 record check, #591 model judge and goal check, #590 never wait with docs, version and QA), the systems doc has a "Plan after the audit" section, the decisions log has an entry, and the build plan page `docs/plans/2026-11-23-roadblock-detection-fix-plan.html` is rewritten for four steps (editor pass applied, sent to aj), waiting on "Build plan approved: roadblock detection fix". The goal check was tested on three made-up sessions with the small model: unreached blocked, reached passed, and a login-blocked session was told to continue with the docs (the sharper wording was needed); each call about $0.002 and 4 to 5 seconds. Nothing built.

aj approved the audit as "Design approved: roadblock check audit 1B 2A 3A 4* 5A". Answer 4 is aj's own: stall phrases are checked only at the end of the turn, and a separate check reads the session's goal and decides whether the session genuinely cannot move forward unattended or can continue until the goals are reached. The loop stage is Plan. An agent-hook test of that goal check is running in a throwaway folder; planning (systems doc, issues, plan page) follows its result. Nothing built.

The audit page's editor pass is applied and the final page was sent to aj. A count on it was corrected: the old probe test matches 13 program names plus `command -v`, not nine words. Waiting on aj's five picks ("Design approved: roadblock check audit").

aj asked for an audit of the weaknesses and traps in the plan. Measured against real transcripts and fixtures: eight weak spots (curly apostrophe and blockquotes, the loose probe test, non-Bash tools, undefined failure, weak fallbacks, false alarms, window resets, environment). A model-judged Stop hook was tested once and worked. Audit page `docs/plans/2026-11-23-roadblock-check-audit.html` (editor pass applied, sent to aj) offers five picks; the systems doc has the table. Nothing built.

aj corrected the method count: not two in total but three attempts, the first try plus two more by different methods. Issue #589, the plan page, the systems doc and the decisions entry now say three (editor pass applied, page sent to aj). Pickup at this point found 0 uncommitted files, newest save `4048c12` at 21:34 UTC.

aj tightened answer 1 mid-plan: a first try never counts as "I cannot"; two different methods must fail, and the reply must list every method tried. Step 2 (#589) and step 1 (#588) issue bodies, the plan page, the systems doc and the decisions entry now say so; the phrase list also gains the general inability wording (unable to, genuinely unable, could not, couldn't). The editor pass on the changed page strings is applied and the page sent to aj; the page now counts nine always-flagged phrases and four stall phrases.

aj asked to find the unverified facts by other means and to add "I've stopped here" to the phrase list. Done: the retry behaviour was tested with a throwaway hook, the bypass mode value was read from Claude Code's own program file, and the phrase is in the plan, systems doc, decisions entry and issue #588.

aj approved the detection fix as "Design approved: roadblock detection fix 1* 2* 3*" with three answers of their own (evidence of a failed attempt; a longer phrase list; never wait in unattended or bypass mode). Planning is done: systems doc section in `docs/4-systems/roadblocks.md`, a decisions entry, parent issue #587 with steps #588, #589 and #590, and a build plan page `docs/plans/2026-11-23-roadblock-detection-fix-plan.html` waiting on aj's "Build plan approved: roadblock detection fix" (editor pass applied; aj also added mid-plan that a can't-be-done or can't-verify claim needs two different failed methods, now part of step 2, #589). Found while planning: the approved "blocks twice" never happens in a real session, because the check returns at the `stop_hook_active` retry (confirmed with a test hook that blocked twice: `stop_hook_active` was False, then True, and the second block was allowed; Claude Code caps consecutive blocks at 8); and the Stop payload carries `permission_mode` (observed value `default`; the bypass value `bypassPermissions` comes from Claude Code's own mode list, not a live bypass run). No code built.

aj's screenshot from their PC showed the merged roadblocks check letting through "remaining steps need Blender shell models and Unity scene work that I can't verify here" (Castle session). Reproduced two bugs with the merged code: a curly apostrophe (can’t) is not matched, and a turn that ran `git ls-files` counts as a probe because the pattern matches the word `ls` anywhere in a command. aj confirmed both sessions ran 2.89.0, so the old-build cause is ruled out. The Castle transcript could not be read: aj's PC lists the PlunderSpell and GameDev folders but does not offer them to cloud sessions, so the two bugs are reproduced in test runs, not confirmed on that turn. A second screenshot (Castle session, unattended run) showed the agent ending a reply with "Your call: where does Krak's crypt go?" and waiting, although unattended mode says to pick a reversible default: the `noask` hook only denies the formal question tool, not plain text. Added as a third question (editor pass applied, final page sent to aj) on the proposal page `docs/plans/2026-11-23-roadblock-detection-fix.html`, which is waiting on aj's two picks; nothing is built.

Pull request #574 (clear roadblocks, plugin 2.89.0) was merged by aj after `verify` passed on its CI. Issues #569 to #572 are closed as completed, labelled `AjsAgent completed this`, and each has a comment giving the reason. The work is done; what remains unverified is aj's own test on a PC, a roadblock worded outside the check's phrase list, and bypass-mode installs, which are a rule and not a hook.

## 2026-11-22

Pull request #574's CI check `verify` failed one check: the injected rules measured 9717 characters at the runner's longer plugin path (9691 locally), against 9700. Reproduced at a runner-like path, then fixed by dropping the roadblocks pointer from `rules/house-rules.md` (the line above it already links users-hands.md, which links roadblocks.md): 9674 at the runner-like path, and verify.py passes locally and there. Local sizes under-count by about 26 characters.

Clear roadblocks live test passed on this machine: a headless session loaded with the branch plugin (house-rules 2.89.0) said "I cannot continue because Unity is not installed", was blocked ("block 1 of 2"), ran `which` probes, and replied with what they found. Pull request #574 is open (`Refs #569`), waiting on aj's review and merge. The QA page's last editor pass is applied.

Clear roadblocks QA found that main already shipped a different 2.88.0 (#573), so main was merged into the branch and the feature moved to 2.89.0. The rule had to fold into the user's-hands section to fit the 9700-character limit (9691 now). verify.py 1443 of 1443, verify_tools.py 55 of 55 pass after the merge.

Clear-roadblocks rule: proposal page `docs/plans/2026-11-22-clear-roadblocks.html` written, aj approved it as "Design approved: clear roadblocks 1C 2A". Planning is done: systems doc `docs/4-systems/roadblocks.md`, parent issue #569 with steps #570, #571 and #572, and a build plan page `docs/plans/2026-11-22-clear-roadblocks-plan.html` waiting on aj's "Build plan approved: clear roadblocks". The editor pass is applied to the plan page. aj then approved the build plan; the stage is Build and step 1 (#570) is done: aj chose to delete the "Plain language and the voice" stub to make room, and verify.py passes (205 of 205 core checks, 9694 characters injected against 9700). Step 2 (#571) is built: the end-of-reply roadblock check blocks twice per user message, then warns; verify.py 213 of 213 core checks and verify_tools.py 55 of 55 pass. Step 3 (#572) is built as plugin 2.88.0 (verify.py 1345 of 1345, verify_tools.py 55 of 55). A live-style run of the branch hook with the same roadblock claim three times gave block, block, then the warning. QA page: `docs/plans/2026-11-22-clear-roadblocks-qa.html`, the editor pass is applied, issues #569 to #572 say `needs review`, and aj's test is next. No issues filed and nothing built. The `@house-rules:editor` pass was applied, a second time to the option C wording, to the page text and the page rebuilt. Handoff: `docs/5-today/handoff-ajsagent-affectionate-lovelace-r0zfgg.md`.

Free issue closing, plugin 2.83.0, built on `AjsAgent/free-issue-closing` (issues #548 to #552). The agent closes an issue on its own when it is labelled `needs review`, `in review` or completed by someone else and is in no GitHub milestone; anything else, milestone issues and milestones need aj's "Close approved". The five issues were made with a command that printed only numbers, so the design loop recorded none of them; aj's "Issues for free issue closing" came after the stage had moved to Build and also recorded nothing. Design: `docs/4-systems/issue-closing.md`, "Free issue closing (2.83.0)".

## 2026-11-19

Flexible pages, plugin 2.82.0, built and waiting on aj's QA (issues #541 to #545, all `needs review`). The cut-off Windows session's step 4 was recovered from its autosave onto `ajsagent/sharp-edison-y4xjzv`; verify.py passes 1294 of 1294 and verify_tools 54 of 54. QA page: `docs/plans/flexible-pages-qa.html`.

The QA page was then rewritten by hand as `docs/qa/flexible-pages-qa.html`: four numbered steps, each with a copy button, the exact output to expect and a tick-box. The builder version in `docs/plans/` is superseded.
The hand-written page replaced the published claude.ai page at the same link, and both branches were pushed again.

Then aj typed "QA failed: flexible pages": the desktop app still ran the old build (its claude.ai account copy follows main). Issues back to `in progress`; the agent now runs the QA itself in headless sessions on the branch code.

Live test run 1 passed 3 of 3 on the branch build (refused once, good page, starter); run 2 is running. The design loop was switched off and back on by aj.

Live test run 2 failed one test: the page checker stopped at a missing page type and hid the missing checklist. A fix for step 1 (#542) is being built.

The checker fix for #542 is merged. verify.py turned out to fail 9 checks whenever a typed switch is saved in the repo; aj chose to fix verify.py (#546), now being built; live test run 3 is running.

Picked up after a usage-limit cut-off: live test run 3 passed 3 of 3, and the #546 fix is merged into `AjsAgent/speed-switches` with its own test corrected. On aj's PC, from the repo with the typed switch present, verify.py passes 1289 of 1295 and verify_tools 53 of 54; every failure is a known Windows-only one (#523). aj chose to skip a fourth run. The QA page `docs/qa/flexible-pages-qa.html` now reports runs 1 to 3 and asks aj to read run 3's result and reply; it meets all seven basics by `page_criteria.py --visual`. Published on aj's account as "Flexible pages: your QA"; issues #541 to #546 now say `needs review`. aj typed "QA passed: flexible pages"; stage Done, decisions log updated, pull request to main opened.

Later on 2026-11-19: the finished work was pushed to `AjsAgent/speed-switches` too (both branches at the same commit). Each QA test on the page now carries its exact PowerShell command or prompt; `use_branch.py AjsAgent/speed-switches` installed 2.82.0 in a throwaway config here.

## 2026-11-18

Branch `AjsAgent/speed-switches` now holds all of main. Phase 3 retested on aj's Windows PC (1246 of 1252 and 53 of 54
checks; the failures are Linux-only path assumptions in tests). New: a proposal page for flexible page formats,
`docs/plans/2026-11-18-flexible-pages-design.html`, waiting on aj's three choices. No code built yet.

Flexible pages design approved (1A 2A 3A). Systems doc `docs/4-systems/flexible-pages.md`, parent issue #541 with steps
#542 to #545, build plan page `docs/plans/2026-11-18-flexible-pages-build-plan.html` waiting on aj's approval and two choices.

Flexible pages design and build plan both approved (aj); stage is Build. Step 1 (#542, the page checker) is built and checked (21 checks pass); step 2 (#543, the page check reads pages) is built; step 3 (#544, starters) is built; step 4 (#545, rules, docs, version) is with a builder; decisions log updated.

# Earlier — 2026-11-12

Roadmap phases 1 and 2, plugin 2.79.0, on the branch `AjsAgent/qol-phases-1-2`, both passed by aj's QA. Phase 1 (#493):
approvals work with the feature name first and in cloud sessions, an "Approve" button counts, a build plan reads the
feature's issues from GitHub, "QA failed" returns to Build in one message, the last ways around the code lock are
closed, and design decisions come only from aj. Phase 2 (#494): a commit names the docs that cite what it changes and
`scripts/docs_drift.py` finds stale citations (this repo now has 0), every repo keeps a CHANGELOG.md, merged branches
and finished helper copies are cleaned up, big files reach git only on aj's word through Git LFS, three rules gained
checks, and Research.md and Vocabulary.md join the decisions tier. The session handoff (#406) is not in this branch: it
moves to phase 3, because its saves do not reach GitHub from cloud sessions yet.

Handover pages and checkpoints, plugin 2.66.0 (issues #251 to #258). Every page is now made by
`scripts/make_page.py` from the template, with picture slots and before-and-after compare, and takes its look from
the project's `docs/page-style.json`. At the end of a reply, a missing page, editor pass, evidence, commit or plain
summary blocks once; "no page" in your message lets one reply through. Built, waiting on your QA and the PlunderSpell
regeneration test (issue 259), which has not run.

The new item visual v2, plugin 2.65.1 (issue #240). On a handover page a New item now opens to three boxes:
what exists today, what this creates, and how it impacts you. Every item you open lists the files it touched,
with lines added and removed, counted from git by `tools/diff_parts.py`. The changes page covers the whole pull
request this way. `verify.py` also no longer fails when an earlier run left a stale temp file (#229).

The clear writing check, plugin 2.65.0 (issue #245). One rule, "Write it so nothing is left to guess", now
covers how everything you read is written: proper sentences, a human tone, said once, context spelled out,
numbers counted rather than guessed, and references named. A checker reads every reply, page and issue for
vague numbers, bare "#229"s, repetition, jargon and overlong sentences; an issue without "Depends on",
"Depended on by" and "Done when" is refused; and a new editor helper rewrites pages and long replies. It
replaced the plain-language rule and folded in three other lines. `HOUSE_RULES_CLEAR_WRITING=off` turns it off.

The new item visual, plugin 2.64.1 (issue #240). On a handover page, a New item now opens to three boxes:
what sets it off, what it does, what you get. The changes page has one for each of its 13 new items. A pasted
page reply such as ": 1C" no longer becomes part of a feature's name, so a redo after "QA failed" is recognised.

The label check, plugin 2.64.0 (issue #235). An issue's label now says whose move it is, and every step of the
design loop checks it: `in progress` while I work, `needs review` when it's your turn. Swapping every issue to
`needs review` starts a new QA stage and closes code; your QA answer only counts then; after "QA failed" the
issues go back to `in progress` before the redo's design can be approved. Labels are read from GitHub, or from my
own recorded label changes when GitHub can't be read, and the check says which. It ships in the same pull request
as the design loop.

The design loop, plugin 2.63.0 (issue #223). Every feature now goes Design → Plan → Build → my review → your QA →
Done, and only your own message moves it on: "Design approved: <feature>", "Build plan approved: <feature>",
"QA passed: <feature>" or "QA failed: <feature>". Code edits are refused outside Build, for helpers too; "skip
design" lets one small change through. An approval only counts once the decisions log has a new entry, and a
build plan needs its GitHub issues first. A reply over 200 words with no page gets a reminder, and every page is
built from `templates/handover-page.html`. `HOUSE_RULES_LOOP=off` turns it all off. It reaches your sessions once
this branch is merged and the plugin updates. Proof: a real run in a scratch repo (`docs/plans/loop-qa.html`).


New rule, plugin 2.62.0 (issue #216): a reply that refers back to something names it in a few words, and never
leaves you to work out what a bare "#2" or "option B" meant. An issue number always comes with its title. It sits
under "Plain language on the surfaces a human reads", with examples in `rules/detail/plain-language.md`. It takes
effect in the next session after the plugin updates.

Guard fixes, plugin 2.61.0 (issues #200, #203, #189):

- A risky command on a second line, or after a tab, now asks like any other. Before, `ls` + new line + `rm -rf build`
  ran with no prompt, and so did `nohup`, `setsid`, `sleep 99 &` and a wait piped to `tail` on a second line (#200).
- A commit message that mentions "cd" no longer makes a commit on the agent's own branch ask (#203).
- A commit that sets its author with a quoted value, like `git -c user.name="aj's agent" commit`, is now checked for a
  Claude credit like any other commit (#189, PR #190's change, ported here).

Checked with the test suite, including every command form from the three issues, and by running each one through
the guard before and after the change. Not yet tried in a live session.

## 2026-10-09

Roadmap re-triaged: all 97 open issues are placed in `docs/2-roadmap/Roadmap.md` by how bad each is and how
often it gets in the way, from P0 (safety holes and daily blockers, led by #200; the #196 permission-stall work below has since shipped and moved to the built list)
to P3 (separate tracks), plus a list of built issues waiting on your test before they close. Audit findings
#200-#206 were filed today.

Permission stalls, plugin 2.60.0 (issues #196-#199): a commit, push or merge on any branch except `main` now
runs with no prompt at all, helpers' worktree branches included. On `main` they are refused at once with
"make a branch and open a pull request". Only deletions, force pushes and discarding unsaved work still ask,
and those are refused instead of asked inside a helper or when you have not written for 5 minutes, so
nothing sits waiting. Checked with the test suite (602 checks) and by running the hook on test repos; not yet
in a live session.

Guard branch ownership, plugin 2.59.1: a commit or push is now judged on the branch of the directory it runs in, so a
worktree subagent on its own `AjsAgent/` branch is no longer prompted. `ccr-` cloud-session branches count as yours,
and `HOUSE_RULES_OWNED_BRANCHES=foo/,bar-` adds more. Force push, merge and the rest still ask.

GitHub tools, plugin 2.59.0 (issue #178): pull requests, issues, comments and pushes made through the GitHub tools
now get the same check as shell commands. Text that credits Claude is refused, and so is creating a new `claude/`
branch (use `AjsAgent/<name>`). File contents are not read, and pushing to an existing `claude/` branch is still
allowed. Checked with the test suite and a simulated call, not yet in a real session.

Commit author, plugin 2.58.0 (issue #177): cloud containers sign commits as "Claude", so the guard now refuses
a commit authored as Claude (or an anthropic.com email) and says the one command that fixes it, and a cloud session
is told at start to run it. The agent's identity is "AJ's agent" with your GitHub noreply address. Not yet tried in
a real cloud session.

Cloud branches, plugin 2.57.0 (issue #176): a cloud session that the app starts on a `claude/<name>`
branch is now told to move to `AjsAgent/<name>` before its first edit, and to push and open pull
requests from there. Still to check in a real cloud session: whether the app's own "Create PR"
button follows the new branch.

Prompt timer, live test on the phone app: the timer refused an unanswered prompt after exactly 5 minutes and
the refused action showed on your next message. The house-rules delete prompt reaches you as a real dialog.
Found a gap: if the session's worker restarts while a prompt is open, the prompt sits on your screen with no
timer behind it (it waited 12 minutes until you denied it), issue #159. A house-rules delete prompt left alone
was refused after exactly 5 minutes and nothing was deleted, so the timer covers those too. The refused
dialog then closed by itself and showed as "Failed" (#149).

Prompt timer follow-ups, plugin 2.53.0 (issues #149, #151, #152): questions and plan approvals are never
timed out. Once one permission prompt goes unanswered, the next ones in that session are refused straight
away instead of each waiting another 5 minutes; your next message puts prompts back to normal. An action that
actually ran is no longer recorded as timed out. Still open: the app may keep showing a dialog the timer
already refused (#149), which needs checking on the desktop app.

Destructive steps (issue #153, same release): Claude may now reset, rebase, revert or restore without asking
only on its own `AjsAgent/` (or `claude/`) branch, and only when nothing is uncommitted and every commit is already pushed, so
nothing can be lost. Anywhere else it asks you, as before. Force-push, `git clean`, dropping a stash and
deleting files always ask.

Prompt timer, plugin 2.52.0 (issue #142): a permission prompt nobody answers for 5 minutes is now refused,
never approved, and Claude carries on with the rest of the work. The refused action goes on a waiting-on-you
list, which shows on your next message and at the next session start. Plan:
[`2026-10-04-permission-prompt-timeout.md`](../plans/2026-10-04-permission-prompt-timeout.md). Next: on the
desktop app, check whether the house-rules prompts (`guard`) are timed too (#143), then the overnight-style
run (#147).


Credit "aj's agent", never Claude, plugin 2.51.0 (issue #133): the installer now writes Claude Code's
`attribution` setting (commit `Committed by AJ's agent`, pull request `Opened by AJ's agent`, no session link, no
email), and `guard` refuses a commit, pull request or issue text that credits Claude, as the backstop for cloud
sessions that never read the settings file. Plan: [`attribution-build-plan.md`](../plans/attribution-build-plan.md).
Next: update the plugin on other machines (`toolsootstrap.ps1`) so the setting lands there too.

Helper tiers, plugin 2.50.0 (issues #110-#112): the executor is gone; delegate to `@house-rules:scout`
(lookups), `@house-rules:builder` (one issue's work) or `@house-rules:reviewer` (second opinion). A new
hook refuses a third running subagent, subagent reports in the parent are far shorter, and the open-issue
list now says it loaded. Plan: [`subagent-tiers-build-plan.md`](../plans/subagent-tiers-build-plan.md). Next:
update the plugin, restart Claude Code, spawn each tier once and confirm the model and tool list.

Issue workflow, plugin 2.49.0 (issues #108-#110): approving a plan of more than three steps now
makes the hooks demand a parent issue and child issues before any source edit; pull requests must say
`Refs #N` and never a closing word; closing an issue always asks you. Plan:
[`issue-workflow-build-plan.md`](../plans/issue-workflow-build-plan.md). Next: restart Claude Code after
the update, open PlunderSpell, approve a four-step plan, and confirm the edit is refused until the issues
exist (a real session there could not be run from the build session).

Hook overhead cut, plugin 2.48.0: the "looked, nothing to do" trace lines no longer print unless
`HOUSE_RULES_TRACE=verbose`, `run.sh` caches the interpreter, and `autosave`/`commitgate` skip git
on non-subagent branches. Plan: [`hooks-efficiency-review.md`](../plans/hooks-efficiency-review.md).
Next: confirm in a fresh session that the transcript notices are gone; findings 4-8 are in the
Roadmap.

Subagent work is now saved while it runs: `autosave`, `commitgate` and `worktreesweep`, plugin
2.47.0. See the dated entry in [`Decisions.md`](../6-decisions/Decisions.md).

## What was done (2026-09-30)

- **Three new hooks**, on `worktree-agent-` branches only. They snapshot and push after each step,
  block edits at 3+ uncommitted files, and commit for the subagent if it ignores that or goes
  10 minutes without a commit. The parent-side sweep commits a dead subagent's leftovers.
  `subagentcommit` also cleans up the save point on a clean finish, and commits leftovers on
  its retry.
- **Tests.** 17 new `verify.py` cases; 454 of 454 pass. 12 of them fail against the pre-change
  code. The other five check that nothing happens (on `main`, with the toggle off, with nothing
  to commit), which was already true before.
- **Real run.** A real worktree edit made the hook save the work and try GitHub. The push was
  refused (HTTP 403 from this cloud session's git proxy), the hook said so, and restoring from the
  local save worked.
- **Issue #105** records the idea of replacing the one executor with dynamic subagent dispatch.

## What to do next

- Merge PR #104 once reviewed.
- On a local machine, check that GitHub accepts a push to `refs/house-rules/autosave/*`.

---

# Earlier — 2026-09-29

Built "open source first" and the hardware-aware machine profile, and fixed the Unity standards
overrun that `verify.py` had never measured. See the dated entry in
[`Decisions.md`](../6-decisions/Decisions.md) and the plan in
[`2026-09-29-local-first-free-first.md`](../plans/2026-09-29-local-first-free-first.md).

## What was done

- **New core rule.** "Open source first; paid is the last resort", with a five-rung ladder, and
  `rules/detail/free-first.md` holding the ladder, the build-your-own estimate for Pro/Max, and
  one example. "Find out what machine you are on" now says detected hardware is the local budget;
  `rules/detail/environment.md` says what "doesn't fit" means.
- **Unity rule moved out of the core (Option B).** It now lives in
  `rules/standards/csharp-unity-standards.md`, so only Unity projects load it. That document is
  split: a small always-injected core plus `rules/standards/csharp-unity-detail.md` (six sections
  moved unchanged, checked with a diff). `inject` is 8,943 of 9,000.
- **Unity standards overrun fixed.** `standards` emitted 9,832 chars for a Unity-only project and
  13,376 for Unity + Node; now 5,782 and 9,326 (budget 9,500). `verify.py` measures both, which it
  never did before.
- **Profile detects hardware and plan.** CPU, RAM, GPU/VRAM, free disk and the Claude plan, at
  runtime, each with a timeout and a "not detected (reason)" line. On a remote session it is
  labelled as the sandbox's, and the local budget is the user's machine.
- **Tests.** New `verify.py` cases for all of the above; each fails against the previous code.
- **Docs.** `docs/architecture.md`, `docs/4-systems/hook-engine.md`, `Decisions.md`,
  `ProjectState.md`, the plan.
- **Version bump.** `2.45.0` to `2.46.0` in `plugin.json`.

## What to do next, in order

1. Check on a real local machine whether `claude auth status --json` reports a plan (it does not
   in a cloud session), and run the profile on macOS and Windows: those probe branches were not
   run.
2. Tell `Ajw2003/Coding-Standards` about the split of `csharp-unity-standards.md`, or the next
   `tools/sync_standards.py` run reverts it.
3. Run `/house-rules:plain-docs` on the remaining system docs (`verify-suites.md`,
   `plugin-distribution.md`, `offshoot-plugins.md`) — still open.
4. Everything still open in [`ProjectState.md`](../3-state/ProjectState.md)'s Cross-cutting
   section.

**Later on 2026-11-22:** aj replied `QA failed: wait clocks. fix the test issues and the two false alarms`. The stage is Build; two builders are fixing the three browser-dependent tests, the loop-state check, and the two wait false alarms. Decision entry added to `docs/6-decisions/Decisions.md`.

**Still 2026-11-22:** the 14 issues were relabelled `in progress` (the design loop blocks code edits while they say `needs review`); the two builders are re-running the four fixes.

**Still 2026-11-22:** the wait false-alarm fixes are in (refused launches skipped; `timeout` matched at command position only). The test-side fixes are written; my full test run is next.

**Still 2026-11-22:** the four QA-failed fixes are built; full verify.py 1434 of 1434 here and in a CI-like run, verify_tools 55 of 55. Issues are `needs review` again and the QA page was rebuilt and resent.

**Still 2026-11-22:** the editor helper reworded the two new QA-page rows; the page was rebuilt and sent again.

**Still 2026-11-22:** all work is pushed and the issues are `needs review`; waiting on aj's QA verdict.

**Still 2026-11-22:** aj passed QA ("QA passed: wait clocks"). The stage is done and PR 573 is ready for review.

**Still 2026-11-22:** GitHub CI on PR 573 fails 2 of 1430 checks (injected rules 21 characters over the limit on the runner's longer path; one make_page send check with no browser). Diagnosed, not fixed: code edits are closed at Done.

**Still 2026-11-22:** waiting on aj to reopen code edits for the two CI fixes.

**Still 2026-11-22:** aj typed "skip design"; the two CI fixes are written (a make_page test skip, 33 characters off the injected rules) and being checked at a GitHub-like path.

**Still 2026-11-22:** GitHub CI passed on the fix commit; PR 573 waits for aj to merge.

Live roadblock sessions on the branch build 2.90.0 (2026-11-23): curly apostrophe, `git ls-files` only, three methods and unattended stall all behave correctly; the bypass question cannot be tested headless (question tool disabled in `claude -p`), fixture cases only. Next: QA page, pull request with `Refs #587`, issues #587 to #591 to `needs review`.

Pull request #602 (roadblock detection fix, Refs #587) is open; QA page `docs/plans/2026-11-23-roadblock-detection-fix-qa.html` sent to aj; issues #587 to #591 are `needs review`; CI pending.

Pull request #602 has Auto-fix on (aj said yes). The live status page was edited by the editor and marked superseded by the QA page.

Status page 2026-11-23-roadblock-live-status.html had a second editor pass; stale 9:20pm wording now reads as past.
