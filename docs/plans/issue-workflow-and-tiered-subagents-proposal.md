# Proposal: mandatory issue workflow, and tiered runtime subagents

STATUS: proposal, awaiting approval. Nothing here is built. Related open issues: #94, #103, #105 (this proposal is the design for all three).

## Part 1. Issues as the tracked workflow

### The rule (goes in `rules/house-rules.md`, about 80 words; detail in `rules/detail/issue-workflow.md`)

A plan of more than 3 steps becomes GitHub issues before any work starts. One tracking issue holds the plan as a task list; each chunk of 3 steps or fewer that can ship on its own becomes a child issue. Work discovered mid-task becomes a new issue, not a silent addition. I comment progress on the issue I am working. Every PR links its issues. I never close an issue until the user has tested and said so.

### Design decisions that need your eyes

1. **Hooks never create issues themselves; they force me to.** This keeps the issue-forge rule ("a hook never runs `gh issue create`") intact. The hook blocks or reminds; I run `gh`. Approving a plan with ExitPlanMode is the explicit chat approval for creating that plan's issues, so each creation is covered without a per-issue prompt. This is a reversal of nothing, but issue-forge's `rules/issue-forge.md` hard rule needs a line saying the house-rules workflow is the approved exception path; log it in `docs/6-decisions/Decisions.md`.
2. **PRs use `Refs #N`, never `Closes/Fixes/Resolves #N`.** GitHub auto-closes on those keywords at merge, which would close an issue before you have tested. A guard rejects the closing keywords.
3. **Closing is gated by your own approval click, not by me reading chat.** A hook cannot see whether you said "tested, close it". So `gh issue close` returns `permissionDecision: "ask"`: the UI prompt that appears is your go-ahead. After the PR merges and you approve, I close with a comment linking the PR.
4. **GitHub is the source of truth, no local ledger.** Issues I open carry label `claude-tracked` and a body marker `<!-- house-rules:issue plan=<id> -->` (same pattern as issue-forge's dedup marker). A small cache file in `.git/` (60 s TTL) avoids a network call on every turn.

### Hook mechanics (all inside the existing handlers; no new processes)

| When | Handler | What it does |
|---|---|---|
| SessionStart | extend `inject` | Lists open `claude-tracked` issues (max 10 titles, about 200 tokens), so your new issues steer the next pickup. |
| PostToolUse ExitPlanMode | extend `delegate` | If the plan has more than 3 steps, inject: create the tracking issue and child issues now, show me the numbers. Sets a `plan-needs-issues` flag in `.git/`. |
| PreToolUse Write/Edit | `commitgate` path | While the flag is set, deny source edits (docs and plan files allowed) until the issues exist. Clears when `gh issue list` shows the plan marker. |
| PreToolUse Bash `gh pr create` | `guard` | Deny unless the body has `Refs #N` for an open tracked issue. Deny if it has a closing keyword. |
| PreToolUse Bash `gh issue close` | `guard` | Always `ask`. |
| Stop (end of turn) | extend `handover` | Only when something changed this turn: commits without a `#N` in the message, a plan with no issues, a PR with no link, follow-up work named in my reply with no issue. Reminder only, with the exact `gh` command to run. Silent otherwise. |
| UserPromptSubmit | extend `scope` | After a PR merges, reminds me to ask for your go-ahead to close, never to close unasked. |

Limits, stated honestly: "follow-up work named in my reply" and "user tested it" cannot be detected reliably. The Stop check is a heuristic nudge; the hard gates are the plan flag, the PR guard and the close prompt.

### Cost

One `gh issue list --json` call (about 0.5 s) at session start and on gated events only, cached 60 s. No per-tool-call cost beyond a file read. Net token cost: about 250 at session start, 100 to 300 on gated events.

## Part 2. Tiered runtime subagents (replaces the single `executor`)

Issue #105 already asks for this. Runtime generation uses the Agent tool's per-call `model`, `isolation` and `prompt` parameters with a built-in subagent type, so no per-job agent files exist. The executor and archivist agent files go away once the tiers cover them (archivist's move-comments job becomes a scout-tier prompt template).

### Tiers

| Tier | Model | Use for | Tools |
|---|---|---|---|
| scout | haiku | find, list, read, summarise; no writes | read-only |
| build | sonnet | implement one issue's chunk (3 steps or fewer) | edit, bash |
| review | opus, only on demand | adversarial check of a finished diff, or a stuck build | read-only |

### Assignment

The tier comes from the issue, not from me deciding ad hoc: label `tier:scout`, `tier:build` or `tier:review` set when the issue is created (default `tier:build`). The dispatch prompt is generated from one short template: issue number and body, files in scope, the verification commands, a report limit of 150 words, and the rule that the subagent comments its result on the issue.

### Guardrails against the credit burn you saw

1. **Serial by default, cap of 2 concurrent.** A PreToolUse hook on the Agent tool counts running agents (SubagentStart and SubagentStop already fire) and denies a third with the reason.
2. **No nesting.** A subagent cannot spawn subagents (deny when the parent is already a subagent).
3. **One subagent per issue, not per step.** A spawn needs an issue number in the prompt; the hook denies a spawn without one.
4. **Delegate only when it pays.** Keep the existing exception: one file and 3 steps or fewer stays on the main thread. Issue #95 (cost analysis) should be answered with real numbers before the threshold is tuned.
5. **Shorter reports.** The "report every command verbatim" mandate applies to `build` only; scouts return results, not transcripts.
6. **Review tier is opt-in.** It runs only for issues labelled `tier:review` or when a build attempt fails twice.

### Spike result (2026-09-30)

A general-purpose subagent spawned with `model: "haiku"` replied `claude-haiku-4-5-20251001` when asked for its model ID. So the per-call override is accepted and the subagent believes it is haiku. This is the subagent's own statement; the plugin's `verdict` hook reads the model from the transcript and should be used to confirm it independently before the executor is retired. The same probe with `model: "sonnet"` answered `claude-sonnet-5-5` and with `model: "opus"` answered `claude-opus-5-5`, so all three tiers map to distinct models. Each spawn used one tool call (the hand-back) and about 57k subagent tokens for the sonnet and opus probes, 41k for haiku, which is the fixed spawn overhead to weigh against the delegation threshold.

## Build order (each a separate PR, each with `verify.py` cases and a version bump)

1. Issue workflow: rule text, PR guard, close prompt, `claude-tracked` label and marker. No enforcement on edits yet.
2. Plan flag and edit gate, SessionStart issue list, Stop nudge.
3. Model-override spike, then the tier template and the concurrency cap hook.
4. Retire `executor` and `archivist`; migrate their references (`rules/house-rules.md`, `scope` and `delegate` hook text, docs).
5. Reconcile `claude-issue-forge` (backlog scanner) with the new label and marker so the two do not duplicate issues.

## Revision 2 (2026-09-30): after reading focus-deck-app and measuring spawn cost

This section supersedes the label design in Part 1 (decision 4), the granularity rule, and the "no agent files" line in Part 2.

### What Focus Deck does with an issue (read from `Ajw2003/focus-deck-app` docs, code and screenshots)

- Each repo you add is a **project card**. Each **labelled open issue** is one **flat task row** under "In progress" or "Up next". Unlabelled issues are ignored. Pull requests are filtered out. Only the first 100 open issues per repo are fetched (one page), so a backlog past 100 would silently drop rows.
- A row shows the **title only**, plus chips. There is no parent/child display and the issue body is not shown on the row. Ticking the checkbox closes the issue on GitHub; unticking reopens it.
- **Every label becomes a category chip**, except reserved ones: `priority: urgent|high|medium|low`, `in progress` (also `wip`, `doing`, which moves the row to "In progress"), `Claude created this`, `Claude completed this`.
- The repo's contract for Claude (`docs/4-systems/claude-integration.md`): Claude may only **create, comment, close and reopen**. Never delete. Every issue it creates carries at least one label. It applies `Claude created this` when it opens an issue and `Claude completed this` when it closes one. It never edits an issue body or removes a label.

### Consequences for the design

1. **No new labels.** `claude-tracked` and `tier:build` would each show up as a category chip on every row. Ownership is `Claude created this` (already reserved and hidden). The subagent tier goes in a hidden comment in the issue body, not a label. Plain category labels (`Feature`, `fix`, `Chore`) stay as they are.
2. **Titles carry the whole overview**, because the title is all Focus Deck shows. Titles are written in plain language, no jargon.
3. **Claude cannot edit a body later**, so a parent issue's checklist can never be ticked by me. Progress is shown by the child rows themselves being ticked off in Focus Deck. The parent is closed last, after your approval.
4. **Moving a row to "In progress" needs the `in progress` label added to an existing issue.** The contract does not allow Claude to add labels after creation. Needs your decision (question 1).
5. **Closing uses your tick or your approval prompt.** Ticking the checkbox in Focus Deck closes the issue, so your manual test result can be given there. The `gh issue close` guard stays as the second route.

### Granularity (your rule)

- **One parent issue per plan or major change**: a feature added, a feature removed, or a large overhaul of an existing feature or mechanic.
- **Smaller child issues for the steps inside it**, written in plain language for you, not for me. Example parent title: "Quieter notices and a faster start for the hooks". Example child titles: "Stop the hooks announcing when they did nothing", "Make the hook launcher remember which Python works", "Skip slow git checks on ordinary branches".
- Order: create the parent first (its body lists the step titles in plain text), then the children, each with `Part of #<parent>` in its body, in the order they will be worked. Children are created in that order so Focus Deck's "Up next" lists them in the order of work.
- The 3-step threshold still decides *whether* a plan gets issues at all: 3 steps or fewer is one issue with no children.

### The loop for every child issue (forced checkpoints)

1. Pick the next open child (yours first if you added one).
2. Mark it in progress (see question 1).
3. Do the work on a branch; commit messages reference `#N`.
4. Comment on the issue: what changed, how it was tested, the real output.
5. Open the PR with `Refs #N` (never `Closes`).
6. **Stop and ask you to test.** Nothing moves until you say so.
7. On your approval: close with `Claude completed this` and a comment linking the merged PR.
8. Pick the next child. When the last child closes, ask before closing the parent.
New work found mid-task becomes a new issue (comment on the current one linking it), not a silent addition.

### Spawn cost, measured (this machine, this session, trivial one-word job, 2026-09-30)

What the number means: `subagent_tokens` in the completion report is the **final context size**, not the amount billed. Each spawn makes 3 to 4 model calls. The first call writes the whole starting context to the cache. The later calls re-read it. Two of those calls come from the harness (the `SubagentHandback` report call and a "no visible output" nudge), not from the task.

| Agent type | Model | Starting context written to cache | Final context size |
|---|---|---|---|
| Explore | haiku | 25.3k | 26.7k |
| claude-code-guide | haiku | 33.2k | 34.1k |
| general-purpose | haiku | 38.5k | 40.9k |
| cavecrew-investigator | haiku | 38.6k | 41.4k |
| Explore | sonnet | 37.2k | 37.8k |
| claude-code-guide | sonnet | 45.5k | 45.9k |
| general-purpose | sonnet / opus | 55.4k | 57.6k / 57.7k |
| house-rules:executor (earlier run) | (session model) | 53.8k | not recorded |

Repeat of haiku general-purpose: 40,849 then 40,945. Fixed to within about 0.2 percent.

**What the starting context is made of** (characters in the transcript's prompt snapshot; about 4 to 5 characters per token):

| Part | Explore (haiku) | general-purpose (haiku) | claude-code-guide (haiku) |
|---|---|---|---|
| Tool definitions | 105,600 (37 tools) | 181,900 (41 tools) | 19,300 (6 tools) |
| System prompt | 3,200 | 2,700 | 103,700 |
| Skill list | 13,500 | 13,500 | none |
| Deferred-tool name list | 8,300 | 8,400 | none |
| Hook-injected rules (SubagentStart) | 6,900 | 6,900 | 6,900 |
| Your CLAUDE.md | none | 5,400 | 5,400 |
| Agent-type list | none | 5,100 | none |

Biggest single items: the `Artifact` tool definition is 54,900 characters, `Bash` 22,400, `PowerShell` 18,100 (both shells are loaded on this Windows machine), `Agent` 16,700, and the browser tool set is about 40,000 across a dozen tools.

**Does caching carry across spawns?** Yes. Two Explore/haiku spawns run back to back: the first wrote 27,598 tokens; the second's first call **read** 27,598 from cache and wrote 0. The earlier parallel and 7-minute-apart repeats showed no hit, because parallel spawns start before the cache exists and the gap exceeded the cache lifetime.

**Cost of one trivial spawn**, in input-token equivalents using Anthropic's standard cache ratios (write 1.25x, read 0.1x, output 5x; I assumed these apply to this account and did not verify them): Explore/haiku first spawn about 45k, the same spawn run straight after another about 16k. A general-purpose/haiku spawn is about 65k. These are relative units, not dollars.

### Levers, ranked

1. **Trim tool definitions with a tool allowlist** (biggest). Only an agent definition file can restrict a subagent's tools; the Agent tool call cannot. A scout limited to Read, Grep, Glob and the handback call would carry about 15,000 characters of tools instead of 105,600 to 181,900. This reverses my earlier "no agent files": three thin tier files (scout, build, review) that only set model, tool allowlist and a two-line role, with everything job-specific still generated at spawn from the issue. Estimated saving for a scout: roughly 18k to 30k tokens of starting context.
2. **Run same-tier spawns back to back, not in parallel.** The second onward reads the cache at a tenth of the price. This fits the serial-by-default cap.
3. **Pick the smallest agent type that can do the job.** Explore is 12k to 14k tokens lighter than general-purpose, on haiku. claude-code-guide is heavier than Explore despite far fewer tools, because its system prompt is 103,700 characters.
4. **Shrink what every spawn inherits**: the skill list (13,500 characters) and deferred-tool list (8,300) come from enabled plugins. Disabling plugins you do not use in this repo (the Unity skills, for example) cuts every spawn and the main session. The house-rules SubagentStart rules add about 6,900 characters; they are on the list for trimming in finding 5.
5. **Fewer calls per spawn** is not something we can control. The two harness-driven calls re-read the whole context each time.

**Caveat on the table above:** the sonnet spawns were given smaller tool sets than the haiku spawns (Explore 85,021 characters of tools on sonnet against 105,671 on haiku; claude-code-guide 11,615 against 19,269), while the system prompts were byte-identical. The tool saving in lever 1 is therefore measured on haiku only.

**Haiku versus sonnet and opus.** Sonnet counted more tokens for fewer characters, which supports the different-tokenizer reading; a token-count call on identical text would prove it and needs an API key this environment does not have. The same agent type counts 35 to 42 percent more tokens on sonnet (Explore 26.7k vs 37.8k, claude-code-guide 34.1k vs 45.9k, general-purpose 40.9k vs 57.6k). That ratio is steady rather than a fixed block, which points to a different tokenizer, not extra hidden context (inference, not checked). So lowering the context helps every tier in proportion, and the trim in lever 1 pays back more on sonnet and opus because each token costs more there. Haiku's saving is mainly that its tokens are cheap, so trimming it is worth doing but is not where the largest money is. Nothing above reduces the quality of the sonnet and opus tiers: their tool lists would stay full, because the build tier needs Edit, Write and Bash.

## Decisions

1. **Answered, yes (aj, 2026-09-30):** Claude may add the `in progress` label to an existing issue when work starts, and remove it when the issue is closed. This is the one label edit allowed after creation; the rest of the Focus Deck contract (no body edits, no deletes, no removing `Claude created this` or `Claude completed this`) stands. The contract text lives in the focus-deck-app repo (`docs/4-systems/claude-integration.md`) and still says Claude never edits labels afterwards; that repo has not been changed and its doc is now out of step with this decision.

## Still open

2. Is blocking source edits until a plan's issues exist acceptable, or should that stop at a reminder?
3. Approve the three thin tier files (scout, build, review) in place of the single executor and archivist?
4. Which repos should this apply to: only AjsClaudeCodeTools, or every repo you add to Focus Deck?
