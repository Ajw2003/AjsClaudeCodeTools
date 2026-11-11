# Phase 1 live tests (2026-11-11)

Run in a cloud session against plugin 2.78.0 on `AjsAgent/session-handoff`, with the installed 2.76.0 switched off
for every test session (`--settings '{"enabledPlugins":{"house-rules@aj-house-rules":false}}'`), so only this
branch's hooks ran.

- `live_loop.py <empty folder>`: 14 real headless sessions (`claude -p --plugin-dir`) walk a throwaway repo through
  the whole design loop. GitHub is replaced by the plugin's stand-in files. Result: 14 of 14
  (`live_loop-result.txt`).
- `live_branches.py <empty folder>`: the real scope and commitgate hooks with real `git checkout` and `git merge`,
  for the branch hold (D9) and a merged feature on main (U3). Result: 6 of 6.
- `hook_timing.py <empty folder>`: the hooks phase 1 touches, timed five times each against 2.76.0 on a fresh clone of
  this branch. Result: the same speed (handover 0.79 s against 0.82 s, the rest 0.05 to 0.06 s), every exit code 0.

Also run by hand: in an empty Claude config, `claude plugin marketplace add
'https://github.com/Ajw2003/AjsClaudeCodeTools.git#AjsAgent/session-handoff'` then `claude plugin install
house-rules@aj-house-rules` installed 2.78.0; adding the plain repository URL back and reinstalling gave 2.76.0.
