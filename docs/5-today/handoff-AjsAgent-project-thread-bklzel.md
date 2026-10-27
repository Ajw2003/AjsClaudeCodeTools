# Handoff: usage limit handoff (2026-10-27)

**For.** Keep work saved and handed off on every reply, so a usage limit never strands it. Parent issue #406 (replaces #140); steps #407 to #410.

**Where it stands.** Design approved ("Design approved: usage limit handoff 1A 2A 3A"). Plan stage: system doc `docs/4-systems/usage-handoff.md`, decision entry in `docs/6-decisions/Decisions.md`, issues #406 to #410 labelled `in progress`, and the build plan page `docs/plans/2026-10-27-usage-limit-handoff-build-plan.html`. No code changed yet.

**Next step.** Wait for aj's "Build plan approved: usage limit handoff". Then build #407 first (save check in `event_handover`, `scripts/hook.py`, beside `handover_commit_check` in `scripts/house_rules/safe_git.py`), writing its verify.py cases before the code. Then #408 (pickup at session start), #409 (design-loop approval bugs in `design_loop.py` `_loop_name` and `core.py` `_is_relayed_prompt`), and #410 (rule text, docs, version 2.75.0, real cloud run, QA page).

**Unverified.** Whether the desktop app runs a status line; it was never connected to the thread. StopFailure at a real usage limit. Neither is relied on.

**Watch out.** The stage file `.claude/house-rules-loop.json` holds the feature as "usage limit handoff 1A 2A 3A</message>" (the #409 bug). Build plan approval doesn't compare names, so it still works.
