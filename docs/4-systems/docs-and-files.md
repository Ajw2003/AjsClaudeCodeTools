# Docs and files you can trust

## What it owns

That the record a session leaves behind is right: the docs agree with the code, every repo has a changelog, finished
branches and helper copies are cleaned up once their work is safe on GitHub, and no big or generated file reaches git
without aj's word. Roadmap phase 2, issue #494. Design page `docs/plans/2026-11-11-phase-2-docs-and-files.html`,
approved 2026-11-11 as "Design approved: Phase 2 1A 2A 3A 4A 5A".

## How it works (built 2026-11-11, plugin 2.79.0)

| Piece | Where | What it does |
|---|---|---|
| Docs named at the commit (#508) | `_staged_docs_status` and `_citing_docs_note` in `scripts/house_rules/docs.py`, shown by the guard | The guard's message for a commit names each living doc that cites a file the commit changes, by path, partial path or bare name, and any drifted citation of those files. Living docs: tiers 1 to 5, `docs/architecture.md`, `docs/README.md`, `README.md`, `CLAUDE.md`; never `docs/6-decisions/`, `docs/plans/` or other history. |
| Drift check (#508) | `scripts/docs_drift.py` | Lists every citation in the living docs to a path that is gone or a line past the end of its file; a name shared by several files counts only when the line is past the end of every one; a bare name that is no repo file (a runtime file) is skipped. Exit 1 when any. |
| Changelog (#509) | `templates/CHANGELOG.md`; `event_docstiers`; the `changelog` row in `CHECKPOINTS` (`design_loop.py`); `core.pr_changelog_note` | Session start names a repo without `CHANGELOG.md`. In a repo with one, a turn that wrote files outside `.claude/` and left it alone is sent back once (the row needs the design loop on). Opening a pull request whose branch leaves it unchanged adds a reminder with no permission decision, so Claude Code's own prompt stays. |
| Cleanup after a merge (#510) | `_merge_cleanup` in `design_loop.py`, run by `event_closablemerge` | Deletes the merged pull request's local branch when its tip is the merged head (`branch -d`, then `-D` only under that condition, for squash merges); never the default branch or a checked-out one. Removes helper worktrees under `.claude/worktrees/` that are clean, pushed, merged and idle for 30 minutes (`worktree remove`, never `--force`). Names what it deleted and kept, and why. `HOUSE_RULES_CLEANUP=off`. |
| Big files (#511) | `scripts/house_rules/bigfiles.py` | A commit with a file over 50 MB (a starting value) is refused unless "LFS approved: <path>" from aj recorded it and Git LFS tracks it; real size is measured, so an LFS pointer does not hide it. A file in a regenerated folder is refused. The approval checks the 10 GiB free LFS allowance from GitHub's billing API, or, where that is refused (cloud sessions), this repo's LFS files, and then asks aj to confirm once. |
| Disk report (#511) | `event_diskreport` (SessionStart) in `bigfiles.py` | Names helper worktrees and regenerated folders over 5 GB (a starting value) with their size, within 6 s. `HOUSE_RULES_DISKREPORT=off`. |
| Rules with checks (#512) | `rules/checks.json`; harvest; the end-of-turn two-repo line | Every rule section maps to the check that enforces it, and `verify.py` fails on a new section with none; the nine with no check today are listed with reasons. Harvest names a new tuning-shaped literal; the end-of-turn check names a turn that wrote in two repos. |
| Research and vocabulary (#513) | `OPTIONAL_TIER_FILES` in `docs.py`; `skills/project-docs/SKILL.md` | `docs/6-decisions/Research.md` and `Vocabulary.md` are optional tier files, never asked for. |

The approved plan, step by step, with what changed while building, is in `docs/3-state/ProjectState.md` (the
2026-11-11 phase 2 lines) and the commits that say `Refs #508` to `Refs #514`.

## Testing (every check phase 1 had, at aj's word on 2026-11-11)

1. Every step: its own verify.py cases, each written to fail on today's code and pass after, then the full verify.py (the baseline is 1135 of 1135) before the step merges.
2. Every helper's work is read as a diff and merged only after the full verify.py passes again on the branch; each claimed fix is checked by running it, not by the helper's report.
3. Real headless Claude sessions (claude -p) loading only this branch's plugin, with the installed copy switched off, walk a throwaway repo through every new behaviour: a commit naming the docs that cite it, a turn sent back for a missing changelog line, a branch and worktree deleted after a real merge and kept when unpushed, a big file refused, then let in after "LFS approved", and refused again when it would pass the allowance.
4. Real git and real Git LFS: a real 60 MB file, a real git lfs track and commit, a real merge followed by the cleanup, and a real dirty worktree that must survive.
5. The drift check run on this whole repo, with its list of dead citations on the QA page.
6. Each hook phase 2 changes, timed five times against 2.78.0 on a fresh clone; every exit code must be 0.
7. A real session in a fresh clone of the branch, listing every hook's result, with no hook error.
8. Install from the branch URL into an empty Claude config, then roll back to main, checking the version each time.
9. tools/verify_tools.py in full.
10. The test scripts and their saved results committed under docs/plans/, as phase 1's were.
11. The QA page lists anything that could not run here and says what stopped it (for example: your Windows PC, the billing API from a cloud session, PlunderSpell's 153 GB).

## Not known yet

- Why PlunderSpell's folders take over 153 GB. Not measured: the folder is on aj's PC and this cloud session was
  refused access to that repo. The disk report from step 4 measures it at the next session start there.
- Whether aj's own `gh` login can read GitHub's billing API (it is refused from a cloud session; checked 2026-11-11).
