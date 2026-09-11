# Make delegation visible, and make the executor actually fire

## Context

Two problems, one section of the rules.

**1. A delegation is invisible.** `docs/architecture-backlog.md` entry 7 records aj watching a
real executor delegation on the Windows desktop **Code** tab and being unable to tell it was the
executor, that it ran on Sonnet, or that it carried the right rules digest. The entry is explicit
that the frontmatter `model: sonnet` is a *declaration, not evidence*, that `ListAgents` shows no
model, and that the completion notification reports tokens and duration but no model. The failure
this invites is silent: a delegation that fell back to the parent model, or a digest that drifted,
would look identical from outside. aj's one fixed requirement was that the **plugin**, not the
user, makes the three properties visible.

**2. The executor sometimes doesn't fire when it should.** This turns out to have a dated,
evidenced cause, not just drift — see D1 below.

Intended outcome: every delegation announces which agent, at what declared model and effort, under
which digest — and, when it finishes, which model **actually served it**, read out of the
subagent's own transcript. Plus the reminder that asks for the delegation is restored to full
strength and widened to the sessions it currently misses.

## What was established before designing (facts, not assumptions)

**D1 — the evidenced regression.** The sentence authorizing proactive spawning was **dropped from
the injected note**. `docs/plans/2026-08-31-executor-proactive-delegation.md` records the original
fix: the harness gates autonomous subagent spawning behind the user explicitly asking *or* the
target agent's description marking it proactive, and `delegate.sh`'s note was amended to name that
authorization. Commit `ec6105e` ("switch hooks.json to run.sh/hook.py, delete the sh hook scripts")
rewrote `delegate.sh` into `DELEGATE_NOTE` and lost the sentence. It survives today only in
`house-rules.md:444` and the two agent descriptions — never in the text that lands in context at
the moment the model decides whether to spawn.

It shipped invisibly because the drift check at `verify.py:849` is **one-directional**: it asserts
the phrases appear in `house-rules.md`, never that they still appear in `DELEGATE_NOTE`. This is
`docs/architecture-backlog.md` entry 1's predicted gap, realised.

**D2 — the hook events exist and can be matched by agent type.** Confirmed against
`https://code.claude.com/docs/en/hooks.md`: `SubagentStart` ("when a subagent is spawned") and
`SubagentStop` ("when a subagent finishes") are real events, and the matcher for both filters on
**agent type**, with plugin-scoped names given as an example form (`^my-plugin:reviewer$`).
Common payload fields documented for all events include `session_id`, `transcript_path`, `cwd`,
`permission_mode`, **`effort`** and `hook_event_name`; `agent_id` and `agent_type` are documented
as present when the hook fires inside a subagent.

**D3 — the observed model is recoverable.** Probed live in this session: subagent transcripts are
written to their own file at
`~/.claude/projects/<project>/<session-id>/subagents/agent-<agent_id>.jsonl`, every `assistant`
entry carries `message.model`, and `isSidechain: true` marks the sidechain. The parent transcript
for this same session reports `claude-opus-5` across 55 assistant entries; the subagent reports
`claude-haiku-4-5-20251001` across 26. `tools/session_ledger.py:70` already knows this directory
convention (it excludes `subagents/` when picking the newest transcript).

**D4 — two things are NOT documented and must be probed, never assumed.**
- `agent_transcript_path` is not in the reference. The layout in D3 is empirical, for this CLI
  version, in a cloud session. The docs additionally warn the transcript entry format is internal
  and changes between releases.
- Whether `SubagentStart`/`SubagentStop` honour `systemMessage` / `additionalContext`, and where
  that output goes, is not documented.

Both are why the runtime-probe-and-fail-loud posture below is the design, not a caveat on it.

**D5 — a correction worth recording.** A docs sweep relayed the claim that `PreToolUse` never
fires for the Agent tool and that Agent "never prompts for permission". The reference does not
support that: it names `EndConversation` as the only tool skipping `PreToolUse`/`PostToolUse`.
Nothing here depends on it either way — this design uses the subagent lifecycle events and
prompts for nothing — but the claim should not be written down as fact.

**D6 — `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`.** Documented as forcing all subagents onto one model,
ignoring frontmatter. That is a real, named mechanism by which `model: sonnet` is silently not
honoured, and it is readable from the hook's environment.

**Baseline:** `python claude-house-rules/plugins/house-rules/scripts/verify.py` → 176 checks, all
PASS, at `2def041`. Plugin version `2.17.0`.

## Approach

### Part 1 — Two new handlers, so a delegation says what it is

Both live in `scripts/hook.py` alongside the existing nine, dispatched by `run.sh` the same way,
registered in `hooks/hooks.json` with **no matcher** — the complaint was "I couldn't tell which
agent", which is about every subagent, not only the house-rules two. Cost is one line per spawn.

**`announce` — `SubagentStart`.** Extracts `agent_type`, `agent_id` and `effort` with the same
one-field posture as every other handler (`_PROMPT_FIELD_RE`/`_COMMAND_FIELD_RE` at
`hook.py:519`/`:537` are the shape to copy — note `_FILE_PATH_RE` at `:601` is the one that
silently differs on escape handling; copy the first two, not it). Then emits one `systemMessage`:

- the agent being launched, by name;
- what the **installed** `agents/<name>.md` *declares* — model and effort, parsed from that file's
  frontmatter under `${CLAUDE_PLUGIN_ROOT}`, never a string hardcoded in `hook.py`, so the line
  reports the copy actually in the plugin cache;
- the effort the **payload** reports, labelled as the payload's value (the docs do not say whether
  it is the subagent's or the session's — say which field it came from, claim nothing more);
- the plugin version from `.claude-plugin/plugin.json` and a short fingerprint (first 8 hex of a
  `hashlib.sha256` over the digest section of `agents/<name>.md`), which answers "which digest,
  from which version, was in its context";
- if `CLAUDE_CODE_SUBAGENT_MODEL` or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set (D6), that fact,
  because the declaration may not be what runs.

For an agent the plugin does not ship, it names the agent and says there is no declaration to
compare against — which is still the useful half of the answer.

**`verdict` — `SubagentStop`.** Turns the declaration into evidence. Resolves the subagent
transcript by probing, in order: an `agent_transcript_path` field if the payload carries one (D4 —
it may, it is just not documented), then
`<dirname(transcript_path)>/<session_id>/subagents/agent-<agent_id>.jsonl` (D3). Scans it for
distinct `message.model` values on `assistant` entries and emits one line: the agent, the observed
model(s) and how many assistant turns, and — for a house-rules agent — **MATCH** or **MISMATCH**
against the declared model.

Failure contract: fails **open and loud**, the same as `handover`, and for the same reason — a
non-zero exit at a stop event must never wedge anything, and `decision: "block"` here would send
the subagent back to work. Every "I could not tell" path says so by name and lists the paths it
tried: no transcript found, unreadable, no `assistant` entry carrying a model, a JSONL shape it
did not recognise. Per `CLAUDE.md`'s nothing-fails-silently constraint, silence from it must mean
only that it looked and found nothing to say.

One lever, matching the `HOUSE_RULES_HANDOVER=off` precedent at `hook.py:1087`:
`HOUSE_RULES_DELEGATION=off` disables both. These are **not** `HOUSE_RULES_TRACE`-gated — the
verdict is the deliverable, not a trace of a silent path, and gating it behind the trace lever
would make the feature's own output optional.

Files: `scripts/hook.py` (two handlers + two `EVENTS` rows), `hooks/hooks.json` (two events),
`scripts/run.sh` (its per-event fallback names each event — add both, and match `handover`'s
fail-open behaviour, not `guard`'s fail-closed).

### Part 2 — Harden what makes the executor fire

**H1. Restore the dropped authorization to `DELEGATE_NOTE`** (`hook.py:973`). One sentence naming
the agent description's proactive-use marking as the harness's own documented basis for spawning
without a fresh per-turn ask. This is the D1 regression fix and the single highest-value change
here — it is the text present at the moment of the decision.

**H2. Make the delegate drift check bidirectional** (`verify.py:847-857`). Every bound phrase must
appear in **both** `house-rules.md` and `DELEGATE_NOTE`, so H1 cannot silently reverse again.
Deliberately scoped to this one restatement: building the full `Restatement(source, phrases)`
table is `architecture-backlog.md` entry 1's job, and widening this change into it is exactly what
the executor digest forbids. Note in that entry that the delegate row is now done.

**H3. Close the no-plan-mode gap** (`hook.py:480-552`). `delegate` only fires on `ExitPlanMode`,
so auto and accept-edits sessions — which `house-rules.md:437` says the rule explicitly covers —
never see it. Add a go-ahead clause to `scope`, appended when the extracted `prompt` field matches
an implementation-shaped phrase (`implement`, `go ahead`, `build it`, `do it`, `execute the plan`,
`make the changes`, `proceed`, `ship it`), the same broad-within-the-extracted-field posture as
`_SCOPE_COMMAND_HINT_RE`. **`scope`'s never-fail contract is absolute** — a non-zero exit on
`UserPromptSubmit` erases the user's prompt — so the clause is a module-level constant appended
inside the existing `try`, with every failure path still reaching `SCOPE_REMINDER_SHORT`.

**H4. Make the skip-it exception testable, not elastic.** Today `house-rules.md:435` says "work
small enough that describing it costs more than doing it" and `DELEGATE_NOTE` says "a single file,
or a handful of steps or fewer" — a self-judged threshold the model talks itself past. State one
fixed threshold in `house-rules.md`, restate it identically in `DELEGATE_NOTE` (H2's check then
binds them), and require the skip to be **said out loud in one line naming which limb applies**.
This is the same defect class as the open "Vague statements and instructions" entry in
`docs/rules-backlog.md`; cross-reference it rather than duplicating the argument.

**H5. The rule does not expire after the first hand-off.** State in `house-rules.md` that each
group of a multi-group plan is its own delegation. The `delegate` reminder fires once per
`ExitPlanMode`; nothing re-fires when group 1 returns, which is when remaining groups get absorbed
inline.

### Part 3 — Docs and version

- **`CLAUDE.md` and `claude-house-rules/README.md` hook tables** both need rows for `announce` and
  `verdict`. Not optional: `verify.py:2026` derives the registered events from `hooks.json` and
  fails if either table is missing a row.
- **`docs/architecture.md`**, "One subagent, for the model split" section — a subsection recording
  that the model is now **observed**, not declared; the probe order and why it is a probe (D4);
  and that the parent/child model split was measured (D3), so the claim rests on evidence.
- **`docs/architecture-backlog.md`** — delete entry 7 (the file's own rule: when one ships, delete
  it) and mark the delegate restatement done in entry 1.
- **`docs/plans/2026-09-11-delegation-visibility.md`** — this plan, copied into the repo per the
  artifact rule.
- **`.claude-plugin/plugin.json`** — `2.17.0` → `2.18.0`, and the plugin `description` gains the
  delegation-reporting behaviour.

**Deliberately out of scope:** `verify.py:1381`'s dead-field check forbids `permissionMode:` on an
agent as a field "plugin subagents silently ignore", but the current subagent reference documents
it as supported. That is a separate, unverified staleness — record it as a new
`architecture-backlog.md` entry, do not change the check in this work.

## Verification

1. **Suite, first and last.** `python claude-house-rules/plugins/house-rules/scripts/verify.py` —
   176 checks pass at baseline; it must pass with its own (higher) computed count at the end. Do
   not write the new number into any file; `verify.py` fails any doc that hardcodes one.
2. **New `verify.py` cases**, added in the same change as the handlers — untested rule text has no
   effect:
   - `announce` names the agent, the declared model, the plugin version and a digest fingerprint,
     for a payload with `agent_type: house-rules:executor`;
   - `announce` on an agent the plugin does not ship still names it and says no declaration exists;
   - `verdict` against a **fixture** transcript (hand-written JSONL under a temp dir, the same way
     guard's cases use hand-written `.git/HEAD` fixtures rather than whichever branch the suite
     runs from) reports the observed model, and reports MISMATCH when the fixture says `opus`;
   - `verdict` with no resolvable transcript emits a `systemMessage` naming the paths it tried and
     exits 0 — the nothing-fails-silently case;
   - both exit 0 with `PATH` empty and on an unparseable payload;
   - `HOUSE_RULES_DELEGATION=off` silences both;
   - `main()`'s last-resort net covers both (extend the loop at `verify.py:1384`);
   - H2's bidirectional delegate drift check;
   - `scope`'s go-ahead clause fires on a go-ahead prompt, is absent otherwise, and `scope` still
     exits 0 on every failure path.
3. **Tools suite:** `python tools/verify_tools.py` — must still pass (`session_ledger.py`'s
   `subagents/` exclusion is adjacent to this work).
4. **Cost:** `python tools/measure_footprint.py` — price the two new lines. They fire per subagent
   spawn, not per prompt, so the expected delta is small; if it is not, that is a finding.
5. **End-to-end, in a real session** (this is what actually proves it, not the fixtures): spawn
   `@house-rules:executor` on a trivial task and confirm the launch line appears at spawn, the
   verdict line appears at finish, and the observed model it names matches what
   `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl` contains. Per D4 the
   transcript layout is empirical for this CLI version — if the probe fails on the desktop Code
   tab, the handler must *say so by name* there, and that is a passing result for the failure
   path, not a silent one.
6. **CI:** `.github/workflows/verify.yml` runs the suite on push and PR; a green run is the last
   gate.
