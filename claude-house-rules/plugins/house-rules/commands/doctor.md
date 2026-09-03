---
description: Diagnose why house-rules hooks aren't running, and propose the fix for this machine
---

The house-rules plugin needs two things on this machine: POSIX `sh` (to run `run.sh`, the hook
shim) and a working Python 3 interpreter (to run `hook.py`, where every handler lives). If
either is missing or unreachable, hooks silently do nothing or fail — this command finds out
which, and gives you the exact install command for the OS you're actually on.

Do the following, in order:

1. **Detect the OS.** Run a command appropriate to find out (e.g. `python3 -c "import
   platform; print(platform.system())"` if Python is reachable at all, or an OS-native check
   otherwise — `ver` on Windows, `uname -s` on Linux/macOS).

2. **Check for a working Python interpreter**, using the same probe `run.sh` uses — actually
   run each candidate and check its output, never just `command -v`:

   ```sh
   [ "$(python3 -c 'print(9)' 2>/dev/null)" = 9 ] && echo python3 works
   [ "$(python -c 'print(9)' 2>/dev/null)" = 9 ] && echo python works
   ```

   A candidate that is "found" by `command -v`/`Get-Command` but does not print `9` (for
   example the Windows Store App Execution Alias stub for `python3`) is **not working** — say
   so explicitly, do not report it as fine.

3. **Check for `sh`** (POSIX shell). On Windows this means Git for Windows; check for
   `C:\Program Files\Git\bin\sh.exe`. On macOS/Linux, `sh` is normally always present — flag it
   as unusual if it is not.

4. **Check for `git`** on PATH — needed for the plugin install/update commands themselves.

5. **For each gap found**, propose exactly **one command**, matched to the detected OS, and run
   it only after the user approves (the normal Bash/PowerShell permission prompt covers this —
   do not bypass it):

   | Gap | OS | Command |
   |---|---|---|
   | No working Python | Windows | `winget install Python.Python.3.12` |
   | No working Python | macOS | `brew install python` |
   | No working Python | Debian/Ubuntu | `apt install python3` |
   | No working Python | Fedora/RHEL | `dnf install python3` |
   | No `sh` | Windows | Direct the user to install Git for Windows (`winget install Git.Git`) — this also brings `sh`, `grep`, `bash`. |
   | No `sh` | macOS/Linux | Extremely unlikely; say so and ask before proposing anything. |
   | No `git` | Windows | `winget install Git.Git` |
   | No `git` | macOS | `brew install git` |
   | No `git` | Debian/Ubuntu | `apt install git` |
   | No `git` | Fedora/RHEL | `dnf install git` |

   If `HOUSE_RULES_PYTHON` is set but does not probe successfully, say so specifically — that
   overrides the resolution order, and getting it wrong is a common mistake that isn't fixed by
   installing anything.

6. **Report a one-line summary** at the end: either "this machine has everything the plugin
   needs" or the exact gap(s) found and whether they were fixed.

Follow the house rules while doing this: one command per gap, exact and copy-pasteable, run in
the shell the user actually has, confirmed before running anything that installs software.
