# Today — 2026-09-30

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
