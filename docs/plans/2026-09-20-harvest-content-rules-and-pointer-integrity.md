# Content-based harvest and self-maintaining doc pointers

Handoff from a session in the RockSkipping repo (2026-09-20), which exposed the problem. **Status:
brainstorming stopped after decomposing the work; nothing below B and C is designed or built.**
This document is the brief for an agent working in this repo. It replaces a scratch copy in the OS
temp directory. Piece B (pointer integrity) is designed and built: see [the design spec](../superpowers/specs/2026-09-20-pointer-integrity-design.md) and [its implementation plan](2026-09-20-pointer-integrity-implementation.md). Pieces A and C are still open.

## Status of the working tree when this was written

`git status` in this clone showed **uncommitted** changes in `CLAUDE.md`, `plugin.json` (2.27.0),
`commands/harvest-scan.md`, `scripts/harvest_scan.py`, `scripts/hook.py`, `scripts/verify.py`,
`docs/Decisions.md`, `docs/architecture.md`, and `docs/comment-harvest-calibration.md`. Read
`git status` and `git diff` first and do not clobber them.

One of those changes already delivers part of what the session asked for: **the line criterion is
gone and the default is `HARVEST_MIN_CHARS = 500`** (`hook.py`; `HOUSE_RULES_HARVEST_MIN_LINES` and
`--min-lines` no longer exist). Rationale and measurements are in
[`../comment-harvest-calibration.md`](../comment-harvest-calibration.md), "Current default: 500
characters, no line criterion". So the detector is no longer `lines >= 3 OR chars >= 150`; that
was the session's starting point and is history now. Do not redo it.

## What the user wants

Their words, condensed: everything in code that is not code (explanation, reasoning, history,
summary, useful notes, written by the agent or the user) should be **moved, not deleted**, to the
tier-4 / tier-6 docs where it belongs. The code keeps readable names, the useful bits, and a
**pointer**. A mechanism should **keep those pointers true when the docs change**. Longer term:
docs that stay current from the code plus observations made in sessions.

Decisions the user has made:

1. **Classify by content, not size.** Size (characters) only orders the review queue.
2. **Characters, not lines,** as the size signal. *(Landed, uncommitted; see above.)*
3. Balance human and AI readability. Humans dislike comment density; the target is well-named code
   plus docs that hold the rationale.
4. **Keep:** one-idea "why here" notes, load-bearing invariants, `///` doc-comment tooltips.
   **Move:** history, rationale, post-mortems, rejected approaches, repeated explanations.
5. The RockSkipping rule "heavy comment density is INTENTIONAL and must not be trimmed" was not
   chosen by the user and contradicts the harvest rule (see the end).

## Evidence from the RockSkipping scan

At the old default (3 lines / 150 chars) the scan flagged 831 blocks in 116 of 127 files. Chars-only
histogram over the same project: >=150: 820, >=300: 483, >=500: 218, >=800: 105, >=1200: 35,
>=2000: 3. To regenerate against RockSkipping, from
`C:\Users\aj\Desktop\GameDev\RockSkipping`, run the installed `harvest_scan.py` with the chars
threshold you want (the `--min-lines` flag existed only before the working-tree change).

Eight blocks near 300 chars were read to the user. What they showed, which should shape the rule:

- **Mixed blocks:** a good "why" note plus a history sentence in one comment
  (`Assets/Scripts/Game/Physics/SkipPhysics.cs:184-188` and `:211-215` carry `D1: 9c3f201 ...`
  regression records; `Assets/Scripts/Game/RockController.cs:262-265` ends with a post-mortem
  sentence). The archivist must be able to split inside a block.
- **Invariant that must stay:** `Assets/Scripts/Managers/Bootstrap.cs:120-123` (subscriber order).
- **Tooltip that should stay:** `Assets/Scripts/Net/RelayClient.cs:60-65` (`/// <summary>`).
- **Rationale that should move:** `relay/server.js:332-336` (why one origin), restated in the
  `RelayClient` summary.
- **Already points at a doc:** `Assets/Scripts/UI/JoinScreen.cs:426-429`.
- Many hits are file or class headers (`EventTypes/*`, `PlaceholderArt.cs:6-35`), and
  `deploy/spike/*`, `tools/`, and `*test*` files are throwaway or test code; consider exempting.

## The three pieces (recommended order B, A, C; the user did not confirm it)

The user answered the ordering question by asking for this handoff. Confirm the order with them
before building.

### B. Pointer integrity (foundation; deterministic; testable)

Today the archivist leaves "a one-line pointer naming the document and section"
(`agents/archivist.md`). Nothing checks it, so a renamed section or an archived doc makes the pointer
lie silently.

- Give each moved note a **stable ID**; the code pointer names the ID and path, not prose.
- A **checker** (script, run by `verify.py` and offered as a command) that finds every pointer in a
  project, resolves it to a doc section or ID, and reports dangling ones. A **fixer** that follows a
  moved or archived doc and rewrites the pointers. The `project-docs` skill already says to "fix the
  pointers into it" when a doc is archived; make that mechanical.
- Open decisions: ID format and where it lives in the doc (heading anchor or marker line); pointer
  syntax per language; what happens when a doc is split, merged, or a section is deleted; whether a
  hook or an explicit command runs the check.

### A. Content-based harvest rule (detection half is done; classification is not)

- Rewrite the rule text (`rules/house-rules.md`, "Long-form reasoning goes in a document, not in a
  comment") and `agents/archivist.md` to classify by content per the decisions above.
- The archivist must **split a mixed block** (keep the why, move the history) and never delete. Keep
  the two-pass staging flow for batches (`docs/plans/<date>-harvest-staging.md`).
- Exemptions to decide: file headers are already exempt; add doc-comment summaries and
  spike/test/tools paths if wanted.
- Re-run the scanner at realistic scale after changes; a toy fixture once passed a broken scanner.

### C. Docs that update from code (largest; design only after B)

- Link code regions to doc sections (B's IDs are the seed), flag or update the doc section when the
  code it describes changes, and capture session observations (user and agent) into the right doc
  instead of leaving them in chat or comments.
- Needs agent judgement. Decide what is deterministic (flagging stale pointers and sections) versus
  agent-written (updating prose). Not scoped yet.

## Constraints and preferences

- Standing rules: build only what was asked, ask when ambiguous, hand commands over as step cards,
  never hand over a command that was not run, artifacts as real files in the project, hand approved
  plans to `house-rules:executor`. In RockSkipping the user also asked that findings go to `.md`
  before source changes and that the agent not run mutating git; check this repo's `CLAUDE.md` for
  what applies here.
- Non-trivial plugin changes get a `docs/Decisions.md` entry, and `verify.py` must pass (it asserts
  on the archivist text and the harvest hook behaviour).
- Brainstorming reached: classified **architectural**, context explored, decomposition presented.
  Still owed: clarifying questions, 2-3 approaches, sectioned design, a written spec, user review,
  then a plan.

## Not for this repo (do separately, in RockSkipping)

- Reword the density bullet in `Assets/CLAUDE.md` "Documented deviations" to: short why-notes stay,
  long-form history and rationale move to docs. Not done; awaiting the user's go-ahead.
- Porting RockSkipping's actual blocks happens only after the mechanism exists.

## Suggested skills for the next agent

- `superpowers:brainstorming`: resume at "ask clarifying questions" (architectural path).
- `superpowers:writing-plans`: after the design is approved.
- `superpowers:test-driven-development`: for the checker/fixer and any detector change.
- `house-rules:project-docs`: tier definitions and the "fix the pointers" convention.
- `superpowers:verification-before-completion`: run `verify.py` and a realistic-scale scan first.
- `house-rules:doctor` if hooks misbehave while testing.
