---
name: plain-docs
description: Write a plain-English copy of a tier-4 system doc (or another eligible tier), for a
  reader who does not want file paths and line numbers. Use when asked to write, redo, or check a
  plain copy of a doc, or when the plain-docs checker flags a stale or missing one. Not for
  editing the technical doc itself - the original stays exactly as detailed as it needs to be.
---

# Plain copies of the docs

The technical docs (`docs/systems/*.md`, `docs/README.md`, `docs/ProjectState.md`,
`docs/Roadmap.md`) are written for precision, which makes them slow for a person to read. This
skill writes a **second, plain copy** of one of those docs, for people. The original is never
rewritten by this skill.

Usage: `/house-rules:plain-docs <path>` for one doc, or `/house-rules:plain-docs stale` to redo
every plain copy whose source has changed since it was written.

## What gets a plain copy, and in what order

1. `docs/systems/*.md` - the system docs. This is where the need is greatest.
2. `docs/README.md`, `docs/ProjectState.md`, `docs/Roadmap.md`.
3. `docs/architecture.md`, split by section, only once 1 and 2 have proven useful.

Left out, never given a plain copy: `docs/Decisions.md`, `docs/plans/`, `docs/archive/`,
`docs/sessions/`, `docs/generated/`. These are history or working notes; a plain copy of one
would go stale as fast as it was written.

## Where copies live

`docs/plain/`, mirroring the original layout exactly: `docs/plain/systems/hook-engine.md` is the
plain copy of `docs/systems/hook-engine.md`. It is a non-tier folder, like `docs/generated/` -
see `docs/README.md` and the `project-docs` skill for where it's listed.

## The header

The first line of every plain copy, exactly this shape:

```
<!-- plain copy of: <source path, repo-relative, forward slashes> @ <40-hex git blob hash> -->
```

The hash is the source file's git blob hash at the moment the plain copy is (re)written. Get it
with `git hash-object <source path>` - it works on the file's current on-disk content, whether or
not that content is committed yet. This is how the checker (below) tells a plain copy is stale:
if the source's blob hash no longer matches the header, the source changed after the copy was
written.

## Steps

1. **Read the source doc in full.**
2. **List every section heading in it**, and every other system doc it cross-references (a
   `docs/systems/*.md` file it links or names). Each heading must end up either covered in the
   plain copy or named in the closing **Left out** note - this is how "covers everything
   necessary" gets checked instead of hoped for. Each cross-referenced system becomes a
   **Related** entry.
3. **Write the copy** in the fixed shape below, with the header line first, then the full-doc
   link under the title, then the five sections, then **Left out**.
4. **Upgrade pointers.** Search every other existing plain copy for a `*(no plain copy yet)*`
   link to the doc you just covered, and switch each one to link to the new plain copy instead
   (drop the `*(no plain copy yet)*` marker). Creating `raid` in plain English upgrades the
   pointer in `castle` in the same change.
5. **Handle a related system with no technical doc at all** before dropping it from **Related**:
   - Check `docs/systems/README.md`'s left-out list first. Already listed there with a reason?
     Leave it out of **Related** and move on.
   - Not listed yet? Judge it by the tier-4 test in the `project-docs` skill: is it critical to
     the product at runtime, with rules that must hold or mistakes that have already cost time?
     - No: leave it out of **Related**, and add it to `docs/systems/README.md`'s left-out list
       with a one-line reason, so the question isn't asked again.
     - Yes: this skill does not write the technical doc itself - that's a bigger job than a plain
       copy. List the system under **Related** with no link, marked `*(needs a doc)*`, and name
       it to the user when the run finishes.
6. **Run the checker** (`plain_docs_check.py`, see below). Fix anything it flags as `FAIL`, then
   run it again until it reports none. A `WARN` is a choice, not a blocker - note why it's
   acceptable if you leave one in place.

## The fixed shape

Under the title, one line: `Full technical doc: [<name>.md](<relative link to the technical
doc>)`. Then:

1. **What it is.** One or two sentences.
2. **Why it matters.** What breaks, in everyday terms, if this goes wrong.
3. **How it works.** Numbered steps, seven at most.
4. **Risks and safeguards.** One line per risk: bold the risk name, then say what prevents it.
   Where nothing does yet, mark it `*Still open:*` and say what's needed. Lead with the
   safeguard, not the failure mechanism.
5. **Related.** One entry per system the technical doc cross-references:
   - Plain copy already exists -> link to it.
   - No plain copy yet -> link to the technical doc, marked `*(no plain copy yet)*`.
   - No technical doc at all -> see step 5 above (either dropped, or listed unlinked and marked
     `*(needs a doc)*`).

Then a closing **Left out** line naming what the technical doc covers that this copy doesn't -
settings, exact numbers, test names, code detail - so the reader knows where to look for it.

## Writing rules

| Rule | Limit |
|---|---|
| Length | Aim for a quarter of the source's word count (excluding the header line). Up to a third only when the system is too dense to cover in less. Never over a third. |
| Sentences | 20 words or fewer as a target. |
| Dashes | No em dashes or en dashes used as punctuation. Use a full stop, comma or colon. |
| Jargon | None. A technical word that can't be avoided (like "hook") gets explained in plain words the first time, in the same sentence. |
| Code detail | No file paths, line numbers, function names or code blocks. The full-doc link covers that. |
| Filler | No intros, no "in summary", no restating the heading. |

The goal above all of them: the shortest, easiest read that still covers everything necessary.

## The checker: `plain_docs_check.py`

Lives beside this skill at `scripts/plain_docs_check.py`, stdlib-only Python, so an installed
copy of the plugin has it too. Run it from anywhere in the repo:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/plain_docs_check.py"
```

With no path it checks every `.md` under `docs/plain/`; pass a path to check one file only.
`--root` overrides the repo root it checks against (default: the git top level, else the current
directory).

It fails (`FAIL`, exit 1) on:

- any em dash or en dash
- a word count over a third of the source's (over a quarter is a `WARN` instead, not a fail)
- a banned word from the small, editable list at the top of the script (starts with `payload`,
  `stdin`, `dispatch`, `handler`, `idempotent`, `shim`, `argv`)
- a code block, a `file:line` reference, or a file path in prose (a link's own target is fine)
- a missing or malformed header, or a missing full-doc link under the title
- the source file not existing at all
- a broken relative link
- a related link to a technical doc that already has a plain copy (should link to the plain copy)
- a `*(no plain copy yet)*` pointer whose target now has a plain copy (an unupgraded pointer)

It warns (`WARN`, exit still 0 if nothing else fails) on:

- a word count over a quarter of the source's
- a stale header: the source's current blob hash no longer matches the header's

It always prints, info-only, never affecting pass/fail:

- average sentence length
- the running to-do list of every `*(no plain copy yet)*` line found (systems still needing a
  plain copy) and every `*(needs a doc)*` line found (systems still needing a technical doc)

A repo with no `docs/plain/` folder is not silently skipped - the checker says so in one line and
exits 0, since there's nothing to check yet.
