# Review of the reviewer agent (code mode), 2026-11-24

Target: `claude-house-rules/plugins/house-rules/agents/reviewer.md`
Question asked: is Opus the right model for the reviewer, or would Sonnet or Haiku do with a marginal loss of quality?

Status: findings come from one `house-rules:reviewer` run. The main session re-checked the model settings (reviewer.md:4-5, `common.py:58`, and the other four agents' frontmatter) and the `waitfor.py` and `review-modes` lines (reviewer.md:9 and :20). The other findings are the reviewer's and were not re-run. No benchmark of Sonnet or Haiku was run, so every quality claim below is judgement, not evidence.

## Current setting

- `reviewer.md:4` is `model: opus`, `:5` is `effort: medium`.
- The Opus pin is enforced by `scripts/checks/common.py:58` (`TIERS`) and the `verify.py` pin check (`scripts/checks/delegation.py:749-775`). Nothing checks effort.
- The other agents: builder `sonnet`/`low`, scout `haiku`/`low`, archivist `sonnet`/`low`, editor `sonnet`/`low`. The reviewer is the only Opus agent and the only one at `medium`.
- Recorded reason for Opus: `docs/plans/issue-workflow-and-tiered-subagents-proposal.md:46` ("adversarial check of a finished diff, or a stuck build") and `docs/6-decisions/Decisions.md:2233-2235`. Both assumed rare, on-demand diff review. Neither gives a deeper reason.
- `effort: medium` has no recorded reason anywhere.

## Model verdict per mode (judgement)

| Mode | Verdict |
|---|---|
| page | Keep Opus. Last gate before aj approves; hunts holes and reversals against a 2,200-line Decisions.md; runs are rare. |
| plan | Sonnet is adequate. Mostly mechanical cross-checks. |
| acceptance | Sonnet is adequate. Long and tool-heavy, so Opus costs most here. |
| diff | Keep Opus for "builder failed twice" (the builder is Sonnet, so a Sonnet second opinion is weaker). Sonnet for routine second opinions. |
| code | Sonnet is adequate for most files; Opus helps on subtle logic bugs. |
| codebase | Strongest case for Sonnet. Breadth over depth, cost scales with repo size (measured about 4,400 tokens per file on Opus-era run, 71 s for 10 files). |
| image | Sonnet is adequate. "A doubt is a FAIL" already biases toward catching problems. |
| style | Sonnet is adequate. |

Haiku: not recommended for any mode. Its only precedent is scout (lookups). Adversarial reading and harsh visual judgement are where a small model misses things. There is no evidence either way.

Recommendation: keep Opus for page and the stuck-builder diff. Move the rest to a Sonnet variant. Because one agent file pins one model and the `TIERS` check flags a mismatch, this needs a second agent file (for example `reviewer-fast`) plus `TIERS` and pin-check entries. A per-spawn `model:` override alone would be flagged.

Measure before switching: run the same 8-file codebase batch and one page review on Sonnet and Opus, then compare findings, tokens and seconds.

## Findings on reviewer.md

1. [high] `agents/reviewer.md:9`: tells the agent to read the `review-modes.md` path from the spawn prompt, but `commands/review.md:27-30` and `:38-39` never pass that path. The five plan checks, lettered options, the `wording` tag and the visual-loop conventions are normally never read. (Confirmed in this very run: the spawn prompt did not carry the path.) Fix: put the absolute `${CLAUDE_PLUGIN_ROOT}/rules/detail/review-modes.md` in reviewer.md, or have both spawn steps pass it.
2. [medium] `reviewer.md:3`: description is stale ("second opinion... builder failed twice"). It is now also the design-loop gate and the engine of `/house-rules:review` (`docs/4-systems/review-loop.md:13-15`). Routing by description will under-use it.
3. [medium] `reviewer.md:20`: relative path `scripts/waitfor.py` resolves inside the user's project, not the plugin. Already reported by the 2026-11-24 sweep (`docs/qa/review-command/batch-measurement.md`) and still unfixed. Fix: `${CLAUDE_PLUGIN_ROOT}/scripts/waitfor.py`.
4. [medium] `docs/4-systems/hook-engine.md:177` lists the tools as "Read, Grep, Glob, Bash"; the file and `delegation.py:746` include `Write`.
5. [medium] `reviewer.md:13` limits writes to `docs/qa/<feature>/`; `review-loop.md:13` says "writes only under `docs/`".
6. [medium] `reviewer.md:6,13,19`: `Write` is granted in every mode but only acceptance needs it, and the write limit is prose, not enforced.
7. [low] `reviewer.md:11`: page mode output "before -> after" does not fit design findings with no before text.
8. [low] `reviewer.md:5`: `effort: medium` has no recorded reason or check; the others are `low`.
9. [low] `reviewer.md:11-18` copies `review-modes.md` almost line for line; only the mode list is kept in step.

## Not checked

- No Sonnet or Haiku benchmark was run.
- Whether the visual-loop skill gives a Bash-only reviewer a way to take screenshots in acceptance mode.
- Findings 2 and 4-9 were taken from the reviewer's report without a second read by the main session.
