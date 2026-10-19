# Audit 6 of the house-rules plugin: what the recent issues change

aj asked on 2026-10-16 for the issues opened recently to be read against the audit, and for the
changes they force on its recommendations. This file covers ten open issues on
`Ajw2003/AjsClaudeCodeTools`, read in full on 2026-10-16, plus the state of the work already
started on them.

## The issues

| Issue | What it asks | State of the work |
|---|---|---|
| #303 "the design loop is broken and blocks sessions; switch off the conflicting checks now" | Severity highest. A patch release that switches off the checks behind eight incidents from an `Ajw2003/Unblocked` session, then a fix and a `verify.py` case for each, turned back on one at a time | Nothing built |
| #301 "a session finishes its own task; other work becomes an issue in its own repo" | No context switching. Work for another repo becomes an issue in that repo, from a five-field template (observation, severity, feature/fix/both, needs research, up next or backlog), then the session returns to its task. It supersedes the parts of the issue workflow it covers. | Nothing built |
| #304 "a two-helper tool that cleans a session transcript, then files issues from it" | One helper flags credentials and sensitive text in a transcript, with quotes, for aj to confirm and remove. A second files issues from the cleaned transcript using the #301 template. It also states the plugin's goal, quoted below | Nothing built |
| #302 "proposal pages need before-and-after visuals for any visible change" | A page proposing a visible change can't be built or published without before-and-after visuals | Nothing built |
| #297 "After every pull request, a check makes sure it says how to test it and what's next", with #298, #299, #300 | Pull request bodies, QA pages and replies reporting a pull request must say how to test it and what's next. Step 4 sets the agent name through `HOUSE_RULES_AGENT_NAME` in aj's setup scripts | Design approved; the branch `AjsAgent/after-pr-answers` stopped at Plan two hours ago, docs only |
| #287 "Agent name, credit and branch prefix are configurable, not hard-coded to AJ" | One name drives credit and branch prefix; it defaults to `git config user.name`, then the Claude account email, with an env override | Nothing built |
| #296 "Design-loop approvals are dropped silently when the session folder isn't a git repo" | In a session with two repos attached, the folder is `/home/user`, so approvals are dropped with no message | Nothing built |

Issues #285 and #288-#293 are built in 2.68.0 and wait on aj's QA (`needs review`). The restructure
must keep their behaviour.

## The plugin's goal, in aj's words (#304)

> The goal of this and the plugin as a whole is being able to safely work on multiple projects at a
> time in different sessions with separate contexts while still being able to note an observation in
> the moment if that observation concerns another project ... and to have the session transcript be
> safely used as a data point for another session to analyze in order to fix a given issue

This answers the audit's open question about the core identity. None of the three options on the
audit page matched it, so the identity choice changes.

## What each issue changes in the audit's recommendations

### 1. A patch comes first (#303)
The audit proposed grilling, then the restructure. #303 is severity highest and says nothing can
proceed, so a patch release (2.68.1) must ship before either. Its eight incidents line up with the
audit's findings:

| #303 incident | Audit finding it matches | Patch |
|---|---|---|
| 1. Two approvals in one message: only one is read | `_loop_apply` parses one phrase (`hook.py:5467-5568`) | Read every approval phrase in the message, in stage order |
| 2. The feature name gets stuck | The loop keeps the old feature across approvals | A design approval always sets the feature name |
| 3. Issues opened in another repo count as this feature's issues | Loop state is shared, issue state is per worktree; `_loop_record_issues` records any created issue (audit 4) | Record only issues created in the repo that owns the stage file |
| 4. Docs can't be written from the shell while code is locked | Also hit in this session (a screenshot script in the scratch folder was refused) | Switch the shell-write refusal off |
| 5. The re-creation check fires on a one-entry docs append | Also hit three times in this session | Switch the parity check off |
| 6. The page check pushes other repos' work into the session | Five end-of-reply checks judge only the newest message, and none knows which repo a topic belongs to | Page checkpoint reports instead of blocking |
| 7. The page builder demands a lock phrase on another repo's proposal | `make_page.py` refuses any other approval phrase | Accept any approval line; only the loop phrases move the stage |
| 8. The writing check misreads the word "I" | The bare-word jargon and reference checks can't see context (`clarity.py:195-197`, audit 5) | Switch the bare-reference check off |

The page-dodge fix approved earlier today belongs in this patch too, since it changes the same
page checkpoint.

### 2. The core identity is aj's stated goal (#304, #301)
The audit's suggestion was "Guardrails". aj's own goal is wider: safe work on several projects at
once, each session in its own context, with observations about other projects captured as issues,
and transcripts usable as evidence without leaking secrets. The core therefore needs a part the
audit didn't propose: **project boundaries**. It works out which repo a message or tool call
belongs to (#296, #303 incident 3), keeps each repo's state apart, and turns work for another repo
into an issue there (#301).

### 3. A new sub-plugin: Session triage (#304)
It holds the two helpers from #304 and builds on what exists: `tools/session_ledger.py` and
`scripts/session_ledger_render.py` already turn transcripts into records under `docs/sessions/`.
Those tools have no redaction step today (checked by searching both for redact, secret, token and
credential), and they write into this public repo. A scan of the two committed ledger files found
no credential-shaped strings, but nothing prevents the next one. The cleaning helper must run
before any ledger is committed or published.

### 4. The issue workflow is replaced, not moved (#301)
The audit put the issue workflow inside the Design loop sub-plugin. #301 supersedes the parts it
covers, so the plan-step counting, the per-feature issue record and the label checks that #303
incident 3 trips on are replaced by the five-field template rule. The parent-and-child issue
structure for a build plan is a question for the grilling session.

### 5. Identity settings: one mechanism, not three (#287, #297)
#287 proposes a git-name default with `HOUSE_RULES_AGENT_NAME` as an override. #297 step 4 sets
that variable in aj's setup scripts. The audit proposed Claude Code's `userConfig`. These fit
together: `userConfig` as the setting each user fills in, defaulting to the git name as #287 says,
with the environment variable kept only as an override for scripts.

### 6. After-pull-request checks wait for the restructure (#297-#300)
They add a guard and an end-of-reply checkpoint to the same 8,365-line file the audit proposes to
split. Building them now adds code that moves again weeks later. They fit the Design loop
sub-plugin, so they are best built there, and their branch stays parked at Plan until then.

### 7. Before-and-after visuals become a page rule (#302)
`make_page.py` already supports a before-and-after compare and a `"pictures": "required"` style
setting, but only when a project's style file asks for it. #302 makes it required for any proposal
of a visible change. The audit page itself now shows today's structure and the proposed one as a
before-and-after compare.
