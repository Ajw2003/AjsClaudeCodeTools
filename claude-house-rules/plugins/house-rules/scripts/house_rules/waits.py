"""house_rules.waits - the wait clock numbers (#560): reads rules/waits.json, environment variables override.

STDLIB ONLY and no hook runtime, so a script like waitfor.py can import it. Every problem (file missing or
unreadable, a value that is not a positive number) is written to stderr in words and the built-in default is used.
"""

import json
import os
import sys

DEFAULTS = {"first_check_seconds": 60, "interval_seconds": 60, "stalled_after_quiet_checks": 3,
            "foreground_limit_seconds": 60,
            "deadline_seconds": {"command": 60, "agent": 60, "build": 60, "ci": 60},
            "long_runners": ["unity", "dotnet build", "dotnet test", "msbuild", "gradle", "docker build", "npm run build",
                             "npm test", "pytest", "verify.py", "cargo build"]}
_ENV = {"first_check_seconds": "HOUSE_RULES_WAIT_FIRST_CHECK", "interval_seconds": "HOUSE_RULES_WAIT_INTERVAL",
        "stalled_after_quiet_checks": "HOUSE_RULES_WAIT_STALLED_AFTER",
        "foreground_limit_seconds": "HOUSE_RULES_WAIT_FOREGROUND_LIMIT"}
_ENV_DEADLINE = {k: "HOUSE_RULES_WAIT_DEADLINE_" + k.upper() for k in DEFAULTS["deadline_seconds"]}
# HOUSE_RULES_WAITS_FILE points at another settings file (the verify cases use it).
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rules", "waits.json")


def _note(msg):
    sys.stderr.write("house-rules waits: %s\n" % msg)


def _number(value, name, default, source):
    try:
        num = float(value)
        if num > 0 and num != float("inf"):  # NaN fails num > 0
            return int(num) if num == int(num) else num
    except (TypeError, ValueError):
        pass
    _note("%s in %s is %r, not a positive number; using the built-in %s." % (name, source, value, default))
    return default


def _pick(env_name, data, key, default, path):
    env = os.environ.get(env_name)
    if env is not None:
        return _number(env, env_name, default, "the environment")
    return _number(data[key], key, default, path) if key in data else default


def load_waits():
    """The settings as a dict shaped like DEFAULTS."""
    path = os.environ.get("HOUSE_RULES_WAITS_FILE") or FILE
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("the top level is not an object")
    except (OSError, ValueError) as exc:
        data = {}
        _note("the settings file %s could not be read (%s: %s); using the built-in numbers."
              % (path, type(exc).__name__, str(exc)[:120]))
    out = {k: _pick(_ENV[k], data, k, d, path) for k, d in DEFAULTS.items() if k not in ("deadline_seconds", "long_runners")}
    dl = data.get("deadline_seconds") if isinstance(data.get("deadline_seconds"), dict) else {}
    out["deadline_seconds"] = {k: _pick(_ENV_DEADLINE[k], dl, k, d, path)
                               for k, d in DEFAULTS["deadline_seconds"].items()}
    lr = data.get("long_runners")
    out["long_runners"] = [x for x in lr if isinstance(x, str) and x] if isinstance(lr, list) else DEFAULTS["long_runners"]
    return out
