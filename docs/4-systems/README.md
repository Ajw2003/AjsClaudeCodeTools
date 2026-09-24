# Systems

One document per runtime-critical system — the test applied was **if this is wrong, does the
product stop working?**, not "is it a folder." Each covers, in order: what it owns, how it
works, invariants, and traps that have already cost time.

| System | Owns |
|---|---|
| [hook-engine.md](hook-engine.md) | Dispatching every `house-rules` hook event to the handler that enforces it |
| [verify-suites.md](verify-suites.md) | Proving the three plugins' hook payloads produce the decisions the docs claim |
| [plugin-distribution.md](plugin-distribution.md) | Getting the plugins onto a machine, upgrading them, and the settings only a machine-level install can write |
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
