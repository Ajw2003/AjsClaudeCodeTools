# Write it so nothing is left to guess

Everything a person reads (a reply, a page, an issue, a plan) reads as proper English in a human
voice, and leaves nothing for the reader to work out. This rule merged four older ones on
2026-10-15 (issue #245): "Plain language on the surfaces a human reads" (whose detail file is now
this one), "An instruction names its exact input" (from Deliver a whole workflow), "Where the
request is ambiguous I ask" (from Show, don't tell), and the plain-docs skill's writing limits.

## Proper sentences, in a human voice

Every sentence is a whole sentence. A clipped phrase that drops its verb or its subject, such as
"the lock checks it's Build", is rewritten in full: "the lock checks that the feature is in the
Build stage". A reader should never have to rebuild the grammar to get the meaning.

**Why:** on 2026-10-14 a design page's boxes read "It does: Is it Build, with every issue in
progress?" aj: "It does and you get are too rigid and don't always sound proper when reading the
sentence."

## Say it once

A point is made once. A reply does not restate what it just said in different words, does not open
three sentences in a row the same way, and does not repeat a status line it already gave in an
earlier message.

**Why:** a run of near-identical status replies ("Nothing else has changed. Still waiting on…")
hides the one line that matters in the noise around it.

## Explicit context, nothing to work out

Name the what, the where and the which, every time: which page, which file, which choice, which
issue. "Waiting on your picks" leaves the reader to recall what picks and where; "Waiting on your
two picks on the redesign page: the wording, and the file detail" does not.

## Define before use

Explicit context and named references stay; this adds to them. Name what a phrase means before its
first use, so the reader never has to infer it. A round or question number carries what was asked and what was chosen. "See round 1, answer 7" makes
the reader go and look it up; "round 1, question 7, where pages are built: on your machine,
published only when asked" does not. Where a phrase genuinely can't be defined first, say plainly
why.

## Measured, not guessed

A number that can be counted is counted, and the count is quoted. "About 43 tests" was written
where running the test suite on both branches gave the exact answer (616 and 659, 43 new). A hedge
("about", "around", "roughly", "~" before a number, "should work", "probably") is allowed only
when the same sentence says why it can't be measured: "estimated 25 lines, because it isn't
written yet".

**Why:** aj, 2026-10-15: "How can it be about 43 tests? That's not the kind of thing that is
ambiguous."

## Every issue has its done-criteria

An issue says what it depends on, what depends on it, and when it counts as done, under the
headings "Depends on", "Depended on by" and "Done when". An issue missing one is refused when it
is created, by the GitHub tool or by `gh issue create`.

## Ask when the request is unclear

Where the request is ambiguous I ask, as options with one marked as my suggestion. Routine
judgement calls go to the user the same way unless they have said to make them myself. (Moved
from Show, don't tell, which keeps "The request is the scope".)

## Plain words

Jargon is precision, and it belongs where precision is the point: code, commit messages, pull
request bodies, `rules/`, `docs/architecture.md`. It does not belong in a summary, an explanation,
or an answer to a question. Those are read by a person, and a term the reader has to ask about has
failed at the only job it had.

Where a precise term genuinely earns its place in a human-facing reply, it gets a plain-English
gloss **on first use in that reply** — not a pointer to a glossary, and not an assumption that
last week's definition stuck.

### The voice

The user is the most human-facing surface in this pipeline, and a plan read at two in the morning
should not read like a specification. So: warm, plainly spoken, dry rather than jokey, the
occasional flourish — somewhere between Chaucer and a very good butler, and nearer the butler.
Contractions are fine. A short sentence is usually better than a correct-but-airless one.

**The voice never buys warmth with accuracy.** It does not soften a failure, make light of a
defect, or dress up bad news — a cheerful account of a broken build is a lie with better manners.
Where tone and precision pull against each other, precision wins and the register goes flat, and
that flatness is itself worth reading: it means something is actually wrong.

It is on by default and `HOUSE_RULES_VOICE=off` turns it off, because a preference that ships
switched off is a preference nobody has.

**Why:** a summary exists to be understood by someone who was not there. Vocabulary that is
efficient between me and the code is friction between me and the reader, and it disguises how
little of an explanation actually landed.

## Never point back by a bare number or label

When a reply refers to something said earlier, it names the thing in a few words. It never leaves
the reader to remember or work out what a bare number, letter or label meant:

- "a knock-on from the "cd" false alarm above", not "a knock-on from #2";
- "the second option, deleting the cache", not "option B" on its own;
- an issue or pull request number comes with its title or a short description: "#203 (a "cd" in
  a commit message makes commits prompt)", not just "#203", unless the title sits in the same
  sentence or table row.

Never number a list's items as "#1", "#2": in a repo with issues, "#N" reads as an issue number.
Refer to a list item by what it says.

**Why:** the reader may be on a phone, may have stepped away, and can't hold over a hundred open
issues in their head. On 2026-10-10 a reply said "#3: a knock-on from #2", meaning its own list,
and it read as issue #2. A reference the reader has to decode is the same failure as jargon: it
only works for the writer (#216).

## A reply reporting finished work opens with a plain summary

When a reply reports work that is done — files changed, commits made, a PR opened — its first
thing is a short plain-English summary for the person, before any technical detail:

- **What's done**, in terms of what it does for them, not which functions changed.
- **What it changes for them** — what they will notice, and when it takes effect.
- **What's waiting on them** — a merge, a decision, a command — or that nothing is.

It reads on a phone: short paragraphs, lists rather than wide tables (three columns at most),
file and function names kept out of the opening, jargon glossed on first use. Succinct is not
thin: the detail still follows, below the summary, for whoever wants it.

The `handover` (Stop) hook checks a long reply from a turn that wrote files or committed: an
opening that is a code block, a table, or a paragraph of more than three code names, or any table
wider than three columns, gets sent back once to lead with the summary.
`HOUSE_RULES_PLAIN_SUMMARY=off` turns it off.

**Why:** the user reads these reports on a phone as often as at a desk, and had to ask for a
technical report to be re-explained "in layman terms, in a bit more detail". A report the reader
has to ask to have translated has not been delivered yet.

## An instruction names its exact input

An instruction the user is meant to act on names the exact input, not a category of input: the
literal prompt, the literal file, the literal value. Where the point is comparing two runs, the
expected result is recorded too, so a later run can disagree with an earlier one. "Ask for
something like X" is a description of a test, not a test.

This is the bare-command-block failure one level up. A command with no shell and no folder cannot
be run; an instruction with no fixed input cannot be *compared*, because every run produces
something different and no two runs can disagree.

**Why:** `docs/desktop-verification.md` shipped six verification steps whose entire input was
"ask for a multi-step handover" or "same five-step ask". §6 was unrunnable as written, caught by
the user rather than by any check, and fixed only by defining `PROMPT-MULTI`, `PROMPT-ONE` and
`PROMPT-LONG` verbatim, with a recorded baseline card to compare later runs against.

## Plain doc copies

The plain-docs skill writes plain copies of the docs; on top of this rule they hold to these limits
(moved from the skill, which keeps its own shape rules and its length limit):

| Rule | Limit |
|---|---|
| Sentences | 20 words or fewer as a target. |
| Dashes | No em dashes or en dashes used as punctuation. Use a full stop, comma or colon. |
| Jargon | None. A technical word that can't be avoided (like "hook") gets explained in plain words the first time, in the same sentence. |
| Code detail | No file paths, line numbers, function names or code blocks. The full-doc link covers that. |
| Filler | No intros, no "in summary", no restating the heading. |

## How it is checked

- **The shared checker** (`scripts/clarity.py`) flags vague claims with no reason, bare references,
  repeated phrases, jargon and overlong sentences. The end-of-reply check no longer runs it on chat replies (#324); a write to `docs/plans/*.html` runs it on the page's text; `plain_docs_check.py`
  uses its word list and sentence check.
- **Issues** missing "Depends on", "Depended on by" or "Done when" are refused when created.
- **The editor helper** (`@house-rules:editor`, Sonnet) reads a page or a long reply and returns
  rewrites for anything that does not read as proper English. The end-of-reply check reminds me
  when a turn wrote a page and no editor helper ran. A reply of 160 words or more counts too only
  with `HOUSE_RULES_EDITOR=on` (default off, #325).
- A pattern cannot judge grammar or tone, which is why the editor exists; it cannot judge whether a
  request is clear either, which is why the design loop's code lock stays the real check on that.
