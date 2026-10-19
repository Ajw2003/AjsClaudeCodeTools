# Audit 1 of the house-rules plugin: rules against rules

Raw findings from a read-only scout pass on 2026-10-16. Every line cites both sides. The findings
are not yet verified one by one; the summary report marks which ones were spot-checked.

Scope read: `rules/house-rules.md`, `rules/show-dont-tell.md`, `rules/clear-writing.md`, every
`rules/detail/*.md`, `rules/standards/*.md`, `output-styles/handover-cards.md`, `agents/*.md`,
`commands/*.md`, `skills/*/SKILL.md`, and the repo's `CLAUDE.md`. Paths are relative to
`claude-house-rules/plugins/house-rules/`.

## 1. Contradictions and stale references

### Subagents
- `rules/detail/delegate-execution.md:16` says the helper tiers omit the Agent tool; `agents/archivist.md:1-6` has no tools line, so it inherits every tool.
- `rules/detail/delegate-execution.md:33-35` says each tier's description says "use proactively"; `agents/reviewer.md:3` says "Use only when a second opinion is asked for".
- `rules/detail/green-suite.md:16-17` says "I run it twice"; `agents/builder.md:13` says "run the full suites exactly once".
- `agents/builder.md:11` says "stop and ask"; `rules/detail/destructive-action.md:51-52` says a subagent cannot answer a prompt.
- `agents/builder.md:17` caps the report at 6 lines and quotes output "only for a failure"; `rules/detail/evidence-before-claims.md:21` requires quoting real output.
- `rules/detail/delegate-execution.md:66-68` says no hook keeps state; the same file at lines 14-15 (agentcap) and `rules/detail/issue-workflow.md:28` (`house-rules-issues.json`) keep state.

### Branches, deletion and asking
- `rules/detail/commit-branches.md:21-22` says other branches are open "without a prompt"; `destructive-action.md:10` refuses commits on a branch not confirmed mine; `skills/plain-docs/SKILL.md:124-126` says stop and ask.
- `commit-branches.md:19` says "Refused, not asked"; `commit-branches.md:23-24` says force-push, branch delete and `git clean` "still ask"; `destructive-action.md:7-18` refuses them.
- `destructive-action.md:20-21` lets a committed, unchanged delete through because git can bring it back; `edit-place.md:8-9` says git recovery does not make the loss safe; `rules/standards/coding-philosophy.md:58` says ask before deleting files.
- `commit-branches.md:46-47` says "I never sweep up unrelated dirty files"; `delegate-execution.md:83-84` says worktreesweep commits any untouched subagent worktree.

### Issues, labels and attribution
- `issue-workflow.md:5` applies the issue rule only to plans over three steps; `rules/detail/show-dont-tell.md:90-92` requires two issues before any "Build plan approved".
- `rules/detail/show-dont-tell.md:82` says "The user then closes it"; `issue-workflow.md:6` treats closing as an approval step.
- `issue-workflow.md:19` adds a fourth label, "Claude completed this"; `commands/labels.md:2` says "the three house labels".
- `commit-branches.md:65-70` bans Claude branding and Co-Authored-By, while Claude Code's own session attribution asks for both; `commit-branches.md:74-77` says the guard refuses them.

### Pages and handover
- `rules/detail/handover-command.md:162-163` says "I never publish a page unasked"; `rules/show-dont-tell.md:18-19` says a missing page blocks until the reply links one.
- `handover-command.md:166-168` builds the page from `templates/step-card.html` and says "I do not retry"; `rules/detail/show-dont-tell.md:97-98` says every page goes through `make_page.py` from `handover-page.html`, with retries.
- `rules/detail/artifact-location.md:5-6` puts HTML in `docs/generated/`; `show-dont-tell.md:99-100` writes pages to `docs/plans/`.
- `output-styles/handover-cards.md:43-44` drops "plus why" from item 5; `rules/house-rules.md:101-103` requires it.
- `output-styles/handover-cards.md:30` calls house-rules.md "the only real copy"; `handover-command.md:59-92` restates the six items.
- `rules/house-rules.md:107-109` says the card lives only in the output style; `handover-command.md:94-117` holds a full template.

### Docs and harvest
- `skills/project-docs/SKILL.md:34` says plans are named for the work, not the date; `commit-branches.md:87` and `agents/archivist.md:52` use dated names.
- `agents/archivist.md:22-23` says append to Decisions.md; `skills/project-docs/SKILL.md:132` says newest at top; the same skill at line 26 says "only appended to".
- `rules/detail/long-form-reasoning.md:9` says the block moves before turn end; `commands/harvest-scan.md:33-34` says do not port automatically, and cites "the harvest rule", which does not exist.
- `agents/archivist.md:3` has a skip exception that `long-form-reasoning.md:22-24` lacks.
- `rules/detail/docs-tiers.md:47-48` keeps scaffolded docs out of git in repos aj doesn't own; `artifact-location.md:6-7` says "Tracked, committable".

### Other
- `rules/detail/shim-compiles.md:13-15` runs Unity batch mode whenever reachable; `rules/standards/csharp-unity-detail.md:70-71` allows it only when no CLI or plugin exists.
- `commands/doctor.md:6-7` says hooks "silently do nothing"; `rules/detail/fails-silently.md:7-8` forbids that.
- `rules/standards/coding-philosophy.md:60` allows an unasked bug fix; `rules/show-dont-tell.md:9-10` says the request is the scope.
- Stale: `rules/detail/edit-place.md:4` says "The rule above carves out ordinary edits"; no such text exists.
- Stale: `rules/detail/environment.md:9` puts `rules/environment.md` next to this file, but this file is in `rules/detail/`. Neither `rules/environment.md` nor `rules/handover-target.md` ships in the tree.

## 2. Duplication
- The six handover items appear in `rules/house-rules.md:101-103`, `rules/detail/handover-command.md:59-92` and `output-styles/handover-cards.md:34-45`; the output style has drifted.
- The card template appears in `handover-command.md:99-117` and `handover-cards.md:51-70`, with different "how" examples.
- Plain-copy limits appear in `rules/detail/clear-writing.md:149-155`, `skills/plain-docs/SKILL.md:102-104` and `scripts/plain_docs_check.py`.
- Each injected rule exists as a summary and a detail file (`rules/show-dont-tell.md` and `rules/detail/show-dont-tell.md`; the same for clear-writing).
- Ask-when-unclear appears in `rules/detail/clear-writing.md:51-55` and `show-dont-tell.md:11-12`.
- Doc placement is spread over `artifact-location.md`, `long-form-reasoning.md`, `docs-tiers.md` and `skills/project-docs/SKILL.md:31-45`.
- The source-edit lock appears in `show-dont-tell.md:64-66` and `issue-workflow.md:11-13`.
- Delete-before-add appears in `coding-philosophy.md:15-16` and `show-dont-tell.md:41-50`.
- Five commands repeat the same plugin-root boilerplate: `commands/docref.md:18-21`, `plain-docs.md:18-21`, `harvest-scan.md:20-23`, `labels.md:18-21`, `agents/archivist.md:32-37`.

## 3. Personal assumptions (block use by anyone else)
- Named people and repos: `commit-branches.md:79-80` (an email), `docs-tiers.md:44` (Ajw2003), `deliver-workflow.md:14-15` (repo URL, aj-house-rules), `delegate-execution.md:60` (PlunderSpell), `no-local-paths.md:10` (RockSkipping), `issue-workflow.md:24` (Focus Deck board), `unity-tools-first.md:26`.
- Named labels and branches: AjsAgent in `commit-branches.md:6`, `issue-workflow.md:22`, `destructive-action.md:10`.
- "aj" throughout, for example `agents/editor.md:9`, `rules/show-dont-tell.md:116-117`, `destructive-action.md:24`, `CLAUDE.md:7`.
- A paid plan: `free-first.md:26` ("Pro or Max").
- Windows and Git Bash: `handover-command.md:127-128`, `commands/doctor.md:29`, `deliver-workflow.md:10-16`.
- Unity and Rider: `rules/standards/csharp-unity-standards.md`, `csharp-unity-detail.md:87-92`, `shim-compiles.md:4-18`, `unity-tools-first.md`.
- Grep only, not read: `scripts/hook.py:4896` writes "Co-Authored-By: Claude".

## 4. Themes (input to a sub-plugin split)
| Theme | Rules |
|---|---|
| Safety guards | destructive-action, commit-branches, edit-place, parity-inventory, delegate-execution (worktree part) |
| Honesty and evidence | evidence-before-claims, what-prompted-me, read-docs-first, green-suite, shim-compiles, reported-update, fails-silently, visual-check |
| Writing and voice | clear-writing, show-dont-tell (page part) |
| Design loop | show-dont-tell, issue-workflow, no-local-paths |
| GitHub and attribution | issue-workflow, no-local-paths, commit-branches (credit), labels |
| Environment and budget | environment, free-first, deliver-workflow, unity-tools-first, shim-compiles |
| Delegation | delegate-execution, the five agents |
| Docs | docs-tiers, long-form-reasoning, artifact-location, project-docs, plain-docs |
| Handover | handover-command, users-hands, handover-cards, reported-update |
| Code standards | code-standards, coding-philosophy, the three standards files |

Rules with an unclear purpose or an overlap: build-alone (no mechanism named), free-first (no hook
named), what-prompted-me and reported-update (both overlap evidence-before-claims), and the
docs-tiers silent exception (not reflected in fails-silently).

## 5. Rules vague enough to read two ways
- `delegate-execution.md:26` "agreed in conversation", against the approval gate in `show-dont-tell.md:73-76`.
- `edit-place.md:15` "wholesale" is undefined.
- `free-first.md:3-4` "the first rung that does the job" is undefined.
- `long-form-reasoning.md:9-11` "grown into an essay" has no length.
- `evidence-before-claims.md:38-39` "not prohibitively expensive" has no threshold.

## Findings from this session itself (observed, 2026-10-16)
- The writing check flags a term as jargon even when the same reply defines it, and flags it again when a reply merely quotes it while reporting the problem, so the check can loop on its own report.
- The session-start version notice said "still running 2.67.1" while the hooks ran 2.68.0 (see `docs/plans/2026-10-16-version-notice-and-page-dodge.html`).
- The page checkpoint measures only the newest message, so a shorter retry clears a page block.
- The commit-attribution guard and Claude Code's own attribution instructions demand opposite commit trailers.
- The rules still say "no nohup", but 2.68.0 removed the guard that enforced it (`scripts/hook.py`, comment for #292).
