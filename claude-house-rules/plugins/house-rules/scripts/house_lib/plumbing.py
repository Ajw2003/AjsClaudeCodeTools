"""house_lib.plumbing - hook payload, output and trace helpers shared by every plugin (#439).

Moved verbatim from house_rules/core.py. STDLIB ONLY. The source lives once in
claude-house-rules/plugins/house-lib/house_lib/; tools/sync_library.py copies it into each plugin."""

import json
import os
import sys


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception as exc:
        # Loud, not silent: an unreadable stdin and an empty stdin both return "" to the
        # caller, so without this line the two are indistinguishable downstream.
        sys.stderr.write("house-rules: could not read the hook payload from stdin: %s\n" % exc)
        return ""
    return raw.strip()


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


_TRACE_OFF = {"off", "0", "false", "no"}


def _truncate_with_notice(text, limit, label):
    """Cut text to fit limit, appending a notice that names what was cut and why - truncation
    that happens without saying so is exactly what "nothing fails silently" forbids."""
    if len(text) <= limit:
        return text
    notice = (
        "\n\n[house-rules profile: %s is %d chars and was truncated to stay under the "
        "SessionStart context limit - %d chars shown here. Read %s directly for the rest.]\n"
        % (label, len(text), limit, label)
    )
    room = max(0, limit - len(notice))
    return text[:room] + notice


def trace_enabled():
    """The decision trace ships ON. A diagnostic nobody enables until they are already lost
    is not a diagnostic - see "nothing fails silently" in rules/house-rules.md. stderr is not
    an option here: a hook that exits 0 has its stderr sent to the debug log only, never the
    transcript, so a trace written there would be off by default in everything but name.
    HOUSE_RULES_TRACE=off is the one lever, and it covers every handler. HOUSE_RULES_TRACE=
    verbose additionally restores the "looked, nothing to do" traces (see trace_noop).
    """
    return os.environ.get("HOUSE_RULES_TRACE", "on").strip().lower() not in _TRACE_OFF


def trace(message):
    """Say what this handler decided, on a path that would otherwise emit nothing.

    Only for handlers with a genuinely silent success path - guard's allow, artifact,
    runnable, handover and harvest. inject, standards, scope and delegate always emit
    something already, so a trace there would duplicate the proof it exists to provide, at
    the most expensive possible frequency (scope runs on every prompt).
    """
    if trace_enabled():
        emit({"systemMessage": message})


def trace_verbose():
    return os.environ.get("HOUSE_RULES_TRACE", "on").strip().lower() == "verbose"


def trace_noop(message):
    """The "looked, nothing to do" trace: a handler that decided nothing and acted on nothing.

    Silence is the correct output there - rules/house-rules.md defines silence as "looked,
    nothing to do". Emits only under HOUSE_RULES_TRACE=verbose. "Could not tell" and "acted"
    traces stay on trace(), which still prints by default.
    """
    if trace_verbose():
        emit({"systemMessage": message})


def _read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


# Hardware and plan probes for the machine profile: doc-ref ad50 docs/4-systems/hook-engine.md
