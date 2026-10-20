# Plugin restructure

How the house-rules plugin is being reshaped, and how the first deliverable, the 2.68.1 patch,
works. The direction was approved on 2026-10-16 (`docs/6-decisions/Decisions.md`, "Design approved:
plugin restructure direction"). The audit behind it is `docs/audits/2026-10-16-plugin-audit/`.

## Why

House-rules 2.68.0 works for one person. One 8,365-line file (`scripts/hook.py`) answers every
hook event, each rule lives in several copies that have drifted (28 rule-against-rule
contradictions), and 62 lines in 15 shipped files name aj, aj's repos or aj's labels. The issue
"the design loop is broken and blocks sessions" (#303) shows the cost: sessions in other repos are
blocked by checks that contradict each other.

## Target structure

The plugin's identity is aj's goal from the issue "a two-helper tool that cleans a session
transcript, then files issues from it" (#304): safe work on several projects at once, each session
in its own context, with observations about other projects captured as issues there, and session
transcripts usable as evidence without leaking secrets.

| Part | Holds | Installed by default |
|---|---|---|
| Core | Project boundaries (which repo a message or tool call belongs to; state kept per repo; other repos' work becomes an issue there), per-user settings through Claude Code's `userConfig`, one state store under `CLAUDE_PLUGIN_DATA`, git and transcript helpers, rule loading from one source file per rule, a failure message for every entry point | Yes |
| Safe git | The destructive and branch guard, the overwrite guard, credit checks, the prompt timer | Yes |
| Session triage | A helper that flags secrets in a transcript for aj to confirm and remove, and a helper that files issues from the cleaned transcript | Yes |
| Design loop | Stages, approvals, pages, QA, the after-pull-request checks, required before-and-after visuals | No |
| Writing | One clarity checker, the editor helper, plain docs | No |
| Delegation | Helper agents, the running-helper limit, audits, worktree autosave | No |
| Docs | Doc tiers, the long-comment harvest, doc-ref pointers, the archivist helper | No |

Each optional part declares the core in its `plugin.json` `dependencies`, so installing it installs
the core. Updates come from marketplace `autoUpdate` and load with `/reload-plugins`; the
self-updater (`hook.py:1471-1633`) goes. The 28 rule contradictions are settled in a grilling
session before any of this is built.

## The 2.68.1 patch

It ships before the restructure so that sessions can work. Each change answers incidents from the
issue "the design loop is broken and blocks sessions" (#303), and each gets a `verify.py` case that
reproduces the incident first.

### Every approval in a message is read
`_loop_apply` (`hook.py:5467`) tests the build-plan phrase first and returns as soon as it refuses,
so a message holding "Design approved: X" and "Build plan approved: X" never has its design approval
read (incident 1). The patch finds every approval phrase in the message and applies them in stage
order: design, then build plan, then QA. A design approval always sets the feature name, so a stale
name can't survive into the next feature (incident 2).

### Only this repo's issues count
`_loop_record_issues` (`hook.py:5737`) records any issue the session creates, so issues opened in
another repo were counted as the current feature's, and the end-of-reply label check then blocked the
session seven times (incident 3). The patch records an issue only when its repo matches the repo that
owns the stage file (`.claude/house-rules-loop.json`).

### Four checks report instead of blocking
| Check | Where | Incident |
|---|---|---|
| The refusal of shell commands that write files while code is locked | `_loop_gate`, message at `hook.py:5685` | 4 |
| The re-creation (parity) check at the end of a reply | `hook.py:7698` | 5 |
| The page checkpoint | `_check_page`, `hook.py:7354` | 6 |
| The bare-reference writing check | `clarity.py:135`, row at `clarity.py:213` | 8 |

Each still prints what it would have blocked, so the grilling session has evidence. The page builder
(`make_page.py:328`) accepts any approval line instead of only the design-loop phrases; only those
phrases move a stage when aj types them (incident 7).

### A blocked page stays owed
The page checkpoint counts words in the newest message only (`hook.py:7746`), so a shorter retry
cleared it. The patch records the page as owed against aj's message (the page-blocks file,
`hook.py:7561-7576`), and the reminder repeats on every reply to that message until one links a page.

## Not changed by the patch
Everything else in 2.68.0, including the guard work from the issue "Guards block only unrecoverable
actions" (#285), which is waiting for aj's QA.

## Step 2: how hook.py splits (#340)

Design approved 2026-10-20 ("Design approved: restructure step 2 1A"): real modules now. Each part
becomes its own Python module in a package beside `hook.py`, `scripts/house_rules/`; `hook.py` keeps
only the `main()` dispatcher that `run.sh` calls, so the 32 entries in `hooks/hooks.json` and `run.sh`
do not change. A part module imports from the core and never from another part. Where a check in one
part needs another part's code, the dispatcher in `hook.py` calls both.

**Inventory.** Every block of `hook.py` (8,588 lines, 31 `event_*` handlers) and where it goes. Every
block is kept and moved; nothing is dropped in step 2. "Split" marks a block whose pieces go to
different parts.

| Lines | Block | Goes to | Note |
|---|---|---|---|
| 1-141 | shared helpers, payload reading, `emit` | core | |
| 142-643 | `inject` (rules at session start) | core | |
| 644-680 | `showrule` | core | |
| 681-772 | `profile` (machine profile) | core | |
| 773-998 | `standards` | core | |
| 999-1160 | `docstiers` | docs | |
| 1161-1635 | `versioncheck` and the self-updater | core | kept until step 10 (#348) removes it |
| 1636-1755 | `scope` | core | split: its delegation clause goes to delegation |
| 1756-2760 | `guard` (destructive and branch guard) | safe git | split: `_staged_docs_status` (1948-2042) to docs, `work_saved_elsewhere` (2250) to core |
| 2761-2854 | `guardwrite` (overwrite guard) | safe git | |
| 2855-2974 | `artifact` | core | split: the page writing note goes to writing |
| 2975-3091 | `branchnudge` | safe git | |
| 3092-3145 | `runnable` | core | |
| 3146-3339 | `delegate`, announce helpers, `subagentrules` | delegation | |
| 3340-3935 | `announce`, `verdict` and the audit report | delegation | |
| 3936-4067 | `agentcap` | delegation | |
| 4068-4533 | `prompttimer` | safe git | |
| 4534-4578 | `promptran` | core | |
| 4579-4924 | `subagentcommit`, autosave and worktree helpers | delegation | |
| 4925-5223 | issue workflow | design loop | |
| 5224-6028 | design loop: stages, labels, approvals | design loop | |
| 6029-6176 | attribution and `creditcheck` | safe git | |
| 6177-6454 | `guardgithub` | safe git | split: `_author_guard` and `_issues_guard` (6317-6390) to design loop |
| 6455-6489 | `issuelist` | design loop | |
| 6490-6639 | `autosave`, `commitgate` | delegation | |
| 6640-6692 | `worktreesweep` | delegation | |
| 6693-6844 | `audit`, `userpromptaudit` | delegation | |
| 6845-7118 | `handover` (end-of-reply) | core dispatcher | split: each check moves to its part |
| 7119-7229 | commit-obligation helpers | safe git | |
| 7230-7528 | parity, visual, plain-summary, long-reply and editor helpers | writing | parity's check goes to docs |
| 7529-7601 | end-of-reply checkpoints | design loop | |
| 7602-7805 | `pagecheck` | design loop | |
| 7806-8089 | end-of-reply dispatcher | core dispatcher | |
| 8090-8542 | `harvest` | docs | |
| 8543-8588 | `main` | `hook.py` | stays as the only code in `hook.py` |

Session triage has no code in `hook.py` today; its module is created empty and filled in step 9 (#347).

**What changes in `verify.py`.** 211 of its tests run `hook.py` through `run.sh` and are unaffected.
Six load `hook.py` in-process and call nine internal names; each is pointed at the module that owns
the name. One test (`verify.py:3236`) replaces `_read_back_body` before running the credit check; it
replaces it on the safe git module instead. Every changed test line is listed in the step's pull
request.
