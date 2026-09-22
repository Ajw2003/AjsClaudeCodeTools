# Decisions

The paper trail: what was decided, when, why, what alternatives were rejected, and what it
superseded. Append-mostly — newest entry at the top. An entry is never rewritten or deleted; the
one allowed edit to an existing entry is flipping its `Status` line to `Superseded`, with a
pointer, when a later entry replaces it.

---

## 2026-09-22 — Split the machine profile into its own SessionStart hook, and expand ${CLAUDE_PLUGIN_ROOT} at emit time

**Context.** Step-1 review of the rules split above found two defects the suite did not catch.
First, the size check measured `inject` with no recorded `rules/environment.md`, so it missed
that a *real* recorded profile pushes the combined text over budget: fed a copy of
`docs/example-environment.md`, `inject` emitted 12,695 chars — over Claude Code's 10,000-char
per-hook limit, so on a real machine with a hand-verified profile the rules would again be
persisted to a file instead of reaching the model in full. Second, the trimmed core's detail
pointers read literally as `${CLAUDE_PLUGIN_ROOT}/rules/detail/<file>.md` in the emitted text —
that variable is expanded by the harness inside `hooks.json`'s own command strings, but never in
`additionalContext`, so Claude was being handed a path it could not open.

**Decision.** The machine profile (a recorded `rules/environment.md` or its runtime-detected
fallback, preflight warnings, and the remote handover-target block) moved out of `inject` into a
new `profile` SessionStart handler, registered as its own `hooks.json` entry right after `inject`
so a failure in one can never take the other down — same fail-loud (`systemMessage`) pattern.
`inject` now carries only the rules core, and substitutes `${CLAUDE_PLUGIN_ROOT}` for the real
absolute plugin root (derived from `hook.py`'s own location) before emitting. `profile` truncates
its own output with a visible notice naming the oversized file if a recorded profile would itself
push it over budget, rather than silently overflowing. `verify.py`'s size check now asserts
`inject` ≤ 9,000 chars (tighter than before, since it no longer carries runtime-varying content)
and `profile` ≤ 9,500 chars fed `docs/example-environment.md` as a stand-in for a real recorded
profile — the realistic case that actually overflowed. Added a case asserting no literal
`${CLAUDE_PLUGIN_ROOT}` reaches the injected text and that one named detail path resolves on
disk. Updated the `CLAUDE.md` and `claude-house-rules/README.md` hook tables for the new entry.

**Why.** The size check the first pass shipped measured a scenario (no recorded profile) that
understated the real one — the whole point of a recorded `rules/environment.md` is that most
users who bother to write one will have more to say than the runtime-detected fallback, not less.
Splitting the hook, not just trimming further, is the structural fix: the limit is per hook, so
the machine profile competing with the rules core for the same 10,000-char budget was always
going to reproduce the original bug the moment either side grew. And a pointer variable nothing
expands is not a pointer, it is a string that looks like one.

**Status.** Standing.

---

## 2026-09-22 — Split house-rules.md into an imperative core and rules/detail/*.md, so the rules actually reach the model

**Context.** A grilling session on 2026-09-22 found that `inject` emitted 44,506 chars.
Claude Code saves any single hook's `additionalContext` over 10,000 chars to a file and puts only
a ~2KB preview in context — everything past the first section of `house-rules.md`, including the
docs-tier rule, was invisible in that session. `house-rules.md` had doubled since the 2026-09-07
footprint work (20.8KB → 43KB), because that earlier pass's practice was to keep every "Why:"
rationale block inline rather than move it out — a reasonable call at 20.8KB, wrong at 43KB.

**Decision.** `house-rules.md` is now an imperative-only core: one to three sentences per rule,
plus a pointer naming `${CLAUDE_PLUGIN_ROOT}/rules/detail/<topic>.md` for that rule's full
rationale, "Why:" block and examples, moved there verbatim. `#### The card` collapses to a
pointer at the forced `handover-cards` output style, which is now the single copy of the
step-card checklist — the core no longer restates it. A new `INJECT_CHAR_LIMIT = 10_000` constant
in `hook.py` documents the hard limit; `verify.py` checks the real emitted `inject` and
`standards` `additionalContext` (not source file size) against a 9,500-char safety margin, each
checked separately since Claude Code's limit is per hook. Every verify.py drift check that used
to grep `house-rules.md` alone for a phrase now greps a corpus of `house-rules.md` plus every
`rules/detail/*.md` file — the phrase still has to exist somewhere the rules own, it no longer has
to survive being injected. The one check that could not be satisfied this way (the six-field
step-card checklist, since it deliberately left the injected text) was repointed instead: it now
checks that the core's `#### The card` section names `handover-cards.md` and does not restate the
checklist, rather than requiring the checklist phrases to appear in the injected text.

**Why.** A rule nobody's context contains is not a rule, it is a file. Keeping every rationale
block inline reversed the 2026-09-07 decision to do exactly that, because the number that mattered
— total injected size, not "does this file still read well" — had moved past the point where the
choice was free. Moving detail out loses nothing: `docref.py check`-style corpus checking means
every phrase a test ever pinned is still provably present, just no longer paid for on every
session start.

**Status.** Standing.

---

## 2026-09-22 — Guard against a full-file rewrite standing in for an in-place edit

**Context.** In a separate project, a scheduled, unattended task rewrote a CSS file wholesale
instead of touching the one thing that needed to change. Nobody was watching that run in real
time, so the regression it introduced sat unnoticed until someone found it later. The existing
destructive-action rule did not catch this: it explicitly carves out "ordinary edits to tracked,
committed files" because git already holds them, and a full-file rewrite of a tracked file fell
inside that carve-out even though it discards everything the change was never meant to touch. The
`guard` hook's `rm` pattern had a matching gap of its own — it only matched `rm -r`/`rm -f`, so a
plain `rm styles.css` (no flag needed to delete a single existing file) went unmatched too.

**Decision.** A new rule in `rules/house-rules.md`, "Edit in place; a full rewrite is a delete,
not an edit": changing only the lines that need to change is the default, and a full rewrite of a
file that already exists is a manually approved exception, named by what it discards and why,
whether or not the run is attended. Enforced by a new hook, `guardwrite`, registered at
`PreToolUse` on `Write` — since `Write` always replaces a file's entire contents, any call
targeting a path already on disk is a full-file replacement by definition, and `guardwrite` asks
every time, naming the path and the line counts where it can read both. It fails closed like
`guard`: an unreadable payload or internal error blocks the write rather than letting an
unchecked overwrite through. Also broadened `guard`'s `rm` pattern from `rm -r`/`rm -f` only to
any `rm <target>`, closing the plain-single-file-delete gap the same incident exposed on the
shell side. Updated `CLAUDE.md`'s hook table, `claude-house-rules/README.md`'s hook table and
"What trips the guard" table, and `docs/systems/hook-engine.md`. Bumped the plugin version
2.29.0 → 2.30.0.

**Why.** Git being able to recover the old blob after the fact is not the same as the regression
being caught before it ships — especially on a run nobody was watching. The destructive-action
rule's tracked-file carve-out was written for edits that change a few lines under version control,
not for a rewrite that discards the whole file and gambles that the new version is complete and
correct. Closing the gap needed both a rule (what "ordinary edit" excludes) and a mechanism
(`guardwrite`), because a rule with no shell or tool signature to match on is exactly the kind
that gets read once and then drifted past.

**Status.** Standing.

---

## 2026-09-20 — Issue and pull-request text never names a local path

**Context.** Issue #65 on this public repository was published with the user's local project
path in its body. The user closed the issue and asked for a standing rule.

**Decision.** A new rule in `rules/house-rules.md`: titles, descriptions, comments and review
comments on issues and pull requests never contain a path from the user's machine (a drive letter,
a home directory, another project's folder, a scratchpad or temp file). Files are named by
repo-relative path, other repositories by name or `owner/repo`. The check covers a body file
passed with `--body-file`. Commands handed to the user to run keep their absolute local paths,
since that text never leaves their machine. Commit messages are not covered: the user did not ask.
Plugin bumped to 2.29.0 for the added rule.

**Alternatives rejected.** A `guard` pattern on `gh issue`/`gh pr` commands: the local path lives in
the body file's contents, not in the command line, and a `--body-file` argument is itself a local
path, so the pattern would prompt on every legitimate call. Restating the rule in the `scope`
per-prompt reminder: it would cost tokens on every prompt for a rule that only matters when
publishing.

**Why.** A local path tells another reader nothing, discloses how the user's machine is laid
out, and stays in the edit history after the text is corrected. The rule is carried by the
session injection alone, so the check is the model's.

**Status.** Standing.

---

## 2026-09-20 — Pointers carry a stable id, and a command keeps them true

**Context.** The archivist left "a one-line pointer naming the document and section". Nothing
checked it, so a renamed heading or a doc moved to `docs/archive/` left the pointer lying, silently.
The `project-docs` skill said to "fix the pointers" when a doc moves, with no tool behind it.

**Decision.** A moved note gets a 4-hex id. In the doc it is a `<!-- ref:<id> -->` marker alone on
its own line under the heading; in code it is `doc-ref <id> <path>` in any language's comment
syntax. `scripts/docref.py` has `check` (ok / stale / dangling / ambiguous / malformed),
`fix --write` (rewrites stale paths by id only), and `new` (an unused id). It is a command, run by
`verify.py` and `/house-rules:docref`, **not a hook**: a doc-write hook is deferred until its cost
can be measured against a working checker. Existing prose pointers are left alone and only counted.

Three refinements over the spec, found while writing the plan: (1) a marker must be alone on its
line, so a doc that quotes one inline does not register a fake marker; (2) the file list is
`git ls-files --cached --others --exclude-standard` when the root is a git work tree, else a
directory walk, and the output names which — so ignored build output is never read and a note
moved into an uncommitted doc is still seen; (3) `--exclude GLOB` (recorded in the spec), matched
case-sensitively against the whole relative posix path, with a note when a pattern matches nothing.

Fences in docs follow the CommonMark opening/closing rule: a fence closes only on the same
character with a run at least as long, any other fence-looking line inside is content, and a doc
that ends inside a fence is reported MALFORMED at the line that opened it. `fix --write` writes a
temp file beside the source and `os.replace`s it, so an interrupted write never truncates code.
The states a run can report are ok, stale, dangling, ambiguous, malformed, duplicate (two markers
claim one id), unreadable and undecodable (a doc under `docs/` that is not valid UTF-8).

`fix`'s exit code is not a proxy for `check`'s. `fix --write` exits 0 when it could not read a file
at scan time (it names the file), and exits 2 only when a file it found fails at rewrite time,
while `check` exits 1 for that same unreadable file.

Three behaviours were added in review. When the directory-walk fallback is used, the "scanned"
line says why (`via directory walk (git did not list files: <reason>)`), and walk errors such as
unreadable directories are reported as UNREADABLE findings and fail the check. `fix` names
unreadable files (UNREADABLE lines, counted in its "still unresolved" summary) and keeps exit 0
for that, but handles each pointer file's read and write separately and returns 2 if any file
could not be read or written after being found, printing UNREADABLE/UNWRITABLE per file and how
many failed; `new` keeps the id alone on stdout and warns on stderr if any file was unreadable,
since the id may collide. The live check in `verify.py` runs `docref.py check` on this repo with
`--exclude` for `verify.py` and `docref.py`, which hold example pointers on purpose.

**Alternatives rejected.** Path plus heading anchor (a rename is indistinguishable from a
delete, so the fixer can only guess); fuzzy-matched heading text (repairs are guesses a person
must review); a hook on doc writes (adds file reads to the write path before we know what they
cost); extending `harvest_scan.py` (a different job, finding comments to move, in the same file).

**Why.** A pointer that can lie silently is worse than none: it is trusted. An id makes the
common failure (doc moved or renamed) mechanical, and everything that is not mechanical
(a deleted note) is reported with `file:line` for a person to decide.

**Status.** Standing. Piece B of the harvest content-rules work; A and C build on it.

## 2026-09-20 — Size the harvest threshold by characters alone, default 500

**Context.** `/house-rules:harvest-scan` on a real Unity project returned 831 blocks. The size
test in `_harvest_blocks` was `lines >= 3 OR chars >= 150`, so a block qualified on either axis:
three short lines were enough, and 150 characters (about 25 words) is an ordinary "why this line
is odd" note, not an essay. About 99% of that project's comment blocks tripped it.

**Decision.** Characters are the only size criterion, default `HARVEST_MIN_CHARS = 500` (about 80
words). `HARVEST_MIN_LINES`, `HOUSE_RULES_HARVEST_MIN_LINES` and `harvest_scan.py --min-lines` are
removed. Characters are counted over the joined text, so wrapping and indentation cannot move a
comment across the line; a line count can. Plugin version bumped to 2.27.0 for the removed knob.
On that project 500 flags 218 blocks (820 at 150); on this repo it flags 0.

**Alternatives rejected.** Keeping the lines knob and setting `MIN_LINES` very high per machine —
works without a code change, but leaves a dead criterion in the handler and a default that is still
wrong for everyone else. Words instead of characters — same signal, needs a tokenizer for no gain.

**Why.** The threshold only narrows what gets looked at; each flagged block is still moved or kept
by judgement (a subtle-ordering-bug comment can stay in place with a pointer). The table is in
[comment-harvest-calibration.md](comment-harvest-calibration.md); if 218 is still noise, raise
`HOUSE_RULES_HARVEST_MIN_CHARS` to 800 rather than editing the constant.

**Status.** Standing.

---

## 2026-09-20 — Use the braced `${CLAUDE_PLUGIN_ROOT}` in `/house-rules:harvest-scan`

**Context.** `/house-rules:harvest-scan` failed in a real session: `commands/harvest-scan.md` ran
`python "$CLAUDE_PLUGIN_ROOT/scripts/harvest_scan.py"`. Claude Code substitutes only the braced
form `${CLAUDE_PLUGIN_ROOT}` inline in plugin content (every `hooks.json` entry uses it) and does
not export the variable to the Bash tool's shell, so the bare form expanded to empty, giving
`/scripts/harvest_scan.py`, which Git Bash mapped to `C:\Program Files\Git\scripts\...` (exit 2).
`verify.py` only checked that the literal text `$CLAUDE_PLUGIN_ROOT` appeared, so it passed while
the command was broken.

**Decision.** The command now uses `${CLAUDE_PLUGIN_ROOT}` and tells Claude to stop and report if
the path did not resolve, rather than searching `~/.claude/plugins` or guessing (the cache holds
several versions). `verify.py` now requires the braced form and the stop instruction, and fails if
any file under `commands/` contains a bare `$CLAUDE_PLUGIN_ROOT`. Plugin version bumped to 2.26.2.

**Why.** A check that only proves a string is present cannot catch a string that is present but
never substituted. The bare-form ban is the assertion that would have failed on the original.

**Status.** Standing.

---

## 2026-09-20 — Reproduce the install-upgrade fix against the real CLI before trusting it

**Context.** `tools/` had no coverage of `install.py` at all before 2.15.0, and the gap cost
something concrete: `claude plugin marketplace add` answers "already on disk" for a marketplace
the device has already seen and does not re-fetch it, so the cached clone stayed on the old
commit and `claude plugin update` afterward reported "already at the latest version" — naming
the **old** version, a confident wrong answer. Unit-testing `install.py`'s `install_steps()`
order in isolation would prove the sequence was internally consistent without proving it fixed
anything a real machine would hit.

**Decision.** Before trusting the fix (inserting `plugin marketplace update` into the sequence),
it was reproduced against the real `claude` CLI: a stale cache registered version 2.17.0; running
the *old* three-command sequence against it reproduced the "already at the latest version"
lie naming 2.17.0; running the fixed four-command sequence against the same stale cache reported
"updated from 2.17.0 to 2.18.0" correctly. `tools/verify_tools.py`'s install-upgrade-path checks
(`verify_tools.py:313-322`) pin the resulting **order** of `install_steps()`'s four commands,
without shelling out to the real CLI or mutating a machine's config on every test run — that
real-CLI reproduction was a one-time manual step, not something the automated suite repeats.

**Why.** `install_steps()`'s docstring and `docs/systems/plugin-distribution.md` already record
*why* the order must be add/update/install/update. What wasn't recorded anywhere is that the fix
was confirmed against the actual failure mode on the actual CLI, not just argued for — and that
distinction matters because the argument alone ("marketplace add doesn't re-fetch") could be
right in theory and still miss some other reason `plugin update` reports what it does. Recording
the reproduction is what lets a later reader trust the checks are testing the right thing, not
just a plausible-sounding invariant.

---

## 2026-09-20 — Give the archivist a two-pass process for batch harvests

**Context.** Running `/house-rules:harvest-scan` against this repo at the harvest hook's own
default thresholds (3 lines / 150 chars — see
[`comment-harvest-calibration.md`](comment-harvest-calibration.md)) found 162 blocks across 16
files. The archivist agent's instructions describe per-block judgment (tier-4 systems doc vs.
`docs/Decisions.md`) but say nothing about how to behave at that scale. Dispatched with 162
blocks in one shot, nothing stopped a plausible shortcut: paste everything into one tier-4 doc,
verbatim, with pointers, and report the sweep done — which is capture, not the actual
redistribution the harvest rule asks for (see "Long-form reasoning goes in a document, not in a
comment" in `rules/house-rules.md`).

**Decision.** Added a "Working from a batch" section to
[`agents/archivist.md`](../claude-house-rules/plugins/house-rules/agents/archivist.md) requiring
two explicit passes whenever more than a handful of blocks are handed over at once: Pass 1 lands
every block verbatim, with `file:line` citations, into a dated scratch file at
`docs/plans/<date>-harvest-staging.md`; Pass 2 works through that staging file entry by entry,
applying the existing per-block classification, moving each into its real tier-4 doc or a dated
`Decisions.md` entry, updating the original site's pointer to the final destination, and deleting
the entry from staging. The staging file is explicitly scratch, not a seventh tier — the report
must confirm it was deleted, or say exactly what is still in it and why. A single block flagged
live by the `harvest` hook is unaffected; it still goes straight to its final destination in one
pass, per the agent's original instructions.

**Why.** The whole point of the harvest rule is that reasoning ends up somewhere it can be
maintained and found — a tier-4 doc or a dated decision, not a comment nobody re-reads. A batch
run that dumps 162 blocks into one document with pointers satisfies "verbatim" and "pointer" but
not "found where it belongs," and nothing in the agent's prior instructions would have caught
that as incomplete. Splitting capture from redistribution, and making the staging file's own
emptiness the completion signal, closes that gap without changing how a single live-flagged block
is handled.

---

## 2026-09-20 — Fix the harvest handler treating an Edit fragment's line 1 as the file's header

**Context.** A user's screenshot showed a trace reading "2 comment runs, none met 5 lines / 300
chars; longest was 7 lines, 397 chars (file header)" — self-contradictory, since 7/397 clears
5/300. `_harvest_blocks()` exempts a comment run starting at line 1 as a module docstring/file
header, which is correct for a `Write` (whose `content` is the whole file, so line 1 really is
the file's first line) but was applied unconditionally, including to `Edit`'s `new_string`. An
Edit's fragment has its own line numbering starting from wherever the replacement begins — so an
Edit that happened to insert or replace a comment block at the top of its fragment got exempted
as a "file header" purely by coincidence of where the edit started, not because it was one.

**Decision.** Added a `full_file` parameter to `_harvest_blocks()` (default `True`, preserving
`Write` and standalone full-file-scan behaviour); `event_harvest()` now passes `full_file=ranged`
so an `Edit` never gets the file-header exemption. Separately, fixed `_harvest_trace()`'s summary
line, which always said "none met N lines / M chars" regardless of the actual rejection reason —
now it only says that when the longest run genuinely failed the size check, and names the real
reason (file header, license header, commented-out code, etc.) when a run met the size threshold
but was rejected for cause. Also lowered the defaults from 5 lines/300 chars to 3 lines/150 chars
per direct request, and normalized C#'s `///` doc-comments (and `////` dividers) by stripping all
leading slashes rather than just the two the `//` marker consumes. Added `harvest_scan.py` for a
manual, project-wide sweep using the same detection code, and wrapped it in a rerunnable
`/house-rules:harvest-scan` command (`commands/harvest-scan.md`) so it resolves the installed
plugin's script via `$CLAUDE_PLUGIN_ROOT` instead of requiring a hand-built plugin-cache path.
Bumped the plugin version.

**Why.** The bug meant `Edit` calls — the common case for touching an existing file, as opposed
to `Write`'s full-file rewrite — could silently exempt exactly the comment blocks the handler
exists to catch, whenever the edit happened to start on one. The trace wording bug compounded it:
even where the file-header exemption was correct (a real `Write`), or where a different exemption
fired (license, commented-out code), the message claimed "none met the threshold," which reads as
the detector missing an essay rather than deliberately setting it aside — the exact confusion that
surfaced the bug in the first place.

**Status.** Standing.

---

## 2026-09-17 — Ask permission to run the plugin's own update commands, rather than only relaying them

**Context.** The previous entry above fixed *how* a hook-relayed command gets handed over (card,
`UNTESTED:`, then stop and wait) but not *whether* handing it over was the right move at all. A
real user hit exactly that card on the desktop Code tab and could not act on it: the desktop's own
plugin-update button was greyed out on a stale marketplace cache, and the card's fix commands ran
into the same wall the button did, because both routes required the user's own hands. Meanwhile
`rules/house-rules.md` already says "the user's hands are for decisions, not labour" and Claude's
own shell tool, in that same session, reaches the exact machine the freshness check just read —
running the two refresh commands itself was always possible, and never attempted.

**Decision.** Extended `event_versioncheck()`'s banner in `hook.py` to instruct Claude to ask the
user's permission to run the marketplace-refresh and plugin-update commands itself, on this
machine, right now, and only fall back to relaying them through the step-card format (unchanged
from the previous entry) if the user declines or the session has no shell tool. Added a matching
paragraph to `rules/house-rules.md` under "Never hand over a command I have not run where they
will run it," updated `CLAUDE.md`'s hooks table, and extended `verify.py`'s banner and drift checks
to require the new ask-permission instruction alongside the existing card/`UNTESTED:`/stop-and-wait
ones. Bumped the plugin version 2.24.2 → 2.24.3.

**Why.** A command handed over for the user to run is still labour if Claude could have run it
instead — the card format exists for commands only the user's own hands can execute (a different
shell, a different machine, credentials Claude doesn't hold), not as a default for every relayed
fix. It's also the more reliable path here specifically: the CLI refresh works even when the
surface that would otherwise run it (a greyed-out desktop button) does not, so offering to run it
directly sidesteps a UI bug rather than routing the user straight into it.

**Status.** Standing.

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
