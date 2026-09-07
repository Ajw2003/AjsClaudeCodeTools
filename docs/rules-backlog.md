# Rules backlog

Rule changes that are decided but not yet written into
[`rules/house-rules.md`](../claude-house-rules/plugins/house-rules/rules/house-rules.md).

This file exists so a decision made mid-task has somewhere to land that is neither "implement it
right now, off-scope" nor "mention it in chat and lose it". An entry here is a commitment, not an
idea: it names the defect, the evidence, and what the rule should say. When one ships, delete the
entry — the rules document is the record, this is only the queue.

---

## Vague statements and instructions

**Status:** open. Raised 2026-09-07.

**The defect.** Handing over an instruction whose wording cannot be acted on the same way twice.
`docs/desktop-verification.md` shipped six of them — "ask for a multi-step handover", "same
five-step ask" — as the *entire* input to a verification step. Each run produces a different card,
so no two runs can disagree, and nothing is actually being tested. The step reads like a test and
is not one.

This is the same failure as a bare command block, one level up: a command block with no shell and
no working directory cannot be run, and an instruction with no fixed input cannot be *compared*.
The six-item contract already forbids the first and says nothing about the second.

**Evidence.** §6 asked for "a multi-step handover" with no prompt text and no expected answer. It
was unrunnable as written — caught by the user, not by any check. Fixed in the checklist by
defining `PROMPT-MULTI` / `PROMPT-ONE` / `PROMPT-LONG` verbatim, plus a recorded baseline card for
`PROMPT-MULTI` to compare later runs against.

**What the rule should say.** Roughly: an instruction the user is meant to *act on* names the exact
input, not a category of input — the literal prompt, the literal file, the literal value. Where the
point is comparing two runs, the expected result is recorded too, so a later run can disagree with
an earlier one. "Ask for something like X" is a description of a test, not a test.

**Open questions before writing it.**

- Does this belong in the six-item contract or as its own rule? The placement lesson from 2.9.0
  says a rule that must change the draft belongs in the six — but the six are specifically about
  *shell commands handed over*, and this is broader. Widening the six risks diluting them.
- Can `verify.py` check it at all? The existing drift checks match fixed strings; "is this
  instruction specific enough" is not a string match. It may be a rule with no test, which the repo
  has so far avoided shipping.

---

## Unexplained abbreviations

**Status:** open. Raised 2026-09-07.

**The defect.** Using an abbreviation the user has not seen defined, in an instruction they are
meant to act on. `docs/desktop-verification.md` §9 said "switch the environment dropdown to WSL"
with no expansion anywhere in the repo — the reader is told to do a thing to a thing they have no
name for. Caught by the user asking what it meant.

**Why this is the same defect as the entry above, not a new one.** "Ask for a multi-step handover"
fails because the *input* is a category rather than a value. "Switch the dropdown to WSL" fails
because the *object* is a token rather than a referent. Both produce a step that reads as
actionable and is not, and both were caught by a person rather than by a check.

**What the rule should say.** Roughly: expand an abbreviation on first use in any document or
handover, unless it has already been defined in this conversation or is domain-standard vocabulary
the rules already use (`git`, `PowerShell`, `JSON`). Assumed-shared vocabulary is an assumption, and
the rules already forbid building on those elsewhere — this is that rule applied to prose rather
than to environments.

**Fixed in place for this instance:** WSL is expanded on first use in `CLAUDE.md` and
`docs/desktop-verification.md`. Note that `verify.py` matches surface names out of the `CLAUDE.md`
table as literal substrings, so the row *label* has to stay `WSL session`; the expansion goes in
the prose beside it.

**Open question.** Whether this and the entry above are one rule or two. They share a cause —
an instruction that cannot be acted on as written — and a single rule covering both would be
shorter, which matters for text injected into every session. Two rules would be more checkable.
Neither is obviously right yet.
