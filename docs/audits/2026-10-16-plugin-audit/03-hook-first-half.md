# Audit 3 of the house-rules plugin: hook.py, lines 1 to 4200

Raw findings from a read-only scout pass on 2026-10-16 (Read tool only). All line numbers refer to
`claude-house-rules/plugins/house-rules/scripts/hook.py` at plugin version 2.68.0. Items checked
by hand afterwards are marked **confirmed**.

## Inventory of hook entry points in this range

| Event | Entry point (lines) | What it does | Rule it serves | State and external calls | Off switch |
|---|---|---|---|---|---|
| SessionStart | `event_inject` (584-641) | Loads `rules/house-rules.md` into context | All standing rules | Reads plugin rules and `~/.claude/plugins/installed_plugins.json` (`_rules_root`, 523) | None |
| SessionStart | `event_showrule` (655-678) | Loads show-dont-tell and clear-writing | Show, don't tell; clear writing | Plugin files only | `HOUSE_RULES_VOICE=off` removes the voice section (495) |
| SessionStart | `event_profile` (690-770) | Machine profile from `rules/environment.md`, else detected at runtime | Build for the recorded machine | Reads `rules/handover-target.md` when remote; runs nvidia-smi, system_profiler, powershell, sysctl, `claude auth status --json` | None |
| SessionStart | `event_standards` (866-996) | Picks `rules/standards/*.md` from project markers | Code follows the loaded standards | Reads a `.claude/standards` override | None; the override only narrows the set |
| SessionStart | `event_docstiers` (1062-1158) | Checks the six doc tiers | Documentation goes in tiers | Reads `.git/config` for the owner | None; owner override `HOUSE_RULES_GITHUB_OWNER` |
| SessionStart | `event_versioncheck` (1471-1633) | Compares installed, marketplace and GitHub versions, and updates | Keep the plugin up to date | raw.githubusercontent.com, then api.github.com; runs `claude plugin update`; writes a temp-dir marker (1307) | `HOUSE_RULES_VERSION_CHECK=off`, `HOUSE_RULES_AUTO_UPDATE=off` |
| UserPromptSubmit | `event_scope` (1707-1753) | Short or full scope reminder, chosen by regex | The request is the scope | Payload only | None |
| PreToolUse | `event_guard` (2394-2636) | Refuses or asks on git writes and deletes | Commit on own branches; no destructive action unchecked | Reads `.git/HEAD` and the temp marker (2411); runs git status and diff | None; `HOUSE_RULES_OWNED_BRANCHES` extends it |
| PreToolUse | `event_guardwrite` (2790-2852) | Refuses an overwrite of an existing file | Edit in place | Reads the target file | None |
| PreToolUse | `event_agentcap` (4024-4065) | Caps running helpers at 2 | Delegate, max two | `house-rules-agents.json` in the git common dir (3944, 3998) | `HOUSE_RULES_AGENTS=off` |
| PostToolUse | `event_artifact` (2925-2972) | Flags documents written outside the project | Artifacts live in the project | No state; uses `clarity.py` for pages | None |
| PostToolUse | `event_branchnudge` (2989-3051) | Nudges a branch switch on the first change | Commit on own branch | Runs git status | `_commit_check_enabled()` |
| PostToolUse | `event_runnable` (3092-3143) | Asks for a run of new runnable files | Run what you wrote | None | None |
| PostToolUse | `event_delegate` (3185-3209) | Delegation note after plan approval | Delegate to builder | None | `_parity_enabled()` |
| SubagentStart | `event_announce` (3480-3541) | Reports helper type and declared model | Delegation | Reads the agent file; writes agentcap state (3503) | `HOUSE_RULES_DELEGATION=off` (3270) |
| SubagentStart | `event_subagentrules` (3340-3390) | Injects the subagent core from house-rules.md | Delegation | Plugin files | `HOUSE_RULES_DELEGATION=off` |
| PermissionRequest | `event_prompttimer` (4068 on) | Refuses an unanswered prompt after a timeout | The user's hands are for decisions | `.git/house-rules/waiting-on-you.json` (4104-4112) | `HOUSE_RULES_PROMPT_TIMEOUT=off` |
| SubagentStop | `event_verdict` (3796-3933) | Reports the model that actually ran, plus an audit | Delegation; evidence | Reads the helper transcript; writes `docs/sessions/` only with `HOUSE_RULES_SUBAGENT_LEDGER=on` (3754) | `HOUSE_RULES_DELEGATION=off` |

Four entry points have no off switch at all and run in every session: inject, profile, standards,
and guard.

## Logic against logic
- The module docstring says guardwrite asks about a whole-file overwrite (24-26); the code refuses it outright (2850).
- `event_guard` is documented as failing closed, but an empty payload is allowed through (2406-2408). **Confirmed.**
- Comments say only `git diff --cached` shells out in guard (1896, 2255); `_delete_refusal` (2692), `_never_blocked_own_file` (2387) and `_payload_toplevel` (2649) also run git.
- Prose hardcodes "two" helpers (1676, 3154) beside the constant `AGENT_CAP = 2` (3942), so changing the constant leaves the text wrong.

## Design problems
- Errors are swallowed with no message at 1337 (`_read_and_clear_outdated_marker`), 2069, 2244 and 3599 (`_observed_models`), against the rule "Nothing fails silently".
- Hardcoded owner: `DEFAULT_GITHUB_OWNER` (1026) and the raw GitHub URL (1169).
- Functions over 150 lines: `event_guard` (2394-2636, 243 lines) and `event_versioncheck` (1471-1633, 163 lines).
- Hidden coupling: versioncheck writes a marker in the temp dir (1307) that guard reads and clears (2411). Fixed `.tmp` file names at 3992 and 4127 can collide between sessions.
- Helpers are interleaved between constants at 3255. `import time` is repeated (1263, and 1963 as `_t`), and `_time` and `_sys` are duplicate aliases (147-148).

## Natural split lines
- **Session start:** inject, showrule, profile, standards, docstiers, versioncheck.
- **Guards:** lines 1757-2760.
- **Helpers and delegation:** lines 3212-4065.
- **Prompt timer:** line 4068 onward.

## Notes
- The scout's report was first cut to its 150-word report limit. That limit comes from the helper's own instructions, not from a repo file. The full inventory came only after a second request, so any audit run through these helpers needs a "send everything" instruction.
- `event_issuelist` exists at 6309, outside this range. **Confirmed.**
