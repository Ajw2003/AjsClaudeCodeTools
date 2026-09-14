# agent-router

STATUS: shell / v0.1. A third offshoot of the `house-rules` formula in this repo, alongside
`prompt-workshop` — same one-shim-plus-one-Python-file plugin shape, same "nothing fails
silently on the paths that can speak" discipline. This one classifies each prompt's complexity
and nudges Claude toward the model-pinned subagent that fits, instead of running everything on
whatever model the session happens to be on.

See [docs/offshoots-plan.md](../docs/offshoots-plan.md) at the repo root for the plan this was
built against and what's still open.

## Read this before anything else: what a hook can and can't do

**This plugin cannot switch the model your Claude Code session is already running on.** There
is no hook output for that. What it *can* do is notice a prompt's shape and suggest delegating
it to a subagent whose `model:` frontmatter really is pinned — the same mechanism `house-rules`
uses for `@house-rules:executor`. Claude reads the suggestion and decides whether to delegate;
this plugin only ever nudges. Full explanation, including which surfaces this even reaches
(plugins don't load in WSL sessions or the Desktop Cowork tab), is in
[rules/agent-router.md](plugins/agent-router/rules/agent-router.md).

## What it actually does

Every hook, defined in
[plugins/agent-router/hooks/hooks.json](plugins/agent-router/hooks/hooks.json), runs
`sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <event>`, which resolves a working Python interpreter
and hands off to [scripts/hook.py](plugins/agent-router/scripts/hook.py):

| Hook event | When | What it does |
|---|---|---|
| `SessionStart` | every session | the `inject` handler prints [rules/agent-router.md](plugins/agent-router/rules/agent-router.md) — the routing methodology — into Claude's context. |
| `UserPromptSubmit` | before every prompt | the `route` handler classifies the prompt into one of three tiers (doc/comms, recon/implementation, planning-architecture-management) by pattern-matching the prompt text, and — if one fits clearly — suggests delegating to the matching subagent, naming that subagent's own declared model (read live from its `agents/*.md` frontmatter, never hardcoded). Never blocks; silent when no tier clearly fits. |

There is also [`/agent-router:route`](plugins/agent-router/commands/route.md) to run the same
classification on demand.

## The three subagents

| Agent | Model | For |
|---|---|---|
| [`@agent-router:scribe`](plugins/agent-router/agents/scribe.md) | `haiku` | Simple doc/comms writing — READMEs, changelogs, comments, docstrings, commit messages, wording fixes. |
| [`@agent-router:operative`](plugins/agent-router/agents/operative.md) | `sonnet` | Recon and implementation against a plan — the default tier for task-shaped prompts that aren't clearly doc or architecture work. |
| [`@agent-router:architect`](plugins/agent-router/agents/architect.md) | `opus` | Planning, architecture, and management-shaped work — design, tradeoffs, roadmaps, breaking work into a plan. |

None of them receive this plugin's `SessionStart` context — subagent contexts don't inherit the
parent session's injected `additionalContext` — so each carries its own short, self-contained
digest instead of assuming `rules/agent-router.md` reached it.

## What's deliberately still rough (v0.1)

- The classifier is keyword pattern-matching on raw prompt text, the same "stay broad within the
  extracted field, a false positive is cheap" posture `house-rules`' `guard` and
  `prompt-workshop`'s `workshop` handler use — not a tuned or learned classifier.
- Nothing enforces that Claude actually delegates on a fired suggestion, or that a subagent
  spawned this way actually ran on the model it declared — `house-rules`' `announce`/`verdict`
  pair is the template for closing that second gap if it's worth closing (see
  `docs/offshoots-plan.md`).
- No coverage yet for prompts that genuinely span two tiers (a request that's part doc fix, part
  redesign) — the classifier picks the highest tier that matches and says nothing about the mix.

## Running the test suite

```bash
python claude-agent-router/plugins/agent-router/scripts/verify.py
```

32 checks: the fail-open/fail-loud contracts, that each agent declares the model the rules doc
promises, that route's suggestions read that declaration live, a dozen representative
classification cases, and the hooks.json/EVENTS parity check.

## Installing it

Not yet published as an everyday-installable marketplace entry — listed in
`.claude-plugin/marketplace.json` at the repo root as `agent-router`. Install the same way
`house-rules` is:

```bash
claude plugin marketplace add ajw2003/ajsclaudecodetools
claude plugin marketplace update aj-house-rules
claude plugin install agent-router@aj-house-rules
```

`update` takes the marketplace's registered name (`aj-house-rules`, from `.claude-plugin/marketplace.json`'s
own `name` field), not the `owner/repo` shorthand `add` takes — the two commands don't share an
argument form. It matters on a machine that has already seen this marketplace: `add` alone
answers "already on disk" without re-fetching (see [`tools/install.py`](../tools/install.py)),
so `update` is the step that actually pulls the current commit before `install` registers the
plugin from it.
