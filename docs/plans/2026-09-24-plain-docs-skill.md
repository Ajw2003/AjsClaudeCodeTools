# A skill that writes plain-English copies of the docs

## Context

The docs are written for precision. That makes them good for Claude and for checking claims against
the code, but slow for a person. `docs/4-systems/hook-engine.md` alone is 1,624 words, full of file
paths, line numbers and event names. `architecture.md` is 10,240 words. Reading the code can be
faster than reading its doc, which defeats the point of having one.

The fix is not to rewrite the originals. They stay as they are, because `verify.py`, the archivist's
`doc-ref` pointers and future Claude sessions all depend on their detail. Instead, a skill writes a
**second, plain copy** of each doc, for people.

## What a plain copy looks like

Every plain copy uses the same short shape, so a reader always knows where to look.

Under the title, one line links to the full technical doc it was written from.

1. **What it is.** One or two sentences.
2. **Why it matters.** What breaks, in everyday terms, if this goes wrong.
3. **How it works.** Numbered steps, seven at most.
4. **Risks and safeguards.** One line per risk, covering both known failure points and the
   promises the system keeps. Name the risk in a few words, then say what prevents it. Where
   nothing does yet, mark it *Still open* and say what is needed. Focus on the safeguard, not
   on how the failure happens.
5. **Related.** One line per related system: what it does in a few words, and a link. See
   "Pointers" below for how these links are chosen and kept current.

Writing rules. The goal above all of them: the shortest, easiest read that still covers
everything necessary.

| Rule | Limit |
|---|---|
| Length | Aim for a quarter of the original's word count. Up to a third only when the system is too dense to cover in less. Never over a third |
| Sentences | 20 words or fewer as a target |
| Dashes | No em dashes (`—`) and no en dashes (`–`) used as punctuation. Use a full stop, comma or colon |
| Jargon | None. If a technical word cannot be avoided (like "hook"), explain it in plain words the first time, in the same sentence |
| Code detail | No file paths, line numbers, function names or code blocks. The link to the full doc covers that |
| Filler | No intros, no "in summary", no restating the heading |

Example of the register, for the hook engine (illustration only, not final text):

> **What it is.** The part of the plugin that makes the rules actually happen. Claude Code sends a
> signal at set moments, such as when a session starts or before a command runs. The hook engine
> catches each signal and runs the right check.
>
> **Why it matters.** If it breaks, the rules become words nobody enforces. A warning that should
> stop a risky command just never shows up.

## Where the copies live

`docs/plain/`, mirroring the original layout: `docs/plain/4-systems/hook-engine.md` is the plain copy
of `docs/4-systems/hook-engine.md`. It is a non-tier folder, like `generated/`, and gets a line in
`docs/1-landing/README.md` and in the `project-docs` skill.

Each plain copy starts with a one-line header naming its source file and the source's git blob hash
at the time it was written. That hash is how staleness gets caught.

## Pointers

Every plain copy carries two kinds of link.

**The full technical doc.** One line under the title, always. This is the way back to the detail
the plain copy leaves out.

**Related systems.** Built from the technical doc's own cross-references. If the technical doc
points at another system doc, the plain copy lists that system under **Related**. Each entry links
to the best copy that exists right now:

- If the related system already has a plain copy, link to that.
- If it doesn't, link to its technical doc and mark the line *(no plain copy yet)*.

Pointers get upgraded, not left behind. Two things keep them current:

1. **When the skill writes a new plain copy**, it searches every existing plain copy for a
   *(no plain copy yet)* link to the same technical doc, and switches each one to the new plain
   copy. Creating `raid` in plain English upgrades the pointer in `castle` in the same change.
2. **The checker backs this up.** It fails on any related link that points at a technical doc
   when a plain copy of that doc exists, and on any link that doesn't resolve. It also lists every
   *(no plain copy yet)* line, which doubles as the to-do list of plain copies still to write.

**A related system with no technical doc at all** gets checked before it is dropped:

1. **Already decided?** `docs/4-systems/README.md` lists systems that were deliberately left without
   a doc, with the reason. If it is on that list, leave it out of **Related**.
2. **Not decided yet?** Judge it by the tier 4 test in the `project-docs` skill: is it
   critical to the product at runtime, with rules that must hold or mistakes that have already
   cost time?
   - **No, it is simple enough.** Leave it out, and add it to the left-out list in
     `docs/4-systems/README.md` with a one-line reason, so the question is not asked again.
   - **Yes, it should have a doc.** The skill does not write the technical doc itself, since that
     is a bigger job than a plain copy. It lists the system under **Related** with no link, marked
     *(needs a doc)*, and names it to the user at the end of the run. The checker lists every
     *(needs a doc)* line alongside the *(no plain copy yet)* ones.

## What gets a plain copy

In order:

1. `docs/4-systems/*.md` (the four system docs). This is where the need is greatest.
2. `docs/1-landing/README.md`, `docs/3-state/ProjectState.md`, `docs/2-roadmap/Roadmap.md`.
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
2. List every section heading in it. Each heading must end up either covered in the plain copy
   or named in a short "Left out" note at the bottom (for example, "exact event list: see full
   doc"). This is how "covers everything necessary" gets checked instead of hoped for. Also list
   every other system doc it points at; each becomes a **Related** entry.
3. Write the copy in the fixed shape above, with the full-doc link under the title and a
   **Related** entry for each system it points at.
4. Upgrade any *(no plain copy yet)* pointers in other plain copies that this new copy now
   satisfies.
5. Run the checker (below). Fix anything it flags, then run it again until it passes.

### 2. The checker: `plain_docs_check.py`

The model will slip an em dash or a long sentence in eventually. So the rules that a script can
check, a script checks. Lives beside the skill, so installed copies have it too.

It fails on:

- any em dash or en dash
- a word count over a third of the source's (hard fail), or over a quarter (a warning, so the
  extra length has to be a choice)
- a banned word from a small, editable list (starting with things like `payload`, `stdin`,
  `dispatch`, `handler`, `idempotent`, `shim`, `argv`)
- a code block, file path or `file:line` reference
- a missing or malformed source header, or a missing full-doc link under the title
- a broken link, or a related link to a technical doc that already has a plain copy
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

## Result

Executed 2026-09-24, on branch `claude/intelligent-davinci-bxeni1`. The open questions above were
answered before this pass started (see the commits under this plan's own filename): folder is
`docs/plain/`, stale is a warning not a fail, it ships in the plugin (tests in `verify.py`), and
the sample (`docs/plans/2026-09-24-plain-docs-example-castle.md`) came first.

Built:

- `claude-house-rules/plugins/house-rules/skills/plain-docs/SKILL.md` — the skill.
- `claude-house-rules/plugins/house-rules/scripts/plain_docs_check.py` — the checker. Header
  format settled on `<!-- plain copy of: <source path> @ <40-hex git blob hash> -->`, one line,
  first line of the file; the hash comes from `git hash-object <source>`, which works on the
  file's current on-disk content whether or not it is committed.
- `claude-house-rules/plugins/house-rules/commands/plain-docs.md` — the command wrapper, same
  shape as `commands/docref.md`.
- 18 cases in `scripts/verify.py` (the `pd_case` helper, fixtures built with a real `git init` so
  blob hashes are real): one per failure type and warning type, plus a clean pass, the to-do
  listing, pointer-upgrade detection, and single-file-path mode. Suite: 355/355 PASS.
- Docs: `docs/1-landing/README.md` and the `project-docs` skill now list `docs/plain/` as a fourth non-tier
  folder; `docs/4-systems/verify-suites.md` and `docs/3-state/ProjectState.md` carry the new check count;
  `CLAUDE.md`'s command list gained the checker; `docs/5-today/Today.md` rewritten for this session.
- Plugin version bumped `2.31.0` → `2.32.0`.

Deliberately not done: no plain copies of this repo's own docs were written (explicitly out of
scope for this plan) and no new tier-4 system doc was written for `plain-docs` itself — judged
the same way `docref.py` was, covered by the existing hook-engine/verify-suites scope rather than
a system of its own.

Verification: `python claude-house-rules/plugins/house-rules/scripts/verify.py` exits 0 (355/355);
`python tools/verify_tools.py` exits 0 (39/39); `plain_docs_check.py` run against a scratch
fixture built from the sample above passed with one expected warning (word count over a quarter)
and correctly listed all four `*(no plain copy yet)*` to-do entries; run against this repo's own
root (no `docs/plain/` yet) it reported that plainly and exited 0.

### Follow-up: project-wide mode

`plain_docs_check.py` gained `--queue`: it prints every eligible source (`docs/4-systems/*.md`
except `README.md`, sorted by name, then `docs/1-landing/README.md`, `docs/3-state/ProjectState.md`,
`docs/2-roadmap/Roadmap.md`) with its status (`MISSING`/`STALE`/`CURRENT`) and mirrored plain-copy path, a
`DEFERRED` line for `docs/architecture.md`, and an `EXCLUDED` summary naming every excluded group
and any unlisted `docs/*.md` file by name. It always exits 0, since it is a listing, not a check.
The `house-rules:plain-docs` skill gained `/house-rules:plain-docs all` (project-wide, one doc at
a time, committing each doc separately) and redefined `stale` as the same loop limited to `STALE`
entries. 8 new `pd_case` tests in `verify.py` cover `--queue`; suite is now 363/363 PASS. Version
bumped `2.32.0` → `2.33.0`. `all` was not run on this repo in this pass; no new plain copies were
written.
