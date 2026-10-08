# house-rules

Your global CLAUDE.md rules, turned into a Claude Code plugin so they follow you to every
device and every project instead of living in a file you have to copy into each repo.

## What it actually does

Every hook, defined in [plugins/house-rules/hooks/hooks.json](plugins/house-rules/hooks/hooks.json),
runs the same command — `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>` — which resolves a
working Python interpreter and hands off to
[scripts/hook.py](plugins/house-rules/scripts/hook.py), where every handler lives:

| Hook event | When | What it does |
|---|---|---|
| `SessionStart` | every session, every project | the `inject` handler prints [rules/house-rules.md](plugins/house-rules/rules/house-rules.md) into Claude's context, with `${CLAUDE_PLUGIN_ROOT}` substituted for the real path. This is the CLAUDE.md replacement — no per-repo file needed. |
| `SessionStart` | every session, every project | a second entry, split out of `inject` so the two stay under Claude Code's 10,000-char per-hook limit separately: the `profile` handler prints [rules/environment.md](plugins/house-rules/rules/environment.md) (or a runtime-detected fallback) and preflight warnings, truncating with a visible notice if the recorded profile is itself too large. |
| `SessionStart` | every session, every project | a third entry on the same event, so a detection failure here can never take down the injection above: the `standards` handler selects and prints the coding standards docs from [rules/standards/](plugins/house-rules/rules/standards) that apply to the repo it's sitting in — always the coding philosophy, plus the C#/Unity and/or web/JS/TS/Node docs when their project markers are detected. A repo whose needs differ pins its own set in `.claude/standards` (one document name per line). |
| `SessionStart` | every session, every project | a fourth entry, its own hook so a failure can't affect `inject`/`profile`/`standards`: the `docstiers` handler checks the project root for the six documentation tiers named in [skills/project-docs/SKILL.md](plugins/house-rules/skills/project-docs/SKILL.md). All present, it says nothing at all; any missing, it names which and tells you to load `house-rules:project-docs` and scaffold them first — and, in a repo not owned by the configured GitHub account (`.git/config`'s remote, no subprocess), to add the scaffolded paths to `.git/info/exclude` too. |
| `SessionStart` | every session, every project | a fifth entry: the `versioncheck` handler compares the installed plugin version against the local marketplace clone **and** GitHub's default branch — the marketplace clone can go stale on its own, independently of the installed copy. A mismatch is fixed by the hook itself: it runs `claude plugin marketplace update` / `claude plugin update`, checks the new version really landed in `installed_plugins.json`, and tells you to start a new session to load it. If the newer version is already installed and only this session is old, it just says to start a new session. Only when the update fails does it print a loud warning, have Claude run the commands itself, and arm `guard` to prompt once on the next shell command. `HOUSE_RULES_AUTO_UPDATE=off` skips the automatic update; `HOUSE_RULES_VERSION_CHECK=off` disables the whole check. GitHub is tried at `raw.githubusercontent.com` first and `api.github.com` second. A network failure is never treated as "out of date," but if neither route answers, Claude is told and will mention it in its first reply, naming what failed. |
| `SessionStart` | every session in a GitHub repo | a sixth entry: the `issuelist` handler adds up to 10 open issue titles from `gh issue list --state open --limit 10 --json number,title`, only when `gh` is on PATH and `origin` is a GitHub remote. 5 s timeout, 60 s cache in the git directory; on failure it prints `house-rules: could not list open issues (<reason>)`. Its own entry because `inject` is at its size margin; it is the only network call in the issue workflow and it never runs on a tool call. `HOUSE_RULES_ISSUES=off` disables it. Issue #110. Also (#145): lists entries left in the waiting-on-you list by other sessions (newest first, max 10) to Claude and to you in the same single output, then drops those and any entry older than 7 days. |
| `UserPromptSubmit` | before every prompt you send | the `scope` handler restates the short version — match depth to the task, the environment is fixed, the request is the scope, deliver something runnable, artifacts go in the project, update the docs tier that changed, no success claim without a run you can quote. The SessionStart copy fades over a long session; this is what keeps it true at message 200. Also (#145): when the prompt is a real message from aj (not a background task-notification), it lists this session's `timed-out` entries from the waiting-on-you list as context, sets them to `reported` (which no longer blocks a retry) and deletes this session's `waiting` entries. |
| `PreToolUse` on `Bash` / `PowerShell` | before any shell command runs | the `guard` handler checks the pending command. If it trips a rule, Claude Code shows you a permission prompt naming the rule and quoting the command. It also checks for a pending `versioncheck` warning and prompts once for that, on the first command of an out-of-date session, even if the command itself is otherwise fine. On a `git commit`, it also checks the staged files: a staged source file with nothing staged under `docs/` gets a reminder — on your own branch the commit still runs, with the reminder attached for Claude; anywhere else it's folded into the prompt you already see. A missing `git`, a timeout, or a command naming another repo never changes the underlying decision. Issue workflow (2.49.0, `HOUSE_RULES_ISSUES=off` disables it): a `gh pr create` is denied unless its body (`--body`, `-b`, or the file named by `--body-file`/`-F`, which is read) says `Refs #N`, `Refs owner/repo#N`, `Part of #N` or a line `No-issue: <reason>`, and denied if it pairs a closing word (close/fix/resolve in any tense) with an issue reference, because GitHub would close the issue at merge before the user has tested; an unreadable body file, stdin or no body asks instead. `gh issue close`, `gh issue edit --state closed` and a `gh api` PATCH to closed always ask, with the follow-up (add `Claude completed this`, remove `in progress`, comment the merged PR link) added to the context. Issues #108 and #109. |
| `PreToolUse` on `Write` | before a `Write` runs | the `guardwrite` handler checks whether the target file already exists. `Write` always replaces a file's *entire* contents, so a call that targets an existing path is a full-file replacement by definition — there is no such thing as a small one. When it is, Claude Code shows you a permission prompt naming the file and, where it can, how many existing lines would be discarded for how many new ones. A brand-new path is never prompted about; only an overwrite is. This is the other half of "never take a destructive action without checking first" — `guard` catches a shell command deleting a file, this catches `Write` doing the same thing under a different name. |
| `Stop` | a turn ending with a reply that **hands over a shell command, or claims success with no evidence** | the `handover` handler hands Claude the command-handover checklist **once**, as Stop hook feedback rather than a blocking error, when the reply has a fenced block labelled as a shell (not a fence in another language, or unlabelled) — a reply with no shell fence handed over no commands, so it stays silent instead of making you watch Claude answer a check you never asked about. The checklist: how you get there (the folder as an absolute path, plus opening a terminal or PowerShell in it), shell named (and correct as the fence label), exact command, what you will see, `UNTESTED:` above the fence if it was not actually run, and one numbered step per action once there is more than one command — all of it in the step-card format. Separately, if the reply claims success (fixed, works, tested, …) with no tool run since your last real message and no quoted evidence, it gets a reminder to run the check and quote it, or say the claim is untested. If the turn changed files or committed and the reply opens with code, a table or a paragraph of file and function names instead of a plain summary — or has a table too wide for a phone — it is told to lead with a short plain-English summary of what's done, what it changes for you and what's waiting on you. If the turn was a port, rewrite, restructure or migration and the reply never says what was kept and what was dropped, it is told to report that against the original — naming every dropped feature, with an issue for each one to add back later. If the turn changed something visual (CSS, HTML, a component, a Unity scene) and never captured or looked at a screenshot, it is told to screenshot the same flow before and after. The same goes for a claim that something can't be done or doesn't exist. And a reply that says something was "not checked" or "untested" without saying why the check couldn't run is told to run it: checking is the default. Separately again, if a file this turn wrote or edited is still uncommitted according to `git status`, it tells Claude to commit it scoped to those paths — on its own `claude/…` branch, or after branching off if the checkout is on yours (`HOUSE_RULES_COMMIT_CHECK=off` turns just this part off). A transcript it cannot read never asserts anything either way; it just says so. The retry goes through, so it cannot loop. **You are never prompted;** set `HOUSE_RULES_HANDOVER=off` to disable it. While the issue gate is still closed it adds one line (never blocks). Issue #110. |
| `PostToolUse` on `Write` / `Edit` | after a file is written | the `artifact` handler notices documents written outside a project — plan files, scratchpad notes — and tells Claude to copy them into the repo. **You are never prompted;** the nudge goes to Claude. |
| `PostToolUse` on `Write` / `Edit` | after a file is written | the `branchnudge` handler checks which branch the checkout is on. On a branch that is not `AjsAgent/…` (or `claude/…`), when the file just written is the **only** uncommitted change, it tells Claude to branch off now (`git switch -c AjsAgent/<topic>` carries the change along) unless that branch was opened for this session's work. It stays quiet on a `claude/…` branch and once other changes exist, which the `Stop` check covers instead. **You are never prompted.** `HOUSE_RULES_COMMIT_CHECK=off` disables it, the `Stop` commit check and the `audit` line below. |
| `PostToolUse` on `Write` | after a file is created | the `runnable` handler notices runnable files (`.py .js .ts .sh .ps1 .bat .cmd`, `Dockerfile`, `docker-compose.yml`) created inside the project and tells Claude to run them before finishing — the teeth behind "deliver a whole workflow, not a starting point." A compiled-language file (`.cs`) gets a different reminder: compile it with the real toolchain (Unity batch mode, or `dotnet build`/`msbuild` against the project's own `.csproj`) instead of a hand-rolled stand-in for the engine's APIs, which only proves the stand-in compiles. `Write` only, never `Edit`. **You are never prompted;** the nudge goes to Claude. |
| `PostToolUse` on `Write` / `Edit` | after a file is written | the `harvest` handler finds comment blocks that have grown into essays and reminds Claude to move them into the tier-4 system doc that owns that code, leaving a one-line pointer - and traces what it measured on every source write, whether or not it fires. Only ever looks at text written this turn — to sweep a whole project by hand, run `/house-rules:harvest-scan [path]` in any Claude Code session, which shares the same detection code via `scripts/harvest_scan.py`. The pointer that move leaves is `doc-ref <id> <path>`; `/house-rules:docref` (`scripts/docref.py`) checks that each one still resolves and repairs the ones whose doc has moved. |
| `PostToolUse` on `ExitPlanMode` | the moment a plan is approved | the `delegate` handler tells Claude the deliberation is over and the implementation should go to a subagent, `@house-rules:builder` for implementation (pinned to Sonnet). This is the model split on surfaces where the `opusplan` setting below does not reach. **You are never prompted;** the nudge goes to Claude. Also counts the plan's steps (numbered lines, `- [ ]` items, `### Step`/`### Change` headings); more than 3 writes `house-rules-issues.json` (`needs_issues: true`) into the git directory and appends the issue-workflow note (parent issue, one child per step, labels, `in progress`); 3 or fewer writes nothing and says so in one line naming the count. Issue #110. |
| `PreToolUse` on `Agent` / `Task` | before a subagent is spawned | the `agentcap` handler denies the spawn when two are already running (the list is kept by `announce` and `verdict` in a file in the common git directory; a record older than 45 minutes is ignored) or when the call comes from inside a subagent. A corrupt state file is reported in one line and the spawn is allowed. `HOUSE_RULES_AGENTS=off` disables it. Issue #112. |
| `PermissionRequest` | a permission dialog is shown | the `prompttimer` handler waits `HOUSE_RULES_PROMPT_TIMEOUT` seconds (default 300; `off` disables). If nobody has answered it refuses - never approves - telling Claude to route around it without the same effect, and records the action in the waiting-on-you list in the common git directory. Issue #144. Every read-change-write of the list goes through `_waiting_update`, under a lock file `waiting-on-you.json.lock` (`O_CREAT|O_EXCL`, retried up to 3 s; a lock older than 15 s is stale and removed, said on stderr; if it cannot be taken it says so and updates unlocked). From #145 the list is shared with `scope` (reports and clears it) and `issuelist` (shows earlier sessions'); the `guard` and `guardwrite` prompts also say the timeout and that unanswered means refused. |
| `PostToolUse` + `PostToolUseFailure` | a Bash, PowerShell, write, web or MCP call has run | the `promptran` handler marks a waiting prompt's action as run, so `prompttimer` stops without a decision; an action already recorded as timed out that ran anyway is removed from the waiting-on-you list and reported. Issue #149. |
| `PostToolUse` on `Agent` / `Task` | a **foreground** subagent call returns | the `audit` handler hands `verdict`'s same audit summary straight to Claude itself, not just to you — a `SubagentStop` handler's own additionalContext and systemMessage don't reach the model in the same turn, but this channel does. Silent for a backgrounded call, which returns before its work exists; `userpromptaudit` below covers that. **You are never prompted;** the nudge goes to Claude. |
| `UserPromptSubmit` | a turn that is a **backgrounded** subagent's completion notice | the `userpromptaudit` handler covers the case `audit` can't: a `run_in_background` call's real completion arrives later as an ordinary-looking new prompt. It recognizes that shape and sends Claude the same audit summary. Every other prompt is untouched. **You are never prompted;** the nudge goes to Claude. |
| `SubagentStart` | every time a subagent is spawned | the `announce` handler says which agent is starting, what it is **declared** to run on (model and effort, read out of the agent file that actually shipped), the plugin version, and a short fingerprint of the agent definition — so you can see it was the agent and model you meant, under the digest you expect, instead of taking all three on trust. Warns if a `CLAUDE_CODE_SUBAGENT_MODEL*` variable is set, since that overrides the declaration. A separate `subagentrules` handler re-injects the house rules **into the subagent itself** (a SessionStart hook never reaches a spawned subagent — only `SubagentStart` does) and tells you the transcript's expected path. **You are never prompted.** Set `HOUSE_RULES_DELEGATION=off` to disable this and the verdict below. |
| `SubagentStop` | every time a subagent finishes | the `subagentcommit` handler checks whether the subagent left any file it wrote uncommitted — in whichever repo or worktree that file lives. If so, it sends the subagent back **once** to commit those files (scoped to them, on its own branch; branching off first if it is on yours) before it can finish. If the task told it not to run git, it lists the files in its report instead. The second time round it never holds the subagent again, only reports. **You are never prompted** (though the subagent's own `git commit` still goes through `guard` like any other). `HOUSE_RULES_COMMIT_CHECK=off` disables it. |
| `PreToolUse` on `Write` / `Edit` / `NotebookEdit` | before an edit, on a subagent's own `worktree-agent-` branch | the `commitgate` handler blocks the edit once 3 files are uncommitted and tells the subagent to commit first. If it tries again without committing, the hook commits for it. Your own branches are never touched. Also the issue gate, on any branch of the main session: while `house-rules-issues.json` says `needs_issues`, denies Write/Edit/NotebookEdit on source files, naming the two missing pieces (parent issue, child issues); `docs/`, `.claude/`, any `.md`, files outside the project and the state file stay open. A corrupt state file is reported in one line and treated as no gate. A subagent worktree has its own git directory, so the gate does not reach it. `HOUSE_RULES_ISSUES=off` disables it. Issue #110. |
| `PostToolUse` on `Write` / `Edit` / `NotebookEdit` / `Bash` | after each step, on a subagent's own `worktree-agent-` branch | the `autosave` handler saves the subagent's work to a hidden save point (`refs/house-rules/autosave/<branch>`) and pushes it to GitHub once a minute, so a subagent that is killed mid-run loses nothing. After 10 minutes without a commit it commits for the subagent. The same entry also records `gh issue create` calls for the issue gate on any branch: it parses the issue URL from the tool output and whether the command carried the `Claude created this` label, and clears the gate after two labelled issues; an unlabelled creation gets a correction note and does not count. Only the `Bash` tool is watched, not `PowerShell`. Issue #110. |
| `UserPromptSubmit` | every time Claude wakes up in the main session | the `worktreesweep` handler commits any subagent's work that has sat uncommitted for 10+ minutes, which catches a subagent that was killed and can no longer commit for itself. |
| `SubagentStop` | every time a subagent finishes | the `verdict` handler reports the model that **actually** served it, read from the subagent's own transcript, and whether that matches what the agent declares, plus the transcript path it found. A delegation that quietly ran on the planning model now says so. It also prints an audit summary built from the transcript — commands with exit status, files written or edited, tool-use counts — so you can check the subagent's own report against what it actually did. If it cannot find or read the transcript it tells you which paths it tried rather than going quiet. Set `HOUSE_RULES_SUBAGENT_LEDGER=on` to also render the full transcript into `docs/sessions/` (off by default). **You are never prompted.** |

### Why a shim in front of `hook.py`

[scripts/run.sh](plugins/house-rules/scripts/run.sh) is the one POSIX-sh file left in the
plugin. Its only job is finding a Python interpreter that actually runs code, by **probing**
each candidate (running it and checking the output) rather than trusting `command -v` — on the
machine this was built on, `python3` is the Windows Store App Execution Alias stub: on PATH,
found by `command -v`, but it prints an install nag to stdout and exits 0 instead of running
anything. See the comments at the top of `run.sh` for the full resolution order and what each
hook event does when no interpreter probes successfully.

### And one subagent — the mechanism the model split actually runs on

Three tier agents replace the old executor: [scout](plugins/house-rules/agents/scout.md) (haiku;
Read, Grep, Glob; lookups), [builder](plugins/house-rules/agents/builder.md) (sonnet; one issue's
chunk of work) and [reviewer](plugins/house-rules/agents/reviewer.md) (opus; adversarial check of a
finished diff). Each has a short tool allowlist so a spawn starts small, and none has `Agent`. The
`agentcap` hook (PreToolUse on `Agent`) denies a third running subagent and any spawn made by a
subagent; `HOUSE_RULES_AGENTS=off` disables it. the `delegate` handler (above) is what asks for that delegation.

**This, not the `opusplan` setting below, is what makes "Opus plans, Sonnet executes" actually
happen.** Agent frontmatter ships with the plugin, so it works on every surface. The setting
covers the CLI and the IDE only, and only at the plan-mode boundary:

- In the desktop app's **Code** tab the model comes from the picker next to the send button.
  That is a session-level selection, and it outranks the `model` field in any settings file —
  the desktop docs map both `--model` and `ANTHROPIC_MODEL` to that dropdown. `opusplan` is an
  alias rather than a model, so it is not offered there either.
- Cloud sessions (Code tab or web) run on Anthropic-managed VMs, which never receive a settings
  file deployed to your device — and your device is the only place `install.py` can write.
- Auto and accept-edits sessions never enter plan mode, so the one boundary `opusplan` switches
  at is never crossed. That one applies in the CLI too.

The subagent was in this repo before any of that was understood, and nothing ever invoked it.
the `delegate` handler and the delegation rule in `house-rules.md` are what ask for it now. If you would
rather force the split by hand in a Code-tab session, pick Sonnet in the dropdown once the plan
is approved — but you should not have to, and that is the point.

The guard **never blocks a matched command outright**. Every match becomes an "ask", because
the rules are "do not do X without asking" — not "X is forbidden". Nothing else here can block
at all: both `PostToolUse` reminders go to Claude, and you never see them.

Every hook is **stateless**. Nothing is written to disk between invocations, nothing carries
over between turns, and there is nothing to clean up. An earlier version enforced the
deliver-a-whole-workflow rule with three scripts and a `Stop` hook that kept session state in
your temp directory; it leaked a file for every session that ended unexpectedly, and any
unrelated shell command silently defeated it. The reminder was the whole value, so the state
is gone.

## No runtime dependency, and it cannot fail silently

`run.sh` needs POSIX `sh`. `hook.py` needs a working Python 3 interpreter and nothing else -
no third-party packages, stdlib only. That is a deliberate constraint, not an accident. An
earlier version parsed the hook payload as JSON with node, and a missing node meant the guard
exited without a decision and every command sailed through unchecked - a safety net that
disappears exactly when you have not noticed it is gone. Matching stays textual even in Python,
for the same reason: the rule patterns match the raw payload text just as well, which costs
nothing but a slightly wider net. `run.sh`'s own job is not letting the interpreter search
itself become a silent-failure point - see 'Why a shim in front of hook.py' above.

What is left cannot fail quietly either:

- **`guard` fails closed.** If the payload is unreadable or an internal error occurs, it
  writes the reason to stderr and exits 2 — a blocking error. The command does not run. There is
  no path through the handler that silently lets a command past. `run.sh` extends this: no
  working interpreter at all is also a blocking failure for `guard`.
- **`inject` fails loud.** If the rules file is missing or unreadable, it still prints a
  `systemMessage`, so you see "The rules were NOT loaded into this session" in the session
  instead of the rules just not being there.

- **`scope` cannot fail at all.** On `UserPromptSubmit` a non-zero exit *erases your prompt*, so
  that handler is one fixed string — it reads no file and runs no subprocess, so it has no
  failure path to hit. Its text is therefore a second copy of some wording, which the suite
  guards against drifting.
- **`artifact` and `runnable` never obstruct.** `PostToolUse` cannot block anyway (the write
  already happened), and neither tries to be a gate. Any internal error gets you a
  `systemMessage` saying the reminder is offline, not a broken write.
- **`guard` falls back rather than failing either way** when it cannot find the `command` field
  in a payload — a tool whose input field is named something else is matched against the whole
  payload, exactly as the guard behaved before it extracted anything. It is never waved through,
  and never blocked wholesale.

Every one of these properties is tested by the suite below.

### What trips the guard

| Rule | Patterns |
|---|---|
| Never hide work: it stays visible, reachable and readable | `-WindowStyle Hidden`, `Start-Process`, `Start-Job`, `-AsJob`, `nohup`, `setsid`, `disown`, a trailing `&`, a wait or loop (`while`, `until`, `sleep`, `timeout`, `watch`) piped through `tail`/`head`, which hides its output until it exits |
| Commit constantly on my own branches, never on theirs | `git push` and `git commit` (force push always prompts; a plain push or commit stands down on an `AjsAgent/` (or `claude/`) branch); `reset`, `revert`, `rebase` (prompt unless on a `claude/` branch with a clean tree and every commit on a remote, #153); `clean`, `merge`, `filter-branch`, `cherry-pick`, `am`, `apply` (prompt on every branch, mine included — they can discard what exists nowhere else, or finish something the user started) |
| Never take a destructive action without checking first | `rm` (any form, not just `-r`/`-f` — a plain `rm file` deletes just as permanently), `Remove-Item`, `del /f`, `rmdir /s`, `Stop-Process`, `taskkill`, `pkill`, `kill -9`, `Clear-Content`, `truncate -s`, `git checkout --`/`git restore` (discards uncommitted edits; unasked on a `claude/` branch with a clean tree and every commit pushed, #153), `git stash drop`/`clear` (deletes stashed work permanently) |

`git status`, `git log`, `git diff`, `git show` and every ordinary command pass through
silently — read-only inspection is explicitly fine under the rules. So do the navigational git
verbs (`add`, a bare `checkout`/`switch` to change branches, `branch`, `tag`, `remote`,
`submodule`, a bare `stash`): none of them write history, the index, or the remote, so prompting
on them was pure noise and they were deliberately dropped from the pattern set.

The other rules — match response depth to the task, the fixed environment, build only what was
asked, docs-before-research, build for a human working alone, the user's hands are for decisions
not labour, once the approach is decided, delegate the execution, never name a local path in an
issue or a pull request — have no shell signature to match on. They are carried by the SessionStart injection and the per-prompt reminder.

Four are exceptions, because a rule carried only by injected text is a rule that gets read and
then drifted past:

- **"Deliver a whole workflow"** — its runnable-file half has a real check, at `PostToolUse`:
  a script created and never run gets a reminder, and a compiled-language file (`.cs`) gets a
  reminder to compile it with the real toolchain instead of a hand-rolled stand-in for the
  engine's APIs — "a shim that compiles is not proof the real code does."
- **"Never hand over a command I have not run"** — enforced at `Stop`, which is the only event
  that happens after the reply exists and before the turn ends. A `Stop` hook *can* see the
  reply, via `last_assistant_message`, and the handler uses it to decide whether to fire at all —
  but only coarsely: a fenced block means a command was handed over. It still cannot judge
  whether that command was actually run, or whether the folder is right, so it does not try. What
  it does is put the checklist in front of Claude at the moment the turn would otherwise go out,
  and only on the turns where a command is in play. That is the one command-shaped rule the `guard` handler
  cannot cover, because it only ever sees commands Claude *runs*, never ones it *types into a
  reply*.
- **"Once the approach is decided, delegate the execution"** — enforced at `PostToolUse` on
  `ExitPlanMode`: the moment a plan is approved, the `delegate` handler names `@house-rules:builder`
  before Claude gets a chance to just start implementing on the planning model.
- **"Edit in place; a full rewrite is a delete, not an edit"** — enforced at `PreToolUse` on
  `Write`, not on `guard`'s Bash/PowerShell matcher, because the mechanism this rule is actually
  about is the `Write` tool overwriting a file wholesale, not a shell command. The `guardwrite`
  handler asks every time a `Write` targets a path that already exists.

## Coding standards, per repo

Three ecosystem docs ship vendored in [rules/standards/](plugins/house-rules/rules/standards) —
`coding-philosophy.md` (always), `csharp-unity-standards.md`, `web-js-ts-node-standards.md`.
They're vendored copies, not a git submodule: `claude plugin install` does not recurse
submodules, so the directory would be empty on every fresh machine and every cloud session.
`Ajw2003/Coding-Standards` stays where they're authored; `tools/sync_standards.py` pulls it and
copies changes into the plugin, printing which files changed and which were already identical.

The `standards` hook picks which of the ecosystem docs apply, per project: it detects Unity
project markers (`ProjectSettings/ProjectVersion.txt`, an `Assets/` directory, any `*.csproj`)
and Node markers (`package.json`, `tsconfig.json`, `deno.json`) across the repo root and one
level of subdirectories, so a mixed repo (Unity under `Game/`, Node at the root) gets both. It
also catches opening a Unity project at its `Assets/` folder rather than the project root one
level up — a normal workflow — by checking one level *up* for `ProjectSettings/`/`*.csproj` when
the root's own directory name is exactly `Assets`. When that's the case, it re-scans from the
real project root instead of `Assets/`, so a sibling Node service next to `Assets/` (not just the
Unity markers) still gets found. If detection gets a project wrong, or its
needs differ, drop a `.claude/standards` file in the repo
— one document name per line (`coding-philosophy`, `csharp-unity-standards`,
`web-js-ts-node-standards`), blank lines and `#` comments ignored — and it overrides detection
entirely.

## The machine profile

Rule one is "build for this machine, not for everywhere" — which is worthless if nobody wrote
down what this machine is. `rules/environment.md`, next to the plugin's other rules, is that
record: OS, shells, hardware, what is on PATH and what only looks like it is. It is injected
alongside the rules at every session start, but it is **machine-local and gitignored** — it
never ships with the plugin, so a fresh install has none.

When it's missing, the `inject` handler falls back to live runtime detection instead of a
hardcoded default or a bare "go find out": OS, Python, and whether `git`, `sh`, `bash`, `pwsh`,
`powershell`, `node` and `npm` are on PATH, checked for real on the machine the session is
running on. That's enough to work from immediately; write a hand-verified
`rules/environment.md` when you also need things detection can't know — RAM, GPU, line-ending
config. [docs/example-environment.md](../docs/example-environment.md) is a worked example, kept
for the traps it already caught.

It records one trap in particular, because it has already produced a bad instruction: **`sh`
and `bash` are not on PATH** on the machine that example was recorded from. Git for Windows only
adds `C:\Program Files\Git\cmd`, which holds `git.exe` and nothing else. The shells exist, but
must be called by full path.

## Verify it yourself

Do not take any of the above on faith. Run it yourself, from the **repo root**, in PowerShell
or Git Bash — it's plain Python, no full-path/short-form split to remember:

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Every check is numbered and prints what it tested, what it expected, what it got, and PASS or
FAIL — so a failure tells you what broke without opening the script. The count is printed at
the end rather than written down here, because a number in a README drifts the moment a case
is added.

The guard checks feed one real command each and assert the decision, including the ones that
must *not* prompt: `git status`, `git checkout -b`, `git branch -d`, and a harmless command
whose *description* mentions committing. Others run the hooks with a deliberately broken `PATH`
to prove the fail-closed and fail-loud behaviour, and confirm a payload with no `command` field
still gets checked rather than waved through. The reminder checks cover the two cases that
would misfire — a file whose *contents* merely mention a temp path, and a script written to a
temp directory rather than the project. The drift checks catch reminder text that no longer
matches the rules, a `CLAUDE.md` turned back into a second copy of them, an architecture table
that no longer matches `hooks.json`, and any return of the deliverable state machine. The last
few confirm the machine profile reaches the session, and that a missing one reads as "go and
find out" rather than "assume".

Exit code 0 means all passed. It runs in your terminal, in the foreground, in about a second —
nothing is hidden and nothing is logged to a file only Claude reads.

## Testing that the hooks are actually live

`verify.py` proves the handlers are correct. It cannot prove Claude Code **loaded** them —
hooks are read at startup, so a stale install passes every file-level check while the running
session uses the old copy. That has already happened once here: the plugin sat three commits
behind for a whole session, injecting four rules while the repo on disk had eleven.

`python tools/clean_install_test.py` at the repo root automates the install half. The rest has to be
observed in a live session, after fully quitting and restarting Claude Code:

| Hook | How to see it | What proves it |
|---|---|---|
| `SessionStart` | Ask: *what are my house rules, and what machine am I on?* | It answers both **without opening a file** — names the rules, and says the CPU/OS/shell either from a hand-verified `rules/environment.md` or from live runtime detection if none exists. If it goes looking for files, nothing was injected. |
| `UserPromptSubmit` | Run `claude --debug`, then send any prompt | The hook runs and injects the line starting `Standing house rules` |
| `PostToolUse` | Ask it to write a `.md` file into a temp directory | A reminder about artifact custody comes back **to Claude**; you are not prompted |
| `PreToolUse` | See the constraint below | A permission prompt naming *Commit constantly on my own branches, never on theirs* |
| `Stop` | Ask for something that ends in a command to run, and let the turn end | The turn is extended exactly once with the command-handover checklist, then ends normally on the retry. Ask a question whose answer contains **no** fenced block and it stays silent - that is the firing condition, not a bug. Restart with `HOUSE_RULES_HANDOVER=off` set and it never fires. |
| `PostToolUse` on `ExitPlanMode` | Approve any plan out of plan mode | A delegation nudge naming `@house-rules:builder` comes back **to Claude**; you are not prompted |

### The guard test needs an uncommitted change, and a branch that isn't mine

`git add` isn't gated at all — it's a navigational verb, not one that writes history, so it
was deliberately dropped from the pattern set (see "What trips the guard" above). `git commit`
is, but only on a branch I did not create: the commit rule stands down on an `AjsAgent/`- or `claude/`-prefixed
branch by design, so testing this on one of my own branches will show no prompt and prove
nothing. Run this on `main` (or any branch you named). Make a change first, so there is
something to commit — a clean worktree does not work as a test, because Claude has nothing to
commit and so never attempts the command:

```bash
echo scratch > guard-test.txt
git add guard-test.txt
```

Then ask Claude to commit it. The prompt should appear, naming the rule and quoting the
command. Deny it, and clean up:

```bash
del guard-test.txt
```

On a clean tree the command stages nothing whether it was intercepted or not, so the result
looks identical either way and the test tells you nothing. Give it something real to stage and
the outcome is unambiguous.

## What it costs

`verify.py` proves the hooks are correct. It says nothing about what they cost, and a rule that
fires correctly on every prompt can still be expensive. From the repo root:

```bash
python tools/measure_footprint.py
```

It measures the copy in the plugin cache — the one Claude Code actually runs — not this repo,
because a bumped version that never re-registered leaves those two disagreeing. It reports the
per-prompt reminder in both its short and long forms, replays your real transcripts through the
live gating regex to show how often each one fires, prints the per-session injection size, and
asserts that the three malformed-payload cases still exit 0. That last part matters more than it
looks: `scope` runs on `UserPromptSubmit`, where a non-zero exit erases your prompt before Claude
sees it.

Exit code 0 means the gating is live and the failure paths are safe. Pass `--repo` to measure
uncommitted changes before installing them. [docs/measuring-footprint.md](../docs/measuring-footprint.md)
explains what each section means and how to read the numbers honestly.

## Install on a new device

One command, from the repo root:

```bash
.\tools\bootstrap.ps1
```
```bash
sh tools/bootstrap.sh
```

`bootstrap.ps1`/`bootstrap.sh` probe for a working Python interpreter (the same probe `run.sh`
uses) and hand off to `tools/install.py`, which installs the plugin and applies the settings
the plugin cannot apply to itself (see below). Idempotent, and it **upgrades** an existing
install as well as creating a new one.

If you would rather do it by hand, it is four commands, and on a machine that already has the
plugin the second one is the one that matters:

```bash
claude plugin marketplace add https://github.com/Ajw2003/AjsClaudeCodeTools.git
```
```bash
claude plugin marketplace update aj-house-rules
```
```bash
claude plugin install house-rules@aj-house-rules
```
```bash
claude plugin update house-rules@aj-house-rules
```

**Why four and not two.** `marketplace add` answers `already on disk` for a marketplace this
device has seen before and does not re-fetch it, so the cached clone stays on the old commit;
`plugin install` is a no-op once the plugin is registered. Run only those two on a machine that
already has house-rules and it stays on its old version, while `plugin update` reports
`already at the latest version` and names that old version — a confident wrong answer.
`marketplace update` re-fetches the clone and `plugin update` re-points the registration at it.
On a fresh machine the two extra commands are harmless no-ops.

Or run `/plugin` in an interactive `claude` terminal and pick it from the menu. Restart to
load it.

### Updating by double-click (Windows)

`tools\update.bat` runs exactly those four commands and nothing else — **double-click it**.

It deliberately needs no Python and no clone of this repo: copy it to your Desktop and it still
works. It prints what it is doing at each step, stops with a readable message if a command
fails, shows you the installed version at the end, and reminds you to fully quit Claude Code —
hooks and agents are read at startup, so an update is not live in a window that is already open.

It does not apply the `verbose` / `opusplan` settings below; `bootstrap.ps1` is still the full
install. `.ps1` files are not double-click-runnable by default on Windows, which is why this one
is a `.bat`.

### Settings the plugin cannot ship

A plugin can ship hooks, rules, scripts and agents. It cannot set anything the **harness**
reads, because those live in `~/.claude/settings.json` and are read at startup — no amount of
rule text in `house-rules.md` can change how the transcript is rendered or which model runs,
since rules steer Claude and these are the harness.

So `tools/install.py` (invoked via `bootstrap.ps1`/`bootstrap.sh`) writes them, preserving every other key in the file:

| Key | Value | Why |
|---|---|---|
| `verbose` | `true` | Default to the verbose transcript view — full tool calls and outputs, not the collapsed summary. Matches the rule that nothing is hidden and nothing goes to a log only an agent reads. |
| `model` | `opusplan` | Opus while planning, switching automatically to Sonnet to execute. Deliberation belongs in the plan; once the approach is decided, execution wants the faster model, not more reasoning. **Read by the CLI and the IDE only** — see [And one subagent](#and-one-subagent) for why it does nothing in the desktop Code tab or a cloud session, and what covers those instead. |

Run it with `-NoVerbose` to leave the transcript view alone, or `-NoModel` to leave the model
alone on a device you deliberately run on something else.

**A hook cannot do this.** No hook output sets a model — a `SessionStart` hook may be *told*
which model is running, and there is no `$CLAUDE_MODEL` — so the split is agent frontmatter plus
a setting, never script logic. Do not try to add it to the `guard` handler. What a hook *can*
do is ask for the delegation, which is all the `delegate` handler does: it emits text, and the model change comes
from the agent it names.

The marketplace manifest lives at the **repo root** (`.claude-plugin/marketplace.json`), which
is where `marketplace add` looks — keep it there. Its plugin entries use paths relative to the
repo root, so this plugin is `./claude-house-rules/plugins/house-rules`. Any future tool in
this repo becomes another entry in the same list.

<details>
<summary>Declarative form, for a machine you want configured with no commands</summary>

Add these two keys to `~/.claude/settings.json` and Claude Code clones the repo and installs
the plugin at next startup, with no commands run.

This is the **same configuration the CLI produces**, not a competing method — verified by
watching it happen: `claude plugin marketplace add` writes `extraKnownMarketplaces`, and
`claude plugin install` writes `enabledPlugins`, both into this same file. So the choice is
only about ergonomics: run two commands, or ship a settings file to a machine before it has
ever started. Doing one after the other is harmless — the second finds the keys already
there.

(An earlier version of this README said not to combine the two. That was wrong.)

```json
{
  "extraKnownMarketplaces": {
    "aj-house-rules": {
      "source": { "source": "git", "url": "https://github.com/Ajw2003/AjsClaudeCodeTools.git" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "house-rules@aj-house-rules": true },
  "verbose": true,
  "model": "opusplan"
}
```

`model` here is subject to the same limits as above: the CLI and IDE read it, the desktop Code
tab and cloud sessions do not.

`verbose` and `model` are not part of the plugin install — they are the two settings
`install.py` also writes, included here so a shipped settings file configures the machine
completely.
</details>

Editing the rules is then one commit — every device picks it up on its next update.

For a local checkout instead, swap the source for
`{ "source": "directory", "path": "C:\\path\\to\\AjsClaudeCodeTools" }` — the **repo root**, since that is
where `marketplace.json` lives. (It previously named `...\\claude-house-rules`, which stopped
being right when the manifest moved to the root.)

## On Windows

Every hook command is `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>` — `sh` still, even
after the Python port. "Environment-agnostic" means every OS **given a POSIX shell**, not every
OS unconditionally: `run.sh` is what resolves a working Python interpreter for `hook.py`, and
`hooks.json` has to reach `run.sh` itself first, through `sh`.

On Windows that `sh` comes from Git Bash. On a Windows machine with no Git Bash at all, Claude
Code falls back to PowerShell and the `sh` invocation fails outright — visibly, as a hook error
on every command, not silently. That has not changed and is not fixed by this port: it is the
same risk the plugin has always carried on Windows, stated plainly rather than glossed over.
Install Git for Windows and it works, on every OS including this one.

## Editing the rules

[plugins/house-rules/rules/house-rules.md](plugins/house-rules/rules/house-rules.md) is the
single source of truth for the text Claude reads. It is the **only** copy — `CLAUDE.md` files are
pointers to it, not duplicates. Claude Code auto-loads every `CLAUDE.md` it finds, so a full copy
there means the rules land in context twice and the two can drift apart unnoticed. The suite
fails if one reappears.

[plugins/house-rules/scripts/hook.py](plugins/house-rules/scripts/hook.py)'s `scope` handler
restates a few phrases from the rules inline (it cannot read a file — see above). If you reword
one of those rules, the suite tells you the reminder no longer matches. The same file's `guard`
handler holds the patterns the guard matches. If you add a rule to the markdown that has a
shell signature, add a check next to it and a case in `verify.py`.

## Known limitation

Matching is textual and runs against the extracted `command` field (or the whole payload, on
the fallback tier when no `command` field is found — see "What trips the guard" above), so a
command that merely mentions a tripwire word — `echo "git commit"` — prompts too. An extra
keypress is cheaper than a missed commit.
