"""house_rules.delegation - the delegation part (#359, step 2c of #340): delegate, subagent rules, announce,
verdict and the audit report, the agent cap, the subagent commit check, autosave, commitgate, worktreesweep, audit and
userpromptaudit. Moved verbatim from hook.py; docs/4-systems/plugin-restructure.md, "Step 2c", says what moved and why.

Imports only from house_rules.core. Where it needs design loop code (the issue plan note, the helper note, the issue and
label recording, the edit gates) it loops over a core link list the design loop registers on."""

import json
import os
import re
import time

from house_rules import core, settings
from house_rules.core import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _AUDIT_COMMAND_TOOLS,
    _AUDIT_WRITE_TOOLS,
    _GATED_TOOLS,
    _PARITY_ACCOUNTED_RE,
    _PARITY_RE,
    _PLAN_VALUE_RE,
    _PROMPT_VALUE_RE,
    _SESSION_ID_RE,
    _TOGGLE_OFF,
    _TRANSCRIPT_RE,
    _ag,
    _branch_advice,
    _commit_check_enabled,
    _common_git_dir,
    _expand_detail_paths,
    _field,
    _git_dir,
    _issues_enabled,
    _loop_enabled,
    _parity_enabled,
    _parse_status_porcelain,
    _plugin_version,
    _read_text,
    _truncate_with_notice,
    _uncommitted_among,
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


def event_delegate():
    try:
        note = DELEGATE_NOTE
        payload = read_payload() or ""
        if _parity_enabled():
            plan = _field(_PLAN_VALUE_RE, payload) or ""
            if _PARITY_RE.search(plan) and not _PARITY_ACCOUNTED_RE.search(plan):
                note = note + DELEGATE_PARITY_NOTE
        for fn in DELEGATE_NOTE_HOOKS:
            note = note + fn(payload)
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
        here = SCRIPTS_DIR
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
        loop_note = "".join(fn(payload or "") for fn in SUBAGENT_NOTE_HOOKS)
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
    here = SCRIPTS_DIR
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
    """The automatic commit's message: the subject and the derived credit line, no Claude line (#349).
    session_id is kept so the callers do not change; it is no longer written into the message."""
    return subject + "\n\n" + settings.commit_credit()


def _wip_commit(top, subject, session_id=""):
    """Commit everything in the worktree on the subagent's behalf. (short sha, files), or
    (None, []) when there was nothing to commit. --no-verify: a repo's pre-commit hook must not
    be able to block the one commit that protects the work."""
    files = _dirty_files(top)
    if not files:
        return None, []
    _ag(top, ["add", "-A"])
    # Author name is the agent's name, email the user's own git email (#349); house-rules@localhost only when
    # git has no usable email, so the commit still happens.
    ident = ["-c", "user.name=%s" % (settings.agent_name() or "house-rules"),
             "-c", "user.email=%s" % (settings.git_email(top) or "house-rules@localhost")]
    _ag(top, ident + ["commit", "--no-verify", "-q", "-m", _wip_message(subject, session_id)])
    return _ag(top, ["rev-parse", "--short", "HEAD"])[1].strip(), files


def _head_age_seconds(top):
    import time as _t

    return _t.time() - int(_ag(top, ["log", "-1", "--format=%ct"])[1].strip() or "0")


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
        issue_notes = []
        for fn in TOOL_RECORD_HOOKS:
            issue_notes += fn(payload)
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
        for fn in EDIT_GATE_HOOKS:
            if fn(payload):
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


def _autosave_merged_sweep(root):
    """#349 (round 2 answer 7): delete an autosave snapshot, locally and on origin, once its helper's work is merged.
    (dropped, problems), both lists of text.

    The merge signal is what git can prove, not a recorded event: the snapshot holds nothing beyond the commit it
    sits on (its tree equals its parent's tree), and that parent is contained in some branch that is not a helper
    branch (a local branch or an origin one). Then every byte the snapshot holds is already on a real branch, so
    deleting it loses nothing. A snapshot with uncommitted work in it (a live or killed helper) never matches."""
    dropped, problems = [], []
    rc, out, err = _ag(root, ["for-each-ref", "--format=%(refname) %(objectname)", AUTOSAVE_REF_PREFIX], check=False)
    if rc != 0:
        return dropped, ["could not list the autosave snapshots (%s)" % (err.strip() or "git failed")]
    for line in out.splitlines():
        ref, _sp, sha = line.partition(" ")
        branch = ref[len(AUTOSAVE_REF_PREFIX):]
        try:
            rc1, parent, _e = _ag(root, ["rev-parse", "--verify", "-q", sha + "^"], check=False)
            if rc1 != 0:
                continue  # a snapshot always has a parent; one that does not is not ours to judge
            parent = parent.strip()
            if _ag(root, ["rev-parse", sha + "^{tree}"])[1].strip() != _ag(root, ["rev-parse", parent + "^{tree}"])[1].strip():
                continue  # the snapshot holds work no commit has: not merged
            homes = [r for r in _ag(root, ["for-each-ref", "--format=%(refname)", "--contains", parent,
                                           "refs/heads", "refs/remotes"])[1].split()
                     if r != "refs/heads/" + branch and not r.endswith("/" + branch) and not r.endswith("/HEAD")
                     and not r.startswith(("refs/heads/" + AUTOSAVE_BRANCH_PREFIX, "refs/remotes/origin/" + AUTOSAVE_BRANCH_PREFIX))]
            if not homes:
                continue
            _ag(root, ["update-ref", "-d", ref])
            on_origin = ""
            if _ag(root, ["remote", "get-url", "origin"], check=False)[0] == 0:
                rc2, listed, e2 = _ag(root, ["ls-remote", "--exit-code", "origin", ref], check=False, timeout=AUTOSAVE_PUSH_TIMEOUT)
                if rc2 == 0 and listed.strip():
                    _ag(root, ["push", "--quiet", "origin", ":" + ref], timeout=AUTOSAVE_PUSH_TIMEOUT)
                    on_origin = " and on origin"
                elif rc2 != 2:
                    problems.append("could not check origin for %s (%s); delete it there by hand if it exists" % (ref, e2.strip() or "ls-remote failed"))
            dropped.append("%s (work is in %s)%s" % (ref, homes[0].split("/", 2)[-1], on_origin))
        except RuntimeError as exc:
            problems.append("could not drop %s (%s)" % (ref, exc))
    return dropped, problems


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
        dropped, drop_problems = _autosave_merged_sweep(root)
        problems += drop_problems
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
        if not swept and not problems and not dropped:
            return 0
        lines = []
        if dropped:
            lines.append("house-rules worktreesweep: dropped the snapshot of merged helper work: %s." % "; ".join(dropped))
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


def _strip_subagent_markers(body):
    """inject: the <!-- subagent --> markers are for _subagent_core(), not the main session."""
    return "\n".join(
        line for line in body.split("\n") if line.strip() != SUBAGENT_SECTION_MARKER
    )


def _scope_delegate_link(payload, field):
    # With the design loop on, only "Build plan approved" starts a build (#232), so the
    # go-ahead guess runs only when the loop is off.
    if field is not None and _SCOPE_GOAHEAD_RE.search(field) and not _loop_enabled():
        return SCOPE_DELEGATE_CLAUSE, ""
    return "", ""


core.register_session_start("inject", _strip_subagent_markers)
core.register_prompt(_scope_delegate_link)
