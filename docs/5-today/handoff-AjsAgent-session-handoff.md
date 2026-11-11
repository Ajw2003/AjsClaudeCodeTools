# Handoff: AjsAgent/session-handoff

## What the work is for

Session handoff (issue #406): a session's work is saved as it happens and picked up by the next
session, whatever the Claude account or folder, so nothing is lost or left half done.

## Phase 1, 2026-11-11 (built, waiting on aj's QA)

Roadmap phase 1 (#493, "approvals and the design loop just work") is built on this branch as plugin 2.78.0,
steps #501 to #507, after the build plan was approved as "Build plan approved: Phase 1 1A 2A". The session that
started it on aj's PC was cut off by an account switch before any code was written; a cloud session built all
seven steps on 2026-11-11. `verify.py` 1135/1135 PASS, `tools/verify_tools.py` 52/52 PASS. What each step does is
in `docs/3-state/ProjectState.md` and `docs/4-systems/design-loop.md`. Next: aj's QA from the phase 1 QA page;
the usage-handoff QA below is still owed too.

## Where it stood on 2026-11-09 (usage handoff)

All six steps are built and merged on this branch, plugin 2.77.0: #486 automatic save, #487 save at
turn end and on a usage-limit stop, #407 end-of-reply check, #408 pickup, #409 quoted approvals,
#410 rule text, docs and version. `verify.py` shows only the 7 failures `main` already has (1080
checks). A real run against GitHub on 2026-11-08 saved an uncommitted `docs/5-today/Today.md`, and a
fresh clone's pickup listed it, and its restore command brought back an identical file.

## Desktop app QA, 2026-11-09 (failed on the restore)

Two desktop sessions ran in fresh clones on `AjsAgent/session-handoff-qa`, using each clone's own
hooks through `.claude/settings.local.json`. Session A's uncommitted edit reached GitHub (snapshot
e724bf2, with its facts file). Session B opened with the pickup, and its snapshot copy of `Today.md`
matched A's file apart from Windows line endings. The restore command the pickup prints is refused
twice. It names `.claude/house-rules-loop.json`, which the design-loop guard blocks, and the main
guard blocks any `git restore`. The fix needs a code change, and code is locked in QA. Also seen:
the desktop app's synced copy of the plugin (2.76.0) still ran alongside, even though the clone's
settings turned it off.

## Next step

aj's QA: install 2.77.0 from this branch, then run the two-account test from the QA page
(`docs/plans/2026-11-08-session-handoff-qa.html`). After QA passes, a pull request to `main`.

## Unverified

- A second Claude account picking the work up. Live headless sessions (`claude -p --plugin-dir`, this
  branch, same account) did run on 2026-11-08: an edit in one fresh clone was saved to GitHub
  (ref 3111948), the end-of-reply check fired, and a session in a second fresh clone opened with the
  pickup listing that file and its restore command.
- A turn actually cut off by a usage limit (`StopFailure`); only replayed payloads have run.
- `tools/verify_tools.py` check A16 fails here and on a clean `main` alike (1 of 52, checked
  2026-11-08), so it is not caused by this work.

## Issues

#406 (parent), #486, #487, #407, #408, #409, #410. Phase 1: #493 (parent), #501 to #507.
