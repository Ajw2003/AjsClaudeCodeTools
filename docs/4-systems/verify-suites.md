# The verify suites

## What it owns

Proving, mechanically, that each plugin's hook payloads produce the JSON decisions the docs
claim — not that the code reads well, that it *decides correctly* when fed a real payload. Three
suites, one per plugin, same shape:

| Suite | Lines | Checks (last run 2026-09-24) |
|---|---|---|
| [`house-rules/scripts/verify.py`](../../claude-house-rules/plugins/house-rules/scripts/verify.py) | 5300+ | 365 PASS |
| [`agent-router/scripts/verify.py`](../../claude-agent-router/plugins/agent-router/scripts/verify.py) | 245 | 41 PASS |
| [`prompt-workshop/scripts/verify.py`](../../claude-prompt-workshop/plugins/prompt-workshop/scripts/verify.py) | 228 | 22 PASS |

If this is wrong — a check that passes when the hook it's judging is actually broken — every
other document in this repo that cites "verify.py passes" as evidence is standing on nothing.
This is the mechanism that turns "I read the code and it looks right" into "I ran the check and
it agreed," which is the whole reason `CLAUDE.md` calls it, not the README, the source of truth
for whether a change took effect.

It does not own getting the plugins installed (`plugin-distribution.md`, whose own
`tools/verify_tools.py` tests *that* system's decision logic instead) or being correct rules text
in the first place (`rules/house-rules.md`).

## How it works

Each suite feeds hand-built JSON payloads to the plugin's `hook.py` — by calling its handler
functions directly for the common case, and by shelling out to `run.sh` under a deliberately
broken `PATH` for the "no interpreter available" fallback cases — and asserts on the returned
decision (a `PASS`/`FAIL` line per check, numbered, printed with what was tested, expected, and
got). The check count is computed at runtime and never hardcoded in any doc, `house-rules`'
suite included — a written-down number drifts the moment a case is added, and `verify.py` fails
any doc caught stating one.

Beyond individual hook cases, `house-rules`' suite carries **drift checks**: `rules/house-rules.md`
is canonical, and several other files restate a phrase or requirement from it (`hook.py`'s
`SCOPE_REMINDER`, `RUNNABLE_NOTE`, `DELEGATE_NOTE`, `HANDOVER_NOTE`; `output-styles/handover-cards.md`;
`agents/executor.md`; `templates/step-card.html`; `docs/claude-ai-instructions.md`). A drift check
asserts a named phrase still appears in the restatement, so a reword of the canonical text that
silently drops what a restatement depends on gets caught rather than discovered live.

`house-rules`' suite also runs from two places — this repo, and the installed copy in
`~/.claude/plugins/cache/` — and several checks read files that exist only in the repo
(`CLAUDE.md`, `claude-house-rules/README.md`, `docs/claude-ai-instructions.md`,
`docs/desktop-verification.md`, `tools/install.py`). Those checks report a third state, `SKIP`,
gated on `IN_REPO` (the presence of `.claude-plugin/marketplace.json` beside the plugin
directory) rather than `FAIL`, so the installed copy's result isn't permanently red for a reason
that has nothing to do with the hooks. Inside a repo checkout the skip is unreachable — a missing
file there is still a real failure.

## Invariants

- **Exit code 0 means every check in that suite passed.** Nothing else about a suite's output is
  load-bearing except the individual PASS/FAIL lines and the final count.
- **No third-party test framework, stdlib only** — same constraint as the code under test, so the
  checker is never a bigger dependency than the thing it checks.
- **The check count is never written down as a number anyone maintains** — it's computed and
  printed, and a doc that hardcodes one is itself a drift check failure.
- **A repo-only check `SKIP`s outside a checkout and `FAIL`s inside one** — the distinction is
  `IN_REPO`, and a check that can't tell which state it's in must fail rather than guess.
- **The guarded-verb list is never hand-copied into a doc.** The README's "What trips the
  guard" table is checked by tokenizing the backtick code spans in the table itself against
  `GUARD_R3`/`GUARD_R4`'s actual verb lists (`GUARDED_GIT_VERBS`, `NAVIGATIONAL_GIT_VERBS` in
  `verify.py`), rather than by hand-copying the verb list into a second check. The README's
  table listed the old, broader verb set for months after `guard`'s git patterns were narrowed
  to only the verbs that write history, the index, or the remote (navigational verbs — `add`, a
  bare `checkout`/`switch`, `branch`, `tag`, `remote`, `submodule`, a bare `stash` — were
  deliberately left unmatched, since matching them produced only noise). A reader who tested
  with `git add -A`, expecting a prompt, saw none and could reasonably conclude the hook was
  broken rather than working as designed. Tokenizing the table means a future re-narrowing (or
  re-widening) of the guarded verbs breaks this check instead of silently leaving the table
  wrong again (`verify.py:2372-2393`).

## Traps

- **Most drift checks run in one direction only.** Most restatement checks in `house-rules`' suite
  assert that a phrase still appears in `house-rules.md`; they do not assert that the phrase still
  appears in the *restatement* the check is named for. So a phrase can be quietly deleted from
  `RUNNABLE_NOTE` or `HANDOVER_NOTE` and the suite still reports every check passing. This already
  happened once for real: the `delegate` restatement lost its proactive-use authorization sentence
  during the shell-to-Python port, survived in `house-rules.md` and both agent descriptions, and
  every check still passed — because the check never looked at what `event_delegate` actually
  emits. `delegate` and `versioncheck` are now bidirectional (checked over both `house-rules.md`
  and the emitted text); the remaining restatements are still one-directional as of this writing.
  Treat "the drift check passes" as weaker evidence for those than it looks.
- **Naming a command is not the same as verifying it will be handled correctly.** `versioncheck`'s
  out-of-date banner is checked twice, separately, on purpose: one case proves the banner still
  names the right fix command (the mismatch case), a second proves the banner still tells Claude
  to route that command through the card format, marked `UNTESTED:`, and then stop and wait rather
  than continuing into unrelated work. A real session hit exactly the gap the second check exists
  to close: the banner printed the raw fix command with no `UNTESTED:`/card instruction and no
  "then stop," so the reply relayed it as a ready-to-run block and moved straight into unrelated
  repo exploration in the same turn (2026-09-17). The two checks are kept separate rather than
  merged, because a banner that names the right command but drops the handling instructions (or
  the reverse) should fail exactly one of them, not neither.
- **There is no way to run one check or one category.** Editing a single `guard` pattern means
  re-running all 203 `house-rules` checks and reading the output to find the ~28 that were
  actually relevant. Nothing prevents this today; it's a known friction, not a bug.
- **A suite testing branch-dependent behavior must not inherit the developer's actual branch.**
  `house-rules`' guard/branch-ownership cases use hand-written fixture `.git/HEAD` files under
  throwaway directories rather than reading whatever branch the suite happens to run from — the
  same fact that makes a plain-file read fast enough to do on every `guard` call also makes it
  reproducible as a fixture. A case that reads the real repo's branch would pass or fail
  depending on who ran it and from where, which proves nothing.
- **A check can be wrong about the code it's checking.** One `hook.py`-source check searched for
  the literal string `rev-parse` to prove `branch_ownership()` never shells out to git — and
  failed, because `rev-parse` appears in that function's own docstring, precisely to say it is
  *not* used. The check was flagging the sentence explaining the invariant as a violation of it.
  It now matches call syntax only. Lesson: grepping prose for the absence of an idea is not the
  same as checking for the idea's absence in code.
