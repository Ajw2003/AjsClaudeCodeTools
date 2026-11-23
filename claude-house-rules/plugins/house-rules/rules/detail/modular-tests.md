# Tests are modules, run alone or chained

A test is a module when all five hold:

1. **It has a name**, on a header line in its first 15 lines: `# test-module: <name>` (or the
   language's own comment mark).
2. **It runs alone** with one exact command, on a second header line: `# run-alone: <command>`.
3. **It needs nothing from another module**: no state, file or fixture another module leaves behind.
4. **It chains**: a suite with several modules has one runner that takes `--parts a,b`, and no
   argument means every module.
5. **Only a test of everything may run everything.** A whole-system test declares it with
   `# test-module: end-to-end` and `# end-to-end: <why it must run whole>`.

A change to one part of a project runs that part's modules only.

## Examples

- This repo: `scripts/verify.py` already splits into parts (`--parts core`, `--changed`); it needs
  only the header lines. `tools/clean_install_test.py` and the live QA folders are end-to-end.
- Illustration only: Plunderspell's heavy-carry test is one module for that carry, chainable with
  the other carry modules, never requiring the rest.

## Existing tests that are not modules

They are listed in `docs/3-state/non-modular-tests.md`. Work continues past that list, except in a
refactor (typed `refactor on`, or one I declare and name in my reply), where a listed test is
converted before the refactor touches what it tests. A new test that is not a module is refused.

## Why

A suite that only runs whole is run rarely, fails for reasons far from the change, and hides which
part broke. Small named modules can be run after every change, twice where it matters, and chained
when the whole is wanted. The gate (issue #578) is not built yet; until then this rule is on me.
