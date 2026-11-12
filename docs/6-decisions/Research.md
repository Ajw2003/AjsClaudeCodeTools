# Research

What was looked into, what was found, and where it came from. Newest first. A finding that turns out
wrong gets a dated note under it, never a silent edit. Decisions that rest on these entries are in
[Decisions.md](Decisions.md).

## 2026-11-12 - Can a cloud session push the handoff's save refs?

**Why it mattered.** The session handoff (#406) saves work to `refs/house-rules/autosave/<branch>` on GitHub, and phase 3
depends on picking that save up from any account.

**Found.** No. From this cloud session, `git push origin <ref>:refs/house-rules/autosave/AjsAgent/handoff-qa-2` fails
every time with "send-pack: unexpected disconnect" and "the remote end hung up" (4 tries with backoff; the network
proxy listed no failure of its own), while pushing a branch from the same clone works. Every save ref already on
GitHub was made in aj's PC's time zone (-0700): 2026-11-08, 2026-11-09 and 2026-11-11. So the save works from a
session on aj's PC and not from a cloud session.

**Source.** The pushes and `git ls-remote`, run 2026-11-12 in this repo's cloud session
(`docs/plans/2026-11-12-handoff-retest/live_handoff-result.txt`).

## 2026-11-11 - Does context from a PreToolUse hook reach Claude without a permission decision?

**Why it mattered.** The pull request changelog reminder (#509) first went out with an "allow" decision, because a
code comment said context only reaches the model on "allow". That skipped Claude Code's own permission prompt.

**Found.** It does reach the model without a decision. A throwaway plugin whose PreToolUse hook on Bash returned only
`additionalContext` ("The code word is PELICAN-73.") was run in a headless session (`claude -p`, Claude Code 2.1.322);
the session repeated the code word back. The reminder now carries no decision.

**Source.** The live probe, run in this repo's cloud session; the setup is in the 2026-11-11 phase 2 work
(`docs/3-state/ProjectState.md`, step 2 checks).

## 2026-11-11 - Which GitHub calls work from a Claude Code cloud session?

**Found.**
- `gh issue list` and `gh pr view` are refused with HTTP 403: "GitHub GraphQL is not available from Claude Code
  sessions; use the REST API". The plugin's issue read (#503) and pull request body read (#510) now use
  `gh api repos/<owner>/<repo>/...` (REST), which works: #493 and #501 to #507 came back in 0.7 s.
- `gh api /users/<login>/settings/billing/usage` is refused: "sessions are bound to their configured repositories".
  So the LFS allowance check (#511) cannot read the account's usage in the cloud and falls back to this repo's files.
- `docs.github.com` does not resolve from the session's network, so GitHub's docs had to be read through a web search.

**Source.** The calls themselves, run 2026-11-11 in this repo's cloud session.

## 2026-11-11 - How much Git LFS does a free GitHub account get?

**Found.** 10 GiB of LFS storage and 10 GiB of LFS download bandwidth a month for a free personal account; unused
bandwidth does not roll over. Past that, use is billed per GiB when a payment method is on file (quoted as $0.07 per
GiB stored and $0.0875 per GiB downloaded) rather than blocked. Older help pages still say 1 GB; they are out of date.

**Source.** A web search of GitHub's billing docs on 2026-11-11, because the docs host could not be opened directly:
[About billing for Git Large File Storage](https://docs.github.com/en/billing/using-the-new-billing-platform/about-billing-for-git-large-file-storage),
[Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

## 2026-11-11 - Can the plugin be tried from a branch without merging to main?

**Found.** Yes. In an empty Claude config, `claude plugin marketplace add
'https://github.com/Ajw2003/AjsClaudeCodeTools.git#AjsAgent/session-handoff'` then `claude plugin install
house-rules@aj-house-rules` installed 2.78.0; adding the plain repository URL back and reinstalling gave 2.76.0.

**Source.** The commands, run 2026-11-11 (`docs/plans/2026-11-11-phase-1-live-tests/README.md`).
