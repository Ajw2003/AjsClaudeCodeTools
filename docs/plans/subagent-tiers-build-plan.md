# Build plan: three helper tiers replace the executor (issues #111, #112) and a visible note on the issue list (#110)

STATUS: approved by aj 2026-09-30. Design background, measurements and the levers behind these choices: `docs/plans/issue-workflow-and-tiered-subagents-proposal.md` ("Revision 2", "Spawn cost, measured"). One PR, `Refs #110, #111, #112`, never a closing word. Plugin version 2.50.0.

## Why (aj's words, 2026-09-30)

"The old executor is driving me nuts." Asked what about it, aj picked three: **too slow** (the last build ran 32 minutes), **costs too much** (about 54k tokens just to start), **too chatty or opaque**. Not picked: the commit/autosave behaviour, so leave `commitgate`, `autosave`, `worktreesweep` and `subagentcommit` exactly as they are. aj also chose: **leave the archivist alone**.

## Hard constraints

- The retired agent is `executor` only. `archivist.md` and everything that names it stay as they are.
- Subagents get the house rules core from the `subagentrules` SubagentStart hook, which is proven to reach them. The new agent files carry no rules digest of their own. Keep each file short; they are paid on every spawn.
- Tier files only set model, tool allowlist and role. Everything job-specific is written into the spawn prompt by the parent.
- Do not touch GitHub issues, labels or PRs. Reading is fine.
- No new hook process on Write, Edit or Bash calls. A new PreToolUse entry matched to `Agent` only is allowed (it runs only when a subagent is spawned).
- Match the existing style in `hook.py`; every behaviour gets a `verify.py` case; bump to 2.50.0; update the docs tiers; add a dated `docs/6-decisions/Decisions.md` entry.
- New agent types exist only after the plugin updates and Claude Code restarts. You cannot spawn them in this build. Test the files by parsing them and by exercising the hooks with simulated payloads, and say so in the report.

## Part 1: the three tier files (#111)

Create in `claude-house-rules/plugins/house-rules/agents/`. Read `executor.md` first for the frontmatter fields this Claude Code accepts (it uses `name`, `description`, `model`, `effort`) and mirror those; if `tools` is not an accepted field, find the accepted spelling from the Claude Code docs (the `claude-code-guide` agent type can answer) before writing the files.

| File | model | tools | Used for |
|---|---|---|---|
| `scout.md` | haiku | Read, Grep, Glob | Find, list, read, summarise. Never edits, never runs commands. |
| `builder.md` | sonnet | Read, Edit, Write, Bash, Grep, Glob | One issue's chunk of work (3 steps or fewer). |
| `reviewer.md` | opus | Read, Grep, Glob, Bash | Adversarial check of a finished diff. Only when asked, or after a builder failed twice. |

Why these tool lists: measured on this machine, the tool definitions are the largest part of a spawn's starting context (Explore 105,600 characters, general-purpose 181,900; the `Artifact` tool alone is 54,900, `PowerShell` 18,100, `Agent` 16,700, the browser tools about 40,000). A tier with a short allowlist avoids all of that. Leaving `Agent` out also makes nesting impossible by construction.

Body text, each file 15 lines or fewer, plain and imperative:
- **scout:** answer first, evidence as `path:line`, report 150 words or fewer, nothing written anywhere.
- **builder:** do the issue's steps as written; commit as you go on your own branch, scoped to the paths you changed; **run only the checks for the code you changed while working, and the full suites exactly once, at the end**; if the scope grows, stop and say what new issue it needs rather than doing it; do not touch GitHub issues or labels; **final report is at most 6 lines**: done or not done, files changed, each check with pass or fail and its one result line, what is unverified and why, branch and head SHA. Quote full output only for a failure.
- **reviewer:** findings only, `path:line: problem. fix.`, ten lines or fewer, no praise.

Delete `agents/executor.md`. Update every live reference to it (list from `grep -rn "house-rules:executor\|@house-rules:executor"`): `rules/house-rules.md`, `rules/detail/delegate-execution.md`, `output-styles/handover-cards.md`, `hook.py` (5 places: the delegate and scope notes, the digest check, the verdict model expectation), `verify.py`, `claude-house-rules/README.md`, `tools/install.py`, `tools/measure_footprint.py`, `docs/architecture.md`, `docs/measuring-footprint.md`, `docs/claude-ai-instructions.md`, `docs/4-systems/offshoot-plugins.md`, and the agent-router offshoot (`claude-agent-router/`: `agents/architect.md`, `rules/agent-router.md`, `README.md`). Do not edit `docs/sessions/`, `docs/archive/`, `docs/plans/` (history) or past `Decisions.md` entries. Add a verify.py check that no live file outside those folders still names `house-rules:executor`.

Rewrite the rules section "Once the approach is decided, delegate the execution" in `rules/house-rules.md` (same length or shorter) to say: delegate a settled plan one subagent per issue, never per step; read-only lookups go to `@house-rules:scout`, implementation to `@house-rules:builder`, a second opinion to `@house-rules:reviewer`; one at a time, never more than two; subagents do not start subagents; skip delegation only for one file and 3 steps or fewer, named in one line; multi-file or behaviour work uses `isolation: "worktree"`. Keep the `<!-- subagent -->` markers wherever a section is part of the subagent core, and keep the injected size within `verify.py`'s margin (it was raised to 9,700 characters last time; do not raise it again, trim instead). Update `rules/detail/delegate-execution.md` to match, and the `delegate`/`scope` notes in `hook.py` that name the executor.

`verdict` checks the model a subagent actually ran on against what it was meant to run on. Extend it to the tier map: scout is haiku, builder is sonnet, reviewer is opus (read how it does this for the executor today and generalise it; keep the executor line out). The `digestdrift` check enforces a rules digest inside agent files: restrict it to `archivist.md`.

## Part 2: keep the spawn count under control (#112)

Add a PreToolUse entry in `hooks/hooks.json` matched to `Agent` that calls a new `agentcap` handler (reuse `run.sh`; no new script). Behaviour:
- Count running subagents in a small JSON state file in the **common** git directory (the directory `git rev-parse --git-common-dir` names, shared by every worktree). Subagents run in their own worktrees, so the per-worktree directory `_git_dir()` returns is not shared; read the `commondir` file from it to find the shared one. Maintain the list from the existing SubagentStart handler (`announce`) and SubagentStop handler (`verdict`); do not add new entries for those events.
- Each record carries a start time. A record older than 45 minutes is ignored, because a stopped session or an outage means SubagentStop never fires (this happened on 2026-09-29).
- Deny a spawn when two are already running, with a plain message naming them and saying to wait for one to finish. Read-only foreground work still counts.
- Deny a spawn made by a subagent when the PreToolUse payload for an `Agent` call from inside a subagent carries an `agent_id` (probe how the existing handlers read `agent_id`; if the payload does not identify the caller, say so in the report and rely on the tier files omitting the `Agent` tool).
- Kill switch `HOUSE_RULES_AGENTS=off`. A corrupt or unwritable state file is reported in one line and the spawn is allowed (fail open, loud).
- verify.py cases: second spawn allowed, third denied, stale record ignored, kill switch, corrupt state file, record cleared by SubagentStop.

## Part 3: quieter subagent reports (the "chatty or opaque" complaint)

The `audit` handler (PostToolUse on Agent, and `userpromptaudit` for background ones) prints every command the subagent ran, 30 or more lines per spawn into the parent's context. Change it to: total tool uses by tool; every command that failed, in full; every file written or edited; and the count of other commands. Keep the instruction to reconcile the subagent's report against the record. Add a verify.py case with a 40-command transcript that checks the output stays under about 1,500 characters, that every failed command and every written file still appears, and that a subagent that claims success while the record shows a failure is still flagged.

Also in `SUBAGENT_MANDATE` (the text injected at SubagentStart): drop "report every command and result verbatim" for the tier files, which now carry their own short report formats. Keep it for `archivist` and any other agent type.

## Part 4: the visible note on the issue list (#110)

`event_issuelist` currently sends the open issues as context only, which the user never sees. Add a `systemMessage` in the same single JSON object: `house-rules: <N> open issues loaded` (`house-rules: no open issues` when the list is empty). Only when the list loads; the silent cases (no `gh`, no GitHub remote) and the existing could-not-list message stay as they are. Update the issuelist verify.py cases.

## Measurement

Run `python tools/measure_footprint.py --repo` before and after and report the subagent-spawn rows. Then measure the starting context of each new tier by parsing the files: report the tool allowlist and the agent file size in characters for each, against the executor's figures from `git show HEAD:claude-house-rules/plugins/house-rules/agents/executor.md`. A real spawn of each tier can only be measured after the update and a restart; say so.

## Housekeeping and reporting

Version 2.50.0. Update `docs/architecture.md` (hook table and the agent section), `docs/4-systems/hook-engine.md`, `docs/3-state/ProjectState.md`, `docs/5-today/Today.md`, `docs/2-roadmap/Roadmap.md`, and a dated Decisions entry (executor retired and why, tool allowlists, the cap and its 45-minute expiry, archivist untouched, the quieter audit, the issue-list note). Run `verify.py`, `verify_tools.py`, `check_plugin_version_bump.py --base origin/main --head HEAD`. Commit as you go on your worktree branch, scoped to changed paths. Report: what changed per part, verbatim short outputs of every check, everything you could not run and why, branch and head SHA.

## Out of scope

The archivist, `commitgate`/`autosave`/`worktreesweep`/`subagentcommit`, the installer bug (#114), the one-issue-per-spawn *requirement* (it is rule text only, not enforced by a hook), and anything in `claude-issue-forge/`.
