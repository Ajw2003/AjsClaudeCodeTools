#!/usr/bin/env python3
"""hook.py — every agent-router hook handler in one stdlib-only file.

STATUS: shell/v0.1. Offshoot of house-rules' formula — one POSIX shim, one stdlib Python file
dispatched by event, "never fails silently on the paths that can speak." See
docs/offshoots-plan.md at the repo root for the plan this was built against.

Two events:

  - inject (SessionStart)     fails LOUD, not closed: prints a systemMessage, exits 0.
  - route  (UserPromptSubmit) cannot fail: never raises, never exits non-zero. A non-zero exit
                               on UserPromptSubmit erases the user's prompt — same contract as
                               house-rules' `scope` and prompt-workshop's `workshop` handlers,
                               which this borrows its shape from directly.

WHAT `route` ACTUALLY DOES. It cannot switch the running session's model — no hook output does
that. It classifies the prompt into a tier and, if one fits, names the matching subagent and
that subagent's OWN declared `model:` — read out of its agents/*.md frontmatter at the moment
this runs, never hardcoded here, the same "declaration read from the file, not restated" rule
house-rules' `announce` handler follows for the same reason. Claude reads the suggestion and
decides whether to delegate; this hook only ever suggests. See rules/agent-router.md.

run.sh resolves a working interpreter and execs this with two argv values: the event name and
nothing else — the payload always arrives on stdin.

JSON OUTPUT: every hookSpecificOutput/systemMessage payload is emitted with
json.dumps(obj, separators=(",", ":")) — no space after the colon — so verify.py can assert on
the literal serialized bytes, the same convention house-rules and prompt-workshop use.
"""

import json
import os
import re
import sys


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception as exc:
        sys.stderr.write("agent-router: could not read the hook payload from stdin: %s\n" % exc)
        return ""
    return raw.strip()


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


# ---------------------------------------------------------------------------------------
# inject — SessionStart. Loads the routing methodology into context, the same way
# house-rules'/prompt-workshop's inject loads their own rules file.
# ---------------------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.normpath(os.path.join(_HERE, "..", "rules", "agent-router.md"))
_AGENTS_DIR = os.path.normpath(os.path.join(_HERE, "..", "agents"))


def event_inject():
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as fh:
            body = fh.read()
    except Exception as exc:
        emit(
            {
                "systemMessage": "agent-router plugin: could not read rules/agent-router.md "
                "(%s: %s). Routing guidance was NOT loaded into this session."
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
# route — UserPromptSubmit. Classifies the prompt into a tier and, if one fits clearly,
# suggests delegating to the matching subagent along with that subagent's declared model.
# Never blocks; a false negative just means this plugin suggested nothing.
# ---------------------------------------------------------------------------------------

_PROMPT_FIELD_RE = re.compile(r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"')

# Tier 3: planning, architecture, management. Checked first — an ambiguous prompt that could
# read as either "just implement it" or "decide how to build it" costs less by being
# over-routed to the stronger model than by being under-routed to the cheaper one.
_ARCH_RE = re.compile(
    r"\b(design|architecture|architect|roadmap|trade-?offs?|strategy|strategic|RFC|"
    r"migration plan|prioriti[sz]e|prioriti[sz]ation|orchestrate|orchestration|rearchitect|"
    r"redesign|restructur\w*|governance|headcount|budget|coordinate|scheduling|plans?|"
    r"planning|planned|should we|evaluate options|system design|weigh the options|"
    r"weigh the trade-?offs|decide whether|decide how|decide what|make a decision|manage|"
    r"management|delegate|delegation)\b",
    re.IGNORECASE,
)

# Tier 1: simple doc/comms writing. Checked second — a doc-noun match is a strong, specific
# signal that should win over a generic task verb, but should not override an architecture
# signal (a request to "write the migration plan" is architecture-tier work, not doc-tier).
_DOC_RE = re.compile(
    r"\b(readme|changelog|docstring|docstrings|comment|comments|commit message|typo|typos|"
    r"proofread|wording|reword|rephrase|grammar|capitali[sz]ation|formatting|whitespace|"
    r"documentation|doc comment)\b",
    re.IGNORECASE,
)

# Tier 2: recon & implementation, the default task-shaped tier when neither of the above fit.
_TASK_VERB_RE = re.compile(
    r"\b(build|make|create|add|write|fix|refactor|implement|improve|update|change|rewrite|"
    r"optimize|migrate|debug|integrate|investigate|search|find|trace|reproduce|explore|"
    r"look into|figure out|test|set ?up|clean ?up|generate|automate)\b",
    re.IGNORECASE,
)

# Also Tier 2: investigative questions. Why this exists, why it's kept separate from
# _TASK_VERB_RE, and why it's checked after _ARCH_RE: docs/systems/offshoot-plugins.md,
# Invariants ("agent-router's recon-question regex is checked after the architecture regex").
_RECON_QUESTION_RE = re.compile(
    r"\bwhy (?:is|does|are|do|isn'?t|doesn'?t|aren'?t|don'?t|won'?t|did|wasn'?t|weren'?t)\b|"
    r"\bhow (?:does|do|did|is|are)\b.{0,60}\b(?:work|works|working|worked|fail|fails|failing|"
    r"failed|happen|happens|happened|break|breaks|breaking|broke|connect|connects|interact|"
    r"interacts|communicate|communicates)\b|"
    r"\bwhat(?:'s| is) causing\b|\bwhat causes\b",
    re.IGNORECASE,
)

# If the prompt already names a subagent, routing was either already decided or is being
# discussed directly — adding another suggestion on top would be noise, not help.
_ALREADY_ROUTED_RE = re.compile(r"@agent-router:", re.IGNORECASE)

_TIER_AGENTS = {
    "architect": "architect",
    "scribe": "scribe",
    "operative": "operative",
}

_TIER_LABELS = {
    "architect": "planning/architecture/management",
    "scribe": "doc/comms",
    "operative": "recon/implementation",
}


def _declared_model(agent_name):
    """The model the named agent's own frontmatter declares, read fresh every call.

    Never hardcoded here - if agents/<name>.md changes its model, this reflects that on the
    next prompt with no edit needed in hook.py. Same rationale as house-rules' _declared().
    """
    path = os.path.join(_AGENTS_DIR, agent_name + ".md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read()
    except Exception:
        return ""
    m = re.search(r"^model:\s*(\S+)\s*$", body, re.MULTILINE)
    return m.group(1) if m else ""


def _classify(field_text):
    if _ALREADY_ROUTED_RE.search(field_text):
        return None
    if _ARCH_RE.search(field_text):
        return "architect"
    if _DOC_RE.search(field_text):
        return "scribe"
    if _TASK_VERB_RE.search(field_text) or _RECON_QUESTION_RE.search(field_text):
        return "operative"
    return None


def event_route():
    # UserPromptSubmit: a non-zero exit or an unhandled raise here ERASES THE USER'S PROMPT.
    # Every failure path must fall through to emitting nothing and exiting 0 — never raise
    # past this function.
    try:
        payload = read_payload()
        m = _PROMPT_FIELD_RE.search(payload)
        if m:
            tier = _classify(m.group(1))
            if tier:
                agent = _TIER_AGENTS[tier]
                model = _declared_model(agent)
                model_clause = (" (declared model: %s)" % model) if model else " (model not declared — check agents/%s.md)" % agent
                note = (
                    "agent-router: this prompt reads as %s-tier work. Consider delegating to "
                    "@agent-router:%s%s instead of running it on the current session's model — "
                    "skip this if the session is already on that tier, or if the prompt doesn't "
                    "cleanly fit one tier. See rules/agent-router.md."
                    % (_TIER_LABELS[tier], agent, model_clause)
                )
                emit(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": note,
                        }
                    }
                )
    except Exception:
        # Silent recovery, same reasoning as prompt-workshop's workshop handler: the only
        # safe thing to emit on this event when something has already gone wrong is nothing.
        pass
    return 0


EVENTS = {
    "inject": event_inject,
    "route": event_route,
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
        if event == "route":
            return 0
        emit(
            {
                "systemMessage": "agent-router plugin: the %s hook hit an internal error (%s) "
                "and did not run for this call." % (event, detail)
            }
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
