# Offshoot plugins: prompt-workshop and agent-router

## What it owns

Two sibling plugins, both `plugin.json` version `0.1.0` and both self-labeled `STATUS: shell /
v0.1`, that copy `house-rules`' formula (one POSIX shim, one stdlib-only `hook.py`, a `verify.py`
proving hook payloads produce the claimed decisions) toward a different moment — not "how work
gets done and handed back" (that's `house-rules`), but "what the work should even be":

- **`prompt-workshop`** notices a prompt that reads as an underspecified task and nudges Claude
  to run a goal/constraints/success-criteria/gating clarification pass with the user before
  proceeding on an inferred reading.
- **`agent-router`** classifies a prompt's complexity into one of three tiers and nudges Claude
  to delegate to the model-pinned subagent that fits: `@agent-router:scribe` (haiku, doc/comms),
  `@agent-router:operative` (sonnet, recon/implementation), `@agent-router:architect` (opus,
  planning/architecture/management).

If either is wrong, the cost is narrow by design: a missed or spurious nudge, never a blocked
prompt or a wrong model forced on the session — see Invariants for why that ceiling exists.

## How it works

Both follow `house-rules`' shape at roughly a tenth the size:

| Plugin | `hook.py` | `verify.py` | Checks (2026-09-15) |
|---|---|---|---|
| `prompt-workshop` | [202 lines](../../claude-prompt-workshop/plugins/prompt-workshop/scripts/hook.py) | [228 lines](../../claude-prompt-workshop/plugins/prompt-workshop/scripts/verify.py) | 22 PASS |
| `agent-router` | [248 lines](../../claude-agent-router/plugins/agent-router/scripts/hook.py) | [245 lines](../../claude-agent-router/plugins/agent-router/scripts/verify.py) | 41 PASS |

Each registers exactly two hooks: `SessionStart` → `inject` (prints its own methodology doc —
`rules/prompt-workshop.md` or `rules/agent-router.md` — into context) and `UserPromptSubmit` →
its own classifier (`workshop` or `route`), which pattern-matches the raw prompt text and, when a
case fits, emits `additionalContext` suggesting a next action. Neither can do more than suggest:
**no hook output can switch the model a running session is already on** — there is no
`$CLAUDE_MODEL` and no hook field that changes it. What actually pins a model is a subagent's own
`model:` frontmatter, the same mechanism `house-rules` uses for `@house-rules:executor`. So
"routing" here means classify-and-suggest; Claude still decides whether to delegate.

`agent-router`'s `route` handler reads each agent's declared model live off its
`agents/*.md` frontmatter every time it fires, rather than hardcoding a model name in `hook.py` —
the same "read the declaration from the file that actually ships" discipline `house-rules`'
`announce` handler uses, for the same reason: a hardcoded restatement can drift from what the
agent file actually declares.

Neither plugin is listed as an everyday-installable marketplace entry the way `house-rules` is
presented — both READMEs describe installing them the same way, once ready, via the three
`claude plugin` commands against this repo's marketplace.

## Invariants

- **Never blocks the prompt.** Both `workshop` and `route` run on `UserPromptSubmit`, where a
  non-zero exit erases the user's prompt before Claude ever sees it — the identical contract
  `house-rules`' `scope` handler has, and every failure path in both handlers recovers silently
  rather than reporting, on the same reasoning.
- **Silent when nothing clearly fits** — a routing suggestion on a prompt that already names
  `@agent-router:` explicitly, or on a plain question, would be noise the classifier should not
  add; both classifiers are built to say nothing rather than guess.
- **A subagent spawned this way carries no inherited context.** Subagent contexts don't receive
  the parent session's injected `additionalContext`, so each of `agent-router`'s three agents
  (`scribe`, `operative`, `architect`) carries its own short, self-contained digest rather than
  assuming `rules/agent-router.md` reached it.
- **`agent-router`'s recon-question regex is checked after the architecture regex, and kept
  separate from the general task-verb regex, on purpose.** `_RECON_QUESTION_RE`
  (`hook.py:124-131`) exists because "recon" — `operative`'s own stated job — naturally comes
  phrased as an inquiry ("why is this flaky") rather than an imperative ("investigate why this
  is flaky"); without a dedicated pattern the classifier missed exactly that phrasing. It's kept
  separate from the task-verb regex rather than folded in, so a bare "why"/"how" with no
  investigative shape stays cheap to reason about on its own. And it's checked after the
  architecture regex so a decision phrased as a question ("why should we consolidate these")
  still routes to `architect` — "should" is deliberately absent from the why-clause list so that
  case doesn't get claimed here first.

## Traps

- **Both classifiers are hand-picked-case pattern matching, not tuned on real prompt traffic.**
  `prompt-workshop`'s under-specification heuristic (task-verb present, short, missing 2+ of
  {success criteria, constraints, gating} signal words) and `agent-router`'s tier classifier were
  each verified against a dozen or so hand-picked cases in their own `verify.py`, not against
  real sessions the way `house-rules`' guard patterns were refined. Expect a real false-positive
  and false-negative rate neither author has measured yet — this is stated as an open question in
  [`docs/offshoots-plan.md`](../offshoots-plan.md), not a surprise to discover independently.
- **Nothing confirms a fired suggestion was acted on, or that a subagent it led to actually ran
  on its declared model.** `house-rules`' `announce`/`verdict` `SubagentStart`/`SubagentStop` pair
  closes exactly this gap for `@house-rules:executor`; neither offshoot ships the equivalent yet.
  A routed-to-`architect` delegation that silently ran on the parent's own model would currently
  go unnoticed.
- **No handling for a prompt that genuinely spans two of `agent-router`'s tiers** (part doc fix,
  part redesign) — the classifier picks the single highest-precedence tier that matches and says
  nothing about the mix.
- **Surface reach is inherited from `house-rules`, not independently verified**: no plugin hooks
  load in a WSL session, and the Desktop Cowork tab sources skills/plugins from the claude.ai
  account rather than `~/.claude` — both offshoots do nothing on either surface, same as if they
  weren't installed there.
