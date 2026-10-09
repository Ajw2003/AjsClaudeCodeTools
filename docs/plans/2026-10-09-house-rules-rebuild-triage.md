# House-rules rebuild: what stays, what goes, and where every open issue lands

Step 1 of the rebuild (#208, this is #209). Nothing below has been cut yet. This page is for aj to
approve or edit; step 2 designs the new plugin from whatever survives it.

## The short version

- The new plugin keeps three jobs: **protect work**, **run the workflow**, and **prove it's done**.
  Anything that does none of those goes.
- Today's 29 hooks become about **8**. The 6,500-line `hook.py` and 8,100-line `verify.py` get
  rewritten small. The target is under 1,500 lines each, with the tests written as a table.
- Of the 97 open issues: **31 are fixed by the rebuild** (bugs in code being rewritten or dropped),
  **34 are carried in** (they become requirements for the new plugin), **14 look already done**
  (aj decides whether to close them), and **18 belong to other projects**.

## What today's plugin costs (measured 2026-10-09, cloud container, Python 3.13)

| What | Today | Target |
|---|---|---|
| Text added at every session start (inject, profile, standards, issuelist) | 16,876 characters, about 4,200 tokens | under 4,000 characters |
| Slowest session-start hook (`profile`, hardware probe) | 858 ms | no probe |
| One hook call (`guard` on `ls`) | 125 ms | under 50 ms |
| Hooks fired by one file Write | 8 separate Python starts | 2 |
| Hooks fired by one shell command | 3 | 2 |

How it was measured: each handler piped a minimal payload through `scripts/run.sh` and the output
counted with `wc -c`, timed with `date +%s%N`. One run each, so treat the timings as rough.

## Inventory: every part of the plugin

**Keep** means it survives, usually rewritten smaller. **Merge** means its job moves into another
part. **Drop** means it goes; a drop that loses something says what.

### Hooks (29 today)

| Hook | When it runs | Verdict | Why |
|---|---|---|---|
| `inject` | session start | **Keep** | The rules themselves. Shrunk from 9,700 to about 3,000 characters, built around the workflow. |
| `profile` | session start | Merge into `inject` | One line saying which machine this is, plus the handover-target file for remote sessions. The hardware probe goes. |
| `standards` | session start | Merge into `inject` | Names which coding standards apply and where they are, instead of pasting their full text. |
| `docstiers` | session start | Merge into `inject` | Still checks the six doc tiers exist. |
| `issuelist` | session start | Merge into `inject` | Still lists open issues (part of the workflow). |
| `versioncheck` | session start | Drop from start-up | It can take up to 90 s and needs the network. It moves to the `doctor` command. |
| `scope` | every message | **Keep** | One short line: the workflow router (two steps or fewer, just do it; otherwise brainstorm, research, plan, issues). |
| `userpromptaudit` | every message | Drop | Reports on finished background helpers; Claude Code now says when one finishes. |
| `worktreesweep` | every message | Merge into `autosave` | Saving a dead helper's work is the same job as saving anyone's. |
| `guard` | before a shell command | **Keep, rewrite** | The core protection. It splits the command properly instead of pattern-matching raw JSON, which is the root cause of 9 open bugs. |
| `guardwrite` | before Write | **Keep** | Asks before a Write replaces an existing file wholesale. |
| `guardgithub` | before GitHub tool writes | Merge into `guard` | Same checks (credit, default branch), one place. |
| `agentcap` | before a helper starts | Drop | The two-helper limit is buggy (#201) and is better as one line in the rules. |
| `commitgate` | before an edit | **Keep, rewrite** | The issue gate. It arms on multi-file work however it was planned, not only from plan mode. |
| `handover` | end of turn | **Keep** | The step-card check, extended to steps that aren't shell commands (#194). |
| `artifact` | after Write | Drop | One rule line ("deliverables live in the project") does this. |
| `branchnudge` | after Write | Merge into `guard` | "You're on aj's branch, branch off" is said once, before the first write. |
| `runnable` | after Write | Merge into `handover` | "You wrote a script, run it" becomes part of the end-of-turn proof check. |
| `harvest` | after Write | Drop | Moving long comments into docs is nice to have, not protection. The archivist goes with it. |
| `delegate` | after plan approval | Merge into `commitgate` | Plan approved means open the issues; that's the gate's job. |
| `audit` | after a helper | Drop | Visibility machinery for helpers. Claude Code shows this itself now. |
| `autosave` | after edits and commands | **Keep** | The main "never lose work" net: snapshots uncommitted work without touching the branch. |
| `promptran` | after any tool | Merge into `prompttimer` | Only exists to support the timer. |
| `announce` | helper starts | Drop | Says which model a helper runs on. Not protection. |
| `subagentrules` | helper starts | **Keep, small** | Helpers get the guard lines and the "commit as you go" line, nothing else. |
| `verdict` | helper stops | Drop | Checks the model that served a helper. Not protection. |
| `subagentcommit` | helper stops | Merge into `autosave` | Same job. |
| `prompttimer` | a permission prompt opens | **Keep, simplified** | A prompt nobody answers in 5 minutes is refused and listed under "waiting on you". It doesn't refuse every later prompt and it keeps no extra state. With fewer prompts it rarely fires. |

### Agents, commands, skills and other files

| Part | Verdict | Why |
|---|---|---|
| `builder` agent | **Keep** | Carries the builder rules from #125, #138, #139 and #160. |
| `reviewer` agent | **Keep** | The adversarial check before "done". |
| `scout` agent | Drop | Claude Code's built-in Explore helper does the same. |
| `archivist` agent | Drop | Goes with `harvest`. |
| `doctor` command | **Keep** | Gains the version check. |
| `docref`, `harvest-scan`, `plain-docs` commands | Drop | Support for parts being dropped. |
| `project-docs` skill | **Keep** | The six-tier docs structure (goal 7). |
| `plain-docs` skill | Drop | Plain-English doc copies; the main docs get written plainly instead. |
| `handover-cards` output style | **Keep** | The step-card format. |
| `templates/step-card.html` | **Keep** | The publish-a-page version of a card. |
| `stallcheck.py` | Drop | Has 5 open bugs (#122 to #127). It's replaced by builders posting a progress line per step (#150). |
| `docref.py`, `harvest_scan.py`, `plain_docs_check.py` | Drop | Support for parts being dropped. |
| `session_ledger_render.py` (and `tools/session_ledger.py`) | **Keep** | Session logs (goal 7). |
| `rules/detail/*.md` (27 files) | Merge | Cut to the few the short rules file actually points at. |
| `rules/standards/*.md` (5 files) | **Keep** | Loaded by pointer, not pasted in full. #117 (no hard-coded values) is added. |
| `verify.py` | **Keep, rewrite** | One table of cases (command in, decision out), runnable by name (#44). |

## Where every open issue lands

### Fixed by the rebuild (31)

These are bugs in code being rewritten or dropped. Each still gets a test in the new suite where it
was a guard bug, so the fix is proven, not assumed.

- **Guard misreads commands** (rewritten `guard` splits commands properly): #200 (risky step on a
  second line slips through), #203 (`cd` in a commit message prompts), #189 (quoted `-c` slips
  past the credit check), #192 (`git -C` reads the wrong repo), #206 (two copies of the folder lookup).
- **Too many prompts** (only truly destructive steps ask; nothing else prompts on a non-default branch):
  #136, #173, #149, #152, #159.
- **Code being dropped**: #201 (helper cap), #202 (docref), #122, #123, #124, #127 and #120 (stallcheck).
- **Speed** (small file, cached): #204.
- **Old architecture notes** made moot by the rewrite: #41, #42, #43, #44, #45, #46.
- **Plan-mode-only issue gate** (gate arms however work was planned): #119, #128, #129, #130, #110, #94, #103.

### Carried into the rebuild (34)

These become requirements. Step 2's design must say how each is met.

- **Guards and branches**: #153 (destructive steps on own pushed branch), #205 (fail closed when
  Python is missing), #193 (prompts say in plain words what they'll do), #151 (questions never time out).
- **Credit "aj's agent", never Claude**: #174 (parent), #176 (cloud sessions move to `AjsAgent/`),
  #179 (cloud attribution setting), #191 (the PR footer the app appends).
- **Workflow and issues**: #107 (plan becomes issues), #132 (in-progress and done labels), #131 and
  #141 (ask which finished issues to close), #156 (delete merged branches), #140 (save and hand off
  before the session runs out), #172 (builder recovers from a stopped task).
- **Helpers**: #105 (choose the helper per job; the lean version is builder plus reviewer),
  #118 (skip delegation on Sonnet), #125, #138, #139, #160 (builder waits, retries and testing
  scope), #150 (see a builder's progress from the phone).
- **Proof and handover**: #158 (visual check plus a plain summary after each task), #102 (final
  plain-language pass before pushing), #194 (cards for non-shell steps), #155 (questions as
  cards or multiple choice), #137 (Windows `&` commands), #147 (a real overnight test).
- **Docs and logs**: #71 (archive a session compactly), #117 (no hard-coded values), #114
  (installer false failure, needed for the switch-over), #95 (cost of delegating, measured in step 3).
- **Research for step 2**: #69 (superpowers workflow), #62 (agyrules dynamic helpers).

### Looks already done: aj decides whether to close (14)

Re-checked on 2026-10-09 against plugin 2.60.1 by feeding the real hooks test commands in
throwaway repos; every check for these issues passed. #113 and the timer wording were checked by
reading the files. Nothing closes without aj's
say-so.

- #133, #175, #177, #178: credit and branch naming (shipped 2.55.0 to 2.59.0).
- #142, #144, #145, #146: the prompt timer (shipped 2.52.0 to 2.53.0). Its rework is carried in the list above.
- #196, #197, #198, #199, #134: stop prompts stalling work (shipped 2.60.0). Commits run unasked
  off `main` and are refused on it, and a helper's destructive step is refused instead of left waiting.
- #113: the note about helpers and the instructions file (fixed, waiting on aj's look).

### Other projects, left out (18)

- Art pipeline: #161, #162, #163, #164, #167, #168, #169, #170, #171.
- Eldritch goose: #183 to #187.
- Old Claude credits across aj's repos: #180, #181, #182. Not done yet. It's a one-off
  migration, not plugin code, so it runs separately whenever aj wants.
- Unity: #116 (always open a fresh Unity project). It belongs in the Unity standards file, not
  the core rules.

## Decisions this page asks aj for

1. **Approve the drop list.** The biggest cuts are `harvest` plus the archivist, `stallcheck`,
   the helper model reports (`announce`, `verdict`, `audit`) and the plain-docs copies.
2. **Close the 14 "looks done" issues**, or name the ones to keep open.

Next, step 2 (#210): design the eight hooks, the short rules file, and one issue per piece to build.
