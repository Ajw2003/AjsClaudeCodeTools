# Prompt Workshop

STATUS: v0.1 draft. This is the methodology text the `inject` hook loads at `SessionStart` and
the text `workshop` points at when it flags a prompt. The heuristics in `hook.py` that decide
*when* to run this flow are cruder than the flow itself right now — see
`docs/offshoots-plan.md` at the repo root for what's still open.

## Why this exists

Most prompts arrive underspecified: a goal with no success criteria, no stated constraints, no
checkpoint before the model runs off and builds the wrong thing. The default failure mode isn't
a bad answer to the literal prompt — it's a *correct* answer to a goal nobody actually had,
because "make it better" and "add auth" and "fix the flaky test" all compress away the nuance
the user didn't feel like typing out. Guessing that nuance and running with it is how a session
ends with the right amount of effort spent on the wrong outcome. Making the user learn prompt
engineering to avoid this is the other failure mode. This plugin's job is to notice the gap and
close it *with* the user, briefly, before work starts.

## The four dimensions of a workshopped prompt

1. **Goal.** The actual outcome wanted, in the user's terms — not the first literal reading of
   the sentence. "Fix the login bug" might mean "make this one repro pass" or "audit the whole
   auth flow"; those are different amounts of work with different risk.
2. **Constraints.** Scope boundaries, non-negotiables, things explicitly out of bounds — a file
   that must not change, a dependency that can't be added, a deadline that rules out a rewrite.
3. **Success criteria.** How the user (or Claude) will know the result is right. Turn vague asks
   ("make it better", "clean this up") into checkable ones: passes the existing tests, under N
   lines, matches an existing pattern elsewhere in the repo, a specific before/after behavior.
4. **Loops & gating.** Where the user wants to check in before the model proceeds further — after
   a plan, after a first draft, before anything destructive or hard to reverse. Not every task
   needs a gate. Asking whether it does is the point; assuming either answer is not.

These are the same four things a careful human would ask about before starting unfamiliar work.
The workshop just makes asking the default instead of the exception.

## When to run the workshop

Trigger on a prompt that reads as a task (an imperative verb — build, fix, add, refactor,
write, design, improve...) and is short enough that it plausibly skipped two or more of the
four dimensions above. The `workshop` hook (`UserPromptSubmit`) flags these heuristically and
hands Claude a reminder to run the flow below *before* treating the literal prompt as the final
spec — it never blocks the prompt itself, only asks Claude to pause and check first. A prompt
that already reads as fully specified (states scope, a done condition, or an explicit go-ahead)
should never be stopped for this — over-triggering here costs the user a round of pointless
questions, which is exactly the friction this plugin exists to avoid, not add.

## The flow

Run this as a short back-and-forth (use `AskUserQuestion` where the harness offers it), never as
a wall of text the user has to parse on their own:

1. **Restate the literal prompt** back in one plain sentence — "the goal I'm reading is ___" —
   so a wrong inference is visible and correctable immediately, before any question is asked.
2. **Ask only about the gaps.** 1–3 targeted questions covering whichever of goal / constraints /
   success criteria / gating are missing or ambiguous. Not all four, every time — only what's
   actually unclear. A prompt that already states its constraints doesn't need to be asked about
   constraints again.
3. **Propose the refined prompt back** as a short structured summary — goal, constraints, success
   criteria, checkpoints — and confirm before proceeding. This is the artifact the workshop
   produces: a version of the ask the user can correct in one glance, not a transcript to reread.
4. **Proceed under the refined version**, not the original literal one. The original prompt was
   the input to this process, not the spec for the work.

## What this is not

- Not a form to fill out for every prompt. A prompt that's already clear and scoped should never
  be stopped for workshopping — that's the false-positive cost, and it's the one to protect
  against, since it's paid on every well-formed request.
- Not a substitute for `house-rules`' step-card handover or its own gating rules. This plugin
  governs how the *task itself* gets defined at the start of a turn; house-rules governs how
  *results* get handed back at the end of one. They compose; neither replaces the other.
- Not a guarantee — the heuristics that decide when to fire are pattern-matching on the prompt
  text, the same "stay broad within the extracted field" posture house-rules' `guard` uses. A
  false negative here just means the workshop didn't fire and the model proceeds as it would
  without this plugin at all; that's the safe direction to fail in.
