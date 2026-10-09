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
  `claude/` branch. #189 is fixed (2.60.0): git rules no longer miss a command whose `-c` value is
  quoted with a space in it (`-c user.name="aj's agent"`), which had let six Claude-credited commits
  through. Not built: #179 cloud settings, #180 Focus Deck label, #181-#182 retroactive report and renames.
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
