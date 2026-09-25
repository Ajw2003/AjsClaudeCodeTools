# Today — 2026-09-24 (session 3)

Fixed `versioncheck` staying silent to the model when it could not reach GitHub — the reason a
session ran on house-rules 2.31.0 while GitHub had 2.33.0 and nobody was told. See the dated
entry in [`Decisions.md`](../6-decisions/Decisions.md).

## What was done

- **API fallback.** `_github_version()` in `hook.py` tries `raw.githubusercontent.com`, then the
  `api.github.com` contents endpoint derived from the same owner/repo/path, in one 4 s budget.
  `HOUSE_RULES_VC_GITHUB_API_URL` overrides the derived URL.
- **Model-visible "couldn't verify".** If the check can't finish and finds no mismatch, it emits
  `additionalContext` naming each failed route and the installed version. No banner, no marker.
- **Tests.** Three new `verify.py` cases (raw fails + API newer → banner; both fail →
  `additionalContext`, no marker; all agree → no `additionalContext`), using `file://` URLs.
  The first two fail against the previous `hook.py`.
- **Docs.** `docs/architecture.md` (row and section), `claude-house-rules/README.md`,
  `Decisions.md`.
- **Version bump.** `2.34.0` → `2.35.0` in `plugin.json`.
- **Verified against the real network.** Default run: raw route answered, `2.34.0` matched.
  Raw forced dead: the real `api.github.com` answered `2.34.0`. Both routes blocked via a dead
  proxy: the `additionalContext` notice named both `Connection refused` failures.

## What to do next, in order

1. Run `/house-rules:plain-docs` on the remaining system docs (`verify-suites.md`,
   `plugin-distribution.md`, `offshoot-plugins.md`) — unchanged from before this session, still
   open.
2. Everything still open in [`ProjectState.md`](../3-state/ProjectState.md)'s Cross-cutting
   section — none of it was touched by this plan.
