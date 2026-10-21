# The verify suites

## What it owns

Proving, mechanically, that each plugin's hook payloads produce the JSON decisions the docs
claim — not that the code reads well, that it *decides correctly* when fed a real payload. Three
suites, one per plugin, same shape:

| Suite | Lines | Checks (last run 2026-09-24) |
|---|---|---|
| [`house-rules/scripts/verify.py`](../../claude-house-rules/plugins/house-rules/scripts/verify.py) (the runner, 338 lines) and [`checks/`](../../claude-house-rules/plugins/house-rules/scripts/checks) (7 part files plus `common.py`, 10,738 lines) | 11,076 | 913 PASS (2026-10-21, #370) |
| [`agent-router/scripts/verify.py`](../../claude-agent-router/plugins/agent-router/scripts/verify.py) | 245 | 41 PASS |
| [`prompt-workshop/scripts/verify.py`](../../claude-prompt-workshop/plugins/prompt-workshop/scripts/verify.py) | 228 | 22 PASS |

If this is wrong — a check that passes when the hook it's judging is actually broken — every
other document in this repo that cites "verify.py passes" as evidence is standing on nothing.
This is the mechanism that turns "I read the code and it looks right" into "I ran the check and
it agreed," which is the whole reason `CLAUDE.md` calls it, not the README, the source of truth
for whether a change took effect.

It does not own getting the plugins installed (`plugin-distribution.md`, whose own
`tools/verify_tools.py` tests *that* system's decision logic instead) or being correct rules text
in the first place (`rules/house-rules.md`).

## How it works

Each suite feeds hand-built JSON payloads to the plugin's `hook.py` — by calling its handler
functions directly for the common case, and by shelling out to `run.sh` under a deliberately
broken `PATH` for the "no interpreter available" fallback cases — and asserts on the returned
decision (a `PASS`/`FAIL` line per check, numbered, printed with what was tested, expected, and
got). The check count is computed at runtime and never hardcoded in any doc, `house-rules`'
suite included — a written-down number drifts the moment a case is added, and `verify.py` fails
any doc caught stating one.

Beyond individual hook cases, `house-rules`' suite carries **drift checks**: `rules/house-rules.md`
is canonical, and several other files restate a phrase or requirement from it (`hook.py`'s
`SCOPE_REMINDER`, `RUNNABLE_NOTE`, `DELEGATE_NOTE`, `HANDOVER_NOTE`; `output-styles/handover-cards.md`;
`agents/executor.md`; `templates/step-card.html`; `docs/claude-ai-instructions.md`). A drift check
asserts a named phrase still appears in the restatement, so a reword of the canonical text that
silently drops what a restatement depends on gets caught rather than discovered live.

`house-rules`' suite also runs from two places — this repo, and the installed copy in
`~/.claude/plugins/cache/` — and several checks read files that exist only in the repo
(`CLAUDE.md`, `claude-house-rules/README.md`, `docs/claude-ai-instructions.md`,
`docs/desktop-verification.md`, `tools/install.py`). Those checks report a third state, `SKIP`,
gated on `IN_REPO` (the presence of `.claude-plugin/marketplace.json` beside the plugin
directory) rather than `FAIL`, so the installed copy's result isn't permanently red for a reason
that has nothing to do with the hooks. Inside a repo checkout the skip is unreachable — a missing
file there is still a real failure.

## Invariants

- **Exit code 0 means every check in that suite passed.** Nothing else about a suite's output is
  load-bearing except the individual PASS/FAIL lines and the final count.
- **No third-party test framework, stdlib only** — same constraint as the code under test, so the
  checker is never a bigger dependency than the thing it checks.
- **The check count is never written down as a number anyone maintains** — it's computed and
  printed, and a doc that hardcodes one is itself a drift check failure.
- **A repo-only check `SKIP`s outside a checkout and `FAIL`s inside one** — the distinction is
  `IN_REPO`, and a check that can't tell which state it's in must fail rather than guess.
- **The guarded-verb list is never hand-copied into a doc.** The README's "What trips the
  guard" table is checked by tokenizing the backtick code spans in the table itself against
  `GUARD_R3`/`GUARD_R4`'s actual verb lists (`GUARDED_GIT_VERBS`, `NAVIGATIONAL_GIT_VERBS` in
  `verify.py`), rather than by hand-copying the verb list into a second check. The README's
  table listed the old, broader verb set for months after `guard`'s git patterns were narrowed
  to only the verbs that write history, the index, or the remote (navigational verbs — `add`, a
  bare `checkout`/`switch`, `branch`, `tag`, `remote`, `submodule`, a bare `stash` — were
  deliberately left unmatched, since matching them produced only noise). A reader who tested
  with `git add -A`, expecting a prompt, saw none and could reasonably conclude the hook was
  broken rather than working as designed. Tokenizing the table means a future re-narrowing (or
  re-widening) of the guarded verbs breaks this check instead of silently leaving the table
  wrong again (`verify.py:2372-2393`).

## Traps

- **A stale temp file from an earlier run turned asks into refusals (#229).** The hooks keep
  state in the temp folder (`house-rules-last-seen-<session>`, the waiting-on-you list) and the
  suite reuses session names, so a file over five minutes old made `guard` believe aj was away:
  41 checks failed until a rerun refreshed it. Since 2026-10-15 every run sets its own `TMPDIR`.
  Reproduced before the fix by planting 20-minute-old files: the old suite failed 41, the new
  one passed 684 of 684, twice.

- **Most drift checks run in one direction only.** Most restatement checks in `house-rules`' suite
  assert that a phrase still appears in `house-rules.md`; they do not assert that the phrase still
  appears in the *restatement* the check is named for. So a phrase can be quietly deleted from
  `RUNNABLE_NOTE` or `HANDOVER_NOTE` and the suite still reports every check passing. This already
  happened once for real: the `delegate` restatement lost its proactive-use authorization sentence
  during the shell-to-Python port, survived in `house-rules.md` and both agent descriptions, and
  every check still passed — because the check never looked at what `event_delegate` actually
  emits. `delegate` and `versioncheck` are now bidirectional (checked over both `house-rules.md`
  and the emitted text); the remaining restatements are still one-directional as of this writing.
  Treat "the drift check passes" as weaker evidence for those than it looks.
- **Naming a command is not the same as verifying it will be handled correctly.** `versioncheck`'s
  out-of-date banner is checked twice, separately, on purpose: one case proves the banner still
  names the right fix command (the mismatch case), a second proves the banner still tells Claude
  to route that command through the card format, marked `UNTESTED:`, and then stop and wait rather
  than continuing into unrelated work. A real session hit exactly the gap the second check exists
  to close: the banner printed the raw fix command with no `UNTESTED:`/card instruction and no
  "then stop," so the reply relayed it as a ready-to-run block and moved straight into unrelated
  repo exploration in the same turn (2026-09-17). The two checks are kept separate rather than
  merged, because a banner that names the right command but drops the handling instructions (or
  the reverse) should fail exactly one of them, not neither.
- **There is still no way to run one check, only one part.** Since #370 `verify.py --parts safe_git`
  or `--changed` runs one part (11 to 281 checks), not one check; see "The split layout (#370)"
  below. Editing a single `guard` pattern still re-runs the 186 safe-git checks to find the ~28
  that were relevant.
- **A suite testing branch-dependent behavior must not inherit the developer's actual branch.**
  `house-rules`' guard/branch-ownership cases use hand-written fixture `.git/HEAD` files under
  throwaway directories rather than reading whatever branch the suite happens to run from — the
  same fact that makes a plain-file read fast enough to do on every `guard` call also makes it
  reproducible as a fixture. A case that reads the real repo's branch would pass or fail
  depending on who ran it and from where, which proves nothing.
- **A check can be wrong about the code it's checking.** One `hook.py`-source check searched for
  the literal string `rev-parse` to prove `branch_ownership()` never shells out to git — and
  failed, because `rev-parse` appears in that function's own docstring, precisely to say it is
  *not* used. The check was flagging the sentence explaining the invariant as a violation of it.
  It now matches call syntax only. Lesson: grepping prose for the absence of an idea is not the
  same as checking for the idea's absence in code.

## Planned: the verify.py rework (restructure, after step 2)

Design approved 2026-10-21 ("Design approved: verify rework 1A 2A"); proposal
`docs/plans/2026-10-21-verify-rework.html`.

**Why.** One run on 2026-10-21 took 197 seconds for 913 checks. 154.2 of them went on starting
`hook.py` as a fresh process 898 times (0.172 seconds each), and 0.084 seconds of each start is Python
recompiling the 8,588-line script (issue #204). Page builds took 28.6 seconds. aj: verify.py takes
several minutes in a cloud session, and the run-twice rule doubles it.

**What changes.**
- Step 2 of the restructure (#340) turns `hook.py` into a dispatcher that imports the part modules, so
  Python caches their compiled form; that is expected to remove 75 of the 197 seconds, measured after
  step 2 lands.
- Question 1, answer A: `verify.py` splits into one test file per part (core, safe git, session triage,
  design loop, writing, delegation, docs) plus a runner script. In a session the runner runs the parts at
  the same time on the machine's cores and can run only the parts a change touched. CI runs every part on
  every pull request. No existing check is deleted.
- Question 2, answer A: in a session, the parts a change touched run twice and everything else once; CI
  runs the full suite. This replaces "twice, everywhere" from grilling round 1, question 3, and the "Twice"
  line in `rules/detail/green-suite.md` and `rules/house-rules.md` changes with it.

**Measured after step 2 (2026-10-21, house-rules 2.71.0, #360).** Same machine and method as the
baseline, `python3 claude-house-rules/plugins/house-rules/scripts/verify.py` from the repo root:

| Run | Result | Exit | Seconds |
|---|---|---|---|
| 1 | `RESULT: PASS - all 913 checks passed.` | 0 | 134.3 |
| 2 | `RESULT: PASS - all 913 checks passed.` | 0 | 132.6 |

The baseline was 197 seconds per run before step 2, so a run is about 63 seconds (32 percent) shorter;
the forecast above was 75 seconds. `python3 tools/verify_tools.py` passed twice (`all 47 checks passed`,
exit 0) in 0.66 and 0.68 seconds. Starting `hook.py` through `run.sh` (`echo '{}' | bash .../run.sh
scope`, 20 calls in 1.59 seconds) averages 0.0795 seconds per call, against 0.172 seconds before. The
cached `.pyc` files of the part modules are where the saving comes from. The remaining time is mostly the
898 process starts and the page builds, which is what the per-part test files and the parallel runner
(question 1, answer A) address.

## Which part every check belongs to (#369)

Step 1 of the verify.py rework (#368). It moves nothing: it lists what the next step (#370) has to split.
Measured 2026-10-21 on house-rules 2.71.0, branch `AjsAgent/issue-369-inventory` off `AjsAgent/issue-281-fix`
at 86034c5, on a 4-core machine, from the repo root.

**What counts as a check.** One `report(...)` call (`verify.py` lines 90-97) is one check. It adds 1 to the
global `STEP` and prints `NN. PASS|FAIL|SKIP  title`; the final line reads `all STEP checks passed`. A real
run printed `RESULT: PASS - all 913 checks passed.` (exit 0, 131.9 seconds, nothing skipped). There is no
section object and no registry: the numbering is simply print order, and a check's number moves whenever one
is added or removed before it.

**How checks are produced** (five shapes, all top-level code in one 10,407-line file):
- One statement, one check: a `report(...)` straight after the setup it judges.
- A loop over a table, one check per row: for example `GUARD_CASES` (17-66), `BRANCH_CASES` (67-86), the
  `_size_cases` loop (1-5), the crash loop (228-234).
- A case helper that wraps `report`: `_sv_case` (88-92), `check_scope` (126-129), `art_case` (132-143),
  `run_case` (154-160), `compile_case` (161-162), `harv_case` (172-191), `std_case` (436-448), `hand_case`
  (236-264), `pv_case` (262-280), `commit_case` (281-401 and 485-520), `docref_case` (565-611),
  `pd_case` (615-640), `_cap_case` (524-535).
- Collect first, report last: cases are appended to a list (`_loop_cases`, `_cl_cases`, `_cw_cases`,
  `_ck_cases`, `_mp_cases`, ...) and a final loop prints them all, so the work for a whole block runs before
  its first number is printed (checks 643-913). Per-check timing inside these blocks is not possible.
- A check that bundles several assertions: one number, many commands (for example each of the attribution
  checks 362-375 runs several commands and reports once).

**How the part was chosen.** By the module that owns the code the check exercises: the hook event it runs
through `run.sh` (the handler-to-module table in docs/architecture.md), or the module whose names it loads.
Where a check runs a script, the script is named and then placed with its part: `clarity.py` with writing,
`docref.py`, `plain_docs_check.py` and `harvest_scan.py` with docs, `stallcheck.py` with delegation,
`labels.py` with the design loop, `make_page.py` on its own as `tools/make_page`. Judgment calls, so #370 does
not have to guess again:
- Code that lives in a part but is reached through another part's event goes with the part that owns the code.
  The issue guards (pull request rule 350-357, author guard 376-380, close guard 382-385) are in
  `design_loop.py`, registered on the guard event, so they are design loop, not safe git. The agent-branch and
  git-identity warnings (358-361, 381) are registered by `safe_git.py` on the profile event, so they are safe git.
  `_scope_delegate_link` (464-465) is in `delegation.py`, so the scope delegation clause is delegation.
- Static checks of the rules document, `hooks.json`, agents, templates and docs go with the part whose rule or
  handler the text is about; generic ones (CLAUDE.md size, output style, card template, architecture tables
  against `hooks.json`) go with core, because core injects the rules.
- The Stop-time checks in `hook.py`'s `event_handover` are core; their helpers are split: evidence, not-checked,
  parity are core, the plain-summary, long-reply, editor and visual checks are writing, the commit check
  (`handover_commit_check`) is safe git, the page and checkpoint table are design loop.
- Session triage has no checks: `house_rules/session_triage.py` is empty until step 9 (#347).

### Summary: checks and seconds per part

Seconds are wall-clock from a copy of `verify.py` kept outside the repo, run once on 2026-10-21: it wraps
`report` to log, for each check, its number, title, call-site line and the time since the previous check
(total 127.3 seconds of logged time; the same suite untraced took 131.9 s). The time before a number is
printed is charged to that number. In the collect-first blocks (643-913 and label setup 766-778) a whole
block's time lands on its first number, so the block's time is shared equally across its checks; that only
matters where a block mixes parts (779-808 writing, 809-861 design loop and others), so treat those parts
as accurate to a second or two. One run, no repeat, with other work on the machine: the figures show shape,
not precision.

| Part | Checks | Seconds | Share of the run | Also exercised by two-or-more-part checks |
|---|---|---|---|---|
| core | 181 | 16.2 | 13% | 6 |
| safe git | 184 | 31.7 | 25% | 13 |
| design loop | 253 | 28.5 | 22% | 6 |
| writing | 41 | 2.5 | 2% | 10 |
| delegation | 99 | 14.1 | 11% | 3 |
| docs | 125 | 6.8 | 5% | 2 |
| session triage | 0 | 0.0 | 0% | 0 |
| tools/make_page | 30 | 27.5 | 22% | 4 |
| **Total** | **913** | **127.3** | 100% | |

How to read the seconds. Safe git, design loop and tools/make_page each take 27-32 seconds; delegation and
core take 14-16. The longest single part sets the floor for a parallel run: about 32 seconds against 127 for
the whole, if every part gets its own core. Four cores means three big parts and the rest compete for the
fourth. Three things inside the big parts are not CPU work and do not shrink with more cores: safe git's
prompttimer cases wait on real timeouts (12.2 seconds across 491-512, one case is 2.1 s alone),
delegation's stallcheck `--watch` case sleeps 4.0 s (524), and tools/make_page's 27.5 seconds is mostly
`make_page.py` starting as a fresh process for each build and its visual check (862-891, 30 checks; the one
cost to cut there is the process start, not the number of checks). Fixture setup (temp repos) is charged to
the check that follows it.

### The full grouped list

Every check appears in exactly one row. "Source lines" is the first and last line in `verify.py` where a
check in the row is reported (the call site of the case, not the helper). "Also touches" names the other
part(s) a check exercises (see the two-or-more-parts list below). "First check as printed" is the first 50
characters of what the run printed under the row's first number; `tools/check_verify_inventory.py` compares
it with a real run.

| Checks | Source lines | Part | Also touches | Seconds | What it tests | First check as printed |
|---|---|---|---|---|---|---|
| 1-4 | 335 | core |  | 0.5 | inject, showrule, standards and profile each stay under the per-hook context limit | inject stays under the per-hook additionalContext  |
| 5 | 335 | docs |  | 0.1 | docstiers stays under the per-hook context limit | docstiers stays under the per-hook additionalConte |
| 6-7 | 361-379 | core |  | 0.1 | showrule injects the show-don't-tell and clear-writing rules once | showrule injects the show-don't-tell rule, once, w |
| 8-16 | 455-478 | docs |  | 0.7 | docstiers: tiers present, missing, owned or not owned remote, old flat layout, tier list matches SKILL.md | docstiers: all six tiers present - silent |
| 17-66 | 566 | safe git |  | 4.0 | guard decision table: which shell commands prompt, which pass (GUARD_CASES) | git status |
| 67-86 | 623 | safe git |  | 1.6 | guard on commits and pushes depending on the branch (BRANCH_CASES) | git commit -m "checkpoint"   [on claude/some-topic |
| 87 | 640 | safe git |  | 0.3 | a prompt the branch exemption could have silenced says why it did not | a prompt the branch exemption could have silenced  |
| 88-92 | 685-728 | safe git |  | 1.3 | guard when work is saved: reset, restore, delete, force-push on clean or unpushed branches | guard: off the default branch with a clean tree an |
| 93-95 | 736-810 | safe git |  | 1.2 | guard branch trace, linked-worktree branch, branch judged by payload cwd / cd / git -C | an exempted command traces the branch it was exemp |
| 96-99 | 861-938 | safe git |  | 2.0 | guard inside a subagent, idle-aj timeouts, the waiting-on-you list shown by scope | guard: inside a subagent a destructive step (and a |
| 100-111 | 1024-1148 | safe git |  | 1.3 | guard docs-tier reminder on commit, git add parsing, missing git binary, -C refusal | a claude/ branch commit with a staged source file  |
| 112-115 | 1167-1221 | safe git |  | 0.2 | branch ownership read from .git/HEAD, guard internal error exits 2, odd payload shapes | branch ownership is read from .git/HEAD, never by  |
| 116-120 | 1258-1305 | safe git |  | 0.3 | guardwrite: Write over an existing file refused, new file allowed, empty and broken payloads | Write over a file I did not create is refused, nam |
| 121-125 | 1332-1411 | core |  | 0.1 | inject: every rule heading, plugin root, step-card pointer, unreadable rules file warns | SessionStart injects every rule heading into conte |
| 126-131 | 1456-1493 | core |  | 0.4 | scope: long and short reminder, no-prompt payload, empty PATH, size baseline | a command-shaped prompt gets the full reminder |
| 132-144 | 1526-1610 | core |  | 0.9 | artifact: documents written outside the project are flagged; generated-note drift | plan written to ~/.claude/plans is flagged for cop |
| 145-147 | 1627-1663 | core |  | 0.0 | repo-only checks: repo versus installed copy, CLAUDE.md not a copy of the rules, 4000-byte limit | the repo-only checks can tell a repo checkout from |
| 148-153 | 1685-1759 | core |  | 2.1 | profile and handover target: machine profile, local versus remote, drift between rules and code | SessionStart injects the recorded machine profile |
| 154-162 | 1783-1827 | core |  | 0.6 | runnable and compile reminders for created scripts, Dockerfiles and .cs files | a runnable .sh created in the project is flagged t |
| 163-164 | 1848-1869 | core |  | 0.0 | rules text: shim-is-not-a-compiler and green-suite rules | the shim-is-not-a-compiler rule states the check,  |
| 165-166 | 1878-1887 | delegation |  | 0.1 | delegate reminder after plan mode, and its hooks.json wiring | delegate reminds Claude to hand the plan to the bu |
| 167 | 1910 | core |  | 0.0 | rules text: disclosure rule | the disclosure rule states attribution, continuati |
| 168 | 1928 | writing |  | 0.0 | rules text: clear-writing rule carries the voice and hard constraint | the clear-writing rule carries the voice and its h |
| 169 | 1959 | core |  | 0.1 | HOUSE_RULES_VOICE=off removes the voice from inject | HOUSE_RULES_VOICE=off removes the voice and no rul |
| 170-171 | 1983-1998 | safe git |  | 0.0 | rules text: commit rule, and every rule the guard cites is a real heading | the commit rule draws the line at branch ownership |
| 172-195 | 2083-2292 | docs |  | 1.6 | harvest: long design comments flagged for docs/4-systems, thresholds, Edit handling, bad payloads | a design essay in a .cs file is flagged for portin |
| 196 | 2315 | safe git |  | 0.1 | guard traces its allow decision | guard traces its decision on the allow path, the p |
| 197-199 | 2315 | core |  | 0.3 | artifact and runnable trace their decisions | artifact traces its decision on a file that is not |
| 200-201 | 2327-2334 | safe git |  | 0.2 | guard silent by default, verbose trace on request | guard is silent by default on the allow path, the  |
| 202-207 | 2327-2334 | core |  | 0.4 | artifact and runnable silent by default, verbose trace on request | artifact is silent by default on a file that is no |
| 208-210 | 2345 | safe git |  | 0.2 | guard and guardwrite still print their could-not-tell trace by default | guard still prints its 'could not tell' trace by d |
| 211-213 | 2356-2372 | docs |  | 0.2 | harvest silent when nothing qualifies, speaks on a bad override or found blocks | harvest is silent by default when no comment block |
| 214 | 2400 | core | safe git, docs | 0.5 | HOUSE_RULES_TRACE=off silences every trace but not guard refusals or the harvest reminder | HOUSE_RULES_TRACE=off silences every trace and no  |
| 215 | 2423 | core |  | 0.1 | handover stays silent on its stand-down | handover stays silent on its stand-down, and the r |
| 216-219 | 2439-2478 | docs |  | 0.3 | harvest: multi-megabyte file scan budget, registration, no-Python warning | a multi-megabyte file is scanned, not skipped, and |
| 220-226 | 2520-2570 | core |  | 0.2 | run.sh interpreter cache: first run, cached run, stale, nag stub, unwritable, override | run.sh: the first run probes and writes the cache |
| 227 | 2616 | core | safe git, design loop, writing, delegation, docs | 0.0 | no except block in hook.py or any part module swallows a failure silently (reads all seven files) | no except block in hook.py swallows a failure with |
| 228-230 | 2664 | core |  | 0.2 | an internal crash in scope, artifact or runnable is announced, not swallowed | an internal crash in scope is announced rather tha |
| 231 | 2664 | delegation |  | 0.1 | an internal crash in delegate is announced | an internal crash in delegate is announced rather  |
| 232 | 2664 | core |  | 0.1 | an internal crash in handover is announced | an internal crash in handover is announced rather  |
| 233-235 | 2664-2692 | docs |  | 0.1 | an internal crash in harvest or docstiers is announced; archivist agent shaped for harvest delegation | an internal crash in harvest is announced rather t |
| 236-261 | 2734-2958 | core |  | 1.8 | handover Stop checks: command-card checklist, evidence-of-success, untested-without-reason, cannot-be-done claims | a reply containing a fenced block gets the handove |
| 262-263 | 2993-2995 | core |  | 0.1 | Stop parity note for ports that name nothing kept or dropped | Stop: a port that wrote files but names nothing ke |
| 264 | 2999 | writing |  | 0.0 | Stop visual note: an .html change looked at nothing | Stop: the same turn changed an .html file and look |
| 265-266 | 3002-3004 | core |  | 0.1 | parity note: stays quiet when the reply says what was kept, and the off switch | Stop: a port whose reply names what was kept and d |
| 267 | 3007 | core | writing | 0.1 | an everyday replace edit to a non-visual file trips neither parity nor visual note | Stop: an everyday 'replace' edit to a non-visual f |
| 268-270 | 3012-3018 | writing |  | 0.2 | visual check: screenshot or captured image in the turn, off switch | Stop: a visual edit with a Playwright screenshot i |
| 271-272 | 3021-3024 | core |  | 0.1 | scope adds the inventory-first clause for rewrite prompts only | scope: a prompt that reads like a rewrite gets the |
| 273-274 | 3028-3032 | delegation |  | 0.1 | delegate adds the parity note for a port plan without an inventory | delegate: an approved port plan with no keep/chang |
| 275-280 | 3050-3060 | writing |  | 0.8 | Stop plain-summary check: code-name openings, wide tables, off switch | Stop: a work report opening with a pile of code na |
| 281-286 | 3118-3184 | safe git |  | 0.5 | Stop commit check: uncommitted file this turn wrote, user's main, outside git | Stop: a file this turn wrote, still uncommitted on |
| 287-295 | 3198-3233 | safe git |  | 0.8 | branchnudge on the first uncommitted change; owned branch names; hooks.json wiring | branchnudge: the first uncommitted change on a non |
| 296-302 | 3268-3283 | safe git |  | 0.0 | creditcheck: Claude credit in a pull request body read back | creditcheck: a body with a Claude credit gets the  |
| 303-310 | 3299-3358 | delegation |  | 0.7 | audit and subagentcommit: files a subagent wrote and left uncommitted | audit: a file the subagent wrote that is still unc |
| 311-321 | 3424-3555 | delegation |  | 2.1 | autosave: ref saves, rate limit, fast path, worktrees, unreachable origin, 10-minute commit | autosave: an edit on a worktree-agent- branch save |
| 322-324 | 3570-3596 | delegation |  | 0.6 | commitgate: 3 uncommitted files block, then the hook commits | commitgate: 2 uncommitted files pass; 3 block the  |
| 325-326 | 3612-3624 | delegation |  | 0.6 | subagentcommit: autosave ref cleanup, retry commits for a worktree-agent branch | subagentcommit: a clean finish deletes the autosav |
| 327-330 | 3646-3674 | delegation |  | 0.3 | worktreesweep, one JSON object per call, hooks.json wiring | worktreesweep: the parent commits a subagent workt |
| 331-349 | 3777-3937 | design loop |  | 3.0 | issue gate: 3+ step plans need labelled issues before source edits; recording, Stop line, subagent worktree | issues: a 5-step plan writes the gate state and th |
| 350-357 | 3954-3997 | design loop |  | 1.7 | pull request rule: Refs required, closing words refused (reaches guard through the issue-guard link) | pr: a body with 'Closes #5' is denied and the reas |
| 358-361 | 4030-4045 | safe git |  | 0.7 | agent-branch rule at SessionStart profile: claude/ branch told to switch to AjsAgent/ | agent-branch: claude/foo is told to git switch -c  |
| 362-375 | 4057-4219 | safe git |  | 3.5 | attribution and guardgithub: Claude credit in commits, PRs, issues, gh api and curl refused | attribution: a commit crediting Claude (co-author  |
| 376-380 | 4252-4274 | design loop |  | 0.9 | author guard: Claude git identity refused (code in design_loop, reached through guard) | author: a Claude repo identity is refused with the |
| 381 | 4288 | safe git |  | 0.3 | remote profile warns about a Claude git identity | author: a remote profile with a Claude identity sa |
| 382-385 | 4297-4321 | design loop |  | 1.2 | close guard: gh issue close refused without recorded QA and merge | close: `gh issue close` with nothing recorded is r |
| 386-393 | 4334-4400 | design loop |  | 0.6 | issuelist: open issue titles at SessionStart, cache, gh failure, switches | issuelist: a GitHub repo gets the open issue title |
| 394-395 | 4413-4425 | design loop | delegation, safe git, core | 0.4 | issue workflow: no gh call on a tool call; every output is one JSON object | issues: delegate, commitgate, the Bash PostToolUse |
| 396 | 4437 | core |  | 0.0 | no extra hook processes on Write/Edit/Bash (hooks.json count) | issues: no new hook process on Write/Edit/Bash - P |
| 397 | 4444 | design loop |  | 0.0 | issue-workflow rules section and detail file exist at the plugin version | issues: the rules section and its detail file exis |
| 398 | 4452 | delegation |  | 0.0 | builder and archivist agents commit as they go | the builder and archivist commit as they go, not o |
| 399-400 | 4469-4478 | core |  | 0.9 | profile flags a memory that restates the old commit rule | profile: a memory restating the old commit rule is |
| 401-402 | 4489-4612 | core |  | 0.1 | handover emits Stop feedback; scope long reminder matches the rules document | the handover check emits Stop feedback, not a bloc |
| 403-404 | 4612 | safe git |  | 0.2 | Stop commit note and branch nudge match the rules document | the Stop commit note (#97), on the user's branch m |
| 405-406 | 4612 | core |  | 0.2 | compile and runnable notes match the rules document | the compile-verification note (runnable handler, . |
| 407 | 4612 | delegation |  | 0.1 | delegate reminder matches the rules document | the delegate reminder (ExitPlanMode, including the |
| 408 | 4612 | docs |  | 0.1 | harvest reminder matches the rules document | the harvest reminder (long-form comments) matches  |
| 409-410 | 4612-4639 | core |  | 0.1 | command-handover checklist matches the rules; old deliverable machinery gone | the command-handover checklist (Stop hook) matches |
| 411-414 | 4668-4687 | delegation |  | 0.1 | delegation nudge on plan exit, wiring, rule stated once | the delegation nudge is emitted when plan mode is  |
| 415 | 4703 | core |  | 0.0 | card format stated once alongside the six items | house-rules.md states the card format once, alongs |
| 416-418 | 4743-4792 | delegation |  | 0.0 | scout, builder, reviewer, editor agents; no executor reference; archivist digest | the scout, builder, reviewer and editor agents exi |
| 419-423 | 4822-4920 | core |  | 0.0 | output style, card pointer, step-card template, anti-patterns, desktop-verification table | the handover-cards output style is forced, so it a |
| 424 | 4978 | design loop |  | 0.0 | page rule and architecture table agree, nothing publishes unasked | the page rule and the architecture.md table agree, |
| 425-426 | 5000-5030 | core |  | 0.0 | card template not duplicated in CLAUDE.md; claude.ai chat block | the card template was not duplicated into CLAUDE.m |
| 427 | 5040 | delegation |  | 0.0 | scout and builder descriptions authorize proactive use | the scout and builder descriptions authorize proac |
| 428-432 | 5073-5141 | core |  | 0.6 | install.py opusplan; SessionStart preflight; profile truncation; doctor install commands | install.py sets model = opusplan and the docs scop |
| 433 | 5168 | docs |  | 0.0 | harvest-scan command exists and runs harvest_scan.py | /house-rules:harvest-scan exists and runs the inst |
| 434 | 5216 | core |  | 0.0 | architecture tables match hooks.json | the architecture tables in docs/architecture.md an |
| 435 | 5255 | safe git |  | 0.0 | 'What trips the guard' table matches the guard's git verbs | the 'What trips the guard' table matches GUARD_R3/ |
| 436-462 | 5290-5641 | core |  | 1.4 | standards injection by project type, profile hardware lines, free-first rule, run.sh fallbacks | a bare directory injects coding-philosophy and nei |
| 463 | 5668 | docs |  | 0.0 | tiered-docs rule and project-docs skill have not drifted | the tiered-docs rule and the project-docs skill it |
| 464-465 | 5704-5732 | delegation |  | 1.1 | scope adds the delegation clause on a go-ahead (code in delegation) | scope adds the delegation clause on a go-ahead and |
| 466-478 | 5829-6009 | delegation |  | 1.5 | announce and verdict: declared model, observed model, MISMATCH, deferral, wiring | announce reports the agent, its declared model and |
| 479-484 | 6046-6108 | delegation |  | 0.2 | subagentrules: subagent core from marked sections, SubagentStart wiring | subagentrules generates a subagent core from house |
| 485-490 | 6154-6197 | delegation |  | 0.8 | agentcap: spawn cap of two, expiry, off switch, corrupt state, subagent spawn denied | agentcap: the first and second spawn are allowed,  |
| 491-500 | 6251-6347 | safe git |  | 5.6 | prompttimer: unanswered prompt denied after timeout, per-action timers, locks | prompttimer: an unanswered prompt is denied after  |
| 501-504 | 6368-6393 | safe git |  | 2.4 | scope lists the session's timed-out action once; waiting-on-you list | scope: a background task-notification prompt chang |
| 505-506 | 6419-6431 | design loop | safe git | 0.2 | issuelist shows and drops other sessions' waiting entries | issuelist: another session's entry is shown to Cla |
| 507-512 | 6451-6509 | safe git |  | 4.1 | guard prompt text names the timeout; prompttimer exemptions and per-session behavior | guard: the prompt says 'If nobody answers within 5 |
| 513-516 | 6530-6563 | core | safe git | 2.4 | promptran: an action that ran while its prompt waited stops the timer | promptran: an action that ran while its prompt was |
| 517-523 | 6583-6688 | delegation |  | 0.6 | verdict audit summary, subagent ledger, audit after a foreground return | verdict's audit summary reports commands with exit |
| 524-535 | 6728-6776 | delegation |  | 4.4 | stallcheck.py: STALLED, finished, --session, --agent, --watch | stallcheck: --watch re-prints a row that stays STA |
| 536-544 | 6787-6905 | delegation |  | 0.5 | audit and userpromptaudit never block; wiring; reported-update rule | audit never blocks a PostToolUse call, even on a b |
| 545-551 | 6986-7060 | core |  | 0.7 | versioncheck quiet when agreeing; inject and showrule load newer installed rules | versioncheck is quiet when installed, marketplace  |
| 552-556 | 7079-7161 | core |  | 0.3 | versioncheck: lagging marketplace, failed auto-update, banner rule, stale GitHub, off switch | versioncheck flags installed lagging the marketpla |
| 557 | 7187 | safe git | core | 0.3 | guard surfaces versioncheck's marker once | guard surfaces versioncheck's marker once, on the  |
| 558-564 | 7225-7384 | core |  | 0.7 | versioncheck: API fallback, unreachable GitHub, new session, auto-update | versioncheck falls back to the GitHub API when the |
| 565-579 | 7461-7578 | docs |  | 0.7 | docref.py check: ok, stale, dangling, duplicate, malformed, fences, git tree | docref check: a pointer whose id is in exactly one |
| 580 | 7630 | docs |  | 0.0 | docref.py check: unreadable directory forces exit 1 | docref check: a directory the walk cannot list is  |
| 581-587 | 7647-7715 | docs |  | 0.4 | docref.py fix: dry run, --write repairs, CRLF, comment closers, unresolved | docref fix: without --write it reports what it wou |
| 588-595 | 7727-7855 | docs |  | 0.1 | docref.py new, new_id, unreadable files, bad --root | docref new: prints a 4-hex id not used by any mark |
| 596-611 | 7866-8017 | docs |  | 0.8 | docref.py fence edge cases, temp files, sentence periods, --exclude, deleted/nested/undecodable files | docref check: a four-backtick block holding an unc |
| 612-614 | 8039-8082 | docs |  | 0.1 | docref command exists; live check passes on this repo's own docs | /house-rules:docref exists and runs the installed  |
| 615-640 | 8183-8504 | docs |  | 1.5 | plain_docs_check.py: every rule, --queue, --root, single file | plain_docs_check: a well-formed plain copy passes  |
| 641-642 | 8540-8547 | docs |  | 0.1 | plain_docs_check.py: reader that stops early | plain_docs_check --queue: a reader that stops earl |
| 643-717 | 8986 | design loop |  | 7.8 | design loop stage machine: approvals, code lock, labels, QA, worktree, script writes, page reminder | design loop: a fresh project refuses a code edit |
| 718-727 | 9068 | design loop |  | 0.9 | closable record: QA pass saves issues, merge stamps them | closable record: a QA failure creates no closable  |
| 728-748 | 9170 | design loop |  | 1.8 | close guard: gh and MCP closes need QA plus merge or an approved list | close guard: gh close with a QA pass and a merge i |
| 749-751 | 9270 | design loop | tools/make_page | 1.1 | sweep approvals: sweep page builds through make_page.py and refuses bad rows | sweep approvals: a sweep page builds, shows each r |
| 752-759 | 9270 | design loop |  | 2.9 | sweep approvals: phrases move rows into sweep; guard allows matching closes | sweep approvals: Sweep approved: issues moves the  |
| 760-765 | 9306-9369 | design loop |  | 0.5 | approval reading: several approvals in one message, QA redo, cross-repo issues | design loop (#307): a design and a build-plan appr |
| 766-778 | 9490 | design loop |  | 0.2 | label setup: labels.py creates only missing house labels | label setup: all three missing: all three created  |
| 779-797 | 9707 | writing |  | 1.0 | clarity.py: vague numbers, bare references, repeats, jargon; reply and page writing notes | clear writing: vague: "about 43 tests" is flagged  |
| 798-800 | 9707 | writing | design loop | 0.2 | clarity.py issue-section check, reached through the issue refusal in design_loop | clear writing: issue: the GitHub tool's issue with |
| 801-808 | 9707 | writing |  | 0.4 | editor reminder and page-scan rules | clear writing: editor: writing a page under docs/p |
| 809-827 | 9924 | design loop |  | 1.4 | checkpoint table: page rule, once-per-message, page links | checkpoints: page (#309): a long reply with no pag |
| 828-830 | 9924 | design loop | writing | 0.2 | checkpoint row: editor | checkpoints: editor: a miss blocks once, naming th |
| 831-833 | 9924 | design loop | core | 0.2 | checkpoint row: evidence | checkpoints: evidence: a miss blocks once, naming  |
| 834-836 | 9924 | design loop | safe git | 0.2 | checkpoint row: commit | checkpoints: commit: a turn that left its file unc |
| 837-839 | 9924 | design loop | writing | 0.2 | checkpoint row: plain summary | checkpoints: plain summary: a miss blocks once, na |
| 840-844 | 9924 | design loop |  | 0.4 | checkpoint table: page rule on proposals and short answers; aj's no-page escape | checkpoints: page (#309): a short proposal with th |
| 845-846 | 9924 | design loop | writing | 0.2 | checkpoint table: no-page escape for editor; bare reference gets no report line | checkpoints: editor: the same escape lets a long r |
| 847-861 | 9924 | design loop |  | 1.1 | checkpoint table: QA page rows, retry never blocks, HOUSE_RULES_LOOP=off | checkpoints: page: "no page" quoted inside a helpe |
| 862-880 | 10264 | tools/make_page |  | 17.4 | make_page.py: style file, build, QA mode, approval field, picture rules | make_page: build with no style file exits 3 and na |
| 881 | 10264 | tools/make_page | design loop | 0.9 | make_page.py: the copied approval text matches the design-loop gate (loads design_loop) | make_page: the copied text, with choices (approval |
| 882-891 | 10264 | tools/make_page |  | 9.2 | make_page.py: clipped-card check, outside-folder line, summary pages | make_page: a 40-character unbroken word in card te |
| 892-904 | 10326 | design loop |  | 1.1 | pagecheck: hand-written pages refused, builder pages allowed | pagecheck: Write of a hand-written docs/plans page |
| 905-910 | 10382 | safe git |  | 0.5 | never-blocked list: own-branch commits and pushes, own files, claude/ branch refused | never-blocked: git commit on an AjsAgent/ branch g |
| 911 | 10382 | safe git | design loop | 0.1 | never-blocked list: issue missing sections refused | never-blocked: enforced: an issue missing its sect |
| 912 | 10382 | delegation |  | 0.1 | never-blocked list: a helper starting a helper is refused | never-blocked: enforced: a helper starting its own |
| 913 | 10382 | design loop | tools/make_page | 0.1 | never-blocked list: publishing a make_page.py page goes through | never-blocked: publishing a make_page.py page goes |

### Checks that exercise two or more parts

Multi-part checks: 35. The part in the second column is the one counted in the summary; the third
names the other parts the check also exercises.

| Checks | Counted under | Also exercises | What it does |
|---|---|---|---|
| 214 | core | safe git, docs | HOUSE_RULES_TRACE=off silences every trace but not guard refusals or the harvest reminder |
| 227 | core | safe git, design loop, writing, delegation, docs | no except block in hook.py or any part module swallows a failure silently (reads all seven files) |
| 267 | core | writing | an everyday replace edit to a non-visual file trips neither parity nor visual note |
| 394-395 | design loop | delegation, safe git, core | issue workflow: no gh call on a tool call; every output is one JSON object |
| 505-506 | design loop | safe git | issuelist shows and drops other sessions' waiting entries |
| 513-516 | core | safe git | promptran: an action that ran while its prompt waited stops the timer |
| 557 | safe git | core | guard surfaces versioncheck's marker once |
| 749-751 | design loop | tools/make_page | sweep approvals: sweep page builds through make_page.py and refuses bad rows |
| 798-800 | writing | design loop | clarity.py issue-section check, reached through the issue refusal in design_loop |
| 828-830 | design loop | writing | checkpoint row: editor |
| 831-833 | design loop | core | checkpoint row: evidence |
| 834-836 | design loop | safe git | checkpoint row: commit |
| 837-839 | design loop | writing | checkpoint row: plain summary |
| 845-846 | design loop | writing | checkpoint table: no-page escape for editor; bare reference gets no report line |
| 881 | tools/make_page | design loop | make_page.py: the copied approval text matches the design-loop gate (loads design_loop) |
| 911 | safe git | design loop | never-blocked list: issue missing sections refused |
| 913 | design loop | tools/make_page | never-blocked list: publishing a make_page.py page goes through |

Cross-part reads that are not listed because each still has one owner: the rules-text drift checks (402-409)
compare one handler's note against `house-rules.md`, so they depend on the rules document but exercise one part.

### Shared test setup

Everything below is defined once near the top (or just before its first user) and used by checks in several
parts. A per-part test file for #370 needs its own copy or a shared helper module.

| Setup | Source lines | What it is | Checks that use it |
|---|---|---|---|
| `report`, `STEP`, `FAILURES`, `SKIPPED` | 81-97, 10386-10407 | the numbering, the failure count and the exit code | all 913 |
| `_RUN_TMP` / `TMPDIR` | 42-45 | per-run temp folder put in `os.environ` for every child process (#229), removed at exit | every check that starts a hook |
| path constants `HERE`, `HOOK`, `CORE`, `SAFE_GIT`, `DOCS`, `DELEGATION`, `DESIGN_LOOP`, `WRITING`, `RUN`, `ROOT`, `RULES_FILE`, `HOOKS_JSON`, `AGENTS_DIR`, `ARCHIVIST`, `STYLE`, `TEMPLATE`, `DOCSKILL`, `CHATDOC`, `VERIFYDOC`, `ARCHDOC` | 47-71 | where the files under test are | all parts |
| `IN_REPO`, `absent_repo_files`, `skip_repo_check` | 87-116 | repo-only checks SKIP outside a checkout | 145-150, 423-436, 614 (plus doc reads in docs) |
| `read`, `rules_corpus`, `rules_text`, `DETAIL_DIR`, `STANDARDS_DIR` | 118-142 and each use | read a file; the rules text plus detail files | `read`: about 145 call sites in every part; rules text: 144-171, 402-429, 462-465, 544-556 |
| `run_hook`, `run_shell`, `payload_for`, `env_in`, `verbose_env`, `_additional_context` | 142-326 | start a handler through `run.sh` with a payload and an environment | `run_hook` has 217 call sites: 1-415, 429-564, 643-808, 892-913, i.e. every part that drives a hook |
| `_FIXTURE_ROOT`, `_GIT_GLOBAL`, `_repo_on` and `REPO_THEIRS`, `REPO_MINE`, `REPO_DETACHED`, `REPO_THEIRS_FEATURE`, `REPO_NONE` | 197-224 | one temp folder for all fixtures; an isolated git config so the developer's does not leak; five hand-written `.git/HEAD` repos | `REPO_*`: 1-94, 115-118, 214; `_FIXTURE_ROOT` also 148-158, 220-364, 399-401, 431-432, 485-492, 524-530, 643-765 |
| `DOCSTIERS_*` repos and `_docstiers_repo` | 244-300 | docs-tier fixtures | 5, 8-15 |
| `EXAMPLE_ENV`, `_size_cases` | 310-335 | example machine profile; size-limit table | 1-7, 358-364 |
| `_sv_*` (saved-work repo) | 648-728 | repo with commits, pushed or not | 88-92 |
| `_ua_*`, `_fr_*` (unattended-aj repo, scratchpad refusals) | 822-943 | session folder, helper-agent payloads, waiting list | 96-99 |
| `stop_payload` | 2725 | a Stop payload | 236-295, 345-350, 394-401, 643-717, 779-861 |
| `_hand_transcript`, `_turn_transcript`, `hand_case`, `pv_case` | 2700-3043 | transcript fixtures and the handover case helper | `hand_case`: 236-264; transcripts: 247-328, 779-861; `_turn_transcript`: 262-280 |
| `commit_case` | 3105 | a plain report-and-print helper that only has a commit-sounding name | 117 call sites in 281-401 and 32 more in 485-520 (agentcap, prompttimer, promptran, issuelist, scope), so it serves delegation, safe git, design loop and core |
| `_commit_repo`, `_wrote_transcript`, `_project_env`, `_nudge`, `_stop_context` | 3067-3200 | repo with committed and dirty files, and env | 281-310, 322-330, 399-401, 905-913 |
| `_as_*` (autosave repos, bare origin) | 3366-3560 | autosave fixtures | 311-321 |
| stub `gh`: `_ISS_STUBDIR`, `_iss_stub`, `_ISS_MARK`, `_iss_repo`, `_iss_env`, `_iss_call`, `_iss_guard` | 3681-4478 | stub `gh` on PATH that leaves a marker when it runs | 331-336, 388-398; `_iss_env` also 728-748 |
| `_pt_*` (prompttimer repo and state file) | 6203-6560 | waiting-on-you state under `.git/house-rules/` | 491-516 |
| `_cap_case` | 6698 | stallcheck case helper | 524-535 |
| `docref_mod` (loaded in-process), `_dr_*`, `docref_case` | 7437-8082 | docref fixtures | 565-614 |
| `pd_case`, `pd_closed_reader_case` | 8150-8547 | plain_docs_check fixtures | 615-642 |
| `_loop_dir`, `_loop_env`, `_loop_labels_file` (stand-in labels file), `_loop_gh`, `_loop_edit`, `_loop_stop`, `_loop_state`, `_loop_stage` | 8560-8951 | the design-loop project and its fake GitHub labels | 643-717; `_loop_env` is also the base of `_cl_env` (718-748) and the label-setup, clear-writing and checkpoint blocks (766-861); `_loop_dir` also 779-861 |
| `_cl_*` (closable-record repo) | 8988-9170 | state file and Decisions.md | 718-727 |
| importlib loads of `hook.py` as a module: `hook_creditcheck`, `hook_nogh`, `hook_for_labels`, `hook_for_page_scan`, `hook_for_approval` | 3240, 4384, 9472, 9648, 10149 | call part functions directly | 296-302, 392, 766-778, 807-808, 881 |
| `_cw_*`, `_CW_USER`, `_CW_WRITE`, `_CW_EDITOR` | 9492-9707 | clear-writing cases; transcript pieces reused by the checkpoint block | 779-808 and 809-861 |
| `_ck_*` (checkpoint table cases, `_ck_stage`) | 9709-9925 | stage-file writer and reply runner | 809-861 |
| `MAKE_PAGE`, `_mp_tmp`, `_mp`, `_mp_proj`, `_mp_content` | 9926-10265 | one temp folder, many named projects | 862-891 (and the sweep page build, 749-751, calls `make_page.py` too) |

### Checks whose result depends on running order or state left earlier

Found by reading the code; none was proven by reordering (that would take a run per permutation). "Reads"
means a later check inspects a file or value an earlier one wrote, so moving either breaks it.

| Checks | State they share | Evidence |
|---|---|---|
| 643-717 | `_loop_dir` stage file: each case starts in the stage the previous one left (`Design` then `Plan` then `Build` then `QA` then `Done`, with `QA failed` looping back) | `_loop_stage()` is read after earlier approvals at lines 8649-8801; strictly ordered |
| 779-808, 809-861 | the same `_loop_dir` and `_loop_env` after 643-717 has left its last stage; pages created under `docs/plans/` (9558) are scanned by later checks; only the QA rows (848-859) set a stage themselves (`_ck_stage`) | reads of `_loop_dir` at 9546-9869 |
| 88-92 | `_sv_repo`: `git reset`/commit steps between cases change what the next case sees | lines 698-728 |
| 96-99 | the waiting-on-you list in `_ua_dir` (written by 96, read by 99), and the `house-rules-last-seen-verify-ua-sub` file in the temp folder (removed at 942) | lines 929-943 |
| 311-314 | one autosave repo `_d`: 312 reads what 311 left; 314's one-push-a-minute rule depends on the push stamp from 311/313 | lines 3416-3445 |
| 331, 334-340, 345-346 | one issues repo `_d` with the gate file: 331 closes the gate, 334-337 are refused by it, 339-340 open it | lines 3772-3870 |
| 386-389 | issuelist cache: 388 expects the cache the 386 start wrote (60 seconds) | lines 4334-4351 |
| 491-493, 494-498, 501-507, 508-511, 513-514, 515-516 | one waiting-on-you state file per run of cases; it is deleted between runs (6207, 6270, 6313, 6341, 6356, 6473, 6506, 6517, 6552) but not inside one. 499, 500 and 512 are alone | `_pt_state` resets |
| 718-727, 728-748, 749-759 | `_cl_dir` / `_iss_*` state: most cases start with `_cl_set`, which resets the stage but appends to `Decisions.md` and keeps the closable list; 719-720 and 731 read entries made earlier | lines 8990-9040; not read case by case |
| every check | `STEP`: a check's number is its print position, so splitting or reordering renumbers everything after it | lines 90-97 |

Timing-sensitive, not order-dependent but flaky if parts share a busy CPU: 216 (a multi-megabyte scan must
finish inside the hook timeout), 313 (autosave inside a 10 second budget), 492 and 497 (a one-second timeout
must wait about one second), 524 (`--watch` timing).

Not order-dependent that I found: the make_page cases make a named project folder each (`_mp_proj(name)`);
the docref and plain_docs_check case helpers were not read case by case, so that is unverified for them.

### What in verify.py makes the split in #370 hard

1. **No structure to split along.** It is straight-line script code with about 400 `report(` call sites and hundreds of module-level variables, not functions or classes. A part's checks are scattered:
   safe git is 14 separate runs: 17-120, 170-171, 196, 200-201, 208-210, 281-302, 358-375, 381, 403-404,
   435, 491-504, 507-512, 557, 905-911.
   Splitting means cutting the file into 7 parts' worth of fragments while keeping every variable they read.
2. **Helpers are defined far from where they are used.** `_hand_transcript` (2817) is used at 9605; `stop_payload`
   (2725) at 8593; `commit_case` (3105) at 6154-6563; `_commit_repo` (3067) at 10339; `_loop_env` (8563)
   at 9711; `_CW_*` (9605) in the checkpoint block. These need a shared helper module that every part file
   imports.
3. **Collect-first blocks.** From 643 on, cases are appended to a list and printed at the end, so a failed
   or slow case cannot be pinned to its call site by the number, and splitting a block mid-way means
   splitting a list.
4. **Real state chains** (the order-dependence list): 643-717 (75 checks) and 779-861 must stay in order and
   together; the design loop's chain is also read by the writing and checkpoint blocks through `_loop_dir`.
5. **Whole-repo reads across parts.** Checks 227, 402-409, 423-436 read several modules or the rules document at once; they
   cannot be filed in one part's file without importing the others' paths.
6. **Hard-coded release facts.** Check 397 asserts `plugin.json` is exactly `2.71.0` (lines 4442-4448), so each
   release edits `verify.py`; a per-part file would put that edit in whichever part holds the check.
7. **Fixed shared locations.** Session names such as `loop` and `pt-sess` and the scratchpad path built at
   line 868 are reused across blocks; parts that run at the same time need separate `TMPDIR` folders (the
   `_RUN_TMP` mechanism already gives one per process) or the files collide.
8. **Process-start cost.** A run makes 898 `hook.py` starts through `run.sh` (measured in #360, above); the
   parallel gain comes from running parts together, not from fewer checks. A runner that gives each part its
   own `TMPDIR` is what the split needs, which `_RUN_TMP` already supports.
9. **Balance.** Even perfectly split, three parts of about 28-32 seconds each set the floor at about 32
   seconds; cutting `make_page.py` process starts and the prompttimer waits is what would lower it, not the
   split.

### How this inventory was proved

`python tools/check_verify_inventory.py --run` runs `verify.py` once and checks: the grouped list covers
checks 1 to 913 once each with no gap or overlap; the list total equals the summary total (913); each part's
count in the summary equals the sum of its rows; the multi-part count stated above equals the rows with an
"Also touches" part. Everything above this paragraph is numbered as the single-file `verify.py` printed it
before #370, so those numbers describe that run and no longer match any current output. Since #370 the tool
also checks the split tables below (per-part counts after the moves, each part file present) and compares
the run per part: each part's section printed the number of results the split table says, 913 in all with
`all 913 checks passed`, and every row's "First check as printed" is a prefix of a check printed by the part
the table puts that row in. Without `--run` or `--output FILE` it checks the structure only and says it did
not compare with a run.

## The split layout (#370)

Step 2 of the verify.py rework (#368). Built 2026-10-21 on house-rules 2.71.0, branch
`AjsAgent/issue-370-split` off `AjsAgent/issue-281-fix` at ee77a81, on a 4-core machine. Design approved as
"verify rework 1A 2A". No check was deleted, merged or reworded: a full run prints exactly the 913 titles the
single-file run printed (the sorted list of titles is identical, no title differs even in a number).

### Layout

`claude-house-rules/plugins/house-rules/scripts/` holds:

| File | What it is |
|---|---|
| `verify.py` | the runner (below). Same name and same last line as before, so CI and CLAUDE.md are unchanged. |
| `checks/common.py` | the setup the parts share: `report`, `STEP`, `FAILURES`, `SKIPPED`, `finish()`, the path constants, `run_hook` and `run_shell`, the temp-repo helpers, the stub `gh` (`_iss_*`), the payload builders (`stop_payload`, `payload_for`, `guardwrite_payload`), the case helpers (`commit_case`, `pv_case`, `hand_case`'s transcript builders) and the fixtures more than one part reads. Defines `__all__` as every name it holds, underscore names included. |
| `checks/core.py`, `safe_git.py`, `design_loop.py`, `writing.py`, `delegation.py`, `docs.py`, `make_page.py` | one part each. Each starts with `from common import *`, runs on its own, numbers its checks from 1, ends with `finish()` and prints its own `RESULT:` line. |

Session triage has no checks yet (`house_rules/session_triage.py` is empty until #347), so it has no file.

**Isolation.** Each part is its own process. `common.py` names the temp folder after the part
(`house-rules-verify-<part>-...`) and points `TMPDIR` at it before any hook starts, and the fixture folder, the
stub `gh` folder and every repo the checks make sit inside it, so parts running at the same time share no
session name, scratchpad path, stage file, waiting-on-you list or git config.

**What was done to the code.** Every check was moved as written. The only edits:
- `common.py`: `HERE` is one folder up (`scripts/`, not `checks/`) and is put on `sys.path` so `import clarity`,
  `labels` and `make_page` still resolve; the temp folder carries the part's name; the banner prints moved to the runner.
- Six loops that reported checks of several parts were cut into one copy per part, body unchanged: the size
  loop (`_size_cases[:4]` core, `[4:]` docs), both `trace_cases` loops (`[:1]` guard in safe git, `[1:]` in core),
  the internal-crash loop (three copies with the events each part owns), the `RESTATEMENTS` loop (four copies,
  each selecting its rows by index) and the never-blocked list (reported in three groups, with `_nb_cases = []`
  between them).
- `docs.py`: the live `docref check` exclude list gains `scripts/checks/*.py`, because the part files hold the same
  deliberately well-formed example pointers `verify.py` did.
- Nothing else; `__file__` in the "no live file names the retired executor agent" check now names its own part file.

### The runner

`python claude-house-rules/plugins/house-rules/scripts/verify.py [options]`

| Option | What it does |
|---|---|
| none | runs every part at the same time, in subprocesses, as many at once as the machine has cores (slowest parts started first) |
| `--parts core,safe_git` | runs only the named parts; an unknown name exits 2 and lists the parts |
| `--changed` | runs only the parts a change touched (mapping below); cannot be combined with `--parts` |
| `--serial` | one part after another, in the fixed order, for debugging |
| `--timeout N` | seconds before a part counts as hung (default 900) |

It prints which parts it ran and why (the option, or each changed file with the part it mapped to), then each
part's output whole, in the fixed order core, safe_git, design_loop, writing, delegation, docs, make_page (never
interleaved), then a table of checks, result and seconds per part, then the last line
`RESULT: PASS - all N checks passed. The hooks are behaving as written.` with N the total. Exit 0 only if every
part passed. A part that exits without its `RESULT:` line, exits with a code that disagrees with it, cannot start
or times out counts as failed, and the runner names it. If no changed file maps to a part it prints
`RESULT: PASS - 0 checks run` and says so, rather than a silent pass.

### `--changed`

It diffs the working tree against `git merge-base origin/main HEAD` (so committed work on the branch, staged and
unstaged edits all count) and adds untracked files. If git or `origin/main` is unavailable it says so and runs every
part. Each changed file maps like this (under `claude-house-rules/plugins/house-rules/` unless stated); a file the
table does not know inside the plugin means every part:

| Changed file | Parts that run |
|---|---|
| `scripts/house_rules/<part>.py` for safe_git, design_loop, delegation, docs | that part |
| `scripts/house_rules/writing.py` | writing and design_loop (the clear-writing cases live in `checks/design_loop.py`, see below) |
| `scripts/house_rules/core.py`, `__init__.py`, `session_triage.py` | every part |
| `scripts/checks/<part>.py` for safe_git, design_loop, writing, delegation, docs, make_page | that part |
| `scripts/checks/core.py`, `scripts/checks/common.py` | every part |
| `scripts/hook.py`, `run.sh`, `verify.py`, `hooks/hooks.json` | every part |
| `scripts/clarity.py` | writing and design_loop (the clear-writing cases live in `checks/design_loop.py`, see below) |
| `scripts/make_page.py` | make_page |
| `scripts/docref.py`, `plain_docs_check.py`, `harvest_scan.py` | docs |
| `scripts/stallcheck.py` | delegation |
| `scripts/labels.py` | design_loop |
| `templates/step-card.html` | core and make_page |
| `templates/handover-page.html` | design_loop and make_page |
| `templates/decision-summary.page.json`, any other template | make_page (other templates: core, design_loop and make_page) |
| `agents/archivist.md` | delegation and docs; other `agents/*` : delegation |
| `skills/project-docs/*` | core and docs; `skills/plain-docs/*`: docs |
| `output-styles/*` | core |
| `commands/docref.md`, `harvest-scan.md`, `plain-docs.md` | docs; `labels.md`: design_loop; `doctor.md`: core |
| `.claude-plugin/*` (plugin.json) | core, design_loop and make_page |
| `rules/**` and anything else in the plugin | every part |
| `docs/architecture.md`, `CLAUDE.md` | core, design_loop, docs, delegation |
| `docs/claude-ai-instructions.md`, `docs/desktop-verification.md`, `.claude-plugin/marketplace.json` (repo root) | core, docs, delegation |
| `docs/example-environment.md`, `claude-house-rules/README.md` | core, safe_git, docs, delegation |
| any other file outside the plugin (other docs, `tools/`, `.github/`) | docs and delegation, the two parts that scan the whole repo (docref and plain_docs_check; the retired-agent scan) |

Two things in the table go further than "a change to a part's file runs that part". `clarity.py` and
`house_rules/writing.py` also run design_loop, because 30 of the clear-writing checks live there (below). And a
change outside the plugin still runs docs and delegation, because those two scan every file in the repo.

### Checks per part after the split

Run alone, one part at a time, then added up (913). Counts are what each part file prints; seconds are one parallel
full run (wall-clock 34.5 s, second run 35.9 s).

| Part | Checks | Seconds (full run 1 / 2) | Lines | The #369 summary said |
|---|---|---|---|---|
| core | 181 | 15.8 / 16.2 | 2,489 | 181 |
| safe_git | 186 | 31.2 / 32.4 | 1,706 | 184 |
| design_loop | 281 | 27.3 / 28.8 | 1,981 | 253 |
| writing | 11 | 1.4 / 1.3 | 76 | 41 |
| delegation | 99 | 13.7 / 14.5 | 1,486 | 99 |
| docs | 125 | 7.1 / 7.2 | 1,805 | 125 |
| make_page | 30 | 29.0 / 30.6 | 365 | 30 |
| **Total** | **913** | | | 913 |

### Checks placed differently from the inventory

Two groups depend on state left earlier in one run and cross a part boundary in the #369 inventory. The design says
an order-dependent group stays whole in one file, so each moved to the part that owns the state:

| Checks (old numbers) | From | To | Count | Why |
|---|---|---|---|---|
| 505-506 | design_loop | safe_git | 2 | `issuelist` shows and drops other sessions' waiting entries from the same `_pt_state` file that 501-504 and 507 write and read; the group "501-507" runs on one waiting-on-you state file |
| 779-808 | writing | design_loop | 30 | the clear-writing cases (779-808) and the checkpoint table (809-861) run in the same `_loop_dir` project folder with the same `_loop_env`, and the checkpoint rows read pages and transcripts the writing cases leave under `docs/plans/`. Both halves stay together, in order, in `checks/design_loop.py` after the 643-717 chain |

Everything else is in the part the inventory gave it (multi-part checks stay with the part that owns the code they
mainly exercise, as counted in the #369 summary). Because the clear-writing cases moved, a change to `clarity.py` or
`house_rules/writing.py` runs design_loop as well as writing (the design said `clarity.py` maps to writing alone;
that would have left the 30 moved cases unrun).

### Measured times (2026-10-21, 4 cores, same machine and method as the earlier runs)

| Run | Result | Seconds |
|---|---|---|
| Full parallel, run 1 | `RESULT: PASS - all 913 checks passed.` | 34.5 |
| Full parallel, run 2 | `RESULT: PASS - all 913 checks passed.` | 36.0 |
| `--serial` | `RESULT: PASS - all 913 checks passed.` | 132.1 |
| `--parts design_loop` | `RESULT: PASS - all 281 checks passed.` | 29.9 |

Before the rework a run took 197 seconds, and 130-134 after restructure step 2. A parallel run is about 35 seconds,
which is the slowest part (safe_git, 31-32 s) plus start-up: the floor the #369 inventory predicted (about 32 s).
`--serial` matches the old single-process time because the checks are unchanged. The remaining time inside safe_git
(prompttimer waits) and make_page (process starts per page build) is what a later step would cut.

### Adding or changing a check

Put it in the part file for the code it exercises, with `report(...)` / `commit_case(...)` as before. Anything
a second part needs goes in `common.py`; a helper used by one part stays in that part's file. A check that depends
on state an earlier check leaves must sit in the same file, after it. Run the part alone first
(`python3 .../checks/<part>.py`), then `verify.py`. `python tools/check_verify_inventory.py --run` proves the table
above still matches the files.

## Measured after the rework (#371)

Measured 2026-10-21 on this machine (4 cores, Linux), wall clock around `verify.py`, after 2.72.0.
Every run reported 913 checks.

| Run | Wall clock |
|---|---|
| Before restructure step 2 (2026-10-21) | 197 s |
| After step 2, before the split (about) | 130 s |
| Full `verify.py`, run 1 (parallel) | 40.7 s |
| Full `verify.py`, run 2 (parallel) | 39.5 s |
| `verify.py --serial` | 132.5 s |
| `verify.py --changed`, writing.py touched, run 1 | 1.8 s |
| `verify.py --changed`, writing.py touched, run 2 | 1.5 s |

- **The rule being timed (2A):** a session runs the touched parts twice and everything else once; CI
  runs the full suite. For a writing-only change that is about 3.3 s for both touched runs, against
  about 80 s for two full runs.
- **Touched-parts run:** a comment-only line appended to `scripts/checks/writing.py`, uncommitted.
  `--changed` chose only `writing` (11 checks, 1.4 to 1.7 s inside the part) and ran nothing else.
  The edit was then removed by copying the original back.
- **Caveat on `--changed`:** it diffs against the merge base with `origin/main`. On a branch that
  already differs from `origin/main` in every part (this one, until #370 merges), `--changed`
  selects all seven parts and takes the full-run time (39.5 s was measured). The 1.8 s figure was
  taken in a scratch clone whose `origin/main` was set to this branch's head, so only the
  uncommitted edit counted. On a branch cut from an up-to-date `main` the two are the same.
- **Speed-up:** parallel full run is about 5x faster than 197 s and about 3.3x faster than 130 s;
  serial (132.5 s) matches the 130 s step-2 figure, so the split costs nothing when run in series.
