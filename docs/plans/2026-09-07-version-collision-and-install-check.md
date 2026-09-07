# Bump off the collided 2.4.0, and make a stale install detectable

## Context

Two different code states shipped under **the same version number**:

- PR #12 merged first, publishing `2.4.0` — the card defects, the forced output style, and the two
  missing surfaces.
- PR #13 merged after, adding the `Stop` hook firing condition, **with no version bump**, because
  the commit reasoned "2.4.0 has never been installed anywhere". That was true when it was written
  and false by the time it merged, since #12 went in first. `main` then carried the firing change
  while still reporting `2.4.0`.

Whether that actually blocks `claude plugin update` is **unresolved, and was not guessed at**. The
evidence cuts both ways: the plugin cache is version-keyed
(`~/.claude/plugins/cache/aj-house-rules/house-rules/<version>/`), which leaves a same-version
change nowhere new to land; but `installed_plugins.json` also records a `gitCommitSha`, so the
updater may compare commits instead. The message observed in practice — `already at the latest
version (2.3.1)` — is phrased by version.

The deeper problem is that **nothing in the repo would have caught it**. `clean_install_test.py`
checks the installed SHA against remote, but it *strips the cache first*, so a fresh install is
guaranteed and always looks correct. The one mode that inspects what is really on the machine,
`--skip-strip`, did not compare content at all.

Outcome wanted: the version is unambiguous again, and a stale install is something the repo can
detect rather than something a person has to suspect.

## Changes

### 1. Version → 2.5.0

`claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json`, `2.4.0` → `2.5.0`.

Minor, not patch: the change alters **when a hook fires** and swaps its output shape, which is
user-visible behaviour on every device — the same bar that made forcing the output style a minor
bump. It also cleanly separates "the 2.4.0 that shipped in #12" from "the 2.4.0 that shipped in
#13", which is the defect being corrected.

### 2. `tools/clean_install_test.py` — compare installed content against the repo

A new step, *"Does the installed copy match the repo, byte for byte?"*, placed after the existing
*"Did the install land on the commit that is actually on GitHub?"* check and before *"Does the
installed copy contain every file the hooks need?"*, reusing that step's `install_path` and the
file's existing `step` / `ok` / `bad` / `info` helpers.

It walks the repo's `claude-house-rules/plugins/house-rules/` and byte-compares every shipped file
against the same relative path under `install_path`. Skips `rules/environment.md` (gitignored and
machine-local, so the installed copy legitimately lacks it), `__pycache__/`, and `*.pyc`.

It then reports the version recorded in `installed_plugins.json` against the version in the repo's
`plugin.json`. **Equal versions with differing content** is precisely this bug, and the step says
so in those words — which is what turns the failure from a mystery into a diagnosis.

**Why this catches it and the SHA check does not:** the SHA check runs after a strip, when the
cache has been deleted and a fresh clone is guaranteed. Content comparison under `--skip-strip`
inspects the copy the machine is actually running, which is where a stale install lives.

### 3. `docs/desktop-verification.md` — a version-independent landed check

§0 proved an update by the version number the CLI reports, which is exactly the signal this
incident showed can lie. A direct check now sits alongside it: grep the **installed** copy for a
marker from the newest change (`_reply_hands_over_a_command`) rather than trusting the reported
version. Marked `UNTESTED:`, since it has not been run on that machine.

A dated finding records the collision, what remains unverified about it, and that the cache is
version-keyed.

### 4. `CLAUDE.md` — one line under `tools/`

Notes that `clean_install_test.py` byte-compares the installed copy against the repo, and that
`--skip-strip` is the mode that catches a stale install, because a strip deletes the cache and
therefore guarantees a fresh clone.

## Not done, deliberately

No `verify.py` change. It tests hook behaviour from the repo and knows nothing about what is
installed; that separation is worth preserving rather than blurring.

## Verification

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

95 checks passing, count unchanged — nothing here touches hook behaviour, so a changed count would
itself be a defect.

`tools/clean_install_test.py` was checked for syntax only. It is **not** run here: it touches the
real plugin install.

The check is only proven once it has been seen to **fail**. On a machine whose plugin predates the
change, `python tools/clean_install_test.py --skip-strip` should report mismatches, and report
clean after `claude plugin marketplace update` + `claude plugin update` + a restart. A check that
has only ever passed has not been tested.

## Open

Whether `claude plugin update` would have shipped #13's code under the unchanged 2.4.0. Answerable
only on the desktop, via the §0 grep. 2.5.0 makes it moot for this release and the content
comparison makes a repeat detectable, so it does not block — but until someone looks, the honest
answer is "unverified".
