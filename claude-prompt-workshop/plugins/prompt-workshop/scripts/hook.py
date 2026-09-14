#!/usr/bin/env python3
"""hook.py — every prompt-workshop hook handler in one stdlib-only file.

STATUS: shell/v0.1. This plugin is an offshoot of house-rules' formula (one POSIX shim, one
stdlib Python file dispatched by event, "never fails silently" on the paths that can speak) —
see docs/offshoots-plan.md at the repo root for what's a real decision here versus a stand-in.
Two events only, so far:

  - inject   (SessionStart)      fails LOUD, not closed: prints a systemMessage, exits 0.
  - workshop (UserPromptSubmit)  cannot fail: never raises, never exits non-zero. A non-zero
                                  exit on UserPromptSubmit erases the user's prompt — same
                                  contract as house-rules' `scope` handler, which this borrows
                                  its shape from directly.

run.sh resolves a working interpreter and execs this with two argv values: the event name and
nothing else — the payload always arrives on stdin.

JSON OUTPUT: every hookSpecificOutput/systemMessage payload is emitted with
json.dumps(obj, separators=(",", ":")) — no space after the colon — so verify.py can assert on
the literal serialized bytes, the same convention house-rules uses.
"""

import json
import os
import re
import sys


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception as exc:
        sys.stderr.write("prompt-workshop: could not read the hook payload from stdin: %s\n" % exc)
        return ""
    return raw.strip()


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


# ---------------------------------------------------------------------------------------
# inject — SessionStart. Loads the workshop methodology into context, the same way
# house-rules' inject loads rules/house-rules.md.
# ---------------------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.normpath(os.path.join(_HERE, "..", "rules", "prompt-workshop.md"))


def event_inject():
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as fh:
            body = fh.read()
    except Exception as exc:
        # Fails LOUD, not closed: SessionStart has nothing to block, so the honest response to
        # "the methodology file is missing or unreadable" is to say so, not to go quiet.
        emit(
            {
                "systemMessage": "prompt-workshop plugin: could not read rules/prompt-workshop.md "
                "(%s: %s). The workshop methodology was NOT loaded into this session."
                % (type(exc).__name__, exc)
            }
        )
        return 0

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": body,
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# workshop — UserPromptSubmit. Heuristically flags a prompt that reads as a task and is short
# enough to plausibly have skipped constraints, success criteria, or gating, and hands Claude a
# reminder to run the workshop flow (rules/prompt-workshop.md) before treating the literal
# prompt as the final spec. Never blocks; a false negative just means this plugin did nothing,
# which is the safe direction to fail in.
# ---------------------------------------------------------------------------------------

_PROMPT_FIELD_RE = re.compile(r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"')

# Imperative task verbs — broad on purpose, the same "over-triggering within the extracted
# field is cheap" posture house-rules' guard patterns use. A false positive here costs one
# extra clarifying round; a false negative costs nothing this plugin would have caught anyway.
_TASK_VERB_RE = re.compile(
    r"\b(build|make|create|add|write|fix|refactor|design|implement|improve|update|change|"
    r"rewrite|optimize|migrate|debug|integrate|set ?up|clean ?up|redo|automate|generate)\b",
    re.IGNORECASE,
)

_SUCCESS_CRITERIA_RE = re.compile(
    r"\b(test|tests|should|must|pass(?:es|ing)?|criteria|acceptance|so that|until|spec|"
    r"done when|expects?|verify|verif(?:y|ied|ication))\b",
    re.IGNORECASE,
)

_CONSTRAINT_RE = re.compile(
    r"\b(only|without|must not|don'?t|do not|cannot|can'?t|except|excluding|within|no more "
    r"than|limit|constraint|scope|out of scope|do not touch|keep|preserve)\b",
    re.IGNORECASE,
)

_GATING_RE = re.compile(
    r"\b(confirm|check with me|ask me|before you|before proceeding|let me review|approve|"
    r"approval|gate|checkpoint|wait for|don'?t start until|step[- ]by[- ]step|one step at a "
    r"time)\b",
    re.IGNORECASE,
)

# A prompt with an explicit go-ahead or this much detail already did the work this plugin
# exists to prompt for; firing on it would be pure friction. Rough word-count proxy for "short
# enough to have skipped something" — heuristic, not a parse.
_SHORT_WORD_LIMIT = 20

WORKSHOP_NOTE = (
    "prompt-workshop: this prompt reads as a task (an imperative verb, no stated success "
    "criteria/constraints/checkpoints) and is short enough that it may be missing more than "
    "it says. Before treating it as the final spec, run the workshop flow in "
    "rules/prompt-workshop.md: restate the goal in one sentence, ask (via AskUserQuestion) "
    "only about whichever of goal / constraints / success criteria / gating is unclear, "
    "propose the refined prompt back, then proceed under that version. Skip this entirely if "
    "the prompt is already a direct reply to a clarifying question this flow just asked, or "
    "already states its own scope and done condition."
)


def _looks_underspecified(field_text):
    if not _TASK_VERB_RE.search(field_text):
        return False
    word_count = len(field_text.split())
    if word_count > _SHORT_WORD_LIMIT:
        return False
    missing = 0
    if not _SUCCESS_CRITERIA_RE.search(field_text):
        missing += 1
    if not _CONSTRAINT_RE.search(field_text):
        missing += 1
    if not _GATING_RE.search(field_text):
        missing += 1
    return missing >= 2


def event_workshop():
    # UserPromptSubmit: a non-zero exit or an unhandled raise here ERASES THE USER'S PROMPT.
    # Every failure path must fall through to emitting nothing (equivalent to "no opinion")
    # and exiting 0 — never raise past this function.
    try:
        payload = read_payload()
        m = _PROMPT_FIELD_RE.search(payload)
        if m and _looks_underspecified(m.group(1)):
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": WORKSHOP_NOTE,
                    }
                }
            )
    except Exception:
        # Silent recovery is correct here, same reasoning as house-rules' scope: reporting the
        # failure would mean emitting *something*, and the only safe thing to emit on this
        # event when something has already gone wrong is nothing at all.
        pass
    return 0


EVENTS = {
    "inject": event_inject,
    "workshop": event_workshop,
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(event)
    if handler is None:
        return 0
    try:
        return handler()
    except BaseException as exc:
        detail = "%s: %s" % (type(exc).__name__, exc)
        if event == "workshop":
            # Never non-zero, never a raise reaching the caller - see event_workshop's own
            # comment. Going quiet is correct; there is no safe way to report this one.
            return 0
        emit(
            {
                "systemMessage": "prompt-workshop plugin: the %s hook hit an internal error "
                "(%s) and did not run for this call." % (event, detail)
            }
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
