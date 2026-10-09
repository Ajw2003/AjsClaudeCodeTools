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

# Claude Code's per-hook additionalContext limit is 10,000 chars (docs/6-decisions/Decisions.md, 2026-09-22).
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


# Hardware and plan probes for the machine profile: doc-ref ad50 docs/4-systems/hook-engine.md
PROBE_TIMEOUT_SECONDS = 3.0
PROBE_TOTAL_SECONDS = 6.0
_GIB = 1024 ** 3
_PLAN_KEYS = {"subscriptiontype", "subscription_type", "subscription", "plan", "plantype", "plan_type"}


class _ProbeClock:
    def __init__(self):
        self.deadline = _time.monotonic() + PROBE_TOTAL_SECONDS

    def remaining(self):
        return self.deadline - _time.monotonic()


def _probe(argv, clock):
    """Run argv with a short timeout. Returns (stdout, None) or (None, reason)."""
    import subprocess

    room = min(PROBE_TIMEOUT_SECONDS, clock.remaining())
    if room <= 0:
        return None, "probe time budget of %g s already used up" % PROBE_TOTAL_SECONDS
    try:
        proc = subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=room,
            text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, "%s timed out after %g s" % (os.path.basename(argv[0]), room)
    except OSError as exc:
        return None, "%s could not run: %s" % (os.path.basename(argv[0]), exc)
    if proc.returncode != 0:
        first = (proc.stderr or proc.stdout or "").strip().splitlines()
        why = first[0][:120] if first else "no output"
        return None, "%s exited %d: %s" % (os.path.basename(argv[0]), proc.returncode, why)
    return proc.stdout, None


def _fmt_gib(nbytes):
    return "%.1f GB" % (nbytes / _GIB)


def _probe_cpu(clock):
    cores = os.cpu_count()
    cores_txt = "%d logical cores" % cores if cores else "core count not detected (os.cpu_count() returned None)"
    model, why = None, None
    system = platform.system()
    if system == "Linux":
        try:
            for line in _read_text("/proc/cpuinfo").splitlines():
                if line.lower().startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
            if model is None:
                why = "/proc/cpuinfo has no 'model name' line"
        except OSError as exc:
            why = "cannot read /proc/cpuinfo: %s" % exc
    elif system == "Darwin":
        sysctl = shutil.which("sysctl")
        if not sysctl:
            why = "sysctl not on PATH"
        else:
            out, why = _probe([sysctl, "-n", "machdep.cpu.brand_string"], clock)
            model = out.strip() if out and out.strip() else None
    else:
        model = platform.processor() or None
        if model is None:
            why = "platform.processor() is empty"
    if model:
        return "CPU: %s, %s" % (model, cores_txt)
    return "CPU: model not detected (%s), %s" % (why or "unknown", cores_txt)


def _probe_ram(clock):
    system = platform.system()
    try:
        if system == "Linux":
            for line in _read_text("/proc/meminfo").splitlines():
                if line.startswith("MemTotal:"):
                    return "RAM: %s total" % _fmt_gib(int(line.split()[1]) * 1024)
            return "RAM: not detected (/proc/meminfo has no MemTotal line)"
        if system == "Darwin":
            sysctl = shutil.which("sysctl")
            if not sysctl:
                return "RAM: not detected (sysctl not on PATH)"
            out, why = _probe([sysctl, "-n", "hw.memsize"], clock)
            if out is None:
                return "RAM: not detected (%s)" % why
            return "RAM: %s total" % _fmt_gib(int(out.strip()))
        if system == "Windows":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemStatus()
            status.dwLength = ctypes.sizeof(_MemStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return "RAM: not detected (GlobalMemoryStatusEx returned failure)"
            return "RAM: %s total" % _fmt_gib(status.ullTotalPhys)
        return "RAM: not detected (no RAM probe for %s)" % system
    except (OSError, ValueError, AttributeError) as exc:
        return "RAM: not detected (%s: %s)" % (type(exc).__name__, exc)


def _probe_gpu(clock):
    system = platform.system()
    smi = shutil.which("nvidia-smi")
    if smi:
        out, why = _probe([smi, "--query-gpu=name,memory.total", "--format=csv,noheader"], clock)
        if out is None:
            return "GPU: not detected (%s)" % why
        rows = [r.strip() for r in out.splitlines() if r.strip()]
        if not rows:
            return "GPU: not detected (nvidia-smi listed no GPU)"
        return "GPU: " + "; ".join(r.replace(", ", " with ", 1) + " VRAM" for r in rows)
    if system == "Darwin":
        profiler = shutil.which("system_profiler")
        if not profiler:
            return "GPU: not detected (nvidia-smi and system_profiler not on PATH)"
        out, why = _probe([profiler, "SPDisplaysDataType"], clock)
        if out is None:
            return "GPU: not detected (%s)" % why
        chips = [l.split(":", 1)[1].strip() for l in out.splitlines() if "Chipset Model:" in l]
        vram = [l.split(":", 1)[1].strip() for l in out.splitlines() if "VRAM" in l and ":" in l]
        if not chips:
            return "GPU: not detected (system_profiler listed no 'Chipset Model')"
        tail = ", VRAM %s" % vram[0] if vram else ", VRAM not reported (likely unified memory shared with RAM)"
        return "GPU: %s%s" % ("; ".join(chips), tail)
    if system == "Windows":
        ps = shutil.which("powershell") or shutil.which("pwsh")
        if not ps:
            return "GPU: not detected (nvidia-smi, powershell and pwsh not on PATH)"
        script = ("Get-CimInstance Win32_VideoController | ForEach-Object "
                  "{ $_.Name + '|' + $_.AdapterRAM }")
        out, why = _probe([ps, "-NoProfile", "-NonInteractive", "-Command", script], clock)
        if out is None:
            return "GPU: not detected (%s)" % why
        found = []
        for row in [r.strip() for r in out.splitlines() if r.strip()]:
            name, _, ram = row.rpartition("|")
            try:
                nbytes = int(ram)
            except ValueError:
                found.append("%s, VRAM not reported" % (name or row))
                continue
            note = ""
            # AdapterRAM is a 32-bit field: a card with more than 4 GB reads as ~4 GB.
            if nbytes >= 4 * _GIB - 1024 * 1024:
                note = " (may be higher - Windows reports at most 4 GB here)"
            found.append("%s with %s VRAM%s" % (name, _fmt_gib(nbytes), note))
        if not found:
            return "GPU: not detected (Win32_VideoController listed no adapter)"
        return "GPU: " + "; ".join(found)
    return "GPU: not detected (nvidia-smi not on PATH; no other GPU probe for %s)" % system


def _probe_disk():
    where = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        usage = shutil.disk_usage(where)
    except OSError as exc:
        return "Free disk: not detected (shutil.disk_usage(%r) failed: %s)" % (where, exc)
    return "Free disk: %s free of %s on the drive holding %s" % (
        _fmt_gib(usage.free), _fmt_gib(usage.total), where)


def _probe_claude_plan(clock):
    claude = shutil.which("claude")
    if not claude:
        return "Claude plan: not detected (claude not on PATH)"
    out, why = _probe([claude, "auth", "status", "--json"], clock)
    if out is None:
        return "Claude plan: not detected (%s)" % why
    try:
        data = json.loads(out)
    except ValueError as exc:
        return "Claude plan: not detected (claude auth status --json was not JSON: %s)" % exc
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in _PLAN_KEYS and isinstance(value, str) and value.strip():
                return "Claude plan: %s (from claude auth status: %s)" % (value.strip(), key)
    return "Claude plan: not detected (claude auth status reports no plan field)"


def _detect_hardware():
    clock = _ProbeClock()
    remote = bool(os.environ.get("CLAUDE_CODE_REMOTE"))
    if remote:
        head = ("## Hardware of this sandbox (for my own checks only - NOT the user's local "
                "build budget)")
    else:
        head = "## Hardware (the local build budget)"
    lines = [head, _probe_cpu(clock), _probe_ram(clock), _probe_gpu(clock), _probe_disk(),
             _probe_claude_plan(clock)]
    if remote:
        lines.append(
            "The local build budget is the user's own machine, from rules/handover-target.md, "
            "not the figures above."
        )
    return lines


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
    lines.extend(_detect_hardware())
    lines.append("")
    lines.append(
        "This section was generated by hook.py's profile handler, not hand-verified. Hardware "
        "and Claude plan above were probed at session start; a field marked 'not detected' "
        "is unknown, not zero. Before relying on any other fact - line-ending config, "
        "anything else - discover it and write it into rules/environment.md (gitignored, "
        "machine-local) so it is recorded rather than re-detected every session. Claude plan "
        "not detected: ask the user once, the first time a paid option comes up, and record "
        "the answer there."
    )
    return "\n".join(lines) + "\n"


# A saved memory restating the commit rule this plugin replaced ("never commit without asking")
# silently won over the current rule in a real session (#97). These catch the old rule's
# wording, not every mention of git.
_STALE_COMMIT_MEMORY_RE = re.compile(
    r"never (?:run|do|use|perform) (?:any )?git|no git (?:commands|actions|operations)|"
    r"never commit|do(?:n'?t| not) commit|commit only (?:when|if) asked|"
    r"never (?:commit|push) without (?:asking|permission)|ask before (?:committing|any commit)",
    re.IGNORECASE,
)
MEMORY_SCAN_MAX_FILES = 50


def _project_memory_dir():
    """Where Claude Code keeps this project's auto-memory: <config>/projects/<project dir with
    every non-alphanumeric character turned into '-'>/memory. HOUSE_RULES_MEMORY_DIR overrides
    it, which is how verify.py points it at a fixture."""
    override = os.environ.get("HOUSE_RULES_MEMORY_DIR")
    if override:
        return override
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(config, "projects", re.sub(r"[^A-Za-z0-9]", "-", project), "memory")


def _stale_memory_warnings():
    """One preflight line per memory file that restates the old commit rule. An unreadable
    memory folder says so; a missing one is the normal case and adds nothing."""
    mem_dir = _project_memory_dir()
    if not os.path.isdir(mem_dir):
        return []
    try:
        names = sorted(n for n in os.listdir(mem_dir) if n.lower().endswith(".md"))[:MEMORY_SCAN_MAX_FILES]
    except OSError as exc:
        return ["- could not read the memory folder %s (%s), so memories were not checked "
                "against the commit rule." % (mem_dir, type(exc).__name__)]
    found = []
    unread = []
    for name in names:
        try:
            text = _read_text(os.path.join(mem_dir, name))
        except (OSError, UnicodeDecodeError) as exc:
            unread.append("%s (%s)" % (name, type(exc).__name__))
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if _STALE_COMMIT_MEMORY_RE.search(line):
                found.append("%s:%d \"%s\"" % (name, lineno, line.strip()[:120]))
                break
    out = []
    if found:
        out.append(
            "- a saved memory restates the old commit rule, which the current one replaced: "
            + "; ".join(found)
            + " (in %s). A memory that contradicts a house rule is stale: follow the rule, tell "
            "the user about the conflict, and offer to delete or correct the memory." % mem_dir
        )
    if unread:
        out.append(
            "- could not read memory file(s) %s, so they were not checked against the commit "
            "rule." % ", ".join(unread)
        )
    return out


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
    warnings.extend(_stale_memory_warnings())
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


def _expand_detail_paths(text):
    """Write every plugin path as <plugin>/... and state the absolute plugin root once, so the
    injected size does not grow with the install path's length or the number of pointers."""
    root = _plugin_root()
    if "${CLAUDE_PLUGIN_ROOT}" not in text:
        return text
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", "<plugin>")
    return "<plugin> in the paths below is the plugin root: %s\n\n%s" % (root, text)


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
    # text is going into additionalContext, which nothing expands. The root is stated once
    # rather than substituted into every pointer: 26 copies of a long install path pushed this
    # past its size margin on a CI runner whose checkout path was merely 26 chars longer.
    body = _expand_detail_paths(body)

    preamble = (
        "The following are the user standing house rules. They apply to every project and "
        "override default behaviour. A PreToolUse hook also prompts for destructive "
        "commands, backgrounded/hidden processes, and mutating git commands - except a "
        "plain commit or push on an `AjsAgent/` branch. That hook is a backstop, not "
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
# profile — a third SessionStart handler, split out of inject in 2.17.1 (docs/6-decisions/Decisions.md,
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
                "recorded. Recorded? Build for exactly that; its hardware, not the sandbox's, is "
                "the local build budget:\n\n" + handover_body
            )
        else:
            handover_block = (
                "\n\n---\n\nThis session is remote: the machine profile above is the sandbox "
                "hook.py runs on, not necessarily the user's own machine. Before the first "
                "command I hand over, find out theirs - check docs/example-environment.md if "
                "present (say it's inferred, and from when, not confirmed), or ask - then "
                "record the confirmed answer into rules/handover-target.md so a later session "
                "does not have to ask again. Ask for their hardware too (CPU, RAM, GPU and "
                "VRAM, free disk) and their Claude plan: that hardware, not the sandbox's, is "
                "the local build budget.\n"
            )

        handover_block += _agent_branch_block()
        handover_block += _agent_identity_block()

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

    Why and how: doc-ref 0d4d docs/4-systems/hook-engine.md (Invariants).
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
            # The Unity core points at rules/standards/csharp-unity-detail.md by the same
            # ${CLAUDE_PLUGIN_ROOT} spelling house-rules.md uses; nothing expands it inside
            # additionalContext, so resolve it here (a no-op when no document uses it).
            content = _expand_detail_paths(content)
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
# drift check keeps the two from disagreeing. Full rationale: docs/6-decisions/Decisions.md, 2026-09-22, and
# rules/detail/docs-tiers.md.
# ---------------------------------------------------------------------------------------

DOCS_TIER_FILES = [
    "docs/1-landing/README.md",
    "docs/2-roadmap/Roadmap.md",
    "docs/3-state/ProjectState.md",
    "docs/5-today/Today.md",
    "docs/6-decisions/Decisions.md",
]
DOCS_TIER4_DIR = "docs/4-systems"
# The pre-folder layout, kept only so a project still on it gets a "move X to Y" message
# instead of being told to scaffold tiers it already has. See docs/6-decisions/Decisions.md,
# 2026-09-24.
OLD_DOCS_TIER_FILES = [
    "docs/README.md",
    "docs/Roadmap.md",
    "docs/ProjectState.md",
    "docs/Today.md",
    "docs/Decisions.md",
]
OLD_DOCS_TIER4_DIR = "docs/systems"
DEFAULT_GITHUB_OWNER = "Ajw2003"


def _tier4_present(root, tier4_dir=DOCS_TIER4_DIR):
    d = os.path.join(root, *tier4_dir.split("/"))
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
        missing = []
        moves = []
        for new_path, old_path in zip(DOCS_TIER_FILES, OLD_DOCS_TIER_FILES):
            if os.path.isfile(os.path.join(root, *new_path.split("/"))):
                continue
            if os.path.isfile(os.path.join(root, *old_path.split("/"))):
                moves.append("%s to %s" % (old_path, new_path))
            else:
                missing.append(new_path)

        tier4_new = _tier4_present(root)
        if not tier4_new:
            if _tier4_present(root, OLD_DOCS_TIER4_DIR):
                moves.insert(3, "%s/*.md to %s/*.md" % (OLD_DOCS_TIER4_DIR, DOCS_TIER4_DIR))
            else:
                missing.insert(3, "%s/*.md (at least one system document)" % DOCS_TIER4_DIR)

        if moves:
            text = (
                "House rules, documentation goes in tiers: this project still has %d "
                "documentation tier(s) in the old flat layout - move %s. %s"
                % (
                    len(moves),
                    "; ".join(moves),
                    (
                        "It is also missing %d tier(s) outright - %s. Load "
                        "house-rules:project-docs and scaffold those before any other work."
                        % (len(missing), ", ".join(missing))
                        if missing
                        else "Load house-rules:project-docs for the current folder layout."
                    ),
                )
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


_RAW_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$"
)


def _github_api_url(raw_url):
    """The contents-API URL for the same owner/repo/ref/path as a raw.githubusercontent URL, or
    "" if raw_url is not in that shape. Derived, not a second constant, so a fork's
    HOUSE_RULES_VC_GITHUB_URL gets a working fallback without setting anything else."""
    override = os.environ.get("HOUSE_RULES_VC_GITHUB_API_URL")
    if override:
        return override
    m = _RAW_URL_RE.match(raw_url)
    if not m:
        return ""
    owner, repo, ref, path = m.groups()
    return "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (owner, repo, path, ref)


def _fetch_version(url, headers, timeout):
    import urllib.request

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return data.get("version", "") or ""


def _describe_fetch_error(exc):
    detail = str(getattr(exc, "reason", "") or exc).strip()
    if len(detail) > 120:
        detail = detail[:117] + "..."
    return "%s: %s" % (type(exc).__name__, detail) if detail else type(exc).__name__


def _github_version(problems):
    """GitHub's published version: raw.githubusercontent first, then the contents API, both
    inside one _GITHUB_FETCH_TIMEOUT budget. Two routes because some sandboxes reset
    connections to raw.githubusercontent.com while api.github.com works (docs/architecture.md,
    "versioncheck checks three copies of the version"). Each failed route goes into problems."""
    override = os.environ.get("HOUSE_RULES_VC_GITHUB")
    if override is not None:
        return override
    import time

    deadline = time.monotonic() + _GITHUB_FETCH_TIMEOUT
    raw_url = os.environ.get("HOUSE_RULES_VC_GITHUB_URL") or _GITHUB_PLUGIN_JSON_URL
    failures = []
    try:
        return _fetch_version(raw_url, {}, _GITHUB_FETCH_TIMEOUT)
    except Exception as exc:
        failures.append("raw.githubusercontent.com (%s)" % _describe_fetch_error(exc))

    api_url = _github_api_url(raw_url)
    remaining = deadline - time.monotonic()
    if not api_url:
        failures.append("no GitHub API fallback (HOUSE_RULES_VC_GITHUB_URL is not a raw URL)")
    elif remaining < 0.5:
        failures.append("GitHub API not tried (the %gs budget ran out)" % _GITHUB_FETCH_TIMEOUT)
    else:
        try:
            return _fetch_version(
                api_url, {"Accept": "application/vnd.github.raw"}, remaining
            )
        except Exception as exc:
            failures.append("api.github.com (%s)" % _describe_fetch_error(exc))

    problems.append(
        "could not reach GitHub to check the published version - %s" % "; ".join(failures)
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


_VC_PLUGIN_NAME = "house-rules"
_VC_DEFAULT_MARKETPLACE = "aj-house-rules"
# One budget for every update command together. hooks.json gives versioncheck 90 s, so this
# leaves the version reads and the re-check room to finish inside it.
_VC_UPDATE_BUDGET = 60.0


def _auto_update_enabled():
    return os.environ.get("HOUSE_RULES_AUTO_UPDATE", "on").strip().lower() not in _TRACE_OFF


def _installed_plugins_path():
    return os.environ.get("HOUSE_RULES_VC_INSTALLED_PLUGINS_JSON") or os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "installed_plugins.json"
    )


def _installed_on_disk(problems):
    """(plugin id, versions) for house-rules as installed_plugins.json records it.

    This is what the NEXT session will load. _plugin_version() is the copy running right now,
    which stays the same until Claude Code restarts, even after an update (a /clear does not
    reload it). Comparing only the running copy is what made versioncheck ask for an update
    that was already installed (docs/6-decisions/Decisions.md, 2026-09-26).
    """
    path = _installed_plugins_path()
    if not os.path.isfile(path):
        return "", []
    try:
        data = json.loads(_read_text(path))
    except Exception as exc:
        problems.append("could not read installed_plugins.json (%s)" % type(exc).__name__)
        return "", []
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    for plugin_id, entries in sorted(plugins.items()):
        if plugin_id.split("@", 1)[0] != _VC_PLUGIN_NAME:
            continue
        if isinstance(entries, dict):
            entries = [entries]
        versions = [
            e.get("version", "")
            for e in entries
            if isinstance(e, dict) and e.get("version")
        ]
        return plugin_id, versions
    return "", []


def _claude_command():
    """The argv prefix that runs the `claude` CLI, or [] if it is not on PATH.
    HOUSE_RULES_VC_CLAUDE (a JSON list) replaces it, so verify.py never runs a real update."""
    override = os.environ.get("HOUSE_RULES_VC_CLAUDE")
    if override:
        return json.loads(override)
    found = shutil.which("claude")
    return [found] if found else []


def _tail(text, limit=300):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else "..." + text[-(limit - 3):]


def _run_update_commands(commands):
    """Run each `claude ...` command in order inside _VC_UPDATE_BUDGET, stopping at the first
    failure. Returns (log lines, error or "")."""
    import subprocess

    try:
        base = _claude_command()
    except ValueError as exc:
        return [], "HOUSE_RULES_VC_CLAUDE is not a JSON list (%s)" % exc
    if not base:
        return [], "the `claude` command is not on PATH for this hook"
    deadline = _time.monotonic() + _VC_UPDATE_BUDGET
    log = []
    for args in commands:
        shown = "claude " + " ".join(args)
        remaining = deadline - _time.monotonic()
        if remaining < 1:
            return log, "ran out of time before `%s`" % shown
        try:
            proc = subprocess.run(
                base + args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            return log, "`%s` did not finish within %gs" % (shown, _VC_UPDATE_BUDGET)
        except OSError as exc:
            return log, "could not start `%s` (%s)" % (shown, exc)
        output = proc.stdout.decode("utf-8", "replace")
        log.append("`%s` exited %d: %s" % (shown, proc.returncode, _tail(output) or "(no output)"))
        if proc.returncode != 0:
            return log, "`%s` failed with exit code %d" % (shown, proc.returncode)
    return log, ""


def _vc_restart_notice(on_disk, running, how):
    """The context for "the right version is on disk, this process just predates it"."""
    return {
        "systemMessage": "house-rules %s is installed%s. This session is still running %s - "
        "start a new session to load it." % (on_disk, how, running),
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "house-rules %s is installed on this machine%s, but this session is still "
                "running %s: plugins load when Claude Code starts, and a /clear does not reload "
                "them. Nothing needs updating. In your first reply, tell the user in one "
                "sentence that %s is installed and loads when they start a new session. Do not "
                "run any update command, do not ask about updating, and do not stop work."
                % (on_disk, how, running, on_disk)
            ),
        },
    }


def event_versioncheck():
    try:
        if not _version_check_enabled():
            return 0

        payload = read_payload()
        session_id = _vc_session_id(payload)

        problems = []
        installed = _plugin_version(problems)
        plugin_id, on_disk = _installed_on_disk(problems)
        market_version = _marketplace_version(problems)
        github_version = _github_version(problems)
        latest = github_version or market_version

        market_name = plugin_id.split("@", 1)[1] if "@" in plugin_id else _VC_DEFAULT_MARKETPLACE
        plugin_ref = plugin_id or "%s@%s" % (_VC_PLUGIN_NAME, market_name)
        update_cmd = "claude plugin update %s" % plugin_ref
        marketplace_cmd = "claude plugin marketplace update %s" % market_name

        marketplace_stale = bool(
            github_version and (not market_version or market_version != github_version)
        )
        if latest and installed != latest and latest in on_disk and not marketplace_stale:
            emit(_vc_restart_notice(latest, installed, ""))
            return 0

        reasons = []
        if installed and market_version and installed != market_version:
            reasons.append(
                "installed copy is %s but the local marketplace clone has %s - run `%s`."
                % (installed, market_version, update_cmd)
            )
        if market_version and github_version and market_version != github_version:
            reasons.append(
                "the local marketplace clone is %s but GitHub's default branch has %s - the "
                "marketplace clone itself has not synced. Run `%s`, then `%s`."
                % (market_version, github_version, marketplace_cmd, update_cmd)
            )
        elif not market_version and installed and github_version and installed != github_version:
            # The marketplace clone could not be found/read at all - fall back to comparing
            # the installed copy straight against GitHub so a mismatch is still caught.
            reasons.append(
                "installed copy is %s but GitHub's default branch has %s (the local "
                "marketplace clone could not be checked). Run `%s`, then `%s`."
                % (installed, github_version, marketplace_cmd, update_cmd)
            )

        if not reasons:
            if problems:
                # Said to the model, not only the UI: a systemMessage never reaches the model,
                # so an unverified check used to look identical to a verified one. Still not
                # "out of date" - no banner, no marker (docs/6-decisions/Decisions.md, 2026-09-24).
                out = {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": (
                            "house-rules versioncheck could not confirm the plugin is current. "
                            "Installed version: %s. What failed: %s. In your first reply this "
                            "session, tell the user in one or two sentences that the plugin's "
                            "freshness could not be checked, naming what failed. This is not an "
                            "out-of-date result - do not ask to update and do not stop work."
                            % (installed or "unknown", "; ".join(problems))
                        ),
                    }
                }
                if trace_enabled():
                    out["systemMessage"] = (
                        "versioncheck: could not fully verify the plugin is current - %s"
                        % "; ".join(problems)
                    )
                emit(out)
            else:
                trace(
                    "versioncheck: installed %s matches the marketplace clone and GitHub's "
                    "default branch." % (installed or "unknown")
                )
            return 0

        # Out of date: update it here rather than asking, then check the result on disk rather
        # than trusting the exit code (docs/6-decisions/Decisions.md, 2026-09-26).
        failure = "automatic updating is switched off (HOUSE_RULES_AUTO_UPDATE=off)"
        log = []
        if _auto_update_enabled():
            commands = []
            if marketplace_stale or not market_version:
                commands.append(["plugin", "marketplace", "update", market_name])
            commands.append(["plugin", "update", plugin_ref])
            log, failure = _run_update_commands(commands)
            after_id, after = _installed_on_disk([])
            if not failure and latest and latest in after:
                if installed == latest:
                    trace(
                        "versioncheck: refreshed the stale marketplace clone; %s was already "
                        "installed and running." % installed
                    )
                else:
                    emit(_vc_restart_notice(latest, installed, " - updated automatically at "
                                            "session start, up from %s" % installed))
                return 0
            if not failure:
                failure = (
                    "the update commands exited 0, but installed_plugins.json lists %s, not %s"
                    % (", ".join(after) or "no house-rules install", latest or "a newer version")
                )

        _write_outdated_marker(session_id, reasons)

        banner_lines = [
            "",
            "=" * 70,
            "HOUSE-RULES PLUGIN IS OUT OF DATE",
            "=" * 70,
            "",
            "versioncheck tried to update the plugin itself at session start and could not "
            "finish: %s." % failure,
        ]
        banner_lines.extend("  %s" % line for line in log)
        banner_lines.extend(
            [
                "",
                "Before doing any other work this session: run the command(s) below yourself, "
                "in order, right now, on this machine - the same machine the check above just "
                "read - and report the real output rather than the command. Do not ask in chat "
                "first: the user has asked for the plugin's own update to just happen, and the "
                "permission prompt the harness puts on your first shell command is where they "
                "say yes or no. Check the result with `claude plugin list`; a reported update "
                "is not a completed one. Once it is installed, tell the user it loads in a new "
                "session (a /clear does not reload plugins) and carry on with their request.",
                "",
                "If they decline that prompt, or this session has no shell tool to run them "
                "with, relay the command(s) instead - through the step-card format, marked "
                "`UNTESTED:` since this hook relayed them and they have not been run on this "
                "machine - then stop and wait for the user's answer.",
                "",
            ]
        )
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
                "systemMessage": "house-rules is out of date and could not update itself: %s."
                % failure,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "\n".join(banner_lines),
                },
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
    waiting = ""
    try:
        payload = read_payload()
        waiting = _waiting_scope_note(payload)
        m = _PROMPT_FIELD_RE.search(payload)
        if m:
            field = m.group(0)
            if _SCOPE_COMMAND_HINT_RE.search(field):
                reminder = SCOPE_REMINDER
            if _SCOPE_GOAHEAD_RE.search(field):
                reminder = reminder + SCOPE_DELEGATE_CLAUSE
            if _PARITY_RE.search(field) and _parity_enabled():
                reminder = reminder + SCOPE_PARITY_CLAUSE
    except Exception:
        # Whatever went wrong, the safe short reminder still goes out. A non-zero exit or a
        # raise here would ERASE THE USER'S PROMPT, so this recovers rather than reporting.
        reminder = SCOPE_REMINDER_SHORT

    try:
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": reminder + ("\n\n" + waiting if waiting else ""),
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
    # #85: a wait piped through tail/head shows nothing until it exits - a stuck wait and a
    # working one look identical for its whole timeout.
    (
        r"(^|[^0-9A-Za-z_-])(while|until|sleep|timeout|watch)\s.*\|\s*(tail|head)([^0-9A-Za-z_-]|$)",
        "pipes a wait or loop through tail/head, which hides its output until it exits",
    ),
]

# One shell word: quoted runs may hold spaces, so -c user.name="aj's agent" is one word (#189).
_WORD = r"""(?:"[^"]*"|'[^']*'|[^\s"'])+"""
# `git` plus any run of global options before the subcommand.
# Why the alternation's first branch exists: docs/architecture.md, "The pre-existing hole this exposed".
_GIT = (
    r"git\s+((?:-[cC]|--git-dir|--work-tree|--namespace|--exec-path|--super-prefix)"
    r"[=\s]\s*" + _WORD + r"\s+|-" + _WORD + r"\s+)*"
)

# Marks a pattern the commit rule stands down for when the checkout is on a branch I created.
# Everything without it prompts on every branch, mine included. See the ownership helpers below
# and "Commit constantly on my own branches, never on theirs" in rules/house-rules.md.
OWNED = "owned-branch-exempt"
# Marks a destructive pattern that runs unasked only on my branch AND when everything it could
# lose is already saved elsewhere: a clean tree and every commit on a remote (#153).
SAVED = "saved-work-exempt"

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
    # reset/revert/rebase only lose work that is not saved elsewhere, so on my branch with a
    # clean tree and every commit pushed they run unasked (SAVED, #153). clean can remove
    # ignored files that exist nowhere else, and merge/cherry-pick/am/apply/filter-branch are
    # how a hook would end up finishing something the user started - not exemptible anywhere.
    (
        _GIT + r"(reset|revert|rebase)([^0-9A-Za-z-]|$)",
        "discards work or rewrites history (reset / revert / rebase)",
        SAVED,
    ),
    (
        _GIT + r"(clean|merge|filter-branch|cherry-pick|am|apply)([^0-9A-Za-z-]|$)",
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
        SAVED,
    ),
    (
        _GIT + r"stash\s+(drop|clear)([^0-9A-Za-z-]|$)",
        "deletes stashed work permanently (git stash drop / clear)",
    ),
]

GUARD_BUCKETS = [
    ("Never hide work: it stays visible, reachable and readable", GUARD_R1),
    ("Commit constantly on my own branches, never on theirs", GUARD_R3),
    ("Never take a destructive action without checking first", GUARD_R4),
]

# Reuses GUARD_R3's own commit pattern rather than a second copy - "is this a commit" and "is
# this exempt from asking" are different questions, and the docs check needs the first one
# independent of the second (a commit on my own branch is exempt from asking but still needs
# the docs reminder).
_GIT_COMMIT_RE = re.compile(_GIT + r"commit([^0-9A-Za-z-]|$)", re.IGNORECASE)

# git diff --cached is the ONE deliberate, narrowly-scoped exception to "no subprocess in
# guard" - branch_ownership() stays subprocess-free. doc-ref 8713 docs/6-decisions/Decisions.md.
DOCS_CHECK_TIMEOUT = 2.0


# `git add` split off the same way a compound command is read for other purposes - on &&, ||,
# ; and newlines - so "git add f.py && git commit -m x" is seen as two statements, not one
# unmatched blob. Reuses _GIT (git plus any run of global options) the same way _GIT_COMMIT_RE
# does; "is this an add" and "is this a commit" are two independent questions on two possibly
# different statements of the same command.
_GIT_ADD_RE = re.compile(_GIT + r"add([^0-9A-Za-z-]|$)", re.IGNORECASE)
_STATEMENT_SPLIT_RE = re.compile(r"&&|\|\||;|\n")
# -a/--all/-am/-ma on the COMMIT statement: git stages every tracked, modified/deleted file at
# commit time, before the commit itself runs - doc-ref c79f docs/6-decisions/Decisions.md.
_COMMIT_ALL_RE = re.compile(r"(^|\s)(-a\b|--all\b|-am\b|-ma\b)", re.IGNORECASE)
_ADD_ALL_RE = re.compile(r"(^|\s)(-A\b|--all\b)|(^|\s)\.(\s|$)", re.IGNORECASE)
_ADD_UPDATE_RE = re.compile(r"(^|\s)(-u\b|--update\b)", re.IGNORECASE)


def _unquote_git_path(path):
    """git quotes a path in porcelain output (surrounding double quotes, C-style backslash
    escapes) whenever it contains a space or other "unusual" byte - core.quotePath's default.
    A plain path is returned unchanged. A quoted path that fails to parse is a recovered case,
    not a silent bail: the still-quoted string is kept and used as-is (it simply will not
    prefix-match a literal `git add` argument), same posture as a decode that falls back
    rather than giving up."""
    unquoted = path
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        try:
            unquoted = json.loads(path)
        except ValueError as exc:
            sys.stderr.write(
                "house-rules: could not unquote git status path %r (%s); using it as-is.\n"
                % (path, exc)
            )
    return unquoted


def _parse_status_porcelain(lines):
    """[(path, tracked)] from `git status --porcelain -uall` output. Best-effort on a rename
    line ("R  old -> new"): keeps the new path, which is what a fresh `git add` would stage."""
    out = []
    for line in lines:
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append((_unquote_git_path(path.strip()), code != "??"))
    return out


def _staged_docs_status(subject, elsewhere):
    """('needs-docs'|'clear'|'unknown', detail) for what this commit will ACTUALLY include -
    not just what is staged right now, since guard runs before the command it is judging.

    'unknown' on anything that could make guard's own decision unreliable: a command naming
    another repo (elsewhere), no working git, the shared time budget running out, undecodable
    output. The caller's existing decision is never changed by this - only the message it
    shows may gain a line. doc-ref c79f docs/6-decisions/Decisions.md.
    """
    if elsewhere:
        return "unknown", "the command names another repo (-C/--git-dir/--work-tree)"
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    import shlex
    import subprocess
    import time as _t

    # subject is the raw, still-JSON-escaped "command":"..." field slice - fine for every
    # regex below (none of them need real quote characters), but wrong for shlex, which has
    # to see the actual command text to tokenize a quoted path like "my file.py" correctly.
    decoded = _field(_COMMAND_VALUE_RE, subject) or subject

    deadline = _t.time() + DOCS_CHECK_TIMEOUT

    def run_git(args):
        remaining = deadline - _t.time()
        if remaining <= 0:
            raise RuntimeError("the docs check's time budget ran out")
        proc = subprocess.run(
            ["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining
        )
        if proc.returncode != 0:
            raise RuntimeError("git %s exited %d" % (" ".join(args), proc.returncode))
        return [p for p in proc.stdout.decode("utf-8", "replace").splitlines() if p.strip()]

    try:
        effective = set(p.strip() for p in run_git(["diff", "--cached", "--name-only"]))

        statements = _STATEMENT_SPLIT_RE.split(decoded)
        commit_stmt = next((s for s in statements if _GIT_COMMIT_RE.search(s)), "")
        commit_all = bool(_COMMIT_ALL_RE.search(commit_stmt))

        add_all = False
        add_tracked_only = False
        literal_paths = []
        for s in statements:
            m = _GIT_ADD_RE.search(s)
            if not m:
                continue
            args_part = s[m.end() :]
            if _ADD_ALL_RE.search(args_part):
                add_all = True
            elif _ADD_UPDATE_RE.search(args_part):
                add_tracked_only = True
            else:
                # shlex, not .split(): a quoted path with a space ("my file.py") is one
                # argument, not two. posix=True so quotes/backslashes resolve the way a real
                # shell would read them. Unbalanced quotes raise ValueError, which the outer
                # try/except below turns into "unknown" - never a guess at what was meant.
                literal_paths.extend(
                    tok for tok in shlex.split(args_part, posix=True) if not tok.startswith("-")
                )

        status = None  # lazy: only fetched if something below actually needs it
        if commit_all:
            effective.update(p.strip() for p in run_git(["diff", "HEAD", "--name-only"]))
        if add_all or add_tracked_only or literal_paths:
            status = _parse_status_porcelain(run_git(["status", "--porcelain", "-uall"]))
        if add_all:
            effective.update(p for p, _tracked in status)
        elif add_tracked_only:
            effective.update(p for p, tracked in status if tracked)
        for lp in literal_paths:
            lp_norm = lp.rstrip("/")
            effective.update(p for p, _tracked in status if p == lp_norm or p.startswith(lp_norm + "/"))
    except Exception as exc:
        return "unknown", "could not resolve what this commit will include (%s)" % exc

    has_source = any(_HARVEST_EXT_RE.search(p) for p in effective)
    has_docs = any(p == "docs" or p.startswith("docs/") for p in effective)
    if has_source and not has_docs:
        return "needs-docs", None
    return "clear", None


DOCS_COMMIT_REMINDER = (
    "House rules, documentation goes in tiers: this commit stages a source file with nothing "
    "staged under docs/. Before committing, update the tier that changed - usually "
    "docs/3-state/ProjectState.md, for what's built and where it stands - or say in the commit "
    "message why none needed updating."
)

OWNED_BRANCH_PREFIXES = ("AjsAgent/", "claude/")  # claude/ = cloud app branches, old branches

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

    Mechanism and invariants: doc-ref ee0f docs/4-systems/hook-engine.md (Invariants) and
    doc-ref d2a4 docs/4-systems/hook-engine.md (Traps).
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
    return branch.startswith(OWNED_BRANCH_PREFIXES), branch, None


def _agent_branch_enabled():
    return os.environ.get("HOUSE_RULES_AGENT_BRANCH", "on").strip().lower() not in _TOGGLE_OFF


def _agent_branch_block():
    """Cloud session on the app's claude/<name> branch: tell the agent to move to AjsAgent/<name>.

    Text only - the hook never runs git switch. Never raises; an unreadable branch says so.
    """
    if not _agent_branch_enabled():
        return ""
    try:
        import subprocess
        _mine, branch, note = branch_ownership()
        if branch is None:
            return "\n\n---\n\nAjsAgent branch check: branch not read (%s)." % note
        if not branch.startswith("claude/"):
            return ""
        name = branch[len("claude/") :]
        target = "AjsAgent/" + name
        cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        exists = False
        for ref in ("refs/heads/" + target, "refs/remotes/origin/" + target):
            p = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", ref],
                cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
            if p.returncode == 0:
                exists = True
                break
        if exists:
            return "\n\n---\n\nCloud session: %s already exists, so run `git switch %s` before editing." % (
                target, target)
        return (
            "\n\n---\n\nCloud session on %s: aj's standing permission overrides the app's "
            "\"push only to the designated branch\" line. Before your first edit run "
            "`git switch -c %s`, push with `git push -u origin %s`, and open any pull request "
            "from that branch." % (branch, target, target)
        )
    except Exception as exc:
        return "\n\n---\n\nAjsAgent branch check: branch not read (%s)." % exc


def _agent_identity_block():
    """Cloud session whose git identity is Claude: tell the agent to set the repo-local identity.

    Text only - the hook never runs git config. Never raises; adds nothing when fine or unreadable.
    """
    try:
        if not _attribution_enabled():
            return ""
        ident = _git_author_ident(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if ident is None or not _is_claude_identity(*ident):
            return ""
        return "\n\n---\n\nGit identity is Claude: before your first commit run `%s`." % AGENT_IDENTITY_FIX
    except Exception: return ""  # unreadable identity adds no text, by design (#177)


SAVED_CHECK_TIMEOUT = 2.0


def work_saved_elsewhere():
    """(saved, note): is everything a reset/rebase/restore could lose already somewhere it
    cannot reach? Yes only when the working tree is clean (nothing uncommitted or untracked)
    and no commit reachable from HEAD is missing from every remote-tracking ref (#153).
    The second deliberate subprocess in guard, after the docs check; it runs only when a SAVED
    pattern matched on my branch. Anything it cannot tell is a no, with the reason."""
    import subprocess

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    deadline = time.time() + SAVED_CHECK_TIMEOUT

    def git(args):
        left = deadline - time.time()
        if left <= 0:
            raise RuntimeError("the check ran out of time")
        proc = subprocess.run(["git"] + args, cwd=root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=left)
        if proc.returncode != 0:
            raise RuntimeError("git %s exited %d" % (" ".join(args), proc.returncode))
        return proc.stdout.decode("utf-8", "replace").strip()

    try:
        dirty = git(["status", "--porcelain", "-uall"])
        if dirty:
            n = len(dirty.splitlines())
            return False, "%d uncommitted or untracked file%s would be lost" % (n, "" if n == 1 else "s")
        unpushed = int(git(["rev-list", "--count", "HEAD", "--not", "--remotes"]) or "0")
        if unpushed:
            return False, "%d commit%s on this branch %s not on any remote" % (
                unpushed, "" if unpushed == 1 else "s", "is" if unpushed == 1 else "are")
        return True, None
    except Exception as exc:
        return False, "could not check that the work is saved elsewhere (%s)" % exc


# tier 3: pull out just "command":"..." — the first one. Allows backslash-escaped quotes.
_COMMAND_FIELD_RE = re.compile(r'"command"\s*:\s*"(?:[^"\\]|\\.)*"')


def _guard_subject(payload):
    m = _COMMAND_FIELD_RE.search(payload)
    return m.group(0) if m else payload


_COMMAND_VALUE_RE = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _trace_subject(subject, limit=60):
    """The command as a human reads it, collapsed to one short line.

    Why this decodes separately from matching: doc-ref 361f docs/4-systems/hook-engine.md
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

    # Issue workflow: gh pr create must say Refs, gh issue close always asks. A deny ends here;
    # an ask is folded into the prompt built below so a compound command is asked about once.
    issue_hit = (_attribution_guard(subject, payload) or _author_guard(subject, payload)
                 or _issues_guard(subject, payload))
    if issue_hit and issue_hit[0] == "deny":
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": issue_hit[1]}})
        return 0

    is_mine, branch, ownership_note = branch_ownership()
    # A command carrying -C / --git-dir / --work-tree acts on a repo other than the one we
    # just read the branch from, so the exemption cannot be justified and is withheld.
    elsewhere = bool(_OTHER_REPO_RE.search(subject))
    exempting = is_mine and not elsewhere

    hits = {title: [] for title, _ in GUARD_BUCKETS}
    exempted = []
    saved_state = None  # (saved, note), computed at most once and only when a SAVED pattern matched
    saved_blocked = None
    for title, patterns in GUARD_BUCKETS:
        for entry in patterns:
            pattern, reason = entry[0], entry[1]
            if not re.search(pattern, subject, re.IGNORECASE):
                continue
            marker = entry[2] if len(entry) > 2 else None
            if exempting and marker == OWNED:
                exempted.append(reason)
                continue
            if exempting and marker == SAVED:
                if saved_state is None:
                    saved_state = work_saved_elsewhere()
                if saved_state[0]:
                    exempted.append(reason)
                    continue
                saved_blocked = saved_state[1]
            hits[title].append(reason)

    is_commit = bool(_GIT_COMMIT_RE.search(subject))
    docs_status, docs_detail = _staged_docs_status(subject, elsewhere) if is_commit else (None, None)

    if not any(hits.values()) and not outdated and not issue_hit:
        # The allow path. Silent, this is the plugin's least distinguishable "ran and decided
        # not to fire" from "never ran" - and it is the security-shaped backstop, so that is
        # the worst place to leave the ambiguity. Exactly one emit() call either way - two
        # would be two concatenated JSON objects on stdout, which is not valid hook output.
        if exempted:
            allow_trace = (
                "guard: checked %s - %s on `%s`, which is mine to commit on%s."
                % (_trace_subject(subject), " and ".join(exempted), branch,
                   ", with nothing uncommitted and every commit on a remote"
                   if saved_state and saved_state[0] else "")
            )
        else:
            allow_trace = "guard: checked %s - no house rule matched." % _trace_subject(subject)

        if docs_status == "needs-docs":
            # Still an allow - the commit rule already lets this through - but Claude gets a
            # reminder in-context. PreToolUse's additionalContext reaches the model on an
            # "allow" decision (probed live, doc-ref 8713 docs/6-decisions/Decisions.md), the channel
            # guard did not otherwise use before this.
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "additionalContext": DOCS_COMMIT_REMINDER,
                }
            }
            if trace_verbose():
                out["systemMessage"] = allow_trace
            emit(out)
            return 0
        if docs_status == "unknown":
            trace("%s - docs check could not tell: %s." % (allow_trace, docs_detail))
        else:
            trace_noop(allow_trace)
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
                "  You are on `%s`, which is yours, not an `AjsAgent/` (or `claude/`) branch." % branch
            )
        if why_not_exempt:
            lines.append("")
            lines.append(why_not_exempt)

    if saved_blocked:
        lines.append("")
        lines.append(
            "  On `%s`, but this runs unasked only when the work is saved elsewhere: %s."
            % (branch, saved_blocked)
        )

    if issue_hit:
        lines.append("")
        lines.append("  Rule: Issue workflow (PRs link with Refs, the user closes issues)")
        lines.append("    - %s" % issue_hit[1])

    if docs_status == "needs-docs":
        lines.append("")
        lines.append("  Rule: Documentation goes in tiers, and I update the tier that changed")
        lines.append(
            "    - this commit stages a source file with nothing staged under docs/ - "
            "update the tier that changed, or say why none did"
        )
    elif docs_status == "unknown":
        lines.append("")
        lines.append(
            "  Could not tell whether docs need updating for this commit: %s." % docs_detail
        )

    lines.append("")
    _tl = _prompt_timeout_line()
    if _tl:
        lines.append(_tl)
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
                **({"additionalContext": issue_hit[2]} if issue_hit and issue_hit[2] else {}),
            }
        }
    )
    return 0


# ---------------------------------------------------------------------------------------
# guardwrite — PreToolUse on Write. Fails closed and loud, same contract as guard.
# doc-ref bf94 docs/4-systems/hook-engine.md (Invariants)
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
        trace_noop("guardwrite: %s does not exist yet - a new file, not an overwrite." % file_path)
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
    _tl = _prompt_timeout_line()
    if _tl:
        lines.append(_tl)
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
            trace_noop("artifact: %s is not a document extension - not checked." % base)
            return 0
        if not _is_outside_project(file_path):
            trace_noop("artifact: %s is inside the project - nothing to copy." % base)
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


# ---------------------------------------------------------------------------------------
# branchnudge - PostToolUse on Write|Edit. The commit rule's "branch off first", at the moment
# it applies: the first uncommitted change on a branch that is not AjsAgent/ (or claude/). Never obstructs.
# ---------------------------------------------------------------------------------------

BRANCH_NUDGE_NOTE = (
    "House rules, commit on your own branch: that write is the only uncommitted change on "
    "`{branch}`, which is not an AjsAgent/ (or claude/) branch. If that branch was opened for this session's "
    "work, carry on and commit there. If it is the user's, branch off now, before editing "
    "further (`git switch -c AjsAgent/<topic>` carries this change with it), and commit on that "
    "branch, scoped to the paths you changed."
)


def event_branchnudge():
    # PostToolUse, not PreToolUse: a PreToolUse hook can only put context in front of the model
    # alongside a permission decision, and "allow" would skip the user's own write prompt.
    # Stateless: "the only dirty path is the one just written" is what makes it the first
    # change. If the user already had uncommitted edits, this stays quiet and the Stop commit
    # check still catches the turn's files.
    try:
        if not _commit_check_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit(
                {
                    "systemMessage": "house-rules plugin: the branch nudge got an empty "
                    "payload and did not run for this call."
                }
            )
            return 0
        file_path = _extract_file_path(payload)
        if not file_path:
            return 0
        is_mine, branch, note = branch_ownership()
        if is_mine:
            trace_noop("branchnudge: on own branch %s - nothing to nudge." % branch)
            return 0
        if not branch:
            trace("branchnudge: no branch to judge (%s) - not checked." % note)
            return 0
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        try:
            status = _dirty_paths(root)
            dirty = status[1]
            written = _uncommitted_among([file_path], root, status)
        except Exception as exc:
            emit(
                {
                    "systemMessage": "house-rules: branch nudge could not tell whether that "
                    "was the first change on %s (%s: %s)." % (branch, type(exc).__name__, exc)
                }
            )
            return 0
        if written and len(dirty) == 1:
            emit(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": BRANCH_NUDGE_NOTE.format(branch=branch),
                    }
                }
            )
            return 0
        trace_noop(
            "branchnudge: %d uncommitted path(s) on %s - not the first change, no nudge."
            % (len(dirty), branch)
        )
    except Exception as exc:
        emit(
            {
                "systemMessage": "house-rules plugin: the branch nudge hit an error (%s: %s) "
                "and is offline for this call." % (type(exc).__name__, exc)
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
                trace_noop("runnable: %s is outside the project - scratch work, not compiled." % base)
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
            trace_noop("runnable: %s is not a runnable file - nothing to run." % base)
            return 0
        if _is_outside_project(file_path):
            trace_noop("runnable: %s is outside the project - scratch work, not run." % base)
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

# A backgrounded call's hand-back prompt shape, probed live - doc-ref 8313 docs/6-decisions/Decisions.md.
_PROMPT_VALUE_RE = re.compile(r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"')
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


def _common_git_dir(start):
    gd = _git_dir(start)
    if not gd:
        return None
    cd = os.path.join(gd, "commondir")
    if os.path.isfile(cd):
        rel = _read_text(cd).strip()
        if rel:
            return os.path.abspath(rel if os.path.isabs(rel) else os.path.join(gd, rel))
    return gd


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


# prompttimer - PermissionRequest (issue #144, plan docs/plans/2026-10-04-permission-prompt-timeout.md).
# Runs beside the permission dialog. If nobody answers within HOUSE_RULES_PROMPT_TIMEOUT seconds
# (default 300) it refuses, so one unanswered prompt cannot hold a whole session overnight. It only
# ever refuses: an unanswered prompt is a no, and the only other outcome is saying nothing, which
# leaves the dialog in charge. The refusal goes into the waiting-on-you list, which issue #145 shows.
PROMPT_TIMEOUT_DEFAULT = 300.0
WAITING_FILE = "waiting-on-you.json"
# Questions and choices put to aj, not permission to act: refusing one would throw the question
# away, not route around a blocked action, so they wait for aj however long that takes (#151).
PROMPT_TIMER_EXEMPT_TOOLS = ("AskUserQuestion", "ExitPlanMode")


class _PromptAnswered(Exception):
    """The hook was told to stop (SIGTERM/SIGINT): aj answered the dialog first."""


def _prompt_timeout_seconds():
    """(seconds or None when off, problem text or "")."""
    raw = os.environ.get("HOUSE_RULES_PROMPT_TIMEOUT")
    if raw is None or not raw.strip():
        return PROMPT_TIMEOUT_DEFAULT, ""
    val = raw.strip().lower()
    if val in ("off", "0"):
        return None, ""
    try:
        secs = float(val)
    except ValueError:
        secs = 0.0
    if 0 < secs < float("inf"):
        return secs, ""
    return PROMPT_TIMEOUT_DEFAULT, (
        "HOUSE_RULES_PROMPT_TIMEOUT=%r is not 'off', '0' or a positive number; using %d seconds"
        % (raw, PROMPT_TIMEOUT_DEFAULT)
    )


def _waiting_path(session_id=""):
    """The waiting-on-you list: in the common git directory, so worktrees share it. Outside a
    repository it is a session-keyed file in the temp directory, like versioncheck's marker.
    Returns (path, in_repo)."""
    cd = _common_git_dir(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if cd:
        return os.path.join(cd, "house-rules", WAITING_FILE), True
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-waiting-%s.json" % safe), False


def _waiting_load(path):
    """The entries; ValueError/OSError when the file exists but cannot be read as a list."""
    if not os.path.isfile(path):
        return []
    data = json.loads(_read_text(path))
    if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
        raise ValueError("unexpected shape, wanted a JSON list of objects")
    return data


def _waiting_save(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(entries, f, indent=1)
    os.replace(tmp, path)


WAITING_LOCK_WAIT = 3.0
WAITING_LOCK_STALE = 15.0


def _waiting_update(path, fn, who="prompttimer"):
    """Load, apply fn, save - under a lock file (path + '.lock', O_CREAT|O_EXCL) so two hooks
    cannot overwrite each other's entry. fn returns the new list, or None to leave the file as
    it is. Waits up to 3 s for the lock; a lock older than 15 s is stale and is removed (said on
    stderr). If the lock cannot be taken it says so and updates unlocked: never hangs, never
    crashes on the lock. A corrupt list is reported and started again; save errors raise."""
    lock = path + ".lock"
    held = False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        deadline = time.time() + WAITING_LOCK_WAIT
        while True:
            try:
                os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                held = True
                break
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(lock)
                except OSError:
                    continue  # it vanished between the two calls: take it
                if age > WAITING_LOCK_STALE:
                    try:
                        os.remove(lock)
                        sys.stderr.write("house-rules %s: removed a stale lock %s (%d s old).\n"
                                         % (who, lock, age))
                    except OSError as exc:
                        sys.stderr.write("house-rules %s: could not remove the stale lock %s (%s).\n"
                                         % (who, lock, exc))
                        time.sleep(0.05)
                    if time.time() >= deadline:
                        break
                    continue
                if time.time() >= deadline:
                    break
                time.sleep(0.05)
        if not held:
            sys.stderr.write("house-rules %s: could not take the lock %s within %g s; updating %s "
                             "without it, so a simultaneous update may be lost.\n"
                             % (who, lock, WAITING_LOCK_WAIT, path))
    except Exception as exc:
        sys.stderr.write("house-rules %s: could not take the lock %s (%s: %s); updating %s without it.\n"
                         % (who, lock, type(exc).__name__, exc, path))
    try:
        try:
            entries = _waiting_load(path)
        except (ValueError, OSError) as exc:
            sys.stderr.write("house-rules %s: could not read %s (%s: %s); starting that list again.\n"
                             % (who, path, type(exc).__name__, exc))
            entries = []
        new = fn(entries)
        if new is not None:
            _waiting_save(path, new)
    finally:
        if held:
            try:
                os.remove(lock)
            except OSError as exc:
                sys.stderr.write("house-rules %s: could not remove the lock %s (%s).\n" % (who, lock, exc))


def _waiting_clock(ts):
    try:
        return time.strftime("%H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError, OSError):
        return "an unknown time"


def _waiting_lines(entries):
    return "\n".join("- %s: %s" % (e.get("tool", "?"), e.get("summary", "?")) for e in entries)


def _waiting_scope_note(payload):
    """UserPromptSubmit: if this prompt is a real message from aj (a background task-notification
    is not aj being back), report this session's timed-out entries, mark them reported and drop
    its waiting entries. Returns the text for Claude, or "". Never raises."""
    try:
        m = _PROMPT_VALUE_RE.search(payload or "")
        if not m or _TASK_NOTIFICATION_RE.search(m.group(1)):
            return ""
        data = json.loads(payload)
        session_id = str(data.get("session_id") or "") if isinstance(data, dict) else ""
        path, _ = _waiting_path(session_id)
        if not os.path.isfile(path):
            return ""
        shown = []

        def fn(entries):
            mine = [e for e in entries if e.get("session_id") == session_id]
            timed = [e for e in mine if e.get("status") == "timed-out"]
            if not mine:
                return None
            shown.extend(dict(e) for e in timed)
            out = []
            for e in entries:
                if e.get("session_id") == session_id:
                    if e.get("status") in ("waiting", "ran"):
                        continue
                    if e.get("status") == "timed-out":
                        e = dict(e, status="reported")
                out.append(e)
            return out
        _waiting_update(path, fn, "scope")
        if not shown:
            return ""
        since = _waiting_clock(min(e.get("started", 0) for e in shown))
        return (
            "house-rules: %d action%s waiting on you since %s (local time):\n%s\n"
            "aj is here now, so retrying one shows a normal permission prompt."
            % (len(shown), "" if len(shown) == 1 else "s", since, _waiting_lines(shown))
        )
    except Exception as exc:
        sys.stderr.write("house-rules scope: could not report the waiting-on-you list (%s: %s).\n"
                         % (type(exc).__name__, exc))
        return ""


def _waiting_session_note(payload):
    """SessionStart: entries left by OTHER sessions, newest first, max 10; shown ones and any
    older than 7 days are dropped. Returns the text, or "". Never raises."""
    try:
        try:
            data = json.loads(payload) if payload else {}
        except ValueError:
            data = {}
        session_id = str(data.get("session_id") or "") if isinstance(data, dict) else ""
        path, _ = _waiting_path(session_id)
        if not os.path.isfile(path):
            return ""
        shown = []

        def fn(entries):
            others = [e for e in entries if e.get("session_id") != session_id and e.get("status") != "ran"]
            others.sort(key=lambda e: e.get("started") or 0, reverse=True)
            shown.extend(others[:10])
            gone = set(id(e) for e in shown)
            cutoff = time.time() - 7 * 86400
            keep = [e for e in entries if id(e) not in gone and e.get("status") != "ran"
                    and (e.get("started") or 0) >= cutoff]
            return keep if len(keep) != len(entries) else None
        _waiting_update(path, fn, "issuelist")
        if not shown:
            return ""
        return "Left waiting on you by an earlier session:\n" + "\n".join(
            "- %s %s: %s (%s)" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("started") or 0)),
                                  e.get("tool", "?"), e.get("summary", "?"), e.get("status", "?"))
            for e in shown)
    except Exception as exc:
        sys.stderr.write("house-rules issuelist: could not read the waiting-on-you list (%s: %s).\n"
                         % (type(exc).__name__, exc))
        return ""


def _waiting_clear_session(entries, session_id, status=None):
    """The entries without this session's (optionally only those with this status)."""
    return [e for e in entries
            if not (e.get("session_id") == session_id and (status is None or e.get("status") == status))]


def _waiting_key(tool_name, tool_input):
    blob = tool_name + json.dumps(tool_input, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _waiting_summary(tool_name, tool_input):
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool_name in ("Bash", "PowerShell"):
        text = ti.get("command")
    else:
        text = ti.get("file_path") or ti.get("notebook_path")
    text = " ".join(str(text).split()) if text else tool_name
    return text if len(text) <= 100 else text[:97] + "..."


def _prompt_refusal(minutes, path, summary):
    return (
        "Nobody answered this permission prompt for %s, so it was refused - not approved - and "
        "added to the waiting-on-you list (%s). Refused action: %s. Do not retry this action, or a "
        "variation of it, this session; it would only be refused again. Look for a route that needs no permission AND does "
        "not have the same effect (for example: commit to an AjsAgent/ branch instead of aj's branch; "
        "make the change with Edit instead of a full-file Write). Never get the same destructive "
        "result another way - deleting, force-pushing or killing a process has no substitute: leave "
        "it. Carry on with every part of the task that does not depend on this. Before you stop, "
        "list each refused action under 'Waiting on you' in your reply." % (minutes, path, summary)
    )


def _prompt_deny(text):
    emit({"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                 "decision": {"behavior": "deny", "message": text, "reason": text}}})


def _prompt_timeout_line():
    """The guard prompts' one line about the timer; "" when the timer is off."""
    secs, _ = _prompt_timeout_seconds()
    if secs is None:
        return ""
    return ("If nobody answers within %s, this is refused (never approved) and added to the "
            "waiting-on-you list." % _prompt_minutes(secs))


def _prompt_minutes(secs):
    if secs < 60:
        return "%g seconds" % secs
    n = round(secs / 60.0)
    return "%d minute%s" % (n, "" if n == 1 else "s")


def event_prompttimer():
    secs, problem = _prompt_timeout_seconds()
    if problem:
        sys.stderr.write("house-rules prompttimer: %s.\n" % problem)
    if secs is None:
        sys.stderr.write("house-rules prompttimer: off (HOUSE_RULES_PROMPT_TIMEOUT), no timer for this prompt.\n")
        return 0
    try:
        payload = read_payload()
    except Exception as exc:
        sys.stderr.write("house-rules prompttimer: could not read the permission-request payload (%s: %s); "
                         "no timer, the dialog decides.\n" % (type(exc).__name__, exc))
        return 0
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or not isinstance(data.get("tool_name"), str) or not data["tool_name"]:
            raise ValueError("not an object with a tool_name")
        tool_name = data["tool_name"]
        session_id = str(data.get("session_id") or "")
        tool_input = data.get("tool_input")
    except ValueError as exc:
        sys.stderr.write(
            "house-rules prompttimer: could not read the permission-request payload (%s: %s); "
            "no timer, the dialog decides.\n" % (type(exc).__name__, exc)
        )
        return 0
    if tool_name in PROMPT_TIMER_EXEMPT_TOOLS:
        sys.stderr.write("house-rules prompttimer: %s is a question for aj, not a permission prompt; "
                         "no timer, it waits for the answer.\n" % tool_name)
        return 0
    key = _waiting_key(tool_name, tool_input)
    summary = _waiting_summary(tool_name, tool_input)
    path, in_repo = _waiting_path(session_id)
    if not in_repo:
        sys.stderr.write("house-rules prompttimer: not inside a git repository; the waiting-on-you "
                         "list is the session file %s.\n" % path)

    def mine(e):
        return e.get("session_id") == session_id and e.get("key") == key

    def update(fn):
        """Load, change, save under the lock. A state problem is loud and never stops the timer."""
        try:
            _waiting_update(path, fn, "prompttimer")
        except Exception as exc:
            sys.stderr.write("house-rules prompttimer: could not write %s (%s: %s); the timer still "
                             "applies.\n" % (path, type(exc).__name__, exc))

    try:
        existing = _waiting_load(path)
    except (ValueError, OSError) as exc:
        sys.stderr.write("house-rules prompttimer: could not read %s (%s: %s); treating the list as "
                         "empty.\n" % (path, type(exc).__name__, exc))
        existing = []
    if any(mine(e) and e.get("status") == "timed-out" for e in existing):
        _prompt_deny(
            "This exact action already timed out this session and is still waiting on aj, so it was "
            "refused again without waiting. " + _prompt_refusal(_prompt_minutes(secs), path, summary))
        return 0
    away = [e for e in existing if e.get("session_id") == session_id and e.get("status") == "timed-out"]
    if away:
        # aj had the full wait on an earlier prompt and has not written since: they are away, and a
        # new prompt would only cost another full wait before the same refusal (#152).
        now = time.time()
        update(lambda es: [e for e in es if not mine(e)] + [
            {"session_id": session_id, "key": key, "tool": tool_name, "summary": summary,
             "started": now, "status": "timed-out", "timed_out_at": now}])
        _prompt_deny(
            "Another permission prompt this session already went unanswered (%s, since %s) and aj has "
            "not written since, so this one was refused at once instead of waiting again. "
            % (away[0].get("summary", "?"), _waiting_clock(away[0].get("started")))
            + _prompt_refusal(_prompt_minutes(secs), path, summary))
        return 0

    started = time.time()
    entry = {"session_id": session_id, "key": key, "tool": tool_name, "summary": summary,
             "started": started, "status": "waiting"}
    update(lambda es: [e for e in es if not mine(e)] + [entry])

    def stop(signum, frame):
        raise _PromptAnswered()

    try:
        import signal
        for name in ("SIGTERM", "SIGINT"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), stop)
    except (ImportError, ValueError, OSError) as exc:
        sys.stderr.write("house-rules prompttimer: could not watch for a stop signal (%s); an answered "
                         "prompt may leave a stale 'waiting' entry in %s.\n" % (exc, path))
    unreadable = []

    def ran():
        """promptran marked this action as run: it was approved some way that never stopped this
        hook (#149), so there is nothing left to time out."""
        try:
            return any(mine(e) and e.get("status") == "ran" for e in _waiting_load(path))
        except (ValueError, OSError) as exc:
            if not unreadable:  # once, not every second of the wait
                unreadable.append(exc)
                sys.stderr.write("house-rules prompttimer: could not read %s while waiting (%s: %s); "
                                 "cannot tell if the action ran, so the timer carries on.\n"
                                 % (path, type(exc).__name__, exc))
            return False

    try:
        while True:
            left = started + secs - time.time()
            if left <= 0:
                break
            time.sleep(min(1.0, left))
            if ran():
                sys.stderr.write("house-rules prompttimer: the action ran (approved without stopping "
                                 "this hook); removed its entry, no decision.\n")
                update(lambda es: [e for e in es if not (mine(e) and e.get("status") == "ran")])
                return 0
    except (_PromptAnswered, KeyboardInterrupt):
        sys.stderr.write("house-rules prompttimer: stopped while waiting (the prompt was answered); "
                         "removed its waiting entry, no decision.\n")
        update(lambda es: [e for e in es if not (mine(e) and e.get("status") == "waiting")])
        return 0

    def mark(es):
        es = [e for e in es if not mine(e)]
        es.append(dict(entry, status="timed-out", timed_out_at=time.time()))
        return es
    update(mark)
    _prompt_deny(_prompt_refusal(_prompt_minutes(secs), path, summary))
    return 0


def event_promptran():
    """PostToolUse / PostToolUseFailure: a tool call ran, so it was not refused (#149). A
    'waiting' entry for it becomes 'ran', which tells its prompttimer to stop without a decision.
    A 'timed-out' one is removed and reported, because it means an action recorded as refused
    ran anyway - for example through the old dialog, answered after the timer's refusal."""
    try:
        payload = read_payload()
        data = json.loads(payload) if payload else None
        if not isinstance(data, dict) or not isinstance(data.get("tool_name"), str):
            return 0
        session_id = str(data.get("session_id") or "")
        path, _ = _waiting_path(session_id)
        if not os.path.isfile(path):
            return 0
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
            emit({"systemMessage": text, "hookSpecificOutput": {
                "hookEventName": data.get("hook_event_name") or "PostToolUse", "additionalContext": text}})
    except Exception as exc:
        sys.stderr.write("house-rules promptran: could not update the waiting-on-you list (%s: %s).\n"
                         % (type(exc).__name__, exc))
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
            _branch_advice(bool(branch and branch.startswith(OWNED_BRANCH_PREFIXES)), branch,
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

AUTOSAVE_BRANCH_PREFIX = "worktree-agent-"
AUTOSAVE_REF_PREFIX = "refs/house-rules/autosave/"
COMMITGATE_THRESHOLD = 3
COMMITGATE_LIST_MAX = 8
CHECKPOINT_MINUTES = 10
STALLCHECK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stallcheck.py")
AUTOSAVE_PUSH_INTERVAL = 60
AUTOSAVE_PUSH_TIMEOUT = 6.0
AUTOSAVE_GIT_TIMEOUT = 4.0
SWEEP_MAX_WORKTREES = 10
WIP_NOT_COMMITTED = "wip: autosave - subagent did not commit when asked"
WIP_CHECKPOINT = "wip: checkpoint - %d min without a commit" % CHECKPOINT_MINUTES
WIP_PARENT = "wip: parent checkpoint of subagent work"
_AUTOSAVE_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash"}
_GATED_TOOLS = {"Write", "Edit", "NotebookEdit"}


def _autosave_enabled():
    return os.environ.get("HOUSE_RULES_AUTOSAVE", "on").strip().lower() not in _TOGGLE_OFF


def _ag(top, args, timeout=AUTOSAVE_GIT_TIMEOUT, env=None, check=True):
    """Run git in `top`; (returncode, stdout, stderr). Raises RuntimeError on failure when
    `check`, and on a timeout always - every caller turns that into a systemMessage."""
    import subprocess

    e = dict(os.environ)
    e["GIT_TERMINAL_PROMPT"] = "0"
    if env:
        e.update(env)
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=top, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, env=e,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("git %s timed out after %ss" % (args[0], timeout))
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace").strip()
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args[:2]), err or "exit %d" % proc.returncode))
    return proc.returncode, out, err


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
# PRs link with Refs and never close, and closing an issue always asks. The hooks FORCE Claude
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
    "create`. Show the user the issue numbers. Mark a step `in progress` (`gh issue edit N "
    "--add-label \"in progress\"`) when work on it starts and remove it when the issue closes. "
    "Until a parent and at least one child exist, a hook blocks edits to source files "
    "(docs/, .md files and .claude/ stay open). Do not close any issue yourself: closing always "
    "asks the user."
)


def _issues_enabled():
    return os.environ.get("HOUSE_RULES_ISSUES", "on").strip().lower() not in _TOGGLE_OFF


def _payload_cwd(payload):
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


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
    return ISSUE_NOTE.format(n=n)


_ISSUE_EDIT_ALLOWED_TOPS = ("docs", ".claude")


def _issues_gate(payload):
    """(deny reason or None, problem or None) for a Write/Edit/NotebookEdit payload."""
    try:
        data = json.loads(payload)
    except ValueError:
        return None, "house-rules: the issue gate could not parse the hook payload, so it is off for this call."
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
    state, problem = _issues_read(git_dir)
    if problem:
        return None, problem
    if not state or not state.get("needs_issues"):
        return None, None
    if not os.path.isabs(fp):
        fp = os.path.join(cwd, fp)
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(fp)), os.path.normcase(top))
    except ValueError:
        rel = ".."  # another drive: outside the project
    parts = rel.replace("\\", "/").split("/")
    if (parts[0] == ".." or parts[0] in _ISSUE_EDIT_ALLOWED_TOPS or rel.lower().endswith(".md")
            or os.path.basename(rel) == ISSUES_FILE):
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


_GH_PREFIX = r"(?:^|[;&|(\n`]|\$\()\s*gh\s+"
_GH_ISSUE_CREATE_RE = re.compile(_GH_PREFIX + r"issue\s+create\b")
_GH_PR_CREATE_RE = re.compile(_GH_PREFIX + r"pr\s+create\b")
_GH_ISSUE_CLOSE_RES = (
    re.compile(_GH_PREFIX + r"issue\s+close\b"),
    re.compile(_GH_PREFIX + r"issue\s+edit\b[^\n;&|]*--state[=\s]+[\"']?closed", re.IGNORECASE),
    re.compile(_GH_PREFIX + r"api\b(?=[^\n]*(?:-X|--method)[=\s]+[\"']?PATCH)(?=[^\n]*issues/\d+)"
               r"(?=[^\n]*state\W{0,4}closed)", re.IGNORECASE),
)
_ISSUE_URL_RE = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")


def _issues_record(payload):
    """PostToolUse Bash: record a `gh issue create` in the gate state. Returns a list of note
    strings (empty when nothing applies). Never raises."""
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or data.get("tool_name") != "Bash":
            return []
        ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
        cmd = ti.get("command") or ""
        if not _GH_ISSUE_CREATE_RE.search(cmd):
            return []
        top, git_dir = _issues_locate(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if not git_dir:
            return []
        state, problem = _issues_read(git_dir)
        if problem:
            return [problem]
        if not state or not state.get("needs_issues"):
            return []
        resp = data.get("tool_response")
        text = resp if isinstance(resp, str) else json.dumps(resp)
        found = list(dict.fromkeys(_ISSUE_URL_RE.findall(text)))
        if not found:
            return ["house-rules: a `gh issue create` ran but no issue URL was in its output, so it "
                    "was not counted toward the issue gate."]
        labelled = any(l.lower() in cmd.lower() for l in (ISSUES_LABEL, ISSUES_LABEL_OLD))
        created = state.setdefault("created", [])
        for repo, number in found:
            created.append({"repo": repo, "number": int(number), "labelled": labelled})
        notes = []
        if not labelled:
            notes.append("house-rules: issue #%s was created without the `%s` label, so it does not "
                         "count toward the issue gate and Focus Deck will ignore it. Add it with `gh "
                         "issue edit %s --add-label \"%s\"` and create the next issues with it."
                         % (found[0][1], ISSUES_LABEL, found[0][1], ISSUES_LABEL))
        have = _labelled_count(state)
        if have >= ISSUES_NEEDED:
            state["needs_issues"] = False
            notes.append("house-rules: %d labelled issues recorded, so source edits are unblocked." % have)
        _issues_write(git_dir, state)
        return notes
    except Exception as exc:
        return ["house-rules: could not record the `gh issue create` in the issue gate (%s: %s)."
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
_PR_BODY_FILE_RE = re.compile(r"(?:--body-file|(?<![\w-])-F)(?:=|\s+)(\"[^\"]+\"|'[^']+'|\S+)")
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
CLOSE_ASK_NOTE = (
    "House rules, closing an issue always asks the user: the user must have tested the work first, "
    "and this approval prompt is their go-ahead. On approval, also run `gh issue edit N "
    "--add-label \"Claude completed this\" --remove-label \"in progress\"` and comment on the "
    "issue with the merged PR link."
)


def _decoded_command(subject):
    m = _COMMAND_VALUE_RE.search(subject)
    if not m:
        return subject
    text = m.group(1)
    try:
        text = json.loads('"%s"' % text)
    except ValueError:
        text = m.group(1)  # undecodable escapes: match against the raw slice
    return text


def _attribution_enabled():
    return os.environ.get("HOUSE_RULES_ATTRIBUTION", "on").strip().lower() not in _TOGGLE_OFF


# Credit goes to "aj's agent", with no email and no Claude branding (issue #133). The Claude Code
# `attribution` setting is the primary mechanism and is written by tools/install.py; this check is
# the backstop for sessions that never read the settings file (cloud sessions).
_ATTRIBUTION_TEXT_RES = [
    re.compile(r"co-authored-by:[^\n]*(?:claude|anthropic)", re.IGNORECASE),
    re.compile(r"noreply@anthropic\.com", re.IGNORECASE),
    re.compile(r"generated with \[?claude", re.IGNORECASE),
    re.compile(r"claude\.com/claude-code", re.IGNORECASE),
    re.compile(r"claude-session\s*:", re.IGNORECASE),
    re.compile(r"claude\.ai/code/", re.IGNORECASE),
]
_ATTRIBUTION_CMD_RE = re.compile(
    r"(?:" + _GIT + r"commit([^0-9A-Za-z-]|$))|(?:" + _GH_PREFIX + r"(?:pr|issue)\s+(?:create|edit|comment)\b)",
    re.IGNORECASE,
)
ATTRIBUTION_DENY = (
    "House rules, credit aj's agent: this %s credits Claude (`%s`). Credit \"aj's agent\" instead, "
    "with no email and no Claude branding: commits end with `Committed by AJ's agent`, pull requests "
    "with `Opened by AJ's agent`. HOUSE_RULES_ATTRIBUTION=off disables this check."
)


def _attribution_guard(subject, payload):
    """None when the command's text does not credit Claude, else ("deny", reason, None)."""
    if not _attribution_enabled():
        return None
    cmd = _decoded_command(subject)
    if not _ATTRIBUTION_CMD_RE.search(cmd):
        return None
    text = cmd
    fm = _PR_BODY_FILE_RE.search(cmd)
    if fm and fm.group(1).strip("\"'") != "-":
        name = fm.group(1).strip("\"'")
        path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = text + "\n" + f.read()
        except OSError:
            pass  # the PR-body check already asks about an unreadable file; nothing more to say here
    for rx in _ATTRIBUTION_TEXT_RES:
        m = rx.search(text)
        if m:
            kind = "commit message" if _GIT_COMMIT_RE.search(cmd) else "pull request or issue text"
            return ("deny", ATTRIBUTION_DENY % (kind, m.group(0).strip()[:60]), None)
    return None


# Issue #178: the same credit check for writes made through the GitHub MCP tools, which never
# pass through `guard`. Only title/body/message and branch/head are read, never file content.
_GITHUB_COMMIT_TOOLS = ("push_files", "create_or_update_file")
BRANCH_DENY = (
    "House rules, credit aj's agent: `%s` is a new branch under `claude/`. Name agent branches "
    "`AjsAgent/<topic>` instead. HOUSE_RULES_ATTRIBUTION=off disables this check."
)


def event_guardgithub():
    # Fails open, loud (the plan: a broken check must not stop a GitHub write), unlike guard.
    try:
        raw = read_payload()
        payload = json.loads(raw) if raw else None
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
    except Exception as exc:
        emit({"systemMessage": "house-rules guardgithub: could not read the hook payload (%s); "
                               "the GitHub write was NOT checked for Claude credit." % exc})
        return 0
    if not payload:
        trace("guardgithub: empty payload - nothing was checked for this call.")
        return 0
    if not _attribution_enabled():
        trace_noop("guardgithub: HOUSE_RULES_ATTRIBUTION=off - nothing was checked.")
        return 0
    tool = str(payload.get("tool_name") or "")
    short = tool.split("__")[-1]
    args = payload.get("tool_input")
    if not isinstance(args, dict):
        trace("guardgithub: no tool_input object - nothing was checked for this call.")
        return 0
    kind = "commit message" if short in _GITHUB_COMMIT_TOOLS else "pull request or issue text"
    reason = None
    for field in ("title", "body", "message"):
        val = args.get(field)
        if not isinstance(val, str):
            continue
        for rx in _ATTRIBUTION_TEXT_RES:
            m = rx.search(val)
            if m:
                reason = ATTRIBUTION_DENY % (kind, m.group(0).strip()[:60])
                break
        if reason:
            break
    if not reason:
        new_branch = None
        if short == "create_branch":
            new_branch = args.get("branch")
        elif short == "create_pull_request":
            new_branch = args.get("head")
        if isinstance(new_branch, str) and new_branch.startswith("claude/"):
            reason = BRANCH_DENY % new_branch
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    return 0


# The agent's commit identity (issue #177): cloud containers ship user.name=Claude and
# noreply@anthropic.com, which signs every commit as Claude whatever the message says.
AGENT_IDENTITY_FIX = (
    "git config user.name \"AJ's agent\" && "
    "git config user.email \"79066376+Ajw2003@users.noreply.github.com\""
)
_ARG = r"(\"[^\"]*\"|'[^']*'|\S+)"
_AUTHOR_FLAG_RE = re.compile(r"--author(?:=|\s+)" + _ARG)


def _c_option_re(key):
    """-c key=value, also with the whole pair quoted (-c "user.name=aj's agent", #189)."""
    return re.compile(
        r"(?:^|\s)-c\s*(?:\"" + key + r"=([^\"]*)\"|'" + key + r"=([^']*)'|" + key + r"=" + _ARG + r")",
        re.IGNORECASE,
    )


_C_NAME_RE = _c_option_re(r"user\.name")
_C_EMAIL_RE = _c_option_re(r"user\.email")
_ENV_NAME_RE = re.compile(r"(?:^|[\s;&|])GIT_AUTHOR_NAME=" + _ARG)
_ENV_EMAIL_RE = re.compile(r"(?:^|[\s;&|])GIT_AUTHOR_EMAIL=" + _ARG)


def _unquote(s):
    return s.strip().strip("\"'").strip()


def _is_claude_identity(name, email):
    return (name or "").strip().lower() == "claude" or (email or "").strip().lower().endswith("anthropic.com")


def _git_author_ident(cwd):
    """(name, email) from `git var GIT_AUTHOR_IDENT` in cwd, or None when it cannot be read."""
    import subprocess
    try:
        p = subprocess.run(["git", "var", "GIT_AUTHOR_IDENT"], cwd=cwd, capture_output=True,
                           text=True, timeout=5)
    except Exception: return None  # git missing or timed out: identity unreadable, callers stay silent
    if p.returncode != 0:
        return None
    m = re.match(r"\s*(.*?)\s*<([^>]*)>", p.stdout)
    return (m.group(1), m.group(2)) if m else None


def _effective_author(cmd, cwd):
    """(name, email) the commit would carry; either may be None, whole result None when unreadable."""
    name = email = None
    m = _AUTHOR_FLAG_RE.search(cmd)
    if m:
        a = _unquote(m.group(1))
        am = re.match(r"(.*?)\s*<([^>]*)>\s*$", a)
        if am:
            name, email = am.group(1).strip(), am.group(2).strip()
        else:
            name = a
        return name, email
    for rx, which in ((_C_NAME_RE, 0), (_C_EMAIL_RE, 1), (_ENV_NAME_RE, 0), (_ENV_EMAIL_RE, 1)):
        m = rx.search(cmd)
        if m:
            # lastindex: _C_*_RE capture in whichever quoting branch matched.
            if which == 0 and name is None:
                name = _unquote(m.group(m.lastindex))
            elif which == 1 and email is None:
                email = _unquote(m.group(m.lastindex))
    if name is None or email is None:
        ident = _git_author_ident(cwd)
        if ident is None:
            return (name, email) if (name or email) else None
        name = ident[0] if name is None else name
        email = ident[1] if email is None else email
    return name, email


def _author_guard(subject, payload):
    """None unless a git commit would be authored as Claude, else ("deny", reason, None)."""
    if not _attribution_enabled():
        return None
    cmd = _decoded_command(subject)
    if not _GIT_COMMIT_RE.search(cmd):
        return None
    try:
        who = _effective_author(cmd, _payload_cwd(payload))
    except Exception: return None  # unreadable identity: let the commit through, as for an unreadable body file
    if who is None or not _is_claude_identity(*who):
        return None
    return ("deny", "House rules, credit aj's agent: this commit would be authored as `%s <%s>`, "
            "which signs it as Claude. Set the agent's identity in this repo and retry: `%s`. "
            "HOUSE_RULES_ATTRIBUTION=off disables this check."
            % (who[0] or "?", who[1] or "?", AGENT_IDENTITY_FIX), None)


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
    if any(r.search(cmd) for r in _GH_ISSUE_CLOSE_RES):
        return ("ask", CLOSE_ASK_NOTE, CLOSE_ASK_NOTE)
    return None


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
        if not _autosave_enabled() and not _issues_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit({"systemMessage": "house-rules plugin: autosave got an empty payload and did not run for this call."})
            return 0
        issue_notes = _issues_record(payload) if _issues_enabled() else []
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
        if not _autosave_enabled() and not _issues_enabled():
            return 0
        payload = read_payload()
        if not payload:
            emit({"systemMessage": "house-rules plugin: commitgate got an empty payload and did not run for this call."})
            return 0
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
        if status == "async_launched" and _autosave_enabled():
            watch_cmd = "python \"%s\" --watch --threshold 300" % STALLCHECK_PATH
            scope_notes = []
            for flag, label, value in (
                ("--session", "session_id", _field(_SESSION_ID_RE, payload)),
                ("--agent", "agentId", _field(_RESPONSE_AGENT_ID_RE, payload)),
            ):
                if re.fullmatch(r"[A-Za-z0-9_-]+", value or ""):
                    watch_cmd += " %s %s" % (flag, value)
                elif value:
                    scope_notes.append("the %s in the payload is not shell-safe, so %s is omitted" % (label, flag))
                else:
                    scope_notes.append("the payload has no %s, so %s is omitted" % (label, flag))
            scope_note = ""
            if scope_notes:
                scope_note = ("Note: " + "; ".join(scope_notes) + (
                    "; with no --session the watch is unscoped and reports every session's subagents. "
                    if "--session" not in watch_cmd else ". "))
            # Nothing to audit yet. A killed background subagent runs no hooks of its own, so
            # the parent's worktreesweep is what commits its work - and that only runs when the
            # parent wakes. Ask for a check-in so it does.
            emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
                "house-rules: a subagent is running in the background, so it must be checked for stalls "
                "every 5 minutes. Cheapest reliable way, no model call until something stalls: start "
                "Monitor with the command `%s` (it prints only on a "
                "STALLED or finished line), or run that command without --watch each time you wake. %s"
                "A parent that wakes also lets worktreesweep commit a stalled subagent's work (every "
                "%d min). On a STALLED line: find the agent's last tool call or blocking child process "
                "(newest transcript record, process list), tell the user how long it has been stuck and what it is "
                "blocked on, and ask before stopping a command that cannot finish. Do not assume it died or is "
                "fine; no later STALLED line is not progress; SendMessage cannot reach an agent blocked inside a "
                "tool call." % (watch_cmd, scope_note, CHECKPOINT_MINUTES))}})
            return 0
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

_TOGGLE_OFF = {"off", "0", "false", "no"}

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


# #89: a disclosure that something was not checked. The default is to check; a disclosure is
# right only when the check cannot run here, and then the reply says why. Lowercase-only for
# "untested"/"unverified" so a handover card's own "UNTESTED:" marker - which the card rule
# already requires a reason beside - is never what trips it.
_NOT_CHECKED_RE = re.compile(
    r"\b((?:[Nn]ot|[Hh]aven't|[Hh]ave not|[Dd]idn't|[Dd]id not|[Ww]asn't|[Ww]as not|[Hh]asn't|"
    r"[Hh]as not) (?:been )?(?:checked|verified|tested|run it|confirmed)|unverified|untested)\b"
)
# A reason in the same sentence makes the disclosure the rule-compliant kind.
_REASON_RE = re.compile(
    r"\b(because|since|as there|no access|not available|unavailable|not installed|"
    r"not reachable|(?:can't|cannot) (?:reach|run|access)|requires|would need|needs a|"
    r"no .{0,20} (?:here|on this machine)|on your machine|prohibitively|had no|has no|"
    r"there (?:is|was) no|does(?:n't| not) have|did(?:n't| not) have)\b",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?\n]")


def _unreasoned_not_checked(text):
    """'Not checked' phrases whose own sentence gives no reason the check could not run."""
    found = []
    text = text or ""
    for m in _NOT_CHECKED_RE.finditer(text):
        if _is_quoted(text, m.start()):
            continue
        start = max((e.end() for e in _SENTENCE_END_RE.finditer(text, 0, m.start())), default=0)
        end_m = _SENTENCE_END_RE.search(text, m.end())
        sentence = text[start : end_m.start() if end_m else len(text)]
        if _REASON_RE.search(sentence):
            continue
        found.append(m.group(1).lower())
    return found


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


# ---------------------------------------------------------------------------------------
# The commit rule's obligation half. guard only judges git commands that are run, so a session
# that never runs one produced no signal at all (#97). These helpers answer the one question
# the Stop, branchnudge and audit checks share: which of these files are still uncommitted?
# ---------------------------------------------------------------------------------------

COMMIT_CHECK_TIMEOUT = 2.0


def _commit_check_enabled():
    return os.environ.get("HOUSE_RULES_COMMIT_CHECK", "on").strip().lower() not in _TOGGLE_OFF


def _dirty_paths(root):
    """(repo top level, [repo-relative dirty paths]) for the repo containing `root`.

    Raises on no git, not a repo, or the time budget running out - every caller turns that
    into a "could not tell" line, never a guess.
    """
    import subprocess
    import time as _t

    deadline = _t.time() + COMMIT_CHECK_TIMEOUT

    def run_git(args):
        remaining = deadline - _t.time()
        if remaining <= 0:
            raise RuntimeError("the commit check's time budget ran out")
        proc = subprocess.run(
            ["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining
        )
        if proc.returncode != 0:
            raise RuntimeError("git %s exited %d" % (" ".join(args), proc.returncode))
        return [p for p in proc.stdout.decode("utf-8", "replace").splitlines() if p.strip()]

    top = run_git(["rev-parse", "--show-toplevel"])[0].strip()
    return top, [p for p, _tracked in _parse_status_porcelain(run_git(["status", "--porcelain", "-uall"]))]


def _uncommitted_among(paths, root, status=None):
    """The subset of `paths` (absolute, or relative to `root`) that git reports as changed or
    untracked. A path outside the repo is never in the subset: it is not this repo's to commit.
    `status` is a (top, dirty) pair from _dirty_paths, when the caller already has one."""
    top, dirty = status if status is not None else _dirty_paths(root)
    dirty_set = set(os.path.normcase(os.path.normpath(p)) for p in dirty)
    found = []
    for p in paths:
        absolute = p if os.path.isabs(p) else os.path.join(root, p)
        rel = os.path.relpath(os.path.realpath(absolute), os.path.realpath(top))
        if rel.startswith(".."):
            continue
        if os.path.normcase(os.path.normpath(rel)) in dirty_set:
            found.append(rel.replace(os.sep, "/"))
    return found


def _branch_advice(is_mine, branch, note):
    """What to do about uncommitted work, given whose branch the checkout is on."""
    if is_mine:
        return (
            "You are on your own branch `%s`: commit them now, scoped to those paths "
            "(`git commit -- <paths>`), and say what you committed and where." % branch
        )
    if branch:
        return (
            "The checkout is on `%s`, which is not an AjsAgent/ (or claude/) branch. If that branch was opened "
            "for this session's work, commit there, scoped to those paths. If it is the user's, "
            "branch off first (`git switch -c AjsAgent/<topic>` carries the changes with it), "
            "then commit, scoped to those paths. Either way, say what you committed and where."
            % branch
        )
    return (
        "No branch could be read (%s), so branch off first (`git switch -c AjsAgent/<topic>`), "
        "then commit, scoped to those paths, and say what you committed and where." % note
    )


def _commit_note(uncommitted):
    is_mine, branch, note = branch_ownership()
    shown = ", ".join(uncommitted[:8]) + (" and %d more" % (len(uncommitted) - 8) if len(uncommitted) > 8 else "")
    return (
        "House rules, commit on your own branch: this turn changed %s, and git still shows "
        "them uncommitted. %s Work left uncommitted is not a checkpoint." % (shown, _branch_advice(is_mine, branch, note))
    )


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
    return (
        "House rules, re-creating existing behaviour: this turn was a %s and wrote files, but "
        "the reply names nothing kept or dropped. Before this turn ends, report against the "
        "original: the keep/change/drop inventory with the original's file:line, every dropped "
        "feature named plainly - not only the ones the new platform forced - and a GitHub issue "
        "for each feature to be re-added later. If nothing was dropped, say so and say how you "
        "compared old and new." % word.lower()
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

    needs_card = _reply_needs_card_check(payload)

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
    transcript_path = _field(_TRANSCRIPT_RE, payload)
    if transcript_path and (_parity_enabled() or _visual_check_enabled() or _plain_summary_enabled()):
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
            if written_now and _visual_check_enabled():
                visual = [os.path.basename(p) for p in written_now if _VISUAL_EXT_RE.search(p)]
                if visual and not _looked_at_result(list(_turn_tool_uses(turn_records))):
                    visual_files = visual

    issue_line, issue_problem = _issues_stop_line(payload)

    trace_lines = []
    if issue_problem:
        trace_lines.append(issue_problem)
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

    if (not needs_card and not needs_evidence and not not_checked and not uncommitted
            and not parity_word and not visual_files and not plain_problems and not issue_line):
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
    if not_checked:
        parts.append(_not_checked_note(not_checked))
    if plain_problems:
        parts.append(_plain_summary_note(plain_problems))
    if parity_word:
        parts.append(_parity_report_note(parity_word))
    if visual_files:
        parts.append(_visual_note(visual_files))
    if uncommitted:
        parts.append(_commit_note(uncommitted))
    if issue_line:
        parts.append(issue_line)
    out = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "\n\n".join(parts)}}
    if trace_lines:
        out["systemMessage"] = " ".join(trace_lines)
    emit(out)
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
    "that owns that code (docs/4-systems/*.md), creating one if none does, under the section "
    "that fits - the design into How it works, an operational gotcha into Traps, a rule that "
    "must stay true into Invariants. Design rationale, a rejected approach, or a post-mortem is "
    "different - it is a record of a choice, not current truth about the system - so it becomes "
    "a dated entry in docs/6-decisions/Decisions.md instead. Either way, leave a one-line pointer at the "
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

    full_file must be False for an Edit's new_string fragment. See docs/6-decisions/Decisions.md,
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
        # check. See docs/6-decisions/Decisions.md, "Fix the harvest handler treating an Edit fragment's
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

        # Default: speak only when something was found or an override was bad. The
        # "no comment runs found / none met the threshold" line is a no-op trace, verbose only.
        if not quiet and (blocks or problems or trace_verbose()):
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
