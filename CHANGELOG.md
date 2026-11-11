# Changelog

What changed in this repo, newest first. Plain words first, exact detail after.

## Unreleased

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
