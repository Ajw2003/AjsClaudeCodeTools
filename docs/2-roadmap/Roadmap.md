# Roadmap

What 0-100% means for each milestone, and what "done" is checked against. A milestone is done
when its acceptance criterion has actually been run and passed, not when the code exists.

## 1. The house-rules hook engine — 100%

Enforces aj's global CLAUDE.md rules as Claude Code hooks, on every device and every project,
without a per-repo file to copy around.

**Contains.** Eleven hook handlers dispatched from
[`hooks.json`](../claude-house-rules/plugins/house-rules/hooks/hooks.json) through
[`hook.py`](../claude-house-rules/plugins/house-rules/scripts/hook.py)'s `EVENTS` table —
`inject`, `standards`, `scope`, `guard`, `artifact`, `runnable`, `delegate`, `announce`,
`verdict`, `handover`, `harvest`. The `@house-rules:executor` subagent that the model-split rule
actually runs on. Full detail in [`docs/systems/hook-engine.md`](systems/hook-engine.md).

**Acceptance.** `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0.
**Checked 2026-09-15: 203/203 PASS.**

## 2. The six-tier documentation convention — 100% as a mechanism

`house-rules:project-docs` defines the tier structure this very file is part of, and the plugin
routes rationale/post-mortems into `docs/Decisions.md` rather than into a tier-4 system doc.

**Contains.** The `house-rules:project-docs` skill, the tier list and card format in
`rules/house-rules.md`, `hook.py`'s `harvest`/archivist routing to `docs/Decisions.md`, and
`verify.py`'s tiered-docs drift checks (the rule names the skill, the skill specifies all six
tiers, the routing text agrees in both directions).

**Acceptance.** The tiered-docs checks inside `house-rules`' `verify.py` pass (they're part of
the 203 above, checked 2026-09-15). This criterion is about the **mechanism** — a repo *can*
adopt the six tiers and the plugin routes correctly if it does. Whether *this* repo's own
`docs/` actually instantiates all six is tracked separately, in
[`ProjectState.md`](ProjectState.md), because "the mechanism works" and "every repo has adopted
it" are different claims — the second was explicitly deferred as its own follow-up in
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](archive/2026-09-15-sixth-documentation-tier.md).

## 3. Offshoot plugins (`prompt-workshop`, `agent-router`) — 50%

Two v0.1 shells copying the `house-rules` formula toward "what should the work even be" instead
of "how should it be handed back." Both plugin.json versions read `0.1.0`.

**Contains.** `prompt-workshop`'s under-specification nudge and `agent-router`'s three-tier
model-routing nudge, each a full shim+hook.py+verify.py+agents set, not stub code. Detail in
[`docs/systems/offshoot-plugins.md`](systems/offshoot-plugins.md).

**Acceptance, split because the mechanism and the judgment quality are different claims:**

- *Mechanism ships and verifies* — `prompt-workshop`'s and `agent-router`'s `verify.py` both
  exit 0. **Checked 2026-09-15: 22/22 and 41/41 PASS.** Done.
- *The classifiers are good enough to trust unattended* — **not done, and not yet measurable.**
  Both heuristics were verified only against hand-picked cases in their own suites, never against
  real prompt traffic; neither ships `SubagentStart`/`SubagentStop` visibility to confirm a
  suggestion was acted on or that a routed subagent ran on its declared model. These are named as
  open questions by the plan that built them
  ([`docs/offshoots-plan.md`](offshoots-plan.md#open-questions-not-resolved-by-this-shell)), not
  newly discovered here.

50% reflects "the mechanism is real and passes its own tests" against "the actual value
proposition — good routing — is unvalidated," weighted roughly even.

## 4. Distribution & install tooling — 100%

Getting all three plugins onto a machine, upgrading an existing install without stranding it on
an old version, and writing the two settings only a machine-level install can write.

**Contains.** `tools/install.py`'s four-command `install_steps()`, `bootstrap.ps1`/`bootstrap.sh`,
`tools/update.bat`, `tools/clean_install_test.py`, and `tools/verify_tools.py`. Detail in
[`docs/systems/plugin-distribution.md`](systems/plugin-distribution.md).

**Acceptance.** `python tools/verify_tools.py` exits 0 — **checked 2026-09-15: 32/32 PASS.**
Additionally, per prior recorded verification on this machine, the real `bootstrap`/`plugin
update` command sequence has actually been run against the live `claude` CLI on this device (not
just its decision logic in isolation) — the higher bar `clean_install_test.py` exists for. Not
re-run as part of writing this roadmap; see [`ProjectState.md`](ProjectState.md) for what that
means for how fresh this claim is.
