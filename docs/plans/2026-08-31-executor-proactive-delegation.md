# Fix: executor delegation doesn't survive the Agent tool's "explicit ask" gate

## Context

Observed live in a new Auto-mode Desktop session: a plan was approved (`ExitPlanMode` fired,
`delegate.sh` injected its "delegate to `@house-rules:executor`" nudge), then the user typed a
generic `implement the plan`. Claude's own visible reasoning explicitly noted the conflict —
"house rules suggest delegating... but the system prompt explicitly forbids calling the Agent
tool unless the user requested it, and that delegation trigger didn't actually happen" — and
implemented the plan itself on the planning model, defeating the entire point of the
`opusplan`/executor split documented in [CLAUDE.md](../../CLAUDE.md) ("the primary mechanism, not the
fallback").

The root cause is precise, not a vibe: the harness's Agent-tool system prompt gates autonomous
spawning behind two things — the user explicitly asking, **or** the target agent's own
`description` field saying it should be used proactively ("If the agent description mentions
that it should be used proactively, then you should try your best to use it without the user
having to ask for it first"). Confirmed by reading every relevant file: the word "proactively"
(or any synonym) appeared nowhere in this repository before this change — not in
`agents/executor.md`'s description, not in `delegate.sh`'s injected message, not in
`house-rules.md`. So `delegate.sh`'s nudge was a plain directive with no way to satisfy the
harness's own gate, and a generic instruction like "implement the plan" gave Claude nothing that
counted as the user "explicitly" naming the subagent. The nudge fired, and still lost.

`verify.sh` proved the hook *emits* the right text and is *wired* to the right event, and that
the agent is *pinned* to Sonnet — but nothing checked that the description actually satisfies the
harness's proactive-use trigger, so this exact gap shipped invisibly.

## Approach

Close the gap at its actual location — the agent's `description` field — and make the
supporting text consistent with that fix.

1. **`agents/executor.md`** — description now reads: "Runs an already-decided plan. Use
   PROACTIVELY the moment a plan is approved (after ExitPlanMode) or when asked to
   implement/execute/build it out - delegate here without waiting to be asked by name, so
   implementation runs on Sonnet at low effort instead of re-deliberating on Opus. Skip only for
   a true one-liner where delegating costs more than it saves." This is the actual fix — it's the
   literal word the harness's Agent-tool instructions check for.
2. **`scripts/delegate.sh`** — the injected `NOTE` now names *why* the delegation is authorized
   ("Its agent description is marked for proactive use, which is the harness's own documented
   basis for invoking a subagent without a fresh per-turn ask..."), not just asserts it. Kept the
   `@house-rules:executor` and `plan is settled` substrings intact for `verify.sh`'s drift check.
3. **`rules/house-rules.md`** ("Once the plan is settled, delegate execution" section) — added a
   paragraph stating the Agent tool's gate explicitly and that the executor's description is
   written to satisfy it.
4. **`scripts/verify.sh`** — new check right after the existing "executor subagent is pinned to
   Sonnet" block: asserts `agents/executor.md`'s description contains "proactiv"
   (case-insensitive). This is the check that would have caught the original gap.
5. **`CLAUDE.md`** ("One subagent, for the model split" section) — added a paragraph documenting
   the harness-level Agent-tool gate itself and the live-session failure this fixes, matching the
   section's existing style of explaining design choices via the failure that motivated them.

## Verification

Ran the full suite — all 66 checks passed, including the new check #64 ("the executor
description authorizes proactive use"):

```
sh claude-house-rules/plugins/house-rules/scripts/verify.sh
```

Confirmed the new check actually catches the regression it targets: temporarily reverted just
the `executor.md` description change and re-ran the suite — check #64 failed as expected
("agents/executor.md description has no 'proactively' (or similar) wording") — then restored the
fix and re-ran; all 66 passed again.

No end-to-end way exists to re-run the exact harness gate that failed originally (that's the
assistant's own system-prompt reasoning at runtime, outside this repo's control) — the closest
available proof is `verify.sh` passing plus confirming the new description literally contains the
word the harness's Agent-tool instructions look for.
