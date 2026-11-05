# Audit fixes

**Owns:** the order and scope of the fixes for the 45 findings in
[`docs/audits/2026-11-05-combined-ranked.md`](../audits/2026-11-05-combined-ranked.md). Status: planned, parent issue #476.
aj approved the order on 2026-11-05 as "Design approved: audit fix order 1A" on
`docs/plans/2026-11-05-combined-ranked.html`. Choice A means critical holes first, then the blocks
on routine work, then handoff and full disk.

Each finding's proof, cause and `file:line` are in its own report, and this doc doesn't repeat them:
A in `2026-11-05-ponytail-audit-full.md`, D in `2026-11-05-design-loop-deep-dive.md`, U in
`2026-11-05-loop-usability-audit.md` and H in the combined list.

## Rules for every step

1. **All the code is planned first, then approved once, then checked once.** aj decided on
   2026-11-05 ("plan out all of the code first and then show me it so I can approve or deny it
   rather than a 6 different QAs"). The exact proposed code for every finding is written in
   `docs/plans/audit-fixes-code/` before any source file changes. aj approves or denies it on one
   page. The six steps are then built in order, one builder per step, each committed with its
   checks passing, and aj gets one QA page for the whole build.
2. **A test with every fix.** Each fix lands with the `verify.py` case that fails before it and
   passes after it (finding A17). The case is written first and run against the old code.
3. **The three promises hold.** No fix may let anything other than aj's own message move a stage,
   open source edits before a build plan is approved, or delete something that can't be brought back.
4. **One version bump per step**, with the change recorded in `docs/3-state/ProjectState.md`.

## The steps

| Step | Findings | What changes | Main files |
|---|---|---|---|
| 1. Close the critical holes (#477) | A1, A11, D1, A3, A4, U5, A8 | Guard patterns: `$(...)`, backticks and `-c core.hooksPath` in a commit (A1); `/bin/rm`, `find -delete`, `unlink`, `: > file` (A3); `checkout HEAD --`, `switch -f` (A4); `worktree remove --force` (U5). Autosave adds tracked changes and the helper's written files only (A11). The installer writes `settings.json` through a temp file and `os.replace` (A8). Four more relayed-message markers in `_RELAYED_PROMPT_RE` (D1). | `safe_git.py`, `delegation.py`, `core.py`, `tools/install.py` |
| 2. Stop blocking routine work (#478) | A5, A6 + H3 + U8, U6 + H1, H2, U7 | `agent/` branches are owned (A5). A script counts as run only as the first word or an interpreter's first argument (A6). Single-quoted text and heredocs with a quoted delimiter are not read as commands, and `$(...)` inside double quotes still is (U6, H1). `restore --staged` and `reset HEAD <path>` are allowed (H2). The first cloud commit gets the identity fix in one refusal, not three (U7). | `safe_git.py`, `core.py` |
| 3. Fix handoff and full disk (#479) | U4, U1, U2, U2b | Folder deletes that git or an install can undo are allowed: ignored build output, `node_modules`, `/tmp`, caches, clean worktrees (U4). "Continue from: <branch>" in aj's message copies that branch's stage and issues (U1). "Issues for <feature>: #N" in aj's message records issues (U1, U2b). Issue recording sees `do gh`, `python -c` and `gh api` (U2b). The stage file is pushed straight after each approval (U2). | `safe_git.py`, `design_loop.py`, `core.py` |
| 4. Close the lock's side doors (#480) | D3, D4, A9, A7, D2, D9, A2, A10, and an issue for D10 | Legacy stage file ignored once a project has its own (D3). `.claude/settings.json`, worktree sources and code under `docs/` locked (D4). Shell writes to the stage file refused (A9). Stage file written atomically (A7). A question or a "don't" doesn't approve (D2). An old branch's stage isn't trusted when the label read fails (D9). Closing is unlocked only by a pull request that names the issue (A2). A placeholder record closes the helper-cap race (A10). D10 gets its own issue under the restructure. | `design_loop.py`, `delegation.py`, `core.py` |
| 5. Make approvals do what aj said (#481) | D5, D6, D7, D8, U3 | Re-approving in Build keeps the feature's issues (D5). An approval's name must match the feature or start a new one on purpose (D6). "skip design" ends with its stage (D7). Only the QA page built for this feature counts (D8). `main` gets no stage file from a merged feature (U3). | `design_loop.py` |
| 6. Tidy up (#482) | A12, A16, A13, A14, A15, D11, D12, H5, A18, A19, A20, H4 | Version check compares tuples (A12). `force_update.py` says when the plugin is left uninstalled (A16). The installer's tree hash skips caches (A13). The page builder's node check runs with `node -e` (A14). One commit `-a` check (A15). "Labelled" is read from the flags (D11). A `gh` failure isn't recorded as a label change (D12). `.txt`, `.csv` and `.json` are open (H5). Small dead-code and miscount fixes (A18 to A20). Merge the small hooks into fewer processes (H4), measured before and after. | various |

## How each step is proved

- The new `verify.py` cases fail on the old code and pass on the new.
- The full `verify.py` and `tools/verify_tools.py` pass.
- For steps 1 to 3, the commands from the audit's proof are run again through `hook.py <name>`
  in a throwaway repo, and each one now gets the decision the step promises.
- Step 3 is also tried in a real cloud session: a handoff with "Continue from:", and a
  `node_modules` delete on a full disk.

## Not decided yet

- Which exact folders count as "git or an install can undo" in step 3. The build plan for step 3
  will list them for aj before code.
- Whether H4's hook merge in step 6 is worth its size. It will be measured first.
