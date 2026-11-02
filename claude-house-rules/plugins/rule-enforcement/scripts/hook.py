#!/usr/bin/env python3
"""hook.py - the rule-enforcement hook handlers (#440, step 3 part A of the plugin split).

run.sh resolves a working interpreter and execs this with one argv value, the event name; the hook
payload arrives on stdin. Four events, moved out of house-rules' hook.py with their text unchanged, plus lockgate (step 3 part B):

  - inject, showrule (SessionStart) fail LOUD, not closed: a systemMessage, exit 0.
  - subagentrules    (SubagentStart) never obstructs a delegation: any failure emits a systemMessage
                     and exits 0.
  - lockgate         (PreToolUse) the repeat-failure lock; never refuses because something broke: it says so
                     in a systemMessage and allows the call.
  - scope            (UserPromptSubmit) can never erase the user's prompt: it never raises and always
                     exits 0 with at least the short reminder.

STDLIB ONLY, like house-rules. NOTHING FAILS SILENTLY (rules/house-rules.md): the last-resort net in
main() says that the event failed and did not run.
"""

import os
import sys

# The sys.path line makes `rule_enforcement` and the vendored `house_lib` importable when run.sh starts this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rule_enforcement.core import (  # noqa: E402
    emit,
    event_inject,
    event_scope,
    event_showrule,
    event_subagentrules,
)
from rule_enforcement.lock import event_lockgate  # noqa: E402

EVENTS = {
    "inject": event_inject,
    "showrule": event_showrule,
    "scope": event_scope,
    "subagentrules": event_subagentrules,
    "lockgate": event_lockgate,
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(event)
    if handler is None:
        return 0
    try:
        return handler()
    except BaseException as exc:
        # A stack trace on stdout would be read as a malformed hook decision, so it never goes there -
        # but it never goes nowhere either: the event says that it failed and did not run.
        detail = "%s: %s" % (type(exc).__name__, exc)
        if event == "inject":
            emit(
                {
                    "systemMessage": "house-rules plugin: internal error (%s). The rules "
                    "were NOT loaded into this session." % detail
                }
            )
            return 0
        emit(
            {
                "systemMessage": "house-rules plugin: the %s hook hit an internal error "
                "(%s) and did not run for this call." % (event, detail)
            }
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
