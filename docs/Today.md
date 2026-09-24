# Today — 2026-09-24

Executed [`docs/plans/2026-09-24-plain-docs-skill.md`](plans/2026-09-24-plain-docs-skill.md):
built the `house-rules:plain-docs` skill and its checker. Did not write any actual plain copies
of this repo's docs — that's explicitly out of scope for the plan, left for a follow-up.

Then extended the skill to run project-wide: `plain_docs_check.py --queue` lists every eligible
source with its status (`MISSING`/`STALE`/`CURRENT`), a `DEFERRED` line for
`docs/architecture.md`, and an `EXCLUDED` summary; the skill's new `all` mode (and the redefined
`stale` mode) work the queue one doc at a time, committing each doc on its own. Did not run `all`
on this repo — no new plain copies were written by this pass either.

## What was done

- **The skill.** `claude-house-rules/plugins/house-rules/skills/plain-docs/SKILL.md` — what gets
  a plain copy and in what order, the fixed shape (title, full-doc link, five sections, Left
  out), the writing-rules table, the header format (source path + git blob hash), and the steps
  for upgrading `*(no plain copy yet)*` pointers and handling a related system with no doc.
- **The checker.** `claude-house-rules/plugins/house-rules/scripts/plain_docs_check.py` —
  stdlib-only, runs from anywhere, checks a whole `docs/plain/` tree or a single file. Fails on
  em/en dashes, an over-a-third word count, banned jargon, code blocks/file paths/`file:line`
  refs in prose, a missing or malformed header, a missing full-doc link, a missing source, a
  broken relative link, and a related link that should point at an existing plain copy but
  doesn't. Warns on an over-a-quarter word count and a stale source hash. Always prints average
  sentence length and the running to-do lists (`*(no plain copy yet)*`, `*(needs a doc)*`).
- **The command wrapper.** `commands/plain-docs.md`, same shape as `commands/docref.md`.
- **Tests.** 18 new cases in `scripts/verify.py` (`pd_case`), one per failure/warning type plus a
  clean pass, the to-do listing, pointer-upgrade detection, and the single-file-path mode. Suite
  is now 355/355 PASS.
- **Docs.** `docs/README.md` and the `project-docs` skill now list `docs/plain/` as a fourth
  non-tier folder. `docs/systems/verify-suites.md` and `docs/ProjectState.md` updated with the
  new check count. `CLAUDE.md`'s command list gained the checker.
- **Version bump.** `2.31.0` → `2.32.0` in `plugin.json`, per the version-bump guard. A second
  bump, `2.32.0` → `2.33.0`, went with the `--queue`/`all` mode addition.

## What was deliberately not done

- **Only one plain copy so far.** The first real run of the skill wrote
  [`docs/plain/systems/hook-engine.md`](plain/systems/hook-engine.md). The checker passes it with
  one warning (27% of the source, over the quarter target, under the one-third cap), kept because
  cutting further would drop real safeguards. The other three system docs have no plain copy yet.
- **No new tier-4 system doc for `plain-docs` itself.** Judged the same way `docref.py` was:
  covered by `verify-suites.md`/`hook-engine.md`'s existing scope rather than a document of its
  own, since nothing about it is a runtime-critical system in the tier-4 sense.

## What to do next, in order

1. Run `/house-rules:plain-docs` on the remaining system docs. `verify-suites.md` and
   `plugin-distribution.md` first: the hook-engine plain copy already points at both.
2. Everything still open in [`ProjectState.md`](ProjectState.md)'s Cross-cutting section — none
   of it was touched by this plan.
