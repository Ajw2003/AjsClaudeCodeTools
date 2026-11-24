# One self-judging test for what this machine cannot test

Use this only after the reviewer, in acceptance mode, says in its report under `docs/qa/<feature>/`
that something genuinely cannot be tested here: phone sensors, a GPU, aj's own accounts or logins,
another OS. Not before.

Why: aj should run one command and read one word. aj never judges a screenshot or ticks a list.

## Steps
1. Try the sandbox, a stand-in or a mock first. Record that attempt in the QA page.
2. Copy `templates/selftest/selftest.py` into the project. Put the checks in the marked block: each
   is a named function returning `(True/False, "one-line reason")`.
3. Run it here first against stand-ins. Paste its output into the QA page.
4. Hand it over as ONE step card, in the format of `output-styles/handover-cards.md`: the absolute
   folder path, the shell, the exact command that runs from anywhere, and what aj will see
   (`PASS name` lines, then `RESULT: PASS` or `RESULT: FAIL (n failed)`). A sample card: `templates/selftest/handover-card.md`.
5. If it was not run on aj's machine, put `UNTESTED:` as the first line above the fence.

## What it does
- Prints its first line with the machine facts it assumed (OS, python version).
- Prints one line per check, then one `RESULT:` line. Writes the same lines to
  `selftest-result.txt` beside the script.
- Exit code 0 pass, 1 fail, 2 cannot run (and it says exactly what is missing).
- Never asks a question and never waits for input.

## On the QA page
List it as ONE step in a "needs your machine" item. Never a pile of manual checks.
