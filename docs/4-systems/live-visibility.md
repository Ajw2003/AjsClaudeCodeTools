# Live visibility

Status: **planned**. Design approved 2026-10-28 ("Design approved: live visibility 1A 2A 3A 4A"). Decision:
`docs/6-decisions/Decisions.md`, entry "2026-10-28 - Design approved: live visibility". Proposal page:
`docs/plans/live-visibility.html`. Measurements behind it: `docs/generated/2026-10-28-long-call-measurement.md`.
It extends [work-tracking.md](work-tracking.md), which stays the owner of the project-thread pieces.

## What it owns

aj can see, at any moment and on a phone, which session is doing the work, what it is doing now, whether
it is stuck, and every step a helper took. Nothing runs quiet by default; anything quieted names its switch.

## Pieces

| Piece | Hook | Changes |
|---|---|---|
| Thread link (1A, 2A) | SessionStart `inject`, `thread_link_note` | Gate becomes `CLAUDE_CODE_REMOTE=true` plus a `cse_` id, not `CLAUDE_CODE_PROJECTS_SESSION=1`. The note asks for the link at the top of the first reply, and in the checklist header in a project thread. |
| Link owed in the first reply | Stop `handover`, `handover_links_owed` | Blocks once when the first reply of a cloud session lacks the `/code/session_` link. In a plain cloud session there is no `post_message`, so it reads the reply text. |
| Long-call check (3A, 4A) | PreToolUse, new handler `longcall` | Stops a call that will run over 60 seconds or show nothing while it runs: a Bash `timeout` over 60000, a `sleep` or wait loop, `run_in_background`, Monitor, and a foreground Agent or Task call. The refusal says to ask aj in the reply or split the work. aj's next message saying yes lets the one call asked about through. `HOUSE_RULES_LONG_CALLS=off` turns it off. |
| Progress lines | PostToolUse, new handler `progress`, plus `stallcheck.py --every` | One timestamp file per session. After 2 minutes with nothing visible posted, the next tool result asks for one progress line. For approved long work, `stallcheck.py --every 120` prints a status line on a fixed interval and counts the work's live processes, since an output file can stop growing while the work runs (seen with `verify.py` on 2026-10-28). |
| Helper work trail, everywhere | PostToolUse `audit`, UserPromptSubmit `userpromptaudit`, `_worktrail_note` | Runs in every session, not only project threads. Cloud and local sessions write to a git-ignored `work-trail/` folder in the project; project threads keep `/mnt/project-files/work-trail/`. The renderer lists every tool call with a short result, the helper's prompt, its text and its report, not only shell commands and writes. Refreshed at each progress line while the helper runs. |
| Rule section | `rules/house-rules.md` | One section in aj's words: nothing hidden without an easy way to see it; long or quiet work asked for first, otherwise short visible steps. The delegation rule says a helper is a long call. |
| Trace default | `house_rules/core.py`, `trace_verbose` | `HOUSE_RULES_TRACE` defaults to `verbose`; `on` brings back the 2.48.0 level, `off` still silences. |

## Invariants

- No session link or transcript reaches git: the `work-trail/` folder is git-ignored, and the #405 credit guard
  is unchanged.
- No handler reaches the network.
- Every failure to build a link, write a trail or read a timestamp is said in the same turn.

## Open, to prove during the build

- That a Monitor line wakes a project thread mid-task. Untested from a cloud session; it needs a real thread.
- The token cost of the `verbose` trace default, measured with `tools/measure_footprint.py`.
