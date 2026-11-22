# Changelog

What changed in this repo, newest first. Plain words first, exact detail after.

## Unreleased

Checked the two CI fixes in a copy at a GitHub-like path with a bare PATH: 1426 of 1432 checks pass, 6 skipped, none fail; the injected rules measure 9696 of 9700 there. GitHub's own run on the pushed commit is being read next.

Fixed the two failing CI checks on pull request #573: the clean-page send check now skips when there is no browser, and the injected rules are 33 characters shorter (9721 to 9688 on GitHub's path, limit 9700).

Diagnosed the two failing CI checks on pull request #573 (injected rules 9721 of 9700 characters on the runner; a make_page send check with no browser); not fixed yet, waiting on aj to reopen code edits.

aj passed QA on the wait clocks work; pull request #573 (plugin 2.88.0) is ready for review, waiting on aj's merge.

Recorded that the wait clocks work is pushed and waiting on aj's QA verdict (handoff note and Today updated; no code change).

Reworded the two new rows on the wait clocks QA page after the editor pass (page `docs/plans/2026-11-22-wait-and-visual-checks-qa.html`, rebuilt with `make_page.py build`).

Fixed the four known test-side issues on the wait clocks branch after aj's QA failed: three browser-dependent picture-repair tests now skip when no browser re-check ran, the handover stand-down check runs in a scratch folder, the unchecked-wait note ignores a launch the guard refused, and the foreground-wait pattern matches `timeout` only at command position. verify.py 1434 of 1434, also in a CI-like run without a browser.

Opened draft pull request #573 for the wait clocks, visual checks, page sending and pictures work (plugin 2.88.0, refs #555 to #568). It stays a draft until four known test-side checks are fixed, which needs aj's go-ahead. No code changed in this step.

Tested the wait clocks, visual checks, page sending and pictures work (#555) for a pull request: three more real sessions confirmed the never-sent page block, the guard refusal for a launch with no timeout, and the unchecked-wait note. A CI-like run (Python 3.12, no browser) found 4 failing test checks and two false alarms in the wait checks, recorded in `docs/plans/2026-11-22-wait-and-visual-checks-live-tests/live-qa-results.txt`; the fixes wait for aj's go-ahead. Pull request opened as a draft.

QA for the wait clocks, visual checks, page sending and pictures work (#555) is open again after the visual reminder fix: all 14 issues say `needs review` and aj has the final QA page. No code changed in this step.

Fixed the visual reminder noise from aj's QA of the wait clocks work (#555): pages that carry the page builder's mark or the handover-page meta tag no longer trigger the end-of-turn visual reminder; plain visual files are still checked. Proven by two real headless sessions on the fixed build (0 reminders, down from 1 and 2, repair still works) and a full `verify.py` 1428 of 1428.

QA failed on the wait clocks work (#555) with one item to fix: the end-of-turn visual reminder fired after ordinary pages in both real test sessions. It is being changed to skip pages that carry the page builder's mark or the handover-page meta tag; everything else visual is checked as before. Not released.

Reworded the QA page for the wait clocks, visual checks, page sending and pictures work after a final editor pass, and sent it to aj again (`docs/plans/2026-11-22-wait-and-visual-checks-qa.html`). No code changed.

Ran the Linux equivalent of the QA steps for wait clocks, visual checks, page sending and pictures (#555): the branch installs as 2.88.0, `waitfor.py` times out with exit 3, and two real headless sessions showed the send reminder, a re-send after an edit, and the send hook repairing an old page in place (results in `docs/plans/2026-11-22-wait-and-visual-checks-live-tests/live-qa-results.txt`). Found: the end-of-turn visual reminder fires after ordinary docs pages; the fix waits for aj's decision.

Plugin 2.88.0, ready for QA (#555, steps #556 to #568): wait clocks with a deadline and `waitfor.py`, a guard refusal for background launches with no timeout (switch group `waits`), pictures built into pages with a check and in-place repair before a page is sent, a turn-end check that a made or changed page was sent, `visualcheck.py`, `ledger.py` and the `visual-loop` skill, and an end-of-turn visual check that needs a real capture. Also fixed: the writing check no longer reads inline picture data as prose, and long commands in a page's numbered steps wrap on a phone. Full `verify.py` 1422 of 1422.

The visual loop is built and proven live (#555): `visualcheck.py` video, frame sheets and motion measures (#565), the `visual-loop` skill with `ledger.py` and a 4-round cap (#566), and an end-of-turn visual check that needs a real capture, a ledger check and an image read instead of a keyword (#567). The wait rule is folded into "Nothing fails silently" to keep the injected rules under their size limit. Full `verify.py` 1417 of 1417. Not released: no version bump until #568.

Wait clock rule text and agent prompts (#563) and the first part of the visual capture tool, `visualcheck.py` doctor and screenshots (#564), are built on `ajsagent/eloquent-mayer-0ayp82` (#555). Running the new page-send check on a real old page showed that repairing a page by rebuilding it from its source is wrong for QA pages; it is being changed to embed the pictures into the page in place. Not released.

Fixed a miss in the new picture check (#557): it reported no broken pictures for builder pages whose pictures only appear when a row is tapped, because nothing was rendered at page load. It now also scans the page for any picture source that is not built into the file, and `sendcheck` repairs such a page before it is sent. Found by running the check on a real old page. Full `verify.py` 1381 of 1381.

Phase 1 is built (#559 and #562 added on `ajsagent/eloquent-mayer-0ayp82`, #555): a made or changed page that was not sent is caught at turn end (blocks once), the new `sendcheck` hook repairs a page whose pictures are in a folder before it is sent, and the guard refuses a background launch with no timeout. Full `verify.py` 1377 of 1377. Not released: no version bump until #568.

Phase 1 and the start of the wait clock are built and merged on `ajsagent/eloquent-mayer-0ayp82` (#555): pictures are built into the page file (#556), a copy of the page opened alone is checked for broken pictures (#557), the send rule and the builder's send line exist (#558), the wait numbers live in `rules/waits.json` (#560), and `scripts/waitfor.py` gives every wait a clock and a deadline (#561). Full `verify.py` 1361 of 1361. Not yet released: no version bump until the docs step (#568).

Build started on the wait clocks, visual checks, page sending and pictures work (#555): aj approved the build plan with an early check after phase 1, and builders began #556 and #558. Nothing is merged yet.

Docs only: the wait clocks, visual checks, page sending and pictures design was approved (1A 2A 3B 4B 5A 6A). Added the systems doc `docs/4-systems/wait-and-visual-checks.md`, a decisions entry, parent issue #555 with 13 step issues (#556 to #568), and a build plan page waiting on aj. Nothing is built.

Docs only: measured why pictures on pages break. The page builder links each picture in a `<page>-pics/` folder that is not sent with the page, so a copy of the proposal page opened on its own showed 5 of 5 pictures broken, against 0 of 5 in the repo. Detail is in `docs/plans/2026-11-22-wait-and-visual-checks.html`, Fix 4.

Docs only: a proposal page for four workflow fixes: a one-minute clock and deadline for every wait, an unattended capture-critique-fix loop for visual work, and every made or changed page sent to aj at the end of the turn, and pictures built into each page so they always show. Nothing is built; it waits on aj's six choices. See `docs/plans/2026-11-22-wait-and-visual-checks.html`.

Plugin 2.87.0: unattended mode on one typed line. Type `unattended on` (or `unattended off`, add `everywhere` for all folders) at any point; it turns every other switch off except autosave, refuses questions and prompts, tells the agent to use its own judgment and push only to its own `AjsAgent/` branch, never `main`, and the art-pipeline plugin follows the same line. The switch file is not to be committed while it is on.

Plugin 2.86.0: unattended mode, stage 2. With `HOUSE_RULES_UNATTENDED=on`, a whole-file Write, a commit with a big file and a `Co-Authored-By: Claude` line are allowed with a note instead of refused, so an overnight run is not stopped on a question only aj can answer; attended they refuse as before. The guard's two allow paths now keep a note instead of dropping it. aj approved the relaxations on 2026-11-22.

Plugin 2.85.0: unattended mode, stage 1. The unattended session note now says the "hand it over, then wait" and ask-before rule text is overridden (report the command, take the conservative reversible option); versioncheck says one line and updates nothing when unattended; a guard ask is refused even with `HOUSE_RULES_PROMPT_TIMEOUT=off`.

Plugin 2.84.0: unattended mode. `HOUSE_RULES_UNATTENDED=on` turns every switch off except autosave, refuses guard prompts outright (listed under "Waiting on you"), and the new `noask` hook denies `AskUserQuestion` and `ExitPlanMode`; `tools/overnight.sh` starts a run with it and `ART_PIPELINE=unattended`.

Plugin 2.83.0: free issue closing (#548 to #552). The agent closes an issue on its own when it is labelled `needs review`, `in review` or completed by someone else and is in no GitHub milestone, then labels it `AjsAgent completed this`. Other issues, milestone issues and milestones need aj's "Close approved: #N" or "Close approved: milestone N". The sweep page is no longer required.

- The guard reads every open issue's labels and milestone in one GitHub call and reuses it for 60 seconds, so a mass close makes one call; a failed read refuses the close (#549).
- A completed label the agent added itself does not count (#550, aj's choice 2A).
- `gh api -X PATCH .../milestones/N` to closed is refused until approved (#551).
- 2026-11-20: the closing rule sentence in `rules/house-rules.md` was shortened by 68 characters; CI measured the injected rules at 9709 characters against a 9700 margin.

- 2026-11-19: verify.py no longer picks up switches typed in the repo it tests (#546). Its new check (g) handed the ignore list to the wrong environment copy and failed everywhere; fixed when merged.
- 2026-11-19: live test run 3 passed 3 of 3 on the branch code (`live_flexible_pages-result-3.txt`).
- 2026-11-19: the QA page now reports the three live runs instead of asking aj to test in the desktop app: `docs/qa/flexible-pages-qa.html`, two steps (read run 3's result, send the verdict). aj chose to skip a fourth run. Editor pass applied (plainer wording, issue numbers named).

Plugin 2.82.0: flexible pages (#542 to #545). A page can now take any format as long as it meets seven basics. aj's QA passed on 2026-11-19 (recorded in `.claude/house-rules-loop.json`, c6d2a42); pull request #547 to main opened.

- 2026-11-19: aj's QA failed because the desktop app loaded the claude.ai account's plugin copy (following main), not the branch build `use_branch.py` installs. QA now runs in the agent's own headless sessions on the branch code: `docs/plans/2026-11-19-flexible-pages-live-tests/live_flexible_pages.py`.
- 2026-11-19: the QA page is now hand-written at `docs/qa/flexible-pages-qa.html` (aj found the builder version's steps vague: tests hidden behind identical icons, commands buried, the next-step box showing my step). It sits outside `docs/plans/` because this session's 2.81.2 page check refuses hand-written pages there; aj chose that.
- 2026-11-19: picked up after a usage-limit cut-off; the QA page is `docs/plans/flexible-pages-qa.html` and issues #541 to #545 say `needs review`. verify.py 1294 of 1294, verify_tools 54 of 54.

- A page no longer has to come from the page builder: the page check reads it and, if a basic is missing, refuses once naming each one (#543). Pages with the builder's mark still pass unread.
- `scripts/page_criteria.py` is the checker for the seven basics (#542); its phone-width check is the optional `--visual` flag (first run 2026-11-19: light and dark, no overflow).
- `make_page.py start <type>` gives one optional starter per page type (proposal, build plan, QA, review, art) (#544). Known gaps: a builder `review` page cannot carry a `finding` marker, and `art` passes only because the template's hidden icon sprite counts as a picture.
- Rule text and `docs/4-systems/flexible-pages.md` now describe the basics and the types instead of "every page is built by make_page.py" (#545); plugin bumped to 2.82.0.
- The checker no longer stops at a missing page type; it names every other failed basic too (#542).

Plugin 2.81.2 (2.81.0 plus the desktop QA fixes): phase 3, pick up on any account (#495), and feature switches anywhere (#535). Waiting on aj's QA.

- Work is saved as it happens: on every edit (at most once a minute) and at once when a turn ends or a usage limit cuts it off. On a PC each folder saves under `refs/house-rules/saves/<branch>/<folder id>`, so no folder erases another's save; a cloud session, which cannot push that ref, commits `wip: autosave` on its own branch and pushes it (#527, #528, #529).
- A reply that changed files is sent back once when the branch is not pushed, the handoff note `docs/5-today/handoff-<branch>.md` is older than the newest commit, or `docs/5-today/Today.md` was not touched (#530).
- A new session opens with the handoff note, the newest save's facts and the files other folders' saves hold, each with a restore command it never runs itself (#531).
- `python tools/use_branch.py <branch>` switches the installed plugin to a branch build and `main` switches back, printing what is really installed (#532).
- Any feature group can be switched by typing one line, in any folder, git or not: design loop, pages, builders, issues, writing checks, autosave, house rules; add "everywhere" for the whole machine. The destructive-command guard, the main-branch guard and the credit check never switch off (#536, #537, #538).
- Saves now hold every new file git does not ignore, however it was made; a file over 50 MB is left out and named (aj, 2026-11-17, after a real-GitHub test showed a shell-made file was never saved).
- QA failed on aj's PC (the desktop app saved nothing, silently), so: the save now also runs after the PowerShell tool; every save and pickup decision prints one line saying what it did (`HOUSE_RULES_TRACE=off` hides them); versioncheck compares a branch build with its own branch on GitHub, not main; and a comma ends a feature name in loop lines.
- Desktop retest found the cause: the Claude desktop app runs the house-rules copy added to the claude.ai account (`AppData\Local\Claude-Data\...\rpm\...`, following main), never the copy `tools/use_branch.py` installs. With that account copy switched off, 2.81.1 saved and pushed from the desktop app. The version check's mistaken update request for that copy is filed as #539.
- 2.81.2 (tested: 1253 of 1253 checks, install from GitHub printed 2.81.2 at 8ab0039). At the end of a reply with nothing new to save, the line now says your work is saved, with the file count and save time, instead of only "nothing changed"; and the pickup note asks Claude to open its first reply with one line saying what it picked up, since the desktop app shows no session-start notices (aj, 2026-11-17).
- CI fix for #540: the session-start rules text is back under its 9,700-character limit (the added save-and-pickup sentence in `house-rules.md` was cut; `rules/detail/commit-branches.md` still holds it), and the committed loop state is `done` after aj's QA pass, so the handover checks no longer see an unfinished QA stage.
- QA steps for aj's PC as 13 step cards in `docs/plans/2026-11-17-phase-3-qa-steps.md`.
- Fixes: `verify.py --only <text>` (#44); agent frontmatter fields no longer forbidden (#46); no leading `&` in handed-over commands unless PowerShell-only (#137); a warning when Python is missing for two checks (#205); a merged phase pull request lets its step issues close (#520); the docs-tiers note offers instead of orders (#521); switching to a new owned branch and committing in one command is allowed (#522); the guard counts lowercase `ajsagent/` branches as the agent's (#528); a flaky approval check fixed.
- Flexible pages approved (aj, 2026-11-18, 1A 2A 3A): the systems doc `docs/4-systems/flexible-pages.md`, issues #541 to #545 and a build plan page `docs/plans/2026-11-18-flexible-pages-build-plan.html`; no code yet.
- A proposal page for flexible page formats (any format that meets seven basics, optional starters per page type): docs/plans/2026-11-18-flexible-pages-design.html (not built yet; waiting on approval).
- A proposal page for creating issues on repos you own without a permission prompt: docs/plans/issue-create-no-prompt.html (not built yet; waiting on approval).

Plugin 2.80.0: speed switches (#524, #525).

- Two switches aj types in chat: "design loop off" / "design loop on" and "builders off" / "builders on", saved for the repo in `.claude/house-rules-mode.json`; `/house-rules:mode` shows them. A switch that is off also leaves its rule text out of the session, so the model stops following it. A switch counts only when typed as its own sentence or line, never when quoted. Every model starts full; there is no Fable default, because hooks are not told the model at session start.
- aj's approvals always move the stage: missing issues, labels, a decisions-log entry or a slightly different feature name become a to-do for the agent in that turn, never a refusal. With the design loop off, closing an issue no longer asks for QA records the loop never kept (#515).
- A foreground command that waits in a sleep loop, or with `timeout` over 60 seconds, is refused and pointed at run_in_background.
- The rerun limit counts the same command on the same code: any code change, committed or not, allows two more runs, and a different command is counted on its own. Editing only the test script or docs does not reset it.
- Live tests in real headless sessions (`claude -p --plugin-dir`, installed plugin switched off for each run) passed 5 of 6; they found that a quoted "design loop off" flips the switch and that hooks cannot see the model at session start, so Fable starts full. Results in `docs/plans/2026-11-12-speed-switches-live-tests/`.
- A delete whose folder does not exist is refused on Linux instead of slipping past the guard: `_delete_refusal` now treats git failing to start there (`OSError`) like any other unanswerable check (CI case 81). The same case now expects a foreground wait loop (sub-case 7b) to be refused with the run_in_background hint.
- Fixed after phase 2 QA: the two-repo note works with Windows paths, and the drift check no longer counts history (dated log lines, deleted files) or shell variables (#517, #518). This repo's docs now have 0 out-of-date citations.

Plugin 2.79.0: roadmap phases 1 (#493) and 2 (#494). The session handoff (#406) is not included; it moves to phase 3.

- Two optional docs sit beside the decisions log: `Research.md` (what was researched, found, and cited) and `Vocabulary.md` (the project's terms); session start never asks for them (#513).
- Three old rules get checks: tunable values hardcoded as bare numbers are reported by harvest (#117), a turn that wrote in two repos is told to file an issue in the other (#301), and every house-rules.md section must map to a check in `rules/checks.json` or be named unenforced (#228; #512).
- Big files go into git only when aj asks: a commit with a file over 50 MB, or inside Library/Temp/obj/Builds/node_modules, is refused unless aj wrote "LFS approved: <path>" and the file fits the LFS allowance (one file at a time); session start names helper worktrees and regenerated folders over 5 GB (#511; `HOUSE_RULES_DISKREPORT=off` turns the report off).
- After a pull request merges, the local copy of its branch and any finished helper worktree are deleted when nothing unsaved goes with them, and the note says what was deleted or kept and why (#510; `HOUSE_RULES_CLEANUP=off` turns it off; nothing is deleted if GitHub cannot be read).
- Docs are named at the commit: a commit's guard message lists each living doc that cites a changed file, and any citation that has drifted (#508; `scripts/docs_drift.py` lists all drift, 27 found on first run).
- Every repo keeps a changelog: session start names a repo without one, a turn that edits files without touching it is sent back once, and a pull request that leaves it unchanged gets a reminder (#509).
- Aj's close line is offered after a merge: after "QA passed" and the merge, "Close as completed: #N ..." is put to aj; the wrong-labels line is said once per set (#507; plugin 2.78.0).
- Design points are only decided by aj: a reply that says "I went with ..." is sent back once, and a reply in Build ending on a question holds code edits until aj answers (#506).
- Design-loop gaps are closed: the old stage file in `.git` is no longer read, a new feature name starts a new feature, and an older branch holds code edits until "Continue from: <branch>" (#505).
- "QA failed: <feature> <what's wrong>" returns the feature to Build with its issues and build plan kept (#504).
- The build plan reads its issues from GitHub: "Build plan approved" lists the feature issue and every open issue saying "Part of #N", falling back to the recorded list with a note (#503).
- The page builder refuses a plan page whose copy-box line the loop would reject, and a bare "Approve" (the Approve button) is read as the one line offered (#502).
- Approvals work in either word order: "Phase 1 design approved 1A" counts as well as "Design approved: Phase 1 1A" (#501).
