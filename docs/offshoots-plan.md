# Offshoots plan

Two new sibling plugins were scaffolded alongside `house-rules`, following the same formula
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

## Offshoot 2: unnamed / undefined

The task named the second offshoot as TBD and asked for a shell regardless. What shipped is
exactly that: a plugin (`claude-offshoot-2/plugins/offshoot-2/`) with the same structural
pieces as the other two — `plugin.json`, `hooks.json` registering one `SessionStart` hook,
`run.sh`, a `hook.py` whose only handler announces "this is a placeholder" via `systemMessage`,
an empty `rules/` directory with a note explaining what goes there, and a `verify.py` proving
the placeholder announces itself correctly and never fails. It is wired into the root
`marketplace.json` and this repo's CI (`.github/workflows/verify.yml`) exactly like the other
two, so it's a real, checked artifact rather than dead scaffolding nobody will notice broke.

Nothing about its purpose was assumed. `claude-offshoot-2/README.md` spells out the four steps
to turn it into a real plugin once a purpose exists: write the rules doc, add handlers the way
`prompt-workshop` added `event_workshop` next to `event_inject`, register the new hook events,
extend `verify.py`, then rename it away from the `offshoot-2` placeholder name.

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
- **`offshoot-2`'s purpose.** Entirely open. The shell imposes no constraint on what it becomes.
- **Marketplace naming.** `offshoot-2` is a placeholder plugin name, not a shipped one — rename
  it (directory, `plugin.json`, the marketplace entry) once it has a real purpose, per its own
  README.
