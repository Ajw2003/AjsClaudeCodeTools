# A skill that writes plain-English copies of the docs

## Context

The docs are written for precision. That makes them good for Claude and for checking claims against
the code, but slow for a person. `docs/systems/hook-engine.md` alone is 1,624 words, full of file
paths, line numbers and event names. `architecture.md` is 10,240 words. Reading the code can be
faster than reading its doc, which defeats the point of having one.

The fix is not to rewrite the originals. They stay as they are, because `verify.py`, the archivist's
`doc-ref` pointers and future Claude sessions all depend on their detail. Instead, a skill writes a
**second, plain copy** of each doc, for people.

## What a plain copy looks like

Every plain copy uses the same short shape, so a reader always knows where to look:

1. **What it is.** One or two sentences.
2. **Why it matters.** What breaks, in everyday terms, if this goes wrong.
3. **How it works.** Numbered steps, seven at most.
4. **What can go wrong.** Short list of known failure points.
5. **Where to go for more.** One link to the full doc.

Writing rules:

| Rule | Limit |
|---|---|
| Length | Around a quarter of the original. Hard cap of 300 words for a system doc |
| Sentences | 20 words or fewer as a target |
| Dashes | No em dashes (`—`) and no en dashes (`–`) used as punctuation. Use a full stop, comma or colon |
| Jargon | None. If a technical word cannot be avoided (like "hook"), explain it in plain words the first time, in the same sentence |
| Code detail | No file paths, line numbers, function names or code blocks. The one link to the full doc covers that |
| Filler | No intros, no "in summary", no restating the heading |

Example of the register, for the hook engine (illustration only, not final text):

> **What it is.** The part of the plugin that makes the rules actually happen. Claude Code sends a
> signal at set moments, such as when a session starts or before a command runs. The hook engine
> catches each signal and runs the right check.
>
> **Why it matters.** If it breaks, the rules become words nobody enforces. A warning that should
> stop a risky command just never shows up.

## Where the copies live

`docs/plain/`, mirroring the original layout: `docs/plain/systems/hook-engine.md` is the plain copy
of `docs/systems/hook-engine.md`. It is a non-tier folder, like `generated/`, and gets a line in
`docs/README.md` and in the `project-docs` skill.

Each plain copy starts with a one-line header naming its source file and the source's git blob hash
at the time it was written. That hash is how staleness gets caught.

## What gets a plain copy

In order:

1. `docs/systems/*.md` (the four system docs). This is where the need is greatest.
2. `docs/README.md`, `docs/ProjectState.md`, `docs/Roadmap.md`.
3. `docs/architecture.md`, split by its sections, if 1 and 2 prove useful.

Left out: `Decisions.md`, `plans/`, `archive/`, `sessions/`, `generated/`. These are history or
working notes. A plain copy would go stale as fast as it was written.

## The pieces

### 1. The skill: `house-rules:plain-docs`

Lives at `claude-house-rules/plugins/house-rules/skills/plain-docs/SKILL.md`, so it works in every
repo the plugin is installed in, not just this one.

Usage: `/house-rules:plain-docs <path>` for one doc, or `/house-rules:plain-docs stale` to redo
every copy whose source has changed.

What it tells Claude to do:

1. Read the source doc in full.
2. List every section heading in it. Each one must end up either covered in the plain copy or
   named in a short "Left out" note at the bottom (for example, "exact event list: see full doc").
   This is how "covers everything necessary" gets checked instead of hoped for.
3. Write the copy in the fixed shape above.
4. Run the checker (below). Fix anything it flags, then run it again until it passes.

### 2. The checker: `plain_docs_check.py`

The model will slip an em dash or a long sentence in eventually. So the rules that a script can
check, a script checks. Lives beside the skill, so installed copies have it too.

It fails on:

- any em dash or en dash
- a word count over the cap
- a banned word from a small, editable list (starting with things like `payload`, `stdin`,
  `dispatch`, `handler`, `idempotent`, `shim`, `argv`)
- a code block, file path or `file:line` reference
- a missing or malformed source header
- **stale**: the source's current blob hash no longer matches the header

It reports average sentence length but does not fail on it, since a hard limit there produces
choppy writing.

### 3. Tests and CI

A case per failure type in `tools/verify_tools.py` (or `verify.py`, see the open question below),
so CI proves the checker catches what it claims to. CI then runs the checker over `docs/plain/`.

## Open questions for aj

1. **Folder name.** `docs/plain/` is the recommendation. Alternatives: `docs/human/`,
   `docs/easy/`.
2. **Stale copies in CI.** Fail the build, or only warn? Recommendation: **warn**. Failing would
   block every doc edit until the plain copy is redone, and that pressure tends to produce rushed
   copies.
3. **Ship in the plugin or keep in this repo?** Recommendation: **ship it**, since the problem is
   the same in every repo that uses the six tiers. That makes the checker's tests belong in
   `verify.py`.
4. **Sample first?** Recommendation: write the hook engine's plain copy by hand first, agree the
   register on that one doc, then build the skill around what worked.

## Out of scope for now

- A hook that reminds Claude to refresh a plain copy when its source is edited. Worth adding only
  if the stale warning turns out to be ignored.
- Plain copies of code comments or commit messages.
