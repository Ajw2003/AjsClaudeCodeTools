#!/usr/bin/env python3
"""hook.py — every issue-forge hook handler in one stdlib-only file.

STATUS: shell/v0.1. Offshoot of house-rules' formula — one POSIX shim, one stdlib Python file
dispatched by event, "never fails silently on the paths that can speak." See
docs/offshoots-plan.md at the repo root for the plan this was built against.

Two events:

  - inject  (SessionStart)  fails LOUD, not closed: prints a systemMessage, exits 0.
  - suggest (PostToolUse)   can't block anyway (the write/command already happened); every
                            path - fires or not - emits a one-line trace, same discipline as
                            house-rules' artifact/runnable/harvest handlers.

WHAT `suggest` ACTUALLY DOES. It is registered on two matchers in hooks.json - `Edit|Write` and
`Bash` - and dispatches to this single handler either way. It never shells out to `gh`, and it
never invokes forge.py itself: the hard rule in rules/issue-forge.md is that `gh issue create`
is a "publish/post public content" action requiring explicit chat confirmation every time, so
this hook only ever notices and reminds Claude to *offer* running `forge.py --dry-run` - the
read-only phase - never the create phase.

  - On an Edit/Write payload: reads `file_path`. If it matches one of the configured backlog
    files (ISSUE_FORGE_BACKLOG_FILES, default docs/architecture-backlog.md and
    docs/rules-backlog.md), emits a reminder.
  - On a Bash payload: reads `command`. If it references session_ledger.py, emits a reminder -
    needed because ledgers are written by a plain Python script via open(), not through the
    Write tool, so file-path matching alone can't catch a new ledger landing.

run.sh resolves a working interpreter and execs this with two argv values: the event name and
nothing else - the payload always arrives on stdin.

JSON OUTPUT: every hookSpecificOutput/systemMessage payload is emitted with
json.dumps(obj, separators=(",", ":")) - no space after the colon - so verify.py can assert on
the literal serialized bytes, the same convention house-rules/prompt-workshop/agent-router use.
"""

import json
import os
import re
import sys


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception as exc:
        sys.stderr.write("issue-forge: could not read the hook payload from stdin: %s\n" % exc)
        return ""
    return raw.strip()


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


def trace(line):
    if os.environ.get("ISSUE_FORGE_TRACE", "") == "off":
        return
    emit({"systemMessage": "issue-forge: %s" % line})


# ---------------------------------------------------------------------------------------
# inject — SessionStart. Loads the methodology + hard confirmation rule into context, the same
# way house-rules'/prompt-workshop's/agent-router's inject loads their own rules file.
# ---------------------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.normpath(os.path.join(_HERE, "..", "rules", "issue-forge.md"))


def event_inject():
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as fh:
            body = fh.read()
    except Exception as exc:
        emit(
            {
                "systemMessage": "issue-forge plugin: could not read rules/issue-forge.md "
                "(%s: %s). Issue-forge guidance was NOT loaded into this session."
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
# suggest — PostToolUse (Edit|Write, and separately Bash). Never blocks (PostToolUse can't
# anyway); every path, fires or not, emits a one-line trace. Never shells out to gh.
# ---------------------------------------------------------------------------------------

_FILE_PATH_RE = re.compile(r'"file_path"\s*:\s*"((?:[^"\\]|\\.)*)"')
_COMMAND_FIELD_RE = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"')

_DEFAULT_BACKLOG_FILES = ("docs/architecture-backlog.md", "docs/rules-backlog.md")

SUGGEST_NOTE_DOC = (
    "issue-forge: this edit touched a backlog doc ({path}). Consider offering to run "
    "`python scripts/forge.py --dry-run` to see if it produced anything issue-worthy - show the "
    "drafted list in chat and only create issues the user explicitly names. This is a reminder "
    "to you; the user was not prompted and does not need to do anything."
)

SUGGEST_NOTE_LEDGER = (
    "issue-forge: this command referenced session_ledger.py, which may have just written a new "
    "session ledger under docs/sessions/. Consider offering to run "
    "`python scripts/forge.py --dry-run` to see if the new ledger's flagged actions are "
    "issue-worthy - show the drafted list in chat and only create issues the user explicitly "
    "names. This is a reminder to you; the user was not prompted and does not need to do "
    "anything."
)


def _extract_field(payload, pattern):
    m = pattern.search(payload)
    return m.group(1) if m else None


def _configured_backlog_files():
    raw = os.environ.get("ISSUE_FORGE_BACKLOG_FILES", "")
    if not raw.strip():
        return _DEFAULT_BACKLOG_FILES
    files = [p.strip() for p in raw.split(os.pathsep) if p.strip()]
    return tuple(files) if files else _DEFAULT_BACKLOG_FILES


def _normalize(path):
    return re.sub(r"[\\/]+", "/", path).lower()


def _matches_backlog_file(file_path, backlog_files):
    norm = _normalize(file_path)
    for configured in backlog_files:
        if norm.endswith(_normalize(configured)):
            return configured
    return None


def event_suggest():
    try:
        payload = read_payload()
        if not payload:
            trace("suggest got an empty payload - nothing to check for this call.")
            return 0

        file_path = _extract_field(payload, _FILE_PATH_RE)
        if file_path:
            backlog_files = _configured_backlog_files()
            matched = _matches_backlog_file(file_path, backlog_files)
            if matched:
                emit(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": SUGGEST_NOTE_DOC.format(path=matched),
                        }
                    }
                )
                return 0
            trace(
                "suggest: %s is not a configured backlog file - not flagged." % file_path
            )
            return 0

        command = _extract_field(payload, _COMMAND_FIELD_RE)
        if command is not None:
            if "session_ledger.py" in command:
                emit(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": SUGGEST_NOTE_LEDGER,
                        }
                    }
                )
                return 0
            trace("suggest: command does not reference session_ledger.py - not flagged.")
            return 0

        trace("suggest: payload had neither file_path nor command - nothing to check.")
    except Exception:
        emit(
            {
                "systemMessage": "issue-forge plugin: the suggest reminder hit an internal "
                "error and did not run for this call."
            }
        )
    return 0


EVENTS = {
    "inject": event_inject,
    "suggest": event_suggest,
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
                "systemMessage": "issue-forge plugin: the %s hook hit an internal error (%s) "
                "and did not run for this call." % (event, detail)
            }
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
