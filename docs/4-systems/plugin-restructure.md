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

**Inventory.** Every block of `hook.py` (8,588 lines, 31 `event_*` handlers) and where it goes. The line numbers in the table are **line numbers as of 2.70.0, before the split**; `hook.py` is 332 lines now ("Step 2 result" at the foot of this section shows where every block ended up). Every
block is kept and moved; nothing is dropped in step 2. "Split" marks a block whose pieces go to
different parts.

| Lines (as of 2.70.0, before the split) | Block | Goes to | Note |
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

### Step 2a: the package and the core (#357)

Built on the 2026-10-20 core-links decision (answer 1A). `scripts/house_rules/` now exists with
`__init__.py` and seven modules; only `core.py` has code (1,853 lines; `hook.py` went from 8,931 to
7,248). The six part modules (`safe_git`, `session_triage`, `design_loop`, `writing`,
`delegation`, `docs`) hold a one-line docstring each, and `session_triage` stays empty until step 9
(#347).

**Moved verbatim into `core.py`.** The shared helpers, payload reading and `emit`; the trace
helpers; `inject`, `showrule`, `profile` (with the hardware probes) and `standards`;
`versioncheck` and the self-updater; `scope`; `artifact` (with the file-path helpers `branchnudge`
also uses); `runnable`; `promptran`; and `work_saved_elsewhere`. Constants moved with the function
that uses them (the runnable notes, the scope reminders). `_plugin_version` also moved, because
`_rules_root` needs it and `core.py` may not import a part; it was an announce helper in the
inventory. Every path that was computed from `hook.py`'s `__file__` now uses one `SCRIPTS_DIR`
(the `scripts/` folder), so each resolved path is unchanged.

**The three core links.** `core.py` never imports `hook.py` or a part. It keeps three lists with a
register function each, and the handlers loop over them; the code still in `hook.py` registers
itself at import (the "core links" block just above `EVENTS`):

| List | Register | Who loops | What is registered today |
|---|---|---|---|
| `SESSION_START_HOOKS` | `register_session_start(consumer, fn)` | `inject` (strip subagent markers), `profile` (remote branch and git-identity notes) | `_strip_subagent_markers`, `_agent_branch_block`, `_agent_identity_block` |
| `PROMPT_HOOKS` | `register_prompt(fn)` | `scope`, on every message | the waiting-on-you note, the design loop note, the delegation clause, the parity clause |
| `POST_TOOL_HOOKS` | `register_post_tool(consumer, fn)` | `artifact` (page writing note), `promptran` (waiting-on-you update) | `_page_writing_note`, `_promptran_waiting_link` |

Two lists carry a consumer name because two core handlers read each of them. Registering the same
function name again replaces the earlier entry, because `verify.py` loads `hook.py` several times
in one process. A prompt link returns `(clause, note)`; a later link's note goes in front, which
keeps the old order (loop note, then waiting note).

**Left in `hook.py` for now, and why.** The scope delegation clause and its go-ahead pattern
(`SCOPE_DELEGATE_CLAUSE`) and the artifact page writing note (`_page_writing_note`,
`_PLANS_PAGE_RE`) need the delegation and writing parts, which do not exist yet; they sit in the
core-links block and move in those parts' steps. `_agent_branch_block` and `_agent_identity_block`
stay in the guard block (safe git). `SUBAGENT_SECTION_MARKER` stays with the delegation code.

**`verify.py`.** Five changes, no check removed or skipped (913 checks before and after): the
source-reading checks for silent `except` blocks and for deliverable state read `core.py` beside
`hook.py`; the inject fail-loud test patches `core._read_text` (the patch on `hook` would no longer
reach it); the one-shot `emit` failure test patches `core.emit` too; the declared-model check ends
its slice at `event_announce` since `_plugin_version` left; and the copied plugin root used by the
newest-rules tests now copies `house_rules/` as well. `_read_back_body` stays in `hook.py`, and its
patch at the credit check still takes effect (that test passes). `hooks.json` and `run.sh` are
unchanged. `core.py` compiles to a cached `.pyc` after the first run (`python -X importtime`:
14 ms the first time, 2.3 ms after).

### Step 2b: the safe git and docs modules (#358)

`hook.py` went from 7,248 to 4,633 lines; `house_rules/safe_git.py` has 1,888 lines and
`house_rules/docs.py` 717 (`core.py` grew from 1,853 to 2,057). Everything moved verbatim except
the three call sites listed under "Links" below. `hooks.json` and `run.sh` are unchanged, and the
`guard` refusal texts are byte-identical before and after (`git push --force`, a delete, a
Claude credit in a commit message, `reset --hard`, an empty payload, `guardgithub`, `guardwrite`).

**Moved into `safe_git.py`.** The guard block (patterns, `branch_ownership`, `_command_dir`,
`_never_blocked_*`, the delete and scratchpad checks, `event_guard`); `event_guardwrite`;
`event_branchnudge`; `event_prompttimer` with the whole waiting-on-you list (`_waiting_*`);
attribution (`_attribution_guard`, `_ATTRIBUTION_*`, `_read_back_body`, `event_creditcheck`);
`event_guardgithub` with `BRANCH_DENY`; the commit identity helpers (`_effective_author`,
`_is_claude_identity`, `AGENT_IDENTITY_FIX`); the commit-obligation helpers (`_dirty_paths`,
`_uncommitted_among`, `_branch_advice`, `_commit_note`); and `_agent_branch_block` and
`_agent_identity_block`, which register themselves on the core's session-start list at the foot of
the file, so the registration moved with them. `_GH_PREFIX` and `_PR_BODY_FILE_RE` moved too,
because the attribution check uses them; `hook.py` imports them back.

**Moved into `docs.py`.** `event_docstiers` with its tier lists, `_staged_docs_status` with its
`git add` patterns, and `event_harvest` with all its helpers. It registers `_staged_docs_status`
on a core list at the foot of the file.

**Moved into `core.py`** because two parts, or a part and the code still in `hook.py`, both read
them and a part may not import another part: `_WORD`, `_GIT`, `_GIT_COMMIT_RE`,
`_STATEMENT_SPLIT_RE`, `_COMMAND_VALUE_RE`, `_unquote_git_path`, `_parse_status_porcelain`,
`_git_dir`, `_common_git_dir`, `_ag` (with `AUTOSAVE_GIT_TIMEOUT` and `AUTOSAVE_BRANCH_PREFIX`),
`_field`, `_payload_cwd`, `_TOGGLE_OFF`, `_PROMPT_VALUE_RE` and `_is_relayed_prompt`. The step 2a
builder's inventory had no row for them; each is a single helper, not a block.

**Links.** Three more lists in `core.py`, the same shape as the 2a lists (a register function each,
same-name registration replaces, so `verify.py` loading `hook.py` many times is safe):

| List | Register | Who loops | What is registered today |
|---|---|---|---|
| `GUARD_ISSUE_HOOKS` | `register_guard_issue(fn)` | `event_guard`, after its own attribution check, first answer wins | `_author_guard`, `_issues_guard` (in `hook.py`) |
| `GITHUB_WRITE_HOOKS` | `register_github_write(fn)` | `event_guardgithub`, before its credit check | `_guardgithub_issue_checks` (in `hook.py`) |
| `DOCS_STATUS_HOOKS` | `register_docs_status(fn)` | `event_guard`, once per commit | `_staged_docs_status` (from `docs.py`) |

Three call sites changed: the `issue_hit = ... or _author_guard(...) or _issues_guard(...)` line in
`event_guard` became a loop over `GUARD_ISSUE_HOOKS`; the `_staged_docs_status(...)` call became
`_docs_status(...)`, which asks the first `DOCS_STATUS_HOOKS` entry (and says "the docs part is not
loaded" if none is registered); and the two checks at the top of `event_guardgithub` (the issue
sections check, #248, and the close guard, #363) moved into `_guardgithub_issue_checks` in
`hook.py`, which returns `True` where the old code did `return 0`. Order is unchanged.

**Left in `hook.py` for step 2c, and why.** `_author_guard` and `_issues_guard` and the close guard
(`_close_decide`, `_close_check`, `_close_forget`, `_close_gh_*`) with `event_closablemerge`: design
loop code, reached through the links above. The `_PR_BODY_FLAG_RE`, `_PR_LINK_RE`, `_PR_CLOSING_RE`
and `PR_ASK_NOTE` patterns: only `_issues_guard` uses them. `SCOPE_PARITY_CLAUSE`, `_PARITY_RE`,
`_parity_enabled` and the parity part of `event_handover`: the parity check is not a function of its
own, it is a few lines inside `event_handover` that also feed the visual check, and the same
patterns are read by `event_delegate` (delegation) and by `scope`; moving them to `docs.py` would
make delegation import the docs part. It waits for the end-of-reply split in 2c. The delegation,
writing and design-loop blocks, `handover` and `pagecheck`.

**`verify.py`.** 913 checks before and after, none removed or skipped. The source-reading checks
for `branch_ownership`, the guard bucket titles and the prompttimer block read `safe_git.py`; the
silent-`except` scan and the deliverable-state check read all four files; the prompttimer slice now
ends at a marker comment, `# End of the prompttimer block`, added after `event_prompttimer`. Five
in-process lines point at the module that owns the name: `_cc_mod.safe_git._read_back_body` (the
credit check test), `hook.safe_git.read_payload` (the guard and guardwrite crash tests),
`hook.docs.HARVEST_BUDGET_SECONDS` (the harvest budget test), and `emit` patched on `hook.docs` and
`hook.safe_git` beside `hook` and `core` (the one-shot failure test). The credit check patch was
broken on purpose once (patching `hook` instead): checks 296 and 297 failed, so the patch does take
effect where it is now.

### Step 2c: the delegation, design loop and writing modules, and the end-of-reply split (#359)

`hook.py` went from 4,633 to 332 lines. Line counts now: `hook.py` 332, `house_rules/core.py` 3,000
(was 2,057), `delegation.py` 1,656, `design_loop.py` 2,151, `writing.py` 340, `safe_git.py` 1,648
(was 1,888), `docs.py` 717, `session_triage.py` 1 (still empty until step 9, #347), `__init__.py` 1.
Code moved verbatim with its constants. The only edited lines are the call sites listed under "Links"
and "Dispatcher" below, and the four paths that were computed from `hook.py`'s `__file__`, which now
use `SCRIPTS_DIR`. `hooks.json` and `run.sh` are unchanged. Reference outputs of `handover` (a reply of
170 words with no page link, a Stop retry, no transcript), `pagecheck`, `issuelist`, `guard` and
`guardgithub` on an issue close with no evidence, `announce`, `verdict`, `closablemerge` (a merge and a
close), `delegate`, `scope`, `artifact` and `inject`, run through `run.sh` on a fixture repository before
and after, are byte-identical (18 payloads).

**Moved into `delegation.py`.** `event_delegate` with `DELEGATE_NOTE`, `SCOPE_DELEGATE_CLAUSE` and
`_SCOPE_GOAHEAD_RE`; `event_subagentrules` and the announce helpers; `event_announce`, `event_verdict`
and the audit report; `event_agentcap`; `event_subagentcommit` with its autosave and worktree helpers;
`event_autosave`, `event_commitgate`, `event_worktreesweep`, `event_audit` and `event_userpromptaudit`.
`SUBAGENT_SECTION_MARKER` went with them: core never uses it, only `_strip_subagent_markers`, which
registers itself on `SESSION_START_HOOKS` ("inject"). `_scope_delegate_link` registers on `PROMPT_HOOKS`.

**Moved into `design_loop.py`.** The issue workflow and the loop stages, labels and approvals;
`event_issuelist`; `_author_guard`, `_issues_guard`, the pull request body patterns and `PR_ASK_NOTE`;
`_guardgithub_issue_checks`; the close guard (`_close_*`), `event_closablemerge`, `_closable_merge_of` and
`_closed_issue_of`; `_loop_sweep_apply`; the end-of-reply checkpoints, the page-block counter and
`event_pagecheck`. It registers `_author_guard` and `_issues_guard` on `GUARD_ISSUE_HOOKS`,
`_guardgithub_issue_checks` on `GITHUB_WRITE_HOOKS` and `_scope_loop_link` (the design loop note) on
`PROMPT_HOOKS`, plus the four new lists below.

**Moved into `writing.py`.** The plain-summary, long-reply, visual and editor helpers, `_pages_changed_this_turn`,
`EDITOR_NOTE` and the note builders, and `_page_writing_note` with `_PLANS_PAGE_RE`, which registers on
`POST_TOOL_HOOKS` ("artifact").

**Moved into `core.py`** because a second part, or the dispatcher in `hook.py`, reads them. From
`hook.py`: the evidence, claim and not-checked helpers and the card check (`HANDOVER_NOTE`,
`_reply_needs_card_check`, `_claim_words`, `_impossibility_claims`, `_unreasoned_not_checked`,
`_evidence_note`, `_not_checked_note`); the transcript-turn readers (`_load_turn`,
`_records_since_last_user_message`, `_last_user_text`, `_turn_tool_uses`, `_tool_use_since_last_user_message`,
`_written_since_last_user_message`); the parity patterns and note (`_PARITY_RE`, `_PARITY_ACCOUNTED_RE`,
`SCOPE_PARITY_CLAUSE`, `_parity_enabled`, `_parity_report_note`); the page-link helpers (`_reply_links_page`,
`_outside_page_links`, `_html_paths`, `_inside`, `LONG_REPLY_WORDS` and their patterns);
`_clear_writing_enabled`, `_issues_enabled`, `_loop_enabled`, `_issues_locate`, `_GATED_TOOLS`,
`_AUDIT_WRITE_TOOLS`, `_AUDIT_COMMAND_TOOLS`, `_PLAN_VALUE_RE`, `_SESSION_ID_RE`, `_TRANSCRIPT_RE`; and the
shared writing checker import (`clarity`, `CLARITY_ERROR`). The step 2b inventory had no row for these;
the handover rows said "each check moves to its part", but the evidence and card checks belong to no part.
From `safe_git.py`, because the author and issue guards (design loop) and the delegation part use them:
the commit identity helpers (`_effective_author`, `_is_claude_identity`, `_git_author_ident` and their
patterns), `_command_dir`, `_decoded_command`, `_apply_assigns`, `_GH_PREFIX`, `_PR_BODY_FILE_RE`,
`_attribution_enabled`, `AGENT_IDENTITY_FIX`, `_commit_check_enabled`, `_uncommitted_among`, `_dirty_paths`,
`_branch_advice`, `owned_branch_prefixes`, `COMMIT_CHECK_TIMEOUT`, and the waiting-on-you file helpers
(`_waiting_path`, `_waiting_load`, `_waiting_save`, `_waiting_update`, `_waiting_session_note`), which
`event_issuelist` also reads. `safe_git.py` imports them back from core.

**Links.** Four new lists in `core.py`, the same shape as the 2a and 2b lists (a register function each; the
same name registered again replaces the earlier entry). They exist because the delegation part calls four
pieces of design loop code and neither part may import the other:

| List | Register | Who loops | What is registered today |
|---|---|---|---|
| `DELEGATE_NOTE_HOOKS` | `register_delegate_note(fn)` | `event_delegate`, appending each answer to the plan reminder | `_issues_plan_note` (design loop) |
| `SUBAGENT_NOTE_HOOKS` | `register_subagent_note(fn)` | `event_subagentrules`, joining each answer onto the subagent core | `_loop_helper_note` (design loop) |
| `TOOL_RECORD_HOOKS` | `register_tool_record(fn)` | `event_autosave`, adding each list of notes | `_post_tool_records` (design loop: `_issues_record`, then `_loop_record_labels`) |
| `EDIT_GATE_HOOKS` | `register_edit_gate(fn)` | `event_commitgate`, first; `True` means the call was answered | `_edit_gates` (design loop: `_loop_gate`, then `_issues_gate`) |

Four call sites changed, one per list. `_post_tool_records` and `_edit_gates` are the old inline lines
moved into the design loop part unchanged, so the order and the emitted messages are the same. The
existing lists have new registrants: `PROMPT_HOOKS` now gets the waiting-on-you link from `safe_git.py`
(with the `promptran` post-tool link), the design loop link from `design_loop.py` and the delegation
clause from `delegation.py`; the parity link is the last, registered by `hook.py` after it imports the
parts, so the clauses keep their old order. There is no list for the end-of-reply checks, because
`hook.py` is allowed to import every part and calls them directly.

**Dispatcher.** `event_handover` stays in `hook.py` and calls each check in the order it always ran:
`handover_evidence_check` (core), `handover_commit_check` (`safe_git.py`), then inside the transcript
scan `handover_turn_writes`, `handover_plain_check`, the inline parity check, `handover_page_editor_check`
and `handover_visual_check` (`writing.py`), then `handover_stop_lines` (`design_loop.py`),
`handover_long_reply` (`writing.py`), `handover_page_row`, `handover_checkpoints` or `handover_qa_retry`
(`design_loop.py`). Each is the old block moved into a function with its inputs as arguments and its
results returned. The emission is built exactly as before.

**Left in `hook.py`, and why.** `main()` and `EVENTS` (the entry point `run.sh` calls); `event_handover`,
the end-of-reply dispatcher, with the parity check inline, because it shares the transcript scan with
the visual and plain-summary checks and its patterns are read by delegation and scope, so they sit in
core while the check stays where the checks are combined; `_scope_parity_link` and its registration;
and the imports. Nothing else.

**`verify.py`.** 913 checks before and after, none removed or skipped, and the list of check titles is
identical to the step 2b run. Source-reading checks read the three new files too: the silent-`except`
scan reads all seven files, the deliverable-state check reads all seven, the declared-model check reads
`delegation.py`, and the "was created without the" label-advice check reads `design_loop.py`. In-process
lines point at the module that owns the name: `hook.delegation._audit_report`,
`_ig_mod.design_loop._open_issues_text` and `_loop_name`, `_ig_mod.core._is_relayed_prompt`,
`_lb_hook.design_loop._house_labels_note`, `_pc_hook.writing._pages_changed_this_turn`,
`_cc_mod.core._reply_links_page`, `_cc_mod.design_loop._check_page`, `_hk.design_loop._LOOP_DESIGN_RE` and
`_LOOP_PLAN_RE`; the one-shot `emit` failure test patches `emit` on the three new parts too.
`make_page.py` loads the stage patterns from `hook.py` by path, so it now reads them from
`design_loop` (a sweep page build and the QA page tests failed until it did).

**Found and fixed after the merge.** `harvest_scan.py` (broken since 2b) and `tools/measure_footprint.py`
(broken since 2a) read underscore names off the `hook` module (`hook._HARVEST_EXT_RE`,
`hook._SCOPE_COMMAND_HINT_RE`), and a star import does not carry underscore names. `harvest_scan.py` now
imports `house_rules.docs`; `measure_footprint.py` imports `house_rules.core`, or `hook` for an installed
plugin older than the package. Both ran clean on 2026-10-21. No check in `verify.py` runs either script;
the verify rework (#368) is where a check for them belongs.

### Step 2 result (#340, house-rules 2.71.0)

Steps 2a to 2c (#357, #358, #359) are merged on `AjsAgent/issue-281-fix`; 2d (#360) is the docs and the
version. `hooks.json` and `run.sh` never changed, and no handler's behaviour changed.

**Final line counts** (`wc -l`, 2026-10-21):

| File | Lines |
|---|---|
| `scripts/hook.py` | 332 |
| `scripts/house_rules/core.py` | 3,000 |
| `scripts/house_rules/delegation.py` | 1,656 |
| `scripts/house_rules/design_loop.py` | 2,151 |
| `scripts/house_rules/safe_git.py` | 1,648 |
| `scripts/house_rules/docs.py` | 717 |
| `scripts/house_rules/writing.py` | 340 |
| `scripts/house_rules/session_triage.py` | 1 (empty until step 9, #347) |
| `scripts/house_rules/__init__.py` | 1 |
| `scripts/verify.py` | 10,407 |

`hook.py` plus the package is 9,846 lines against 8,931 before step 2a; the difference is the module
docstrings, the imports, the link lists and the `handover_*` functions. The handler for each event is
listed in `docs/architecture.md`, "Which module owns each handler".

**Every link list in `core.py`** (ten; each has a `register_*` function, and registering the same function
name again replaces the earlier entry). Registrations from `grep -n 'core.register_'` over `hook.py` and the
package:

| List | Registrants |
|---|---|
| `SESSION_START_HOOKS` | `_strip_subagent_markers` for `inject` (`delegation.py`); `_agent_branch_block` and `_agent_identity_block` for `profile` (`safe_git.py`) |
| `PROMPT_HOOKS` | `_scope_waiting_link` (`safe_git.py`), `_scope_loop_link` (`design_loop.py`), `_scope_delegate_link` (`delegation.py`), `_scope_parity_link` (`hook.py`, registered last so the clauses keep their old order) |
| `POST_TOOL_HOOKS` | `_page_writing_note` for `artifact` (`writing.py`); `_promptran_waiting_link` for `promptran` (`safe_git.py`) |
| `GUARD_ISSUE_HOOKS` | `_author_guard`, `_issues_guard` (`design_loop.py`); `event_guard` loops over them |
| `GITHUB_WRITE_HOOKS` | `_guardgithub_issue_checks` (`design_loop.py`); `event_guardgithub` loops over it |
| `DOCS_STATUS_HOOKS` | `_staged_docs_status` (`docs.py`); `event_guard` asks the first entry |
| `DELEGATE_NOTE_HOOKS` | `_issues_plan_note` (`design_loop.py`); `event_delegate` loops |
| `SUBAGENT_NOTE_HOOKS` | `_loop_helper_note` (`design_loop.py`); `event_subagentrules` loops |
| `TOOL_RECORD_HOOKS` | `_post_tool_records` (`design_loop.py`); `event_autosave` loops |
| `EDIT_GATE_HOOKS` | `_edit_gates` (`design_loop.py`); `event_commitgate` loops, first |

**Every `verify.py` line changed across 2a to 2c**, from the diff of `verify.py` between `887183b` (before
2a) and `ba75a62` (after 2c); 913 checks before and after, none removed or skipped. Line numbers are those
at `ba75a62`. Where two steps touched one line, it is listed under the step that first changed it.

Step 2a (#357, commit `a396c6c`):

| Line | Change | Why |
|---|---|---|
| 49-50 | new `CORE` path | source-reading checks need to read `core.py` |
| 1397-1403 | inject fail-loud test patches `core._read_text` | the function moved; a patch on `hook` would no longer reach it |
| 2581 | silent-`except` scan reads `HOOK` and `CORE` | the rule is enforced over every file that holds handler code |
| 2635, 2643 | one-shot `emit` test also patches `core.emit` | `core` holds its own `emit` name |
| 4636 | deliverable-state check reads `HOOK` and `CORE` | same reason as the `except` scan |
| 5838-5839 | declared-model slice ends at `def event_announce(` | `_plugin_version` left `hook.py`, so the old end marker is gone |
| 7005-7006 | `_nr_make` copies `house_rules/` beside `hook.py` | the copied plugin root must import the package |

Step 2b (#358, commit `aa46dc1`):

| Line | Change | Why |
|---|---|---|
| 51-53 | new `SAFE_GIT` and `DOCS` paths | source-reading checks need those files |
| 1161 | `branch_ownership` source read from `SAFE_GIT` | the function moved there |
| 1180, 1295 | guard and guardwrite crash tests patch `hook.safe_git.read_payload` | both handlers moved there |
| 1994 | guard bucket titles read from `SAFE_GIT` | the bucket list moved there |
| 2448 | harvest budget test patches `hook.docs.HARVEST_BUDGET_SECONDS` | harvest moved to `docs.py` |
| 2581 | silent-`except` scan reads four files | two more files hold handler code |
| 2643 | one-shot `emit` test patches `hook.docs.emit` and `hook.safe_git.emit` | each part holds its own `emit` name |
| 3248 | credit check test replaces `_cc_mod.safe_git._read_back_body` | `event_creditcheck` moved there |
| 4636 | deliverable-state check reads four files | same as the `except` scan |
| 6295-6296 | prompttimer block read from `SAFE_GIT`, ending at `# End of the prompttimer block` | the old end marker, `# subagentcommit`, stayed behind; a marker comment was added after `event_prompttimer` |

Step 2c (#359, commits `4558e83` and `86039ae`):

| Line | Change | Why |
|---|---|---|
| 54-57 | new `DELEGATION`, `DESIGN_LOOP`, `WRITING` paths | source-reading checks need those files |
| 2581 | silent-`except` scan reads all seven files | the rule must cover every file that holds handler code |
| 2644 | one-shot `emit` test also patches `hook.delegation.emit`, `hook.design_loop.emit`, `hook.writing.emit` | each part holds its own `emit` name |
| 3295 | `hook.delegation._audit_report` | the audit report moved to delegation |
| 4391 | `_ig_mod.design_loop._open_issues_text` | the function moved to the design loop |
| 4636 | deliverable-state check reads all seven files | same as the `except` scan |
| 5838-5839 | declared-model check reads `DELEGATION`; `86039ae` restored one space in the slice line | `_declared` and `event_announce` moved there |
| 8730 | label-advice source read from `DESIGN_LOOP` | the issue workflow moved there |
| 8758-8761 | `_ig_mod.core._is_relayed_prompt` (four uses) | the helper is in core |
| 8781, 8945-8946 | `design_loop._loop_name` (three lines) | the helper moved to the design loop |
| 9480-9482 | `_lb_hook.design_loop._house_labels_note` (three uses) | the helper moved to the design loop |
| 9669, 9700 | `writing._pages_changed_this_turn` (two uses) | the helper moved to writing |
| 9797-9809 | `_cc_mod.core._reply_links_page` (six uses), `_cc_mod.design_loop._check_page` | the helpers sit in core and the design loop |
| 10152 | `_hk.design_loop._LOOP_DESIGN_RE`, `_LOOP_PLAN_RE` | the stage patterns moved to the design loop |

2.71.0 changed two more lines, 4445 and 4448 (the plugin version the issues check expects).

**Timing.** The after-step-2 `verify.py` and hook-start timings are in `docs/4-systems/verify-suites.md`,
"Planned: the verify.py rework".

## Steps 3 to 7: one feature (#381)

Design approved 2026-10-24 ("Design approved: restructure steps 3 to 7"); design page
`docs/plans/2026-10-21-restructure-steps-3-7.html`, build plan `docs/plans/2026-10-24-restructure-steps-3-7-plan.html`.
Built in order: step 3 #341 (settings and identity), step 4 #349 (safe git), step 5 #343 (design loop and pages),
step 6 #344 (writing, evidence and rewrite rules), step 7 #345 (helper agents). One QA page and one release,
#382, version 2.74.0. Steps 4 and 7 read the agent name and branch prefix from step 3's settings.


**Built: step 3 (#341).** Two settings, `agent_name` and `extra_owned_prefixes`, live in a new leaf module,
`scripts/house_rules/settings.py`, with a command-line front end, `scripts/settings.py` (`set`, `get`, `show`;
it prints what it saved and where). *Settings file:* `<config dir>/house-rules/settings.json`, where the config
dir is `$CLAUDE_CONFIG_DIR` or `~/.claude`, the same place `core.py` already reads per-user Claude state from, so
it sits outside every repo and follows the machine (`HOUSE_RULES_SETTINGS_FILE` moves it; the checks use that).
*Read order,* first value wins: the environment (`HOUSE_RULES_AGENT_NAME`, `HOUSE_RULES_OWNED_BRANCHES`), then the
settings file, then `/plugin configure`, which is skipped because `plugin.json` has no `userConfig`. An empty
`extra_owned_prefixes` counts as set; an empty `agent_name` does not. No setting has an assumed default. *The gate:*
while a setting is unset the guard (for Bash) and a new no-matcher `settingsgate` hook (every other tool) refuse
the call, naming each missing setting and its `settings.py set` command; the one thing let through is a lone
`python <plugin>/scripts/settings.py set|get|show` (no `;`, `&`, `|`, `$`, backticks or redirects outside quotes,
and only this plugin's own script). At session start, `profile` adds a note asking the model to ask the user, with
the suggestion `<GitHub login lowercased>sAgent` from `gh api user`, else the git remote's owner, saying which.
*Identity strings now from settings:* the credit lines (`Committed by <agent_name>`, `Opened by <agent_name>`),
the agent branch prefix `<agent_name>/` (the cloud `claude/` move, the branch advice, the refusal texts), the
owned-branch test (own prefix, the extras, and cloud-session `ccr-`), the commit author name, and the git
identity fix text (its email is read from `git config user.email`, shown as `<your own git email>` when that is
Claude's). *Left literal, in `settings.py` only:* the GitHub label names (`AjsAgent created this`,
`AjsAgent completed this`, `Claude created this`) and their descriptions, because existing labels carry them and
renaming would orphan every issue that has one; the default repo owner and the plugin.json address. The rules
text in `rules/` and the docs still name "aj's agent" and `AjsAgent/`; they are prose, not code, and are not
part of this step. The checks run with `HOUSE_RULES_AGENT_NAME=testsAgent` (set in `checks/common.py`) and assert
values derived from it.

**Built: step 4 (#349).** *Deletes:* a delete of a committed, unchanged file (git can restore it) is allowed
only on a branch that is the agent's own (own prefix, the extras, `ccr-`, helper `worktree-agent-` branches). On
any other branch, `main` included, it is refused naming the branch, with the words "not a branch of the agent's
own", and the safe way (`_to_delete/` or a new branch under the agent prefix). Uncommitted, changed, never-committed,
glob and recursive deletes are refused as before, and the scratchpad exemption is unchanged. *Identity:* the
automatic work-in-progress commits (`_wip_message`, `_wip_commit` in `delegation.py`) now end with the derived
`Committed by <agent_name>` line, carry no Claude `Co-Authored-By` or `Claude-Session` line, and are authored as
`<agent_name>` with the user's own git email (`house-rules@localhost` only when git has none). The attribution
and credit checks needed no new code: they refuse Claude's lines and accept anything else, so they already accept
exactly the derived `Committed by` and `Opened by` lines; a new check pins that. *Snapshot branches:* the
`worktreesweep` hook (every prompt) now also deletes an autosave snapshot, locally and on origin, once its
helper's work is merged. There is no recorded merge event to trust, so the signal is what git can prove: the
snapshot holds nothing a commit lacks (its tree equals its parent's) and that parent is contained in a branch that
is not a helper branch. A snapshot with unsaved work, or whose commits sit only on helper branches, is kept. It
cannot tell "merged" from "never started" (a helper with no commits also matches), which loses nothing because
the snapshot then holds nothing. The autosave push still uses `--force`; that is step 7 (#345). *`run.sh`:* with no
working Python the `settingsgate` event now fails closed (3 lines on stderr, exit 2), as `guard` does, instead of
doing nothing. Seven checks were added to `checks/safe_git.py` (all prefixed `#349`).

**Built: step 5 (#343).** *Sub-features:* when a `gh issue create` or the GitHub tool's `issue_write` create has
the words "Part of" and an issue number in its body, the post-tool hook (`_sub_issue_note` in `design_loop.py`) adds a
reminder to also link the new issue as a sub-issue of the parent with `mcp__github__sub_issue_write` or
`gh api .../sub_issues`. It is a note, not a refusal, because the link can only be made after the create. A
sub-feature's QA pass already records only its own issues (#375); a check now pins that. Nothing beyond the reminder
was built for "finds its parent": the decisions say only that the link is GitHub's sub-issue link. *Decisions-log
entry:* before, an unchanged log counted every time (#327), so an entry never written was never noticed. Now the first
approval with no new entry still counts and sets `log_owed` in the stage file; the next approval with the log still
unchanged is refused ("never written"), and a changed log clears `log_owed`. One older per-feature check needed a log
write between its two approvals. *Cloud pages:* in a session with `CLAUDE_CODE_REMOTE` set, the end-of-reply page
check also needs a `https://claude.ai/artifact/...` or `https://claude.ai/code/artifact/...` link; a local `.html`
alone is blocked with a message naming the Artifact tool's publish step. A local session is unchanged. The page
builder is untouched. Checks are in `checks/design_loop.py`, prefixed "restructure step 5 (#343)".

**Built: step 6 (#344).** *Wholesale rewrite by Edit:* the `guardwrite` hook (matcher now `Write|Edit|MultiEdit`)
also refuses an Edit or MultiEdit that replaces more than half the file's lines in one call. Replaced lines are
old_string's line count (at least 1), times its occurrences for `replace_all`, summed over a MultiEdit's edits;
refused when `replaced * 2 > file lines` (51 of 100 refused, 50 and 49 pass). The refusal and the approval
mechanism are the Write guard's: a deny naming the rule, with "needs aj's approval by name". The exemption is the
Write guard's own and nothing more: a file I made myself (untracked, inside the project) is never refused. There
is no `docs/` or `.md` exemption on the Write guard, so none was added. *Skipping a check:* the end-of-reply
check now adds a note (same single emission, so it reports and lets the reply stand on the retry, like the other
reply notes) when a sentence says a check was skipped or not run and gives time, cost or an unreachable
machine or account as the reason, and the reply asks aj no question about skipping or running it. The note
quotes aj's rule. *Unasked fixes:* a note, not a block, when the reply says "while I was there/at it", "I also
fixed/patched/cleaned up" or "unrelated fix/change" and names no `#number`. Both live in
`house_rules/writing.py` (`skipped_check_reasons`, `unasked_fix_phrases`); a scan of 2,425 string fixtures in
`checks/` found no false positive. Checks are prefixed "(#344)" in `checks/safe_git.py` and `checks/writing.py`.

**Built: step 7 (#345).** *Helper instructions follow the grilling answers (round 1, answers 4, 5, 12, 13).*
`agents/builder.md`, `agents/reviewer.md` and the subagent rules text that `event_subagentrules` injects
(`SUBAGENT_MANDATE`) now say what `rules/detail/green-suite.md` says: while working run the parts the change
touched (`verify.py --changed` here), at the end the touched parts twice and everything else once. A question
only aj can answer stops the helper and goes in its final report under a `QUESTION FOR AJ` heading, for the
parent to ask. The builder's 6-line report cap no longer covers RESULT and FAIL lines: every one is quoted
verbatim. The parent-side audit (`_audit_report`) never checked report length, so it needed no change.
*Autosave:* the local snapshot ref keeps its one name, `refs/house-rules/autosave/<branch>`. Each push to
origin now goes to a fresh ref, `refs/house-rules/autosave/<branch>-s<UTC YYYYMMDDTHHMMSSZ>-<sha7>`, with no
`--force`. `_autosave_cleanup` and `_autosave_merged_sweep` list origin with `ls-remote` (the legacy fixed name
plus every `-s...` name) and delete all of them in one push. The worktree sweep is unchanged and a check now
proves it commits only inside the helper's own worktree. Checks are titled "(#345)" in `checks/delegation.py`.
