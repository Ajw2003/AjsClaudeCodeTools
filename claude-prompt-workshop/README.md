# prompt-workshop

STATUS: shell / v0.1. This is an offshoot of the `house-rules` formula in this repo — same
one-shim-plus-one-Python-file plugin shape, same "nothing fails silently on the paths that can
speak" discipline — aimed at a different problem: prompts arrive underspecified more often than
not, and guessing at the missing goal/constraints/success-criteria/gating and running with it
produces a *correct* answer to a goal nobody actually had.

See [docs/offshoots-plan.md](../docs/offshoots-plan.md) at the repo root for the plan this was
built against, what's a real decision here versus a stand-in, and what's still open.

## What it actually does

Every hook, defined in
[plugins/prompt-workshop/hooks/hooks.json](plugins/prompt-workshop/hooks/hooks.json), runs
`sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`, which resolves a working Python interpreter
and hands off to
[scripts/hook.py](plugins/prompt-workshop/scripts/hook.py), where both handlers live:

| Hook event | When | What it does |
|---|---|---|
| `SessionStart` | every session | the `inject` handler prints [rules/prompt-workshop.md](plugins/prompt-workshop/rules/prompt-workshop.md) — the workshop methodology — into Claude's context. |
| `UserPromptSubmit` | before every prompt | the `workshop` handler heuristically flags a prompt that reads as a task (an imperative verb) and is short enough to plausibly be missing constraints, success criteria, or a gating checkpoint, and reminds Claude to run the workshop flow — restate the goal, ask about the gaps with `AskUserQuestion`, propose a refined prompt, confirm, then proceed under that — before treating the literal text as the final spec. It never blocks the prompt; a false negative just means this plugin did nothing. |

There is also an explicit command,
[`/prompt-workshop:workshop`](plugins/prompt-workshop/commands/workshop.md), for running the
same flow on demand — the previous message, or text pasted alongside the command — when the
heuristic didn't fire but the user wants the flow anyway.

## What's deliberately still rough (v0.1)

- The under-specification heuristic in `hook.py` (task-verb present, short, missing 2+ of
  {success criteria, constraints, gating} signal words) is a first pass, not a tuned detector.
  It is pattern-matching on the raw prompt text, the same "stay broad within the extracted
  field" posture `house-rules`' `guard` uses — a false positive costs one clarifying round, a
  false negative costs nothing this plugin would otherwise have caught.
- No `SubagentStart`/`SubagentStop` visibility, no `standards`-style per-repo detection, no
  state carried between the workshop firing and the refined prompt actually being followed —
  the hook can only nudge at the start of a turn; it can't verify that Claude actually ran the
  flow it asked for.
- `scripts/verify.py` covers the two fail-open/fail-loud contracts and a handful of
  representative trigger/non-trigger prompts, not the scale of house-rules' guard suite.

## Running the test suite

```bash
python claude-prompt-workshop/plugins/prompt-workshop/scripts/verify.py
```

Same shape as `house-rules`' suite: numbered PASS/FAIL, a computed check count, exit 0 on
all-pass.

## Installing it

Not yet published to the marketplace as an installable entry a user would reach for day to day —
see `.claude-plugin/marketplace.json` at the repo root, where it's listed as
`prompt-workshop`. Install the same way `house-rules` is installed once you're ready to use it:

```bash
claude plugin marketplace add ajw2003/ajsclaudecodetools
claude plugin install prompt-workshop@aj-house-rules
```
