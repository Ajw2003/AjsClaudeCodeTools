# Plan: a permission prompt nobody answers for 5 minutes stops blocking the session

STATUS: proposed 2026-10-04, not approved, nothing built. Building it takes more than three steps,
so the issue workflow applies: one parent issue and one child per step before any source edit.

## The problem, in aj's words

> Currently the issue we need to solve is you getting stuck over night because of a single
> permission prompt and letting that block the whole session when it should not. Permission as a
> blocker should be isolated, not affect the rest of the project.

Asked for: a 5-minute timer on permission prompts. If a prompt is still unanswered after
5 minutes, Claude tries to solve the problem with tools and calls that need no permission.

## What Claude Code allows (read 2026-10-04, then probed on 2.1.289)

From the hooks reference (code.claude.com/docs/en/hooks, `PermissionRequest`):

> This hook runs in parallel with the permission dialog shown to the user. Both the hook and the
> dialog race: whichever finishes first determines the outcome. If the hook allows or denies the
> call, the dialog closes and the hook's decision applies. If the hook defers or times out, the
> user's choice on the dialog takes effect.

Hook timeouts default to 600 seconds and can be set higher. So a hook that waits 300 seconds and
then refuses works as a real timer on the dialog. Nothing in the docs gives prompts a built-in
expiry, so this race is the only way to time one out.

Probes run in this session (scratch hooks, headless `claude -p` on Claude Code 2.1.289, Haiku):

| # | What was tested | Result |
|---|---|---|
| B | A `PreToolUse` hook returns `ask` (what `guard` does) | Headless: refused at once, `PermissionRequest` **never fired**. Headless has no dialog, so this says nothing yet about the desktop app. |
| C | An ordinary prompt (`touch`, not allow-listed, default mode) | `PermissionRequest` fired, the hook waited 5 s and refused, and Claude went on to reply. |
| C | Refusal text in `decision.reason` (the field the docs name) | Claude saw only `Permission denied by hook`. The reason was **not** passed on. |
| D | The same text in `decision.message` | Claude saw the text, ran the suggested alternative command (`echo ALT_DONE`), and finished. |

Not yet tested, because an interactive session here needed a browser login (and copying this
sandbox's credentials was rightly refused):

- **R1.** In the desktop app, does a `guard`/`guardwrite` `ask` reach `PermissionRequest`? These
  are the prompts the overnight stalls actually come from, so the plan depends on this answer.
- **R2.** When aj answers first, does Claude Code stop the waiting hook, or does it keep running?
- **R3.** Does `PermissionRequest` fire for a subagent's prompt as well as the main thread's?

## The mechanism

### 1. A new `prompttimer` handler on `PermissionRequest`

`hooks.json` gets a `PermissionRequest` entry with no matcher (every tool) and a 330-second
timeout, which is longer than the 300-second wait. `hook.py` gets `event_prompttimer`:

1. Write a "waiting" entry to the queue file (section 3): session, tool, a one-line summary of the
   command or file, and the start time.
2. If this session already timed out on this exact action, and aj has not sent a message since,
   refuse at once. A retry should not cost another 5 minutes.
3. Otherwise wait in 1-second steps for `HOUSE_RULES_PROMPT_TIMEOUT` seconds (default 300;
   `off` turns the whole feature off).
4. If it is still running at the end, aj has not answered. Mark the entry "timed out" and refuse,
   with the instructions in section 2 in **both** `message` and `reason` (probe C/D: only
   `message` reaches Claude on 2.1.289, and `reason` is the documented name).

**It only ever refuses, never approves.** An unanswered prompt is not a yes. The destructive
action does not run. Only the wait is removed. `verify.py` checks that the handler has no route
to an `allow`.

### 2. What Claude is told when the timer fires

The refusal text is the enforcement Claude actually sees, so it does the work:

- What was refused and why: unanswered for 5 minutes, queued for aj, **not** approved.
- Do not retry the same action in this session. It would only wait again.
- Look for a route that needs no permission **and does not have the same effect**. Examples:
  - Committing or pushing on `main` or another of aj's branches: branch to `claude/<topic>`,
    commit and push there, and leave the merge to aj.
  - A full-file `Write` over an existing file: make the same change with `Edit`.
  - Deleting, force-pushing or killing a process: no safe substitute. Leave it, note it.
- Getting the same destructive result by another tool, command or encoding is forbidden. (Such a
  route would hit `guard` again anyway, and wait again.)
- Carry on with every part of the task that does not depend on the refused action.
- Before stopping, list each refused action under **Waiting on you** in the final reply, with what
  it would have done.

### 3. The queue: a blocked action stays recorded and doesn't block anything else

One small JSON file per repository, `<git common dir>/house-rules/waiting-on-you.json`. It goes
in the same place `agentcap` already keeps its state, so worktrees share it and it never shows up
in `git status`. Each entry: session, time, tool, one-line summary, status
(`waiting` / `timed-out`).

- **`UserPromptSubmit`** (folded into the existing `scope` handler, not a new process): when aj
  sends a message, list the session's timed-out actions as context ("2 actions waiting on you since
  02:14: …"). Clear the retry block from step 1.2, so a retry now shows a normal prompt again.
  Delete `waiting` entries, because aj is evidently present.
- **`SessionStart`** (folded into `issuelist`): show entries left over from earlier sessions in
  this repository, so a stall overnight is visible the next morning in any session.
- **Removing entries:** an entry goes once aj approves the action (it runs) or says to drop it.
  Each entry is keyed by session and a hash of the tool input, the same way `versioncheck`'s
  marker is keyed by session, which is why one session's leftover is never mistaken for another's.

### 4. Changes to existing parts

| Part | Change |
|---|---|
| `hooks.json` | Add the `PermissionRequest` → `prompttimer` entry (timeout 330). |
| `hook.py` `event_guard` / `event_guardwrite` | One line in the prompt text: "Unanswered for 5 minutes, this is refused and queued. It never runs by itself." |
| `hook.py` `event_scope`, `event_issuelist` | Show the queue (section 3). |
| `rules/house-rules.md` | One clause in "Never take a destructive action without checking first": an unanswered prompt is a no; route around it without the same effect. **The file is at 9,692 of its 9,700-character limit**, so other wording has to be trimmed to fit. The limit stays where it is. |
| `rules/detail/destructive-action.md` | The full version of section 2, with the examples. |
| `docs/architecture.md` | A row in the hook table; the queue file recorded as a second deliberate exception to "no hook keeps state", with the reasons, next to `versioncheck`'s marker. |
| `docs/4-systems/hook-engine.md`, `verify-suites.md` | Describe the handler and its tests. |
| `docs/6-decisions/Decisions.md` | Dated entry: why a race-and-refuse timer, why never approve, why `message` plus `reason`. |
| Roadmap, ProjectState, Today | Update in the same change. |
| Plugin version | 2.52.0. |

### 5. Tests in `verify.py`

Run with `HOUSE_RULES_PROMPT_TIMEOUT=1`, so the suite stays fast:

- An unanswered prompt gives `behavior: deny`, with the instructions in both `message` and
  `reason`, and the queue holds one `timed-out` entry.
- The handler has no path to `allow`, whatever the input.
- The same action again in the same session is refused at once, without the wait.
- A `scope` run (aj sends a message) lists the entry and clears the retry block.
- `HOUSE_RULES_PROMPT_TIMEOUT=off` makes no decision and writes nothing.
- An unreadable or corrupt queue file is reported out loud and does not crash the hook. On
  failure the hook makes no decision, which leaves the dialog in charge as it is today; it never
  allows.
- Timed with a wall clock: the 1-second setting refuses after about 1 second, not 0 or 10.

## Build order (one child issue each)

1. **Settle R1-R3 on the desktop app.** Drop the scratch probe hooks into a throwaway project, run
   one prompt Claude Code shows on its own and one `guard` `ask`, leave both unanswered, then
   answer one early. Record the result in Decisions. **Everything after this step waits on R1.**
2. `prompttimer` handler, queue file, `hooks.json` entry, tests.
3. Showing the queue from `scope` / `issuelist`, plus the one-line note in the `guard` and
   `guardwrite` prompt text, plus tests.
4. Rule clause (with the trim), detail file, docs tiers, Decisions entry, version bump.
5. A real overnight-shaped check: a session left with a destructive action prompting and other
   work queued behind it. After 5 minutes the work carries on, and the action appears under
   "Waiting on you" and at the next session start.

## If R1 comes back "no" (the `guard` prompts never reach `PermissionRequest`)

No hook can close a dialog that `PreToolUse` opened. Then the timer covers only the prompts
Claude Code shows on its own, not the house-rules ones. The fallback is an **absence check
instead of a timer**: `scope` records when aj last sent a message, and when `guard` matches more
than 5 minutes after that, it refuses with the section 2 text and queues the action instead of
asking. Two weaknesses: aj reading without typing counts as away, and it predicts an unanswered
prompt rather than timing one. Either is easy to undo, though: aj says "go" and the retry asks
normally. If R1 fails, aj decides whether the fallback is worth it before anything is built.

## Out of scope (not asked for)

Other dialogs that can also stall a session overnight: `AskUserQuestion`, plan approval, and the
desktop app's "trust this folder" prompt. They are not permission prompts, and none of the above
touches them.
