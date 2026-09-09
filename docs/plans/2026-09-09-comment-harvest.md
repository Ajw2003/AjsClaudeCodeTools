# Harvest long-form comments into tier-4 docs

## Context

Claude writes long-form prose into source files — design rationale, bug post-mortems, physics
derivations, platform-quirk notes — in one consistent voice. The content is genuinely valuable;
its location is wrong. It rots there, because nothing forces it to change when the code does, and
it is invisible to anyone reading `docs/`.

The two failure modes to avoid are (a) telling Claude to stop writing them, which loses the
reasoning at the moment it is cheapest to capture, and (b) stripping them, which loses it
outright. The wanted behaviour is: **write them as you always have, then port them before the
turn ends.**

This repo is the proof case. `docs/architecture-backlog.md` §6 already records that settled
reversals are re-argued in code comments at three sites each and that "the comments shrink to a
pointer" — the same defect, raised independently, with no mechanism behind it. This is that
mechanism.

Nothing in `rules/house-rules.md` currently says anything about comment length, and
`rules/standards/coding-philosophy.md` says only "comment *why*, not *what*". The tier-4 spec in
`skills/project-docs/SKILL.md` already describes the destination precisely — system docs "give
the shape that the code's comments assume you already have" — so the destination exists and is
simply not being written to.

**Second, separable goal, raised while planning this:** nothing must fail silently. A caught
exception or an early return that produces no output is undebuggable by the human or the agent who
comes next, and that is the largest goal here. This change adds that as a rule, and applies it to
`hook.py` — including to code that already exists and currently violates it (see §0).

## Approach

Four pieces, matching the plugin's existing rule → hook → subagent split. **The hook only ever
nudges; Claude does the move.** No handler edits source files.

---

### 0. The failure-loudly rule, and the existing code it indicts

This lands first, because the harvest handler is written to it.

**New rule in `rules/house-rules.md`,** placed immediately after `## Build for a human working
alone` (currently ends line 105), which it extends:

> ## Nothing fails silently

Its substance: **silence means "I looked and there was nothing to do". Anything meaning "I could
not tell" says so, out loud, naming what it could not do and why.** A caught exception that
produces no output is a bug, not a safeguard. `except: pass` is forbidden. Degrading quietly is a
decision a shipped system may earn deliberately and record; it is never the default, and never in
something still being built — the phase where a silent failure costs the most is exactly the phase
where it is most tempting to add one. Failing loudly is not the same as failing *closed*: a check
that must not obstruct still announces that it did not run. And a diagnostic channel that ships
switched off does not count — nobody enables it until they are already lost, so the default has to
carry enough to answer "did this run, on what, and what did it decide".

**Why:** an agent or a human debugging this later has only the output. A path that produces
nothing is indistinguishable from a path that was never reached, and that is the difference
between a five-minute fix and an afternoon.

**This immediately indicts existing code**, which is the point — the rule is worthless if the
repo's own hooks violate it:

- `hook.py:874-891` — `main()`'s last-resort `except BaseException` net emits for `guard` and
  `inject` and **returns 0 silently for every other event**. So an internal crash in `scope`,
  `artifact`, `runnable`, `delegate` or `handover` is completely invisible. Fix: every event emits
  a `systemMessage` naming the event and that it did not run. `guard` keeps its stderr + exit 2.
- `event_delegate` (`hook.py:735`) has no `try` at all. Give it the same contract as its siblings.
- The `if not payload: return 0` early returns in `artifact` (`:641`) and `runnable` (`:688`) are
  the ambiguous case: an empty payload means the hook could not tell. Under the new rule these
  become loud. Keep the extension-gate returns silent — those are genuine "nothing to do".

**Make it self-enforcing.** `verify.py` gains a structural check over `hook.py` source: **no
`except` block returns without first calling `emit` or writing to stderr.** That is mechanical, it
is the kind of check the repo already does (the dead-state-file check at `verify.py:715` is the
same shape), and it means the rule cannot rot. This is the rule's test — `CLAUDE.md` warns that
untested rule text has no effect.

**The trace, on by default.** A debug channel that ships off is decoration — nobody turns it on
until they are already lost. So the decision trace is **always on**, and the design constraint is
therefore that it must be worth reading every single time. Three tiers:

1. **Out of jurisdiction → nothing.** A write to a `.md`, `.json` or `.yaml` file is not a
   decision `harvest` made; the handler has no business there. Emitting for these would be the
   noise that gets the whole channel switched off.
2. **In jurisdiction → always one line, always.** Once the file *is* source code, the handler says
   what it measured and what it concluded, every time, whether or not it fires:
   `harvest: Orbit.cs — 2 blocks (44-71, 90-104)` or
   `harvest: Orbit.cs — 3 comment runs, none met 5 lines / 300 chars; longest was 3 lines, 180
   chars`. That second form is the one that earns the channel: it names the near-misses with their
   real measurements, so tuning the threshold is evidence, not guesswork.
3. **`HOUSE_RULES_DEBUG=1` → verbose.** Per-run detail: every run considered, and which prose test
   rejected it. `run.sh` already honours this variable; this extends it into `hook.py`.

Carried as a top-level `systemMessage` next to `hookSpecificOutput` (separate keys, one emit).
`HOUSE_RULES_HARVEST=quiet` keeps the reminder and drops the trace, for anyone who finds it
noisy — the escape hatch exists so the default does not have to be the timid choice. `=off`
disables both.

*Scope note:* the trace is introduced for `harvest` only. The other handlers keep their current
output shape in this change; making them all traceable the same way is a follow-up, and belongs in
`docs/architecture-backlog.md` rather than being smuggled in here. The universal part of §0 — a
crash in any handler becoming visible — does land now, because that is a bug, not a style.

---

### 1. The harvest rule — `rules/house-rules.md`

New `## ` section after the tiers rule (currently ends line 93), so the two documentation rules sit
together. Working title:

> ## Long-form reasoning goes in a document, not in a comment

It must state, in the rules document's own voice: keep writing the reasoning down as it occurs; a
comment that has grown into an essay — design rationale, a post-mortem, a derivation, a platform
quirk — is documentation that landed in the wrong file; before the turn ends it moves into the
tier-4 system document that owns that code, and the site keeps a **one-line pointer** naming the
document and section; anything a reader genuinely needs *at that exact line* stays an ordinary
comment. **Why:** a comment nothing forces to change when the code does is the definition of a doc
that will rot, and it is unfindable from `docs/`.

The phrases `long-form`, `one-line pointer` and `@house-rules:archivist` must appear here, because
the hook's note is drift-checked against this file (`verify.py` idiom at `verify.py:570-580`).

### 2. The hook — new `harvest` handler

`hooks/hooks.json`: a fourth `PostToolUse` block, `"matcher": "Write|Edit"` (same matcher as
`artifact`), command `sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" harvest`, `"timeout": 10`. Add
`harvest` to `run.sh`'s per-event fallback `case` with a **loud** `systemMessage` ("no working
Python, so the comment-harvest check did not run") rather than letting it fall into `*) exit 0` —
the old plan let it fall through silently, which §0 now forbids.

`scripts/hook.py`: `HARVEST_NOTE` + `event_harvest()` after `event_runnable` (~line 715),
registered in `EVENTS` (line 862), and added to the module docstring's failure-contract table
(lines 16-22).

**Failure contract: never obstruct, never silent.** Exit 0 on every path — `PostToolUse` cannot
block and must not try. But every non-decision path emits a `systemMessage` naming what happened:
payload unreadable, payload would not parse, content field absent, scan budget exceeded, threshold
env var unparseable, unexpected exception. With the always-on trace above, **the only fully silent
exit is the out-of-jurisdiction one** — the file is not source code. A source file that simply had
nothing worth harvesting still says so, with its measurements.

**What it reads.** The one deliberate departure from an existing tested invariant: `artifact` and
`runnable` match `file_path` only and never look at contents, and `verify.py:564` pins that.
`harvest` must read `tool_input.content` (Write) / `tool_input.new_string` (Edit), because the
comment body *is* the subject. Reading the payload rather than opening the file keeps two
properties worth having: it stays stdin-only and stateless, and it sees **only text written this
turn**, so it never fires on pre-existing essays in files it merely touches.

Code content is dense with escaped quotes and newlines, so the raw-slice regex idiom
(`_FILE_PATH_RE`, `hook.py:601`) cannot decode it. Use `json.loads(payload)` inside the handler's
`try`; a parse failure emits a `systemMessage` saying the payload did not parse and the check did
not run.

**Detection ladder**, each tier cheap before the next:

1. **Extension gate.** Source files only — `.cs .py .js .mjs .cjs .ts .tsx .jsx .go .rs .java .c
   .h .cpp .hpp .rb .php .swift .kt .sh .ps1`. Markdown, JSON and YAML never fire, so a write to
   `docs/` is silent by construction. *(The one fully silent path: out of jurisdiction, not a
   decision.)*
2. **Comment runs.** One linear pass over lines using `str.startswith`, no per-line regex and no
   backtracking, so cost is O(n) in the content and large files are not a problem to be bailed out
   of. Marker families: `//` and `/* */` for C-family, `#` for Python/Ruby/shell, `"""`/`'''`
   docstring bodies for Python, `<# #>` for PowerShell.
3. **Scan budget, not a size cap.** No byte ceiling — scan whatever arrives. Bound the *work*
   instead: a wall-clock check (~3 s, well inside the 10 s hook timeout) that, if exceeded,
   abandons the scan and emits a `systemMessage` naming the file and its size and saying the check
   did not run on it. Loud, never silent, and no arbitrary limit on what is allowed through.
4. **Threshold — tunable, and low by default.** `HARVEST_MIN_LINES = 5` and
   `HARVEST_MIN_CHARS = 300` as module constants, each overridable by
   `HOUSE_RULES_HARVEST_MIN_LINES` / `HOUSE_RULES_HARVEST_MIN_CHARS`. An unparseable or
   non-positive value emits a `systemMessage` naming the variable and the bad value and falls back
   to the default — it does not silently ignore it.
5. **Prose test**, to reject false positives: require ≥ 2 sentence terminators; reject a run where
   most lines end in `;`, `{`, `}` or `)` (commented-out code, which `coding-philosophy.md`
   already says to delete, not harvest); reject a license header (starts within the file's first 3
   lines and contains `Copyright`, `SPDX`, `Licensed under`); reject generated banners
   (`<auto-generated`, `DO NOT EDIT`, `Code generated by`).

**Consequence of the lower threshold, stated rather than tuned around.** At 5 lines / 300 chars,
`hook.py`'s own `_ARTIFACT_EXT_RE` note (6 lines, ~430 chars) now fires, where at 10/600 it did
not. That is correct — it *is* a design essay, and `architecture-backlog.md` §6 already says so —
but it means the detector is deliberately set to catch medium-sized blocks, and more of this
repo's own comments qualify. The tunables exist so this is a dial the user turns, not a number
baked into the source.

**Line numbers.** For `Write`, content line numbers are the file's, so report `file:a-b` per block.
For `Edit`, `new_string` is a fragment and its offsets are meaningless — report the block count and
file only, and say ranges are unavailable. A confidently wrong `file:line` would poison the "cite
claims to `file:line`" convention the destination docs rely on. Cap the report at 5 blocks plus
"and N more" so the note stays cheap.

**Toggle.** `HOUSE_RULES_HARVEST=off` (reminder and trace both), `=quiet` (reminder only), reusing
`_TOGGLE_OFF` (`hook.py:783`) for the first.

**`HARVEST_NOTE`** restates the rule and names the destination and the delegation: port each block
into the tier-4 system document that owns that code (`docs/systems/*.md` — *How it works*,
*Invariants*, *Traps*), creating one if none owns it; leave a one-line pointer at the site; hand
the port to `@house-rules:archivist`; close with the standard "This is a reminder to you; the user
was not prompted and does not need to do anything."

### 3. The subagent — `agents/archivist.md`

Mirrors `agents/executor.md` in shape: `name: archivist`, `model: sonnet`, `effort: low`, a
description containing **`proactiv`** (the Agent tool's own gate on proactive spawning — without it
the delegation silently never happens, as `house-rules.md:307-312` explains for `executor`), no
`hooks:` / `mcpServers:` / `permissionMode:` keys (plugin subagents silently ignore them).

Its body carries the porting spec directly rather than a new skill: read the block, decide which
tier-4 system owns that code, write it into the right section (rationale → *How it works*,
post-mortem → *Traps*, invariant → *Invariants*), cite back to `file:line`, replace the block with
a one-line pointer, keep any line a reader needs at that exact site, and report which blocks moved
and which were deliberately kept and why. Plus the same "the house rules are NOT injected into this
subagent" digest `executor.md` carries, extended with the new failure-loudly line.

*Deliberately not a skill.* `architecture-backlog.md` §1 already flags nine restatements of the
rules text with no module holding them; the archivist is the only consumer of this spec, so a tenth
restatement in a `skills/comment-harvest/SKILL.md` buys nothing.

### 4. Docs the suite will fail without

`verify.py` parses registered events out of `hooks.json` and fails any missing table row:

- `CLAUDE.md` — new `PostToolUse` / `harvest` row; and the "Each handler's failure mode is
  deliberate" bullet list gains the never-silent contract and the `main()` fix.
- `claude-house-rules/README.md` — the same hook-table row.
- `docs/architecture.md` — why `harvest` reads payload content when `artifact` and `runnable`
  deliberately do not, and why the scan is budget-bounded rather than size-capped.

Do **not** write a check count into any of these — `verify.py` fails a doc that hardcodes one.

### 5. `verify.py` cases

Add near the `artifact`/`runnable` families (~line 560), following `art_case` (`verify.py:370`).
`harv_case(expect, title, file_path, content, tool="Write", env=None)` classifies `out` as
`remind` (carries `additionalContext`) / `trace` (`systemMessage` only) / `silent` (no output) /
`malformed`. A `systemMessage` is now a **first-class expected outcome**, not a failure — which is
the whole shift in §0.

Because the trace is always on, `silent` is now only correct for the out-of-jurisdiction case;
every in-jurisdiction non-firing outcome expects `trace` (a `systemMessage`, no
`additionalContext`). That distinction is itself the check that the channel really ships on.

- **Detection:** C# 10-line design essay → remind; 2-line *why* comment → trace; 20 lines of
  commented-out code → trace; SPDX header → trace; Python triple-quoted essay → remind.
- **Jurisdiction:** `.md` file with long prose → **silent**, no output at all.
- **The trace earns its place:** on the 2-line case, assert the message carries the measured
  longest run and the active threshold — not just "did not fire".
- **Threshold boundary:** 4 lines / 280 chars → trace; 5 lines → remind; and with
  `HOUSE_RULES_HARVEST_MIN_LINES=20` the 5-line case → trace, proving the tunable is live.
  A bad value (`HOUSE_RULES_HARVEST_MIN_LINES=banana`) → announces the bad value *and still
  detects*, proving it falls back rather than ignoring.
- **Toggles:** `HOUSE_RULES_HARVEST=quiet` on the essay case → remind, no trace;
  `=off` → silent.
- **Edit:** `new_string` essay → remind, and assert the output carries **no** line range.
- **Loud failure paths:** malformed JSON → trace, exit 0; empty payload → trace, exit 0; content
  field absent → trace, exit 0. None of these may be silent.
- **Registration:** `'run.sh\\" harvest' in hooks_json_text` (mirrors `verify.py:592`).
- **Drift, both directions** — the gap `architecture-backlog.md` §1 documents: the existing idiom
  only checks phrases against `rules_text`, so also run the hook and assert the emitted note still
  carries them. Do this for both new rules.
- **The §0 structural check:** no `except` in `hook.py` returns without emitting or writing stderr.
- **Regression for the `main()` fix:** force a crash in a non-`guard`, non-`inject` handler (the
  `crash_snippet` monkeypatch idiom at `verify.py:186`/`:286`) and assert a `systemMessage` on
  stdout — today this produces nothing.
- **Archivist:** `ARCHIVIST` path constant plus the executor checks mirrored onto it
  (`^model: sonnet$`, `^name: archivist$`, no `hooks:`/`mcpServers:`/`permissionMode:`, `proactiv`
  in the description).

## Known cost, stated rather than exempted

At the lowered threshold this repo's own `hook.py` and `verify.py` will fire the hook on most
edits. That is the tool working — `architecture-backlog.md` §6 already says those comments should
shrink to pointers — but it is real friction, and the honest levers are the two threshold env vars,
`HOUSE_RULES_HARVEST=off`, or actually doing the port. No special-case exemption for the plugin's
own scripts; special-pleading in the detector is how a rule stops meaning anything.

The always-on trace is the second cost, and it is the one most likely to be regretted: it puts a
`systemMessage` on **every source-file write in every session**. That is deliberate — it is what
makes "did the hook run, and on what" answerable without opening the source — but it is why the
trace must stay one line and why the out-of-jurisdiction path emits nothing at all. Verification
step 5 measures it; if the per-write cost is not in line with `artifact`/`runnable`, the line is
too long, not the channel wrong.

## Verification

1. `python claude-house-rules/plugins/house-rules/scripts/verify.py` — exit 0, every line PASS.
   This is the repo's stated source of truth.
2. **Calibration evidence.** Run the detector standalone over this repo's own `hook.py`,
   `verify.py` and `tools/install.py` and print every block it flags with its line range, at the
   5/300 default and again at 10/600. Read both lists: every flagged block should be one a human
   agrees is an essay. Record the two lists in `docs/` — this is the only thing that proves the
   heuristic works rather than merely reads well, and it is what makes the default defensible.
3. **The loud-failure paths, by hand.** Feed `harvest` a truncated JSON payload and a 5 MB file and
   confirm each prints a `systemMessage` naming the cause and exits 0. Then, with **no env vars
   set**, run it on a source file that does not qualify and confirm the default trace already says
   why — if that needs `HOUSE_RULES_DEBUG=1`, the channel shipped off and the design failed.
   Finally confirm `HOUSE_RULES_DEBUG=1` adds the per-run rejection reasons on top.
4. **End-to-end, live.** Install with `.\tools\bootstrap.ps1` (or `tools/bootstrap.sh`), start a
   session, have Claude write a `.cs` file containing a 10-line design essay, and confirm the
   reminder appears and that Claude ports the block and leaves a one-line pointer. Then confirm
   `HOUSE_RULES_HARVEST=off` silences it.
5. `python tools/measure_footprint.py --repo` — confirm the new handler's per-write cost is in line
   with `artifact`/`runnable` and that its failure paths exit 0. This now measures the always-on
   trace as well, since it fires on every source write; that number is the one to watch.
6. `python tools/clean_install_test.py` before considering it shippable.

## Files touched

| File | Change |
|---|---|
| `.../rules/house-rules.md` | two new rules: nothing-fails-silently, long-form-reasoning |
| `.../hooks/hooks.json` | fourth `PostToolUse` block |
| `.../scripts/hook.py` | `HARVEST_NOTE`, `event_harvest`, `EVENTS`, docstring table, **`main()` loud-failure fix**, `event_delegate` try, always-on trace + `HOUSE_RULES_DEBUG` verbose tier |
| `.../scripts/run.sh` | `harvest` case with a loud no-interpreter fallback |
| `.../agents/archivist.md` | new |
| `.../scripts/verify.py` | `harv_case` + cases, both-direction drift, `except`-emits structural check, `main()` regression, archivist checks |
| `CLAUDE.md`, `claude-house-rules/README.md` | hook-table row; failure-mode bullets |
| `docs/architecture.md` | payload-content departure; budget-not-cap |
| `.claude-plugin/marketplace.json`, `plugin.json` | version bump |

## Out of scope for this change

- A `Stop`-time git-diff sweep as a backstop. It would catch essays written by any means, but
  "since last commit" over-captures, so a block deliberately kept re-nags every turn — and the
  `Stop` precedent (`hook.py:798-820`) is explicit that a hook must never fire in a way whose only
  possible output is an announcement. Revisit if the `PostToolUse` reminder proves to be missed.
- Mechanical extraction. Deciding where prose ends and which system doc owns it is judgement, and
  `skills/project-docs/SKILL.md` is explicit: never invent content to fill a tier.
- Giving the other seven handlers the same always-on trace. It follows from the new rule and
  should happen, but doing it here would double the diff and put every hook's output shape in one
  change. Raise it as an entry in `docs/architecture-backlog.md` instead.
- Editing `rules/standards/coding-philosophy.md`. It is vendored from `Ajw2003/Coding-Standards`
  and synced by `tools/sync_standards.py`; comment-length and fail-loudly rules belong upstream.
