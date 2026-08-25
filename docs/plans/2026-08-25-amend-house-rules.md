# Amend the house rules: scope discipline, human-first delivery, artifact custody

## Context

You gave six new observations about how I work and asked for two things: a comparison against
the existing rules implementation, and an amended rules document reflecting whatever the
comparison turns up.

The existing implementation is a Claude Code plugin (`house-rules@aj-house-rules`) that does two
things — injects `rules/house-rules.md` into every session at `SessionStart`, and puts a
permission prompt in front of shell commands that trip a rule at `PreToolUse`. It covers four
rules. Three of them have shell signatures the guard can match; one ("Build things the user can
run, verify, and keep") is text-only.

Your six new observations map onto that as follows:

| Your observation | Covered today? |
|---|---|
| Don't reason about environments I don't use (Linux, other PowerShell versions) | **No.** Nothing anywhere states what your machine actually is, so I speculate. |
| Only generate what was asked; ask when ambiguous | **No.** Not present in any form. |
| Build for a human working alone — independently runnable, readable, diagnosable | **Partly.** Rule 2 says "self-narrating, numbered steps, pass/fail" but frames it as *an artifact you own*, not as *a design constraint on everything I build*. |
| Your hands are for decisions, not labour (no manual file creation, name copying, value pasting) | **No.** Rule 2 says give literal instructions; it never says stop handing you work I could have done. |
| Deliver end-to-end, zero manual config, with real test steps | **Partly.** "Not 'run the spike and let me know'" is the seed of it; the standard isn't stated. |
| Docs first, then verify against the code; observed logic beats stale docs | **No.** Not present. |
| Artifacts belong in the project directory, not chat or temp | **Partly.** Rule 2 says "committed to the repo, not left in a temp directory" — buried in a bullet, and plan mode violates it by default (plan files go to `~/.claude/plans\`). |

So: two of seven partly covered, five absent. That justifies a rewrite of the rules document
rather than a patch, plus two new hooks so the new rules have teeth instead of being hopeful text.

## What I found in the existing implementation

Read directly, then cross-checked against the docs and the installed binary.

**The plugin works and its core design is sound.** Fail-closed guard (`exit 2` when `grep` is
missing), fail-loud injector (`systemMessage` when the rules can't be read), no node/jq/python
dependency, 23 self-narrating checks in `verify.sh`. None of that needs changing.

**Four byte-identical copies of the rules text exist**, all 3970 bytes, md5 `ed23f5fc`:

- `claude-house-rules/plugins/house-rules/rules/house-rules.md` (the source of truth)
- `CLAUDE.md` (repo root)
- `C:\Users\aj\Desktop\CLAUDE.md`
- `C:\Users\aj\.claude\CLAUDE.md`

The three `CLAUDE.md` files are auto-loaded by Claude Code, so in this repo the rules land in
context **four times per session** — roughly 16KB of duplicate text. The README states the plugin
"replaces copying a CLAUDE.md file into each repo"; that benefit is currently not realised
because the copies were never removed. Nothing keeps them in sync, so adding rules to one would
silently stale the other three.

### Documentation vs. observed reality

Checked the docs first, then verified against `C:\Users\aj\.local\bin\claude.exe`. Three
deviations, all resolved in favour of what the binary actually does:

1. **`permissionDecision` values.** The hooks docs page describes `"allow" | "deny" | "escalate"`.
   The binary validates against `allow, deny, ask, defer` and throws
   `Unknown hook permissionDecision type` on anything else — `escalate` is not among them.
   `guard.sh` emits `"ask"`, which is **correct**. No change; do not "fix" it to match the docs.
2. **Per-hook `if` field.** The docs describe narrower filtering via `"if": "Edit(*.ts)"`. The
   binary's hook-entry schema exposes only `matcher` and `hooks`. New hooks will use `matcher`
   plus in-script matching, not `if`.
3. **`UserPromptSubmit` + `additionalContext`** is real and supported — confirmed in the binary's
   schema. That is the mechanism the scope rule will use.

Also confirmed: `PostToolUse` cannot block (informational only), and `UserPromptSubmit` exit 2
*erases your prompt* — so the new hooks must never fail closed the way `guard.sh` does.

### Smaller findings

- README's local-checkout example still points a `directory` source at `...\AjsClaudeCodeTools\claude-house-rules`.
  Stale since `marketplace.json` moved to the repo root in `9726751`; it must now be the repo root.
- `Modified.md` is an empty **directory** (not a file) in the repo root — invisible to git, looks like debris.
- `New Text Document.txt` is 0 bytes and **staged but not committed**. Any `git commit` sweeps it in.
- The guard covers `Bash|PowerShell` only. The `Write`/`Edit` tools are unguarded.

## Decisions taken (your answers)

1. **Duplication** → pointer stubs. Plugin rules file is the only real copy.
2. **Scope hook** → `UserPromptSubmit` every prompt, plus the full rule at `SessionStart`.
3. **Artifacts** → `docs/` in-repo, with a `PostToolUse` hook that reminds *me* in-context. No prompts for you.
4. **Doc shape** → rewrite tighter. All eleven rules merged and compressed into one denser document.

## The plan

### 1. Rewrite the rules document

**File:** `claude-house-rules/plugins/house-rules/rules/house-rules.md`

Compressed rewrite. Every load-bearing clause from the current four rules is preserved in
substance — these specifically must survive the compression, since they are the parts that
actually change behaviour:

- read-only git (`status`, `log`, `diff`, `show`) is explicitly fine
- agreement is **per-action, not standing**; push always gets its own ask
- show the exact command, and for a commit the exact message, before running it
- `git status` check before anything destructive
- committed scratch output is now your work; removing it is your call
- long work runs in the foreground with live progress you can read
- artifacts are self-narrating: numbered steps, explicit pass/fail, printed result

New sections, in the same first-person voice:

- **The target environment is fixed.** States the machine plainly: Windows 11 Pro (10.0.26100),
  Git Bash for `sh`/`grep`/`sed`/`awk`, Windows PowerShell 5.1 for the PowerShell tool (no `&&`,
  no ternary, no `??`), Claude Code as a native binary, single device, no CI. Then the rule: build
  for exactly that. No portability work, no version-compatibility branches, no "and on Linux…"
  unless you ask. If I think another environment genuinely matters, I ask instead of building for it.
- **Only what was asked.** Ambiguity is a question, not a judgement call I make quietly.
- **Documentation first, then verify.** Search existing docs → verify against the code, file tree,
  or git history → where they disagree, say so, record it, and follow the observed behaviour. The
  three deviations above are the worked example of this rule.
- **Your hands are for decisions, not labour.** Intervention is for approving destructive actions,
  approving plans, clarifying intent, answering questions, adjusting direction. It is not for
  creating files by hand, copying filenames, pasting values, or running commands I could have run.
- **Delivery standard.** End-to-end runnable, zero manual config editing, with literal test steps —
  the exact command, what you'll see, what it means. "Just test it" is not a delivery. Includes a
  compressed version of your A-vs-B example as the illustration (B: two commands, no config editing).
- **Artifacts live in the project.** Plans, reports, notes go in `<project>/docs/` (plans in
  `docs/plans/`), tracked and committable. Never chat-only, never left in a temp directory.

Note: the environment block is baked into a plugin published on GitHub, so anyone else installing
it inherits your machine's assumptions. Acceptable for a personal plugin — flagging it, not solving it.

### 2. New hook — `scope.sh` on `UserPromptSubmit`

**File:** `claude-house-rules/plugins/house-rules/scripts/scope.sh` (new)

Emits `hookSpecificOutput.additionalContext` with a ~40-word standing reminder before every
prompt: the fixed environment, only-what-was-asked, ask-don't-assume, deliver-runnable,
artifacts-in-project.

Design constraints, driven by what the binary actually does:

- **It has no dependencies at all** — a single `printf` of a static string. No file read, no `sed`,
  no `awk`, no `grep`. There is nothing in it that can fail, which matters because on
  `UserPromptSubmit` a non-zero exit *erases your prompt*. It always exits 0.
- The reminder text is therefore hardcoded rather than read from the rules file. To stop that
  becoming a fifth copy that drifts, `verify.sh` gets a check asserting the reminder's key phrases
  still appear in `house-rules.md`. Drift fails a test instead of going unnoticed.

### 3. New hook — `artifact.sh` on `PostToolUse` for `Write|Edit`

**File:** `claude-house-rules/plugins/house-rules/scripts/artifact.sh` (new)

Extracts just the `"file_path":"…"` field with `grep -o` (not the whole payload — otherwise a file
whose *contents* mention `/tmp` would trigger). If that path is under a temp, scratchpad, or
`.claude\plans` location **and** looks like a document (`.md`/`.txt`), it returns
`additionalContext` reminding me to mirror the file into `<project>/docs/` before finishing.

`PostToolUse` cannot block and this deliberately does not try to. You see no prompt; the nudge
goes to me. If `grep` is missing it emits a `systemMessage` saying the reminder is offline and
exits 0 — loud, but never obstructive.

This is what makes plan mode comply: plan files are written to `~/.claude/plans\` by the harness,
and this hook is what reminds me to copy the finished plan into `docs/plans/`.

### 4. Wire both hooks

**File:** `claude-house-rules/plugins/house-rules/hooks/hooks.json`

Add a `UserPromptSubmit` entry (no matcher — the event takes none) and a `PostToolUse` entry with
matcher `Write|Edit`. Both invoked as `sh "${CLAUDE_PLUGIN_ROOT}/scripts/…"`, `timeout: 10`,
matching the existing two entries exactly.

### 5. Extend `verify.sh`

**File:** `claude-house-rules/plugins/house-rules/scripts/verify.sh`

The step counter auto-numbers, so nothing needs renumbering by hand. Existing 23 checks stay as
they are. New checks appended:

- `scope.sh` emits valid JSON containing the environment line and the only-what-was-asked line
- `scope.sh` under `PATH=""` **still** emits it — proving the zero-dependency claim rather than asserting it
- `artifact.sh` reminds on a `.md` write to a temp path
- `artifact.sh` stays silent on a write inside the project
- `artifact.sh` stays silent when only the file *contents* mention `/tmp` — the over-trigger case
- drift check: every key phrase hardcoded in `scope.sh` still appears in `house-rules.md`
- drift check: repo-root `CLAUDE.md` is still a pointer stub, not a re-pasted full copy
- update the existing step-22 heading list to the new rule headings

### 6. Replace the three duplicate `CLAUDE.md` files with pointer stubs

Overwrites, so I show you the exact stub text and get your go-ahead before writing:

- `CLAUDE.md` (repo root) — tracked, so recoverable from git
- `C:\Users\aj\Desktop\CLAUDE.md`
- `C:\Users\aj\.claude\CLAUDE.md`

The latter two are outside the repo, but their contents are byte-identical to git blob `90ff713`,
so nothing is genuinely unrecoverable. Each stub is a few lines: where the real rules live, that
the plugin injects them automatically, and not to paste the rules back in.

### 7. Update the README

**File:** `claude-house-rules/README.md`

- Add the two new hooks to the hooks table and describe what each does
- Fix the stale `directory` source path (repo root, not `claude-house-rules/`)
- Update the "23 numbered checks" count
- Note that `CLAUDE.md` is now a pointer, and why — so the next person doesn't re-duplicate it

### 8. Mirror this plan into the repo

Create `docs/plans/` and write this plan there, per the new artifact rule. Plan mode wrote it to
`~/.claude/plans\` first; that copy is not tracked and doesn't count.

### Flagged, not actioned

`Modified.md` (empty directory) and the staged 0-byte `New Text Document.txt` are debris. Removing
them is destructive and untracked, so I'm not touching either without you saying so.

## Files at a glance

| File | Change |
|---|---|
| `claude-house-rules/plugins/house-rules/rules/house-rules.md` | rewritten, tighter, 11 rules |
| `claude-house-rules/plugins/house-rules/scripts/scope.sh` | **new** — `UserPromptSubmit` |
| `claude-house-rules/plugins/house-rules/scripts/artifact.sh` | **new** — `PostToolUse` |
| `claude-house-rules/plugins/house-rules/hooks/hooks.json` | two new entries |
| `claude-house-rules/plugins/house-rules/scripts/verify.sh` | ~8 new checks |
| `claude-house-rules/README.md` | new hooks, stale path fix, count |
| `CLAUDE.md`, `~/Desktop/CLAUDE.md`, `~/.claude/CLAUDE.md` | replaced with pointer stubs |
| `docs/plans/` | new, holds this plan |
| `guard.sh`, `inject.sh`, `plugin.json`, `marketplace.json` | **unchanged** |

## How you verify it — without me

Three steps, in your own terminal, foreground, about a second each.

**Step 1 — run the test script.** From the repo root:

```bash
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Prints a numbered PASS/FAIL line per check (~31 of them) and a final `RESULT: PASS` or
`RESULT: FAIL`. Every command tested is printed next to its result, so a FAIL tells you which
rule broke and on what input. Exit code 0 means all passed.

**Step 2 — see the scope reminder fire on a real prompt.** Restart Claude Code so the plugin
reloads, then:

```bash
claude --debug
```

Type any prompt. The debug output shows the `UserPromptSubmit` hook running and the reminder text
it injected. If you see the environment line, it's live on every prompt from then on.

**Step 3 — confirm the duplication is gone.** This prints the size of each rules copy:

```bash
for f in ~/.claude/CLAUDE.md ~/Desktop/CLAUDE.md ./CLAUDE.md ./claude-house-rules/plugins/house-rules/rules/house-rules.md; do printf '%6s  %s\n' "$(wc -c <"$f")" "$f"; done
```

The first three should be a few hundred bytes each (pointer stubs). Only the last should be full
size. If any of the first three is back up around 4000, something re-duplicated the rules.

I'll run all three myself after implementing and paste the output, so you can compare your run
against mine rather than taking my word for either.

## What I'm not doing

- Not changing `guard.sh`'s `"ask"` decision — verified correct against the binary despite the docs
- Not adding a repo-root README (you didn't ask for one)
- Not touching `Modified.md` or `New Text Document.txt`
- Not committing anything. When the work is done I'll propose the message and wait.

---

## What changed after this plan was approved

Recorded 2026-08-25, after implementation. The plan above is the approved version; these are
the deviations from it, so the two can be read together without the plan quietly going stale.

**Two more rules were added,** at the user's request, after the first pass shipped:

1. **Rule 1 was rewritten.** It no longer just declares the environment. Windows 11 and
   PowerShell 5.1 are the *default assumption*; the real configuration is discovered and
   recorded in a new `rules/environment.md`, and the rule now says to check that file before
   relying on any environment fact — and to go and find out, then write it down, when a fact
   is not recorded.
2. **A new rule: "Never hand over a command I have not run where they will run it."** Prompted
   by a real failure in this session: `sh verify.sh` was given as an instruction after being
   tested only in the agent's Bash tool. It fails in PowerShell, which is the shell actually
   in use, because `sh` is not on PATH there.

**New file: `rules/environment.md`** — the discovered machine profile (OS, shells, hardware,
PATH contents, git config), injected alongside the rules at every session start. `inject.sh`
was rewritten to emit both files; when the profile is absent it emits a `NOT RECORDED YET`
instruction to discover it, so a new machine reads as "find out" rather than "assume". The
path is overridable via `HOUSE_RULES_ENV_FILE` purely so the test can exercise that branch
without moving the real file.

**verify.sh grew from 32 to 34 checks** — steps 33 and 34 cover the two paths above.

**The README's own verify command was wrong** and is now given per shell: the full
`sh.exe` path for PowerShell, the short form for Git Bash, both from the repo root. Verified by
running each in the shell it names.

Final state: 34/34 passing, confirmed from PowerShell at the repo root.
