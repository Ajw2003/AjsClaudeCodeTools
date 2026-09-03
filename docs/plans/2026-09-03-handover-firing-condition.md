# Make the Stop hook fire only when there is something to check

## Context

The second real handover (2.3.1, desktop Code tab) came out essentially correct: item 1 stated as a
navigate-and-open instruction, no redundant `cd`, PowerShell notation matching the shell that was
actually used, `UNTESTED:` above the fence, header line and `*Next:*` present. The four defects
from the first screenshot did not recur, and 2.4.0's rule changes were not even in play.

So the format is no longer the problem. The **hook's noise** is:

- `Both steps already carry all six fields in card shape.` — the hook fired on a *conforming* reply
  and the compliance got announced, which `HANDOVER_NOTE` already forbids in as many words.
- A turn that opened a pull request and handed over no commands at all still had to answer the
  check, producing `This turn handed over no commands`. Pure overhead, on every such turn.

Research settled how to fix it, and the mechanism is documented and recommended:

- **`Stop` payloads carry `last_assistant_message`** — "the text content of Claude's final
  response, so hooks can access it without parsing the transcript file". The docs explicitly
  steer hooks that need the final text *away* from `transcript_path`, which "may lag the in-memory
  conversation".
- **`hookSpecificOutput.additionalContext` is the documented alternative to `decision: "block"`**
  for a hook "working as designed and giving Claude guidance". Same continuation semantics and the
  same loop protections (`stop_hook_active`, an 8-consecutive-continuation cap), but the transcript
  labels it `Stop hook feedback` instead of raising a hook *error*.
- **The corrected turn cannot be made silent.** Undocumented, and `suppressOutput` "has no effect".
  So not firing is the only lever that exists — which is exactly what gating on
  `last_assistant_message` buys.

Outcome wanted: a turn that hands over no commands ends silently, and a turn that does hand them
over gets guidance framed as guidance rather than as an error.

## Changes

### 1. `hook.py` — `event_handover` gates on what was actually written

Keep the existing order: `HOUSE_RULES_HANDOVER=off` → silent; unreadable payload → `systemMessage`,
exit 0 (it must never wedge a turn); `stop_hook_active` → silent.

Then add the field extraction, following **`guard`'s three-tier ladder**, which exists for exactly
this shape of problem and is already the documented pattern in `CLAUDE.md`:

1. **`last_assistant_message` found** → fire only if it contains a fenced block (` ``` `). No fence
   means no command was handed over and there is nothing to check.
2. **Field absent** (an older CLI that does not send it) → fire, exactly as the handler behaves
   today. The middle tier is what stops a version difference silently disabling the check.
3. **Unreadable or internal error** → unchanged, fails open and loud.

Per your call, the trigger stays at "contains a fenced block" rather than also skipping replies
that already carry the card markers — so a conforming reply still gets checked.

### 2. `hook.py` — emit guidance, not an error

Replace `{"decision": "block", "reason": HANDOVER_NOTE}` with
`{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": HANDOVER_NOTE}}`, matching
the shape `event_delegate` already emits for `PostToolUse`.

The failure mode is unchanged in the direction that matters: if an older CLI ignores the field, the
check goes quiet rather than wedging the turn, and `handover` is documented as failing open anyway.

### 3. `HANDOVER_NOTE` — two wording changes the gating forces

- **Delete the "handed over no commands" branch entirely.** It cannot happen once the hook only
  fires on a reply containing a fence, and leaving it in invites exactly the noise being removed.
- **Strengthen the satisfied branch.** Since a conforming reply still fires the check, this
  sentence is now carrying the whole weight: end the turn with no commentary, and say plainly that
  a sentence asserting the reply already complies *is itself* the failure — that is the observed
  defect, and "do not mention this check" was evidently not strong enough.

### 4. `rules/house-rules.md` — one line, under `#### The card`

A card never announces its own compliance. Belongs in the rules on its own merits, and gives
`verify.py` a phrase to pin the new `HANDOVER_NOTE` wording against.

### 5. `verify.py` — the firing condition is now the thing under test

`hand_case` currently detects `'"decision":"block"' in out`; that must become the
`additionalContext` shape, or every existing Stop case silently stops testing what it claims to.

New cases alongside the existing four:

- `last_assistant_message` containing a fenced block → **fires**.
- `last_assistant_message` with no fence → **silent**. This is the noise fix, and the case that
  would have caught the "handed over no commands" turn.
- **No `last_assistant_message` field at all** → **fires**. Pins the middle tier of the ladder, the
  same way the existing guard test pins its fallback.
- Assert the emitted JSON carries `hookEventName: "Stop"` and `additionalContext`, not `decision`.
- Extend the handover drift list with the new phrases.

### 6. Docs

- `CLAUDE.md` — the `Stop`/`handover` row says "Blocks the turn **once**". It now adds feedback
  once, and only when the reply contains a fenced block. The row must say both, since `verify.py`
  checks this table against `hooks.json`.
- `docs/desktop-verification.md` — record under **Findings so far**: the second real handover on
  2.3.1 was correct in every field, so the format wording is working and the four earlier defects
  did not recur; the only defect was the compliance sentence, which motivated this change. This is
  also further partial evidence for §2a, which it does not close.

### 7. Version

Fold into the unreleased **2.4.0** rather than bumping again. PR #12 is still open and `main` is at
2.3.1, so 2.4.0 has never been installed anywhere; two version numbers for one unreleased change
would be noise. The PR body needs updating to cover this.

## Critical files

- `claude-house-rules/plugins/house-rules/scripts/hook.py` — `event_handover` and `HANDOVER_NOTE`
- `claude-house-rules/plugins/house-rules/scripts/verify.py` — `hand_case` plus the new cases
- `claude-house-rules/plugins/house-rules/rules/house-rules.md` — one line
- `CLAUDE.md`, `docs/desktop-verification.md`

## Verification

```bash
python claude-house-rules/plugins/house-rules/scripts/verify.py
```

Exit 0 with the new cases passing, and — importantly — the existing Stop cases still passing
against the changed output shape rather than being quietly satisfied by a string that no longer
appears.

Then on the desktop app, after merging and updating: a turn that hands over no commands should end
with **no** trailing sentence about the check, and a turn that hands over commands correctly should
end with **no** "already carries all six fields" line. Both were observed and are what this fixes.

## Not doing

- Reading `transcript_path`. The docs warn it "may lag the in-memory conversation" and steer hooks
  needing the final text to `last_assistant_message` instead.
- Skipping the check when card markers are already present — your call, so a conforming reply is
  still checked and the note's wording carries that load.
- Trying to make the corrected turn silent. Undocumented, and `suppressOutput` explicitly does
  nothing.
