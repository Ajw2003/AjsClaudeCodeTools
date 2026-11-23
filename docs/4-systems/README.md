# Systems

One document per runtime-critical system — the test applied was **if this is wrong, does the
product stop working?**, not "is it a folder." Each covers, in order: what it owns, how it
works, invariants, and traps that have already cost time.

| System | Owns |
|---|---|
| [hook-engine.md](hook-engine.md) | Dispatching every `house-rules` hook event to the handler that enforces it |
| [verify-suites.md](verify-suites.md) | Proving the three plugins' hook payloads produce the decisions the docs claim |
| [plugin-distribution.md](plugin-distribution.md) | Getting the plugins onto a machine, upgrading them, and the settings only a machine-level install can write |
| [guards.md](guards.md) | Which actions the hooks let through, refuse with the safe way named, or ask aj about |
| [roadblocks.md](roadblocks.md) | The rule that the agent checks a roadblock claim, installs what is missing and tries other routes, plus the end-of-reply check that enforces it. |
| [design-loop.md](design-loop.md) | Keeping design aj's job: the stages, the approvals that move them, and the lock on code outside Build |
| [label-setup.md](label-setup.md) | Making sure a repo has the three house labels before the plugin depends on them (planned) |
| [clear-writing.md](clear-writing.md) | Making what aj reads proper, human and explicit: the rule, the shared checker, the issue check and the editor helper |
| [plugin-restructure.md](plugin-restructure.md) | Reshaping house-rules into a shared core and six optional sub-plugins, and the 2.68.1 patch that ships first (planned) |
| [work-tracking.md](work-tracking.md) | Letting aj follow every layer of work a project thread delegates: transcript links and helper work trails |
| [audit-fixes.md](audit-fixes.md) | The six-step order for fixing the 45 findings of the 2026-11-05 audits (planned) |
| [flexible-pages.md](flexible-pages.md) | Letting a page take any format that meets seven basics, checked by `page_criteria.py` instead of refused for lacking the builder's mark |
| [wait-and-visual-checks.md](wait-and-visual-checks.md) | Giving every wait a clock and deadline, checking visual work with captures and an unattended loop, sending every made or changed page, and building pictures into the page (built, waiting on QA) |
| [offshoot-plugins.md](offshoot-plugins.md) | `prompt-workshop` and `agent-router` — the two v0.1 nudge plugins built on the same formula |

## Considered and deliberately left out

- **`tools/session_ledger.py`, `tools/measure_footprint.py`, `tools/sync_standards.py`** —
  real, working scripts, but diagnostic/reporting utilities rather than systems in this sense: if
  any of the three is wrong, no hook stops enforcing anything and no install stops working — a
  ledger goes unwritten, a footprint number is misreported, or a vendored standards doc goes
  stale. Their behavior is covered where it matters instead: `session_ledger.py` and
  `measure_footprint.py`'s decision logic is exercised by `tools/verify_tools.py`, discussed in
  [`plugin-distribution.md`](plugin-distribution.md); `sync_standards.py`'s role is one line in
  [`docs/architecture.md`](../architecture.md) under "Where things live, and why."
- **`docs/sessions/*`** — output *of* `session_ledger.py`, not a system. A per-session audit
  record, not code with invariants of its own.
- **A single combined "house-rules" system doc** — rejected in favor of splitting the hook engine
  from the suite that verifies it (`hook-engine.md` vs. `verify-suites.md`). They have different
  owners in the "what breaks if this is wrong" sense: a hook-engine defect changes what Claude
  Code actually does; a verify-suite defect changes only what anyone can *prove* about that,
  which is a materially different failure and reads better as its own document than as a second
  half of the first.
