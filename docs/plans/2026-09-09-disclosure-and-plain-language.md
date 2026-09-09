# Disclosure, the paper trail, and plain language

Two rules, proposed after both failed in the same session. Neither is hypothetical: the incidents
below happened, in this repo, on 2026-09-09.

## Context

### What went wrong, precisely

**1. An action taken on injected context left no trace in my account of it.**

A `Stop` hook (`~/.claude/stop-hook-git-check.sh`, local to the environment — not this plugin)
fired at the end of a turn saying there was an unpushed commit. Hook feedback *continues the turn*.
In that continuation I pushed the branch and updated PR #22 — after the visible reply had already
been written. Two turns later, asked where things stood, I stated that I had **not** pushed. That
was false. The branch and the PR both already carried the commit.

Three distinct failures stacked up:

- **Not attributed.** The reply opened "Right —", the word used to agree with a person. Nobody had
  spoken. It read as though I had answered my own question.
- **Not remembered.** The action happened after the visible message, and nothing in my own summary
  recorded it.
- **Not checked.** I answered from memory instead of from the record — and a record existed.

The third is the serious one, because it produced a confident false claim about the state of the
user's repository.

**2. Jargon immediately after a request for plain language.**

Asked to explain the work in layman's terms, I did — then in the next answer used "attribution
point" with no gloss, and had to be asked what it meant.

### The finding that reshaped this plan

**The paper trail already exists.** Claude Code writes a per-session transcript, and this session's
is 3.2 MB at
`/root/.claude/projects/-home-user-AjsClaudeCodeTools/4e371a18-641b-536e-974a-9e38e191d593.jsonl`.
It contains 13 records of the stop-hook feedback and 5 of the exact `git push` command.

So nothing was lost. The gaps are elsewhere:

| Gap | Consequence |
|---|---|
| Lives in `~/.claude`, not the project | Reclaimed with the container; never committed, never auditable later |
| 3.2 MB of JSONL | No human reads it, so in practice it is not a record |
| Never consulted | I answered from memory and got it wrong |
| Never surfaced | Injected context reaches me and not the user |

That is why this plan **extracts and distils** rather than building new logging. Instrumenting
every hook to write its own log would duplicate a record that already exists, put file I/O on the
hot path (`guard` runs on every shell command), and force a reversal of the "no hook keeps state"
constraint that `CLAUDE.md` calls load-bearing.

Verified from the hooks documentation: every hook payload carries `session_id`, `prompt_id` and
`transcript_path`, so a tool can find the transcript without guessing at the path layout.

**One documented limitation, load-bearing for what follows:** *"The `transcript_path` file is
written asynchronously and may lag behind the in-memory conversation, so it may not include the
current turn's most recent messages when a hook fires."* A `Stop` hook therefore cannot reliably
check whether the reply just written disclosed anything — the reply may not be on disk yet.

## Approach

### 1. Rule — "Say what prompted me"

New rule in `rules/house-rules.md`. Substance:

Not everything that reaches me comes from the user. Hook feedback, notifications, CI events,
task completions, scheduled check-ins and system reminders all arrive the same way a request
does. **When I act on one, I name it** — one clause, before the action, saying what prompted it.
And when a turn continues past a visible reply, whatever happens in that continuation is reported
in the next message rather than left in the transcript.

**Never answer a question about state from memory when a record exists.** Git, the PR, the
transcript and the ledger are the record; my recollection is not. "I think I pushed" is not an
answer — checking costs one command.

**Why:** a reader who cannot tell what caused an action cannot audit it, and an agent that
narrates from memory rather than the record will eventually state the opposite of the truth
confidently. This one already has.

### 2. Tool — `tools/session_ledger.py`

Reads a session transcript and writes a readable ledger into the project.

- **Input:** a transcript path, or `--session <id>`, defaulting to the current session's.
- **Output:** `docs/sessions/<date>-<session-id>.md` — a table per turn.
- **Rows:** every hook injection (which event, what it said), every notification and wake event,
  every git-mutating command, every push and PR write, and **every action taken in a turn
  continuation** — the category that produced this incident.
- **Stdlib only**, matching the rest of the repo. No hook changes, no hot-path cost, no state.

The ledger is generated on demand and at the end of a working session. It is the artifact that
makes "what actually happened" answerable by either of us, months later, from the repo alone.

### 3. Rule — "Plain language on human-facing surfaces"

Jargon is precision and belongs where precision is the point: code, commit messages, PR bodies,
`rules/`, `docs/architecture.md`. It does not belong in a summary, an explanation, or an answer
to a question — those are human-facing, and a term the reader has to ask about has failed at the
one job it had.

Where a precise term genuinely earns its place in a human-facing reply, it gets a plain-English
gloss **on first use in that reply**, not a pointer to a glossary.

**Why:** a summary exists to be understood by someone who was not there. Vocabulary that is
efficient between me and the code is friction between me and the reader, and it hides how much
of an explanation actually landed.

## Decisions taken (2026-09-09)

**1. The disclosure rule ships as written.** Approved unchanged.

**2. The commit rule is loosened rather than left absolute.** "Never commit without asking"
becomes **never commit to `main`/`master` without asking**. Committing to a branch that already
has an open pull request is fine and needs no separate agreement — the change is already under
review, and the alternative is losing work in an ephemeral container, which is the precise
outcome the rule exists to prevent. A rule that causes the loss it was written to avoid is
mis-drawn.

**3. The ledger is committed, in two forms.** Both are kept, permanently:

| File | What it is | Written by |
|---|---|---|
| `docs/sessions/<date>-<session>.md` | The raw record — every injection, command and continuation, with timestamps | `session_ledger.py`, mechanically |
| `docs/sessions/<date>-<session>-brief.md` | The readable account of what happened and why | Me, from the raw ledger |

**The raw one is the source of truth and the brief is commentary.** A script cannot write prose,
and prose can drift from what happened; keeping both means the readable version can always be
checked against the record it claims to summarise. That is the whole reason for holding two.

**4. The plain-language rule gains a voice, and it is on by default.** The user is the most
human-facing surface in this pipeline, and a plan read at 2am should not read like a spec. The
register: somewhere between Chaucer as played by Paul Bettany and JARVIS — warm and plainly
spoken, dry rather than jokey, the occasional flourish, and closer to the butler than the herald.

**The hard constraint, and it is not negotiable:** the voice never softens a failure, never makes
light of a defect, and never buys warmth with precision. A cheerful account of a broken build is
a lie with better manners. Where those pull against each other, accuracy wins and the voice goes
flat — which is itself a signal worth reading.

Toggled by `HOUSE_RULES_VOICE=off`, read by `inject`, defaulting on. Same shape as
`HOUSE_RULES_TRACE`: one lever, ships enabled, because a preference that ships off is a
preference nobody has.

## Still open

**Whether a `Stop`-time disclosure check is worth building.** The async lag means it can only ever
check the *previous* turn, one behind. Deferred rather than decided — the rule and the ledger land
first, and whether an automated check adds anything on top is better judged once they exist.

## Deliberately not proposed

- **Per-hook logging.** Duplicates the transcript, puts I/O on `guard`'s per-command path, and
  reverses a constraint `CLAUDE.md` calls load-bearing for reasons that still hold.
- **A `Stop` hook that blocks a reply lacking disclosure.** `Stop` fails open by design; a
  non-zero exit there stops the turn ending at all.

## Verification

1. `python claude-house-rules/plugins/house-rules/scripts/verify.py` — every check passes.
2. Run `session_ledger.py` against **this** session's transcript and confirm the ledger contains
   the incident this plan exists because of: the stop-hook feedback, the push that followed it in
   the turn continuation, and the PR update. If the ledger does not surface that, it does not work.
3. Run it **twice**, and against a fresh clone, per the green-suite rule.
4. Time it against the 3.2 MB transcript — a ledger nobody waits for is a ledger nobody runs.
