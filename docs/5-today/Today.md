# Today — 2026-10-09

House-rules rebuild started (#208): step 1's triage page is up for your approval, `docs/plans/2026-10-09-house-rules-rebuild-triage.md`. It sorts every part of the plugin into keep, merge or drop, and every open issue into fixed by the rebuild, carried in, looks done, or another project. Nothing is cut yet.

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
