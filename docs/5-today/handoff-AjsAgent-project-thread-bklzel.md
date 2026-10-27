# Handoff: usage limit handoff (2026-10-27)

**For.** Keep work saved and handed off on every reply, so a usage limit never strands it. Parent issue #406 (replaces #140); steps #407 to #410.

**Where it stands.** Paused on 2026-10-27 at aj's request. #406 is now a sub-issue of the restructure (#306), so its build plan is checked against restructure steps 3 to 7 (#381), which rewrite the same files, before anything is built. Design approved ("Design approved: usage limit handoff 1A 2A 3A"). The build plan page `docs/plans/2026-10-27-usage-limit-handoff-build-plan.html` lists every file each step changes and is not approved. No code changed.

**Next step.** The restructure work reviews this branch's plan pages, system doc `docs/4-systems/usage-handoff.md` and decision entry against its own plan, and folds them into the restructure branch. Nothing here is built until aj approves the reconciled build plan. The build order inside it stays #407 (save check), #408 (pickup), #409 (design-loop approval bugs in `design_loop.py` `_loop_name` and `core.py` `_RELAYED_PROMPT_RE`), #410 (rule text, docs, version, real cloud run, QA page).

**Unverified.** Whether the desktop app runs a status line; it was never connected to the thread. StopFailure at a real usage limit. Neither is relied on.

**Watch out.** The stage file `.claude/house-rules-loop.json` holds the feature as "usage limit handoff 1A 2A 3A</message>" (the #409 bug). Build plan approval doesn't compare names, so it still works.
