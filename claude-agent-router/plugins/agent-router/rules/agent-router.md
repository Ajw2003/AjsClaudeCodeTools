# Agent Router

STATUS: v0.1 draft. This is the methodology text the `inject` hook loads at `SessionStart` and
the text `route` points at when it flags a prompt. Read the "What a hook can actually do here"
section before assuming this changes the running session's model — it doesn't, and being clear
about that is the point of this document.

## The idea

Not every prompt deserves the same model. Fixing a typo in a README doesn't need the same
thinking budget as deciding whether to rewrite the auth layer. Asked to do both on the same
session, on the same model, either the doc fix costs more than it should or the architecture
call gets less thought than it needs. This plugin's job is to look at each prompt and say which
tier of work it is — so the *right* amount of model gets spent, not the same amount every time.

## The three tiers

1. **Doc / comms** (`haiku`) — writing or editing prose where the content is already decided or
   trivial to decide: README updates, changelog entries, commit messages, code comments,
   formatting fixes, straightforward renames, docstrings. Low ambiguity, low stakes if wrong,
   cheap to redo.
2. **Recon & implementation** (`sonnet`) — the bulk of engineering work: searching/reading a
   codebase to understand it, writing or fixing code against a plan that's already been decided,
   debugging, running tests. Real judgment, bounded scope, the plan (if one exists) does the
   hard thinking already. Recon in particular is as often a *question* as an instruction — "why
   is this test flaky", "how does the auth flow work across these services" — and routes here
   the same as an imperative "investigate why..." would; see "When to stay silent" below for the
   line between this and a quick contextual question that shouldn't be routed at all.
3. **Planning, architecture & management** (`opus`) — deciding what to build and why: system
   design, weighing tradeoffs, roadmaps, cross-cutting migrations, anything where getting the
   *framing* wrong costs more than getting an implementation detail wrong. "Management" here
   means orchestration-shaped work too — breaking a large ask into a plan, deciding what to
   delegate to what, prioritizing across competing asks — not literally managing people.

These map to the same split `house-rules` already uses for its own model routing (its
`opusplan` setting plus `@house-rules:executor` pinned to Sonnet) — this plugin generalizes that
split into three explicit tiers instead of two, and makes the routing decision per-prompt
instead of per-session.

## What a hook can actually do here

A `UserPromptSubmit` hook cannot switch the model the current session is running on — there is
no hook output for "run the rest of this turn on a different model." What it *can* do is inject
`additionalContext` that Claude reads before acting, and Claude can act on that by delegating the
prompt to a subagent — and a subagent's `model:` frontmatter **is** a real, enforced pin (the
same mechanism `house-rules`' `@house-rules:executor` uses). So "routing" here concretely means:

1. The `route` hook classifies the prompt and names which of the three subagents below fits.
2. It reads that subagent's own `agents/*.md` frontmatter at the moment it fires — never a
   hardcoded model name in `hook.py` — so the suggestion always matches what's actually shipped,
   the same "declaration, read out of the file, not restated" discipline `house-rules`' `announce`
   handler uses.
3. Claude decides whether to delegate. A false positive costs one skippable suggestion; a false
   negative just means the prompt runs on whatever model the session is already on, which is the
   safe direction to fail in — no worse than not having this plugin at all.

**This plugin never changes what model the top-level conversation defaults to.** That's still a
`/model` command or a `~/.claude/settings.json` `model` setting, entirely outside a plugin's
reach - see `house-rules`' own docs/architecture.md on why `opusplan` alone isn't enough and a
subagent is the mechanism that actually works. If the session is already running on the tier a
prompt needs (an Opus session doing architecture work, say), the router should say nothing —
delegating to a same-tier subagent would add overhead for no benefit.

## The subagents

- `@agent-router:scribe` — `model: haiku`. Simple, low-ambiguity writing.
- `@agent-router:operative` — `model: sonnet`. Recon and implementation against a plan.
- `@agent-router:architect` — `model: opus`. Planning, architecture, and management-shaped work.

None of these have this plugin's `SessionStart` context — subagent contexts don't inherit the
parent session's injected `additionalContext` (the same fact `house-rules`' `executor.md`
documents about itself). Each agent file below carries its own short, self-contained digest of
what it needs to know instead of assuming this document reached it.

## Which surfaces this actually reaches

Same caveat `house-rules`' CLAUDE.md documents for its own hooks — plugins don't load
everywhere, so neither does routing:

| Surface | Hooks load? | Routing works? |
|---|---|---|
| Claude Code — CLI | yes | yes |
| Claude Code — IDE extension | yes (inherits the CLI) | yes |
| Claude Code — Desktop **Code** tab | yes | yes |
| Claude Code — web / cloud session | ships with the repo install | yes, if the plugin is installed there |
| Claude Code — WSL session | **no** | **no — plugins are unavailable in WSL entirely** |
| Claude Code — Desktop **Cowork** tab | sources skills/plugins from the claude.ai account, not `~/.claude` | **no**, unless separately installed for that account |
| claude.ai chat (web/desktop/mobile) | no plugin hooks at all | **no** — this is a Claude Code plugin, not a claude.ai feature |

Where hooks don't load, this plugin does nothing — not "routes incorrectly," just absent. The
session runs on whatever model it's already on, same as if this plugin weren't installed.

## When to stay silent

Not every question is a routing candidate, but "it's phrased as a question" isn't the test — an
investigative question ("why is this test flaky", "how does the auth flow work") is recon work
and routes to `operative` the same as an imperative version would. What should get no routing
suggestion at all: a quick contextual question that depends on the conversation so far ("what
does *this* do", pointing at something just discussed), a reply to something Claude just asked,
a one-line confirmation, or a prompt that already names which agent/model to use. The distinction
is whether delegating would lose context the question actually depends on, not whether a
question mark is present — a subagent doesn't inherit this conversation, so a question that
only makes sense *within* it should stay here rather than being routed away from the context it
needs. Routing every message would still be noise regardless; the point is to catch prompts —
question-shaped or not — whose tier is clear and self-contained enough to name.

## What this is not

- Not a guarantee — the classification is heuristic pattern-matching on prompt text, the same
  "stay broad within the extracted field" posture `house-rules`' `guard` and `prompt-workshop`'s
  `workshop` handler use. See `docs/offshoots-plan.md` at the repo root for what's still open.
- Not a cost-control mechanism by itself — it's a suggestion Claude can ignore. Enforcing tier
  boundaries (never letting a doc fix run on Opus) would need something stronger than a hook,
  and isn't what this ships.
- Not a replacement for `house-rules`' own `delegate` hook, which is about handing an *approved
  plan* to an executor once planning is done. This plugin routes *before* any plan exists, by
  the shape of the raw prompt.
