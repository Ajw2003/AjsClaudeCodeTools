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

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse

# The shared writing checker (#247), a sibling file. A missing or broken copy must not take every
# hook down with it, so it is loaded here and each check that needs it reports when it is absent.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import clarity
    CLARITY_ERROR = None
except ImportError as _clarity_exc:
    clarity = None
    CLARITY_ERROR = "house-rules: the writing checker (scripts/clarity.py) could not load (%s)." % _clarity_exc

# The core (#357, step 2a of #340): shared helpers, inject/showrule/profile/standards/versioncheck,
# scope, artifact, runnable, promptran and work_saved_elsewhere now live in house_rules/core.py.
# The star import brings every public name back so the code still here keeps working; the
# underscore names are listed because `import *` skips them. The sys.path line above makes
# `house_rules` importable when run.sh starts this file.
from house_rules import core
from house_rules.core import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _GIT_COMMIT_RE,
    _PROMPT_VALUE_RE,
    _TOGGLE_OFF,
    _ag,
    _common_git_dir,
    _expand_detail_paths,
    _extract_file_path,
    _field,
    _git_dir,
    _is_relayed_prompt,
    _parse_status_porcelain,
    _payload_cwd,
    _plugin_root,
    _plugin_version,
    _read_and_clear_outdated_marker,
    _read_text,
    _time,
    _truncate_with_notice,
    _vc_session_id,
)

# The parts (#358, step 2b of #340): the safe git part and the docs part. Same pattern as the core: the
# star import brings the public names back, the underscore names the code still here uses are listed.
from house_rules import docs, safe_git
from house_rules.docs import *  # noqa: F401,F403
from house_rules.safe_git import *  # noqa: F401,F403
from house_rules.safe_git import (  # noqa: F401
    _GH_PREFIX,
    _PR_BODY_FILE_RE,
    _apply_assigns,
    _attribution_enabled,
    _branch_advice,
    _command_dir,
    _commit_check_enabled,
    _commit_note,
    _decoded_command,
    _effective_author,
    _is_claude_identity,
    _uncommitted_among,
    _waiting_clock,
    _waiting_key,
    _waiting_path,
    _waiting_scope_note,
    _waiting_session_note,
    _waiting_update,
)



# ---------------------------------------------------------------------------------------
# delegate — PostToolUse on ExitPlanMode. No dependencies, one fixed string.
# ---------------------------------------------------------------------------------------

DELEGATE_NOTE = (
    "House rules, execution model: the plan is settled, so the implementation is delegated "
    "work now. Hand it to the @house-rules:builder subagent (Task tool, subagent_type "
    "house-rules:builder), one per issue and never per step; use @house-rules:scout for "
    "read-only lookups, and never more than two subagents at once. The plan is already committed to the repo as a real file (per the "
    "artifact rule); pass that file's path in the delegation prompt so the builder reads the "
    "decided plan instead of re-deriving it from this conversation - the ExitPlanMode payload "
    "itself carries the plan as inline text, not a path, so naming the file is on you, not "
    "something to read off the tool call. That agent is pinned to Sonnet at low effort, which "
    "is the whole point: deliberation is done, and re-deliberating it on the planning model "
    "costs the user for nothing. Its agent description is marked for proactive use, which is "
    "the harness's own documented basis for invoking a subagent without a fresh per-turn ask "
    "from the user - so this delegation is authorized, not merely suggested, even when the "
    "next instruction is as generic as \"implement the plan\". Do not re-plan inside the "
    "delegation - give it the decided steps and the plan file path. A multi-group plan is "
    "one delegation per group: this reminder fires once, but the rule does not expire when "
    "group 1 comes back, and absorbing the rest inline is the failure it exists to prevent. "
    "Skip the delegation only when the plan touches one file AND is three steps or fewer; "
    "that is the whole exception, it is a count and not a judgement call, and taking it means "
    "saying so in one line that names the count. A delegation that touches more than one file, "
    "or changes behavior rather than just reading, passes isolation: \"worktree\" on the Agent "
    "call - two concurrent delegations must never be able to land in the same working directory. "
    "This is a reminder to you; the user was not prompted and does not need to do anything."
)


DELEGATE_PARITY_NOTE = (
    " This plan reads like re-creating existing behaviour and carries no keep/change/drop "
    "inventory of the original. Before delegating, inventory what the original does from its "
    "code, show it to the user, and pass it - or an instruction to read the original first - "
    "in the delegation prompt: a spec written from memory is how a regression gets specified."
)
_PLAN_VALUE_RE = re.compile(r'"plan"\s*:\s*"((?:[^"\\]|\\.)*)"')


def event_delegate():
    try:
        note = DELEGATE_NOTE
        payload = read_payload() or ""
        if _parity_enabled():
            plan = _field(_PLAN_VALUE_RE, payload) or ""
            if _PARITY_RE.search(plan) and not _PARITY_ACCOUNTED_RE.search(plan):
                note = note + DELEGATE_PARITY_NOTE
        note = note + _issues_plan_note(payload)
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": note,
                }
            }
        )
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the delegate reminder hit an error "
                "(%s) and is offline for this call." % type(exc).__name__
            }
        )
    return 0


# announce / verdict - the two subagent-lifecycle handlers. Both fail OPEN and loud, same
# contract as handover (a decision:"block" here would wedge a subagent mid-run).
# Why these exist and how the transcript is probed: docs/architecture.md, "announce and
# verdict handlers fix" / "The transcript is probed, never assumed".

# Same shape as _PROMPT_FIELD_RE / _COMMAND_FIELD_RE: pull one field out of the raw payload
# without trusting the whole thing to parse. Value-capturing, and escape-aware - NOT the
# _FILE_PATH_RE shape, which drops escape handling and is the known-divergent one.
_AGENT_TYPE_RE = re.compile(r'"agent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')
_AGENT_ID_RE = re.compile(r'"agent_id"\s*:\s*"((?:[^"\\]|\\.)*)"')
_EFFORT_RE = re.compile(r'"effort"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SESSION_ID_RE = re.compile(r'"session_id"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TRANSCRIPT_RE = re.compile(r'"transcript_path"\s*:\s*"((?:[^"\\]|\\.)*)"')
_AGENT_TRANSCRIPT_RE = re.compile(r'"agent_transcript_path"\s*:\s*"((?:[^"\\]|\\.)*)"')

# Agent/Task's PostToolUse tool_response uses its own camelCase names - doc-ref 8313 docs/6-decisions/Decisions.md.
_RESPONSE_STATUS_RE = re.compile(r'"status"\s*:\s*"((?:[^"\\]|\\.)*)"')
_RESPONSE_AGENT_ID_RE = re.compile(r'"agentId"\s*:\s*"((?:[^"\\]|\\.)*)"')
_RESPONSE_AGENT_TYPE_RE = re.compile(r'"agentType"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TOOL_INPUT_SUBAGENT_TYPE_RE = re.compile(r'"subagent_type"\s*:\s*"((?:[^"\\]|\\.)*)"')

_TASK_NOTIFICATION_RE = re.compile(r"<task-notification>")
_TASK_ID_RE = re.compile(r"<task-id>([0-9A-Za-z]+)</task-id>")
_TASK_STATUS_RE = re.compile(r"<status>([^<]*)</status>")

# Documented as forcing every subagent onto one model, ignoring frontmatter - the named
# mechanism by which "model: sonnet" is silently not what runs. Worth reporting when set.
_MODEL_OVERRIDE_VARS = ("CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "CLAUDE_CODE_SUBAGENT_MODEL")


def _delegation_enabled():
    """HOUSE_RULES_DELEGATION=off disables both handlers.

    Deliberately NOT HOUSE_RULES_TRACE-gated. The trace lever covers handlers whose output
    merely narrates an otherwise-silent path; here the report IS the feature, and hiding it
    behind the trace lever would make the thing being shipped optional by default.
    """
    return os.environ.get("HOUSE_RULES_DELEGATION", "on").strip().lower() not in _TOGGLE_OFF


# subagentrules — a third subagent-lifecycle handler, its own SubagentStart entry, separate
# from announce. doc-ref c67d docs/6-decisions/Decisions.md
SUBAGENT_SECTION_MARKER = "<!-- subagent -->"
SUBAGENT_CORE_CHAR_LIMIT = 4_500

SUBAGENT_MANDATE = (
    "\nYour final report must list every command you ran and its result verbatim, every file "
    "you wrote or edited, and anything you could not do.\n"
)


# The tier agents (agents/scout.md, builder.md, reviewer.md) carry their own short report formats,
# so they are not also told to list every command verbatim. Every other agent type still is.
TIER_AGENTS = ("scout", "builder", "reviewer")


def _is_tier_agent(agent_type):
    return (agent_type or "").split(":")[-1].strip() in TIER_AGENTS


def _subagent_core(rules_path=None, agent_type=""):
    """The marked sections of house-rules.md, in file order, plus SUBAGENT_MANDATE.

    Returns (text, problems). A section is a "## " heading through the next "## " heading (or
    end of file); it is included only when the line immediately after the heading is
    SUBAGENT_SECTION_MARKER, which is then stripped from the emitted text - the marker is a
    build-time signal, not something the subagent needs to read.
    """
    problems = []
    if rules_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        rules_path = os.path.join(here, "..", "rules", "house-rules.md")
    try:
        body = _read_text(rules_path)
    except OSError as exc:
        problems.append("could not read rules/house-rules.md (%s)" % type(exc).__name__)
        return "", problems

    body = body.replace("\r\n", "\n")
    lines = body.split("\n")
    sections = []
    current = None
    for line in lines:
        if line.startswith("## "):
            current = {"heading": line, "body": []}
            sections.append(current)
        elif current is not None:
            current["body"].append(line)

    kept = []
    for sec in sections:
        body_lines = sec["body"]
        if body_lines and body_lines[0].strip() == SUBAGENT_SECTION_MARKER:
            kept.append(sec["heading"] + "\n" + "\n".join(body_lines[1:]).strip())

    if not kept:
        problems.append("no section in house-rules.md is marked %s" % SUBAGENT_SECTION_MARKER)
        return "", problems

    text = "\n\n".join(kept).strip() + "\n" + SUBAGENT_MANDATE
    # ${CLAUDE_PLUGIN_ROOT} is expanded the same way inject does it: additionalContext is
    # plain text nothing else expands, so a literal placeholder here would be an unopenable
    # path for the subagent, exactly the bug inject fixed for the main session.
    text = _expand_detail_paths(text)
    return _truncate_with_notice(text, SUBAGENT_CORE_CHAR_LIMIT, "the subagent rules core"), problems


def event_subagentrules():
    """SubagentStart: inject the subagent core, and tell the user where its transcript will
    land, before it exists - so it is findable without waiting for verdict to say so."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        core, problems = _subagent_core(agent_type=_field(_AGENT_TYPE_RE, payload))
        loop_note = _loop_helper_note(payload or "")
        if loop_note:
            core = (core + "\n\n" + loop_note) if core else loop_note
        bits = []
        if not payload:
            problems.append("the SubagentStart payload was empty")
        else:
            candidates = _transcript_candidates(payload)
            expected = candidates[-1] if candidates else ""
            if expected:
                bits.append(
                    "house-rules: subagent transcript expected at %s (verdict will report "
                    "the path it actually finds when this agent stops)" % expected
                )
            else:
                problems.append(
                    "not enough of agent_id/transcript_path/session_id in the payload to "
                    "predict the transcript path"
                )
        if problems:
            bits.append("house-rules subagentrules COULD NOT TELL: %s" % "; ".join(problems))
        out = {}
        if bits:
            out["systemMessage"] = " | ".join(bits)
        if core:
            out["hookSpecificOutput"] = {
                "hookEventName": "SubagentStart",
                "additionalContext": core,
            }
        if not out:
            out["systemMessage"] = (
                "house-rules plugin: subagentrules had nothing to report or inject for this "
                "subagent start."
            )
        emit(out)
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the subagent-rules injector hit an "
                "error (%s) and did not run for this call." % type(exc).__name__
            }
        )
    return 0


def _agent_file(agent_type):
    """The shipped definition for this agent, or "" if the plugin does not ship it.

    agent_type arrives plugin-scoped ("house-rules:builder"), so the scope prefix is
    stripped before looking for agents/<name>.md. An agent the plugin does not ship is not
    an error - it is the common case (Explore, Plan, general-purpose) and is reported as
    "no declaration", which is still the useful half of the answer.
    """
    name = (agent_type or "").split(":")[-1].strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return ""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "agents", name + ".md")
    return path if os.path.isfile(path) else ""


def _declared(agent_type, problems=None):
    """(model, effort, fingerprint) declared by the installed agent definition.

    Why this reads the file instead of hardcoding a claim: docs/architecture.md,
    "announce (SubagentStart) reports the declaration".
    """
    path = _agent_file(agent_type)
    if not path:
        return "", "", ""
    body = ""
    try:
        body = _read_text(path)
    except OSError as exc:
        # NOT the same as "the plugin does not ship this agent" - it ships it and we could
        # not read it. Collapsing the two would report a broken install as a normal one.
        if problems is not None:
            problems.append(
                "agents/%s.md is shipped but unreadable (%s), so its declared model is unknown"
                % (os.path.basename(path)[:-3], type(exc).__name__)
            )
        return "", "", ""
    model = ""
    effort = ""
    m = re.search(r"^model:\s*(\S+)\s*$", body, re.MULTILINE)
    if m:
        model = m.group(1)
    m = re.search(r"^effort:\s*(\S+)\s*$", body, re.MULTILINE)
    if m:
        effort = m.group(1)
    digest = ""
    try:
        import hashlib

        digest = hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:8]
    except Exception as exc:
        if problems is not None:
            problems.append("could not fingerprint the digest (%s)" % type(exc).__name__)
    return model, effort, digest


def event_announce():
    """SubagentStart: say which agent is starting, and what it is DECLARED to run on."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: a subagent started but the "
                    "SubagentStart payload was empty, so nothing could be reported about "
                    "which agent, model or digest it is running."
                }
            )
            return 0

        problems = []
        agent_type = _field(_AGENT_TYPE_RE, payload, problems)
        agent_id = _field(_AGENT_ID_RE, payload, problems)
        effort = _field(_EFFORT_RE, payload, problems)
        version = _plugin_version(problems)
        model, decl_effort, digest = _declared(agent_type, problems)
        if agent_id:
            cap_note = _agentcap_update(add=(agent_id, agent_type))
            if cap_note:
                problems.append(cap_note)

        bits = ["house-rules: subagent starting - %s" % (agent_type or "agent type not in payload")]
        if agent_id:
            bits.append("id %s" % agent_id)
        if model or decl_effort:
            bits.append(
                "declared %s"
                % ", ".join(x for x in ("model " + model if model else "", "effort " + decl_effort if decl_effort else "") if x)
            )
        else:
            bits.append("no declaration shipped by this plugin to compare against")
        if effort:
            # The docs do not say whether this is the subagent's effort or the session's.
            # Name the field it came from and claim nothing more.
            bits.append("payload effort field says %s" % effort)
        if version:
            bits.append("house-rules %s" % version)
        if digest:
            bits.append("digest %s" % digest)
        overrides = [v for v in _MODEL_OVERRIDE_VARS if os.environ.get(v, "").strip()]
        if overrides:
            bits.append(
                "WARNING: %s is set, so the declared model may not be what runs"
                % " and ".join(overrides)
            )
        if problems:
            bits.append("COULD NOT TELL: %s" % "; ".join(problems))
        emit({"systemMessage": " | ".join(bits)})
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the subagent-start report hit an error "
                "(%s) and is offline for this call." % type(exc).__name__
            }
        )
    return 0


def _transcript_candidates(payload, agent_id=None):
    """Where the subagent's own transcript might be, most authoritative first.

    Why this probes rather than assumes: docs/architecture.md, "The transcript is probed,
    never assumed, and that is deliberate." agent_id is normally read out of the payload's
    own "agent_id" field (SubagentStart/SubagentStop); callers reading a differently-shaped
    payload (PostToolUse's "agentId", a hand-back prompt's <task-id>) pass it in directly.
    """
    out = []
    direct = _field(_AGENT_TRANSCRIPT_RE, payload)
    if direct:
        out.append(direct)
    if agent_id is None:
        agent_id = _field(_AGENT_ID_RE, payload)
    parent = _field(_TRANSCRIPT_RE, payload)
    session = _field(_SESSION_ID_RE, payload)
    if agent_id and parent:
        base = os.path.dirname(parent)
        stem = os.path.basename(parent)
        if stem.endswith(".jsonl"):
            stem = stem[: -len(".jsonl")]
        leaf = os.path.join("subagents", "agent-%s.jsonl" % agent_id)
        for sess in [s for s in (session, stem) if s]:
            cand = os.path.join(base, sess, leaf)
            if cand not in out:
                out.append(cand)
    return out


_DEFERRAL_PHRASES = (
    "i'll report back",
    "i will report back",
    "i've launched",
    "i have launched",
    "i'll get started",
    "i will get started",
    "i'm about to start",
    "i am about to start",
)


def _observed_models(path):
    """(models, assistant-entry count, total tool_use blocks, last assistant text) from a
    transcript JSONL. The last two feed event_verdict()'s completion-sanity check."""
    models = []
    turns = 0
    tool_calls = 0
    last_text = ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant":
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            turns += 1
            model = msg.get("model")
            if model and model not in models:
                models.append(model)
            content = msg.get("content")
            if isinstance(content, list):
                text_bits = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        tool_calls += 1
                    elif block.get("type") == "text" and isinstance(block.get("text"), str):
                        text_bits.append(block["text"])
                if text_bits:
                    last_text = "\n".join(text_bits)
    return models, turns, tool_calls, last_text


# Caps on the audit summary below: a subagent that ran hundreds of commands must not produce
# a systemMessage so large it becomes unreadable (or gets truncated) itself.
AUDIT_MAX_COMMANDS = 40
AUDIT_COMMAND_CHARS = 160
AUDIT_MAX_FAILED = 8
AUDIT_FAILED_CHARS = 500
AUDIT_MAX_FILES = 15
_AUDIT_COMMAND_TOOLS = ("Bash", "PowerShell")
_AUDIT_WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")


def _audit_summary(path):
    """(command lines, file lines, tool_counts) read straight from a subagent transcript.

    A command line pairs each Bash/PowerShell tool_use with its matching tool_result (by
    tool_use_id), so the reported exit status is what the transcript actually recorded, not
    an inference. Tool uses whose result never arrives (the run was cut short) are reported
    as such rather than silently dropped.
    """
    pending = {}
    commands = []
    files = []
    tool_counts = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            msg = obj.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            if obj.get("type") == "assistant":
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name") or "?"
                    tool_counts[name] = tool_counts.get(name, 0) + 1
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    tid = block.get("id")
                    if name in _AUDIT_COMMAND_TOOLS and tid:
                        cmd = inp.get("command") or inp.get("script") or ""
                        pending[tid] = (name, cmd)
                    elif name in _AUDIT_WRITE_TOOLS:
                        fp = inp.get("file_path") or inp.get("notebook_path") or "(no file_path)"
                        files.append("%s %s" % (name, fp))
            elif obj.get("type") == "user":
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    tid = block.get("tool_use_id")
                    entry = pending.pop(tid, None) if tid else None
                    if entry is None:
                        continue
                    name, cmd = entry
                    status = "ERROR" if block.get("is_error") else "ok"
                    commands.append("%s [%s]: %s" % (name, status, cmd))
    for name, cmd in pending.values():
        commands.append("%s [NO RESULT RECORDED]: %s" % (name, cmd))
    return commands, files, tool_counts


def _capped_lines(lines, max_count, max_chars):
    shown = [
        (l if len(l) <= max_chars else l[: max_chars - 3] + "...") for l in lines[:max_count]
    ]
    if len(lines) > max_count:
        shown.append("...%d more" % (len(lines) - max_count))
    return shown


def _audit_report(found):
    """The multi-line AUDIT block - commands with exit status, files written/edited, tool-use
    counts, then the reconcile instruction - shared by verdict, audit and userpromptaudit, so
    all three read a transcript the same way and say the same thing about it. A transcript that
    cannot be re-read says so instead of raising - this is called from three fail-open handlers
    that must never let an audit failure take the rest of their report down with it.
    """
    try:
        commands, wrote, tool_counts = _audit_summary(found)
    except OSError as exc:
        return "AUDIT COULD NOT TELL: transcript at %s could not be re-read for the audit " \
            "summary (%s)" % (found, type(exc).__name__)
    lines = ["AUDIT (from the transcript, not the subagent's own report):"]
    if tool_counts:
        lines.append(
            "  tool uses: %s" % ", ".join("%s x%d" % (n, c) for n, c in sorted(tool_counts.items()))
        )
    failed = [c for c in commands if not c.split(": ", 1)[0].endswith("[ok]")]
    if failed:
        lines.append(
            "  FAILED commands (%d) - a report that claims success without accounting for these "
            "is unsupported:" % len(failed)
        )
        lines.extend("    cmd: %s" % l for l in _capped_lines(failed, AUDIT_MAX_FAILED, AUDIT_FAILED_CHARS))
    files = list(dict.fromkeys(wrote))
    lines.extend("  wrote: %s" % l for l in _capped_lines(files, AUDIT_MAX_FILES, AUDIT_COMMAND_CHARS))
    if len(commands) > len(failed):
        lines.append("  other commands: %d ok (not listed)" % (len(commands) - len(failed)))
    if wrote and _commit_check_enabled():
        paths = [w.split(" ", 1)[1] for w in wrote if " " in w]
        try:
            left = _uncommitted_among(paths, os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        except Exception as exc:
            lines.append("  uncommitted: could not tell (%s: %s)" % (type(exc).__name__, exc))
        else:
            if left:
                lines.append(
                    "  uncommitted: %s - the subagent wrote these and they are not committed. "
                    "The commit is yours now, whoever wrote them: commit on your own branch, "
                    "scoped to those paths." % ", ".join(_capped_lines(left, 8, AUDIT_COMMAND_CHARS))
                )
    lines.append(
        "Reconcile the subagent's report against this record; flag every claim the record "
        "does not support before relaying."
    )
    return "\n".join(lines)


def _subagent_ledger_enabled():
    """HOUSE_RULES_SUBAGENT_LEDGER=on renders the subagent transcript into docs/sessions/.
    Off by default: it writes a file on every subagent stop, which nobody asked for as the
    default cost of delegating."""
    return os.environ.get("HOUSE_RULES_SUBAGENT_LEDGER", "off").strip().lower() not in _TOGGLE_OFF


def _write_subagent_ledger(transcript_path, payload):
    """Render transcript_path into docs/sessions/ with the shared renderer. Returns a short
    status string for the systemMessage - never raises, since this is an opt-in extra, never
    allowed to take the whole verdict report down with it."""
    try:
        import session_ledger_render as slr

        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            records = []
            bad = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    bad += 1
        session_id = os.path.splitext(os.path.basename(transcript_path))[0]
        turns = slr.build_turns(records)
        body = slr.render(turns, transcript_path, session_id, bad)

        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        outdir = os.path.join(root, "docs", "sessions")
        os.makedirs(outdir, exist_ok=True)
        import datetime

        stamp = datetime.date.today().isoformat()
        dest = os.path.join(outdir, "%s-subagent-%s.md" % (stamp, session_id))
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return "LEDGER: rendered subagent transcript to %s" % dest
    except Exception as exc:
        return "LEDGER COULD NOT TELL: failed to render the subagent transcript (%s: %s)" % (
            type(exc).__name__,
            exc,
        )


def event_verdict():
    """SubagentStop: say which model ACTUALLY served the subagent, from its transcript."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: a subagent finished but the "
                    "SubagentStop payload was empty, so the model it actually ran on could "
                    "not be checked."
                }
            )
            return 0

        problems = []
        raw_type = _field(_AGENT_TYPE_RE, payload, problems)
        agent_type = raw_type or "agent type not in payload"
        declared, _decl_effort, _digest = _declared(raw_type, problems)
        stop_id = _field(_AGENT_ID_RE, payload)
        if stop_id:
            cap_note = _agentcap_update(remove=stop_id)
            if cap_note:
                problems.append(cap_note)

        candidates = _transcript_candidates(payload)
        if not candidates:
            emit(
                {
                    "systemMessage": "house-rules: %s finished, but its transcript could not "
                    "be located - the payload carried no agent_transcript_path and not enough "
                    "of agent_id/transcript_path to reconstruct one, so the model it ran on is "
                    "unverified." % agent_type
                }
            )
            return 0

        found = ""
        models = []
        turns = 0
        tool_calls = 0
        last_text = ""
        unreadable = []
        for cand in candidates:
            if not os.path.isfile(cand):
                continue
            try:
                models, turns, tool_calls, last_text = _observed_models(cand)
            except OSError as exc:
                unreadable.append("%s (%s)" % (cand, type(exc).__name__))
                continue
            found = cand
            break

        if not found:
            detail = "; tried: %s" % ", ".join(candidates)
            if unreadable:
                detail += "; unreadable: %s" % ", ".join(unreadable)
            emit(
                {
                    "systemMessage": "house-rules: %s finished, but no transcript was readable "
                    "at any known location, so the model it ran on is unverified%s"
                    % (agent_type, detail)
                }
            )
            return 0

        if not models:
            emit(
                {
                    "systemMessage": "house-rules: %s finished; its transcript at %s had no "
                    "assistant entry carrying a model field (%d assistant entr%s seen), so "
                    "the model it ran on is unverified." % (agent_type, found, turns, "y" if turns == 1 else "ies")
                }
            )
            return 0

        observed = ", ".join(models)
        bits = [
            "house-rules: %s finished" % agent_type,
            "transcript found at %s" % found,
            "observed model %s" % observed,
            "%d assistant turn%s" % (turns, "" if turns == 1 else "s"),
        ]
        if declared:
            # "sonnet" against "claude-sonnet-4-5-20250929", or a full model id against
            # itself. Every observed model must match, so a subagent that started on the
            # declared model and fell back mid-run still reads as a mismatch.
            low = declared.lower()
            if models and all(low in m.lower() for m in models):
                bits.append("declared %s - MATCH" % declared)
            else:
                bits.append(
                    "declared %s - MISMATCH, the delegation did not run on what it declares"
                    % declared
                )
        else:
            bits.append("no declared model shipped for this agent, so nothing to compare")
        if turns and tool_calls == 0:
            bits.append(
                "SUSPICIOUS COMPLETION: 0 tool calls across %d assistant turn%s - this may "
                "be a status update, not finished work; verify concrete deliverables before "
                "trusting it" % (turns, "" if turns == 1 else "s")
            )
        else:
            low_text = last_text.lower()
            hit = next((p for p in _DEFERRAL_PHRASES if p in low_text), "")
            if hit:
                bits.append(
                    "SUSPICIOUS COMPLETION: last message matches deferral phrase %r - this "
                    "may be a status update, not finished work; verify concrete deliverables "
                    "before trusting it" % hit
                )
        # The audit summary: built from the transcript itself, not from anything the
        # subagent said about itself. Delivered here on systemMessage because that is the
        # one channel probed to reach the USER for a SubagentStop (neither additionalContext
        # nor systemMessage reaches the PARENT MODEL's context in-turn at SubagentStop -
        # doc-ref 8313 docs/6-decisions/Decisions.md). audit/userpromptaudit cover reaching the model
        # itself, on the channels that were probed to actually do that.
        bits.append(_audit_report(found))

        if _subagent_ledger_enabled():
            ledger_note = _write_subagent_ledger(found, payload)
            if ledger_note:
                bits.append(ledger_note)

        if problems:
            bits.append("COULD NOT TELL: %s" % "; ".join(problems))
        emit({"systemMessage": " | ".join(bits)})
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the subagent-stop model check hit an "
                "error (%s) and is offline for this call." % type(exc).__name__
            }
        )
    return 0


# agentcap — PreToolUse on Agent|Task. Counts running subagents so the spawn count stays under
# control (issue #112). The list is kept by announce (SubagentStart adds) and verdict
# (SubagentStop removes); this handler only reads it. The state file lives in the COMMON repo
# directory because subagents run in their own worktrees, whose per-worktree directory is not
# shared. A record older than AGENT_STALE_SECONDS is ignored: a stopped session or an outage
# means SubagentStop never fires (2026-09-29). Fails open, loud.
AGENT_CAP = 2
AGENT_STALE_SECONDS = 45 * 60
AGENT_STATE_FILE = "house-rules-agents.json"


def _agentcap_enabled():
    return os.environ.get("HOUSE_RULES_AGENTS", "on").strip().lower() not in _TOGGLE_OFF


def _agentcap_path():
    # HOUSE_RULES_AGENTS_STATE points the state file elsewhere: verify.py and measure_footprint.py
    # use it so their simulated spawns never leave records in the real repository.
    override = os.environ.get("HOUSE_RULES_AGENTS_STATE", "").strip()
    if override:
        return override
    cd = _common_git_dir(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return os.path.join(cd, AGENT_STATE_FILE) if cd else None


def _agentcap_load(path):
    """The records, or ValueError when the file exists but is not the expected shape."""
    if not os.path.isfile(path):
        return []
    data = json.loads(_read_text(path))
    recs = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(recs, list) or not all(
        isinstance(r, dict) and isinstance(r.get("start"), (int, float)) for r in recs
    ):
        raise ValueError("unexpected shape")
    return recs


def _agentcap_live(recs, now=None):
    now = time.time() if now is None else now
    return [r for r in recs if now - r["start"] <= AGENT_STALE_SECONDS]


def _agentcap_save(path, recs):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"agents": recs}, f)
    os.replace(tmp, path)


def _agentcap_update(add=None, remove=None):
    """Add or remove one record. Returns "" or a one-line problem (never raises)."""
    if not _agentcap_enabled():
        return ""
    note = ""
    try:
        path = _agentcap_path()
        if not path:
            return "agent cap: not inside a repository, so running subagents are not tracked"
        try:
            recs = _agentcap_load(path)
        except (ValueError, OSError) as exc:
            recs = []
            note = "agent cap: state file %s was unreadable (%s) and was reset" % (path, type(exc).__name__)
        recs = _agentcap_live(recs)
        if remove:
            recs = [r for r in recs if r.get("id") != remove]
        if add:
            recs = [r for r in recs if r.get("id") != add[0]]
            recs.append({"id": add[0], "type": add[1], "start": time.time()})
        _agentcap_save(path, recs)
    except Exception as exc:
        return "agent cap: could not update the running-subagent list (%s: %s)" % (type(exc).__name__, exc)
    return note


def event_agentcap():
    try:
        if not _agentcap_enabled():
            return 0
        payload = read_payload()
        caller = ""
        try:
            data = json.loads(payload) if payload else {}
            caller = (data.get("agent_id") or "") if isinstance(data, dict) else ""
        except ValueError as exc:
            emit({"systemMessage": "house-rules: agent cap could not parse the call payload (%s); "
                  "the spawn is allowed, the cap is not enforced this time." % type(exc).__name__})
            return 0
        if caller:
            reason = (
                "house-rules: a subagent may not start another subagent (agent %s tried). "
                "Report back to the parent and let it decide. HOUSE_RULES_AGENTS=off disables "
                "this check." % caller
            )
        else:
            path = _agentcap_path()
            try:
                recs = _agentcap_live(_agentcap_load(path)) if path else []
            except (ValueError, OSError) as exc:
                emit({"systemMessage": "house-rules: agent cap could not read %s (%s); the spawn is "
                      "allowed, the cap is not enforced this time." % (path, type(exc).__name__)})
                return 0
            if len(recs) < AGENT_CAP:
                return 0
            names = ", ".join("%s %s" % (r.get("type") or "agent", r.get("id") or "?") for r in recs)
            reason = (
                "house-rules: %d subagents are already running (%s). Wait for one to finish "
                "before spawning another; the cap is %d. A record older than %d minutes is "
                "ignored. HOUSE_RULES_AGENTS=off disables this check."
                % (len(recs), names, AGENT_CAP, AGENT_STALE_SECONDS // 60)
            )
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the agent cap hit an error (%s: %s) and did not "
              "run for this call; the spawn is allowed." % (type(exc).__name__, exc)})
    return 0


# subagentcommit — SubagentStop, its own hooks.json entry so verdict's report never depends on
# it. The one handler that returns decision "block" on purpose: probed on CLI 2.1.284, a block
# sends the subagent back to work with the reason as its instruction, and the retry's payload
# carries stop_hook_active: true, which is what stops it looping.

SUBAGENT_COMMIT_REASON = (
    "House rules, commit on your own branch: before you finish, commit the files you wrote "
    "that git still shows uncommitted - {files}. {advice} If whoever delegated this told you "
    "not to run git, do not; say in your final report exactly which files are uncommitted "
    "instead. Then finish."
)


def _repo_top(path, cache):
    """The git top level holding `path`, or None when it is not in a repo. Walks up to the
    nearest directory that exists, since a written file may since have been moved."""
    import subprocess

    d = os.path.dirname(os.path.abspath(path))
    while d and not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    if d in cache:
        return cache[d]
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=d, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=COMMIT_CHECK_TIMEOUT,
    )
    top = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else None
    cache[d] = top
    return top


def _repo_branch(top):
    import subprocess

    proc = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=top, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=COMMIT_CHECK_TIMEOUT,
    )
    return proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else None


def _uncommitted_by_repo(paths):
    """[(repo top, branch or None, [uncommitted repo-relative paths])], one entry per repo that
    has any. Each file is judged in its OWN repo, so a subagent working in an isolated worktree
    is checked against that worktree, not the session's project directory."""
    cache = {}
    by_top = {}
    for p in paths:
        top = _repo_top(p, cache)
        if top:
            by_top.setdefault(top, []).append(p)
    out = []
    for top, ps in sorted(by_top.items()):
        left = _uncommitted_among(ps, top)
        if left:
            out.append((top, _repo_branch(top), left))
    return out


def event_subagentcommit():
    try:
        if not _commit_check_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: the subagent commit check got an "
                    "empty SubagentStop payload and did not run for this call."
                }
            )
            return 0
        agent_type = _field(_AGENT_TYPE_RE, payload) or "a subagent"
        found = next((c for c in _transcript_candidates(payload) if os.path.isfile(c)), "")
        if not found:
            emit(
                {
                    "systemMessage": "house-rules: commit check could not tell whether %s "
                    "left files uncommitted - no readable transcript." % agent_type
                }
            )
            return 0
        _commands, wrote, _counts = _audit_summary(found)
        paths = [w.split(" ", 1)[1] for w in wrote if " " in w]
        if not paths:
            return 0
        left = _uncommitted_by_repo(paths)
        if not left:
            cache, notes = {}, []
            for top in sorted(set(filter(None, (_repo_top(p, cache) for p in paths)))):
                note = _autosave_cleanup(top)
                if note:
                    notes.append(note)
            if notes:
                emit({"systemMessage": " | ".join(notes)})
            else:
                trace("subagentcommit: %s committed everything it wrote." % agent_type)
            return 0
        shown = "; ".join(
            "%s in %s" % (", ".join(files[:8]) + (" and %d more" % (len(files) - 8) if len(files) > 8 else ""), top)
            for top, _branch, files in left
        )
        if re.search(r'"stop_hook_active"\s*:\s*true', payload):
            # The retry. Blocking again could loop. On the subagent's own worktree branch the hook
            # commits the leftovers itself; anywhere else it only names them.
            sid = _field(re.compile(r'"session_id"\s*:\s*"([^"]*)"'), payload) or ""
            parts = []
            for top, branch, files in left:
                if _autosave_enabled() and branch and branch.startswith(AUTOSAVE_BRANCH_PREFIX):
                    sha, done = _wip_commit(top, WIP_NOT_COMMITTED, sid)
                    note = _autosave_snapshot(top, branch, force_push=True)
                    parts.append("committed %d file(s) in %s as %s%s"
                                 % (len(done), top, sha, " | " + note if note else ""))
                else:
                    parts.append("%s in %s left uncommitted" % (", ".join(files[:8]), top))
            emit(
                {
                    "systemMessage": "house-rules: %s finished with files still uncommitted "
                    "after being asked once: %s. %s." % (agent_type, shown, "; ".join(parts))
                }
            )
            return 0
        advice = " ".join(
            _branch_advice(bool(branch and branch.startswith(owned_branch_prefixes())), branch,
                           "HEAD is detached in %s" % top)
            for top, branch, _files in left
        )
        emit({"decision": "block", "reason": SUBAGENT_COMMIT_REASON.format(files=shown, advice=advice)})
    except Exception as exc:
        # Fails open: a crash here must never hold a subagent back.
        emit(
            {
                "systemMessage": "house-rules plugin: the subagent commit check hit an error "
                "(%s: %s) and did not run for this call." % (type(exc).__name__, exc)
            }
        )
    return 0


# autosave (PostToolUse), commitgate (PreToolUse), worktreesweep (UserPromptSubmit) - subagent
# worktree branches only. subagentcommit above runs only at SubagentStop, which never fires for a
# subagent killed mid-run (the 2026-09-29 safety-classifier outage). See docs/6-decisions/
# Decisions.md, 2026-09-30. Related future direction: issue #105 (dynamic dispatch).

AUTOSAVE_REF_PREFIX = "refs/house-rules/autosave/"
COMMITGATE_THRESHOLD = 3
COMMITGATE_LIST_MAX = 8
CHECKPOINT_MINUTES = 10
AUTOSAVE_PUSH_INTERVAL = 60
AUTOSAVE_PUSH_TIMEOUT = 6.0
SWEEP_MAX_WORKTREES = 10
WIP_NOT_COMMITTED = "wip: autosave - subagent did not commit when asked"
WIP_CHECKPOINT = "wip: checkpoint - %d min without a commit" % CHECKPOINT_MINUTES
WIP_PARENT = "wip: parent checkpoint of subagent work"
_AUTOSAVE_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash"}
_GATED_TOOLS = {"Write", "Edit", "NotebookEdit"}


def _autosave_enabled():
    return os.environ.get("HOUSE_RULES_AUTOSAVE", "on").strip().lower() not in _TOGGLE_OFF


def _autosave_target(payload):
    """(repo top, branch, tool_name, session_id) when the edited file (or, for Bash, the payload
    cwd) is in a repo on a worktree-agent- branch; None otherwise - not a subagent worktree."""
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise RuntimeError("the payload was not a JSON object")
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    path = ti.get("file_path") or ti.get("notebook_path") or data.get("cwd")
    if not path:
        return None
    if not os.path.isabs(path) and data.get("cwd"):
        path = os.path.join(data["cwd"], path)
    # Fast path: .git/HEAD is a file read, so a branch that is not a subagent worktree branch
    # is ruled out with zero git subprocesses. An unreadable HEAD raises (loud, as before).
    start = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    git_dir = _git_dir(start)
    if not git_dir:
        return None
    head = _read_text(os.path.join(git_dir, "HEAD")).strip()
    if not head.startswith("ref: refs/heads/" + AUTOSAVE_BRANCH_PREFIX):
        return None
    top = _repo_top(os.path.join(path, "x") if os.path.isdir(path) else path, {})
    if not top:
        return None
    branch = _repo_branch(top)
    if not branch or not branch.startswith(AUTOSAVE_BRANCH_PREFIX):
        return None
    return top, branch, tool, data.get("session_id") or ""


def _autosave_state_path(top, branch, kind):
    gitdir = _ag(top, ["rev-parse", "--absolute-git-dir"])[1].strip()
    return os.path.join(gitdir, "house-rules-autosave-%s.%s" % (branch.replace("/", "_"), kind))


def _autosave_read(path):
    """A state file's contents, or "" when it does not exist yet (its normal first state)."""
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _autosave_write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _dirty_files(top):
    return [p for p, _t in _parse_status_porcelain(_ag(top, ["status", "--porcelain", "-uall"])[1].splitlines())]


def _shown(files):
    text = ", ".join(files[:COMMITGATE_LIST_MAX])
    if len(files) > COMMITGATE_LIST_MAX:
        text += " and %d more" % (len(files) - COMMITGATE_LIST_MAX)
    return text


def _autosave_push(top, branch, sha, now, force=False):
    """Push the autosave ref to origin, at most once per AUTOSAVE_PUSH_INTERVAL unless `force`.
    Returns a systemMessage string, or None."""
    ref = AUTOSAVE_REF_PREFIX + branch
    stamp = _autosave_state_path(top, branch, "pushed")
    prev = _autosave_read(stamp).split()
    if len(prev) == 2 and prev[1] == sha:
        return None  # this exact snapshot is already on origin
    if not force and len(prev) == 2 and now - float(prev[0]) < AUTOSAVE_PUSH_INTERVAL:
        return None  # saved locally; the next edit after the window pushes the latest
    if _ag(top, ["remote", "get-url", "origin"], check=False)[0] != 0:
        marker = _autosave_state_path(top, branch, "noorigin")
        if _autosave_read(marker):
            return None
        _autosave_write(marker, "1")
        return ("house-rules autosave: this repo has no `origin` remote, so %s is local-only and "
                "would be lost with the container. (Said once.)" % ref)
    # Stamped before the attempt, so an unreachable origin costs one timeout a minute, not one
    # per edit.
    _autosave_write(stamp, "%s %s" % (now, prev[1] if len(prev) == 2 else "-"))
    try:
        _ag(top, ["push", "--force", "--quiet", "origin", "%s:%s" % (ref, ref)], timeout=AUTOSAVE_PUSH_TIMEOUT)
    except RuntimeError as exc:
        return "house-rules autosave: could not push %s to origin (%s). It is saved locally only." % (ref, exc)
    _autosave_write(stamp, "%s %s" % (now, sha))
    return None


def _autosave_snapshot(top, branch, force_push=False):
    """Snapshot the worktree, untracked files included, to the autosave ref without touching
    the real index, branch or working tree, then push it. Returns a systemMessage or None."""
    import time as _t

    ref = AUTOSAVE_REF_PREFIX + branch
    now = _t.time()
    idx = _autosave_state_path(top, branch, "index")
    env = {"GIT_INDEX_FILE": idx}
    try:
        if os.path.exists(idx):
            os.remove(idx)
        _ag(top, ["read-tree", "HEAD"], env=env)
        _ag(top, ["add", "-A"], env=env)
        tree = _ag(top, ["write-tree"], env=env)[1].strip()
    finally:
        if os.path.exists(idx):
            os.remove(idx)
    rc, cur, _e = _ag(top, ["rev-parse", "--verify", "-q", ref], check=False)
    cur = cur.strip() if rc == 0 else ""
    head = _ag(top, ["rev-parse", "HEAD"])[1].strip()
    cur_parent = _ag(top, ["rev-parse", "%s^" % cur], check=False)[1].strip() if cur else ""
    cur_tree = _ag(top, ["rev-parse", "%s^{tree}" % cur])[1].strip() if cur else ""
    if cur and tree == cur_tree and cur_parent == head:
        sha = cur
    else:
        stamp = _t.strftime("%Y-%m-%d %H:%M:%SZ", _t.gmtime(now))
        sha = _ag(top, ["-c", "user.name=house-rules", "-c", "user.email=house-rules@localhost",
                        "commit-tree", tree, "-p", "HEAD", "-m",
                        "house-rules autosave: %s %s" % (branch, stamp)])[1].strip()
        _ag(top, ["update-ref", ref, sha])
    return _autosave_push(top, branch, sha, now, force=force_push)


def _wip_message(subject, session_id=""):
    msg = subject + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    if re.match(r"^session_[A-Za-z0-9]+$", session_id or ""):
        msg += "\nClaude-Session: https://claude.ai/code/%s" % session_id
    return msg


def _wip_commit(top, subject, session_id=""):
    """Commit everything in the worktree on the subagent's behalf. (short sha, files), or
    (None, []) when there was nothing to commit. --no-verify: a repo's pre-commit hook must not
    be able to block the one commit that protects the work."""
    files = _dirty_files(top)
    if not files:
        return None, []
    _ag(top, ["add", "-A"])
    ident = []
    if _ag(top, ["config", "user.name"], check=False)[0] != 0:
        ident += ["-c", "user.name=house-rules"]
    if _ag(top, ["config", "user.email"], check=False)[0] != 0:
        ident += ["-c", "user.email=house-rules@localhost"]
    _ag(top, ident + ["commit", "--no-verify", "-q", "-m", _wip_message(subject, session_id)])
    return _ag(top, ["rev-parse", "--short", "HEAD"])[1].strip(), files


def _head_age_seconds(top):
    import time as _t

    return _t.time() - int(_ag(top, ["log", "-1", "--format=%ct"])[1].strip() or "0")


# ---------------------------------------------------------------------------------------
# Issue workflow (2.49.0): plans over three steps become issues, source edits wait for them,
# PRs link with Refs and never close, and an issue closes only on recorded evidence (#361). The hooks FORCE Claude
# to do these things; none of them runs `gh issue create` or `gh issue close` itself. No new
# hook process on Write/Edit/Bash: delegate writes the state, the Bash PostToolUse entry that
# autosave uses records creations, commitgate gates, handover nags, guard checks the gh commands.
# Plan: docs/plans/issue-workflow-build-plan.md. HOUSE_RULES_ISSUES=off disables all of it.
# ---------------------------------------------------------------------------------------

ISSUES_FILE = "house-rules-issues.json"
ISSUES_LABEL = "AjsAgent created this"
ISSUES_LABEL_OLD = "Claude created this"  # still counts: plans already in flight
ISSUES_STEP_THRESHOLD = 3
ISSUES_NEEDED = 2  # one parent plus at least one child

ISSUE_NOTE = (
    " Issue workflow: this plan has {n} steps, which is more than three, so before any code is "
    "written create one parent issue for the plan and one child issue per step with `gh issue "
    "create`. Each child says `Part of #<parent>` in its body. Titles are plain language a "
    "non-programmer can follow. Every issue carries at least one category label and the label "
    "`AjsAgent created this`; if the repo lacks that label, create it first with `gh label "
    "create`. Show the user the issue numbers. Mark a step `in progress` (`gh api repos/<owner>/<repo>/issues/N/labels "
    "-f \"labels[]=in progress\"`; the `gh issue edit` form fails in cloud sessions) when work on it starts and remove it when the issue closes. "
    "Until a parent and at least one child exist, a hook blocks edits to source files "
    "(docs/, .md files and .claude/ stay open). Do not close any issue yourself: closing always "
    "asks the user."
)


def _issues_enabled():
    return os.environ.get("HOUSE_RULES_ISSUES", "on").strip().lower() not in _TOGGLE_OFF


def _issues_locate(start):
    """(checkout top, resolved git directory) for `start`, or (None, None) outside a repo."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d, _git_dir(d)
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


def _issues_read(git_dir):
    """(state dict or None, problem or None). A missing file is the normal no-gate state; an
    unreadable or corrupt one is reported and treated as no gate (fail open, loud)."""
    path = os.path.join(git_dir, ISSUES_FILE)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as exc:
        return None, ("house-rules: could not read %s (%s), so the issue gate is off for this call."
                      % (ISSUES_FILE, exc))
    return data, None


def _issues_write(git_dir, state):
    with open(os.path.join(git_dir, ISSUES_FILE), "w", encoding="utf-8") as f:
        json.dump(state, f)


def _labelled_count(state):
    return sum(1 for c in state.get("created", []) if isinstance(c, dict) and c.get("labelled"))


_STEP_LINE_RES = (
    re.compile(r"^\s*\d+[.)]\s", re.MULTILINE),
    re.compile(r"^\s*[-*]\s+\[ \]", re.MULTILINE),
    re.compile(r"^#{3,}\s+(?:Step|Change)", re.MULTILINE | re.IGNORECASE),
)


def _plan_step_count(plan):
    return sum(len(r.findall(plan)) for r in _STEP_LINE_RES)


def _issues_plan_note(payload):
    """Delegate's issue half: count the plan's steps, write the gate state when it is over the
    threshold, and return the text to append to the delegate note (always at least one sentence)."""
    if not _issues_enabled():
        return ""
    raw = _field(_PLAN_VALUE_RE, payload or "")
    if raw is None:
        return " Issue workflow: could not read the plan text from the payload, so the issue gate is off for this plan."
    try:
        plan = json.loads('"%s"' % raw)
    except ValueError:
        plan = raw
    n = _plan_step_count(plan)
    if n <= ISSUES_STEP_THRESHOLD:
        return " Issue workflow: this plan counts %d step(s), 3 or fewer, so no issues are required." % n
    top, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return (" Issue workflow: this plan counts %d steps but the directory is not in a git repo, "
                "so no gate was set." % n)
    import datetime
    state = {"plan_steps": n, "approved_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "needs_issues": True, "created": []}
    try:
        _issues_write(git_dir, state)
    except OSError as exc:
        return (" Issue workflow: this plan counts %d steps but the gate state could not be written "
                "(%s), so edits are not blocked. Create the issues anyway." % (n, exc)) + ISSUE_NOTE.format(n=n)
    # #276: no label setup here. This runs on a tool call, and tool calls never reach the network;
    # the labels are created when aj's "Design approved" arrives, before any issue is made.
    return ISSUE_NOTE.format(n=n)


_ISSUE_EDIT_ALLOWED_TOPS = ("docs", ".claude")


def _gated_edit(payload, who):
    """(git_dir or None, problem or None) for a Write/Edit/NotebookEdit of a source file inside a
    repo. None for anything the edit blocks never cover: another tool, a path outside the
    project, docs/, .claude/, any .md file. `who` names the block in the problem message."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None, "house-rules: the %s could not parse the hook payload, so it is off for this call." % who
    if not isinstance(data, dict) or data.get("tool_name") not in _GATED_TOOLS:
        return None, None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp:
        return None, None
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None, None
    if not _is_source_path(fp, cwd, top):
        return None, None
    return git_dir, None


def _is_source_path(fp, cwd, top):
    """The commitgate test: is `fp` a source file of the checkout at `top`? False for a path
    outside it, docs/, .claude/, any .md file and the tracker files."""
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(fp)), os.path.normcase(top))
    except ValueError:
        rel = ".."  # another drive: outside the project
    parts = rel.replace("\\", "/").split("/")
    return not (parts[0] == ".." or parts[0] in _ISSUE_EDIT_ALLOWED_TOPS or rel.lower().endswith(".md")
                or os.path.basename(rel) in (ISSUES_FILE, LOOP_FILE))


_SHELL_TOOLS = ("Bash", "PowerShell")
_HEREDOC_RE = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)
_QUOTED_RE = re.compile(r"(>>?[ \t]*)?(\"[^\"\n]*\"|'[^'\n]*')")
_REDIRECT_RE = re.compile(r"(?<![<>&|])(?:\d|&)?>>?(?![&(>])[ \t]*(\"[^\"\n]+\"|'[^'\n]+'|[^\s;&|<>()\"']+)")
_PY_OPEN_RE = re.compile(r"\bopen\(\s*([^,()]+?)\s*,\s*(?:mode\s*=\s*)?['\"][wax]")
_PY_WRITE_TEXT_RE = re.compile(r"\.write_text\(")
_PY_WRITE_TEXT_LIT_RE = re.compile(r"Path\(\s*(['\"])([^'\"]+)\1\s*\)\s*\.write_text\(")
_NODE_WRITE_RE = re.compile(r"\bwriteFileSync\(")
_NODE_WRITE_LIT_RE = re.compile(r"\bwriteFileSync\(\s*(['\"])([^'\"]+)\1")
_SCRIPT_RUNNER_RE = re.compile(r"(?:^|[\s;&|(/])(?:python3?|py|node)(?:\.exe)?(?=\s|$)")
_LITERAL_RE = re.compile(r"^(['\"])(.+)\1$")


def _script_write_targets(cmd):
    """(targets, unreadable): file paths a shell command writes through a python/node script
    (open w/a, write_text, writeFileSync), sed -i / perl -pi, tee, or a > / >> redirect, and
    whether some write's path could not be read from the command text (#262)."""
    import shlex
    targets, unreadable = [], False
    body = _HEREDOC_RE.sub("", cmd)
    if _SCRIPT_RUNNER_RE.search(cmd):
        for m in _PY_OPEN_RE.finditer(cmd):
            lit = _LITERAL_RE.match(m.group(1))
            if lit and "$" not in lit.group(2):
                targets.append(lit.group(2))
            else:
                unreadable = True
        lits = _PY_WRITE_TEXT_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_PY_WRITE_TEXT_RE.findall(cmd)) > len(lits):
            unreadable = True
        lits = _NODE_WRITE_LIT_RE.findall(cmd)
        targets += [p for _, p in lits]
        if len(_NODE_WRITE_RE.findall(cmd)) > len(lits):
            unreadable = True
    for stmt in re.split(r"&&|\|\||;|\n|\|", body):
        try:
            words = shlex.split(stmt)
        except ValueError:
            sys.stderr.write("house-rules design-loop lock: could not split a statement (unbalanced quotes) "
                             "to look for sed -i / tee; skipping that statement.\n")
            continue
        for i, w in enumerate(words):
            if w not in ("sed", "perl", "tee"):
                continue
            if any(p not in ("sudo", "env", "time", "nohup") and "=" not in p for p in words[:i]):
                continue  # not in command position (e.g. `echo sed -i`, `grep tee f`)
            rest = words[i + 1:]
            files, has_script, skip = [], False, False
            in_place = w == "tee"
            for a in rest:
                if skip:
                    skip = False
                elif a in ("-e", "-f", "--expression", "--file"):
                    has_script, skip = True, True
                elif re.match(r"^-[A-Za-z]+$", a) and a.endswith("e") and not re.match(r"^-[A-Za-z]*i", a):
                    has_script, skip = True, True  # -ne / -pe: the next word is the script
                elif a.startswith("-"):
                    if a == "--in-place" or a.startswith("--in-place=") or re.match(r"^-[A-Za-z]*i", a):
                        in_place = True
                else:
                    files.append(a)
            if not in_place:
                continue
            if w == "sed" and not has_script and files:
                files = files[1:]
            if not files:
                unreadable = True
            for f in files:
                if re.search(r"[$`~*?]", f):
                    unreadable = True
                else:
                    targets.append(f)
            break
    plain = _QUOTED_RE.sub(lambda m: m.group(0) if m.group(1) else " ", body)
    for m in _REDIRECT_RE.finditer(plain):
        t = m.group(1).strip("'\"")
        if t.startswith("/dev/"):
            continue
        if re.search(r"[$`~*?]", t):
            unreadable = True
        else:
            targets.append(t)
    return targets, unreadable


def _gated_script_write(payload):
    """(git_dir, problem, paths, unreadable) for a Bash/PowerShell command that writes a source
    file through a script, sed -i, tee or a redirect. git_dir None when nothing is gated."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None, "house-rules: the design-loop lock could not parse the hook payload, so it is off for this call.", [], False
    if not isinstance(data, dict) or data.get("tool_name") not in _SHELL_TOOLS:
        return None, None, [], False
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    cmd = ti.get("command")
    if not isinstance(cmd, str) or not cmd:
        return None, None, [], False
    cmd = _apply_assigns(cmd)
    targets, unreadable = _script_write_targets(cmd)
    if not targets and not unreadable:
        return None, None, [], False
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None, None, [], False
    src = [t for t in targets if _is_source_path(t, cwd, top)]
    if not src and not unreadable:
        return None, None, [], False
    return git_dir, None, src, unreadable


def _issues_gate(payload):
    """(deny reason or None, problem or None) for a Write/Edit/NotebookEdit payload."""
    git_dir, problem = _gated_edit(payload, "issue gate")
    if not git_dir:
        return None, problem
    state, problem = _issues_read(git_dir)
    if problem:
        return None, problem
    if not state or not state.get("needs_issues"):
        return None, None
    have = _labelled_count(state)
    return (
        "House rules, plans become issues: the approved plan has %s steps, so source edits are "
        "blocked until its issues exist. Two pieces are missing: (1) a parent issue for the plan, "
        "(2) at least one child issue per step saying `Part of #<parent>`, each carrying the label "
        "`%s` (%d of %d recorded). Create them with `gh issue create --label \"%s\"`, show the user "
        "the numbers, then repeat this edit. docs/, .md files and .claude/ are editable meanwhile. "
        "To switch this off: HOUSE_RULES_ISSUES=off." % (state.get("plan_steps", "more than 3"),
                                                          ISSUES_LABEL, have, ISSUES_NEEDED, ISSUES_LABEL),
        None,
    )


# ---------------------------------------------------------------------------------------
# The design loop (#223, #225): each project has a stage - design, plan, build, done - kept in
# LOOP_FILE in .claude/ of the main checkout and carried across sessions. Only aj's own message moves it
# (scope reads it before the model does), and code edits are refused outside build. "I review"
# happens inside build, because fixing what the review finds is code. Design:
# docs/plans/loop-design.html. HOUSE_RULES_LOOP=off disables it.
# ---------------------------------------------------------------------------------------

LOOP_FILE = "house-rules-loop.json"
LOOP_STAGE_NAMES = {"design": "Design", "plan": "Plan", "build": "Build", "qa": "QA", "done": "Done"}
_LOOP_DESIGN_RE = re.compile(r"\bdesign\s+approved\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)
_LOOP_PLAN_RE = re.compile(r"\bbuild\s+plan\s+approved\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)
_LOOP_QA_RE = re.compile(r"\bqa\s+(passed|failed)\s*:?[ \t]*(\S[^\n]*)", re.IGNORECASE)
_LOOP_SKIP_RE = re.compile(r"\bskip\s+design\b", re.IGNORECASE)
_LOOP_BARE_RE = re.compile(r"\b(approved|qa\s+passed|qa\s+failed)\b", re.IGNORECASE)


def _loop_enabled():
    return os.environ.get("HOUSE_RULES_LOOP", "on").strip().lower() not in _TOGGLE_OFF


def _loop_dir(git_dir):
    """#262: where the stage file lives - the COMMON git directory (what `git rev-parse
    --git-common-dir` prints, read from the worktree's `commondir` file so no git process is
    spawned on every edit), so every worktree of a repo shares one stage. A git directory with no
    readable commondir is its own common directory (a plain checkout, or git unreadable)."""
    cd = os.path.join(git_dir, "commondir")
    if os.path.isfile(cd):
        rel = _read_text(cd).strip()
        if rel:
            return os.path.abspath(rel if os.path.isabs(rel) else os.path.join(git_dir, rel))
    return git_dir


def _loop_path(git_dir):
    """#265: the stage file lives in .claude/ of the MAIN checkout (the parent of the common git
    directory), so it is committed with the branch and a fresh clone keeps the stage."""
    return os.path.join(os.path.dirname(_loop_dir(git_dir)), ".claude", LOOP_FILE)


def _loop_read(git_dir):
    """(state, problem). No file means a project that has not started a feature: Design. The old
    place, LOOP_FILE in the git directory, is read until the next write moves it."""
    fresh = {"feature": "", "stage": "design", "skip": False, "approvals": []}
    path = _loop_path(git_dir)
    if not os.path.isfile(path):
        path = os.path.join(_loop_dir(git_dir), LOOP_FILE)
    if not os.path.isfile(path):
        return fresh, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("stage") not in LOOP_STAGE_NAMES:
            raise ValueError("no valid stage")
    except (OSError, ValueError) as exc:
        return None, ("house-rules: could not read %s (%s), so the design-loop lock is off for this call."
                      % (LOOP_FILE, exc))
    return dict(fresh, **data), None


def _loop_write(git_dir, state):
    path = _loop_path(git_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _loop_file_refusal(payload):
    """Deny reason when a Write/Edit/NotebookEdit or a shell redirect/script names the stage file:
    only aj's approval messages move the stage. None otherwise."""
    data = json.loads(payload)  # _loop_gate calls this only after _gated_edit parsed the same payload
    if not isinstance(data, dict):
        return None
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if data.get("tool_name") in _GATED_TOOLS:
        paths = [ti.get("file_path") or ti.get("notebook_path")]
    elif data.get("tool_name") in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        paths = _script_write_targets(_apply_assigns(ti["command"]))[0]
    else:
        return None
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top, git_dir = _issues_locate(cwd)
    if not git_dir:
        return None
    want = os.path.normcase(os.path.abspath(_loop_path(git_dir)))
    for p in paths:
        if isinstance(p, str) and p:
            p = p if os.path.isabs(p) else os.path.join(cwd, p)
            if os.path.normcase(os.path.abspath(p)) == want:
                return ("House rules, design loop: %s is the stage tracker and only aj's approval messages "
                        "move the stage, so it cannot be edited by hand. To switch the loop off: "
                        "HOUSE_RULES_LOOP=off." % LOOP_FILE)
    return None


LOOP_LOG = os.path.join("docs", "6-decisions", "Decisions.md")


def _loop_log_mark(top):
    """A fingerprint of the decisions log, or None when the project has none. Any other read error
    propagates to _loop_scope_note, which reports it."""
    path = os.path.join(top, LOOP_LOG)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _loop_unlogged(state, top, label, name):
    """#230: an approval counts only once the stage being closed is in the decisions log - the log
    must exist and have changed since the last approval. A refusal note, or "" when it may count."""
    mark = _loop_log_mark(top)
    if mark is None:
        return ('Design loop: aj wrote "%s: %s", but this project has no decisions log (%s), so nothing '
                "moved. Create it, log this stage's decisions, then ask aj to approve again."
                % (label, name, LOOP_LOG.replace(os.sep, "/")))
    if mark == state.get("log_mark"):
        # #327: the model can only log the entry after the approval, so refusing made aj type it twice.
        # The approval counts; the note asks for the entry. log_mark stays, so the next approval still
        # detects whether this one got logged.
        state["log_ask"] = True
        return ""
    state["log_mark"] = mark
    return ""


# A feature name ends at the end of its sentence, or where a pasted reply such as "Build plan: 1A 2A"
# starts on the same line - found in the real run, where the whole line became the name. A spaced
# dash ends it too: "QA failed: label check - it should say hi" (found in the label check's real run). So
# does a pasted page reply's answer codes: "New item visual: 1C", "Label check plan: 1A 2A" (#243).
# A capitalised header before a colon ends it only when an answer code does not follow (#266): "enforced QA
# stage: 1A" is a name and its codes, but a pasted "Build plan: 1A" header is cut whole.
_LOOP_NAME_END_RE = re.compile(r"[.!?](?:\s|$)|\s+(?:Build|Design) plan:|\s+[A-Z][A-Za-z ]{0,30}:\s(?!\d+[A-Za-z*](?:\s|$))"
                               r"|\s+[-–—]\s|\s*:\s*\d+[A-Za-z*](?:\s|$)")


def _loop_name(raw):
    m = _LOOP_NAME_END_RE.search(raw)
    return (raw[:m.start()] if m else raw).strip() or raw.strip()


# #235: an issue's label says whose move it is - `in progress` is mine, `needs review` is aj's - and
# every stage move checks it. Labels are read from GitHub every time (#236); when that read fails,
# from the label changes this hook recorded, and the note says why.
LOOP_WORKING, LOOP_REVIEW = "in progress", "needs review"
LOOP_GH_SECONDS = 5  # the reads run in parallel, well inside hooks.json's 10s per hook
# Tests point this at a JSON file of {"owner/repo#n": [labels]} standing in for GitHub; a missing
# file reads as a failed GitHub read.
LOOP_LABELS_FILE_ENV = "HOUSE_RULES_LOOP_LABELS_FILE"


def _loop_key(repo, number):
    return "%s#%d" % (repo, int(number))


def _loop_gh_labels(repo, number):
    import subprocess
    proc = subprocess.run(["gh", "api", "repos/%s/issues/%d" % (repo, number), "--jq", "[.labels[].name]"],
                          capture_output=True, text=True, timeout=LOOP_GH_SECONDS)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(detail[0] if detail else "gh exited %d" % proc.returncode)
    return json.loads(proc.stdout)


def _loop_labels(state):
    """({key: [labels] or None}, note) for the feature's issues. The note is "" when GitHub answered,
    else it says the labels came from the record and why."""
    import subprocess
    issues = [i for i in state.get("issues", []) if isinstance(i, dict) and i.get("repo") and "number" in i]
    if not issues:
        return {}, ""
    keys = [_loop_key(i["repo"], i["number"]) for i in issues]
    stand_in = os.environ.get(LOOP_LABELS_FILE_ENV)
    try:
        if stand_in:
            with open(stand_in, "r", encoding="utf-8") as f:
                found = json.load(f)
            return {k: found.get(k) for k in keys}, ""
        if not shutil.which("gh"):
            raise RuntimeError("gh is not installed")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            got = list(pool.map(lambda i: _loop_gh_labels(i["repo"], i["number"]), issues))
        return dict(zip(keys, got)), ""
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        why = "Labels were taken from the changes this hook recorded, because the GitHub read failed (%s)." % exc
    recorded = state.get("labels") if isinstance(state.get("labels"), dict) else {}
    return {k: recorded.get(k) for k in keys}, why


def _loop_wrong(labels, want):
    """The issues whose labels don't fit `want` (LOOP_WORKING or LOOP_REVIEW), named with what they have."""
    wrong = []
    for key, have in labels.items():
        low = [str(l).lower() for l in have] if isinstance(have, list) else None
        ok = low is not None and (LOOP_WORKING in low if want == LOOP_WORKING
                                  else LOOP_REVIEW in low and LOOP_WORKING not in low)
        if not ok:
            wrong.append("#%s (%s)" % (key.split("#")[1], ", ".join(have) if low else "no labels known"))
    return wrong


def _loop_to_qa(state, labels):
    """Build becomes QA once every issue says needs review and none says in progress. True if it moved."""
    if state["stage"] == "build" and labels and not _loop_wrong(labels, LOOP_REVIEW):
        state["stage"] = "qa"
        return True
    return False


_PR_URL_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
_GITHUB_PR_CREATE_RE = re.compile(r"^mcp__(github|GitHub)__create_pull_request$")
_LOOP_PR_NOTE = (" QA started because a pull request was opened: code edits are now closed. Swap every issue to "
                 "`needs review` and build the QA page with make_page.py; aj answers \"QA passed: <feature>\" "
                 "or \"QA failed: <feature>\".")

_LOOP_QA_NOTE = (" Every issue of the feature says `needs review`, so the stage is QA: code edits are closed, "
                 "and aj answers \"QA passed: <feature>\" or \"QA failed: <feature>\" with the changes.")


def _house_labels_note(top):
    """#276: create any house label this repo's GitHub copy is missing (scripts/labels.py), and say
    what it created or could not. "" when the repo has every label or no GitHub remote. Never raises."""
    try:
        import labels as _labels  # scripts/labels.py, beside this file (sys.path is set above)
        git_dir = _common_git_dir(top) if top else None
        if not git_dir:
            return ""
        repo, _why = _labels.repo_from_git(git_dir)
        if not repo:
            return ""  # no GitHub remote: there is nowhere to create labels
        return _labels.summary_note(_labels.ensure_labels(repo), repo)
    except Exception as exc:
        return ("house-rules: label setup hit an error (%s: %s), so missing house labels were not created."
                % (type(exc).__name__, exc))


def _loop_label_refusal(said, want, wrong, note, top=None):
    made = _house_labels_note(top)
    return ('Design loop: aj wrote "%s", but these issues are not labelled `%s`: %s. Nothing moved. Fix the '
            "labels, then ask aj to approve again.%s%s" % (said, want, "; ".join(wrong), " " + note if note else "",
                                                          " " + made if made else ""))


_LOOP_STAGE_ORDER = ((_LOOP_DESIGN_RE, 0), (_LOOP_PLAN_RE, 1), (_LOOP_QA_RE, 2))


_LOOP_SWEEP_RE = re.compile(r"\bsweep\s+approved\s*:\s*issues\b([^\n]*)", re.IGNORECASE)
_LOOP_NOTPLANNED_RE = re.compile(r"\bclose\s+as\s+not\s+planned\s*:[ \t]*([^\n]*)", re.IGNORECASE)
_LOOP_NP_PAIR_RE = re.compile(r"(?:([\w.-]+/[\w.-]+))?#(\d+)\s+replaced\s+by\s+(?:[\w.-]+/[\w.-]+)?#(\d+)",
                              re.IGNORECASE)


def _loop_sweep_apply(state, text):
    """#364: aj's sweep approvals. "Sweep approved: issues [keep #N ...]" moves sweep_proposed into sweep;
    "Close as not planned: #N replaced by #M[, ...]" appends not_planned entries. Returns notes ("" if none)."""
    notes = []
    m = _LOOP_SWEEP_RE.search(text)
    if m:
        proposed = [x for x in (state.get("sweep_proposed") or []) if isinstance(x, dict)]
        if not proposed:
            notes.append('Design loop: aj wrote "Sweep approved: issues", but no sweep page has recorded '
                         "proposed rows, so there is nothing to approve and nothing moved.")
        else:
            k = re.search(r"\bkeep\b(.*)", m.group(1), re.IGNORECASE)
            kept = {int(n) for n in re.findall(r"#(\d+)", k.group(1))} if k else set()
            moved = [x for x in proposed if x.get("number") not in kept]
            left_out = [x for x in proposed if x.get("number") in kept]
            if not isinstance(state.get("sweep"), list):
                state["sweep"] = []
            state["sweep"].extend(moved)
            state.pop("sweep_proposed", None)
            notes.append('Design loop: aj wrote "Sweep approved: issues". Recorded %d sweep row(s) for the close '
                         "guard%s." % (len(moved), ("; kept open at aj's word: " + ", ".join(
                             "#%s" % x.get("number") for x in left_out)) if left_out else ""))
    m = _LOOP_NOTPLANNED_RE.search(text)
    if m:
        pairs = _LOOP_NP_PAIR_RE.findall(m.group(1))
        if not pairs:
            notes.append('Design loop: aj wrote "Close as not planned:", but no "#N replaced by #M" pair '
                         "was found, so nothing was recorded.")
        else:
            if not isinstance(state.get("sweep"), list):
                state["sweep"] = []
            for repo, n, by in pairs:
                state["sweep"].append({"repo": repo, "number": int(n), "action": "not_planned",
                                       "replaced_by": int(by)})
            notes.append('Design loop: aj wrote "Close as not planned:". Recorded %d not-planned close(s) for the '
                         "close guard: %s." % (len(pairs), ", ".join("#%s replaced by #%s" % (n, b)
                                                                      for _r, n, b in pairs)))
    return " ".join(notes)


def _loop_apply(state, text, top):
    sweep_note = _loop_sweep_apply(state, text)
    note = _loop_apply_stage(state, text, top)
    return " ".join(n for n in (sweep_note, note) if n)


def _loop_apply_stage(state, text, top):
    """Move the stage for one message of aj's. Returns a note for the model, or "" when the
    message approves nothing. Mutates state.

    #307: a message can hold more than one approval ("Design approved: X.  Build plan approved: X").
    Each phrase is cut out up to where the next one starts, and the pieces are applied in stage order -
    design, then build plan, then QA - so one refusal no longer hides the approvals beside it."""
    found = sorted((m.start(), order) for rx, order in _LOOP_STAGE_ORDER for m in rx.finditer(text))
    if len(found) < 2:
        return _loop_apply_one(state, text, top)
    pieces = [(order, text[start:found[i + 1][0] if i + 1 < len(found) else len(text)])
              for i, (start, order) in enumerate(found)]
    notes = [_loop_apply_one(state, piece, top) for _order, piece in sorted(pieces, key=lambda p: p[0])]
    return " ".join(n for n in notes if n)


def _loop_apply_one(state, text, top):
    """Move the stage for one approval phrase (or none). Returns a note for the model, or "" when the
    text approves nothing. Mutates state."""
    stage, feature = state["stage"], state.get("feature") or ""
    approval = None
    m = _LOOP_PLAN_RE.search(text)
    if m:
        name = _loop_name(m.group(1))
        if stage != "plan":
            return ('Design loop: aj wrote "Build plan approved: %s", but the stage is %s, not Plan, so '
                    "nothing moved. A build plan is approved after its design." % (name, LOOP_STAGE_NAMES[stage]))
        have = sum(1 for i in state.get("issues", []) if isinstance(i, dict) and i.get("labelled"))
        if have < ISSUES_NEEDED:
            return ('Design loop: aj wrote "Build plan approved: %s", but the feature has %d labelled issue(s) '
                    "made since its design was approved, and needs at least %d: one issue for the feature "
                    "and a sub-issue per step, each naming what it depends on, what depends on it and when "
                    "it counts as done, labelled `%s`. Nothing moved. Create them, then ask aj to approve again."
                    % (name, have, ISSUES_NEEDED, ISSUES_LABEL))
        labels, src = _loop_labels(state)
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if wrong:
            return _loop_label_refusal("Build plan approved: %s" % name, LOOP_WORKING, wrong, src, top)
        unlogged = _loop_unlogged(state, top, "Build plan approved", name)
        if unlogged:
            return unlogged
        state["stage"], approval = "build", ("Build plan approved", name)
    else:
        m = _LOOP_DESIGN_RE.search(text)
        if m:
            name = _loop_name(m.group(1))
            # #307: the redo is for the feature QA failed, even when the stored name went stale.
            failed = [a.get("name") or "" for a in state.get("approvals", [])
                      if isinstance(a, dict) and a.get("stage") == "QA failed"]
            redo = state.get("redo") and name.lower() in {feature.lower(), (failed[-1] if failed else "").lower()}
            if redo:
                labels, src = _loop_labels(state)
                wrong = _loop_wrong(labels, LOOP_WORKING)
                if wrong:
                    return _loop_label_refusal("Design approved: %s" % name, LOOP_WORKING, wrong, src, top)
            unlogged = _loop_unlogged(state, top, "Design approved", name)
            if unlogged:
                return unlogged
            state["feature"], state["stage"], approval = name, "plan", ("Design approved", name)
            state["redo"] = False
            if not redo:
                state["issues"] = []
                state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: not the next feature's
        else:
            m = _LOOP_QA_RE.search(text)
            if m:
                verdict, name = m.group(1).lower(), _loop_name(m.group(2))
                if stage == "build":
                    labels, src = _loop_labels(state)
                    if not _loop_to_qa(state, labels):
                        wrong = _loop_wrong(labels, LOOP_REVIEW)
                        return ('Design loop: aj wrote "QA %s: %s", but QA starts only once every issue of the '
                                "feature says `needs review`, and these don't: %s. Nothing moved. Swap their "
                                "labels when the build is ready for aj, then ask again.%s"
                                % (verdict, name, "; ".join(wrong) or "no issues are recorded",
                                   " " + src if src else ""))
                elif stage != "qa":
                    return ('Design loop: aj wrote "QA %s: %s", but the stage is %s, so nothing moved. QA '
                            "follows a build." % (verdict, name, LOOP_STAGE_NAMES[stage]))
                unlogged = _loop_unlogged(state, top, "QA " + verdict, name)
                if unlogged:
                    return unlogged
                state["stage"] = "done" if verdict == "passed" else "design"
                if verdict == "passed":  # #362: the closable record; "Design approved" never touches it
                    if not isinstance(state.get("closable"), list):
                        state["closable"] = []
                    state["closable"].append({
                        "feature": name,
                        "issues": [{"repo": i["repo"], "number": i["number"]} for i in state.get("issues", [])
                                   if isinstance(i, dict) and i.get("repo") and "number" in i],
                        "qa_at": int(time.time()), "qa": "QA passed: " + name, "merged_pr": None})
                state["redo"] = verdict == "failed"
                if state["redo"]:
                    state.pop("qa_page", None); state.pop("qa_page_linked", None)  # #269: the redo gets a new page
                approval = ("QA " + verdict, name)
    if approval:
        state.setdefault("approvals", []).append(
            {"stage": approval[0], "name": approval[1], "at": int(time.time())})
        note = 'Design loop: aj wrote "%s: %s". The stage is now %s.' % (
            approval[0], approval[1], LOOP_STAGE_NAMES[state["stage"]])
        if state.pop("log_ask", False):  # #327
            note += (" The decisions log (%s) has nothing new since the last approval: add this stage's "
                     "entry to it before the turn ends." % LOOP_LOG.replace(os.sep, "/"))
        if state["stage"] == "plan":
            note += (" Code edits stay closed. Planning owes: a systems doc in docs/4-systems/, a GitHub issue "
                     "for the feature and a sub-issue per step, each naming dependencies, dependants and "
                     "done-criteria, labelled `%s` and `%s`." % (ISSUES_LABEL, LOOP_WORKING))
            made = _house_labels_note(top)  # #276: planning is when the labels are first needed
            return note + (" " + made if made else "")
        if state["stage"] == "build":
            note += (" Code edits are open for the approved steps while every issue says `%s`. Hand each "
                     "approved step to @house-rules:builder (one per issue; at most two running) unless aj said "
                     "to build it yourself; helpers build only approved steps and never design or approve. When "
                     "the build is ready for aj, swap every issue's `%s` for `%s`: that starts QA."
                     % (LOOP_WORKING, LOOP_WORKING, LOOP_REVIEW))
        elif approval[0] == "QA failed":
            note += (" Their list of changes starts the next design. Move every issue back to `%s` now; the "
                     "redo's \"Design approved\" is refused until they are." % LOOP_WORKING)
        elif approval[0] == "QA passed":
            note += (" Code edits stay closed. The issues keep `%s` until aj closes them; never close one."
                     % LOOP_REVIEW)
        else:
            note += " Code edits stay closed."
        return note
    if _LOOP_SKIP_RE.search(text):
        state["skip"] = True
        return 'Design loop: aj wrote "skip design", so the next code edit goes through, then the lock is back.'
    if _LOOP_BARE_RE.search(text):
        return ('Design loop: aj\'s message says "approved" but names no stage and feature, so nothing moved. '
                'Ask which they mean; an approval reads like "Design approved: <feature>", '
                '"Build plan approved: <feature>", "QA passed: <feature>" or "QA failed: <feature>".')
    return ""


def _loop_scope_note(payload):
    """scope's half: read aj's message, move the stage, say what happened. Never raises."""
    if not _loop_enabled():
        return ""
    try:
        m = _PROMPT_VALUE_RE.search(payload or "")
        if not m:
            return ""
        text = json.loads('"%s"' % m.group(1))
        if _is_relayed_prompt(text, payload):
            return ("Design loop: this message is a helper's report or a notification, not aj, "
                    "so it moved nothing.")
        top, git_dir = _issues_locate(_payload_cwd(payload))
        if not git_dir:
            return ""
        state, problem = _loop_read(git_dir)
        if problem:
            return problem
        before = json.dumps(state, sort_keys=True)
        note = _loop_apply(state, text, top)
        if json.dumps(state, sort_keys=True) != before:
            _loop_write(git_dir, state)
        return note
    except Exception as exc:
        return "house-rules: the design-loop check hit an error (%s: %s), so this message moved nothing." % (
            type(exc).__name__, exc)


def _loop_helper_note(payload):
    """#232: what a helper is told at start-up about the feature it works inside. "" when the loop
    is off or the helper is not in a repo."""
    if not _loop_enabled():
        return ""
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return ""
    state, problem = _loop_read(git_dir)
    if problem:
        return problem
    issues = ", ".join("#%d" % i["number"] for i in state.get("issues", []) if isinstance(i, dict) and "number" in i)
    return (
        "Design loop: the feature is %s and its stage is %s%s. You build only the steps aj approved in its "
        "build plan; you never design, change the plan, or approve anything - an approval only counts from "
        "aj's own message. Anything unexpected comes back to the main session, not into the code. Code edits "
        "are refused outside Build." % (
            '"%s"' % state["feature"] if state.get("feature") else "not started",
            LOOP_STAGE_NAMES[state["stage"]],
            "; its issues are %s" % issues if issues else ""))


def _loop_stop_line(payload):
    """#238, handover: (line or None, problem or None) - name every issue whose label doesn't fit the
    stage. Quiet when there is no feature with issues, or every label fits."""
    if not _loop_enabled():
        return None, None
    _, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return None, None
    state, problem = _loop_read(git_dir)
    if problem:
        return None, problem
    stage = state["stage"]
    if stage == "done" or (stage == "design" and not state.get("redo")) or not state.get("issues"):
        return None, None
    labels, src = _loop_labels(state)
    if _loop_to_qa(state, labels):
        _loop_write(git_dir, state)
        return "House rules, design loop:" + _LOOP_QA_NOTE, src or None
    want = LOOP_REVIEW if stage == "qa" else LOOP_WORKING
    wrong = _loop_wrong(labels, want)
    if not wrong:
        return None, src or None
    return ("House rules, design loop: \"%s\" is in %s, so every issue should be labelled `%s`, and these "
            "are not: %s. Fix the labels before this turn ends.%s"
            % (state.get("feature") or "", LOOP_STAGE_NAMES[stage], want, "; ".join(wrong),
               " Code edits are refused until they are." if stage == "build" else "")), src or None


def _loop_gate(payload):
    """(deny reason or None, problem or None): code edits only in Build, or once after skip design."""
    git_dir, problem = _gated_edit(payload, "design-loop lock")
    if not problem:
        refusal = _loop_file_refusal(payload)
        if refusal:
            return refusal, None
    script_paths, script_unreadable, script = [], False, False
    if not git_dir and not problem:
        # #262: a Bash/PowerShell script write of a source file is held to the same lock.
        git_dir, problem, script_paths, script_unreadable = _gated_script_write(payload)
        script = bool(git_dir)
    if not git_dir:
        return None, problem
    state, problem = _loop_read(git_dir)
    if problem:
        return None, problem
    if script and state["stage"] == "build":
        return None, None  # Build: nothing changes for shell commands
    if state["stage"] == "build":
        labels, src = _loop_labels(state)
        if _loop_to_qa(state, labels):
            _loop_write(git_dir, state)
            return "House rules, design loop:" + _LOOP_QA_NOTE, None
        wrong = _loop_wrong(labels, LOOP_WORKING)
        if not wrong:
            return None, src or None
        return ("House rules, design loop: code edits in Build need every issue of \"%s\" labelled `%s`, and "
                "these are not: %s. Fix the labels, then edit again.%s"
                % (state.get("feature") or "", LOOP_WORKING, "; ".join(wrong), " " + src if src else "")), None
    if state.get("skip"):
        state["skip"] = False
        _loop_write(git_dir, state)
        return None, None
    feature = state.get("feature") or ""
    if script:
        # #309 (incident 4 of #303): a shell command is reported, never refused, until the restructure. The
        # refusal stopped docs and .claude/ writes made from the shell, which are meant to stay open.
        what = ("a file it can't name" if script_unreadable and not script_paths
                else ", ".join(script_paths) or "a source file")
        return None, ("house-rules design loop (report only, #309): code is locked in the %s stage, and this "
                      "shell command writes %s. It was let through; the shell-write refusal is switched off "
                      "until the restructure." % (LOOP_STAGE_NAMES[state["stage"]], what))
    return (
        "House rules, design loop: code edits are closed in the %s stage%s. They open when aj types "
        "\"Build plan approved: <feature>\" after approving a design, or \"skip design\" for one small "
        "change. docs/, .claude/ and .md files stay open, so write the design or plan as a page "
        "now. To switch this off: HOUSE_RULES_LOOP=off." % (
            LOOP_STAGE_NAMES[state["stage"]], ' of "%s"' % feature if feature else ""),
        None,
    )


_GH_ISSUE_CREATE_RE = re.compile(_GH_PREFIX + r"issue\s+create\b")
_GH_PR_CREATE_RE = re.compile(_GH_PREFIX + r"pr\s+create\b")
_GH_ISSUE_CLOSE_RES = (
    re.compile(_GH_PREFIX + r"issue\s+close\b"),
    re.compile(_GH_PREFIX + r"issue\s+edit\b[^\n;&|]*--state[=\s]+[\"']?closed", re.IGNORECASE),
    re.compile(_GH_PREFIX + r"api\b(?=[^\n]*(?:-X|--method)[=\s]+[\"']?PATCH)(?=[^\n]*issues/\d+)"
               r"(?=[^\n]*state\W{0,4}closed)", re.IGNORECASE),
)
_ISSUE_URL_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


_GITHUB_ISSUE_WRITE_RE = re.compile(r"^mcp__(github|GitHub)__issue_write$")


def _created_issue(data):
    """(found, labelled, how) for a tool call that created a GitHub issue - a terminal
    `gh issue create` or the GitHub tool's issue_write with method create (#231) - or None for any
    other call. `found` lists (repo, number) pairs from the response; `labelled` says whether the
    project label was set."""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    tool = data.get("tool_name") or ""
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if not _GH_ISSUE_CREATE_RE.search(cmd):
            return None
        label_text, how = cmd, "`gh issue create`"
    elif _GITHUB_ISSUE_WRITE_RE.match(tool) and str(ti.get("method", "")).lower() == "create":
        labels = ti.get("labels") if isinstance(ti.get("labels"), list) else []
        label_text, how = " ".join(str(l) for l in labels), "GitHub tool issue_write"
    else:
        return None
    resp = data.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp)
    found = list(dict.fromkeys(_ISSUE_URL_RE.findall(text)))
    labelled = any(l.lower() in label_text.lower() for l in (ISSUES_LABEL, ISSUES_LABEL_OLD))
    return found, labelled, how


_GITHUB_SLUG_RE = re.compile(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?\s*$", re.IGNORECASE)


def _origin_slug(top):
    """(slug, problem): the "owner/repo" of the checkout's GitHub origin remote, or "" when it has none,
    and why it couldn't be read ("" when it could)."""
    import subprocess
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=top, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=3).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return "", "house-rules: could not read this checkout's git remote (%s)" % exc
    m = _GITHUB_SLUG_RE.search(url.strip())
    return (m.group(1) if m else ""), ""


def _loop_record_issues(git_dir, found, labelled, top=None):
    """#231: issues made while a feature is in Plan count toward its build-plan approval.

    #308: only issues made in the repo that owns the stage file count. In an Unblocked session, two issues
    opened in another repo were counted as Unblocked's, and the label check then blocked the turn seven
    times. A checkout with no GitHub origin can't say which repo it is, so its issues count as before."""
    if not _loop_enabled() or not found:
        return []
    state, problem = _loop_read(git_dir)
    if problem:
        return [problem]
    if state["stage"] != "plan":
        return []
    own, slug_problem = _origin_slug(top) if top else ("", "")
    own = own.lower()
    notes = [slug_problem + ", so every new issue counts toward this feature."] if slug_problem else []
    for repo, number in found:
        if own and str(repo).lower() != own:
            notes.append("Design loop: issue %s#%s was made in another repo, so it doesn't count toward \"%s\" "
                         "here (this checkout is %s)." % (repo, number, state.get("feature") or "this feature", own))
            continue
        state.setdefault("issues", []).append({"repo": repo, "number": int(number), "labelled": labelled})
    _loop_write(git_dir, state)
    return notes


_GH_ISSUE_EDIT_RE = re.compile(_GH_PREFIX + r"issue\s+edit\s+(\d+)\b([^\n;&|]*)")
_GH_LABEL_FLAG_RE = re.compile(r"(?:--(add-label|remove-label|label)|-(l))(?:=|\s+)(\"[^\"]*\"|'[^']*'|[^\s\"']+)")


def _gh_label_flags(cmd):
    """{"add": [...], "remove": [...]} from a gh command's label flags (--label and -l count as add)."""
    out = {"add": [], "remove": []}
    for long_flag, _short, value in _GH_LABEL_FLAG_RE.findall(cmd):
        names = [v.strip() for v in value.strip("\"'").split(",") if v.strip()]
        out["remove" if long_flag == "remove-label" else "add"].extend(names)
    return out


_GH_API_LABELS_RE = re.compile(_GH_PREFIX + r"api\s+([^\n;&|]*?)\brepos/([\w.-]+/[\w.-]+)/issues/(\d+)/labels(?:/([^\s\"']+))?([^\n;&|]*)")
_GH_API_METHOD_RE = re.compile(r"(?:-X|--method)(?:=|\s+)[\"']?(\w+)", re.I)
_GH_API_LABEL_FIELD_RE = re.compile(r"(?:-f|-F|--raw-field|--field)(?:=|\s+)(?:\"labels\[\]=([^\"]*)\"|'labels\[\]=([^']*)'|labels\[\]=(\S+))")
_GH_API_FAILED_RE = re.compile(r"\(HTTP [45]\d\d\)|^gh: |\"status\":\s*\"[45]\d\d\"", re.M)


def _gh_api_label_change(cmd, text):
    """#278: (repo, number, None, add, remove) for a succeeded `gh api repos/O/R/issues/N/labels` call (the REST
    form that works in cloud sessions), else None. Repo and number come from the path, not the response."""
    m = _GH_API_LABELS_RE.search(cmd)
    if not m or _GH_API_FAILED_RE.search(text):
        return None
    pre, repo, number, name, post = m.groups()
    method = (_GH_API_METHOD_RE.search(pre + " " + post) or [None, "POST" if "-f" in post or "-F" in post or "field" in post else "GET"])[1].upper()
    if method == "DELETE" and name:
        return (repo, int(number), None, [], [urllib.parse.unquote(name)])
    if method == "POST" and not name:
        adds = [(x or y or z).strip("\"'") for x, y, z in _GH_API_LABEL_FIELD_RE.findall(pre + " " + post)]
        if adds:
            return (repo, int(number), None, adds, [])
    return None


def _label_changes(data):
    """#236: [(repo, number, set_to or None, add, remove)] for a tool call that set issue labels and
    succeeded - the GitHub tool's issue_write, or `gh issue create` / `gh issue edit`."""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    tool = data.get("tool_name") or ""
    resp = data.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp)
    urls = list(dict.fromkeys(_ISSUE_URL_RE.findall(text)))
    if _GITHUB_ISSUE_WRITE_RE.match(tool) and isinstance(ti.get("labels"), list):
        labels = [str(l) for l in ti["labels"]]
        if str(ti.get("method", "")).lower() == "create":
            return [(repo, int(n), labels, [], []) for repo, n in urls]
        number = ti.get("issue_number")
        repo = "%s/%s" % (ti.get("owner"), ti.get("repo"))
        if number and any(r.lower() == repo.lower() and int(n) == int(number) for r, n in urls):
            return [(repo, int(number), labels, [], [])]
        return []
    if tool != "Bash":
        return []
    cmd = ti.get("command") or ""
    if _GH_ISSUE_CREATE_RE.search(cmd):
        flags = _gh_label_flags(cmd)
        return [(repo, int(n), flags["add"], [], []) for repo, n in urls]
    api = _gh_api_label_change(cmd, text)
    if api:
        return [api]
    m = _GH_ISSUE_EDIT_RE.search(cmd)
    if m:
        flags = _gh_label_flags(m.group(2))
        if flags["add"] or flags["remove"]:
            return [(repo, int(n), None, flags["add"], flags["remove"]) for repo, n in urls if int(n) == int(m.group(1))]
    return []


def _pr_opened(data):
    """True for a successful pull request creation: the GitHub tool or `gh pr create`, with a PR URL in the response."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    if not (_GITHUB_PR_CREATE_RE.match(tool) or (tool == "Bash" and _GH_PR_CREATE_RE.search(ti.get("command") or ""))):
        return False
    resp = data.get("tool_response")
    return bool(_PR_URL_RE.search(resp if isinstance(resp, str) else json.dumps(resp)))


def _loop_record_labels(payload):
    """PostToolUse: record label changes for the GitHub-read fallback, and move Build to QA once every
    issue says needs review. Returns notes. Never raises."""
    if not _loop_enabled():
        return []
    try:
        data = json.loads(payload)
        changes = _label_changes(data) if isinstance(data, dict) else []
        pr = isinstance(data, dict) and _pr_opened(data)
        if not changes and not pr:
            return []
        _, git_dir = _issues_locate(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return []
        state, problem = _loop_read(git_dir)
        if problem:
            return [problem]
        recorded = state.setdefault("labels", {})
        for repo, number, set_to, add, remove in changes:
            key = _loop_key(repo, number)
            now = list(set_to) if set_to is not None else list(recorded.get(key) or [])
            now = [l for l in now if l.lower() not in {r.lower() for r in remove}]
            now += [a for a in add if a.lower() not in {l.lower() for l in now}]
            recorded[key] = now
        notes = []
        if pr and state["stage"] == "build":
            state["stage"] = "qa"
            notes.append("Design loop:" + _LOOP_PR_NOTE)
        elif state["stage"] == "build" and changes:
            labels, src = _loop_labels(state)
            if _loop_to_qa(state, labels):
                notes.append("Design loop:" + _LOOP_QA_NOTE + (" " + src if src else ""))
        _loop_write(git_dir, state)
        return notes
    except Exception as exc:
        return ["house-rules: could not record an issue label change for the design loop (%s: %s)."
                % (type(exc).__name__, exc)]


def _issues_record(payload):
    """PostToolUse Bash or GitHub tool: record a created issue in the issue-gate and design-loop
    state. Returns a list of note strings (empty when nothing applies). Never raises."""
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            return []
        hit = _created_issue(data)
        if hit is None:
            return []
        found, labelled, how = hit
        top, git_dir = _issues_locate(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return []
        loop_notes = _loop_record_issues(git_dir, found, labelled, top)
        if not _issues_enabled():
            return loop_notes
        state, problem = _issues_read(git_dir)
        if problem:
            return loop_notes + [problem]
        if not state or not state.get("needs_issues"):
            return loop_notes
        if not found:
            return loop_notes + ["house-rules: a %s ran but no issue URL was in its output, so it "
                                 "was not counted toward the issue gate." % how]
        created = state.setdefault("created", [])
        for repo, number in found:
            created.append({"repo": repo, "number": int(number), "labelled": labelled})
        notes = []
        if not labelled:
            notes.append("house-rules: issue #%s was created without the `%s` label, so it does not "
                         "count toward the issue gate and Focus Deck will ignore it. Add it with `gh "
                         "api repos/%s/issues/%s/labels -f \"labels[]=%s\"` and create the next issues with it."
                         % (found[0][1], ISSUES_LABEL, found[0][0], found[0][1], ISSUES_LABEL))
        have = _labelled_count(state)
        if have >= ISSUES_NEEDED:
            state["needs_issues"] = False
            notes.append("house-rules: %d labelled issues recorded, so source edits are unblocked." % have)
        _issues_write(git_dir, state)
        return loop_notes + notes
    except Exception as exc:
        return ["house-rules: could not record a created issue in the issue gate (%s: %s)."
                % (type(exc).__name__, exc)]


def _issues_stop_line(payload):
    """Handover: (line or None, problem or None) - the gate is still closed at Stop."""
    if not _issues_enabled():
        return None, None
    top, git_dir = _issues_locate(_payload_cwd(payload))
    if not git_dir:
        return None, None
    state, problem = _issues_read(git_dir)
    if problem:
        return None, problem
    if state and state.get("needs_issues"):
        return ("House rules, plans become issues: the approved %s-step plan still has no parent and "
                "child issues recorded (%d of %d), so source edits stay blocked. Create them with `gh "
                "issue create` and the `%s` label, or tell the user why not."
                % (state.get("plan_steps", "multi"), _labelled_count(state), ISSUES_NEEDED, ISSUES_LABEL)), None
    return None, None


# gh pr create / gh issue close, checked in guard. Both work from the decoded command text.
_PR_BODY_FLAG_RE = re.compile(r"(?:--body|(?<![\w-])-b)(?:=|\s+|(?=[\"']))")
_PR_LINK_RE = re.compile(r"\b(?:Refs|Part of)\s+(?:[\w.-]+/[\w.-]+)?#\d+", re.IGNORECASE)
_PR_NO_ISSUE_RE = re.compile(r"(?:^|\n|[\"']|\\n)\s*No-issue:\s*\S", re.IGNORECASE)
_PR_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s+"
    r"(?:(?:[\w.-]+/[\w.-]+)?#\d+|https?://github\.com/[\w.-]+/[\w.-]+/issues/\d+)",
    re.IGNORECASE,
)

PR_ASK_NOTE = (
    "House rules, pull requests link issues without closing them: say `Refs #N` (or `Part of #N`, "
    "or a line `No-issue: <reason>`) in the body, and never a closing word, because GitHub would "
    "close the issue at merge, before the user has tested."
)


def _author_guard(subject, payload):
    """None unless a git commit would be authored as Claude, else ("deny", reason, None)."""
    if not _attribution_enabled():
        return None
    cmd = _decoded_command(subject)
    if not _GIT_COMMIT_RE.search(cmd):
        return None
    try:
        who = _effective_author(cmd, _command_dir(payload)[0])  # the repo a cd / -C moves to
    except Exception: return None  # unreadable identity: let the commit through, as for an unreadable body file
    if who is None or not _is_claude_identity(*who):
        return None
    return ("deny", "House rules, credit aj's agent: this commit would be authored as `%s <%s>`, "
            "which signs it as Claude. Set the agent's identity in this repo and retry: `%s`. "
            "HOUSE_RULES_ATTRIBUTION=off disables this check."
            % (who[0] or "?", who[1] or "?", AGENT_IDENTITY_FIX), None)


def _guardgithub_issue_checks(payload, raw):
    """The two checks event_guardgithub used to run first (the safe git part now loops over this
    through core.GITHUB_WRITE_HOOKS): True when the call was handled and answered."""
    # #248: an issue made with the GitHub tool needs its three sections, like one made with gh.
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if (_GITHUB_ISSUE_WRITE_RE.match(str(payload.get("tool_name") or ""))
            and str(ti.get("method", "")).lower() == "create" and _issues_enabled() and _clear_writing_enabled()):
        if clarity is None:
            emit({"systemMessage": CLARITY_ERROR + " The issue was NOT checked for its sections."})
        else:
            missing = clarity.missing_issue_sections(str(ti.get("body") or ""))
            if missing:
                emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                      "permissionDecisionReason": ISSUE_SECTIONS_DENY % ", ".join("\"%s\"" % m for m in missing)}})
                return True
    # #363: a close through the GitHub tool goes through the same close guard as gh.
    if (_GITHUB_ISSUE_WRITE_RE.match(str(payload.get("tool_name") or "")) and _issues_enabled()
            and str(ti.get("method", "")).lower() == "update" and str(ti.get("state", "")).lower() == "closed"):
        num = ti.get("issue_number")
        try:
            num = int(num)
        except (TypeError, ValueError):
            num = None
        repo = "%s/%s" % (ti.get("owner"), ti.get("repo")) if ti.get("owner") and ti.get("repo") else ""
        ok, text, ctx = _close_decide(repo, num, str(ti.get("state_reason") or "").lower(), _payload_cwd(raw))
        if ok:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                         "additionalContext": ctx}})
        else:
            emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": text}})
        return True
    return False


# --- #363: the close guard. A close goes through only on recorded evidence or an approved list. ---
CLOSE_COMMENT_NOTE = (
    "House rules, this close is allowed: %s. Before or right after it, comment on issue #%d with that "
    "evidence (the QA message and the merged pull request link, or the sweep approval and the replacing "
    "issue), add the label `AjsAgent completed this` (`gh api repos/%s/issues/%d/labels -f "
    "\"labels[]=AjsAgent completed this\"`) and remove `in progress` (`gh api -X DELETE "
    "repos/%s/issues/%d/labels/in%%20progress`)."
)


def _close_repo_match(a, b):
    return not a or not b or a.lower() == b.lower()


def _close_check(repo, number, reason, state):
    """(allowed, reason_text) for closing issue `number` of `repo` with state reason `reason`
    ("completed", "not_planned" or "" for none), from the design-loop `state` (#363)."""
    reason = (reason or "completed").strip().lower().replace(" ", "_")
    if not isinstance(state, dict):
        state = {}
    sweep = [x for x in (state.get("sweep") or []) if isinstance(x, dict) and x.get("number") == number
             and _close_repo_match(repo, x.get("repo", ""))]
    for x in sweep:
        if x.get("action") == reason:
            if reason == "not_planned" and x.get("replaced_by"):
                return True, "#%d is on the approved sweep list as not planned, replaced by #%s" % (number, x["replaced_by"])
            return True, "#%d is on the approved sweep list as %s" % (number, reason.replace("_", " "))
    holders = []
    for e in state.get("closable") or []:
        if isinstance(e, dict) and any(isinstance(i, dict) and i.get("number") == number
                                       and _close_repo_match(repo, i.get("repo", "")) for i in e.get("issues") or []):
            holders.append(e)
    ready = [e for e in holders if e.get("merged_pr")]
    if ready and reason == "completed":
        e = ready[0]
        pr = e["merged_pr"]
        return True, "%s, and pull request %s#%s was merged since" % (
            e.get("qa") or "QA passed", pr.get("repo") or repo or "?", pr.get("number"))
    if reason != "completed":
        return False, ("a not-planned close needs an approved sweep or a named list, and #%d is not on one "
                       "with the action not_planned" % number)
    if holders:
        return False, "#%d's feature passed QA but no merged pull request is recorded since" % number
    if sweep:
        return False, "#%d is on the approved sweep list with a different action than completed" % number
    return False, ("no QA pass is recorded for a feature that holds #%d, and it is on no approved sweep or "
                   "named list" % number)


def _close_forget(git_dir, repo, number):
    """Take `number` out of its closable entry (the entry goes once empty) and out of sweep."""
    state, problem = _loop_read(git_dir)
    if problem or not isinstance(state, dict):
        return
    hit = lambda i: isinstance(i, dict) and i.get("number") == number and _close_repo_match(repo, i.get("repo", ""))
    changed = False
    if isinstance(state.get("closable"), list):
        keep = []
        for e in state["closable"]:
            if isinstance(e, dict) and any(hit(i) for i in e.get("issues") or []):
                e["issues"] = [i for i in e["issues"] if not hit(i)]
                changed = True
                if not e["issues"]:
                    continue
            keep.append(e)
        state["closable"] = keep
    if isinstance(state.get("sweep"), list):
        n = len(state["sweep"])
        state["sweep"] = [x for x in state["sweep"] if not hit(x)]
        changed = changed or len(state["sweep"]) != n
    if changed:
        _loop_write(git_dir, state)


def _close_decide(repo, number, reason, cwd):
    """(allowed, text, context). Reads the stage file and changes nothing; the evidence is
    removed after a successful close, in event_closablemerge."""
    if number is None:
        return False, ("House rules, close guard: I could not tell which issue this close is for (no issue "
                       "number found), so it is refused. Name the issue number."), None
    _, git_dir = _issues_locate(cwd)
    if not git_dir:
        return False, ("House rules, close guard: could not find the project's stage file from %s, so the "
                       "close of #%d is refused." % (cwd, number)), None
    state, problem = _loop_read(git_dir)
    if problem:
        return False, "%s The close of #%d is refused." % (problem, number), None
    ok, why = _close_check(repo, number, reason, state)
    if not ok:
        return False, "House rules, close guard: refused to close #%d: %s." % (number, why), None
    slug = repo or "<owner>/<repo>"
    return True, why, CLOSE_COMMENT_NOTE % (why, number, slug, number, slug, number)


def _close_gh_parse(cmd):
    """(repo, number, reason) from a gh close command; number None when it cannot be read."""
    repo = ""
    m = re.search(r"(?:-R|--repo)[ =]+[\"']?([\w.-]+/[\w.-]+)", cmd)
    if m:
        repo = m.group(1)
    um = _ISSUE_URL_RE.search(cmd)
    number = None
    if um:
        repo, number = um.group(1), int(um.group(2))
    else:
        am = re.search(r"issues/(\d+)", cmd)
        if am:
            number = int(am.group(1))
            rm = re.search(r"repos/([\w.-]+/[\w.-]+)/issues", cmd)
            if rm:
                repo = rm.group(1)
        else:
            im = re.search(r"issue\s+(?:close|edit)\s+(?:(?:-R|--repo)[ =]+\S+\s+)?#?(\d+)(?![\w/-])", cmd)
            if im:
                number = int(im.group(1))
    reason = ""
    rm = re.search(r"(?:--reason|-r)[ =]+[\"']?(not[ _]planned|completed|duplicate)", cmd, re.IGNORECASE)
    if not rm:
        rm = re.search(r"state_reason[=\s:\"']+(not[ _]planned|completed|duplicate)", cmd, re.IGNORECASE)
    if rm:
        reason = rm.group(1).lower().replace(" ", "_")
    return repo, number, reason


def _close_gh_decision(cmd, payload):
    repo, number, reason = _close_gh_parse(cmd)
    ok, text, ctx = _close_decide(repo, number, reason, _payload_cwd(payload))
    return ("allow", text, ctx) if ok else ("deny", text, None)


def _issues_guard(subject, payload):
    """None when the issue rules have nothing to say about this command, else
    (kind, reason, context) with kind "deny" or "ask"."""
    if not _issues_enabled():
        return None
    cmd = _decoded_command(subject)
    if _GH_PR_CREATE_RE.search(cmd):
        body = cmd
        fm = _PR_BODY_FILE_RE.search(cmd)
        if fm:
            name = fm.group(1).strip("\"'")
            if name == "-":
                return ("ask", "House rules: `gh pr create --body-file -` reads the body from stdin, so I "
                        "could not check it for `Refs #N` and closing words. " + PR_ASK_NOTE, PR_ASK_NOTE)
            path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError as exc:
                return ("ask", "House rules: could not read the PR body file %s (%s), so I could not check "
                        "it for `Refs #N` and closing words. %s" % (name, exc, PR_ASK_NOTE), PR_ASK_NOTE)
        elif not _PR_BODY_FLAG_RE.search(cmd):
            return ("ask", "House rules: this `gh pr create` has no --body or --body-file (--web, --fill "
                    "or interactive), so I cannot check it for `Refs #N` and closing words. " + PR_ASK_NOTE,
                    PR_ASK_NOTE)
        closing = _PR_CLOSING_RE.search(body)
        if closing:
            return ("deny", "House rules, pull requests link issues without closing them: the body says "
                    "`%s`, and GitHub would close that issue when the PR merges, before the user has "
                    "tested. Reword it as `Refs #N` (the user closes the issue after testing)."
                    % closing.group(0), None)
        if not (_PR_LINK_RE.search(body) or _PR_NO_ISSUE_RE.search(body)):
            return ("deny", "House rules, pull requests link issues without closing them: the body needs "
                    "`Refs #N`, `Refs owner/repo#N` or `Part of #N`, or a line `No-issue: <reason>`. "
                    "Add it and run the command again.", None)
        return None
    if _GH_ISSUE_CREATE_RE.search(cmd) and _clear_writing_enabled() and clarity is not None:
        body = cmd
        fm = _PR_BODY_FILE_RE.search(cmd)
        if fm and fm.group(1).strip("\"'") != "-":
            name = fm.group(1).strip("\"'")
            path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError as exc:
                return ("ask", "House rules: could not read the issue body file %s (%s), so I could not "
                        "check it for its three sections." % (name, exc), None)
        missing = clarity.missing_issue_sections(body)
        if missing:
            return ("deny", ISSUE_SECTIONS_DENY % ", ".join("\"%s\"" % m for m in missing), None)
    if any(r.search(cmd) for r in _GH_ISSUE_CLOSE_RES):
        return _close_gh_decision(cmd, payload)
    return None


# #248: an issue says what it depends on, what depends on it, and when it's done.
ISSUE_SECTIONS_DENY = (
    "House rules, write it so nothing is left to guess: this issue is missing %s. Every issue needs "
    "\"Depends on\", \"Depended on by\" and \"Done when\" sections (\"Nothing\" is a fine answer), so "
    "a blocker shows up as an unfinished dependency and done means something. Add them and create it "
    "again. HOUSE_RULES_CLEAR_WRITING=off turns this off."
)


def _open_issues_text(cwd):
    """(text or "", problem or None) for the SessionStart open-issue list. Silent ("", None)
    when there is nothing to list against: no gh, or no GitHub remote."""
    import subprocess
    import time
    gh = shutil.which("gh")
    if not gh:
        return "", None
    top, git_dir = _issues_locate(cwd)
    if not top or not git_dir:
        return "", None
    try:
        remote = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=top,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=3).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return "", "git remote lookup failed: %s" % exc
    if "github.com" not in remote:
        return "", None
    cache = os.path.join(git_dir, "house-rules-issues-cache.json")
    try:
        with open(cache, "r", encoding="utf-8") as f:
            c = json.load(f)
        if time.time() - float(c["ts"]) < 60:
            return c["text"], None
    except (OSError, ValueError, KeyError, TypeError):
        pass  # no usable cache: fetch fresh below
    try:
        proc = subprocess.run([gh, "issue", "list", "--state", "open", "--limit", "10", "--json",
                               "number,title"], cwd=top, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=5)
    except subprocess.TimeoutExpired:
        return "", "timed out after 5 s"
    except OSError as exc:
        return "", "could not run gh: %s" % exc
    if proc.returncode != 0:
        first = (proc.stderr.decode("utf-8", "replace").strip().splitlines() or ["exit %d" % proc.returncode])[0]
        return "", first[:120]
    try:
        items = json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError as exc:
        return "", "unreadable gh output: %s" % exc
    if not items:
        text = "Open issues: none."
    else:
        text = "Open issues (newest first):\n" + "\n".join(
            "- #%s %s" % (i.get("number"), str(i.get("title", ""))[:80]) for i in items[:10])
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "text": text}, f)
    except OSError as exc:
        return text, "cache not written (%s)" % exc
    return text, None


def event_issuelist():
    """SessionStart: the open issues, so the session starts knowing what work is tracked. Its own
    entry (like profile) because inject is already near the 10,000-char per-hook limit."""
    try:
        payload = read_payload()
        waiting = _waiting_session_note(payload)
        text, problem = "", ""
        if _issues_enabled():
            text, problem = _open_issues_text(_payload_cwd(payload or ""))
        out = {}
        context = [t for t in (text, waiting) if t]
        if context:
            out["hookSpecificOutput"] = {"hookEventName": "SessionStart",
                                         "additionalContext": "\n\n".join(context)}
        notes = []
        if _issues_enabled():
            if problem and not text:
                notes.append("house-rules: could not list open issues (%s)" % problem)
            elif text:
                n = sum(1 for l in text.splitlines() if l.startswith("- #"))
                notes.append("house-rules: %d open issue%s loaded" % (n, "" if n == 1 else "s")
                             if n else "house-rules: no open issues")
                if problem:
                    notes.append("house-rules: open issue list: %s" % problem)
        if waiting:
            notes.append("house-rules: " + waiting)
        if notes:
            out["systemMessage"] = " | ".join(notes)
        if out:
            emit(out)
    except Exception as exc:
        emit({"systemMessage": "house-rules: could not list open issues (%s: %s)" % (type(exc).__name__, exc)})
    return 0


def event_autosave():
    """PostToolUse (Write|Edit|NotebookEdit|Bash) on a worktree-agent- branch: after a
    CHECKPOINT_MINUTES stretch with no commit, commit for the subagent; then snapshot the
    worktree to the autosave ref and push it. The same entry records `gh issue create` calls for
    the issue gate (_issues_record), which is why it runs on any branch."""
    try:
        if not _autosave_enabled() and not _issues_enabled() and not _loop_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit({"systemMessage": "house-rules plugin: autosave got an empty payload and did not run for this call."})
            return 0
        issue_notes = _issues_record(payload) if (_issues_enabled() or _loop_enabled()) else []
        issue_notes += _loop_record_labels(payload)
        target = _autosave_target(payload) if _autosave_enabled() else None
        if target is None:
            if issue_notes:
                emit({"systemMessage": " | ".join(issue_notes)})
            return 0
        top, branch, tool, sid = target
        if tool not in _AUTOSAVE_TOOLS or not _dirty_files(top):
            if issue_notes:
                emit({"systemMessage": " | ".join(issue_notes)})
            return 0
        notes = list(issue_notes)
        if _head_age_seconds(top) >= CHECKPOINT_MINUTES * 60:
            sha, done = _wip_commit(top, WIP_CHECKPOINT, sid)
            if sha:
                notes.append("house-rules autosave: %d min passed without a commit on %s, so the "
                             "hook committed %d file(s) as %s: %s."
                             % (CHECKPOINT_MINUTES, branch, len(done), sha, _shown(done)))
        msg = _autosave_snapshot(top, branch, force_push=bool(notes))
        if msg:
            notes.append(msg)
        # One JSON object per hook call: Claude Code parses stdout as a single object, so the
        # trace is the fallback line, never an extra one.
        if notes:
            emit({"systemMessage": " | ".join(notes)})
        else:
            trace("autosave: %s%s saved." % (AUTOSAVE_REF_PREFIX, branch))
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: autosave hit an error (%s: %s) and did not run for this call."
                               % (type(exc).__name__, exc)})
    return 0


def event_commitgate():
    """PreToolUse (Write|Edit|NotebookEdit) on a worktree-agent- branch: once COMMITGATE_THRESHOLD
    files are uncommitted, deny the edit and say commit first. Asked once and ignored (HEAD has not
    moved), commit for the subagent instead and let the edit through. It also carries the issue
    gate (_issues_gate), which applies on any branch of the main session."""
    try:
        if not _autosave_enabled() and not _issues_enabled() and not _loop_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit({"systemMessage": "house-rules plugin: commitgate got an empty payload and did not run for this call."})
            return 0
        if _loop_enabled():
            deny, problem = _loop_gate(payload)
            if deny:
                emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": deny}})
                return 0
            if problem:
                emit({"systemMessage": problem})
        if _issues_enabled():
            deny, problem = _issues_gate(payload)
            if deny:
                emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": deny}})
                return 0
            if problem:
                emit({"systemMessage": problem})
                return 0
        if not _autosave_enabled():
            return 0
        target = _autosave_target(payload)
        if target is None:
            return 0
        top, branch, tool, sid = target
        if tool not in _GATED_TOOLS:
            return 0  # Bash is never gated: it is how the subagent commits
        files = _dirty_files(top)
        counter = _autosave_state_path(top, branch, "denied")
        if len(files) < COMMITGATE_THRESHOLD:
            if os.path.exists(counter):
                os.remove(counter)
            return 0
        head = _ag(top, ["rev-parse", "HEAD"])[1].strip()
        if _autosave_read(counter) == head:
            sha, done = _wip_commit(top, WIP_NOT_COMMITTED, sid)
            os.remove(counter)
            note = _autosave_snapshot(top, branch, force_push=True)
            text = ("house-rules commitgate: the subagent did not commit when asked, so the hook "
                    "committed %d file(s) on %s as %s: %s." % (len(done), branch, sha, _shown(done)))
            emit({"systemMessage": text + (" | " + note if note else "")})
            return 0
        _autosave_write(counter, head)
        reason = (
            "House rules, commit as you go: %d files are uncommitted on %s (%s), so this edit is "
            "blocked until you commit what you have. Run `git add <paths> && git commit -m "
            "\"<type>: <summary>\"` now, then repeat the edit. If you repeat it without committing, "
            "the hook commits everything for you." % (len(files), branch, _shown(files))
        )
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: commitgate hit an error (%s: %s) and did not run for this call."
                               % (type(exc).__name__, exc)})
    return 0


def _autosave_cleanup(top):
    """On a subagent's clean finish, drop its autosave ref locally and on origin. A failure
    message, or None (also None when there is nothing to do)."""
    if not _autosave_enabled():
        return None
    branch = _repo_branch(top)
    if not branch or not branch.startswith(AUTOSAVE_BRANCH_PREFIX) or _dirty_files(top):
        return None
    ref = AUTOSAVE_REF_PREFIX + branch
    had_ref = _ag(top, ["rev-parse", "--verify", "-q", ref], check=False)[0] == 0
    _ag(top, ["update-ref", "-d", ref], check=False)
    pushed = _autosave_read(_autosave_state_path(top, branch, "pushed")).split()
    for kind in ("pushed", "noorigin", "denied"):
        p = _autosave_state_path(top, branch, kind)
        if os.path.exists(p):
            os.remove(p)
    if not had_ref or len(pushed) != 2 or pushed[1] == "-":
        return None  # never reached origin, so there is nothing there to delete
    if _ag(top, ["remote", "get-url", "origin"], check=False)[0] != 0:
        return None
    try:
        _ag(top, ["push", "--quiet", "origin", ":" + ref], timeout=AUTOSAVE_PUSH_TIMEOUT)
    except RuntimeError as exc:
        return "house-rules autosave: could not delete %s on origin (%s); delete it by hand." % (ref, exc)
    return None


def _newest_mtime(top, files):
    newest = 0.0
    for f in files:
        try:
            newest = max(newest, os.path.getmtime(os.path.join(top, f)))
        except OSError:
            continue  # a deleted file has no mtime; the others decide
    return newest


def event_worktreesweep():
    """UserPromptSubmit on the parent (prompts, task notifications, scheduled check-ins): commit
    any subagent worktree left with uncommitted work untouched for CHECKPOINT_MINUTES - the case a
    killed subagent leaves behind, where none of its own hooks will ever run again."""
    import time as _t

    try:
        if not _autosave_enabled():
            return 0
        payload = read_payload()
        try:
            data = json.loads(payload) if payload else {}
        except ValueError:
            data = {}
        root = os.environ.get("CLAUDE_PROJECT_DIR") or (data.get("cwd") if isinstance(data, dict) else "") or os.getcwd()
        rc, out, _e = _ag(root, ["worktree", "list", "--porcelain"], check=False)
        if rc != 0:
            return 0  # not a git repo: no subagent worktrees to sweep
        worktrees, path = [], None
        for line in out.splitlines():
            if line.startswith("worktree "):
                path = line[len("worktree "):]
            elif line.startswith("branch refs/heads/" + AUTOSAVE_BRANCH_PREFIX) and path:
                worktrees.append((path, line[len("branch refs/heads/"):]))
        sid = data.get("session_id", "") if isinstance(data, dict) else ""
        swept, problems = [], []
        now = _t.time()
        for top, branch in worktrees[:SWEEP_MAX_WORKTREES]:
            try:
                files = _dirty_files(top)
                if not files or now - _newest_mtime(top, files) < CHECKPOINT_MINUTES * 60:
                    continue  # clean, or a live subagent is still editing it
                sha, done = _wip_commit(top, WIP_PARENT, sid)
                note = _autosave_snapshot(top, branch, force_push=True)
                swept.append("%s (%s): committed %d file(s) as %s - %s%s"
                             % (top, branch, len(done), sha, _shown(done), " | " + note if note else ""))
            except Exception as exc:
                problems.append("%s (%s): %s" % (top, branch, exc))
        if not swept and not problems:
            return 0
        lines = []
        if swept:
            lines.append("house-rules worktreesweep: subagent work sat uncommitted for %d+ min, so the "
                         "hook committed it: %s." % (CHECKPOINT_MINUTES, "; ".join(swept)))
        if problems:
            lines.append("house-rules worktreesweep: could not check or commit %s." % "; ".join(problems))
        emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": " ".join(lines)}})
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: worktreesweep hit an error (%s: %s) and did not run for this call."
                               % (type(exc).__name__, exc)})
    return 0


# audit — PostToolUse on Agent|Task, its own hooks.json entry. doc-ref 8313 docs/6-decisions/Decisions.md.


def event_audit():
    """PostToolUse (Agent|Task): hand the audit summary + reconcile instruction straight to
    the parent model as additionalContext when a FOREGROUND subagent call returns."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: a subagent tool call returned but "
                    "the PostToolUse payload was empty, so it could not be audited."
                }
            )
            return 0

        status = _field(_RESPONSE_STATUS_RE, payload)
        # #292: a background subagent no longer gets the 5-minute stall-check reminder; its hand-back is
        # still audited when it arrives (userpromptaudit).
        if status != "completed":
            # "async_launched" with autosave off, or an unrecognised shape: genuinely nothing
            # to audit yet, not a failure to report - userpromptaudit picks up a backgrounded
            # call's eventual hand-back.
            return 0

        problems = []
        agent_id = _field(_RESPONSE_AGENT_ID_RE, payload, problems)
        agent_type = (
            _field(_RESPONSE_AGENT_TYPE_RE, payload)
            or _field(_TOOL_INPUT_SUBAGENT_TYPE_RE, payload)
            or "agent type not in payload"
        )
        if not agent_id:
            emit(
                {
                    "systemMessage": "house-rules: a subagent tool call completed but the "
                    "payload carried no agentId, so its transcript could not be located to "
                    "audit."
                }
            )
            return 0

        candidates = _transcript_candidates(payload, agent_id=agent_id)
        found = next((c for c in candidates if os.path.isfile(c)), "")
        if not found:
            emit(
                {
                    "systemMessage": "house-rules: %s (agent %s) finished, but its transcript "
                    "could not be located to audit - tried: %s"
                    % (agent_type, agent_id, ", ".join(candidates) or "(no candidates - not "
                       "enough of session_id/transcript_path in the payload)")
                }
            )
            return 0

        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "house-rules: %s (agent %s) finished (foreground) - %s"
                        % (agent_type, agent_id, _audit_report(found))
                    ),
                }
            }
        )
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the foreground subagent audit hit an "
                "error (%s) and did not run for this call." % type(exc).__name__
            }
        )
    return 0


# userpromptaudit — UserPromptSubmit, its own entry, separate from scope. doc-ref 8313 docs/6-decisions/Decisions.md.


def event_userpromptaudit():
    """UserPromptSubmit: when this turn's prompt IS a background subagent's hand-back
    notification, hand the audit summary + reconcile instruction to the parent model as
    additionalContext - the completion this backgrounded call's own PostToolUse never saw."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        if not payload:
            return 0
        m = _PROMPT_VALUE_RE.search(payload)
        if not m:
            return 0
        prompt_field = m.group(1)
        if not _TASK_NOTIFICATION_RE.search(prompt_field):
            # The ordinary case, every other prompt: nothing to do, and nothing to say -
            # this handler exists for exactly one shape of prompt, not every one.
            return 0
        status_m = _TASK_STATUS_RE.search(prompt_field)
        if not status_m or status_m.group(1) != "completed":
            # A notification for a still-running or failed task carries no finished work to
            # audit yet; a later notification for the same task-id covers it when it does.
            return 0
        id_m = _TASK_ID_RE.search(prompt_field)
        if not id_m:
            emit(
                {
                    "systemMessage": "house-rules: a background subagent hand-back arrived "
                    "with no <task-id>, so its transcript could not be located to audit."
                }
            )
            return 0
        agent_id = id_m.group(1)

        candidates = _transcript_candidates(payload, agent_id=agent_id)
        found = next((c for c in candidates if os.path.isfile(c)), "")
        if not found:
            emit(
                {
                    "systemMessage": "house-rules: background subagent %s finished, but its "
                    "transcript could not be located to audit - tried: %s"
                    % (agent_id, ", ".join(candidates) or "(no candidates)")
                }
            )
            return 0

        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": (
                        "house-rules: subagent %s finished (background) - %s"
                        % (agent_id, _audit_report(found))
                    ),
                }
            }
        )
    except Exception as exc:
        # Silence-plus-systemMessage, never additionalContext and never a non-zero exit -
        # additionalContext built from a half-formed state here could be worse than nothing,
        # and a raise or non-zero exit would erase the user's prompt.
        emit(
            {
                "systemMessage": "house-rules plugin: the background subagent audit hit an "
                "error (%s) and did not run for this call." % type(exc).__name__
            }
        )
    return 0


# ---------------------------------------------------------------------------------------
# handover — Stop. Fails OPEN, loud: never wedge the turn.
# ---------------------------------------------------------------------------------------

HANDOVER_NOTE = (
    "House rules, command handover - check before this turn ends. For every shell command "
    "in this reply, all six must be present: (1) how they get there - the folder as an "
    "absolute path plus the explicit action that opens a prompt in it (navigate to <path> "
    "and open a terminal or PowerShell there), not the working directory named as an aside "
    "on the command; (2) the shell it runs in, named in the prose AND correct as the fence "
    "label - the fence label tells the reader which shell the syntax is for; the command must "
    "not depend on where the prompt is, because the Run button executes in the session's "
    "working directory, not the folder the step names; (3) the exact command, "
    "copy-pasteable, no placeholders, and it runs from anywhere - never a bare command "
    "that assumes the reader is already in the right folder; (4) what the user will see when it works; (5) "
    "UNTESTED: as the first line of the step, above the fence and never inside it, if you "
    "did not run that exact command, in that shell, against those exact paths - running "
    "something similar is not running it; "
    "(6) one numbered step per action whenever the handover is more than a single command - "
    "each step a short bold title, one thing to do, and its own fenced block, never a stack "
    "of commands in one fence. All six go in the step-card format: a --- rule opening and "
    "closing the card, ### Step 1 of N - title as each step's heading, the folder and shell "
    "in prose, one fenced block per step labelled with the shell, and You should see: for the "
    "expected output. If the reply already satisfies all six, stop immediately and "
    "add nothing - do not restate it, do not re-run anything, do not mention this check. If "
    "something is missing, reprint the corrected step in full card shape, introduced by "
    "Replacing step N: - one step, not the whole handover, so the reader ends on something "
    "followable rather than a note about what was wrong above it. Never repeat the whole "
    "answer. If the reply is already correct, end the turn with no commentary at all: a "
    "sentence saying it already carries the six fields, or already complies, is itself the "
    "failure this is guarding against - the user did not ask about the check and should "
    "never learn it ran. A card never announces its own compliance."
)


# Same shape as _COMMAND_FIELD_RE: match the raw JSON slice, escapes included, and search inside
# it. Backticks are not escaped in JSON, so a fenced block survives verbatim in the payload.
_LAST_MESSAGE_FIELD_RE = re.compile(r'"last_assistant_message"\s*:\s*"(?:[^"\\]|\\.)*"')
_LAST_MESSAGE_VALUE_RE = re.compile(r'"last_assistant_message"\s*:\s*"((?:[^"\\]|\\.)*)"')


# The three marks a card cannot be missing: the rule that opens and closes it, the step heading,
# and the expected-output line. A reply carrying all three is already in the shape this check
# exists to produce, so the check has nothing to add - see _reply_needs_card_check.
_CARD_MARKERS = ("---", "###", "You should see:")

# Only a SHELL-labelled fence hands over a command - a fence in another language, or with no
# label at all, is not the thing this check exists to correct. doc-ref 6534 docs/6-decisions/Decisions.md
_SHELL_FENCE_LANGS = ("bash", "sh", "zsh", "shell", "console", "powershell", "pwsh", "ps1", "cmd", "bat", "fish")
_SHELL_FENCE_RE = re.compile(r"```\s*(%s)\b" % "|".join(_SHELL_FENCE_LANGS), re.IGNORECASE)


def _reply_is_already_a_card(reply):
    return all(mark in reply for mark in _CARD_MARKERS)


def _reply_needs_card_check(payload):
    """Three tiers, the same ladder guard uses on its own input.

    Why not firing on a compliant reply is the point, and the cost that trades away:
    docs/architecture.md, "handover is the one deliberate exception". A reply with no
    last_assistant_message at all (an older CLI) still needs the check - a version gap must
    not silently disable it.
    """
    m = _LAST_MESSAGE_FIELD_RE.search(payload)
    if m is None:
        return True
    reply = m.group(0)
    return bool(_SHELL_FENCE_RE.search(reply)) and not _reply_is_already_a_card(reply)


# --- evidence check: independent of the fence gate above ---------------------------------------
# Word-boundary catches these forms; it naturally MISSES "untested"/"unverified" ("un" + word has
# no boundary between them, so \btested\b never matches inside "untested") without extra logic.
_CLAIM_WORD_RE = re.compile(
    r"\b(works|working|fixed|passes|passing|passed|verified|tested|confirmed|succeeded)\b",
    re.IGNORECASE,
)
# Explicit negation forms word-boundary alone cannot catch: "not tested", "haven't verified".
_NEGATION_RE = re.compile(
    r"\b(not|never|no longer|hasn't|haven't|didn't|isn't|wasn't|won't|can't|cannot|couldn't)\b",
    re.IGNORECASE,
)
# A reply that quotes real output does not need the reminder - a fenced block (any language),
# or a line shaped like real captured output: this repo's own RESULT: PASS/FAIL convention, an
# exit code, or a test runner's "N passed" summary line. Deliberately NOT the bare word "passed"
# on its own - that would treat the prose claim "the tests passed" as its own evidence.
_EVIDENCE_QUOTE_RE = re.compile(
    r"(?m)```|RESULT:\s*(PASS|FAIL)|\bexit\s+0\b|^\s*\d+\s+passed\b", re.IGNORECASE
)


def _claim_words(text):
    """Claim words found in text, each checked against the ~25 chars right before it for a
    negation cue - a window, not a full-sentence parse, same posture as every other regex here."""
    found = []
    for m in _CLAIM_WORD_RE.finditer(text or ""):
        window = text[max(0, m.start() - 25) : m.start()]
        if _NEGATION_RE.search(window):
            continue
        found.append(m.group(1).lower())
    return found


# #92: "it can't be done" is a claim of fact too, and the one most often made from memory. Only
# phrasings that assert impossibility or absence - a bare "can't" is everywhere in ordinary prose.
_IMPOSSIBLE_RE = re.compile(
    r"\b(can(?:'|no)t be done|can not be done|(?:is|isn't|is not|not) (?:possible|supported)|"
    r"impossible|no way to|does(?:n't| not) (?:support|exist)|"
    r"there(?:'s| is) no (?:way|option|setting|flag|api|command))\b",
    re.IGNORECASE,
)
# "is possible" / "is supported" are matched above only to be dropped here: the negative forms
# are the claim this catches.
_POSITIVE_FORM_RE = re.compile(r"^is (possible|supported)$", re.IGNORECASE)


_QUOTE_CHARS = "\"'`\u201c\u2018"


def _is_quoted(text, start):
    """A phrase opening right after a quote mark is being talked about, not asserted."""
    return start > 0 and text[start - 1] in _QUOTE_CHARS


def _impossibility_claims(text):
    found = []
    for m in _IMPOSSIBLE_RE.finditer(text or ""):
        if _is_quoted(text, m.start()):
            continue
        phrase = m.group(1).lower()
        if _POSITIVE_FORM_RE.match(phrase):
            continue
        found.append(phrase)
    return found


# #89: a disclosure that something was not checked. Since #247 the detector lives in the shared
# writing checker (scripts/clarity.py), which also tells a list label ("Not checked:") from a
# disclosure.
def _unreasoned_not_checked(text):
    return clarity.unreasoned_not_checked(text) if clarity else []


def _is_genuine_user_message(record):
    """A real human turn - not a tool_result carrier, not Stop hook feedback, not a background
    task's <task-notification> hand-back, and (when the field is present) not attributed to a
    non-human origin. "Genuine user message" definition: doc-ref 25b2 docs/6-decisions/Decisions.md
    """
    if not isinstance(record, dict) or record.get("type") != "user":
        return False
    msg = record.get("message")
    if not isinstance(msg, dict):
        return False
    content = msg.get("content")
    if isinstance(content, list):
        if content and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        text = " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    elif isinstance(content, str):
        text = content
    else:
        return False
    if re.match(r"^\s*Stop hook feedback", text or "", re.IGNORECASE):
        return False
    if "<task-notification>" in (text or ""):
        return False
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    return True


_TURN_CACHE = {}


def _records_since_last_user_message(transcript_path):
    """(records after the last genuine user message, None) or (None, detail) when that cannot
    be told - an unreadable transcript, or no genuine user message in it at all."""
    records, _user, detail = _load_turn(transcript_path)
    return records, detail


def _last_user_text(transcript_path):
    """The text of the last genuine user message, or "" when there is none to read."""
    _records, user, _detail = _load_turn(transcript_path)
    if not user:
        return ""
    content = (user.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _load_turn(transcript_path):
    """(records after the last genuine user message, that message, None), or (None, None,
    detail). Read once per process: the Stop checks each need it, and a long session's
    transcript is megabytes."""
    if transcript_path not in _TURN_CACHE:
        _TURN_CACHE[transcript_path] = _read_turn(transcript_path)
    return _TURN_CACHE[transcript_path]


def _read_turn(transcript_path):
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
    except OSError as exc:
        return None, None, "could not read the transcript (%s)" % type(exc).__name__

    records = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            records.append(None)
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            records.append(None)

    last_user_idx = None
    for i, rec in enumerate(records):
        if rec is not None and _is_genuine_user_message(rec):
            last_user_idx = i
    if last_user_idx is None:
        return None, None, "no genuine user message found in the transcript"
    return records[last_user_idx + 1 :], records[last_user_idx], None


def _turn_tool_uses(records):
    """Every tool_use block the assistant made in `records`, in order."""
    for rec in records:
        if not isinstance(rec, dict) or rec.get("type") != "assistant":
            continue
        content = (rec.get("message") or {}).get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block


def _tool_use_since_last_user_message(transcript_path):
    """(True/False/None, detail). None means could not tell - an unreadable transcript, or no
    genuine user message found in it at all."""
    records, detail = _records_since_last_user_message(transcript_path)
    if records is None:
        return None, detail
    for _block in _turn_tool_uses(records):
        return True, None
    return False, None


def _written_since_last_user_message(transcript_path):
    """(file paths Write/Edit/NotebookEdit touched this turn, None) or (None, detail)."""
    records, detail = _records_since_last_user_message(transcript_path)
    if records is None:
        return None, detail
    paths = []
    for block in _turn_tool_uses(records):
        if block.get("name") not in _AUDIT_WRITE_TOOLS:
            continue
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        fp = inp.get("file_path") or inp.get("notebook_path")
        if fp and fp not in paths:
            paths.append(fp)
    return paths, None


def _evidence_note(claim_words, impossible_words=()):
    kinds = []
    if claim_words:
        kinds.append("claims success (%s)" % ", ".join(sorted(set(claim_words))))
    if impossible_words:
        kinds.append("says something cannot be done or does not exist (%s)"
                     % ", ".join(sorted(set(impossible_words))))
    return (
        "House rules, evidence before claims: this reply %s, but no tool ran since your last "
        "real message and the reply does not quote any command output. Before this turn ends, "
        "either run the check and quote its real output, or restate the claim as untested and "
        "say why. Reasoning, docs and memory are not a check." % " and ".join(kinds)
    )


def _not_checked_note(phrases):
    return (
        "House rules, evidence before claims: this reply says something was not checked (%s) "
        "without saying why it could not be. Checking is the default, not an offer. If the check "
        "can run here and is not prohibitively expensive, run it now and report its real "
        "result; leave it unchecked only when it cannot run, and say in the same sentence what "
        "stops it." % ", ".join(sorted(set(phrases)))
    )


# --- parity (#90/#87) and visual (#88/#96) checks --------------------------------------------
# Wording that re-creates existing behaviour rather than editing it. "replace" and "move to" are
# left out on purpose: they are everyday edit words, and a false positive at Stop costs a whole
# continuation.
_PARITY_RE = re.compile(
    r"\b(port(?:ing|ed)?|rewrit\w*|rebuild\w*|re-?do|from scratch|restructur\w*|"
    r"split (?:\w+ ){0,2}into|merg\w* (?:\w+ ){0,2}into|reorgani[sz]\w*|consolidat\w*|"
    r"migrat\w*|rework\w*|v2)\b",
    re.IGNORECASE,
)
# A reply or plan that already accounts for what was kept and dropped.
_PARITY_ACCOUNTED_RE = re.compile(
    r"parity|\bkeep\b.{0,400}\bdrop|\bkept\b.{0,400}\bdropped|nothing (?:was )?dropped|"
    r"no (?:features? |behaviou?rs? )?(?:were |was )?(?:dropped|lost|removed)",
    re.IGNORECASE | re.DOTALL,
)
_VISUAL_EXT_RE = re.compile(
    r"\.(css|scss|sass|less|html?|jsx|tsx|vue|svelte|astro|uss|uxml|xaml|unity|prefab)$", re.IGNORECASE
)
_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|bmp)$", re.IGNORECASE)
_SCREENSHOT_WORD_RE = re.compile(r"screenshot|playwright|puppeteer|capture|browser|computer", re.IGNORECASE)

SCOPE_PARITY_CLAUSE = (
    "\n- This reads like re-creating existing behaviour (a port, rewrite, restructure or "
    "migration). Inventory what the original does from its code first - keep/change/drop, "
    "shown before building - verify against the original, and name every drop."
)


# --- plain summary first (#98) -------------------------------------------------------------
# A reply reporting finished work opens with a plain summary a person can read on a phone. What
# can be checked from text: the opening is not code, not a table, not a pile of `names`, and no
# table anywhere is too wide for a phone screen. Measured on this repo's own session before
# shipping: the 4 real end-of-work replies all passed.
PLAIN_SUMMARY_MIN_CHARS = 600
PLAIN_OPENING_CHARS = 500
PLAIN_OPENING_MAX_CODE_SPANS = 3
PLAIN_MAX_TABLE_COLUMNS = 3
_GIT_COMMIT_OR_PUSH_RE = re.compile(r"\bgit\b[^|;&\n]*\b(commit|push)\b")
_MD_FENCE_RE = re.compile(r"```")
_MD_TABLE_ROW_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")
_MD_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")
_MD_LEADING_HEADING_RE = re.compile(r"^\s*#+ .*\n+")


def _plain_summary_enabled():
    return os.environ.get("HOUSE_RULES_PLAIN_SUMMARY", "on").strip().lower() not in _TOGGLE_OFF


def _plain_summary_problems(reply):
    """What stops this reply's opening reading as a plain summary on a phone - [] when nothing
    does, or when the reply is too short to need one."""
    if len(reply or "") < PLAIN_SUMMARY_MIN_CHARS:
        return []
    body = _MD_LEADING_HEADING_RE.sub("", reply, count=1)
    opening = body[:PLAIN_OPENING_CHARS].split("\n\n")[0]
    problems = []
    if _MD_FENCE_RE.search(opening):
        problems.append("it opens with a code block")
    if _MD_TABLE_ROW_RE.search(opening):
        problems.append("it opens with a table")
    spans = len(_MD_CODE_SPAN_RE.findall(opening))
    if spans > PLAIN_OPENING_MAX_CODE_SPANS:
        problems.append("its first paragraph carries %d code names" % spans)
    widest = max((l.count("|") - 1 for l in reply.splitlines() if _MD_TABLE_ROW_RE.match(l)), default=0)
    if widest > PLAIN_MAX_TABLE_COLUMNS:
        problems.append("it has a %d-column table, too wide for a phone" % widest)
    return problems


# #226: a reply of LONG_REPLY_WORDS words or more that links no page or picture gets a reminder to
# move the detail onto a page and end on one question. Code blocks are not counted as words.
# #282: the threshold is 160 words or more (it was over 200).
LONG_REPLY_WORDS = 160
_PAGE_LINK_RE = re.compile(r"claude\.ai/(?:code/)?artifact/|!\[[^\]]*\]\(|\.html\b", re.IGNORECASE)
_MD_FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_PAGE_ART_RE = re.compile(r"claude\.ai/(?:code/)?artifact/|!\[[^\]]*\]\(", re.IGNORECASE)
_HTML_PATH_RE = re.compile(r"""(?:file:///)?[^\s()<>\[\]"'`]+?\.html?""", re.IGNORECASE)


def _html_paths(reply, cwd):
    """#329: every .html/.htm path in the reply as (path as written, absolute normcased path or None
    for a bare file name with no folder)."""
    out = []
    for m in _HTML_PATH_RE.finditer(reply):
        raw = m.group(0)
        p = urllib.parse.unquote(raw[8:]) if raw.lower().startswith("file:///") else raw
        if raw.lower().startswith("file:///"):
            p = p if re.match(r"[A-Za-z]:", p) else "/" + p
        if "/" not in p and "\\" not in p:
            out.append((p, None))
            continue
        out.append((p, os.path.normcase(os.path.abspath(os.path.join(cwd, p)))))
    return out


def _inside(path, cwd):
    c = os.path.normcase(os.path.abspath(cwd))
    return path == c or path.startswith(c + os.sep)


def _reply_links_page(reply, cwd):
    """#329: True when the reply links a page the app can open: an artifact link, a picture, or an
    .html path inside the session folder cwd. A bare .html file name counts only when the reply has no
    .html path at all, so the text of [x.html](../elsewhere/x.html) can't pass for the link. Empty cwd:
    any .html counts."""
    if not reply:
        return False
    if _PAGE_ART_RE.search(reply):
        return True
    if not cwd:
        return bool(_PAGE_LINK_RE.search(reply))
    found = _html_paths(reply, cwd)
    paths = [a for _, a in found if a is not None]
    if paths:
        return any(_inside(a, cwd) for a in paths)
    return bool(found)


def _outside_page_links(reply, cwd):
    """#329: the .html paths in the reply that sit outside the session folder cwd."""
    if not cwd:
        return []
    return [p for p, a in _html_paths(reply, cwd) if a is not None and not _inside(a, cwd)]
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019-]*")


def _long_reply_words(reply, cwd=""):
    """The word count when the reply is too long and links no page or picture, else 0."""
    if not reply or _reply_links_page(reply, cwd):
        return 0
    words = len(_WORD_RE.findall(_MD_FENCED_BLOCK_RE.sub("", reply)))
    return words if words >= LONG_REPLY_WORDS else 0


def _long_reply_note(words):
    return (
        "House rules, show don't tell: this reply is %d words and links no page or picture. At %d words or more, "
        "the detail belongs on a page: move it there, keep the reply to a plain summary, the link, and "
        "numbered steps for what aj needs to do, and end on one question or next step." % (words, LONG_REPLY_WORDS)
    )


def _clear_writing_enabled():
    return os.environ.get("HOUSE_RULES_CLEAR_WRITING", "on").strip().lower() not in _TOGGLE_OFF


# #309 (incident 8 of #303): writing kinds that only report, to aj, until the restructure. The bare-reference
# check read "the option I suggested" as a bare "option I" and asked for the reply to be resent, twice in a row.
_WRITING_REPORT_ONLY = ("bare-ref",)


# #249: a page goes past the editor helper before aj reads it; a long reply does too only with
# HOUSE_RULES_EDITOR=on (#325: a long chat reply forcing a subagent run cost too many tokens).
EDITOR_NOTE = (
    "House rules, write it so nothing is left to guess: %s, and no @house-rules:editor helper ran this "
    "turn. Hand the text (or the page's path) to @house-rules:editor (Agent tool, subagent_type "
    "house-rules:editor), apply its rewrites, then send the result. HOUSE_RULES_CLEAR_WRITING=off "
    "turns this off; only pages are checked unless HOUSE_RULES_EDITOR=on adds long replies."
)


def _pages_changed_this_turn(transcript_path, cwd):
    """(pages, problem): docs/plans/*.html pages modified since aj's last message, however they
    were written. No pages when the project has no docs/plans folder or the message carries no
    timestamp; a timestamp that can't be read is reported as the problem."""
    import datetime
    _records, user, _detail = _load_turn(transcript_path)
    stamp = (user or {}).get("timestamp")
    top = _issues_locate(cwd)[0] or cwd
    plans = os.path.join(top, "docs", "plans")
    if not stamp or not os.path.isdir(plans):
        return [], None
    try:
        since = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        return [], "house-rules: could not read aj's message time (%s), so pages written by a shell command were not checked." % exc
    pages = [n for n in os.listdir(plans) if n.lower().endswith((".html", ".htm"))]
    if _common_git_dir(top):
        # #284: a clone, checkout or merge sets every file's time, so in a repository a page counts only
        # when git shows it new, edited, or in a commit made since aj's message.
        try:
            _rc, status, _e = _ag(top, ["status", "--porcelain", "--untracked-files=all", "--", "docs/plans"])
            rc, log, err = _ag(top, ["log", "--since=@%d" % int(since), "--no-merges", "--name-only",
                                     "--format=", "--", "docs/plans"], check=False)
            if rc != 0:
                if "does not have any commits" not in err:  # a new repository has no log yet; status covers it
                    raise RuntimeError("git log failed: %s" % (err or "exit %d" % rc))
                log = ""
        except RuntimeError as exc:
            return [], "house-rules: git could not list this turn's pages (%s), so they were not checked." % exc
        touched = {os.path.basename(line[3:].strip().strip('"')) for line in status.splitlines() if len(line) > 3}
        try:
            # During an uncommitted merge, status lists every page the other branch brought in. A page
            # still identical to MERGE_HEAD's copy came from the merge, not this turn, so it does not count.
            if _ag(top, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], check=False)[0] == 0:
                _rc, differ, _e = _ag(top, ["diff", "--name-only", "MERGE_HEAD", "--", "docs/plans"])
                differ = {os.path.basename(line.strip()) for line in differ.splitlines() if line.strip()}
                touched = {n for n in touched if n in differ}
        except RuntimeError as exc:
            return [], "house-rules: git could not compare pages with the merge (%s), so they were not checked." % exc
        touched |= {os.path.basename(line.strip()) for line in log.splitlines() if line.strip()}
        return sorted(os.path.join(plans, n) for n in pages if n in touched), None
    return sorted(os.path.join(plans, n) for n in pages if os.path.getmtime(os.path.join(plans, n)) >= since), None


def _editor_enabled():
    # #325: off unless set to something that is not an "off" value, i.e. "on".
    return os.environ.get("HOUSE_RULES_EDITOR", "off").strip().lower() not in _TOGGLE_OFF


def _editor_owed(written, tool_uses, reply):
    """What makes the editor helper owed this turn ("" when nothing does, or when it ran)."""
    for block in tool_uses:
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        if block.get("name") in ("Agent", "Task") and str(inp.get("subagent_type", "")).endswith("editor"):
            return ""
    pages = [os.path.basename(p) for p in written if _PLANS_PAGE_RE.search(str(p).replace("\\", "/"))]
    if pages:
        return "this turn wrote the page %s" % ", ".join(sorted(set(pages)))
    if not _editor_enabled():  # #325: the long-reply trigger needs HOUSE_RULES_EDITOR=on
        return ""
    words = len(_WORD_RE.findall(_MD_FENCED_BLOCK_RE.sub("", reply or "")))
    if words >= LONG_REPLY_WORDS:
        return "this reply is %d words" % words
    return ""


def _writing_note(not_checked, writing, long_words):
    """#248: one end-of-reply note for every writing finding, in place of separate notes."""
    lines = []
    if not_checked:
        lines.append(_not_checked_note(not_checked))
    if writing:
        lines.append(
            "House rules, write it so nothing is left to guess: aj has already seen this "
            "reply, so send only the corrected sentences, not the whole reply again:\n" + "\n".join(
                "- \"%s\": %s" % (phrase, why) for _kind, phrase, why in writing[:12])
            + ("\n(and %d more)" % (len(writing) - 12) if len(writing) > 12 else "")
            + "\nCount what can be counted, name what you point at, say each thing once, and give a "
            "reason in the same sentence for anything that genuinely can't be measured. "
            "HOUSE_RULES_CLEAR_WRITING=off turns this off.")
    if long_words:
        lines.append(_long_reply_note(long_words))
    return "\n\n".join(lines)


def _plain_summary_note(problems):
    return (
        "House rules, plain summary first: this reply reports finished work, but %s. Rewrite it "
        "so it opens with a short plain-English summary - what is done, what it changes for the "
        "user, what is waiting on them - before any technical detail, in short paragraphs that "
        "read on a phone, with no table wider than three columns and jargon glossed on first "
        "use. Keep the technical detail; put it after the summary." % "; ".join(problems)
    )


def _parity_enabled():
    return os.environ.get("HOUSE_RULES_PARITY", "on").strip().lower() not in _TOGGLE_OFF


def _visual_check_enabled():
    return os.environ.get("HOUSE_RULES_VISUAL_CHECK", "on").strip().lower() not in _TOGGLE_OFF


def _parity_report_note(word):
    # #309 (incident 5 of #303): report only until the restructure. The demand for an inventory and an
    # issue per drop fired on a one-entry Decisions.md append, and three times on audit-notes turns.
    return (
        "House rules, re-creating existing behaviour (report only, #309): aj's message reads like a %s "
        "and this turn wrote files, but the reply names nothing kept or dropped. Nothing is required "
        "this turn; the note is kept as evidence for the restructure." % word.lower()
    )


def _looked_at_result(tool_uses):
    """True when the turn captured or read an image of the result."""
    for block in tool_uses:
        name = block.get("name") or ""
        inp = block.get("input") if isinstance(block.get("input"), dict) else {}
        if _SCREENSHOT_WORD_RE.search(name):
            return True
        if name == "Read" and _IMAGE_EXT_RE.search(inp.get("file_path") or ""):
            return True
        if name in _AUDIT_COMMAND_TOOLS and _SCREENSHOT_WORD_RE.search(inp.get("command") or ""):
            return True
    return False


def _visual_note(files):
    return (
        "House rules, a visual change is checked by looking at it: this turn changed %s, but "
        "nothing in it captured or looked at the result. Before this turn ends, screenshot the "
        "same flow before (the committed version) and after, plus any flow the change adds, and "
        "say what the images show. If nothing can render here, say what stops it and name the "
        "screenshot the user should take." % ", ".join(files[:6])
    )


# #256: the checkpoint table. Each row is (moment, rule name, check function, "block" or "remind").
# A check takes the context dict event_handover builds and returns the exact fix when the rule is
# missed, else "". A "block" row at "reply ends" stops the reply once; on the retry
# (stop_hook_active) it only reports, the same safety event_subagentcommit uses.
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S", re.MULTILINE)
_OPTION_LABEL_RE = re.compile(r"\boption\s+(?:[A-Za-z]|\d+)\b|\(\s*[A-Ca-c1-3]\s*\)", re.IGNORECASE)
_PICK_QUESTION_RE = re.compile(r"\b(approve|approval|pick|choose|which|sign off|go ahead)\b", re.IGNORECASE)
_NO_PAGE_RE = re.compile(r"\bno\s+page\b", re.IGNORECASE)


def _offers_choices(reply):
    """True when a reply offers named options or lays out a plan for aj to approve. Conservative:
    it needs a closing question, plus either two labelled options in it or a list of 3+ items
    earlier with a question asking aj to pick or approve."""
    text = _MD_FENCED_BLOCK_RE.sub("", reply or "").strip()
    if not text.endswith("?"):
        return False
    final = text.split("\n\n")[-1] if "\n\n" in text else text.splitlines()[-1]
    if len({m.group(0).lower() for m in _OPTION_LABEL_RE.finditer(text)}) >= 2:
        return True
    items = _LIST_ITEM_RE.findall(text[:len(text) - len(final)] if final else text)
    return len(items) >= 3 and bool(_PICK_QUESTION_RE.search(final))


def _page_escape(ctx):
    """True when aj's own genuine message says "no page". A helper's hand-back never counts."""
    text = ctx.get("user_text") or ""
    return bool(_NO_PAGE_RE.search(text)) and not _is_relayed_prompt(text)


def _check_page(ctx):
    if _page_escape(ctx):
        return ""
    reply = ctx.get("reply") or ""
    cwd = ctx.get("cwd") or ""
    if _reply_links_page(reply, cwd):
        return ""
    out = _outside_page_links(reply, cwd)
    if out:
        return ("%s is outside this session's folder %s, so the app cannot open it: copy it into "
                "%s/docs/plans/ and link the copy" % (out[0], cwd, cwd))
    if ctx.get("long_words") or _offers_choices(reply):
        return ("put the detail on a page: write a content.json, run `python3 %s build <content.json>` "
                "and link the page it makes in the reply"
                % os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_page.py"))
    return ""


def _check_editor(ctx):
    if _page_escape(ctx) or not ctx.get("editor_owed"):
        return ""
    return ("hand the text to @house-rules:editor (Agent tool, subagent_type house-rules:editor), "
            "apply its rewrites, then send the reply (%s)" % ctx["editor_owed"])


def _check_evidence(ctx):
    if not ctx.get("needs_evidence"):
        return ""
    return "run the check and quote its real output, or restate the claim as untested and say why"


def _check_commit(ctx):
    if not ctx.get("uncommitted"):
        return ""
    return "commit %s on your own branch" % ", ".join(ctx["uncommitted"][:8])


def _check_plain(ctx):
    if not ctx.get("plain_problems"):
        return ""
    return "open with a short plain-English summary (%s)" % "; ".join(ctx["plain_problems"])


# --- pagecheck (#257): a handover page must come from make_page.py -------------------------
# PreToolUse on Write and Artifact. The two rows below sit in CHECKPOINTS so the list shows every
# moment; only "reply ends" rows run at Stop, so these checks do nothing there (pagecheck acts).
PAGE_MARK_RE = re.compile(r"<!--\s*house-rules make_page\b")
_PAGE_EXT = (".html", ".htm")
_PAGE_SKIP_ACTIONS = {"read", "list", "open", "delete", "view", "get", "ls", "remove"}
_PAGE_DENY = (
    "House rules, page check: %s is a hand-written page - it has no house-rules make_page mark. "
    "Pages are built, not typed. Write the content file, then run: python3 %s build <content.json> "
    "and use the page it builds. HOUSE_RULES_LOOP=off turns this check off."
)


def _page_note(text):
    emit({"systemMessage": "house-rules page check: " + text})


def _page_in_plans(path):
    parts = [p for p in re.split(r"[\\/]+", path) if p]
    return any(parts[i] == "docs" and parts[i + 1] == "plans" for i in range(len(parts) - 1))


def _page_deny(page):
    script = os.path.join(_plugin_root(), "scripts", "make_page.py")
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": _PAGE_DENY % (page, script)}})


def _page_candidates(ti):
    out = []
    fp = ti.get("file_path")
    if isinstance(fp, str) and fp:
        out.append(fp)
    files = ti.get("files")
    vals = list(files.values()) if isinstance(files, dict) else (files if isinstance(files, list) else [])
    out.extend(v for v in vals if isinstance(v, str) and v and v not in out)
    return out


def event_pagecheck():
    try:
        if not _loop_enabled():
            return 0
        payload = read_payload()
        data = json.loads(payload) if payload else {}
        ti = data.get("tool_input") if isinstance(data, dict) else None
        if not isinstance(ti, dict):
            _page_note("the call carried no tool_input, so the check could not run; the call is allowed.")
            return 0
        tool = str(data.get("tool_name") or "")
        if tool == "Write":
            fp = ti.get("file_path")
            if not (isinstance(fp, str) and fp.lower().endswith(_PAGE_EXT) and _page_in_plans(fp)):
                return 0  # not a docs/plans page: nothing to check, nothing to say
            if PAGE_MARK_RE.search(str(ti.get("content") or "")):
                return 0
            _page_deny(fp)
            return 0
        # Artifact (or any other tool the matcher routes here)
        action = str(ti.get("action") or ti.get("command") or ti.get("operation") or "").lower()
        if action in _PAGE_SKIP_ACTIONS:
            _page_note("skipped, the Artifact call is a %s action, not a page save." % action)
            return 0
        if ti.get("asset") is True:
            _page_note("skipped, the Artifact call is an asset upload, not a page.")
            return 0
        cands = _page_candidates(ti)
        pages = [c for c in cands if c.lower().endswith(_PAGE_EXT)]
        if not pages:
            if ti.get("type") or ti.get("artifact_type"):
                _page_note("skipped, the Artifact input is the data file of a typed artifact, not an HTML page.")
            else:
                _page_note("skipped, the Artifact input names no HTML file (%s)."
                           % (", ".join(cands) or "no file path"))
            return 0
        for page in pages:
            try:
                with open(page, encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4096)
            except OSError as exc:
                _page_note("could not read %s (%s), so the check did not run; the publish is allowed."
                           % (page, type(exc).__name__))
                continue
            if not PAGE_MARK_RE.search(head):
                _page_deny(page)
                return 0
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the page check hit an error (%s: %s) and did not "
                               "run for this call; the call is allowed." % (type(exc).__name__, exc)})
    return 0


def _check_page_saved(ctx):
    return ""  # runs as the PreToolUse hook event_pagecheck, never at Stop


_QA_ARTIFACT_RE = re.compile(r"https://claude\.ai/artifact/\S+|claude\.ai/code/artifact/\S+", re.IGNORECASE)


def _record_qa_link(ctx):
    """True (and qa_page_linked recorded) when the reply links the QA page. Also used on a retry."""
    page, reply = ctx.get("qa_page") or "", ctx.get("reply") or ""
    cwd = ctx.get("cwd") or ""
    in_reply = page in reply or os.path.basename(page) in reply
    if page and cwd and in_reply:  # #329: the page counts only when its path opens inside the folder
        in_reply = _inside(os.path.normcase(os.path.abspath(os.path.join(cwd, page))), cwd)
    if not (page and (in_reply or _QA_ARTIFACT_RE.search(reply))):
        return False
    state, problem = _loop_read(ctx["qa_git_dir"])
    if problem:
        raise OSError(problem)
    state["qa_page_linked"] = True
    _loop_write(ctx["qa_git_dir"], state)
    return True


def _check_qa_page(ctx):
    """#269: in QA the build is handed over with a make_page.py QA page, linked in a reply. Not
    skipped by "no page": a QA page is mandatory."""
    if ctx.get("qa_stage") != "qa" or ctx.get("qa_linked"):
        return ""
    page = ctx.get("qa_page") or ""
    if _record_qa_link(ctx):
        return ""
    missing = "the QA page is built but not linked in the reply" if page else "no QA page is built yet"
    return ("%s: build it with `python3 %s build docs/plans/<name>-qa.page.json`, where the content file has a "
            "`qa` block (feature, base, unverified, files), then link the page in the reply"
            % (missing, os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_page.py")))


CHECKPOINTS = [
    ("page saved", "page built", _check_page_saved, "block"),
    ("page published", "page built", _check_page_saved, "block"),
    ("reply ends", "page", _check_page, "report"),  # #309: report only until the restructure
    ("reply ends", "editor", _check_editor, "block"),
    ("reply ends", "evidence", _check_evidence, "block"),
    ("reply ends", "commit", _check_commit, "block"),
    ("reply ends", "plain summary", _check_plain, "block"),
    ("reply ends", "qa page", _check_qa_page, "block"),
]

CHECKPOINT_RULES = {
    "page built": "A handover page is built by make_page.py, never typed by hand.",
    "page": "A reply that offers choices, lays out a plan, or runs to %d words or more links a page." % LONG_REPLY_WORDS,
    "editor": "A page goes past @house-rules:editor before aj reads it; a long reply too when HOUSE_RULES_EDITOR=on.",
    "evidence": "A success claim needs a tool run and its quoted output behind it.",
    "commit": "Files a turn writes are committed on your own branch before it ends.",
    "qa page": "In QA, the build is handed to aj with a QA page built by make_page.py, linked in a reply.",
    "plain summary": "A reply reporting finished work opens with a short plain-English summary.",
}


def _missed_checkpoints(ctx):
    """[(rule name, fix)] for every blocking checkpoint at 'reply ends' that the reply misses."""
    if not _loop_enabled():
        return []
    return [(name, fix) for moment, name, fn, mode in CHECKPOINTS
            if moment == "reply ends" and mode == "block" for fix in [fn(ctx)] if fix]


def _checkpoint_reason(missed):
    lines = ["House rules, the reply is not done yet. It misses %d checkpoint%s:" % (
        len(missed), "" if len(missed) == 1 else "s")]
    for name, fix in missed:
        lines.append("- %s: %s Fix: %s." % (name, CHECKPOINT_RULES[name], fix))
    lines.append("Fix these and send only what changed, not the whole reply again. A missing page blocks every retry "
                 "until the reply links one; the other checks block once. HOUSE_RULES_LOOP=off turns it off.")
    return "\n".join(lines)


# #283: the page checkpoint keeps blocking on the retry until the reply links a page. aj's pick on the
# automatic-pages build plan: after PAGE_BLOCK_LIMIT blocks in a row the reply goes through with a note,
# so a broken page builder can't loop a session with nobody watching.
PAGE_BLOCK_LIMIT = 3
PAGE_BLOCKS_FILE = "page-blocks.json"


def _page_blocks_path(cwd, session_id):
    """In the common git directory, so worktrees share it; outside a repository, a session-keyed temp file."""
    cd = _common_git_dir(cwd)
    if cd:
        return os.path.join(cd, "house-rules", PAGE_BLOCKS_FILE)
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-page-blocks-%s.json" % safe)


def _page_blocks(path, session_id, mark, change=None):
    """Page blocks in a row for this session since aj's message `mark` (a new message starts again at 0).
    change "bump" adds one block, "clear" resets the count; either saves the file. Raises OSError or
    ValueError when the file can't be read or written, and the caller reports it."""
    data = json.loads(_read_text(path)) if os.path.isfile(path) else {}
    if not isinstance(data, dict):
        raise ValueError("%s is not a JSON object" % path)
    entry = data.get(session_id) if isinstance(data.get(session_id), dict) else {}
    count = entry.get("count", 0) if entry.get("mark") == mark else 0
    if change:
        count = count + 1 if change == "bump" else 0
        data[session_id] = {"mark": mark, "count": count}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    return count


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

    # The evidence check is independent of the fence gate above - a reply can claim success
    # with no fence in it at all.
    needs_evidence = False
    evidence_words = []
    impossible_words = []
    not_checked = []
    could_not_tell = None
    vm = _LAST_MESSAGE_VALUE_RE.search(payload)
    if vm is not None:
        try:
            reply_text = json.loads('"%s"' % vm.group(1))
        except ValueError:
            reply_text = vm.group(1)
        claims = _claim_words(reply_text)
        impossible = _impossibility_claims(reply_text)
        not_checked = _unreasoned_not_checked(reply_text)
        if (claims or impossible) and not _EVIDENCE_QUOTE_RE.search(reply_text):
            transcript_path = _field(_TRANSCRIPT_RE, payload)
            if not transcript_path:
                could_not_tell = "the Stop payload carried no transcript_path"
            else:
                has_tool, detail = _tool_use_since_last_user_message(transcript_path)
                if has_tool is None:
                    could_not_tell = detail
                elif has_tool is False:
                    needs_evidence = True
                    evidence_words = claims
                    impossible_words = impossible

    # The commit check, independent of both: a turn that wrote files and left them uncommitted
    # gets told at the end of that turn, whatever the reply says. Its "could not tell" is its
    # own line - it must never be mistaken for the evidence check's.
    uncommitted = []
    commit_could_not_tell = None
    if _commit_check_enabled():
        transcript_path = _field(_TRANSCRIPT_RE, payload)
        if transcript_path:
            written, detail = _written_since_last_user_message(transcript_path)
            if written:
                try:
                    uncommitted = _uncommitted_among(
                        written, os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
                    )
                except Exception as exc:
                    commit_could_not_tell = "%s: %s" % (type(exc).__name__, exc)
            elif written is None:
                commit_could_not_tell = detail

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
            written_now = []
            committed_now = False
            for block in _turn_tool_uses(turn_records):
                inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                if block.get("name") in _AUDIT_WRITE_TOOLS:
                    fp = inp.get("file_path") or inp.get("notebook_path")
                    if fp and fp not in written_now:
                        written_now.append(fp)
                elif block.get("name") in _AUDIT_COMMAND_TOOLS and _GIT_COMMIT_OR_PUSH_RE.search(inp.get("command") or ""):
                    committed_now = True
            if (written_now or committed_now) and _plain_summary_enabled() and vm is not None:
                plain_problems = _plain_summary_problems(reply_text)
            if written_now and _parity_enabled():
                pm = _PARITY_RE.search(_last_user_text(transcript_path))
                reply_for_parity = reply_text if vm is not None else ""
                if pm and not _PARITY_ACCOUNTED_RE.search(reply_for_parity):
                    parity_word = pm.group(1)
            if _clear_writing_enabled():
                # A page written by a shell command never passes the Write hook (found in the real
                # run, #250), so pages changed since aj's message are checked here too.
                changed, page_problem = _pages_changed_this_turn(transcript_path, _payload_cwd(payload))
                if page_problem:
                    trace_lines_early.append(page_problem)
                shell_pages = [pg for pg in changed if pg not in written_now]
                for pg in shell_pages:
                    note = _page_writing_note(pg)
                    if note:
                        shell_page_notes.append(note)
                editor_owed = _editor_owed(written_now + shell_pages, list(_turn_tool_uses(turn_records)),
                                           reply_text if vm is not None else "")
            if written_now and _visual_check_enabled():
                visual = [os.path.basename(p) for p in written_now if _VISUAL_EXT_RE.search(p)]
                if visual and not _looked_at_result(list(_turn_tool_uses(turn_records))):
                    visual_files = visual

    issue_line, issue_problem = _issues_stop_line(payload)
    try:
        label_line, label_problem = _loop_stop_line(payload)
    except Exception as exc:
        label_line, label_problem = None, "house-rules: the design-loop label check hit an error (%s: %s)." % (
            type(exc).__name__, exc)

    trace_lines = list(trace_lines_early)
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

    long_words = _long_reply_words(reply_text, _payload_cwd(payload)) if (vm is not None and _loop_enabled()) else 0
    # #324: the writing check no longer runs on chat replies (pages and new issues keep it), so no findings
    # and no report line here; the not-checked disclosure still goes through _writing_note.
    writing = []

    # #256: the checkpoint table. A miss blocks once, except the page row (#283), which blocks every
    # retry up to PAGE_BLOCK_LIMIT in a row. Any error here fails open with a message.
    def _page_count(ctx, change=None):
        mark = hashlib.sha1((ctx.get("user_text") or "").encode("utf-8")).hexdigest()[:16]
        return _page_blocks(_page_blocks_path(_payload_cwd(payload), _field(_SESSION_ID_RE, payload) or ""),
                            _field(_SESSION_ID_RE, payload) or "", mark, change)

    # #309 (incident 6 of #303): the page row reports instead of blocking, on the first reply and the retry
    # alike, until the restructure. It pushed another repo's work into a session as a proposal page.
    page_note = ""
    if _loop_enabled():
        try:
            pctx = {"reply": reply_text if vm is not None else "", "long_words": long_words,
                    "cwd": _payload_cwd(payload),
                    "user_text": _last_user_text(transcript_path) if transcript_path else ""}
            fix = _check_page(pctx)
            # #310: once a reply to aj's message is flagged, the page stays owed for every later reply to the
            # same message until one links a page - a shorter retry no longer clears it. The page-blocks file
            # keeps a count per message; above zero means owed.
            if _page_escape(pctx) or _reply_links_page(pctx["reply"], pctx["cwd"]):
                _page_count(pctx, "clear")
            elif fix or _page_count(pctx) > 0:
                # #326: the note is said once per message of aj's, on the first flag (count 0). The bump still
                # records that a page is owed; later replies to the same message, flagged or owed, stay quiet.
                first = _page_count(pctx) == 0
                _page_count(pctx, "bump")
                if first:
                    page_note = ("House rules, page checkpoint (report only, #309): %s. Nothing is blocked; if this "
                                 "reply belongs to another repo's work, the issue for that repo is enough." % fix)
        except Exception as exc:
            trace_lines.append("house-rules: the page checkpoint could not run (%s: %s), so this reply got no "
                               "page reminder." % (type(exc).__name__, exc))
    if not retry:
        try:
            ctx = {
                "reply": reply_text if vm is not None else "",
                "long_words": long_words,
                "editor_owed": editor_owed,
                "needs_evidence": needs_evidence,
                "uncommitted": uncommitted,
                "plain_problems": plain_problems, "cwd": _payload_cwd(payload),
                "user_text": _last_user_text(transcript_path) if transcript_path else "",
            }
            try:
                _top, _gd = _issues_locate(_payload_cwd(payload))
                if _gd:
                    _st, _pr = _loop_read(_gd)
                    if _pr:
                        raise OSError(_pr)
                    ctx.update(qa_stage=_st.get("stage"), qa_page=_st.get("qa_page"),
                               qa_linked=_st.get("qa_page_linked"), qa_git_dir=_gd)
            except Exception as exc:
                trace_lines.append("house-rules: the QA page checkpoint could not read the stage file (%s: %s), "
                                   "so it is off for this reply." % (type(exc).__name__, exc))
            missed = _missed_checkpoints(ctx)
            if missed:
                emit({"decision": "block", "reason": _checkpoint_reason(missed)})
                return 0
        except Exception as exc:
            trace_lines.append("house-rules: the checkpoint table hit an error (%s: %s), so this reply was "
                               "not blocked." % (type(exc).__name__, exc))
    else:
        # #269: a QA page linked only in the retry reply is still recorded; the retry never blocks.
        try:
            _top, _gd = _issues_locate(_payload_cwd(payload))
            if _gd:
                _st, _pr = _loop_read(_gd)
                if _pr:
                    raise OSError(_pr)
                if _st.get("stage") == "qa" and _st.get("qa_page") and not _st.get("qa_page_linked"):
                    _record_qa_link({"reply": reply_text if vm is not None else "",
                                     "qa_page": _st.get("qa_page"), "qa_git_dir": _gd,
                                     "cwd": _payload_cwd(payload)})
        except Exception as exc:
            trace_lines.append("house-rules: the QA page link could not be recorded on the retry (%s: %s)."
                               % (type(exc).__name__, exc))
    if (not needs_card and not needs_evidence and not not_checked and not uncommitted
            and not parity_word and not visual_files and not plain_problems and not issue_line
            and not long_words and not label_line and not writing and not editor_owed
            and not shell_page_notes and not page_note):
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
    if retry:
        # #322/#323: the retry reports to aj only; additionalContext would wake the model and loop.
        emit({"systemMessage": " ".join(trace_lines + parts)})
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "\n\n".join(parts)}}
    if trace_lines:
        out["systemMessage"] = " ".join(trace_lines)
    emit(out)
    return 0


# closablemerge - PostToolUse on Bash|merge_pull_request (#362). A merged pull request stamps every
# closable entry (state["closable"], saved by a QA pass) that has no merge yet. Never raises.
_GH_PR_MERGE_RE = re.compile(r"(?:^|[;&|(\s])gh\s+pr\s+merge\b([^;&|\n]*)")


def _closable_merge_of(data):
    """(repo, number) of a merge this payload reports, else None."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    resp = data.get("tool_response")
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except ValueError:
            resp = None
    if tool.lower().startswith("mcp__github__") and tool.endswith("merge_pull_request"):
        if isinstance(resp, dict) and resp.get("merged") is True and ti.get("pullNumber") is not None:
            return "%s/%s" % (ti.get("owner"), ti.get("repo")), int(ti["pullNumber"])
        return None
    if tool in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        m = _GH_PR_MERGE_RE.search(ti["command"])
        if not m:
            return None
        code, out = None, ""
        if isinstance(resp, dict):
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if code is None and resp.get("interrupted"):
                code = 1
            out = "%s\n%s" % (resp.get("stdout") or "", resp.get("stderr") or "")
        # Stamp only on proof: exit code 0, or, where no code is reported, gh's own success line
        # ("Merged pull request", "Squashed and merged pull request", "Rebased and merged pull request").
        # "will be automatically merged" is not a merge yet.
        if code is None and not re.search(r"merged pull request", out, re.IGNORECASE):
            return None
        if code not in (None, 0):
            return None
        num = re.search(r"(?<![\w-])(\d+)(?![\w-])", m.group(1))
        url = re.search(r"github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)", m.group(1))
        repo = re.search(r"(?:-R|--repo)[ =]+(\S+)", m.group(1))
        if url:
            return url.group(1), int(url.group(2))
        if num:
            return (repo.group(1) if repo else ""), int(num.group(1))
    return None


def _closed_issue_of(data):
    """(repo, number) of a close this PostToolUse payload proves succeeded, else None (#363)."""
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    resp = data.get("tool_response")
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except ValueError:
            resp = {"raw": resp}  # not JSON: kept as text, which proves nothing for the tool route
    if _GITHUB_ISSUE_WRITE_RE.match(tool):
        if str(ti.get("method", "")).lower() != "update" or str(ti.get("state", "")).lower() != "closed":
            return None
        try:
            num = int(ti.get("issue_number"))
        except (TypeError, ValueError):
            num = None  # no usable issue number: nothing to remove
        if num is None:
            return None
        text = json.dumps(resp) if resp is not None else ""
        if isinstance(resp, dict) and (resp.get("error") or resp.get("isError")):
            return None
        ok = (isinstance(resp, dict) and (str(resp.get("state", "")).lower() == "closed" or resp.get("url")))
        if not ok and not re.search(r'"state"\s*:\s*"closed"', text, re.IGNORECASE):
            return None
        return ("%s/%s" % (ti.get("owner"), ti.get("repo")) if ti.get("owner") and ti.get("repo") else ""), num
    if tool in _SHELL_TOOLS and isinstance(ti.get("command"), str):
        cmd = ti["command"]
        if not any(r.search(cmd) for r in _GH_ISSUE_CLOSE_RES):
            return None
        repo, num, _ = _close_gh_parse(cmd)
        if num is None:
            return None
        code, out = None, ""
        if isinstance(resp, dict):
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if code is None and resp.get("interrupted"):
                code = 1
            out = "%s\n%s" % (resp.get("stdout") or "", resp.get("stderr") or "")
        if code is None and not re.search(r"(closed issue|\"state\"\s*:\s*\"closed\")", out, re.IGNORECASE):
            return None
        if code not in (None, 0):
            return None
        return repo, num
    return None


def event_closablemerge():
    try:
        if not _loop_enabled():
            trace("house-rules plugin: closable-merge stamping is off (HOUSE_RULES_LOOP=off), so it did nothing.")
            return 0
        payload = read_payload()
        if not payload:
            return 0
        data = json.loads(payload)
        if not isinstance(data, dict):
            return 0
        closed = _closed_issue_of(data)
        if closed:  # #363: the evidence goes only once the close is proven to have worked
            _, git_dir = _issues_locate(_payload_cwd(payload))
            if git_dir:
                _close_forget(git_dir, closed[0], closed[1])
                trace("house-rules plugin: close of %s#%d succeeded, its closable/sweep record was removed." % closed)
            return 0
        merged = _closable_merge_of(data)
        if not merged:
            return 0
        _, git_dir = _issues_locate(_payload_cwd(payload))
        if not git_dir:
            return 0
        state, problem = _loop_read(git_dir)
        if problem:
            emit({"systemMessage": problem})
            return 0
        open_ = [e for e in state.get("closable", []) if isinstance(e, dict) and e.get("merged_pr") is None]
        if not open_:
            return 0
        repo, number = merged
        for e in open_:
            e["merged_pr"] = {"repo": repo, "number": number, "at": int(time.time())}
        _loop_write(git_dir, state)
        trace("house-rules plugin: merge of %s#%d stamped %d closable record(s)." % (repo, number, len(open_)))
    except Exception as exc:
        emit({"systemMessage": "house-rules plugin: the closable-merge check hit an error (%s: %s) and "
                               "stamped nothing for this call." % (type(exc).__name__, exc)})
    return 0


# ---------------------------------------------------------------------------------------
# The core links (#357). The core (house_rules/core.py) never imports this file, so the code
# that still lives here registers itself on its three lists at import, and the core handlers
# (inject, profile, scope, artifact, promptran) loop over them. Same behaviour as when they
# called these directly; each block moves to its part module in a later step.
# ---------------------------------------------------------------------------------------

# The delegation clause. delegate only fires on ExitPlanMode, so an auto or accept-edits
# session - which house-rules.md says the rule explicitly covers - never sees it, and neither
# does a plan simply agreed in conversation. This closes that gap from the prompt side, which
# is the only stateless place to close it: the go-ahead is in the prompt text.
SCOPE_DELEGATE_CLAUSE = (
    "\n- This reads like a go-ahead on settled work. Hand the implementation to the "
    "@house-rules:builder subagent (one per issue, never per step; at most two running) rather "
    "than running it on the planning model; its "
    "description is marked for proactive use, so that is authorized without a fresh ask. "
    "Skip it only when the work touches one file AND is three steps or fewer, and say so in "
    "one line naming the count."
)

# Prompt text that reads as "go ahead and do the thing we agreed" - the case the delegation
# clause exists for. Broad within the extracted field, like every other pattern here: a false
# positive costs one extra sentence of reminder, a false negative costs a whole implementation
# run on the planning model.
_SCOPE_GOAHEAD_RE = re.compile(
    r"\b(implement|execute|go ahead|build it|build that|do it|make the changes?|proceed|"
    r"ship it|carry it out|get (?:it|that) done|start (?:on )?(?:it|that)|"
    r"apply (?:the|those) (?:changes?|edits?|fixe?s?))\b",
    re.IGNORECASE,
)


_PLANS_PAGE_RE = re.compile(r"(?:^|[\\/])docs[\\/]plans[\\/][^\\/]+\.html?$", re.IGNORECASE)


def _page_writing_note(file_path):
    """#248: the shared writing checker on a page just written under docs/plans/, or "" when the
    file is not such a page, is clean, or the check is off."""
    if not _PLANS_PAGE_RE.search(file_path.replace("\\", "/")) or not _clear_writing_enabled():
        return ""
    if clarity is None:
        return CLARITY_ERROR
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except OSError as exc:
        return "house-rules: the page writing check could not read %s (%s)." % (file_path, exc)
    found = clarity.findings(clarity.page_text(html), skip=("not-checked",) + _WRITING_REPORT_ONLY)
    if not found:
        return ""
    return ("House rules, write it so nothing is left to guess: the page %s has %d thing(s) to fix "
            "before you publish it:\n%s\nCount what can be counted, name what you point at, and say "
            "each thing once. Then hand the page to @house-rules:editor before publishing."
            % (os.path.basename(file_path), len(found),
               "\n".join("- \"%s\": %s" % (p, why) for _k, p, why in found[:12])))


def _strip_subagent_markers(body):
    """inject: the <!-- subagent --> markers are for _subagent_core(), not the main session."""
    return "\n".join(
        line for line in body.split("\n") if line.strip() != SUBAGENT_SECTION_MARKER
    )


def _scope_waiting_link(payload, field):
    return "", _waiting_scope_note(payload)


def _scope_loop_link(payload, field):
    return "", _loop_scope_note(payload)


def _scope_delegate_link(payload, field):
    # With the design loop on, only "Build plan approved" starts a build (#232), so the
    # go-ahead guess runs only when the loop is off.
    if field is not None and _SCOPE_GOAHEAD_RE.search(field) and not _loop_enabled():
        return SCOPE_DELEGATE_CLAUSE, ""
    return "", ""


def _scope_parity_link(payload, field):
    if field is not None and _PARITY_RE.search(field) and _parity_enabled():
        return SCOPE_PARITY_CLAUSE, ""
    return "", ""


def _promptran_waiting_link(data):
    """promptran: the waiting-on-you update; returns the report text, or "" for none."""
    session_id = str(data.get("session_id") or "")
    path, _ = _waiting_path(session_id)
    if not os.path.isfile(path):
        return ""
    key = _waiting_key(data["tool_name"], data.get("tool_input"))
    late = []

    def fn(entries):
        out, changed = [], False
        for e in entries:
            if e.get("session_id") == session_id and e.get("key") == key:
                status = e.get("status")
                if status == "waiting":
                    e, changed = dict(e, status="ran"), True
                elif status in ("timed-out", "reported"):
                    if status == "timed-out":
                        late.append(e)
                    changed = True
                    continue
            out.append(e)
        return out if changed else None
    _waiting_update(path, fn, "promptran")
    if late:
        text = ("house-rules: '%s' ran although its permission prompt was refused as unanswered "
                "at %s; something approved it afterwards (possibly a late answer on the old dialog). "
                "Removed it from the waiting-on-you list."
                % (late[0].get("summary", "?"), _waiting_clock(late[0].get("timed_out_at"))))
        return text
    return ""


core.register_session_start("inject", _strip_subagent_markers)
# Order matters: the core puts a later hook's note in front of an earlier one, so the loop note
# lands before the waiting note, as it did when scope called them in this order.
core.register_guard_issue(_author_guard)
core.register_guard_issue(_issues_guard)
core.register_github_write(_guardgithub_issue_checks)
core.register_prompt(_scope_waiting_link)
core.register_prompt(_scope_loop_link)
core.register_prompt(_scope_delegate_link)
core.register_prompt(_scope_parity_link)
core.register_post_tool("artifact", _page_writing_note)
core.register_post_tool("promptran", _promptran_waiting_link)


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
