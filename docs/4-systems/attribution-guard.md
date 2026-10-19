# Attribution guard on GitHub

## What it owns

Making sure no repo aj owns ever carries Claude credit on its default branch: no commit authored or
committed as Claude, no `Co-Authored-By`, `Claude-Session` or "Generated with Claude Code" line, and
no claude.ai link. Design `docs/plans/2026-10-19-attribution-guard.html`, approved 2026-10-19
("Design approved: attribution guard 1A 2A"); aj's earlier answers are in
`docs/6-decisions/Decisions.md`, 2026-10-19. Status: planned, not built.

The in-session hook (`guardgithub` and `guard`, `_ATTRIBUTION_TEXT_RES` in `hook.py`) already refuses
Claude credit in what a session writes. Two routes get past it: the claude.ai server appends its
footer to a pull request description after the request is made, and merges are not checked at all.
This system closes both, on GitHub itself and in the hook.

## How it works

| Piece | Where | What it does |
|---|---|---|
| Patterns | `rules/attribution-patterns.json` | The one list of text patterns plus the author rule (name "Claude", or an email ending in `anthropic.com`). `hook.py` and the workflow both read it, so they cannot drift. |
| Check | `.github/workflows/attribution-guard.yml` in AjsClaudeCodeTools, job `check` | Runs on `pull_request_target`, so it always runs the default branch's copy and a pull request cannot edit it to pass. Reads every commit's author, committer and message, the title and the description through the API; it never checks out the pull request's code. Fails on any match. |
| Cleanup | same workflow, job `cleanup` | On a description or comment being posted or edited, removes each line that matches a pattern. GitHub keeps the edit record, so nothing is hidden. |
| Audit | same workflow, job `audit` | On a push to the default branch, checks every pushed commit. A match opens an issue in that repo naming the commit and the line. History is never rewritten (aj, 2026-10-19). |
| Caller | `.github/workflows/attribution-guard.yml` in each repo | A few lines that call the shared workflow, so a pattern fix reaches every repo at once. |
| Ruleset | each public repo's default branch | Makes the check required, pinned to the GitHub Actions app, with an empty bypass list. GitHub Free cannot enforce rulesets on private repos. |
| Merge gate | `hook.py` `guard` and `guardgithub` | Refuses a merge (`merge_pull_request`, `gh pr merge`) unless the `attribution-guard / check` run on the pull request's head commit concluded `success`, and checks the merge message. Reads the result with `gh api`; if it cannot read it, the merge is refused, never asked, so an unattended run is never parked on a prompt. Direct pushes to a default branch are already refused by `guard`. |
| Install | `tools/attribution_guard_install.py` | Adds the caller to all 71 repos aj owns (forks included, 1B), and the ruleset to the public ones. `--dry-run` lists what it would change. Merge settings are left alone (no squash, aj 2026-10-19). |

## The one gap

On a private repo, aj clicking Merge in the GitHub website is not stopped: GitHub Free gives no outside
tool a way to block its own merge button. aj chose to let the audit record it (choice 1A). Moving to
GitHub Pro would close it, by letting the ruleset apply to private repos.
