# house-rules

Your global CLAUDE.md rules, turned into a Claude Code plugin so they follow you to every
device and every project instead of living in a file you have to copy into each repo.

## What it actually does

Five hooks on four events, all defined in [plugins/house-rules/hooks/hooks.json](plugins/house-rules/hooks/hooks.json):

| Hook | When | What it does |
|---|---|---|
| `SessionStart` | every session, every project | [inject.sh](plugins/house-rules/scripts/inject.sh) prints [rules/house-rules.md](plugins/house-rules/rules/house-rules.md) **and** [rules/environment.md](plugins/house-rules/rules/environment.md) into Claude's context. This is the CLAUDE.md replacement — no per-repo file needed. |
| `UserPromptSubmit` | before every prompt you send | [scope.sh](plugins/house-rules/scripts/scope.sh) restates the short version — match depth to the task, the environment is fixed, the request is the scope, deliver something runnable, artifacts go in the project. The SessionStart copy fades over a long session; this is what keeps it true at message 200. |
| `PreToolUse` on `Bash` / `PowerShell` | before any shell command runs | [guard.sh](plugins/house-rules/scripts/guard.sh) checks the pending command. If it trips a rule, Claude Code shows you a permission prompt naming the rule and quoting the command. |
| `PostToolUse` on `Write` / `Edit` | after a file is written | [artifact.sh](plugins/house-rules/scripts/artifact.sh) notices documents written outside a project — plan files, scratchpad notes — and tells Claude to copy them into the repo. **You are never prompted;** the nudge goes to Claude. |
| `PostToolUse` on `Write` | after a file is created | [runnable.sh](plugins/house-rules/scripts/runnable.sh) notices runnable files (`.py .js .ts .sh .ps1 .bat .cmd`, `Dockerfile`, `docker-compose.yml`) created inside the project and tells Claude to run them before finishing — the teeth behind "deliver a whole workflow, not a starting point." `Write` only, never `Edit`. **You are never prompted;** the nudge goes to Claude. |

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

The hooks need `sh`, `grep`, `sed` and `awk`. **No node, no jq, no python.** Nothing that can
be absent on a fresh machine and quietly take the rules offline with it.

That is a deliberate constraint, not an accident. An earlier version parsed the hook payload
as JSON with node, and a missing node meant the guard exited without a decision and every
command sailed through unchecked — a safety net that disappears exactly when you have not
noticed it is gone. The fix was to stop parsing: the rule patterns match the raw payload text
just as well, which costs nothing but a slightly wider net.

What is left cannot fail quietly either:

- **guard.sh fails closed.** If `grep` is unreachable or the payload is unreadable, it writes
  the reason to stderr and exits 2 — a blocking error. The command does not run. There is no
  path through the script that silently lets a command past.
- **inject.sh fails loud.** If the rules file or `sed`/`awk` is missing, it still prints a
  `systemMessage`, so you see "The rules were NOT loaded into this session" in the session
  instead of the rules just not being there.

- **scope.sh cannot fail at all.** On `UserPromptSubmit` a non-zero exit *erases your prompt*, so
  that hook is one `printf` of a fixed string — it reads no file and runs no other program, so it
  has no failure path to hit. Its text is therefore a second copy of some wording, which the
  suite guards against drifting.
- **artifact.sh and runnable.sh never obstruct.** `PostToolUse` cannot block anyway (the write
  already happened), and neither tries to be a gate. Missing `grep` gets you a `systemMessage`
  saying the reminder is offline, not a broken write.
- **guard.sh falls back rather than failing either way** when it cannot find the `command` field
  in a payload — a tool whose input field is named something else is matched against the whole
  payload, exactly as the guard behaved before it extracted anything. It is never waved through,
  and never blocked wholesale.

Every one of these properties is tested by the suite below.

### What trips the guard

| Rule | Patterns |
|---|---|
| Never hide work in a background window or a silent process | `-WindowStyle Hidden`, `Start-Process`, `Start-Job`, `-AsJob`, `nohup`, `setsid`, `disown`, a trailing `&` |
| Never commit without asking | `git` + `add commit push checkout switch reset revert stash rm mv branch merge rebase clean tag cherry-pick am apply remote submodule filter-branch` |
| Never take a destructive action without checking first | `rm -r/-f`, `Remove-Item`, `del /f`, `rmdir /s`, `Stop-Process`, `taskkill`, `pkill`, `kill -9`, `Clear-Content`, `truncate -s` |

`git status`, `git log`, `git diff`, `git show` and every ordinary command pass through
silently — read-only inspection is explicitly fine under the rules.

The other rules — match response depth to the task, the fixed environment, build only what was
asked, docs-before-research, build for a human working alone, the user's hands are for decisions
not labour, never hand over an untested command — have no shell signature to match on. They are
carried by the SessionStart injection and the per-prompt reminder. "Deliver a whole workflow" is
the exception: its runnable-file half now has a real check, at `Stop` — see the hooks table above.

## The machine profile

Rule one is "build for this machine, not for everywhere" — which is worthless if nobody wrote
down what this machine is. [rules/environment.md](plugins/house-rules/rules/environment.md) is
that record: OS, shells, hardware, what is on PATH and what only looks like it is. It is
injected alongside the rules at every session start.

If it is missing, the injection says **NOT RECORDED YET** and tells the session to go and
discover the facts rather than assume them. On a new machine that is the correct first move:
run the commands at the bottom of that file and rewrite it. The suite covers both paths.

It records one trap in particular, because it has already produced a bad instruction: **`sh`
and `bash` are not on PATH** on this machine. Git for Windows only adds `C:\Program Files\Git\cmd`,
which holds `git.exe` and nothing else. The shells exist, but must be called by full path.

## Verify it yourself

Do not take any of the above on faith. Run it yourself, from the **repo root**.

In PowerShell — where `sh` is not on PATH, so it needs its full path:

```bash
& "C:\Program Files\Git\bin\sh.exe" claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Or from a Git Bash window, where the short form works:

```bash
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
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

`verify.sh` proves the scripts are correct. It cannot prove Claude Code **loaded** them —
hooks are read at startup, so a stale install passes every file-level check while the running
session uses the old copy. That has already happened once here: the plugin sat three commits
behind for a whole session, injecting four rules while the repo on disk had eleven.

`tools/clean-install-test.ps1` at the repo root automates the install half. The rest has to be
observed in a live session, after fully quitting and restarting Claude Code:

| Hook | How to see it | What proves it |
|---|---|---|
| `SessionStart` | Ask: *what are my house rules, and what machine am I on?* | It answers both **without opening a file** — names the rules, and says the CPU/OS/shell from `environment.md`. If it goes looking for files, nothing was injected. |
| `UserPromptSubmit` | Run `claude --debug`, then send any prompt | The hook runs and injects the line starting `Standing house rules` |
| `PostToolUse` | Ask it to write a `.md` file into a temp directory | A reminder about artifact custody comes back **to Claude**; you are not prompted |
| `PreToolUse` | See the constraint below | A permission prompt naming *Never commit without asking* |
| `PostToolUse` + `Stop` | Ask it to write a throwaway `.sh` or `.py` script, then say "stop, don't run it" | Claude's turn gets blocked once, naming the unrun file, before it can end the turn |

### The guard test needs an uncommitted change — this is the part that catches people

Testing the guard with `git add -A` on a **clean worktree does not work as a test**. Make a
change first, so there is something to stage:

```bash
echo scratch > guard-test.txt
```

Then ask Claude to run `git add -A`. The prompt should appear, naming the rule and quoting the
command. Deny it, and clean up:

```bash
del guard-test.txt
```

On a clean tree the command stages nothing whether it was intercepted or not, so the result
looks identical either way and the test tells you nothing. Give it something real to stage and
the outcome is unambiguous.

## Install on a new device

One command, from the repo root, in PowerShell:

```bash
.\tools\install.ps1
```

It installs the plugin and applies the settings the plugin cannot apply to itself (see below).
It is idempotent — running it on a machine that already has the plugin changes nothing.

If you would rather do it by hand, the plugin half is two commands:

```bash
claude plugin marketplace add Ajw2003/AjsClaudeCodeTools
```
```bash
claude plugin install house-rules@aj-house-rules
```

Or run `/plugin` in an interactive `claude` terminal and pick it from the menu. Restart to
load it.

### Settings the plugin cannot ship

A plugin can ship hooks, rules and scripts. It cannot set anything the Claude Code **UI**
reads, because those live in `~/.claude/settings.json` and the harness reads them at startup —
no amount of rule text in `house-rules.md` can change how the transcript is rendered, since
rules steer Claude and this is the harness.

So `tools/install.ps1` writes them, preserving every other key in the file:

| Key | Value | Why |
|---|---|---|
| `verbose` | `true` | Default to the verbose transcript view — full tool calls and outputs, not the collapsed summary. Matches the rule that nothing is hidden and nothing goes to a log only an agent reads. |

Run it with `-NoVerbose` to install the plugin and leave the transcript view alone.

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
      "source": { "source": "github", "repo": "Ajw2003/AjsClaudeCodeTools" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "house-rules@aj-house-rules": true },
  "verbose": true
}
```

`verbose` is not part of the plugin install — it is the transcript-view setting `install.ps1`
also writes, included here so a shipped settings file configures the machine completely.
</details>

Editing the rules is then one commit — every device picks it up on its next update.

For a local checkout instead, swap the source for
`{ "source": "directory", "path": "C:\\path\\to\\AjsClaudeCodeTools" }` — the **repo root**, since that is
where `marketplace.json` lives. (It previously named `...\\claude-house-rules`, which stopped
being right when the manifest moved to the root.)

## On Windows

Hooks run through Git Bash when Git is installed, which is where `sh`, `grep`, `sed` and `awk`
come from. On a Windows machine with no Git Bash at all, Claude Code falls back to PowerShell
and the `sh` invocation fails — visibly, as a hook error on every command, not silently. Install
Git for Windows and it works.

## Editing the rules

[plugins/house-rules/rules/house-rules.md](plugins/house-rules/rules/house-rules.md) is the
single source of truth for the text Claude reads. It is the **only** copy — `CLAUDE.md` files are
pointers to it, not duplicates. Claude Code auto-loads every `CLAUDE.md` it finds, so a full copy
there means the rules land in context twice and the two can drift apart unnoticed. The suite
fails if one reappears.

[plugins/house-rules/scripts/scope.sh](plugins/house-rules/scripts/scope.sh) restates a few
phrases from the rules inline (it cannot read a file — see above). If you reword one of those
rules, the suite tells you the reminder no longer matches.
[plugins/house-rules/scripts/guard.sh](plugins/house-rules/scripts/guard.sh) holds the patterns
the guard matches. If you add a rule to the markdown that has a shell signature, add a check
next to it and a case in `verify.sh`.

## Known limitation

Matching is textual and runs against the whole hook payload, so a command that merely mentions
a tripwire word — `echo "git commit"` — prompts too. An extra keypress is cheaper than a missed
commit.
