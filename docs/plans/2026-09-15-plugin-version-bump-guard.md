# Plan: stop a silent "already up to date" from ever shipping unbumped content again

## Incident (context, already resolved — see #33, #34, #35)

Two merged PRs (#33, #34) changed the house-rules plugin's shipped files without bumping
`claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json`'s `version` field. Every
prior content-changing commit had bumped it; nothing enforced the convention, so it silently
lapsed. The result: `claude plugin update` — which is version-gated — reported "already at the
latest version" on this desktop after a full `tools/bootstrap.ps1` run, while the installed
cache still held the pre-#33/#34 content. `python tools/force_update.py` (a pre-existing manual
escape hatch that hash-verifies the installed cache against source) confirmed the mismatch and,
once run, confirmed the fix. #35 bumped the version and the next `force_update.py` run confirmed
the cache now matches source file-for-file.

This is not a one-off typo to shrug off. The user's direction: (1) no merge to `main` should ever
be possible again without a version bump when it's needed, enforced as a hard GitHub
branch-protection block — this repo currently has **zero** branch protection on `main`, confirmed
via `gh api repos/Ajw2003/AjsClaudeCodeTools/branches/main/protection` (404, "Branch not
protected"); (2) the broader failure mode — a tool reporting success/no-op without the underlying
artifact actually being verified to match — should never be allowed to happen silently again, in
this repo or any other project this plugin's rules reach.

Two separable fixes, matching the two places this actually failed:

## A. This repo: block merging plugin-file changes without a version bump

1. **New script `tools/check_plugin_version_bump.py`.** Structure it like the rest of `tools/` —
   a thin `main()` that shells out to `git`, calling into pure, independently-testable functions:
   - `changed_paths(base, head="HEAD")` — `git diff --name-only <base>...<head>`, returns a list.
   - `plugin_version_at(ref, path="claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json")`
     — `git show <ref>:<path>`, parse JSON, return the `version` string (raise a named exception,
     not a bare one, if the ref/path/JSON is bad — this must fail loud, not silently return `None`
     and let a caller treat that as "no plugin files at that ref").
   - `decide(changed, old_version, new_version) -> (ok: bool, message: str)` — the actual policy,
     with zero I/O, so `tools/verify_tools.py` can test it directly without touching git:
     - No path under `claude-house-rules/plugins/house-rules/` in `changed` → `(True, "no plugin
       files changed, no bump required")`.
     - A path changed, and `old_version == new_version` → `(False, "<file list> changed under the
       plugin, but plugin.json's version is still <old_version> - bump it")`.
     - A path changed, versions differ, but `new_version` does not semver-compare strictly greater
       than `old_version` (parse both as `(major, minor, patch)` tuples; anything unparseable is a
       failure, named) → `(False, "...moved from X to Y, which is not an increase")`.
     - A path changed and the new version is strictly greater → `(True, "...bumped from X to Y")`.
   - `main()` reads `--base` (default `origin/main`) and `--head` (default `HEAD`) args, calls the
     three functions above, prints the message, and exits 0/1 on `ok`. Every branch prints
     something — no silent exit.
2. **Wire it into CI as a new step in the existing `verify` job**, not a new job — one required
   check name (`verify`) is simpler to make required than two, and this repo already has zero
   branch protection to build on top of.
   - `.github/workflows/verify.yml`: change the `actions/checkout@v4` step to `fetch-depth: 0`
     (the default shallow clone has no history to diff against — `check_plugin_version_bump.py`
     needs `origin/main` reachable).
   - Add a step, gated `if: github.event_name == 'pull_request'` (a push to `main` only happens
     via an already-checked PR merge, so re-checking on push is redundant noise, not a gap):
     `python tools/check_plugin_version_bump.py --base ${{ github.event.pull_request.base.sha }}`.
3. **Turn on branch protection for `main`** — user confirmed: hard block, not an
   admin-overridable warning. This is a `gh api` call, not a repo file, so it does **not** go
   through the executor delegation below — run it directly, after the PR below merges (so the
   `verify` check has actually run successfully on this repo's real history at least once before
   the rule requires it):
   `gh api repos/Ajw2003/AjsClaudeCodeTools/branches/main/protection -X PUT -F
   required_status_checks[strict]=true -F 'required_status_checks[contexts][]=verify' -F
   enforce_admins=true -F required_pull_request_reviews=null -F restrictions=null` — read GitHub's
   actual branch-protection API docs first (`gh api` payload shape is picky about nested arrays;
   verify the exact working form by testing against this repo, not by guessing the flag syntax).
   Confirm afterward with a read (`gh api repos/Ajw2003/AjsClaudeCodeTools/branches/main/protection`)
   showing `required_status_checks.contexts` containing `"verify"`.

## B. Any project: a reported update is not evidence it happened

New rule in `claude-house-rules/plugins/house-rules/rules/house-rules.md`, text-only (no hook
mirrors this — like its two neighbors below, it's a verification habit, not something
mechanically checkable at a `PreToolUse`/`PostToolUse` boundary). Place it directly after "A shim
that compiles is not proof the real code does" (which ends around line 301) and before "Never
hand over a command I have not run" (line 303) — it belongs with the other two "a passing signal
is not proof" rules, in the same voice and length as its neighbors.

Working title: **"A reported update is not a completed one."** Content to cover (write it in the
house voice, don't just concatenate these bullets):

- A tool reporting "already up to date," "already installed," "success," or a version/status
  string is reporting what it compared, not what the reader needs to know. It can be accurate
  about its own check and still wrong about whether anything actually changed, if the thing it
  compared (a version number, a hash, a timestamp) didn't move for a reason unrelated to whether
  new content exists.
- Before believing an install, update, sync, or deploy took effect, verify the actual target
  changed — diff the content, compare a hash, read the file — rather than trusting the tool's own
  status message.
- **Why:** cite this incident by shape, not by PR number (PR numbers won't mean anything to a
  future reader in a different repo): a plugin's `claude plugin update` reported "already at the
  latest version" after the source had genuinely changed, because the one field it compared
  (a version string) hadn't moved. The message was true about what it checked and false about
  what the reader needed to know.

## C. Local tooling: `tools/install.py` verifies instead of trusting the CLI's own message

`tools/force_update.py` already does the right check (hash-compares the installed cache against
the marketplace source tree, `tree_hash()`) but only runs when someone remembers to invoke it by
name — exactly the "opt-in verification" shape that let this slip through `tools/bootstrap.ps1`
in the first place.

1. **Factor `tree_hash()` out of `tools/force_update.py`** into a small shared module (e.g.
   `tools/_plugin_sync.py`) so `install.py` and `force_update.py` both import one implementation
   instead of risking two copies drifting — this repo already treats that kind of drift as a
   tested failure mode elsewhere (`verify.py`'s literal-drift checks), so don't reintroduce the
   pattern here.
2. **`tools/install.py`'s `install_steps()`**: after the existing four `claude plugin` commands
   succeed, add a step that hash-compares the installed cache directory against the marketplace
   source tree (same comparison `force_update.py` already makes). On mismatch:
   - Automatically run the uninstall+reinstall sequence `force_update.py` already uses (don't
     just print a suggestion to run a different script by hand — "the user's hands are for
     decisions, not labour").
   - Re-verify the hash match after that.
   - If it still mismatches, fail the step loudly, print exactly which paths differ (source-only /
     cache-only / differs, same as `force_update.py`'s existing output shape), and point at
     `tools/force_update.py` for manual investigation — this is the one case worth surfacing to a
     human, since automatic recovery already failed once.
   - If the first hash-compare already matched, say so plainly and move on — no reinstall needed.
3. Keep `tools/force_update.py` as the standalone manual entry point (useful mid-iteration on a
   branch, per its own docstring), now built on the shared `tree_hash()`.

## D. Record the decision

`docs/6-decisions/Decisions.md` (tier 6): a dated entry recording why the version-bump gate and the
install.py self-verification exist — that "the version-gated `claude plugin update` reporting
success was trusted without checking" was the actual failure, not just "forgot to bump a number,"
and that the fix is enforcement (branch protection + automatic hash-verification) rather than a
reminder to remember next time. Follow the existing entries in that file for format/length.

## Tests

- `tools/verify_tools.py`:
  - New cases exercising `check_plugin_version_bump.py`'s `decide()` directly (no git, no
    subprocess) — no plugin files changed; plugin files changed with an unmoved version; changed
    with an increased version; changed with a decreased/invalid version.
  - A real end-to-end case using a throwaway git fixture repo (`tempfile.mkdtemp`, `git init`,
    two commits) exercising `changed_paths()` and `plugin_version_at()` against actual git, since
    the pure-function tests above don't touch the git-shelling code at all — this repo's own
    testing rule ("against the mechanism, not my model of it") applies here specifically because
    the original bug was a mismatch between "the version string as I assumed it behaved" and how
    `claude plugin update` actually gates.
  - New cases for `install.py`'s new hash-verify-and-self-heal step: feed it a fake source tree
    and a fake "installed" tree that already match (expect no reinstall attempted) and ones that
    differ (expect the self-heal path is taken) — mock or stub the actual `claude` subprocess
    calls (follow whatever mocking pattern `verify_tools.py` already uses for testing `install.py`
    today, since it already imports and exercises that module).
- `claude-house-rules/plugins/house-rules/scripts/verify.py`: one straightforward presence check
  that `house-rules.md` contains the new rule's title text — matching the style of other
  rule-presence assertions already in this file, not a drift check (nothing else restates this
  rule's wording elsewhere).

## Steps, in order

1. Do the design work above (already decided; the executor should not re-derive it).
2. Write `tools/_plugin_sync.py`, `tools/check_plugin_version_bump.py`, update
   `tools/force_update.py` to import the shared function, update `tools/install.py`'s
   `install_steps()`.
3. Add the new house rule to `house-rules.md`.
4. Update `.github/workflows/verify.yml` (`fetch-depth: 0` plus the new conditional step).
5. Add the tests described above to `tools/verify_tools.py` and `verify.py`.
6. **Bump `plugin.json`'s version** (this PR itself changes plugin-shipped files — `house-rules.md`
   — so it must bump the version to pass its own new check; that's the natural first real test of
   the mechanism).
7. Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` and
   `python tools/verify_tools.py` — both must be 0 failures.
8. Run `python tools/check_plugin_version_bump.py --base origin/main` against this branch's real
   diff, by hand, as a final integration sanity check before committing — it should report success
   given step 6.
9. Commit (scoped to changed paths), on an isolated worktree (`isolation: "worktree"` on this
   delegation, per the rule this plugin now mandates for multi-file work) — do not push or open
   the PR; that happens from the main session so branch protection setup (step A.3 above, run
   directly, not delegated) can follow the merge in the same flow the user is already watching.

## What happens after the executor reports back

Main session: push the branch, open the PR, wait for CI (which now includes the new
version-bump-gate step and must pass, having verified locally already), merge, then apply the
branch-protection API call (A.3) and confirm it stuck by reading it back. Then re-run
`tools/force_update.py` on this desktop one more time as the final end-to-end proof that the
whole chain — repo gate, local tooling, and the actual installed plugin — is consistent.
