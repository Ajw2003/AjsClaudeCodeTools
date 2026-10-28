#!/usr/bin/env python3
"""hook.py — every house-rules hook handler in one stdlib-only file.

run.sh resolves a working interpreter and execs this with two argv values: the event name
(one of those below) and nothing else — the hook payload always arrives on stdin, exactly
as it did for the shell scripts this replaces.

STDLIB ONLY. No third-party imports. That is the same "the checker must not itself be the
single point of failure" reasoning the old grep-only shell scripts were built on, ported
forward: any working CPython 3.8+ interpreter can run this file with nothing else installed.

JSON OUTPUT: every hookSpecificOutput/systemMessage/decision payload is emitted with
json.dumps(obj, separators=(",", ":")) — no space after the colon — because the test suite
(verify.py) asserts on the literal serialized bytes.

NOTHING FAILS SILENTLY (rules/house-rules.md). Silence from a handler means one thing: it
looked and there was nothing to do. Every path meaning "I could not tell" — an unreadable
payload, a field that would not parse, a budget exceeded, an unexpected exception — says so,
by emitting a systemMessage or writing to stderr. Never obstructing is not the same as never
speaking: a PostToolUse handler still announces that it did not run. verify.py enforces this
structurally: no `except` in this file may return without emitting or writing to stderr.

Each event handler mirrors the failure-mode contract its shell predecessor had:
  - guard        (PreToolUse)   fails CLOSED and loud: prints to stderr, exits 2.
  - guardwrite   (PreToolUse)   fails CLOSED and loud, same contract as guard: a Write that
                 would replace an existing file's entire contents is asked about, never let
                 through unchecked just because an internal error occurred.
  - inject       (SessionStart) fails LOUD, not closed: prints a systemMessage, exits 0.
  - scope        (UserPromptSubmit) cannot fail: never reads a file, never raises.
  - artifact, runnable, delegate, harvest, audit (PostToolUse) never obstruct, but never go
                 quiet: any failure emits a systemMessage and exits 0.
  - announce, subagentrules (SubagentStart), verdict (SubagentStop) never obstruct a
                 delegation: any failure emits a systemMessage and exits 0.
  - userpromptaudit (UserPromptSubmit) can never erase the user's prompt: any failure
                 emits a systemMessage (never additionalContext) and exits 0.
  - handover     (Stop) fails OPEN, loud: any failure prints a systemMessage and exits 0,
                 because a non-zero exit here would stop the turn from ending at all.

harvest additionally emits a one-line decision TRACE on every source-file write, whether or
not it fires. That is on by default on purpose: a diagnostic that ships switched off is never
enabled until someone is already lost.
"""

import os
import re
import sys

# The core and the parts (#357, #358, #359, steps 2a-2c of #340). The star imports bring every public name
# back (EVENTS below needs the event_* handlers); the underscore names this file uses are listed.
# The sys.path line makes `house_rules` and `clarity` importable when run.sh starts this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_rules import core, docs, safe_git, design_loop, delegation, writing
from house_rules.core import *  # noqa: F401,F403
from house_rules.docs import *  # noqa: F401,F403
from house_rules.safe_git import *  # noqa: F401,F403
from house_rules.design_loop import *  # noqa: F401,F403
from house_rules.delegation import *  # noqa: F401,F403
from house_rules.writing import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _PARITY_ACCOUNTED_RE,
    _PARITY_RE,
    _TOGGLE_OFF,
    _TRANSCRIPT_RE,
    _clear_writing_enabled,
    _evidence_note,
    _field,
    _last_user_text,
    _parity_enabled,
    _parity_report_note,
    _records_since_last_user_message,
    _reply_needs_card_check,
)
from house_rules.safe_git import (  # noqa: F401
    _commit_note,
)
from house_rules.writing import (  # noqa: F401
    _plain_summary_enabled,
    _plain_summary_note,
    _visual_check_enabled,
    _visual_note,
    _writing_note,
)

# ---------------------------------------------------------------------------------------
# handover - the end-of-reply dispatcher (Stop). It stays here (#359, step 2c): it calls each part's check in
# the order the checks always ran, builds one emission from what they found, and holds the parity check inline,
# because that check shares its transcript scan with the visual and plain-summary checks and its patterns are
# read by delegate and scope too. The checks themselves live in the parts:
#   core          handover_evidence_check    (reply text, the evidence claims and the not-checked disclosure)
#   safe_git      handover_commit_check
#   writing       handover_turn_writes, handover_plain_check, handover_page_editor_check, handover_visual_check,
#                 handover_long_reply
#   design_loop   handover_stop_lines, handover_page_row, handover_checkpoints, handover_qa_retry
# ---------------------------------------------------------------------------------------

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
        emit(
            {
                "systemMessage": "house-rules plugin: the command-handover check got an "
                "empty Stop payload and did not run for this turn."
            }
        )
        return 0

    # #256: on the retry (stop_hook_active) the checks still run, but only report; never block.
    retry = bool(re.search(r'"stop_hook_active"\s*:\s*true', payload))

    # The card check is not a checkpoint: it keeps its old once-only behaviour and stays quiet on the retry.
    needs_card = False if retry else _reply_needs_card_check(payload)

    (reply_text, needs_evidence, evidence_words, impossible_words, not_checked,
     could_not_tell) = handover_evidence_check(payload)
    have_reply = reply_text is not None

    uncommitted, commit_could_not_tell = handover_commit_check(payload)

    # Parity, visual and plain-summary checks share the transcript the commit check already read.
    parity_word = None
    visual_files = []
    plain_problems = []
    editor_owed = None
    shell_page_notes = []
    trace_lines_early = []
    transcript_path = _field(_TRANSCRIPT_RE, payload)
    if transcript_path and (_parity_enabled() or _visual_check_enabled() or _plain_summary_enabled()
                            or _clear_writing_enabled()):
        turn_records, _detail = _records_since_last_user_message(transcript_path)
        if turn_records is not None:
            written_now, committed_now = handover_turn_writes(turn_records)
            plain_problems = handover_plain_check(written_now, committed_now, have_reply, reply_text)
            if written_now and _parity_enabled():
                pm = _PARITY_RE.search(_last_user_text(transcript_path))
                reply_for_parity = reply_text if have_reply else ""
                if pm and not _PARITY_ACCOUNTED_RE.search(reply_for_parity):
                    parity_word = pm.group(1)
            shell_page_notes, editor_owed, trace_lines_early = handover_page_editor_check(
                transcript_path, payload, written_now, turn_records, have_reply, reply_text)
            visual_files = handover_visual_check(written_now, turn_records)

    issue_line, issue_problem, label_line, label_problem = handover_stop_lines(payload)

    trace_lines = list(trace_lines_early)
    # #398: links the hooks told a project thread to post and that never went out.
    links_owed = []
    try:
        if transcript_path and delegation._in_project_thread():
            links_records, _links_detail = _records_since_last_user_message(transcript_path)
            if links_records is not None:
                links_owed = handover_links_owed(links_records)
        if transcript_path and delegation._link_session():
            own = delegation.session_link_owed(transcript_path, reply_text if have_reply else "")
            if own:
                links_owed.append(own)
    except Exception as exc:
        trace_lines.append("house-rules: links-owed check could not run (%s)" % type(exc).__name__)
    if issue_problem:
        trace_lines.append(issue_problem)
    if label_problem:
        trace_lines.append(label_problem)
    if could_not_tell:
        # Fail open, loud: a claim was made and this could not confirm or deny it, so it says
        # so rather than silently assuming either answer - but it never blocks, and it never
        # asserts the claim is wrong.
        trace_lines.append(
            "house-rules: evidence check could not tell whether a tool ran for this reply's "
            "claim (%s)." % could_not_tell
        )
    if commit_could_not_tell:
        trace_lines.append(
            "house-rules: commit check could not tell whether this turn's files are committed "
            "(%s)." % commit_could_not_tell
        )

    long_words = handover_long_reply(payload, have_reply, reply_text)
    # #324: the writing check no longer runs on chat replies (pages and new issues keep it), so no findings
    # and no report line here; the not-checked disclosure still goes through _writing_note.
    writing = []

    page_note = handover_page_row(payload, transcript_path, have_reply, reply_text, long_words, trace_lines)
    if not retry:
        if handover_checkpoints(payload, transcript_path, have_reply, reply_text, long_words, editor_owed,
                                needs_evidence, uncommitted, plain_problems, trace_lines):
            return 0
    else:
        handover_qa_retry(payload, have_reply, reply_text, trace_lines)
    if (not needs_card and not needs_evidence and not not_checked and not uncommitted
            and not parity_word and not visual_files and not plain_problems and not issue_line
            and not long_words and not label_line and not writing and not editor_owed
            and not shell_page_notes and not page_note and not links_owed):
        if trace_lines:
            emit({"systemMessage": " ".join(trace_lines)})
        # The one handler that must NOT trace when no check fires - direct rule conflict,
        # not a cost argument. docs/architecture.md, "handover is the one deliberate exception".
        return 0

    # additionalContext, not decision: "block". Both continue the turn under the same loop
    # protections, but this one is labelled Stop hook feedback rather than raising a hook
    # error - and this hook is guidance working as designed, not a failure. All checks share
    # ONE emission when several fire - two emit() calls would be two concatenated JSON objects.
    parts = []
    if needs_card:
        parts.append(HANDOVER_NOTE)
    if needs_evidence:
        parts.append(_evidence_note(evidence_words, impossible_words))
    if not_checked or writing or long_words:
        parts.append(_writing_note(not_checked, writing, long_words))
    if plain_problems:
        parts.append(_plain_summary_note(plain_problems))
    parts.extend(shell_page_notes)
    if page_note:
        parts.append(page_note)
    if editor_owed:
        parts.append(EDITOR_NOTE % editor_owed)
    if parity_word:
        parts.append(_parity_report_note(parity_word))
    if visual_files:
        parts.append(_visual_note(visual_files))
    if uncommitted:
        parts.append(_commit_note(uncommitted))
    if issue_line:
        parts.append(issue_line)
    if label_line:
        parts.append(label_line)
    if links_owed:
        if delegation._in_project_thread():
            how = "Post them (post_message, attached) and fix the checklist header before ending the turn."
        else:
            how = "Put the link at the top of your reply before ending the turn."
        parts.append("House rules, work tracking: links owed - %s. %s" % ("; ".join(links_owed), how))
    if retry:
        # #322/#323: the retry reports to aj only; additionalContext would wake the model and loop.
        emit({"systemMessage": " ".join(trace_lines + parts)})
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "\n\n".join(parts)}}
    if trace_lines:
        out["systemMessage"] = " ".join(trace_lines)
    emit(out)
    return 0


def _scope_parity_link(payload, field):
    if field is not None and _PARITY_RE.search(field) and _parity_enabled():
        return SCOPE_PARITY_CLAUSE, ""
    return "", ""


# The parity clause is the last prompt link, after the waiting, loop and delegate links the parts register
# when they are imported above, so scope still adds the clauses in the order it always did.
core.register_prompt(_scope_parity_link)


EVENTS = {
    "inject": event_inject,
    "showrule": event_showrule,
    "issuelist": event_issuelist,
    "profile": event_profile,
    "standards": event_standards,
    "docstiers": event_docstiers,
    "versioncheck": event_versioncheck,
    "scope": event_scope,
    "guard": event_guard,
    "guardwrite": event_guardwrite,
    "guardgithub": event_guardgithub,
    "artifact": event_artifact,
    "branchnudge": event_branchnudge,
    "creditcheck": event_creditcheck,
    "runnable": event_runnable,
    "delegate": event_delegate,
    "announce": event_announce,
    "subagentrules": event_subagentrules,
    "verdict": event_verdict,
    "subagentcommit": event_subagentcommit,
    "autosave": event_autosave,
    "commitgate": event_commitgate,
    "worktreesweep": event_worktreesweep,
    "agentcap": event_agentcap,
    "prompttimer": event_prompttimer,
    "promptran": event_promptran,
    "audit": event_audit,
    "rclink": event_rclink,
    "userpromptaudit": event_userpromptaudit,
    "handover": event_handover,
    "harvest": event_harvest,
    "pagecheck": event_pagecheck,
    "closablemerge": event_closablemerge,
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(event)
    if handler is None:
        return 0
    try:
        return handler()
    except BaseException as exc:
        # The last-resort net. A stack trace on stdout would be read as a malformed hook
        # decision, so it never goes there - but it never goes nowhere either. Every event
        # says that it failed and did not run; see "nothing fails silently" in the module
        # docstring. Before that rule landed this returned 0 in silence for every event
        # except guard and inject, which made an internal crash in scope, artifact,
        # runnable, delegate or handover completely invisible.
        detail = "%s: %s" % (type(exc).__name__, exc)
        if event == "guard":
            sys.stderr.write(
                "house-rules guard: internal error (%s), blocking rather than letting it "
                "through unchecked.\n" % detail
            )
            return 2
        if event == "guardwrite":
            sys.stderr.write(
                "house-rules guardwrite: internal error (%s), blocking rather than letting "
                "an unchecked overwrite through.\n" % detail
            )
            return 2
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
