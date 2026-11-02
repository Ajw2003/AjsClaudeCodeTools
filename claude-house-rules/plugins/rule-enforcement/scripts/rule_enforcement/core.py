"""rule_enforcement.core - the rule-loading handlers moved out of house-rules (#440, step 3 part A of #437).

inject, showrule (SessionStart), subagentrules (SubagentStart) and scope (UserPromptSubmit), plus what
only they use: the voice toggle, the plugin-root / newer-install lookup, the <plugin> path expansion and
the subagent core. Moved from house_rules/core.py and house_rules/delegation.py; the text each emits is
unchanged. docs/4-systems/plugin-split.md, "Step 3 part A", says what moved and where each link went.

What house-rules still adds, on the same events, in its own small hooks (scopelinks, subagentlinks,
threadlink): the prompt clauses and notes the design loop, safe git, delegation and parity parts
register, the design loop's helper note and the subagent transcript line, and the project-thread
transcript link. STDLIB ONLY, like house-rules.
"""

import json
import os
import re
import sys

# This file is one folder deeper than hook.py: SCRIPTS_DIR is the scripts/ folder that holds hook.py,
# house_lib/ (the vendored shared library, copied in by tools/sync_library.py) and this package.
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS_DIR)
from house_lib.plumbing import (  # noqa: E402,F401
    read_payload, emit, _TRACE_OFF, _truncate_with_notice, _read_text,
)

# The plugin name _rules_root looks for in installed_plugins.json: the plugin that holds rules/.
_PLUGIN_NAME = "rule-enforcement"


def _installed_plugins_path():
    return os.environ.get("HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON") or os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "installed_plugins.json"
    )


def _plugin_version(problems=None):
    path = os.path.join(SCRIPTS_DIR, "..", ".claude-plugin", "plugin.json")
    version = ""
    try:
        version = json.loads(_read_text(path)).get("version", "") or ""
    except Exception as exc:
        if problems is not None:
            problems.append("could not read the plugin version (%s)" % type(exc).__name__)
    return version


def _delegation_enabled():
    """HOUSE_RULES_DELEGATION=off disables subagentrules, as it did in house-rules (the off switches
    are removed in a later part of #440)."""
    return os.environ.get("HOUSE_RULES_DELEGATION", "on").strip().lower() not in {"off", "0", "false", "no"}


# The voice is a preference, so it gets a lever - but it ships ON, for the same reason the
# decision trace does: a setting nobody enables until they are already unhappy is not a setting.
# Off removes only the "### The voice" subsection; the clear-writing rule above it is not a
# preference and always loads. Since #245 the voice lives in rules/clear-writing.md (showrule).
_VOICE_HEADING = "### The voice"


def _apply_voice_toggle(body):
    if os.environ.get("HOUSE_RULES_VOICE", "on").strip().lower() not in _TRACE_OFF:
        return body
    start = body.find(_VOICE_HEADING)
    if start == -1:
        # The section this is meant to remove is gone, which means the rules text moved and this
        # toggle now silently does nothing. Say so rather than pretending it worked.
        sys.stderr.write(
            "house-rules: HOUSE_RULES_VOICE=off, but the %r section was not found in "
            "the rules - the toggle had no effect.\n" % _VOICE_HEADING
        )
        return body
    nxt = body.find("\n## ", start)
    return body[:start] + (body[nxt + 1 :] if nxt != -1 else "")


def _plugin_root():
    return os.path.normpath(os.path.join(SCRIPTS_DIR, ".."))


def _version_tuple(text):
    parts = []
    for piece in str(text).split("."):
        m = re.match(r"\d+", piece)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts)


def _rules_root(needed):
    """(root, note): the plugin folder whose rules SessionStart should load.

    A session starts on the folder the harness resolved at launch. If an update lands during
    that same SessionStart (versioncheck, last in hooks.json), inject and showrule already ran
    from the old folder, so a session carried the old rules beside the new checks (issue #252).
    So: use installed_plugins.json's installPath when it exists, is newer by version, and has
    every file in `needed` (paths under rules/); otherwise this folder. `note` is one line, or
    "" when nothing differs. It is never silent when the answer could not be worked out.
    """
    own = _plugin_root()
    path = _installed_plugins_path()
    if not os.path.isfile(path):
        return own, "could not check for newer rules: %s does not exist, so this folder's rules (%s) were loaded" % (path, own)
    try:
        data = json.loads(_read_text(path))
        plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
        entry = None
        for plugin_id, entries in sorted(plugins.items()):
            if plugin_id.split("@", 1)[0] != _PLUGIN_NAME:
                continue
            if isinstance(entries, dict):
                entries = [entries]
            entry = next((e for e in entries if isinstance(e, dict) and e.get("installPath")), None)
            break
    except Exception as exc:
        return own, "could not check for newer rules: installed_plugins.json is unreadable (%s), so this folder's rules (%s) were loaded" % (type(exc).__name__, own)
    if entry is None:
        return own, "could not check for newer rules: installed_plugins.json has no installPath for %s, so this folder's rules (%s) were loaded" % (_PLUGIN_NAME, own)
    new_root = os.path.normpath(entry["installPath"])
    if os.path.realpath(new_root) == os.path.realpath(own):
        return own, ""
    try:
        new_version = str(entry.get("version", "")) or _plugin_version_of(new_root)
    except Exception as exc:
        return own, "could not check for newer rules: no version for %s (%s), so this folder's rules (%s) were loaded" % (new_root, type(exc).__name__, own)
    own_version = _plugin_version()
    if not new_version or _version_tuple(new_version) <= _version_tuple(own_version):
        return own, ""
    missing = [n for n in needed if not os.path.isfile(os.path.join(new_root, "rules", n))]
    if missing:
        return own, "newer rules %s are installed at %s but lack rules/%s, so this folder's %s rules were loaded" % (
            new_version, new_root, ", rules/".join(missing), own_version or "unknown")
    return new_root, "loaded the rules from house-rules %s (%s), not this session's %s, because an update installed it after this session started" % (
        new_version, new_root, own_version or "unknown")


def _plugin_version_of(root):
    return json.loads(_read_text(os.path.join(root, ".claude-plugin", "plugin.json"))).get("version", "") or ""


def _expand_detail_paths(text, root=None):
    """Write every plugin path as <plugin>/... and state the absolute plugin root once, so the
    injected size does not grow with the install path's length or the number of pointers."""
    root = root or _plugin_root()
    if "${CLAUDE_PLUGIN_ROOT}" not in text:
        return text
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", "<plugin>")
    return "<plugin> in the paths below is the plugin root: %s\n\n%s" % (root, text)


def event_inject():
    root, note = _rules_root(("house-rules.md",))
    rules_path = os.path.join(root, "rules", "house-rules.md")

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
    # The <!-- subagent --> markers are a build-time signal for _subagent_core() (which
    # sections of this same file to re-inject at a subagent's own SubagentStart), not
    # something the main session needs to read - stripping them here keeps this file the
    # single source for both without paying for the markers twice.
    body = _strip_subagent_markers(body)
    if not body.strip():
        emit(
            {
                "systemMessage": "house-rules plugin: rules/house-rules.md is empty. "
                "The rules were NOT loaded into this session."
            }
        )
        return 0

    # The rules text names its detail files as ${CLAUDE_PLUGIN_ROOT}/rules/detail/<file>.md -
    # that variable is expanded by the harness in hooks.json's own command strings, but this
    # text is going into additionalContext, which nothing expands. The root is stated once
    # rather than substituted into every pointer: 26 copies of a long install path pushed this
    # past its size margin on a CI runner whose checkout path was merely 26 chars longer.
    body = _expand_detail_paths(body, root)

    preamble = (
        "The following are the user standing house rules. They apply to every project and "
        "override default behaviour. A PreToolUse hook also refuses destructive commands, "
        "naming the safe way, and refuses commit/push/merge on `main`. "
        "That hook is a backstop, not "
        "permission to skip asking first. Machine profile: injected separately.\n\n"
    )

    out = {
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": preamble + body,
        },
    }
    if note:
        out["systemMessage"] = "house-rules plugin: " + note + "."
    emit(out)
    return 0


# ---------------------------------------------------------------------------------------
# showrule — the "Show, don't tell" rule, injected by its own SessionStart entry for the same
# reason profile was split out: house-rules.md was 47 chars from inject's size margin when the
# rule was approved (issue #224). Full rationale: rules/detail/show-dont-tell.md.
# ---------------------------------------------------------------------------------------


# The rules loaded in their own slot, in order: show-dont-tell (#225) and clear-writing (#245).
SHOWRULE_FILES = (("show-dont-tell.md", "show-don't-tell"), ("clear-writing.md", "clear-writing"))


def event_showrule():
    root, note = _rules_root(tuple(n for n, _ in SHOWRULE_FILES))
    bodies, missing = [], []
    for name, label in SHOWRULE_FILES:
        try:
            body = _read_text(os.path.join(root, "rules", name)).replace("\r\n", "\n")
        except OSError:
            missing.append("cannot read rules/%s, so the %s rule was NOT loaded" % (name, label))
            continue
        if not body.strip():
            missing.append("rules/%s is empty, so the %s rule was NOT loaded" % (name, label))
            continue
        bodies.append(_apply_voice_toggle(body) if name == "clear-writing.md" else body)
    if not bodies:
        emit({"systemMessage": "house-rules plugin: " + "; ".join(missing + ([note] if note else [])) + "."})
        return 0
    out = {"suppressOutput": True, "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "Standing house rules, loaded separately from the rest:\n\n"
        + _expand_detail_paths("\n\n".join(bodies), root)}}
    if missing or note:
        out["systemMessage"] = "house-rules plugin: " + "; ".join(missing + ([note] if note else [])) + "."
    emit(out)
    return 0



# ---------------------------------------------------------------------------------------
# scope — UserPromptSubmit. Must not be able to fail: one fixed string, no file read.
# ---------------------------------------------------------------------------------------

SCOPE_REMINDER = (
    # The long form fires on roughly 40% of real prompts, so its size is paid often. It was
    # trimmed from 1,435 chars by merging the two handover bullets: the step-card shape and
    # the per-command fields are one rule from the model's point of view, and stating them
    # separately bought nothing. Every rule the old text carried is still here - this is the
    # same content said once instead of twice, not a shorter list of rules.
    "Standing house rules (full text was injected at session start):\n"
    "- Show, don't tell: plans reach the user as a page to approve; nothing unasked is "
    "built.\n"
    "- Find out what machine you are on and build for that. The coding standards injected "
    "at session start are binding, each governing only its own languages.\n"
    "- Deliver a whole workflow: exact commands to run, nothing left for the user to "
    "configure by hand.\n"
    "- Artifacts are real files in the project directory, not chat and not a temp "
    "directory.\n"
    "- Never hand over a command you have not run where the user will run it. Running "
    "something similar is not running it.\n"
    "- Update the docs tier that changed before this turn ends - state usually - or say why "
    "none did.\n"
    "- No success claim without a run you can quote: evidence before claims, every time.\n"
    "- Commit finished work on your own branch, scoped to the paths you changed; on the "
    "user's branch, branch off first."
)

SCOPE_REMINDER_SHORT = (
    "House rules reminder: update the docs tier that changed; no success claim without a run "
    "you can quote; commit finished work on your own branch. Never hand over a command you "
    "have not run. Build only what was asked - where it is ambiguous, ask instead of assuming."
)

# Prompt text suggesting this turn will involve commands, files, or builds - the case the full
# reminder exists for. Deliberately broad (over-triggering here just means the longer, still-
# correct string fires) - the same "match the extracted field, stay broad within it" posture as
# guard's patterns.
_SCOPE_COMMAND_HINT_RE = re.compile(
    r"\b(run|install|build|deploy|command|script|terminal|shell|powershell|bash|npm|pip|git|"
    r"file|files|folder|directory|write|edit|create|delete|download|test|config|setup)\b",
    re.IGNORECASE,
)

_PROMPT_FIELD_RE = re.compile(r'"prompt"\s*:\s*"(?:[^"\\]|\\.)*"')


def event_scope():
    # UserPromptSubmit: a non-zero exit here ERASES THE USER'S PROMPT. Every failure path -
    # unreadable payload, missing "prompt" key, any exception at all - must fall through to
    # emitting the safe short reminder and exiting 0. Never raise, never exit non-zero.
    reminder = SCOPE_REMINDER_SHORT
    try:
        payload = read_payload()
        m = _PROMPT_FIELD_RE.search(payload)
        field = m.group(0) if m else None
        # The clauses and notes other parts add (waiting, design loop, delegation, parity) are no
        # longer gathered here: house-rules' own scopelinks hook emits them on the same event.
        if m:
            if _SCOPE_COMMAND_HINT_RE.search(field):
                reminder = SCOPE_REMINDER
    except Exception:
        # Whatever went wrong, the safe short reminder still goes out. A non-zero exit or a
        # raise here would ERASE THE USER'S PROMPT, so this recovers rather than reporting.
        reminder = SCOPE_REMINDER_SHORT

    try:
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": reminder,
                }
            }
        )
    except Exception:
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": SCOPE_REMINDER_SHORT,
                }
            }
        )
    return 0



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
    """SubagentStart: inject the subagent core. The transcript line and the design loop's helper note
    that used to ride along are emitted by house-rules' own subagentlinks hook on the same event."""
    try:
        if not _delegation_enabled():
            return 0
        core, problems = _subagent_core()
        out = {}
        if problems:
            out["systemMessage"] = "house-rules subagentrules COULD NOT TELL: %s" % "; ".join(problems)
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


def _strip_subagent_markers(body):
    """inject: the <!-- subagent --> markers are for _subagent_core(), not the main session."""
    return "\n".join(
        line for line in body.split("\n") if line.strip() != SUBAGENT_SECTION_MARKER
    )

