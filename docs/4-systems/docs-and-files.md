# Docs and files you can trust

## What it owns

That the record a session leaves behind is right: the docs agree with the code, every repo has a changelog, finished
branches and helper copies are cleaned up once their work is safe on GitHub, and no big or generated file reaches git
without aj's word. Roadmap phase 2, issue #494. Design page `docs/plans/2026-11-11-phase-2-docs-and-files.html`,
approved 2026-11-11 as "Design approved: Phase 2 1A 2A 3A 4A 5A".

## Planned: phase 2 (2026-11-11)

Seven build steps, one sub-issue each (#508 to #514), built one after another:

1. **Drift at the commit (#508, 1A).** `_staged_docs_status` in `scripts/house_rules/docs.py` already works out what a
   commit will include. It also names each doc under `docs/` that cites one of those files (by path or `file:line`),
   and a drift check flags citations to files that are gone or lines past the end of the file.
2. **Changelog (#509, 2A; #384 to #388, #244).** `templates/CHANGELOG.md`; the docs tiers scaffold it; `docstiers`
   names a repo without one; the end-of-turn checkpoint table gets a `changelog` row that sends a turn back once when
   it wrote files but added no changelog line; opening a pull request whose branch leaves the changelog unchanged
   gets a reminder; the documentation rule names it.
3. **Cleanup after a merge (#510, 3A; #156).** When `event_closablemerge` sees a merge, the merged local branch is
   deleted if every commit on it is on GitHub and in the merge, and helper worktrees that are clean and pushed are
   removed. The session is told which, and which were kept and why. Remote branches follow GitHub's own setting.
4. **Big files on aj's word (#511, 4A).** The commit check refuses a staged file over 50 MB (a starting value) and a
   file inside a regenerated folder (`Library/`, `Temp/`, `obj/`, `Builds/`, `node_modules/`) that `.gitignore`
   does not cover. "LFS approved: <file>" in aj's own message, one file at a time, is recorded in the stage file;
   that file may then go in through Git LFS once the allowance check passes. The check reads the account's LFS use
   from GitHub's billing API; that read is refused in cloud sessions (tried 2026-11-11), so there it adds up this
   repo's LFS files, says other repos were not counted, and asks aj. Session start names helper worktrees and
   generated folders over 5 GB (a starting value).
5. **Three rules (#512, 5A; #117, #301, #228).** No hardcoded tunable values; a session finishes its own task and
   other repos' work becomes an issue there; every rule section names the check that enforces it, proven by a
   `verify.py` case.
6. **Research and vocabulary (#513; #336, #45).** `docs/6-decisions/Research.md` and `docs/6-decisions/Vocabulary.md`,
   optional tier files the docs check lists but never requires.
7. **Proof, docs, version, QA (#514).** `verify.py` cases for #199, #399, #404, #479 and #463, this doc moved to
   built, plugin 2.79.0, live tests, and the QA page.

## Not known yet

- Why PlunderSpell's folders take over 153 GB. Not measured: the folder is on aj's PC and this cloud session was
  refused access to that repo. The disk report from step 4 measures it at the next session start there.
- Whether aj's own `gh` login can read GitHub's billing API.
