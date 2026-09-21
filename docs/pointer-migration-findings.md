# Pointer migration findings

A by-hand migration of nine legacy prose pointers (ten targets) to the `doc-ref` format, done on
purpose without a `migrate` command so the friction could shape one. Design:
`docs/superpowers/specs/2026-09-20-pointer-integrity-design.md`. `docref.py` and every test were
left untouched; each place the tool or the format resisted is recorded below instead.

Marker convention tried: the marker is the last line of the target bullet or paragraph, alone on
its line, indented to the bullet's continuation indent (no indent for a top-level paragraph).

## What was migrated

| Site | Doc | Section | Id | Result |
|---|---|---|---|---|
| claude-agent-router/.../hook.py, above `_RECON_QUESTION_RE` | offshoot-plugins.md | Invariants | `ac58` | migrated |
| house-rules hook.py, `_unity_markers_in_parent` | hook-engine.md | Invariants | `0d4d` | migrated |
| house-rules hook.py, `branch_ownership` (target 1) | hook-engine.md | Invariants | `ee0f` | migrated |
| house-rules hook.py, `branch_ownership` (target 2) | hook-engine.md | Traps | `d2a4` | migrated; section name corrected, see finding 2 |
| house-rules hook.py, `_trace_subject` | hook-engine.md | Invariants | `361f` | migrated |
| tools/clean_install_test.py, `residual_config` | plugin-distribution.md | Traps | `47f6` | migrated |
| tools/clean_install_test.py, byte-compare step | plugin-distribution.md | Traps | `3470` | migrated |
| tools/install.py, `install_steps` | plugin-distribution.md | How it works | `db64` | migrated (paragraph) |
| tools/measure_footprint.py, `split_output` | plugin-distribution.md | How it works | `312e` | migrated (paragraph) |
| tools/verify_tools.py, above `BAT` | plugin-distribution.md | Invariants | `20e2` | migrated |

Nine sites, ten targets, all ten migrated. None was already stale (every quoted bullet was
found), none left as prose. `docref.py check` (excluding `verify.py` and `docref.py`) reports
every one of them ok. Behavior of the code is unchanged; only comments and docstrings moved.

## Friction

1. **Bullet-level targets fit "marker under the heading" badly (format gap, confirmed).** The spec
   wording puts the marker under a heading, but 8 of the 10 targets are single bullets inside a
   section that holds many of them (Invariants has around a dozen). A marker "under the heading"
   would name the whole section, and the pointer would then mean "somewhere in Invariants",
   which is what the prose pointer already meant and what the id was meant to fix. The
   end-of-bullet convention worked mechanically: an indented marker line stays inside the list
   item, `check` sees it (leading whitespace is allowed by the marker pattern), and the list
   stays one list. Smallest fix: state the convention in the spec and in `commands/docref.md`
   (marker is the last line of the note it names, at the note's indent), and say the note is
   whatever block contains the marker, not the section.

2. **The `(Section)` in a pointer is never checked and was already wrong once (tool defect,
   confirmed).** The task brief and the prose pointer both said the second `branch_ownership`
   target was in Invariants; the bullet is under Traps. The first migration carried the wrong
   section through, and `docref.py check` reported OK. The id resolves the note, so the section
   name is decoration that can rot silently, and it duplicates information the id already
   carries. Smallest fix: either have `check` compare the parenthesised name with the heading the
   marker sits under, or drop the section from the pointer form. This run corrected the one
   instance it found.

3. **One pointer naming two targets (site 3, format gap, confirmed).** `POINTER_RE` takes one id
   per match, so a docstring citing two bullets needs two full `doc-ref <id> <path>` clauses.
   That worked and both are counted, but it reads as noise: same path twice, same section
   twice. Smallest fix: none needed for correctness; a migrator should emit one clause per
   target, and the archivist guidance could say a site citing two notes in one doc is a hint the
   two bullets belong together.

4. **verify.py's real pointers cannot be migrated (confirmed).** Prose pointers in
   `claude-house-rules/plugins/house-rules/scripts/verify.py` (near lines 61, 1029, 2400 and
   3032 into `docs/systems/verify-suites.md`, others into `docs/architecture.md` and
   `docs/Decisions.md`) can never be checked. The live check is run with
   `--exclude` on that file because it holds dozens of deliberately fake pointer fixtures
   (`a3f9`, `beef` and others) that would otherwise read as dangling. So a real pointer added
   there is never checked, and the tool cannot tell a fixture from a real one. Smallest fix: a
   per-line opt-out (a trailing comment such as a fixture marker) or having `check` skip
   pointers inside string literals, so the file can be scanned; until then those stay
   prose. Related: `docref.py` itself must also be excluded, for the same reason.

5. **Pointers into Decisions.md need a decision (confirmed, not acted on).** The only real code
   pointer into `docs/Decisions.md` is the regression comment in verify.py near line 1390, out
   of reach anyway (finding 4). The file is append-mostly and entries are "never rewritten", so a
   marker would have to be added to a finished entry, which the file's own header forbids except
   for flipping `Status`.
   Smallest fix: decide whether adding a marker line counts as an allowed edit, or whether
   Decisions pointers should name an entry by date and title and stay outside the id scheme.

6. **Doc-to-code line numbers rot, and nothing covers them (doc problem, new).** Two of the
   target notes cite code lines: `hook.py:1006-1014` for `_trace_subject` (the function now
   starts at 991) and `clean_install_test.py:298-304` for the byte-compare (the step starts at
   294). The pointer scheme only guards code-to-doc, so the reverse direction stays unchecked.
   Smallest fix: refer to functions by name in docs, never by line.

7. **Marker placement after a paragraph with no blank line (format, tested by reading).** For the
   two "How it works" paragraphs (`db64`, `312e`) the marker sits directly under the paragraph
   text with no blank line. An HTML comment block may interrupt a paragraph in CommonMark, so it
   should not render as text, but this run did not render it in a viewer, only ran `check`.
   Smallest fix: put a blank line before a top-level marker, or state that either is fine.

8. **A reader cannot get from the id to the note without a search (convention gap).** The code
   says `ee0f` and a path; the reader must grep the doc for the marker and then work out that
   the note is the block *above* it. Backward-looking placement (marker at the end) makes the
   note's extent ambiguous when two bullets are adjacent. Smallest fix: put `docref.py where <id>`
   in the tool, printing the line and the block, and note in the docs that the marker closes the
   note it follows.

9. **Pointer text replaces the quoted phrase, losing context (loss, minor).** The old prose
   quoted the bullet, so a reader of the code could tell what the note was about without opening
   the doc. The migration removes that on purpose. Where the docstring's own first sentence
   already states the subject ("Why this exists instead of reusing ...") that is enough; it is
   worth keeping in any automated migration, since only the sentence before the pointer gives
   the hint.

10. **`new` does not reserve the id (tool behavior, confirmed by the brief, no collision hit).**
    Each marker had to be written to the doc before the next `new`. A batch migrator needs to
    allocate several ids at once, or `new` needs a count argument.
