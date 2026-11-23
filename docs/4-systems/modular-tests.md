# Modular tests

**Owns:** the rule that every test is a module that runs alone or chained, the write-time refusal of
tests that are not, the `refactor on`/`refactor off` switch, the audit list of old tests that are not
modular yet, and the conversion skill and command. Status: design approved 2026-11-23 as "Design
approved: modular tests 1A 2* 3A" (aj's own answer to choice 2: "c plus A"); not built yet. Page:
`docs/plans/2026-11-23-modular-tests/proposal.html`.

## What a test module is

A test is a module when all five hold:

1. **It has a name**, on a header line in its first 15 lines: `# test-module: <name>` (or the
   language's own comment mark).
2. **It runs alone** with one exact command, on a second header line: `# run-alone: <command>`.
3. **It needs nothing from another module**: no state, file or fixture another module leaves behind.
4. **It chains**: a suite with several modules has one runner that takes `--parts a,b` (the shape
   `scripts/verify.py` already has), and no argument means every module.
5. **Only a test of everything may run everything.** A whole-system test declares it instead, with
   `# test-module: end-to-end` and `# end-to-end: <why it must run whole>`. The live QA folders and
   `tools/clean_install_test.py` are of this kind.

A change to one part of a project runs that part's modules only. Plunderspell's heavy-carry test is the
model: one module for that carry, chainable with the other carry modules, never requiring the rest.

## The gate (choice 1A: refuse at write time)

A new `PreToolUse` check in `hook.py` looks at a `Write` or `Edit` of a file that looks like a test
(`test_*`, `*_test.*`, `verify*.py`, files under a `tests/` folder). It refuses when the written file has
no module header or no `run-alone` line, and the refusal says which line to add. A file declared
`end-to-end` passes. A test file that already exists and is not modular is not refused for unrelated
edits (see the audit below); the refusal applies to new files, and to edits during a refactor.

Not built, by choice: a CI check that fails a pull request (choice 1B). It can be added later without
redoing the hook.

## Refactor (choice 2: "c plus A")

A refactor is in force when either holds:

- **A.** aj types `refactor on` as its own line; `refactor off` ends it. It is stored like the other
  typed switches (`docs/4-systems/speed-switches.md`). This is the part the hook can check.
- **c.** The agent judges the session is a refactor and says so in its reply, naming why. The hook cannot
  check this one; it is a rule on the agent, recorded in the reply.

While a refactor is in force, an existing test file listed as non-modular must be converted before the
refactor's other changes touch what it tests.

## The audit

`/house-rules:modular-tests audit` scans for test files, classifies each as modular, end-to-end
(exempt, with the reason) or not modular, and writes
`docs/3-state/non-modular-tests.md`. Work continues past that list, except in a refactor.

## Conversion (choice 3A)

`/house-rules:modular-tests convert <path>` splits one test file into modules and proves the old run
and the new runs report the same checks. First proof: `tools/verify_tools.py`. The two offshoot suites
(`claude-agent-router`, `claude-prompt-workshop`) each get one issue and are converted after.
`scripts/verify.py` of house-rules is already split into seven parts; it needs only the header lines.

## Build plan: steps, order and done-criteria

| Step | Depends on | Done when |
|---|---|---|
| 1. Rule text, detail file, `checks.json` entry | nothing | `verify.py` passes with the new section mapped |
| 2. `refactor on`/`off` typed switch | nothing | the switch is saved and read back by a `verify.py` case |
| 3. The write-time gate | 1, 2 | refuses and allows the cases in this doc, each as a `verify.py` case |
| 4. Skill, command and audit script | 1 | audit writes `docs/3-state/non-modular-tests.md` from this repo |
| 5. Convert `tools/verify_tools.py` | 4 | same checks, now `--parts`-selectable, `verify_tools.py` full run matches the old count |
| 6. Issues for the two offshoot suites | 5 | two issues exist, each naming its suite |
| 7. Docs, changelog, version | 1 to 5 | `CHANGELOG.md` line, this doc's status updated, plugin version bumped |
