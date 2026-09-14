#!/usr/bin/env python3
"""hook.py — offshoot-2 placeholder.

STATUS: shell/v0.0.1. This plugin has no defined purpose yet — see docs/offshoots-plan.md at
the repo root. What exists is scaffolding only: the same dispatch-by-event shape as house-rules
and prompt-workshop (run.sh resolves an interpreter, execs this with the event name on argv[1]
and the payload on stdin), one handler (`inject`), and a SessionStart hook that says plainly,
inside the session it loads into, that this plugin is not yet doing anything.

When this offshoot gets a real purpose: replace INJECT_NOTE below, add handlers the same way
prompt-workshop's `event_workshop` was added next to `event_inject`, register the new events in
../hooks/hooks.json, and extend verify.py to cover them. Keep the same failure-mode contract per
event that house-rules documents (fails closed+loud, fails loud only, or must never fail at
all) — pick the one that matches what the new hook event is allowed to do.
"""

import json
import sys


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


INJECT_NOTE = (
    "offshoot-2 plugin: placeholder shell, no rules or behavior defined yet. This session's "
    "context was not changed by this plugin. See docs/offshoots-plan.md at the repo root for "
    "what this offshoot is waiting on."
)


def event_inject():
    # SessionStart: nothing to block, so state the placeholder status plainly rather than
    # staying silent — a silent SessionStart hook looks identical to a missing one, and the
    # point of this shell is to be visibly present while undefined.
    emit({"systemMessage": INJECT_NOTE})
    return 0


EVENTS = {
    "inject": event_inject,
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
        emit(
            {
                "systemMessage": "offshoot-2 plugin: the %s hook hit an internal error (%s) "
                "and did not run for this call." % (event, detail)
            }
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
