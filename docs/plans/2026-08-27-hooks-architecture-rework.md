# house-rules: hooks architecture rework

Status: **implemented** — confirmed 2026-08-27, delivered in five commits on this branch.
Date: 2026-08-27
Branch: `claude/grillme-iuqx4y`

## Why

Four problems, found by auditing the plugin against its own documentation:

1. `CLAUDE.md` describes "four hooks, nothing else". Reality is seven scripts on five
   events. The three undocumented ones (`track-write.sh`, `clear-pending.sh`,
   `deliverable.sh`) implement a stateful "you never ran that script" nag. The doc also
   hardcodes "34-check suite" in three places while `verify.sh` computes its count at
   runtime — so the number drifts silently.
2. That nag is the only stateful subsystem here, and it leaks: its `$TEMP` state file is
   removed only by a later shell command or by `Stop` firing. Any session that ends
   otherwise leaves a file behind forever, with no reaper. It also violates the plugin's
   own "artifacts never live in a temp directory" rule, and it is defeated by any
   unrelated shell command.
3. `guard.sh` matches the whole raw payload, which includes the tool `description` field —
   so a Bash call *described* as "check for uncommitted changes before we commit" prompts.
   `artifact.sh` already solved this by extracting one field; `guard.sh` never adopted it.
4. `Claude2.0plugins/` is a complete abandoned node implementation still checked out,
   carrying a second `.claude-plugin/marketplace.json` — a real footgun for
   `claude plugin marketplace add`.

## Settled decisions

| # | Decision |
|---|---|
| Q1 | Rewrite `CLAUDE.md` to match reality **and** add a `verify.sh` case that fails when `hooks.json` names a script the docs' table does not. De-hardcode the check count everywhere. |
| Q2 | Collapse the deliverable nag to stateless. Delete the `Stop` hook, `deliverable.sh`, and `clear-pending.sh`. |
| Q3 | Delete `Claude2.0plugins/` entirely. Git history preserves it. Delete the 0-byte `New Text Document.txt`. |
| Q4 | `guard.sh` extracts the `command` field with `grep -o`, same one-liner already used twice, and matches against that instead of the whole payload. |
| Q5 | The replacement reminder is its own script: `track-write.sh` gutted of state and renamed `runnable.sh`. One script, one rule. |
| Q6 | It fires on `Write` only (never `Edit`) and skips files in known-outside-the-project locations. |
| Q7 | `guard.sh` gets a three-tier ladder: unreadable payload -> `exit 2` (unchanged); readable but no `command` field -> fall back to whole-payload matching, exactly as today; field found -> match that alone. Strictly safer than today, never weaker. |
| Q8 | Split the git verbs across rules. Mutating verbs stay under "Never commit without asking". Destructive forms move to "Never take a destructive action without checking first". Navigational verbs stop prompting. |
| Q9 | `scope-check` skill: delete now with the tree, port later as its own change. Not part of this work. |
| Q10 | `runnable.sh` reuses `artifact.sh`'s known-outside-location patterns rather than introducing `cwd` or `$CLAUDE_PROJECT_DIR`. No new mechanism. |
| Q11 | Reminder text names the rule, states the action, and says the user was not prompted — and `verify.sh` pins its key phrases against `house-rules.md`, the way step 31 pins `scope.sh`. |
| Q12 | Rule 4 gets a distinct reason line per git form. Not a shared "deletes files" line. |
| Q13 | `verify.sh` keeps its flat numbered structure. Revisit at ~100 cases. |
| Q14 | Four commits, docs last, suite green at each step. |

## Resulting shape

Five hook scripts on four events:

| Event | Script | Matcher | Effect |
|---|---|---|---|
| `SessionStart` | `inject.sh` | — | injects `house-rules.md` + `environment.md` |
| `UserPromptSubmit` | `scope.sh` | — | standing reminder, zero dependencies |
| `PreToolUse` | `guard.sh` | `Bash\|PowerShell` | extracts `command`, matches rule patterns, returns `ask` |
| `PostToolUse` | `artifact.sh` | `Write\|Edit` | document written outside the project -> reminder |
| `PostToolUse` | `runnable.sh` | `Write` | runnable file created in the project -> reminder |

Every script is stateless. Nothing writes to `$TEMP`.

## Commits

### 1. guard.sh: narrow the input, split the verbs

- Extract `"command"` with `grep -o`, first match only.
- Three-tier ladder per Q7. Empty extraction falls back to `$PAYLOAD`.
- Rule 3 verbs: `commit|push|reset|revert|clean|rebase|merge|filter-branch|cherry-pick|am|apply`.
- Rule 4 gains, with its own reason line each:
  - `git checkout --` / `git checkout .` / `git restore` -> "throws away uncommitted edits to a file"
  - `git stash drop` / `git stash clear` -> "deletes stashed work permanently"
- Drop `add|checkout|switch|branch|tag|remote|submodule` as bare prompts.
- `verify.sh` cases: fallback tier still catches `git commit` with no `command` field; a
  `description` mentioning commit no longer fires; each split verb fires under the correct rule.

### 2. Replace the Stop machinery with a stateless reminder

- Delete `deliverable.sh`, `clear-pending.sh`, and the `Stop` block in `hooks.json`.
- Rename `track-write.sh` -> `runnable.sh`; strip all state. Keep the extension test
  (`py|js|mjs|cjs|ts|sh|ps1|bat|cmd`, bare `Dockerfile`/`docker-compose.y?ml`).
- Add the outside-location skip, reusing `artifact.sh`'s patterns.
- Reminder text: names the rule ("whole workflows"), states the action, closes with
  "do not hand over a command you have not run", says the user was not prompted.
- `verify.sh`: remove the 10 `deliverable.sh`/`clear-pending.sh` cases; add fires-on-write,
  does-not-fire-on-temp-path, and the text drift pin.

### 3. Delete the legacy tree

- `rm -r Claude2.0plugins/` and `New Text Document.txt`.
- Confirm the root `.claude-plugin/marketplace.json` is the only one left.

### 4. Docs and the drift check

- Rewrite the `CLAUDE.md` architecture section: five scripts, four events, the table above.
- Replace every hardcoded "34" with "the suite".
- New `verify.sh` case: every script named in `hooks.json` appears in `CLAUDE.md`'s table,
  and vice versa. This is the case that stops problem 1 recurring.

## Not in scope

- Porting `scope-check` as a plugin skill (Q9 — separate change).
- Any change to `inject.sh`, `scope.sh`, `environment.md`, or `tools/`.
- Measuring guard false-positive rates. Q4/Q8 fix the known causes; no instrumentation.

## Done when

`sh claude-house-rules/plugins/house-rules/scripts/verify.sh` exits 0 after each of the
four commits, and `.\tools\clean-install-test.ps1` passes against the pushed branch.

## What actually happened

Four commits as planned, plus a fifth that was not.

The baseline was **40 checks, not 34** — the docs had drifted further than the audit found.
The suite ends at **54**.

Commit 5 fixes the plugin's own `README.md`, which documented `track-write.sh`,
`clear-pending.sh` and `deliverable.sh` with markdown links to all three. Commit 2 deleted
those files, so the README that ships with the plugin carried three broken links. That was a
defect introduced by this branch, not pre-existing drift, so it was fixed rather than left
for a follow-up. Every check-by-number reference went with it, for the same reason the counts
did.

Two things were found by testing rather than by reasoning, and both would have shipped
silently:

- The first version of the docs-vs-`hooks.json` drift check grepped the whole of `CLAUDE.md`.
  Every script is also discussed in the prose below the table, so deleting a table row still
  passed — the check proved nothing. It is now scoped to the table rows, and was confirmed by
  deleting a row, adding an unregistered script, and reinstating a hardcoded count.
- `runnable.sh`'s reminder originally said "written but never run", which is not the rule's
  wording. The drift pin added in the same commit caught it. The text now reads "a starting
  point, not a whole workflow", which is the rule.

Still outstanding: `.\tools\clean-install-test.ps1` has not been run. It is PowerShell and
needs the Windows machine — see the handover note in the final report.
