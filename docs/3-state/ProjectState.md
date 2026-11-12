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
the rules (`_subagent_core` in `claude-house-rules/plugins/house-rules/scripts/house_rules/delegation.py`) since `SessionStart`'s own `additionalContext` never
reaches a spawned subagent, and added a commit-time docs-tier reminder to `guard` itself
(`_staged_docs_status` in `claude-house-rules/plugins/house-rules/scripts/house_rules/docs.py`) rather than only once per session. What's not built:
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

2026-11-03, branch `ccr-e35d967e-dmwsj0`, plugin 2.75.0: the hook half of #453 is built (#454). The `guard` hook refuses an agent's third run of the same project script in a session unless a commit since the last run changed a file other than that script (aj's choices 1B, 2B, 3B on `docs/plans/rerun-limit-hook-plan.html`; build plan `docs/plans/rerun-limit-build-plan.html`, choice 1A). The draft was written by a builder that went around the design-loop lock through Bash before the build plan was approved; aj chose to keep it after a line-by-line review. Real sessions on 2026-11-03 (a throwaway repo, `claude -p --plugin-dir` on this branch, a `house-rules:builder` subagent): the third run of `tools/x.sh` was refused with the stop-and-report message, and after a commit changing `src.txt` the next run went through. The first session also showed that a run refused for another reason was still counted; `_rerun_take_back` now restores the count when the guard refuses or asks (case 197, which fails with the fix removed). `verify.py` 973 PASS. Design: `docs/4-systems/rerun-limit.md`. Waits on aj's QA.

2026-11-05, branch `AjsAgent/audit-2026-11-05`, plugin 2.76.0: the three audits of 2026-11-05 are merged into one ranked list of 45 findings (`docs/audits/2026-11-05-combined-ranked.md`). aj approved the fix order as "Design approved: audit fix order 1A". The plan is `docs/4-systems/audit-fixes.md`, parent issue #476, with steps #477 to #482. aj approved all the code at once (`docs/plans/2026-11-05-audit-fix-code-approval.html`; choices in `docs/6-decisions/Decisions.md`), to be checked in one QA. Step 1 (#477) is built and merged at `4d03a41`: `verify.py` 1004 of 1004, `tools/verify_tools.py` exit 0. Three changes from the written plan: a folder under `/tmp` or `~/.cache` counts as temporary only when no `.git` sits above it, because a repo there can hold unpushed work; autosave says why it saved nothing in place of "committed 0 file(s)"; four guard tests that asserted the old behaviour aj approved changing now assert the new one, and three autosave tests register their files the way a real Write does. Step 2 (#478) is built and merged at `d605275`: `verify.py` 1018 of 1018, `tools/verify_tools.py` 48 of 48. The guard now sets the repo's git identity to Edens Agent in a cloud session, and every "AJ's agent" in the plugin and tools now says Edens Agent. The installed plugin keeps the old name until this ships. Two changes from the written plan: heredoc bodies are still read by the issue check, so a pull request's `Refs` line counts; and a quote before `rm` now counts as the start of a command, so `bash -c 'rm -rf docs'` is refused. Step 3 (#479) is built and merged at `a3b962a`: `verify.py` 1029 of 1029, `tools/verify_tools.py` 48 of 48. aj's own message can now say "Continue from: <branch>" to copy that branch's stage and issues, or "Issues for <feature>: #N" to record issues in Plan; a relayed message can't use either. Issues from loops, `python3 -c` and `gh api` are counted, and each approval note says to commit and push the stage file. Two tests were added for the "Issues for" success path, which the builder had left untested. Step 4 (#480) is built and merged at `daddd3f`: `verify.py` 1040 of 1040, `tools/verify_tools.py` 48 of 48. The old `.git` stage file, `.claude/settings.json`, code under `docs/` and worktree sources are locked; shell writes to the stage file are refused; the stage file is written atomically; a question or a "don't" no longer approves; only a pull request that names an issue unlocks closing it; the helper cap holds for launches made together. In Build, when GitHub can't be read, edits are refused (aj's choice 6B); the REST read the hook uses works in cloud sessions. `.txt` and `.csv` are open, `.json` stays locked (8A). The shell-write gap is #484. Step 5 (#481) is built and merged at `80f963d`: `verify.py` 1046 of 1046, `tools/verify_tools.py` 48 of 48. Re-approving a design keeps the feature's issues; an approval must name the current feature (choices after the name, such as "1A 2B", are allowed; aj's choice 7A); "skip design" ends with its stage; only the feature's own QA page file counts; and a merge keeps the stage on main and asks aj what's next (9A). Step 6 (#482) is built and merged at `489de54`: `verify.py` 1052 of 1052, `tools/verify_tools.py` 52 of 52. The version check, installer, page builder, `force_update.py` and label recording give right answers, and dead code and the unused `tools/check_verify_inventory.py` are deleted (10A). The hook merge (H4) was measured and not built: it would save about 14 ms per shell command, under the 100 ms bar (timings in `docs/4-systems/hook-engine.md`). The plugin is 2.76.0 for the whole build. Waits on aj's QA.

2026-11-02, branch `ccr-e35d967e-dmwsj0`, plugin 2.74.3: the first half of #453 ("Stop builders rerunning the same check"), taking in #139. `agents/builder.md` now limits any in-game, end-to-end or harness check to two runs, forbids changing a check to make it pass, asks for a code read between runs, and says a number from a check is evidence, not the finish line unless the plan says so. `rules/detail/delegate-execution.md` tells the parent not to write a measured number as a builder's only done-when, and to look at a running builder after about 10 minutes. No hook changes yet: the hook that refuses a third run waits on aj's design choices.

2026-11-02, branch `AjsAgent/sword-pitch-reference`, plugin 2.74.2: a second reference page is saved at `docs/plans/reference/sword-fighting-proposal.html`, the sword-duel game pitch from `Ajw2003/AjsCanadaPrty`. aj chose it as the template for future plans and pitches. It comes with its content file, nine pictures, and the sources that drew them, under `sword-fighting-proposal-sources/` (three.js concept-frame renderer, SVG diagrams, render scripts). The reference README now says what each of the two pages is the reference for. `rules/show-dont-tell.md` now points every plan or pitch page at it, and its detail file carries the seven-point checklist (Decisions, 2026-11-02). No hook changes.

2026-10-17, branch `AjsAgent/issue-315-attribution-routes`, plugin 2.68.3: #315 (attribution guard gaps, #316 to #319) is built and waiting for aj's QA.

2026-10-18, branch `AjsAgent/nifty-newton-x2jaaj`, plugin 2.68.4: #322 (the end-of-reply checks looped on retries) is built and waiting for aj's QA. The Stop retry now only reports to aj and never continues the turn (#323); the writing check no longer runs on chat replies, only on pages and new issues (#324); the editor checkpoint is pages-only unless `HOUSE_RULES_EDITOR=on` (#325); the page checkpoint's note is said once per message of aj's (#326); and an approval counts the first time, with the decisions-log entry asked for afterwards (#327). The cloud QA run of #315 passed: the credit read-back reported the footer GitHub added to test issue #321.

2026-10-18, branch `AjsAgent/issue-329-page-links`, plugin 2.68.4: #329 (a page link in a reply must open, #330 to #332) is built and waiting for aj's QA. The page checkpoint counts an .html link only when it resolves inside the session's folder, and `make_page.py` warns when it writes a page outside the folder it runs in. `verify.py` still fails the 4 checks that already failed on `main` in a separate working folder (95, 97, 751, and the pagecheck case); no new failures.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.68.5: the #322 loop fix (pull request #328, branch `AjsAgent/nifty-newton-x2jaaj`) is merged with `main` and the #306 grilling work, plus one more cause of the loop: during an uncommitted merge, every page the other branch brought in counted as written this turn. A page still identical to the merged branch's copy no longer counts. aj asked for this on `main` straight away.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.68.5: aj approved the 10-step build plan for the #306 restructure (`docs/plans/2026-10-19-restructure-build-plan.html`), move first and ship after each step. Steps are #339, #340, #341, #349 and #343 to #348; step 1 (#339, the summary template) is in progress.

2026-10-19, branch `AjsAgent/issue-281-fix`, plugin 2.69.0: restructure step 1 (#339) passed aj's QA on 2026-10-20 and is on `main` as house-rules 2.69.0 (pull request #356). Step 2 (#340) waits on aj's answer on `docs/plans/2026-10-20-restructure-step-2-split.html`: real modules now, or one shared namespace until step 10. The writing rule keeps its "Explicit context" and "Named references" lines and adds a "Define before use" line beside them (aj's QA failure, 2026-10-20), the checker flags a round or question reference that names nothing, and summary pages have a "Decided by" box, one line per decision and a before-and-after strip, from the starter file `templates/decision-summary.page.json`. The grilling summary page is rebuilt from it.

2026-10-28, aj's PC (DESKTOP-ENFEPDQ, Windows, PowerShell 5.1, Python 3.13.7), checked by a read-only session there: under 2.74.0 every tool, Read included, was refused. `HOUSE_RULES_AGENT_NAME` and `HOUSE_RULES_OWNED_BRANCHES` were not visible to it: the cloud environment's variables do not reach a Remote Control (bridge) session, and no `env` block exists in the user or GameDev settings files. The refusal's fix command uses `python3`, which on that PC is only the Microsoft Store alias; `python` works. The session loads the plugin from a copy synced from the claude.ai account (under `AppData\Local\Claude-Data`), not from the plugin cache. aj approved saving `agent_name = ajw2003sAgent` and `extra_owned_prefixes = ""` there, after which the tools ran.

2026-10-28, branch `AjsAgent/revert-restructure`, pull request #428: the restructure (2.74.0, pull request #427) is reverted on `main` back to 2.73.3 (`2b30052`), because its settings gate refused every tool, replies included, and aj's QA failed it. Nothing is lost: the restructure commits stay in history and on `AjsAgent/issue-281-fix`, and the 2.74.1 settings-gate fix stays on `ajsagent/affectionate-turing-y4ypfg`. `verify.py` 965 PASS on the reverted code. It is numbered 2.74.1 (aj's choice: a patch) so installed 2.74.0 copies update; the only code differences from 2.73.3 are that number and the check that pins it, and `verify.py` still passes 965 checks. Still to do: a catalogue of 2.73.3's behaviour compared against the restructure in real sessions before any of it returns to `main`.

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

2026-10-27, plugin 2.73.3: `docref.py check` passes on `main` again. Its own test file, `scripts/checks/docs.py`, opts out with a `docref: skip-file` line, and the check names every skipped file. The same patch removes the three published page links on `main` (in `docs/plans/2026-10-19-restructure-step-1-qa.html`, its `.page.json` and `docs/plans/new-item-visual-qa.html`), replacing each with the repo path of the page it pointed at. Branch `AjsAgent/docref-skip-fixtures`; merges after pull request #402 (2.73.2).

2026-10-27, plugin 2.73.1: the design-loop lock now finds the repo when aj's message arrives from the folder above it (a cloud session's folder of clones), and says so when it can't; before, both approvals for #389 (QA pages must prove each change with evidence for its type) were lost in silence. Branch `AjsAgent/loop-missed-approval`, pull request into `main`. #389's own build waits on this fix and aj resending its two approvals.

2026-10-21, plugin 2.73.0: the proof check fix (#367) is built and waits on aj's QA. #374 unwraps the GitHub tool's text-block replies before both proof checks; #375 keeps each feature's issues under its name, so a QA pass after the next feature's approval still records the right issues. `verify.py` 925 PASS (40 seconds). Restructure steps 3 to 7 follow as one feature (`docs/plans/2026-10-21-restructure-steps-3-7.html`).

2026-10-24: aj passed QA on the proof check fix; 2.73.0 goes to `main` by pull request, and aj tests the live close in a new session (this one loaded 2.72.0). The next merge in a 2.73.0 session stamps the waiting closable entries for the verify rework (#368 to #371) and the proof check fix (#374 to #376).

2026-10-27, branch `AjsAgent/background-work-tracking`, plugin 2.73.2: background work tracking (#396) is built and waits on aj's QA on `docs/plans/background-work-tracking-qa.html`. In a claude.ai project thread, the session-start hook gives the thread its own transcript link for its checklist header (#400), a new `rclink` hook asks for a Remote Control session's transcript link once it starts (#383), the audit hooks write each finished helper's commands to `/mnt/project-files/work-trail/` and ask for the file to be attached (#397), and the end-of-turn check blocks once on a link that was never posted (#398). `verify.py` 951 PASS after merging main. Version 2.73.2 (2.73.1 went to the design-loop lock fix, pull request #401, the same day), not 2.74.0, because the unmerged restructure branch already uses 2.74.0; this must merge first.

2026-10-27, same branch and version: aj failed the first QA so every known gap closes before `main`. The redo adds #403 (the helper ledger lists commands, feature names drop pasted tags and answer codes, a synced cloud copy gets one plain line instead of failing update commands), #405 (safety commits credit aj's agent; the guard refuses claude.ai session, project, artifact and share links in messages, GitHub text and the lines a commit adds; the three artifact links in `docs/plans/` are gone) and #404 (docs, new QA page `docs/plans/work-tracking-gap-fixes-qa.html`). `verify.py` 963 PASS, `verify_tools.py` 47 PASS. Squash-merge pull request #402 so session ids in older branch commits stay off `main`.

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

2026-11-08, branch `AjsAgent/session-handoff`, plugin 2.77.0: usage handoff (#406) is built in steps #486 to #409 (autosave on every branch, save at turn end, the handoff check, the session-start pickup) and documented in `docs/4-systems/usage-handoff.md`; the real two-account run and QA are still to do (#410).

2026-11-11, same branch, roadmap phase 1 (#493, "approvals and the design loop just work"), building steps #501 to #507 in order:
- Step 1 (#501) built: an approval may put the feature name first ("Phase 1 design approved 1A"), a leading cloud `<system-reminder>` block is set aside unless it carries a relayed message, a "don't" or "not" before any approval stops it, picks with no stage words get a note saying so, and an approval sent from outside a repo is never silent. `verify.py` 1092/1092 PASS.
- Step 2 (#502) built: the page builder refuses a design or build plan page whose copy-box line the loop would reject (pages for another repo, summary pages and sweep pages are exempt), the end-of-reply check records the approval lines a reply offered, and a bare "Approve" (plus picks) is read as the one line offered, or moves nothing and says why. `verify.py` 1097/1097 PASS.
- Step 3 (#503) built: a step issue counts toward the feature only when it says "Part of #N"; "Build plan approved" reads the feature issue and every open issue naming it from GitHub's REST list (a live read on this repo returned #493 and #501 to #507 in 0.7 s), and falls back to the recorded issues with a note when GitHub can't be read. `verify.py` 1101/1101 PASS.
- Step 4 (#504) built: "QA failed: <feature> <what's wrong>" sends the feature back to Build in one message with its issues and build plan kept; code opens once the issues are back to `in progress`, and the stage does not bounce straight back to QA while they still say `needs review`. `verify.py` 1103/1103 PASS.
- Step 5 (#505) built: the old stage file inside `.git` is no longer read (D3); a design approval with a different name starts a new feature and keeps the old one with its issues in any stage (D6, choice A); a branch whose newest approval is older than the newest in this clone holds code edits until "Continue from: <branch>" or a new approval, recorded in `house-rules-loop-seen.json` in the common git folder (D9, choice A); on the default branch a stage file in QA reads as Done without being written (U3). `verify.py` 1109/1109 PASS.
- Step 6 (#506) built: the "unless they have said otherwise" exception is gone from the rules; a helper's unexpected finding is a question for aj; a reply in Build whose last paragraph asks a question holds code edits until aj's next real message; a reply saying "I went with ..." or "I chose ..." is sent back once. `verify.py` 1120/1120 PASS.
- Step 7 (#507) built: after "QA passed" and the merge, the close line ("Close as completed: #N ...") is offered to aj; the end-of-reply label line is said once per set of wrong labels; 15 proof cases cover the eight audit findings already fixed and #102, #107, #110, #128, #129, #130. Plugin 2.78.0. `verify.py` 1135/1135 PASS, `tools/verify_tools.py` 52/52 PASS. Phase 1 is built; aj's QA is next.
- Live tests, 2026-11-11 (`docs/plans/2026-11-11-phase-1-live-tests/`): 14 of 14 real headless sessions through the whole loop, 6 of 6 real-git branch and merge checks, hooks as fast as 2.76.0, and 2.78.0 installs from the branch URL and rolls back to 2.76.0. Not run: Windows, the app's real Approve button, a real merge's close-line offer.
- 2026-11-11: aj wrote "QA passed: Phase 1". The stage is Done; issues #501 to #507 keep `needs review` until aj closes them after a merge.
- 2026-11-11: phase 2 (#494, docs and files you can trust) design page `docs/plans/2026-11-11-phase-2-docs-and-files.html` is up for aj's approval; nothing built. The session handoff re-test was stopped at aj's word (phase 2 first) before it pushed anything.
- 2026-11-11: at aj's word, the phase 2 design now sends big files through Git LFS instead of keeping them out of git; only folders a build regenerates stay out. A risk item names GitHub's LFS limits (not checked) and git-lfs on aj's PC (not checked).
- 2026-11-11: at aj's word, phase 2's big files stay out of git by default; one goes in through Git LFS only when aj names it ("LFS approved: <file>") and the free 10 GiB allowance has room. GitHub's billing API was refused from this cloud session (repo-bound), so the allowance check falls back to this repo's LFS sizes there.
- 2026-11-11: phase 2 design approved ("Design approved: Phase 2 1A 2A 3A 4A 5A"); plan in `docs/4-systems/docs-and-files.md`, issues #508 to #514, build plan page `docs/plans/2026-11-11-phase-2-build-plan.html` up for approval.
- Phase 2 step 1 (#508) built: a commit's guard message names each living doc that cites a file the commit changes, and any drifted citation of those files; `scripts/docs_drift.py` lists all drift in the living docs. Its first run on this repo found 27 drifted citations, mostly `hook.py` and `verify.py` line numbers from before the restructure (`docs/plans/2026-11-11-phase-2-live-tests/docs_drift-this-repo.txt`). A live run of the real guard on a real commit named the citing doc and the stale line. `verify.py` 1144/1144 PASS.
- Phase 2 step 2 (#509) built: every repo keeps a CHANGELOG.md. Session start names a repo without one; a turn that edits files in a repo that has one, without touching it, is sent back once (the changelog checkpoint); a pull request that leaves it unchanged gets a one-line reminder, never a refusal. This repo's own CHANGELOG.md starts with phase 1 and step 1.
- Step 2 checks, 2026-11-11: the helper's edit had pasted 1537 lines of `checks/design_loop.py` in twice (237 checks ran twice) and one pull request case ended in `or True`; both fixed, so the suite reads 1154/1154 PASS. The pull request reminder carried an "allow" that skipped Claude Code's own prompt; it now carries no decision (context-only output reaches the model, probed live on Claude Code 2.1.322). Live: 3 of 3 real sessions (`docs/plans/2026-11-11-phase-2-live-tests/live_changelog-result.txt`). The changelog row needs the design loop on (`HOUSE_RULES_LOOP`), like every checkpoint.
- Phase 2 step 3 (#510) built: after a merge the hook deletes the merged pull request's local branch when its tip is the merged head (a forced delete only then, for squash merges), and removes helper worktrees that are clean, pushed, and idle for 30 minutes; anything kept is named with the reason, and the default branch is never deleted. Checking it found and fixed four more things: a brand-new helper copy would have been removed mid-task, a pull request from main could have deleted local main, the merge hook printed two JSON objects (so its note could be lost), and it read pull request bodies over GraphQL, which cloud sessions refuse, so no merge was ever stamped there (phase 1's close offer depends on it). Live against real GitHub (#485): 4 of 4. `verify.py` 1167/1167 PASS.
- Phase 2 step 4 (#511) built (`scripts/house_rules/bigfiles.py`): a commit with a file over 50 MB is refused unless aj approved it ("LFS approved: <path>") and Git LFS tracks it; a file in a regenerated folder (Library/, Temp/, obj/, Builds/, node_modules/) is refused; aj's approval checks the 10 GiB free LFS allowance (GitHub's billing API, refused in cloud sessions, so there it counts this repo only and asks aj to confirm once); a new `diskreport` session-start hook names helper copies and generated folders over 5 GB. Live, real sessions and real Git LFS: 5 of 5 (`live_bigfiles-result.txt`). The guard on a commit: 0.10 s against 2.76.0's 0.06 s. `verify.py` 1181/1181 PASS. Not run: the billing API from aj's own gh login.
- Phase 2 step 5 (#512) built: two rule clauses (tunable values are never hardcoded; another repo's work becomes an issue there) with report-only checks (harvest names a new tuning-shaped literal; the end-of-turn check names a turn that wrote in two repos), and `rules/checks.json` mapping every rule section to the check that enforces it; a new rule with no check fails `verify.py`. Nine sections have no enforcing check today and are listed with reasons in checks.json's `unenforced` list. Live: 2 of 2 (`live_rules-result.txt`). `verify.py` 1194/1194 PASS.
- Phase 2 steps 6 and 7 (#513, #514) built: Research.md and Vocabulary.md are optional tier files (this repo has both, from its real record); seven `verify.py` cases prove #199, #399, #404, #479 and #463; `docs/4-systems/docs-and-files.md` describes what was built; plugin 2.79.0. Every check in the plan ran: `verify.py` 1204/1204, `tools/verify_tools.py` 52/52, live tests for each step (`docs/plans/2026-11-11-phase-2-live-tests/`), hooks timed against 2.78.0 with no slowdown, a real session in a fresh clone with every hook exit 0, and install from the branch then roll back to main. Phase 2 is built; aj's QA is next.
- 2026-11-11, at aj's word: `scripts/docs_drift.py` was used on this repo's own docs and fixed 21 stale citations (27 down to 6; the 6 left are history and one shell variable, which need a small checker change). On PlunderSpell (attached read-only this session) it found 2 real drifted citations (`docs/4-systems/alarm.md:326`, `docs/4-systems/raid.md:203`). PlunderSpell's tracked files come to about 1 GB in a shallow clone, the largest 24.8 MB, and `.claude/worktrees/` is ignored there, so the 153 GB on aj's PC is not in git; the disk report measures it on the PC.
- 2026-11-12, first Windows run of the branch (aj's PC, a separate Claude config folder, plugin 2.79.0): `verify.py` 1195 of 1203 pass. Of the 8 failures, 7 are older tests (safe_git 79, 81, 177, 203; design_loop 264, 341; make_page A14), matching the 7 that `main` already failed on Windows on 2026-11-08; the one new failure is #301's two-repo check, whose test compares a Windows path (`C:\...`) with git's (`C:/...`). `tools/verify_tools.py` fails only A16, also failing on `main`. The drift check needed `safe.directory` because the clone folder is owned by Administrators; with it, it reported the same 6 history and shell-variable citations as here.
- 2026-11-12, fixes after phase 2 QA (#516 to #518) built: the two-repo report puts git's `C:/...` paths in Windows form before comparing them (#517), and the drift check skips dated log lines, lines saying a file was deleted or removed, and shell variables (#518). This repo's docs now list 0 drifted citations; PlunderSpell still lists its 2 real ones. `verify.py` 1209/1209 PASS; live two-repo test 2 of 2 again. The Windows rerun is aj's to do on the PC.
- 2026-11-12, Windows rerun after the fixes (aj's PC, Windows PowerShell, branch at 0050cf9): `verify.py` 7 of 1208 failed, exactly the 7 older tests `main` also fails on Windows (79, 81, 177, 203, 264, 341, A14); the docs part, holding the #301 two-repo check, passed 159 of 159. `tools/verify_tools.py` failed only A16, as on `main`. `docs_drift.py`: 0 drifted citations in 26 living docs. Phase 2 adds no Windows failure.
