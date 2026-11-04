#!/usr/bin/env python3
"""checks/common.py - the test setup the rule-enforcement checks share (#440).

Not run on its own: checks/rule_enforcement.py starts with `from common import *`. Same shape as
house-rules' scripts/checks/common.py, cut down to what these four handlers need: `report` and the
counters, the paths, `run_hook`, `env_in`, `_additional_context`.

STDLIB ONLY, like hook.py.
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile

# Each run gets its own temp folder, as in house-rules' suite, so nothing leaks between runs.
PART = os.path.splitext(os.path.basename(sys.argv[0]))[0] or "part"
_RUN_TMP = tempfile.mkdtemp(prefix="rule-enforcement-verify-%s-" % PART)
os.environ["TMPDIR"] = _RUN_TMP
tempfile.tempdir = _RUN_TMP
atexit.register(shutil.rmtree, _RUN_TMP, True)

# checks/ sits one level below scripts/, which holds hook.py, run.sh and the rule_enforcement package.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
HOOK = os.path.join(HERE, "hook.py")
CORE = os.path.join(HERE, "rule_enforcement", "core.py")
RUN = os.path.join(HERE, "run.sh")
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RULES_FILE = os.path.join(PLUGIN, "rules", "house-rules.md")
DETAIL_DIR = os.path.join(PLUGIN, "rules", "detail")
HOOKS_JSON = os.path.join(PLUGIN, "hooks", "hooks.json")
PLUGIN_JSON = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
SH = shutil.which("sh") or "sh"

STEP = 0
FAILURES = 0
SKIPPED = []


def report(result, title):
    global STEP, FAILURES
    STEP += 1
    if result == "FAIL":
        FAILURES += 1
    elif result == "SKIP":
        SKIPPED.append(title)
    print(f"{STEP:2d}. {result}  {title}")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_hook(event, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [sys.executable, HOOK, event],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=e,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def run_shell(args, payload="", env=None):
    e = dict(os.environ) if env is None else env
    proc = subprocess.run(
        [SH] + args,
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=e,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def env_in(project_dir, **extra):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = project_dir
    e.update(extra)
    return e


def _additional_context(event, payload="", env=None):
    code, out, err = run_hook(event, payload, env=env)
    try:
        parsed = json.loads(out)
        return code, parsed["hookSpecificOutput"]["additionalContext"], err
    except Exception as exc:
        return code, None, f"{err}\ncould not parse {event} output as JSON: {exc}"


def finish():
    """Print this part's verdict and exit, with the RESULT lines house-rules' suite prints."""
    print()
    print("-" * 32)
    if FAILURES == 0 and not SKIPPED:
        print(f"RESULT: PASS - all {STEP} checks passed. The hooks are behaving as written.")
    elif FAILURES == 0:
        print(f"RESULT: PASS - {STEP - len(SKIPPED)} of {STEP} checks passed, {len(SKIPPED)} skipped.")
        for t in SKIPPED:
            print(f"          - {t}")
    else:
        print(f"RESULT: FAIL - {FAILURES} of {STEP} checks failed. See the FAIL lines above.")
    print()
    sys.exit(0 if FAILURES == 0 else 1)


__all__ = [_n for _n in dir() if not _n.startswith("__")]
