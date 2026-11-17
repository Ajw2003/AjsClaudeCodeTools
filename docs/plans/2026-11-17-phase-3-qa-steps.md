# Phase 3 QA: your steps

For the QA page `docs/plans/2026-11-16-phase-3-qa.html`. Run these on your PC, in Windows PowerShell 5.1 (inferred from
`docs/example-environment.md`, recorded 2026-08-25), with this repo cloned to `C:\Users\aj\Desktop\AjsClaudeCodeTools`.

Every command uses full paths, so it runs from any folder. To open PowerShell: press Start, type `PowerShell`, press
Enter. Paste one command at a time, press Enter, and check the result before the next step.

**Phase 3 QA: 13 steps.** Do them in order; each step's output tells you it worked.

---

### Step 1 of 13 — Fetch the phase 3 branch

UNTESTED: run on Linux in the cloud session (same git command), not in Windows PowerShell on your PC.

In **Windows PowerShell**, opened anywhere:

```powershell
git -C "C:\Users\aj\Desktop\AjsClaudeCodeTools" fetch origin AjsAgent/phase-3-handoff
```

**You should see:** a line ending in `AjsAgent/phase-3-handoff -> FETCH_HEAD`. That means the branch is downloaded.

*Next: step 2 puts that branch in its own folder.*

---

### Step 2 of 13 — Put the branch in its own folder

UNTESTED: run on Linux in the cloud session, not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
git -C "C:\Users\aj\Desktop\AjsClaudeCodeTools" worktree add --detach "C:\Users\aj\Desktop\phase-3-qa" FETCH_HEAD
```

**You should see:** `Preparing worktree (detached HEAD ...)` and then a line starting `HEAD is now at`. A new folder,
`C:\Users\aj\Desktop\phase-3-qa`, now holds the phase 3 code. Your Desktop clone is unchanged.

*Next: step 3 switches the plugin to this build.*

---

### Step 3 of 13 — Switch the plugin to the phase 3 build

UNTESTED: run on Linux in the cloud session (in a throwaway settings folder), not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
python "C:\Users\aj\Desktop\phase-3-qa\tools\use_branch.py" AjsAgent/phase-3-handoff
```

**You should see:** these four lines at the end:

```text
marketplace ref : AjsAgent/phase-3-handoff
plugin version  : 2.81.0
checkout commit : <a 7-letter commit>
OK: installed build matches the request. Restart Claude Code to load it.
```

Then quit the Claude desktop app fully and open it again, so it loads 2.81.0.

*Next: step 4 makes a test branch for the pickup.*

---

### Step 4 of 13 — Make a test branch for the pickup

UNTESTED: run on Linux in the cloud session (it printed the line below), not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
git -C "C:\Users\aj\Desktop\phase-3-qa" switch -c AjsAgent/qa-pickup
```

**You should see:** `Switched to a new branch 'AjsAgent/qa-pickup'`.

*Next: step 5 puts that branch on GitHub.*

---

### Step 5 of 13 — Put the test branch on GitHub

UNTESTED: the same push form ran from the cloud session to GitHub on 2026-11-17 (it made `ajsagent/phase-3-live-cloud`), not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
git -C "C:\Users\aj\Desktop\phase-3-qa" push -u origin AjsAgent/qa-pickup
```

**You should see:** `* [new branch]      AjsAgent/qa-pickup -> AjsAgent/qa-pickup`.

*Next: step 6 makes an unsaved change on your first account.*

---

### Step 6 of 13 — Account A: make a change and leave it uncommitted

No command. In the **Claude desktop app**, signed in as your first account (A):

1. Open the folder `C:\Users\aj\Desktop\phase-3-qa` in a new Code session.
2. Send exactly: `Run this shell command and nothing else: echo hello > qa-note.txt`
3. When it has replied, close the session.

**You should see:** Claude runs the command and replies. Nothing is committed. When Claude finishes its reply, the plugin saves the
new file to GitHub on its own.

*Next: step 7 makes a second folder, as a second machine would have.*

---

### Step 7 of 13 — Make a second folder from GitHub

UNTESTED: run on Linux in the cloud session with another branch name (the test branch does not exist until step 5), not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
git clone -b AjsAgent/qa-pickup https://github.com/Ajw2003/AjsClaudeCodeTools.git "C:\Users\aj\Desktop\phase-3-qa-b"
```

**You should see:** `Cloning into 'C:\Users\aj\Desktop\phase-3-qa-b'...` and then the prompt again. This folder does
not have `qa-note.txt`, because it was never committed.

*Next: step 8 opens it on your second account.*

---

### Step 8 of 13 — Account B: open the second folder and read the pickup

No command. In the **Claude desktop app**:

1. Sign out, and sign in as your second account (B).
2. Open the folder `C:\Users\aj\Desktop\phase-3-qa-b` in a new Code session.
3. Send exactly: `Quote, word for word, the house-rules pickup note you were given when this session started.`

**You should see:** a note starting `house-rules pickup: loaded from`, naming `qa-note.txt` and giving a restore command
that starts `git diff` and ends `| git apply`, and a line telling Claude to ask you before it runs that command. That is the pickup
working across accounts. Do not run the restore command; this is only a test.

*Next: step 9 makes a folder that is not a git repository.*

---

### Step 9 of 13 — Make a plain folder for the pages switch

UNTESTED: not run anywhere; it is a standard PowerShell folder create.

In **Windows PowerShell**:

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\aj\Desktop\pages-test"
```

**You should see:** a small table naming the folder `pages-test`. It is not a git repository.

*Next: step 10 switches pages off there.*

---

### Step 10 of 13 — Switch pages off in that folder

No command. In the **Claude desktop app**, either account:

1. Open the folder `C:\Users\aj\Desktop\pages-test` in a new Code session.
2. Send exactly: `pages off`
3. Then send exactly: `Quote, word for word, any house-rules note about Pages that you were given with my last message.`

**You should see:** a reply quoting a note that starts `Pages OFF (you typed "pages off", in this folder)`.

*Next: step 11 checks the switch was saved in that folder.*

---

### Step 11 of 13 — Check the switch file

UNTESTED: not run anywhere; it is a standard PowerShell file read.

In **Windows PowerShell**:

```powershell
Get-Content "C:\Users\aj\Desktop\pages-test\.claude\house-rules-mode.json"
```

**You should see:** a line `"pages": "off"` between braces. The switch is saved in that folder, with no git repo.

*Next: step 12 runs the tests on your PC.*

---

### Step 12 of 13 — Run the plugin's tests on Windows

UNTESTED: the same file was run on Linux in the cloud session (1247 of 1247 passed), not in Windows PowerShell.

In **Windows PowerShell**:

```powershell
python "C:\Users\aj\Desktop\phase-3-qa\claude-house-rules\plugins\house-rules\scripts\verify.py"
```

**You should see:** after a minute or two, a last line starting `RESULT:`. Eight failures are expected. They are the
Windows-only failures that issue #523 tracks, and I will fix them from your results. Copy every line that
contains `FAIL` and paste those lines into your reply to me. If no line contains it, say so.

*Next: step 13 switches the plugin back.*

---

### Step 13 of 13 — Switch the plugin back to the normal build

UNTESTED: run on Linux in the cloud session (in a throwaway settings folder), not in Windows PowerShell on your PC.

In **Windows PowerShell**:

```powershell
python "C:\Users\aj\Desktop\phase-3-qa\tools\use_branch.py" main
```

**You should see:** these lines at the end:

```text
marketplace ref : (none - default branch)
plugin version  : 2.80.0
checkout commit : <a 7-letter commit>
OK: installed build matches the request. Restart Claude Code to load it.
```

Then quit the Claude desktop app fully and open it again.

---

**When you are done:** send me `QA passed: Phase 3`, or `QA failed: Phase 3` with what went wrong, and paste the
`FAIL` lines from step 12. The test folders (`phase-3-qa`, `phase-3-qa-b`, `pages-test`) and the branch
`AjsAgent/qa-pickup` can stay; I will not delete anything without your word.
