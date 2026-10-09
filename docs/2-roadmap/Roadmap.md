# Roadmap

What 0-100% means for each milestone, and what "done" is checked against. A milestone is done
when its acceptance criterion has actually been run and passed, not when the code exists.

## 1. The house-rules hook engine — 100%

Enforces aj's global CLAUDE.md rules as Claude Code hooks, on every device and every project,
without a per-repo file to copy around.

**Contains.** Eleven hook handlers dispatched from
[`hooks.json`](../../claude-house-rules/plugins/house-rules/hooks/hooks.json) through
[`hook.py`](../../claude-house-rules/plugins/house-rules/scripts/hook.py)'s `EVENTS` table —
`inject`, `standards`, `scope`, `guard`, `artifact`, `runnable`, `delegate`, `announce`,
`verdict`, `handover`, `harvest`. The `@house-rules:builder` subagent that the model-split rule
actually runs on. Full detail in [`docs/4-systems/hook-engine.md`](../4-systems/hook-engine.md).

**Acceptance.** `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
**Checked 2026-09-15: 203/203 PASS.**

## 2. The six-tier documentation convention — 100% as a mechanism

`house-rules:project-docs` defines the tier structure this very file is part of, and the plugin
routes rationale/post-mortems into `docs/6-decisions/Decisions.md` rather than into a tier-4 system doc.

**Contains.** The `house-rules:project-docs` skill, the tier list and card format in
`rules/house-rules.md`, `hook.py`'s `harvest`/archivist routing to `docs/6-decisions/Decisions.md`, and
`verify.py`'s tiered-docs drift checks (the rule names the skill, the skill specifies all six
tiers, the routing text agrees in both directions).

**Acceptance.** The tiered-docs checks inside `house-rules`' `verify.py` pass (they're part of
the 203 above, checked 2026-09-15). This criterion is about the **mechanism** — a repo *can*
adopt the six tiers and the plugin routes correctly if it does. Whether *this* repo's own
`docs/` actually instantiates all six is tracked separately, in
[`ProjectState.md`](../3-state/ProjectState.md), because "the mechanism works" and "every repo has adopted
it" are different claims — the second was explicitly deferred as its own follow-up in
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](../archive/2026-09-15-sixth-documentation-tier.md).

## 3. Offshoot plugins (`prompt-workshop`, `agent-router`) — 50%

Two v0.1 shells copying the `house-rules` formula toward "what should the work even be" instead
of "how should it be handed back." Both plugin.json versions read `0.1.0`.

**Contains.** `prompt-workshop`'s under-specification nudge and `agent-router`'s three-tier
model-routing nudge, each a full shim+hook.py+verify.py+agents set, not stub code. Detail in
[`docs/4-systems/offshoot-plugins.md`](../4-systems/offshoot-plugins.md).

**Acceptance, split because the mechanism and the judgment quality are different claims:**

- *Mechanism ships and verifies* — `prompt-workshop`'s and `agent-router`'s `verify.py` both
  exit 0. **Checked 2026-09-15: 22/22 and 41/41 PASS.** Done.
- *The classifiers are good enough to trust unattended* — **not done, and not yet measurable.**
  Both heuristics were verified only against hand-picked cases in their own suites, never against
  real prompt traffic; neither ships `SubagentStart`/`SubagentStop` visibility to confirm a
  suggestion was acted on or that a routed subagent ran on its declared model. These are named as
  open questions by the plan that built them
  ([`docs/offshoots-plan.md`](../offshoots-plan.md#open-questions-not-resolved-by-this-shell)), not
  newly discovered here.

50% reflects "the mechanism is real and passes its own tests" against "the actual value
proposition — good routing — is unvalidated," weighted roughly even.

## 4. Distribution & install tooling — 100%

Getting all three plugins onto a machine, upgrading an existing install without stranding it on
an old version, and writing the two settings only a machine-level install can write.

**Contains.** `tools/install.py`'s four-command `install_steps()`, `bootstrap.ps1`/`bootstrap.sh`,
`tools/update.bat`, `tools/clean_install_test.py`, and `tools/verify_tools.py`. Detail in
[`docs/4-systems/plugin-distribution.md`](../4-systems/plugin-distribution.md).

**Acceptance.** `python tools/verify_tools.py` exits 0 — **checked 2026-09-15: 32/32 PASS.**
Additionally, per prior recorded verification on this machine, the real `bootstrap`/`plugin
update` command sequence has actually been run against the live `claude` CLI on this device (not
just its decision logic in isolation) — the higher bar `clean_install_test.py` exists for. Not
re-run as part of writing this roadmap; see [`ProjectState.md`](../3-state/ProjectState.md) for what that
means for how fresh this claim is.

## Open issues, in the order to take them

Triaged 2026-10-09 against `main` at `34639ce` (house-rules 2.59.1), with every one of the 97 open
issues read in full, the open pull requests (Ajw2003/AjsClaudeCodeTools#166, #190) and the unmerged
`ccr-9ab94e76-iufs44` branch checked for work already under way.

**How the order was set.** Each issue is placed by two things together: how bad it is when it bites
(a safety hole or lost work beats an annoyance), and how often it gets in the way of a normal working
day (every session beats once a month). Where those disagree, a safety hole wins. Issues that are the
same change are listed together, so they can be done in one go. Within a tier, the first item goes
first.

The previous version of this section (triaged 2026-09-28) listed groups A and B. Every issue in them
is now closed (#47, #85, #87-#93, #96-#98), so they are dropped here. Its unnumbered efficiency and
issue-workflow follow-ups are kept, in P2.

### P0. Safety holes and things that stop work every day

Fix these first. Each one either lets something risky through unchecked, or halts a session or a
helper on ordinary work.

1. **#200 The guard misses `rm`, `nohup` and background jobs on a second line.** A multi-line
   command can delete files or hide a process with no prompt. It's a one-pattern fix plus a test.
   It's been there since 2026-09-11, and neither open branch changes it.
2. **#196 Permission prompts stop stalling sessions and helpers** (children #197, #198, #199). This
   is the most common day-to-day blocker: helpers stall on every commit, and one unanswered prompt
   refuses everything after it. Built on `ccr-9ab94e76-iufs44`, which has no pull request yet. It
   covers #134 (helpers prompt on every commit), #136 (builders blocked on deletes and scripted
   writes), #173 (a timeout blocks safe work), #159 (the timer is lost on a worker restart), the
   `-C` half of #192, and the timed-out-prompt part of #172.
   - **Do with it:** #203 (any "cd" in a command, even in a commit message, makes commits prompt).
     It's the same code (`_ANY_CD_RE`), and that branch keeps the bug.
   - **Do with it:** #193 (prompts say in plain words what they're asking). Once only destructive
     prompts are left, each one needs to be readable from a phone at a glance.
3. **#189 The attribution guard misses commits that set the author with a quoted `-c` value.**
   Commits credited to Claude went out unchecked in another repo. The fix is pull request #190
   (`AjsAgent/quoted-git-options`), which is open and ready to review. The same `_GIT` prefix is
   shared by every git rule, so this also closes a way around the other git guards.
4. **#201 The two-subagent limit loses agents started at the same time.** In a test, 100 of 100
   simultaneous starts lost a record, and 24 left the state file broken, which wipes the list. The
   fix is to reuse the lock that `_waiting_update` already has.
5. **#179 Cloud sessions get the attribution setting, and every cloud environment installs the
   plugin.** Every cloud session starts from the environment's filesystem snapshot. That snapshot
   is rebuilt only when the setup script changes or about every seven days. This environment's was
   taken on 2026-10-07, so sessions start on house-rules 2.53.0 and only load the update the session
   after. Installing from `main` in the setup script fixes both that and the missing attribution
   setting.
6. **#191 Pull requests opened from a cloud session still get a Claude footer added after creation.**
   Every pull request a cloud session opens credits Claude. The checked fix: re-read the body after
   creating it and edit the footer out. The "with Claude" label can't be removed from a cloud
   session; the rule should say so.
7. **#114 The installer reports a false failure right after an update.** It's the moment you most
   need to trust the result, and it sends you investigating a problem that doesn't exist. Labelled
   high priority.

### P1. Rules that don't fire yet, and friction you hit most weeks

The rule text covers these, or you've asked for them, but nothing enforces them yet, or they slow a
working day down without stopping it.

1. **#128 The issue workflow works however the work was planned** (children #129, #130, #131,
   #132). Today it's only enforced after plan mode. #119 is the same problem, written up before the
   split, so close it as covered once this lands. Your older requests #94 and #103 (open issues
   automatically and track progress through them) are what this delivers.
   - **Do with it:** #141 (ask to close each finished issue, so they stop piling up). It's the
     closing half of the same loop.
2. **#194 Steps that aren't shell commands skip the step-card check.** Browser and app steps (make a
   token, paste a secret) reach you as a bare list. It happened on 2026-10-09.
   - **Related:** #155 (waiting-on-you items as clear cards, or as multiple-choice questions in the
     app).
3. **#150 A running builder's progress can't be followed from the phone.** You only see the start
   and the final report. Pairs with the stall-check work below.
4. **Builder behaviour rules,** all for `agents/builder.md`, one change:
   - #160: builders over-test;
   - #139: one run per in-game or harness check;
   - #138: wait loops grep raw Unity JSON and never match.

   Each one costs minutes to hours per build in game projects.
5. **#140 Make a handoff document and commit everything at 95% usage.** Without it, work in flight
   at the usage limit is lost.
6. **#156 Delete Claude's branches once their pull request has merged.** This repo has 74 branches,
   and about 25 of them share no history with `main`.
7. **#158, #102 A plain-language "here's what changed", with a visual check, before finishing and
   pushing.** Partly built already: the plain summary first (#98) and the screenshot rule (#88/#96).
   What's left is the end-of-task pass and fail conversation.
8. **#137 Handed-over Windows commands that start with `&` keep failing.** Pick one form that works
   in both PowerShell and cmd, then update `docs/example-environment.md` and `handover-command.md`.
9. **#118 Skip delegation when the session is already on Sonnet.** It saves a cold start on every
   delegated job there.
10. **#127 stallcheck counts a just-resumed agent's age from before the watch started.** It isn't
    reproduced yet; the next step is to reproduce it.
11. **#117 Never hardcode values; expose them to the user.** A rule request for the code standards.
12. **#116 Unity work opens a fresh project, or a second editor, by default.** A rule request for the
    Unity standards.

### P2. Upkeep: speed, tidiness and the engine's own structure

Nothing breaks for you if these wait, but each one makes the next change slower or riskier.

1. **#202 `docref check` always fails here,** because it reads `verify.py`'s own test pointers. It
   can't join CI until this is fixed.
2. **#204 Every hook call recompiles all of `hook.py`.** That's about 47 of 87 ms per call, and an
   Edit fires up to eight hooks.
3. **#41 One failure-mode contract,** in the `EVENTS` table.
   - **Do with it:** #205 (with no Python, `guardgithub` and `commitgate` let everything through
     silently). It's the `run.sh` copy of the same contract.
4. **#42 One payload-field extractor.**
   - **Do with it:** #206 (two copies of "which folder does this command run in").
5. **#44 `verify.py` gets a name filter.** It's now over 8,000 lines and always runs every check.
6. **#43 Split `event_standards` into detect and render.**
7. **#46 Re-check the agent frontmatter fields `verify.py` forbids.**
8. **#45 A glossary and one decision record per reversal.**
9. **Hooks-efficiency follow-ups** (from `docs/plans/hooks-efficiency-review.md`; findings 1-3
   shipped in 2.48.0):
   - 2b/2c: one dispatcher per event, then per-event modules;
   - 4: duplicated resolvers in `hook.py`;
   - 5: rule-base weight and repetition, and the stale token figure in `docs/architecture.md`;
   - 6: rules that conflict or over-fire;
   - 7: make the docs-tier reminder cheaper to resolve;
   - 8: repo maintenance (one shared `run.sh`, offshoot overlap, `worktreesweep`'s per-prompt walk).
10. **Issue-workflow leftovers** (from `docs/plans/issue-workflow-build-plan.md`):
    - commits with no issue number get an end-of-turn check;
    - `gh issue create` through PowerShell isn't recorded by the gate;
    - win back the inject size margin.
11. **#95 Cost of delegating versus doing it on the main thread, with a chart.** Builds on
    `tools/measure_footprint.py`.
12. **#71 Archive a whole session,** subagents included. It extends `tools/session_ledger.py`.

### P3. Separate tracks: worth doing, but they don't touch the daily workflow here

- **The art-pipeline plugin (#161),** on pull request #166 (`claude/art-pipeline`):
  - #167: get pull request #166 green and installable first;
  - then #162, #163, #164, #168, #169, #170, #171;
  - the eldritch goose asset (#183, children #184-#187) is its first real use, so it waits on
    #167.
- **Retroactive attribution across aj's repos,** in this order:
  - #181: a report only;
  - #182: renames, after you've read the report;
  - #180: Focus Deck's reserved label (work happens in Ajw2003/focus-deck-app).
- **#105 Dynamic subagent dispatch.** Largely overtaken by the three helper tiers (#111, closed).
  Re-scope it or close it.
- **Research with nothing to build yet:**
  - #69: port the superpowers subagent-driven-development workflow;
  - #62: the agyrules dynamic subagents, which need that plugin's source.

### Built, waiting on your test before closing

Each of these is on `main` with tests passing. It's open only because closing needs your yes after
you've tried it (rule: a pull request never closes an issue). Some also need a check in a real
session that can't be done from the test suite. That check is noted where it applies.

- **Stall check:**
  - #120, #122, #123, #124, #125: re-alerts, session scoping, STALLED guidance, waits with a time
    limit.
- **Prompt timer:** #142 and its children.
  - #144, #145, #146, #149, #151, #152 are built.
  - #147 still needs the overnight-style check in a real session.
  - #159 isn't fixable from the plugin as it stands; #198 removes the case.
- **Destructive steps on a pushed agent branch:** #153. Still needs a real session confirming the
  prompt disappears.
- **Attribution:**
  - #133: the rule and the guard;
  - #174: the parent;
  - #175: `AjsAgent/` branches and label;
  - #176: cloud sessions move to `AjsAgent/`. Still unchecked: whether the app's "Create PR" button
    follows the new branch;
  - #177: commit author;
  - #178: GitHub tool calls.
- **#192 Commits on an agent branch prompt outside the session's main folder.** The `cd` and
  worktree half shipped in 2.59.1. The `git -C` half is in #197.
- **Issue workflow:**
  - #110: approved plans become issues (2.49.0);
  - #107: the parent plan, with the helper tiers (#111, #112, closed).
- **#113 The note that said helpers never see the project instructions file.** Fixed in 7c57cf4.
- **#172 Builders can't recover from failed or timed-out tasks.** This issue has no description. The
  timed-out part is covered by #196. Say what else it meant, or close it.
