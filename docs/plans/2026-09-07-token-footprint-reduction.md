# Reduce house-rules' token footprint without cutting functionality

## Context

The usage panel reports four things: 78% of usage was at >150k context, 33% came from
subagent-heavy sessions, 16% from subagents under `house-rules:executor`, and 16% from the
`house-rules` plugin itself. Those are independent characteristics, not a breakdown, so they
overlap — but three of the four point at this plugin.

Measured, not estimated, on this repo:

| Source | Bytes | ≈ tokens | When |
|---|---|---|---|
| `inject` — `rules/house-rules.md` | 20,806 | ~5,200 | once per session |
| `inject` — `rules/environment.md` | 4,861 | ~1,200 | once per session |
| `standards` — `coding-philosophy.md` | 3,722 | ~930 | once per session |
| repo `CLAUDE.md` (auto-loaded) | 23,075 | ~5,800 | once per session |
| `output-styles/handover-cards.md` | 2,841 | ~710 | once per session |
| **Fixed total** | | **~13,800** | before the first word |
| `scope` reminder | 1,435 | **~360** | **every user prompt** |

The fixed ~13,800 sits at the front of the context and lands in the cached prefix, so it is
paid at full rate once and at ~10% thereafter. It is large but it is not what drives the >150k
figure.

`scope` is what drives it. It is appended at the tail of every prompt, so it never caches away
and it accumulates: a 60-turn session carries ~21,600 tokens of restated rules, and every one
of those tokens is re-read on every subsequent request. That is the compounding cost and the
single largest lever.

The second finding is duplication: 8,051 chars — **38.7% of `house-rules.md`** — is the
handover/card format, and the forced output style states the same format in the system prompt
every session.

The intended outcome is a materially smaller per-prompt and per-session footprint with every
rule still enforced and every "Why:" block intact — the user chose to keep all rationale, on
the grounds that it is only ~760 tokens, sits in the cached prefix, and is what lets a rule
survive an edge case instead of being applied literally and wrongly.

## Constraints that shape the work

- **`scope` runs on `UserPromptSubmit`, where a non-zero exit erases the user's prompt.** This
  is why the handler is currently one fixed string with no file read and no logic. Any
  conditionality added must be wrapped so that every failure path emits the safe short string
  or nothing at all, and never raises. This constraint is documented in `CLAUDE.md` and is not
  negotiable.
- **`verify.py` pins the card format into `house-rules.md`** (lines ~698–712): exactly one
  `#### The card` heading, the literal `6. **One numbered step per action**`, and the phrase
  `never inside it`. The card section can be *compressed* but not *removed* without a
  deliberate change to those checks.
- **`verify.py` checks `scope` for drift** (lines ~379–399) — each line of the reminder must
  still appear in `house-rules.md`. Trimming the reminder is safe; rewording it is not, unless
  the rules document is reworded to match.
- **No hook keeps state between invocations.** Any conditional firing must be stateless —
  derived from the payload, the way `handover` gates on a fence in `last_assistant_message`.
- Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` after each lever. It is
  the source of truth for whether a change took effect.

## Lever 1 — cut the per-prompt `scope` cost (largest win)

**File:** `claude-house-rules/plugins/house-rules/scripts/hook.py`, the `SCOPE_REMINDER`
constant (~lines 405–422) and `event_scope` (~line 426).

Two changes, both stateless:

1. **Shorten the string.** The current reminder restates nine rules in full sentences, several
   of them near-verbatim from `house-rules.md` — which is already in context. Reduce to a
   terse pointer plus the rules that genuinely decay over a long session (handover format,
   ask-don't-assume, no unrun commands). Target ~400 chars, down from 1,435 — about **260
   tokens saved per prompt**.

2. **Gate the long form on prompt content.** Follow the `handover` precedent: emit the full
   reminder only when the incoming prompt suggests commands, files or builds are involved
   (the payload's `prompt` field), and the short pointer otherwise. Wrap the entire check in
   `try/except` that falls back to emitting the short form — never an exception, never a
   non-zero exit.

Update the `SCOPE_REMINDER` drift check in `verify.py` to match the new phrasing, and add a
case asserting the handler still exits 0 and emits the short form when the payload has no
`prompt` field at all.

## Lever 2 — remove the card-format duplication

**Test first, edit second.** The open question is whether `SessionStart` `additionalContext`
reaches a subagent. `agents/executor.md` asserts it does ("The house rules are already in this
session's context. Do not restate them."). If that assertion is false, two things are true at
once: the executor has been running without the rules, and the main session is paying for the
card format twice.

1. Spawn `@house-rules:executor` with a trivial task that asks it to report whether the house
   rules are present in its context, and to quote the first rule heading.
2. **If the rules do reach it:** the card section in `house-rules.md` is load-bearing for
   subagents and cannot be deleted. Compress it instead — the 8,051-char section can lose its
   worked prose without losing the six items. Keep the `#### The card` heading, item 6, and
   `never inside it` so `verify.py` stays green. Target ~4,000 chars.
3. **If the rules do not reach it:** that is a real defect, and the fix is separate from this
   one — `executor.md` must carry a rules digest itself, and its "already in this session's
   context" line is wrong and must go. Record the finding, fix the agent, then compress the
   card section as in step 2.

Either way the outcome is a smaller `house-rules.md`; the test decides whether the executor
also needs repair. **Files:** `rules/house-rules.md`, possibly `agents/executor.md`.

## Lever 3 — trim this repo's `CLAUDE.md`

**File:** `CLAUDE.md` (23,075 bytes, auto-loaded every session in this repo).

This is repo-local, not a plugin-wide win, but it is the second-largest single file in the
session prefix. Most of its bulk is architecture *rationale* — why the shim exists, why the
output style was forced and then reversed, why the state machinery was removed. That is
valuable to a human reading the repo and rarely load-bearing for a session doing work in it.

Move the long-form rationale into `docs/architecture.md`, leaving `CLAUDE.md` with: what the
repo is, the commands, the hook table (which `verify.py` checks against `hooks.json`), the
design constraints that actually govern edits, and pointers into `docs/`. Target ~10,000 bytes.

`verify.py` reads `CLAUDE.md` for several checks — the hook-event table, the surface table
cross-referenced against `docs/desktop-verification.md`, the rules-duplication check and the
card-template-duplication check. **Every one of those sections must stay in `CLAUDE.md`**; only
narrative prose moves. Run the suite to confirm.

## Lever 4 — tighten executor delegation

**File:** `claude-house-rules/plugins/house-rules/scripts/hook.py`, the `delegate` handler
(~line 669) and its reminder string.

`executor` is already `model: sonnet` at `effort: low`, so the per-token rate is as low as it
goes. The waste is cold start — the subagent re-explores what the main session already knows —
and over-firing, since the handler fires on every `ExitPlanMode` regardless of plan size.

1. **Pass the plan file path.** In plan mode a plan file already exists on disk. Have the
   reminder instruct that the delegation include that path, so the executor reads the plan
   instead of re-deriving it. The path is available in the `ExitPlanMode` payload — confirm the
   field name against a real payload before relying on it, and fall back to the current
   wording if it is absent.
2. **Strengthen the trivial-work exception.** The reminder already mentions "trivial"
   (`verify.py` asserts the word is present). Sharpen it into an actionable threshold — a plan
   whose steps touch one file, or that is shorter than a handful of steps, is cheaper to do
   inline than to hand over.

Keep the `@house-rules:executor` name and the word `trivial` in the emitted text; `verify.py`
checks for both.

## Order of execution

**Step 0:** copy this plan into the repo as `docs/plans/token-footprint-reduction.md`. Plan mode
confines edits to `~/.claude/plans/`, which is outside the project and untracked — the house
rules require plans to live in the repo as real files, so this is the first action once plan
mode exits.

Then sequential, verifying after each — the levers touch overlapping files and a combined failure
would be hard to attribute.

1. Lever 1 (`scope`) — largest win, smallest blast radius.
2. Lever 2 (duplication) — begins with the subagent test, which may surface a separate defect.
3. Lever 4 (delegation) — same file as Lever 1, done after it settles.
4. Lever 3 (`CLAUDE.md`) — largest diff, touches the most `verify.py` checks, and is
   repo-local so it gains nothing on other machines.

## Verification

After **each** lever, from the repo root in PowerShell:

```powershell
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Exit code 0 and every line reading PASS. The suite computes its own check count, so a changed
total is expected where a lever adds cases; a FAIL line names the case, expected and actual.

Additional checks beyond the suite:

- **Lever 1:** feed `hook.py` a `scope` payload with a command-shaped prompt and one without,
  and confirm the two emitted strings differ and both exit 0. Then feed it a payload with no
  `prompt` key and confirm it still exits 0 — this is the path that would erase a user's prompt
  if it regressed.
- **Lever 2:** the subagent probe described above, run before any edit; record its actual
  answer in the commit body, since it settles a question `CLAUDE.md` currently only asserts.
- **Lever 3:** `python tools/clean_install_test.py --skip-strip` to confirm the installed copy
  still matches the repo after the docs move.
- **End to end:** start a fresh session in this repo and confirm the rules still inject, the
  standards still inject, and a handed-over command still arrives as a step card. Measure the
  new session-start footprint against the ~13,800-token baseline above and record the delta.
