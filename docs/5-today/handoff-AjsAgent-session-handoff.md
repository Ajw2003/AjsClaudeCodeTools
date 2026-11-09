# Handoff: AjsAgent/session-handoff

## What the work is for

Session handoff (issue #406): a session's work is saved as it happens and picked up by the next
session, whatever the Claude account or folder, so nothing is lost or left half done.

## Where it stands

All six steps are built and merged on this branch, plugin 2.77.0: #486 automatic save, #487 save at
turn end and on a usage-limit stop, #407 end-of-reply check, #408 pickup, #409 quoted approvals,
#410 rule text, docs and version. `verify.py` shows only the 7 failures `main` already has (1080
checks). A real run against GitHub on 2026-11-08 saved an uncommitted `docs/5-today/Today.md`, and a
fresh clone's pickup listed it, and its restore command brought back an identical file.

## Next step

aj's QA: install 2.77.0 from this branch, then run the two-account test from the QA page
(`docs/plans/2026-11-08-session-handoff-qa.html`). After QA passes, a pull request to `main`.

## Unverified

- The hooks firing inside a live Claude Code session (this session runs the installed plugin, not
  this branch).
- A second Claude account picking the work up.
- `tools/verify_tools.py` check A16 fails here; not yet compared with `main`.

## Issues

#406 (parent), #486, #487, #407, #408, #409, #410.
