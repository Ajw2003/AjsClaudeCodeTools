"""house_rules.core - the core of the house-rules hook engine (#357, step 2a of #340).

Holds the shared helpers (payload reading, emit, trace), the SessionStart handlers (inject,
showrule, profile, standards, versioncheck and the self-updater), scope (UserPromptSubmit),
artifact, runnable and promptran (PostToolUse), and work_saved_elsewhere. Moved verbatim from
hook.py; docs/4-systems/plugin-restructure.md, "Step 2", says what moved and why.

The core never imports hook.py or any part module. Where a core handler needs code that
belongs to another part, that code registers itself on one of the three link lists at the
bottom of this file (SESSION_START_HOOKS, PROMPT_HOOKS, POST_TOOL_HOOKS) and the handler loops
over the list. STDLIB ONLY, like hook.py.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse

# This file is one folder deeper than hook.py, so every path hook.py computed from its own
# __file__ is computed from this instead: the scripts/ folder that holds hook.py and house_rules/.
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
            if plugin_id.split("@", 1)[0] != _VC_PLUGIN_NAME:
                continue
            if isinstance(entries, dict):
                entries = [entries]
            entry = next((e for e in entries if isinstance(e, dict) and e.get("installPath")), None)
            break
    except Exception as exc:
        return own, "could not check for newer rules: installed_plugins.json is unreadable (%s), so this folder's rules (%s) were loaded" % (type(exc).__name__, own)
    if entry is None:
        return own, "could not check for newer rules: installed_plugins.json has no installPath for %s, so this folder's rules (%s) were loaded" % (_VC_PLUGIN_NAME, own)
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
    # That strip is delegation's knowledge, so it is a hook registered under "inject" on
    # SESSION_START_HOOKS: each takes the rules text and returns it.
    for fn in _session_start_hooks("inject"):
        body = fn(body)
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
# profile — a third SessionStart handler, split out of inject in 2.17.1 (docs/6-decisions/Decisions.md,
# 2026-09-22): the per-hook additionalContext limit is 10,000 chars, and a recorded
# rules/environment.md can by itself be large enough that appending it to inject's own text
# risked pushing inject over the limit. Registered with no matcher gate of its own (SessionStart
# only), right after inject in hooks.json, so a failure here can never take inject down with it.
# ---------------------------------------------------------------------------------------


def event_profile():
    here = SCRIPTS_DIR
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

        # Remote-session branch and git-identity notes are the safe git part's; each one
        # registered under "profile" on SESSION_START_HOOKS returns its text ("" for none).
        for fn in _session_start_hooks("profile"):
            handover_block += fn()

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
        here = SCRIPTS_DIR
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


def _is_synced_copy():
    """#403: claude.ai cloud sessions load the plugin from a synced copy under
    .../plugins/synced/, not from the marketplace, so `claude plugin update` cannot work."""
    for root in (os.environ.get("CLAUDE_PLUGIN_ROOT", ""), _plugin_root()):
        if "/plugins/synced/" in (root or "").replace("\\", "/"):
            return True
    return False


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

        if _is_synced_copy():
            if installed and installed == latest:
                return 0
            line = (
                "house-rules %s is a copy synced from your claude.ai account, so it cannot be "
                "updated by command here%s."
                % (installed or "(version unknown)", "; GitHub has %s" % latest if latest else "")
            )
            emit({
                "systemMessage": line,
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line},
            })
            return 0

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
    waiting = ""
    try:
        payload = read_payload()
        m = _PROMPT_FIELD_RE.search(payload)
        field = m.group(0) if m else None
        # The prompt links (PROMPT_HOOKS): code that belongs to another part adds its clause
        # to the reminder and/or a note after it. A note from a later hook goes in front of
        # the ones before it; notes are kept as they come so a failing hook loses only its own.
        clauses, notes = [], []
        for fn in PROMPT_HOOKS:
            clause, note = fn(payload, field)
            clauses.append(clause)
            if note:
                notes.insert(0, note)
                waiting = "\n\n".join(notes)
        if m:
            if _SCOPE_COMMAND_HINT_RE.search(field):
                reminder = SCOPE_REMINDER
            reminder = reminder + "".join(clauses)
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


SAVED_CHECK_TIMEOUT = 2.0


def work_saved_elsewhere(root=None):
    """(saved, note): is everything a reset/rebase/restore could lose already somewhere it
    cannot reach? Yes only when the working tree is clean (nothing uncommitted or untracked)
    and no commit reachable from HEAD is missing from every remote-tracking ref (#153).
    The second deliberate subprocess in guard, after the docs check; it runs only when a SAVED
    pattern matched on my branch. Anything it cannot tell is a no, with the reason."""
    import subprocess

    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
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
        # The page writing note belongs to the writing part: whatever registered under
        # "artifact" on POST_TOOL_HOOKS is asked, and its notes (if any) are joined.
        page_note = "\n\n".join(n for n in (fn(file_path) for fn in _post_tool_hooks("artifact")) if n)
        if not _is_outside_project(file_path):
            if page_note:
                emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": page_note}})
            else:
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
                    "additionalContext": ARTIFACT_NOTE.format(where=where)
                    + ("\n\n" + page_note if page_note else ""),
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
    "command you have not run. One clean run is not proof it works: run the parts you "
    "touched twice (the rest once; CI runs it all), since the second run meets the state the "
    "first one left behind, and give it a realistic input "
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



def _plugin_version(problems=None):
    here = SCRIPTS_DIR
    path = os.path.join(here, "..", ".claude-plugin", "plugin.json")
    version = ""
    try:
        version = json.loads(_read_text(path)).get("version", "") or ""
    except Exception as exc:
        if problems is not None:
            problems.append("could not read the plugin version (%s)" % type(exc).__name__)
    return version



def event_promptran():
    """PostToolUse / PostToolUseFailure: a tool call ran, so it was not refused (#149). A
    'waiting' entry for it becomes 'ran', which tells its prompttimer to stop without a decision.
    A 'timed-out' one is removed and reported, because it means an action recorded as refused
    ran anyway - for example through the old dialog, answered after the timer's refusal.
    The waiting-on-you list belongs to the safe git part, so the update itself is the hook
    registered under "promptran" on POST_TOOL_HOOKS; it returns the report text, or "" for none."""
    try:
        payload = read_payload()
        data = json.loads(payload) if payload else None
        if not isinstance(data, dict) or not isinstance(data.get("tool_name"), str):
            return 0
        for fn in _post_tool_hooks("promptran"):
            text = fn(data)
            if text:
                emit({"systemMessage": text, "hookSpecificOutput": {
                    "hookEventName": data.get("hook_event_name") or "PostToolUse", "additionalContext": text}})
    except Exception as exc:
        sys.stderr.write("house-rules promptran: could not update the waiting-on-you list (%s: %s).\n"
                         % (type(exc).__name__, exc))
    return 0


# ---------------------------------------------------------------------------------------
# Shared by more than one part (#358, step 2b). A part may not import another part, so what the
# safe git part and the docs part (or the code still in hook.py) both read lives here, moved
# verbatim from hook.py.
# ---------------------------------------------------------------------------------------

# One shell word: quoted runs may hold spaces, so -c user.name="aj's agent" is one word (#189).
_WORD = r"""(?:"[^"]*"|'[^']*'|[^\s"'])+"""
# `git` plus any run of global options before the subcommand.
# Why the alternation's first branch exists: docs/architecture.md, "The pre-existing hole this exposed".
_GIT = (
    r"git\s+((?:-[cC]|--git-dir|--work-tree|--namespace|--exec-path|--super-prefix)"
    r"[=\s]\s*" + _WORD + r"\s+|-" + _WORD + r"\s+)*"
)


# Reuses GUARD_R3's own commit pattern rather than a second copy - "is this a commit" and "is
# this exempt from asking" are different questions, and the docs check needs the first one
# independent of the second (a commit on my own branch is exempt from asking but still needs
# the docs reminder).
_GIT_COMMIT_RE = re.compile(_GIT + r"commit([^0-9A-Za-z-]|$)", re.IGNORECASE)


_STATEMENT_SPLIT_RE = re.compile(r"&&|\|\||;|\n")


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


_COMMAND_VALUE_RE = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"')


# A backgrounded call's hand-back prompt shape, probed live - doc-ref 8313 docs/6-decisions/Decisions.md.
_PROMPT_VALUE_RE = re.compile(r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"')


# #253: prompts that reach UserPromptSubmit but are a helper's report or a system notice, not aj.
_RELAYED_PROMPT_RE = re.compile(
    r"<task-notification>|<system-reminder>|<agent-message\b|\[Subagent hand-?back\]"
    r"|Another Claude session sent a message", re.IGNORECASE)


def _is_relayed_prompt(text, payload=None):
    """True when the prompt is a subagent hand-back, agent message or task/system notification, or
    the payload carries a non-human `origin` (as _is_genuine_user_message honours)."""
    if text and _RELAYED_PROMPT_RE.search(text):
        return True
    try:
        data = json.loads(payload) if payload else None
    except ValueError:
        data = None
    origin = data.get("origin") if isinstance(data, dict) else None
    if isinstance(origin, dict):
        origin = origin.get("kind") or origin.get("type")
    return bool(origin) and str(origin).lower() not in ("human", "user")


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


AUTOSAVE_BRANCH_PREFIX = "worktree-agent-"


AUTOSAVE_GIT_TIMEOUT = 4.0


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


def _payload_cwd(payload):
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


_TOGGLE_OFF = {"off", "0", "false", "no"}


# ---------------------------------------------------------------------------------------
# The core links (#357). The core never imports hook.py or a part module, so where one of its
# handlers needs code that belongs to another part, that code registers itself here and the
# handler loops over the list. Three lists, one register function each:
#   SESSION_START_HOOKS  (consumer, fn): inject asks fn(body) -> body, profile asks fn() -> text
#   PROMPT_HOOKS         fn(payload, field) -> (clause, note)   scope runs each on every message;
#                        field is the prompt JSON field or None; clause is added straight after
#                        the reminder, note after it (a later hook's note goes in front)
#   POST_TOOL_HOOKS      (consumer, fn): artifact asks fn(file_path) -> note text, promptran
#                        asks fn(data) -> report text; each handler runs only its own consumer's
# Step 2b adds three more, read by the safe git part (#358):
#   GUARD_ISSUE_HOOKS    fn(subject, payload) -> None or (kind, reason, context); guard asks each,
#                        in order, after its own attribution check, and takes the first answer
#   GITHUB_WRITE_HOOKS   fn(payload, raw) -> True when it handled the call (and emitted);
#                        guardgithub asks each before its own credit check
#   DOCS_STATUS_HOOKS    fn(subject, elsewhere, root) -> (status, detail); guard asks the first
# ---------------------------------------------------------------------------------------

SESSION_START_HOOKS = []
PROMPT_HOOKS = []
POST_TOOL_HOOKS = []
GUARD_ISSUE_HOOKS = []
GITHUB_WRITE_HOOKS = []
DOCS_STATUS_HOOKS = []


def _register(hooks, entry):
    # Replace an earlier registration of the same name instead of adding a second one:
    # verify.py loads hook.py several times in one process, and a plain append would make
    # every later load run each hook twice. The module loaded last is the one in use.
    name = (entry[0], entry[-1].__name__) if isinstance(entry, tuple) else entry.__name__
    for i, old in enumerate(hooks):
        if ((old[0], old[-1].__name__) if isinstance(old, tuple) else old.__name__) == name:
            hooks[i] = entry
            return
    hooks.append(entry)


def register_session_start(consumer, fn):
    _register(SESSION_START_HOOKS, (consumer, fn))
    return fn


def register_prompt(fn):
    _register(PROMPT_HOOKS, fn)
    return fn


def register_post_tool(consumer, fn):
    _register(POST_TOOL_HOOKS, (consumer, fn))
    return fn


def _session_start_hooks(consumer):
    return [fn for name, fn in SESSION_START_HOOKS if name == consumer]


def _post_tool_hooks(consumer):
    return [fn for name, fn in POST_TOOL_HOOKS if name == consumer]


def register_guard_issue(fn):
    _register(GUARD_ISSUE_HOOKS, fn)
    return fn


def register_github_write(fn):
    _register(GITHUB_WRITE_HOOKS, fn)
    return fn


def register_docs_status(fn):
    _register(DOCS_STATUS_HOOKS, fn)
    return fn


# ---------------------------------------------------------------------------------------
# Moved here in step 2c (#359): helpers that more than one part, or a part and the end-of-reply
# dispatcher in hook.py, use. The first group came out of the safe git part, the second out of hook.py.
# ---------------------------------------------------------------------------------------

OWNED_BRANCH_PREFIXES = ("AjsAgent/", "claude/", "ccr-")  # claude/ = cloud app branches, old branches; ccr- = cloud sessions


def owned_branch_prefixes():
    """The defaults plus HOUSE_RULES_OWNED_BRANCHES (comma-separated extras, never replacing)."""
    extra = tuple(p.strip() for p in os.environ.get("HOUSE_RULES_OWNED_BRANCHES", "").split(",") if p.strip())
    return OWNED_BRANCH_PREFIXES + extra


# Any -C at all, broad on purpose (`grep -C 3` included); only the `git -C <dir>` form below is
# resolved to a directory, and a -C it does not explain leaves where the command runs unclear.
_ANY_C_FLAG_RE = re.compile(r"(^|\s)-C(\s|=)")


_GIT_C_DIR_RE = re.compile(r"""\bgit\s+-C\s*(?:"([^"$`\\]+)"|'([^']+)'|([^\s;&|"'$`\\()<>~*?]+))""")


_LEADING_CD_RE = re.compile(r"""^\s*cd\s+(?:"([^"$`\\]+)"|'([^']+)'|([^\s;&|"'$`\\()<>~*?]+))\s*(?:&&|;)""")


# A statement-leading NAME=value, NAME="value" or NAME='value' followed by ; or && (#261).
_ASSIGN_RE = re.compile(r"""(?:^|(?<=[;&\n]))\s*([A-Za-z_]\w*)=(?:"([^"$`\\\n]*)"|'([^'\n]*)'|([^\s;&|"'$`\\()<>*?]*))[ \t]*(?:&&|;)""")


# cd/pushd only where a command can start, so `git commit -m "fix cd handling"` keeps the
# exemption (#203); shell keywords count, so `if t; then cd x; fi` is still seen.
_ANY_CD_RE = re.compile(r"(?:^|[;&|({!\n]|\b(?:if|elif|while|until|then|do|else|time|exec)\b)\s*(?:cd|pushd)(?=\s|$)")


def _apply_assigns(cmd):
    """#261/#262: drop simple same-command NAME=value assignments and expand $NAME / ${NAME}
    from them; a name that was not assigned stays as written."""
    assigns = {}
    for am in _ASSIGN_RE.finditer(cmd):
        assigns[am.group(1)] = am.group(2) if am.group(2) is not None else (am.group(3) if am.group(3) is not None else am.group(4))
    if assigns:
        cmd = _ASSIGN_RE.sub("", cmd)
        cmd = re.sub(r"\$\{(\w+)\}|\$(\w+)", lambda mm: assigns.get(mm.group(1) or mm.group(2), mm.group(0)), cmd)
    return cmd


def _command_dir(payload):
    """(dir, moved_unclear): where a guarded Bash command runs. The payload's `cwd`, else
    CLAUDE_PROJECT_DIR, else getcwd(); a lone leading `cd <dir> &&`, or `git -C <dir>` naming one
    directory, moves it to <dir>. Any other -C, any other
    cd/pushd, or a leading one that does not resolve to a directory, sets moved_unclear and the
    caller withholds the exemption. doc-ref d2a4 docs/4-systems/hook-engine.md (Traps).
    """
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    base = cwd if isinstance(cwd, str) and cwd else (os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        cmd = data["tool_input"]["command"]
    except (TypeError, KeyError):
        m = _COMMAND_VALUE_RE.search(payload)
        try:
            cmd = json.loads('"%s"' % m.group(1)) if m else ""
        except ValueError:
            cmd = ""
    if not isinstance(cmd, str):
        return base, False
    # #261: simple NAME=value / NAME="value" assignments earlier in the command expand into a
    # cd or -C target; a target that still holds a $ afterwards stays unclear.
    cmd = _apply_assigns(cmd)
    c_flags = _ANY_C_FLAG_RE.findall(cmd)
    if c_flags:
        # `git -C <dir>` (#192): judged by <dir> when every -C names the same one and nothing cds.
        dirs = set(m.group(1) or m.group(2) or m.group(3) for m in _GIT_C_DIR_RE.finditer(cmd))
        if _ANY_CD_RE.search(cmd) or len(dirs) != 1 or len(_GIT_C_DIR_RE.findall(cmd)) != len(c_flags):
            return base, True
        target = os.path.abspath(os.path.join(base, dirs.pop()))
        return (target, False) if os.path.isdir(target) else (base, True)
    if not _ANY_CD_RE.search(cmd):
        return base, False
    m = _LEADING_CD_RE.match(cmd)
    if m and len(_ANY_CD_RE.findall(cmd)) == 1:
        target = os.path.abspath(os.path.join(base, m.group(1) or m.group(2) or m.group(3)))
        if os.path.isdir(target):
            return target, False
    return base, True


WAITING_FILE = "waiting-on-you.json"


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


_GH_PREFIX = r"(?:^|[;&|(\n`]|\$\()\s*gh\s+"


_PR_BODY_FILE_RE = re.compile(r"(?:--body-file|(?<![\w-])-F)(?:=|\s+)(\"[^\"]+\"|'[^']+'|\S+)")


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


_PLAN_VALUE_RE = re.compile(r'"plan"\s*:\s*"((?:[^"\\]|\\.)*)"')


_SESSION_ID_RE = re.compile(r'"session_id"\s*:\s*"((?:[^"\\]|\\.)*)"')


_TRANSCRIPT_RE = re.compile(r'"transcript_path"\s*:\s*"((?:[^"\\]|\\.)*)"')


_AUDIT_COMMAND_TOOLS = ("Bash", "PowerShell")


_AUDIT_WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")


_GATED_TOOLS = {"Write", "Edit", "NotebookEdit"}


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


def _loop_enabled():
    return os.environ.get("HOUSE_RULES_LOOP", "on").strip().lower() not in _TOGGLE_OFF


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


SCOPE_PARITY_CLAUSE = (
    "\n- This reads like re-creating existing behaviour (a port, rewrite, restructure or "
    "migration). Inventory what the original does from its code first - keep/change/drop, "
    "shown before building - verify against the original, and name every drop."
)


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


def _clear_writing_enabled():
    return os.environ.get("HOUSE_RULES_CLEAR_WRITING", "on").strip().lower() not in _TOGGLE_OFF


def _parity_enabled():
    return os.environ.get("HOUSE_RULES_PARITY", "on").strip().lower() not in _TOGGLE_OFF


def _parity_report_note(word):
    # #309 (incident 5 of #303): report only until the restructure. The demand for an inventory and an
    # issue per drop fired on a one-entry Decisions.md append, and three times on audit-notes turns.
    return (
        "House rules, re-creating existing behaviour (report only, #309): aj's message reads like a %s "
        "and this turn wrote files, but the reply names nothing kept or dropped. Nothing is required "
        "this turn; the note is kept as evidence for the restructure." % word.lower()
    )


# The shared writing checker (#247), a sibling file of hook.py (moved from hook.py in step 2c: the writing part, the
# design loop part and the end-of-reply dispatcher all use it). A missing or broken copy must not take every hook
# down with it, so it is loaded here and each check that needs it reports when it is absent.
sys.path.insert(0, SCRIPTS_DIR)
try:
    import clarity
    CLARITY_ERROR = None
except ImportError as _clarity_exc:
    clarity = None
    CLARITY_ERROR = "house-rules: the writing checker (scripts/clarity.py) could not load (%s)." % _clarity_exc


# ---------------------------------------------------------------------------------------
# The step 2c link lists (#359). Same shape as the lists above. The delegation part calls the design
# loop part at four places, and neither may import the other, so the design loop registers on these.
#   DELEGATE_NOTE_HOOKS  fn(payload) -> str      event_delegate appends each answer to the plan reminder
#   SUBAGENT_NOTE_HOOKS  fn(payload) -> str      event_subagentrules joins each answer onto the subagent core
#   TOOL_RECORD_HOOKS    fn(payload) -> [notes]  event_autosave adds each list to its notes, in order
#   EDIT_GATE_HOOKS      fn(payload) -> bool     event_commitgate asks each first; True = it answered
# ---------------------------------------------------------------------------------------

DELEGATE_NOTE_HOOKS = []
SUBAGENT_NOTE_HOOKS = []
TOOL_RECORD_HOOKS = []
EDIT_GATE_HOOKS = []


def register_delegate_note(fn):
    _register(DELEGATE_NOTE_HOOKS, fn)
    return fn


def register_subagent_note(fn):
    _register(SUBAGENT_NOTE_HOOKS, fn)
    return fn


def register_tool_record(fn):
    _register(TOOL_RECORD_HOOKS, fn)
    return fn


def register_edit_gate(fn):
    _register(EDIT_GATE_HOOKS, fn)
    return fn


# ---------------------------------------------------------------------------------------
# The evidence check of the end-of-reply dispatcher (event_handover in hook.py), moved out of it verbatim.
# ---------------------------------------------------------------------------------------

def handover_evidence_check(payload):
    """(reply text or None when the payload carries none, needs_evidence, evidence_words, impossible_words,
    not_checked, could_not_tell). The evidence check is independent of the fence gate: a reply can claim
    success with no fence in it at all."""
    needs_evidence = False
    evidence_words = []
    impossible_words = []
    not_checked = []
    could_not_tell = None
    reply_text = None
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
    return reply_text, needs_evidence, evidence_words, impossible_words, not_checked, could_not_tell
