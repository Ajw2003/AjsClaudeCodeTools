# Triage: house-rules core and the restructure into sub-plugins

Triage of the open issues on `Ajw2003/AjsClaudeCodeTools` that belong to the house-rules plugin's
core or to the restructure into a core plus six sub-plugins (issue #306, "restructure into a shared
core with project boundaries and six optional sub-plugins"). Run on 2026-10-17 with the label
mapping in [docs/agents/triage-labels.md](../agents/triage-labels.md).

Every row is a **recommendation**. No label has been applied and no issue closed.

**Where each issue goes.** The target part is taken from the table in
`docs/4-systems/plugin-restructure.md` on `main`: Core, Safe git, Session triage, Design loop,
Writing, Delegation, Docs.

**How a state was picked.**
- An issue labelled `needs review` is built and waits for aj's testing, so it becomes
  `ready-for-human`.
- An issue labelled `in progress`, or a clear spec with no open question, becomes `ready-for-agent`.
  Most of these are built inside their sub-plugin during the restructure, not in today's `hook.py`
  (audit 6, section 6, on `main`).
- An issue that the restructure or a later issue replaces becomes `wontfix`, with the issue that
  replaces it named.
- An issue whose behaviour already exists in the code becomes `wontfix` (already implemented). The
  code location is given.

**What was checked against the code.** Each row's last column says Checked (with the place in the
code on `origin/main`) or Not checked. "Not checked" means the row is read from the issue title and
labels only.

## Superseded: the first rebuild plan

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #208 Rebuild house-rules from the ground up | Feature | wontfix | Replaced by #306, which aj approved on 2026-10-16 with a different target structure | Checked: #306 body |
| #209 Rebuild step 1: list what the plugin does and sort every open issue | Feature | wontfix | Replaced by the 2026-10-16 plugin audit (`docs/audits/2026-10-16-plugin-audit/`) and this triage | Checked: audit files on `main` |
| #210 Rebuild step 2: design the lean plugin | Feature | wontfix | Replaced by `docs/4-systems/plugin-restructure.md` | Checked |
| #211 Rebuild step 3: build the new plugin | Feature | wontfix | Replaced by #306's build sub-issues | Checked: #306 body |
| #212 Rebuild step 4: switch aj's machine over | Feature | wontfix | Replaced by #306; updates come from marketplace autoUpdate | Checked: #306 body |

## The 2.68.1 patch

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #303 the design loop is broken and blocks sessions | bug | ready-for-agent | Parent of the patch; closes when #307 to #311 pass QA | Checked: #306 body |
| #307 reads every approval in a message | bug | ready-for-human | Built, waits for aj's QA | Not checked |
| #308 records only issues created in its own repo | bug | ready-for-human | Built, waits for aj's QA | Not checked |
| #309 four checks report instead of blocking | bug | ready-for-human | Built, waits for aj's QA | Not checked |
| #310 a blocked page stays owed across retries | bug | ready-for-human | Built, waits for aj's QA | Not checked |
| #311 release the patch | Feature | ready-for-human | Built, waits for aj's QA | Not checked |

## Core

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #306 restructure into a shared core and six sub-plugins | Feature | ready-for-agent | The parent for everything below | Checked |
| #301 a session finishes its own task; other work becomes an issue in its own repo | Feature | ready-for-agent | Project boundaries, the core's main job | Checked: `plugin-restructure.md` |
| #296 approvals dropped silently when the folder isn't a git repo | bug | ready-for-agent | Project boundaries | Not checked |
| #287 agent name, credit and branch prefix are configurable | Feature | ready-for-agent | Per-user settings through `userConfig` (audit 6, section 5) | Not checked |
| #204 every hook call recompiles all of hook.py | Feature | ready-for-agent | `run.sh:162` runs `hook.py` as source on every event, so it is compiled every time. Splitting the file into the core and sub-plugins is the fix | Checked: `run.sh:162` |
| #205 with no Python, the credit check and issue gate let everything through silently | bug | ready-for-agent | The core needs a failure message for every entry point | Not checked |
| #206 two copies of "which folder does this command run in" | Feature | ready-for-agent | Becomes one core git helper. Only one copy (`_command_dir`, `hook.py:2145`) was found in `hook.py`; the second copy is not in that file | Checked: `hook.py` only |
| #41 the failure-mode contract is written three times | Feature | ready-for-agent | Becomes one core failure message | Not checked |
| #42 four near-identical payload-field regexes | Feature | ready-for-agent | Becomes one core helper | Not checked |
| #43 `event_standards` mixes detection with prose | Feature | ready-for-agent | Becomes core rule loading | Not checked |
| #44 `verify.py` has no interface beyond running the whole file | Feature | ready-for-agent | Each sub-plugin gets its own tests | Not checked |
| #46 `verify.py` forbids agent fields the reference supports | bug | ready-for-agent | Same test split | Not checked |
| #215 verify.py fails 31 guard checks after more than 5 minutes | bug | ready-for-agent | Possible duplicate of #229 | Not checked |
| #229 verify.py's guard tests fail with an old "last seen" temp file | bug | ready-for-agent | Possible duplicate of #215; one should close | Not checked |
| #114 installer reports a false failure after an update | bug | wontfix | The self-updater is removed by #306 (`plugin-restructure.md`, "the self-updater goes") | Checked: `plugin-restructure.md` |
| #228 audit every rule for a check that enforces it | Feature | ready-for-human | Part of the grilling session on the 28 rule contradictions, which needs aj | Checked: #306 body |
| #45 the vocabulary and settled reversals have nowhere to live | Feature | needs-info | Labelled speculative; it doesn't say which part should own it | Not checked |

## Safe git

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #315 the attribution guard misses gh api and curl | bug | ready-for-agent | New, clearly specified | Not checked |
| #189 the attribution guard misses a quoted -c author | bug | ready-for-agent | Clearly specified | Not checked |
| #191 pull requests from a cloud session still credit Claude | bug | ready-for-agent | Clearly specified | Not checked |
| #178 the attribution guard also checks GitHub tool calls | Feature | wontfix (already implemented) | `_attribution_guard` checks GitHub MCP tool writes; its comment cites "Issue #178" | Checked: `hook.py:6050-6101` |
| #285, #289, #290, #291, #292, #293 the guard rebuild (built in 2.68.0) | bug | ready-for-human | Built, waits for aj's QA | Checked: labels |
| #134, #192, #197, #203 commits on the agent's own branch prompt | bug | ready-for-human | Probably fixed by #289's never-blocked list. aj's QA of #289 settles it, then these close | Not checked |
| #153, #198, #200 destructive actions and second-line commands | bug | ready-for-human | Probably fixed by #291. Close after aj's QA of #291 | Not checked |
| #136, #173, #196 unanswered prompts block work | bug | ready-for-human | Probably fixed by #285, #290 and #292. Close after QA | Not checked |
| #142, #144, #145, #146, #147, #149, #151, #152, #159 the prompt timer | Feature/bug | ready-for-human | #290 rebuilt the prompt timer. Close each one that #290's QA covers | Not checked |
| #174 credit "aj's agent" and AjsAgent/ branches everywhere, with #175, #176, #177, #179 | Feature | ready-for-human | Partly live: this session's commits already say "Committed by AJ's agent". Becomes a setting under #287. aj decides which are done | Checked: this session's commits |
| #156 delete the agent's branches once a pull request merges | Feature | ready-for-human | Conflicts with the house rule "never delete one unasked", so aj decides how far it goes | Checked: `house-rules.md`, commit-branches section |
| #181, #182 report and rename old claude/ branches across aj's repos | Feature | ready-for-human | Changes other repos, so aj approves each one | Not checked |

## Session triage

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #304 a two-helper tool that cleans a transcript, then files issues | Feature | ready-for-agent | The Session triage sub-plugin | Checked: audit 6 |
| #71 a skill that extracts a session's whole context | Feature | wontfix | Covered by #304 and `tools/session_ledger.py` | Checked: audit 6, section 3 |
| #140 a handoff document and commit at 95% usage | Feature | needs-info | Not checked: can a hook read the session's usage percentage? Which part owns it? | Not checked |

## Design loop

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #297, #298, #299, #300 after-pull-request checks | Feature | ready-for-agent | aj chose to build these inside the Design loop sub-plugin | Checked: #306 body |
| #302 before-and-after visuals on proposal pages | Feature | ready-for-agent | In progress | Checked: audit 6, section 7 |
| #313 pictures mandatory on every page | Feature | ready-for-agent | Labelled `up next`; overlaps #302 | Not checked |
| #281 the page after a long reply must be automatic, with #282, #283, #284 | bug | ready-for-agent | This branch's work | Checked: branch name |
| #273 the end-of-reply label check repeats without limit | bug | ready-for-agent | Clearly specified | Not checked |
| #224, #225, #226, #227, #230, #231, #232, #233, #240 to #243, #261, #262, #265, #286, #288 design loop and pages (built) | Feature/bug | ready-for-human | Built, waits for aj's QA | Checked: labels |
| #274 to #278 house labels created automatically (built) | Feature | ready-for-human | #274 is `in progress`; the rest wait for QA | Checked: labels |
| #94, #103, #107, #110, #119, #128, #129, #130, #131, #132, #141 the issue workflow | Feature/bug | wontfix | #301 replaces the issue workflow's step counting and label checks (audit 6, section 4). aj confirms before any close | Checked: audit 6 |
| #102, #155, #158 plain-language summary and visual check after each task | Feature | ready-for-human | The QA page mode may already cover these. aj judges | Not checked |
| #244 automatic change log every turn | Feature | ready-for-agent | Clearly specified | Not checked |

## Writing

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #245 to #250 clear-writing check (built) | Feature | ready-for-human | Built, waits for aj's QA | Checked: labels |
| #193, #260 permission prompts in plain words | Feature | ready-for-agent | Two issues ask for the same thing; keep #260, close #193 | Not checked |
| #216 replies never use a bare number or label | Feature | wontfix (already implemented) | The bare-reference check in `clarity.py` does this | Checked: `plugin-restructure.md` cites `clarity.py:135` |
| #194 steps for aj that aren't shell commands skip the step-card check | bug | ready-for-agent | Clearly specified | Not checked |
| #137 handed-over Windows commands starting with "&" fail | bug | ready-for-agent | Clearly specified | Not checked |

## Delegation

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #118 skip executor delegation on Sonnet | Feature | wontfix | There is no executor agent any more; the agents are scout, builder, reviewer, editor and archivist | Checked: `agents/` on `main` |
| #105 replace the single executor with dynamic dispatch | Feature | wontfix | Done another way: one agent per job type (scout, builder, reviewer) | Checked: `agents/` on `main` |
| #120 check every background job every 5 minutes | Feature | ready-for-agent | In progress | Not checked |
| #122, #123, #124, #127 stallcheck reports wrongly | bug | ready-for-agent | `stallcheck.py` still ships | Checked: `scripts/` on `main` |
| #125, #138, #139, #160, #172 builder behaviour | bug | ready-for-agent | Builder agent rules | Not checked |
| #201 the two-helper limit loses track of simultaneous starts | bug | ready-for-agent | Clearly specified | Not checked |
| #150 follow a builder's progress from the phone | Feature | needs-info | Doesn't say what view would work on the phone | Not checked |
| #62, #69, #95 research into agyrules, superpowers and delegation cost | Feature | ready-for-human | Research and judgment, not a build | Not checked |

## Docs

| Issue | Category | State | Why | Check |
|---|---|---|---|---|
| #113 fix the note that says helpers never see the project instructions | bug | wontfix (already implemented) | Corrected on 2026-09-30 at `docs/architecture.md:23` | Checked |
| #202 docref check fails on verify.py's own pointers | bug | ready-for-agent | Clearly specified | Not checked |
| #199 rule text and docs for the new branch rule | Feature | ready-for-human | Belongs with #197's QA | Not checked |

## Left out: not part of the house-rules core

The art pipeline (#161 to #171), the eldritch goose (#183 to #187), Unity work (#116, #117,
#218 to #222) and Focus Deck (#180) are separate projects.
