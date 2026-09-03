#!/usr/bin/env python3
"""hook.py — all seven house-rules hook handlers in one stdlib-only file.

run.sh resolves a working interpreter and execs this with two argv values: the event name
(one of the seven below) and nothing else — the hook payload always arrives on stdin, exactly
as it did for the shell scripts this replaces.

STDLIB ONLY. No third-party imports. That is the same "the checker must not itself be the
single point of failure" reasoning the old grep-only shell scripts were built on, ported
forward: any working CPython 3.8+ interpreter can run this file with nothing else installed.

JSON OUTPUT: every hookSpecificOutput/systemMessage/decision payload is emitted with
json.dumps(obj, separators=(",", ":")) — no space after the colon — because the test suite
(verify.py) asserts on the literal serialized bytes.

Each event handler mirrors the failure-mode contract its shell predecessor had:
  - guard        (PreToolUse)   fails CLOSED and loud: prints to stderr, exits 2.
  - inject       (SessionStart) fails LOUD, not closed: prints a systemMessage, exits 0.
  - scope        (UserPromptSubmit) cannot fail: never reads a file, never raises.
  - artifact, runnable, delegate (PostToolUse) never obstruct: any failure is silent, exit 0.
  - handover     (Stop) fails OPEN, loud: any failure prints a systemMessage and exits 0,
                 because a non-zero exit here would stop the turn from ending at all.
"""

import json
import re
import sys


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:
        return ""
    return raw.strip()


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


# ---------------------------------------------------------------------------------------
# inject — SessionStart
# ---------------------------------------------------------------------------------------

import os


def _read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def event_inject():
    here = os.path.dirname(os.path.abspath(__file__))
    rules_path = os.path.join(here, "..", "rules", "house-rules.md")
    envfile = os.environ.get("HOUSE_RULES_ENV_FILE") or os.path.join(
        here, "..", "rules", "environment.md"
    )

    try:
        body = _read_text(rules_path)
    except OSError:
        emit(
            {
                "systemMessage": "house-rules plugin: cannot read rules/house-rules.md. "
                "The rules were NOT loaded into this session."
            }
        )
        return 0

    body = body.replace("\r\n", "\n")
    if not body.strip():
        emit(
            {
                "systemMessage": "house-rules plugin: rules/house-rules.md is empty. "
                "The rules were NOT loaded into this session."
            }
        )
        return 0

    try:
        envbody = _read_text(envfile).replace("\r\n", "\n")
    except OSError:
        envbody = ""

    if not envbody.strip():
        envbody = (
            "# This machine\n\n"
            "NOT RECORDED YET. rules/environment.md is missing or empty, so nothing is "
            "known about this machine beyond runtime-detected facts.\n\n"
            "Before relying on any environment fact - a shell, a tool, a version, a path - "
            "discover it by running the check, then write what you found into "
            "rules/environment.md. Do not assume it.\n"
        )

    preamble = (
        "The following are the user standing house rules. They apply to every project and "
        "override default behaviour. They are also enforced by a PreToolUse hook that will "
        "put a permission prompt in front of the user for mutating git commands, destructive "
        "commands, and backgrounded or hidden processes. That hook is a backstop, not "
        "permission to skip asking in chat first.\n\n"
    )
    separator = (
        "\n\n---\n\nThe machine these rules run on, as recorded. The first rule says to "
        "build for what is written here rather than what seems likely:\n\n"
    )

    emit(
        {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": preamble + body + separator + envbody,
            },
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# scope — UserPromptSubmit. Must not be able to fail: one fixed string, no file read.
# ---------------------------------------------------------------------------------------

SCOPE_REMINDER = (
    "Standing house rules (full text was injected at session start):\n"
    "- Match response depth to the task - do not reason at length about something simple.\n"
    "- Find out what machine you are on, then build for that - no portability work unless asked.\n"
    "- Build only what was asked. Where it is ambiguous, ask instead of assuming.\n"
    "- Deliver a whole workflow: exact commands to run, no manual config editing, no step the "
    "user has to do by hand.\n"
    "- Artifacts go in the project directory as real files, not in chat and not in a temp "
    "directory.\n"
    "- Never hand over a command you have not run where the user will run it. Running "
    "something similar is not running it.\n"
    "- Every command you hand over states the shell (named, and correct as the fence label - "
    "that label is what the Run button executes), the absolute working directory, the exact "
    "command, and what the user will see. If you did not run it, the block starts with "
    "UNTESTED:. A bare command block is not an instruction."
)


def event_scope():
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": SCOPE_REMINDER,
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# guard — PreToolUse on Bash / PowerShell. Fails closed and loud.
# ---------------------------------------------------------------------------------------

# The 14 guard patterns, ported character-for-character from guard.sh's grep -E regexes to
# Python re syntax. [[:alnum:]] -> [0-9A-Za-z] (never \w — the patterns list "_" separately).
GUARD_R1 = [
    (r"-WindowStyle\s+Hidden", "starts a hidden window you cannot watch"),
    (r"Start-Process", "spawns a separate process with Start-Process"),
    (r"Start-Job|\s-AsJob", "runs the work as a background job"),
    (
        r"(^|[^0-9A-Za-z_.-])(nohup|setsid|disown)([^0-9A-Za-z_-]|$)",
        "detaches the process from your terminal",
    ),
    (r'[^&]&\s*\\?"', "backgrounds the command with a trailing ampersand"),
]

GUARD_R3 = [
    (
        r"git\s+(-[^\s]+\s+)*push([^0-9A-Za-z-]|$)",
        "reaches a remote (push)",
    ),
    (
        r"git\s+(-[^\s]+\s+)*(commit|reset|revert|clean|rebase|merge|filter-branch|cherry-pick|am|apply)([^0-9A-Za-z-]|$)",
        "writes history, the index, or the working tree",
    ),
]

GUARD_R4 = [
    (
        r"(^|[^0-9A-Za-z_./-])rm\s+-[^\s]*[rf]",
        "deletes files recursively or by force",
    ),
    (r"Remove-Item", "deletes files (Remove-Item)"),
    (r"(del|erase)\s+/[fqs]|rmdir\s+/s", "deletes files (del /f or rmdir /s)"),
    (r"Stop-Process|taskkill|pkill|kill\s+-9", "kills a running process"),
    (
        r"Clear-Content|truncate\s+-s",
        "truncates or overwrites file contents in place",
    ),
    (
        r"git\s+(-[^\s]+\s+)*(checkout\s+(--|\.(\s|$))|restore([^0-9A-Za-z-]|$))",
        "throws away uncommitted edits to a file (git checkout -- / git restore)",
    ),
    (
        r"git\s+(-[^\s]+\s+)*stash\s+(drop|clear)([^0-9A-Za-z-]|$)",
        "deletes stashed work permanently (git stash drop / clear)",
    ),
]

GUARD_BUCKETS = [
    ("Never hide work in a background window or a silent process", GUARD_R1),
    ("Never commit without asking", GUARD_R3),
    ("Never take a destructive action without checking first", GUARD_R4),
]

# tier 3: pull out just "command":"..." — the first one. Allows backslash-escaped quotes.
_COMMAND_FIELD_RE = re.compile(r'"command"\s*:\s*"(?:[^"\\]|\\.)*"')


def _guard_subject(payload):
    m = _COMMAND_FIELD_RE.search(payload)
    return m.group(0) if m else payload


def event_guard():
    try:
        payload = read_payload()
    except Exception:
        sys.stderr.write(
            "house-rules guard: could not read the hook payload from stdin.\n"
        )
        sys.stderr.write(
            "Blocking this command rather than letting it through unchecked.\n"
        )
        return 2

    if not payload:
        return 0

    subject = _guard_subject(payload)

    hits = {title: [] for title, _ in GUARD_BUCKETS}
    for title, patterns in GUARD_BUCKETS:
        for pattern, reason in patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                hits[title].append(reason)

    if not any(hits.values()):
        return 0

    lines = ["Your house rules want you asked before this runs:"]
    for title, _ in GUARD_BUCKETS:
        reasons = hits[title]
        if reasons:
            lines.append("")
            lines.append(f"  Rule: {title}")
            for r in reasons:
                lines.append(f"    - {r}")
    lines.append("")
    lines.append(
        "Approve to let it run, or reject and Claude will explain what it was about to do."
    )
    reason_text = "\n".join(lines)

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason_text,
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# artifact / runnable — PostToolUse. Narrow: match the file_path field only, never contents.
# ---------------------------------------------------------------------------------------

_FILE_PATH_RE = re.compile(r'"file_path"\s*:\s*"([^"]*)"')

_OUTSIDE_PATTERNS = [
    re.compile(r"[\\/]+\.claude[\\/]+plans[\\/]+", re.IGNORECASE),
    re.compile(r"AppData[\\/]+Local[\\/]+Temp[\\/]+", re.IGNORECASE),
    re.compile(r'(^|[\\/:"])(tmp|temp)[\\/]+', re.IGNORECASE),
    re.compile(r"scratchpad", re.IGNORECASE),
]


def _extract_file_path(payload):
    m = _FILE_PATH_RE.search(payload)
    return m.group(1) if m else None


def _is_outside_project(file_path):
    return any(p.search(file_path) for p in _OUTSIDE_PATTERNS)


ARTIFACT_NOTE = (
    "House rules, artifact custody: that document was written outside the project "
    "directory, so it is not tracked and will not outlive this session. Before you finish "
    "this task, copy it into the project as a real file - docs/ for documents, docs/plans/ "
    "for plans - and tell the user the path. This is a reminder to you; the user was not "
    "prompted and does not need to do anything."
)


def event_artifact():
    try:
        payload = read_payload()
        if not payload:
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        if not re.search(r"\.(md|txt)$", file_path, re.IGNORECASE):
            return 0
        if not _is_outside_project(file_path):
            return 0
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": ARTIFACT_NOTE,
                }
            }
        )
    except Exception:
        emit(
            {
                "systemMessage": "house-rules plugin: the artifact-location reminder hit an "
                "error and is offline for this call."
            }
        )
    return 0


RUNNABLE_NOTE = (
    "House rules, whole workflows: you just created a runnable file. A runnable file you "
    "have not run is a starting point, not a whole workflow. Before you finish this task, "
    "run it and confirm it works, or say why running does not apply. Never hand over a "
    "command you have not run. This is a reminder to you; the user was not prompted and "
    "does not need to do anything."
)

_RUNNABLE_EXT_RE = re.compile(
    r"\.(py|js|mjs|cjs|ts|sh|ps1|bat|cmd)$", re.IGNORECASE
)
_RUNNABLE_BARE_RE = re.compile(
    r"^(dockerfile|docker-compose\.ya?ml)$", re.IGNORECASE
)


def event_runnable():
    try:
        payload = read_payload()
        if not payload:
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        base = re.split(r"[\\/]", file_path)[-1]
        if not (_RUNNABLE_EXT_RE.search(base) or _RUNNABLE_BARE_RE.match(base)):
            return 0
        if _is_outside_project(file_path):
            return 0
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": RUNNABLE_NOTE,
                }
            }
        )
    except Exception:
        emit(
            {
                "systemMessage": "house-rules plugin: the run-what-you-wrote reminder hit "
                "an error and is offline for this call."
            }
        )
    return 0


# ---------------------------------------------------------------------------------------
# delegate — PostToolUse on ExitPlanMode. No dependencies, one fixed string.
# ---------------------------------------------------------------------------------------

DELEGATE_NOTE = (
    "House rules, execution model: the plan is settled, so the implementation is delegated "
    "work now. Hand it to the @house-rules:executor subagent (Task tool, subagent_type "
    "house-rules:executor) with the plan steps written out, rather than implementing it "
    "here. That agent is pinned to Sonnet at low effort, which is the whole point: "
    "deliberation is done, and re-deliberating it on the planning model costs the user for "
    "nothing. Do not re-plan inside the delegation - give it the decided steps. The "
    "exception is genuinely trivial work, where handing over the context costs more than "
    "doing it; say so in one line and just do it. This is a reminder to you; the user was "
    "not prompted and does not need to do anything."
)


def event_delegate():
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": DELEGATE_NOTE,
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# handover — Stop. Fails OPEN, loud: never wedge the turn.
# ---------------------------------------------------------------------------------------

HANDOVER_NOTE = (
    "House rules, command handover - check before this turn ends. For every shell command "
    "in this reply, all five must be present: (1) the shell it runs in, named in the prose "
    "AND correct as the fence label - the fence label is what the Run button executes; (2) "
    "the absolute working directory to run it from; (3) the exact command, copy-pasteable, "
    "no placeholders; (4) what the user will see when it works; (5) UNTESTED: as the first "
    "word of the block if you did not run that exact command, in that shell, against those "
    "exact paths - running something similar is not running it. If the reply already "
    "satisfies all five, stop immediately and add nothing - do not restate it, do not "
    "re-run anything, do not mention this check. If something is missing, append one short "
    "corrected block covering only what was missing - never repeat the whole answer. If "
    "this turn handed over no commands, say so in one line and stop - do not re-explain "
    "the work."
)

_TOGGLE_OFF = {"off", "0", "false", "no"}


def event_handover():
    import os as _os

    toggle = _os.environ.get("HOUSE_RULES_HANDOVER", "on").strip().lower()
    if toggle in _TOGGLE_OFF:
        return 0

    try:
        payload = read_payload()
    except Exception:
        emit(
            {
                "systemMessage": "house-rules plugin: could not read the Stop payload, so "
                "the command-handover check is offline for this turn."
            }
        )
        return 0

    if not payload:
        return 0

    if re.search(r'"stop_hook_active"\s*:\s*true', payload):
        return 0

    emit({"decision": "block", "reason": HANDOVER_NOTE})
    return 0


EVENTS = {
    "inject": event_inject,
    "scope": event_scope,
    "guard": event_guard,
    "artifact": event_artifact,
    "runnable": event_runnable,
    "delegate": event_delegate,
    "handover": event_handover,
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(event)
    if handler is None:
        return 0
    try:
        return handler()
    except BaseException:
        # Never let an unhandled exception crash silently with a stack trace on stdout
        # (which would be read as a malformed hook decision). Each handler already fails
        # according to its own event's contract; this is the last-resort net.
        if event == "guard":
            sys.stderr.write(
                "house-rules guard: internal error, blocking rather than letting it "
                "through unchecked.\n"
            )
            return 2
        if event == "inject":
            emit(
                {
                    "systemMessage": "house-rules plugin: internal error. The rules were "
                    "NOT loaded into this session."
                }
            )
            return 0
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
