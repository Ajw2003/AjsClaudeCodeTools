# Fix the Opus→Sonnet split on the Desktop Code tab

## Context

The plugin claims a working "Opus plans, Sonnet executes" split. It rests on two things
(`CLAUDE.md` § *One subagent, for the model split*):

1. `"model": "opusplan"` written into `~/.claude/settings.json` by `tools/install.ps1`; and
2. `agents/executor.md`, pinned to `model: sonnet`.

In the Claude desktop app's **Code** tab, neither fires. Three separate reasons, all confirmed
against the docs:

- **The dropdown outranks the file.** Desktop sets a per-session model from the picker next to
  the send button. The desktop docs' CLI-equivalence table maps both `--model sonnet` and
  `ANTHROPIC_MODEL` to that dropdown — i.e. it is a session-level override, and model
  resolution puts session/startup selection *above* the `model` field in a settings file. So
  `~/.claude/settings.json` `model` is never consulted in a Code-tab session.
- **`opusplan` is not in the dropdown.** It is an alias reachable via `/model`, `--model`,
  `ANTHROPIC_MODEL`, or a settings file. The picker lists concrete models. There is no way to
  select the hybrid in the Code tab at all.
- **Cloud sessions never see the file.** Code-tab sessions that run on Anthropic-managed VMs
  (and web/mobile) don't receive device-deployed settings; only server-managed settings reach
  them. `install.ps1` writes to `$env:USERPROFILE\.claude`, which does not exist there.

And the auto-mode half: `opusplan` only switches **at the plan-mode boundary**. Auto and Accept
edits never enter plan mode, so even in the CLI those sessions stay on Opus start to finish.
That is the exact gap `executor.md` was written to cover — but nothing in the plugin ever tells
Claude to delegate to it, so it is dead weight in practice.

Outcome wanted: execution runs on Sonnet on every surface, including the Desktop Code tab, and
the repo stops asserting a mechanism that only works in the CLI.

## Approach

Stop relying on a setting the desktop app doesn't read. Route execution through the subagent —
which *is* surface-independent, since agent frontmatter is honoured wherever the plugin is
installed — and make the plugin actually ask for that delegation.

### 1. New hook: `delegate.sh` on `PostToolUse` / `ExitPlanMode`

New script `claude-house-rules/plugins/house-rules/scripts/delegate.sh`, registered in
`hooks/hooks.json` as a third `PostToolUse` entry with `"matcher": "ExitPlanMode"`.

It emits `additionalContext` telling Claude that the plan is settled and the implementation
should be delegated to `@house-rules:executor`, unless the work is a one-liner where the
delegation costs more than it saves.

Follow the existing conventions exactly:

- Model it on `runnable.sh` — the closest sibling (PostToolUse, reminder aimed at Claude, never
  at the user, always `exit 0`).
- **Hardcoded string, no file read** (same reasoning as `scope.sh`/`runnable.sh`), so drift is
  caught by a `verify.sh` phrase check rather than by a runtime read.
- No dependency beyond `sh`; no JSON parsing. This hook needs no field from the payload at all
  — the matcher already selects the event — so it is a single `printf`, with **no `grep`
  dependency** and therefore no offline path.
- Stateless. Nothing under `$TEMP`.

### 2. Rules text (per your call, models go in the rules)

Add a short rule to
`claude-house-rules/plugins/house-rules/rules/house-rules.md`: once the approach is decided,
delegate implementation to `@house-rules:executor` rather than implementing on the planning
model — and note that this is the workflow in Auto and Accept-edits sessions too, which never
cross a plan-mode boundary.

Leave **`scope.sh` untouched.** Its verify check runs scope→rules (every phrase in `scope.sh`
must still appear in `house-rules.md`), so adding text to the rules file cannot break it, and
`scope.sh`'s zero-dependency guarantee is worth more than restating this one rule.

### 3. Docs corrections — the claims that are currently false

- **`CLAUDE.md`** § *One subagent, for the model split*: rewrite. `opusplan` covers the CLI and
  IDE only; on the Desktop Code tab the dropdown wins and the alias isn't offered; cloud
  sessions never read the local file. The subagent is not the "case opusplan misses" — it is
  the primary mechanism, and `opusplan` is the CLI convenience on top.
- **`CLAUDE.md`** hook table: add the `delegate.sh` row (`verify.sh` fails if the table and
  `hooks.json` disagree).
- **`claude-house-rules/README.md`**: same correction in the "And one subagent" section and the
  settings table; state plainly that the Desktop Code tab needs Sonnet picked in the dropdown
  (or the delegation) because the setting does not reach it.
- **`tools/install.ps1`**: keep writing `opusplan` (it is still correct for the CLI), but
  correct the `.DESCRIPTION` text — it currently says the settings file is "the only place it
  can be set", which is what led to this bug — and print a line at the end saying the model
  setting does not apply to Desktop Code-tab or cloud sessions, where the split comes from the
  executor agent.

### 4. `verify.sh` cases

Per the repo rule that a rule with a shell signature ships with its test:

- `delegate.sh` fed a real `ExitPlanMode` `PostToolUse` payload returns JSON naming
  `@house-rules:executor`, and exits 0.
- `delegate.sh` is registered on `PostToolUse` with matcher `ExitPlanMode` in `hooks.json`
  (and, via the existing table check, appears in `CLAUDE.md`).
- Drift: the phrase `@house-rules:executor` appears in both `delegate.sh` and
  `house-rules.md`.
- The `Stop`-hook check stays as is — `delegate.sh` is on `PostToolUse`, so nothing there loosens.
- Existing executor/`opusplan` checks stay; the README grep still passes since `opusplan` remains
  documented.

Do not write a check count anywhere — `verify.sh` computes its own.

## Files

| File | Change |
|---|---|
| `claude-house-rules/plugins/house-rules/scripts/delegate.sh` | new |
| `claude-house-rules/plugins/house-rules/hooks/hooks.json` | register it |
| `claude-house-rules/plugins/house-rules/rules/house-rules.md` | delegation rule |
| `claude-house-rules/plugins/house-rules/scripts/verify.sh` | new cases |
| `CLAUDE.md`, `claude-house-rules/README.md`, `tools/install.ps1` | corrections |

## Verification

Run the suite from the repo root:

```bash
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Expect exit 0 with the new cases printed as PASS. I will run this here (Linux, `sh` on PATH)
and paste the real output. Note the CLAUDE.md command is the Windows one
(`& "C:\Program Files\Git\bin\sh.exe" ...`) — that is the form to hand back to you for your
own machine, marked `UNTESTED:` since I cannot run PowerShell 5.1 in this container.

End-to-end, on your machine: reinstall with `.\tools\install.ps1`, open a Code-tab session,
plan something, exit plan mode, and confirm the delegation nudge appears and the implementation
runs as `@house-rules:executor` on Sonnet.

Commit to `claude/desktop-code-model-switching-kxuqwm` and push.
