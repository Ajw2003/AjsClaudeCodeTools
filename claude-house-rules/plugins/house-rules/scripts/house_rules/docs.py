"""house_rules.docs - the docs part (#358, step 2b of #340): docstiers, the staged-docs check
(_staged_docs_status) and harvest. Moved verbatim from hook.py; docs/4-systems/plugin-restructure.md,
"Step 2b", says what moved and why.

Imports only from house_rules.core. guard (the safe git part) reaches the staged-docs check through the
core's DOCS_STATUS_HOOKS list, which this file registers on.
"""

import json
import os
import re
import sys
import time

from house_rules import core
from house_rules.core import *  # noqa: F401,F403
from house_rules.core import (  # noqa: F401
    _COMMAND_VALUE_RE,
    _GIT,
    _GIT_COMMIT_RE,
    _STATEMENT_SPLIT_RE,
    _TOGGLE_OFF,
    _field,
    _git_dir,
    _parse_status_porcelain,
    _read_text,
    _time,
)


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


# git diff --cached is the ONE deliberate, narrowly-scoped exception to "no subprocess in
# guard" - branch_ownership() stays subprocess-free. doc-ref 8713 docs/6-decisions/Decisions.md.
DOCS_CHECK_TIMEOUT = 2.0


# `git add` split off the same way a compound command is read for other purposes - on &&, ||,
# ; and newlines - so "git add f.py && git commit -m x" is seen as two statements, not one
# unmatched blob. Reuses _GIT (git plus any run of global options) the same way _GIT_COMMIT_RE
# does; "is this an add" and "is this a commit" are two independent questions on two possibly
# different statements of the same command.
_GIT_ADD_RE = re.compile(_GIT + r"add([^0-9A-Za-z-]|$)", re.IGNORECASE)


# -a/--all/-am/-ma on the COMMIT statement: git stages every tracked, modified/deleted file at
# commit time, before the commit itself runs - doc-ref c79f docs/6-decisions/Decisions.md.
_COMMIT_ALL_RE = re.compile(r"(^|\s)(-a\b|--all\b|-am\b|-ma\b)", re.IGNORECASE)
_ADD_ALL_RE = re.compile(r"(^|\s)(-A\b|--all\b)|(^|\s)\.(\s|$)", re.IGNORECASE)
_ADD_UPDATE_RE = re.compile(r"(^|\s)(-u\b|--update\b)", re.IGNORECASE)


def _staged_docs_status(subject, elsewhere, root=None):
    """('needs-docs'|'clear'|'unknown', detail) for what this commit will ACTUALLY include -
    not just what is staged right now, since guard runs before the command it is judging.

    'unknown' on anything that could make guard's own decision unreliable: a command naming
    another repo (elsewhere), no working git, the shared time budget running out, undecodable
    output. The caller's existing decision is never changed by this - only the message it
    shows may gain a line. doc-ref c79f docs/6-decisions/Decisions.md.
    """
    if elsewhere:
        return "unknown", "the command names another repo (-C/--git-dir/--work-tree) or changes directory"
    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

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


core.register_docs_status(_staged_docs_status)
