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
