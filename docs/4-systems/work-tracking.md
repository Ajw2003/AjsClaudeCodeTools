# Work tracking

Status: **planned** for plugin 2.73.1. Design approved 2026-10-27 in the HouseRules project on
claude.ai ("Design approved: background work tracking 1A 2A"). Decision: `docs/6-decisions/Decisions.md`,
entry "Design approved: background work tracking". Proposal page:
`docs/plans/background-work-tracking.html`. Parent issue: "Background work tracking: every layer of
delegated work is one tap away"; #383 is its first step.

## What it owns

Making sure aj can follow work a project thread delegates, at every layer, without asking for it:

| Layer | What aj sees | Where it comes from |
|---|---|---|
| 1. What is needed | The thread's checklist and replies | Unchanged; the thread already posts these |
| 2. The session doing the work | A transcript link for the thread itself, for each Remote Control session on aj's PC, and a work-trail file for each helper agent | The hooks below |
| 3. The commands that session ran | The transcript page (thread and Remote Control sessions list every command with its output), or the work-trail file (helpers) | Claude Code's transcript; `session_ledger_render.py` for helpers |

Choice 2A puts the links in the header line of the thread's checklist, updated in place, plus once in
the reply that starts the work. Every link is also attached to that reply, so it stays in the
project's Library after the thread is resolved.

Only a project thread gets any of this. Every handler first checks `CLAUDE_CODE_PROJECTS_SESSION`,
which the container sets to `1` in a project thread, and does nothing anywhere else.

## The link

A claude.ai session page lives at `https://claude.ai/code/session_<id>`. The ids the tools hand back
start with `cse_` instead. Swapping the `cse_` prefix for `session_` gave a working link on two
sessions: #383's Remote Control session (`cse_01PsKYQzaq5dxPrns28sUQMS`, opened by aj on 2026-10-26),
and this feature's own design thread, whose `CLAUDE_CODE_REMOTE_SESSION_ID` is
`cse_018ddrfbUqBBFUVGmxxEzptr` and whose commit trailer names `session_018ddrfbUqBBFUVGmxxEzptr`.
The swap is observed, not documented, so every message that carries a link also carries the raw id.

## How it works

| Piece | Hook | What it does |
|---|---|---|
| Thread link | SessionStart, `inject` (`house_rules/delegation.py`) | Reads `CLAUDE_CODE_REMOTE_SESSION_ID`, builds the thread's transcript link and tells the thread to open every checklist header with it. A missing or malformed id is said, not skipped. |
| Remote Control link (#383) | PostToolUse on `mcp__hearthbot__start_remote_control`, new handler `rclink` | When the result says `started` or `already_running`, tells the thread to call `remote_control_status`, read the session id, and post and attach "Transcript of the session on your PC". If the status call fails or carries no id, the thread says what failed in the same message. A second session gets its own link; an old one is never replaced silently. |
| Helper work trail | PostToolUse on `Agent|Task` (`audit`), and UserPromptSubmit (`userpromptaudit`) for a backgrounded helper | Both already locate the helper's transcript. In a project thread they also render it with `session_ledger_render.py` into `/mnt/project-files/work-trail/<date>-<agent type>-<agent id>.md` and tell the thread to attach that file. The opt-in SubagentStop ledger (`HOUSE_RULES_SUBAGENT_LEDGER`) is unchanged outside project threads. |
| Links owed | Stop, `handover` (`hook.py`) | Reads this turn's records. If a Remote Control session started, a helper finished, or a checklist was posted, and no `post_message` or `update_progress_checklist` call this turn carried the matching link or trail path, it blocks the end of the turn once and names what is missing. On the retry it only reports. |

The proposal page placed the helper trail on SubagentStop. It moves to `audit` and `userpromptaudit`
because those two already reach the thread's model with `additionalContext`; SubagentStop output
reaches only aj's screen (doc-ref 8313 in `docs/6-decisions/Decisions.md`), so the thread could never
be told the file's path from there.

## Invariants

- Outside a project thread, every handler here is silent and changes nothing.
- No handler reaches the network. The Remote Control id is fetched by the thread's own tool call,
  which the hook asks for.
- A work-trail file is written only from a transcript that already exists; nothing is logged per
  command, so the per-command guard path gains no file write (choice 1C was rejected for this).
- Every failure to build a link or write a trail is reported in the same turn, naming what failed.

## Traps

- `/mnt/project-files` is a network mount and can be a symlink: write with a trailing slash on the
  folder path, and never search the whole folder.
- The SubagentStop payload reaches aj only, never the model. Anything the thread must act on goes
  through `audit` or `userpromptaudit`.
