"""house_rules.safe_git - the safe git part (#358, step 2b of #340): the destructive and branch guard,
guardwrite, branchnudge, prompttimer, the credit (attribution) check and creditcheck, the GitHub-tool
guard, the commit-obligation helpers and the session-start agent branch and identity notes. Moved
verbatim from hook.py; docs/4-systems/plugin-restructure.md, "Step 2b", says what moved and why.

Imports only from house_rules.core. Where guard needs code that belongs to another part (the
issue workflow's author and issue guards, the docs check, the GitHub tool's issue checks) it loops
over a core link list that part registers on; none of them is imported here.
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
    _GH_PREFIX,
    _GIT,
    _GIT_COMMIT_RE,
    _PROMPT_VALUE_RE,
    _PR_BODY_FILE_RE,
    _STATEMENT_SPLIT_RE,
    _TOGGLE_OFF,
    _TRANSCRIPT_RE,
    _ag,
    _apply_assigns,
    _attribution_enabled,
    _branch_advice,
    _command_dir,
    _commit_check_enabled,
    _common_git_dir,
    _decoded_command,
    _dirty_paths,
    _extract_file_path,
    _field,
    _git_author_ident,
    _git_dir,
    _is_claude_identity,
    _is_relayed_prompt,
    _parse_status_porcelain,
    _payload_cwd,
    _read_and_clear_outdated_marker,
    _read_text,
    _time,
    _uncommitted_among,
    _vc_session_id,
    _waiting_load,
    _waiting_path,
    _waiting_update,
    _written_since_last_user_message,
)


# ---------------------------------------------------------------------------------------
# guard — PreToolUse on Bash / PowerShell. Fails closed and loud.
# ---------------------------------------------------------------------------------------

# The 14 guard patterns, ported character-for-character from guard.sh's grep -E regexes to
# Python re syntax. [[:alnum:]] -> [0-9A-Za-z] (never \w — the patterns list "_" separately).
# The subject is the JSON-encoded command, so a new line or tab before a word reads as the two
# characters \n or \t; _LINE_START accepts those as a word start, or `ls` + newline + `rm` slips by (#200).
_LINE_START = r"\\[nrt]|"

# #292: the background-work patterns (hidden windows, Start-Process, background jobs, nohup/setsid/
# disown, a trailing &, a wait piped through tail/head) and the process-kill pattern were removed:
# none of them changes a branch or deletes saved work, so none of them stops the agent any more.




# Marks a git write that runs unasked on any branch except the repo's default branch, and is
# refused outright on the default branch: that branch only changes through a pull request (#197).
BRANCH_WRITE = "branch-write"
# Marks a destructive pattern that runs unasked only off the default branch AND when everything
# it could lose is already saved elsewhere: a clean tree and every commit on a remote (#153).
SAVED = "saved-work-exempt"

GUARD_R3 = [
    # Force-pushing rewrites history that was already backed up, and --all/--mirror push (or
    # delete) every branch, the default one included, so they ask on every branch.
    (
        _GIT + r"push\b.*(--force|--force-with-lease|--mirror|--all|(^|\s)-f([^0-9A-Za-z-]|$))",
        "rewrites remote history or pushes every branch (force push, --all, --mirror)",
    ),
    (
        _GIT + r"push\b.*(--delete|(^|\s)-d(\s|$)|\s:[^\s:]+)",
        "deletes a branch on the remote (push --delete)",
    ),
    (
        _GIT + r"push([^0-9A-Za-z-]|$)",
        "reaches a remote (push)",
        BRANCH_WRITE,
    ),
    (
        _GIT + r"commit([^0-9A-Za-z-]|$)",
        "writes history (commit)",
        BRANCH_WRITE,
    ),
    # These add or replay commits; the old ones stay in the reflog and on the remote, so off the
    # default branch nothing is lost (#197).
    (
        _GIT + r"(merge|cherry-pick|revert|rebase|am|apply)([^0-9A-Za-z-]|$)",
        "adds or replays commits (merge / cherry-pick / revert / rebase / am / apply)",
        BRANCH_WRITE,
    ),
    # reset only loses work that is not saved elsewhere, so off the default branch with a clean
    # tree and every commit pushed it runs unasked (SAVED, #153).
    (
        _GIT + r"reset([^0-9A-Za-z-]|$)",
        "discards work (reset)",
        SAVED,
    ),
    # clean can remove ignored files that exist nowhere else; filter-branch rewrites every commit.
    (
        _GIT + r"(clean|filter-branch)([^0-9A-Za-z-]|$)",
        "deletes untracked files or rewrites all history (clean / filter-branch)",
    ),
    (
        _GIT + r"branch\s+(.*\s)?((?-i:-D)|--delete\s+--force|--force\s+--delete)(\s|$)",
        "deletes a local branch even if its work is not merged (branch -D)",
    ),
]

GUARD_R4 = [
    (
        # Was -r/-f only, so a plain `rm styles.css` - no recursive or force flag needed to
        # delete a single existing file - slipped through unasked. Deleting one file this way is
        # exactly the mechanism behind the CSS-file regression this rule now also has to catch.
        r"(^|" + _LINE_START + r"[^0-9A-Za-z_./-])rm\s+\S",
        "deletes one or more files",
    ),
    (r"Remove-Item", "deletes files (Remove-Item)"),
    (r"(del|erase)\s+/[fqs]|rmdir\s+/s", "deletes files (del /f or rmdir /s)"),
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
    ("Commit constantly on my own branches, never on theirs", GUARD_R3),
    ("Never take a destructive action without checking first", GUARD_R4),
]

# #291: a destructive action is refused outright, and the refusal names the safe way to do the job.
# aj is asked only when the command's description cites a source proving no safe way exists.
_DELETE_REASONS = ("deletes one or more files", "deletes files (Remove-Item)", "deletes files (del /f or rmdir /s)")
SAFE_WAYS = {
    "rewrites remote history or pushes every branch (force push, --all, --mirror)":
        "push a new branch instead: `git push -u origin @PREFIX@<topic>`",
    "deletes a branch on the remote (push --delete)": "leave the branch for aj to delete",
    "deletes a local branch even if its work is not merged (branch -D)": "leave the branch for aj to delete",
    "discards work (reset)": "commit the work on a new branch first (`git switch -c @PREFIX@<topic>`, then commit)",
    "deletes untracked files or rewrites all history (clean / filter-branch)":
        "for clean, move the files into a `_to_delete/` folder; for filter-branch, rewrite on a copy branch "
        "(`git branch <name>-copy`)",
    "truncates or overwrites file contents in place": "write a new file beside it",
    "throws away uncommitted edits to a file (git checkout -- / git restore)":
        "commit the work on a new branch first (`git switch -c @PREFIX@<topic>`, then commit)",
    "deletes stashed work permanently (git stash drop / clear)": "keep the stash",
    "recursive": "move the folder into a `_to_delete/` folder instead",
    "unsaved": "move the file into a `_to_delete/` folder instead",
    "not mine": "make a new branch and commit there: `git switch -c @PREFIX@<topic>`",
}
_NO_SAFE_WAY_RE = re.compile(r"\bno safe way:\s*(\S.*)", re.IGNORECASE)
GUARD_REFUSAL = (
    "House rules: refused, because this could destroy data with no way back, or change work that may not "
    "be yours:\n%s\nDo it the safe way named above. If no safe way exists, put `no safe way: <source>` in the "
    "command's description, citing the source that proves it (for example the git manual page), and aj "
    "will be asked instead."
)



DOCS_COMMIT_REMINDER = (
    "House rules, documentation goes in tiers: this commit stages a source file with nothing "
    "staged under docs/. Before committing, update the tier that changed - usually "
    "docs/3-state/ProjectState.md, for what's built and where it stands - or say in the commit "
    "message why none needed updating."
)




# A command that names its own repo, git dir or work tree is not talking about the checkout
# this hook can see, so the branch read below would be the wrong branch to judge it by. Broad
# on purpose — `grep -C 3` in the same command line costs an extra keypress, and that is the
# direction guard is allowed to be wrong in.
_OTHER_REPO_RE = re.compile(r"(^|\s)(--git-dir|--work-tree)")


PROTECTED_BRANCHES = ("main", "master")


def default_branch(start):
    """The repo's default branch as origin/HEAD names it (a file read, no git process), or None."""
    try:
        cd = _common_git_dir(start)
        if not cd:
            return None
        head = _read_text(os.path.join(cd, "refs", "remotes", "origin", "HEAD")).strip()
    except Exception: return None  # no origin/HEAD recorded: main and master are still protected
    prefix = "ref: refs/remotes/origin/"
    return head[len(prefix):] if head.startswith(prefix) else None


def is_protected_branch(branch, start):
    """Is `branch` the one that only changes through a pull request (#197)?"""
    return branch in PROTECTED_BRANCHES or branch == default_branch(start)






def branch_ownership(start=None):
    """Whose branch is this checkout on? Returns (is_mine, branch_name, note).
    `start` is where the command runs (payload cwd); None keeps CLAUDE_PROJECT_DIR / getcwd.

    Mechanism and invariants: doc-ref ee0f docs/4-systems/hook-engine.md (Invariants) and
    doc-ref d2a4 docs/4-systems/hook-engine.md (Traps).
    """
    try:
        git_dir = _git_dir(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
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
    return branch.startswith(owned_branch_prefixes()), branch, None








def _agent_branch_enabled():
    return os.environ.get("HOUSE_RULES_AGENT_BRANCH", "on").strip().lower() not in _TOGGLE_OFF


def _agent_branch_block():
    """Cloud session on the app's claude/<name> branch: tell the agent to move to <agent prefix><name>.

    Text only - the hook never runs git switch. Never raises; an unreadable branch says so.
    """
    if not _agent_branch_enabled():
        return ""
    try:
        import subprocess
        _mine, branch, note = branch_ownership()
        if branch is None:
            return "\n\n---\n\nAgent branch check: branch not read (%s)." % note
        if not branch.startswith("claude/"):
            return ""
        name = branch[len("claude/") :]
        prefix = settings.agent_prefix()
        if not prefix:
            return "\n\n---\n\nAgent branch check: agent_name is not set, so the agent branch could not be named."
        target = prefix + name
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
        return "\n\n---\n\nAgent branch check: branch not read (%s)." % exc


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
        return "\n\n---\n\nGit identity is Claude: before your first commit run `%s`." % agent_identity_fix(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    except Exception: return ""  # unreadable identity adds no text, by design (#177)



# tier 3: pull out just "command":"..." — the first one. Allows backslash-escaped quotes.
_COMMAND_FIELD_RE = re.compile(r'"command"\s*:\s*"(?:[^"\\]|\\.)*"')


def _guard_subject(payload):
    m = _COMMAND_FIELD_RE.search(payload)
    return m.group(0) if m else payload






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


PROTECTED_DENY = (
    "House rules: `%s` is the default branch, and it only changes through a pull request - never "
    "a direct commit, push or merge (refused: %s). Do this on a branch instead: `git switch -c "
    "@PREFIX@<topic>`, commit and push there, then open a pull request. Do not retry it on the "
    "default branch."
)
_GIT_PUSH_RE = re.compile(_GIT + r"push([^0-9A-Za-z-]|$)", re.IGNORECASE)


def _push_targets_protected(subject, where):
    """The protected branch a push names as its destination (`git push origin main`,
    `HEAD:main`), or None."""
    names = set(PROTECTED_BRANCHES)
    d = default_branch(where)
    if d:
        names.add(d)
    for stmt in _STATEMENT_SPLIT_RE.split(_decoded_command(subject)):
        m = _GIT_PUSH_RE.search(stmt)
        if not m:
            continue
        for tok in stmt[m.end():].split():
            ref = tok.strip("\"'").lstrip("+").split(":")[-1]
            ref = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
            if ref in names:
                return ref
    return None


_ONLY_GIT_STMT_RE = re.compile(r"^\s*(git\s|cd\s)")


def _only_git_statements(subject):
    """True when every statement of the command (pipes split too) is a git or cd statement."""
    stmts = [x for x in re.split(r"&&|\|\||;|\n|\|", _decoded_command(subject)) if x.strip()]
    return bool(stmts) and all(_ONLY_GIT_STMT_RE.match(x) for x in stmts)


_NB_GIT_RE = re.compile(r"^\s*(cd\s+\S+\s*&&\s*)?" + _GIT + r"(commit|push)\b")
_NB_BAD_RE = re.compile(r"(--force|--mirror|--all|--delete|--prune|(^|\s)-[A-Za-z]*[fd]\b|(^|\s):\S|(^|\s)\+\S)")


def _never_blocked_git(subject, branch, where):
    """Never-blocked list, case a: a routine git commit/push on the agent's own branch (an owned
    prefix or a helper's worktree branch). Force, --all/--mirror, --delete and the default branch
    are not routine, so they fall through to the normal guard. The design loop is not consulted here."""
    if not branch or is_protected_branch(branch, where):
        return False
    if not branch.startswith(owned_branch_prefixes() + (AUTOSAVE_BRANCH_PREFIX,)):
        return False
    if not _only_git_statements(subject):
        return False
    stmts = [x for x in re.split(r"&&|\|\||;|\n", _decoded_command(subject)) if x.strip()]
    for x in stmts:
        if re.match(r"\s*cd\s", x):
            continue
        if not _NB_GIT_RE.match(x):
            return False
        if re.search(r"push\b", x) and _NB_BAD_RE.search(x.split("push", 1)[1]):
            return False
    return True


def _never_blocked_own_file(file_path):
    """Case c: a file the agent made itself. shortcut: no creation record exists in the hook, so
    "untracked by git and inside the project root" stands in for it; upgrade by recording creates."""
    try:
        path = os.path.abspath(_guardwrite_resolve(file_path))
        root = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        if os.path.commonpath([path, root]) != root:
            return False
        rc, _o, _e = _ag(os.path.dirname(path), ["ls-files", "--error-unmatch", path], check=False)
        return rc != 0 and os.path.isfile(path)
    except (OSError, ValueError) as exc:
        sys.stderr.write("house-rules guardwrite: could not tell whether %s is untracked (%s); the normal check applies.\n" % (file_path, exc))
        return False


def _docs_status(subject, elsewhere, root):
    """The docs part's answer for this commit, through the core link; 'unknown' when it is not loaded."""
    if not core.DOCS_STATUS_HOOKS:
        return "unknown", "the docs part is not loaded"
    return core.DOCS_STATUS_HOOKS[0](subject, elsewhere, root)


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

    # #341: while a setting is unset, only the settings script runs. First, before any other check.
    unset = settings_refusal(payload)
    if unset:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": unset}})
        return 0

    if not payload:
        trace("guard: empty payload - nothing was checked for this call.")
        return 0

    subject = _guard_subject(payload)
    outdated = _read_and_clear_outdated_marker(_vc_session_id(payload))

    # Issue workflow: gh pr create must say Refs, gh issue close always asks. A deny ends here;
    # an ask is folded into the prompt built below so a compound command is asked about once.
    issue_hit = _attribution_guard(subject, payload)
    for _issue_guard in core.GUARD_ISSUE_HOOKS:  # _author_guard, _issues_guard: registered by hook.py
        issue_hit = issue_hit or _issue_guard(subject, payload)
    if issue_hit and issue_hit[0] == "deny":
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": issue_hit[1]}})
        return 0

    allow_ctx = None  # #363: an allowed close carries its follow-up instruction
    if issue_hit and issue_hit[0] == "allow":
        allow_ctx, issue_hit = issue_hit[2], None

    where, moved_unclear = _command_dir(payload)
    _mine, branch, ownership_note = branch_ownership(where)
    # --git-dir / --work-tree, or a cd / -C that could not be followed, acts on a repo other than
    # the one we just read the branch from, so the branch cannot justify anything.
    elsewhere = bool(_OTHER_REPO_RE.search(subject)) or moved_unclear
    known = branch is not None and not elsewhere
    protected = known and is_protected_branch(branch, where)
    # A push naming the default branch as its destination writes to it from any branch.
    if known and not protected:
        target = _push_targets_protected(subject, where)
        if target:
            protected, branch = True, target

    hits = {title: [] for title, _ in GUARD_BUCKETS}
    exempted = []
    plain_hits = []  # branch writes asked only because the folder is unclear (#261)
    refused = []  # branch writes aimed at the default branch: refused, never asked (#197)
    not_mine = []  # branch writes on a branch the guard can't confirm is the agent's: refused (#291)
    delete_kind = None  # "recursive" or "unsaved" once a delete pattern matched (#291)
    saved_state = None  # (saved, note), computed at most once and only when a SAVED pattern matched
    saved_blocked = None
    for title, patterns in GUARD_BUCKETS:
        for entry in patterns:
            pattern, reason = entry[0], entry[1]
            if not re.search(pattern, subject, re.IGNORECASE):
                continue
            marker = entry[2] if len(entry) > 2 else None
            if reason == "deletes one or more files" and _rm_only_in_scratchpad(subject, payload):
                continue  # #261: every rm path is inside this session's scratchpad
            if reason in _DELETE_REASONS:
                delete_kind = delete_kind or _delete_refusal(subject, where)
                if not delete_kind:
                    exempted.append(reason)  # committed and unchanged, so git can bring it back (#291)
                    continue
            if marker == BRANCH_WRITE and known:
                if protected:
                    refused.append(reason)
                elif branch.startswith(owned_branch_prefixes() + (AUTOSAVE_BRANCH_PREFIX,)):
                    exempted.append(reason)
                else:
                    not_mine.append(reason)
                continue
            if marker == BRANCH_WRITE:
                plain_hits.append(reason)
            if marker == SAVED and known and not protected:
                if saved_state is None:
                    saved_state = work_saved_elsewhere(where)
                if saved_state[0]:
                    exempted.append(reason)
                    continue
                saved_blocked = saved_state[1]
            hits[title].append(reason)

    if refused:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": settings.fill(PROTECTED_DENY % (branch, "; ".join(refused)))}})
        return 0

    # #291: destructive actions are refused with the safe way named, unless the command cites a source
    # proving no safe way exists; then aj is asked below, with the citation shown.
    cited = _cites_no_safe_way(payload)
    danger = []
    for r in (x for rs in hits.values() for x in rs):
        if r in plain_hits and elsewhere:
            safe = ("run it as plain `git ...` from %s, with no cd, -C or variables, and it will be checked "
                    "normally" % _payload_toplevel(payload))
        elif r in plain_hits:
            safe = SAFE_WAYS["not mine"]
        elif r in _DELETE_REASONS:
            safe = SAFE_WAYS[delete_kind or "unsaved"]
        else:
            safe = SAFE_WAYS.get(r, "do the job without this step")
        danger.append("  - %s: %s" % (r, settings.fill(safe)))
    danger += ["  - %s on `%s`, which the guard can't confirm is mine: %s" % (r, branch, settings.fill(SAFE_WAYS["not mine"]))
               for r in not_mine]
    if danger and not cited:
        if elsewhere:
            danger.append("  (This command names another repo, with --git-dir or a cd / -C I could not follow, so "
                          "the branch I can see is not the one it acts on.)")
        elif ownership_note and (plain_hits or not_mine):
            danger.append("  (I could not read which branch this is on: %s.)" % ownership_note)
        elif protected:
            danger.append("  (`%s` is the default branch, which only changes through a pull request.)" % branch)
        if saved_blocked:
            danger.append("  (On `%s`, this runs unasked only when the work is saved elsewhere: %s.)"
                          % (branch, saved_blocked))
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": GUARD_REFUSAL % "\n".join(danger)}})
        return 0
    for r in not_mine:
        hits["Commit constantly on my own branches, never on theirs"].append(r)

    is_commit = bool(_GIT_COMMIT_RE.search(subject))
    docs_status, docs_detail = _docs_status(subject, elsewhere, where) if is_commit else (None, None)

    if not any(hits.values()) and not outdated and not issue_hit:
        # The allow path. Silent, this is the plugin's least distinguishable "ran and decided
        # not to fire" from "never ran" - and it is the security-shaped backstop, so that is
        # the worst place to leave the ambiguity. Exactly one emit() call either way - two
        # would be two concatenated JSON objects on stdout, which is not valid hook output.
        if exempted:
            allow_trace = (
                "guard: checked %s - %s on `%s`, which is not the default branch%s."
                % (_trace_subject(subject), " and ".join(exempted), branch,
                   ", with nothing uncommitted and every commit on a remote"
                   if saved_state and saved_state[0] else "")
            )
        else:
            allow_trace = "guard: checked %s - no house rule matched." % _trace_subject(subject)

        # An exempted git write is approved outright so Claude Code's own prompt cannot stall it
        # either (#197) - only when every statement is git or cd, so the approval never carries an
        # unrelated command along. docs/plans/2026-10-09-stop-permission-stalls.md
        approve = bool(exempted) and _only_git_statements(subject)
        if docs_status == "needs-docs" or approve or allow_ctx:
            # PreToolUse's additionalContext reaches the model on an "allow" decision (probed
            # live, doc-ref 8713 docs/6-decisions/Decisions.md).
            out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
            if docs_status == "needs-docs":
                out["hookSpecificOutput"]["additionalContext"] = DOCS_COMMIT_REMINDER
            if allow_ctx:
                _ac = out["hookSpecificOutput"].get("additionalContext")
                out["hookSpecificOutput"]["additionalContext"] = (_ac + " " if _ac else "") + allow_ctx
            if docs_status == "unknown" and trace_enabled():
                out["systemMessage"] = "%s - docs check could not tell: %s." % (allow_trace, docs_detail)
            elif trace_verbose():
                out["systemMessage"] = allow_trace
            emit(out)
            return 0
        if docs_status == "unknown":
            trace("%s - docs check could not tell: %s." % (allow_trace, docs_detail))
        else:
            trace_noop(allow_trace)
        return 0

    if known and not issue_hit and not outdated and _never_blocked_git(subject, branch, where):
        # Never-blocked list: a routine commit/push on the agent's own branch is let through, silently.
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
        if docs_status == "needs-docs":
            out["hookSpecificOutput"]["additionalContext"] = DOCS_COMMIT_REMINDER
        emit(out)
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
                "  This command names another repo (--git-dir, or a cd / -C I could not follow), so "
                "the branch I can see is not the one it acts on."
            )
        elif ownership_note:
            why_not_exempt = "  I could not read which branch this is on: %s." % ownership_note
        elif protected:
            why_not_exempt = "  `%s` is the default branch, which only changes through a pull request." % branch
        if why_not_exempt:
            lines.append("")
            lines.append(why_not_exempt)

    if saved_blocked:
        lines.append("")
        lines.append(
            "  On `%s`, but this runs unasked only when the work is saved elsewhere: %s."
            % (branch, saved_blocked)
        )

    if cited and danger:
        lines.append("")
        lines.append("  No safe way exists, the agent says, citing: %s" % cited)

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
    rewrite = None
    all_hits = [r for rs in hits.values() for r in rs]
    if all_hits and not outdated and not issue_hit and docs_status != "needs-docs" and not saved_blocked:
        if elsewhere and not protected and all(r in plain_hits for r in all_hits):
            rewrite = ("Run it as plain `git ...` from %s, with no cd, -C or variables, and it will be "
                       "checked normally." % _payload_toplevel(payload))
    _ask_or_refuse(payload, reason_text, issue_hit[2] if issue_hit and issue_hit[2] else None, rewrite)
    return 0


def _payload_toplevel(payload):
    """The repo top-level of the payload cwd; the cwd itself when git cannot say (#261)."""
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    cwd = cwd if isinstance(cwd, str) and cwd else (os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        import subprocess
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True,
                           text=True, timeout=10)
        top = p.stdout.strip()
        if p.returncode == 0 and top:
            return top
    except Exception as exc:
        sys.stderr.write("house-rules guard: could not read the repo top-level (%s: %s); naming the "
                         "working folder instead.\n" % (type(exc).__name__, exc))
    return cwd


_DELETE_CMD_RE = re.compile(r"(^|[\s;&|(])(rm|Remove-Item|del|erase|rmdir)(\s|$)", re.IGNORECASE)
_RECURSIVE_DELETE_RE = re.compile(
    r"(^|[\s;&|(])rm\s+(?:\S+\s+)*?(-[A-Za-z]*[rR][A-Za-z]*|--recursive)(\s|$)"
    r"|rmdir\s+/s|Remove-Item\b.*-Recurse|(del|erase)\s+(?:\S+\s+)*?/s(\s|$)", re.IGNORECASE)


def _delete_refusal(subject, where):
    """#291: "recursive" for a recursive delete, "unsaved" when any target has uncommitted changes, was
    never committed, or can't be checked (a glob or variable), else None: every target is committed and
    unchanged, so git can bring it back."""
    import shlex
    text = _decoded_command(subject)
    if _RECURSIVE_DELETE_RE.search(text):
        return "recursive"
    base = where or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    for stmt in re.split(r"&&|\|\||;|\n|\|", text):
        m = _DELETE_CMD_RE.search(stmt)
        if not m:
            continue
        try:
            words = shlex.split(stmt[m.end(2):])
        except ValueError:
            return "unsaved"
        targets = [w for w in words if not w.startswith(("-", "/")) or os.path.isabs(w) and not re.match(r"^/[a-zA-Z]$", w)]
        if not targets:
            return "unsaved"
        for t in targets:
            if re.search(r"[*?\[\]$`~]", t):
                return "unsaved"
            path = t if os.path.isabs(t) else os.path.join(base, t)
            folder = os.path.dirname(os.path.abspath(path))
            try:
                tracked, _o, _e = _ag(folder, ["ls-files", "--error-unmatch", "--", path], check=False)
                changed, _o, _e = _ag(folder, ["diff", "--quiet", "HEAD", "--", path], check=False)
            except RuntimeError:
                return "unsaved"
            if tracked != 0 or changed != 0:
                return "unsaved"
    return None


def _cites_no_safe_way(payload):
    """The source the agent cites for "no safe way exists", from the command's description, or None."""
    try:
        data = json.loads(payload)
    except ValueError as exc:
        sys.stderr.write("house-rules guard: could not read the command's description (%s), so no "
                         "\"no safe way\" citation was found; the refusal stands.\n" % exc)
        return None
    ti = data.get("tool_input") if isinstance(data, dict) else None
    m = _NO_SAFE_WAY_RE.search(str(ti.get("description") or "")) if isinstance(ti, dict) else None
    return m.group(1).strip() if m else None


def _rm_only_in_scratchpad(subject, payload):
    """True when every `rm` in the command has only absolute path arguments inside this session's
    scratchpad (/tmp/claude-*/<project>/<session_id>/scratchpad), or - if that cannot be derived -
    under /tmp/claude- with the session_id as a path component. Globs/.. that could leave: False."""
    import shlex
    try:
        data = json.loads(payload)
    except ValueError:
        sys.stderr.write("house-rules guard: could not read the payload to check whether rm stays in the "
                         "scratchpad; asking as usual.\n")
        return False
    if not isinstance(data, dict) or not data.get("session_id"):
        return False
    sid = str(data["session_id"])
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    proj = re.sub(r"[^A-Za-z0-9]", "-", cwd) if cwd else None
    seen = False
    for stmt in re.split(r"&&|\|\||;|\n|\|", _apply_assigns(_decoded_command(subject))):
        try:
            words = shlex.split(stmt)
        except ValueError:
            sys.stderr.write("house-rules guard: could not split an rm statement (unbalanced quotes); "
                             "asking as usual.\n")
            return False
        if "rm" not in words:
            continue
        args = words[words.index("rm") + 1:]
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            return False
        for a in paths:
            if not a.startswith("/") or re.search(r"[$`~]", a) or ".." in a.split("/"):
                return False
            norm = os.path.normpath(a)
            parts = norm.split("/")
            ok = False
            if proj and re.match(r"^/tmp/claude-[^/]+/%s/%s/scratchpad(/|$)" % (re.escape(proj), re.escape(sid)), norm):
                ok = True
            elif norm.startswith("/tmp/claude-") and sid in parts:
                ok = True
            # a glob in the directory part before the session folder could escape it
            if not ok or re.search(r"[*?\[]", norm.split(sid)[0]):
                return False
        seen = True
    return seen


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

    if _never_blocked_own_file(file_path):
        trace_noop("guardwrite: never-blocked list - %s is a file made here, untracked." % file_path)
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

    # #293: refused outright with the fix named, instead of asking. A file I created myself already
    # went through above (never-blocked list, #289).
    lines = [
        "House rules, %s: refused. This Write replaces the ENTIRE existing contents of `%s`, a file "
        "I did not create." % (RULE_EDIT_IN_PLACE, file_path),
    ]
    if old_lines is not None and new_lines is not None:
        lines.append("%d existing line(s) would be discarded and replaced with %d new line(s)." % (old_lines, new_lines))
    lines.append(
        "Fix: edit it in place with the Edit tool, changing only the lines that need to change. A whole-file "
        "rewrite needs aj's approval by name first, with what it discards and why an in-place edit will not do."
    )
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": "\n".join(lines)}})
    return 0


# ---------------------------------------------------------------------------------------
# branchnudge - PostToolUse on Write|Edit. The commit rule's "branch off first", at the moment
# it applies: the first uncommitted change on a branch that is not one of the agent's own branches. Never obstructs.
# ---------------------------------------------------------------------------------------

BRANCH_NUDGE_NOTE = (
    "House rules, commit on your own branch: that write is the only uncommitted change on "
    "`{branch}`, which is not one of your own branches ({owned}). If that branch was opened for this session's "
    "work, carry on and commit there. If it is the user's, branch off now, before editing "
    "further (`git switch -c @PREFIX@<topic>` carries this change with it), and commit on that "
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
        is_mine, branch, note = branch_ownership(_payload_cwd(payload))
        if is_mine:
            trace_noop("branchnudge: on own branch %s - nothing to nudge." % branch)
            return 0
        if not branch:
            trace("branchnudge: no branch to judge (%s) - not checked." % note)
            return 0
        root = _payload_cwd(payload)
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
                        "additionalContext": settings.fill(BRANCH_NUDGE_NOTE.format(branch=branch, owned=", ".join(owned_branch_prefixes()))),
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


# prompttimer - PermissionRequest (issue #144, plan docs/plans/2026-10-04-permission-prompt-timeout.md).
# Runs beside the permission dialog. If nobody answers within HOUSE_RULES_PROMPT_TIMEOUT seconds
# (default 300) it refuses, so one unanswered prompt cannot hold a whole session overnight. It only
# ever refuses: an unanswered prompt is a no, and the only other outcome is saying nothing, which
# leaves the dialog in charge. The refusal goes into the waiting-on-you list, which issue #145 shows.
PROMPT_TIMEOUT_DEFAULT = 300.0
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
        if not m or _is_relayed_prompt(m.group(1), payload):
            return ""
        data = json.loads(payload)
        session_id = str(data.get("session_id") or "") if isinstance(data, dict) else ""
        path, _ = _waiting_path(session_id)
        if not os.path.isfile(path):
            return ""
        shown = []

        def fn(entries):
            mine = [e for e in entries if e.get("session_id") == session_id]
            timed = [e for e in mine if e.get("status") in ("timed-out", "refused")]
            if not mine:
                return None
            shown.extend(dict(e) for e in timed)
            out = []
            for e in entries:
                if e.get("session_id") == session_id:
                    if e.get("status") in ("waiting", "ran"):
                        continue
                    if e.get("status") in ("timed-out", "refused"):
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
    return settings.fill(
        "Nobody answered this permission prompt for %s, so it was refused - not approved - and "
        "added to the waiting-on-you list (%s). Refused action: %s. Do not retry this action, or a "
        "variation of it, this session; aj has not approved it. Look for a route that needs no permission AND does "
        "not have the same effect (for example: commit to one of your own branches (@PREFIX@) instead of aj's branch; "
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


def _asked_path(session_id):
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", session_id or "unknown")[:100]
    return os.path.join(tempfile.gettempdir(), "house-rules-asked-%s" % safe)


def _record_ask(session_id, key):
    """A guard raised this prompt: note its key so prompttimer times it (#290). Never raises."""
    try:
        with open(_asked_path(session_id), "a", encoding="utf-8") as f:
            f.write(key + "\n")
    except OSError as exc:
        sys.stderr.write("house-rules guard: could not record this prompt for the timer (%s); "
                         "it will get no timer.\n" % exc)


UNATTENDED_REFUSAL = (
    "\n\nRefused, not asked: %s, so a prompt would only sit unanswered. Do not retry this action, "
    "or reach the same result another way. Carry on with everything that does not depend on it, "
    "and list it under 'Waiting on you' before you stop."
)


def _ask_or_refuse(payload, reason_text, context=None, rewrite=None):
    """Emit the guard's ask - or, inside a subagent (the payload carries agent_id), a refusal
    (#198): a helper cannot answer a prompt. Refusals go on the waiting-on-you list.
    HOUSE_RULES_PROMPT_TIMEOUT=off turns the refusal off. An ask is recorded for prompttimer."""
    why = None
    secs, _ = _prompt_timeout_seconds()
    try:
        data = json.loads(payload)
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    session_id = str(data.get("session_id") or "")
    if secs is not None and data.get("agent_id"):
        why = "this runs inside a helper (subagent), which cannot answer a permission prompt"
    if not why:
        _record_ask(session_id, _waiting_key(str(data.get("tool_name") or "?"), data.get("tool_input")))
        out = {"hookEventName": "PreToolUse", "permissionDecision": "ask",
               "permissionDecisionReason": reason_text}
    elif rewrite:
        # #261: a routine command that only needs rewriting: say how, no "Do not retry", and it
        # is not a waiting-on-you item.
        out = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
               "permissionDecisionReason": reason_text + "\n\nRefused, not asked: %s, so a prompt would "
               "only sit unanswered. %s" % (why, rewrite)}
    else:
        tool, ti = str(data.get("tool_name") or "?"), data.get("tool_input")
        now = time.time()
        entry = {"session_id": session_id, "key": _waiting_key(tool, ti), "tool": tool,
                 "summary": _waiting_summary(tool, ti), "started": now, "status": "refused", "timed_out_at": now}
        try:
            path, _ = _waiting_path(session_id)
            _waiting_update(path, lambda es: [e for e in es if not (e.get("session_id") == session_id
                                                                     and e.get("key") == entry["key"])] + [entry], "guard")
        except Exception as exc:
            sys.stderr.write("house-rules guard: could not add the refused action to the waiting-on-you "
                             "list (%s: %s); it is still refused.\n" % (type(exc).__name__, exc))
        out = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
               "permissionDecisionReason": reason_text + UNATTENDED_REFUSAL % why}
    if context:
        out["additionalContext"] = context
    emit({"hookSpecificOutput": out})


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
    try:
        if isinstance(tool_input, dict):
            if tool_name in ("Edit", "Write") and isinstance(tool_input.get("file_path"), str) \
                    and _never_blocked_own_file(tool_input["file_path"]):
                return 0
            if tool_name == "Bash" and isinstance(tool_input.get("command"), str):
                _m, _b, _n = branch_ownership(None)
                if _never_blocked_git(tool_input["command"], _b, None):
                    return 0
    except Exception as exc:
        sys.stderr.write("house-rules prompttimer: never-blocked check failed (%s); timer applies.\n" % exc)
    key = _waiting_key(tool_name, tool_input)
    try:
        asked = key in _read_text(_asked_path(session_id)).split()
    except OSError:
        asked = False
    if not asked:
        sys.stderr.write("house-rules prompttimer: no house-rules guard raised this prompt (%s); no timer, "
                         "the dialog decides.\n" % tool_name)
        return 0
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
# End of the prompttimer block (verify.py slices the source between its first comment and this line).










# Credit goes to the agent (settings: agent_name), with no email and no Claude branding (issue #133). The Claude Code
# `attribution` setting is the primary mechanism and is written by tools/install.py; this check is
# the backstop for sessions that never read the settings file (cloud sessions).
_ATTRIBUTION_TEXT_RES = [
    re.compile(r"co-authored-by:[^\n]*(?:claude|anthropic)", re.IGNORECASE),
    re.compile(r"noreply@anthropic\.com", re.IGNORECASE),
    re.compile(r"generated with \[?claude", re.IGNORECASE),
    re.compile(r"claude\.com/claude-code", re.IGNORECASE),
    re.compile(r"claude-session\s*:", re.IGNORECASE),
    re.compile(r"claude\.ai/code/", re.IGNORECASE),
    re.compile(r"generated by[\[_* ]*claude code", re.IGNORECASE),
    re.compile(r"claude\.ai/code(?![\w/])", re.IGNORECASE),
]
_ATTRIBUTION_CMD_RE = re.compile(
    r"(?:" + _GIT + r"commit([^0-9A-Za-z-]|$))|(?:" + _GH_PREFIX + r"(?:pr|issue)\s+(?:create|edit|comment)\b)"
    r"|(?:" + _GH_PREFIX + r"api\b[^\n]*?repos/[\w.-]+/[\w.-]+/(?:pulls|issues)\b)"
    r"|(?:(?:^|[;&|(\n`]|\$\()\s*curl\b[^\n]*api\.github\.com)",
    re.IGNORECASE,
)
# #316: a `gh api` call writes when it has a method flag or any field/input flag; a plain GET does not.
_GH_API_WRITE_RE = re.compile(r"(?<![\w-])(?:-X\s*(?:POST|PATCH|PUT)|--method\b|-f\b|-F\b|--field\b|--raw-field\b|--input\b)", re.IGNORECASE)
_GH_API_FILE_RE = re.compile(r"(?:(?<![\w-])-F|--field)(?:=|\s+)body=@(\"[^\"]+\"|'[^']+'|\S+)|--input(?:=|\s+)(\"[^\"]+\"|'[^']+'|\S+)")
ATTRIBUTION_DENY = (
    "House rules, credit @NAME@: this %s credits Claude (`%s`). Credit \"@NAME@\" instead, "
    "with no email and no Claude branding: commits end with `@COMMIT_CREDIT@`, pull requests and issues "
    "with `@PR_CREDIT@`. HOUSE_RULES_ATTRIBUTION=off disables this check."
)


def _attribution_guard(subject, payload):
    """None when the command's text does not credit Claude, else ("deny", reason, None)."""
    if not _attribution_enabled():
        return None
    cmd = _decoded_command(subject)
    if not _ATTRIBUTION_CMD_RE.search(cmd):
        return None
    text = cmd
    if re.search(_GH_PREFIX + r"api\b", cmd, re.IGNORECASE):
        if not _GH_API_WRITE_RE.search(cmd):
            return None
        for am in _GH_API_FILE_RE.finditer(cmd):
            name = (am.group(1) or am.group(2)).strip("\"'")
            path = name if os.path.isabs(name) else os.path.join(_payload_cwd(payload), name)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = text + "\n" + f.read()
            except OSError:
                trace("attribution: could not read the gh api body file %s; its text was NOT checked for Claude credit." % name)
        fm = None
    else:
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
            return ("deny", settings.fill(ATTRIBUTION_DENY % (kind, m.group(0).strip()[:60])), None)
    return None


# #318: PostToolUse on Bash. GitHub itself can add a Claude credit after a send (cloud sessions), so
# after a pull request / issue / comment write the body is read back once and checked.
_CREDIT_COMMENT_API_RE = re.compile(r"repos/([\w.-]+/[\w.-]+)/issues/comments/(\d+)")
_CREDIT_ITEM_URL_RE = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/(?:pull|issues)/(\d+)(?:#issuecomment-(\d+))?")


def _read_back_body(path):
    """(body, problem): the body of a GitHub issue, pull request or comment via `gh api`. verify.py stubs this."""
    import subprocess
    try:
        r = subprocess.run(["gh", "api", path, "-q", ".body"], capture_output=True, timeout=10)
    except FileNotFoundError:
        return None, "gh is not installed"
    except subprocess.TimeoutExpired:
        return None, "gh timed out after 10 seconds"
    if r.returncode != 0:
        return None, "gh exited %d: %s" % (r.returncode, r.stderr.decode("utf-8", "replace").strip()[:100])
    return r.stdout.decode("utf-8", "replace"), None


def event_creditcheck():
    try:
        if not _attribution_enabled():
            return 0
        raw = read_payload()
        data = json.loads(raw) if raw else None
        ti = data.get("tool_input") if isinstance(data, dict) else None
        cmd = str(ti.get("command") or "") if isinstance(ti, dict) else ""
        if not cmd or _GIT_COMMIT_RE.search(cmd) or not _ATTRIBUTION_CMD_RE.search(cmd):
            return 0
        if re.search(_GH_PREFIX + r"api\b", cmd, re.IGNORECASE) and not _GH_API_WRITE_RE.search(cmd):
            return 0
        resp = data.get("tool_response")
        out = resp.get("stdout") if isinstance(resp, dict) else resp
        out = out if isinstance(out, str) else json.dumps(out)
        path = url = None
        m = _CREDIT_COMMENT_API_RE.search(out)
        if m:
            path, url = m.group(0), "https://github.com/" + m.group(1) + "/issues/comments/" + m.group(2)
        else:
            m = _CREDIT_ITEM_URL_RE.search(out)
            if m:
                url = m.group(0)
                path = ("repos/%s/issues/comments/%s" % (m.group(1), m.group(3)) if m.group(3)
                        else "repos/%s/issues/%s" % (m.group(1), m.group(2)))
        if not path:
            problem, what = "no pull request, issue or comment address in the command's output", "what was sent"
        else:
            body, problem = _read_back_body(path)
            what = url
        if problem:
            text = ("House rules, credit check: could not read back %s (%s), so whether GitHub added a Claude "
                    "credit is unknown; say so in your reply." % (what, problem))
        else:
            hit = next((m.group(0) for m in (rx.search(body) for rx in _ATTRIBUTION_TEXT_RES) if m), None)
            if hit:
                text = ("House rules, credit check: GitHub added a Claude credit to %s after it was sent (`%s`). "
                        "It can't be removed from a cloud session; say so in your reply instead of saying the "
                        "credit is clean." % (url, hit.strip()[:60]))
            else:
                text = "House rules, credit check: read back %s; no Claude credit on it." % url
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}})
    except Exception as exc:
        emit({"systemMessage": "house-rules: the credit check hit an error (%s: %s); the body was NOT read back."
                               % (type(exc).__name__, exc)})
    return 0


# Issue #178: the same credit check for writes made through the GitHub MCP tools, which never
# pass through `guard`. Only title/body/message and branch/head are read, never file content.
_GITHUB_COMMIT_TOOLS = ("push_files", "create_or_update_file")
BRANCH_DENY = (
    "House rules, credit @NAME@: `%s` is a new branch under `claude/`. Name agent branches "
    "`@PREFIX@<topic>` instead. HOUSE_RULES_ATTRIBUTION=off disables this check."
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
    # The issue-sections check (#248) and the close guard (#363) belong to the design loop; they are
    # registered on the core link and run first, as they did when they sat here.
    for _check in core.GITHUB_WRITE_HOOKS:
        if _check(payload, raw):
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
                reason = settings.fill(ATTRIBUTION_DENY % (kind, m.group(0).strip()[:60]))
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
            reason = settings.fill(BRANCH_DENY % new_branch)
    if not reason and short in _GITHUB_COMMIT_TOOLS:
        target = args.get("branch")
        if isinstance(target, str) and is_protected_branch(target, _payload_cwd(raw)):
            reason = settings.fill(PROTECTED_DENY % (target, "a file write through the GitHub tools"))
    if reason:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})
    return 0
















# ---------------------------------------------------------------------------------------
# The commit rule's obligation half. guard only judges git commands that are run, so a session
# that never runs one produced no signal at all (#97). These helpers answer the one question
# the Stop, branchnudge and audit checks share: which of these files are still uncommitted?
# ---------------------------------------------------------------------------------------











def _commit_note(uncommitted):
    is_mine, branch, note = branch_ownership()
    shown = ", ".join(uncommitted[:8]) + (" and %d more" % (len(uncommitted) - 8) if len(uncommitted) > 8 else "")
    return (
        "House rules, commit on your own branch: this turn changed %s, and git still shows "
        "them uncommitted. %s Work left uncommitted is not a checkpoint." % (shown, _branch_advice(is_mine, branch, note))
    )


core.register_session_start("profile", _agent_branch_block)
core.register_session_start("profile", _agent_identity_block)


def _scope_waiting_link(payload, field):
    return "", _waiting_scope_note(payload)


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


# The commit check of the end-of-reply dispatcher (event_handover in hook.py), moved out of it verbatim (#359).
def handover_commit_check(payload):
    """(uncommitted files, could-not-tell text or None). The commit check is independent of the evidence
    check: a turn that wrote files and left them uncommitted gets told at the end of that turn, whatever the
    reply says. Its "could not tell" is its own line - it must never be mistaken for the evidence check's."""
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
    return uncommitted, commit_could_not_tell


core.register_prompt(_scope_waiting_link)
core.register_post_tool("promptran", _promptran_waiting_link)
