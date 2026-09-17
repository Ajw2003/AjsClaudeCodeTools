# Decisions

The paper trail: what was decided, when, why, what alternatives were rejected, and what it
superseded. Append-mostly — newest entry at the top. An entry is never rewritten or deleted; the
one allowed edit to an existing entry is flipping its `Status` line to `Superseded`, with a
pointer, when a later entry replaces it.

---

## 2026-09-17 — Route a hook-relayed command through the same verified-command rule as any other

**Context.** A live session hit `versioncheck`'s out-of-date banner (installed plugin behind the
marketplace clone), printed the exact fix command as a plain fenced block with no `UNTESTED:`
label, and moved straight into unrelated repo exploration in the same reply — the command had
never been run on that machine, and the turn never paused for an answer. `rules/house-rules.md`
already had a rule against handing over an unverified command, and a narrower rule about stopping
after a page offer; neither said a command relayed from a hook's own diagnostic got the same
treatment, so `event_versioncheck()`'s banner text told Claude only to "tell the user plainly ...
and give them the update command(s)," with no card/`UNTESTED:` instruction and no instruction to
stop.

**Decision.** Extended "Never hand over a command I have not run" in `rules/house-rules.md` to
cover a command relayed from a hook, tool, or diagnostic explicitly — same card, same `UNTESTED:`
marker unless actually run this session on this machine — and added "Telling them is not the same
as stopping for them": once something needs the user's answer before I continue, I say so and then
stop, rather than continuing into unrelated work in the same turn. Reworded `event_versioncheck()`'s
banner in `hook.py` to instruct exactly that (card format, `UNTESTED:`, then stop and wait), and
updated `CLAUDE.md`'s hooks table to match. Added a `verify.py` check that the banner actually
carries those instructions (not just the right command), and a bidirectional drift check between
`rules/house-rules.md` and the banner text so a future reword on either side gets caught — see
`docs/systems/verify-suites.md`, "Traps". Bumped `plugin.json` 2.24.1 → 2.24.2 for the rule/hook
change.

**Why.** The command-verification rule and the page-offer stop-and-wait rule already existed
separately; a command that arrived via a hook's own diagnostic fell through the gap between them
because neither one said it applied to a relayed command. Naming the problem out loud and then
continuing into unrelated work is functionally the same failure as never naming it — the user
still has to notice, on their own, that nothing is actually waiting on their answer.

**Status.** Standing.

---

## 2026-09-15 — Widen the version-bump gate to root CLAUDE.md and docs/, not just PLUGIN_ROOT

**Context.** While preparing to merge the docs-tier-scaffolding PR (the one that added
`docs/README.md`, `Roadmap.md`, `ProjectState.md`, `Today.md`, and `docs/systems/*`),
`tools/check_plugin_version_bump.py` (added the same day; see the entry below) reported "no
plugin files changed, no bump required" for a PR that changed only root `CLAUDE.md` and files
under `docs/`. The user objected: both are directly used by the plugin and change as the plugin
is worked on and used live in this repo — `CLAUDE.md` is auto-loaded into every session here, and
`docs/` is read and written continuously while following the rules — even though neither ships
inside the installed plugin package the check's `PLUGIN_ROOT` constant was scoped to.

**Decision.** Widened `check_plugin_version_bump.py`'s notion of "plugin-relevant" beyond
`PLUGIN_ROOT` to also cover the root `CLAUDE.md` file (exact match) and everything under `docs/`
(prefix match), via a `PLUGIN_RELEVANT_PREFIXES`/`PLUGIN_RELEVANT_EXACT` pair and an
`_is_plugin_relevant()` helper. Added matching cases to `tools/verify_tools.py`'s `decide()`
table. Bumped `plugin.json` 2.24.0 → 2.24.1 for the PR this was raised against, now that it
requires one under the widened rule.

**Why.** The check exists to stop the exact failure the entry below describes — a version-gated
updater reporting "already at the latest version" while content the user actually relies on has
changed underneath it. Root `CLAUDE.md` and `docs/` are exactly that kind of content for this
repo: they're not packaged into what `claude plugin install` ships, but they're what a live
session in this repo actually reads and is governed by, which is the same "did the thing I rely
on change" question the original incident was about. Scoping the check to `PLUGIN_ROOT` alone
answered a narrower question than the one it was built to answer. The alternative — leave the
check as-is and just bump the version for this one PR without changing the check's logic — was
rejected because it would have left the same gap open for the next PR that touches only
`CLAUDE.md` or `docs/`.

**Status.** Standing.

---

## 2026-09-15 — Enforce the version bump instead of trusting it, in this repo and on the desktop

**Context.** Two merged PRs (#33, #34) changed files under
`claude-house-rules/plugins/house-rules/` without bumping `.claude-plugin/plugin.json`'s
`version`. Every prior content-changing commit had bumped it; nothing enforced the convention, so
it silently lapsed. The result: `claude plugin update` — version-gated — reported "already at the
latest version" on the desktop after a full `tools/bootstrap.ps1` run, while the installed cache
still held the pre-#33/#34 content. `tools/force_update.py` (a pre-existing manual escape hatch
that hash-compares the installed cache against the marketplace source tree) confirmed the mismatch
and, once run, confirmed the fix after #35 bumped the version. The real failure was not "forgot to
bump a number" — it was that a tool's own "already up to date" message was trusted without
checking whether the underlying content actually matched. Full design:
[`docs/plans/2026-09-15-plugin-version-bump-guard.md`](plans/2026-09-15-plugin-version-bump-guard.md).

**Decision.** Two separable fixes for the two places this failed. (1) This repo: a new
`tools/check_plugin_version_bump.py` compares `plugin.json`'s version between a PR's base and
head whenever a file under the plugin changed, and fails the change if the version did not
strictly increase; wired into the existing `verify` CI job (`fetch-depth: 0` plus a
pull-request-only step), with branch protection on `main` requiring that check to follow in a
separate step once this PR merges. (2) Any project: a new house rule, "A reported update is not
a completed one," naming this failure shape by pattern rather than by PR number. (3) Local
tooling: `tools/install.py`'s install steps now hash-compare the installed cache against source
after every install/update, using `tree_hash()`/`diff_trees()` factored out of
`tools/force_update.py` into `tools/_plugin_sync.py` so the two scripts share one implementation;
on a mismatch it automatically runs the same uninstall+reinstall sequence `force_update.py` used
manually, re-verifies, and only surfaces to the user if that self-heal still doesn't match.

**Why.** The convention ("bump the version when you touch the plugin") was correct but
unenforced, so it lapsed exactly once and nothing caught it before it shipped. A reminder to
"remember next time" would have the same shelf life as the original convention. Enforcement — a
CI gate that blocks the merge, and local tooling that verifies rather than trusts — closes the gap
structurally instead of relying on memory a second time. The house rule generalizes the lesson
beyond this repo: any version-gated updater can report "no-op" truthfully about the one field it
compared while being wrong about whether the underlying content changed.

**Status.** Standing.

---

## 2026-09-15 — Distinguish "the machine I run on" from "the machine a handover targets"

**Context.** A Step 2 command handed over earlier the same day assumed Linux/bash — wrong, the
user is on Windows/PowerShell. Root cause, confirmed by reading the code: `rules/house-rules.md`'s
"Find out what machine you are on, then build for that" rule and `hook.py`'s
`_detect_environment()` only ever described **the machine executing this session's tool-calls**.
For a local CLI/IDE/Desktop-Code-tab session that machine and the user's own machine are the same
box, so the rule had always been correct there. The session that made the mistake was remote
(`CLAUDE_CODE_REMOTE=true`, `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`): the sandbox
`hook.py` ran on was Linux, the user's actual machine was Windows, and nothing in the rule or the
injected "This machine" profile ever flagged that these could differ. The rule's own example text
even listed "a cloud session on Linux" as just another machine to build for, reinforcing the
conflation instead of catching it. The evidence needed to fix this without guessing already
existed in the repo: `docs/example-environment.md`, a committed worked-example record of aj's real
machine (Windows 11 Pro, PowerShell, Git Bash for POSIX, `sh`/`bash` not on PATH), dated
2026-08-25 — and the user separately confirmed PowerShell was in fact right. Full design in
[`docs/plans/2026-09-15-handover-target-machine.md`](plans/2026-09-15-handover-target-machine.md).

**Decision.** Give the plugin a second, distinct machine-local record —
`rules/handover-target.md`, gitignored, same shape and lifecycle as `rules/environment.md` — that
answers "what machine will a human run a step-card's command on," never confused with the
sandbox's own profile. `hook.py`'s `event_inject()` only reads and injects it when
`CLAUDE_CODE_REMOTE` is set, so a local session pays nothing: recorded content is injected under a
heading distinct from "This machine"; missing content becomes an instruction to find out (check
`docs/example-environment.md`, or ask) and record it, so a later session in the same remote
environment does not have to ask again. Extended the "Find out what machine you are on" rule in
`rules/house-rules.md` with a clause naming the local/remote distinction, added matching
`verify.py` cases and a drift check, and updated `.gitignore` and the root `CLAUDE.md` hook table.

**Why.** The two questions — where do my tool-calls run, and where will the user run what I hand
them — are the same question on every local session, which is why the conflation was invisible
until a remote session exposed it. Detecting the user's actual machine at runtime is impossible
from inside the sandbox; the fix is to make the gap askable and rememberable exactly once per
remote environment, rather than silently building for the wrong machine.

**Status.** Standing.

---

## 2026-09-15 — A third non-tier folder, `docs/generated/`, for generated artifacts

**Context.** The tiered-docs system had two non-tier folders: `docs/plans/` (forward intent) and
`docs/archive/` (inert docs) — both hand-written. The `artifact` hook already caught a document
written outside the project and reminded Claude to copy it in, but it sent every extension to the
same place: "docs/ for documents, docs/plans/ for plans." Nothing distinguished a hand-written
markdown doc from an HTML report or other tool output, so both landed in `docs/`. This repo had
two loose examples proving the gap: `docs/architecture-review-2026-09-07.html` and
`docs/2026-09-09-branch-aware-guard-rollout.html`, sitting directly in `docs/` with no other
document like them. Full design and exact wording constraints are in the plan this decision
executed: [`docs/plans/2026-09-15-generated-artifacts-directory.md`](plans/2026-09-15-generated-artifacts-directory.md).

**Decision.** Add `docs/generated/` — a third non-tier folder for tool-produced deliverables:
HTML reports, exported diagrams/images, anything from the Artifact tool or a generated-report
script. Made the `artifact` hook's routing extension-aware: hand-authored `md`/`txt` still go to
`docs/` (or `docs/plans/` for a plan), while tool-produced `html`/`csv`/`json`/`svg`/`pdf` now go
to `docs/generated/` instead. Updated `rules/house-rules.md`, the `project-docs` skill, and
`CLAUDE.md`'s hook table to match, and moved this repo's two loose HTML files into the new
folder with a `README.md` explaining it.

**Why.** `docs/plans/` and `docs/archive/` are both hand-written; a generated HTML report is
neither forward-looking intent nor a formerly-true document — it's tool output that gets
regenerated, not edited, when it needs to change. Mixing it into `docs/` made `docs/` unreliable
as "documentation" versus "whatever a tool happened to produce." Giving generated artifacts their
own folder keeps `docs/` readable as hand-authored documentation while still backing up generated
output as a tracked, committable file instead of leaving it in a scratchpad or temp directory.

**Status.** Standing.

---

## 2026-09-15 — Add a sixth documentation tier, `docs/Decisions.md`

**Context.** `house-rules:project-docs` defined five tiers (`README.md`, `Roadmap.md`,
`ProjectState.md`, `systems/*.md`, `Today.md`) plus two non-tier folders (`plans/`, `archive/`).
None of the five was *why*: tier 3 says where things stand, tier 4 says how a system works
*today*, but nothing durable recorded why a choice was made, what was tried and rejected, or what
an earlier decision used to say before it was reversed. That gap was already visible as ad hoc
workarounds in this repo — [`docs/rules-backlog.md`](rules-backlog.md) and
[`docs/architecture-backlog.md`](architecture-backlog.md) are hand-rolled decision logs (Status /
Defect / Evidence / "what the rule should say" per entry) that exist only because nothing in the
shipped tier system covered this. The `harvest` hook and `archivist` subagent also misfiled this
material — design rationale or a bug post-mortem got routed into a tier-4 system doc's *How it
works*/*Traps*, which is supposed to describe current truth, not carry historical narrative. Full
design and the exact wording constraints are in the plan this decision executed:
[`docs/archive/2026-09-15-sixth-documentation-tier.md`](archive/2026-09-15-sixth-documentation-tier.md).

**Decision.** Add Tier 6 — `docs/Decisions.md` — to the house-rules tiered-docs system: one
running, dated, append-mostly log (Context/Decision/Why/Status per entry), as designed in the
plan above. Updated `rules/house-rules.md`, the `project-docs` skill, the `archivist` subagent's
routing, and `hook.py`'s `HARVEST_NOTE` so rationale, rejected approaches, and post-mortems route
here instead of into tier-4 system docs; ongoing mechanisms, invariants, and operational traps
still go to tier-4, unchanged. Bumped the plugin version 2.20.0 → 2.21.0.

**Why.** `docs/plans/` is forward-looking intent that goes inert once executed and moves to
`docs/archive/`; `docs/archive/` holds documents that are no longer true. Neither is the right
home for a decision's reasoning, which stays true history even after the decision it describes is
superseded — it isn't inert, and it isn't forward-looking. A single append-mostly file (matching
the shape of tiers 2/3/5, not tier 4's per-system folder, since entries are short and
chronological rather than one-per-topic) gives `harvest`/`archivist` a real destination instead of
stuffing rationale into a system doc, and lets tiers 1–5 stop carrying their own change history
inline — they rewrite cleanly to state current truth and leave a one-line pointer into this log.
The alternative of folding decisions into tier-4 `Traps`/`How it works` was rejected because it
conflates "what is true now" with "what we chose and why," which is exactly the misfiling this
tier fixes.

**Status.** Standing.
