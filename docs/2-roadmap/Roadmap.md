# Roadmap

What 0-100% means for each milestone, and what "done" is checked against. A milestone is done
when its acceptance criterion has actually been run and passed, not when the code exists.

## 1. The house-rules hook engine — 100%

Enforces aj's global CLAUDE.md rules as Claude Code hooks, on every device and every project,
without a per-repo file to copy around.

**Contains.** Eleven hook handlers dispatched from
[`hooks.json`](../../claude-house-rules/plugins/house-rules/hooks/hooks.json) through
[`hook.py`](../../claude-house-rules/plugins/house-rules/scripts/hook.py)'s `EVENTS` table —
`inject`, `standards`, `scope`, `guard`, `artifact`, `runnable`, `delegate`, `announce`,
`verdict`, `handover`, `harvest`. The `@house-rules:builder` subagent that the model-split rule
actually runs on. Full detail in [`docs/4-systems/hook-engine.md`](../4-systems/hook-engine.md).

**Acceptance.** `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
**Checked 2026-09-15: 203/203 PASS.**

## 2. The six-tier documentation convention — 100% as a mechanism

`house-rules:project-docs` defines the tier structure this very file is part of, and the plugin
routes rationale/post-mortems into `docs/6-decisions/Decisions.md` rather than into a tier-4 system doc.

**Contains.** The `house-rules:project-docs` skill, the tier list and card format in
`rules/house-rules.md`, `hook.py`'s `harvest`/archivist routing to `docs/6-decisions/Decisions.md`, and
`verify.py`'s tiered-docs drift checks (the rule names the skill, the skill specifies all six
tiers, the routing text agrees in both directions).

**Acceptance.** The tiered-docs checks inside `house-rules`' `verify.py` pass (they're part of
the 203 above, checked 2026-09-15). This criterion is about the **mechanism** — a repo *can*
adopt the six tiers and the plugin routes correctly if it does. Whether *this* repo's own
`docs/` actually instantiates all six is tracked separately, in
[`ProjectState.md`](../3-state/ProjectState.md), because "the mechanism works" and "every repo has adopted
it" are different claims — the second was explicitly deferred as its own follow-up in
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](../archive/2026-09-15-sixth-documentation-tier.md).

## 3. Offshoot plugins (`prompt-workshop`, `agent-router`) — 50%

Two v0.1 shells copying the `house-rules` formula toward "what should the work even be" instead
of "how should it be handed back." Both plugin.json versions read `0.1.0`.

**Contains.** `prompt-workshop`'s under-specification nudge and `agent-router`'s three-tier
model-routing nudge, each a full shim+hook.py+verify.py+agents set, not stub code. Detail in
[`docs/4-systems/offshoot-plugins.md`](../4-systems/offshoot-plugins.md).

**Acceptance, split because the mechanism and the judgment quality are different claims:**

- *Mechanism ships and verifies* — `prompt-workshop`'s and `agent-router`'s `verify.py` both
  exit 0. **Checked 2026-09-15: 22/22 and 41/41 PASS.** Done.
- *The classifiers are good enough to trust unattended* — **not done, and not yet measurable.**
  Both heuristics were verified only against hand-picked cases in their own suites, never against
  real prompt traffic; neither ships `SubagentStart`/`SubagentStop` visibility to confirm a
  suggestion was acted on or that a routed subagent ran on its declared model. These are named as
  open questions by the plan that built them
  ([`docs/offshoots-plan.md`](../offshoots-plan.md#open-questions-not-resolved-by-this-shell)), not
  newly discovered here.

50% reflects "the mechanism is real and passes its own tests" against "the actual value
proposition — good routing — is unvalidated," weighted roughly even.

## 4. Distribution & install tooling — 100%

Getting all three plugins onto a machine, upgrading an existing install without stranding it on
an old version, and writing the two settings only a machine-level install can write.

**Contains.** `tools/install.py`'s four-command `install_steps()`, `bootstrap.ps1`/`bootstrap.sh`,
`tools/update.bat`, `tools/clean_install_test.py`, and `tools/verify_tools.py`. Detail in
[`docs/4-systems/plugin-distribution.md`](../4-systems/plugin-distribution.md).

**Acceptance.** `python tools/verify_tools.py` exits 0 — **checked 2026-09-15: 32/32 PASS.**
Additionally, per prior recorded verification on this machine, the real `bootstrap`/`plugin
update` command sequence has actually been run against the live `claude` CLI on this device (not
just its decision logic in isolation) — the higher bar `clean_install_test.py` exists for. Not
re-run as part of writing this roadmap; see [`ProjectState.md`](../3-state/ProjectState.md) for what that
means for how fresh this claim is.

## Open issues, in the order to take them

Triaged 2026-09-28 against the code on `main` (`a5bde41`, house-rules 2.38.0). #48, #50 and #70
were closed as stale, #75 as a duplicate of #72 and #86 as a duplicate of #90; each closing
comment gives the evidence. The 22 still open are grouped below. Within a group they're listed roughly in priority order, and
issues that overlap are named so they can be done as one change.

### A. Enforce the rules that already exist (highest: failures are happening now)

The rules text covers these; what's missing is a hook that fires when the rule is skipped.

- **#97 Commit rule has no hook for the obligation half.** Built in 2.39.0: a `Stop` commit
  check, the `branchnudge` handler, an `uncommitted:` line in `audit`, and a stale-memory
  preflight warning (`docs/6-decisions/Decisions.md`, 2026-09-28). Closes when its PR merges.
- **#93, #91, #92, #89 Verification required, not suggested.** Built in 2.40.0: the `Stop`
  evidence check now catches "can't be done"/"doesn't exist" claims and any "not checked" with
  no reason beside it (`docs/6-decisions/Decisions.md`, 2026-09-28). Closes when its PR merges.
- **#85 Verify a wait's target before leaving it.** Built in 2.41.0: the rule under "Nothing
  fails silently" and a `guard` pattern for a wait piped through `tail`/`head`.
- **#47 Vague instructions.** Built in 2.42.0: "An instruction names its exact input", under
  "Deliver a whole workflow".

- **#98 Plain summary first.** Built in 2.45.0, taken ahead of group C at the user's request: a
  work report opens with a plain summary readable on a phone, checked at Stop.

### B. Guard against silently dropped features

- **#90 (lead), #87 Parity inventory before a rewrite, port, restructure or migration.** Built in
  2.44.0 (rule plus `scope`/`delegate`/Stop checks); the feature-surface diff tripwire was not.
  #90 is the full write-up (#86 was closed as its duplicate), and #87 adds opening issues for
  features to be re-added. One change: widen `rules/detail/edit-place.md`, add the parity-inventory rule, then
  the hook ideas in #90.
- **#88, #96 Screenshots for visual changes.** Built in 2.44.0: the rule and a Stop check. Capture old and new flows and compare them. This
  fits under #90's "compare against the original, not itself", so do it after #90.

### C. The hook engine's own structure (from `docs/architecture-backlog.md`)

Refactors with no change in behaviour, needed before group A adds more handlers. Suggested order:

1. **#41 One failure-mode contract.** Put each event's fail policy in the `EVENTS` table so
   `verify.py` no longer builds `crash_snippet` source strings. Still open: `main()` still has
   its `if event ==` chain (`hook.py` ~3673).
2. **#42 One payload-field extractor.** `_FILE_PATH_RE` still drops escape handling (`hook.py`
   ~1908).
3. **#44 `verify.py` gets a name filter.** It is now 5,588 lines and still runs all of its checks
   every time.
4. **#43 Split `event_standards` into detect and render.**
5. **#46 Re-check the agent fields `verify.py` forbids.** The ban is still at `verify.py` ~2148
   and ~2586.
6. **#45 Vocabulary and ADRs.** Half done: `docs/6-decisions/Decisions.md` now holds decisions.
   Still missing: a glossary (`CONTEXT.md`) and entries for the `force-for-plugin` and `Stop`
   narrowing reversals.

### D. New tools and features

- **#94 Open issues automatically for work in progress.** Related: `claude/issue-forge-offshoot`
  (not merged) turns backlog docs into issues but doesn't track changes as they happen.
- **#71 Archive a whole session.** `tools/session_ledger.py` covers the main transcript but skips
  subagent transcripts (line ~65), so this is an extension of it.
- **#95 Cost of delegating to the executor versus doing the work on the main thread, with a
  chart.** Builds on `tools/measure_footprint.py`, which prices every hook since #74.

### D2. Hooks efficiency follow-ups (from `docs/plans/hooks-efficiency-review.md`; findings 1-3 shipped in 2.48.0)

- **Finding 2b/2c.** Merge same-event handlers into one dispatcher per event/matcher; later split
  `hook.py` into per-event modules.
- **Finding 4.** Duplicated logic inside `hook.py` (path extraction, base-name splitting, empty
  payload handling, four repo/branch resolvers); a merged dispatcher removes most of it.
- **Finding 5.** Rule-base weight and repetition (handover field list, evidence text, the "See
  `<plugin>/rules/detail/x.md`" suffix on 26 sections, the delegation exception in four places);
  stale token figure at `docs/architecture.md:460`.
- **Finding 6.** Rules that conflict or over-fire (commit-constantly vs the guard, autosave's
  `git add -A`, `SUBAGENT_MANDATE` for read-only agents, loose delegation trigger, handover check
  on illustrative fences).
- **Finding 7.** Docs tiers stay mandatory; only make the nag cheaper to resolve, fix the wording
  conflict with "build only what was asked", dedupe the repeated rule text.
- **Finding 8.** Repo maintenance: `verify.py` speed (test `hook.py` directly), one shared shim
  instead of three `run.sh` copies, offshoot overlap and `route`'s `except Exception: pass`,
  issue-forge duplicate PostToolUse entries, `worktreesweep` per-prompt walk and WIP-commit squash,
  `docs/architecture.md` overlap and unarchived plans.

### D3. Issue workflow follow-ups (from `docs/plans/issue-workflow-build-plan.md`; #108-#110 shipped in 2.49.0)

- **#142.** Shipped in 2.52.0: the prompt timer and the waiting-on-you list (#144-#146). Open: #143 (do
  `guard` prompts reach the timer in the desktop app?) and #147 (overnight-style check), both on aj's machine.
- **#133.** Shipped in 2.51.0: the installer sets the `attribution` setting and `guard` refuses text crediting Claude.
  Open: other machines get the setting only when `bootstrap` or `update` runs there.
- **#111, #112.** Shipped in 2.50.0: the `scout`/`builder`/`reviewer` tiers and the `agentcap` spawn cap.
  Still open: measuring a real spawn of each tier after an update and restart.
- **Commits without an issue number.** The end-of-turn check the plan left out.
- **`gh issue create` through `PowerShell`.** Not recorded by the gate today; needs either a wider
  `autosave` matcher (one more process per PowerShell call) or a move of the recording into `guard`.
- **Inject size margin.** `verify.py`'s inject margin went 9,000 to 9,700 for the new rules section;
  finding 5 of the efficiency review is the place to win that back.

### E. Research, with nothing to build yet

- **#69** How the superpowers subagent-driven-development workflow could be ported. #63 (auto
  push/PR) already took part of it.
- **#62** Dynamic subagent generation in the agyrules plugin, and its CLAUDE.md equivalent.
  Nothing about it is in this repo yet; it needs the agyrules source.
