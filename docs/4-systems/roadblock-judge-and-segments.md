# Roadblock judge tuning and one-minute segments

**Owns:** the written criteria the end-of-reply roadblock judge applies, where the judge runs, the
shared block cap, the reason standard, and the rule that every wait-bound job runs as independent
segments of at most 60 seconds. Status: design approved 2026-11-24 as "Design approved: judge
blocking fix and one-minute segments 1A 2A 3A"; built in plugin 2.93.0 except the 60-second flag
in the modular-tests gate and audit (issue #611, which waits on #578 and #579). Proposal page:
`docs/plans/judge-blocking-fix.html`. It extends, and does not replace,
`docs/4-systems/modular-tests.md` (issue #575) and `docs/4-systems/roadblocks.md` (issue #587).

## Why

A test session was blocked 12 times in a row by the end-of-reply judge, even when three different
methods had been tried. Read from the code: three checks run on every Stop and share nothing.

| Check | Where | Counter |
|---|---|---|
| Model judge | the `prompt` entry on Stop in `hooks/hooks.json` | none; sees only the last reply |
| Phrase and record check | `roadblock_check` in `scripts/house_rules/core.py` | 2 blocks |
| Goal check | `_goal_check` in the same file | 6 blocks, separate counter |

The model judge's rule is one sentence. It never says what a different method is, never sees the tool
calls, and never says which rule failed, so a model that did the work could still fail. The 12 blocks
were not reproduced: no transcript of that session was found.

## Choices made (aj, 2026-11-24)

1. **Judge location: A.** The judge moves into the scripted Stop hook, as a nested Haiku call like
   `_goal_check`, so it reads the real tool calls and shares the counter. The `hooks.json` prompt
   entry goes.
2. **Shared cap: A.** Two blocks per user message across all three checks, reset only when the turn
   made a real tool call after the last block. After the cap the reply goes out with a warning.
3. **Data flow between segments: A.** A step that needs the previous step's output reads a named
   checkpoint file and checks it at its start, so any segment can run alone.

Also decided by aj: the launch guard refuses a foreground or background launch over 60 seconds unless
the launch description says `Cannot split:` with a reason that passes criterion C5.

## The five criteria (one source: `rules/detail/roadblocks.md`)

- **C1 trigger:** a claim that something is missing, unreachable or impossible and that stops the
  task. A plain `Unverified:` note is not a trigger.
- **C2 what passes:** three attempts this turn, each aimed at the claimed thing, each from a
  different method class (existence check, disk search, package database, run it, ask the
  environment, other source such as CI, git history or docs). One output read three ways is one method.
- **C3 proof and the reason standard:** the attempts appear in the real tool calls. Every reason the
  judge reads gives the check that was run, what it actually returned, and the logic from that
  evidence to the claim.
- **C4 ways out:** `No other method`, `NEEDS YOU`, `Unverified`, `Goal status`, or `Cannot split`,
  each with a reason that meets C3.
- **C5 Cannot split:** accepted only for a genuine impossibility to split the work, shown by the
  C3 standard, with a progress signal for each minute. Slowness or habit is never a reason.

The judge, the guard's refusal message, every block message and the rules all quote this one text.

## Fewer false alarms

Remove "next step" from `_STALL_RE` (the house rules tell every reply to end with one). Drop the bare
phrases "could not", "unable to" and "I can't" from `_ROADBLOCK_RE`; keep phrases about a missing tool,
machine or access. A `NEEDS YOU` line exempts the goal check too.

## The segment rule

Before waiting on anything over a minute, the model writes a segment plan: name, the one command, the
input and how it is checked in seconds, the output, and a 60-second deadline. It runs segment 1, reads
its result, then starts segment 2; a failed segment stops the later ones. `rules/waits.json` drops the
600, 900 and 1200 second deadlines to 60 seconds per segment. The guard treats a known long runner with
no explicit timeout as over 60 seconds (the runner list lives in `rules/waits.json`). `verify.py`
prints each part when it finishes, not in a fixed order. Modular-test modules (issue #575) gain a
measured time and a 60-second flag in the gate (#578) and audit (#579).

## Page check fixes found on the way

`scripts/clarity.py` strips picture data with a pattern that stops at the first space (line 257), so
inline pictures with raw spaces leaked markup into its findings (132 on the proposal page, 9 after the
pictures were fixed). The check should read to the closing quote and drop inline `svg`. The page build
should refuse a picture that is not well-formed XML; a raw angle bracket broke one picture that the
visual check reported as fine.

## Known limits

- Speed differs by machine; times are measured and recorded on the machine that runs the work.
- A job that truly cannot split (one engine build, a CI run) must still report progress each minute.
- Whether Claude Code's own limit of 8 consecutive Stop blocks applies to prompt hooks is unknown.
- The guard checks that the reason's three parts are present; the Stop judge checks them against the
  real tool calls.
- The plugin's own `verify.py` takes over a minute per part on this Windows machine (core 68.9 s,
  safe_git 127.6 s, design_loop 201.1 s, delegation 142.9 s, make_page 105.5 s) and has failures here
  that pass on main's Linux CI. Fixing those is separate work.
