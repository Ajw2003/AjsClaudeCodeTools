# Rerun limit

**Owns:** stopping any agent, a builder or the main thread, from running the same project script a
third time with no new commit in between. Status: designed under issue #453 ("Stop builders
rerunning the same check: a builder rule and a hook that enforces it"). aj approved the design on
2026-11-02 as "Design approved: rerun limit 1B 2B 3B" on `docs/plans/rerun-limit-hook-plan.html`.
The builder rule half shipped in 2.74.3; this hook is built in 2.75.0 (#454), in `_rerun_check` in
`scripts/house_rules/safe_git.py`, with cases 191 to 197 in `scripts/checks/safe_git.py`.

**Changed in 2.80.0 (speed switches, #525):** the count is kept per command (the same script with
the same arguments) and resets when any code file changes, committed or not, rather than on a new
commit. Editing only the script or the docs still does not reset it. See `speed-switches.md`,
"Rerun check"; the sections below describe the 2.75.0 design.

## Why it exists

In Ajw2003/PlunderSpell#569, on 2026-11-02, a builder ran one co-op check 12 times in 23 minutes.
Each run opens Play mode and a second game window on aj's screen, and several runs went on repairing
the check rather than the code. The written rule in `agents/builder.md` limits a check to two runs,
but a rule is only text; this hook makes the limit hold.

## What aj chose

| Question | Choice | Meaning |
|---|---|---|
| What counts as the same check? | 1B | Any script file inside the project, whatever its arguments. |
| What resets the count? | 2B | Only a new commit, and only one that changes a file other than the script itself. |
| How does an agent get past it? | 3B | No override. Only a new commit, `HOUSE_RULES_RERUNS=off`, or aj. |

## How it works

1. **Where it runs.** Inside the existing `guard` handler (`PreToolUse` on `Bash|PowerShell`),
   next to the issue-workflow refusals, so no new hook entry is added. The probe on 2026-11-02 showed
   the hook fires inside a subagent and the payload carries `agent_id` and `agent_type`; the main
   thread's payload carries neither.
2. **Finding the script.** The command is split into statements and words. The first word in a
   statement that names an existing file inside the project (the git top level of the command's
   folder) with a script extension (`.sh`, `.bash`, `.py`, `.ps1`, `.js`, `.mjs`, `.ts`, `.rb`,
   `.bat`, `.cmd`) is the script. Its path relative to the project is its identity, so arguments
   do not matter. A command that names no project script is never counted, which keeps out
   `git status`, compiles and bare test runners.
3. **Who it counts for.** One count per session, per agent (`agent_id`, or `main` for the main
   thread), per script.
4. **Counting.** The state file `house-rules-reruns.json` sits in the common git directory, shared by
   every worktree, beside the `agentcap` state. Each record holds the script, the commit `HEAD`
   pointed at when it was last counted, and the count. A run is counted before it starts; a refused
   run is not counted.
5. **Reset.** When `HEAD` has moved since the record's commit, and `git diff --name-only <old>..HEAD`
   lists any file other than the script, the count starts again at zero. A commit that only changes
   the script does not reset it.
6. **Refusal.** The third run is denied (`permissionDecision: "deny"`), as the guard does for commits
   on `main`. The message names the script, and says: stop, read the code
   for the cause, and report what failed; do not edit the check; a new commit that changes the code
   allows two more runs.
7. **Off switch.** `HOUSE_RULES_RERUNS=off`. `HOUSE_RULES_RERUNS_STATE` points the state file
   elsewhere, so `verify.py` never writes into the real repository.
8. **Failure.** It fails open and loud: an unreadable state file, a missing `git` or a timeout lets
   the command through with a one-line `systemMessage` saying the count could not be checked.

## Refused runs are taken back

The count is taken before the guard's other rules run. When the guard then refuses the command or
asks about it, `_rerun_take_back` restores the record, so a run that never happened does not count.
This matters most inside a builder, where every ask becomes a refusal: the real-session test on
2026-11-03 lost a builder's first run this way before the fix (case 197 covers it). A run aj
approves after an ask is not counted either.

## Known cost of choice 1B

Every project script counts, helpers included. In this repo that means `verify.py`, `make_page.py`
and `docref.py`; in PlunderSpell, `eval.sh`, `recompile.sh` and `run_tests.sh`. An agent that runs
one of them a third time without committing is refused. Committing between runs, which the house
rules already ask for, keeps ordinary work moving.
