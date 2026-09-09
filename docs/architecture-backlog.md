# Architecture backlog

Deepening opportunities identified in the plugin's own code but not yet decided on. Sibling to
[`rules-backlog.md`](rules-backlog.md), which queues changes to
[`rules/house-rules.md`](../claude-house-rules/plugins/house-rules/rules/house-rules.md); this
file queues changes to the code that enforces it — `hook.py`, `verify.py`, and the files they
police.

An entry here is a **candidate, not a commitment** — that is the one way this file differs from
`rules-backlog.md`. Nothing here has been approved. Each entry names the friction, the evidence
with file and line, and what would change; entries carry a strength (`strong` / `worth exploring`
/ `speculative`) so a later reader knows how much of the argument was already made. When one
ships, delete the entry — the code is the record, this is only the queue.

Vocabulary below is from the `/codebase-design` skill: **module**, **interface**,
**implementation**, **depth**, **shallow**, **seam**, **adapter**, **leverage**, **locality**.

---

## Baseline

Raised 2026-09-07 against `11b5744`. `python claude-house-rules/plugins/house-rules/scripts/verify.py`
→ **101 checks, all PASS**. Every claim below was read out of the tree at that commit; the check
count is quoted here as the baseline a change is measured against, not as a number to maintain
(the suite computes its own, and `verify.py` fails any doc that hardcodes one — this file states
it once, as evidence, and must not restate it).

Where the churn is, over the last 80 commits:

| File | Touches |
|---|---|
| `CLAUDE.md` | 22 |
| `claude-house-rules/README.md` | 19 |
| `scripts/verify.py` | 18 |
| `.claude-plugin/plugin.json` | 17 |
| `scripts/hook.py` | 15 |
| `rules/house-rules.md` | 15 |
| `docs/desktop-verification.md` | 13 |

Six of those seven are the rules text, a restatement of it, or a check policing the two. That is
what pulled the review toward entries 1, 2 and 5 rather than anywhere else in the tree.

---

## 1. The rules text has nine restatements and no module holding them

**Status:** open, `strong`. Raised 2026-09-07.

**The friction.** `rules/house-rules.md` is canonical, and nine places restate part of it:
`SCOPE_REMINDER`, `SCOPE_REMINDER_SHORT`, `RUNNABLE_NOTE`, `DELEGATE_NOTE` and `HANDOVER_NOTE` in
`hook.py`, plus `output-styles/handover-cards.md`, `agents/executor.md`,
`templates/step-card.html` and `docs/claude-ai-instructions.md`. That relationship is real and
load-bearing — `CLAUDE.md` states it as an editing rule — but no module holds it. Each restatement
is policed by a hand-copied `drift = []` / loop / PASS-FAIL block: nine of them, at `verify.py`
lines 418, 544, 574, 688, 834, 869, 960, 983 and 1283. The interface is as wide as the
implementation.

**Evidence — this is a live gap, not a tidiness complaint.** Three of the nine check only that the
phrase still appears in `house-rules.md`, never that it still appears in the restatement they are
named for:

- `verify.py:545` (`runnable`) matches `"whole workflow"`, `"starting point"` and
  `"hand over a command"` against `rules_text` only.
- `verify.py:575` (`delegate`) matches `"@house-rules:executor"` and `"plan is settled"` the same way.
- `verify.py:689` (`handover`) matches fourteen phrases the same way — the longest checklist in the
  plugin.

So `"starting point"` and `"hand over a command you have not run"` can both be deleted from
`RUNNABLE_NOTE` and the suite still reports every check passing. Only the long-form `scope` check at
`verify.py:435` actually reads an emitted string, and only because it was added separately for cost
reasons.

**What would change.** One `Restatement(source, phrases)` table plus a single checker behind it.
Each row names where the text lives and which phrases bind it to the canonical rules; the checker
asserts **both** directions for every row, so the gap above closes by construction rather than by
remembering. Adding a tenth restatement becomes a row, not a block.

**Deletion test.** Passes: delete the module and the both-directions assertion reappears nine times.

**Open questions.**

- Do all nine restatements bind the same way? `templates/step-card.html` is checked for JS field
  names (`title:`, `location:`, …), not prose phrases — it may be a second kind of row rather than
  the same kind.
- `executor.md`'s digest is checked for phrases that must be *absent* too (`"already in this
  session"`, `verify.py:832`). A row may need both a requires and a forbids list.

---

## 2. The failure-mode contract is written three times

**Status:** open, `strong`. Raised 2026-09-07.

**The friction.** Which way each handler fails — closed, loud, or quiet — is the load-bearing design
decision of this plugin, and `CLAUDE.md` devotes a section to it. It is stated in three places that
must agree and are not checked against each other: the module docstring (`hook.py:16–22`), each
handler's own `try/except` (`:121–140`, `:390–397`, `:446–477`, `:545–560`, `:649–656`, `:696–703`,
`:820–829`), and `main()`'s last-resort `if event == "guard"` / `if event == "inject"` chain
(`:854–891`). A new event means remembering all three, and nothing fails if you don't.

**Evidence.** `verify.py` has to reach past the interface to test it: `:186` and `:286` build Python
source in a string (`crash_snippet = "import sys, hook\n…"`) to monkeypatch `hook.read_payload` and
`hook._read_text`, because there is no seam at which a failing input can be injected. That is the
"testing past the interface" smell — the module is the wrong shape for the test that matters most.

**What would change.** Make the policy the value in the existing `EVENTS` table:
`{"guard": (event_guard, FailClosed), "inject": (event_inject, FailLoud), …}`. Handlers compute a
decision or raise; the dispatch seam owns fail-closed, fail-loud and fail-quiet. `main()`'s `if
event ==` chain becomes a lookup, and the contract becomes assertable directly — one check per row —
instead of via two embedded source strings.

**Open questions.**

- `guard`'s failure path also lives in `run.sh` (no interpreter at all is a blocking failure). The
  table covers `hook.py` only; whether `run.sh` should be driven from the same data, or stay
  hand-written and be checked against it, is undecided.
- `scope` is the strictest case — a non-zero exit erases the user's prompt. Its safety currently
  comes from a `try/except` the reader can see inside `event_scope`. Moving it to the seam is
  correct but makes the guarantee less visible at the call site; that trade needs a decision.

---

## 3. Four near-identical payload-field regexes

**Status:** open, `worth exploring`. Raised 2026-09-07.

**The friction.** "Pull one field out of the payload without trusting the whole thing to parse" is
stated four times: `_PROMPT_FIELD_RE` (`hook.py:443`), `_COMMAND_FIELD_RE` (`:537`),
`_LAST_MESSAGE_FIELD_RE` (`:777`) and `_FILE_PATH_RE` (`:601`), plus two extractor functions
(`_guard_subject` `:540`, `_extract_file_path` `:611`) and one inline `m.group(0)` (`:809`). The
comment at `:775` says as much: *"Same shape as `_COMMAND_FIELD_RE`"*.

**Evidence.** The fourth silently differs. Three match the raw JSON slice and allow backslash-escaped
quotes (`(?:[^"\\]|\\.)*`); `_FILE_PATH_RE` captures the value with `([^"]*)` and drops escape
handling. Nothing currently exercises a Windows path with an escaped quote in it, so the divergence
is unobserved rather than proven harmless.

**What would change.** One `field_slice(payload, name)` at that seam, with raw-slice-vs-value as a
parameter. `guard`'s deliberate three-tier ladder — field absent means fall back to matching the
whole payload — moves inside it and gets tested once instead of being re-derived per handler.

**Open question.** The ladder's middle tier is `guard`-specific: `artifact` and `runnable` return
early when the field is absent rather than falling back. Whether the fallback is a parameter or
stays at the `guard` call site is the actual design decision here.

---

## 4. `event_standards` mixes detection with prose

**Status:** open, `worth exploring`. Raised 2026-09-07.

**The friction.** `hook.py:271–397` is one 127-line function doing five things: parse the
`.claude/standards` override, scan depth-1 for markers, rescan from the parent when the project root
is a Unity `Assets/` folder, assemble English grammar (`"One"`/`"Two"`, plural, verb — `:346–369`),
and read bodies and emit. There is no seam between deciding *which documents apply* and *how that
reads*.

**Evidence.**

- The rescan at `:309–314` retypes the detection loop from `:293–299` verbatim rather than calling
  it again.
- All nine standards checks in `verify.py` (`:1131–1242`) assert on the emitted prose —
  `"### csharp-unity-standards.md" in out`, `"in \`Game/\`" in out`, `"Assets/\` folder" in out` —
  because prose is the only interface detection has. Rewording the preamble breaks detection tests
  that have nothing to do with the wording.

**What would change.** A seam between them: `detect(project_dir)` returns which documents apply and
why; `render(selections)` turns that into `additionalContext`. The rescan becomes a second call to
`detect`. Detection tests then assert on values, and prose tests stop being detection tests.

**Open question.** The `systemMessage` for a document named in `.claude/standards` but missing
(`:379–384`) is produced during body loading, which straddles the proposed seam. It may belong to a
third step, or to `render`.

---

## 5. `verify.py` has no interface beyond running the whole file

**Status:** open, `worth exploring`. Raised 2026-09-07. **Depends on nothing; entries 1 and 2 land
inside it.**

**The friction.** The suite is the repo's stated source of truth for whether a change took effect,
and it is 1306 lines executing at module scope. 88 `report()` call sites mutate two module globals
(`STEP`, `FAILURES`); 26 accumulator lists, four of them separately named `drift` (`:418`, `:544`,
`:574`, `:688`); `import re` sits at `:775`, mid-file, after 774 lines that do not use it.

**Evidence.** There is no way to run one check or one kind of check. Editing a single `guard` pattern
means running all 101 and reading the output to find the 28 that were relevant. The three `run_hook`
/ `run_shell` / fixture helpers are good and reused; everything above them is open-coded.

**What would change.** Each check becomes a value in one list — `GuardCase`, `HookCase`,
`StructureCheck`, `DocTable` — and the runner takes a name filter, so `verify.py guard` runs the 28.
Entries 1 and 2 then land as two more kinds of value rather than as more blocks.

**Constraints that must survive.** `CLAUDE.md` pins three things and this must not break any:
stdlib only, no test framework, and the check count computed at runtime and written down nowhere.

**Open question.** Whether the printed output stays byte-identical. The current format (numbered
line, then an indented detail line) is deliberate and documented in `CLAUDE.md` as the reason not to
open the script when something fails. A filter changes the numbering, which may be fine or may not.

---

## 6. The vocabulary and the settled reversals have nowhere to live

**Status:** open, `speculative`. Raised 2026-09-07.

**The friction.** The repo uses at least a dozen terms precisely and defines none of them as terms:
*the card*, *the six*, *restatement*, *drift check*, *surface*, *handler*, *fail closed / open /
loud*, *marker*, *the gate*, *the three-tier ladder*, *machine profile*, *the shim*. There is no
`CONTEXT.md` and no `docs/adr/`. `CLAUDE.md` is the hottest file in the repo (22 touches) partly
because it is the only place any of this lives — and it is auto-loaded every session and re-paid on
every subagent spawn, which its own header says it is trying to avoid.

**Evidence.** Settled reversals are re-argued in comments at three sites each:

- `force-for-plugin` was asserted *absent* in 2.3.0 and *present* in 2.4.0 — the argument appears at
  `verify.py:850–854`, in `output-styles/handover-cards.md`, and in `CLAUDE.md`.
- The `Stop` gate narrowing (rather than being switched off) is argued at `hook.py:790–805`,
  `verify.py:632–635`, and in `CLAUDE.md`'s hook table.
- The removed stateful deliverable machinery is still policed at `verify.py:715` and explained in
  `CLAUDE.md` and `docs/architecture.md`.

**What would change.** A `CONTEXT.md` holding the terms, and one ADR per reversal. The comments
shrink to a pointer.

**Open questions.**

- This repo already has `docs/architecture.md` for exactly the "long-form rationale" role, added by
  the token-footprint work. An ADR directory may be a second home for the same thing — the entry may
  reduce to "move the three reversals into `architecture.md` and point at it", with no new
  convention.
- `verify.py` currently reads `CLAUDE.md` for four checks. Anything moved out must not be one of the
  sections those depend on (the hook-event table, the surface table, the two duplication checks).
