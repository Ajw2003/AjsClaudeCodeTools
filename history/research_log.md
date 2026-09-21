# Research Log: Adding Matt Pocock's Skills to AjsClaudeCodeTools

**Date:** 2026-09-20  
**Repository:** `Ajw2003/AjsClaudeCodeTools`  
**Worktree Branch:** `add_mattpocock_skills`  
**Workspace Path:** `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills`  
**Investigator:** Subagent Research Agent  
**Task:** Research repository context, remote skills in `https://github.com/mattpocock/skills`, CLI behavior of `npx skills add`, skill relevance, and execution requirements.

---

## 1. Executive Summary

1. **Existing Repo State**: The repository is the home of `house-rules` (a Claude Code plugin enforcing standing rules via hooks) along with experimental offshoots `claude-prompt-workshop` and `claude-agent-router`. The workspace already has `skills-lock.json` tracking two installed skills from `mattpocock/skills`: `grill-me` and `grilling`, located in `.claude/skills/`.
2. **Remote Repository (`mattpocock/skills`)**: Authored by Matt Pocock (commit `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`). It contains exactly **38 skills** distributed across four categories: `engineering` (18), `productivity` (7), `in-progress` (9), and `misc` (4).
3. **CLI Behavior (`npx skills add`)**:
   - `npx skills add <url> --list` reliably queries and lists all 38 skills.
   - When running in an automated environment (detecting `antigravity`), `npx skills add` defaults to **non-interactive** execution.
   - **Crucial CLI Hazard**: Running `npx skills add "https://github.com/mattpocock/skills"` non-interactively without the `--skill` flag automatically installs **all 38 skills** into `.agents/skills/` (or target agent).
   - To install specific skills into Claude Code safely without interactive prompt hanging, the command must explicitly supply:
     ```bash
     npx skills add "https://github.com/mattpocock/skills" --agent claude-code --skill <skill-names...> -y
     ```
4. **Relevance Analysis**:
   - **Foundational / Prerequisite**: `setup-matt-pocock-skills` (configures issue tracker, domain docs, triage labels).
   - **High Relevance to Plugin/Agent Tool Development**: `writing-for-agents`, `research`, `grill-with-docs`, `domain-modeling`, `code-review`, `codebase-design`, `tdd`, `diagnosing-bugs`.
   - **Workflow & Quality**: `to-spec`, `to-tickets`, `implement`, `improve-codebase-architecture`, `resolving-merge-conflicts`, `pr`, `handoff`, `wait-what`, `ask-matt`.
   - **Already Installed**: `grill-me`, `grilling`.
   - **Direct Conflict**: `git-guardrails-claude-code` installs PreToolUse bash hooks to hard-block `git push`/`reset`. This directly contradicts the design philosophy of `house-rules`, which already checks destructive git commands and intentionally prompts for confirmation rather than blocking outright.
   - **Irrelevant**: Language-specific skills (`migrate-to-shoehorn`, `setup-pre-commit`, `setup-ts-deep-modules`), course exercise stubs (`scaffold-exercises`), and experimental drafts (`writing-beats`, `writing-fragments`, `writing-shape`, `loop-me`, `implement-spec`).

---

## 2. Current Repository Context

### 2.1 Git Status & Branch
- **Branch**: `add_mattpocock_skills` (tracking origin).
- **Working Tree**: Clean (no uncommitted modifications).
- **Recent Commits**:
  - `af1172f` run the archivist agent for the first proper full run and in the repo it was created, these are the docs and changes it produced
  - `45e10e9` Merge pull request #54 from Ajw2003/claude/archivist-batch-harvest-process
  - `ac639b3` feat: give archivist a two-pass process for batch harvests

### 2.2 Repository Purpose & Architecture
- **Primary Product**: `house-rules`, a personal Claude Code plugin allowing standing user preferences to follow across devices without manual file copying.
- **Hook Lifecycle**: Uses Claude Code hooks (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStart`, `SubagentStop`).
- **Safety Policy**: As documented in `README.md` lines 27–30 & 48–52:
  > "Before a terminal command runs / PreToolUse: The command's text gets checked against a list of things worth a heads-up first — deleting things, rewriting git history, force-pushing... What it deliberately never does: Block a command outright — the strongest thing it ever does is ask for confirmation."
- **Testing Requirements**:
  - Test suite: `python claude-house-rules/plugins/house-rules/scripts/verify.py`
  - Tools test suite: `python tools/verify_tools.py`
  - Zero external npm dependencies for verification; Python stdlib only.
- **CLAUDE.md Policy**:
  - `CLAUDE.md` at root is strictly a pointer, not a copy of rules. Duplicate rules violate `verify.py`.

### 2.3 Existing Skills & Lockfile
- `skills-lock.json` currently contains:
  ```json
  {
    "version": 1,
    "skills": {
      "grill-me": {
        "source": "mattpocock/skills",
        "sourceType": "github",
        "skillPath": "skills/productivity/grill-me/SKILL.md",
        "computedHash": "9cdbb4b8f7a3aeaef82e6230c9e823500d4a8a1214c726cf342cf9829d34fc7d"
      },
      "grilling": {
        "source": "mattpocock/skills",
        "sourceType": "github",
        "skillPath": "skills/productivity/grilling/SKILL.md",
        "computedHash": "4dd886b0196bf43729d954ae326016f2bd9f5f79d892500b407c33a753362f14"
      }
    }
  }
  ```
- `.claude/skills/` contains directories for `grill-me` and `grilling`.
- Internal plugin skill: `claude-house-rules/plugins/house-rules/skills/project-docs`.

---

## 3. Remote Skills Repository Analysis (`mattpocock/skills`)

**Remote URL:** `https://github.com/mattpocock/skills.git`  
**Clone / Cache Inspection:** `C:\Users\aj\AppData\Local\Temp\skills-repo`  
**Latest Commit:** `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`  

### 3.1 Invocation Taxonomy
The repository classifies skills along one primary architectural axis:
1. **User-invoked** (`disable-model-invocation: true`): Orchestration skills invoked intentionally by a human typing the command (e.g. `/grill-me`, `/setup-matt-pocock-skills`). They coordinate workflows, interview users, and may call model-invoked skills.
2. **Model-invoked** (`disable-model-invocation: false`): Autonomous disciplines that can be called by the model when the context matches (or explicitly called by another skill). They contain reusable rules, standards, and execution loops.

### 3.2 Complete Catalog of 38 Skills

#### Category 1: `engineering` (18 skills)
| Skill Name | Invocation | Summary / Role |
| :--- | :--- | :--- |
| `ask-matt` | User | Router over the skills in `mattpocock/skills`. Recommends the right skill or workflow. |
| `code-review` | Model | Two-axis review (Standards vs Spec) executed via parallel sub-agents to avoid context pollution. |
| `codebase-design` | Model | Shared vocabulary & principles for deep modules (Ousterhout: interface vs implementation, depth, seams). |
| `diagnosing-bugs` | Model | Gated diagnosis loop for hard bugs (tight feedback loop -> minimize -> hypothesize -> instrument -> fix). |
| `domain-modeling` | Model | Actively builds/sharpens domain glossary (`CONTEXT.md`) and Architectural Decision Records (`docs/adr/`). |
| `grill-with-docs` | User | Relentless interview to sharpen design while concurrently updating `CONTEXT.md` and ADRs. |
| `implement` | User | Implements tickets/specs, driving `tdd` at agreed seams and concluding with `code-review`. |
| `improve-codebase-architecture` | User | Scans codebase for deepening opportunities, generates visual HTML report in temp dir, and grills candidates. |
| `prototype` | Model | Builds throwaway prototype (HTML file or toggleable UI variations) to answer design questions. |
| `research` | Model | Investigates questions against primary sources and writes cited Markdown notes via background agent. |
| `resolving-merge-conflicts` | Model | Resolves git merge/rebase conflicts hunk by hunk, tracing intent to primary sources. |
| `setup-matt-pocock-skills` | User | Scaffolds repo configuration (issue tracker, triage labels, domain doc layout) and updates CLAUDE.md/AGENTS.md. |
| `tdd` | Model | Test-Driven Development reference (red-green-refactor vertical slices at pre-agreed public seams). |
| `to-spec` | User | Synthesizes current conversation into a formal spec published to the configured issue tracker. |
| `to-tickets` | User | Decomposes a spec into tracer-bullet tickets with explicit blocking edges. |
| `triage` | User | Moves issues/PRs through canonical triage states (`needs-triage`, `needs-info`, `ready-for-agent`, etc.). |
| `wayfinder` | User | Plans massive multi-session work as a graph of decision tickets resolved sequentially. |
| `wizard` | Model | Generates interactive bash wizard for human-only operations (credentials, infra provisioning). |

#### Category 2: `productivity` (7 skills)
| Skill Name | Invocation | Summary / Role |
| :--- | :--- | :--- |
| `grill-me` | User | Relentless design-tree interview to sharpen a plan or decision (delegates to `grilling`). |
| `grilling` | Model | The reusable interview primitive mapping decisions into frontier questions and design trees. |
| `handoff` | User | Compacts current conversation into a structured handoff document for another agent session. |
| `teach` | User | Multi-session tutoring skill using the workspace as a stateful teaching environment. |
| `to-questionnaire` | User | Formats unresolved decisions into an async Markdown questionnaire for human stakeholders. |
| `wait-what` | User | Stops and re-pitches misunderstood messages using plain English and `CONTEXT.md` vocabulary. |
| `writing-for-agents` | Model | Rules for authoring agent-facing documents (skills, CLAUDE.md, pointers, context load vs cognitive load). |

#### Category 3: `in-progress` (9 skills)
| Skill Name | Invocation | Summary / Role |
| :--- | :--- | :--- |
| `claude-handoff` | User | Hands conversation off to a background Claude agent. |
| `implement-spec` | User | In-progress alternative to `implement`. |
| `loop-me` | User | Experimental workflow spec interview. |
| `pr` | Model | Template and guidelines for writing concise, scannable pull request bodies. |
| `retro` | User | Retrospective analysis of a coding session. |
| `setup-ts-deep-modules` | User | Wires `dependency-cruiser` into TypeScript packages. |
| `writing-beats` | User | Writing exploit phase: assemble material into a journey of beats. |
| `writing-fragments` | User | Writing explore phase: collect unstructured raw fragments. |
| `writing-shape` | User | Writing exploit phase: shape fragments into an article paragraph by paragraph. |

#### Category 4: `misc` (4 skills)
| Skill Name | Invocation | Summary / Role |
| :--- | :--- | :--- |
| `git-guardrails-claude-code` | Model | Installs PreToolUse bash hooks to hard-block `git push`, `reset --hard`, etc. |
| `migrate-to-shoehorn` | Model | Migrates TypeScript tests from `as` casts to `@total-typescript/shoehorn`. |
| `scaffold-exercises` | Model | Scaffolds exercise directories for video courses. |
| `setup-pre-commit` | Model | Installs Husky and lint-staged (Prettier, test, typecheck). |

---

## 4. Investigation of CLI Behavior (`npx skills add`)

### 4.1 CLI Help Specification
Running `npx skills --help` reveals the following key options:
- `add <package>`: Add a skill package (URL or GitHub owner/repo).
- `-g, --global`: Install globally instead of project-level.
- `-a, --agent <agents>`: Specify agent target (e.g. `claude-code`, or `*`).
- `-s, --skill <skills>`: Specify skill names to install (separated by space or multiple `-s`).
- `-l, --list`: List available skills in the repository without installing.
- `-y, --yes`: Skip confirmation prompts.
- `--copy`: Copy files instead of symlinking.
- `--all`: Shorthand for `--skill '*' --agent '*' -y`.

### 4.2 Non-Interactive Behavior in Agent Environment
When running `npx skills add "https://github.com/mattpocock/skills"` inside an agent environment:
1. The CLI detects the execution context and prints:  
   `• antigravity Agent detected — installing non-interactively`
2. If **no skill name is specified** (`--skill` omitted), the CLI **does not prompt**; instead, it automatically selects and installs **all 38 skills**.
3. If `--agent` is not specified, it writes them into `.agents/skills/<skill-name>`.
4. If `--agent claude-code` is specified, it writes them into `.claude/skills/<skill-name>`.

### 4.3 Lockfile Integration
The CLI updates or generates `skills-lock.json` at the root of the project, recording the skill name, source repo, sourceType (`github`), relative skillPath, and sha256 `computedHash`.

---

## 5. Relevance Assessment & Skill Selection Matrix

### 5.1 Criteria for Relevance
To determine which skills from `mattpocock/skills` are relevant to `AjsClaudeCodeTools`:
1. **Domain Alignment**: Is the skill useful for developing, refining, and testing Claude Code plugins, hooks, documentation, and agent tooling?
2. **Compatibility**: Does the skill complement rather than fight the existing repo's architecture and philosophy?
3. **Execution Feasibility**: Can the skill operate cleanly in this environment (Python/Markdown/JSON)?

### 5.2 Category-by-Category Evaluation

| Skill | Verdict | Rationale |
| :--- | :---: | :--- |
| **`setup-matt-pocock-skills`** | **ESSENTIAL** | Prerequisites orchestrator required before other engineering skills can locate issue trackers, triage labels, and domain docs. |
| **`writing-for-agents`** | **CRITICAL** | Core discipline for authoring/editing skills, CLAUDE.md, and agent docs. Directly applicable to this entire repo. |
| **`research`** | **CRITICAL** | Primary-source investigation pattern yielding Markdown artifacts in repo. Perfect match for research tasks. |
| **`grill-me`** | **KEEP** | Already installed in `.claude/skills/grill-me`. Used for plan alignment. |
| **`grilling`** | **KEEP** | Already installed in `.claude/skills/grilling`. The foundational decision-tree interview primitive. |
| **`grill-with-docs`** | **RELEVANT** | Couples `grilling` with active updating of `CONTEXT.md` and ADRs in `docs/adr/`. |
| **`domain-modeling`** | **RELEVANT** | Maintains project glossary and architectural decisions. Pairs with repo's tiered documentation. |
| **`code-review`** | **RELEVANT** | Dual-axis review (Standards vs Spec) using parallel sub-agents; enforces repo standards and Fowler smell baselines. |
| **`codebase-design`** | **RELEVANT** | Establishes deep module vocabulary (depth, interface, seams, leverage, locality) for Python modules and hooks. |
| **`tdd`** | **RELEVANT** | Red-green-refactor loop focused on pre-agreed seams; fits python `verify.py` and `verify_tools.py`. |
| **`diagnosing-bugs`** | **RELEVANT** | Structured bug reproduction and diagnosis loop via deterministic feedback loops. |
| **`to-spec`** | **RELEVANT** | Turns discussions into issue tracker specifications. |
| **`to-tickets`** | **RELEVANT** | Decomposes specs into tracer-bullet tickets with dependency edges. |
| **`implement`** | **RELEVANT** | Standard implementation orchestrator driving TDD and code review. |
| **`improve-codebase-architecture`** | **RELEVANT** | Deepening opportunity scanner producing visual HTML reports. |
| **`resolving-merge-conflicts`** | **RELEVANT** | Standard git conflict resolution discipline. |
| **`ask-matt`** | **RELEVANT** | Skill routing assistant. |
| **`handoff`** | **RELEVANT** | Compacting session state for clean handoff. |
| **`wait-what`** | **RELEVANT** | Miscommunication recovery tool. |
| **`pr`** | **RELEVANT** | Clean PR description generator. |
| **`git-guardrails-claude-code`** | **DO NOT ADD** | **CONFLICTS DIRECTLY WITH HOUSE-RULES**. `house-rules`' PreToolUse hook already checks dangerous git commands and asks confirmation without blocking outright. Installing this would clash with the plugin's stated philosophy and create competing hooks. |
| **`migrate-to-shoehorn`** | **DO NOT ADD** | TypeScript type-assertion migration tool; inapplicable to this Python/Markdown repo. |
| **`setup-pre-commit`** | **DO NOT ADD** | Husky/npm pre-commit setup; repo uses zero-npm Python stdlib test runners. |
| **`setup-ts-deep-modules`** | **DO NOT ADD** | TypeScript-specific `dependency-cruiser` wiring. |
| **`scaffold-exercises`** | **DO NOT ADD** | Domain-specific video course exercise generator. |
| **`teach`** | **DO NOT ADD** | Educational tutoring assistant; not relevant to current development/maintenance work. |
| **`wizard`** | **SKIP** | Generates bash wizards for cloud/infra provisioning. |
| **`triage`** | **OPTIONAL** | Issue state machine; only useful if actively managing an open GitHub issue tracker. |
| **`wayfinder`** | **OPTIONAL** | Multi-session epic planning. |
| **`writing-beats` / `fragments` / `shape`** | **DO NOT ADD** | Experimental in-progress essay writing skills. |
| **`claude-handoff` / `implement-spec` / `loop-me` / `retro`** | **DO NOT ADD** | Experimental / in-progress drafts. |

---

## 6. Detailed Skill Instructions & Operational Directives

### 6.1 `setup-matt-pocock-skills`
- **Trigger**: Run once per repo.
- **Workflow**:
  1. **Explore**: Probe git remote (`git remote -v`), check for existing issue trackers, inspect `CLAUDE.md` / `AGENTS.md`, `CONTEXT.md`, `docs/adr/`.
  2. **Present Findings & Questions**:
     - **Section A (Issue Tracker)**: GitHub Issues (`gh`), GitLab (`glab`), or Local Markdown (`.scratch/`). For this repo, GitHub issues (or local markdown) is standard.
     - **Section B (Triage Labels)**: If `triage` is installed, define the 5 canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
     - **Section C (Domain Docs)**: Single-context (`CONTEXT.md` + `docs/adr/` at root) vs Multi-context (`CONTEXT-MAP.md`).
  3. **Edit `CLAUDE.md`**: Add an `## Agent skills` section pointing to `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, etc.
  4. **Scaffold Docs**: Create `docs/agents/issue-tracker.md` and `docs/agents/domain.md`.

### 6.2 `writing-for-agents`
- **Core Directives**:
  - Treat instructions as documents for an agent taking a predictable process rather than producing identical text.
  - **Context Pointers**: Front-load trigger words, collapse duplicate branches, eliminate preamble.
  - **Information Hierarchy**:
    1. In-file steps (primary process)
    2. In-file reference (rules/heuristics)
    3. Disclosed reference (pushed into external files behind pointers)
  - **Completion Criteria**: Ensure every step has an unambiguous, testable completion bound.
  - **Leading Words**: Anchor behaviors with established terms (e.g. *tight*, *red*, *tracer bullet*).
  - **Prompt Positive**: Ban prohibitions without a positive target. Don't say "don't do X"; say "do Y instead".

### 6.3 `research`
- **Core Directives**:
  - Delegate legwork to a background agent.
  - Base findings exclusively on primary sources (specs, code, official documentation, official CLI behavior), never secondary summaries.
  - Output findings to a cited Markdown document saved according to repository conventions.

### 6.4 `code-review`
- **Core Directives**:
  - Run two distinct sub-agents in parallel:
    - **Standards**: Checks repo documented conventions (`CODING_STANDARDS.md`, `CLAUDE.md`) plus the Fowler smell baseline (Feature Envy, Primitive Obsession, Speculative Generality, etc.).
    - **Spec**: Checks implementation fidelity against originating issue or spec.
  - Aggregate findings separately under `## Standards` and `## Spec` without merging or re-ranking.

### 6.5 `codebase-design`
- **Core Directives**:
  - Standardize vocabulary: **Module**, **Interface**, **Implementation**, **Depth**, **Seam**, **Adapter**, **Leverage**, **Locality**.
  - Favor deep modules (small interface, rich hidden implementation).
  - Enforce Michael Feathers' seam concept: public test surface without internal coupling.

### 6.6 `tdd`
- **Core Directives**:
  - Red before green: Write failing test at pre-agreed seam first.
  - Vertical slices (tracer bullets): One seam, one test, minimal code.
  - Ban tautological assertions and implementation coupling.

---

## 7. Sources Explicitly Cited

1. **Remote Skills Repository**:
   - `https://github.com/mattpocock/skills`
   - Commit `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`
   - Files:
     - `README.md`
     - `skills/engineering/setup-matt-pocock-skills/SKILL.md`
     - `skills/productivity/writing-for-agents/SKILL.md`
     - `skills/engineering/research/SKILL.md`
     - `skills/engineering/code-review/SKILL.md`
     - `skills/engineering/codebase-design/SKILL.md`
     - `skills/engineering/tdd/SKILL.md`
     - `skills/engineering/diagnosing-bugs/SKILL.md`
     - `skills/engineering/domain-modeling/SKILL.md`
     - `skills/engineering/improve-codebase-architecture/SKILL.md`
     - `skills/engineering/grill-with-docs/SKILL.md`
     - `skills/productivity/grilling/SKILL.md`
     - `skills/productivity/grill-me/SKILL.md`
     - `skills/misc/git-guardrails-claude-code/SKILL.md`
2. **Local Workspace Files**:
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\README.md`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\CLAUDE.md`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\skills-lock.json`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\.claude\skills\grill-me\SKILL.md`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\.claude\skills\grilling\SKILL.md`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\claude-house-rules\plugins\house-rules\scripts\verify.py`
   - `C:\Users\aj\.gemini\antigravity\worktrees\AjsClaudeCodeTools\add_mattpocock_skills\tools\verify_tools.py`
3. **CLI Commands Executed & Inspected**:
   - `npx skills --help`
   - `npx skills add "https://github.com/mattpocock/skills" --list`
   - `npx skills list`
   - `git status`, `git log`, `git remote -v`

---

## 8. Recommendations for Planner & Implementer

1. **Exact Addition Command**:
   Execute the skill installation targeting `claude-code` and explicitly selecting the recommended subset of skills:
   ```bash
   npx skills add "https://github.com/mattpocock/skills" --agent claude-code --skill setup-matt-pocock-skills writing-for-agents research grill-with-docs domain-modeling code-review codebase-design tdd diagnosing-bugs to-spec to-tickets implement improve-codebase-architecture resolving-merge-conflicts ask-matt handoff wait-what pr -y
   ```
2. **Setup Execution**:
   Run `/setup-matt-pocock-skills` instructions:
   - Create `docs/agents/issue-tracker.md` (pointing to GitHub issues / `gh` CLI).
   - Create `docs/agents/domain.md` (declaring single-context layout).
   - Carefully update `CLAUDE.md` to append the `## Agent skills` block without disturbing existing guidance or causing `verify.py` duplication errors.
3. **Verification**:
   Run `python claude-house-rules/plugins/house-rules/scripts/verify.py` and `python tools/verify_tools.py` to confirm that all additions preserve the repository's verification standards.
