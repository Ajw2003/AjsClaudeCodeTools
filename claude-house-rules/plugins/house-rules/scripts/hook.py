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

# The core and the parts (#357, #358, #359, steps 2a-2c of #340). Each event imports only the part it
# needs (EVENTS below); the old `hook.<name>` lookups still work through __getattr__.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib

from house_rules import core

_PARTS = ("core", "docs", "safe_git", "design_loop", "delegation", "writing", "bigfiles")


def __getattr__(name):
    """Lazy `hook.<name>` for every name the parts define (public or underscore), as the star imports gave."""
    if name in _PARTS:
        return importlib.import_module("house_rules." + name)
    if not name.startswith("__"):
        for part in _PARTS:
            mod = importlib.import_module("house_rules." + part)
            if hasattr(mod, name):
                return getattr(mod, name)
    raise AttributeError("module 'hook' has no attribute %r" % name)


def _load_all():
    """handover, roadblocks and scope need every part (their globals, and the prompt links the parts register)."""
    g = globals()
    for part in _PARTS:
        mod = importlib.import_module("house_rules." + part)
        for k, v in vars(mod).items():
            if not k.startswith("__"):
                g.setdefault(k, v)
    # The parity clause is the last prompt link, after the links the parts register when imported.
    core.register_prompt(_scope_parity_link)


# ---------------------------------------------------------------------------------------
# handover - the end-of-reply dispatcher (Stop). It stays here (#359, step 2c): it calls each part's check in
# the order the checks always ran, builds one emission from what they found, and holds the parity check inline,
# because that check shares its transcript scan with the visual and plain-summary checks and its patterns are
# read by delegate and scope too. The checks themselves live in the parts:
#   core          handover_evidence_check    (reply text, the evidence claims and the not-checked disclosure)
#   safe_git      handover_commit_check, handover_handoff_check
#   writing       handover_turn_writes, handover_plain_check, handover_page_editor_check, handover_visual_check,
#                 handover_long_reply
#   design_loop   handover_stop_lines, handover_page_row, handover_checkpoints, handover_qa_retry,
#                 handover_record_offers
# ---------------------------------------------------------------------------------------

def event_roadblocks():
    """#588: its own Stop hook, so the roadblock check still runs when unattended turns the handover toggle off."""
    try:
        payload = read_payload()
    except Exception:
        emit({"systemMessage": "house-rules plugin: could not read the Stop payload, so "
              "the roadblock check is offline for this turn."})
        return 0
    if not payload:
        return 0
    retry = bool(re.search(r'"stop_hook_active"\s*:\s*true', payload))
    reply_text = handover_evidence_check(payload)[0]
    block, msg = roadblock_check(payload, reply_text, retry)
    if block:
        emit({"decision": "block", "reason": block})
    elif msg:
        emit({"systemMessage": msg})
    return 0


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
    written_now, committed_now = [], False
    multirepo = ""
    editor_owed = None
    shell_page_notes = []
    trace_lines_early = []
    transcript_path = _field(_TRANSCRIPT_RE, payload)
    if transcript_path and (_parity_enabled() or _visual_check_enabled() or _plain_summary_enabled()
                            or _clear_writing_enabled() or handoff_enabled()):
        turn_records, _detail = _records_since_last_user_message(transcript_path)
        if turn_records is not None:
            written_now, committed_now = handover_turn_writes(turn_records)
            plain_problems = handover_plain_check(written_now, committed_now, have_reply, reply_text)
            multirepo = handover_multirepo_note(written_now)
            if written_now and _parity_enabled():
                pm = _PARITY_RE.search(_last_user_text(transcript_path))
                reply_for_parity = reply_text if have_reply else ""
                if pm and not _PARITY_ACCOUNTED_RE.search(reply_for_parity):
                    parity_word = pm.group(1)
            shell_page_notes, editor_owed, trace_lines_early = handover_page_editor_check(
                transcript_path, payload, written_now, turn_records, have_reply, reply_text)
            visual_files, visual_missing = handover_visual_check(written_now, turn_records)

    try:  # #562: a note for aj only (systemMessage), never blocking
        if transcript_path and not retry:
            _bg = handover_unchecked_waits(_records_since_last_user_message(transcript_path)[0],
                                           _field(re.compile(r'"session_id"\s*:\s*"([^"]*)"'), payload))
            if _bg:
                trace_lines_early.append(_bg)
    except Exception as exc:
        trace_lines_early.append("house-rules: unchecked-wait note could not run (%s)" % type(exc).__name__)

    issue_line, issue_problem, label_line, label_problem = handover_stop_lines(payload)

    trace_lines = list(trace_lines_early)
    # #398: links the hooks told a project thread to post and that never went out.
    links_owed = []
    try:
        if transcript_path and delegation._in_project_thread():
            links_records, _links_detail = _records_since_last_user_message(transcript_path)
            if links_records is not None:
                links_owed = handover_links_owed(links_records)
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

    handover_record_offers(payload, have_reply, reply_text, trace_lines)
    long_words = handover_long_reply(payload, have_reply, reply_text)
    page_note = handover_page_row(payload, transcript_path, have_reply, reply_text, long_words, trace_lines)
    if not retry:
        if handover_checkpoints(payload, transcript_path, have_reply, reply_text, long_words, editor_owed,
                                needs_evidence, uncommitted, plain_problems, trace_lines, written=written_now,
                                committed=committed_now):
            return 0
    else:
        handover_qa_retry(payload, have_reply, reply_text, trace_lines)
    if (not needs_card and not needs_evidence and not not_checked and not uncommitted
            and not parity_word and not visual_files and not plain_problems and not issue_line
            and not long_words and not label_line and not editor_owed
            and not shell_page_notes and not page_note and not links_owed and not multirepo):
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
    if not_checked or long_words:
        parts.append(_writing_note(not_checked, long_words))
    if plain_problems:
        parts.append(_plain_summary_note(plain_problems))
    parts.extend(shell_page_notes)
    if page_note:
        parts.append(page_note)
    if editor_owed:
        parts.append((EDITOR_NOTE if editor_owed.startswith("this reply is") else PAGE_NOTE) % editor_owed)
    if parity_word:
        parts.append(_parity_report_note(parity_word))
    if visual_files:
        parts.append(_visual_note(visual_files, visual_missing))
    if uncommitted:
        parts.append(_commit_note(uncommitted))
    if multirepo:
        parts.append(multirepo)
    if issue_line:
        parts.append(issue_line)
    if label_line:
        parts.append(label_line)
    if links_owed:
        parts.append("House rules, work tracking: links owed - %s. Post them (post_message, attached) and "
                     "fix the checklist header before ending the turn." % "; ".join(links_owed))
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


EVENTS = {  # event -> (module, handler); 'hook' = this file, which loads every part first
    "inject": ("core", "event_inject"),
    "showrule": ("core", "event_showrule"),
    "issuelist": ("design_loop", "event_issuelist"),
    "profile": ("core", "event_profile"),
    "standards": ("core", "event_standards"),
    "docstiers": ("docs", "event_docstiers"),
    "diskreport": ("bigfiles", "event_diskreport"),
    "versioncheck": ("core", "event_versioncheck"),
    "scope": ("hook", "event_scope"),
    "noask": ("core", "event_noask"),
    "guard": ("safe_git", "event_guard"),
    "guardwrite": ("safe_git", "event_guardwrite"),
    "guardgithub": ("safe_git", "event_guardgithub"),
    "artifact": ("core", "event_artifact"),
    "branchnudge": ("safe_git", "event_branchnudge"),
    "creditcheck": ("safe_git", "event_creditcheck"),
    "runnable": ("core", "event_runnable"),
    "delegate": ("delegation", "event_delegate"),
    "announce": ("delegation", "event_announce"),
    "subagentrules": ("delegation", "event_subagentrules"),
    "verdict": ("delegation", "event_verdict"),
    "subagentcommit": ("delegation", "event_subagentcommit"),
    "autosave": ("delegation", "event_autosave"),
    "autosavefinal": ("delegation", "event_autosave_final"),
    "pickup": ("delegation", "event_pickup"),
    "commitgate": ("delegation", "event_commitgate"),
    "worktreesweep": ("delegation", "event_worktreesweep"),
    "agentcap": ("delegation", "event_agentcap"),
    "prompttimer": ("safe_git", "event_prompttimer"),
    "promptran": ("core", "event_promptran"),
    "audit": ("delegation", "event_audit"),
    "rclink": ("delegation", "event_rclink"),
    "userpromptaudit": ("delegation", "event_userpromptaudit"),
    "handover": ("hook", "event_handover"),
    "roadblocks": ("hook", "event_roadblocks"),
    "harvest": ("docs", "event_harvest"),
    "pagecheck": ("design_loop", "event_pagecheck"),
    "sendcheck": ("design_loop", "event_sendcheck"),
    "closablemerge": ("design_loop", "event_closablemerge"),
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    target = EVENTS.get(event)
    if target is None:
        return 0
    try:
        if target[0] == "hook":
            _load_all()
            handler = globals()[target[1]]
        else:
            handler = getattr(importlib.import_module("house_rules." + target[0]), target[1])
        core.keep_payload()  # the speed switches need the payload before some handlers read it
        core.apply_switches()  # typed feature switches set the HOUSE_RULES_ values every check reads
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
