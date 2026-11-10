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

## The roadmap: eight phases, in order (approved 2026-11-09)

The issue list triaged on 2026-10-09 that used to sit here is replaced. Every issue open on 2026-11-09 (226) was
checked against the code, and the work now runs as eight phases, one at a time, each with its own design, build
plan and QA. The next phase starts only when the one before it passes. The page is
[`docs/plans/2026-11-09-roadmap.html`](../plans/2026-11-09-roadmap.html); the per-issue verdicts and each
issue's phase are in [`triage/`](triage/). The decision is in
[`Decisions.md`](../6-decisions/Decisions.md) under 2026-11-09. The old list is in git history before this change.

1. **Approvals and the design loop just work** (20 old issues). Done when each of the failed approvals from
   2026-11-09 gets the right answer and a QA fix needs one message from aj, in a real desktop app session.
2. **Docs and files you can trust** (17). Done when a drift check flags a doc that disagrees with the code, here
   and in PlunderSpell, PlunderSpell's folders are back to a size aj agrees is right, and nothing unsaved was deleted.
3. **Pick up on any of aj's four accounts** (15). Done when work started on one account is picked up on another,
   in the desktop app and in a cloud session.
4. **The command guard refuses only what can't be undone** (15). Done when a recorded day of real commands has no
   refusal of a recoverable action.
5. **Pages that fit the idea, show the work, and stay calm** (36). Done when a build plan shows its planned code
   and a picture, an idea that doesn't fit the template still gets a fitting page, and each page passes a
   calm-by-default check.
6. **Helpers you can follow, and that behave** (31). Done when a build with two helpers can be followed from a
   phone and no helper reruns a check it already ran.
7. **aj's credit everywhere, names configurable** (15). Done when a cloud pull request carries aj's credit and the
   GitHub check refuses one that doesn't.
8. **The plugin split, and faster hooks** (22). Done when the nine plugins install together on a fresh machine and
   every hook runs at least as fast as before.

**No new work** (38): already built, duplicated or replaced. **Other products** (17): #116 (Unity workflow), #161
to #164 and #167 to #171 (art-pipeline, on the branch `origin/claude/art-pipeline`), #180 (Focus Deck, belongs in
the focus-deck-app repo), #183 to #187 (Eldritch goose) and #334 (Unity docs layer).

**Where it stands (2026-11-09).** Approved. The eight phase issues are not opened yet and the 226 are not closed:
both wait on aj approving the GitHub issue command.
