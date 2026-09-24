<!-- plain copy of: docs/systems/hook-engine.md @ c0c6dc86556037e9917334bb2dcf3dbc76189bf5 -->

# The hook engine, in plain English

Full technical doc: [hook-engine.md](../../systems/hook-engine.md)

**What it is.** Makes the rules actually happen. Claude Code lets a plugin step in at set moments,
called hooks, such as when a session starts or before a command runs. The hook engine runs the
right check at each one.

**Why it matters.** If it breaks, the rules become words nobody enforces. Risky commands go
unchallenged and reminders never reach Claude.

**How it works.**

1. Every hook runs one small starter script, which finds a working copy of Python (the plugin's
   language) by test-running it.
2. The starter hands over to one main program, which picks the check for that moment.
3. At session start, it loads the rules, the machine's details and the project's coding standards.
4. On every message, it repeats a short reminder.
5. Before a risky command or a full file overwrite, it asks you first.
6. After work is done, it checks it and flags anything missed.

**Risks and safeguards.**

- **Hooks quietly stop running.** Python is test-run, not just looked for. Some Windows machines
  have a fake one that does nothing.
- **A broken check blocking you.** Each check fails in a fixed way. The command check blocks when
  unsure. The reminder can't fail, since that would erase your message. The rest carry on and
  say what went wrong.
- **Errors nobody hears about.** The tests fail if any error is quietly swallowed, and a last
  safety net catches the rest.
- **Leftover files between sessions.** No check stores anything, and the tests enforce it.
- **The terminal freezing.** The current branch (git's name for a line of work) is read from one
  file instead of running git, which can hang.
- **Guessing whose branch it is.** Any doubt counts as "not Claude's", so you get asked.
- **A risky command slipping through.** Commands are matched on their text, so it sometimes asks
  needlessly rather than miss one.
- **A file replaced by mistake.** Any full overwrite of an existing file asks first, however small.
- **Big files timing out.** The long-comment check is fast enough to finish on large files.
- **Unity game projects missed.** One opened at its Assets folder is still recognised.
- **Extra installs breaking it.** Only Python's built-in parts are used.

**Related.**

- **Verify suites.** Proves the checks do what the docs say.
  [verify-suites.md](../../systems/verify-suites.md) *(no plain copy yet)*
- **Plugin distribution.** Gets the plugin onto a machine and keeps it updated.
  [plugin-distribution.md](../../systems/plugin-distribution.md) *(no plain copy yet)*

**Left out**, see the full doc: the full list of moments and checks, file and line references,
how commands are tidied for display, past bugs and how tests avoid depending on your setup, and
the reasoning behind each design, which lives in the architecture doc.
