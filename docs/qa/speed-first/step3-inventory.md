# Step 3 inventory: every PreToolUse and PostToolUse entry in hooks.json, before the merge

Source: `claude-house-rules/plugins/house-rules/hooks/hooks.json` (before #628), handlers in `scripts/house_rules/*.py`, failure net in `scripts/hook.py` `main()` (hook.py:340-383).

Common to all entries: command is `sh run.sh <event>` then `python hook.py <event>`; the payload comes on stdin; `main()` calls `core.keep_payload()` once and the handler reads it with `read_payload()` (the kept copy). Decisions go to stdout as one JSON object (`json.dumps(..., separators=(",", ":"))`), exit 0, except guard and guardwrite, which can also exit 2 with text on stderr.

Failure rule today: guard and guardwrite are fail CLOSED (a crash gives stderr text and exit 2, hook.py:357-368; no interpreter gives exit 2 in run.sh:108-119). Every other entry is fail OPEN and loud: `main()` emits a systemMessage "the <event> hook hit an internal error ... did not run" and exits 0; with no interpreter run.sh prints a systemMessage (guardgithub, commitgate, harvest, audit, rclink) or nothing (the rest).

## PreToolUse (file order)

| # | Event | Matcher | Timeout | Handler | Reads | Writes | Can block | Crash |
|---|---|---|---|---|---|---|---|---|
| 1 | guard | `Bash\|PowerShell` | 10 | safe_git.event_guard | payload | stdout deny/ask JSON (+systemMessage), or stderr + exit 2 | yes (deny/ask JSON, exit 2) | closed (exit 2) |
| 2 | guardwrite | `Write` | 10 | safe_git.event_guardwrite | payload | stdout deny JSON; stderr + exit 2 on unreadable stdin/stat | yes | closed (exit 2) |
| 3 | guardgithub | `mcp__(github\|GitHub)__(create_pull_request\|...\|create_branch)` | 10 | safe_git.event_guardgithub | payload | stdout deny JSON, or additionalContext JSON | yes (deny) | open, loud |
| 4 | noask | `AskUserQuestion\|ExitPlanMode` | 10 | core.event_noask | payload (permission_mode) | stdout deny JSON; stderr note | yes (deny) | open, loud |
| 5 | agentcap | `Agent\|Task` | 10 | delegation.event_agentcap | payload | stdout deny JSON or systemMessage | yes (deny) | open, loud |
| 6 | commitgate | `Write\|Edit\|NotebookEdit\|Bash\|PowerShell` | 10 | delegation.event_commitgate | payload | stdout deny JSON or systemMessage | yes (deny) | open, loud |
| 7 | sendcheck | `SendUserFile` | 300 | design_loop.event_sendcheck | payload (json.loads) | stdout systemMessage | no ("the send goes ahead") | open, loud |
| 8 | pagecheck | `Write\|Artifact` | 10 | design_loop.event_pagecheck | payload | stdout systemMessage / additionalContext | no | open, loud |

A Write runs 2, 6, 8 (3 processes); a Bash call runs 1, 6 (2).

## PostToolUse (file order)

| # | Event | Matcher | Timeout | Handler | Reads | Writes | Can block | Crash |
|---|---|---|---|---|---|---|---|---|
| 1 | artifact | `Write\|Edit` | 10 | core.event_artifact | payload | additionalContext / systemMessage JSON | no | open, loud |
| 2 | branchnudge | `Write\|Edit` | 10 | safe_git.event_branchnudge | payload | additionalContext / systemMessage | no | open, loud |
| 3 | creditcheck | `Bash` | 15 | safe_git.event_creditcheck | payload | additionalContext / systemMessage | no | open, loud |
| 4 | closablemerge | `Bash\|mcp__(github\|GitHub)__(merge_pull_request\|issue_write)` | 10 | design_loop.event_closablemerge | payload | systemMessage + additionalContext | no | open, loud |
| 5 | runnable | `Write` | 10 | core.event_runnable | payload | additionalContext / systemMessage | no | open, loud |
| 6 | harvest | `Write\|Edit` | 10 | docs.event_harvest | payload | systemMessage / additionalContext | no | open, loud |
| 7 | delegate | `ExitPlanMode` | 10 | delegation.event_delegate | payload | additionalContext / systemMessage | no | open, loud |
| 8 | audit | `Agent\|Task` | 10 | delegation.event_audit | payload | additionalContext / systemMessage | no | open, loud |
| 9 | rclink | `mcp__hearthbot__start_remote_control` | 10 | delegation.event_rclink | payload | additionalContext / systemMessage | no | open, loud |
| 10 | autosave | `Write\|Edit\|NotebookEdit\|Bash\|PowerShell\|mcp__(github\|GitHub)__issue_write` | 10 | delegation.event_autosave | payload | systemMessage | no | open, loud |
| 11 | promptran | `Bash\|PowerShell\|Write\|Edit\|MultiEdit\|NotebookEdit\|WebFetch\|WebSearch\|mcp__.*` | 10 | core.event_promptran | payload | systemMessage + additionalContext; stderr note | no | open, loud |

A Write runs 1, 2, 5, 6, 10, 11 (6 processes); a Bash call runs 3, 4, 10, 11 (4).

Only the PreToolUse entries 1-6 can block. PostToolUse cannot block. Not merged: sendcheck (alone for its tool, timeout 300), and the non-tool events (PostToolUseFailure promptran, SessionStart, Stop, ...).
