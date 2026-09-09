# Measuring the plugin's token footprint

`verify.py` proves the hooks behave as written. It says nothing about what they **cost**, and
those are different questions. A rule that fires correctly on every prompt and costs 360 tokens
each time is correct and expensive at the same time. `tools/measure_footprint.py` answers the
second question.

```bash
python tools/measure_footprint.py
```

Exit code 0 means the per-prompt gating is live and every failure path is safe. It runs in about
two seconds, in the foreground, and writes nothing.

## Why this needed its own tool

Three facts about how the plugin reaches a session make its cost non-obvious:

- **`SessionStart` output lands at the front of the context**, so it is paid once at full rate
  and then served from the prompt cache. Large, but not the thing driving a long session's bill.
- **`UserPromptSubmit` output lands at the tail, on every prompt, and accumulates.** It never
  caches away, and every prompt's copy is re-read on every later request. This is the cost that
  compounds, and the one worth measuring.
- **Both are re-paid in full on every subagent spawn.** A subagent that answers a question with
  zero tool calls still pays the whole prefix — one probe measured at 65,318 tokens.

So "how big is `house-rules.md`" is the wrong question. The right one is how often the expensive
branch is taken, on real prompts, by the copy that is actually installed.

## It measures the installed copy, not the repo

This is the important part, and the reason the tool is not just `wc -c` on a few files.

Claude Code runs the plugin from `~/.claude/plugins/cache/aj-house-rules/house-rules/<version>/`,
not from this repo. Those two can disagree — and have. `claude plugin install` is a no-op when
the plugin is already registered: it fetches the new version into the cache and leaves the
registration pointing at the old one, so a bumped version sits on disk unused while the stale
copy keeps running. (`tools/install.py` now runs `claude plugin update` and asserts the
registered version matches this repo, which is what closed that hole.)

A measurement that read the repo would report the savings from a change that no session had
loaded. So the tool locates the highest version directory in the cache, invokes **that**
`hook.py` as a subprocess with real payloads on stdin, and measures what comes back. Pass
`--repo` to measure the working tree instead — useful for seeing a change's effect before
installing it.

Version directories are sorted numerically, not lexically, so `2.10.0` beats `2.9.0`.

## What each section reports

### 1. Per-prompt cost

Feeds the installed `scope` handler two payloads — one plain conversational prompt, one
command-shaped — and prints the size of each reply. Before 2.6.0 there was a single fixed
1,435-char string with no branch, so if the two forms come back the same size the gating is not
in effect, and the tool says so explicitly rather than reporting a meaningless number.

Sizes are of the `additionalContext` the hook adds, unwrapped from its JSON envelope. Counting
raw stdout would charge the reminder for key names and punctuation the model never sees — about
90 chars a prompt — against a baseline that is plain text, which flatters the result.

### 2. Which form your real prompts get

The split is the whole ballgame: a short form that only fires on 5% of prompts saves nothing.
Rather than guess, this replays every prompt you have actually typed — read from the `.jsonl`
transcripts under `~/.claude/projects/` — through the live `_SCOPE_COMMAND_HINT_RE` from the
installed `hook.py`, and reports the real long/short ratio.

**Injected text is excluded by signature, and this matters.** Transcript records hold more than
what you typed: hook output, system reminders and pasted context sit in the same field. That
text contains the exact words the gating regex looks for — "command", "shell", "run" — so
counting it measures the plugin triggering on its own output. Doing that inflated the long-form
rate from 40.5% to 51.8% on the first pass here. Any change to the noise filter should be
sanity-checked against that gap.

The saving is computed against `BASELINE_SCOPE_CHARS` (1,435), the pre-2.6.0 fixed string. That
constant is a historical baseline, not a value read from anywhere at runtime — leave it alone,
or the numbers stop being comparable to earlier runs.

### 3. Per-session cost

Runs `inject` and `standards` and reports their sizes. Note that `standards` output varies by
repo: it always injects `coding-philosophy.md` and adds the C#/Unity or web/JS docs only when it
detects those markers, so the same command gives a bigger number inside a Unity project. This is
the figure that is also re-paid per subagent spawn.

### 4. Per-tool-call cost

`guard`, `artifact`, `runnable`, `harvest` and `delegate` fire per **tool call**, not per turn,
so frequency is as much of the cost as size is. Sections 1–3 price the per-prompt and per-session
hooks, which left every `PreToolUse`/`PostToolUse` handler unpriced — and with them every decision
trace.

The reminder and the trace are reported **separately**, because one call can emit both and it is
the trace this section exists to price. `reminder_text()` collapses them into one value, which is
right for sections 1–3 and wrong here; `split_output()` is the version that keeps them apart.
Collapsing them is how the harvest trace shipped unmeasured in 2.13.0.

The last two lines re-run the same calls with `HOUSE_RULES_TRACE=off`, so the trace's whole cost
is a single number you can compare against zero.

### 5. Failure paths

`scope` runs on `UserPromptSubmit`, where **a non-zero exit erases the user's prompt** before
Claude ever sees it. That makes a crash here worse than a missing reminder, and it is why the
handler was originally one literal string with no logic at all. Now that it branches on payload
content, these three cases are the regression test for that constraint: a missing `prompt` key,
malformed JSON, and empty stdin must each exit 0 **and** still emit a reminder. Any of them
failing exits the tool non-zero.

## When to re-run it

- After changing `SCOPE_REMINDER`, `SCOPE_REMINDER_SHORT`, or `_SCOPE_COMMAND_HINT_RE` — the
  keyword list is the main tuning knob, and widening it silently raises the long-form share.
- After editing `rules/house-rules.md` or the standards docs, which move the per-session number.
- After any version bump, to confirm the install actually re-pointed rather than reporting PASS
  on a stale copy.

Run `verify.py` as well. Correctness first, then cost — a cheap hook that no longer enforces the
rule is not an improvement.

## Reading the numbers honestly

Token counts are `chars // 4`. That is deliberately rough: the true ratio varies by tokenizer,
and every figure here is a comparison against a baseline measured the same way, so the constant
factor cancels out. Treat the percentages as sound and the absolute token counts as indicative.

The historical total in section 2 answers "what would this have saved over everything I have
already done", not "what will I spend next month". It scales with how much transcript history
is on the machine, so it grows on its own and is not a regression when it changes.
