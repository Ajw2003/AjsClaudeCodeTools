# Technical Specification & Implementation Plan: Matt Pocock's Skills Integration

**Repository:** `Ajw2003/AjsClaudeCodeTools`  
**Branch:** `add_mattpocock_skills`  
**Target Directory:** `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills`  
**Artifact Location:** `history/technical_spec.md`  
**Date:** 2026-09-20  
**Author:** Documentation Agent  

---

## 1. Layman Summary

### 1.1 What Is Happening?
We are installing a curated suite of specialized development and workflow skills authored by Matt Pocock into this repository (`Ajw2003/AjsClaudeCodeTools`). These skills are modular operational runbooks and behavioral protocols packaged for Claude Code.

### 1.2 Why Are We Doing This?
This repository develops and maintains `house-rules` (a Claude Code plugin enforcing safety and operational guidelines via hooks) as well as emerging agent tooling (`claude-prompt-workshop` and `claude-agent-router`). While the repository already has basic interview skills (`grill-me` and `grilling`), it lacks standardized protocols for:
1. **Agent-Facing Documentation Quality**: Enforcing high-signal prompt engineering and documentation hygiene (`writing-for-agents`).
2. **Primary-Source Empirical Research**: Systematic background investigations without hallucination or reliance on secondary commentary (`research`).
3. **Architectural Discipline & Deep Modules**: Standardizing domain vocabularies, Ousterhout-style deep module boundaries, and architectural decision records (`codebase-design`, `domain-modeling`, `grill-with-docs`, `improve-codebase-architecture`).
4. **Rigorous Implementation & Verification**: Enforcing vertical-slice Test-Driven Development (TDD), disciplined bug diagnosis, and decoupled two-axis code reviews (`tdd`, `diagnosing-bugs`, `code-review`, `implement`).
5. **Issue Tracking & Spec Management**: Bridging natural language discussions directly into GitHub issues, specs, and tracer-bullet tickets (`setup-matt-pocock-skills`, `to-spec`, `to-tickets`, `pr`).

### 1.3 How Does This Improve Developer and Agent Workflows?
- **Predictable Agent Actions**: Rather than relying on fuzzy model intuition, autonomous sub-agents and human developers execute proven, battle-tested standard operating procedures.
- **Zero Drift Between Code and Docs**: Domain models and architectural decisions are continuously synchronized with code changes.
- **Clean Context Separation**: Heavy research and reviews run in isolated sub-agents, keeping primary conversational contexts clean and fast.
- **Strict Adherence to Existing Repository Philosophy**: Dangerous external hook skills (such as `git-guardrails-claude-code`, which hard-blocks git commands) are deliberately excluded, ensuring `house-rules` retains full, uncompromised control over terminal safety checks.

---

## 2. Technical Specifications

### 2.1 Invocation Taxonomy
The skills repository establishes two distinct operational classifications:
1. **User-Invoked (`disable-model-invocation: true`)**:
   - Orchestration runbooks explicitly triggered by a human typing `/skill-name`.
   - Designed to run interactive loops, interview developers, or scaffold repository files.
2. **Model-Invoked (`disable-model-invocation: false`)**:
   - Disciplines and domain reference standards that Claude can proactively invoke when context demands it, or that are called programmatically by user-invoked orchestrators.

---

### 2.2 Exhaustive Breakdown of Curated Skills

The following 18 new skills are to be installed, joining the 2 existing skills (`grill-me`, `grilling`) for a total of **20 installed skills**:

| # | Skill Name | Category | Invocation Type | Primary Role & Description | Trigger Conditions | Dependencies & Preconditions |
|---|------------|----------|-----------------|-----------------------------|--------------------|-------------------------------|
| 1 | `setup-matt-pocock-skills` | Engineering | User (`true`) | Repo configuration orchestrator. Scaffolds tracker configs, domain layouts, and CLAUDE.md pointers. | Run once when configuring a repository for engineering skills. | Git CLI, GitHub CLI (`gh`), `CLAUDE.md`. |
| 2 | `writing-for-agents` | Productivity | Model (`false`) | Authoring discipline for agent-facing docs (skills, CLAUDE.md, instructions, prompt positive rules). | Creating/editing skills, CLAUDE.md, AGENTS.md, or system prompts. | None. Markdown reference standard. |
| 3 | `research` | Engineering | Model (`false`) | Investigates technical questions against primary sources and outputs cited Markdown notes via background agents. | When factual technical questions require deep primary source verification. | Web search / primary source docs / git log. |
| 4 | `grill-with-docs` | Engineering | User (`true`) | Relentless interview to sharpen design while concurrently updating `CONTEXT.md` and ADRs. | User wants to flesh out an architecture or feature design before building. | `grilling`, `domain-modeling`, `CONTEXT.md`, `docs/adr/`. |
| 5 | `domain-modeling` | Engineering | Model (`false`) | Builds and maintains project glossary (`CONTEXT.md`) and Architectural Decision Records (`docs/adr/`). | Discussing code organization, concepts, naming, or boundaries. | `docs/agents/domain.md`, `CONTEXT.md`. |
| 6 | `code-review` | Engineering | Model (`false`) | Two-axis review (Standards vs Spec) executed via parallel sub-agents to avoid context pollution. | After writing code or before merging a branch/PR. | Git CLI, parallel sub-agent capability, repo coding standards. |
| 7 | `codebase-design` | Engineering | Model (`false`) | Standard vocabulary for deep modules (interface vs implementation, seams, leverage, locality). | User requests design advice, module boundary refactoring, or API review. | None. Conceptual framework based on Ousterhout / Feathers. |
| 8 | `tdd` | Engineering | Model (`false`) | Strict Test-Driven Development (red-green-refactor at agreed public seams). | Building features or bugfixes where tests can define expected behavior. | Test runners: `verify.py`, `verify_tools.py`, or project test runners. |
| 9 | `diagnosing-bugs` | Engineering | Model (`false`) | Gated diagnosis loop for hard bugs (tight loop -> minimize -> hypothesize -> instrument -> fix). | Reproducing or debugging unexpected test failures, crashes, or regressions. | Reproducible test harness. |
| 10 | `to-spec` | Engineering | User (`true`) | Synthesizes current conversation into a formal spec published to the configured issue tracker. | User completes a planning/grilling session and needs a shareable spec. | `docs/agents/issue-tracker.md`, `gh` CLI. |
| 11 | `to-tickets` | Engineering | User (`true`) | Decomposes a spec into tracer-bullet tickets with explicit blocking edges. | User wants to break an approved spec into atomic execution steps. | `docs/agents/issue-tracker.md`, `gh` CLI. |
| 12 | `implement` | Engineering | User (`true`) | Implements tickets/specs, driving `tdd` at agreed seams and concluding with `code-review`. | User provides a ticket or spec to implement end-to-end. | `tdd`, `code-review`, `docs/agents/issue-tracker.md`. |
| 13 | `improve-codebase-architecture`| Engineering | User (`true`) | Scans codebase for deepening opportunities, generates visual HTML report, and grills candidates. | Proactive codebase health checks and architectural refactoring audits. | Browser / HTML viewer, `domain-modeling`. |
| 14 | `resolving-merge-conflicts` | Engineering | Model (`false`) | Resolves git merge/rebase conflicts hunk by hunk, tracing intent back to commit histories. | In-progress git merge or rebase conflict in the working tree. | Git CLI (`git status`, `git log`). |
| 15 | `ask-matt` | Engineering | User (`true`) | Interactive router across all installed Matt Pocock skills. Recommends the right workflow. | User is unsure which skill fits their immediate situation. | Installed skill catalog in `.claude/skills/`. |
| 16 | `handoff` | Productivity | User (`true`) | Compacts current session state into a structured handoff document for another agent session. | Agent session approaching context budget or handing off to another agent. | Session context. |
| 17 | `wait-what` | Productivity | User (`true`) | Stops execution and re-pitches misunderstood messages using plain English and glossary terms. | Claude gave an explanation that felt jargon-heavy, confusing, or misaligned. | `CONTEXT.md` (if available). |
| 18 | `pr` | In-Progress | Model (`false`) | Template and guidelines for writing concise, scannable pull request descriptions. | Preparing a pull request body. | Git CLI (`git diff`, `git log`). |
| 19 | `grill-me` *(existing)* | Productivity | User (`true`) | Relentless interview to sharpen a plan or decision. | Refining a plan or decision. | `grilling`. |
| 20 | `grilling` *(existing)* | Productivity | Model (`false`) | Foundational interview primitive mapping decisions into frontier questions and trees. | Invoked by `grill-me`, `grill-with-docs`, etc. | None. |

---

### 2.3 Deliberately Excluded Skills & Clash Analysis

| Skill Name | Verdict | Rationale & Clash Analysis |
|---|---|---|
| `git-guardrails-claude-code` | **PROHIBITED** | **Architectural Clash:** Installs `PreToolUse` bash hooks that hard-block commands (`exit 1` on `git push`, `reset --hard`, etc.). This directly clashes with `house-rules`, whose core architectural philosophy (documented in `README.md` and `CLAUDE.md`) is to prompt for confirmation (`permissionDecision: "ask"`) and **never block outright**. Installing this skill would introduce duplicate, conflicting hooks. |
| `migrate-to-shoehorn` | **EXCLUDED** | TypeScript-specific type-cast migration tool (`@total-typescript/shoehorn`). Inapplicable to this Python/Markdown/JSON repository. |
| `setup-pre-commit` | **EXCLUDED** | Installs Husky and `lint-staged`. This repository relies strictly on zero-dependency Python stdlib test harnesses (`verify.py`, `verify_tools.py`). |
| `setup-ts-deep-modules` | **EXCLUDED** | TypeScript-specific package structure and `dependency-cruiser` configuration. |
| `scaffold-exercises` | **EXCLUDED** | Video course exercise generator for Matt Pocock's educational products. |
| `teach` | **EXCLUDED** | Interactive coding tutor. Inapplicable to plugin and agent development. |
| `wizard` | **EXCLUDED** | Generates interactive bash wizards for cloud/infra provisioning. |
| `writing-beats`, `writing-fragments`, `writing-shape` | **EXCLUDED** | In-progress experimental drafting skills for essay writing. |
| `claude-handoff`, `implement-spec`, `loop-me`, `retro` | **EXCLUDED** | Experimental in-progress drafts superseded by `handoff` and `implement`. |
| `triage`, `wayfinder` | **DEFERRED** | Advanced issue state machines; deferred until full multi-developer GitHub issue triage is actively adopted. |

---

### 2.4 Exact CLI Command Specification

To prevent interactive CLI hanging and avoid the hazardous 38-skill mass dump triggered by non-interactive mode:

```powershell
npx skills add "https://github.com/mattpocock/skills" --agent claude-code --skill setup-matt-pocock-skills writing-for-agents research grill-with-docs domain-modeling code-review codebase-design tdd diagnosing-bugs to-spec to-tickets implement improve-codebase-architecture resolving-merge-conflicts ask-matt handoff wait-what pr -y
```

#### CLI Flag Justification:
- `https://github.com/mattpocock/skills`: Remote source repository.
- `--agent claude-code`: Targets Claude Code, installing into `.claude/skills/<skill>/` and updating root `skills-lock.json` (rather than writing to `.agents/skills/`).
- `--skill <names...>`: Explicitly constrains installation to the 18 selected skills.
- `-y`: Non-interactive auto-confirmation.

---

### 2.5 Files to be Added and Modified

```
C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\
├── skills-lock.json                           [MODIFIED: updated with 18 new skill entries and hashes]
├── CLAUDE.md                                  [MODIFIED: append ## Agent skills section]
├── docs/
│   └── agents/
│       ├── issue-tracker.md                   [NEW: GitHub issue tracker specification]
│       └── domain.md                          [NEW: single-context domain doc specification]
└── .claude/
    └── skills/
        ├── ask-matt/SKILL.md                  [NEW]
        ├── code-review/SKILL.md               [NEW]
        ├── codebase-design/SKILL.md           [NEW]
        ├── diagnosing-bugs/SKILL.md           [NEW]
        ├── domain-modeling/SKILL.md           [NEW]
        ├── grill-me/SKILL.md                  [EXISTING]
        ├── grill-with-docs/SKILL.md           [NEW]
        ├── grilling/SKILL.md                  [EXISTING]
        ├── handoff/SKILL.md                   [NEW]
        ├── implement/SKILL.md                 [NEW]
        ├── improve-codebase-architecture/SKILL.md [NEW]
        ├── pr/SKILL.md                        [NEW]
        ├── research/SKILL.md                  [NEW]
        ├── resolving-merge-conflicts/SKILL.md [NEW]
        ├── setup-matt-pocock-skills/SKILL.md  [NEW]
        ├── tdd/SKILL.md                       [NEW]
        ├── to-spec/SKILL.md                   [NEW]
        ├── to-tickets/SKILL.md                [NEW]
        ├── wait-what/SKILL.md                 [NEW]
        └── writing-for-agents/SKILL.md        [NEW]
```

---

## 3. Process & Implementation Definitions

### 3.1 Step-by-Step Implementation Procedure

The Implementation Agent must follow these chronological steps:

1. **Pre-Execution Baseline Validation**:
   - Execute `python claude-house-rules/plugins/house-rules/scripts/verify.py` (ensure 217/217 checks pass).
   - Execute `python tools/verify_tools.py` (ensure 39/39 checks pass).
   - Confirm `git status` is clean.

2. **Skill Installation via CLI**:
   - Run the exact `npx skills add` command specified in Section 2.4.
   - Verify that `skills-lock.json` contains exactly 20 skill definitions.
   - Verify that all 18 new folders exist under `.claude/skills/` and each contains a valid `SKILL.md`.

3. **Scaffold Agent Documentation (`docs/agents/`)**:
   - Create `docs/agents/issue-tracker.md` with the precise contents specified in Section 3.2.
   - Create `docs/agents/domain.md` with the precise contents specified in Section 3.3.

4. **Update `CLAUDE.md`**:
   - Carefully append the `## Agent skills` section at the end of `CLAUDE.md` conforming strictly to the constraints in Section 3.4.

5. **Post-Execution Verification**:
   - Execute `python claude-house-rules/plugins/house-rules/scripts/verify.py`.
   - Execute `python tools/verify_tools.py`.
   - Verify JSON syntax of `skills-lock.json`.
   - Review `git diff` to ensure no stray modifications or unintended deletions occurred.

---

### 3.2 Specification for `docs/agents/issue-tracker.md`

Create `docs/agents/issue-tracker.md` with the following exact content:

````markdown
# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder` if installed. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
````

---

### 3.3 Specification for `docs/agents/domain.md`

Create `docs/agents/domain.md` with the following exact content:

````markdown
# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo (most repos):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

Multi-context repo (presence of `CONTEXT-MAP.md` at the root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← system-wide decisions
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← context-specific decisions
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
````

---

### 3.4 Explicit Constraints on `CLAUDE.md` Modifications

`verify.py` enforces strict structural assertions on `CLAUDE.md`. To guarantee zero test failures, modifications must satisfy the following constraints:

1. **Strict Pointer Policy (No Duplicate Rules)**:
   - `CLAUDE.md` line 28: *"This root `CLAUDE.md` is a pointer, not a copy."*
   - `verify.py` lines 737-743 explicitly check that `"Never take a destructive action without checking first"` does NOT appear in `CLAUDE.md`.
   - **Constraint**: Under no circumstances should rules from `rules/house-rules.md` be copied into `CLAUDE.md`.
2. **No Card Template Duplication**:
   - `verify.py` lines 2185-2196 check that none of the card template markers (`### Step 1 of`, `**You should see:**`, `*Next: step 2`) appear anywhere in `CLAUDE.md`.
   - **Constraint**: Do not include card examples or card markdown templates in `CLAUDE.md`.
3. **Preserve Architecture and Surface Tables**:
   - `verify.py` lines 2083-2173 and 2325-2350 parse markdown tables in `CLAUDE.md` for hook events and client surfaces.
   - **Constraint**: Do not edit, rename, or touch the existing architecture tables in `CLAUDE.md`.
4. **No Hardcoded Check or Hook Counts**:
   - `verify.py` line 2348-2350 flags strings like `[0-9]+-check`, `all [0-9]+ checks`, or `(four|five|six|seven|eight|nine) hooks`.
   - **Constraint**: Do not write hardcoded check counts or spelled-out hook numbers.

#### Exact Addition to `CLAUDE.md`:
Append the following section at the very end of `CLAUDE.md`:

```markdown
## Agent skills

### Issue tracker

GitHub issues via `gh` CLI. See [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).

### Domain docs

Single-context layout (`CONTEXT.md` and `docs/adr/`). See [docs/agents/domain.md](docs/agents/domain.md).
```

---

## 4. Verification & QA Protocol

### 4.1 Verification Scripts

Execute the following test suites from the repository root:

```bash
# 1. Verify house-rules hooks and doc compliance (must pass all 217 checks)
python claude-house-rules/plugins/house-rules/scripts/verify.py

# 2. Verify repository tools and install scripts (must pass all 39 checks)
python tools/verify_tools.py
```

### 4.2 Structural Validation of Installed Skill Files

Validate that:
1. `skills-lock.json`:
   - Valid JSON syntax (`python -m json.tool skills-lock.json > nul`).
   - Contains 20 entries under the `"skills"` key.
   - Each entry contains `"source"`, `"sourceType"`, `"skillPath"`, and `"computedHash"`.
2. `.claude/skills/`:
   - Contains exactly 20 subdirectories matching the skill list in Section 2.2.
   - Each subdirectory contains a readable `SKILL.md` with YAML frontmatter specifying `name: <skill-name>` and `description: ...`.
3. `docs/agents/`:
   - Both `issue-tracker.md` and `domain.md` exist and contain non-empty Markdown.
4. Git Working Tree:
   - Untracked files are limited to `docs/agents/`, the 18 new directories in `.claude/skills/`, and `history/technical_spec.md`.
   - Modified files are limited to `CLAUDE.md` and `skills-lock.json`.

### 4.3 Rollback & Failure Recovery Plan

In the event of command failure, broken tests, or unexpected file corruption:

1. **Discard Modifications to Tracked Files**:
   ```bash
   git checkout -- CLAUDE.md skills-lock.json
   ```
2. **Remove Newly Added Directories**:
   ```powershell
   Remove-Item -Recurse -Force docs/agents
   # Remove only the newly added skills from .claude/skills (preserving grill-me and grilling):
   $newSkills = @('ask-matt', 'code-review', 'codebase-design', 'diagnosing-bugs', 'domain-modeling', 'grill-with-docs', 'handoff', 'implement', 'improve-codebase-architecture', 'pr', 'research', 'resolving-merge-conflicts', 'setup-matt-pocock-skills', 'tdd', 'to-spec', 'to-tickets', 'wait-what', 'writing-for-agents')
   foreach ($s in $newSkills) {
       if (Test-Path ".claude/skills/$s") {
           Remove-Item -Recurse -Force ".claude/skills/$s"
       }
   }
   ```
3. **Re-verify Clean Baseline**:
   Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` and `git status` to ensure the repository has returned cleanly to its pre-execution state.

---

## 5. Summary of Deliverables

1. `history/technical_spec.md` (this document): Complete implementation blueprint and operational specifications.
2. 18 new Matt Pocock skills installed into `.claude/skills/` alongside existing `grill-me` and `grilling`.
3. `skills-lock.json` updated with sha256 checksums for all 20 skills.
4. `docs/agents/issue-tracker.md` created with GitHub CLI conventions.
5. `docs/agents/domain.md` created with single-context domain conventions.
6. `CLAUDE.md` updated with compliant pointers under `## Agent skills`.
7. `verify.py` and `verify_tools.py` passing 100% cleanly.
