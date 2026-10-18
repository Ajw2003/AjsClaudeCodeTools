# Decisions

The paper trail: what was decided, when, why, what alternatives were rejected, and what it
superseded. Append-mostly — newest entry at the top. An entry is never rewritten or deleted; the
one allowed edit to an existing entry is flipping its `Status` line to `Superseded`, with a
pointer, when a later entry replaces it.

---

## 2026-10-18 - #322 writing check loop: design and build plan

**Context.** During the cloud QA test for #315 (credit read-back), the end-of-reply checks looped: each
report-only note went back to the model as Stop `additionalContext`, which continues the turn, and
`event_handover` emits it on the retry (`stop_hook_active` true) as well. Replies of one line kept setting off
the page checkpoint until Claude Code's cap of 9 consecutive blocks ended the turn. The editor checkpoint
also forced a whole subagent run for one 386-word chat reply. aj opened #322 for it ("fix the writing check
asap as it is bleeding tokens on retries, and toggle the editor off by default").

**Decision.** Design approved as "Design approved: #322 writing check loop". The build plan is four
sub-issues, each with its own `verify.py` case: the retry only reports to aj (#323), the writing check
leaves chat replies alone and stays on pages and new issues (#324), the editor checkpoint is pages-only
unless `HOUSE_RULES_EDITOR=on` (#325), and the page checkpoint's still-owed note is said once per message
of aj's (#326). The plan is in `docs/4-systems/clear-writing.md`, "Planned: stop the end-of-reply loop".

**Rejected.** Keeping `HOUSE_RULES_CLEAR_WRITING=off` as the fix: it also turns off the page and issue
checks, and setting it mid-session did not reach hooks already running.

**Status.** Standing.

## 2026-10-16 - QA passed: plugin restructure 2.68.1 patch

**Context.** The 2.68.1 patch (#307 to #311) was built on `ccr-7dcf4ee2-zp3mm8`, pull request #312 (house-rules
2.68.1: unblock the design loop before the restructure), QA page `docs/plans/2026-10-16-patch-2-68-1-qa.html`.
`verify.py` passed 839 checks twice, and two nested sessions with the patched plugin confirmed the double approval
and the page report.

**Decision.** aj passed QA ("QA passed: plugin restructure 2.68.1 patch"). The design loop refused to record it,
because the parent issue #306 (restructure into a shared core with project boundaries and six optional
sub-plugins) is rightly still `in progress`: the loop can't pass QA on one step of a larger feature. The patch
issues keep `needs review` until aj closes them, and #306 is not relabelled to force the stage. How the loop
should track a multi-step feature is added to the grilling session's list.

**Status.** Standing.

## 2026-10-16 - Plugin restructure: the build plan for the 2.68.1 patch

**Context.** aj approved the restructure direction (entry below). The systems document is
`docs/4-systems/plugin-restructure.md`. The parent issue is #306 (restructure into a shared core with
project boundaries and six optional sub-plugins).

**Decision.** The patch is built first, on an `AjsAgent/` branch, one `@house-rules:builder` helper at a
time in a worktree, with `verify.py` run after each step. Each step reproduces its incident in `verify.py`
before the fix. The order is:
1. #307 (the design loop reads every approval in a message, and a design approval sets the feature name).
2. #308 (the design loop records only issues created in its own repo).
3. #309 (four checks report instead of blocking, and the page builder accepts any approval line).
4. #310 (a blocked page stays owed across retries), after #309 because both change the page checkpoint.
5. #311 (release the patch with its version, docs and QA page).

One pull request into `main` says `Refs #303` and `Refs #306`. The `verify.py` baseline before the build is
"RESULT: PASS - all 832 checks passed" (run on 2026-10-16). The grilling session on the 28 rule
contradictions starts after the patch is merged, and the restructure's own steps become sub-issues of #306
after it.

**Status.** Standing.

## 2026-10-16 - Design approved: plugin restructure direction

**Context.** A full audit of house-rules 2.68.0, asked for before restructuring the plugin so it
works for anyone, not only aj's accounts. The findings are in `docs/audits/2026-10-16-plugin-audit/`
(files 1 to 6, each finding cited with `file:line` on both sides), summarised in its `README.md`. The
page aj approved is `docs/plans/2026-10-16-plugin-audit.html`, built from
`docs/plans/2026-10-16-plugin-audit-revised.page.json`. It was revised for ten recent issues:
#287 (Agent name, credit and branch prefix are configurable, not hard-coded to AJ), #296 (Design-loop
approvals are dropped silently when the session folder isn't a git repo), #297 to #300 (After every pull
request, a check makes sure it says how to test it and what's next), #301 (a session finishes its own
task; other work becomes an issue in its own repo), #302 (proposal pages need before-and-after visuals
for any visible change), #303 (the design loop is broken and blocks sessions; switch off the conflicting
checks now) and #304 (a two-helper tool that cleans a session transcript, then files issues from it).

**Decision.** aj approved the direction with three picks ("1A 2A 3A"):
1. **Core identity: safe multi-project work.** aj's own goal, from #304: safe work on several projects
   at once, each session in its own context, observations about other projects captured as issues in
   those projects, and transcripts usable as evidence without leaking secrets. The default install is
   a shared core with project boundaries, plus the Safe git and Session triage sub-plugins. Design loop,
   Writing, Delegation and Docs are optional sub-plugins on the same core.
2. **A 2.68.1 patch ships first, scoped to #303.** It fixes the two approval bugs (every approval phrase
   in a message is read; a design approval always sets the feature name) and records only issues created
   in the repo that owns the stage file. Four checks switch to report-only: the shell-write refusal while
   code is locked, the re-creation (parity) check, the page checkpoint, and the bare-reference writing
   check. The page builder accepts any approval line. The page-dodge fix (a shorter retry must not clear
   the page checkpoint) rides in the same patch.
3. **The after-pull-request checks (#297) are built inside the Design loop sub-plugin** during the
   restructure, not on today's `hook.py`. Their agent-name step uses `userConfig`, not an environment
   variable set by aj's setup scripts.

The restructure also: moves identity into Claude Code's `userConfig` (defaulting to the git name, per
#287); replaces the self-updater with marketplace `autoUpdate` and `/reload-plugins`; keeps plugin-wide
state in `CLAUDE_PLUGIN_DATA`; replaces the issue workflow with #301's five-field template; replaces
`verify.py` with module tests plus a few end-to-end runs per hook event; and loads each rule from one
source file. The 28 rule contradictions are settled one by one in a grilling session before the
restructure is built.

**Alternatives rejected.** Guardrails only as the core identity (it leaves out the project boundaries
#301, #296 and #303 ask for); one plugin split into internal modules (users still install all or
nothing); switching the whole design loop off until the restructure (projects mid-feature lose their
gate); fixing all eight #303 incidents properly now (the restructure rewrites the same code); building
#297 now (built twice).

**Supersedes.** The unapproved build plan `docs/plans/2026-10-16-version-notice-and-page-dodge-plan.html`
(an account-wide git-ref marker for re-injecting rules after an update). It is dropped: another person's
install has no shared place for the marker, and `/reload-plugins` covers each session. Its page-dodge
half moves into the 2.68.1 patch.

**Status.** Standing.

## 2026-10-15 - Guards audit: the build plan

**Context.** aj approved the design ("Design approved: guards audit"). The systems document is
`docs/4-systems/guards.md`.

**Decision.** The build runs on `AjsAgent/issue-281-fix`, one `@house-rules:builder` helper at a time in a
worktree, with `verify.py` run after each. The order is:
1. #289 (Never-blocked list).
2. #290 (Prompt timer: each prompt waits on its own, with no chain of refusals).
3. #291 (Destructive actions are refused with the safe way named, and deletes are narrowed).
4. #292 (Remove the background-work guard and the "Never hide work" rule).
5. #293 (Enforced workflow checks name their exact fix when they refuse).
6. #286 (Page copy box must hold the full reply the design gate accepts).
7. #287 (Agent name, credit and branch prefix are configurable, not hard-coded to AJ).
8. #288 (Page cards clip long words on a phone, and the visual check misses it).
9. #282 to #284, the automatic-pages issues, from `docs/plans/page-must-be-automatic-build-plan.page.json`.
   The stop limit for #283 is three blocks, then the helper reports.

One pull request into `main` says `Refs #281` and `Refs #285`, and it comes with a QA page. The `verify.py`
baseline before the build was "RESULT: PASS - all 785 checks passed".

**Status.** Standing.

## 2026-10-15 - Guards audit: the design aj approved

**Context.** Issue #285 (Guards block only unrecoverable actions). The audit page is
`docs/plans/guards-audit.html`, built from `docs/plans/guards-audit.page.json`. aj's test: a guard stops me only
for data loss with no way back, or for a change to someone else's work.

**Decision.** aj approved the audit's ten cards:
- **Never blocked:** routine commits and pushes on an `AjsAgent/` or helper working-copy branch, publishing a
  page built by `make_page.py`, and edits to files I created inside the folder I was given. Checked before every
  guard, the page check and the prompt timer.
- **Refuse, with the safe way named:** nine destructive actions (push or commit to `main`; commit, merge,
  rebase, cherry-pick, revert, am or apply on a branch not confirmed mine; force-push or `--all`/`--mirror`;
  branch deletes; `git clean`; `filter-branch`; reset, `checkout --` or restore over uncommitted work; stash
  drop or clear; truncating a file). aj is asked only when no safe way exists and a source proving it is cited.
- **Deletes narrowed:** refused only when recursive, or when the file has uncommitted changes or was never
  committed; the refusal names `_to_delete/`.
- **Dropped:** the background-work guard (nohup, trailing `&`, Start-Process, background jobs, tail or head on a
  wait, process kills) and the "Never hide work" rule with its 5-minute stall-check reminder.
- **Enforced with the fix named:** a page not built by `make_page.py`, a Claude credit or `claude/` branch on
  GitHub, an issue missing sections, a third helper or a helper's own helper, and a whole-file overwrite of a
  file I did not create.
- **Prompt timer:** each prompt waits on its own; no chain of refusals after one unanswered prompt.
- **Copy box (#286), agent name (#287), phone check (#288):** as on the page's cards.
- **Kept:** the design-loop lock stays blocking (aj's pick, 15 October, 15:04).

**Status.** Standing.

---

## 2026-10-15 - Build plan approved: Label setup

**Context.** Build plan `docs/plans/label-setup-build-plan.html`, five sub-issues of #274 (The plugin
creates the house labels a repo is missing), #275 to #279. aj replied "Build plan approved: Label setup
build plan", with no answers to the page's four choices.

**Decision.** With no answers given, the page's marked suggestions stand for the three choices that
change nothing outside this repo:
- **1A, where the code lives:** a new `scripts/labels.py`, shared by the hook and the command.
- **2A, when the hook creates labels:** at all three moments: design approved, the issue note, and
  before a label refusal.
- **3A, the label record:** `_label_changes` also records the REST forms.

Choice 4 (creating a private scratch repo, `Ajw2003/label-setup-scratch`, for the real "no labels
yet" run) creates something on aj's account, so it waits for aj's own answer before #279 (Prove it on
a real repo, bump the version and update the docs) runs that step.

**Changed since the plan.** `main` moved to plugin 2.67.1 (the enforced QA stage, #264, and the page
charset fix, #280) before the build started, and was merged into `AjsAgent/label-setup`. So this
build ships as 2.68.0, not 2.67.0. The lines the plan cites moved: `LOOP_WORKING` is now
`scripts/hook.py:5238`, `_loop_labels` `:5259`, `_loop_label_refusal` `:5315`, `_label_changes`
`:5617`, and the two `gh issue edit` notes `:5729` and `:5776`; `ISSUE_NOTE` (`:4814`) and
`_issues_plan_note` (`:4890`) did not move.

**Status.** Standing. Stage Build.

---

## 2026-10-15 - Design approved: Label setup (approved in Ajw2003/Unblocked, built here)

**Context.** A new repo has none of the three house labels the issue workflow and the design loop
depend on, so work stalls until someone creates them by hand. The GitHub tool in a cloud session
cannot create a label, and `gh issue edit --add-label` fails there because it goes through GitHub's
GraphQL API, which answers 403. aj approved the design on 2026-10-15 in a session on
`Ajw2003/Unblocked`: "Design approved: Label setup: 1A 2A 3*", with "handoff" as their own answer to
question 3. That repo holds the decision (`docs/6-decisions/Decisions.md`, entry "Label setup moves
into the house-rules plugin, built by a handed-off session"), the design page
(`docs/plans/label-tool.html`) and the handoff brief (`docs/plans/label-setup-handoff.md`). This
session picked up the handoff from a background-task notice, not from a message aj typed here.

**Decision.**
- **Where:** inside the house-rules plugin, not a standalone script or a GitHub Action.
- **Which labels:** only `AjsAgent created this` (`5b6b7a`, "Opened by AJ's agent"), `in progress`
  (`FBCA04`, "AJ's agent is working on it") and `needs review` (`0E8A16`, "Waiting on aj"). GitHub's
  own category labels are left alone.
- **Behaviour:** when the plugin needs a house label the repo lacks, it creates it with
  `gh label create` and says so. A `/house-rules:labels` command does the same on demand. An existing
  label is never changed or deleted, even one with a different colour or description.
- **Advice:** the plugin's `gh issue edit --add-label` advice moves to the REST form
  (`gh api repos/<owner>/<repo>/issues/<n>/labels`), which works in cloud sessions.

**Checked against this repo.** The handoff cites `scripts/hook.py` lines at commit `e879981`; `main`
is still at `e879981`, and all ten cited lines (4809, 4814, 4820, 5197, 5201, 5208, 5218, 5244, 5268,
5594) say what the handoff says. Two things the handoff does not mention: the `gh issue edit` advice
appears in five places, not one (`scripts/hook.py:4820`, `:5661`, `:5711`, and
`rules/detail/issue-workflow.md:14` and `:19`). And the label recorder (`_label_changes`,
`scripts/hook.py:5563`) only understands `gh issue edit` and the GitHub tool, so a REST label change
would go unrecorded. The build plan covers both.

**Status.** Standing. Stage Plan. Build plan: `docs/plans/label-setup-build-plan.html`.

---

## 2026-10-15 - QA passed: enforced QA stage

**Context.** QA page `docs/plans/qa-stage-qa.html`, built by `make_page.py`'s new QA mode. All seven sub-issues of
#264 (Enforce the QA stage), #265 to #271, are built as plugin 2.67.0. The real run is recorded in
`docs/generated/2026-10-15-qa-stage-real-run.md`.

**Decision.** aj answered "QA passed: enforced QA stage". There were two fixes beyond the plan, both found while
testing: a QA page linked only in a retry reply is now recorded, and a QA page with no choices now renders. The
label check's reply loop (#238) was left out of this build.

**Status.** Standing. The issues keep `needs review` until aj closes them.

## 2026-10-15 - Build plan approved: enforced QA stage

**Context.** `docs/plans/qa-stage-plan.html`, seven sub-issues of #264 (Enforce the QA stage), #265 to #271.

**Decision.** aj approved with "1A 2A":
- **1A, where the stage lives:** a committed file on the branch, `.claude/house-rules-loop.json`, that only the
  hook may change; Write or Edit of it is refused. Rejected: staying in `.git` (lost in every new cloud
  container) and a GitHub label (the hook cannot read GitHub in a cloud session, where `gh` is not logged in).
- **2A, who builds:** `@house-rules:builder` helpers, one step at a time, because five of the seven steps edit
  `hook.py`.

**Status.** Standing.

## 2026-10-15 - Design approved: enforced QA stage

**Context.** Issue #264 (Enforce the QA stage). Pull request #263 (Handover pages and checkpoints) was opened and
every issue swapped to `needs review` with no QA page; aj had to ask for one. During that QA an Edit to
`templates/handover-page.html` also went through, and the writing note made a whole reply post twice.

**Decision.** aj approved `docs/plans/qa-stage-design.html` with "1A 2A 3A 4A":
- **1A, when QA starts:** a pull request opening for the feature, or every issue swapped to `needs review`,
  whichever comes first.
- **2A, how the QA page is detected:** `make_page.py` records the built QA page in the stage file, and the reply
  links it.
- **3A, the file table's numbers:** the builder counts added and removed lines from git against the base branch;
  the content file supplies only the plan's estimate and a note.
- **4A, the duplicated reply:** the writing note and the checkpoint reason ask for the corrected sentences only.
  Blocking was rejected because a Stop hook fires after aj has already seen the reply.

Found after the design was published: the stage file (`.git/house-rules-loop.json`) does not survive a new cloud
session. This session's fresh container had none, although the previous session moved through every stage. The
build plan covers it. Also found: the approval parser took the feature name as "enforced", because
"QA stage: 1A" looked like a pasted answer; the build plan covers that too.

**Status.** Standing.

## 2026-10-15 - The end-of-reply check blocks once, from a checkpoint table

**Context.** aj approved "Design approved: handover pages and checkpoints" (below), which reverses the
"never `decision: "block"`" rule for `Stop` recorded in `docs/architecture.md` and the 2026-09-23 entry
"handover narrows to shell fences" (now marked Superseded in part).

**Decision.** #256 built it. `hook.py` has a `CHECKPOINTS` table of (moment, rule name, check, "block" or
"remind"). Five rows at "reply ends" block: page, editor, evidence, commit, plain summary. A miss returns
`decision: "block"` with each missed rule's one-line text and exact fix, once; on the retry
(`stop_hook_active`) it only reports, as `subagentcommit` does on `SubagentStop`. "no page" in aj's own
genuine message lets one reply past the page and editor rows; a helper's hand-back never counts.
`HOUSE_RULES_LOOP=off` turns all rows off. Any error fails open with a `systemMessage`.

---

## 2026-10-15 - QA passed: handover pages and checkpoints

**Status.** aj: "QA passed: handover pages and checkpoints". Stage Done. QA page: `docs/plans/handover-pages-qa.html`.
Pull request #263 waits on aj's merge. Issues stay `needs review` until aj closes them. Handoff: `docs/handoff-2026-10-15.md`.

## 2026-10-15 - Guard fixes: aj's answers

**Status.** Answered: "Guard fixes answers: 1A 2A 3A 4A", on `docs/plans/guard-fixes.html`, from the nine
refusals in `docs/guard-friction-audit-2026-10-15.md`. The answers:
- **Unclear command, nobody to ask:** refuse, but name the plain form that would pass. "Do not retry" stays
  only for deletes, kills and pushes to the main branch.
- **Scratch folder:** deleting inside this session's scratchpad doesn't ask.
- **Code lock:** also covers source files written by a Bash script.
- **Worktrees:** fixed in this build, so the stage is shared through the repo's common git folder.

Built as two sub-issues of #251, before the pull request. Each one replays today's real refusals as tests.

## 2026-10-15 - Test method for the PlunderSpell regeneration: after the merge

**Status.** Answered: "Test method: 1B", on `docs/plans/plunderspell-test-method.html`, which was the first page
built by the page builder. A brand-new cloud session installs house-rules from main, so it can't load this
branch. The order is now: guard fixes, aj's QA on the pull request, merge, then a genuinely new PlunderSpell
session for #259. This replaces build plan choice 1B ("install from this branch before it is merged").

## 2026-10-15 - Before the pull request: guards must not stall an approved, autonomous build

**Context.** A routine commit of finished, tested work on this session's own branch was refused while aj was
away. The guard couldn't follow `git -C $G`, and its rule then said not to retry, which stopped the build until
aj came back. aj: "a routine commit should never ever be something that kills a loop and requires my
intervention… gates that enforce certain stages of planning vs execution and that the autonomous ones can run
autonomously without intervention unless required."

**Decision.** Finish the eight steps of #251 first. Then, before the pull request, audit every guard or hook
refusal of an approved, routine action in this session, and fix them so none recurs. The fixes go to aj as a
proposal page first, because what a guard allows is a design call. The audit list is
`docs/guard-friction-audit-2026-10-15.md`.

## 2026-10-15 - Project style file: aj's answers

**Status.** Answered: "Style file answers: 1A 2A 3A 4A 5A", on `docs/plans/project-style-file.html`. #255 is built
to these answers:
- **Colour roles:** each page role (you act, accent, blocking, done) maps to one of the project's colours. The
  rule "orange means you act" becomes "one colour means you act in each project". The template's default stays
  orange.
- **Contents:** colours, roles, reserved colours, themes, fonts, shape, labels, icons, pictures and picture
  folders. The worked example is `docs/plans/page-style/plunderspell.page-style.json`.
- **Drafting:** the builder drafts the file from the project's design system or style guide, and aj approves it.
- **No style file:** aj is asked once per project. Choosing the quick option writes a one-line file that says to
  use the defaults.
- **Themes:** each project decides. PlunderSpell is dark only.

**Also received in the same message, for PlunderSpell (not this repo):** aj's picks on the Wick and Ophan plan,
"PlunderSpell Build plan approved: fear entities, picks: 1* 2C 3* 4B 5A 6A 7*":
- **Choice 1 (own answer):** quota first, then the Wick, then the Ophan. The quota and the Wick change the game
  loop most, and the Ophan is the face of the quota.
- **Choice 3 (own answer):** a catch lights the player ablaze, which prevents a revive, and they respawn when the
  team returns home.
- **Choice 7 (own answer):** as originally proposed, the player is spared when carrying the artifacts it wants,
  and killed once it finds them empty-handed.

This session can't act on PlunderSpell (read-only). They're kept here for #259, which rebuilds that page.

## 2026-10-15 - Build plan approved: handover pages and checkpoints

**Status.** Approved: "Build plan approved: handover pages and checkpoints: 1B 2A 3A". The answers:
- **Install for the plunderspell test (1B):** the fresh session installs house-rules from this branch before
  it is merged.
- **Helper-report fix (2A):** in this build, as #253.
- **No browser (3A):** the builder writes the page and says the visual check didn't run, and why.

**Added by aj with the approval:** study PlunderSpell's style guide to decide what `docs/page-style.json`
holds. aj expects fonts and icons, and possibly more. When a project has no style file, the session offers
two options: create one, or use the defaults for speed. The style file's contents come back to aj as a
proposal page before #255 (style file and page builder) is built. #253 (helper reports) and #254 (template
picture slots) don't depend on it and start now.

## 2026-10-15 - Design approved: handover pages and checkpoints

**Status.** Approved: "Design approved: handover pages and checkpoints: 1A 2A 3A 4A 5A 6A 7B 8A". The answers:
- **Pictures:** anywhere they help: In short steps, Changes items and choice options. Changed items get a
  before-and-after compare.
- **Project style:** lives in `docs/page-style.json`, read only by the page builder.
- **How visual:** set in the style file: required for art and visual changes, optional, or off. The builder
  enforces it.
- **How a page is made:** by the page builder, which stamps a mark the page check looks for.
- **What needs a page:** choices, a plan, or a reply over 200 words.
- **On a miss:** block once, then only report on the retry.
- **Scope (7B):** hard checkpoints for the page rule and the editor helper, and also for the evidence,
  commit and plain-summary checks.
- **Escape:** "no page" in aj's message lets one reply through. `HOUSE_RULES_LOOP=off` still turns it all off.

**Added by aj with the approval:** once built, regenerate the plunderspell Wick and Ophan page with the new
tools, exactly as a new session would, to test the formula.

## 2026-10-15 - Design revised: handover pages and checkpoints (second version)

**Status.** Proposed, waiting on "Design approved: handover pages and checkpoints" with eight choices.
This replaces the first version's reply phrase below.

**Context.** aj agreed with the direction ("yes") but asked for changes before the template is enforced:
slots for screenshots and images, and a way for a project's own style guide to shape the page, because "some
projects will require more visual than others". The evidence is plunderspell's rewrite of its Wick and Ophan
plan into the template. The first version had an Editor render of both creatures. The template version has
no picture, because `templates/handover-page.html` has no way to show one.

**Proposal.** Page: `docs/plans/enforced-checkpoints-design.html` (same file, same claude.ai link). Template
first, enforcement second:
- Picture slots on In short steps, Changes items and choice options, plus a before-and-after compare on
  Changed items.
- An optional `docs/page-style.json` in each project, holding colours, fonts and a pictures setting
  (required for art changes, optional, or off).
- A page builder, `scripts/make_page.py`, that writes every page and stamps a mark.
- The first version's checkpoints, with the page check looking for the builder's mark.

## 2026-10-15 - Design proposed: enforced checkpoints

**Status.** Proposed, waiting on "Design approved: enforced checkpoints" with four choices.

**Context.** A plunderspell handover page was hand-built instead of coming from
`templates/handover-page.html`, and this session answered a proposal with no page at all. Audit:
`docs/handover-page-audit-2026-10-15.md`. aj: rules "need to be run at specific points not just as the agent
pleases", and a page "needs to be mandatory". Three causes were found. The injected `rules/show-dont-tell.md`
never names the template. The `Stop` check is recorded as never blocking (`docs/architecture.md:54`). And this
session loaded 2.55.0's start-of-session rules while its later hooks ran 2.65.1.

**Proposal.** Page: `docs/plans/enforced-checkpoints-design.html`. A checkpoint table in `hook.py`. The
end-of-reply check blocks once, then only reports on the retry, the same safety `subagentcommit` uses. A new
check before a page is written under `docs/plans/` or published with the Artifact tool refuses a page without
the template's parts. The injected rule names the template. Start-of-session rules come from the newest
installed version, after a diagnostic check of how the version mix happened. If approved, this reverses
"never `decision: "block"`" on `Stop`.

**Found while proposing, not in this design.** The design loop reads a subagent's hand-back as aj's message.
It logged "Build plan approved" from an editor report that quoted the phrase, which nothing moved only because
the stage was Design. It also unlocked a code edit on a report quoting "skip design". That unlock was not used.

## 2026-10-15 - New item visual v2 built (2.65.1); handed to aj for QA

**Built:** the template labels a New item's boxes "What exists today / What this creates / How it impacts you" and
draws any item's file list on open (#241). `tools/diff_parts.py` counts each file's parts, checked by
`tools/verify_tools.py` (47 of 47). The changes page was rebuilt for the whole pull request by
`docs/plans/design-loop-changes.build.py` (#242): 27 items, all 80 changed hook parts placed exactly once, and every
changed file listed; the build stops otherwise. In a browser at 375px, light and dark: every New item has its
boxes, no other item does, and every item opens to its files. `verify.py` 684 of 684, twice.

**Plan beside build**, on `docs/plans/new-item-visual-qa.html`:
- template: estimated +30 −2, built +21 −5
- changes page: estimated 32 items, built 27
- counting tool: estimated 60 lines, built 85 (Markdown sections, and a fix after it took a `try:` block for a
  function)
- tool checks: estimated +20, built +21
- `verify.py`: estimated +4 −2, built +13 −3 (9 of those lines are the #229 fix)

Not planned: the 161-line page builder, and the test-suite system doc's trap note.

---

## 2026-10-15 - Fixed: verify.py's stale-temp-file flake (#229)

aj: "fix the known failures, we never do a pr if there are things broken". The cause: the hooks keep state in the
temp folder (when aj last wrote, the waiting-on-you list), and `verify.py` reuses session names, so a
`house-rules-last-seen-verify` file left over five minutes earlier made `guard` treat aj as away and refuse
instead of ask. Fix: every run creates its own temp folder and points `TMPDIR` at it, so the hooks it starts can't
see another run's files. Proof: with 20-minute-old last-seen files planted, the previous suite failed 41 of 684
(34 of them "expected ask, got deny"), and the fixed suite passed 684 of 684 on two runs. Calling it a "known
flake" and rerunning was wrong: a failure that a rerun hides is still a failure.

---

## 2026-10-15 - Design approved: new item visual v2

aj: "Design approved New item visual v2: 1A 2A 3A".
- **1A:** the same three labels on every New item: "What exists today", "What this creates", "How it impacts
  you", each with a full sentence under it.
- **3A:** an opened item lists each file it touched once, with what happened in plain words and lines added and
  removed.
- **2A** answered the old wording question, which aj had already replaced with their own format; that question
  stayed on the page by my mistake. Its option A ("one sentence across the boxes, no labels") contradicts 1A, so
  I read it as stale. The build plan shows the box format exactly, so aj can correct this before anything is
  built.

**Plan.** Sub-issues #241 (template: the labelled boxes and every item's file list) and #242 (rebuild the
changes page for the whole pull request, with counts from git, and move the counting script into `tools/`)
were rewritten for v2. #243, the name fix, is already built. Plan page: `docs/plans/new-item-visual-v2-plan.html`,
listing 1 file created and 9 changed, with estimates marked. Approved: "Build plan approved: new item visual". The box format stands as shown.

---

## 2026-10-15 - QA passed: clear writing check

aj: "QA passed: clear writing check". Its issues (#245-#250) stay `needs review` until aj closes them. Next, the
new item visual resumes: its v2 redesign is waiting on aj's pick between the two readings of the box labels.

The real page session, refused earlier while aj was away, was rerun with aj present. The session wrote
`docs/plans/probe2.html` with a shell command, and its record shows both notes: "the page probe2.html has 1
thing(s) to fix" and "this turn wrote the page probe2.html" (the editor reminder). Its reply: "the one note
about it flags "about 43" as "a vague number or claim with no reason it can't be measured"".

---

## 2026-10-15 - Clear writing check built (2.65.0); handed to aj for QA

**Built** across #246-#250, from `3b95462^` to this commit: 5 files created, 15 changed and 1 deleted. `verify.py`
went from 659 to 684 checks, all passing on two clean runs; `tools/verify_tools.py` and `plain_docs_check.py` pass.
QA page: `docs/plans/clear-writing-qa.html`, listing each file's plan beside its build, as aj asked.

**Calibration.** The checker was run over this session's 93 long replies. After removing false alarms (a title
after a number, step cards, quoted examples, parallel list items), 31 replies still had findings. They are the
failures the rule is for: vague numbers that could have been counted, and bare "choice 5"s.

**The real run** used nested `claude -p` sessions with this branch's plugin and a stand-in `gh`:
1. A reply "The pull request adds about 43 tests; see #229." got the writing note naming "about 43" and "#229",
   per the session's own record.
2. `gh issue create --body 'Just a body.'` was refused, naming the three sections; the stand-in `gh` was never
   called.
3. The editor helper rewrote "The lock checks it's Build" as "The design lock checks that the feature is in the
   Build stage and that every issue carries the "in progress" label".
4. A page written with `printf` was not checked: it never passes the Write hook. Fixed: pages under `docs/plans`
   changed since aj's message are now checked when the reply ends, with a test. A rerun of that real session
   was refused by `guard` while aj was away (the words `timeout` and `| head` in one command), so it is waiting
   on aj.

**Six changes beyond the plan**, each named on the QA page:
- the exact-input sentence also left the main rules file
- `clarity.py` gained page-text reading
- the voice switch and the rule loader moved in `hook.py`
- the shell-written page fix
- two extra doc rows
- the template now offers a page's exact reply when it has no choices (it offered "approved", which the loop
  rejects)

**Guard false matches, for the rule audit (#228):** a loop or a `timeout` in one command with `| tail` or `| head`
in another was refused twice as a "hidden wait".

---

## 2026-10-15 - Design proposed: clear writing check (replaces the ambiguity check design)

**Status.** Approved: "Design approved: clear writing check: 1A 2A 3A 4A". The answers:
- **Who judges the wording:** the shared checker on everything, plus the editor helper on pages and long replies.
- **What folds in:** plain language, the ambiguity lines and the plain-docs writing limits.
- **A vague claim:** gets a reminder unless the same sentence says why it can't be measured.
- **An issue missing a section:** is refused.

The new item visual waits behind it.

**Plan.** Issue #245 has five sub-issues, all `in progress`:
- #246: the rule, with the old lines folded in
- #247: the shared checker
- #248: checking replies, pages and issues
- #249: the editor helper, and the check that it ran
- #250: docs, 2.65.0 and a real run

Plan page: `docs/plans/clear-writing-plan.html`, with two choices for aj. One is where the rule loads: the main
rules slot uses 9,381 of 9,700 characters, while the show-don't-tell slot uses 1,654 of 9,500 (both measured by
`verify.py`). The other is the editor helper's model. Waiting on "Build plan approved: clear writing check".

**Plan fixed (aj: "How can a build plan list nothing new it creates in the changes section? No files no
nothing, not an actual plan").** The first version listed three vague changes and no files. It now has one entry
per file: 5 created, 13 changed and 1 deleted. Lines that move or go are counted exactly from the files as they
are:
- `rules/house-rules.md`: the Plain language section, 12 lines (584 characters)
- `rules/detail/plain-language.md`: 71 lines
- `rules/detail/deliver-workflow.md`: the exact-input section, 13 lines
- `rules/detail/show-dont-tell.md`: "ask when unclear", 2 lines
- `skills/plain-docs/SKILL.md`: the writing limits, 10 lines
- `scripts/plain_docs_check.py`: the banned-word list, 16 lines
- `scripts/hook.py`: the not-checked detector, 33 lines

New lines are estimates, each labelled "Estimated, because it isn't written yet." A plan should always list its
files like this; the clear writing check and the automatic change log (#244) are where that gets enforced.

**Build plan approved:** "Build plan approved: clear writing check: 1A 2A". The rule loads beside Show, don't
tell, and the editor helper runs on Sonnet. aj added a requirement for the QA page: it must name explicitly what
changed between the plan and what was actually built, file by file, setting each estimate against the real line
counts.

**What.** aj: "we need to fix wording and ambiguity first, let's fold ambiguity and wording into a single check…
proper sentence structure and human tone, a lack of repetition and clear concise speech that is explicit with
context and leaves nothing for the user to extrapolate." It replaces the ambiguity check design below, which aj
never answered.

**What exists, checked in the code.** The plain-language rule covers jargon, voice, bare references and a plain
summary first; only the plain summary is checked. The plain-docs skill and `plain_docs_check.py` limit sentence
length, ban jargon and keep out code detail, but only for plain doc copies. There's also the long-reply reminder.
Nothing checks grammar, tone or repetition.

**Proposal page:** `docs/plans/clear-writing-check.html`. One rule, "Write it so nothing is left to guess", takes
in plain language, the ambiguity lines and the plain-docs writing limits. A shared checker covers vague claims,
bare references, repetition, jargon, sentence length and issue sections, on every reply, page and issue. A new
editor helper judges grammar, tone and gaps on pages and long replies; a pattern can't see "checks it's Build". The
not-checked and long-reply checks join the shared checker, and Evidence before claims stays its own check.

---

## 2026-10-15 - New item visual v2: aj's answers; automatic change log filed for later

**aj's answers** ("New item visual v2: 1* 2A"):
- **The file list** is option A: each file once, then each part in plain words with its exact counts, shown only
  when an item is opened.
- **The boxes**, in aj's own words: "Labels wrote per item but let's change the format here to, what exists today,
  what this creates, how it impacts the user." This reads two ways: the same three labels on every item, or
  per-item labels in those three roles. Both are shown on the code lock in `docs/plans/new-item-visual-v2.html`,
  with one question; the first is suggested. Still waiting on that answer and "Design approved: new item visual v2".

**Filed for later: #244**, an automatic change log. Written before the turn ends and checked after it, plain
words first with exact detail on open, new files described by what they are (a wizard model with textures and four
animations, not "wizard.fbx"), and visual files previewed from the screenshot check. It goes through the loop when
started.

---

## 2026-10-15 - QA failed: new item visual; redesign proposed

**aj's QA.** "Before this design moves forward we need to fix the wording of the 3 new boxes… It does and you
get are too rigid and don't always sound proper when reading the sentence." aj also wants to see which files
were created or changed, and by how much, "only if I open the change". aj didn't type "QA failed", but the meaning
is clear. #240-#243 are back to `in progress`, and the ambiguity check (proposed below) waits until this is done.

**Redesign page:** `docs/plans/new-item-visual-v2.html`. It shows three wordings on the code lock: one sentence
across the boxes with no labels (suggested), labels written per item, or fixed When / Then / So. It also shows a
file list that appears only in an opened item: each file once, with its total, then each part in plain words
with its own count. The code lock's numbers are real (`scripts/hook.py` +53 −1: +34, +10, +9 −1). They come from a
script that gives each diff line to the function around it, and it matches git's own total for the file
(+616 −32). Known wrinkle for the build: a comment just above a function is counted with the function before it.

---

## 2026-10-15 - Design proposed: ambiguity check

**Status.** Superseded by the clear writing check design (2026-10-15, above), at aj's request.

**What.** aj: "Let's add in an ambiguity check… fold in some of the rules and checks too as ambiguity needs
checking in several places and stages." What exists today:
- Asking when a request is unclear is rule text only (show-dont-tell); in practice the code lock is the check.
- Approvals are checked: a bare "approved" is refused, and names drop pasted answer codes (#243).
- Issue sections (depends on, done when) are asked for in the plan note but not checked.
- Replies: success claims, "can't be done" and unreasoned "not checked" are checked. Vague numbers and
  claims ("about 43", "should work") and bare references ("#2", "option B") are not.
- Pages: only my own hand search.

Proposal page: `docs/plans/ambiguity-check.html`. One "Nothing left vague" rule takes in four lines from three
rules: ask when unclear, exact inputs, named references, and done-criteria. One detector runs three new checks: a
vague claim with no reason in a reply, a bare reference in a reply, and the same two on a page written under
`docs/plans`. Issues are refused without "Depends on", "Depended on by" and "Done when". The not-checked check joins
the vague-claim check, and Evidence before claims stays its own check. Four choices for aj.

---

## 2026-10-15 - Correction: "about 43 tests" was a guess where a count was possible

The changes page said "about 43 tests" and "658 checks"; aj: "That's not the kind of thing that is ambiguous."
Counted by running `verify.py` on `origin/main` and on this branch, then comparing check names: main has 616 and
the branch 659, so 43 new (41 design loop, label check and page template cases, and 2 for the new rule's loading
and size). One more check exists on both and only changed its version number. `verify.py` gained 280 lines and
lost 13. The page now gives these numbers. A count that can be run is run, not estimated.

Side finding: on main, run from a long checkout path, "inject stays under the per-hook additionalContext limit"
failed at 9723 characters against its 9700 margin. The injected text names the plugin path, so a longer path costs
characters. It passes in the normal checkout. Left for the rule audit (#228).

---

## 2026-10-14 - Design proposed: new item visual

**Status.** Approved: "Design approved : New item visual: 1C". Option C: a New item opens to what sets it
off → what it does → what you get.

**Plan.** Issue #240 with sub-issues #241 (the template draws the flow) and #242 (the changes page's 13
New items), all `in progress`. Plan page: `docs/plans/new-item-visual-plan.html`. Found while planning: the
loop reads aj's two real messages as the features "New item visual: 1C" and "Label check plan: 1A 2A"
(checked by calling `_loop_name` on both). A redo after "QA failed" is matched by name, so its label check
would be skipped. Whether to fix it in this build is aj's choice on the plan page.

**Build plan approved:** "Build plan approved: new item visual: 1A". The name fix is a third step,
sub-issue #243.

**Built (2.64.1).** #241: the template draws a New item's `[when, it does, you get]` as three boxes; a New item
without them still shows text. #242: the changes page's 13 New items each have a flow. A browser check at phone
width, light and dark, found 0 New items without a flow and 0 flows on other items, with the page width at 400.
#243: a name stops before ": 1C"-style answer codes. `_loop_name` on aj's real messages now gives "New item
visual" and "Label check plan". `verify.py` 659 PASS on two clean runs (one earlier run hit the stale-file
flake, #229).

**What.** aj on the changes page: Changed items "are fantastic and need nothing", but New items "lack the same
visual flare". New items open to text only. Since it's the page template that would change, it goes through the
loop. Proposal page: `docs/plans/new-item-visual.html`. It shows three looks on the same item: A, before and
after with an empty "wasn't there" box; B, a strip of session moments with where it acts lit up; C, what sets it
off → what it does → what you get (suggested). Changed and Kept items stay as they are.

---

## 2026-10-14 - Correction: the pull request does not carry 2.54-2.62

The design loop pull request's description said the earlier 2.54-2.62 work rode along unmerged. Checked
against `origin/main`: main is at 2.62.0, and the diff holds only the design loop and the label check (36 files).
The claim came from an old note, not a check. The description and `docs/3-state/ProjectState.md` are corrected.
The full breakdown is `docs/plans/design-loop-changes.html`.

---

## 2026-10-14 - Label check built (2.64.0); the real run

**What.** #236, #237 and #238 are built in `hook.py` and covered by `verify.py` (658 PASS, run twice). #239: docs,
2.64.0, and the real run below.

**The real run.** A scratch repo at Plan, its tracker holding two real issues (#236, #237), the real `gh` read,
and nested `claude -p` sessions loading this branch's plugin:
1. "Build plan approved: label check", then create `app.py` → GitHub said both `in progress`; `STAGE: build`,
   `app.py: print('hello')`.
2. I swapped both real issues to `needs review`; a session asked to edit `app.py` → refused, `STAGE: qa`,
   `app.py` unchanged.
3. "QA failed: label check - it should say hi" → `STAGE: design redo: True`; the end-of-reply check told that
   session to move the labels back.
4. "Design approved: label check" with the labels still `needs review` → refused, `STAGE: design`.
5. I moved both back to `in progress`; "Design approved: label check" (through `run.sh scope`) →
   `STAGE: plan redo: False issues kept: [236, 237]`.

A direct read of all five label check issues took 0.71 s; a missing issue fell back to the record with "the
GitHub read failed (gh: Not Found (HTTP 404))".

**Found.** The QA-failed name took the whole line ("label check - it should say hi"): a spaced dash now ends a
name, with a test. Also, `guard` refused a doc-editing command because the text held the word "until" beside a
`| head`; I re-ran the edit from a script file with no pipe. That false match belongs to the rule audit (#228).

---

## 2026-10-14 - Design approved: label check; build plan proposed

**Decision.** aj approved the design ("Design approved: label check"). Planning made a feature
issue, #235, with four sub-issues: #236 (read labels from GitHub, falling back to my recorded
changes), #237 (the QA stage and label-checked stage moves), #238 (the code lock in Build and the
end-of-reply note), and #239 (docs, 2.64.0 and a real run). All are labelled `in progress` and each
names its dependencies and done-criteria. Build plan page: `docs/plans/label-check-plan.html`.
It has two open choices: who builds it (suggested: me), and how it ships (suggested: on this branch,
inside the open design loop pull request).

**Status.** Approved: "Build plan approved Label check plan: 1A 2A". I build it myself, on this
branch, so the open design loop pull request carries it.

---

## 2026-10-14 - Design proposed: label check (the loop enforced at each step)

**Status.** Approved; see the entry above.

**aj's answers** ("Label check: 1A 2* 3A 4B"):
- **QA starts** when I switch every issue to `needs review`.
- **Labels are read from GitHub every time.** When no GitHub account is linked, the check falls
  back to the label changes I made. Tested here: `gh auth status` reports a failed login, yet a REST
  read of an issue's labels works in about half a second, so "linked" means "the GitHub read
  succeeds", not what `gh auth status` says. Each fallback says so; nothing falls back silently.
- **After "QA failed"**, the same issues go back to `in progress`.
- **A wrong label** refuses aj's approval and also blocks my code edits until it's fixed.

**What.** aj: "Build the check now, the loop doesn't function without it. The loop must be enforced
at each step." Proposal page: `docs/plans/label-check.html`. It adds a QA stage between Build and Done,
entered when every issue of the feature says `needs review`, and a record of each issue's labels
taken from my own label changes. "Build plan approved" needs every issue `in progress`. aj's QA answer
counts only in the QA stage. After "QA failed", the redo's design approval needs every issue back
to `in progress`. An end-of-reply check names any label that doesn't match the stage.

**Why a page first.** The loop applies to its own changes. Four choices are open for aj: what
starts QA, where the labels are read from, which issues carry a redo, and what a wrong label blocks.

---

## 2026-10-14 - At QA an issue moves to `needs review`; changes send it back to `in progress`

**Decision.** aj changed the label flow: when an issue reaches aj's QA, `in progress` is swapped for
`needs review`. aj then closes it, or asks for changes and it goes back to `in progress`. This
replaces the `in review` label from the entry below, which is no longer used. The design loop's
parent issue and seven step issues now carry `needs review`.

**Why.** aj's call: one label says whose move it is: `in progress` is mine, `needs review` is aj's.

**Not enforced yet.** Labels are set by hand; no hook checks them. Noted for the rule audit (#228).

---

## 2026-10-14 - `in progress` stays on through review; new `in review` label

**Status.** Superseded by the entry above.

**Decision.** When the design loop's pull request opened I removed `in progress` from its issues.
aj said to keep it and add a new `in review` label instead. The parent issue and the seven step
issues now carry both. `in progress` comes off only when aj closes the issue.

**Why.** aj's call: an issue isn't finished until it's tested and closed, so review is still work
in progress. Written into `rules/detail/show-dont-tell.md`, "A home for each feature".

---

## 2026-10-14 - QA passed: design loop (#223)

**Decision.** aj passed QA on `docs/plans/loop-qa.html` ("Design loop QA: 1A 2A"): QA passed, and release by a pull
request from `AjsAgent/agent-communication-patterns-xo0l8x` to main. The PR also carries the unmerged 2.54-2.62 work
already on this branch. Issues are marked done, not closed: closing stays aj's, after testing in a real session.

**Status.** Standing. Feature: Done.

## 2026-10-14 - The design loop is built; it goes to aj's QA (#223)

**Decision.** All seven build steps are done (#225, #230, #231, #232, #226, #233, #227). My own review included a real
run: five messages to a real Claude Code session loading this branch's plugin in a scratch repo; it found that a
feature name took the whole line (fixed, with a test). Plugin version 2.63.0. Releasing it needs a merge to main,
which is still at 2.53.0; this branch also carries the unmerged 2.54-2.62 work. QA page: `docs/plans/loop-qa.html`.

**Status.** Waiting on aj's QA.

## 2026-10-14 - Issues made with the GitHub tool count too (#231)

**Context.** Building step 3 ("A home for each feature") showed the existing issue record only counts a terminal
`gh issue create`; in cloud sessions issues are made with the GitHub tool and were never counted
(`docs/plans/issue-check-gap.html`).

**Decision.** aj chose 1A: the issue record also counts issues made with the GitHub tool, with the same label
check. Rejected: asking GitHub with `gh` at approval time (no `gh` in cloud sessions); no check (a rule with no
check, ruled out under #228).

**Status.** Standing.

## 2026-10-14 - The loop's stage carries across sessions (#225)

**Decision.** Asked while building the code lock: a new session that opens while a feature is in Build keeps Build,
so code stays open under the plan aj already approved; every other stage stays closed to code. This replaces the
earlier "every session starts locked" (Q1A, 2026-10-13), which predates the staged loop.

**Status.** Standing.

## 2026-10-14 - Build plan approved: design loop (#223)

**Decision.** aj approved the build plan (`docs/plans/loop-build-plan.html`) with "Build plan approved: design loop".
Seven steps, each a sub-issue of #223 naming its dependencies and done-criteria: stage tracker, approvals and the
code lock (#225); an approval only counts once logged (#230); a home for each feature (#231); helpers build only
approved steps (#232); long-reply reminder (#226); handover page template (#233); prove it and update the docs
(#227). Choices: (1) the step cards are replaced later as their own feature through the loop; (2) one version bump
at the end, so nothing reaches aj's sessions until the whole loop is proved. I build it myself, one step at a time.

**Status.** Standing. Stage: Build.

## 2026-10-14 - Design approved: handover format (#223)

**Decision.** aj approved the handover format (`docs/plans/handover-format.html`). Every page has four parts in this
order: In short, Changes, Choices, Wrap-up; In short and Changes are read, Choices and Wrap-up are acted on. Every
part keeps four rules: detail only on tap; names, never bare numbers; one colour, one meaning (orange is always
something aj acts on, nothing else is orange, green is done); I check it first (phone width, light and dark, every
tap, a bare-number search). Choices: (1) a part is left out only when it would be empty; (2) my chat reply around a
page is a plain summary, the link, then numbered steps for what aj needs to do; (3) the template lives in the
plugin's templates folder, next to `templates/step-card.html`, which it replaces when the step cards are replaced.

**Status.** Standing. Building it joins the loop's build plan.

## 2026-10-14 - Design approved: design loop (#223)

**Decision.** aj approved the loop design (`docs/plans/loop-design.html`) with "Design approved: design loop".
Eight steps: Design, Approve design, Plan, Approve plan, Build, I review, Your QA, Done. Colour shows whose step it
is; each step shows what it creates or changes and what it requires, at equal weight. Approvals read
"<Stage> approved: <feature>"; QA reads "QA passed: <feature>" or "QA failed: <feature>" plus the changes. An
approval does not count until the stage is logged. Feature and step issues carry the "in progress" label and name
dependencies, dependants and completion criteria. The paused code-edit lock (#225), long-reply reminder (#226) and
their tests (#227) fold into this build.

**Status.** Standing. Next: the build plan. Still open: approval of the handover page format.

## 2026-10-13 - Pages keep one design language that never contradicts itself (#223)

**Context.** The loop-design page's legend said orange meant "your words move it on", while Design and Plan,
both blue, also needed aj's words to move on. aj caught it.

**Decision.** aj: a cohesive design language that does not contradict itself is required on every page. Added to
`rules/show-dont-tell.md` ("a design language that fits the idea and never contradicts itself") and to its detail
file: every colour, shape and icon means one thing everywhere on the page, and the legend says exactly what. I check
this in my own review before aj sees a page. Under the "a rule with no check is not written" principle (#228), how to
enforce it beyond my own review is for that audit to decide. `verify.py` 618 PASS after the change. A recurring
flake seen along the way is filed as #229 (old "last seen" temp file breaks guard tests).

**Status.** Standing.

## 2026-10-13 - The loop: aj's review and test become one QA step (#223)

**Decision.** aj: "You review" and "You test" merge into one final QA stage with a pass/fail result. A fail states
clearly what needs to change and goes back to Design. Proposed wording: "QA passed: <feature>" and "QA failed:
<feature>" plus the changes. Stages are now Design, Plan, Build, I review, Your QA, Done.

**Status.** Open: aj's approval of the loop design and the handover page format.

## 2026-10-13 - The loop: I review before aj does (#223)

**Decision.** aj: review is split in two. First I review on my own: visual check of every screen the change
touches, a real run of how it works, and fixes for anything that does not match the approved design. Only then
does aj review, separately, and we iterate. Anything that would change the design goes back to aj instead of being
fixed. Reuses the visual-check and "a green test suite is not proof" rules rather than adding a new mechanism. The
loop now has seven stages: Design, Plan, Build, I review, You review, You test, Done.

**Status.** Open: aj's approval of the loop design and the handover page format.

## 2026-10-13 - The loop's design: three choices made (#223)

**Decision.** On `docs/plans/loop-design.html`, aj chose: (1) own answer: a feature is labelled in progress while
worked on, its steps are sub-issues that are labelled and trackable in GitHub, and every issue and sub-issue names
its dependencies, dependants and completion criteria so blockers and progress are easy to see; the existing
"in progress" label from the issue workflow is reused; (2) an approval does not count until the stage is logged;
(3) approvals read "<stage> approved: <feature>", e.g. "Design approved: blockers".

**Status.** Open: aj's approval of the loop design, and of the handover page format.

## 2026-10-13 - The design loop: last choice made (#223)

**Decision.** aj picked "fold them into the loop" for the three paused pieces of work: the code-edit lock (#225), the
long-reply reminder (#226) and their tests (#227). The code-edit lock becomes the lock at every approval and all
three are built as part of the loop, in one build. With the four choices logged earlier today, all five design-loop
choices are made.

**Status.** Standing. Open: approval of the handover page format, and of the loop's own design page.

## 2026-10-13 - A rule with no check is not written (#228)

**Context.** The no-bare-numbers rule (#216) was broken twice in one session. It shipped text only, covers chat
replies but not pages, and no end-of-turn check reads pages (`docs/plans/bare-references.html`).

**Decision.** aj: every rule needs a check that enforces it, because the agent can otherwise ignore it. A rule
nobody can enforce should not be written. Issue #228 (audit every house rule for a check that enforces it) audits
the whole rule set for unenforced rules and fixes the cause at the source. It is taken up after the show-don't-tell
design loop (#223) is agreed and documented. The three choices on the bare-references page wait for that audit.

**Status.** Standing. Audit not started.

## 2026-10-13 - The design loop: four of five choices made (#223)

**Context.** aj asked for auto mode to work like plan mode but force one workflow: design together, aj approves;
plan the build together, aj approves; build; review together; plan changes, aj approves; aj tests and approves.
Every step logs decisions and changes and updates docs, never left for later, and helpers follow the same loop.
Proposal page: `docs/plans/design-loop.html`.

**Decision.** Choices answered by aj: (1) the plugin's own check holds every approval lock (not Claude Code's
plan mode, which docs say switches the session into an editing mode on approval, and which helpers cannot enter);
(2) aj's own answer: a feature lives in the systems docs and as a GitHub issue with sub-issues, plus a line in
this log; features are planned, built, adjusted and finished, and the whole process is trackable at a glance;
(3) helpers only build approved steps and report into the log; (4) "skip design" lets one small fix through, still
logged. Choice 5 (what happens to the paused lock, reminder and tests, issues #225-#227) was asked with bare issue
numbers; aj's answer was that a choice must name what is changed and what it means, never only a numbered issue.
Re-asked with the pieces named.

**Status.** Open: choice 5, and approval of the handover page format itself.

## 2026-10-13 - Show, don't tell; the user designs - its own SessionStart slot, three rules merged in (#223, #224)

**Context.** aj's biggest blocker with agents: work told, not shown; design choices made for them; code written
before they had seen any idea. They asked for a rule where every plan reaches them as a visual, interactive
proposal they approve or deny, design is theirs, and nothing is built before an approved design.

**Decision.** Approved by aj in chat, in this order: picks 1A 2A 3B 4C 5A (one new rule; a page for every plan;
options with my suggestion marked, aj picks; a hook blocks code until a design is approved; replies end on one
question); Q1A Q2A Q3B Q4A (sessions start locked; "approved" plus a name lifts the block; "skip design" lets one
change through; a 200-word no-page reminder ships with the block); "show" definition B (a page shows how the change
works and affects the current product, with correct icons, consistent styling and a fitting design language, and
nothing more); consolidate-first option A (every proposal opens with what exists: merges, cuts, reuses); overlap
map (merge "Build only what was asked", "Match response depth" and the "Prefer proposing a plan" standards line;
replace step cards; reuse the plain-summary and issue-gate checks); rule placement B (its own SessionStart slot).
Built in #224: `rules/show-dont-tell.md` injected by a new `showrule` handler; the two merged rules and their detail
files removed; `verify.py` 618 PASS, run twice. Proposal pages: `docs/plans/show-dont-tell*.html`,
`docs/plans/consolidate-first.html`.

**Rejected.** The rule inside `house-rules.md` (it was 47 chars from `inject`'s 9,700 margin; the rule is 927);
the coding-standards slot (9,304 chars in a Unity + Node project, measured); a short pointer only, or cutting ~930
chars from other rules.

**Why.** The rule exists so aj keeps authorship. A first plan page made of styled text was rejected ("You showed
me nothing you just made the text pretty"), which is why "show" is now defined in the rule itself.

**Status.** Standing. Step cards (replace), the design block (#225), the reminder (#226) and their proof (#227) are
not built yet.

## 2026-10-09 - Git writes are judged by the default branch, not branch prefixes; unanswerable prompts are refused (#196-#199, 2.60.0)

**Context.** Subagents in worktrees sit on `worktree-agent-<id>` branches, which were not "owned", so every
commit they made asked and a background subagent waited on it (#134, #136). After one timeout the prompt timer
refused every later prompt and said never retry, so a refused commit or push stopped the whole job (#173, #192).
A dialog can also outlive a restarted worker with no timer behind it (#159). aj asked for: no prompt for a normal
commit or push, nothing committed or pushed to `main` directly, and only deletions and unrecoverable steps asking.
**Decision.** `guard` draws the line at the repo's default branch (`main`, `master`, `origin/HEAD`). There, a
commit, push, merge, rebase, revert, cherry-pick, `am` or `apply` is denied, as is a push aimed at it from any
branch; elsewhere they run unasked, approved outright (`allow`) when the command is only `git`/`cd`.
`git -C <dir>` is judged by `<dir>`; the author check reads that repo. `guardgithub` denies `push_files` and
`create_or_update_file` to `main`/`master`. A remaining ask becomes a deny, queued on the waiting-on-you list,
inside a subagent (`agent_id`) or when aj last wrote longer ago than the prompt timeout.
**Rejected.** Adding `worktree-agent-` to the owned prefixes (fixes #134 only; aj's feature branches and Claude
Code's own prompts still stall). Keeping `ask` on `main` with the timer behind it (the timer is the part that fails).
**Supersedes.** The 2026-10-09 payload-cwd entry below, and the 2026-10-07 #153 entry, for where the line sits;
their mechanisms (payload cwd, the saved-elsewhere check) are kept.
**Status.** Built; `verify.py` covers each case. Not yet seen in a live session.
Plan: `docs/plans/2026-10-09-stop-permission-stalls.md`.

---

## 2026-10-09 - Branch ownership is judged from the payload cwd; `ccr-` branches are owned (2.59.1)

**Context.** A worktree subagent's commits on its own `AjsAgent/` branch were prompted, because `branch_ownership()` read `CLAUDE_PROJECT_DIR` (the main checkout, on a non-owned branch).
**Decision.** Judge from the payload `cwd` (then `CLAUDE_PROJECT_DIR`, then `getcwd()`), honour one leading `cd <dir> &&`, add `ccr-` as an owned prefix and `HOUSE_RULES_OWNED_BRANCHES` for extras. Exemption stays plain commit and plain push only; `-C`/`--git-dir`, other `cd`s, force push, merge and the rest still prompt.
**Rejected.** Exempting by branch name regardless of cwd (would trust the wrong checkout); parsing arbitrary `cd` chains (unsafe, a wrong guess widens the exemption).
**Status.** Current. Mechanism: docs/4-systems/hook-engine.md, Traps.

---

## 2026-10-09 - The GitHub write tools get their own credit check, text and new branches only (#178, part of #174, 2.59.0)

**Context.** The attribution checks ran only in `guard`, wired to `Bash|PowerShell`. A pull request, issue, comment or push made through the GitHub MCP tools skipped them.

**Decision.** A separate `PreToolUse` entry (`guardgithub`) matched to the eleven write tools under both `mcp__github__` and `mcp__GitHub__`. It checks `title`, `body`, `message` against the existing text patterns and refuses a new `claude/` branch (`create_branch`, a PR `head`). File `content` is never scanned: this repo's own source contains the patterns, so scanning would refuse the work that maintains them. A push onto an existing `claude/` branch is allowed: old branches still get work until #182 renames them, and refusing would strand that work; only creating a new one is refused. It fails open and loud, unlike `guard`: a GitHub write is not a destructive local action, and a broken check should say so rather than stop the write.

**Rejected.** Folding the tools into the `guard` matcher (different payload shape, and every shell call would pay for it). Scanning file content.

**Status.** Built; `verify.py` covers both prefixes, each deny and allow, the kill switch and the matcher regex.

---

## 2026-10-08 - Commits are authored as AJ's agent, enforced by the guard and a session-start line (#177, part of #174, 2.58.0)

**Context.** Cloud containers ship `user.name=Claude`, `user.email=noreply@anthropic.com`; 103 of 227 commits on main carry that author. The attribution guard read message text only.

**Decision.** The agent's identity is `AJ's agent <79066376+Ajw2003@users.noreply.github.com>`: a GitHub noreply address attaches commits to aj's account without publishing a real email, and the account id form is the one GitHub accepts. `guard` refuses a `git commit` whose effective author is Claude or `*anthropic.com`, naming the repo-local `git config` fix. `profile` on a remote session adds one line telling the agent to run it. Both honour `HOUSE_RULES_ATTRIBUTION=off`; an unreadable identity is allowed silently.

**Rejected.** The hook writing the git config itself (the issue text said "sets"): the #176 decision that hooks instruct and don't act wins. A `--global` fix: it would alter the machine's config, not the repo.

**Status.** Built; `verify.py` covers repo config, `--author`, `-c`, inline `GIT_AUTHOR_EMAIL`, a name merely containing claude, the kill switch, PowerShell, and the profile line. It now points git at a fixture global config so results do not depend on the machine's own.

---

## 2026-10-08 - Cloud sessions move off the app's claude/ branch onto AjsAgent/ (#176, part of #174, 2.57.0)

**Context.** The cloud app assigns each session a `claude/<name>` branch and tells the agent to push only there. aj decided every agent branch should be `AjsAgent/`, cloud ones included.

**Decision.** `profile` (SessionStart), on a remote session whose branch starts `claude/`, tells the agent to `git switch -c AjsAgent/<name>` before its first edit (or `git switch AjsAgent/<name>` when that branch already exists locally or on `origin`), push there, and open pull requests from there. The text names aj's standing permission as overriding the app's "push only to the designated branch" line. The hook only instructs; it never switches. `HOUSE_RULES_AGENT_BRANCH=off` disables it.

**Rejected.** Having the hook run `git switch` itself: hooks force, they don't act. Switching only fresh branches: switching carries existing commits along, so there is nothing to protect.

**Status.** Built; `verify.py` covers `claude/foo`, an existing `AjsAgent/foo`, `AjsAgent/foo`, `main`, a local session, the kill switch, and a non-git folder.

**Open.** Not yet checked in a real cloud session: whether the app's "Create PR" button and branch display follow the new branch. If they don't, the PR is opened from `AjsAgent/<name>` with the GitHub tools instead.

---

## 2026-10-08 - Agent branches are AjsAgent/ and the issue label is AjsAgent created this (#175, part of #174, 2.56.0)

**Context.** The agent's work is credited to "aj's agent", not Claude; branch prefix and issue label still said `claude/` and `Claude created this`.

**Decision.** New branches are `AjsAgent/<topic>` and new issues carry `AjsAgent created this`; every message and rules file names the new forms. `OWNED_BRANCH_PREFIXES` in `hook.py` is `("AjsAgent/", "claude/")` and the issue gate also accepts the old label (`ISSUES_LABEL_OLD`).

**Rejected.** Dropping the old names: the cloud app still creates `claude/<name>` branches, 56 old ones exist, and a plan already in flight has old-labelled issues that must not be blocked.

**Status.** Built; `verify.py` cases cover both prefixes, a non-owned branch, and both labels. Injected rules stay under the 9,700 margin.

**Consequence.** Old names are accepted but no longer suggested. Guard attribution text, SessionStart branch switching, git author and MCP matchers are #176-#179.

---

## 2026-10-07 - Destructive git steps run unasked only on my branch, and only when the work is saved elsewhere (#153, 2.53.0)

**Context.** aj: "destructive actions are permitted only on a Claude created branch and only if the work already is saved somewhere else the destructive action would not affect." Asked whether "otherwise" meant ask or never, aj chose ask as today; asked whether `guard` should enforce it, aj chose rule text plus `guard`.

**Decision.** The two rules now draw the line: on a `claude/` branch with a clean tree and every commit on a remote, a destructive step needs no asking; anywhere else it asks exactly as before. `guard` enforces the safe case for `reset`, `revert`, `rebase`, `checkout --` and `restore` through `work_saved_elsewhere()`.

**Rejected.** Exempting force-push: it overwrites the remote, which is the copy that makes the work "saved elsewhere". Exempting `clean`, `stash drop` and `rm`: what they remove (ignored files, stashes, arbitrary paths) is never on the remote, or guard can't tell. Exempting merge-like verbs: a separate rule (don't finish what aj started) covers them.

**Status.** Built; `verify.py` drives a real repo with a local bare remote (safe case passes; dirty tree, unpushed commit and aj's branch ask; force-push, clean, stash drop, merge and rm ask). To fit the 9,700-character inject margin, three phrasings elsewhere in `house-rules.md` were shortened without changing what they say (docs tiers, local paths, the step card), and the commit rule carries no pointer to the destructive one (its detail file does). The injected length includes the plugin's absolute path: 9,650 in this sandbox, about 26 more on the CI runner, where a first attempt at 9,687 failed at 9,713.

**Consequence.** `guard` now runs up to two `git` subprocesses on a matching command on my branch. On aj's branch nothing changes.

---

## 2026-10-07 - The prompt timer skips questions, refuses at once once aj is away, and learns when an action ran (#149, #151, #152, 2.53.0)

**Context.** #149: on 2026-10-06 a subagent's `git push` dialog stayed on screen overnight after the timer refused it, a second push prompt waited another full 5 minutes, and a third push that actually ran was recorded as timed out. aj asked that the timer actually move the agent on to a route that is not blocked rather than leave it waiting long after aj had the chance to answer, and that questions and multiple-choice prompts be left out of it.

**Decision.** (1) `AskUserQuestion` and `ExitPlanMode` get no timer. (2) After one timeout in a session, later prompts in it are refused at once until aj's next message; the refusal names the earlier unanswered prompt. (3) A new `promptran` handler on `PostToolUse`/`PostToolUseFailure` marks an action that ran, so the waiting timer stops with no decision, and reports a timed-out action that ran anyway.

**Rejected.** A `PostToolUse` entry with no matcher: about 130 ms per call on every Read and Grep, where nothing else runs; it is matched to the tools that raise prompts instead. Exempting by a `hooks.json` matcher: a negative match needs a lookahead regex whose support was not checked; the exemption in `hook.py` is explicit and tested. Closing the stale dialog: there is no hook output for it.

**Status.** Built; `verify.py` covers each part. Seen live in the build session itself (cloud, auto mode, 2.52.0 installed): three Bash calls that ran were listed by `scope` as "waiting on you", because auto mode approved them without stopping the timer - the #149 symptom `promptran` removes. Not verified in a real session: whether the stale dialog's Allow can still run the command (if it does, `promptran` now reports it), and whether `PermissionRequest` ever fired for `AskUserQuestion` before this change.

**Consequence.** An aj who is present but missed one prompt sees the next prompts refused until they write anything; writing restores normal prompts.

---

## 2026-10-04 - A permission prompt nobody answers for 5 minutes is refused, never approved (#142, 2.52.0)

**Context.** Overnight, one unanswered permission prompt held up a whole session. Issue #136 is the same failure in background builders. aj: "Permission as a blocker should be isolated, not affect the rest of the project."

**Decision.** A `prompttimer` handler on `PermissionRequest`, the one hook event that runs at the same time as the dialog ("whichever finishes first determines the outcome", hooks reference). It waits `HOUSE_RULES_PROMPT_TIMEOUT` seconds (default 300, `off` disables) and then refuses. It never approves, because an unanswered prompt is a no. The refusal tells Claude not to retry, to route around without the same effect, and to carry on with the rest. The action goes on a waiting-on-you list in `<git common dir>/house-rules/waiting-on-you.json`. That list is shown on aj's next real message and at the next session start. It is the second deliberate exception to "no hook keeps state", after `versioncheck`'s marker, and is kept for the same reason: each entry is keyed by session.

The refusal text goes in both `decision.message` and `decision.reason`. Probed on Claude Code 2.1.289: only `message` reached the model, although `reason` is the documented name.

**Rejected.** Approving after the timeout: that would turn silence into consent for exactly the destructive actions the prompts exist for. A timer inside `PreToolUse`: that hook finishes before the dialog opens, so it cannot time one.

**Status.** Decided and built. Not yet settled (#143): headless, a `guard` `ask` never reached `PermissionRequest`. Whether it does in the desktop app is untested, so whether the house-rules prompts themselves are timed is unknown until #143 runs. If they are not, the fallback in the plan (an absence check) goes to aj first.

**Consequence.** A refused action can sit on the list unseen until aj next writes or a new session starts. That is the point: it waits, and the rest of the session carries on.

---

## 2026-10-01 - Commits and pull requests credit "aj's agent", never Claude (#133, 2.51.0)

**Context.** Claude Code adds a `Co-Authored-By: Claude` trailer to commits and a "Generated with Claude Code" line to pull requests. aj wants the distinction that an agent did the work but not the Claude branding, and no email shown.

**Decision.** Credit "aj's agent": commit text `Committed by AJ's agent`, pull request text `Opened by AJ's agent`, no `Co-Authored-By` trailer (it needs an email), `sessionUrl` false. Two mechanisms. (1) Claude Code's `attribution` setting, written by `tools/install.py` into the user's settings file; it exists in the program (found in 2.1.286) though not in the public docs, and the app applied it to a running session at once. A plugin cannot ship it: Claude Code reads only `agent` and `subagentStatusLine` from a plugin's settings.json. (2) A `guard` check that refuses text crediting Claude, for sessions that never read the settings file (cloud sessions). `HOUSE_RULES_ATTRIBUTION=off` disables the check.

**Status.** Decided. Old commits and pull requests are not rewritten.

**Consequence.** A new machine gets the setting only when the installer runs there. The guard cannot add the right wording, only refuse the wrong one.

---

## 2026-10-01 - "Never hide work in the background" becomes "work stays visible, reachable and readable"; every background job gets a 5-minute stall check (#120)

**Context.** The rule said nothing runs in the background. That stopped being true or useful: subagents, Monitor and `run_in_background` are tools the user can follow, and aj works from a phone. aj amended it: "work should never be hidden, unreachable and unreadable. If I cannot see what is being done or reliably check in on or audit long running tasks on mobile then the rule is being broken." Earlier the same day a subagent sat silent for 26 minutes and nothing said so.

**Decision.** The rule is renamed (*Never hide work: it stays visible, reachable and readable*) and rewritten around that test. Hidden windows, `nohup`, detached jobs and logs only Claude reads stay banned (the `guard` patterns are unchanged). Followable background work is allowed. Every background job is checked every 5 minutes with `scripts/stallcheck.py`: the age of the newest write to its transcript or output file against 300 seconds, no model call. Run under Monitor with `--watch` it costs nothing until something stalls. The reminder hooks that said "check in every 10 minutes" now name that command. `worktreesweep`'s 10-minute commit rule is a separate mechanism and is unchanged.

**Status.** Decided. Supersedes the old rule text and heading; the heading string changed in `guard`'s bucket title and the tests.

**Consequence.** A long model call or a usage-limit wait writes nothing, so it reads as STALLED. That is the definition; the answer is to look and tell aj, not to assume the job died. The check is enforced for subagents by the reminder hook text, not by a hook that blocks; for other background commands it relies on Claude following the rule.

---

## 2026-10-01 - Three helper tiers replace the executor; spawns are capped (2.50.0)

**Context.** Issues #110-#112. aj found the executor too slow (a build ran 32 minutes), too costly
(about 54k tokens just to start) and too chatty. Measured spawn cost is dominated by tool definitions,
so a short tool allowlist is the main lever.

**Decision.** `agents/executor.md` is deleted. `scout` (haiku; Read, Grep, Glob), `builder` (sonnet; Read,
Edit, Write, Bash, Grep, Glob) and `reviewer` (opus; Read, Grep, Glob, Bash) replace it; none has the
`Agent` tool, so nesting is impossible by construction. Tier files carry only model, tools and role; the
rules core reaches them through `subagentrules`. A PreToolUse `agentcap` entry (matched to Agent only)
denies a third running subagent, using a list in the common repository directory; a record older than 45
minutes is ignored because SubagentStop did not fire during the 2026-09-29 outage; it fails open and loud,
and `HOUSE_RULES_AGENTS=off` disables it. The subagent audit now prints tool counts, failed commands in
full, files written and a count of other commands. `issuelist` shows a visible loaded note.

**Alternatives rejected.** Keeping the executor with a trimmed prompt (the tool definitions were the cost);
blocking nesting only by a hook (the tool list does it with no process).

**Left alone on purpose.** The archivist, `commitgate`, `autosave`, `worktreesweep`, `subagentcommit`.

**Supersedes.** The executor-based delegation in the 2026-09 entries; those entries stay as history.

---

## 2026-09-30 - Hooks force the issue workflow; Claude still performs it (2.49.0)

**Context.** Issues #108-#110, parent #107. Plans, pull requests and closures were not tied to
issues, and a merged PR could close an issue before the user had tested. Focus Deck, the user's
board, only shows issues labelled `Claude created this`.

**Decision.** (1) The hooks force; they never act. No hook runs `gh issue create` or `gh issue close`:
a plan over three steps makes `commitgate` deny Write/Edit/NotebookEdit on source files until a
parent and a child issue, both labelled `Claude created this`, are recorded. `docs/`, `.claude/`,
any `.md`, files outside the project and the state file stay editable, so the plan and the issues'
text can still be written. The kill switch is `HOUSE_RULES_ISSUES=off`. (2) Pull request bodies say
`Refs #N`, `Part of #N` or `No-issue: <reason>`; a closing word followed by an issue reference is
denied, because GitHub closes the issue at merge. (3) `gh issue close` always asks; the prompt is the
user's go-ahead after testing, and on approval Claude adds `Claude completed this`, removes `in
progress`, and comments the merged PR link. (4) On 2026-09-30 the user permitted Claude to apply an
`in progress` label to an issue when work on it starts.

**Alternatives rejected.** A hook that creates the issues itself (hooks must not write to GitHub on a
tool call and cannot write plain-language titles). A warning instead of a block (the efficiency review
and past lapses show reminders get ignored). A new hook process per gate (about 114 ms each).

**Status.** Decided. Supersedes nothing.

**Consequence.** `inject` grew by about 115 tokens and its `verify.py` margin moved from 9,000 to
9,700 characters. The open-issue list is its own SessionStart entry because of that margin. `gh
issue create` through the `PowerShell` tool is not recorded. A subagent worktree has its own git
directory, so a plan approved in the main session does not gate it.

## 2026-09-30 — Subagents do receive CLAUDE.md; the "never sees it" claim is withdrawn

**Context.** While measuring what a subagent spawn costs, the transcripts of one
`general-purpose` and one `claude-code-guide` subagent each held an `instructions` attachment
listing the user `CLAUDE.md`, the project `CLAUDE.md` files and `MEMORY.md`. The `Explore` subagent
held none. `CLAUDE.md` said a spawned subagent never sees it, resting on the 2026-09-22 entry
below, which tested `SessionStart`'s `additionalContext` only.

**Decision.** `CLAUDE.md` and `docs/architecture.md` now say most subagent types receive it. The
2026-09-22 finding stands for `SessionStart` `additionalContext`, and is not rewritten.

**Status.** Decided. Replaces the `CLAUDE.md` sentence only; supersedes nothing else.

**Consequence.** Anything added to `CLAUDE.md` is paid again on every general-purpose spawn, which
weighs against adding to it. Not yet measured: whether Explore omits it on purpose or by accident.

---

## 2026-09-30 — Subagent work is saved while it runs, not only when it finishes

**Context.** On 2026-09-29 a safety-classifier outage stopped an executor mid-run. `SubagentStop`
never fired, so `subagentcommit` (the only commit enforcement for subagents) never ran, and
`hook.py`, `verify.py` and six docs sat uncommitted in its worktree until the parent noticed and
committed them by hand. aj asked for the executor to be held to committing constantly, with
progress saved against outages, and then asked for the parent's own 10-minute check (which the
parent had been doing by hand) to become a plugin behaviour too.

**Decision.** Three hooks, all limited to `worktree-agent-` branches (the ones Claude Code creates
for `isolation: "worktree"`), all off with `HOUSE_RULES_AUTOSAVE=off`:
- `autosave` (PostToolUse): snapshots the worktree to `refs/house-rules/autosave/<branch>` through
  a temporary index, pushes it once a minute, and commits for the subagent after 10 minutes
  without a commit.
- `commitgate` (PreToolUse): blocks edits at 3+ uncommitted files. aj chose "tell the executor"
  over auto-committing every edit. aj then added that if the executor ignores it, the hook
  commits itself; `subagentcommit`'s retry path does the same.
- `worktreesweep` (UserPromptSubmit): on every parent wake, commits any subagent worktree left
  untouched 10+ minutes. That is the one case no subagent-side hook can cover, a dead subagent.
  `audit` asks for a 10-minute check-in when a subagent launches in the background, so the
  parent wakes.

aj chose to push the autosave ref, so the save outlives the container.

**Rejected.** Auto-committing every edit (the branch fills with wip commits). An instruction-only
rule, which is what failed on 2026-09-29.

**Consequence.** `autosave` and `commitgate` are the first handlers to keep state between calls:
three small files per branch inside that worktree's git dir, deleted on a clean finish.
`docs/4-systems/hook-engine.md`'s stateless invariant now names them as the exception. In a
Claude Code cloud session the push is refused (HTTP 403 from the session's git proxy, which only
accepts the session's own branch), measured 2026-09-30. There the save stays local and each
failed push says so. Whether GitHub accepts `refs/house-rules/*` from a user's own machine is
untested. Building it was itself blocked twice by the auto-mode classifier as
`[Self-Modification]` when the executor tried it. aj then had the main session build it directly.

**Related.** Issue #105 (replace the single executor with dynamic dispatch) is the longer-term
direction. This protection is needed whatever replaces the executor.

---

## 2026-09-29 — Open source first; the Unity rule leaves the core; the profile records hardware

**Context.** aj asked for two things: build locally for the hardware we have, and prefer free
open-source solutions with paid as the last resort (on Pro or Max, first scope building our own).
The plan is `docs/plans/2026-09-29-local-first-free-first.md`. The core `inject` text had 81
characters of room, so the new rule needed space. Two ways of making it were measured; aj chose
Option B, moving the Unity rule out of the core. Measuring Option B showed that `standards` in a
Unity project already emitted 9,832 chars (budget 9,500) and 13,376 with a Node service beside
it (hard limit 10,000).

**Decision.**
1. A core rule "Open source first; paid is the last resort" with a five-rung ladder, and
   `rules/detail/free-first.md` (the ladder, the build-your-own estimate table, an example). The
   "Find out what machine you are on" rule gains "Detected hardware is the local budget", and
   `rules/detail/environment.md` says what "doesn't fit" means.
2. "Unity work starts with the Unity plugin and the Unity CLI" moves from `house-rules.md` to
   `rules/standards/csharp-unity-standards.md`, so only Unity projects load it. That document
   splits into an always-injected core (C# style, a pointer, the Unity rule) and
   `rules/standards/csharp-unity-detail.md`, holding six sections moved unchanged: Project & folder
   structure, Unity-specific patterns, Performance, Testing, Verifying compilation, Tooling
   (Rider). `standards` now emits 5,782 chars for Unity only and 9,326 for Unity + Node.
3. The `profile` fallback detects CPU, RAM, GPU/VRAM, free disk and the Claude plan at runtime
   (nothing hardcoded), with per-probe timeouts and a `not detected (<reason>)` line on failure.
   On a remote session the numbers are labelled as the sandbox's; the local budget is the
   user's machine, from `rules/handover-target.md`.
4. `verify.py` gains the check that was missing: `standards` measured in a Unity-only and a
   Unity + Node project, plus cases for the Unity rule's placement, the hardware and plan
   fields, and the rule/detail agreement.

**Why.** Option B suits a plugin others install: people who do not use Unity stop paying for a
Unity rule. It only worked once the Unity standards were split, since adding the rule to the
existing document would have put a Unity + Node project past the hard limit. The overrun went
unseen because `verify.py` measured `standards` only in this repo, which has no Unity markers.
The plan tier is read from `claude auth status --json` and never assumed; in a cloud session
that output has no plan field, so the profile says "not detected" and Claude asks once.

**Rejected.** Option A (tightening three other rules' wording) kept the Unity rule in every
session for people who never open Unity. No `guard` pattern: recommending a product is prose,
not a shell command.

**Consequence (superseded by the path move below).** `tools/sync_standards.py` overwrites the vendored Unity document from
`Ajw2003/Coding-Standards`, which reverts the split. The new size check would fail after such a
sync; the fix is to make the same change upstream. Not verified: the macOS and Windows probe
branches, and whether a local claude.ai login reports a plan in `claude auth status`.

**Follow-up, same day: the detail file moved to `rules/standards/`.** The Unity detail file now
lives at `rules/standards/csharp-unity-detail.md`, not `rules/detail/`, so the plugin layout
mirrors upstream (`Ajw2003/coding-standards` carries both Unity files) and `sync_standards.py`
can no longer revert the split. `event_standards` loads only exact stems, so the extra file is
never injected.

**Status.** Standing.

---

## 2026-09-28 — A reply reporting finished work opens with a plain summary (#98)

**Context.** #98 asked for a human-facing document first, in plain terms, readable on mobile or
desktop. The user had just asked for a technical report to be re-explained in layman terms. Asked
which form "document" meant, the user chose a plain summary at the top of the chat reply — not a
file, and not a page, which would have reversed "never publish a page unasked".

**Decision.** A rule under "Plain language": a reply reporting finished work opens with what's
done, what it changes for the user and what waits on them, readable on a phone, before technical
detail. A `handover` (Stop) check for turns that wrote files or committed: a reply of 600+ chars
whose opening paragraph is a code block, a table or more than three code names, or which has a
table wider than three columns, is sent back once. `HOUSE_RULES_PLAIN_SUMMARY=off`.

**Why.** "Plain" cannot be judged from text, but its opposites can: an opening that is code, a
table, or a list of identifiers is not a summary for a person. Measured on this session before
shipping: the 4 real end-of-work replies all passed — which shows no false alarms, not that it
catches bad ones; the tests supply those. The core line brings inject to 8,919 of 9,000 chars.

**Status.** Standing.

---

## 2026-09-28 — Re-creating behaviour starts from an inventory; a visual change gets looked at

**Context.** #90 (with #86 and #87): a port to GitHub Pages silently dropped 10 features because
its spec was written from memory, only forced losses were disclosed, and every check compared the
new page with itself. #88 and #96: visual changes were judged by reading code, never by looking.

**Decision.** Rules: a port, rewrite, restructure or migration inventories the original from its
code first (keep/change/drop, shown before building), verifies against the original, names every
drop, and files an issue per deferred re-add (`rules/detail/parity-inventory.md`, pointed to from
the "Edit in place" core section, which already reaches subagents); a visual change is
screenshotted before and after (`rules/detail/visual-check.md`, one sentence under "A green test
suite"). Hooks: `scope` adds an inventory clause to a prompt that reads like re-creation;
`delegate` adds one to such a plan with no inventory; `handover` (Stop) reminds a re-creation
turn that wrote files but names nothing kept or dropped, and a turn that wrote a visual file
without capturing or reading an image.

**Why.** The failure happens at three points — the ask, the plan handed to a subagent, and the
report — so each gets a check. Rejected for the pattern: "replace" and "move to", which are
everyday edit words; a false positive at Stop costs a whole continuation. Measured: none of the
12 genuine prompts in this machine's transcripts matched; none was a port, so this shows no false
positives rather than proving true ones. Not built from #90's list: the feature-surface diff
tripwire (element IDs, workflow triggers, migration columns), which needs per-project knowledge
of what "the surface" is; the rule carries it instead. Both core additions fit the inject budget
(8,748 of 9,000 chars).

**Status.** Standing.

---

## 2026-09-28 — Subagents commit as they go, and cannot finish with unsaved work

**Context.** The user reported subagents committing less often than the main session. The cause
was in the agents' own instructions: `executor.md` and `archivist.md` both said "Commit messages
(only if asked to commit)", so a subagent never told to commit never did. 2.39.0's `audit` line
only named the leftovers to the parent afterwards. The user suggested either the same save logic
for subagents or a 1-minute autosave timer run by the main session.

**Decision.** The same save logic, at the subagent's own finish line. Both agents now commit each
finished piece as they go, scoped, unless the delegation said not to run git. A new
`subagentcommit` handler on `SubagentStop` returns `decision: "block"` when files the subagent
wrote are still uncommitted, judging each file in its own repo so worktrees are covered, and only
reports on the retry. Its own hook entry, so `verdict`'s report never depends on it.

**Why.** Probed live on CLI 2.1.284 before building: a `SubagentStop` block sent the subagent back
with the reason as its instruction, and the retry's payload carried `stop_hook_active: true`.
End to end in a throwaway repo, a subagent asked only to write a file committed it with the hook
(`Add hello.py`, clean tree) and left `?? hello.py` without it — one run each. Rejected: a
1-minute timer — it commits whatever state the files are in mid-edit, cannot tell the subagent's
edits from the user's, and would be exactly the unwatched background process "never hide work"
forbids. A hook at the point a piece of work finishes is the save point a timer approximates.

**Status.** Standing.

---

## 2026-09-28 — An instruction names its exact input (#47)

**Context.** Queued in `docs/rules-backlog.md` since 2026-09-07: verification steps whose whole
input was "ask for a multi-step handover", so no two runs could disagree.

**Decision.** A rule under "Deliver a whole workflow", core line plus a section in
`rules/detail/deliver-workflow.md`: an instruction the user acts on names the literal input, and
records the expected result when runs are to be compared. The backlog's two open questions: it
does not join the six handover items, which are about shell commands and would be diluted by a
broader rule; and it ships as rule text with no `verify.py` check, since whether an instruction is
specific enough is not a string match.

**Status.** Standing.

---

## 2026-09-28 — Verify a wait's target and working state before leaving it (#85)

**Context.** A test-runner wait reported "running" for its full 10-minute timeout on a run that
finished in 62 seconds: it was called with a bare class name while its verdict script matched by
full-name prefix, and it was piped through `tail`, so nothing showed until it ended.

**Decision.** A rule under "Nothing fails silently" (core line plus
`rules/detail/fails-silently.md`): before leaving a wait or background task, check its target
name against the source and run one status check. `guard` gains a `GUARD_R1` pattern that prompts
on a `while`/`until`/`sleep`/`timeout`/`watch` wait piped through `tail`/`head`.

**Why.** The pipe is the one part of the failure with a shell signature, so it is the part a hook
can catch. Rejected for now: matching test-wrapper names against test classes and Monitor
conditions against source — both need per-project knowledge the guard does not have; the rule
carries them. A plain `cmd | head` with no wait keyword stays silent.

**Status.** Standing.

---

## 2026-09-28 — The Stop evidence check catches "can't be done" and an unreasoned "not checked"

**Context.** #91, #92, #93 and #89 all report the same gap after 2.38.0 widened the evidence
rule: the rule text covered any claim of fact, but the `Stop` check only recognised success words.
"That isn't supported" said from memory went through, and so did "I haven't checked X" when X was
one command away.

**Decision.** Two additions to `handover`'s evidence check, sharing its one emission:
impossibility phrases ("can't be done", "isn't supported", "doesn't exist", "there is no
setting/flag/api/…") count as claims, under the same no-tool-this-turn and no-quoted-output
conditions as success words; and a "not checked" / "unverified" / lowercase "untested" phrase
fires whether or not tools ran, unless its own sentence gives a reason the check could not run.
A phrase opening right after a quote mark is exempt. The rules core now says "can't be done" is a
claim and checking is the default, not an offer.

**Why.** Rejected: a bare "can't" — it is everywhere in ordinary prose. Rejected: firing on the
card's `UNTESTED:` marker — the card rule already requires a reason beside it. The one existing
test that expected a bare "This is untested; I have not run it." to stay silent was flipped on
purpose: that sentence is exactly the disclosure-instead-of-checking #89 asks to stop. Measured on
this session's 49 real replies before shipping: 2 false positives, both quoted meta-talk, fixed
by the quote exemption; 0 after.

**Status.** Standing.

---

## 2026-09-28 — The commit rule's obligation half gets hooks: Stop, first change, audit, memory

**Context.** Issue #97: a multi-day task finished with nothing committed, on the user's `main`,
and no hook fired, because the plugin only enforced the *prohibition* half of the commit rule
(`guard` judges git commands that are run; a session that runs none gets no signal). A saved
memory restating the replaced "never commit without asking" rule had quietly won over the current
rule, and three executor runs told "no git" left the commit to a parent that never made it.

**Decision.** Four signals, all stateless and all behind `HOUSE_RULES_COMMIT_CHECK=off`:
- `handover` (Stop) gains a commit check: the `Write`/`Edit`/`NotebookEdit` paths since the last
  genuine user message, intersected with `git status --porcelain -uall`. Any left → a note naming
  them, with branch-aware advice. Only files this turn wrote count, so the user's own edits never
  trip it.
- A new `branchnudge` handler (`PostToolUse` `Write|Edit`) fires when the path just written is the
  **only** dirty path on a non-`claude/` branch — that is what makes it the first change, with no
  state kept.
- `audit`'s summary names files a subagent wrote that are still uncommitted: the parent owns them.
- `profile`'s preflight warnings flag an auto-memory file whose wording restates the old commit
  rule, and the rules core says a memory contradicting a rule is stale.
Both `scope` forms gain a commit line (long 911 chars, short 263, inside the +10% budgets).

**Why.** The failure was an omission, and only a check that looks for the omission can see it.
Rejected: a `PreToolUse` first-write nudge — its context reaches the model only alongside a
permission decision, and `allow` would skip the user's own write prompt. Rejected: a per-session
marker for "first write" — a second exception to the no-state rule, when "the only dirty path is
this one" answers the same question. Accepted limitation: `branchnudge` stays quiet when the user
already has uncommitted edits (the Stop check still covers the turn), and neither hook can tell a
harness-assigned session branch from the user's, so both say "if this branch was opened for this
session's work, commit there". The memory folder path (`<config>/projects/<project, non-alphanumerics
as ->/memory`) matched this machine's project folder naming; the `memory/` subfolder itself was not
present here to confirm.

**Status.** Standing.

---

## 2026-09-26 — versioncheck installs the update itself, and reads the install on disk

**Context.** A cloud session opened with the out-of-date banner: running 2.29.0, marketplace
2.36.0. Claude stopped and asked to run `claude plugin update`. But 2.36.0 was already installed
— something had updated it after the Claude process started — and `/clear` re-ran the check from
the old loaded copy. The update would have done nothing; a restart was the fix. Separately, the
user's environment setup script, which runs the update commands, is skipped when a cloud session
resumes from a cached environment, so it cannot keep the plugin current. The user asked for the
update prompt to do everything itself and install the update properly.

**Decision.** `event_versioncheck()` now reads `~/.claude/plugins/installed_plugins.json`. If the
newest version is already installed and only the running copy is old, it says "start a new
session" — no banner, no marker, no command. If an update is needed, the hook runs
`claude plugin marketplace update` (only if that clone is stale) and `claude plugin update`
itself, in a 60 s budget (hook timeout raised 10 → 90 s), then re-reads `installed_plugins.json`.
Only the new version appearing there counts as success, which is a one-line notice. On failure
the banner fires as before, now naming the failure, and tells Claude to run the commands itself
without asking in chat first — the `guard` prompt on that first command is the user's yes. The
card-and-stop fallback is kept for a declined prompt or no shell tool.
`HOUSE_RULES_AUTO_UPDATE=off` skips the automatic run. Shipped in 2.37.0.

**Why.** Asking permission for an update the user always wants is a question with one answer.
Re-reading the install, not the exit code, follows "a reported update is not a completed one".
Rejected: a detached background update — faster to start, but its result could not be checked
or reported. Rejected: relying on the setup script — it does not run on a cached resume.

**Supersedes.** 2026-09-17, "Ask permission to run the plugin's own update commands", for the
plugin's own update only; the general rule for other commands is unchanged.

**Status.** Standing.

---

## 2026-09-24 — versioncheck falls back to the GitHub API, and tells the model when it cannot verify

**Context.** On 2026-09-24 a session started with house-rules 2.31.0 installed while GitHub had
2.33.0, and nothing told the model. Two causes in `hook.py`: `_github_version()` fetched only
`raw.githubusercontent.com`, which that machine's sandbox reset while `api.github.com` worked; and
when installed and the marketplace clone agreed (both stale) and GitHub was unreachable, the
handler emitted only a `systemMessage` — shown in the UI, never seen by the model, easy to miss in
the desktop app. An unverified result looked the same as a verified one from the model's side.

**Decision.** `_github_version()` now tries the raw URL, then the contents API derived from the
same owner/repo/ref/path (`Accept: application/vnd.github.raw`, `HOUSE_RULES_VC_GITHUB_API_URL`
to override), both inside the existing 4-second budget, and records each failed route and why.
When the check could not finish and found no mismatch, it now also emits `additionalContext`
telling the model to say in its first reply that freshness could not be checked, naming each
failure and the installed version. It is still not "out of date": no banner, no `guard` marker.
The all-agree path stays a `systemMessage` trace only. Shipped in 2.35.0.

**Why.** "Nothing fails silently": a best-effort check that fails is fine, one that fails without
anyone who can act on it being told is not. A second route is cheaper than asking users to
diagnose a blocked host. Rejected: treating "couldn't verify" as "out of date" — it would block
every offline session on a question the user can't answer.

**Supersedes.** The previous behaviour, in which an unverifiable check told the model nothing.

**Status.** Standing.

---

## 2026-09-24 — Give each documentation tier its own numbered folder

**Context.** The six tiers all lived as flat files directly under `docs/` (`docs/Roadmap.md`,
`docs/ProjectState.md`, `docs/Today.md`, `docs/Decisions.md`, plus a `docs/systems/` folder), with
no signal in the filesystem itself that they sort in tier order or that they're a fixed set of
six. See [docs/plans/tiered-doc-folders.md](../plans/tiered-doc-folders.md) for the plan this
carried out.

**Decision.** Each tier now gets its own numbered folder: `docs/1-landing/`, `docs/2-roadmap/`,
`docs/3-state/`, `docs/4-systems/`, `docs/5-today/`, `docs/6-decisions/`, with the same filenames
inside them (so `docs/Roadmap.md` becomes `docs/2-roadmap/Roadmap.md`, and so on). The full tier-1
index moved into its folder as `docs/1-landing/README.md`; a new, short, human-facing
`docs/README.md` now sits at the top of `docs/` in its place, pointing back at the full index.
`docs/plain/` mirrors the same folder layout, so `docs/plain/systems/hook-engine.md` became
`docs/plain/4-systems/hook-engine.md`. This repo migrated its own docs at the same time as the
tooling changed, rather than leaving them on the old layout: every link and `doc-ref` pointer was
fixed, except inside `docs/archive/` and `docs/sessions/`, which stay untouched as historical
record, and except that old `docs/6-decisions/Decisions.md` entries below only had their link
paths repaired, not their prose — they describe what was true when they were written.

**Why.** Numbered folders sort in tier order in any file browser or `ls`, which a flat pile of
similarly-named files does not. Splitting the tier-1 index out from a short, people-facing landing
page lets each serve its own reader: `docs/README.md` for a person skimming the repo, and
`docs/1-landing/README.md` for the full technical index. The `docstiers` `SessionStart` hook and
the `plain_docs_check.py`/`docref.py` scripts were updated to the new paths in the same change; a
project still on the old flat layout is told which file moves to which new path, rather than
being told to scaffold tiers it already has.

**Status.** Standing.

---

## 2026-09-22 — A SessionStart check for the six documentation tiers, in every repo

**Context.** Step 3 of the rules-that-actually-load plan. The "Documentation goes in tiers" rule
was purely aspirational: nothing noticed a repo missing `docs/` entirely, or missing a tier,
until a person happened to look. The `house-rules:project-docs` skill already carries the full
tier spec and scaffolding steps, but a skill only loads when something tells Claude to load it.

**Decision.** A new `SessionStart` handler, `docstiers`, registered as its own `hooks.json` entry
(right after `standards`, before `versioncheck`) so a failure here can never affect
`inject`/`profile`/`standards`. It checks the project root (`CLAUDE_PROJECT_DIR`, else `cwd`) for
the six tiers exactly as `skills/project-docs/SKILL.md` names them: `docs/README.md`,
`docs/Roadmap.md`, `docs/ProjectState.md`, at least one file under `docs/systems/`,
`docs/Today.md`, `docs/Decisions.md`. All present: it emits nothing at all — the second
deliberate silent exception in the plugin besides `handover`, since it runs every session and a
trace would cost something on every one of them for what is usually true. Any missing: it names
exactly which and instructs loading `house-rules:project-docs` and scaffolding before any other
work, in every repo, including one that is not a git repository. In a git repository, it also
reads the remote's owner from `.git/config` directly (no subprocess — handles `https://` and
`git@host:` URL forms, and a worktree's `.git` file redirect via the existing `_git_dir` helper)
against `HOUSE_RULES_GITHUB_OWNER` (default `Ajw2003`, case-insensitive); not owned, or the
remote can't be read at all (garbage or unreadable `.git/config` — both treated as not-owned,
since scaffolding into a repo of unknown ownership is the riskier default), adds one more
instruction: add every scaffolded path to `.git/info/exclude`, so the new docs never leave the
machine or enter that repo's history. Fails loud via `systemMessage` on an internal error, like
`inject`. `verify.py` gained fixture-backed cases for all six named scenarios (complete, missing
+ owned, missing + not-owned, ssh-form remote, no `.git`, garbage/unreadable config), a size-limit
case (≤9,500 chars, fed the worst-case not-owned fixture), and a drift check that the six
hardcoded tier paths still match what `SKILL.md` names.

**Why.** The docs-tier rule already existed; what was missing was anything that acted on it
without being asked. A silent, every-session check that only ever speaks when something is
actually wrong is the same shape `handover` already uses, extended to a second case where it's
provably the cheaper choice — this runs on every session, unconditionally, so a trace on the
common (complete) case would be paid far more often than the harvest/artifact traces it's
modeled after. The ownership check exists because scaffolding is a write: creating files nobody
asked for in a repo you don't own is the wrong default, so the safer path is to make the write
invisible to that repo's history until someone deliberately commits it.

**Status.** Standing.

---

## 2026-09-22 — CLAUDE.md becomes a real pointer; correct the "re-paid on every subagent spawn" claim; profile truncates only the environment body

**Context.** Step 2 of the rules-that-actually-load plan. Root `CLAUDE.md` had grown to 33,083
bytes despite its own header claiming it "stays short on purpose" — it carried the full hook
table, the design-constraints list, and the surfaces table verbatim, none of which changes when
someone opens an unrelated repo file, and all of which already had a home (or belonged in one) in
`docs/architecture.md`. Separately, `CLAUDE.md` and several docs (`docs/measuring-footprint.md`,
`docs/architecture-backlog.md`, `tools/measure_footprint.py`'s own output) asserted that
SessionStart's injected text is "re-paid on every subagent spawn" — this was never tested and is
false: a spawned subagent's context is its own agent file plus whatever the delegation prompt
passes it; SessionStart's `additionalContext` never reaches it at all
(docs/plans/2026-09-22-rules-that-actually-load.md records the probe). Coordinator review of the
prior commit also found `profile`'s truncation cut the whole assembled profile text, which could
in principle cut into the preflight warnings or the remote handover-target block instead of just
the oversized environment body.

**Decision.** `CLAUDE.md` is now 3,151 bytes: what the repo is, a pointer to `docs/README.md`,
the rules-pointer paragraph, and the command list as one line plus one clause each. The hook
table, the design-constraints list, and the surfaces table moved into `docs/architecture.md` —
the surfaces table merged into its existing "step-card handover format" section rather than
adding a duplicate. `verify.py` gained a named `CLAUDE_MD_BYTE_LIMIT = 4_000` check, and every
check that used to read CLAUDE.md's hook/surfaces/constraints tables (the architecture-tables
check, the surface-coverage check, the publish-a-page table check, the opusplan-scoping check)
now reads `docs/architecture.md` instead — none deleted or narrowed. The false subagent-spawn
claim is corrected everywhere it appeared, with the tested fact stated plainly and a pointer to
where the consequence is documented (`@house-rules:executor`/`@house-rules:archivist` carrying
their own rules digest). `profile` now computes a budget for the environment body alone
(`PROFILE_SOFT_LIMIT` minus the fixed preamble/preflight/handover length) and truncates only
that piece; a new `verify.py` case feeds it an oversized environment file plus a remote handover
fixture and asserts both the handover block and the preflight warning survive intact while the
truncation notice still names the oversized file.

**Why.** A root `CLAUDE.md` that says "stays short on purpose" while carrying 33KB is the exact
kind of drift the rules exist to catch elsewhere — the fix here is the same discipline applied to
the file that states it. A wrong claim about subagent context is not cosmetic: a session claiming
"the rules are re-paid on every subagent spawn" is a session that will not think to ask whether
`@house-rules:executor` actually has them, and the two subagent files that matter here already
had to compensate for the real answer with their own digest. And truncating the wrong part of
`profile`'s output — the handover-target block, say, instead of an oversized environment.md — is
a strictly worse failure than the one the truncation was added to prevent: silence about a fact
the user could act on, in a hook whose whole job is telling Claude what machine it's on.

**Status.** Standing.

---

## 2026-09-22 — Split the machine profile into its own SessionStart hook, and expand ${CLAUDE_PLUGIN_ROOT} at emit time

**Context.** Step-1 review of the rules split above found two defects the suite did not catch.
First, the size check measured `inject` with no recorded `rules/environment.md`, so it missed
that a *real* recorded profile pushes the combined text over budget: fed a copy of
`docs/example-environment.md`, `inject` emitted 12,695 chars — over Claude Code's 10,000-char
per-hook limit, so on a real machine with a hand-verified profile the rules would again be
persisted to a file instead of reaching the model in full. Second, the trimmed core's detail
pointers read literally as `${CLAUDE_PLUGIN_ROOT}/rules/detail/<file>.md` in the emitted text —
that variable is expanded by the harness inside `hooks.json`'s own command strings, but never in
`additionalContext`, so Claude was being handed a path it could not open.

**Decision.** The machine profile (a recorded `rules/environment.md` or its runtime-detected
fallback, preflight warnings, and the remote handover-target block) moved out of `inject` into a
new `profile` SessionStart handler, registered as its own `hooks.json` entry right after `inject`
so a failure in one can never take the other down — same fail-loud (`systemMessage`) pattern.
`inject` now carries only the rules core, and substitutes `${CLAUDE_PLUGIN_ROOT}` for the real
absolute plugin root (derived from `hook.py`'s own location) before emitting. `profile` truncates
its own output with a visible notice naming the oversized file if a recorded profile would itself
push it over budget, rather than silently overflowing. `verify.py`'s size check now asserts
`inject` ≤ 9,000 chars (tighter than before, since it no longer carries runtime-varying content)
and `profile` ≤ 9,500 chars fed `docs/example-environment.md` as a stand-in for a real recorded
profile — the realistic case that actually overflowed. Added a case asserting no literal
`${CLAUDE_PLUGIN_ROOT}` reaches the injected text and that one named detail path resolves on
disk. Updated the `CLAUDE.md` and `claude-house-rules/README.md` hook tables for the new entry.

**Why.** The size check the first pass shipped measured a scenario (no recorded profile) that
understated the real one — the whole point of a recorded `rules/environment.md` is that most
users who bother to write one will have more to say than the runtime-detected fallback, not less.
Splitting the hook, not just trimming further, is the structural fix: the limit is per hook, so
the machine profile competing with the rules core for the same 10,000-char budget was always
going to reproduce the original bug the moment either side grew. And a pointer variable nothing
expands is not a pointer, it is a string that looks like one.

**Status.** Standing.

---

## 2026-09-22 — Split house-rules.md into an imperative core and rules/detail/*.md, so the rules actually reach the model

**Context.** A grilling session on 2026-09-22 found that `inject` emitted 44,506 chars.
Claude Code saves any single hook's `additionalContext` over 10,000 chars to a file and puts only
a ~2KB preview in context — everything past the first section of `house-rules.md`, including the
docs-tier rule, was invisible in that session. `house-rules.md` had doubled since the 2026-09-07
footprint work (20.8KB → 43KB), because that earlier pass's practice was to keep every "Why:"
rationale block inline rather than move it out — a reasonable call at 20.8KB, wrong at 43KB.

**Decision.** `house-rules.md` is now an imperative-only core: one to three sentences per rule,
plus a pointer naming `${CLAUDE_PLUGIN_ROOT}/rules/detail/<topic>.md` for that rule's full
rationale, "Why:" block and examples, moved there verbatim. `#### The card` collapses to a
pointer at the forced `handover-cards` output style, which is now the single copy of the
step-card checklist — the core no longer restates it. A new `INJECT_CHAR_LIMIT = 10_000` constant
in `hook.py` documents the hard limit; `verify.py` checks the real emitted `inject` and
`standards` `additionalContext` (not source file size) against a 9,500-char safety margin, each
checked separately since Claude Code's limit is per hook. Every verify.py drift check that used
to grep `house-rules.md` alone for a phrase now greps a corpus of `house-rules.md` plus every
`rules/detail/*.md` file — the phrase still has to exist somewhere the rules own, it no longer has
to survive being injected. The one check that could not be satisfied this way (the six-field
step-card checklist, since it deliberately left the injected text) was repointed instead: it now
checks that the core's `#### The card` section names `handover-cards.md` and does not restate the
checklist, rather than requiring the checklist phrases to appear in the injected text.

**Why.** A rule nobody's context contains is not a rule, it is a file. Keeping every rationale
block inline reversed the 2026-09-07 decision to do exactly that, because the number that mattered
— total injected size, not "does this file still read well" — had moved past the point where the
choice was free. Moving detail out loses nothing: `docref.py check`-style corpus checking means
every phrase a test ever pinned is still provably present, just no longer paid for on every
session start.

**Status.** Standing.

---

## 2026-09-22 — Guard against a full-file rewrite standing in for an in-place edit

**Context.** In a separate project, a scheduled, unattended task rewrote a CSS file wholesale
instead of touching the one thing that needed to change. Nobody was watching that run in real
time, so the regression it introduced sat unnoticed until someone found it later. The existing
destructive-action rule did not catch this: it explicitly carves out "ordinary edits to tracked,
committed files" because git already holds them, and a full-file rewrite of a tracked file fell
inside that carve-out even though it discards everything the change was never meant to touch. The
`guard` hook's `rm` pattern had a matching gap of its own — it only matched `rm -r`/`rm -f`, so a
plain `rm styles.css` (no flag needed to delete a single existing file) went unmatched too.

**Decision.** A new rule in `rules/house-rules.md`, "Edit in place; a full rewrite is a delete,
not an edit": changing only the lines that need to change is the default, and a full rewrite of a
file that already exists is a manually approved exception, named by what it discards and why,
whether or not the run is attended. Enforced by a new hook, `guardwrite`, registered at
`PreToolUse` on `Write` — since `Write` always replaces a file's entire contents, any call
targeting a path already on disk is a full-file replacement by definition, and `guardwrite` asks
every time, naming the path and the line counts where it can read both. It fails closed like
`guard`: an unreadable payload or internal error blocks the write rather than letting an
unchecked overwrite through. Also broadened `guard`'s `rm` pattern from `rm -r`/`rm -f` only to
any `rm <target>`, closing the plain-single-file-delete gap the same incident exposed on the
shell side. Updated `CLAUDE.md`'s hook table, `claude-house-rules/README.md`'s hook table and
"What trips the guard" table, and `docs/systems/hook-engine.md`. Bumped the plugin version
2.29.0 → 2.30.0.

**Why.** Git being able to recover the old blob after the fact is not the same as the regression
being caught before it ships — especially on a run nobody was watching. The destructive-action
rule's tracked-file carve-out was written for edits that change a few lines under version control,
not for a rewrite that discards the whole file and gambles that the new version is complete and
correct. Closing the gap needed both a rule (what "ordinary edit" excludes) and a mechanism
(`guardwrite`), because a rule with no shell or tool signature to match on is exactly the kind
that gets read once and then drifted past.

**Status.** Standing.

---

## 2026-09-20 — Issue and pull-request text never names a local path

**Context.** Issue #65 on this public repository was published with the user's local project
path in its body. The user closed the issue and asked for a standing rule.

**Decision.** A new rule in `rules/house-rules.md`: titles, descriptions, comments and review
comments on issues and pull requests never contain a path from the user's machine (a drive letter,
a home directory, another project's folder, a scratchpad or temp file). Files are named by
repo-relative path, other repositories by name or `owner/repo`. The check covers a body file
passed with `--body-file`. Commands handed to the user to run keep their absolute local paths,
since that text never leaves their machine. Commit messages are not covered: the user did not ask.
Plugin bumped to 2.29.0 for the added rule.

**Alternatives rejected.** A `guard` pattern on `gh issue`/`gh pr` commands: the local path lives in
the body file's contents, not in the command line, and a `--body-file` argument is itself a local
path, so the pattern would prompt on every legitimate call. Restating the rule in the `scope`
per-prompt reminder: it would cost tokens on every prompt for a rule that only matters when
publishing.

**Why.** A local path tells another reader nothing, discloses how the user's machine is laid
out, and stays in the edit history after the text is corrected. The rule is carried by the
session injection alone, so the check is the model's.

**Status.** Standing.

---

## 2026-09-20 — Pointers carry a stable id, and a command keeps them true

**Context.** The archivist left "a one-line pointer naming the document and section". Nothing
checked it, so a renamed heading or a doc moved to `docs/archive/` left the pointer lying, silently.
The `project-docs` skill said to "fix the pointers" when a doc moves, with no tool behind it.

**Decision.** A moved note gets a 4-hex id. In the doc it is a `<!-- ref:<id> -->` marker alone on
its own line under the heading; in code it is `doc-ref <id> <path>` in any language's comment
syntax. `scripts/docref.py` has `check` (ok / stale / dangling / ambiguous / malformed),
`fix --write` (rewrites stale paths by id only), and `new` (an unused id). It is a command, run by
`verify.py` and `/house-rules:docref`, **not a hook**: a doc-write hook is deferred until its cost
can be measured against a working checker. Existing prose pointers are left alone and only counted.

Three refinements over the spec, found while writing the plan: (1) a marker must be alone on its
line, so a doc that quotes one inline does not register a fake marker; (2) the file list is
`git ls-files --cached --others --exclude-standard` when the root is a git work tree, else a
directory walk, and the output names which — so ignored build output is never read and a note
moved into an uncommitted doc is still seen; (3) `--exclude GLOB` (recorded in the spec), matched
case-sensitively against the whole relative posix path, with a note when a pattern matches nothing.

Fences in docs follow the CommonMark opening/closing rule: a fence closes only on the same
character with a run at least as long, any other fence-looking line inside is content, and a doc
that ends inside a fence is reported MALFORMED at the line that opened it. `fix --write` writes a
temp file beside the source and `os.replace`s it, so an interrupted write never truncates code.
The states a run can report are ok, stale, dangling, ambiguous, malformed, duplicate (two markers
claim one id), unreadable and undecodable (a doc under `docs/` that is not valid UTF-8).

`fix`'s exit code is not a proxy for `check`'s. `fix --write` exits 0 when it could not read a file
at scan time (it names the file), and exits 2 only when a file it found fails at rewrite time,
while `check` exits 1 for that same unreadable file.

Three behaviours were added in review. When the directory-walk fallback is used, the "scanned"
line says why (`via directory walk (git did not list files: <reason>)`), and walk errors such as
unreadable directories are reported as UNREADABLE findings and fail the check. `fix` names
unreadable files (UNREADABLE lines, counted in its "still unresolved" summary) and keeps exit 0
for that, but handles each pointer file's read and write separately and returns 2 if any file
could not be read or written after being found, printing UNREADABLE/UNWRITABLE per file and how
many failed; `new` keeps the id alone on stdout and warns on stderr if any file was unreadable,
since the id may collide. The live check in `verify.py` runs `docref.py check` on this repo with
`--exclude` for `verify.py` and `docref.py`, which hold example pointers on purpose.

**Alternatives rejected.** Path plus heading anchor (a rename is indistinguishable from a
delete, so the fixer can only guess); fuzzy-matched heading text (repairs are guesses a person
must review); a hook on doc writes (adds file reads to the write path before we know what they
cost); extending `harvest_scan.py` (a different job, finding comments to move, in the same file).

**Why.** A pointer that can lie silently is worse than none: it is trusted. An id makes the
common failure (doc moved or renamed) mechanical, and everything that is not mechanical
(a deleted note) is reported with `file:line` for a person to decide.

**Status.** Standing. Piece B of the harvest content-rules work; A and C build on it.

## 2026-09-20 — Size the harvest threshold by characters alone, default 500

**Context.** `/house-rules:harvest-scan` on a real Unity project returned 831 blocks. The size
test in `_harvest_blocks` was `lines >= 3 OR chars >= 150`, so a block qualified on either axis:
three short lines were enough, and 150 characters (about 25 words) is an ordinary "why this line
is odd" note, not an essay. About 99% of that project's comment blocks tripped it.

**Decision.** Characters are the only size criterion, default `HARVEST_MIN_CHARS = 500` (about 80
words). `HARVEST_MIN_LINES`, `HOUSE_RULES_HARVEST_MIN_LINES` and `harvest_scan.py --min-lines` are
removed. Characters are counted over the joined text, so wrapping and indentation cannot move a
comment across the line; a line count can. Plugin version bumped to 2.27.0 for the removed knob.
On that project 500 flags 218 blocks (820 at 150); on this repo it flags 0.

**Alternatives rejected.** Keeping the lines knob and setting `MIN_LINES` very high per machine —
works without a code change, but leaves a dead criterion in the handler and a default that is still
wrong for everyone else. Words instead of characters — same signal, needs a tokenizer for no gain.

**Why.** The threshold only narrows what gets looked at; each flagged block is still moved or kept
by judgement (a subtle-ordering-bug comment can stay in place with a pointer). The table is in
[comment-harvest-calibration.md](../comment-harvest-calibration.md); if 218 is still noise, raise
`HOUSE_RULES_HARVEST_MIN_CHARS` to 800 rather than editing the constant.

**Status.** Standing.

---

## 2026-09-20 — Use the braced `${CLAUDE_PLUGIN_ROOT}` in `/house-rules:harvest-scan`

**Context.** `/house-rules:harvest-scan` failed in a real session: `commands/harvest-scan.md` ran
`python "$CLAUDE_PLUGIN_ROOT/scripts/harvest_scan.py"`. Claude Code substitutes only the braced
form `${CLAUDE_PLUGIN_ROOT}` inline in plugin content (every `hooks.json` entry uses it) and does
not export the variable to the Bash tool's shell, so the bare form expanded to empty, giving
`/scripts/harvest_scan.py`, which Git Bash mapped to `C:\Program Files\Git\scripts\...` (exit 2).
`verify.py` only checked that the literal text `$CLAUDE_PLUGIN_ROOT` appeared, so it passed while
the command was broken.

**Decision.** The command now uses `${CLAUDE_PLUGIN_ROOT}` and tells Claude to stop and report if
the path did not resolve, rather than searching `~/.claude/plugins` or guessing (the cache holds
several versions). `verify.py` now requires the braced form and the stop instruction, and fails if
any file under `commands/` contains a bare `$CLAUDE_PLUGIN_ROOT`. Plugin version bumped to 2.26.2.

**Why.** A check that only proves a string is present cannot catch a string that is present but
never substituted. The bare-form ban is the assertion that would have failed on the original.

**Status.** Standing.

---

## 2026-09-20 — Reproduce the install-upgrade fix against the real CLI before trusting it

**Context.** `tools/` had no coverage of `install.py` at all before 2.15.0, and the gap cost
something concrete: `claude plugin marketplace add` answers "already on disk" for a marketplace
the device has already seen and does not re-fetch it, so the cached clone stayed on the old
commit and `claude plugin update` afterward reported "already at the latest version" — naming
the **old** version, a confident wrong answer. Unit-testing `install.py`'s `install_steps()`
order in isolation would prove the sequence was internally consistent without proving it fixed
anything a real machine would hit.

**Decision.** Before trusting the fix (inserting `plugin marketplace update` into the sequence),
it was reproduced against the real `claude` CLI: a stale cache registered version 2.17.0; running
the *old* three-command sequence against it reproduced the "already at the latest version"
lie naming 2.17.0; running the fixed four-command sequence against the same stale cache reported
"updated from 2.17.0 to 2.18.0" correctly. `tools/verify_tools.py`'s install-upgrade-path checks
(`verify_tools.py:313-322`) pin the resulting **order** of `install_steps()`'s four commands,
without shelling out to the real CLI or mutating a machine's config on every test run — that
real-CLI reproduction was a one-time manual step, not something the automated suite repeats.

**Why.** `install_steps()`'s docstring and `docs/systems/plugin-distribution.md` already record
*why* the order must be add/update/install/update. What wasn't recorded anywhere is that the fix
was confirmed against the actual failure mode on the actual CLI, not just argued for — and that
distinction matters because the argument alone ("marketplace add doesn't re-fetch") could be
right in theory and still miss some other reason `plugin update` reports what it does. Recording
the reproduction is what lets a later reader trust the checks are testing the right thing, not
just a plausible-sounding invariant.

---

## 2026-09-20 — Give the archivist a two-pass process for batch harvests

**Context.** Running `/house-rules:harvest-scan` against this repo at the harvest hook's own
default thresholds (3 lines / 150 chars — see
[`comment-harvest-calibration.md`](../comment-harvest-calibration.md)) found 162 blocks across 16
files. The archivist agent's instructions describe per-block judgment (tier-4 systems doc vs.
`docs/Decisions.md`) but say nothing about how to behave at that scale. Dispatched with 162
blocks in one shot, nothing stopped a plausible shortcut: paste everything into one tier-4 doc,
verbatim, with pointers, and report the sweep done — which is capture, not the actual
redistribution the harvest rule asks for (see "Long-form reasoning goes in a document, not in a
comment" in `rules/house-rules.md`).

**Decision.** Added a "Working from a batch" section to
[`agents/archivist.md`](../../claude-house-rules/plugins/house-rules/agents/archivist.md) requiring
two explicit passes whenever more than a handful of blocks are handed over at once: Pass 1 lands
every block verbatim, with `file:line` citations, into a dated scratch file at
`docs/plans/<date>-harvest-staging.md`; Pass 2 works through that staging file entry by entry,
applying the existing per-block classification, moving each into its real tier-4 doc or a dated
`Decisions.md` entry, updating the original site's pointer to the final destination, and deleting
the entry from staging. The staging file is explicitly scratch, not a seventh tier — the report
must confirm it was deleted, or say exactly what is still in it and why. A single block flagged
live by the `harvest` hook is unaffected; it still goes straight to its final destination in one
pass, per the agent's original instructions.

**Why.** The whole point of the harvest rule is that reasoning ends up somewhere it can be
maintained and found — a tier-4 doc or a dated decision, not a comment nobody re-reads. A batch
run that dumps 162 blocks into one document with pointers satisfies "verbatim" and "pointer" but
not "found where it belongs," and nothing in the agent's prior instructions would have caught
that as incomplete. Splitting capture from redistribution, and making the staging file's own
emptiness the completion signal, closes that gap without changing how a single live-flagged block
is handled.

---

## 2026-09-20 — Fix the harvest handler treating an Edit fragment's line 1 as the file's header

**Context.** A user's screenshot showed a trace reading "2 comment runs, none met 5 lines / 300
chars; longest was 7 lines, 397 chars (file header)" — self-contradictory, since 7/397 clears
5/300. `_harvest_blocks()` exempts a comment run starting at line 1 as a module docstring/file
header, which is correct for a `Write` (whose `content` is the whole file, so line 1 really is
the file's first line) but was applied unconditionally, including to `Edit`'s `new_string`. An
Edit's fragment has its own line numbering starting from wherever the replacement begins — so an
Edit that happened to insert or replace a comment block at the top of its fragment got exempted
as a "file header" purely by coincidence of where the edit started, not because it was one.

**Decision.** Added a `full_file` parameter to `_harvest_blocks()` (default `True`, preserving
`Write` and standalone full-file-scan behaviour); `event_harvest()` now passes `full_file=ranged`
so an `Edit` never gets the file-header exemption. Separately, fixed `_harvest_trace()`'s summary
line, which always said "none met N lines / M chars" regardless of the actual rejection reason —
now it only says that when the longest run genuinely failed the size check, and names the real
reason (file header, license header, commented-out code, etc.) when a run met the size threshold
but was rejected for cause. Also lowered the defaults from 5 lines/300 chars to 3 lines/150 chars
per direct request, and normalized C#'s `///` doc-comments (and `////` dividers) by stripping all
leading slashes rather than just the two the `//` marker consumes. Added `harvest_scan.py` for a
manual, project-wide sweep using the same detection code, and wrapped it in a rerunnable
`/house-rules:harvest-scan` command (`commands/harvest-scan.md`) so it resolves the installed
plugin's script via `$CLAUDE_PLUGIN_ROOT` instead of requiring a hand-built plugin-cache path.
Bumped the plugin version.

**Why.** The bug meant `Edit` calls — the common case for touching an existing file, as opposed
to `Write`'s full-file rewrite — could silently exempt exactly the comment blocks the handler
exists to catch, whenever the edit happened to start on one. The trace wording bug compounded it:
even where the file-header exemption was correct (a real `Write`), or where a different exemption
fired (license, commented-out code), the message claimed "none met the threshold," which reads as
the detector missing an essay rather than deliberately setting it aside — the exact confusion that
surfaced the bug in the first place.

**Status.** Standing.

---

## 2026-09-17 — Ask permission to run the plugin's own update commands, rather than only relaying them

**Context.** The previous entry above fixed *how* a hook-relayed command gets handed over (card,
`UNTESTED:`, then stop and wait) but not *whether* handing it over was the right move at all. A
real user hit exactly that card on the desktop Code tab and could not act on it: the desktop's own
plugin-update button was greyed out on a stale marketplace cache, and the card's fix commands ran
into the same wall the button did, because both routes required the user's own hands. Meanwhile
`rules/house-rules.md` already says "the user's hands are for decisions, not labour" and Claude's
own shell tool, in that same session, reaches the exact machine the freshness check just read —
running the two refresh commands itself was always possible, and never attempted.

**Decision.** Extended `event_versioncheck()`'s banner in `hook.py` to instruct Claude to ask the
user's permission to run the marketplace-refresh and plugin-update commands itself, on this
machine, right now, and only fall back to relaying them through the step-card format (unchanged
from the previous entry) if the user declines or the session has no shell tool. Added a matching
paragraph to `rules/house-rules.md` under "Never hand over a command I have not run where they
will run it," updated `CLAUDE.md`'s hooks table, and extended `verify.py`'s banner and drift checks
to require the new ask-permission instruction alongside the existing card/`UNTESTED:`/stop-and-wait
ones. Bumped the plugin version 2.24.2 → 2.24.3.

**Why.** A command handed over for the user to run is still labour if Claude could have run it
instead — the card format exists for commands only the user's own hands can execute (a different
shell, a different machine, credentials Claude doesn't hold), not as a default for every relayed
fix. It's also the more reliable path here specifically: the CLI refresh works even when the
surface that would otherwise run it (a greyed-out desktop button) does not, so offering to run it
directly sidesteps a UI bug rather than routing the user straight into it.

**Status.** Superseded for the plugin's own update by 2026-09-26, "versioncheck installs the update itself"; standing for every other command.

---

## 2026-09-17 — Route a hook-relayed command through the same verified-command rule as any other

**Context.** A live session hit `versioncheck`'s out-of-date banner (installed plugin behind the
marketplace clone), printed the exact fix command as a plain fenced block with no `UNTESTED:`
label, and moved straight into unrelated repo exploration in the same reply — the command had
never been run on that machine, and the turn never paused for an answer. `rules/house-rules.md`
already had a rule against handing over an unverified command, and a narrower rule about stopping
after a page offer; neither said a command relayed from a hook's own diagnostic got the same
treatment, so `event_versioncheck()`'s banner text told Claude only to "tell the user plainly ...
and give them the update command(s)," with no card/`UNTESTED:` instruction and no instruction to
stop.

**Decision.** Extended "Never hand over a command I have not run" in `rules/house-rules.md` to
cover a command relayed from a hook, tool, or diagnostic explicitly — same card, same `UNTESTED:`
marker unless actually run this session on this machine — and added "Telling them is not the same
as stopping for them": once something needs the user's answer before I continue, I say so and then
stop, rather than continuing into unrelated work in the same turn. Reworded `event_versioncheck()`'s
banner in `hook.py` to instruct exactly that (card format, `UNTESTED:`, then stop and wait), and
updated `CLAUDE.md`'s hooks table to match. Added a `verify.py` check that the banner actually
carries those instructions (not just the right command), and a bidirectional drift check between
`rules/house-rules.md` and the banner text so a future reword on either side gets caught — see
`docs/systems/verify-suites.md`, "Traps". Bumped `plugin.json` 2.24.1 → 2.24.2 for the rule/hook
change.

**Why.** The command-verification rule and the page-offer stop-and-wait rule already existed
separately; a command that arrived via a hook's own diagnostic fell through the gap between them
because neither one said it applied to a relayed command. Naming the problem out loud and then
continuing into unrelated work is functionally the same failure as never naming it — the user
still has to notice, on their own, that nothing is actually waiting on their answer.

**Status.** Standing.

---

## 2026-09-15 — Widen the version-bump gate to root CLAUDE.md and docs/, not just PLUGIN_ROOT

**Context.** While preparing to merge the docs-tier-scaffolding PR (the one that added
`docs/README.md`, `Roadmap.md`, `ProjectState.md`, `Today.md`, and `docs/systems/*`),
`tools/check_plugin_version_bump.py` (added the same day; see the entry below) reported "no
plugin files changed, no bump required" for a PR that changed only root `CLAUDE.md` and files
under `docs/`. The user objected: both are directly used by the plugin and change as the plugin
is worked on and used live in this repo — `CLAUDE.md` is auto-loaded into every session here, and
`docs/` is read and written continuously while following the rules — even though neither ships
inside the installed plugin package the check's `PLUGIN_ROOT` constant was scoped to.

**Decision.** Widened `check_plugin_version_bump.py`'s notion of "plugin-relevant" beyond
`PLUGIN_ROOT` to also cover the root `CLAUDE.md` file (exact match) and everything under `docs/`
(prefix match), via a `PLUGIN_RELEVANT_PREFIXES`/`PLUGIN_RELEVANT_EXACT` pair and an
`_is_plugin_relevant()` helper. Added matching cases to `tools/verify_tools.py`'s `decide()`
table. Bumped `plugin.json` 2.24.0 → 2.24.1 for the PR this was raised against, now that it
requires one under the widened rule.

**Why.** The check exists to stop the exact failure the entry below describes — a version-gated
updater reporting "already at the latest version" while content the user actually relies on has
changed underneath it. Root `CLAUDE.md` and `docs/` are exactly that kind of content for this
repo: they're not packaged into what `claude plugin install` ships, but they're what a live
session in this repo actually reads and is governed by, which is the same "did the thing I rely
on change" question the original incident was about. Scoping the check to `PLUGIN_ROOT` alone
answered a narrower question than the one it was built to answer. The alternative — leave the
check as-is and just bump the version for this one PR without changing the check's logic — was
rejected because it would have left the same gap open for the next PR that touches only
`CLAUDE.md` or `docs/`.

**Status.** Standing.

---

## 2026-09-15 — Enforce the version bump instead of trusting it, in this repo and on the desktop

**Context.** Two merged PRs (#33, #34) changed files under
`claude-house-rules/plugins/house-rules/` without bumping `.claude-plugin/plugin.json`'s
`version`. Every prior content-changing commit had bumped it; nothing enforced the convention, so
it silently lapsed. The result: `claude plugin update` — version-gated — reported "already at the
latest version" on the desktop after a full `tools/bootstrap.ps1` run, while the installed cache
still held the pre-#33/#34 content. `tools/force_update.py` (a pre-existing manual escape hatch
that hash-compares the installed cache against the marketplace source tree) confirmed the mismatch
and, once run, confirmed the fix after #35 bumped the version. The real failure was not "forgot to
bump a number" — it was that a tool's own "already up to date" message was trusted without
checking whether the underlying content actually matched. Full design:
[`docs/plans/2026-09-15-plugin-version-bump-guard.md`](../plans/2026-09-15-plugin-version-bump-guard.md).

**Decision.** Two separable fixes for the two places this failed. (1) This repo: a new
`tools/check_plugin_version_bump.py` compares `plugin.json`'s version between a PR's base and
head whenever a file under the plugin changed, and fails the change if the version did not
strictly increase; wired into the existing `verify` CI job (`fetch-depth: 0` plus a
pull-request-only step), with branch protection on `main` requiring that check to follow in a
separate step once this PR merges. (2) Any project: a new house rule, "A reported update is not
a completed one," naming this failure shape by pattern rather than by PR number. (3) Local
tooling: `tools/install.py`'s install steps now hash-compare the installed cache against source
after every install/update, using `tree_hash()`/`diff_trees()` factored out of
`tools/force_update.py` into `tools/_plugin_sync.py` so the two scripts share one implementation;
on a mismatch it automatically runs the same uninstall+reinstall sequence `force_update.py` used
manually, re-verifies, and only surfaces to the user if that self-heal still doesn't match.

**Why.** The convention ("bump the version when you touch the plugin") was correct but
unenforced, so it lapsed exactly once and nothing caught it before it shipped. A reminder to
"remember next time" would have the same shelf life as the original convention. Enforcement — a
CI gate that blocks the merge, and local tooling that verifies rather than trusts — closes the gap
structurally instead of relying on memory a second time. The house rule generalizes the lesson
beyond this repo: any version-gated updater can report "no-op" truthfully about the one field it
compared while being wrong about whether the underlying content changed.

**Status.** Standing.

---

## 2026-09-15 — Distinguish "the machine I run on" from "the machine a handover targets"

**Context.** A Step 2 command handed over earlier the same day assumed Linux/bash — wrong, the
user is on Windows/PowerShell. Root cause, confirmed by reading the code: `rules/house-rules.md`'s
"Find out what machine you are on, then build for that" rule and `hook.py`'s
`_detect_environment()` only ever described **the machine executing this session's tool-calls**.
For a local CLI/IDE/Desktop-Code-tab session that machine and the user's own machine are the same
box, so the rule had always been correct there. The session that made the mistake was remote
(`CLAUDE_CODE_REMOTE=true`, `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`): the sandbox
`hook.py` ran on was Linux, the user's actual machine was Windows, and nothing in the rule or the
injected "This machine" profile ever flagged that these could differ. The rule's own example text
even listed "a cloud session on Linux" as just another machine to build for, reinforcing the
conflation instead of catching it. The evidence needed to fix this without guessing already
existed in the repo: `docs/example-environment.md`, a committed worked-example record of aj's real
machine (Windows 11 Pro, PowerShell, Git Bash for POSIX, `sh`/`bash` not on PATH), dated
2026-08-25 — and the user separately confirmed PowerShell was in fact right. Full design in
[`docs/plans/2026-09-15-handover-target-machine.md`](../plans/2026-09-15-handover-target-machine.md).

**Decision.** Give the plugin a second, distinct machine-local record —
`rules/handover-target.md`, gitignored, same shape and lifecycle as `rules/environment.md` — that
answers "what machine will a human run a step-card's command on," never confused with the
sandbox's own profile. `hook.py`'s `event_inject()` only reads and injects it when
`CLAUDE_CODE_REMOTE` is set, so a local session pays nothing: recorded content is injected under a
heading distinct from "This machine"; missing content becomes an instruction to find out (check
`docs/example-environment.md`, or ask) and record it, so a later session in the same remote
environment does not have to ask again. Extended the "Find out what machine you are on" rule in
`rules/house-rules.md` with a clause naming the local/remote distinction, added matching
`verify.py` cases and a drift check, and updated `.gitignore` and the root `CLAUDE.md` hook table.

**Why.** The two questions — where do my tool-calls run, and where will the user run what I hand
them — are the same question on every local session, which is why the conflation was invisible
until a remote session exposed it. Detecting the user's actual machine at runtime is impossible
from inside the sandbox; the fix is to make the gap askable and rememberable exactly once per
remote environment, rather than silently building for the wrong machine.

**Status.** Standing.

---

## 2026-09-15 — A third non-tier folder, `docs/generated/`, for generated artifacts

**Context.** The tiered-docs system had two non-tier folders: `docs/plans/` (forward intent) and
`docs/archive/` (inert docs) — both hand-written. The `artifact` hook already caught a document
written outside the project and reminded Claude to copy it in, but it sent every extension to the
same place: "docs/ for documents, docs/plans/ for plans." Nothing distinguished a hand-written
markdown doc from an HTML report or other tool output, so both landed in `docs/`. This repo had
two loose examples proving the gap: `docs/architecture-review-2026-09-07.html` and
`docs/2026-09-09-branch-aware-guard-rollout.html`, sitting directly in `docs/` with no other
document like them. Full design and exact wording constraints are in the plan this decision
executed: [`docs/plans/2026-09-15-generated-artifacts-directory.md`](../plans/2026-09-15-generated-artifacts-directory.md).

**Decision.** Add `docs/generated/` — a third non-tier folder for tool-produced deliverables:
HTML reports, exported diagrams/images, anything from the Artifact tool or a generated-report
script. Made the `artifact` hook's routing extension-aware: hand-authored `md`/`txt` still go to
`docs/` (or `docs/plans/` for a plan), while tool-produced `html`/`csv`/`json`/`svg`/`pdf` now go
to `docs/generated/` instead. Updated `rules/house-rules.md`, the `project-docs` skill, and
`CLAUDE.md`'s hook table to match, and moved this repo's two loose HTML files into the new
folder with a `README.md` explaining it.

**Why.** `docs/plans/` and `docs/archive/` are both hand-written; a generated HTML report is
neither forward-looking intent nor a formerly-true document — it's tool output that gets
regenerated, not edited, when it needs to change. Mixing it into `docs/` made `docs/` unreliable
as "documentation" versus "whatever a tool happened to produce." Giving generated artifacts their
own folder keeps `docs/` readable as hand-authored documentation while still backing up generated
output as a tracked, committable file instead of leaving it in a scratchpad or temp directory.

**Status.** Standing.

---

## 2026-09-15 — Add a sixth documentation tier, `docs/Decisions.md`

**Context.** `house-rules:project-docs` defined five tiers (`README.md`, `Roadmap.md`,
`ProjectState.md`, `systems/*.md`, `Today.md`) plus two non-tier folders (`plans/`, `archive/`).
None of the five was *why*: tier 3 says where things stand, tier 4 says how a system works
*today*, but nothing durable recorded why a choice was made, what was tried and rejected, or what
an earlier decision used to say before it was reversed. That gap was already visible as ad hoc
workarounds in this repo — [`docs/rules-backlog.md`](../rules-backlog.md) and
[`docs/architecture-backlog.md`](../architecture-backlog.md) are hand-rolled decision logs (Status /
Defect / Evidence / "what the rule should say" per entry) that exist only because nothing in the
shipped tier system covered this. The `harvest` hook and `archivist` subagent also misfiled this
material — design rationale or a bug post-mortem got routed into a tier-4 system doc's *How it
works*/*Traps*, which is supposed to describe current truth, not carry historical narrative. Full
design and the exact wording constraints are in the plan this decision executed:
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](../archive/2026-09-15-sixth-documentation-tier.md).

**Decision.** Add Tier 6 — `docs/Decisions.md` — to the house-rules tiered-docs system: one
running, dated, append-mostly log (Context/Decision/Why/Status per entry), as designed in the
plan above. Updated `rules/house-rules.md`, the `project-docs` skill, the `archivist` subagent's
routing, and `hook.py`'s `HARVEST_NOTE` so rationale, rejected approaches, and post-mortems route
here instead of into tier-4 system docs; ongoing mechanisms, invariants, and operational traps
still go to tier-4, unchanged. Bumped the plugin version 2.20.0 → 2.21.0.

**Why.** `docs/plans/` is forward-looking intent that goes inert once executed and moves to
`docs/archive/`; `docs/archive/` holds documents that are no longer true. Neither is the right
home for a decision's reasoning, which stays true history even after the decision it describes is
superseded — it isn't inert, and it isn't forward-looking. A single append-mostly file (matching
the shape of tiers 2/3/5, not tier 4's per-system folder, since entries are short and
chronological rather than one-per-topic) gives `harvest`/`archivist` a real destination instead of
stuffing rationale into a system doc, and lets tiers 1–5 stop carrying their own change history
inline — they rewrite cleanly to state current truth and leave a one-line pointer into this log.
The alternative of folding decisions into tier-4 `Traps`/`How it works` was rejected because it
conflates "what is true now" with "what we chose and why," which is exactly the misfiling this
tier fixes.

**Status.** Standing.

## 2026-09-23 — Subagents get the rules, and their work becomes checkable
<!-- ref:c67d -->

**Context.** SessionStart's `additionalContext` never reaches a spawned subagent (probed with
`claude -p`, docs/plans/2026-09-22-rules-that-actually-load.md); a subagent that never saw the
house rules had no docs-tier discipline, no commit-branch discipline, nothing. Probing further
(same method): `SubagentStart`'s `additionalContext` DOES reach the subagent, but neither
`SubagentStop`'s `additionalContext` nor its `systemMessage` reaches the PARENT session's model
context in the same turn — only the interactive UI shows a `SubagentStop` `systemMessage`, the
same channel `announce`/`verdict` already relied on.

**Decision.** A third `SubagentStart` handler, `subagentrules`, its own hooks.json entry
(separate from `announce`): generates a *subagent core* from the sections of
`rules/house-rules.md` marked `<!-- subagent -->` (docs tiers, nothing fails silently, evidence
before claims, artifacts in the project, commit on own branches, destructive actions, edit in
place), plus a fixed mandate that the final report list every command run and its result
verbatim. Own budget, `SUBAGENT_CORE_CHAR_LIMIT = 4,500`. At `SubagentStart` it also tells the
user the transcript's expected path, before the transcript exists. At `SubagentStop`, `verdict`
now also states the path it actually found and an audit summary built from that transcript
(commands with exit status, files written/edited, tool-use counts, capped), carried on the one
proven channel, `systemMessage`, with an instruction to reconcile the subagent's own report
against it. `HOUSE_RULES_SUBAGENT_LEDGER=on` additionally renders the transcript into
`docs/sessions/` via the renderer moved to `scripts/session_ledger_render.py`, importable from
inside the plugin cache where `tools/` does not exist; off by default.

**Why.** A subagent that never saw the rules and whose finished work nobody could check against
its own transcript was invisible on both ends. `SubagentStart` is the one lifecycle event proven
to reach the subagent's own context, so that is where the rules have to be re-injected, generated
from one file so the subagent core cannot drift from the rules a human session sees. `verdict`
already existed to check which model actually ran; extending it to also state what actually
happened turns "trust the subagent's report" into "check the subagent's report."

**Status.** Standing.

## 2026-09-23 — The audit summary also reaches the parent MODEL, not just the user
<!-- ref:8313 -->

**Context.** The earlier entry this session (doc-ref c67d) found that neither `SubagentStop`'s
`additionalContext` nor its `systemMessage` reaches the parent session's model context in the
same turn - only the interactive UI shows the `systemMessage`. That left `verdict`'s audit
summary and reconcile instruction visible to the person, but not to the model that is supposed
to act on "reconcile the subagent's report against this record." Further probing (same method,
`claude -p` with a planted marker) found two channels that DO reach the parent model: a
`PostToolUse` hook matched on `Agent|Task` sees a **foreground** subagent's return
(`tool_response.status: "completed"`) and its `additionalContext` reaches the parent in-turn. A
**backgrounded** call (`run_in_background: true`) returns immediately with
`tool_response.status: "async_launched"` - its `PostToolUse` fires before the work exists - and
its real completion later arrives as a fresh `UserPromptSubmit` turn whose `prompt` field is a
`<task-notification>` carrying `<task-id>` and `<status>`; `UserPromptSubmit`'s
`additionalContext` also reaches the model.

**Decision.** Two new handlers, both reusing the audit logic `verdict` already built
(`_audit_summary`/`_audit_report`, one source): `audit`, its own `PostToolUse` entry matched on
`Agent|Task`, fires only when `tool_response.status == "completed"` (a foreground return) and
emits the audit as `additionalContext`. `userpromptaudit`, its own `UserPromptSubmit` entry
(never inside `scope`), fires only when the prompt is a `<task-notification>` whose `<status>`
is `completed`, extracts the `<task-id>`, and emits the same audit shape. The two never double-
report: a foreground return's `PostToolUse` status is `"completed"` and it has no later hand-
back turn; a backgrounded call's `PostToolUse` status is `"async_launched"` and `audit` stays
silent for it, so only `userpromptaudit`'s later hand-back turn reports it. `verdict` keeps its
own audit summary on `systemMessage`, for the person, on the channel already proven to reach them.

**Why.** The reconcile instruction is an instruction to the model doing the reconciling, not to
the person watching. A channel that only reaches the person satisfies half the design. Reusing
`_audit_summary`/`_audit_report` rather than re-deriving the audit from each payload shape keeps
one source for what counts as evidence, across all three delivery points.

**Status.** Standing.

## 2026-09-23 — A commit-time docs-tier reminder, and the one subprocess guard is allowed
<!-- ref:8713 -->

**Context.** `guard` (PreToolUse) previously had no opinion on documentation at all - only
`docstiers` (SessionStart) did, and only once per session. A source file could be committed with
no doc updated and nothing would say so until the next session, if ever. `branch_ownership()`
reads `.git/HEAD` directly and is asserted subprocess-free by `verify.py` (`guard` fails closed,
so it must not depend on a process that can hang) - the `git index` formats (v2/v3/v4, prefix-
compressed paths in v4) could in principle be parsed with the standard library, but the index
lists every tracked file, not what's staged; answering "staged" needs a diff against `HEAD`'s
tree, which means reading git objects (zlib, and packfiles) - too heavy for a check that runs on
every commit. A probe (`claude -p`, planted marker) confirmed a `PreToolUse` `allow` decision's
`additionalContext` reaches the model in the same turn, the channel this reminder needed.

**Decision.** `guard` now recognizes a `git commit` command (reusing `GUARD_R3`'s own commit
pattern) and, only then, runs `git diff --cached --name-only` as a subprocess under a 2-second
timeout - the one deliberate, narrowly-scoped exception to "no subprocess in guard",
`branch_ownership()` itself stays exactly as before. If the staged paths include a source file
(the `harvest` extension list) and nothing under `docs/`: on a `claude/` branch, the commit still
allows, but gains an `additionalContext` reminder naming the tier to update; on any other branch,
the existing prompt's reason gains the same line. A command naming another repo
(`-C`/`--git-dir`/`--work-tree`), a missing `git`, a timeout, or any other failure never changes
guard's own decision - it only adds "could not tell" to whichever message was already going out.

**Why.** The reminder needed the channel actually proven to reach the model, not the one assumed
to (`systemMessage`, `docs/Decisions.md`'s two other 2026-09-23 entries record that assumption
failing for `SubagentStop`). Scoping the subprocess to exactly one command shape, under a hard
timeout, whose failure never changes the real decision, keeps `guard`'s fail-closed contract
intact everywhere else.

**Status.** Standing.

## 2026-09-23 — The docs-tier commit check reads what WILL be committed, not what already is
<!-- ref:c79f -->

**Context.** The commit-time docs reminder landed (doc-ref 8713) reading only
`git diff --cached --name-only` - what is staged at the moment `guard` fires, which runs
*before* the tool call it is judging. The coordinator reproduced that `git add f.py && git commit
-m f` on a `claude/` branch, with `f.py` a new source file, got no reminder: the index guard read
was the one from before the `add` in the same command ran. That is the commit form used most, so
the check as built almost never fired.

**Decision.** `_staged_docs_status` now computes the effective path set a commit will actually
include, from the command text itself, still under the same 2-second total time budget and the
same "never changes guard's own decision" contract: `-a`/`--all`/`-am`/`-ma` on the commit
statement unions in `git diff HEAD --name-only` (every tracked, modified/deleted path); an
earlier `git add <paths>` in the same command (split on `&&`, `||`, `;`, newlines, the same way a
compound command is read elsewhere) adds those literal paths, resolved against
`git status --porcelain -uall` by prefix match so a directory argument expands to the files under
it; `git add .`/`-A`/`--all` unions in every path from that same status listing, `-u`/`--update`
only the tracked ones. Each `git` call shares one deadline computed once, so several calls in
sequence cannot each get their own fresh 2 seconds.

**Why.** A check that reads the state from before the command it judges runs is answering the
wrong question - "what is staged right now" instead of "what is this commit about to include."
Parsing the command text for `add`/`-a` is more code than reading the index once, but the
alternative (skip `-a` and pre-`add`, cover only an already-staged `git commit` with nothing
else) covers a minority of how commits are actually written.

**Status.** Standing.

## 2026-09-23 — handover narrows to shell fences, and gains an independent evidence check
<!-- ref:6534 -->
<!-- ref:25b2 -->

**Context.** `handover` (`Stop`) fired the step-card checklist on ANY fenced block, including a
fence with no shell in it at all (a `json` snippet, a diff, an unlabelled example) - noise that
was never a command handover to begin with. Separately, nothing in the plugin checked whether a
reply *claiming* success ("fixed", "it works", "tests passed") was backed by anything - a
confident-sounding reply and a verified one read identically.

**Decision.** Fence gating narrows to a fence whose info-string is a recognized shell (`bash`,
`sh`, `zsh`, `shell`, `console`, `powershell`, `pwsh`, `ps1`, `cmd`, `bat`, `fish`) - the
already-card-shaped stand-down is unchanged. A second, independent check: a reply matching a
claim word (`works`, `working`, `fixed`, `passes`, `passing`, `passed`, `verified`, `tested`,
`confirmed`, `succeeded`, word-boundary so "untested"/"unverified" never match, plus an explicit
negation-window check for "not tested"/"haven't verified") fires when there was no `tool_use` in
the transcript since the last **genuine user message** and the reply quotes no evidence (a fenced
block of any kind, or a line shaped like real captured output - this repo's own `RESULT: PASS`
convention, an exit code, or a test runner's "N passed" summary - deliberately not the bare word
"passed" alone, which would treat the prose claim itself as its own evidence).

**"Genuine user message" definition.** A transcript record with `"type": "user"` whose
`message.content` is not a list made entirely of `tool_result` blocks (a tool-result-carrying
turn, not a person writing), whose text does not start with `Stop hook feedback` (case-
insensitive) and does not contain `<task-notification>` (a background subagent's hand-back,
`doc-ref 8713`/`c79f docs/Decisions.md`'s siblings), and whose `origin.kind`, when the field is
present at all, is `"human"` (absent `origin` reads as human too, matching
`scripts/session_ledger_render.py`'s own `build_turns` - the one other place in this plugin
already keys on the same field for the same reason).

Both checks share exactly one `additionalContext` emission when both fire (two `emit()` calls
would be two concatenated JSON objects on stdout, not valid hook output) - though in practice a
shell fence always satisfies the evidence check's own "quotes evidence" exemption (any fence
counts, including the handed-over command's own), so the two conditions cannot both be true live
on the same reply; the shared-emission code path exists for correctness, not because it fires
today. A transcript that
cannot be read, or that carries no genuine user message at all, never fires the evidence note -
it fails open with a `systemMessage` naming what it could not tell, the same "never assert what
was not confirmed" posture the commit-time docs check (`doc-ref 8713`) already uses.
`stop_hook_active`, `HOUSE_RULES_HANDOVER=off`, and never `decision: "block"` are all unchanged.

**Why.** A fence check that fires on every fence trains the eye to skip the reminder; narrowing
it to shell fences keeps it firing exactly where a command really was handed over. The evidence
check exists because "evidence before claims" (this session's own earlier addition, `doc-ref
c67d`) was, until now, a rule stated in the subagent core and nowhere enforced in the main
session's own replies.

**Status.** Superseded in part: "never `decision: "block"`" on `Stop` was replaced by the 2026-10-15 entry "The end-of-reply check blocks once, from a checkpoint table" (#256). The rest stands.

## 2026-09-23 — scope trades its step-card line for a docs-tier line and an evidence line

**Context.** `scope`'s periodic per-prompt reminder (both its short and long forms) restated the
step-card handover format on every command-shaped prompt. That enforcement now has a live check
at the point it actually matters - `handover` (`Stop`) fires its own card check on a shell-fenced
reply and, independently, an evidence check on an unbacked success claim - so restating it in
`scope` too was paying for the same rule twice, while two rules with no enforcement point at all
(the docs tiers, and evidence before claims) had no per-prompt reminder.

**Decision.** Replaced the step-card line in both `SCOPE_REMINDER` (long form) and
`SCOPE_REMINDER_SHORT` with a docs-tier line ("update the docs tier that changed... or say why
none did") and an evidence line ("no success claim without a run you can quote"), pinned to the
same wording the rules corpus already uses (`tier that changed`, `success claim`) so drift
between the reminder and the rules document is still caught. Both forms shrank rather than grew
(long: 909 → 795 chars; short: 260 → 222), well inside the +10%-of-baseline budget `verify.py`
now checks explicitly. The executor-delegation clause `scope` adds on a go-ahead-shaped prompt is
unchanged.

**Why.** A reminder that keeps restating a rule with its own live enforcement is paying twice for
one thing; the two rules that had no enforcement point at all are the ones worth the recurring
nudge.

**Status.** Standing.

## 2026-09-26 — Evidence before claims covers any claim of fact, and a doc is not a test

**Context.** Issue #72 asked that Claude never assert something is correct without verifying it,
and that statements in chat, memory or docs not count as verification — only an applied test
does. The rule as written already refused chat/docs/reasoning/memory, but it had two gaps against
that ask: it covered *success* claims only ("it works"), not plain statements of fact ("this API
accepts X"), and it accepted "a tool call" as evidence, so reading a README with the Read tool
technically satisfied it.

**Decision.** Rule text only. `rules/house-rules.md` now says any claim that something is true or
correct — a success claim included — needs an applied test behind it: run it, or read the thing
itself. `rules/detail/evidence-before-claims.md` defines what counts (running, calling, loading,
reading the source or config the claim names, observing output) and what does not (a doc,
README, comment, commit message, memory, an earlier chat message, reasoning — even when read with
a tool), and says an unverified fact is attributed to its source and marked unverified. The
`handover` evidence check was deliberately left unchanged: telling "read a doc" apart from
"tested the thing" in a transcript needs a heuristic, and widening its claim-word list to words
like "correct" would fire on ordinary replies. `success claim` stays in the rule text, so the
`scope` reminder's drift pin in `verify.py` still holds.

**Why.** The distinction the issue draws is between a statement about a thing and a test of it;
"a tool call" drew the line in the wrong place. Enforcement can follow if the text alone proves
insufficient.

**Status.** Standing.

## 2026-10-17 — The credit check covers every GitHub write route, and reads the body back

**Context.** Issue #315: pull requests and issues opened with `gh api` from a cloud session still
credited Claude. A run on 2026-10-17 of `_attribution_guard` from `main` refused only `gh pr create`
and let through five `gh api` routes, `curl`, and the platform's "Generated by Claude Code" footer.

**Decision.** aj approved "Design approved: attribution guard gaps" with readback A and where A: the
guard widens to `gh api` and `curl` writes and to bodies in files, gains two footer patterns, and a
`PostToolUse` hook reads the created body back automatically. It is built in today's `hook.py` on
`AjsAgent/issue-315-attribution-routes`; the restructure (#306) moves it into the Safe git
sub-plugin later. Design: `docs/4-systems/guards.md`, "Credit on GitHub".

**Why.** The platform appends its footer after the agent's text is sent, so a guard alone can't
keep it off; reporting it honestly is the part the agent controls.

**Status.** Standing.
