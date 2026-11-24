# Roadblocks

**Owns:** the rule that the agent checks a roadblock claim before making it, installs missing tools
itself, and tries other routes before stopping, plus the end-of-reply check that enforces it.
Status: built in plugin 2.89.0. Parent issue #569; steps #570 (rule text), #571 (the check), #572
(tests, docs, version). aj approved the design on 2026-11-22 as "Design approved: clear roadblocks
1C 2A" on `docs/plans/2026-11-22-clear-roadblocks.html`.

**Merged with main (2.89.0):** main shipped a different 2.88.0 (wait clocks and visual checks, pull request #573), so this feature is 2.89.0. To fit the injected-rules limit after that merge, the rule is two sentences inside the "The user's hands are for decisions, not labour" section rather than its own section; the full list of what stays aj's (purchases, licences, logins, destructive actions) is in `rules/detail/roadblocks.md`.

## Why it exists

A session on aj's PC said it could not go further because Unity was missing and it was on the wrong
machine. Both claims were false, and the session was in bypass permission mode. The existing rules
already say a "can't be done" claim needs a test (`rules/detail/evidence-before-claims.md`) and that
aj's hands are not for labour (`rules/detail/users-hands.md`), but text alone was read and ignored.

## What aj chose

| Question | Choice | Meaning |
|---|---|---|
| How firmly is it enforced? | 1C | A rule plus an end-of-reply check that blocks a roadblock claim twice, then lets the reply through with a visible warning line. |
| What stays aj's? | 2A | Licences, logins, purchases and destructive actions only. |

Dropped from the proposal: a line at session start telling every bypass-mode session that installs
are pre-approved.

## How it will work

1. **Rule.** Probe before claiming (`which`, `ls`, `uname`, `hostname`, `list_computer_folders`);
   install what is missing (without asking in bypass mode, through the normal prompt otherwise);
   try the next route and list every attempt before stopping.
2. **Check.** `roadblock_check` (`scripts/house_rules/core.py:3451`), called from `event_handover` in
   `scripts/hook.py:135` right after `handover_evidence_check`; a block is emitted at once and the
   later checks do not run that reply.
   - **Phrases flagged** (`core.py:3390`, case-insensitive, not inside quotes): "I can't", "I cannot",
     "is/isn't/are/aren't/not installed", "not on your machine", "no access to", "you need/have to install".
   - **Probe or install** (`core.py:3395-3399`, `3411-3423`): a `Bash` command this turn containing
     `which`, `ls`, `uname`, `hostname`, `where`, `command -v`, or `apt`, `apt-get`, `pip`, `pip3`,
     `npm`, `brew`, `winget`, `choco`; or a tool named `list_computer_folders` or
     `request_computer_folder`. Any one clears the reply.
   - **Block count** (`core.py:3470-3488`): no probe means block, up to `ROADBLOCK_BLOCKS = 2`
     (`core.py:3400`) per user message; the third time the reply goes out with a visible
     "a roadblock claim (...) went out unchecked" line. The block reason names the rule file and the
     probe to run.
   - **State file** (`core.py:3435-3440`): `house-rules-roadblocks-<sha1 of transcript path, 16
     chars>.json` in the temp directory, holding `{"key": "<transcript path>|<user-message count>",
     "count": n}` (`core.py:3426-3432`, `3472`). A new user message changes the key, so the count restarts.
   - **Fail-open** (`core.py:3459-3464`, `3482-3484`): no `transcript_path`, an unreadable transcript, or a
     state file that cannot be read or written gives a `house-rules: roadblock check could not ...`
     message and never blocks. On the `stop_hook_active` retry it only warns and does not count
     (`core.py:3468`, #256).
   - **Off-switches:** `HOUSE_RULES_ROADBLOCKS=off` (`core.py:3403`) turns the check off;
     `HOUSE_RULES_ROADBLOCKS_STATE=<path>` (`core.py:3436`) moves the state file (the checks use it).
   - **Tests:** cases 101 to 109 in `scripts/checks/core.py:1188-1243`: blocks 1 and 2, warning on
     the third, no block after which/ls/pip, new message resets, unusable state file, retry, off-switch.
   - **Case 91 changed:** its example reason (`checks/core.py:1113`) was a missing editor; it is now a
     four-hour suite, because a missing-tool reason is exactly what this check blocks.

## What was built (plugin 2.90.0, #587 steps #588 to #591)

- **Record check (#589).** A roadblock claim passes only when the turn's tool results show three failed attempts naming the claimed thing, in three method classes; a reply marking NEEDS YOU for a licence, login, purchase or destructive step is exempt.
- **Own Stop hook (#588).** The `roadblocks` handler runs from its own Stop hook, not inside `handover`, because `unattended on` switches `handover` off and the check must still run unattended. Blocks twice per user message, then warns. Curly apostrophes and the wider phrase list are matched. Stall phrases (next step, not done, I've stopped) are scanned only in unattended or bypass sessions; a Stop payload with no `permission_mode` is treated as attended and says so.
- **Judge (#591).** A `type: "prompt"` Stop hook asks a model whether the reply's roadblock is genuine.
- **Goal check (#591).** On a stall phrase in unattended or bypass mode a nested `claude -p` call reads the goal and blocks (up to 6 times) when work can continue.
- **Never wait (#590).** In unattended or `permission_mode` `bypassPermissions` sessions the `noask` hook (`event_noask`, `scripts/house_rules/core.py`) denies `AskUserQuestion` and `ExitPlanMode` with the reason to choose a reasonable reversible option, record it in the report and carry on; a licence, login, purchase or destructive step blocks only its own part (NEEDS YOU). A payload with no `permission_mode` is treated as attended and announced on stderr. One sentence in `rules/show-dont-tell.md` says the same. The approval gate before source edits is unchanged.
- **Off-switches.** `HOUSE_RULES_ROADBLOCKS=off` (record check and stall scan), `HOUSE_RULES_GOALCHECK=off` (goal check).
- **Unverified.** The `bypassPermissions` value was read from Claude Code's mode list, not seen in a live bypass session; the plan's headless QA steps are on the QA page.

## Detection fix (designed 2026-11-23)

Parent issue #587; steps #588 (detection), #589 (evidence rule), #590 (never wait, docs, version).
aj approved "Design approved: roadblock detection fix 1* 2* 3*" on
`docs/plans/2026-11-23-roadblock-detection-fix.html`, with three answers of aj's own.

**Why.** On aj's PC the merged check let two replies through in the Castle session, and both
sessions ran 2.89.0. Two causes were reproduced with the merged code: the pattern in
`_ROADBLOCK_RE` (`scripts/house_rules/core.py`) needs a straight apostrophe, and
`_PROBE_CMD_RE` counts any command containing `ls`, `where`, `npm`, `pip` or `apt`, so a turn that
ran `git ls-files` counts as a probe. A third fault was found while planning: `roadblock_check`
returns at the `stop_hook_active` retry, so in a real session the second of the "two" blocks never
happens (the field exists in the Stop payload; its value on a continuation was not observed).

**What aj chose, and how it is read.**

| Answer | aj's words, shortened | Reading |
|---|---|---|
| 1 | Only count a probe if it checks the claim and shows the claim cannot run. Added 2026-11-23: try up to two different methods after the first try (three attempts in total) before saying something can't be done or can't be verified | A claim passes only when the turn has three failed attempts naming the claimed thing: the first try, then two more by different methods from it and from each other (fewer attempts get a block saying how many more are needed; if fewer than three methods exist the reply says why). aj's message of 2026-11-23 tightens this: a first try never counts as "I cannot" or "unable to"; only after the first try and two further attempts by different methods all failed (three attempts in total) may the reply say something could not be verified, tested or done, and the reply must list every method tried (each method's command or tool name appears in the reply). `ls` or `git ls-files` alone no longer counts. |
| 2 | can't, won't or unable to verify, don't have access, not available here, isn't available, not done, I've stopped, the next step, next step. Added 2026-11-23: "I've stopped here", and the general inability wording (unable to, genuinely unable, could not, couldn't, cannot be verified or tested) | The first six join the claim pattern everywhere. The last five (not done, I've stopped, I've stopped here, the next step, next step) are stall phrases and are flagged only in unattended or bypass sessions, because every normal reply ends with a next step. |
| 3 | In unattended mode choose a reasonable reversible design; never leave the session waiting in unattended or bypass mode | Mid-build design decisions are chosen, recorded and carried on in both modes. The approval gate before source edits is unchanged. |

**Verified while planning (2026-11-23).**
- The Stop payload carries `permission_mode`; a live headless run showed `default`. Claude Code's
  own program file lists the modes default, acceptEdits, bypassPermissions, plan, dontAsk and auto,
  so bypass is `bypassPermissions`. That value was read from the list, not observed in a live
  bypass session, because the safety check refused a bypass test run.
- A test Stop hook that blocked twice received `stop_hook_active` False on the first call and True
  on the second and third, and Claude Code allowed the second block. So `roadblock_check`
  returning at the retry is the only thing preventing a second block. Claude Code overrides a hook
  after 8 consecutive blocks (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`, default 8), so capping at 2 on our
  own counter is safe.

**Limits to document in step 2.** The thing a claim names is picked out of free text, so a claim
with no recognisable name falls back to "any three failed tool results this turn that differ in method count".

## Audit of the planned check (2026-11-23, proposal on `docs/plans/2026-11-23-roadblock-check-audit.html`)

aj asked for an audit of the weaknesses and traps in the plan, with robust fixes. Measured on this
machine against the merged check and real transcripts (one session, so small samples):

| # | Weak spot | Evidence | Planned fix |
|---|---|---|---|
| 1 | Curly apostrophe not matched; blockquote lines flagged; paraphrases unlisted | Fixtures; a phrase list cannot cover paraphrases (reasoned) | Normalise apostrophes, ignore blockquotes and code, optional model judge |
| 2 | `git ls-files` counts as a probe | Fixture (earlier) | Failed attempts about the claimed target, by method class |
| 3 | Only the `Bash` tool is read | Fixtures: a PowerShell call and a failed MCP call were both blocked | Read every tool; Windows equivalents per method class |
| 4 | "Failed" is undefined | In 224 results `is_error` is set on 9; it also fires for hook refusals and harmless exits; 4 failure-like results have it unset | is_error minus hook refusals and harmless exits, plus strong exit-0 failure text |
| 5 | Fallbacks: unnamed target, fewer than three methods | Reasoned | Attempts must share a target word that appears in the reply or the request; judge checks the reason |
| 6 | False alarms | `next step` in 2 of 28 final replies; one hit was meta talk | Stall phrases need hand-back wording; NEEDS YOU exemption |
| 7 | Window and counter reset | 2 of 17 "genuine" messages were system-reminder carriers | Exclude those carriers |
| 8 | Environment | Handler 0.8 s on 5.3 MB, check +0.08 s; 100 MB about 15 s (estimate); hook time limits unknown | Announce a missing mode, read the tail only |

**Model judge measured once.** A `type: "prompt"` Stop hook (Claude Code supports prompt, agent,
command and http hooks) flagged "I cannot continue because Unity is not installed", gave an
actionable reason, and passed once the agent listed its methods. Its call used 232 output tokens
and cost $0.0041 for two evaluations against $0.2437 for the main model in the same run (one run:
an estimate, not a rate). An `agent` hook that reads the transcript was not tested.

**Verified in Claude Code's own code.** It overrides a hook after 8 consecutive blocks
(`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`, default 8), and the Stop hook feedback message is excluded from
the "this turn" window (`_is_genuine_user_message`).


## Plan after the audit (approved 2026-11-23, not built)

aj approved "Design approved: roadblock check audit 1B 2A 3A 4* 5A" on
`docs/plans/2026-11-23-roadblock-check-audit.html`. Parent issue #587; steps #588 (detection),
#589 (record check), #591 (model judge and goal check), #590 (never wait, docs, version, QA).

| Answer | Choice | Reading |
|---|---|---|
| 1 | 1B | Add a model judge: a `type: "prompt"` Stop hook on every turn end. |
| 2 | 2A | Three attempts must fall in three method classes (existence check, disk search, package database, run it, ask the environment, other tool). |
| 3 | 3A | A reply marking NEEDS YOU for a licence, login, purchase or destructive step is exempt from the three-attempt rule; the rest of the work carries on. |
| 4 | aj's own | Stall phrases are checked only at the end of the turn. A separate goal check then reads the session's goal and decides whether the session genuinely cannot move forward unattended or can carry on until the goals are reached. |
| 5 | 5A | Unattended runs and `bypassPermissions` only. |

**The goal check (answer 4), as read.** The Stop command hook scans for a stall phrase. Only on a
hit does it run a nested `claude -p` call (small fast model, Read tool only, plugin hooks off with
`--setting-sources project` so it cannot recurse). The call gets the first and the most recent
genuine user messages and the transcript path. Its verdict `{"ok": false, "reason": ...}` becomes
the block reason; `{"ok": true}` lets the reply go. It blocks up to 6 times in a row per user
message, below Claude Code's limit of 8 (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`), because answer 3 says
never wait; the roadblock claim check keeps its limit of 2. If `claude` is missing, or the call
fails or times out, the hook says so and does not block.

**Measured on 2026-11-23 (fabricated sessions, small sample).** The judge prompt reads "ANY remaining
part of the work that can continue without the user; a licence, login, purchase or destructive
step blocks only its own part". Goal unreached ("Next step: build castles 2 to 12"): blocked with
"continue building castles 2 to 12". Goal reached with a trailing "Next step: review": passed.
Blocked on an npm login with the docs step still doable: blocked with "continue with the docs
changes and leave only the publish". An earlier wording passed the login case, so the sharper
wording is required. Each call cost about $0.002 and took 4 to 5 seconds.

**Traps of the model layers.** A judge given no input answers ok and says so; a prompt hook
cannot announce a failure, so layer 3 fails open silently and the deterministic layers 1 and 2 are
the backstop. The nested call needs `claude` on the hook's PATH; if the goal is only in a resumed
or compacted session's summary, the first user message is not the real goal (limit). The goal
check passes a stall phrase through when the goal is reached, so ordinary "next step" lines in
finished work stop costing a block. The agent hook type (reads files itself) ran in a test but
its verdict could not be observed in that run, so it is not used.
