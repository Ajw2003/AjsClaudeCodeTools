# Vocabulary

The words this project uses, what each means here, and the decision that settled it where one did. A term that
changes meaning keeps its old meaning below the new one, dated.

**Approval line** - the exact words of aj's that move the design loop: "Design approved: <feature>", "Build plan
approved: <feature>", "QA passed: <feature>", "QA failed: <feature> <what's wrong>". Since phase 1 the feature name may
come first ("Phase 1 design approved 1A"), and a bare "Approve" reply button stands for the one line the last reply
offered. Settled: Decisions.md, 2026-11-10 "Phase 1".

**Build plan** - the page, after a design is approved, that shows each step with its planned code and its GitHub issue.
Approving it opens code edits.

**Changelog** - `CHANGELOG.md` at a repo's root: one plain line per change under "Unreleased", plain words first, exact
detail after. Settled: Decisions.md, 2026-11-11 "Phase 2" (2A).

**Checkpoint** - a row of the end-of-reply check table (`CHECKPOINTS` in `scripts/house_rules/design_loop.py`); a reply
that misses one is sent back once.

**Design loop** - the plugin's tracker for where a feature stands: Design, Plan, Build, QA, Done. Only aj's own messages
move it; code edits are open only in Build.

**Drift** - a doc citation that no longer fits the code: a file that is gone, or a line past the end of the file.
`scripts/docs_drift.py` lists it; a commit names the docs that cite what it changes. Settled: Decisions.md,
2026-11-11 "Phase 2" (1A).

**Feature issue** - the GitHub issue a feature's step issues name in "Part of #N"; the build plan approval reads the
feature's issues from it. Settled: Decisions.md, 2026-11-10 "Phase 1" (1A).

**Guard** - the PreToolUse hook (`event_guard` in `scripts/house_rules/safe_git.py`) that refuses destructive or
unowned git actions, names the safe way, and adds the docs, changelog and big-file checks to a commit.

**Handoff** - a session's work saved as it happens (autosave refs on GitHub plus `docs/5-today/handoff-<branch>.md`)
so the next session, on any account or folder, picks it up (the pickup at session start). Issue #406.

**Helper** - a subagent the main session hands an approved step to (builder, scout, reviewer, editor). It builds only
approved steps and never designs or approves; anything unexpected is a question for aj.

**Helper copy (worktree)** - a separate working copy of the repo under `.claude/worktrees/` that a helper builds in.
Removed after a merge only when clean, pushed and idle for 30 minutes. Settled: Decisions.md, 2026-11-11 "Phase 2" (3A).

**LFS approved** - aj's line ("LFS approved: <path>") that lets one big file into git through Git LFS, after the free
allowance is checked. Without it, files over 50 MB stay out. Settled: Decisions.md, 2026-11-11 "Phase 2" (4A).

**QA page** - the page a build is handed to aj on, built by `make_page.py` in QA mode, listing what was tested and what
could not be. Its reply is "QA passed: <feature>" or "QA failed: <feature> <what's wrong>".

**Stage file** - `.claude/house-rules-loop.json`, committed with the branch: the feature, its stage, aj's approvals and
its issues.
