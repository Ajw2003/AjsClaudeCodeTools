# house-rules

Your global CLAUDE.md rules, turned into a Claude Code plugin so they follow you to every
device and every project instead of living in a file you have to copy into each repo.

## What it actually does

Four hooks, all defined in [plugins/house-rules/hooks/hooks.json](plugins/house-rules/hooks/hooks.json):

| Hook | When | What it does |
|---|---|---|
| `SessionStart` | every session, every project | [inject.sh](plugins/house-rules/scripts/inject.sh) prints [rules/house-rules.md](plugins/house-rules/rules/house-rules.md) into Claude's context. This is the CLAUDE.md replacement — no per-repo file needed. |
| `UserPromptSubmit` | before every prompt you send | [scope.sh](plugins/house-rules/scripts/scope.sh) restates the short version — the environment is fixed, the request is the scope, deliver something runnable, artifacts go in the project. The SessionStart copy fades over a long session; this is what keeps it true at message 200. |
| `PreToolUse` on `Bash` / `PowerShell` | before any shell command runs | [guard.sh](plugins/house-rules/scripts/guard.sh) checks the pending command. If it trips a rule, Claude Code shows you a permission prompt naming the rule and quoting the command. |
| `PostToolUse` on `Write` / `Edit` | after a file is written | [artifact.sh](plugins/house-rules/scripts/artifact.sh) notices documents written outside a project — plan files, scratchpad notes — and tells Claude to copy them into the repo. **You are never prompted;** the nudge goes to Claude. |

The guard **never blocks a matched command outright**. Every match becomes an "ask", because
the rules are "do not do X without asking" — not "X is forbidden".

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
  has no failure path to hit. Its text is therefore a second copy of some wording, which step 31
  guards against drifting.
- **artifact.sh never obstructs.** `PostToolUse` cannot block anyway (the write already happened),
  and it does not try to be a gate. Missing `grep` gets you a `systemMessage` saying the reminder
  is offline, not a broken write.

These properties are tested — steps 21, 23, 25 and 31 below.

### What trips the guard

| Rule | Patterns |
|---|---|
| Never hide work in a background window or a silent process | `-WindowStyle Hidden`, `Start-Process`, `Start-Job`, `-AsJob`, `nohup`, `setsid`, `disown`, a trailing `&` |
| Never commit without asking | `git` + `add commit push checkout switch reset revert stash rm mv branch merge rebase clean tag cherry-pick am apply remote submodule filter-branch` |
| Never take a destructive action without checking first | `rm -r/-f`, `Remove-Item`, `del /f`, `rmdir /s`, `Stop-Process`, `taskkill`, `pkill`, `kill -9`, `Clear-Content`, `truncate -s` |

`git status`, `git log`, `git diff`, `git show` and every ordinary command pass through
silently — read-only inspection is explicitly fine under the rules.

The other rules — the fixed environment, build only what was asked, docs-before-research, build
for a human working alone, the user's hands are for decisions not labour, deliver a whole
workflow — have no shell signature to match on. They are carried by the SessionStart injection
and the per-prompt reminder.

## Verify it yourself

Do not take any of the above on faith. Run this and read the output:

```bash
sh plugins/house-rules/scripts/verify.sh
```

32 numbered checks. Steps 1–20 feed one real command each to the guard and print the command
tested, the decision expected, the decision received, and PASS or FAIL. Steps 21–23 prove the
fail-closed and fail-loud behaviour by running the hooks with a deliberately broken `PATH`.
Steps 24–30 check the scope and artifact reminders, including the two cases that would misfire:
a file whose *contents* merely mention a temp path, and a script (not a document) in a temp
directory. Steps 31–32 catch drift — reminder text that no longer matches the rules, and a
`CLAUDE.md` turned back into a second copy of them.

Exit code 0 means all passed. It runs in your terminal, in the foreground, in about a second —
nothing is hidden and nothing is logged to a file only Claude reads.

## Install on a new device

Two commands, no config editing:

```bash
claude plugin marketplace add Ajw2003/AjsClaudeCodeTools
```
```bash
claude plugin install house-rules@aj-house-rules
```

Or run `/plugin` in an interactive `claude` terminal and pick it from the menu. Restart to
load it.

The marketplace manifest lives at the **repo root** (`.claude-plugin/marketplace.json`), which
is where `marketplace add` looks — keep it there. Its plugin entries use paths relative to the
repo root, so this plugin is `./claude-house-rules/plugins/house-rules`. Any future tool in
this repo becomes another entry in the same list.

<details>
<summary>Declarative alternative, for a machine you want configured with no commands</summary>

Add these two keys to `~/.claude/settings.json` instead. Claude Code clones the repo and
installs the plugin at next startup. Do not combine this with `marketplace add` — both
register the same marketplace name.

```json
{
  "extraKnownMarketplaces": {
    "aj-house-rules": {
      "source": { "source": "github", "repo": "Ajw2003/AjsClaudeCodeTools" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "house-rules@aj-house-rules": true }
}
```
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
there means the rules land in context twice and the two can drift apart unnoticed. Step 32 fails
if one reappears.

[plugins/house-rules/scripts/scope.sh](plugins/house-rules/scripts/scope.sh) restates a few
phrases from the rules inline (it cannot read a file — see above). If you reword one of those
rules, step 31 tells you the reminder no longer matches.
[plugins/house-rules/scripts/guard.sh](plugins/house-rules/scripts/guard.sh) holds the patterns
the guard matches. If you add a rule to the markdown that has a shell signature, add a check
next to it and a case in `verify.sh`.

## Known limitation

Matching is textual and runs against the whole hook payload, so a command that merely mentions
a tripwire word — `echo "git commit"` — prompts too. An extra keypress is cheaper than a missed
commit.
