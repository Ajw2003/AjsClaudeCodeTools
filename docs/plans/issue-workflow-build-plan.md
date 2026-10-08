# Build plan: hooks that force the issue workflow (issues #108, #109, #110)

STATUS: approved by aj 2026-09-30 (edit gate = block source edits; proof repos = this repo and PlunderSpell; order = #108, #109, #110). Design background and Focus Deck facts: `docs/plans/issue-workflow-and-tiered-subagents-proposal.md` (Revision 2). Parent plan issue: #107. One PR for all three, `Refs #108, #109, #110` and never a closing word.

The house-rules plugin is installed at user scope, so every hook below already runs in every repo. "Across this repo and one other" means the behaviour is proved in this repo and in PlunderSpell, not that anything is configured per repo.

## Hard constraints

- **No new hook process on Write, Edit or Bash calls.** The efficiency review showed each entry costs about 114 ms of launcher plus interpreter start. Extend the existing entries: `guard` (PreToolUse Bash), `commitgate` (PreToolUse Write|Edit|NotebookEdit), `delegate` (PostToolUse ExitPlanMode), the existing PostToolUse Bash entry that calls `autosave`, `handover` (Stop), `inject` (SessionStart). Do not add an entry to `hooks/hooks.json` for Write, Edit or Bash.
- **No network call on a tool call.** The only network call allowed is the SessionStart issue list, with a 5 s timeout and a 60 s cache.
- **Hooks never run `gh issue create` or `gh issue close` themselves.** They force Claude to. Nothing fails silently: an unreadable state file or a `gh` failure says so in one line.
- **Kill switch:** `HOUSE_RULES_ISSUES=off` disables every new behaviour, same style as `HOUSE_RULES_AUTOSAVE=off`.
- Subagent worktrees (`worktree-agent-` branches) have their own git directory, so the plan state written in the main session's git directory does not apply to them. Keep it that way; add a test.
- Match the existing file style in `scripts/hook.py`. Every behaviour gets a `verify.py` case in the same change; bump the plugin version (2.49.0).

## State

One JSON file per git directory, `house-rules-issues.json` inside the directory `_git_dir()` returns (`hook.py`, near line 1872; it handles linked worktrees). Fields: `plan_steps` (int), `approved_at` (ISO time), `needs_issues` (bool), `created` (list of `{repo, number, labelled}`). A corrupt or unreadable file is reported in one line and treated as no gate (fail open, loud), matching how the other handlers fail.

## #110: plans become issues, and source edits wait for them

1. **`delegate` (PostToolUse ExitPlanMode, `hook.py` near line 2514).** The plan text is already extracted with `_PLAN_VALUE_RE`. Count steps: lines matching `^\s*\d+[.)]\s` plus `- [ ]` checklist lines; also count `###` headings that start with `Step` or `Change`. If the count is more than 3, write the state file with `needs_issues: true` and append an ISSUE_NOTE to the existing delegate note. If 3 or fewer, write nothing and say so in the note (one line naming the count).
2. **ISSUE_NOTE text (short, plain):** create one parent issue for the plan and one child issue per step before any code is written; children say `Part of #<parent>` in the body; titles in plain language a non-programmer can follow; every issue carries at least one category label and `Claude created this`; create the `Claude created this` label first if the repo lacks it (`gh label create`); show the user the issue numbers; mark a step `in progress` (`gh issue edit N --add-label "in progress"`) when work on it starts and remove it when the issue closes.
3. **Recording creations.** In the existing PostToolUse Bash entry (the one `autosave` uses), when the command is `gh issue create`, parse the issue URL from the tool output (`/issues/(\d+)`), check the command text for the `Claude created this` label, and append to `created`. If the label is missing, emit a correction note once (Focus Deck ignores unlabelled issues) and do not count it. The gate clears (`needs_issues: false`) once two issues are recorded with the label (parent plus at least one child).
4. **The gate, inside `commitgate` (PreToolUse).** When `needs_issues` is true, deny Write, Edit and NotebookEdit on source files with a message naming the two missing pieces. Always allowed: anything under `docs/`, any `.md` file, anything under `.claude/`, files outside the project, and the state file itself. Use the same deny shape `commitgate` already uses.
5. **Stop (`handover`).** If `needs_issues` is still true at Stop, add one line to the existing Stop context. Do not block Stop.
6. **SessionStart (`inject`).** After the rules, add up to 10 open issue titles from `gh issue list --state open --limit 10 --json number,title`, only when `gh` is on PATH and the repo has a GitHub remote. 5 s timeout, 60 s cache in the git directory. On failure print `house-rules: could not list open issues (<reason>)`. About 200 tokens; measure with `tools/measure_footprint.py --repo` before and after and report both.
7. **Rules text.** Add one section to `rules/house-rules.md` (about 90 words, same style as its neighbours) and a detail file `rules/detail/issue-workflow.md` holding the loop and the label rules. Keep the docs-tier rules exactly as they are; they are mandatory. Do not raise the injected size by more than about 150 tokens net; say what you trimmed if you must.

## #108: pull requests link their issue without closing it

In `guard` (PreToolUse Bash/PowerShell), for a command containing `gh pr create`:
- Read the body from `--body`, `-b`, or the file named by `--body-file` / `-F` (read it; if it cannot be read, say so and ask rather than allow).
- Deny with a plain message unless the body contains `Refs #N`, `Refs owner/repo#N` or `Part of #N`, or a line `No-issue: <reason>`.
- Deny if the body contains a closing word followed by an issue reference: close, closes, closed, fix, fixes, fixed, resolve, resolves, resolved (case-insensitive) followed by `#N` or `owner/repo#N`. Explain that GitHub would close the issue at merge, before the user has tested.
- Allow `gh pr create --web` with no body only with the same ask-or-deny treatment.

## #109: closing an issue always asks the user

In `guard`, for `gh issue close` (and `gh issue edit ... --state closed`, `gh api` calls that PATCH an issue to closed): return the ask decision (reuse the shape `guard` already uses for its prompts) with a reason saying the user must have tested first. The approval prompt is the user's go-ahead. Add to the context note: on approval, also run `gh issue edit N --add-label "Claude completed this" --remove-label "in progress"` and comment with the merged PR link. `gh issue comment` and `gh issue create` are not affected.

## Proof in two repos

Unit cases in `scripts/verify.py` use temp repos. Then a separate proof in a second real repo without touching it:
1. `git clone --local --no-checkout C:\Users\aj\Desktop\GameDev\PlunderSpell <scratch dir>` (a copy; never write state in the real PlunderSpell).
2. With that clone as the payload `cwd`, pipe through `sh scripts/run.sh <event>`: an ExitPlanMode payload with a 5-step plan (state file appears, note printed); a Write payload for a `.cs` file (denied); a Write for `docs/x.md` (allowed); a `gh issue create` PostToolUse payload with the label twice (gate clears); the same Write again (allowed); `gh pr create` with no Refs (denied), with `Closes #5` (denied), with `Refs #5` (allowed); `gh issue close 5` (ask).
3. Repeat the same sequence with this repo as `cwd`. Quote the literal outputs of both runs in the report.
4. A real session in PlunderSpell cannot be started from here; the report must say that, and the handover to aj is: restart Claude Code after the plugin update, open PlunderSpell, approve a four-step plan, and confirm the edit is refused until issues exist.

## Housekeeping

Version 2.49.0. Update `docs/architecture.md` hook table, `docs/4-systems/hook-engine.md`, `docs/3-state/ProjectState.md`, `docs/5-today/Today.md`, `docs/2-roadmap/Roadmap.md`, and add a dated `docs/6-decisions/Decisions.md` entry (hooks force issue creation; Claude still performs it; the edit gate and its kill switch; the `Refs`-not-`Closes` rule; the `in progress` label permission aj gave on 2026-09-30). Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` and `python tools/verify_tools.py` (both exit 0) and `python tools/check_plugin_version_bump.py --base origin/main --head HEAD`. Do not touch issues or labels on GitHub; the parent session does that. Commit as you go, scoped to changed paths.

## Out of scope

The tiered helpers (#111, #112), the end-of-turn check for commits without an issue number, and anything in `claude-issue-forge/`.
