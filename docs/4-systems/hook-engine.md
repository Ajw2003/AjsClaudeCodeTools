# The hook engine

## What it owns

Dispatching every `house-rules` hook event — `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
`PostToolUse`, `Stop`, `SubagentStart`, `SubagentStop` — to the one handler that enforces the
corresponding rule from
[`rules/house-rules.md`](../../claude-house-rules/plugins/house-rules/rules/house-rules.md), at
the moment Claude Code actually fires that event. If this is wrong, the rules stop being
enforced and become prose nobody is checking against — a permission prompt that should have
fired doesn't, or a reminder that should have reached Claude never does.

It does **not** own: whether the rule text itself is right (that's the rules document), whether
the claims in this doc are still true (that's
[`verify-suites.md`](verify-suites.md)'s job), or getting the plugin onto a machine in the first
place (that's [`plugin-distribution.md`](plugin-distribution.md)).

## How it works

Every hook command in
[`hooks/hooks.json`](../../claude-house-rules/plugins/house-rules/hooks/hooks.json) is identical:
`sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`.
[`scripts/run.sh`](../../claude-house-rules/plugins/house-rules/scripts/run.sh) is the one
POSIX-sh file left in the plugin, and its only job is finding a Python interpreter that actually
runs code — it **probes** each candidate (runs it, checks the output) rather than trusting
`command -v`, because on this machine `python3` is the Windows Store App Execution Alias stub:
on PATH, found by `command -v`, but it prints an install nag and exits 0 without running
anything. Trusting PATH membership would silently disable every hook the same way a missing
`node` once did (an earlier, pre-Python version parsed payloads with `node`).

`run.sh` execs
[`scripts/hook.py`](../../claude-house-rules/plugins/house-rules/scripts/hook.py) with the event
name as `argv[1]`; the payload always arrives on stdin
(`hook.py:1-6`). `main()` looks the event up in the `EVENTS` dispatch table
(`hook.py:2034-2046`) and calls the matching handler:

| Event | Handler | Fires on |
|---|---|---|
| `SessionStart` | `event_inject` | every session — prints the rules + machine profile |
| `SessionStart` | `event_standards` | every session — prints applicable per-repo coding standards |
| `UserPromptSubmit` | `event_scope` | every prompt — restates the short rule reminder |
| `PreToolUse` (`Bash`/`PowerShell`) | `event_guard` | before a shell command runs |
| `PreToolUse` (`Write`) | `event_guardwrite` | before a `Write` would replace an existing file's entire contents |
| `PostToolUse` (`Write`/`Edit`) | `event_artifact` | a document written outside the project |
| `PostToolUse` (`Write`) | `event_runnable` | a runnable file just created |
| `PostToolUse` (`Write`/`Edit`) | `event_harvest` | a comment block has grown into an essay |
| `PostToolUse` (`ExitPlanMode`) | `event_delegate` | a plan was just approved |
| `SubagentStart` | `event_announce` | any subagent spawns |
| `SubagentStop` | `event_verdict` | any subagent finishes |
| `PreToolUse` (`Write`/`Edit`/`NotebookEdit`) | `event_commitgate` | 3+ uncommitted files on a subagent's `worktree-agent-` branch |
| `PostToolUse` (`Write`/`Edit`/`NotebookEdit`/`Bash`) | `event_autosave` | any step on a subagent's `worktree-agent-` branch |
| `UserPromptSubmit` | `event_worktreesweep` | every parent wake - commits subagent worktrees left untouched 10+ min |
| `Stop` | `event_handover` | a turn ends handing over an untested-looking command |

Full per-handler behavior, including *why* each one is shaped the way it is, is the subject of
[`docs/architecture.md`](../architecture.md) — this doc states what's true now and what breaks it;
that one carries the reasoning and post-mortems, per the [[sixth-documentation-tier]] boundary
between tier 4 and `docs/6-decisions/Decisions.md`.

Every handler is **stateless** except two: nothing is written to disk between invocations,
nothing carries over between turns. The exceptions are `autosave` and `commitgate` (2.47.0),
which keep three small files per branch inside that worktree's own git dir, never the temp
directory: the last push time, whether the subagent has already been asked to commit, and a
said-once "no origin" marker. `subagentcommit` deletes them, with the autosave ref, when the
subagent finishes clean. An earlier version enforced the deliver-a-whole-workflow rule with a `Stop`
hook that kept session state in the temp directory; it leaked a file for every session that
ended unexpectedly, and any unrelated shell command silently defeated it. That machinery is gone
on purpose — `verify.py` fails if it reappears.

**Trace tiers (2.48.0).** `trace()` prints under `HOUSE_RULES_TRACE=on` (the default) and is for
"could not tell" and "acted" messages. `trace_noop()` is for "looked, nothing to do" and prints only
under `HOUSE_RULES_TRACE=verbose`; `off` silences both. `harvest` speaks by default only when it
found blocks or ignored a bad override. `run.sh` remembers the interpreter that last passed its
probe in `scripts/.python-cache` (gitignored, reset when the plugin directory is replaced on
update, deleted and re-probed if the cached command stops resolving; a probe-failing stub is never
written). `_autosave_target` reads `.git/HEAD` through `_git_dir()` first, so `autosave` and
`commitgate` spawn no git process unless the branch is `worktree-agent-*`.

**Issue workflow (2.49.0, issues #108-#110).** Plans over three steps become issues before code, pull
requests link with `Refs` and never close, and closing an issue always asks. The hooks force Claude to
do these; none runs `gh issue create` or `gh issue close`. No new hook process on Write, Edit or Bash:
`delegate` counts the plan's steps (numbered lines, `- [ ]`, `### Step`/`### Change`) and, over 3,
writes `house-rules-issues.json` into the git directory (`_git_dir()`, so a linked worktree or a
subagent's worktree has its own and is not gated by the main session's plan); `commitgate` reads it
before its subagent logic and denies Write/Edit/NotebookEdit on source files while `needs_issues` is
true (`docs/`, `.claude/`, any `.md`, files outside the project and the state file stay open); the
existing Bash PostToolUse entry that runs `autosave` parses `gh issue create` output for the issue URL and
the `AjsAgent created this` label (the old `Claude created this` still counts) and clears the gate at two labelled issues; `handover` adds one Stop
line while the gate is shut; `guard` denies a `gh pr create` whose body lacks `Refs #N` / `Part of #N` /
`No-issue:` or pairs a closing word with an issue reference, and asks on `gh issue close`, `gh issue edit
--state closed` and a `gh api` PATCH to closed. `issuelist` is a sixth SessionStart entry (its own, because
`inject` sits near its size margin) that lists up to 10 open issues with a 5 s timeout and a 60 s cache;
it is the only network call and never runs on a tool call. A corrupt state file is reported in one line
and treated as no gate. `HOUSE_RULES_ISSUES=off` disables all of it. Known limit: `gh issue create` run
through the `PowerShell` tool is not recorded (the `autosave` entry matches `Bash`, not `PowerShell`, and
widening it would add a process per PowerShell call). Plan: `docs/plans/issue-workflow-build-plan.md`.

**Prompt timer (2.52.0, issues #142-#146).** `prompttimer` is the plugin's one `PermissionRequest` entry (no
matcher, timeout 330). That event runs at the same time as the permission dialog, and whichever finishes first
decides. The handler waits `HOUSE_RULES_PROMPT_TIMEOUT` seconds (default 300; `off` or `0` disables), then
refuses with the same text in `decision.message` and `decision.reason`. Probed on 2.1.289: only `message` reached
the model. It never emits an allow. The refused action goes into `<git common dir>/house-rules/waiting-on-you.json`
(outside a repository: a session-keyed temp file), changed only through `_waiting_update`, which holds a
`.lock` file (O_EXCL, 3 s wait, stale after 15 s, loud and unlocked if the lock can't be taken). The same
action again in the same session is refused at once until aj's next real message. On that message `scope`
lists the session's timed-out entries and marks them `reported`; a background task notice does not count.
`issuelist` shows entries other sessions left (newest 10) at session start and drops them, plus anything older
than 7 days. `guard` and `guardwrite` prompts carry one line naming the timeout. Untested: whether a `guard`
`ask` reaches `PermissionRequest` in the desktop app (#143); headless it does not. Plan:
`docs/plans/2026-10-04-permission-prompt-timeout.md`.

**Default-branch rule and unattended refusals (2.60.0, issues #196-#199).** `guard` marks commit, plain push,
merge, rebase, revert, cherry-pick, `am` and `apply` `BRANCH_WRITE`. On the default branch (`is_protected_branch`:
`main`, `master`, or `default_branch()`, a file read of `<common git dir>/refs/remotes/origin/HEAD`) they are denied
with `PROTECTED_DENY`; `_push_targets_protected` also denies a push from any branch whose destination is one of
those names. Off it they are exempt, and `_only_git_statements` decides whether the hook returns `allow` (every
statement `git` or `cd`) or stays silent (anything else rides along, so Claude Code's own rules still judge it).
`_command_dir` follows `git -C <dir>` when every `-C` names the same directory and nothing `cd`s; any other `-C`
(`grep -C 3` included) leaves the branch unknown, which asks. The remaining asks go through `_ask_or_refuse`: a
payload with `agent_id`, or a `house-rules-last-seen-<session>` temp file (written by `scope` on each real message)
older than the prompt timeout, turns the ask into a deny and adds a `refused` / `timed-out` entry to the
waiting-on-you list, which `scope` reports on aj's next message. Plan: `docs/plans/2026-10-09-stop-permission-stalls.md`.

**Prompt timer follow-ups (2.53.0, issues #149, #151, #152).** Three changes. (1) `AskUserQuestion` and
`ExitPlanMode` are in `PROMPT_TIMER_EXEMPT_TOOLS`: the handler says so on stderr and makes no decision, because
refusing a question throws the question away rather than routing around a blocked action. (2) If the session
already holds a `timed-out` entry (aj has not written since), any new prompt is refused at once and queued as
`timed-out`: aj has had the full wait once, and each further prompt would cost another. `scope` marks the
entries `reported` on aj's next message, which ends this. (3) `promptran`, on `PostToolUse` and
`PostToolUseFailure` for the prompt-capable tools, keys the call the same way (`_waiting_key`): a `waiting`
entry becomes `ran`, and the waiting `prompttimer` checks the list once a second and exits with no decision
when it sees that. This covers an approval that never sent the hook SIGTERM (#149: a push that landed was
recorded as timed out). A `timed-out` entry for a call that ran is removed and reported, which is how a late
answer on a stale dialog would show up. `scope` and `issuelist` drop `ran` entries. Known limit: no hook
output closes the app's dialog once the timer has refused (#149); the refusal reaches the model, the dialog
can stay on screen.

**Saved-work exemption (2.53.0, issue #153).** Patterns marked `SAVED` (`reset`, `revert`, `rebase`,
`checkout --`, `restore`) stand down only when the checkout is on an `AjsAgent/` (or `claude/`) branch, the command names no
other repo, and `work_saved_elsewhere()` reports a clean tree (`git status --porcelain -uall` empty) and no
commit missing from every remote (`git rev-list --count HEAD --not --remotes` is 0). It runs at most once
per command, only when such a pattern matched on my branch, with a 2-second budget; any failure is a no. A
prompt that this could have silenced adds one line saying why it did not. Force-push, `clean`,
`stash drop/clear`, `rm`, and merge-like verbs never use it.

**Attribution (2.51.0, issue #133).** `guard` also refuses a `git commit`, `gh pr create|edit` or `gh issue create|comment`
whose text credits Claude (a `Co-Authored-By` line naming Claude or anthropic.com, `Generated with [Claude Code]`, a
`Claude-Session` trailer or a claude.ai/code link). The wording to use is `Committed by AJ's agent` and
`Opened by AJ's agent`, with no email. This is the backstop: the primary mechanism is the Claude Code `attribution`
setting, which `tools/install.py` writes into the user's settings file. Kill switch `HOUSE_RULES_ATTRIBUTION=off`.
A `--body-file` is read; a commit `-F file` is not.

**Author identity (2.58.0, issue #177).** Cloud containers ship `user.name=Claude`, which signs every commit as
Claude whatever its message says. `_author_guard` (next to `_attribution_guard`, same kill switch) works out a
`git commit`'s author in this order: `--author`, `-c user.name/user.email`, inline `GIT_AUTHOR_NAME/EMAIL`, then
`git var GIT_AUTHOR_IDENT` in the payload's cwd (5 s timeout). It denies a name that is exactly `Claude` (any case) or
an email ending `anthropic.com`, naming the fix `git config user.name "AJ's agent" && git config user.email
"79066376+Ajw2003@users.noreply.github.com"` (repo-local). If `git var` fails it allows silently. Works through
the PowerShell tool via `_decoded_command`. Quoted `-c` values with spaces, and a wholly quoted
`-c "user.name=..."`, are read as one value (2.61.0, issue #189); before that the shared `_GIT` prefix
stopped at the space and neither check saw the commit at all.

**GitHub tools (2.59.0, issue #178).** `guard` only sees shell commands, so writes through the GitHub MCP tools
skipped the attribution check. `event_guardgithub` (own `PreToolUse` entry, matcher
`mcp__(github|GitHub)__(create_pull_request|...|create_branch)`, eleven write tools) reads `title`, `body` and
`message` and denies on any `_ATTRIBUTION_TEXT_RES` hit with the `ATTRIBUTION_DENY` wording ("commit message" for
`push_files` and `create_or_update_file`, else "pull request or issue text"). It also denies a `create_branch`
`branch` or `create_pull_request` `head` starting `claude/`, telling the agent to use `AjsAgent/<topic>`. File
`content` is never read, and a push onto an existing `claude/` branch is allowed. Kill switch
`HOUSE_RULES_ATTRIBUTION=off`. Unlike `guard` it fails open: an unreadable payload is a one-line `systemMessage`
and an internal error falls to `main()`'s "hook hit an internal error" message, exit 0.

**Helper tiers and the spawn cap (2.50.0, issues #110-#112).** `agents/executor.md` is retired; `scout`
(haiku; Read, Grep, Glob), `builder` (sonnet; Read, Edit, Write, Bash, Grep, Glob) and `reviewer` (opus;
Read, Grep, Glob, Bash) replace it, each a short role with a tool allowlist, and none can start a
subagent. `agentcap` is a PreToolUse entry matched to `Agent`/`Task` (it runs only when a spawn is
attempted, never on Write, Edit or Bash). It reads a JSON list in the common repository directory
(`git rev-parse --git-common-dir`, found through the `commondir` file `_git_dir()`'s directory holds, so
every worktree shares it), kept by `announce` (adds) and `verdict` (removes). Two running subagents deny a
third; a record older than 45 minutes is ignored; a spawn whose payload carries `agent_id` is denied;
`HOUSE_RULES_AGENTS=off` disables it; a corrupt or unreadable file is one `systemMessage` and the spawn is
allowed. `audit`/`verdict`/`userpromptaudit` now print counts per tool, every failed command in full,
every file written and a count of the other commands. `issuelist` adds a visible
`house-rules: N open issues loaded` (or `no open issues`) in the same JSON object as its context.
Plan: `docs/plans/subagent-tiers-build-plan.md`.

## Invariants

- **`hook.py` is stdlib-only Python** (`hook.py:8-10`) — no third-party imports, nothing beyond
  CPython 3.8+. `run.sh` is the one POSIX-sh dependency in the whole plugin.
- **Every handler's failure mode is fixed and deliberate** (`hook.py:16-34`, the module
  docstring): `guard` fails **closed** — an unreadable payload or internal error writes to
  stderr and returns `2`, blocking the command (`event_guard`, `hook.py:793-803`); `inject` fails
  **loud, not closed** — a missing rules file still emits a `systemMessage`; `scope` **cannot
  fail** — it never reads a file or raises, because a non-zero exit on `UserPromptSubmit` erases
  the user's prompt; `artifact`/`runnable`/`delegate`/`harvest` never obstruct but never go quiet
  — every failure emits a `systemMessage` and exits 0; `handover`, `announce`, `verdict` fail
  **open and loud** — a `decision: "block"` from any of them would stop a turn or a subagent from
  ever finishing.
- **Nothing fails silently.** `verify.py` enforces this structurally over `hook.py`'s own source:
  no `except` block may return or `pass` without emitting, writing to stderr, or recording the
  problem for its caller. An `except` that *recovers* — assigns a fallback and continues — is not
  the defect; the defect is giving up without saying so. `main()`'s last-resort net
  (`hook.py:2049-2085`) catches anything a handler itself missed and speaks for every event.
- **`guard` reads the branch from `.git/HEAD`, never from `git rev-parse`.** `guard` runs on
  every `Bash`/`PowerShell` call and is the one handler that fails closed, so a subprocess on
  that path is a subprocess that can wedge the user's shell for as long as it hangs (a stale
  index lock, a network filesystem, an AV scan on first exec). Reading one file cannot hang that
  way, and it keeps `guard` working where `git` isn't on `PATH`. `verify.py` fails if
  `branch_ownership()` ever reaches for `subprocess`, `os.popen`, `os.system`, or
  `check_output`.
  <!-- ref:ee0f -->
- **No hook keeps state between invocations** — `verify.py` fails if a dead state file or a
  stray `.sh` hook script reappears, or if anything other than `run.sh` is registered on any
  event.
- **Matching is textual**, not semantic, even where it costs a false positive (`echo "git
  commit"` still prompts) — an extra keypress is cheaper than a missed commit.
- **The `guard` trace decodes the command for display; matching still runs on the raw JSON
  slice.** `_guard_subject` deliberately returns the raw slice with escapes intact, because
  matching against escapes intact is what keeps the patterns honest. Printing that raw slice to
  the user would show `"command": "git status"` rather than `git status`, so `_trace_subject`
  (`hook.py:1006-1014`) decodes a copy for the one-line trace only; the match itself never sees
  the decoded form.
  <!-- ref:361f -->
- **`standards` detects a Unity project opened at its `Assets/` folder, not just at its root.**
  Opening a Unity project directly at `Assets/` is a normal workflow, but `_standards_scan_dirs`
  never sees the sibling `ProjectSettings/`/`*.csproj` markers one level up. `_unity_markers_in_
  parent` (`hook.py:340-349`) checks narrowly — the directory must be named exactly `Assets` and
  its parent must carry a real Unity marker (`ProjectSettings/ProjectVersion.txt`, or another
  Unity-marker file) — so a coincidentally-named `Assets/` folder in a non-Unity repo doesn't
  false-positive. When it matches, detection re-scans from that real project root instead of
  `Assets/`, so a sibling Node service next to `Assets/` is still found too.
  <!-- ref:0d4d -->
- **`standards` output stays under its 9,500-char budget in a Unity-only project and in a
  Unity + Node one, and the Unity tools-first rule lives there, not in the core.** The Unity
  document is split the way the rules are: `rules/standards/csharp-unity-standards.md` is the
  always-injected core (C# style, a "read the detail file first" pointer, and the "Unity work
  starts with the Unity plugin and the Unity CLI" rule), and the rest moved verbatim to
  `rules/standards/csharp-unity-detail.md`. `event_standards` expands `${CLAUDE_PLUGIN_ROOT}` in
  what it emits, as `inject` does. Until 2026-09-29 nothing measured `standards` in a Unity
  project, so it emitted 9,832 chars (Unity only) and 13,376 (Unity + Node) against a 10,000 hard
  limit unnoticed. `verify.py` now measures both fixtures. `tools/sync_standards.py` overwrites
  the vendored file from `Ajw2003/Coding-Standards`; a sync reverts the split, and that
  size check is what would say so.
  <!-- ref:23c3 -->
- **`profile`'s runtime-detected fallback records hardware and the Claude plan, with a time
  budget, and never leaves a field blank.** `_detect_hardware` in `hook.py` probes CPU (model and
  logical cores), RAM (`/proc/meminfo`, `sysctl hw.memsize`, or `GlobalMemoryStatusEx`), GPU
  (`nvidia-smi`, else `system_profiler` on macOS or a CIM query on Windows, where an exact 4 GB
  reading is marked "may be higher"), free disk on the project drive, and the plan from
  `claude auth status --json`. Each subprocess gets 3 s and all of them share 6 s, under the
  profile hook's 10 s timeout in `hooks/hooks.json`. A failed probe prints `not detected
  (<reason>)`. Where `claude auth status` has no plan field (as in a cloud session) it says so
  rather than guessing. On a remote session the block is headed as the sandbox's, for Claude's
  own checks, and points at `rules/handover-target.md` for the local build budget. A remote
  session on a `claude/<name>` branch also gets `_agent_branch_block`: an instruction to
  `git switch -c AjsAgent/<name>` (or `git switch` to it when it already exists locally or on
  `origin`) and to push and open PRs from there. Text only, the hook never switches;
  `HOUSE_RULES_AGENT_BRANCH=off` disables it. A remote session whose `git var GIT_AUTHOR_IDENT` is Claude also gets
  `_agent_identity_block`, one line telling it to run the repo-local `git config` fix before its first commit
  (text only; nothing when the identity is fine or unreadable; `HOUSE_RULES_ATTRIBUTION=off` disables it). Only the
  fallback probes: a hand-recorded `rules/environment.md` replaces it, so hardware missing from
  that file is not re-detected. The macOS and Windows branches were written to the documented
  command shapes and not run on those systems.
  <!-- ref:ad50 -->
- **`guardwrite` treats any `Write` to a file that already exists as a full-file replacement,
  full stop — there is no size threshold or content diff that lets a "small" rewrite through.**
  `Write` always replaces a file's entire contents; there is no partial form. A full rewrite is a
  delete and a recreate wearing a single tool call, whether it goes through `rm` (which `guard`'s
  broadened `rm` pattern also now catches with no flag needed) or through `Write` targeting a path
  that is already on disk. Git being able to recover the old blob afterward does not make the loss
  safe, because nobody reviews the diff line by line before an unattended write ships — which is
  the exact failure this hook exists to catch: a scheduled, unattended task once rewrote a CSS file
  wholesale instead of touching the one rule that needed to change, and the regression sat
  unnoticed until someone found it later. `event_guardwrite` (`hook.py`, after `event_guard`) always
  asks in this case; it cannot know *why* a rewrite is happening, only *that* one is about to, so
  the reason it names is what will be discarded, and the "why" is left to whatever Claude has
  already said in chat, per the rule in `rules/house-rules.md`.
  <!-- ref:bf94 -->

## Traps

- **A shim that finds an interpreter on PATH is not proof it runs code.** The `python3` stub
  above is the concrete example this plugin was built around; `run.sh` probing rather than
  checking `command -v` is the fix, and any future interpreter-selection change that reverts to
  a PATH check reopens this.
- **`guard`'s git-prefix regex had a hole `-C` fell through.** Every git pattern shared a prefix
  meant to skip global options (`git\s+(-[^\s]+\s+)*`); it could match a flag but not a flag's
  *argument*, so `git -C /other/repo commit` consumed `-C `, met `/other/repo`, and never reached
  the subcommand — the pattern matched **nothing**, and the command sailed through unchecked.
  Invisible while the answer was always "prompt anyway"; load-bearing the moment `-C` became
  something that should have *withheld* the branch-ownership exemption. Now a shared `_GIT`
  constant knows which global options take a separate argument.
- **The `harvest` scan is budget-bounded, not size-capped, and the first draft got this
  backwards.** Skipping files over a byte ceiling is a silent failure wearing a performance
  argument — the check just doesn't run, and nobody is told which file it skipped. An O(n²)
  accumulator rebuilding each comment run's line list per line took **22 seconds** on a 4.8 MB
  file, past `hooks.json`'s 10-second timeout, so in practice the harness killed the hook rather
  than the hook reporting anything; fixed, the same file scans in 0.29s. Any future change to the
  harvest scan that reintroduces per-line quadratic work reopens this at the next large file.
- **`verify.py`'s guard/branch cases must use hand-written fixture `.git/HEAD` files, not
  whichever branch the suite happens to be run from.** Once a decision depends on branch
  ownership, a suite that inherits the developer's real branch makes the result a property of
  the checkout: it would pass on `main`, fail on an `AjsAgent/…` branch, and agree with neither —
  CI checks out a detached `HEAD`.
- **Every uncertainty in branch ownership resolves to "not mine," never to "assume it's fine."**
  The user's branch, a detached `HEAD`, a directory that isn't a repo, an unreadable `HEAD` all
  fall through to a prompt. A change that adds a new "can't tell" case must route it the same
  way, not default it open.
  <!-- ref:d2a4 -->
- **Ownership is judged where the command runs, not at the project root.** `branch_ownership(start)`
  gets the PreToolUse payload's `cwd` (`_command_dir`), falling back to `CLAUDE_PROJECT_DIR`, then
  `getcwd()`. A subagent with `isolation: "worktree"` runs in `.claude/worktrees/agent-<id>/` on its own
  `AjsAgent/` branch while `CLAUDE_PROJECT_DIR` stays the main checkout; reading the project root judged
  every such commit as "theirs" and prompted (timed out and refused when aj was away). A linked
  worktree's `.git` is a file; `_git_dir` follows it to the worktree's own `HEAD`. A lone leading
  `cd <dir> &&` moves the judged directory; any other `cd`/`pushd`, or a `cd` that does not resolve,
  withholds the exemption (same path as `-C`). A `cd` counts only where a command can start (line
  start, after `;` `&` `|` `(` `{` `!` or a new line, or after `if`/`then`/`do`/`else` and the like),
  so `git commit -m "fix cd handling"` keeps the exemption (2.61.0, #203). Owned prefixes are `AjsAgent/`, `claude/`, `ccr-`
  (cloud sessions) plus `HOUSE_RULES_OWNED_BRANCHES` (comma-separated extras, never replacing).
