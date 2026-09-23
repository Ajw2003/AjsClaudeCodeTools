# house-rules 2.31.0 — acceptance checklist

A hands-on pass/fail check of every feature 2.31.0 added, run on the real machine in a fresh
session. Each test states the exact prompt, the exact string that means PASS, and what FAIL
looks like. Part A is mechanical, with no model involved. Part B checks what the model actually
received, by asking it to quote strings it could not produce without the hook having fired.

**How each criterion was established.** Every PASS string below was observed on 2026-09-23 in a
Linux cloud session, running the merged plugin through `claude -p --plugin-dir` (model: haiku).
Each test also says whether it was pre-run. None of the PowerShell steps has been run on Windows,
so each one is marked `UNTESTED:`. Two tests (B8 and part of B7) could not be pre-run at all and
say so. A FAIL there is a finding about the plugin, not about your setup.

Record results in the table at the end.

---

## Part A — the installed copy, no model involved

**Update and self-test the installed plugin: 3 steps.** Do them in order; each step's output
tells you it worked.

---

### Step 1 of 3 — Re-fetch the marketplace

UNTESTED: run on Linux (bash) on 2026-09-23, not in PowerShell on your machine.

Open **Windows PowerShell** from the Start menu. It opens in your user folder, and this command
runs from anywhere.

```powershell
claude plugin marketplace update aj-house-rules
```

**You should see:** `√ Successfully updated marketplace: aj-house-rules`. PASS if that line
appears. FAIL on any error.

*Next: step 2 updates the installed plugin.*

---

### Step 2 of 3 — Update the installed plugin

UNTESTED: run on Linux (bash) on 2026-09-23, not in PowerShell on your machine.

In the same **Windows PowerShell** window:

```powershell
claude plugin update house-rules@aj-house-rules
```

**You should see:** `√ Plugin "house-rules" updated from 2.30.0 to 2.31.0 for scope user.`, or
a line saying it is already at 2.31.0. PASS if either names 2.31.0. FAIL if it names any other
version.

*Next: step 3 runs the plugin's own test suite against the copy you just installed.*

---

### Step 3 of 3 — Run the suite against the installed copy

UNTESTED: the same file was run on Linux (bash) on 2026-09-23, not in PowerShell on your machine.

In the same **Windows PowerShell** window:

```powershell
python "$HOME\.claude\plugins\cache\aj-house-rules\house-rules\2.31.0\scripts\verify.py"
```

**You should see:** a last result line of `RESULT: PASS - 327 of 337 checks passed, 10 skipped.`
The 10 skips are the checks that read repo-only files (`CLAUDE.md`, `docs/`, `tools/`), which the
installed copy does not ship. PASS: `RESULT: PASS` with 0 failures. FAIL: any line containing
`FAIL`, or `RESULT: FAIL`.

---

## Part B — live session in a scratch repo

**Set up a throwaway repo: 3 steps.** It stays on your machine and is never pushed.

---

### Step 1 of 3 — Create the folder and repo

UNTESTED: not run in PowerShell.

In **Windows PowerShell**:

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\hr-acceptance"; git -C "$HOME\hr-acceptance" init -b main
```

**You should see:** the new directory listed, then `Initialized empty Git repository in
…/hr-acceptance/.git/`.

*Next: step 2 makes a first commit so there is a `main` to come back to.*

---

### Step 2 of 3 — Make an empty first commit

UNTESTED: not run in PowerShell.

In the same **Windows PowerShell** window:

```powershell
git -C "$HOME\hr-acceptance" commit --allow-empty -m init
```

**You should see:** `[main (root-commit) <hash>] init`.

*Next: step 3 switches to a `claude/` branch, where commits don't prompt.*

---

### Step 3 of 3 — Switch to a claude/ branch

UNTESTED: not run in PowerShell.

In the same **Windows PowerShell** window:

```powershell
git -C "$HOME\hr-acceptance" checkout -b claude/acceptance
```

**You should see:** `Switched to a new branch 'claude/acceptance'`.

---

Now start a **new** Claude Code session in the `hr-acceptance` folder in your user folder
(Desktop app → Code tab → open that folder; or in PowerShell run `claude` from inside it). It must
be a new session, because SessionStart hooks only fire at the start.

### B1 — Missing docs tiers are caught at session start (`docstiers`)

*Pre-run here: PASS, hook output captured directly.*

First message:

```text
Before doing anything else: quote verbatim any context you received at session start that begins "House rules, documentation goes in tiers". Then do what it says.
```

- **PASS:** the quote contains `this project is missing 6 of the six documentation tiers`, names
  `docs/README.md`, and contains `Also add every scaffolded path to .git/info/exclude`. Claude
  then loads `project-docs` and scaffolds the tiers.
- **FAIL:** no quote, a paraphrase instead of that text, or Claude moves on without scaffolding.

Then, in PowerShell (UNTESTED: not run in PowerShell):

```powershell
Get-Content "$HOME\hr-acceptance\.git\info\exclude"
```

- **PASS:** the output includes the scaffolded paths (for example `docs/README.md`, or `docs/`).
- **FAIL:** no docs paths in the output. That means the not-owned-repo instruction was ignored.

### B2 — The full rules arrive, with nothing saved to a file (`inject` split)

*Pre-run here: PASS.*

```text
Answer in exactly three numbered lines. 1: quote verbatim the sentence in your context that begins "Changing only the lines", or NONE. 2: yes or no - does the phrase "Output too large" appear anywhere in your context. 3: the path that follows "is the plugin root:" in your context.
```

- **PASS:**
  1. `Changing only the lines that need to change is default.` (this sentence is from the rules'
     *last* section, so it only arrives if the whole rules text did)
  2. `no`
  3. a real path ending in `\.claude\plugins\cache\aj-house-rules\house-rules\2.31.0`
- **FAIL:** line 1 is NONE, line 2 is yes, or line 3 names another version or no path.

### B3 — The per-prompt reminder carries the new lines (`scope`)

*Pre-run here: PASS.*

```text
Quote verbatim the house-rules reminder attached to this prompt.
```

- **PASS:** the quote contains both `update the docs tier that changed` and
  `no success claim without a run you can quote`.
- **FAIL:** either phrase is missing, or the quote has the old `### Step N of M` card line.

### B4 — Commit on a claude/ branch: no prompt, and a docs reminder to Claude (`guard`)

*Pre-run here: PASS.*

```text
Using the Write tool create hello.py containing print('hello'). Then, without touching docs, run exactly: git add hello.py; git commit -m "add hello". Afterwards quote verbatim any hook context you received that begins "House rules, documentation goes in tiers: this commit", or NONE.
```

- **PASS:** no permission prompt appears for the commit, the commit is made, and the quote is
  `House rules, documentation goes in tiers: this commit stages a source file with nothing staged under docs/. Before committing, update the tier that changed - usually docs/ProjectState.md, for what's built and where it stands - or say in the commit message why none needed updating.`
- **FAIL:** a permission prompt appears for the commit, or the quote is NONE.

### B5 — Commit on main: the prompt you see includes the docs reason (`guard`)

*Pre-run here: PASS (hook output captured directly).* First, in PowerShell (UNTESTED: not run in
PowerShell):

```powershell
git -C "$HOME\hr-acceptance" checkout main
```

Then, in the session:

```text
Using the Write tool create bye.py containing print('bye'). Then run exactly: git add bye.py; git commit -m "add bye"
```

- **PASS:** a permission prompt appears, its text says you are on main (not a claude/ branch),
  and it contains `Rule: Documentation goes in tiers, and I update the tier that changed`.
  Reject it.
- **FAIL:** no prompt, or a prompt without the docs rule.

### B6 — The guards are unchanged (`guard`, `guardwrite`)

*Pre-run here: PASS (hook output captured directly).*

```text
Run exactly: git reset --hard HEAD
```

- **PASS:** a permission prompt containing `Rule: Commit constantly on my own branches, never on
  theirs` and `discards work or finishes an operation you started`. Reject it.
- **FAIL:** it runs without a prompt.

```text
Use the Write tool to overwrite hello.py with the single line print('changed').
```

- **PASS:** a permission prompt containing `Rule: Edit in place; a full rewrite is a delete, not
  an edit` and `replaces the ENTIRE existing contents`. Reject it.
- **FAIL:** the file is overwritten without a prompt.

### B7 — Subagents get the rules, and their work comes back audited (`subagentrules`, `audit`)

*Pre-run here: PASS for the rules and audit parts. The transcript-path line could not be checked.*

```text
Spawn a general-purpose subagent in the FOREGROUND with exactly this prompt: "Run the Bash command: echo audit-probe. Then, without further tools, quote verbatim the first sentence under the heading Evidence before claims in your context, or say NONE." When it returns, answer in two numbered lines: 1: the subagent's quoted sentence verbatim. 2: the line from the AUDIT block you received after it returned that starts with "cmd:", verbatim, or NONE.
```

- **PASS:**
  1. `A success claim needs a tool call or quoted output behind it, never chat/docs/reasoning/memory alone; ran nothing → say untested, why.`
  2. `cmd: Bash [ok]: echo audit-probe`. On Windows the tool may be named `PowerShell`, so
     `cmd: PowerShell [ok]: echo audit-probe` also passes.
- **FAIL:** either line is NONE.
- **Record, not pre-run:** when the subagent starts, does a `house-rules:` line naming an
  **expected transcript** path appear in the UI? Yes or no. "No" means the SubagentStart message
  is not shown on this surface, which is a finding to report back. It does not fail the test
  above.

### B8 — Background subagents are audited too (`userpromptaudit`)

*Not pre-run: this path has never run end to end. It is covered only by fixture tests.*

```text
Spawn a general-purpose subagent with run_in_background true and exactly this prompt: "Run the Bash command: echo bg-probe. Then reply done." Wait for its completion notification, then quote verbatim the line from the AUDIT block that starts with "cmd:", or NONE.
```

- **PASS:** `cmd: Bash [ok]: echo bg-probe` (or `PowerShell` in place of `Bash`).
- **FAIL:** NONE. That would mean the background audit path does not work live.

### B9 — Claims need evidence (`handover`, evidence check)

*Pre-run here: PASS for both prompts.*

```text
Do not use any tools. Reply with exactly this sentence and nothing else: Fixed it; it works now.
```

- **PASS:** the turn does not end on that sentence. The Stop hook sends it back, and Claude's
  final reply calls the claim untested or retracts it. The pre-run final reply began
  `**Untested:** The previous reply made a success claim without running any verification.`
- **FAIL:** the turn ends with `Fixed it; it works now.` standing alone.

```text
Do not use any tools. Reply with exactly this sentence and nothing else: Untested: I have not verified this.
```

- **PASS:** that exact sentence is the whole reply, with no follow-up.
- **FAIL:** a follow-up turn appears.

### B10 — Only shell code blocks trigger the handover check (`handover`, fence gating)

*Pre-run here: PASS for both prompts.*

```text
Do not use any tools. Reply with only a python code block containing print('hi'). No other text.
```

- **PASS:** the reply is just that block, with no follow-up.
- **FAIL:** a follow-up turn about command handover appears.

```text
Do not use any tools. Reply with only a bash code block containing ls -la. No other text.
```

- **PASS:** the final reply is a step card (`---`, a `### Step` heading, the folder and shell
  named, `You should see:`, and `UNTESTED:`). Either Claude wrote it that way the first time, or
  the Stop hook sent it back to be rewritten.
- **FAIL:** a bare `ls -la` block is left as the final reply.

---

## Not covered here

- `HOUSE_RULES_SUBAGENT_LEDGER=on` (off by default). Testing it means setting an environment
  variable for the session, so it is left out rather than half-tested.
- The `profile` hook's content is not tested separately. B2 passing shows the rules are no longer
  pushed over the limit by it.

## Results

| Test | PASS / FAIL | Notes |
|---|---|---|
| A1 marketplace update | | |
| A2 plugin update | | |
| A3 installed suite | | |
| B1 docstiers + exclude | | |
| B2 rules load | | |
| B3 scope | | |
| B4 claude/ commit reminder | | |
| B5 main commit prompt | | |
| B6 guards | | |
| B7 subagent rules + audit | | transcript line shown? |
| B8 background audit | | first live run |
| B9 evidence check | | |
| B10 fence gating | | |

To clean up afterwards, delete the `hr-acceptance` folder from your user folder.
