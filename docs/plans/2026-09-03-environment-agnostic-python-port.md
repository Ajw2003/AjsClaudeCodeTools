# Handoff: environment-agnostic `house-rules` — Python port

## Context

`C:\Users\aj\Desktop\EnvAgnosticHooksPlan\2.0Plan.md` proposes porting the `house-rules`
plugin's seven `sh` hooks and three PowerShell device tools to Python, so the plugin behaves
identically in the CLI, the desktop Code tab, and cloud sessions on any OS. I validated that
plan against the live repo. **The architecture is sound and should be built** — the `run.sh`
shim owning interpreter resolution and per-event fallback is the right answer to the "missing
node silently disabled the guard" history the repo is shaped around.

Five findings change the work. One of them is fatal to the plan as written.

This document is the corrected, executable version. The implementation agent should follow
**this** file, and commit it (not `2.0Plan.md`) to `docs/plans/`.

---

## Validation findings

### F1 — FATAL: `command -v python3` picks a stub that exits 0 and prints garbage

Measured on aj's box, in Git Bash, this session:

```
python3 -> /c/Users/aj/AppData/Local/Microsoft/WindowsApps/python3
$ python3 -c "print('hello')"
Python was not found; run without arguments to install from the Microsoft Store, ...
exit=0
```

`python3` is the Microsoft Store **App Execution Alias stub**. It is on PATH, `command -v`
finds it, it writes its refusal to **stdout**, and it **exits 0**.

Under the plan's resolution order (`python3`, then `python`, then `py -3`), `run.sh` would
`exec` that stub for every hook. Claude Code would see exit 0 and non-JSON on stdout — no
decision — and **every guarded command would run unchecked**. That is the exact node failure
the plan exists to prevent, reproduced on the author's own machine on day one. Note that
`C:\Python313\python.exe` *is* installed and healthy; only the `python3` name is poisoned.

**Required change:** `run.sh` must not trust `command -v`. It must **probe** each candidate by
executing it and checking stdout, not exit status:

```sh
probe() { [ "$("$@" -c 'print(9)' 2>/dev/null)" = 9 ]; }
```

The stub prints its message instead of `9` and is rejected. First candidate that probes wins.
Order becomes: `$HOUSE_RULES_PYTHON` (if set, probed too), `python3`, `python`, `py -3`.

`py -3` is two words: keep the interpreter in `"$@"`/`set --` form, never in a single variable
that gets word-split by `exec $PY`.

**Cost:** one extra interpreter start per hook invocation. Measure it in step 2 (see
Verification); if `PreToolUse` latency is unacceptable, the escape hatch is
`HOUSE_RULES_PYTHON` set by `tools/install.py` in the user's environment — **not** a cache
file, which would break the no-hook-keeps-state invariant.

### F2 — The plan contradicts itself on `rules/environment.md`

It keeps the committed Windows profile *and* adds a verify check that the SessionStart
injection must not contain the literal `Windows 11`. The committed profile supplies that
string on every run. **Decided:** the profile becomes user-local and untracked (see Step 4).

### F3 — Ordering step 2 is not green

`verify.sh:632` does `ls "$HERE"/*.sh | grep -v '^verify\.sh$'` and fails if any `.sh` is not
registered in `hooks.json`. Adding `run.sh` alongside the existing scripts breaks `verify.sh`
the moment it lands. Step 2 must also widen that exclusion to `grep -vE '^(verify|run)\.sh$'`
— a one-line edit to `verify.sh`, which keeps the "both suites green" property the plan claims.

### F4 — Counts and references in `2.0Plan.md` are wrong; do not copy them forward

- "31 existing guard cases" — the table at `verify.sh:94-121` holds **28** cases. The other
  three guard-related checks (fail-closed, field-extraction, whole-payload fallback) are
  separate and the plan lists them separately, so 31 double-counts. Port **28 + 3**.
- "verify check 68" — `verify.sh` computes `STEP` at runtime and hardcodes no numbers. Citing
  a check number violates the plan's own rule. Refer to checks by title.
- The plan is right that `CLAUDE.md`'s "step 31" / "step 32" references are stale (the scope
  drift check is now step 41, the CLAUDE.md-duplication check step 42). The stale `# --- 31.`
  / `# --- 32.` comments inside `verify.sh` are stale for the same reason — the port should
  drop numeric comment prefixes entirely.

### F5 — CRLF is an unaddressed release risk

`core.autocrlf = true` with no `.gitattributes` in the repo. A fresh clone (which
`clean_install_test.py` performs) can check `run.sh` out with CRLF, which breaks it under
`sh`. This risk exists today; the port is the moment to close it. **Add `.gitattributes`:**

```
*.sh text eol=lf
*.py text eol=lf
```

### Confirmed-correct claims (build on these as written)

- 14 guard patterns across three buckets: R1×5, R3×2, R4×7. Verified by reading `guard.sh`.
- `verify.sh` asserts `"hookEventName":"PostToolUse"` and `"permissionDecision":"ask"` with
  **no space after the colon** → `json.dumps(obj, separators=(",", ":"))` is required.
- `'[^&]&[[:space:]]*\\?"'` really does match JSON syntax, not shell syntax — it needs the
  closing JSON quote. Python: `r'[^&]&\s*\\?"'`. Keeping the raw-text subject is correct.
- `[[:alnum:]]` → `[0-9A-Za-z]`, never `\w` (patterns list `_` separately, e.g.
  `[^[:alnum:]_.-]`).
- `clean-install-test.ps1` really does hardcode `Run the 34-check suite` (line 265) and
  `all 34 checks passed` (line 273); its expected-file list (lines 239-242) really does omit
  `handover.sh`, `runnable.sh`, `delegate.sh` and `agents/executor.md`; its hooks-wired loop
  (line 257) really does check only four events, missing `Stop`.
- `install.ps1` writes `Name = 'model'` / `opusplan` and both docs carry the "CLI and the IDE"
  scoping string. All three are pinned by verify and must survive the port.

### F6 — `house-rules.md` states the delegation rule twice

`## Once the approach is decided, delegate the execution` (line 156) and `## Once the plan is
settled, delegate execution` (line 221) are the same rule written twice, with the second
wedged between *Never commit without asking* and *Never take a destructive action* for no
reason. Pre-existing, and in scope for this change — the port injects this file into every
session, so a duplicated rule is duplicated context on every run, and two copies drift.

**Merge into one section**, keeping the line-156 heading and body, and folding in the one
paragraph that exists only in the second copy — the Agent-tool proactive-use gate (lines
231-236: spawning a subagent unprompted requires either an explicit user ask or a
`proactively` marking in the target agent's own description, which is why
`agents/executor.md` is written that way). Delete the line-221 section entirely.

Two drift checks constrain the merge and must still pass:
- the delegate drift check greps `house-rules.md` for `@house-rules:executor` **and**
  `plan is settled` (case-insensitive). The surviving body already says *"when a plan is
  settled — approved out of plan mode"* at line 161, so the phrase lives on. Confirm it, do
  not assume it.
- the executor-description check greps `agents/executor.md` for `proactiv`. Untouched by this
  merge, but the paragraph being folded in is the *reason* that check exists — keep them
  consistent.

Add a new check: `house-rules.md` contains exactly one `^## ` heading matching
`delegat`, so the duplication cannot come back.

---

## Decisions taken (these override `2.0Plan.md`)

1. **Bootstrap:** keep two thin bootstrap scripts, `tools/bootstrap.ps1` and
   `tools/bootstrap.sh`, ~20 lines each. Their only job: probe for a working Python (same
   probe as `run.sh`), offer the one install command for the detected OS if none is found,
   then `exec` `tools/install.py`. **All real logic stays in Python.** This mirrors `run.sh` —
   one dependency, resolved in the one place that cannot itself need it. Without this there is
   no working install path on a bare machine, and `python tools/install.py` is a manual
   prerequisite step, which the house rules forbid.
2. **`rules/environment.md` becomes user-local.** Delete the committed Windows profile, add
   `claude-house-rules/plugins/house-rules/rules/environment.md` to `.gitignore`, keep the
   `HOUSE_RULES_ENV_FILE` override (verify uses it). Runtime detection is the only source of
   truth in a fresh clone; a machine may still record local overrides. The "injection contains
   live-detected markers and not the literal `Windows 11`" check then means something.
   Preserve the file's *content* by moving it to `docs/example-environment.md` so the recorded
   `sh`-not-on-PATH trap is not lost — it is referenced from `CLAUDE.md`.

---

## Files to change

| File | Change |
|---|---|
| `claude-house-rules/plugins/house-rules/scripts/run.sh` | **new** — shim, probe-based resolution (F1) |
| `.../scripts/hook.py` | **new** — all seven handlers, stdlib only, single file |
| `.../scripts/verify.py` | **new** — port of `verify.sh` |
| `.../commands/doctor.md` | **new** — `/house-rules:doctor` |
| `.../hooks/hooks.json` | 7 commands → `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>` |
| `.../scripts/{inject,scope,guard,handover,artifact,runnable,delegate,verify}.sh` | **deleted** |
| `.../rules/house-rules.md` | §1 rewrite; §8 fence-label wording de-Windows'd; pinned phrases; **the two delegation sections merged into one (F6)** |
| `.../rules/environment.md` | **deleted + gitignored**; content moved to `docs/example-environment.md` |
| `.../.claude-plugin/plugin.json` | version → `1.3.0` |
| `tools/bootstrap.ps1`, `tools/bootstrap.sh` | **new** — Python bootstrap (decision 1) |
| `tools/install.py`, `tools/clean_install_test.py`, `tools/force_update.py` | **new** |
| `tools/*.ps1` (the three existing) | **deleted** |
| `.gitattributes` | **new** — `*.sh`/`*.py` `eol=lf` (F5) |
| `claude-house-rules/README.md` | hook table → events; doctrine §; `## On Windows`; `## Known limitation` |
| `CLAUDE.md` | hook table → events; design constraints; stale step-31/32 refs |
| `docs/plans/2026-09-03-environment-agnostic-python-port.md` | **new** — this file |

---

## Step-by-step

Each step ends green unless marked otherwise. Do not start the next until the current one is.

### Step 1 — Prep
Commit this document to `docs/plans/2026-09-03-environment-agnostic-python-port.md`. Add
`.gitattributes` (F5). Verify green.

### Step 2 — `run.sh` + `hook.py` alongside the existing scripts, not yet wired
- Write `run.sh` with the **probe** resolver (F1), `set --` arg handling for `py -3`, and the
  three fallback shapes: `pre_tool_use` → 3 stderr lines + `exit 2`; `session_start` →
  `{"systemMessage":"house-rules plugin: no working Python interpreter found on PATH. The
  rules were NOT loaded into this session. Run /house-rules:doctor."}` + exit 0; everything
  else → nothing, exit 0.
- Write `hook.py`: `main(argv)`, `EVENTS` dict, per-event `except BaseException` branches
  exactly as tabulated in `2.0Plan.md` (that table is correct). `json.dumps(...,
  separators=(",", ":"))`. `sys.stdin.buffer.read().decode("utf-8","replace")`.
- Port the 14 guard patterns **character-for-character**, the three-tier ladder, the three
  bucket titles and every reason string verbatim. Subject stays raw text.
- Port the four hardcoded NOTE/REMINDER strings verbatim from `artifact.sh`, `runnable.sh`,
  `handover.sh`, `delegate.sh` (read them from the current files; they are pinned by drift
  checks). `handover.sh`'s `HOUSE_RULES_HANDOVER` toggle and `stop_hook_active` guard move
  across unchanged.
- Edit `verify.sh:632` → `grep -vE '^(verify|run)\.sh$'` (F3).
- Write `verify.py` covering the new files only: the 28 guard cases + 3 guard checks run
  against `hook.py`, and the four missing-interpreter checks.
- **Empirically confirm in this step, before proceeding:**
  (a) the probe rejects the WindowsApps stub and selects `C:\Python313\python.exe`;
  (b) `dirname "$0"` under Claude Code's real `${CLAUDE_PLUGIN_ROOT}` yields a path native
      Python can open — print it once from `run.sh` under `--debug` and look. If it is an MSYS
      `/c/...` path, convert with `cygpath -w` before handing it to Python;
  (c) time `PreToolUse` end-to-end with the probe in place.
- Both suites green.

### Step 3 — The switch (one commit; the only red window)
Rewire `hooks.json` to `run.sh <event>`, delete the eight `.sh`, promote `verify.py` to the
full suite, rewrite both hook tables to name **events not filenames**, rewrite both doctrine
sections. Widen the checks that hardcode `.sh`: the ExitPlanMode-wiring check, the
dead-state-machine check (`ls *.sh`, `STOP_SCRIPTS` awk), the delegate drift check, and the
docs↔`hooks.json` check whose pattern is `grep -o 'scripts/[a-z0-9-]*\.sh'`. Land only with
`verify.py` fully green.

### Step 4 — Rules and runtime profile
§1 rewrite (`The machine is fixed — find out what it is, then build for that` →
`Find out what machine you are on, then build for that`; update the injection-heading
assertion in lockstep). Runtime detection in `session_start`. Reword the scope reminder off
`Windows 11, Git Bash, PowerShell 5.1` and drop the unconditional `*'Windows 11'*` assertion
in the scope check. Delete + gitignore `rules/environment.md`, move its content to
`docs/example-environment.md`, keep `HOUSE_RULES_ENV_FILE`.

Also in this step: merge the two delegation sections per F6 — keep the line-156 heading and
body, fold in the proactive-gate paragraph from the line-221 section, delete the line-221
section, confirm `plan is settled` and `@house-rules:executor` still appear in the file, and
add the "exactly one delegation heading" check to `verify.py`. Green.

### Step 5 — Preflight + `commands/doctor.md`
Preflight block on `session_start` (Python ≥3.8, `git`, `sh` on Windows). `/house-rules:doctor`
maps gaps to `winget install Python.Python.3.12` / `brew install python` /
`apt install python3` / `dnf install python3`, one command per gap, confirmed by the normal
Bash permission prompt. Green.

### Step 6 — `tools/` port
Three `.py` in, three `.ps1` out, plus `bootstrap.ps1`/`bootstrap.sh` (decision 1). Fix
`clean_install_test.py`'s expected-file list and its four-event loop, and delete the `34`
literals (F4). Rewrite the README install section. Green.

### Step 7 — Ship
`plugin.json` → `1.3.0`, README `## On Windows` rewritten to state Risk 2 plainly
(environment-agnostic means every OS **given a POSIX shell**; a Windows box with no Git Bash
still cannot launch a hook, unchanged from today). Correct `## Known limitation` to say *the
extracted field*, not *the whole payload* — stale since the field-extraction change. Push to
`claude/plugin-environment-agnostic-14zsms`.

---

## Verification

Run from `C:\Users\aj\Desktop\ClaudeDev\AjsClaudeCodeTools\.claude\worktrees\env-agnostic-hooks-handoff-09a37b`.

`UNTESTED:` — these are the commands the port creates; none exist yet.

Primary suite, Git Bash:

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Expect a numbered PASS line per check and `RESULT: PASS - all N checks passed`, exit 0.

The single most important assertion in the whole change — fail-closed with no interpreter,
Git Bash:

```bash
printf '{"tool_input":{"command":"ls"}}' | env PATH=/nonexistent sh claude-house-rules/plugins/house-rules/scripts/run.sh pre_tool_use; echo "exit=$?"
```

Expect `exit=2` and the three-line reason on stderr, no stdout.

The F1 regression — the stub must not be selected, Git Bash:

```bash
printf '{"tool_input":{"command":"git commit -m wip"}}' | sh claude-house-rules/plugins/house-rules/scripts/run.sh pre_tool_use
```

Expect JSON containing `"permissionDecision":"ask"` and `Never commit without asking`. If it
prints `Python was not found; run without arguments to install from the Microsoft Store`, the
probe is not working and the guard is dead — stop and fix before anything else.

End to end on this device, PowerShell 5.1, from the repo root:

```powershell
.\tools\bootstrap.ps1
```

Expect it to report the interpreter it selected, then run `install.py` to completion.

Then restart Claude Code and confirm by hand: ask *"what are my house rules and what machine
am I on"* (the profile must name the **actual** machine, not a committed one), run
`git status` (no prompt), run `git commit -m wip` (prompt naming *Never commit without
asking*), approve a plan out of plan mode (delegation nudge), and run `/house-rules:doctor`
with `HOUSE_RULES_PYTHON` pointed at a nonexistent path.
