# house-rules

Your global CLAUDE.md rules, turned into a Claude Code plugin so they follow you to every
device and every project instead of living in a file you have to copy into each repo.

## What it actually does

Two hooks, both defined in [plugins/house-rules/hooks/hooks.json](plugins/house-rules/hooks/hooks.json):

| Hook | When | What it does |
|---|---|---|
| `SessionStart` | every session, every project | Injects [rules/house-rules.md](plugins/house-rules/rules/house-rules.md) into Claude's context. This is the CLAUDE.md replacement — no per-repo file needed. |
| `PreToolUse` on `Bash` / `PowerShell` | before any shell command runs | If the command trips a rule, Claude Code shows you a permission prompt naming the rule and quoting the command. You approve or reject. |

The guard **never blocks outright**. Every match becomes an "ask", because the rules are
"do not do X without asking" — not "X is forbidden".

### What trips the guard

| Rule | Patterns |
|---|---|
| Never hide work in a background window or a silent process | `-WindowStyle Hidden`, `Start-Process`, `Start-Job`, `-AsJob`, `nohup`, `setsid`, `disown`, a trailing `&` |
| Never commit without asking | `git` + `add commit push checkout switch reset revert stash rm mv branch merge rebase clean tag cherry-pick am apply remote submodule filter-branch` |
| Never take a destructive action without checking first | `rm -r/-f`, `Remove-Item`, `del /f`, `rmdir /s`, `Stop-Process`, `taskkill`, `pkill`, `kill -9`, `Clear-Content`, `truncate -s` |

`git status`, `git log`, `git diff`, `git show` and every ordinary command pass through
silently — read-only inspection is explicitly fine under the rules.

"Build things the user can run, verify, and keep" has no shell signature to match on, so it
is enforced by the context injection only.

## Verify it yourself

Do not take the table above on faith. Run this and read the output:

```bash
node plugins/house-rules/scripts/verify.js
```

21 numbered checks, each printing the command tested, the decision expected, the decision
received, and PASS or FAIL. Exit code 0 means all passed. It runs in your terminal, in the
foreground, in about a second — nothing is hidden and nothing is logged to a file only
Claude reads.

## Install on a new device

**Option A — from a git remote (the point of the plugin).** Push this repo somewhere, then
add these two keys to `~/.claude/settings.json` on the new machine:

```json
{
  "extraKnownMarketplaces": {
    "aj-house-rules": {
      "source": { "source": "github", "repo": "YOUR-USER/claude-house-rules" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "house-rules@aj-house-rules": true }
}
```

Claude Code clones the marketplace and installs the plugin at next startup. Editing the
rules is then one commit — every device picks it up on its next update.

**Option B — from a local checkout.** Same two keys, with a directory source:

```json
{
  "extraKnownMarketplaces": {
    "aj-house-rules": {
      "source": { "source": "directory", "path": "C:\\Users\\aj\\Desktop\\ClaudeDev\\claude-house-rules" }
    }
  },
  "enabledPlugins": { "house-rules@aj-house-rules": true }
}
```

**Option C — interactively**, from a `claude` terminal:

```bash
claude plugin marketplace add ./claude-house-rules
```

## Requirements

Node on `PATH`. Claude Code's own installer usually provides it; if `node --version` works,
the hook works.

If Node is missing the hook fails open — the guard exits without a decision and the command
runs normally. That is deliberate: a broken guard must never wedge a session. It also means
the guard is a backstop under the rules in context, not the only thing holding them up.

## Editing the rules

[plugins/house-rules/rules/house-rules.md](plugins/house-rules/rules/house-rules.md) is the
single source of truth for the text Claude reads.
[plugins/house-rules/scripts/house-rules.js](plugins/house-rules/scripts/house-rules.js) holds
the `CHECKS` array for what the guard matches. If you add a rule to the markdown that has a
shell signature, add a check next to it and a case in `verify.js`.

## Known limitation

Matching is textual, so `echo "git commit"` prompts too. An extra keypress is cheaper than a
missed commit.
