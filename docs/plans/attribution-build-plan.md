# Build plan: credit "aj's agent", never Claude (issue #133)

STATUS: approved by aj 2026-10-01. One PR, `Refs #133`, never a closing word. Plugin version 2.51.0.

## What was decided (aj's words and findings)

- Credit **"aj's agent"** on commits and pull requests. aj wants the distinction (an agent did it) but **not the Claude branding**, and **no email displayed**. So no `Co-Authored-By:` trailer (a trailer needs an email).
- Wording: commit text `Committed by AJ's agent`; pull request text `Opened by AJ's agent`; `sessionUrl` false (drops the claude.ai session link/trailer added to commits and PRs from web and Remote Control sessions).
- Claude Code has this as a user setting named `attribution` (fields `commit`, `pr`, `sessionUrl`; an empty string hides attribution). It is not in the public docs; it was found in the installed program (2.1.286). It is already set in aj's own `~/.claude/settings.json` on this machine and the app honoured it immediately (the attribution text handed to Claude changed mid-session).
- A plugin **cannot** carry this setting: the program accepts only the keys `agent` and `subagentStatusLine` from a plugin's `settings.json`. So there are two mechanisms: the installer writes the setting on each machine, and a rule plus a guard hook cover sessions that never read the settings file (cloud sessions).

## Hard constraints

- No new hook process: the check goes into the existing `guard` handler (PreToolUse Bash/PowerShell).
- Injected rules are at 9,645 characters against `verify.py`'s 9,700 margin. **Do not raise the margin.** Add the rule as one short clause in an existing section plus the detail file, and trim other wording if needed.
- Kill switch `HOUSE_RULES_ATTRIBUTION=off` for the guard, same style as the other switches.
- Match the existing style in `hook.py`, `install.py`, `verify.py`, `verify_tools.py`. Every behaviour gets a test in the same change. Bump to 2.51.0. Update the docs tiers. Add a dated `docs/6-decisions/Decisions.md` entry.
- Do not edit any real `~/.claude/settings.json`, and do not run `tools/bootstrap.ps1` or `install.py` against the real machine. Test the installer against a temp directory (read how `verify_tools.py` already does this).
- Do not touch GitHub issues, labels or PRs. Reading is fine.

## Step 1: the installer sets the attribution on every machine

`tools/install.py`, step 4 "Settings the plugin cannot set itself" (it already writes `model = opusplan` and `verbose = true` and preserves every other key). Add `attribution = {"commit": "Committed by AJ's agent", "pr": "Opened by AJ's agent", "sessionUrl": false}`. The existing wanted-settings list takes scalar values; extend it to take an object value, set it exactly (the house rule wins over an existing different `attribution`), and read it back after writing, as the other two do. Add a `--no-attribution` flag next to `--no-verbose` and `--no-model`. Tests in `tools/verify_tools.py`: written into an empty settings file, written while preserving other keys, an existing different `attribution` replaced, `--no-attribution` leaves it alone, read-back verified, a settings file that does not parse is reported and not overwritten.

## Step 2: the rule

One clause, in the existing section "Commit constantly on my own branches, never on theirs" in `rules/house-rules.md` (or the section that fits best), of about 50 characters or fewer: commits and PRs credit "aj's agent", never Claude. The detail goes in `rules/detail/commit-branches.md`: the wording, why no email, why no Claude branding, and that the installer sets the Claude Code `attribution` setting while the guard backs it up where settings are not read. Keep the inject size under 9,700.

## Step 3: the guard hook

In `guard` (PreToolUse Bash/PowerShell), refuse with a plain message that names the replacement wording when the command text contains any of these in a `git commit` message or a `gh pr create` / `gh pr edit` / `gh issue create` / `gh issue comment` body (heredocs and `-m` / `--body` / `--body-file` all count; read a `--body-file` the same way the PR `Refs` check does):
- a `Co-Authored-By:` line naming Claude or an `anthropic.com` address;
- `Generated with [Claude Code]` or `claude.com/claude-code`;
- a `Claude-Session` trailer or a `claude.ai/code/` session link.
A message crediting "aj's agent" with no email must pass. `HOUSE_RULES_ATTRIBUTION=off` disables it. Tests: each refused form, the allowed form, a commit message that merely discusses the word Claude in its subject (must pass, for example `docs: rename the Claude setting`), the kill switch, and a case through the PowerShell tool.

## Housekeeping and reporting

Docs tiers: `docs/architecture.md` hook table, `docs/4-systems/hook-engine.md`, `docs/3-state/ProjectState.md`, `docs/5-today/Today.md`, `docs/2-roadmap/Roadmap.md`, plus the Decisions entry (what was decided, that a plugin cannot carry the setting and why, the guard as backstop). Run `verify.py`, `verify_tools.py`, `check_plugin_version_bump.py --base origin/main --head HEAD`, `measure_footprint.py --repo`. Commit as you go on your worktree branch. Final report at most 30 lines: what changed per step, verbatim short outputs of the checks, the injected size, what you could not run and why, branch and head SHA.

## Out of scope

Rewriting old commits and PRs, other repos' settings, and the attribution text the app hands Claude (the setting already fixed that on this machine).
