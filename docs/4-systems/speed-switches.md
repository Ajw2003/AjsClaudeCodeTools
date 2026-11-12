# Speed switches

**Owns:** the two typed switches (design loop, builders), what each one turns off, the per-model
default, approvals that never get refused, the foreground-wait guard and the rerun check's reset
rule. Status: design approved 2026-11-12 as "Design approved: Speed switches 1A 2* 3A 4* 5A 6A"
(see `docs/6-decisions/Decisions.md`); built in plugin 2.80.0 (#525). Code: `_mode_state`, `_switch_off`,
`_mode_apply` and `_scope_mode_link` in `scripts/house_rules/core.py`; `_loop_apply_one` and `_close_check`
in `design_loop.py`; `_rerun_check` and `_wait_check` in `safe_git.py`; `commands/mode.md`. Page: `docs/plans/2026-11-12-speed-switches.html`.

## The switches

| Switch | Typed line | What it turns off | What stays on |
|---|---|---|---|
| Design loop | "design loop off" / "design loop on" | the show-dont-tell rule text, design and build plan pages, the code-edit lock, issues-before-code, the editor pass, the 160-word page rule, every blocking end-of-reply checkpoint, and every guard that needs evidence only the loop records (#515) | destructive-command guard, main-branch guard; the evidence and commit checks arrive as the stop hook's non-blocking reminders, as they always have with the loop off |
| Builders | "builders off" / "builders on" | the delegation rule text and the delegation and agent-count checks | everything else |

- **Where the state lives:** one small file in `.claude/` of the main checkout, next to the
  design loop's stage file, so it holds for the repo across sessions and branches.
- **Who can change it:** only aj's own message, or `/house-rules:mode`, which sends the same line.
  The agent cannot flip a switch.
- **Starting state:** light (both off) when the session's model is Fable; full for every other
  model. The model comes from the hook payload's `model` field, or else the last `"model"` in the
  transcript's last 64 KB. A typed switch always wins. `HOUSE_RULES_LOOP=off` (design) and
  `HOUSE_RULES_DELEGATION=off` (builders) in settings.json still force a switch off machine-wide; a
  value of `on` is the plain default and does not hold a Fable session in full mode.
- **Rule text:** when a switch is off, its rule section is left out of the injected rules and one
  line says which switch removed it. Rule text already loaded in a session cannot be taken back, so
  a switch flipped mid-session also adds a note to each prompt saying the section no longer applies.

## Approvals never get refused

aj's approval line always moves the stage. Wrong labels, too few issues, a missing decisions-log
entry, a feature name that differs, a GitHub read that fails or times out: each becomes a to-do note
for the agent to fix in the same turn. Issues count however they were made. The note names what is
missing and the exact fix; a later check (closing, QA) still sees anything left unfixed.

## Foreground waits

A Bash call without run_in_background that loops with `sleep`, or wraps a command in `timeout`
longer than 60 seconds, is refused. The refusal gives the same command with run_in_background set.

## Rerun check

A third run of the same command (the same script with the same arguments, however it is invoked)
on the same code is refused, and the refusal asks for a fix first. "The same code" is a fingerprint
of every tracked code file (by extension, `RERUN_CODE_SPECS`), committed or not, leaving out the
test script itself. aj asked for the reset to follow "the code the test touches"; following imports
was not enough, because a test reaches code through subprocesses its imports don't show
(`verify.py` runs `hook.py` that way), so any code change stands in for it. Docs, pages and state
files never reset the count. See `rerun-limit.md` for the rest.
