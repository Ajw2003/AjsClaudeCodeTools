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

import json
import os
import re
import sys

# The core and the parts (#357, #358, #359, steps 2a-2c of #340). The star imports bring every public name
# back (EVENTS below needs the event_* handlers); the underscore names this file uses are listed.
# The sys.path line makes `house_rules` and `clarity` importable when run.sh starts this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from house_rules import core, docs, safe_git, design_loop, delegation, writing, bigfiles
from house_rules.core import *  # noqa: F401,F403
from house_rules.docs import *  # noqa: F401,F403
from house_rules.safe_git import *  # noqa: F401,F403
from house_rules.design_loop import *  # noqa: F401,F403
from house_rules.delegation import *  # noqa: F401,F403
from house_rules.writing import *  # noqa: F401,F403
from house_rules.bigfiles import event_diskreport  # noqa: F401
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
    block, msg = step_stop_check(payload, reply_text)  # #640: first, on every stop, even with no reply text
    if block:
        emit({"decision": "block", "reason": block})
        return 0
    block, msg2 = roadblock_check(payload, reply_text, retry)
    msg = msg or msg2
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


# The parity clause is the last prompt link, after the waiting, loop and delegate links the parts register
# when they are imported above, so scope still adds the clauses in the order it always did.
core.register_prompt(_scope_parity_link)


# ---------------------------------------------------------------------------------------
# pretool / posttool (#628, step 3 of #625): one process per tool phase. Each runs, in hooks.json's old order,
# the checks whose matcher fits the payload's tool_name, replaying the one stdin payload (core.keep_payload).
# Claude Code ran same-phase hooks in parallel and never skipped one because another denied, so none is skipped
# here either; a deny from any wins. sendcheck (timeout 300) keeps its own hooks.json entry.
# ---------------------------------------------------------------------------------------
_GH = "mcp__(github|GitHub)__"
PRE_CHECKS = [
    ("Bash|PowerShell", "guard"),
    ("Write", "guardwrite"),
    (_GH + "(create_pull_request|update_pull_request|issue_write|add_issue_comment|update_issue_comment|"
     "add_reply_to_pull_request_comment|add_comment_to_pending_review|pull_request_review_write|push_files|"
     "create_or_update_file|create_branch)", "guardgithub"),
    ("AskUserQuestion|ExitPlanMode|.*[Pp]ause_goal.*", "noask"),
    ("Agent|Task", "agentcap"),
    ("Write|Edit|NotebookEdit|Bash|PowerShell", "commitgate"),
    ("Write|Artifact", "pagecheck"),
]
POST_CHECKS = [
    ("Write|Edit", "artifact"),
    ("Write|Edit", "branchnudge"),
    ("Bash", "creditcheck"),
    ("Bash|" + _GH + "(merge_pull_request|issue_write)", "closablemerge"),
    ("Write", "runnable"),
    ("Write|Edit", "harvest"),
    ("ExitPlanMode", "delegate"),
    ("Agent|Task", "audit"),
    ("mcp__hearthbot__start_remote_control", "rclink"),
    ("Write|Edit|NotebookEdit|Bash|PowerShell|" + _GH + "issue_write", "autosave"),
    ("Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit|WebFetch|WebSearch|mcp__.*", "promptran"),
]
FAIL_CLOSED = ("guard", "guardwrite")  # a crash in these blocks; main()'s net says the same for the single events
_DECISION_RANK = {"deny": 3, "ask": 2, "allow": 1}


def _run_captured(name):
    """Run one handler with stdout/stderr captured; returns (rc, stdout, stderr, crash text or None)."""
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = EVENTS[name]()
    except BaseException as exc:
        return None, out.getvalue(), err.getvalue(), "%s: %s" % (type(exc).__name__, exc)
    return (rc or 0), out.getvalue(), err.getvalue(), None


def _merge_phase(results):
    """Combine [(name, rc, out, err, crash)] into (stdout text, stderr text, exit code)."""
    errs, objs, rc = [], [], 0
    for name, c, out, err, crash in results:
        if crash:
            if name in FAIL_CLOSED:
                errs.append("house-rules %s: internal error (%s), blocking rather than letting it through "
                            "unchecked.\n" % (name, crash))
                rc = 2
                continue
            errs.append("house-rules %s: internal error (%s); this check did not run, the others continue.\n"
                        % (name, crash))
            objs.append({"systemMessage": "house-rules plugin: the %s hook hit an internal error (%s) and did "
                                          "not run for this call." % (name, crash)})
        if err:
            errs.append(err if err.endswith("\n") else err + "\n")
        if c == 2:
            rc = 2
        if out.strip():
            try:
                obj = json.loads(out)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                objs.append(obj)
            else:
                errs.append("house-rules %s: printed non-JSON on stdout: %s\n" % (name, out.strip()))
    merged, ctx, sysmsg, reasons, top_reasons, best = {}, [], [], [], [], ""
    for o in objs:
        h = o.get("hookSpecificOutput") or {}
        if o.get("systemMessage"):
            sysmsg.append(o["systemMessage"])
        if h.get("additionalContext"):
            ctx.append(h["additionalContext"])
        d = h.get("permissionDecision", "")
        if _DECISION_RANK.get(d, 0) > _DECISION_RANK.get(best, 0):
            best, reasons = d, []
        if d and d == best and h.get("permissionDecisionReason"):
            reasons.append(h["permissionDecisionReason"])
        if o.get("decision") == "block":
            merged["decision"] = "block"
            top_reasons.append(o.get("reason", ""))
        for k, v in o.items():
            if k not in ("systemMessage", "hookSpecificOutput", "decision", "reason"):
                merged.setdefault(k, v)
        for k, v in h.items():
            if k not in ("additionalContext", "permissionDecision", "permissionDecisionReason", "hookEventName"):
                merged.setdefault("hookSpecificOutput", {}).setdefault(k, v)
    if rc == 2:  # exit 2 makes Claude Code ignore stdout, so every message goes to stderr
        errs.extend(r + "\n" for r in reasons + top_reasons + ctx + sysmsg)
        return "", "".join(errs), 2
    if best or ctx or "hookSpecificOutput" in merged:
        hso = merged.setdefault("hookSpecificOutput", {})
        hso["hookEventName"] = next((o["hookSpecificOutput"]["hookEventName"] for o in objs
                                     if (o.get("hookSpecificOutput") or {}).get("hookEventName")), "PreToolUse")
        if best:
            hso["permissionDecision"] = best
            hso["permissionDecisionReason"] = "\n".join(reasons)
        if ctx:
            hso["additionalContext"] = "\n\n".join(ctx)
    if sysmsg:
        merged["systemMessage"] = " ".join(sysmsg)
    if top_reasons:
        merged["reason"] = "\n".join(top_reasons)
    return (json.dumps(merged, separators=(",", ":")) if merged else ""), "".join(errs), 0


def _run_phase(checks, phase):
    try:
        tool = json.loads(core.read_payload()).get("tool_name", "")
    except Exception as exc:
        # Cannot tell which checks apply: before a tool call that blocks (the guard is among them), after it says so.
        sys.stderr.write("house-rules %s: could not read tool_name from the payload (%s: %s)%s.\n" % (
            phase, type(exc).__name__, exc, "; blocking rather than letting the call through unchecked"
            if phase == "pretool" else "; no checks ran for this call"))
        return 2 if phase == "pretool" else 0
    names = [n for m, n in checks if re.fullmatch(m, tool)]
    out, err, rc = _merge_phase([(n,) + _run_captured(n) for n in names])
    sys.stdout.write(out)
    sys.stderr.write(err)
    return rc


def event_pretool():
    return _run_phase(PRE_CHECKS, "pretool")


def event_posttool():
    return _run_phase(POST_CHECKS, "posttool")


EVENTS = {
    "inject": event_inject,
    "showrule": event_showrule,
    "issuelist": event_issuelist,
    "profile": event_profile,
    "standards": event_standards,
    "docstiers": event_docstiers,
    "diskreport": event_diskreport,
    "versioncheck": event_versioncheck,
    "scope": event_scope,
    "noask": event_noask,
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
    "autosavefinal": event_autosave_final,
    "pickup": event_pickup,
    "commitgate": event_commitgate,
    "worktreesweep": event_worktreesweep,
    "agentcap": event_agentcap,
    "prompttimer": event_prompttimer,
    "promptran": event_promptran,
    "audit": event_audit,
    "rclink": event_rclink,
    "userpromptaudit": event_userpromptaudit,
    "handover": event_handover,
    "roadblocks": event_roadblocks,
    "harvest": event_harvest,
    "pagecheck": event_pagecheck,
    "sendcheck": event_sendcheck,
    "closablemerge": event_closablemerge,
    "pretool": event_pretool,
    "posttool": event_posttool,
}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    handler = EVENTS.get(event)
    if handler is None:
        return 0
    try:
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
        if event in ("guard", "pretool"):
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
