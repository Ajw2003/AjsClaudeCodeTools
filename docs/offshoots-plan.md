# Offshoots plan

Three new sibling plugins were scaffolded alongside `house-rules`, following the same formula
(one POSIX shim, one stdlib-only Python file dispatched by event, a `verify.py` that proves the
hook payloads produce the claimed decisions). This doc is the plan they were built against —
what each is for, the decisions already made and why, and what's still open.

## Why offshoots instead of extending `house-rules` itself

`house-rules` enforces a fixed rule set: no hidden background work, no unasked git mutations,
step-card handovers. It's opinionated about *how work gets done and handed back*. Both new
plugins below are about a different moment — *what the work should even be* — and bolting that
onto `house-rules`' hook table would mix two concerns that should be independently installable,
independently versioned, and independently disabled. The formula (shim + stdlib Python +
`verify.py` + fail-mode-per-event discipline) generalizes; the rule set doesn't have to.

## Offshoot 1: `prompt-workshop`

**The problem.** Most prompts arrive underspecified — a goal with no success criteria, no
stated constraints, no checkpoint before the model runs with an inferred reading of what was
actually wanted. Users often don't want to think through that nuance themselves; they'd rather
be walked through it than either (a) get a confidently-wrong result built on a guess, or (b)
have to learn prompt engineering to avoid that. This plugin exists to notice the gap and close
it *with* the user, briefly, at the start of a turn — structure, loops, and gating, the three
things a bare imperative sentence usually skips.

**Decisions made, and why:**

- **A `UserPromptSubmit` hook, not a mandatory pre-turn command.** The goal is "automatically
  walks the user through it," which means the check has to run on every prompt without the user
  remembering to invoke anything — the same reason `house-rules`' `scope` hook exists on that
  event. A hook can only *nudge* Claude via `additionalContext`; it cannot itself run a
  multi-turn Q&A, since hooks are stateless single-shot processes. So the hook's job is
  narrower than "run the workshop" — it's "notice this prompt looks like it needs the workshop,
  and tell Claude to run it," and the actual back-and-forth (via `AskUserQuestion`) happens in
  the turn that follows, driven by the injected instructions plus
  `rules/prompt-workshop.md`. This is the same shape `house-rules`' `delegate` hook uses to
  route an approved plan to `@house-rules:executor` — a hook steering Claude's next action,
  not performing the action itself.
- **A `/prompt-workshop:workshop` command exists too**, for the case the heuristic misses or
  the user wants the flow explicitly on a prompt that didn't trigger it. Automatic-by-default,
  explicit-by-request — the same pairing `house-rules` uses for `guard` (automatic) plus
  `/house-rules:doctor` (explicit, on demand).
- **The four dimensions — goal, constraints, success criteria, loops & gating** — are the
  structure the methodology doc (`rules/prompt-workshop.md`) organizes around, chosen because
  they map directly to the four things the task named: "proper structure, loops, and gating"
  plus the goal itself, which needs restating before anything else can be checked against it.
- **The trigger heuristic is deliberately crude (v0.1).** It flags a prompt that reads as a
  task (an imperative verb) and is short enough to plausibly have skipped two or more of
  {success criteria, constraints, gating} signal words. This is pattern-matching on raw prompt
  text — the same "stay broad within the extracted field, a false positive is cheap" posture
  `house-rules`' `guard` patterns use. It will both under- and over-trigger; that's an accepted
  v0.1 cost, not an oversight (see "Open questions" below).
- **Never blocks, never fails loud on the `UserPromptSubmit` path.** A non-zero exit on that
  event erases the user's prompt, so `event_workshop` mirrors `house-rules`' `scope`
  byte-for-byte on this point: every failure path recovers silently rather than reporting.

**What shipped in this pass:** `plugin.json`, `hooks.json` (`SessionStart` → `inject`,
`UserPromptSubmit` → `workshop`), `hook.py` with both handlers, `rules/prompt-workshop.md` (the
full methodology text), `commands/workshop.md`, a 22-case `verify.py`, and a README. This is
real, runnable v0.1 — not stub code — but the heuristic and the "did the refined prompt actually
get followed" question are both still open, see below.

## Offshoot 2: `agent-router`

Originally scaffolded as an unnamed placeholder (`offshoot-2`) while its purpose was still TBD.
The purpose since given: route each prompt to the model tier that fits its complexity — Haiku
for simple doc writing, Sonnet for recon and code implementation, Opus for planning,
architecture, and management — instead of running everything on whatever model the session
happens to be on. The placeholder was renamed in place (`claude-offshoot-2/` →
`claude-agent-router/`, `offshoot-2` → `agent-router`) rather than left to accumulate content
under its old name — its own README had already said to do exactly that once a purpose existed.

**The load-bearing correction, made before anything else here matters.** The ask was to have
"the plugin leverage hooks to route" — read literally, that could mean a hook switches which
model the live session runs on mid-turn. **No hook can do that.** `UserPromptSubmit` hooks emit
`additionalContext` or block the prompt; there is no hook output that changes a running
session's model. What genuinely is enforced, the same way `house-rules` already uses it for
`@house-rules:executor`, is a subagent's `model:` frontmatter — so "routing" here means: a hook
classifies the prompt and *suggests* Claude delegate to a subagent pinned to the right tier.
Claude decides whether to actually delegate. This is a real mechanism, not a workaround — it's
the same shape `house-rules`' `delegate` hook already uses (nudge toward a pinned subagent
rather than performing the work itself) — but it's a suggestion, not an enforced switch, and
that gap needed to be named rather than built over silently.

**Decisions made, and why:**

- **Three subagents, one per tier, each with only a `model:` pin as their real teeth** —
  `@agent-router:scribe` (haiku), `@agent-router:operative` (sonnet),
  `@agent-router:architect` (opus). `house-rules`' own `opusplan` + `@house-rules:executor` split
  is the two-tier version of this; `agent-router` generalizes it to three explicit tiers and
  makes the routing decision per-prompt instead of per-session.
- **`route` reads each agent's declared model live, off disk, every time it fires** — never a
  hardcoded model name in `hook.py` — the same "declaration read from the file it actually
  ships, not restated" discipline `house-rules`' `announce` handler uses for exactly this reason:
  a hook that hardcodes what a subagent declares can drift from what the subagent actually
  declares.
- **Classification precedence is architecture > doc > recon/code > silent.** An ambiguous prompt
  reading as either "just do it" or "decide how to do it" is resolved toward the stronger model —
  over-routing a simple ask to Opus costs more compute than it should; under-routing a real
  architecture decision to Sonnet risks a worse decision. The asymmetry in what a wrong guess
  costs picked the tie-breaker.
- **Doc-tier is noun-triggered (`readme`, `changelog`, `docstring`, ...), not verb-triggered.**
  A bare verb like "write" is ambiguous between "write the README" (doc) and "write a rate
  limiter" (implementation); the noun is the disambiguating signal, so doc-tier requires one.
- **Silent when the prompt already names `@agent-router:` or fits no tier at all** — a routing
  suggestion on top of an already-explicit delegation, or on a plain question, is noise the
  classifier should not add.
- **`route` never blocks, on the same contract as `prompt-workshop`'s `workshop` handler** — a
  non-zero exit on `UserPromptSubmit` erases the user's prompt, so every failure path in
  `event_route` recovers silently rather than reporting.

**What shipped in this pass:** `plugin.json`, `hooks.json` (`SessionStart` → `inject`,
`UserPromptSubmit` → `route`), `hook.py` with both handlers, `rules/agent-router.md` (the
methodology, including the surfaces table and the "what a hook can't do" section above in short
form), three agent files with real `model:` pins, `commands/route.md`, a 32-case `verify.py`
(including checks that each agent's declared model matches what the rules doc promises, and
that `route`'s suggestions read that declaration live rather than restating it), and a README
that opens with the same correction made above. Real, runnable v0.1 — not stub code — but see
"Open questions" for what a suggestion-only mechanism still can't guarantee.

## Offshoot 3: `issue-forge`

**The problem.** This repo's own documentation already reads like a backlog —
`docs/architecture-backlog.md` (7 open entries) and `docs/rules-backlog.md` (1 open entry) are
hand-maintained decision logs, one entry per candidate/decided change, and `docs/sessions/*.md`
session ledgers (from `tools/session_ledger.py`) flag actions a `Stop` hook continuation took
that the user never saw in the visible reply. Nothing in the repo turns any of that into a
GitHub issue a separate external tool of the user's could then read and auto-populate as tasks.
`session_ledger.py` already classifies GitHub issue-*write* MCP calls for audit purposes, but
nothing actually creates one.

**The load-bearing correction, made before anything else here matters.** This is the one offshoot
structurally different from its two siblings: `prompt-workshop` and `agent-router` only ever nudge
Claude via `additionalContext` — they never take an action with external, visible consequences.
Creating a GitHub issue is "publish/post public content" under the standing safety rules, which
needs explicit user permission in chat every time, not a general one-time approval. So the design
keeps the hook to *noticing and suggesting only*, and puts actual issue creation behind a
separate, always-confirmed step that no hook can reach — see `rules/issue-forge.md`'s hard rule.

**Decisions made, and why:**

- **Two sources, not one.** Per the user's own scoping answers: both the hand-maintained backlog
  logs *and* the session ledgers feed the scan, since both already read as a backlog of
  issue-worthy items, just in different shapes.
- **A `PostToolUse` hook on two matchers (`Edit|Write` and `Bash`), not `UserPromptSubmit`.** The
  trigger is "a relevant doc changed," which is a tool-use fact, not a prompt-shape fact — the
  same reason `house-rules`' `artifact`/`runnable`/`harvest` sit on `PostToolUse` rather than
  `UserPromptSubmit`. The `Bash` matcher exists only because ledgers are written by a plain Python
  script via `open()`, not through the `Write` tool, so file-path matching alone would miss a new
  ledger landing — `suggest` reads `command` and looks for `session_ledger.py` on that path.
- **The engine (`forge.py`) is a strict two-phase split, not a single command with a `--yes`
  flag.** Phase A (`--dry-run`) is read-only against GitHub (a `gh issue list --search` for
  dedup) and needs no confirmation; Phase B (`--create <slugs>`) is the only thing that posts,
  and is never invoked by the hook and never invoked by Claude without first showing the user the
  drafted list and getting an explicit, slug-named go-ahead in chat. The split is the mechanism
  that makes the confirmation rule true in code, not just a habit stated in prose.
- **Dedup via a marker embedded in the issue body (`<!-- issue-forge:source=<slug> -->`), not a
  local state file.** Consistent with this repo's existing bias against hidden state (`hook.py`
  keeps none, `versioncheck`'s marker is the one narrow exception) — there is nothing that can go
  stale independently of what GitHub actually has.
- **Backlog parsing matches the real file structure, not an invented one:** split each file on
  `\n## `, keep only sections containing a `**Status:** open` line — this is why a non-item
  section (`architecture-backlog.md`'s "Baseline" preamble) is skipped by construction rather
  than by a special case. Ledger parsing is one candidate *per ledger*, not per flagged row —
  the row-level detail belongs in the issue body, not in the candidate count.
- **Issue body is a generic structured template**, since the downstream tool's schema isn't known
  yet — Context / Why it matters / Proposed change / Source, plus the dedup marker as an HTML
  comment. Labels are always `source:<origin>`, and architecture-backlog items additionally carry
  whatever strength (`strong`/`worth-exploring`/`speculative`) is already authored into the doc —
  real signal already in the source, not invented.
- **General installable offshoot, not a repo-specific script.** The six-tier docs convention it
  reads (`house-rules:project-docs`) is itself a general convention, not unique to this repo, so
  `ISSUE_FORGE_BACKLOG_FILES` and `--sessions-dir` exist to point the engine at a different
  project's own backlog/ledger files.

**What shipped in this pass:** `plugin.json`, `hooks.json` (`SessionStart` → `inject`,
`PostToolUse` on `Edit|Write` and `Bash` → `suggest`), `hook.py` with both handlers,
`rules/issue-forge.md` (the methodology plus the hard confirmation rule), `commands/forge.md`,
`scripts/forge.py` (the scan/draft/create engine, stdlib-only), a 48-case `verify.py` covering
both hook contracts, backlog/ledger parsing against fixtures shaped like the real docs, and the
dedup/create logic against a stubbed `gh` (never the real CLI), and a README. Real, runnable
v0.1 — not stub code — confirmed against this repo's actual docs: a `--dry-run` run finds 9
candidates (7 architecture-backlog + 1 rules-backlog + 1 session-ledger, the one ledger that
exists today having 2 flagged rows), matching the counts read directly out of the tree while
planning this.

**Open questions.**

- The Context/Why-it-matters/Proposed-change extraction from each backlog entry is a simple
  labeled-paragraph heuristic (`**The friction.**`, `**Evidence.**`, `**What would change.**`, …)
  — it will produce an awkward draft on an entry whose prose doesn't use those exact labels. The
  Phase A review step is the intended backstop for this, not a claim that extraction is perfect.
- Nothing verifies a created issue's content stays in sync if the source backlog entry is edited
  or deleted afterward — the marker prevents a *duplicate*, not staleness.
- No coverage yet, by design, for anything that actually calls the real `gh` CLI end-to-end
  (issue creation against a live repo) — `verify.py` stops at the stubbed-runner boundary, the
  same documented limitation `tools/verify_tools.py` carries for real-CLI-shelling-out code; a
  real `--create` run against a throwaway test repo is a manual verification step, not part of
  the automated suite.

## Open questions (not resolved by this shell)

- **`prompt-workshop`'s heuristic needs real tuning data.** The verify suite's 8 cases are
  hand-picked, not drawn from real prompt traffic the way `house-rules`' guard patterns were
  refined against actual sessions. Whether the false-positive rate (workshopping a prompt that
  didn't need it) is tolerable in practice is unknown until it's used.
- **No way to verify the refined prompt was actually followed.** The hook can ask Claude to run
  the workshop flow; nothing checks that it did, or that the "refined version" it proceeded
  under matches what the user actually confirmed. `house-rules`' `SubagentStop`/`verdict`
  pattern (checking a *declaration* against *evidence* after the fact) is the template for
  closing this gap, if it's worth closing — it would mean a new hook event, most plausibly on
  `Stop`, verifying the turn's transcript mentions the workshop ran when the `UserPromptSubmit`
  hook flagged it.
- **`agent-router`'s classifier needs real tuning data**, for the same reason
  `prompt-workshop`'s does — the 12 cases in `verify.py` are hand-picked, not drawn from real
  prompt traffic.
- **Nothing verifies a routing suggestion was acted on, or that a delegated subagent actually
  ran on its declared model.** `route` can only suggest; whether Claude delegates, and whether
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` or similar quietly overrides the declared model if it does,
  is exactly the gap `house-rules`' `announce`/`verdict` pair closes for its own subagent
  (`executor`) — extending that pair to cover `agent-router`'s three agents (or having
  `agent-router` ship its own `SubagentStart`/`SubagentStop` handlers) is the template if this
  is worth closing, and is the most-open question either offshoot currently has.
- **No handling yet for a prompt that genuinely spans two tiers** (part doc fix, part redesign) —
  the classifier picks the highest-precedence tier that matches and says nothing about the mix,
  rather than flagging that the prompt should probably be split.
- **Surface reach is inherited, not new**, from the same limits `house-rules`' own CLAUDE.md
  documents — no plugin hooks in WSL sessions, and the Desktop Cowork tab sources skills from
  the claude.ai account rather than `~/.claude`. `agent-router` does nothing on either, same as
  if it weren't installed there.
