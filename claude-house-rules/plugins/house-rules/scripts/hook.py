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
  - artifact, runnable, delegate, harvest (PostToolUse) never obstruct, but never go quiet:
                 any failure emits a systemMessage and exits 0.
  - announce, subagentrules (SubagentStart), verdict (SubagentStop) never obstruct a
                 delegation: any failure emits a systemMessage and exits 0.
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
import tempfile


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

# Claude Code's per-hook additionalContext limit is 10,000 chars (docs/Decisions.md, 2026-09-22).
# The machine profile lives in its own SessionStart entry (profile), not appended to inject's
# text, because the limit is per hook and a recorded environment.md can be large on its own.
INJECT_CHAR_LIMIT = 10_000
# The soft budget profile truncates itself against, well under the hard limit above so the
# truncation notice it appends never itself pushes the total back over 10,000.
PROFILE_SOFT_LIMIT = 9_500


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
    HOUSE_RULES_TRACE=off is the one lever, and it covers every handler.
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


# ---------------------------------------------------------------------------------------
# inject — SessionStart
# ---------------------------------------------------------------------------------------

import platform
import shutil
import sys as _sys
import time as _time


def _read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _detect_environment():
    """Runtime detection used when rules/environment.md is missing or empty.

    Why this exists and what it can't replace: docs/architecture.md, "The machine profile is
    data, not code, and is not committed".
    """
    lines = ["# This machine (runtime-detected - not yet hand-verified)", ""]
    lines.append(f"OS: {platform.system()} {platform.release()} ({platform.platform()})")
    lines.append(f"Python: {_sys.version.split()[0]} at {_sys.executable}")
    for tool in ("git", "sh", "bash", "pwsh", "powershell", "node", "npm"):
        found = shutil.which(tool)
        lines.append(f"{tool}: {found if found else 'NOT on PATH'}")
    lines.append("")
    lines.append(
        "This section was generated by hook.py's inject handler, not hand-verified. Before "
        "relying on a fact not listed here - RAM, GPU, line-ending config, anything else - "
        "discover it and write it into rules/environment.md (gitignored, machine-local) so it "
        "is recorded rather than re-detected every session."
    )
    return "\n".join(lines) + "\n"


def _preflight_warnings():
    """Gaps that should be visible in-session, not just discoverable via /house-rules:doctor.

    Checked here (SessionStart, once) rather than in guard/scope (every call): none of these
    are the guard's job, and they should not cost anything on the hot path. Only genuine gaps
    produce a line - a clean machine adds nothing to the injection.
    """
    warnings = []
    if _sys.version_info < (3, 8):
        warnings.append(
            f"- running on Python {_sys.version.split()[0]}, older than the 3.8 this plugin "
            "targets. Handlers may behave unexpectedly."
        )
    if shutil.which("git") is None:
        warnings.append("- git is not on PATH. Nothing here can be committed or inspected.")
    if platform.system() == "Windows" and not (
        shutil.which("sh") or os.path.exists(r"C:\Program Files\Git\bin\sh.exe")
    ):
        warnings.append(
            "- no sh.exe found (Git for Windows not installed or not on PATH). run.sh, and "
            "therefore every hook, cannot execute at all on this machine."
        )
    if not warnings:
        return ""
    return (
        "\n\n---\n\nPreflight gaps found on this machine:\n"
        + "\n".join(warnings)
        + "\n\nRun /house-rules:doctor for the install command for each gap.\n"
    )


# The voice is a preference, so it gets a lever - but it ships ON, for the same reason the
# decision trace does: a setting nobody enables until they are already unhappy is not a setting.
# Off removes only the "### The voice" subsection; the plain-language rule above it is not a
# preference and always loads.
_VOICE_HEADING = "### The voice"


def _apply_voice_toggle(body):
    if os.environ.get("HOUSE_RULES_VOICE", "on").strip().lower() not in _TRACE_OFF:
        return body
    start = body.find(_VOICE_HEADING)
    if start == -1:
        # The section this is meant to remove is gone, which means the rules text moved and this
        # toggle now silently does nothing. Say so rather than pretending it worked.
        sys.stderr.write(
            "house-rules inject: HOUSE_RULES_VOICE=off, but the %r section was not found in "
            "the rules - the toggle had no effect.\n" % _VOICE_HEADING
        )
        return body
    nxt = body.find("\n## ", start)
    return body[:start] + (body[nxt + 1 :] if nxt != -1 else "")


def _plugin_root():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def event_inject():
    here = os.path.dirname(os.path.abspath(__file__))
    rules_path = os.path.join(here, "..", "rules", "house-rules.md")

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
    body = _apply_voice_toggle(body)
    # The <!-- subagent --> markers are a build-time signal for _subagent_core() (which
    # sections of this same file to re-inject at a subagent's own SubagentStart), not
    # something the main session needs to read - stripping them here keeps this file the
    # single source for both without paying for the markers twice.
    body = "\n".join(
        line for line in body.split("\n") if line.strip() != SUBAGENT_SECTION_MARKER
    )
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
    # text is going into additionalContext, which nothing expands. Substitute the real absolute
    # path here so the path Claude reads is one Claude can actually open.
    body = body.replace("${CLAUDE_PLUGIN_ROOT}", _plugin_root())

    preamble = (
        "The following are the user standing house rules. They apply to every project and "
        "override default behaviour. A PreToolUse hook also prompts for destructive "
        "commands, backgrounded/hidden processes, and mutating git commands - except a "
        "plain commit or push on a `claude/` branch. That hook is a backstop, not "
        "permission to skip asking first. Machine profile: injected separately.\n\n"
    )

    emit(
        {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": preamble + body,
            },
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# profile — a third SessionStart handler, split out of inject in 2.17.1 (docs/Decisions.md,
# 2026-09-22): the per-hook additionalContext limit is 10,000 chars, and a recorded
# rules/environment.md can by itself be large enough that appending it to inject's own text
# risked pushing inject over the limit. Registered with no matcher gate of its own (SessionStart
# only), right after inject in hooks.json, so a failure here can never take inject down with it.
# ---------------------------------------------------------------------------------------


def event_profile():
    here = os.path.dirname(os.path.abspath(__file__))
    envfile = os.environ.get("HOUSE_RULES_ENV_FILE") or os.path.join(
        here, "..", "rules", "environment.md"
    )

    try:
        envbody = _read_text(envfile).replace("\r\n", "\n")
    except OSError:
        envbody = ""

    if not envbody.strip():
        # rules/environment.md is machine-local and gitignored (F2) - a fresh clone has none,
        # so this is not an edge case to apologize for, it is the normal first run on a new
        # machine. Runtime detection is the source of truth here, not a hardcoded default.
        envbody = (
            "NOT RECORDED YET as a hand-verified file - the section below is what this "
            "session detected at runtime instead.\n\n" + _detect_environment()
        )

    preamble = (
        "The machine profile, as recorded (rules/house-rules.md is injected separately by "
        "the inject hook). The first rule says to build for what is written here rather "
        "than what seems likely:\n\n"
    )

    preflight = _preflight_warnings()

    handover_block = ""
    if os.environ.get("CLAUDE_CODE_REMOTE"):
        # Only a remote session's tool-calls run somewhere other than the user's own machine, so
        # this is the only case where "the machine I execute on" and "the machine a handed-over
        # command targets" can differ. A local session must add zero text and zero cost here -
        # the two questions are the same one there, already answered by envbody above.
        handover_file = os.environ.get("HOUSE_RULES_HANDOVER_TARGET_FILE") or os.path.join(
            here, "..", "rules", "handover-target.md"
        )
        try:
            handover_body = _read_text(handover_file).replace("\r\n", "\n")
        except OSError:
            handover_body = ""

        if handover_body.strip():
            handover_block = (
                "\n\n---\n\nThe human's own machine (for anything I hand over to them), as "
                "recorded. Recorded? Build for exactly that:\n\n" + handover_body
            )
        else:
            handover_block = (
                "\n\n---\n\nThis session is remote: the machine profile above is the sandbox "
                "hook.py runs on, not necessarily the user's own machine. Before the first "
                "command I hand over, find out theirs - check docs/example-environment.md if "
                "present (say it's inferred, and from when, not confirmed), or ask - then "
                "record the confirmed answer into rules/handover-target.md so a later session "
                "does not have to ask again.\n"
            )

    # Truncate only the environment body if it runs the whole thing over budget - preflight
    # warnings and the remote handover-target block are never the part that gets cut, since
    # either one going missing silently would hide something actionable, not just verbose.
    fixed_len = len(preamble) + len(preflight) + len(handover_block)
    env_budget = max(0, PROFILE_SOFT_LIMIT - fixed_len)
    trimmed_envbody = _truncate_with_notice(envbody, env_budget, envfile)
    full = preamble + trimmed_envbody + preflight + handover_block

    emit(
        {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": full,
            },
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# standards — a second SessionStart handler. Selects and injects the vendored per-ecosystem
# coding standards docs from rules/standards/. Separate hook entry from inject on purpose:
# rules injection must never be able to fail on account of standards detection.
# ---------------------------------------------------------------------------------------

STANDARDS_SKIP_DIRS = {"node_modules", "Library", "Temp", "obj", "bin", ".git"}

STANDARDS_GOVERNS = {
    "coding-philosophy": "applies to all languages and stacks",
    "csharp-unity-standards": "governs C# and Unity code",
    "web-js-ts-node-standards": "governs HTML, CSS, JS, TS and Node code",
}


def _standards_scan_dirs(root):
    """Repo root plus one level of subdirectories, skipping the usual heavy/vendor dirs.

    Depth is exactly one, never recursive - walking node_modules/ or Unity's Library/ is slow
    enough to be felt at every session start.
    """
    dirs = [root]
    try:
        for name in sorted(os.listdir(root)):
            if name in STANDARDS_SKIP_DIRS:
                continue
            full = os.path.join(root, name)
            if os.path.isdir(full):
                dirs.append(full)
    except OSError as exc:
        sys.stderr.write(
            "house-rules standards: could not scan %r (%s); any markers below it were "
            "not seen.\n" % (root, exc)
        )
    return dirs


def _has_unity_markers(d):
    if os.path.exists(os.path.join(d, "ProjectSettings", "ProjectVersion.txt")):
        return True
    if os.path.isdir(os.path.join(d, "Assets")):
        return True
    try:
        for name in os.listdir(d):
            if name.lower().endswith(".csproj"):
                return True
    except OSError as exc:
        sys.stderr.write(
            "house-rules standards: could not list %r (%s); treating it as having no "
            "Unity markers, which may be wrong.\n" % (d, exc)
        )
    return False


def _has_node_markers(d):
    return any(
        os.path.exists(os.path.join(d, name))
        for name in ("package.json", "tsconfig.json", "deno.json")
    )


def _unity_markers_in_parent(project_dir):
    """True when project_dir is itself a Unity project's Assets/ folder.

    Why and how: doc-ref 0d4d docs/systems/hook-engine.md (Invariants).
    """
    normalized = os.path.normpath(project_dir)
    if os.path.basename(normalized) != "Assets":
        return False
    parent = os.path.dirname(normalized)
    if not parent or parent == normalized:
        return False
    if os.path.exists(os.path.join(parent, "ProjectSettings", "ProjectVersion.txt")):
        return True
    try:
        for name in os.listdir(parent):
            if name.lower().endswith(".csproj"):
                return True
    except OSError as exc:
        sys.stderr.write(
            "house-rules standards: could not list the parent directory %r (%s); treating "
            "it as having no Unity markers, which may be wrong.\n" % (parent, exc)
        )
    return False


def _standards_location_phrase(d, root):
    if os.path.abspath(d) == os.path.abspath(root):
        return "at the repo root"
    rel = os.path.relpath(d, root).replace(os.sep, "/")
    return f"in `{rel}/`"


def event_standards():
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        standards_dir = os.path.join(here, "..", "rules", "standards")
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

        override_path = os.path.join(project_dir, ".claude", "standards")
        selected = []  # list of (stem, reason)

        if os.path.isfile(override_path):
            try:
                lines = _read_text(override_path).replace("\r\n", "\n").splitlines()
            except OSError:
                lines = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                selected.append((line, "named in `.claude/standards`"))
        else:
            selected.append(("coding-philosophy", "always applies"))
            dirs = _standards_scan_dirs(project_dir)
            unity_dir = None
            node_dir = None
            for d in dirs:
                if unity_dir is None and _has_unity_markers(d):
                    unity_dir = d
                if node_dir is None and _has_node_markers(d):
                    node_dir = d

            scan_root = project_dir
            assets_note = None
            if unity_dir is None and _unity_markers_in_parent(project_dir):
                # project_dir IS a Unity project's Assets/ folder - rescan from the real
                # project root one level up, so sibling Node services (e.g. a `controller/`
                # or `relay/` next to Assets/) are seen too, not just the Unity markers.
                scan_root = os.path.dirname(os.path.normpath(project_dir))
                assets_note = "this project's root is a Unity project's `Assets/` folder"
                dirs = _standards_scan_dirs(scan_root)
                for d in dirs:
                    if unity_dir is None and _has_unity_markers(d):
                        unity_dir = d
                    if node_dir is None and _has_node_markers(d):
                        node_dir = d

            if unity_dir is not None:
                where = _standards_location_phrase(unity_dir, scan_root)
                reason = f"Unity project markers were found {where}"
                if assets_note:
                    reason += f" ({assets_note})"
                selected.append(("csharp-unity-standards", reason))
            if node_dir is not None:
                where = _standards_location_phrase(node_dir, scan_root)
                reason = f"Node markers were found {where}"
                if assets_note:
                    reason += " (searched from the Unity project root, not this Assets/ folder)"
                selected.append(("web-js-ts-node-standards", reason))

        if not selected:
            return 0

        bodies = []
        missing = []
        for stem, reason in selected:
            path = os.path.join(standards_dir, f"{stem}.md")
            try:
                text = _read_text(path).replace("\r\n", "\n")
            except OSError:
                missing.append(stem)
                continue
            bodies.append((stem, reason, text))

        ecosystem = [(s, r) for s, r, _ in bodies if s != "coding-philosophy"]
        has_philosophy = any(s == "coding-philosophy" for s, _, _ in bodies)

        preamble_parts = []
        if ecosystem:
            n = len(ecosystem)
            word = "One" if n == 1 else "Two"
            plural = "" if n == 1 else "s"
            verb = "applies" if n == 1 else "apply"
            preamble_parts.append(
                f"{word} coding standards document{plural} {verb} to this project."
            )
            for stem, reason in ecosystem:
                governs = STANDARDS_GOVERNS.get(stem, "governs its own languages")
                preamble_parts.append(f"`{stem}.md` {governs} — selected because {reason}.")
            if n > 1:
                preamble_parts.append(
                    "Each governs its own languages; do not apply one stack's conventions to "
                    "the other's files."
                )
            if has_philosophy:
                preamble_parts.append("`coding-philosophy.md` applies to all of it.")
        elif has_philosophy:
            preamble_parts.append(
                "Only `coding-philosophy.md` applies to this project — no ecosystem-specific "
                "markers were found."
            )

        result = {}
        if bodies:
            sections = [f"### {stem}.md\n\n{text}" for stem, _, text in bodies]
            content = " ".join(preamble_parts) + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
            result["hookSpecificOutput"] = {
                "hookEventName": "SessionStart",
                "additionalContext": content,
            }
        if missing:
            named = ", ".join(f"{m}.md" for m in missing)
            result["systemMessage"] = (
                f"house-rules plugin: could not load {named} — named in .claude/standards but "
                "not found in rules/standards/."
            )

        if not result:
            return 0
        emit(result)
        return 0
    except Exception:
        emit(
            {
                "systemMessage": "house-rules plugin: the coding-standards selector hit an "
                "internal error. No standards documents were injected for this session."
            }
        )
        return 0


# ---------------------------------------------------------------------------------------
# docstiers — a fourth SessionStart handler, its own entry so a failure here can never affect
# inject/profile/standards. Tier names are read out of
# skills/project-docs/SKILL.md by a human (this list), never invented at runtime; verify.py's
# drift check keeps the two from disagreeing. Full rationale: docs/Decisions.md, 2026-09-22, and
# rules/detail/docs-tiers.md.
# ---------------------------------------------------------------------------------------

DOCS_TIER_FILES = [
    "docs/README.md",
    "docs/Roadmap.md",
    "docs/ProjectState.md",
    "docs/Today.md",
    "docs/Decisions.md",
]
DOCS_TIER4_DIR = "docs/systems"
DEFAULT_GITHUB_OWNER = "Ajw2003"


def _tier4_present(root):
    d = os.path.join(root, *DOCS_TIER4_DIR.split("/"))
    if not os.path.isdir(d):
        return False
    return any(name.lower().endswith(".md") for name in os.listdir(d))


def _repo_owner_from_config(git_dir):
    """Read the GitHub owner out of .git/config's remote URL(s), no subprocess.

    Returns (owner_or_None, note). note is set whenever owner is None, explaining why - an
    absent/unreadable/garbage config and "no owner found" all read the same to the caller
    (not owned), but the reason differs and gets stated in the emitted text either way.
    """
    config_path = os.path.join(git_dir, "config")
    try:
        text = _read_text(config_path)
    except OSError as exc:
        return None, "could not read .git/config (%s)" % exc

    urls = re.findall(r"(?m)^\s*url\s*=\s*(\S+)", text)
    if not urls:
        return None, ".git/config has no remote url"

    for url in urls:
        m = re.match(r"^https?://[^/]+/([^/]+)/", url)
        if not m:
            m = re.match(r"^(?:ssh://)?[^@/]+@[^:/]+[:/]([^/]+)/", url)
        if m:
            return m.group(1), None
    return None, "no remote url matched a recognizable owner/repo form (%s)" % urls[0]


def event_docstiers():
    try:
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        missing = [f for f in DOCS_TIER_FILES if not os.path.isfile(os.path.join(root, *f.split("/")))]
        if not _tier4_present(root):
            missing.insert(3, "docs/systems/*.md (at least one system document)")

        if not missing:
            # All six tiers present - the one other deliberate silent exception besides
            # handover. This runs every session; a trace here costs something on every one of
            # them for a fact that is true almost always.
            return 0

        git_dir = _git_dir(root)
        configured_owner = os.environ.get("HOUSE_RULES_GITHUB_OWNER", "").strip() or DEFAULT_GITHUB_OWNER
        if git_dir is None:
            ownership_note = "This is not a git repository, so no ownership check applies."
        else:
            owner, note = _repo_owner_from_config(git_dir)
            if owner is not None and owner.strip().lower() == configured_owner.lower():
                ownership_note = (
                    "This repo's remote is owned by %s (the configured owner), so no "
                    ".git/info/exclude step is needed." % configured_owner
                )
            else:
                reason = note or ("the remote owner is %r, not %r" % (owner, configured_owner))
                ownership_note = (
                    "This repo is not owned by the configured account (%s) - %s. Also add "
                    "every scaffolded path to .git/info/exclude, so the new docs never leave "
                    "this machine and never enter this repo's history."
                    % (configured_owner, reason)
                )

        text = (
            "House rules, documentation goes in tiers: this project is missing %d of the six "
            "documentation tiers - %s. Load house-rules:project-docs and scaffold the missing "
            "tiers before any other work, in every repo. %s"
            % (len(missing), ", ".join(missing), ownership_note)
        )
        emit(
            {
                "suppressOutput": True,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": text,
                },
            }
        )
        return 0
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the docs-tier check hit an internal "
                "error (%s: %s) and did not run for this session." % (type(exc).__name__, exc)
            }
        )
        return 0


# ---------------------------------------------------------------------------------------
# versioncheck — a fifth SessionStart handler. Why three version copies, and why guard holds a
# marker for this: docs/architecture.md, "versioncheck checks three copies of the version".
# ---------------------------------------------------------------------------------------

# A fork of this repo under a different owner should point this at its own copy - hence the
# env override rather than only a hardcoded constant.
_GITHUB_PLUGIN_JSON_URL = (
    "https://raw.githubusercontent.com/Ajw2003/AjsClaudeCodeTools/main/"
    "claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json"
)
_GITHUB_FETCH_TIMEOUT = 4.0

# Relative to a marketplace clone's root (~/.claude/plugins/marketplaces/<name>/...) - matches
# the "source" field the plugin's own .claude-plugin/marketplace.json declares for itself.
_MARKETPLACE_PLUGIN_JSON_REL = os.path.join(
    "claude-house-rules", "plugins", "house-rules", ".claude-plugin", "plugin.json"
)


def _version_check_enabled():
    return os.environ.get("HOUSE_RULES_VERSION_CHECK", "on").strip().lower() not in _TRACE_OFF


def _marketplace_plugin_json_path(problems):
    """The marketplace clone's plugin.json, or "" if none found (see docs/architecture.md)."""
    marketplaces_root = os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "marketplaces"
    )
    try:
        names = sorted(os.listdir(marketplaces_root)) if os.path.isdir(marketplaces_root) else []
    except OSError as exc:
        problems.append(
            "could not list ~/.claude/plugins/marketplaces (%s)" % type(exc).__name__
        )
        return ""
    for market in names:
        candidate = os.path.join(marketplaces_root, market, _MARKETPLACE_PLUGIN_JSON_REL)
        if os.path.isfile(candidate):
            return candidate
    return ""


def _marketplace_version(problems):
    override = os.environ.get("HOUSE_RULES_VC_MARKETPLACE")
    if override is not None:
        return override
    path = _marketplace_plugin_json_path(problems)
    if not path:
        return ""
    try:
        return json.loads(_read_text(path)).get("version", "") or ""
    except Exception as exc:
        problems.append(
            "could not read the marketplace clone's plugin.json (%s)" % type(exc).__name__
        )
        return ""


def _github_version(problems):
    override = os.environ.get("HOUSE_RULES_VC_GITHUB")
    if override is not None:
        return override
    url = os.environ.get("HOUSE_RULES_VC_GITHUB_URL") or _GITHUB_PLUGIN_JSON_URL
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=_GITHUB_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        return data.get("version", "") or ""
    except Exception as exc:
        problems.append(
            "could not reach GitHub to check the published version (%s)" % type(exc).__name__
        )
        return ""


_VC_SESSION_ID_RE = re.compile(r'"session_id"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _vc_session_id(payload):
    m = _VC_SESSION_ID_RE.search(payload or "")
    if not m:
        return ""
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\").strip()


def _outdated_marker_path(session_id):
    if not session_id:
        return ""
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id)[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-outdated-%s.json" % safe)


def _write_outdated_marker(session_id, reasons):
    path = _outdated_marker_path(session_id)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"reasons": reasons}, f)
    except OSError as exc:
        sys.stderr.write(
            "house-rules versioncheck: could not write the session marker (%s); the guard "
            "prompt on the first shell command will not fire, only the SessionStart "
            "warning.\n" % exc
        )


def _read_and_clear_outdated_marker(session_id):
    """Read this session's out-of-date marker once, then delete it.

    Consumed rather than merely read, so the guard prompt it drives fires on the first
    Bash/PowerShell call of the session only - not every call after it, which would make
    every command in an out-of-date session carry an extra prompt instead of one.
    """
    path = _outdated_marker_path(session_id)
    if not path or not os.path.isfile(path):
        return None
    try:
        data = json.loads(_read_text(path))
    except Exception:
        data = None
    try:
        os.remove(path)
    except OSError as exc:
        # Not fatal - the marker just lingers and gets ignored by every future session, whose
        # own session_id will not match its filename. Worth a line so a permissions problem on
        # the temp dir is not invisible, but never worth failing the command over.
        sys.stderr.write(
            "house-rules guard: could not remove the out-of-date marker %r (%s); it will be "
            "ignored on future calls anyway.\n" % (path, exc)
        )
    return data


_VC_UPDATE_CMD = "claude plugin update house-rules@aj-house-rules"
_VC_MARKETPLACE_CMD = "claude plugin marketplace update aj-house-rules"


def event_versioncheck():
    try:
        if not _version_check_enabled():
            return 0

        payload = read_payload()
        session_id = _vc_session_id(payload)

        problems = []
        installed = _plugin_version(problems)
        market_version = _marketplace_version(problems)
        github_version = _github_version(problems)

        reasons = []
        if installed and market_version and installed != market_version:
            reasons.append(
                "installed copy is %s but the local marketplace clone has %s - run `%s`."
                % (installed, market_version, _VC_UPDATE_CMD)
            )
        if market_version and github_version and market_version != github_version:
            reasons.append(
                "the local marketplace clone is %s but GitHub's default branch has %s - the "
                "marketplace clone itself has not synced. Run `%s`, then `%s`."
                % (market_version, github_version, _VC_MARKETPLACE_CMD, _VC_UPDATE_CMD)
            )
        elif not market_version and installed and github_version and installed != github_version:
            # The marketplace clone could not be found/read at all - fall back to comparing
            # the installed copy straight against GitHub so a mismatch is still caught.
            reasons.append(
                "installed copy is %s but GitHub's default branch has %s (the local "
                "marketplace clone could not be checked). Run `%s`, then `%s`."
                % (installed, github_version, _VC_MARKETPLACE_CMD, _VC_UPDATE_CMD)
            )

        if not reasons:
            if problems:
                trace(
                    "versioncheck: could not fully verify the plugin is current - %s"
                    % "; ".join(problems)
                )
            else:
                trace(
                    "versioncheck: installed %s matches the marketplace clone and GitHub's "
                    "default branch." % (installed or "unknown")
                )
            return 0

        _write_outdated_marker(session_id, reasons)

        banner_lines = [
            "",
            "=" * 70,
            "HOUSE-RULES PLUGIN IS OUT OF DATE",
            "=" * 70,
            "",
            "Before doing any other work this session: tell the user plainly that this "
            "session is running an out-of-date copy of the house-rules plugin, and ask for "
            "permission to update it yourself, right now, on this machine - the same machine "
            "the check above just read, so your own shell tool reaches the exact install that "
            "needs fixing. Then stop and wait for the user's answer. Reporting the problem and "
            "continuing into unrelated work in the same turn is not the same as asking.",
            "",
            "If they say yes: run the command(s) below yourself, in order, right now, and "
            "report the real output rather than the command. If they say no, or this session "
            "has no shell tool to run them with, relay the command(s) instead - through the "
            "step-card format, marked `UNTESTED:` since this hook relayed them and they have "
            "not been run on this machine.",
            "",
        ]
        banner_lines.extend("- %s" % r for r in reasons)
        banner_lines.append("")
        banner_lines.append(
            "As a second, harness-enforced signal in case this context gets missed, the "
            "first Bash/PowerShell command run this session will also carry a permission "
            "prompt repeating this notice, once."
        )
        banner_lines.append("=" * 70)
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(banner_lines),
                }
            }
        )
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the version-freshness check hit an "
                "internal error (%s) and could not run for this session." % type(exc).__name__
            }
        )
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
    "- Match response depth to the task; build only what was asked, and ask instead of "
    "assuming.\n"
    "- Find out what machine you are on and build for that. The coding standards injected "
    "at session start are binding, each governing only its own languages.\n"
    "- Deliver a whole workflow: exact commands to run, nothing left for the user to "
    "configure by hand.\n"
    "- Artifacts are real files in the project directory, not chat and not a temp "
    "directory.\n"
    "- Never hand over a command you have not run where the user will run it. Running "
    "something similar is not running it.\n"
    "- Hand every command over in the step-card format: --- delimiters, ### Step N of M, "
    "the absolute folder and the shell named in prose and correct as the fence label, one "
    "fenced block per step, then You should see:. If you did not run it, UNTESTED: is the "
    "first line of the step, above the fence."
)

SCOPE_REMINDER_SHORT = (
    "House rules reminder: hand steps over in the step-card format (--- delimiters, ### Step "
    "N of M, one fenced block per step, You should see:). Never hand over a command you have "
    "not run. Build only what was asked - where it is ambiguous, ask instead of assuming."
)

# The delegation clause. delegate only fires on ExitPlanMode, so an auto or accept-edits
# session - which house-rules.md says the rule explicitly covers - never sees it, and neither
# does a plan simply agreed in conversation. This closes that gap from the prompt side, which
# is the only stateless place to close it: the go-ahead is in the prompt text.
SCOPE_DELEGATE_CLAUSE = (
    "\n- This reads like a go-ahead on settled work. Hand the implementation to the "
    "@house-rules:executor subagent rather than running it on the planning model; its "
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
        if m:
            field = m.group(0)
            if _SCOPE_COMMAND_HINT_RE.search(field):
                reminder = SCOPE_REMINDER
            if _SCOPE_GOAHEAD_RE.search(field):
                reminder = reminder + SCOPE_DELEGATE_CLAUSE
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

# `git` plus any run of global options before the subcommand.
# Why the alternation's first branch exists: docs/architecture.md, "The pre-existing hole this exposed".
_GIT = (
    r"git\s+((?:-[cC]|--git-dir|--work-tree|--namespace|--exec-path|--super-prefix)"
    r"[=\s]\s*[^\s]+\s+|-[^\s]+\s+)*"
)

# Marks a pattern the commit rule stands down for when the checkout is on a branch I created.
# Everything without it prompts on every branch, mine included. See the ownership helpers below
# and "Commit constantly on my own branches, never on theirs" in rules/house-rules.md.
OWNED = "owned-branch-exempt"

GUARD_R3 = [
    # Force-pushing is not a checkpoint — it rewrites history that was already backed up — so
    # it prompts even on my own branch. Listed before the plain push so that when both match,
    # the non-exempt reason is the one that survives into the prompt.
    (
        _GIT + r"push\b.*(--force|--force-with-lease|(^|\s)-f([^0-9A-Za-z-]|$))",
        "rewrites remote history (force push)",
    ),
    (
        _GIT + r"push([^0-9A-Za-z-]|$)",
        "reaches a remote (push)",
        OWNED,
    ),
    (
        _GIT + r"commit([^0-9A-Za-z-]|$)",
        "writes history (commit)",
        OWNED,
    ),
    # Not exemptible on any branch. reset/clean/revert destroy work that is not yet a
    # checkpoint, and rebase/merge/cherry-pick/am/apply are how a hook would end up finishing
    # something the user started — which the rule bans even on a branch named after me.
    (
        _GIT + r"(reset|revert|clean|rebase|merge|filter-branch|cherry-pick|am|apply)([^0-9A-Za-z-]|$)",
        "discards work or finishes an operation you started",
    ),
]

GUARD_R4 = [
    (
        # Was -r/-f only, so a plain `rm styles.css` - no recursive or force flag needed to
        # delete a single existing file - slipped through unasked. Deleting one file this way is
        # exactly the mechanism behind the CSS-file regression this rule now also has to catch.
        r"(^|[^0-9A-Za-z_./-])rm\s+\S",
        "deletes one or more files",
    ),
    (r"Remove-Item", "deletes files (Remove-Item)"),
    (r"(del|erase)\s+/[fqs]|rmdir\s+/s", "deletes files (del /f or rmdir /s)"),
    (r"Stop-Process|taskkill|pkill|kill\s+-9", "kills a running process"),
    (
        r"Clear-Content|truncate\s+-s",
        "truncates or overwrites file contents in place",
    ),
    (
        _GIT + r"(checkout\s+(--|\.(\s|$))|restore([^0-9A-Za-z-]|$))",
        "throws away uncommitted edits to a file (git checkout -- / git restore)",
    ),
    (
        _GIT + r"stash\s+(drop|clear)([^0-9A-Za-z-]|$)",
        "deletes stashed work permanently (git stash drop / clear)",
    ),
]

GUARD_BUCKETS = [
    ("Never hide work in a background window or a silent process", GUARD_R1),
    ("Commit constantly on my own branches, never on theirs", GUARD_R3),
    ("Never take a destructive action without checking first", GUARD_R4),
]

OWNED_BRANCH_PREFIX = "claude/"

# A command that names its own repo, git dir or work tree is not talking about the checkout
# this hook can see, so the branch read below would be the wrong branch to judge it by. Broad
# on purpose — `grep -C 3` in the same command line costs an extra keypress, and that is the
# direction guard is allowed to be wrong in.
_OTHER_REPO_RE = re.compile(r"(^|\s)(-C(\s|=)|--git-dir|--work-tree)")


def _git_dir(start):
    """Walk up from `start` looking for `.git`, returning the resolved git directory."""
    d = os.path.abspath(start)
    while True:
        candidate = os.path.join(d, ".git")
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(candidate):
            # A worktree or submodule: `.git` is a file holding `gitdir: <path>`.
            for line in _read_text(candidate).splitlines():
                if line.startswith("gitdir:"):
                    p = line.split(":", 1)[1].strip()
                    return os.path.abspath(p if os.path.isabs(p) else os.path.join(d, p))
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def branch_ownership():
    """Whose branch is this checkout on? Returns (is_mine, branch_name, note).

    Mechanism and invariants: doc-ref ee0f docs/systems/hook-engine.md (Invariants) and
    doc-ref d2a4 docs/systems/hook-engine.md (Traps).
    """
    try:
        git_dir = _git_dir(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return False, None, "this directory is not inside a git repository"
        head = _read_text(os.path.join(git_dir, "HEAD")).strip()
    except Exception as exc:
        return False, None, "could not read .git/HEAD (%s)" % exc

    if not head.startswith("ref:"):
        return False, None, "HEAD is detached, so there is no branch to own"

    ref = head.split(":", 1)[1].strip()
    if not ref.startswith("refs/heads/"):
        return False, None, "HEAD points at %s, which is not a branch" % ref

    branch = ref[len("refs/heads/") :]
    return branch.startswith(OWNED_BRANCH_PREFIX), branch, None


# tier 3: pull out just "command":"..." — the first one. Allows backslash-escaped quotes.
_COMMAND_FIELD_RE = re.compile(r'"command"\s*:\s*"(?:[^"\\]|\\.)*"')


def _guard_subject(payload):
    m = _COMMAND_FIELD_RE.search(payload)
    return m.group(0) if m else payload


_COMMAND_VALUE_RE = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _trace_subject(subject, limit=60):
    """The command as a human reads it, collapsed to one short line.

    Why this decodes separately from matching: doc-ref 361f docs/systems/hook-engine.md
    (Invariants).
    """
    m = _COMMAND_VALUE_RE.search(subject)
    if m:
        try:
            text = json.loads('"%s"' % m.group(1))
        except ValueError:
            text = m.group(1)
    else:
        text = subject
    flat = " ".join(text.split())
    if len(flat) > limit:
        flat = flat[: limit - 1] + "\u2026"
    return "`%s`" % flat


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
        trace("guard: empty payload - nothing was checked for this call.")
        return 0

    subject = _guard_subject(payload)
    outdated = _read_and_clear_outdated_marker(_vc_session_id(payload))

    is_mine, branch, ownership_note = branch_ownership()
    # A command carrying -C / --git-dir / --work-tree acts on a repo other than the one we
    # just read the branch from, so the exemption cannot be justified and is withheld.
    elsewhere = bool(_OTHER_REPO_RE.search(subject))
    exempting = is_mine and not elsewhere

    hits = {title: [] for title, _ in GUARD_BUCKETS}
    exempted = []
    for title, patterns in GUARD_BUCKETS:
        for entry in patterns:
            pattern, reason = entry[0], entry[1]
            if not re.search(pattern, subject, re.IGNORECASE):
                continue
            if exempting and len(entry) > 2 and entry[2] == OWNED:
                exempted.append(reason)
            else:
                hits[title].append(reason)

    if not any(hits.values()) and not outdated:
        # The allow path. Silent, this is the plugin's least distinguishable "ran and decided
        # not to fire" from "never ran" - and it is the security-shaped backstop, so that is
        # the worst place to leave the ambiguity.
        if exempted:
            trace(
                "guard: checked %s - %s on `%s`, which is mine to commit on."
                % (_trace_subject(subject), " and ".join(exempted), branch)
            )
        else:
            trace("guard: checked %s - no house rule matched." % _trace_subject(subject))
        return 0

    lines = ["Your house rules want you asked before this runs:"]
    if outdated:
        lines.append("")
        lines.append("  PLUGIN OUT OF DATE (found at session start, not by this command):")
        for r in outdated.get("reasons", []):
            lines.append("    - %s" % r)
    for title, _ in GUARD_BUCKETS:
        reasons = hits[title]
        if reasons:
            lines.append("")
            lines.append(f"  Rule: {title}")
            for r in reasons:
                lines.append(f"    - {r}")

    # Why the prompt names the branch: docs/architecture.md, "What the exemption does and does not cover".
    if hits["Commit constantly on my own branches, never on theirs"]:
        why_not_exempt = None
        if elsewhere:
            why_not_exempt = (
                "  This command names another repo (-C / --git-dir), so the branch I can see "
                "is not the one it acts on."
            )
        elif ownership_note:
            why_not_exempt = "  I could not establish branch ownership: %s." % ownership_note
        elif not is_mine:
            why_not_exempt = (
                "  You are on `%s`, which is yours, not a `claude/` branch." % branch
            )
        if why_not_exempt:
            lines.append("")
            lines.append(why_not_exempt)

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
# guardwrite — PreToolUse on Write. Fails closed and loud, same contract as guard.
# doc-ref bf94 docs/systems/hook-engine.md (Invariants)
# ---------------------------------------------------------------------------------------

RULE_EDIT_IN_PLACE = "Edit in place; a full rewrite is a delete, not an edit"


def _guardwrite_resolve(file_path):
    if not file_path or os.path.isabs(file_path):
        return file_path
    base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(base, file_path)


_WRITE_CONTENT_RE = re.compile(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _guardwrite_new_line_count(payload):
    m = _WRITE_CONTENT_RE.search(payload)
    if not m:
        return None
    try:
        text = json.loads('"%s"' % m.group(1))
    except ValueError:
        text = m.group(1)
    return len(text.splitlines())


def event_guardwrite():
    try:
        payload = read_payload()
    except Exception:
        sys.stderr.write(
            "house-rules guardwrite: could not read the hook payload from stdin.\n"
        )
        sys.stderr.write("Blocking this write rather than letting it through unchecked.\n")
        return 2

    if not payload:
        trace("guardwrite: empty payload - nothing was checked for this call.")
        return 0

    file_path = _extract_file_path(payload)
    if not file_path:
        trace("guardwrite: no file_path field found - nothing was checked for this call.")
        return 0

    resolved = _guardwrite_resolve(file_path)
    try:
        exists = os.path.isfile(resolved)
    except OSError as exc:
        sys.stderr.write(
            "house-rules guardwrite: could not check whether %r already exists (%s); "
            "blocking rather than letting an unchecked overwrite through.\n" % (resolved, exc)
        )
        return 2

    if not exists:
        trace("guardwrite: %s does not exist yet - a new file, not an overwrite." % file_path)
        return 0

    old_lines = None
    try:
        old_lines = len(_read_text(resolved).splitlines())
    except OSError as exc:
        sys.stderr.write(
            "house-rules guardwrite: %s exists but could not be read (%s) to count its "
            "existing lines; asking anyway, with that count left out.\n" % (resolved, exc)
        )

    new_lines = _guardwrite_new_line_count(payload)

    lines = [
        "Your house rules want you asked before this runs:",
        "",
        "  Rule: %s" % RULE_EDIT_IN_PLACE,
        "    - This Write replaces the ENTIRE existing contents of `%s`." % file_path,
    ]
    if old_lines is not None and new_lines is not None:
        lines.append(
            "    - %d existing line(s) would be discarded and replaced with %d new line(s)."
            % (old_lines, new_lines)
        )
    lines.append(
        "    - Editing in place (the Edit tool, or a targeted patch) changes only the lines "
        "that need to change. Write throws away everything else in the file, whether or not "
        "this call meant to touch it."
    )
    lines.append("")
    lines.append(
        "Before approving, Claude should already have said, in chat, exactly what existing "
        "content this discards and why an in-place edit will not do."
    )
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


# The rule is "every artifact lives in the project directory", so this list is every extension a
# document deliverable actually arrives as. It shipped as md|txt only, which meant an .html report
# written to the scratchpad was invisible to the one backstop that exists to catch exactly that -
# a restatement of the rule quietly narrower than the rule. Runnable extensions stay out on
# purpose: a .py in a temp directory is scratch work, and event_runnable already owns that case.
_ARTIFACT_EXT_RE = re.compile(r"\.(md|txt|html|csv|json|svg|pdf)$", re.IGNORECASE)

# Two destination groups within that union: hand-authored documents stay in docs/, but tool
# output (a report, an export, anything from the Artifact tool) goes to docs/generated/ instead
# so docs/ stays readable as documentation rather than mixed with regenerated deliverables.
_DOC_EXT_RE = re.compile(r"\.(md|txt)$", re.IGNORECASE)
_GENERATED_EXT_RE = re.compile(r"\.(html|csv|json|svg|pdf)$", re.IGNORECASE)

ARTIFACT_NOTE = (
    "House rules, artifact custody: that document was written outside the project "
    "directory, so it is not tracked and will not outlive this session. Before you finish "
    "this task, copy it into the project as a real file - {where} - and tell the user the "
    "path. This is a reminder to you; the user was not prompted and does not need to do "
    "anything."
)


def event_artifact():
    try:
        payload = read_payload()
        if not payload:
            # Not "nothing to do" - "could not tell". An empty payload means the check never
            # got its input, which is not the same as a file that did not qualify.
            emit(
                {
                    "systemMessage": "house-rules plugin: the artifact-location reminder got an "
                    "empty payload and did not run for this call."
                }
            )
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        base = re.split(r"[\\/]", file_path)[-1]
        if not _ARTIFACT_EXT_RE.search(base):
            trace("artifact: %s is not a document extension - not checked." % base)
            return 0
        if not _is_outside_project(file_path):
            trace("artifact: %s is inside the project - nothing to copy." % base)
            return 0
        if _GENERATED_EXT_RE.search(base):
            where = "docs/generated/ for generated or visual artifacts"
        else:
            where = "docs/ for documents, docs/plans/ for plans"
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": ARTIFACT_NOTE.format(where=where),
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
    "command you have not run. One clean run is not proof it works: run it twice, since the "
    "second run meets the state the first one left behind, and give it a realistic input "
    "rather than a toy one - a green suite reports only on the cases someone thought to "
    "write. This is a reminder to you; the user was not prompted and does not need to do "
    "anything."
)

_RUNNABLE_EXT_RE = re.compile(
    r"\.(py|js|mjs|cjs|ts|sh|ps1|bat|cmd)$", re.IGNORECASE
)
_RUNNABLE_BARE_RE = re.compile(
    r"^(dockerfile|docker-compose\.ya?ml)$", re.IGNORECASE
)

# A .cs file is not "run" the way a script is - there is no interpreter to invoke - so it never
# matched _RUNNABLE_EXT_RE, and Unity code written by Claude got no PostToolUse nudge at all.
# That gap is exactly what let "should compile" ship unchecked. Handled here rather than as a
# separate hook event: same trigger (PostToolUse on Write), same "never obstruct, never go
# quiet" contract, and it reuses the existing outside-project scratch-work check.
_COMPILED_EXT_RE = re.compile(r"\.cs$", re.IGNORECASE)

COMPILE_NOTE = (
    "House rules, compiled code: you just created a compiled-language file. \"Should compile\" "
    "is a guess, not a result. A hand-rolled stand-in for the real API surface (a fake "
    "UnityEngine, a stub assembly) proves the stand-in compiles, not that this code does. "
    "Compile the real thing with the real compiler before you say it builds: Unity in batch "
    "mode against the real project, or dotnet build/msbuild against the project's own .csproj "
    "- never one generated to make the check pass. Where nothing here can invoke the real "
    "toolchain, say exactly that and hand the code over as UNTESTED: rather than reporting an "
    "outcome the check never produced. This is a reminder to you; the user was not prompted "
    "and does not need to do anything."
)


def event_runnable():
    try:
        payload = read_payload()
        if not payload:
            # Not "nothing to do" - "could not tell". An empty payload means the check never
            # got its input, which is not the same as a file that did not qualify.
            emit(
                {
                    "systemMessage": "house-rules plugin: the run-what-you-wrote reminder got an "
                    "empty payload and did not run for this call."
                }
            )
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        base = re.split(r"[\\/]", file_path)[-1]
        if _COMPILED_EXT_RE.search(base):
            if _is_outside_project(file_path):
                trace("runnable: %s is outside the project - scratch work, not compiled." % base)
                return 0
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": COMPILE_NOTE,
                    }
                }
            )
            return 0
        if not (_RUNNABLE_EXT_RE.search(base) or _RUNNABLE_BARE_RE.match(base)):
            trace("runnable: %s is not a runnable file - nothing to run." % base)
            return 0
        if _is_outside_project(file_path):
            trace("runnable: %s is outside the project - scratch work, not run." % base)
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
    "house-rules:executor). The plan is already committed to the repo as a real file (per the "
    "artifact rule); pass that file's path in the delegation prompt so the executor reads the "
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


def event_delegate():
    try:
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": DELEGATE_NOTE,
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
# from announce. doc-ref c67d docs/Decisions.md
SUBAGENT_SECTION_MARKER = "<!-- subagent -->"
SUBAGENT_CORE_CHAR_LIMIT = 4_500

SUBAGENT_MANDATE = (
    "\nYour final report must list every command you ran and its result verbatim, every file "
    "you wrote or edited, and anything you could not do.\n"
)


def _subagent_core(rules_path=None):
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
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", _plugin_root())
    return _truncate_with_notice(text, SUBAGENT_CORE_CHAR_LIMIT, "the subagent rules core"), problems


def event_subagentrules():
    """SubagentStart: inject the subagent core, and tell the user where its transcript will
    land, before it exists - so it is findable without waiting for verdict to say so."""
    try:
        if not _delegation_enabled():
            return 0
        payload = read_payload()
        core, problems = _subagent_core()
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


def _field(pattern, payload, problems=None):
    """The extracted value, or "" for a field that is simply absent.

    A field that is not there is an ordinary answer, not a failure - the callers below
    report it as "not in payload". An actual failure while extracting is different, and is
    recorded for the caller to report rather than collapsing into the same empty string:
    see "nothing fails silently" in the module docstring.
    """
    value = ""
    try:
        m = pattern.search(payload or "")
        if m:
            value = m.group(1).replace('\\"', '"').replace("\\\\", "\\").strip()
    except Exception as exc:
        if problems is not None:
            problems.append("could not extract a payload field (%s)" % type(exc).__name__)
    return value


def _agent_file(agent_type):
    """The shipped definition for this agent, or "" if the plugin does not ship it.

    agent_type arrives plugin-scoped ("house-rules:executor"), so the scope prefix is
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


def _plugin_version(problems=None):
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", ".claude-plugin", "plugin.json")
    version = ""
    try:
        version = json.loads(_read_text(path)).get("version", "") or ""
    except Exception as exc:
        if problems is not None:
            problems.append("could not read the plugin version (%s)" % type(exc).__name__)
    return version


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


def _transcript_candidates(payload):
    """Where the subagent's own transcript might be, most authoritative first.

    Why this probes rather than assumes: docs/architecture.md, "The transcript is probed,
    never assumed, and that is deliberate."
    """
    out = []
    direct = _field(_AGENT_TRANSCRIPT_RE, payload)
    if direct:
        out.append(direct)
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
        # subagent said about itself. A failure building it is reported, never silent, and
        # never drops the model-check report already gathered above (probed: neither a
        # SubagentStop additionalContext nor systemMessage reaches the parent session's
        # model context in-turn - docs/Decisions.md, 2026-09-23, doc-ref c67d - so this
        # rides the one channel proven to work, the same one announce/verdict already use).
        try:
            commands, wrote, tool_counts = _audit_summary(found)
            summary_lines = ["AUDIT (from the transcript, not the subagent's own report):"]
            summary_lines.extend("  cmd: %s" % l for l in _capped_lines(commands, AUDIT_MAX_COMMANDS, AUDIT_COMMAND_CHARS))
            summary_lines.extend("  wrote: %s" % l for l in _capped_lines(wrote, AUDIT_MAX_COMMANDS, AUDIT_COMMAND_CHARS))
            if tool_counts:
                summary_lines.append(
                    "  tool uses: %s" % ", ".join("%s x%d" % (n, c) for n, c in sorted(tool_counts.items()))
                )
            summary_lines.append(
                "Reconcile the subagent's report against this record; flag every claim the "
                "record does not support before relaying."
            )
            bits.append("\n".join(summary_lines))
        except OSError as exc:
            bits.append(
                "AUDIT COULD NOT TELL: transcript at %s could not be re-read for the audit "
                "summary (%s)" % (found, type(exc).__name__)
            )

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

_TOGGLE_OFF = {"off", "0", "false", "no"}

# Same shape as _COMMAND_FIELD_RE: match the raw JSON slice, escapes included, and search inside
# it. Backticks are not escaped in JSON, so a fenced block survives verbatim in the payload.
_LAST_MESSAGE_FIELD_RE = re.compile(r'"last_assistant_message"\s*:\s*"(?:[^"\\]|\\.)*"')


# The three marks a card cannot be missing: the rule that opens and closes it, the step heading,
# and the expected-output line. A reply carrying all three is already in the shape this check
# exists to produce, so the check has nothing to add - see _reply_needs_the_handover_check.
_CARD_MARKERS = ("---", "###", "You should see:")


def _reply_is_already_a_card(reply):
    return all(mark in reply for mark in _CARD_MARKERS)


def _reply_needs_the_handover_check(payload):
    """Three tiers, the same ladder guard uses on its own input.

    Why not firing on a compliant reply is the point, and the cost that trades away:
    docs/architecture.md, "handover is the one deliberate exception".
    """
    m = _LAST_MESSAGE_FIELD_RE.search(payload)
    if m is None:
        return True
    reply = m.group(0)
    return "```" in reply and not _reply_is_already_a_card(reply)


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

    if re.search(r'"stop_hook_active"\s*:\s*true', payload):
        # The retry after this check already fired. Tracing here would say the same thing
        # twice for one turn, so this is the one stand-down that stays quiet.
        return 0

    if not _reply_needs_the_handover_check(payload):
        # The one handler that must NOT trace - direct rule conflict, not a cost argument.
        # docs/architecture.md, "handover is the one deliberate exception".
        return 0

    # additionalContext, not decision: "block". Both continue the turn under the same loop
    # protections, but this one is labelled Stop hook feedback rather than raising a hook
    # error - and this hook is guidance working as designed, not a failure.
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": HANDOVER_NOTE,
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# harvest - PostToolUse on Write|Edit. Never obstructs, never goes quiet.
# ---------------------------------------------------------------------------------------

HARVEST_NOTE = (
    "House rules, long-form reasoning belongs in a document: the file you just wrote carries "
    "{n} long comment block{s} - design rationale, a post-mortem, a derivation, a platform "
    "quirk - sitting in the source instead of in docs/. {where} Do not change how you write; "
    "writing the reasoning down as it occurs is the right habit. What changes is where it "
    "lands. Before you finish this turn, move each block to where it belongs: an ongoing "
    "mechanism, invariant, or operational gotcha still goes into the tier-4 system document "
    "that owns that code (docs/systems/*.md), creating one if none does, under the section "
    "that fits - the design into How it works, an operational gotcha into Traps, a rule that "
    "must stay true into Invariants. Design rationale, a rejected approach, or a post-mortem is "
    "different - it is a record of a choice, not current truth about the system - so it becomes "
    "a dated entry in docs/Decisions.md instead. Either way, leave a one-line pointer at the "
    "site: doc-ref <id> <path>, where <id> is a 4-hex id whose <!-- ref:<id> --> marker sits "
    "alone on its own line under the moved note's heading in the doc, made with docref.py new, "
    "so the code still leads to the "
    "reasoning and docref.py check can prove it still does. Anything "
    "a reader genuinely needs at that exact "
    "line to not break the code stays an ordinary comment - only the long-form context moves. "
    "The move is mechanical once the thinking is done, so hand it to the "
    "@house-rules:archivist subagent (Task tool, subagent_type house-rules:archivist), naming "
    "the file and the blocks, rather than doing it on the planning model. This is a reminder "
    "to you; the user was not prompted and does not need to do anything."
)

# Source files only. A write to a .md or .json file is not a decision this handler makes - it
# has no business there at all - which is why that path is the one place harvest stays fully
# silent. Everything in jurisdiction gets a trace line whether or not it fires.
_HARVEST_EXT_RE = re.compile(
    r"\.(cs|py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|c|h|cpp|hpp|rb|php|swift|kt|sh|ps1)$",
    re.IGNORECASE,
)

# Tunable. Characters are the only size criterion: they are counted over the joined text, so
# wrapping and indentation do not move a comment across the line. A line count was tried
# alongside it (3 lines OR 150 chars) and added nothing but false positives - three short
# lines qualified. See docs/comment-harvest-calibration.md for what this number catches.
HARVEST_MIN_CHARS = 500

# Wall-clock budget for the scan, well inside hooks.json's 10s timeout. There is no cap on
# input size: a big file is scanned like any other, and only a scan that actually runs long
# is abandoned - loudly, naming the file and its size.
HARVEST_BUDGET_SECONDS = 3.0

_HARVEST_LINE_MARKERS = {
    "line": ("//", "#", "--"),
}
_HARVEST_REJECT_LICENSE = ("copyright", "spdx", "licensed under", "all rights reserved")
_HARVEST_REJECT_GENERATED = ("<auto-generated", "do not edit", "code generated by")


def _harvest_threshold(name, default, problems):
    """Read one HOUSE_RULES_HARVEST_MIN_CHARS override. A bad value is announced, not ignored."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        problems.append("%s=%r is not a whole number" % (name, raw))
        return default
    if value <= 0:
        problems.append("%s=%r is not a positive number" % (name, raw))
        return default
    return value


def _harvest_comment_runs(text, deadline=None):
    """Split content into runs of consecutive comment-only lines.

    One linear pass, str.startswith only - no per-line regex, so cost is O(n) in the content
    and a large file is a slow scan rather than a special case to bail out of. Returns
    (start_line, end_line, [body lines]) with 1-based line numbers.
    """
    runs = []
    current = None
    in_block = None  # the closing delimiter we are waiting for, or None

    for idx, raw in enumerate(text.split("\n"), start=1):
        if deadline is not None and (idx & 0x3FF) == 0 and _time.time() > deadline:
            # Out of budget mid-scan. Report what was found so far and say so; the caller
            # turns this into a named systemMessage rather than a hook the harness kills.
            if current is not None:
                runs.append(tuple(current))
            return runs, True
        line = raw.strip()
        body = None

        if in_block is not None:
            body = line
            if in_block in line:
                in_block = None
        elif line.startswith("/*"):
            body = line[2:].strip()
            if "*/" not in line[2:]:
                in_block = "*/"
        elif line.startswith("<#"):
            body = line[2:].strip()
            if "#>" not in line[2:]:
                in_block = "#>"
        elif line.startswith('"""') or line.startswith("'''"):
            quote = line[:3]
            body = line[3:].strip()
            if line.count(quote) < 2:
                in_block = quote
        elif line.startswith("*") and current is not None:
            # continuation line of a /* */ block that already closed its delimiter tracking
            body = line[1:].strip()
        else:
            for marker in _HARVEST_LINE_MARKERS["line"]:
                if line.startswith(marker):
                    rest = line[len(marker) :]
                    if marker == "//":
                        # C#'s /// doc-comment (and a plain //// divider) both start with
                        # more slashes than the marker itself - strip all of them, not just
                        # the first two, so a /// <summary> line reads as text, not as text
                        # with a stray slash glued to the front.
                        rest = rest.lstrip("/")
                    body = rest.strip()
                    break

        if body is None:
            if current is not None:
                runs.append(current)
                current = None
            continue

        if body and not body.strip("-=*_#/~ "):
            # A section divider. It belongs to the run (it does not break it) but it is
            # decoration, not text, and counting its characters is how a banner gets
            # mistaken for an essay.
            body = ""

        if current is None:
            current = [idx, idx, [body]]
        else:
            current[1] = idx
            current[2].append(body)

    if current is not None:
        runs.append(tuple(current))
    return runs, False


def _harvest_is_prose(lines):
    """Reject the things that are long but are not essays. Returns (ok, reason)."""
    joined = " ".join(lines).strip()
    low = joined.lower()

    if any(mark in low for mark in _HARVEST_REJECT_GENERATED):
        return False, "generated-file banner"
    if any(mark in low for mark in _HARVEST_REJECT_LICENSE):
        return False, "license header"

    # Shape before prose: commented-out code often has no sentence punctuation at all, and
    # reporting it as "fewer than two sentences" would name the symptom rather than the cause.
    # The trace is only worth having if the reason it gives is the real one.
    codeish = 0
    real = [ln for ln in lines if ln]
    for ln in real:
        if ln.endswith((";", "{", "}", ")", ",")) or ln.startswith(("if ", "for ", "return ")):
            codeish += 1
    if real and codeish * 2 > len(real):
        return False, "looks like commented-out code"

    sentences = low.count(". ") + low.count(".\t") + low.count("? ") + low.count("! ")
    if low.endswith("."):
        sentences += 1
    if sentences < 2:
        return False, "fewer than two sentences"

    return True, ""


def _harvest_is_file_preamble(line):
    """A line that a module docstring is allowed to sit under: a shebang or an encoding line."""
    stripped = line.strip()
    return stripped.startswith("#!") or "coding:" in stripped or "coding=" in stripped


def _harvest_blocks(text, min_chars, deadline, verbose, full_file=True):
    """Find the essay-shaped runs. Returns (blocks, near_misses, timed_out).

    full_file must be False for an Edit's new_string fragment. See docs/Decisions.md,
    "Fix the harvest handler treating an Edit fragment's line 1 as the file's header".
    """
    first_line = text.split("\n", 1)[0] if text else ""
    blocks = []
    misses = []
    runs, timed_out = _harvest_comment_runs(text, deadline)
    if timed_out:
        return blocks, misses, True
    for start, end, lines in runs:
        if _time.time() > deadline:
            return blocks, misses, True
        if full_file and (start == 1 or (start == 2 and _harvest_is_file_preamble(first_line))):
            # A file header - module docstring, shebang, encoding line - is documentation
            # that is already where it belongs. coding-philosophy.md asks for it. What this
            # handler is looking for is an essay buried in the body of the code.
            misses.append((start, end, len(lines), len(" ".join(lines)), "file header"))
            continue
        n_lines = len(lines)
        n_chars = len(" ".join(lines))
        if n_chars < min_chars:
            misses.append((start, end, n_lines, n_chars, "under threshold"))
            continue
        ok, reason = _harvest_is_prose(lines)
        if not ok:
            misses.append((start, end, n_lines, n_chars, reason))
            continue
        blocks.append((start, end, n_lines, n_chars))
    return blocks, misses, False


def _harvest_trace(base, blocks, misses, min_chars, ranged, verbose):
    """The one line this handler always says about a source file it looked at."""
    if blocks:
        if ranged:
            listed = ", ".join("%d-%d" % (b[0], b[1]) for b in blocks[:5])
        else:
            listed = "line ranges unavailable for an Edit fragment"
        more = "" if len(blocks) <= 5 else " (+%d more)" % (len(blocks) - 5)
        head = "harvest: %s - %d block%s: %s%s" % (
            base,
            len(blocks),
            "" if len(blocks) == 1 else "s",
            listed,
            more,
        )
    elif misses:
        longest = max(misses, key=lambda m: m[3])
        plural = "" if len(misses) == 1 else "s"
        # "none met" only holds when the longest run's own rejection reason was the size
        # check. See docs/Decisions.md, "Fix the harvest handler treating an Edit fragment's
        # line 1 as the file's header".
        met_threshold = longest[3] >= min_chars
        if not met_threshold:
            head = (
                "harvest: %s - %d comment run%s, none met %d chars; "
                "longest was %d line%s, %d chars"
                % (
                    base,
                    len(misses),
                    plural,
                    min_chars,
                    longest[2],
                    "" if longest[2] == 1 else "s",
                    longest[3],
                )
            )
        else:
            head = (
                "harvest: %s - %d comment run%s; largest was %d line%s, %d chars but "
                "rejected: %s"
                % (
                    base,
                    len(misses),
                    plural,
                    longest[2],
                    "" if longest[2] == 1 else "s",
                    longest[3],
                    longest[4],
                )
            )
    else:
        head = "harvest: %s - no comment runs found (threshold %d chars)" % (base, min_chars)

    if not verbose or not misses:
        return head
    detail = "; ".join(
        "%d-%d %dL/%dc %s" % (m[0], m[1], m[2], m[3], m[4]) for m in misses[:20]
    )
    return head + " | runs considered: " + detail


def event_harvest():
    try:
        toggle = os.environ.get("HOUSE_RULES_HARVEST", "on").strip().lower()
        if toggle in _TOGGLE_OFF:
            return 0
        # HOUSE_RULES_TRACE is the global lever and covers harvest too; HOUSE_RULES_HARVEST
        # =quiet drops just this handler's trace while keeping its reminder.
        quiet = toggle == "quiet" or not trace_enabled()
        verbose = os.environ.get("HOUSE_RULES_DEBUG", "").strip() not in ("", "0", "false", "no")

        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest check got an "
                    "empty payload and did not run for this call."
                }
            )
            return 0

        try:
            data = json.loads(payload)
        except ValueError as exc:
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest check could not "
                    "parse the tool payload (%s) and did not run for this call." % exc
                }
            )
            return 0

        tool_input = (data or {}).get("tool_input") or {}
        file_path = tool_input.get("file_path") or ""
        if not file_path:
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest check found no "
                    "file_path in the payload and did not run for this call."
                }
            )
            return 0

        base = re.split(r"[\\/]", file_path)[-1]
        if not _HARVEST_EXT_RE.search(base):
            # Out of jurisdiction. The only fully silent path in this handler.
            return 0

        # Write carries the whole file, so its line numbers are the file's. Edit carries a
        # fragment in new_string, whose offsets mean nothing in the file - reporting them
        # would put a confidently wrong file:line into a doc whose own convention is to cite
        # file:line, so the ranges are withheld instead.
        ranged = "content" in tool_input
        text = tool_input.get("content")
        if text is None:
            text = tool_input.get("new_string")
        if text is None:
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest check found "
                    "neither content nor new_string for %s and did not run for this call."
                    % base
                }
            )
            return 0
        if not isinstance(text, str):
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest check got a "
                    "non-text body for %s and did not run for this call." % base
                }
            )
            return 0

        problems = []
        min_chars = _harvest_threshold(
            "HOUSE_RULES_HARVEST_MIN_CHARS", HARVEST_MIN_CHARS, problems
        )

        deadline = _time.time() + HARVEST_BUDGET_SECONDS
        blocks, misses, timed_out = _harvest_blocks(
            text, min_chars, deadline, verbose, full_file=ranged
        )
        if timed_out:
            emit(
                {
                    "systemMessage": "house-rules plugin: the comment-harvest scan of %s "
                    "(%d bytes) exceeded its %gs budget and was abandoned, so that file was "
                    "not checked." % (base, len(text), HARVEST_BUDGET_SECONDS)
                }
            )
            return 0

        out = {}
        if blocks:
            if ranged:
                where = "Blocks: %s." % ", ".join(
                    "%s:%d-%d" % (base, b[0], b[1]) for b in blocks[:5]
                )
                if len(blocks) > 5:
                    where = where[:-1] + ", and %d more." % (len(blocks) - 5)
            else:
                where = (
                    "This was an Edit, so the payload carries only the replacement fragment "
                    "and the line numbers within it do not correspond to %s - find the "
                    "blocks by reading the file." % base
                )
            out["hookSpecificOutput"] = {
                "hookEventName": "PostToolUse",
                "additionalContext": HARVEST_NOTE.format(
                    n=len(blocks), s="" if len(blocks) == 1 else "s", where=where
                ),
            }

        if not quiet:
            trace = _harvest_trace(base, blocks, misses, min_chars, ranged, verbose)
            if problems:
                trace += " | ignoring bad override(s): %s - using the defaults" % "; ".join(
                    problems
                )
            out["systemMessage"] = trace
        elif problems:
            out["systemMessage"] = (
                "house-rules plugin: ignoring bad comment-harvest override(s): %s - using "
                "the defaults." % "; ".join(problems)
            )

        if out:
            emit(out)
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the comment-harvest reminder hit an "
                "error (%s: %s) and is offline for this call." % (type(exc).__name__, exc)
            }
        )
    return 0


EVENTS = {
    "inject": event_inject,
    "profile": event_profile,
    "standards": event_standards,
    "docstiers": event_docstiers,
    "versioncheck": event_versioncheck,
    "scope": event_scope,
    "guard": event_guard,
    "guardwrite": event_guardwrite,
    "artifact": event_artifact,
    "runnable": event_runnable,
    "delegate": event_delegate,
    "announce": event_announce,
    "subagentrules": event_subagentrules,
    "verdict": event_verdict,
    "handover": event_handover,
    "harvest": event_harvest,
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
