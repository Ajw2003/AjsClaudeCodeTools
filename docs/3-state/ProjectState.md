# Project state

Where things actually stand against [`Roadmap.md`](../2-roadmap/Roadmap.md), as of 2026-09-23.

**Headline: ~85%.** Three of four milestones are done against their acceptance criterion; the
fourth (offshoot plugins) ships and verifies but its actual judgment quality is unmeasured.

| Milestone | Status |
|---|---|
| 1. Hook engine | 100% — `verify.py` 368/368 PASS (2026-09-26) |
| 2. Six-tier docs convention | 100% as a mechanism; this repo's own adoption tracked below |
| 3. Offshoot plugins | 50% — mechanism verified, classifiers unvalidated |
| 4. Distribution & install tooling | 100% — `verify_tools.py` 39/39 PASS (2026-09-26) |

## 1. Hook engine — built and verified

What's built: nineteen handlers, dispatched statelessly, each with the fail-mode its rule
requires (`guard`/`guardwrite` closed, `inject`/`standards`/`docstiers`/`versioncheck` loud,
`scope`/`userpromptaudit` unable to erase the prompt, the `PostToolUse` handlers never
obstructing, `handover`/`announce`/`subagentrules`/`verdict`/`audit` open and loud). The
2026-09-22 "rules that actually load" plan (`docs/plans/2026-09-22-rules-that-actually-load.md`,
see its own `## Result`) closed the gap where `inject` emitted 44,506 chars against a proven
10,000-char per-hook limit ([`claude-house-rules/plugins/house-rules/scripts/hook.py:71`](../../claude-house-rules/plugins/house-rules/scripts/hook.py#L71),
`INJECT_CHAR_LIMIT`), added a `SubagentStart` handler that re-injects a subagent-scoped core of
the rules (`hook.py:1886`, `_subagent_core`) since `SessionStart`'s own `additionalContext` never
reaches a spawned subagent, and added a commit-time docs-tier reminder to `guard` itself
(`hook.py:1174`, `_staged_docs_status`) rather than only once per session. What's not built:
nothing against the current rule set — the seven candidate refactors in
[`docs/architecture-backlog.md`](../architecture-backlog.md) are real friction (see Cross-cutting,
below) but none blocks this milestone's own acceptance criterion, which is about behavior, not
code shape.

2.39.0 (2026-09-28, #97) adds the commit rule's obligation half: `handover`'s Stop commit check,
the new `branchnudge` handler, `audit`'s `uncommitted:` line, and a stale-memory preflight
warning in `profile`. Each has `verify.py` cases driving real throwaway git repos. Not
verified live: a real memory file in Claude Code's auto-memory folder, since this machine had none.

2.40.0 (2026-09-28, #89/#91/#92/#93) widens `handover`'s evidence check to impossibility
claims and unreasoned "not checked" disclosures; 0 of this session's 49 real replies trip it. 2.41.0 (#85) adds the verify-a-wait rule
and its `guard` pattern. 2.42.0 (#47) adds "an instruction names its exact input"; group A of
the roadmap is complete. 2.43.0 makes subagents commit as they go, with a `subagentcommit`
hook that sends one back once if it finishes with unsaved work (verified end to end with a
control run). 2.44.0 (group B: #90, #87, #88, #96) adds the parity-inventory and visual-check rules
with `scope`, `delegate` and Stop checks. 2.45.0 (#98) adds "plain summary first" for work reports,
checked at Stop.

2.46.0 (2026-09-29) adds the "Open source first; paid is the last resort" rule and its detail
file, hardware and Claude-plan detection in `profile`, and moves the Unity tools-first rule into
the Unity-only standards (split into a core plus `rules/standards/csharp-unity-detail.md`). That
also fixed `standards` overrunning its budget in Unity projects, which nothing had measured.
Not verified: the macOS and Windows hardware probes, and whether a local claude.ai login reports
a plan in `claude auth status`. 2.46.1 moved the Unity detail file into `rules/standards/` and
Ajw2003/Coding-Standards#2 brought upstream in line, so `tools/sync_standards.py` is a no-op.

2.47.0 (2026-09-30) saves subagent work while it runs: `autosave` snapshots and pushes a
`worktree-agent-` branch after each step, `commitgate` blocks edits at 3+ uncommitted files and
commits if ignored, and `worktreesweep` commits a dead subagent's leftovers when the parent wakes.
Verified in `verify.py` (454/454) and by a real run. Not verified: a push to GitHub from outside a
cloud session, where the session's git proxy refused it with a 403.

2.48.0 (2026-09-30) cuts hook overhead, findings 1-3 of
[`docs/plans/hooks-efficiency-review.md`](../plans/hooks-efficiency-review.md): no-op traces are
silent unless `HOUSE_RULES_TRACE=verbose`, `run.sh` caches the probed interpreter, and
`_autosave_target` reads `.git/HEAD` before any git subprocess. Verified by `verify.py` (478
checks incl. new default-silent, verbose, cache and no-spawn cases) and `verify_tools.py`. Not
verified: the transcript noise being gone in a fresh session, which needs the user to look.
Findings 4-8 of that plan are follow-ups in the Roadmap.

2.49.0 (2026-09-30, #108-#110) adds the issue workflow: `delegate` counts a plan's steps and over
three sets an issue gate, `commitgate` refuses source edits until a parent and a child issue labelled
`AjsAgent created this` (or the older `Claude created this`) are recorded, `guard` denies a `gh pr create` without `Refs #N` or with a
closing word and always asks on `gh issue close`, and a new `issuelist` SessionStart entry lists open
issues. Verified by `verify.py` (new cases driving real throwaway repos with a stub `gh`) and by the
same call sequence replayed through `run.sh` in a scratch clone of PlunderSpell and in this repo. Not
verified: a real Claude Code session in another repo, and a `gh issue create` made through the
`PowerShell` tool, which is not recorded.

Live test of 2.53.0 in a cloud session on the mobile app (2026-10-07/08, transcript timestamps UTC):
a prompt Claude Code raised itself was refused by `prompttimer` after 300.0 s unanswered and listed on aj's
next message, as designed. `guard`'s own `ask` does reach aj as a real dialog (#143, first half). When aj
answered first, the timer stopped with no leftover process or entry (R2). A `guard` prompt left unanswered
(a delete, 02:15:57 UTC) was refused after 300.0 s and the file was not deleted, so the timer covers the
house-rules prompts too (#143); the next prompt was then refused at once (#152). aj's screenshot afterwards
shows both refused steps as "Failed" with the refusal text and no Allow/Deny card left (#149, seen in the
app view aj screenshotted; the phone view was not checked separately). New gap: the worker restarted as a prompt opened; the dialog stayed on aj's screen for 12 minutes while no
hook ran (`guard` ran only after aj pressed Deny), so the timer cannot cover a dialog that outlives its worker (#159).

2.53.0 (2026-10-07, #149, #151, #152) follows the prompt timer up: questions and plan approval are never
timed; after one timeout, later prompts in that session are refused at once until aj writes; and a new
`promptran` hook stops the timer when the action actually ran, and reports one recorded as timed out that ran
anyway. Verified by `verify.py` (562 checks; 7 new). Not verified: the desktop app's stale dialog (#149) and a
real session (#147). The same release (#153) lets `reset`/`revert`/`rebase`/`checkout --`/`restore` run unasked
on an `AjsAgent/` (or `claude/`) branch only when the tree is clean and every commit is on a remote; everything else still asks.
Verified by `verify.py` against a real repo with a local remote.

2.52.0 (2026-10-04, #142-#146) adds `prompttimer`: a permission prompt nobody answers for 5 minutes is
refused (never approved) and goes on a waiting-on-you list, shown on aj's next message and at the next session
start. Verified by `verify.py` (554 checks, 18 of them for the timer, the lock and the list) and by a real
headless Claude Code 2.1.289 run against the built hook: refused after the timeout, the file was never created,
Claude replied with a "Waiting on you" line. Stopping the hook mid-wait with SIGTERM through `run.sh`
removed its "waiting" entry and made no decision (checked by hand, Linux). Not verified: whether Claude Code
actually stops the hook when aj answers first, Windows locking and signals, the desktop app, including whether `guard`'s own
prompts reach the timer (#143), and the overnight-style run (#147).

2.51.0 (2026-10-01, #133) credits "aj's agent" instead of Claude: `tools/install.py` writes the `attribution` setting
(a plugin cannot carry it: Claude Code accepts only `agent` and `subagentStatusLine` from a plugin's settings.json), and
`guard` refuses text crediting Claude (kill switch `HOUSE_RULES_ATTRIBUTION=off`).

2.50.0 (2026-10-01, #110-#112) retires the executor for three tiers (`scout`, `builder`, `reviewer`),
adds the `agentcap` spawn cap (two running, 45-minute expiry, no spawns from subagents), quiets the
subagent audit, and shows a visible note when the open-issue list loads. Verified by `verify.py` (cases
for each cap behaviour, the audit size bound and the issue-list note) and by parsing the tier files. Not
verified: a real spawn of each tier, which needs the plugin updated and Claude Code restarted; and that a
real PreToolUse `Agent` payload carries `agent_id` for a call made from inside a subagent (the cap relies
on the tier files omitting the `Agent` tool if it does not).

2.60.0 (#196-#199): `guard` refuses commit/push/merge on the default branch and approves them on every other
branch; prompts nobody can answer (subagent, aj away) are refused and queued. Verified by `verify.py`; not yet in
a live session.

Unreleased, on `AjsAgent/agent-communication-patterns-xo0l8x` (#223, step #224 of 4): the "Show, don't tell;
the user designs" rule is written and loads through its own SessionStart handler, `showrule` (1,510 chars), because
`house-rules.md` was 47 chars from `inject`'s margin. "Build only what was asked" and "Match response depth" are
merged into it and removed (inject 9,653 → 9,381 chars). `verify.py` 618 PASS, run twice, 2026-10-13. The design
block (#225), the long-reply reminder (#226) and their proof (#227) are not built yet, so the rule describes a
hook that does not exist on this branch until #225 lands. Found on the way: `verify.py`'s guard cases go red if a
`house-rules-last-seen-*` temp file from an earlier run is over five minutes old; a rerun passes. Fixed
2026-10-15 (#229): each `verify.py` run now uses its own temp folder.

2026-10-14, same branch: the design loop (#223) is in Build. Step 1 of 7, "Stage tracker, approvals, and the code
lock" (#225), is built: `scope` reads aj's approvals and moves the stage in `.git/house-rules-loop.json`;
`commitgate` refuses code edits outside Build. The stage carries across sessions (aj's answer, 2026-10-14).
`verify.py` 631 PASS. Step 2, "An approval only counts once the stage is logged" (#230), is built: no new
decisions-log entry since the last approval, no stage move. `verify.py` 633 PASS. Step 3, "A home for each
feature" (#231), is built: issues made with the GitHub tool are now recorded, and "Build plan approved" waits
for two labelled issues made during Plan. `verify.py` 635 PASS. Step 4, "Helpers build only approved steps"
(#232), is built: helpers start with the feature, stage and issues; the go-ahead guess is off while the loop is on.
`verify.py` 638 PASS. Step 5, "Long-reply reminder" (#226), is built: over 200 words with no page link gets a
reminder at the end of the reply. `verify.py` 643 PASS. Step 6, "Handover page template" (#233), is built: `templates/handover-page.html`
fills its four parts from one PAGE block and drops an empty part; the rule describes it. `verify.py` 645 PASS. Step 7 (#227): a real run in a scratch repo, five messages to a real
Claude Code session loading this branch's plugin - code refused in Design, approvals moved the stage, two issues
recorded, code allowed in Build, QA passed moved it to Done. The run found one bug (a feature name took the whole
line), fixed with a test. Version 2.63.0. `verify.py` 646 PASS, run twice. Systems doc: `docs/4-systems/design-loop.md`.
QA passed (aj, 2026-10-14); a pull request to main is the release. Releasing needs a merge to main, which is at 2.62.0 (checked 2026-10-14: the 2.54-2.62 work is already merged, so this pull request carries only the design loop and the label check). Not released: one version bump at the end, after #227 proves the whole loop.

2026-10-14, same branch: the label check (#235), plugin 2.64.0, built and waiting on aj's QA. Every stage move reads
the feature's issue labels: from GitHub (`gh api`), or from the changes `autosave` recorded when GitHub can't be
read, and it says which. "Build plan approved" needs every issue `in progress`; swapping all to `needs review` starts
a new QA stage and closes code; QA answers count only in QA; after "QA failed" the redo needs the labels back; in
Build an edit is refused while a label is wrong; the end-of-reply check names wrong labels. `verify.py` 658 PASS,
run twice. A real run against two real issues (#236, #237) walked Plan → Build → QA → QA failed → refused redo →
Plan. It found one bug (a name ran on past a dash), fixed with a test. Rides the open design loop pull request.

2026-10-14, same branch: the new item visual (#240), plugin 2.64.1, built and waiting on aj's QA. The page template
draws a New item's three phrases as when → it does → you get (#241); the changes page has one per New item (#242);
a feature name stops before a pasted page reply's answer codes (#243).

2026-10-15, same branch: the new item visual failed aj's QA (box wording, and a per-file breakdown wanted); its
redesign waits behind the clear writing check (#245), plugin 2.65.0, now built and waiting on aj's QA. One rule,
`rules/clear-writing.md`, loads beside Show, don't tell; the shared checker `scripts/clarity.py` reads replies,
pages and issues; issues missing their three sections are refused; `agents/editor.md` (Sonnet) rewrites pages and
long replies, with a reminder when it didn't run. `verify.py` 684 PASS. System doc: `docs/4-systems/clear-writing.md`.
QA passed (aj, 2026-10-15).

2026-10-15, same branch: the new item visual v2 (#240), plugin 2.65.1, built and waiting on aj's QA. The template
labels a New item's boxes What exists today / What this creates / How it impacts you, and any item can list its
files with counts; `tools/diff_parts.py` does the counting, checked in `tools/verify_tools.py`. The changes page
covers the whole pull request: 27 items, every changed hook part placed once. The stale-temp-file flake (#229) is fixed.

2026-10-15, branch `ccr-fd3ee01d-o448i8`: handover pages and checkpoints (#251, "Handover pages and checkpoints:
pictures and project style on pages, then rules that run at fixed points"). Design approved, now in Plan, nothing
built. It started from a plunderspell page that skipped the template (`docs/handover-page-audit-2026-10-15.md`).
There are eight sub-issues, #252 to #259, all `in progress`. Build plan page: `docs/plans/handover-pages-plan.html`.
System doc: `docs/4-systems/handover-pages.md`.

2026-10-15, same branch: build plan approved ("1B 2A 3A"); #252 to #258 built, plugin 2.66.0: the page builder
`scripts/make_page.py`, template picture slots and compare, `docs/page-style.json`, the end-of-reply checkpoint table,
the page check, and the rule text. Waiting on aj's QA and the PlunderSpell regeneration test (#259), not yet run.

2026-10-15, branch `ccr-fd3ee01d-o448i8`: handover pages and checkpoints (#251) is built, 2.66.0, in aj's QA. Pull request #263. Every issue (#251 to #259, #261, #262) is `needs review`. `verify.py` 753 PASS and `tools/verify_tools.py` 47 PASS, each run twice. The guard fixes from `docs/guard-friction-audit-2026-10-15.md` are in. #259 (the PlunderSpell regeneration) runs in a new session after the merge.

2026-10-15, branch `AjsAgent/vigilant-meitner-8pp618`: pull request #263 is merged. Enforcing the QA stage (#264) is built, all seven steps (#265 to #271, plugin 2.67.0), QA passed (aj, 2026-10-15); every issue stays `needs review` until aj closes it, and a pull request to main is the release. QA page: `docs/plans/qa-stage-qa.html`. The real run (`docs/generated/2026-10-15-qa-stage-real-run.md`) found two fixes, both merged (a QA page linked in a retry reply is recorded; a QA page with no choices renders), and one older loop in the label check, left for a follow-up. Design approved ("1A 2A 3A 4A", `docs/plans/qa-stage-design.html`), build plan `docs/plans/qa-stage-plan.html` approved ("1A 2A"). Stage file in a committed `.claude/house-rules-loop.json` (#265), QA leak was the 2.65.1 per-checkout file (#266), a pull request opening moves Build to QA (#267), `make_page.py` QA mode (#268), the `qa page` checkpoint (#269), corrected-lines-only notes (#270), rule text and docs (#271).

2026-10-15, branch `AjsAgent/page-charset-fonts`, plugin 2.67.1: built pages carry `<meta charset="utf-8">`, and a style file's `fonts` (display, body, label) now become the page's Google Fonts link in place of the template's default one (`fonts.load` still overrides). Checked on PlunderSpell's fear-entities page served by `python -m http.server`: UTF-8, Eczar and Spectral loaded.

2026-10-16, branch `AjsAgent/friendly-davinci-r8qwdn`, plugin 2.68.0: the guards audit (#285), automatic pages (#281) and label setup (#274) are built on one branch for one pull request into `main`. Pages: the copy box holds the exact approval phrase (#286); cards wrap long words on a phone and the visual check fails the build on a clipped card (#288); a page is required at 160 words or more (#282), keeps blocking until one is linked, three blocks at most (#283), and only pages git shows as new, edited or committed count (#284). Guards: the never-blocked list (#289) and per-prompt timer (#290); nine destructive kinds refused with the safe way named, deletes narrowed (#291); the background-work guard and the "Never hide work" rule removed (#292); enforced checks name their fix and a whole-file Write is refused (#293). Labels: `scripts/labels.py` (#275), created when "Design approved" arrives (#276), `/house-rules:labels` (#277), REST label advice (#278). Not built: #287 (configurable agent name), held for a follow-up because its default would change aj's credit line. Its retired detail file waits in `_to_delete/` for aj.

2026-10-16, branch `ccr-7dcf4ee2-zp3mm8`, plugin 2.68.1: the first step of the plugin restructure (#306), scoped to the issue "the design loop is broken and blocks sessions" (#303). Built: every approval in a message is read, in stage order (#307); only issues made in the checkout's own GitHub repo count toward its feature (#308); the shell-write refusal while code is locked, the re-creation check, the page checkpoint and the bare-reference writing check report instead of blocking, and `make_page.py` builds any approval line (#309); a flagged page stays owed across shorter retries (#310). `verify.py` 839 PASS, run twice. QA passed (aj, 2026-10-16); pull request #312 waits to be merged. The audit behind it is `docs/audits/2026-10-16-plugin-audit/`; the restructure's design is `docs/4-systems/plugin-restructure.md`. Next: the grilling session on the 28 rule contradictions.

2026-10-17, branch `AjsAgent/reference-page`, plugin 2.68.2: aj's reference page is saved at `docs/plans/reference/learning-tools-plugin.html`, with its content file, its eight pictures and a README saying what makes it the reference. No hook or rule changes; the version moves only because `check_plugin_version_bump.py` counts every `docs/` change. Making pictures mandatory on every page is issue #313 (priority: high, up next). `verify.py` 839 PASS.

2026-10-17, branch `AjsAgent/issue-315-attribution-routes`, plugin 2.68.3: #315 (attribution guard gaps, #316 to #319) is built and waiting for aj's QA.

2026-10-18, branch `AjsAgent/nifty-newton-x2jaaj`, plugin 2.68.4: #322 (the end-of-reply checks looped on retries) is built and waiting for aj's QA. The Stop retry now only reports to aj and never continues the turn (#323); the writing check no longer runs on chat replies, only on pages and new issues (#324); the editor checkpoint is pages-only unless `HOUSE_RULES_EDITOR=on` (#325); the page checkpoint's note is said once per message of aj's (#326); and an approval counts the first time, with the decisions-log entry asked for afterwards (#327). The cloud QA run of #315 passed: the credit read-back reported the footer GitHub added to test issue #321.

2026-10-18, branch `AjsAgent/issue-329-page-links`, plugin 2.68.4: #329 (a page link in a reply must open, #330 to #332) is built and waiting for aj's QA. The page checkpoint counts an .html link only when it resolves inside the session's folder, and `make_page.py` warns when it writes a page outside the folder it runs in. `verify.py` still fails the 4 checks that already failed on `main` in a separate working folder (95, 97, 751, and the pagecheck case); no new failures.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.68.5: the #322 loop fix (pull request #328, branch `AjsAgent/nifty-newton-x2jaaj`) is merged with `main` and the #306 grilling work, plus one more cause of the loop: during an uncommitted merge, every page the other branch brought in counted as written this turn. A page still identical to the merged branch's copy no longer counts. aj asked for this on `main` straight away.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.68.5: aj approved the 10-step build plan for the #306 restructure (`docs/plans/2026-10-19-restructure-build-plan.html`), move first and ship after each step. Steps are #339, #340, #341, #349 and #343 to #348; step 1 (#339, the summary template) is in progress.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.69.0: restructure step 1 (#339) passed aj's QA on 2026-10-20 and is on `main` as house-rules 2.69.0 (pull request #356). Step 2 (#340) waits on aj's answer on `docs/plans/2026-10-20-restructure-step-2-split.html`: real modules now, or one shared namespace until step 10. The writing rule keeps its "Explicit context" and "Named references" lines and adds a "Define before use" line beside them (aj's QA failure, 2026-10-20), the checker flags a round or question reference that names nothing, and summary pages have a "Decided by" box, one line per decision and a before-and-after strip, from the starter file `templates/decision-summary.page.json`. The grilling summary page is rebuilt from it.

2026-10-20, branch `AjsAgent/issue-281-fix`, plugin 2.70.0: issue closing (#361, steps #362 to #365) is on `main` as 2.70.0 (pull request #366). The first sweep closed 26 issues on 2026-10-21; 103 agent-created issues stay open. The after-close and merge proof checks don't yet read the GitHub tool's wrapped results. A QA pass saves a feature's issues and a merge marks them; the close guard lets an issue close only with both on record, or on an approved sweep or named list, on both the gh and GitHub tool routes. Restructure step 2 (#340) resumes after this ships, as 2.71.0.

2026-10-21, branch `AjsAgent/issue-281-fix`, plugin 2.70.0: aj approved the verify.py rework (#368, steps #369 to #371): per-part test files with a parallel runner, and in a session the touched parts run twice and the rest once. It is built after restructure step 2 (#340), which resumes now at step 2a (#357).

2026-10-21, branch `AjsAgent/issue-281-fix`: step 2a (#357) is built. `scripts/house_rules/core.py` (1,853 lines) holds the core handlers and three hook lists that parts register on; `hook.py` went from 8,931 to 7,248 lines. `verify.py` 913 PASS, run twice by the builder and once more after the merge (185 seconds). Next is step 2b (#358).

2026-10-21, branch `AjsAgent/issue-281-fix`: step 2b (#358) is built. `house_rules/safe_git.py` (1,888 lines) and `house_rules/docs.py` (717 lines) hold their parts; shared helpers moved into core (2,057 lines); `hook.py` is down to 4,633 lines. The guard's refusals through `run.sh` are byte-identical to before. `verify.py` 913 PASS, run twice by the builder and once more after the merge (162 seconds). Next is step 2c (#359).

2026-10-21, branch `AjsAgent/issue-281-fix`: step 2c (#359) is built. `hook.py` is down to 332 lines (`main()`, the event table and the end-of-reply dispatcher); `house_rules/` holds core 3,000, delegation 1,656, design loop 2,151, writing 340, safe git 1,648 and docs 717 lines. The parts reach each other only through lists kept in core. `harvest_scan.py` and `tools/measure_footprint.py`, broken by the move, are fixed. `verify.py` 913 PASS, run twice by the builder and once more after the merge (130 seconds). Next is step 2d (#360): version 2.71.0, the docs and the QA page.

2026-10-21, branch `AjsAgent/issue-281-fix`, plugin 2.71.0: step 2d (#360) is built, and restructure step 2 (#340) waits on aj's QA on `docs/plans/2026-10-21-restructure-step-2-qa.html`. `docs/architecture.md` maps all 32 handlers to their modules. Timings: a full `verify.py` run took 134 and 132 seconds (197 before step 2); one hook call takes 0.08 seconds (0.17 before).

2026-10-21: aj passed QA on restructure step 2 ("QA passed: restructure step 2"); 2.71.0 goes to `main` by pull request. The loop did not record the pass (its issue list had moved to the verify rework), so step 2's issues close through a sweep. The verify rework (#368) is next.

2026-10-21: house-rules 2.71.0 is on `main` (pull request #372, merged after its `verify` check passed). The verify rework (#368) starts at step 1 (#369).

2026-10-21: verify rework step 1 (#369) is built. `docs/4-systems/verify-suites.md`, "Which part every check belongs to (#369)", places all 913 checks in a part, with per-part seconds (the longest are safe git 31.7, design loop 28.5 and page builds 27.5 of a 127-second run). `tools/check_verify_inventory.py` proves every check is listed exactly once. Next is step 2 (#370), the per-part files and the parallel runner.

2026-10-21, plugin 2.72.0: the verify rework (#368) is built and waits on aj's QA on `docs/plans/2026-10-21-verify-rework-qa.html`. verify.py runs one test file per part (`scripts/checks/`) in parallel: a full run takes 39 to 41 seconds (197 before restructure step 2), and `--changed` runs only the touched parts (the docs part alone: 125 checks in 8.1 seconds). The run-twice rule now says the touched parts run twice and the rest once; CI runs everything.

2026-10-21: aj passed QA on the verify rework ("QA passed: verify rework"); 2.72.0 goes to `main` by pull request. Next is #367 (the proof-check bug), then restructure step 3 (#341).

2026-10-21: house-rules 2.72.0 is on `main` (pull request #373; GitHub's `verify` check took 49 seconds). The close guard refused to close #371, because the merge was not stamped on the closable record: the merge-proof check doesn't read the GitHub tool's result, which is #367. #368 to #371 close once #367 is fixed.

2026-10-21, plugin 2.73.0: the proof check fix (#367) is built and waits on aj's QA. #374 unwraps the GitHub tool's text-block replies before both proof checks; #375 keeps each feature's issues under its name, so a QA pass after the next feature's approval still records the right issues. `verify.py` 925 PASS (40 seconds). Restructure steps 3 to 7 follow as one feature (`docs/plans/2026-10-21-restructure-steps-3-7.html`).

2026-10-24: aj passed QA on the proof check fix; 2.73.0 goes to `main` by pull request, and aj tests the live close in a new session (this one loaded 2.72.0). The next merge in a 2.73.0 session stamps the waiting closable entries for the verify rework (#368 to #371) and the proof check fix (#374 to #376).

2026-10-24: house-rules 2.73.0 is on `main` (pull request #380). The merge ran under this session's 2.72.0 hook, which has no unwrap fix, so the closable entries are still unstamped; the first merge in a 2.73.0 session stamps them. The step 2 sweep page (`docs/plans/2026-10-24-step-2-sweep.html`) and the steps 3 to 7 design page wait on aj.

2026-10-24: aj approved the step 2 sweep; #340 and #357 to #360 are closed. Their 5 rows left the sweep list after the closes, so the after-close check now reads the GitHub tool's replies live. The merge stamp is not yet seen live. 26 old sweep rows from 2026-10-21 remain in the stage file.

2026-10-21: verify rework step 2 (#370) is built on branch `AjsAgent/issue-370-split`, not yet merged or QA'd. `verify.py` is now a runner (`--parts`, `--changed`, `--serial`) over one test file per part in `scripts/checks/`; a full run is 913 checks in 34.5 and 36.0 seconds (4 cores), `--serial` 132.1, `--parts design_loop` 29.9; the sorted list of check titles is identical to the single-file run's. 32 checks sit in a different part than the #369 list gave them, to keep order-dependent groups whole. A pull request for it needs a plugin version bump first (the version-bump check fails without one) and the hard-coded `2.71.0` in `checks/design_loop.py` changed with it. Details: `docs/4-systems/verify-suites.md`, "The split layout (#370)". Next is step 3 (#371), the run-twice rule text.

## 2. Six-tier docs convention — mechanism done, this repo's adoption just started

The plugin-side mechanism (skill, routing, drift checks) has been verified since before this
document existed. This repo's own `docs/` did **not** carry tiers 1, 2, 3, 4, or 5 until the
2026-09-24 scaffolding session — only tier 6 (`Decisions.md`, added 2026-09-15) and the three
non-tier folders (`plans/`, `archive/`, `generated/`) existed. That session scaffolded the other
five (`README.md`, `Roadmap.md`, this file, `systems/*.md`, `Today.md`) by reading the code
directly, per the skill's own scaffolding order (tier 4 first, tier 5 last). A later 2026-09-24
session then gave each tier its own numbered folder (`docs/1-landing/` through
`docs/6-decisions/`) and added the short, plain-English `docs/README.md` at the top of `docs/` —
see [`docs/6-decisions/Decisions.md`](../6-decisions/Decisions.md), "Give each documentation tier
its own numbered folder".

## 3. Offshoot plugins — real but unvalidated

Both `prompt-workshop` and `agent-router` are fully wired, not stub code, and both verify
suites pass. What's missing is everything that would turn "the mechanism works" into "the
mechanism is worth trusting": no tuning against real prompt traffic, no
`SubagentStart`/`SubagentStop` visibility parity with `house-rules`, no handling for a prompt
that spans two of `agent-router`'s tiers. These are stated as open by
[`docs/offshoots-plan.md`](../offshoots-plan.md), not discovered here.

## 4. Distribution & install tooling — built and verified

`install_steps()`'s four-command order, `bootstrap.ps1`/`.sh`, `update.bat`, and both
verification scripts (`clean_install_test.py`'s logic, `verify_tools.py` itself) are all in
place and `verify_tools.py` passes. The one thing this document does *not* claim: that the real
`claude` CLI sequence was re-run today. It wasn't — see "the one thing that is not what it looks
like," below.

`tools/measure_footprint.py` prices every handler registered in `hooks.json` — as of 2026-09-26,
when `docstiers`, `versioncheck`, `guardwrite` and `handover` were added (issue #74); before that
four of the eighteen had no measured cost. `handover` turned out to be the largest per-turn
injection when it fires (~556 tokens for a reply with an uncarded shell fence).

## The one thing that is not what it looks like

**This document, and the four other tiers scaffolded alongside it today, will read as a mature,
long-standing documentation practice — tables, percentages, `file:line` citations — when they
are in fact a same-day first draft, assembled by reading the code once.** None of them has yet
been through the cycle that's supposed to keep them honest: `Today.md` rewritten at the start of
a session, `ProjectState.md` updated when a milestone's status actually changes, a tier-4 doc
revised because its system changed. A reader six months from now should weigh today's dates
(2026-09-15, on every file created in this pass) accordingly — freshly written is not the same
claim as battle-tested, even when the content is accurate.

A second, smaller instance of the same thing: milestone 4's acceptance criterion leans partly on
"per prior recorded verification on this machine, the real command sequence has been run" —
that's a claim inherited from an earlier session, not re-checked today. The suite that *was*
re-run today (`verify_tools.py`) tests the tools' decision logic, not a live `claude` CLI
invocation.

## Cross-cutting issues that belong to no milestone

- **Agent attribution everywhere (#174, planned 2026-10-08).** Credit "aj's agent" and `AjsAgent/`
  branches in every own repo; old `claude/` branches renamed, no history rewrite. Plan:
  [`docs/plans/2026-10-08-agent-attribution-everywhere.md`](../plans/2026-10-08-agent-attribution-everywhere.md).
  #175 is built (2.56.0): owned branches are `AjsAgent/` (`claude/` still recognised) and the issue
  label is `AjsAgent created this` (`Claude created this` still counts). #176 is built (2.57.0): a
  cloud session on `claude/<name>` is told at start to move to `AjsAgent/<name>`; whether the app's
  own PR button follows the new branch is still unchecked. #177 is built (2.58.0): `guard` refuses a
  commit authored as Claude and session start tells a cloud session to set the repo-local identity.
  #178 is built (2.59.0): the GitHub write tools get the same credit check and refuse a new
  `claude/` branch. 2.59.1: `guard` judges branch ownership by the payload cwd (worktree subagents), `ccr-` is owned, `HOUSE_RULES_OWNED_BRANCHES` adds prefixes. 2.61.0: #189 is fixed, so git rules no longer miss a command whose `-c` value is quoted with a space in it (`-c user.name="aj's agent"`), which had let six Claude-credited commits through; PR #190's change, ported. Not built: #179 cloud settings, #180 Focus Deck label, #181-#182 retroactive report and renames.
- **[`docs/architecture-backlog.md`](../architecture-backlog.md)** — seven open refactor candidates
  against `hook.py`/`verify.py` (deduplicating nine restatement checks, unifying the three
  places the failure-mode contract is stated, one open item about agent frontmatter fields
  `verify.py` currently forbids). None are commitments; none block any milestone above.
- **[`docs/rules-backlog.md`](../rules-backlog.md)** — one open item (vague, unrunnable handover
  instructions caught once in `docs/desktop-verification.md`), not yet written into
  `rules/house-rules.md`.
- **Both backlog docs are the exact kind of ad hoc decision log that Tier 6
  (`docs/6-decisions/Decisions.md`) was built to replace**, per
  [`docs/archive/2026-09-15-sixth-documentation-tier.md`](../archive/2026-09-15-sixth-documentation-tier.md#context) —
  but their entries haven't been transcribed into `Decisions.md` yet. They still function as
  backlogs (open items awaiting a decision), which is a different thing from `Decisions.md`'s
  append-only *record* of decisions already made — so this isn't necessarily a migration to do,
  but it's worth a deliberate call rather than leaving both patterns live indefinitely.
- **Stray root-level items with no documented purpose**: `Modified.md` (an empty directory,
  despite the `.md` name), `artifact-test.html` (a committed artifact-publishing smoke test, per
  its own commit message — not part of `docs/`), `skills-lock.json`, and five leftover
  directories under `.claude/worktrees/` from past delegated sessions
  (`auto-mode-subagent-delegation-bfb401`, `changelog-planning-7a4c3f`,
  `house-rules-version-check-3b7798`, `opus-sonnet-fix-plan-349283`,
  `plugin-version-bump-guard`). None were investigated further or touched as part of this
  scaffolding pass — flagged here because they're the kind of thing a documentation audit is
  supposed to surface, not because their disposition was decided.
- **`docs/sessions/` has exactly one recorded ledger** (2026-09-09), despite
  `tools/session_ledger.py` existing to produce one per session. The tool works; running it
  isn't yet a habit.
