"""house_rules/settings.py - the plugin's settings and the one place identity strings may live (#341, step 3 of #381).

Two settings, and every identity string in the hooks derives from them:
  agent_name            the agent's name (for aj: "ajw2003sAgent"). Credit lines, the agent branch prefix and the
                        commit author name all come from it.
  extra_owned_prefixes  extra branch prefixes that count as the agent's own, comma-separated ("AjsAgent/,claude/").
                        Set to the empty string when there are none; an empty value still counts as set.

Derived from agent_name, never stored: "Committed by <name>" (commits), "Opened by <name>" (pull requests and
issues), the branch prefix "<name>/", and the commit author name. The commit author email is the user's own git
email, read from git config; it is not a setting.

READ ORDER, first one that has a value wins (grilling rounds 2 to 4 in docs/6-decisions/Decisions.md):
  1. the environment: HOUSE_RULES_AGENT_NAME, HOUSE_RULES_OWNED_BRANCHES
  2. the settings file: <config dir>/house-rules/settings.json, where <config dir> is $CLAUDE_CONFIG_DIR or
     ~/.claude (the same place core.py already reads per-user Claude state from). It sits outside every repo, so it
     follows the machine. HOUSE_RULES_SETTINGS_FILE points it elsewhere (the checks use that).
  3. `/plugin configure` (userConfig): plugin.json declares no userConfig, so there is nothing to read; skipped.
There is no assumed default. A setting with no value is "unset", and the guard refuses until it has one.

THE DEFAULTS PLACE. This file is the only shipped script allowed to hold the literal strings that name aj's agent or
aj's account (verify.py greps every other shipped script for them). What must stay literal lives in the constants
below: the GitHub label names (existing labels in aj's repos carry them, so renaming would break them) and the
default repo owner.

STDLIB ONLY, no import of another part, so core.py and scripts/settings.py can both use it.
"""

import json
import os
import re
import subprocess

SETTING_NAMES = ("agent_name", "extra_owned_prefixes")
ENV_VARS = {"agent_name": "HOUSE_RULES_AGENT_NAME", "extra_owned_prefixes": "HOUSE_RULES_OWNED_BRANCHES"}
SETTINGS_FILE_ENV = "HOUSE_RULES_SETTINGS_FILE"
NAME_SUFFIX = "sAgent"  # the suggestion: <github login, lowercased> + this
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # becomes a branch prefix and a git author name
CCR_PREFIX = "ccr-"  # cloud-session branches: how Claude Code names them, not the agent's identity
CLAUDE_BRANCH_PREFIX = "claude/"  # the cloud app's branches: a fact about Claude Code, not the agent's identity
SETTINGS_SCRIPT = "settings.py"

# --- what must stay literal ---------------------------------------------------------------------------------
# GitHub labels exist by these names in aj's repos; deriving them from agent_name would orphan every issue that
# carries them, so they stay as they are (reported on #341, not renamed).
ISSUES_LABEL = "AjsAgent created this"
ISSUES_LABEL_OLD = "Claude created this"
COMPLETED_LABEL = "AjsAgent completed this"
HOUSE_LABELS = [
    (ISSUES_LABEL, "5b6b7a", "Opened by AJ's agent"),
    ("in progress", "FBCA04", "AJ's agent is working on it"),
    ("needs review", "0E8A16", "Waiting on aj"),
]
DEFAULT_GITHUB_OWNER = "Ajw2003"
PLUGIN_JSON_URL = (
    "https://raw.githubusercontent.com/Ajw2003/AjsClaudeCodeTools/main/"
    "claude-house-rules/plugins/house-rules/.claude-plugin/plugin.json"
)
# --------------------------------------------------------------------------------------------------------------


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def settings_path():
    return os.environ.get(SETTINGS_FILE_ENV) or os.path.join(config_dir(), "house-rules", "settings.json")


def read_file():
    """(values, problem). A missing file is the normal first run: ({}, None). An unreadable one says so."""
    path = settings_path()
    if not os.path.exists(path):
        return {}, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return {}, "the settings file %s could not be read (%s: %s)" % (path, type(exc).__name__, exc)
    if not isinstance(data, dict):
        return {}, "the settings file %s is not a JSON object" % path
    return data, None


def get(name):
    """(value, source): source is "environment", "settings file", or None when unset. The environment wins.

    agent_name must be non-empty to count as set. extra_owned_prefixes counts as set when present, even empty."""
    if name not in SETTING_NAMES:
        raise KeyError(name)
    env = os.environ.get(ENV_VARS[name])
    if env is not None and (env.strip() or name == "extra_owned_prefixes"):
        return env.strip(), "environment (%s)" % ENV_VARS[name]
    values, _problem = read_file()
    val = values.get(name)
    if isinstance(val, str) and (val.strip() or name == "extra_owned_prefixes"):
        return val.strip(), "settings file (%s)" % settings_path()
    return None, None


def missing():
    return [n for n in SETTING_NAMES if get(n)[0] is None]


def settings_command(name):
    """The exact command that sets a setting, for a refusal or a note."""
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SETTINGS_SCRIPT)
    example = {"agent_name": "<name>", "extra_owned_prefixes": "\"<prefix/>,<prefix/>\" (\"\" for none)"}[name]
    return "python3 %s set %s %s" % (script, name, example)


def agent_name():
    return get("agent_name")[0]


def agent_prefix():
    n = agent_name()
    return n + "/" if n else None


def extra_prefixes():
    v = get("extra_owned_prefixes")[0] or ""
    return tuple(p.strip() for p in v.split(",") if p.strip())


def owned_prefixes():
    """Every prefix that makes a branch the agent's own: its own prefix, the settings' extras, and cloud-session ccr-."""
    own = agent_prefix()
    return ((own,) if own else ()) + extra_prefixes() + (CCR_PREFIX,)


def commit_credit():
    return "Committed by %s" % (agent_name() or "<agent_name>")


def pr_credit():
    return "Opened by %s" % (agent_name() or "<agent_name>")


def git_email(cwd=None):
    """The user's own git email, or None when git has none or it is Claude's (a cloud container's default)."""
    try:
        p = subprocess.run(["git", "config", "user.email"], cwd=cwd or None, capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    email = p.stdout.strip() if p.returncode == 0 else ""
    if not email or email.lower().endswith("anthropic.com"):
        return None
    return email


def identity_fix(cwd=None):
    """The command that gives this repo the agent's commit identity."""
    email = git_email(cwd) or "<your own git email>"
    return "git config user.name \"%s\" && git config user.email \"%s\"" % (agent_name() or "<agent_name>", email)


def fill(text):
    """Swap the tokens in static message text for the settings' values: @PREFIX@ (the agent branch prefix), @NAME@, @COMMIT_CREDIT@ and @PR_CREDIT@."""
    return (text.replace("@PREFIX@", agent_prefix() or "<agent_name>/").replace("@NAME@", agent_name() or "<agent_name>")
            .replace("@COMMIT_CREDIT@", commit_credit()).replace("@PR_CREDIT@", pr_credit()))


def validate(name, value):
    """None when fine, else the reason the value is refused."""
    if name == "agent_name":
        if not NAME_RE.match(value):
            return ("an agent name must start with a letter or digit and hold only letters, digits, '.', '_' and '-' "
                    "(it becomes the branch prefix and the commit author name)")
    elif name == "extra_owned_prefixes":
        for p in [x.strip() for x in value.split(",") if x.strip()]:
            if re.search(r"\s", p):
                return "the prefix %r holds whitespace" % p
    return None


def set_value(name, value):
    """Save one setting to the settings file. Returns the path written."""
    if name not in SETTING_NAMES:
        raise KeyError(name)
    value = value.strip()
    bad = validate(name, value)
    if bad:
        raise ValueError(bad)
    path = settings_path()
    values, problem = read_file()
    if problem:
        raise ValueError(problem + "; fix or delete that file first")
    values[name] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path


# --- the gate ------------------------------------------------------------------------------------------------

_SHELL_META_RE = re.compile(r"[;&|<>()\n\r]")
_PY = r"(?:python3?|py(?:\s+-3)?|\"?[^\s\"']*python3?(?:\.exe)?\"?)"


def is_settings_command(command):
    """True only for a lone `python <...>/settings.py set|get|show ...`: no chaining, no redirects, no substitution.

    `$` and backticks are refused anywhere (they expand inside double quotes); the other shell characters are
    allowed only inside quotes, where they are plain text (a prefix list such as "AjsAgent/,claude/")."""
    if not isinstance(command, str):
        return False
    c = command.strip()
    if "$" in c or "`" in c or _SHELL_META_RE.search(re.sub(r"\"[^\"]*\"|'[^']*'", "", c)):
        return False
    m = re.match(r"^" + _PY + r"\s+(\"[^\"]*\"|'[^']*'|\S+)\s+(set|get|show)(?:\s|$)", c)
    if not m:
        return False
    script = m.group(1).strip("\"'").replace("\\", "/")
    ours = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), SETTINGS_SCRIPT))
    return os.path.realpath(os.path.expanduser(script)) == ours  # this plugin's script, not any file called settings.py


def refusal(payload):
    """None when the call may go ahead, else the refusal text. `payload` is the parsed hook payload (a dict)."""
    gone = missing()
    _values, problem = read_file()
    if not gone and not problem:
        return None
    tool = str(payload.get("tool_name") or "") if isinstance(payload, dict) else ""
    ti = payload.get("tool_input") if isinstance(payload, dict) and isinstance(payload.get("tool_input"), dict) else {}
    if tool in ("Bash", "PowerShell") and is_settings_command(ti.get("command")):
        return None
    lines = ["House rules, settings not set: every tool is refused until each setting has a value, except the "
             "settings script itself. Nothing runs on an assumed default."]
    if problem:
        lines.append("Problem: " + problem + ".")
    for n in gone:
        lines.append("Missing `%s` (or set %s in the environment). Set it with: %s" % (n, ENV_VARS[n], settings_command(n)))
    lines.append("Ask the user for the values in the chat first; do not invent them.")
    return "\n".join(lines)


# --- the session-start note ----------------------------------------------------------------------------------

def _gh_login():
    """(login, source) from `gh api user`, else the git remote's owner, else (None, why)."""
    try:
        p = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True, timeout=10)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip(), "`gh api user`"
        why = "gh exited %d" % p.returncode
    except Exception as exc:
        why = "gh not usable (%s)" % type(exc).__name__
    try:
        p = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=5)
        m = re.search(r"github\.com[:/]([^/\s]+)/", p.stdout) if p.returncode == 0 else None
        if m:
            return m.group(1), "the git remote's owner (%s)" % why
    except Exception as exc:
        why += "; git remote not usable (%s)" % type(exc).__name__
    return None, why


def suggestion():
    """(suggested agent name, source text) or (None, why)."""
    login, source = _gh_login()
    if not login:
        return None, source
    return login.lower() + NAME_SUFFIX, source


def session_note():
    """The session-start note asking the model to ask the user for each unset setting. "" when all are set."""
    gone = missing()
    if not gone:
        return ""
    out = ["House rules settings are not set (%s). Until they are, every tool is refused except the settings "
           "script. Ask the user in the chat for each value, then save it. Nothing runs on an assumed default." %
           ", ".join(gone)]
    if "agent_name" in gone:
        name, source = suggestion()
        if name:
            out.append("agent_name: suggest `%s` (GitHub login lowercased plus \"%s\", from %s). Use it only once the "
                       "user confirms it. Save with: %s" % (name, NAME_SUFFIX, source, settings_command("agent_name")))
        else:
            out.append("agent_name: no GitHub login could be found (%s), so ask the user for a name. Save with: %s"
                       % (source, settings_command("agent_name")))
    if "extra_owned_prefixes" in gone:
        out.append("extra_owned_prefixes: ask which other branch prefixes count as the agent's own (for example "
                   "`AjsAgent/,claude/`), or \"none\". Save with: %s (use \"\" for none)"
                   % settings_command("extra_owned_prefixes"))
    return "\n\n---\n\n" + "\n".join(out)
