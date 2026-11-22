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
  The agent cannot flip a switch. The line must stand alone as its own sentence or line ("design
  loop off.", "builders off, design loop off"); a switch quoted or mentioned inside a longer
  sentence is ignored (`_MODE_LINE_RE` in `scripts/house_rules/core.py`).
- **Starting state:** both on, for every model, until aj types a switch for the repo; then it
  stays as typed. `HOUSE_RULES_LOOP=off` (design) and `HOUSE_RULES_DELEGATION=off` (builders) in
  settings.json still force a switch off machine-wide when nothing is typed.
- **No model default (changed 2026-11-12, after QA):** the approved design started Fable light.
  Live tests showed hooks are not told the model at session start: neither the SessionStart nor
  the UserPromptSubmit payload carries it, no environment variable does, and the transcript names
  it only after the first reply. aj chose to drop the default rather than guess from settings.json.
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

## Feature switches anywhere (built 2026-11-16, "Design approved: Feature switches 1A 2A 3A")

A stop-gap aj asked for while pages cannot yet fit each project: any feature group can be switched off or on by
typing one line, in any folder, git repository or not. Page: `docs/plans/2026-11-16-feature-switches.html`.

- **Where a switch is saved (1A).** Typed alone ("pages off"): in this folder's `.claude/house-rules-mode.json`. Inside
  a git repository that is still the main checkout's `.claude/`, as today; outside one it is the folder the session
  runs in. With "everywhere" ("pages off everywhere"): in `~/.claude/house-rules-mode.json` (the Claude config folder,
  `CLAUDE_CONFIG_DIR` when set), used wherever a folder has said nothing. Order: this folder, then everywhere, then
  `HOUSE_RULES_*` in settings.json, then on. A cloud container is thrown away when the session ends, so "everywhere"
  lasts only that session there.
- **The groups (2A).** One typed name each, mapped onto the settings the plugin already reads:

  | Typed name | Settings it switches |
  |---|---|
  | design loop | `HOUSE_RULES_LOOP`, `HOUSE_RULES_ISSUES` |
  | pages | `HOUSE_RULES_PAGES` (new: the page rule, the 160-word page rule and the editor pass a page needs; approvals still count) |
  | builders | `HOUSE_RULES_DELEGATION`, `HOUSE_RULES_AGENTS` |
  | issues | `HOUSE_RULES_ISSUES` |
  | writing checks | `HOUSE_RULES_CLEAR_WRITING`, `HOUSE_RULES_PLAIN_SUMMARY`, `HOUSE_RULES_VISUAL_CHECK`, `HOUSE_RULES_PARITY`, `HOUSE_RULES_VOICE` |
  | autosave | `HOUSE_RULES_AUTOSAVE`, `HOUSE_RULES_HANDOFF` |
  | house rules | every group above, plus `HOUSE_RULES_HARVEST`, `HOUSE_RULES_COMMIT_CHECK`, `HOUSE_RULES_HANDOVER`, `HOUSE_RULES_RERUNS`, `HOUSE_RULES_DISKREPORT` |

- **How it reaches every check.** `hook.py`'s `main()` already keeps the payload first (`core.keep_payload()`). Right
  after it, the switch layer reads the two files and sets each mapped `HOUSE_RULES_*` value for that hook call, so
  every existing check obeys without being edited. A typed "on" wins over an "off" in settings.json.
- **Test isolation (#546).** `HOUSE_RULES_MODE_IGNORE` (os.pathsep-separated paths) makes `_mode_read` treat those files as absent; `verify.py` sets it to the repo's and the everywhere file.
- **Never switchable (3A).** The destructive-command guard, the main-branch guard and the credit check have no setting
  in any group, so no typed line can turn them off.
- **Where it is built.** The files, groups and hook layer: `core.py:2625` (`_MODE_GROUPS`), `core.py:2652` (`_mode_files`),
  `core.py:2679` (`apply_switches`), `core.py:2720` (`_mode_apply`). Pages: `writing.py:73` (`_pages_enabled`). The
  prompt note naming every group that is off and where it was set: `core.py:2750` (`_mode_note`). Rule text: a switched-off
  design loop leaves out `show-dont-tell.md` (`event_showrule`) and builders leave out their section (`event_inject`);
  "house rules off" sets both off. The page rule is one block inside `show-dont-tell.md`, so "pages off" keeps it
  loaded and relies on the note. Command: `commands/mode.md`. Checks: `scripts/checks/design_loop.py`, "feature switches".

## Unattended mode (2.84.0)

For a run with nobody present. `HOUSE_RULES_UNATTENDED=on` (case-insensitive) turns it on; `core.unattended()` reads it.

- **Turns off:** every group in `_MODE_GROUPS` except autosave (design loop, pages, builders, issues, writing checks, and the rest of "house rules"). `apply_switches()` does this first, so a typed switch such as `pages on` still wins.
- **Stays:** autosave and handoff (work stays committed overnight) and the destructive-command guard, main-branch guard and credit check, which have no switch.
- **Refuse, not ask:** `_ask_or_refuse` in `safe_git.py` always denies, with "Refused, not asked: this is an unattended run (HOUSE_RULES_UNATTENDED=on), so nobody can answer a prompt", and adds the action to "Waiting on you". Before, an ask was refused only after the prompt timeout, and prompttimer ignores prompts no guard raised.
- **`noask`:** a PreToolUse hook on `AskUserQuestion|ExitPlanMode`. Unattended it denies, telling the agent to choose the safest option, record the question and choice in the final report, and carry on. Otherwise silent.
- **Session start** adds one note saying the run is unattended.
- **Launcher:** `tools/overnight.sh` sets `HOUSE_RULES_UNATTENDED=on` and `ART_PIPELINE=unattended`, then runs `claude --dangerously-skip-permissions "$@"`. Use a throwaway branch or clone.
- **Rule text (2.85.0):** the session note says that for this run "hand it over, then wait", "stop and wait for the user's answer" and the ask-before list (new dependency, deleting files, refactors over 3 files, public API changes) are overridden: report the command, take the conservative reversible option, log it. The rules files are not forked.
- **versioncheck (2.85.0):** one line that an update is available and was not applied; no update run, no banner, no marker.
- A guard ask is refused even with `HOUSE_RULES_PROMPT_TIMEOUT=off` (checked).
- **Relaxed guards (2.86.0, aj approved 2026-11-22).** Three guards that would stop a run nobody can answer now let the action through with a note instead of refusing it, only when unattended; attended they refuse as before (each has a verify check for both): a whole-file Write over a file I did not create (`guardwrite`; a systemMessage names the file), a commit holding a file over 50 MB or inside a regenerated folder (`bigfiles`; the note lists the files), and a `Co-Authored-By: Claude`/Anthropic credit line (`_attribution_guard`; the note says the credit rule was relaxed so the line is removed in the morning). The destructive-command guard and the main-branch guard are unchanged.
- The guard's allow paths (an exempted git write, a never-blocked routine commit) now carry a note instead of dropping it.
