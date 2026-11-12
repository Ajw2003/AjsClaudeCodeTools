# Speed switches

**Owns:** the two typed switches (design loop, builders), what each one turns off, the per-model
default, approvals that never get refused, the foreground-wait guard and the rerun check's reset
rule. Status: design approved 2026-11-12 as "Design approved: Speed switches 1A 2* 3A 4* 5A 6A"
(see `docs/6-decisions/Decisions.md`); not built. Page: `docs/plans/2026-11-12-speed-switches.html`.

## The switches

| Switch | Typed line | What it turns off | What stays on |
|---|---|---|---|
| Design loop | "design loop off" / "design loop on" | the show-dont-tell rule text, design and build plan pages, the code-edit lock, issues-before-code, the editor pass, the 160-word page rule, the handoff, plain summary and QA page checks, and every guard that needs evidence only the loop records (#515) | destructive-command guard, main-branch guard, evidence check, commit check |
| Builders | "builders off" / "builders on" | the delegation rule text and the delegation and agent-count checks | everything else |

- **Where the state lives:** one small file in `.claude/` of the main checkout, next to the
  design loop's stage file, so it holds for the repo across sessions and branches.
- **Who can change it:** only aj's own message, or `/house-rules:mode`, which sends the same line.
  The agent cannot flip a switch.
- **Starting state:** light (both off) when the session's model is Fable; full for every other
  model. A typed switch always wins over the default. The settings.json variables
  (`HOUSE_RULES_LOOP`, `HOUSE_RULES_DELEGATION`, ...) keep working as the machine-wide default.
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

Unchanged: a third identical run of a project test script is refused. Changed: the count resets
when the code the test touches changes, not on a new commit and not on unrelated edits. The refusal
says a fix to that code is needed before the next run. See `rerun-limit.md` for the rest.
